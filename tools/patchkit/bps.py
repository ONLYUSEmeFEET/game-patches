"""Pure-Python BPS1 patch encoder, round-trip verifier, and checksum reporter."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

from .rom import hash_bytes


def _enc_vlq(val: int) -> bytes:
    out = bytearray()
    while True:
        x = val & 0x7F
        val >>= 7
        if val == 0:
            out.append(0x80 | x)
            return bytes(out)
        out.append(x)
        val -= 1


def _dec_vlq(buf: bytes | bytearray, pos: int) -> tuple[int, int]:
    val = 0
    shift = 1
    while True:
        b = buf[pos]
        pos += 1
        val += (b & 0x7F) * shift
        if b & 0x80:
            return val, pos
        shift <<= 7
        val += shift


def build_bps(src: bytes | bytearray, dst: bytes | bytearray, metadata: bytes = b"") -> bytes:
    """Build a BPS1 patch from `src` to `dst`."""
    src_b = bytes(src)
    dst_b = bytes(dst)
    n_src = len(src_b)
    n_dst = len(dst_b)

    bps = bytearray(b"BPS1")
    bps += _enc_vlq(n_src)
    bps += _enc_vlq(n_dst)
    bps += _enc_vlq(len(metadata))
    if metadata:
        bps += metadata

    i = 0
    while i < n_dst:
        if i < n_src and src_b[i] == dst_b[i]:
            j = i + 1
            while j < n_dst and j < n_src and src_b[j] == dst_b[j]:
                j += 1
            bps += _enc_vlq(((j - i - 1) << 2) | 0)  # SourceRead
            i = j
        else:
            j = i + 1
            while j < n_dst:
                if j >= n_src or src_b[j] != dst_b[j]:
                    j += 1
                else:
                    # Merge short matching runs (< 4 bytes) to avoid SourceRead overhead
                    k = j
                    while k < n_dst and k < n_src and src_b[k] == dst_b[k] and (k - j) < 4:
                        k += 1
                    if (k - j) < 4:
                        j = k
                    else:
                        break
            bps += _enc_vlq(((j - i - 1) << 2) | 1)  # TargetRead
            bps += dst_b[i:j]
            i = j

    src_crc = zlib.crc32(src_b) & 0xFFFFFFFF
    dst_crc = zlib.crc32(dst_b) & 0xFFFFFFFF
    bps += struct.pack("<II", src_crc, dst_crc)
    patch_crc = zlib.crc32(bps) & 0xFFFFFFFF
    bps += struct.pack("<I", patch_crc)
    return bytes(bps)


def verify_bps(
    src: bytes | bytearray,
    bps_bytes: bytes | bytearray,
    expected_dst: bytes | bytearray | None = None,
) -> bytes:
    """Validate BPS1 checksums and apply patch in memory; return reconstructed target bytes."""
    src_b = bytes(src)
    bps = bytes(bps_bytes)

    if len(bps) < 16 or bps[:4] != b"BPS1":
        raise AssertionError("Invalid BPS header")

    expected_patch_crc = struct.unpack_from("<I", bps, len(bps) - 4)[0]
    actual_patch_crc = zlib.crc32(bps[:-4]) & 0xFFFFFFFF
    if actual_patch_crc != expected_patch_crc:
        raise AssertionError(
            f"BPS patch CRC32 mismatch: expected {expected_patch_crc:08X}, got {actual_patch_crc:08X}"
        )

    src_crc_hdr, dst_crc_hdr = struct.unpack_from("<II", bps, len(bps) - 12)
    actual_src_crc = zlib.crc32(src_b) & 0xFFFFFFFF
    if actual_src_crc != src_crc_hdr:
        raise AssertionError(
            f"BPS source CRC32 mismatch: header={src_crc_hdr:08X}, actual={actual_src_crc:08X}"
        )

    pos = 4
    s_len, pos = _dec_vlq(bps, pos)
    d_len, pos = _dec_vlq(bps, pos)
    m_len, pos = _dec_vlq(bps, pos)
    pos += m_len

    if s_len != len(src_b):
        raise AssertionError(f"BPS source length mismatch: header={s_len}, actual={len(src_b)}")

    out = bytearray()
    src_rel = 0
    dst_rel = 0
    end_actions = len(bps) - 12

    while pos < end_actions:
        cmd, pos = _dec_vlq(bps, pos)
        mode = cmd & 3
        length = (cmd >> 2) + 1
        if mode == 0:  # SourceRead
            off = len(out)
            out += src_b[off : off + length]
        elif mode == 1:  # TargetRead
            out += bps[pos : pos + length]
            pos += length
        elif mode == 2:  # SourceCopy
            delta, pos = _dec_vlq(bps, pos)
            src_rel += -(delta >> 1) if (delta & 1) else (delta >> 1)
            out += src_b[src_rel : src_rel + length]
            src_rel += length
        elif mode == 3:  # TargetCopy
            delta, pos = _dec_vlq(bps, pos)
            dst_rel += -(delta >> 1) if (delta & 1) else (delta >> 1)
            for _ in range(length):
                out.append(out[dst_rel])
                dst_rel += 1

    if len(out) != d_len:
        raise AssertionError(f"BPS target length mismatch: header={d_len}, actual={len(out)}")

    actual_dst_crc = zlib.crc32(out) & 0xFFFFFFFF
    if actual_dst_crc != dst_crc_hdr:
        raise AssertionError(
            f"BPS target CRC32 mismatch: header={dst_crc_hdr:08X}, actual={actual_dst_crc:08X}"
        )

    reconstructed = bytes(out)
    if expected_dst is not None and reconstructed != bytes(expected_dst):
        raise AssertionError("BPS round-trip output does not match target ROM!")

    return reconstructed


def write_bps(
    src: bytes | bytearray,
    dst: bytes | bytearray,
    out_path: str | Path,
    metadata: bytes = b"",
) -> dict[str, str | int | Path]:
    """Generate, round-trip verify, and write a BPS1 patch file."""
    bps_bytes = build_bps(src, dst, metadata=metadata)
    verify_bps(src, bps_bytes, expected_dst=dst)

    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bps_bytes)

    return {
        "path": path,
        "size": len(bps_bytes),
        "crc32": f"{zlib.crc32(bps_bytes) & 0xFFFFFFFF:08X}",
    }


def format_checksums(
    src: bytes | bytearray,
    dst: bytes | bytearray,
    bps_info: dict[str, str | int | Path] | None = None,
) -> str:
    """Format a clean release-ready checksum summary."""
    s = hash_bytes(src)
    d = hash_bytes(dst)
    lines = [
        "Checksums & Patch Verification:",
        f"  Source ROM : {s['size']:,} B  CRC32={s['crc32']}  MD5={s['md5']}  SHA1={s['sha1']}",
        f"  Output ROM : {d['size']:,} B  CRC32={d['crc32']}  MD5={d['md5']}  SHA1={d['sha1']}",
    ]
    if bps_info is not None:
        lines.append(
            f"  BPS Patch  : {bps_info['path']} "
            f"({bps_info['size']:,} B, Patch CRC32={bps_info['crc32']}) [round-trip OK]"
        )
    return "\n".join(lines)
