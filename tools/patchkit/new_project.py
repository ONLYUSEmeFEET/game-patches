#!/usr/bin/env python3
"""Scaffold a new ROM hack project wired into the shared BPS-only patchkit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECT_CONTEXT_TEMPLATE = """# {title} — Project Context

> Single source of truth for reverse-engineered addresses, hardware rules, code caves, and build/test commands.

## 1. Target Platform & Toolchain
- **System**: {system}
- **CPU / ISA**: {cpu}
- **Display / Tile Format**: [e.g., 8x8 2bpp chunky LE / 2bpp planar / 4bpp]
- **Palette Format**: [e.g., 12-bit 0BGR LE, index 0 = transparent]
- **Assembler**: [command / env var]
- **Build Command**: `python {slug}/build_patch.py`

## 2. Clean Source ROM
- **Filename**: `[Exact No-Intro / Redump filename]`
- **Size**: `[bytes]`
- **CRC32**: `[XXXXXXXX]`
- **MD5**: `[...]`
- **SHA-1**: `[...]`

## 3. Code & Data Caves (With Provenance)
| Range | Kind | Capacity | Provenance (How Verified Unused) | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `0x000000..0x000000` | cave | `0 B` | [CDL trace / pointer scan / ROM padding] | [description] |

## 4. Key RAM Addresses & Structs
- `0xXXXX`: [purpose]

## 5. Hardware Budgets & Display Limits
- **VBlank / DMA Budget**: [cycles or bytes/frame]
- **Sprite Limits**: [max sprites total / max per scanline]
- **Palette Sharing Warnings**: [shared HUD/object/water palettes]

## 6. Known Hardware / Engine Quirks & Edge Cases
- [Document confirmed facts vs. hypotheses]

## 7. Automated Emulator QA
- **Runner / Suite**: [e.g., `python -m patchkit.qa --suite {slug}/qa_suite.json --rom ...`]
- **Manual Save-State Checks**: [core mechanic, H/V-flip, damage/water/boss/goal transitions]
"""

BUILD_SCRIPT_TEMPLATE = '''#!/usr/bin/env python3
"""Build & verify {title} (BPS-only via shared patchkit)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

from patchkit import (
    assert_and_patch,
    check_version_sync,
    format_checksums,
    load_clean_rom,
    verify_diff,
    write_bps,
)

VERSION = "0.1"
EXPECTED_SRC_CRC32 = None  # Set to "XXXXXXXX" once verified
EXPECTED_SRC_SIZE = None   # Set to exact clean ROM byte length


def main() -> int:
    parser = argparse.ArgumentParser(description="Build {title} ROM & BPS patch.")
    parser.add_argument("--src", type=Path, required=True, help="Clean base ROM path")
    parser.add_argument("--out-rom", type=Path, required=True, help="Patched ROM output path")
    parser.add_argument("--out-bps", type=Path, required=True, help="BPS patch output path")
    args = parser.parse_args()

    src_bytes = bytes(load_clean_rom(args.src, EXPECTED_SRC_CRC32, EXPECTED_SRC_SIZE))
    rom = bytearray(src_bytes)

    # --- Apply guarded patches here ---
    # assert_and_patch(rom, 0x000000, b"\\x00", b"\\x01", label="example")

    verify_diff(src_bytes, rom, PROJECT_DIR / "allowed_ranges.json")

    args.out_rom.parent.mkdir(parents=True, exist_ok=True)
    args.out_rom.write_bytes(rom)
    bps_info = write_bps(src_bytes, rom, args.out_bps)
    print(format_checksums(src_bytes, rom, bps_info))

    for warning in check_version_sync(VERSION, [REPO_ROOT / "README.md"]):
        print(f"WARNING: {{warning}}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a new game-patches project.")
    parser.add_argument("slug", help="Folder name (e.g., my-new-hack)")
    parser.add_argument("--title", required=True, help="Human-readable hack title")
    parser.add_argument("--system", required=True, help="Target console (e.g., Neo Geo Pocket Color)")
    parser.add_argument("--cpu", required=True, help="Target CPU/ISA (e.g., Toshiba TLCS-900/H)")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    proj_dir = repo_root / args.slug
    if proj_dir.exists():
        raise SystemExit(f"Project directory already exists: {proj_dir}")

    (proj_dir / "src").mkdir(parents=True, exist_ok=True)
    (proj_dir / "PROJECT_CONTEXT.md").write_text(
        PROJECT_CONTEXT_TEMPLATE.format(
            title=args.title, system=args.system, cpu=args.cpu, slug=args.slug
        ),
        encoding="utf-8",
    )
    (proj_dir / "allowed_ranges.json").write_text(
        json.dumps({"ranges": []}, indent=2) + "\n",
        encoding="utf-8",
    )
    (proj_dir / "build_patch.py").write_text(
        BUILD_SCRIPT_TEMPLATE.format(title=args.title),
        encoding="utf-8",
    )

    print(f"Scaffolded project at: {proj_dir}")
    print("Next: fill in PROJECT_CONTEXT.md and allowed_ranges.json (already whitelisted in .gitignore).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
