"""Clean ROM loading, checksum verification, and guarded byte patching."""

from __future__ import annotations

import hashlib
import zlib
from pathlib import Path


def hash_bytes(data: bytes | bytearray) -> dict[str, str | int]:
    """Return size, CRC32, MD5, and SHA-1 hashes for a byte buffer."""
    raw = bytes(data)
    return {
        "size": len(raw),
        "crc32": f"{zlib.crc32(raw) & 0xFFFFFFFF:08X}",
        "md5": hashlib.md5(raw).hexdigest().upper(),
        "sha1": hashlib.sha1(raw).hexdigest().upper(),
    }


def load_clean_rom(
    path: str | Path,
    expected_crc32: str | None = None,
    expected_size: int | None = None,
) -> bytearray:
    """Load an unmodified source ROM into a mutable bytearray after integrity checks."""
    rom_path = Path(path)
    if not rom_path.is_file():
        raise FileNotFoundError(f"Clean source ROM not found: {rom_path}")

    raw = rom_path.read_bytes()
    info = hash_bytes(raw)

    if expected_size is not None and info["size"] != expected_size:
        raise ValueError(
            f"Source ROM size mismatch for {rom_path.name}: "
            f"expected {expected_size} bytes (0x{expected_size:X}), "
            f"got {info['size']} bytes (0x{info['size']:X})"
        )

    if expected_crc32 is not None:
        want = expected_crc32.strip().upper().removeprefix("0X")
        if info["crc32"] != want:
            raise ValueError(
                f"Source ROM CRC32 mismatch for {rom_path.name}: "
                f"expected {want}, got {info['crc32']} "
                f"(MD5={info['md5']}, SHA1={info['sha1']})"
            )

    return bytearray(raw)


def assert_and_patch(
    rom: bytearray,
    offset: int,
    expected: bytes,
    replacement: bytes,
    label: str = "",
) -> None:
    """Verify exact original bytes at `offset` before writing `replacement`."""
    if len(expected) != len(replacement):
        raise ValueError(
            f"Patch length mismatch at 0x{offset:06X}"
            + (f" ({label})" if label else "")
            + f": expected={len(expected)} B, replacement={len(replacement)} B"
        )

    end = offset + len(expected)
    actual = bytes(rom[offset:end])
    if actual != expected:
        raise AssertionError(
            f"Original byte mismatch at 0x{offset:06X}..0x{end - 1:06X}"
            + (f" ({label})" if label else "")
            + f":\n  expected: {expected.hex(' ')}\n  actual  : {actual.hex(' ')}"
        )

    rom[offset:end] = replacement
