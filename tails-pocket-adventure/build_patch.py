#!/usr/bin/env python3
"""Build & verify Tails Pocket Adventure (BPS-only via shared patchkit)."""

from __future__ import annotations

import argparse
import os
import struct
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))
sys.path.insert(0, str(PROJECT_DIR / "src"))

from assets import (
    TileAndMetaAllocator,
    pack_chaos_gg_flying_frames,
    pack_compact_flying_frames,
    pack_flying_frames,
    pack_ngpc_native_flying_frames,
    pack_ngpc_style_flying_frames,
    patch_chaos_emerald_text,
    patch_goalpost_from_sheet,
    patch_hud_tails_head,
    patch_special_stage_standing,
    patch_title_card_silhouettes,
    patch_title_tails_text,
    patch_tornado_sonic_cockpit,
)
from patchkit import (
    assemble_asw,
    assert_and_patch,
    check_version_sync,
    format_checksums,
    load_clean_rom,
    verify_diff,
    write_bps,
    write_sym_file,
)

# Single source of truth for release version & clean base ROM
VERSION = "3.3"
EXPECTED_SRC_CRC32 = "356F0849"
EXPECTED_SRC_SIZE = 2_097_152

DEFAULT_ROM_DIR = REPO_ROOT / "roms"
DEFAULT_SRC_ROM = DEFAULT_ROM_DIR / "Sonic The Hedgehog - Pocket Adventure (World).ngc"
DEFAULT_OUT_ROM = DEFAULT_ROM_DIR / f"Tails Pocket Adventure v{VERSION}.ngc"
DEFAULT_BPS_PATH = PROJECT_DIR / f"Tails Pocket Adventure v{VERSION}.bps"
DEFAULT_SHEETS_DIR = PROJECT_DIR / "sprite_sheets_to_mod"
DEFAULT_ASW = os.environ.get("NGP_ASW", r"s:\Misc Gaming\NGPDev\aswcurr\bin\asw.exe")
DEFAULT_P2BIN = os.environ.get("NGP_P2BIN", r"s:\Misc Gaming\NGPDev\aswcurr\bin\p2bin.exe")


def tlcs900_call(cpu_addr: int) -> bytes:
    """Encode a 4-byte TLCS-900/H 24-bit absolute CALL (opcode 0x1D + LE24)."""
    if not (0 <= cpu_addr <= 0xFFFFFF):
        raise ValueError(f"TLCS-900/H CALL target out of 24-bit range: 0x{cpu_addr:X}")
    return bytes([0x1D, cpu_addr & 0xFF, (cpu_addr >> 8) & 0xFF, (cpu_addr >> 16) & 0xFF])


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Tails Pocket Adventure ROM and BPS patch.")
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC_ROM, help="Clean base ROM path")
    parser.add_argument("--out-rom", type=Path, default=DEFAULT_OUT_ROM, help="Patched ROM output path")
    parser.add_argument("--out-bps", type=Path, default=DEFAULT_BPS_PATH, help="BPS patch output path")
    parser.add_argument(
        "--sheet",
        type=Path,
        default=DEFAULT_SHEETS_DIR / "tails_flying_ngpc_style_1x.png",
        help="Tails flying sprite sheet path",
    )
    parser.add_argument("--asw", type=str, default=DEFAULT_ASW, help="Path to asw.exe")
    parser.add_argument("--p2bin", type=str, default=DEFAULT_P2BIN, help="Path to p2bin.exe")
    args = parser.parse_args()

    src_bytes = bytes(
        load_clean_rom(args.src, expected_crc32=EXPECTED_SRC_CRC32, expected_size=EXPECTED_SRC_SIZE)
    )
    data = bytearray(src_bytes)

    # 1. Enable Playable Tails in Single Player (character flag 0x0067B1 = 0x04)
    assert_and_patch(
        data,
        0x03AEBE,
        b"\x21\x00\x1d\x1b\xd3\x39",
        b"\x21\x04\x1d\x1b\xd3\x39",
        label="Enable Playable Tails in Single Player",
    )

    # 2. Pack Custom Flying Sprites (4 Active + 2 Tired NGPC-style), Goalpost, Chaos Emerald, Title Screen
    alloc = TileAndMetaAllocator()
    custom_frame_ptrs = pack_ngpc_style_flying_frames(args.sheet, alloc)
    patch_goalpost_from_sheet(data, DEFAULT_SHEETS_DIR / "goalpost_signpost_1x.png", alloc)
    patch_chaos_emerald_text(data, DEFAULT_SHEETS_DIR / "tails_chaos_emerald_1x.png", alloc)
    patch_title_card_silhouettes(data, DEFAULT_SHEETS_DIR / "title_card_silhouette_1x.png", alloc)
    patch_tornado_sonic_cockpit(data, DEFAULT_SHEETS_DIR / "tornado_pilot_1x.png", alloc)
    patch_special_stage_standing(data, DEFAULT_SHEETS_DIR / "special_stage_tails_9frames_1x.png", alloc)
    patch_title_tails_text(data, DEFAULT_SHEETS_DIR / "title_screen_tails_1x.png", alloc)

    tile_blob = alloc.tile_blob
    assert len(tile_blob) <= 0x2000, f"Custom tile cave overflow: {len(tile_blob)} > 8192 B"
    data[0x1FB000 : 0x1FB000 + len(tile_blob)] = tile_blob

    assert len(alloc.meta_blob) <= 0x1000, f"Metasprite cave overflow: {len(alloc.meta_blob)} > 4096 B"
    data[0x1FD000 : 0x1FD000 + len(alloc.meta_blob)] = alloc.meta_blob

    # 3. Relocate & Extend Character Frame Table (0x1D35F4 -> 0x1FE000, 145 entries)
    table_fixes = {
        0x50: (0xBC94, 0xBD04),  # Hanging 4
        0x51: (0xBCB6, 0xBD06),  # Hanging 5
        0x52: (0xBCE0, 0xBD10),  # Hanging 6
        0x54: (0xB528, 0xB54E),  # Standing transition
        0x56: (0xB48E, 0xB4F8),  # Idle 1
        0x57: (0xB4B0, 0xB506),  # Idle 2
        0x58: (0xB4CA, 0xB514),  # Idle 3
        0x71: (0xB528, 0xB54E),  # Standing front
    }
    for idx, (tb, to) in table_fixes.items():
        struct.pack_into("<2H", data, 0x1D35F4 + idx * 8 + 4, tb, to)

    data[0x1FE000 : 0x1FE000 + 133 * 8] = data[0x1D35F4 : 0x1D35F4 + 133 * 8]
    for i, (b_moff, o_moff) in enumerate(custom_frame_ptrs):
        struct.pack_into("<4H", data, 0x1FE000 + (0x85 + i) * 8, b_moff, o_moff, b_moff, o_moff)

    assert_and_patch(
        data,
        0x1D3A31,
        b"\xd9\xcf\x84\x00\x6b\xe5\x41\xf4\x35\x3d\x00",
        b"\xd9\xcf\x91\x00\x6b\xe5\x41" + struct.pack("<I", 0x003FE000),
        label="Character Frame Table count & pointer",
    )

    # 4. Assemble Sequentially-Packed TLCS-900/H Cave & Auto-Resolve Hook Targets
    asm_build = assemble_asw(
        PROJECT_DIR / "src" / "main.asm",
        asw_bin=args.asw,
        p2bin_bin=args.p2bin,
    )
    sym = asm_build.symbols
    assert len(asm_build.payload) <= 0x400, (
        f"ASM cave overflow: {len(asm_build.payload)} B exceeds 1024 B limit"
    )
    data[0x1FAC00 : 0x1FAC00 + len(asm_build.payload)] = asm_build.payload

    assert_and_patch(
        data,
        0x03BFFC,
        b"\xeb\xa3\xd5\xf1\x23\xeb\xee\x04\xed\x83",
        tlcs900_call(sym["tile_stream_hook"]) + b"\x00" * 6,
        label="Hook 1: VBlank Tile Streamer",
    )
    assert_and_patch(
        data,
        0x03C081,
        b"\x9c\x08\x26\xd5\xf9\x21",
        tlcs900_call(sym["oam_meta_hook"]) + b"\x00" * 2,
        label="Hook 2: Shadow OAM Metasprite Reader",
    )
    assert_and_patch(
        data,
        0x19AAFD,
        b"\x1d\x96\xd2\x39\x30\x80\x00\x6f\x03\x30\x20\x00",
        tlcs900_call(sym["flight_hook"]) + b"\x68\x06" + b"\x00" * 6,
        label="Hook 3: Player 1 Airborne Loop",
    )
    assert_and_patch(
        data,
        0x19C7EC,
        b"\x1d\xe4\xd4\x39",
        tlcs900_call(sym["hide_tails_hook"]),
        label="Hook 4: Extra Tails Draw Call",
    )
    assert_and_patch(data, 0x19DC21, b"\x6e\x13", b"\x00\x00", label="HUD palette mode-3 skip NOP")
    assert_and_patch(data, 0x19DC27, b"\xc9\xd8\x6e\x0b", b"\xc9\xd8\x66\x0b", label="HUD palette Tails branch")
    assert_and_patch(
        data,
        0x03B203,
        b"\xc1\x41\x4d\x21\xc9\xcc\x1f",
        tlcs900_call(sym["title_debug_hook"]) + b"\x00" * 3,
        label="Hook 5: Title Screen Option -> Debug/Level Select",
    )
    assert_and_patch(
        data,
        0x1CE458,
        b"\xd8\xac\x23\x00\x1d\xb3\xe3\x23\xd8\xad\x23\x01\x1d\xb3\xe3\x23",
        tlcs900_call(sym["signpost_pal_hook"]) + b"\x00" * 12,
        label="Hook 6: Goalpost Signpost Palette",
    )
    assert_and_patch(
        data,
        0x1CA5DD,
        b"\xd8\xaf\x23\x01\x1d\xb3\xe3\x23",
        tlcs900_call(sym["ss_tails_pal_hook"]) + b"\x00" * 4,
        label="Hook 7a: Special Stage Intro Pose Palette",
    )
    assert_and_patch(
        data,
        0x1CA6AC,
        b"\xd8\xaf\x23\x01\x1d\xb3\xe3\x23",
        tlcs900_call(sym["ss_tails_pal_hook"]) + b"\x00" * 4,
        label="Hook 7b: Special Stage Win Pose Palette",
    )

    # 5. SFX Volume, HUD Head, and 1UP Monitor Layer
    assert_and_patch(
        data, 0x1EAD8A, b"\x38\x0f\x01\x0a", b"\x38\x08\x01\x0a", label="SFX 0x00A2 volume (0x0F->0x08)"
    )
    patch_hud_tails_head(data)
    assert_and_patch(data, 0x1D48B7, b"\x04\x01\xe4\x28", b"\x04\x00\xe4\x28", label="1UP Monitor layer #1")
    assert_and_patch(data, 0x1D496B, b"\x04\x01\xe4\x28", b"\x04\x00\xe4\x28", label="1UP Monitor layer #2")

    # 6. Single-Player Tornado Pilot & Wing-Rider Swap
    struct.pack_into("<H", data, 0x03D372 + 4, 0x0F55)
    assert_and_patch(
        data,
        0x1E727D,
        b"\xd8\xa8\x23\x00\x1d\xb3\xe3\x23\xd8\xaf\x23\x01\x1d\xb3\xe3\x23",
        tlcs900_call(sym["ending_tails_pal"]) + b"\x68\x0a" + b"\x00" * 10,
        label="Ending Cutscene Tails Palette hook",
    )
    ending_frame_map = {
        0x0B7C: 0xB528, 0x0D7C: 0xB54E,
        0x0CBE: 0xABFC, 0x0E46: 0xA966,
        0x0CE4: 0xB276, 0x0E54: 0xABA8,
        0x0D0A: 0xB298, 0x0E62: 0xABAA,
        0x0D30: 0xB2BA, 0x0E70: 0xABAC,
        0x0D56: 0xADE6, 0x0E7E: 0xABAE,
    }
    for off in range(0x1E7661, 0x1E76E5):
        if data[off] == 0x04 and data[off + 1] in (0x80, 0x81) and data[off + 4] == 0x00 and data[off + 5] == 0x00:
            old_m = struct.unpack_from("<H", data, off + 2)[0]
            if old_m in ending_frame_map:
                struct.pack_into("<H", data, off + 2, ending_frame_map[old_m])

    struct.pack_into("<3H", data, 0x03C748 + 0x024A * 6, 0x0FFF, 0x04BF, 0x008F)
    struct.pack_into("<3H", data, 0x03C748 + 0x0273 * 6, 0x08DF, 0x0D20, 0x0800)

    # 7. NGPC ROM Header Cart Title (12 bytes at 0x24..0x2F)
    assert data[0x00:0x1C] == b"COPYRIGHT BY SNK CORPORATION"
    assert_and_patch(data, 0x24, b"SONIC POCKET", b"TAILS POCKET", label="NGPC Header Title")

    # 8. Diff Gate, ROM + .sym Output, BPS Round-Trip Verification & Version Sync Check
    dst_bytes = bytes(data)
    verify_diff(src_bytes, dst_bytes, PROJECT_DIR / "allowed_ranges.json")

    args.out_rom.parent.mkdir(parents=True, exist_ok=True)
    args.out_rom.write_bytes(dst_bytes)
    sym_path = write_sym_file(sym, args.out_rom.with_suffix(".sym"), constants=asm_build.constants)

    print(f"Successfully built v{VERSION} ROM: {args.out_rom} ({len(dst_bytes)} bytes)")
    print(f"  Debugger symbols: {sym_path} ({len(sym)} code labels, {len(asm_build.constants)} constants)")
    print(f"  Custom ASM + fly_script at 0x1fac00: {len(asm_build.payload)} / 1024 bytes")
    print(f"  Custom 8x8 2bpp tiles at 0x1fb000: {len(alloc.unique_tiles)} tiles ({len(tile_blob)} bytes)")
    print(f"  Custom metasprites at 0x1fd000: {len(custom_frame_ptrs) * 2} metasprites ({len(alloc.meta_blob)} bytes)")

    bps_info = write_bps(src_bytes, dst_bytes, args.out_bps)
    print(format_checksums(src_bytes, dst_bytes, bps_info))

    for warning in check_version_sync(
        VERSION, [PROJECT_DIR / "Tails Pocket Adventure-README.md", REPO_ROOT / "README.md"]
    ):
        print(f"WARNING: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
