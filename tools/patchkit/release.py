"""Single-source-of-truth release checksum formatter and README version checker."""

from __future__ import annotations

from pathlib import Path

from .rom import hash_bytes


def format_readme_checksums(
    *,
    src_name: str,
    src_bytes: bytes | bytearray,
    dst_name: str,
    dst_bytes: bytes | bytearray,
    bps_info: dict[str, str | int | Path],
) -> str:
    """Format a standardized, copy-ready README Checksums (Verified) section."""
    s = hash_bytes(src_bytes)
    d = hash_bytes(dst_bytes)
    bps_name = Path(bps_info["path"]).name
    return "\n".join(
        [
            "Checksums (Verified)",
            "--------------------",
            f"Source ROM: {src_name} ({s['size']:,} bytes)",
            f"  CRC32 : {s['crc32']}",
            f"  MD5   : {s['md5']}",
            f"  SHA-1 : {s['sha1']}",
            "",
            f"Patched ROM: {dst_name} ({d['size']:,} bytes)",
            f"  CRC32 : {d['crc32']}",
            f"  MD5   : {d['md5']}",
            f"  SHA-1 : {d['sha1']}",
            "",
            "Patch File (BPS):",
            f"  {bps_name} ({bps_info['size']:,} bytes, Patch CRC32: {bps_info['crc32']})",
        ]
    )


def check_version_sync(version: str, readme_paths: list[str | Path]) -> list[str]:
    """Return warning messages for any README that does not mention `v{version}`."""
    needle = f"v{version.lstrip('vV')}"
    warnings: list[str] = []
    for p in readme_paths:
        path = Path(p)
        if not path.is_file():
            warnings.append(f"README not found: {path}")
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        if needle not in content:
            warnings.append(f"Version drift: '{needle}' not found in {path.name}")
    return warnings
