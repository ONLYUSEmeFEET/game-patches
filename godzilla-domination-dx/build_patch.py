#!/usr/bin/env python3
"""Build & verify Godzilla: Domination! DX (AG4J -> English + 8 MB Classic/Tokyo S.O.S. Switcher)."""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

from keystone import KS_ARCH_ARM, KS_MODE_THUMB, Ks

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

VERSION = "1.0"
EXPECTED_JPN_CRC32 = "3157A4FC"
EXPECTED_JPN_SIZE = 0x400000
EXPECTED_USA_CRC32 = "EADE083F"
EXPECTED_USA_SIZE = 0x400000
EXPANDED_ROM_SIZE = 0x800000

JPN_ARCHIVE_BASE = 0x111A18
USA_ARCHIVE_BASE = 0x111D38

CAVE_BASE = 0x3D2D00
EXPANSION_BASE = 0x400000
SKIN_MASK_ADDR        = 0x0203FFFE  # u8 bitmask: b0=GZ, b1=MG, b2=MO, b3=MKG, b4=FireRodan, b5=PurpleMegalon
FLAG_HIDE_PTAG_ADDR   = 0x0203FFFD  # u8: 0 = 1P-4P Tag ON (JPN), 1 = OFF (USA)
FLAG_BONUS_STAGE_ADDR = 0x0203FFFC  # u8: 0 = Bonus Stages OFF (JPN), 1 = ON (USA)
FLAG_STAGE_US_ADDR    = 0x0203FFFB  # u8: 0 = Stage Order JP (Random), 1 = US (Fixed)
BONUS_DONE_MASK_ADDR  = 0x0203FFFA  # u8: bit0=BONUS0 done, bit1=BONUS1 done
OPTIONS_PAGE_ADDR     = 0x0203FFF9  # u8: 0 = Standard Options, 1 = DX Options (1P TAG / BONUS / STAGE)
NIGHT_TOKYO_FLAG_ADDR = 0x0203FFF8  # u8: 1 = Active Custom Mode battle is Nighttime Tokyo ("Tokyo 1")

# Movie-accurate 16-color Mini Mecha-King Ghidorah palette (RGB555) for OBJ Pal 3 (Option B v3):
#   idx 1..6  = movie gold / bronze-gold solar wings & outer scales
#   idx 7     = exact emerald-green middle-head visor & chest gem (48,184,144 = 0x4AE6)
#   idx 8..11 = warm titanium / champagne-silver cybernetic armor (middle head, neck, full chest, wing lining)
#   idx 12    = electric cyan kick-slash energy arc & claws
#   idx 13    = pure white specular & teeth
#   idx 15    = crimson red eyes for the two organic gold heads (248,8,8 = 0x043F)
MKG_PAL3_RGB555: tuple[int, ...] = (
    0x2C40, 0x5FFF, 0x377F, 0x1EBE, 0x11F5, 0x092E, 0x0487, 0x4AE6,
    0x77DF, 0x5EF7, 0x4231, 0x254A, 0x7708, 0x7FFF, 0x0000, 0x043F,
)

# Custom 16-color Fire Rodan palette (RGB555) for OBJ Pal 6:
#   idx 1..5 = blazing crimson/scarlet body, idx 6..10 = fiery gold-orange wings/belly, idx 12..13 = golden beak
FIRE_RODAN_PAL6_RGB555: tuple[int, ...] = (
    0x2C40, 0x1F3F, 0x019F, 0x009D, 0x0037, 0x0010, 0x2BFF, 0x039F,
    0x023F, 0x0119, 0x006F, 0x7FFF, 0x1BFF, 0x029F, 0x0000, 0x4E73,
)

# Custom 16-color Eva Unit-01 Purple Megalon palette (RGB555) for OBJ Pal 7:
#   exact swap of Megalon's green carapace (1..5) <-> purple body/wings (6..10)
PURPLE_MEGALON_PAL7_RGB555: tuple[int, ...] = (
    0x2C40, 0x7FBF, 0x76BA, 0x5DD4, 0x44CD, 0x2406, 0x7FF9, 0x6790,
    0x4EE8, 0x3620, 0x1960, 0x03FF, 0x02FF, 0x01DF, 0x0000, 0x4E73,
)

# Verified 1-to-1 localized UI sprites (JPN archive idx -> USA English archive idx)
UI_SPRITE_REDIRECTS: list[tuple[int, int, str]] = [
    (115, 128, "ui_115_from_usa_128"),
    (214, 133, "ui_hud_banners_ready_pause"),
    (219, 146, "ui_219_from_usa_146"),
    (220, 93,  "ui_custom_mode_title_220"),
    (221, 204, "ui_custom_mode_header"),
    (222, 48,  "ui_monster_select_header"),
    (223, 57,  "ui_results_total_score_223"),
    (224, 122, "ui_224_from_usa_122"),
    (225, 98,  "ui_225_from_usa_98"),
    (226, 56,  "ui_226_from_usa_56"),
    (227, 97,  "ui_227_from_usa_97"),
    (232, 129, "ui_232_from_usa_129"),
    (235, 198, "ui_235_from_usa_198"),
    (238, 197, "ui_title_licensed_by_nintendo_238"),
    (239, 137, "ui_239_from_usa_137"),
    (241, 207, "ui_rage_attacks_level_241"),
    (242, 86,  "ui_winner_monster_nameplates_242"),
    (390, 364, "ui_press_start_390"),
    (391, 366, "ui_licensed_by_nintendo_391"),
]

# Multi-monster shared sprite packs composited across all 16 combinations of
# SKIN_MASK = (Godzilla << 0) | (Mechagodzilla << 1) | (Mothra << 2) | (MKG << 3):
#   (jpn_idx, usa_idx, {frame_idx: (bit_index, alt_src_frame_idx)}, label)
# Note: alt_src_frame_idx lets MKG (bit 3) map King Ghidorah's slot (frame 1) directly to
# official WayForward Mecha-King Ghidorah art (frame 6 in portraits/giant VS, frame 8 in nameplates)!
COMPOSITE_SKIN_PACKS: list[tuple[int, int, dict[int, tuple[int, int]], str]] = [
    (
        212,
        73,
        {
            6: (3, 6), 7: (3, 7), 8: (3, 8), 9: (3, 9), 10: (3, 10), 11: (3, 11),
            21: (1, 21), 22: (1, 22), 23: (1, 23),
            26: (2, 26), 27: (2, 27), 28: (2, 28), 29: (2, 29),
        },
        "monster_select_small_icons",
    ),
    (229, 147, {1: (3, 8), 3: (1, 3)},                                                                       "monster_select_nameplates_15frame"),
]

# Verified 1-to-1 frame permutations (AG4J frame index -> AG4E USA frame index).
# Every permutation is a complete bijection verified by silhouette IoU + visual contact sheets.
# Hitbox/hurtbox 24-byte frame headers are preserved from AG4J so gameplay stays 100% identical.
GODZILLA_JPN_TO_USA: list[int] = (
    [63, 64]                    # JPN  0..1  -> USA 63..64
    + list(range(25, 31))       # JPN  2..7  -> USA 25..30 (Idle / Walk)
    + list(range(0, 25))        # JPN  8..32 -> USA  0..24 (Roar / Attacks)
    + list(range(31, 44))       # JPN 33..45 -> USA 31..43
    + [60, 61, 62]              # JPN 46..48 -> USA 60..62
    + list(range(44, 60))       # JPN 49..64 -> USA 44..59
)
MECHAGODZILLA_JPN_TO_USA: list[int] = (
    [0, 1, 2]                   # JPN  0..2  -> USA  0..2  (Shield Block)
    + [50]                      # JPN  3     -> USA 50
    + list(range(3, 11))        # JPN  4..11 -> USA  3..10 (Walk)
    + [51, 52, 53]              # JPN 12..14 -> USA 51..53 (Punch)
    + list(range(69, 76))       # JPN 15..21 -> USA 69..75 (Chest Beam / Mega-Buster)
    + list(range(11, 19))       # JPN 22..29 -> USA 11..18
    + [68, 67]                  # JPN 30..31 -> USA 68..67 (Shoulder Flash)
    + list(range(19, 27))       # JPN 32..39 -> USA 19..26
    + [54, 55]                  # JPN 40..41 -> USA 54..55
    + list(range(46, 50))       # JPN 42..45 -> USA 46..49
    + list(range(76, 81))       # JPN 46..50 -> USA 76..80
    + [56, 57, 58]              # JPN 51..53 -> USA 56..58
    + [33, 34]                  # JPN 54..55 -> USA 33..34
    + list(range(81, 86))       # JPN 56..60 -> USA 81..85
    + list(range(59, 67))       # JPN 61..68 -> USA 59..66
    + list(range(35, 46))       # JPN 69..79 -> USA 35..45
    + list(range(27, 33))       # JPN 80..85 -> USA 27..32
)
MOTHRA_JPN_TO_USA: list[int] = (
    [28, 29, 30, 31, 32, 40, 41]  # JPN  0..6  -> USA 28..32, 40..41 (Flight / Dive)
    + [6, 7]                      # JPN  7..8  -> USA  6..7
    + [0, 1, 2]                   # JPN  9..11 -> USA  0..2
    + [3, 4, 5]                   # JPN 12..14 -> USA  3..5
    + list(range(8, 18))          # JPN 15..24 -> USA  8..17
    + list(range(18, 23))         # JPN 25..29 -> USA 18..22
    + [33, 34]                    # JPN 30..31 -> USA 33..34
    + [23, 24]                    # JPN 32..33 -> USA 23..24
    + [37, 38, 39]                # JPN 34..36 -> USA 37..39
    + [25, 26, 27]                # JPN 37..39 -> USA 25..27
    + [35, 36]                    # JPN 40..41 -> USA 35..36
)

CLASSIC_REMAPPED_MONSTERS: list[tuple[int, int, list[int], str]] = [
    (32, 27, GODZILLA_JPN_TO_USA,      "godzilla_classic_remapped"),
    (39, 34, MECHAGODZILLA_JPN_TO_USA, "mechagodzilla_classic_remapped"),
    (51, 46, MOTHRA_JPN_TO_USA,        "mothra_classic_remapped"),
]


def get_archive_entry(data: bytes, base: int, idx: int) -> bytes:
    first_off = struct.unpack_from("<I", data, base + 4)[0]
    count = first_off // 4
    off = struct.unpack_from("<I", data, base + idx * 4)[0]
    end_off = len(data.rstrip(b"\x00")) - base
    for j in range(idx + 1, count):
        o2 = struct.unpack_from("<I", data, base + j * 4)[0]
        if o2 > off:
            end_off = o2
            break
    return data[base + off : base + end_off]


def encode_thumb_bl(src_addr: int, dst_addr: int) -> bytes:
    offset = dst_addr - (src_addr + 4)
    if not (-0x400000 <= offset <= 0x3FFFFE) or (offset & 1):
        raise ValueError(f"Thumb BL out of range: 0x{src_addr:08X} -> 0x{dst_addr:08X}")
    hi = 0xF000 | ((offset >> 12) & 0x7FF)
    lo = 0xF800 | ((offset >> 1) & 0x7FF)
    return struct.pack("<2H", hi, lo)


def assemble_thumb(code: str, base_addr: int) -> bytes:
    ks = Ks(KS_ARCH_ARM, KS_MODE_THUMB)
    encoding, _ = ks.asm(code, base_addr)
    if encoding is None:
        raise RuntimeError(f"Keystone failed to assemble at 0x{base_addr:08X}")
    return bytes(encoding)


def _rewrite_story_dialogue_table(base_table: bytes, replacements_by_sec: dict[int, tuple[str, str]]) -> bytes:
    """Safely replace player monster names inside specific Story Mode '#' sections while preserving
    the exact 493-line layout, '#' marker indices, and <= 24-char Connie Matsu dialogue box width.
    """
    n_lines = len(base_table) // 32
    lines = [base_table[i * 32 : (i + 1) * 32].rstrip(b"\x00").decode("ascii") for i in range(n_lines)]

    # Locate '#' section spans
    sec_starts = [i for i, ln in enumerate(lines) if ln.startswith("#")]
    sec_spans = []
    for si, st in enumerate(sec_starts):
        en = sec_starts[si + 1] if si + 1 < len(sec_starts) else n_lines - 1
        sec_spans.append((st, en))

    def wrap_paragraph(text: str, max_w: int, max_lines: int) -> list[str]:
        words = text.split()
        out_l: list[str] = []
        cur = ""
        for w in words:
            if not cur:
                cur = w
            elif len(cur) + 1 + len(w) <= max_w:
                cur += " " + w
            else:
                out_l.append(cur)
                cur = w
        if cur:
            out_l.append(cur)
        # If tight, allow up to 26 chars (dialogue box safely fits 26 chars) before truncating
        if len(out_l) > max_lines and max_w < 26:
            return wrap_paragraph(text, 26, max_lines)
        while len(out_l) > max_lines:
            # Merge last two lines if possible
            tail = out_l.pop()
            if len(out_l[-1]) + 1 + len(tail) <= 28:
                out_l[-1] = out_l[-1] + " " + tail
            else:
                out_l[-1] = (out_l[-1] + " " + tail)[:28]
        while len(out_l) < max_lines:
            out_l.append("")
        return out_l

    for sec_idx, (old_name, new_name) in replacements_by_sec.items():
        st, en = sec_spans[sec_idx]
        # Split section body (st+1 .. en-1) into non-empty paragraphs (preserving blank page breaks!)
        i = st + 1
        while i < en:
            if not lines[i]:
                i += 1
                continue
            j = i
            while j < en and lines[j]:
                j += 1
            para = " ".join(lines[i:j])
            # Protect "GODZILLA WATCH" and "GODZILLA COUNTER" from replacement
            prot = para.replace("GODZILLA WATCH", "__GWN__").replace("GODZILLA COUNTER", "__GCF__")
            if old_name in prot:
                updated = prot.replace(old_name, new_name)
                if old_name == "KING GHIDORAH" and "GHIDORAH" in updated.replace(new_name, ""):
                    # Catch shortened "GHIDORAH HAS JUST BEEN" in sec 10
                    updated = updated.replace("MECHA-GHIDORAH", "__MKG__").replace("GHIDORAH", new_name).replace("__MKG__", new_name)
                updated = updated.replace("__GWN__", "GODZILLA WATCH").replace("__GCF__", "GODZILLA COUNTER")
                wrapped = wrap_paragraph(updated, 24, j - i)
                lines[i:j] = wrapped
            elif old_name == "KING GHIDORAH" and "GHIDORAH" in prot:
                updated = prot.replace("GHIDORAH", new_name).replace("__GWN__", "GODZILLA WATCH").replace("__GCF__", "GODZILLA COUNTER")
                wrapped = wrap_paragraph(updated, 24, j - i)
                lines[i:j] = wrapped
            i = j

    out = bytearray()
    for ln in lines:
        raw = ln.encode("ascii")[:31]
        out.extend(raw.ljust(32, b"\x00"))
    assert len(out) == len(base_table)
    return bytes(out)


def build_english_text_tables(usa_bytes: bytes) -> tuple[bytes, bytes]:
    """Build (eng_text_base, eng_text_alt) — identical 493 x 32-byte layout & '#' indices:
      - eng_text_base: Story Mode Kiryu sections say 'KIRYU' instead of 'MECHAGODZILLA'
      - eng_text_alt : Story Mode DX alt sections say GODZILLA '99 / MECHA-GHIDORAH / FIRE RODAN /
                       MECHAGODZILLA / MOTHRA '92 / MEGALON-01, cleanly re-wrapped to fit the box.
    """
    header_lines = [
        "NORMAL RULE:",
        "STANDARD GAMEPLAY",
        "RULES.",
        "SURVIVAL RULE:",
        "NO HEALTH RECOVERY",
        "OR CONTINUES!",
        "ADRENALINE RULE:",
        "SPECIAL GAUGE FILLS",
        "FASTER THAN NORMAL!",
    ]
    out = bytearray()
    for line in header_lines:
        raw = line.encode("ascii")
        if len(raw) > 31:
            raise ValueError(f"Line too long (>31 chars): {line!r}")
        out.extend(raw.ljust(32, b"\x00"))

    # Copy all 484 lines from USA slot 0 (0x032854..0x0364D4, ending with '~')
    usa_start = 0x032854
    usa_end = 0x0364D4
    usa_slot0 = bytearray(usa_bytes[usa_start:usa_end])
    assert usa_slot0[:11] == b"STORY MODE:", "USA text table anchor mismatch!"
    assert usa_slot0[-32] == 0x7E, "USA text table '~' terminator mismatch!"
    # Update Options description (USA lines 9..11) to hint Select for DX Options!
    for idx, line in ((9, "OPTIONS:"), (10, "GAME SETTINGS"), (11, "(SELECT FOR DX MENU)")):
        usa_slot0[idx * 32 : (idx + 1) * 32] = line.encode("ascii").ljust(32, b"\x00")
    out.extend(usa_slot0)
    raw_eng = bytes(out)

    # Base table: Kiryu (sec 5, 12, 18, 24, 30, 37, 44) says KIRYU
    base_reps = {s: ("MECHAGODZILLA", "KIRYU") for s in (5, 12, 18, 24, 30, 37, 44)}
    eng_base = _rewrite_story_dialogue_table(raw_eng, base_reps)

    # DX Alt table: each monster's Story sections use its DX variant name!
    alt_reps: dict[int, tuple[str, str]] = {}
    for s in (2, 9, 15, 21, 27, 34, 41):
        alt_reps[s] = ("GODZILLA", "GODZILLA '99")
    for s in (3, 10, 16, 22, 28, 35, 42):
        alt_reps[s] = ("KING GHIDORAH", "MECHA-GHIDORAH")
    for s in (4, 11, 17, 23, 29, 36, 43):
        alt_reps[s] = ("RODAN", "FIRE RODAN")
    for s in (6, 13, 19, 25, 31, 38, 45):
        alt_reps[s] = ("MOTHRA", "MOTHRA '92")
    for s in (7, 14, 20, 26, 32, 39, 46):
        alt_reps[s] = ("MEGALON", "MEGALON-01")
    eng_alt = _rewrite_story_dialogue_table(raw_eng, alt_reps)
    return eng_base, eng_alt


# Crisp 5x7 uppercase bitmap font for JPN-exclusive Rule Select & DX Options pill buttons
# (rendered in USA[124]'s exact 4bpp palette indices: 7 = black pill bg, 1 = bright yellow text)
_PILL_FONT_5X7: dict[str, list[str]] = {
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "F": ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    "G": [".####", "#....", "#....", "#..##", "#...#", "#...#", ".###."],
    "I": [".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "J": ["..###", "...#.", "...#.", "...#.", "#..#.", "#..#.", ".##.."],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "M": ["#...#", "##.##", "#.#.#", "#...#", "#...#", "#...#", "#...#"],
    "N": ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "V": ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "W": ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"],
    "1": ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
    ":": [".....", "..#..", "..#..", ".....", "..#..", "..#..", "....."],
    " ": [".....", ".....", ".....", ".....", ".....", ".....", "....."],
}


def _render_rule_pill_tiles(template_frame: bytes, text: str) -> bytes:
    """Take a 0x400-byte (32-tile) USA[124] pill frame and draw English text on OBJs 0..2 (80x16)."""
    tiles = bytearray(template_frame)
    # Build 80x16 pixel grid from OBJs 0 (tiles 0..7), 1 (tiles 8..15), 2 (tiles 16..19)
    grid = [[0] * 80 for _ in range(16)]

    def _read_tile(tidx: int, ox: int, oy: int) -> None:
        tb = tidx * 32
        for py in range(8):
            for pxx in range(4):
                b = tiles[tb + py * 4 + pxx]
                grid[oy + py][ox + pxx * 2] = b & 0xF
                grid[oy + py][ox + pxx * 2 + 1] = b >> 4

    def _write_tile(tidx: int, ox: int, oy: int) -> None:
        tb = tidx * 32
        for py in range(8):
            for pxx in range(4):
                c0 = grid[oy + py][ox + pxx * 2] & 0xF
                c1 = grid[oy + py][ox + pxx * 2 + 1] & 0xF
                tiles[tb + py * 4 + pxx] = c0 | (c1 << 4)

    for obj, ox_base, w_tiles in ((0, 0, 4), (8, 32, 4), (16, 64, 2)):
        for ty in range(2):
            for tx in range(w_tiles):
                _read_tile(obj + ty * w_tiles + tx, ox_base + tx * 8, ty * 8)

    # Clear text region (x=0..69, y=2..13) to solid pill interior color 7 (preserving curved right cap)
    for y in range(2, 14):
        for x in range(0, 70):
            if grid[y][x] != 0:
                grid[y][x] = 7

    # Draw text starting at x=2, y=5 (5x7 glyphs with 1px spacing; fits 11-12 chars cleanly)
    # For "ADRENALINE" (10 chars) / "SURVIVAL" (8 chars) / "NORMAL RULE" (11 chars), 5+1=6px/char -> 66px!
    cx = 2
    for ch in text.upper():
        glyph = _PILL_FONT_5X7.get(ch, _PILL_FONT_5X7[" "])
        w = 3 if ch == " " else 5
        for gy, row in enumerate(glyph):
            for gx in range(w):
                if row[gx] == "#" and (cx + gx) < 70:
                    grid[5 + gy][cx + gx] = 1
        cx += w + 1

    for obj, ox_base, w_tiles in ((0, 0, 4), (8, 32, 4), (16, 64, 2)):
        for ty in range(2):
            for tx in range(w_tiles):
                _write_tile(obj + ty * w_tiles + tx, ox_base + tx * 8, ty * 8)

    # Also clear the stray 'S' from "Story Mode" on the rightmost tile column of OBJ 3 (tiles 23 & 27)
    for tidx in (23, 27):
        tb = tidx * 32
        for py in range(8):
            for pxx in range(4):
                b = tiles[tb + py * 4 + pxx]
                c0, c1 = b & 0xF, b >> 4
                if c0 in (1, 2, 3, 4, 5, 6, 14):
                    c0 = 7
                if c1 in (1, 2, 3, 4, 5, 6, 14):
                    c1 = 7
                tiles[tb + py * 4 + pxx] = c0 | (c1 << 4)
    return bytes(tiles)


def build_english_mode_pills_28f(usa124: bytes) -> bytes:
    """Build a 28-frame English Mode/Rule/DX-Options pill pack from USA[124] (19f) + 9 custom pills."""
    bpp, max_oam, max_tile, n_usa = struct.unpack_from("<4H", usa124, 0)
    assert n_usa == 19
    u_tile_off, u_tile_sz = struct.unpack_from("<2I", usa124, 8)
    oam0_off = struct.unpack_from("<I", usa124, 16)[0]
    oam_stride = struct.unpack_from("<I", usa124, 28)[0] - oam0_off  # 56 B per frame
    assert oam_stride == 56

    extra_labels = (
        "NORMAL RULE",   # 19
        "SURVIVAL",      # 20
        "ADRENALINE",    # 21
        "1P TAG: ON",    # 22
        "1P TAG: OFF",   # 23
        "BONUS: OFF",    # 24
        "BONUS: ON",     # 25
        "STAGE: JP",     # 26
        "STAGE: US",     # 27
    )
    n_new = n_usa + len(extra_labels)  # 28
    new_oam_base = 16 + n_new * 12
    new_tile_off = new_oam_base + n_new * oam_stride
    while new_tile_off % 4 != 0:
        new_tile_off += 1
    new_tile_sz = n_new * 0x400

    out = bytearray()
    out.extend(struct.pack("<4H2I", bpp, max_oam, max_tile, n_new, new_tile_off, new_tile_sz))
    for f in range(n_new):
        out.extend(struct.pack("<3I", new_oam_base + f * oam_stride, f * 0x400, 0x400))

    # OAM blocks: copy USA[124]'s 19 OAM blocks, plus 9 copies of frame 0's OAM block
    usa_oam_all = usa124[oam0_off : oam0_off + n_usa * oam_stride]
    oam_template = usa124[oam0_off : oam0_off + oam_stride]
    out.extend(usa_oam_all)
    for _ in range(len(extra_labels)):
        out.extend(oam_template)
    while len(out) < new_tile_off:
        out.append(0)

    # Tile data: USA[124]'s 19 English frames + 9 rendered English Rule & DX Options pills!
    # MUST use frame 0's tiles ("Story Mode") so tile layout matches frame 0's OAM 100%!
    out.extend(usa124[u_tile_off : u_tile_off + u_tile_sz])
    tmpl_tiles = usa124[u_tile_off : u_tile_off + 0x400]
    for label in extra_labels:
        out.extend(_render_rule_pill_tiles(tmpl_tiles, label))
    return bytes(out)


def build_title_logo_dx(usa136: bytes) -> bytes:
    """Append a bold fiery red-to-yellow 'DX' 32x16 8bpp OBJ badge to USA[136] Title Logo."""
    bpp, max_oam, max_tile, nframes = struct.unpack_from("<4H", usa136, 0)
    tile_off, tile_sz = struct.unpack_from("<2I", usa136, 8)
    oam_off, f_toff, f_tlen = struct.unpack_from("<3I", usa136, 16)
    oam_cnt = struct.unpack_from("<H", usa136, oam_off + 24)[0]
    assert bpp == 0xFF00 and nframes == 1 and oam_cnt == 17

    xs = list(struct.unpack_from(f"<{oam_cnt}h", usa136, oam_off + 26))
    ys = list(struct.unpack_from(f"<{oam_cnt}h", usa136, oam_off + 26 + oam_cnt * 2))
    attrs = list(struct.unpack_from(f"<{oam_cnt}H", usa136, oam_off + 26 + oam_cnt * 4))

    # Prepend OBJ[0] (highest OAM priority!): 32x16 8bpp (shape=1 wide, size=2 -> 0xA400 | tile_num)
    # 8bpp tile_num = tile_sz // 32 (4bpp tile units in GBA OAM!) -> 0x3580 // 32 = 428
    dx_tile_num = tile_sz // 32
    xs.insert(0, 50)      # right next to "DOMINATION!"
    ys.insert(0, -12)     # cleanly below the "A" swoosh, aligned with "DOMINATION!"
    attrs.insert(0, 0xA400 | dx_tile_num)
    new_cnt = oam_cnt + 1

    # Draw bold stylized 'DX' into a 32x16 8bpp pixel grid (0=transparent, 11=black outline, fire gradient fill)
    dx_mask = [
        "................................",
        "................................",
        "....#########....####....####...",
        "....##########...####....####...",
        "....####..#####...####..####....",
        "....####...####....########.....",
        "....####...####.....######......",
        "....####...####.....######......",
        "....####...####....########.....",
        "....####..#####...####..####....",
        "....##########...####....####...",
        "....#########....####....####...",
        "................................",
        "................................",
        "................................",
        "................................",
    ]
    # Fiery top-to-bottom 8bpp indices from USA[332] OBJ palette (matching GODZILLA!)
    fire_grad = [10, 10, 10, 36, 49, 68, 83, 101, 127, 157, 165, 165, 165, 165, 165, 165]
    grid = [[0] * 32 for _ in range(16)]
    # 2px bold black outline (idx 11)
    for y in range(16):
        for x in range(32):
            if dx_mask[y][x] == "#":
                for dy in (-2, -1, 0, 1, 2):
                    for dx in (-2, -1, 0, 1, 2):
                        if abs(dx) + abs(dy) <= 3:
                            ny, nx = y + dy, x + dx
                            if 0 <= ny < 16 and 0 <= nx < 32:
                                grid[ny][nx] = 11
    # Fiery gradient fill
    for y in range(16):
        for x in range(32):
            if dx_mask[y][x] == "#":
                grid[y][x] = fire_grad[y]

    # Encode 32x16 8bpp (4x2 = 8 tiles of 64 bytes = 512 bytes)
    dx_tiles = bytearray()
    for ty in range(2):
        for tx in range(4):
            for py in range(8):
                for px in range(8):
                    dx_tiles.append(grid[ty * 8 + py][tx * 8 + px])
    assert len(dx_tiles) == 512

    # Rebuild 1-frame sprite pack (OAM block grew by 6 bytes: +2B x, +2B y, +2B attr)
    new_oam = bytearray(usa136[oam_off : oam_off + 24])
    new_oam.extend(struct.pack("<H", new_cnt))
    new_oam.extend(struct.pack(f"<{new_cnt}h", *xs))
    new_oam.extend(struct.pack(f"<{new_cnt}h", *ys))
    new_oam.extend(struct.pack(f"<{new_cnt}H", *attrs))
    new_tile_off = oam_off + len(new_oam)
    while new_tile_off % 4 != 0:
        new_tile_off += 1
    new_tile_sz = tile_sz + len(dx_tiles)

    out = bytearray()
    out.extend(struct.pack("<4H2I", bpp, new_cnt, new_tile_sz, 1, new_tile_off, new_tile_sz))
    out.extend(struct.pack("<3I", oam_off, 0, new_tile_sz))
    out.extend(new_oam)
    while len(out) < new_tile_off:
        out.append(0)
    out.extend(usa136[tile_off : tile_off + tile_sz])
    out.extend(dx_tiles)
    return bytes(out)


def build_english_mode_headers_4f(usa95: bytes) -> bytes:
    """Build a 4-frame English Mode/Rule header pack from USA[95] (3f) by duplicating frame 0 for slot 3."""
    bpp, max_oam, max_tile, n_usa = struct.unpack_from("<4H", usa95, 0)
    assert n_usa == 3
    u_tile_off, u_tile_sz = struct.unpack_from("<2I", usa95, 8)
    frames = [struct.unpack_from("<3I", usa95, 16 + f * 12) for f in range(n_usa)]
    # Add 1 extra 12-byte frame entry pointing to frame 0's OAM & tile data (shift all oam_off & tile_off by +12)
    out = bytearray()
    out.extend(struct.pack("<4H2I", bpp, max_oam, max_tile, 4, u_tile_off + 12, u_tile_sz))
    for oam_o, t_o, t_l in frames:
        out.extend(struct.pack("<3I", oam_o + 12, t_o, t_l))
    # Frame 3 (Rule Select header) reuses Frame 0 ("SELECT MODE")
    out.extend(struct.pack("<3I", frames[0][0] + 12, frames[0][1], frames[0][2]))
    out.extend(usa95[16 + n_usa * 12 :])
    return bytes(out)


def build_blank_sprite_8bpp() -> bytes:
    """Build a minimal transparent 1-frame 8bpp sprite pack (used to hide JPN[237] title grid)."""
    # 16B header + 12B frame entry + 32B OAM (24B bbox + 2B cnt=1 + 2B x + 2B y + 2B attr=0x8000) + 64B zero tile
    oam_off = 28
    tile_off = 60
    out = bytearray()
    out.extend(struct.pack("<4H2I", 0xFF00, 1, 64, 1, tile_off, 64))
    out.extend(struct.pack("<3I", oam_off, 0, 64))
    out.extend(b"\x00" * 24)
    out.extend(struct.pack("<HhhH", 1, 0, 0, 0x8000))
    out.extend(b"\x00" * 64)
    return bytes(out)


def remap_sprite_pack_frames(jpn_blob: bytes, usa_blob: bytes, jpn_to_usa: list[int]) -> bytes:
    """Reorder USA sprite pack frames to match AG4J's animation indices while preserving AG4J hitboxes."""
    j_bpp, j_mo, j_mt, j_nf, _, _ = struct.unpack_from("<4H2I", jpn_blob, 0)
    u_bpp, u_mo, u_mt, u_nf, u_toff, _ = struct.unpack_from("<4H2I", usa_blob, 0)
    assert j_bpp == u_bpp and j_nf == u_nf == len(jpn_to_usa)
    assert sorted(jpn_to_usa) == list(range(j_nf)), "Frame mapping must be a complete bijection!"

    oam_blocks: list[bytes] = []
    tile_blocks: list[bytes] = []
    for jf, uf in enumerate(jpn_to_usa):
        j_oam_off = struct.unpack_from("<I", jpn_blob, 16 + jf * 12)[0]
        u_oam_off, u_fto, u_ftl = struct.unpack_from("<3I", usa_blob, 16 + uf * 12)
        u_cnt = struct.unpack_from("<H", usa_blob, u_oam_off + 24)[0]
        u_oam_body = usa_blob[u_oam_off + 24 : u_oam_off + 26 + u_cnt * 6]
        # Preserve AG4J's 24-byte hitbox/hurtbox header + USA's OAM sprite pieces!
        j_hdr24 = jpn_blob[j_oam_off : j_oam_off + 24]
        oam_blocks.append(j_hdr24 + u_oam_body)
        tile_blocks.append(usa_blob[u_toff + u_fto : u_toff + u_fto + u_ftl])

    dir_end = 16 + j_nf * 12
    oam_offs: list[int] = []
    cur = dir_end
    for ob in oam_blocks:
        oam_offs.append(cur)
        cur += len(ob)
    while cur % 4 != 0:
        cur += 1
    new_tile_off = cur

    tile_offs: list[int] = []
    tcur = 0
    for tb in tile_blocks:
        tile_offs.append(tcur)
        tcur += len(tb)

    out = bytearray()
    out.extend(struct.pack("<4H2I", u_bpp, max(j_mo, u_mo), max(j_mt, u_mt), j_nf, new_tile_off, tcur))
    for f in range(j_nf):
        out.extend(struct.pack("<3I", oam_offs[f], tile_offs[f], len(tile_blocks[f])))
    for ob in oam_blocks:
        out.extend(ob)
    while len(out) < new_tile_off:
        out.append(0)
    for tb in tile_blocks:
        out.extend(tb)
    return bytes(out)


def build_composite_skin_pack(
    base_blob: bytes,
    alt_blob: bytes,
    frame_bits: dict[int, tuple[int, int]],
    mask: int,
) -> bytes:
    """Composite a multi-monster sprite pack by picking alt_blob[src_f] where (mask & (1<<bit)) != 0."""
    j_bpp, j_mo, j_mt, j_nf, j_toff, _ = struct.unpack_from("<4H2I", base_blob, 0)
    u_bpp, u_mo, u_mt, u_nf, u_toff, _ = struct.unpack_from("<4H2I", alt_blob, 0)
    assert j_bpp == u_bpp and j_nf == u_nf

    oam_blocks: list[bytes] = []
    tile_blocks: list[bytes] = []
    for f in range(j_nf):
        spec = frame_bits.get(f)
        use_alt = (spec is not None) and bool(mask & (1 << spec[0]))
        src = alt_blob if use_alt else base_blob
        s_toff = u_toff if use_alt else j_toff
        sf = spec[1] if use_alt else f
        s_oam_off, s_fto, s_ftl = struct.unpack_from("<3I", src, 16 + sf * 12)
        s_cnt = struct.unpack_from("<H", src, s_oam_off + 24)[0]
        oam_blocks.append(src[s_oam_off : s_oam_off + 26 + s_cnt * 6])
        tile_blocks.append(src[s_toff + s_fto : s_toff + s_fto + s_ftl])

    dir_end = 16 + j_nf * 12
    oam_offs: list[int] = []
    cur = dir_end
    for ob in oam_blocks:
        oam_offs.append(cur)
        cur += len(ob)
    while cur % 4 != 0:
        cur += 1
    new_tile_off = cur

    tile_offs: list[int] = []
    tcur = 0
    for tb in tile_blocks:
        tile_offs.append(tcur)
        tcur += len(tb)

    out = bytearray()
    out.extend(struct.pack("<4H2I", j_bpp, max(j_mo, u_mo), max(j_mt, u_mt), j_nf, new_tile_off, tcur))
    for f in range(j_nf):
        out.extend(struct.pack("<3I", oam_offs[f], tile_offs[f], len(tile_blocks[f])))
    for ob in oam_blocks:
        out.extend(ob)
    while len(out) < new_tile_off:
        out.append(0)
    for tb in tile_blocks:
        out.extend(tb)
    return bytes(out)


def build_classic_giant_monsters_8f(usa117: bytes) -> bytes:
    """Expand USA[117] (7f 8bpp giant depictions) to 8f to match JPN[243] (dup frame 3 into slot 7)."""
    bpp, max_oam, max_tile, n_usa = struct.unpack_from("<4H", usa117, 0)
    assert bpp == 0xFF00 and n_usa == 7
    u_tile_off, u_tile_sz = struct.unpack_from("<2I", usa117, 8)
    frames = [struct.unpack_from("<3I", usa117, 16 + f * 12) for f in range(n_usa)]
    # Add 1 extra 12-byte frame entry pointing to frame 3 (Classic Mechagodzilla) for slot 7
    out = bytearray()
    out.extend(struct.pack("<4H2I", bpp, max_oam, max_tile, 8, u_tile_off + 12, u_tile_sz))
    for oam_o, t_o, t_l in frames:
        out.extend(struct.pack("<3I", oam_o + 12, t_o, t_l))
    out.extend(struct.pack("<3I", frames[3][0] + 12, frames[3][1], frames[3][2]))
    out.extend(usa117[16 + n_usa * 12 :])
    return bytes(out)


def append_frames_to_pack(base_blob: bytes, extras: list[tuple[bytes, int]]) -> bytes:
    """Append (donor_blob, donor_frame) entries onto a sprite pack."""
    b_bpp, b_mo, b_mt, b_nf, b_toff, _ = struct.unpack_from("<4H2I", base_blob, 0)
    oam_blocks: list[bytes] = []
    tile_blocks: list[bytes] = []
    max_oam, max_tile = b_mo, b_mt

    for f in range(b_nf):
        oam_off, fto, ftl = struct.unpack_from("<3I", base_blob, 16 + f * 12)
        cnt = struct.unpack_from("<H", base_blob, oam_off + 24)[0]
        oam_blocks.append(base_blob[oam_off : oam_off + 26 + cnt * 6])
        tile_blocks.append(base_blob[b_toff + fto : b_toff + fto + ftl])

    for donor_blob, donor_frame in extras:
        d_bpp, d_mo, d_mt, _, d_toff, _ = struct.unpack_from("<4H2I", donor_blob, 0)
        assert b_bpp == d_bpp, f"BPP mismatch: 0x{b_bpp:04X} vs 0x{d_bpp:04X}"
        max_oam = max(max_oam, d_mo)
        max_tile = max(max_tile, d_mt)
        d_oam_off, d_fto, d_ftl = struct.unpack_from("<3I", donor_blob, 16 + donor_frame * 12)
        d_cnt = struct.unpack_from("<H", donor_blob, d_oam_off + 24)[0]
        oam_blocks.append(donor_blob[d_oam_off : d_oam_off + 26 + d_cnt * 6])
        tile_blocks.append(donor_blob[d_toff + d_fto : d_toff + d_fto + d_ftl])

    new_nf = len(oam_blocks)
    cur = 16 + new_nf * 12
    oam_offs: list[int] = []
    for ob in oam_blocks:
        oam_offs.append(cur)
        cur += len(ob)
    while cur % 4 != 0:
        cur += 1
    new_toff = cur

    tile_offs: list[int] = []
    tcur = 0
    for tb in tile_blocks:
        tile_offs.append(tcur)
        tcur += len(tb)

    out = bytearray()
    out.extend(struct.pack("<4H2I", b_bpp, max_oam, max_tile, new_nf, new_toff, tcur))
    for f in range(new_nf):
        out.extend(struct.pack("<3I", oam_offs[f], tile_offs[f], len(tile_blocks[f])))
    for ob in oam_blocks:
        out.extend(ob)
    while len(out) < new_toff:
        out.append(0)
    for tb in tile_blocks:
        out.extend(tb)
    return bytes(out)


# Condensed 3x7 arcade font (4px/char incl. gap; fits 10 chars in 40px inside Custom Mode's 44px box!)
_CUSTOM_FONT_3X7: dict[str, list[str]] = {
    "A": [".#.", "#.#", "#.#", "###", "#.#", "#.#", "#.#"],
    "C": [".##", "#..", "#..", "#..", "#..", "#..", ".##"],
    "D": ["##.", "#.#", "#.#", "#.#", "#.#", "#.#", "##."],
    "E": ["###", "#..", "#..", "##.", "#..", "#..", "###"],
    "F": ["###", "#..", "#..", "##.", "#..", "#..", "#.."],
    "G": [".##", "#..", "#..", "#.#", "#.#", "#.#", ".##"],
    "H": ["#.#", "#.#", "#.#", "###", "#.#", "#.#", "#.#"],
    "I": ["###", ".#.", ".#.", ".#.", ".#.", ".#.", "###"],
    "K": ["#.#", "#.#", "##.", "##.", "#.#", "#.#", "#.#"],
    "L": ["#..", "#..", "#..", "#..", "#..", "#..", "###"],
    "M": ["#.#", "###", "###", "#.#", "#.#", "#.#", "#.#"],
    "N": ["###", "#.#", "#.#", "#.#", "#.#", "#.#", "#.#"],
    "O": [".#.", "#.#", "#.#", "#.#", "#.#", "#.#", ".#."],
    "P": ["##.", "#.#", "#.#", "##.", "#..", "#..", "#.."],
    "R": ["##.", "#.#", "#.#", "##.", "#.#", "#.#", "#.#"],
    "S": [".##", "#..", "#..", ".#.", "..#", "..#", "##."],
    "T": ["###", ".#.", ".#.", ".#.", ".#.", ".#.", ".#."],
    "U": ["#.#", "#.#", "#.#", "#.#", "#.#", "#.#", "###"],
    "Y": ["#.#", "#.#", "#.#", ".#.", ".#.", ".#.", ".#."],
    "Z": ["###", "..#", "..#", ".#.", "#..", "#..", "###"],
    "0": [".#.", "#.#", "#.#", "#.#", "#.#", "#.#", ".#."],
    "1": [".#.", "##.", ".#.", ".#.", ".#.", ".#.", "###"],
    "2": ["##.", "..#", "..#", ".#.", "#..", "#..", "###"],
    "3": ["###", "..#", "..#", ".##", "..#", "..#", "###"],
    "9": ["###", "#.#", "#.#", "###", "..#", "..#", "##."],
    "'": [".#", ".#", "..", "..", "..", "..", ".."],
    ".": ["..", "..", "..", "..", "..", "..", "#."],
    "-": ["...", "...", "...", "###", "...", "...", "..."],
    " ": ["..", "..", "..", "..", "..", "..", ".."],
}


def _render_custom_name_48x8(text: str) -> bytes:
    """Render a crisp 48x8 (6-tile 4bpp) condensed white label fitting cleanly inside the 44px card."""
    grid = [[0] * 48 for _ in range(8)]
    cx = 1  # 1px left margin inside the card
    for ch in text.upper():
        glyph = _CUSTOM_FONT_3X7.get(ch, _CUSTOM_FONT_3X7[" "])
        w = len(glyph[0])
        for gy, row in enumerate(glyph):
            for gx in range(w):
                if row[gx] == "#" and (cx + gx) < 44:
                    grid[gy][cx + gx] = 1
        cx += w + 1
    tiles = bytearray(6 * 32)
    for t in range(6):
        tb = t * 32
        for py in range(8):
            for px in range(4):
                c0 = grid[py][t * 8 + px * 2] & 0xF
                c1 = grid[py][t * 8 + px * 2 + 1] & 0xF
                tiles[tb + py * 4 + px] = c0 | (c1 << 4)
    return bytes(tiles)


def build_custom_mode_names_25f(base167: bytes) -> bytes:
    """Expand JPN[167] (19f) -> 25f: relabel f3='KIRYU' and append f19..f24 for IDs 7..12."""
    b_bpp, b_mo, b_mt, b_nf, b_toff, _ = struct.unpack_from("<4H2I", base167, 0)
    assert b_nf == 19
    oam_blocks: list[bytes] = []
    tile_blocks: list[bytes] = []
    for f in range(b_nf):
        oam_off, fto, ftl = struct.unpack_from("<3I", base167, 16 + f * 12)
        cnt = struct.unpack_from("<H", base167, oam_off + 24)[0]
        oam_blocks.append(base167[oam_off : oam_off + 26 + cnt * 6])
        tile_blocks.append(base167[b_toff + fto : b_toff + fto + ftl])

    # Keep vanilla M-GODZILLA (f3) OAM/tiles as template for 48x8 labels & ID 10 (f22)
    oam_48x8 = oam_blocks[3]
    orig_mg_tiles = tile_blocks[3]

    # Approved v0.9 Era/Variant Custom Mode labels (all <= 42px inside the 44px card!)
    oam_blocks[0] = oam_48x8
    tile_blocks[0] = _render_custom_name_48x8("GODZILLA03")
    tile_blocks[3] = _render_custom_name_48x8("KIRYU")
    oam_blocks[4] = oam_48x8
    tile_blocks[4] = _render_custom_name_48x8("MOTHRA '03")

    # Append f19..f24 for IDs 7..12 + f25 for ID 13 ('RANDOM'!)
    for label in ("GODZILLA99", "M.GHIDORAH", "FIRE RODAN", None, "MOTHRA '92", "MEGALON-01", "RANDOM"):
        oam_blocks.append(oam_48x8)
        tile_blocks.append(orig_mg_tiles if label is None else _render_custom_name_48x8(label))

    new_nf = len(oam_blocks)
    cur = 16 + new_nf * 12
    oam_offs: list[int] = []
    for ob in oam_blocks:
        oam_offs.append(cur)
        cur += len(ob)
    while cur % 4 != 0:
        cur += 1
    new_toff = cur

    tile_offs: list[int] = []
    tcur = 0
    for tb in tile_blocks:
        tile_offs.append(tcur)
        tcur += len(tb)

    out = bytearray()
    out.extend(struct.pack("<4H2I", b_bpp, max(b_mo, 2), max(b_mt, 192), new_nf, new_toff, tcur))
    for f in range(new_nf):
        out.extend(struct.pack("<3I", oam_offs[f], tile_offs[f], len(tile_blocks[f])))
    for ob in oam_blocks:
        out.extend(ob)
    while len(out) < new_toff:
        out.append(0)
    for tb in tile_blocks:
        out.extend(tb)
    return bytes(out)


def build_battle_hud_12entity(usa12: bytes) -> tuple[bytes, bytes]:
    """Overwrite vanilla HUD name tiles (0x26..0x5C = 55 slots) inside USA[12] with crisp outlined
    names for all 12 fighters — keeping USA[12]'s exact 4,304-byte size (0x77 tiles) so BG VRAM
    never overflows into the HUD tilemap!

    Returns (patched_usa12_blob, hud_name_table_192b):
      - entries  0..11 (96 B): Left-aligned  8-byte tile strips for P1/P3 (IDs 1..12)
      - entries 12..23 (96 B): Right-aligned 8-byte tile strips for P2/P4 (IDs 1..12)
    """
    out = bytearray(usa12)
    orig_ntiles = struct.unpack_from("<H", out, 4)[0]
    assert orig_ntiles == 0x77 and len(out) == 496 + orig_ntiles * 32

    # 12 official v0.9 Battle HUD names (aligned to 8px tile boundaries where shared so <= 55 unique tiles!)
    hud_names = (
        "GODZILLA '03",   # ID  1 (6 tiles)
        "KING GHIDORAH",  # ID  2 (7 tiles)
        "RODAN",          # ID  3 (3 tiles)
        "KIRYU",          # ID  4 (3 tiles)
        "MOTHRA '03",     # ID  5 (6 tiles)
        "MEGALON",        # ID  6 (4 tiles)
        "GODZILLA '99",   # ID  7 (shares GODZILLA)
        "MECHA-GHIDORAH", # ID  8 (7 tiles)
        "FIRE RODAN",     # ID  9 (5 tiles)
        "MECHAGODZILLA",  # ID 10 (7 tiles)
        "MOTHRA '92",     # ID 11 (shares MOTHRA)
        "MEGALON-01",     # ID 12 (shares MEGALON)
    )

    def render_hud_tiles(text: str) -> list[bytes]:
        glyphs = [_CUSTOM_FONT_3X7.get(ch, _CUSTOM_FONT_3X7[" "]) for ch in text.upper()]
        grid = [[0] * 64 for _ in range(8)]
        cx = 1
        for g in glyphs:
            w = len(g[0])
            for gy, row in enumerate(g):
                for gx in range(w):
                    if row[gx] == "#" and 0 <= (cx + gx) < 63 and (gy + 1) < 8:
                        grid[gy + 1][cx + gx] = 0xF  # pure white fill
            cx += w + 1
        # Crisp 1px black outline (0xE) around every white pixel
        outlined = [row[:] for row in grid]
        for y in range(8):
            for x in range(64):
                if grid[y][x] == 0:
                    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < 8 and 0 <= nx < 64 and grid[ny][nx] == 0xF:
                            outlined[y][x] = 0xE
                            break
        # Encode non-empty 8x8 tiles (trimmed on right so left & right alignment share identical tiles!)
        tiles_out: list[bytes] = []
        for t in range(8):
            tb = bytearray(32)
            for py in range(8):
                for px in range(4):
                    c0 = outlined[py][t * 8 + px * 2] & 0xF
                    c1 = outlined[py][t * 8 + px * 2 + 1] & 0xF
                    tb[py * 4 + px] = c0 | (c1 << 4)
            tiles_out.append(bytes(tb))
        while tiles_out and tiles_out[-1] == bytes(32):
            tiles_out.pop()
        return tiles_out

    # Allocate strictly inside vanilla monster-name tile range 0x26..0x5C (55 slots!)
    # Note: USA[12] tile 0 starts at byte offset 494 (0x1EE), verified against vanilla GODZILLA (0x26..0x2A)!
    tile_cache: dict[bytes, int] = {bytes(32): 0}
    next_tid = 0x26
    left_strips: list[bytes] = []
    right_strips: list[bytes] = []

    for name in hud_names:
        tlist = render_hud_tiles(name)
        ids: list[int] = []
        for tbytes in tlist:
            if tbytes in tile_cache:
                ids.append(tile_cache[tbytes])
            else:
                assert next_tid <= 0x5C, f"HUD tile pool overflow at {name} (tid=0x{next_tid:02X})"
                tile_cache[tbytes] = next_tid
                off = 494 + next_tid * 32
                out[off : off + 32] = tbytes
                ids.append(next_tid)
                next_tid += 1
        pad = [0] * (8 - len(ids))
        left_strips.append(bytes(ids + pad))
        # Right HUD strip starts at tile col 23 -> cols 23..29 (7 visible tiles); col 30 (slot 7) is off-screen!
        pad_r = [0] * max(0, 7 - len(ids))
        right_strips.append(bytes((pad_r + ids + [0])[:8]))

    return bytes(out), b"".join(left_strips) + b"".join(right_strips)


def build_canonical_mkg_pack(jpn_blob: bytes, only_frame: int | None = None, is_portrait: bool = False) -> bytes:
    """Losslessly remap King Ghidorah's 4bpp tiles in JPN[33] (69f) or JPN[213] (f2 portrait) into
    canonical Mecha-King Ghidorah: metallic silver middle head (with red cyber-eye), metallic silver
    armored chest/torso, metallic silver front & back wings, and bright golden outer heads, legs & tails.
    Preserves exact OAM coordinates, attributes, and 24-byte hitboxes.
    """
    from collections import deque

    oam_dims = {
        (0, 0): (8, 8),   (0, 1): (16, 16), (0, 2): (32, 32), (0, 3): (64, 64),
        (1, 0): (16, 8),  (1, 1): (32, 8),  (1, 2): (32, 16), (1, 3): (64, 32),
        (2, 0): (8, 16),  (2, 1): (8, 32),  (2, 2): (16, 32), (2, 3): (32, 64),
    }
    gold_to_silver = {1: 13, 2: 8, 3: 9, 4: 10, 5: 11, 6: 11, 7: 8}
    gold_to_gunmetal = {1: 8, 2: 9, 3: 10, 4: 10, 5: 11, 6: 11, 7: 9}
    gold_set = {1, 2, 3, 4, 5, 6, 7}

    _, _, _, nf, toff, _ = struct.unpack_from("<4H2I", jpn_blob, 0)
    out = bytearray(jpn_blob)
    frames = [only_frame] if only_frame is not None else list(range(nf))
    cell, ox, oy = (40, 0, 0) if is_portrait else (96, 48, 64)

    for f in frames:
        oam_off, fto, ftl = struct.unpack_from("<3I", jpn_blob, 16 + f * 12)
        cnt = struct.unpack_from("<H", jpn_blob, oam_off + 24)[0]
        xs = struct.unpack_from(f"<{cnt}h", jpn_blob, oam_off + 26)
        ys = struct.unpack_from(f"<{cnt}h", jpn_blob, oam_off + 26 + cnt * 2)
        attrs = struct.unpack_from(f"<{cnt}H", jpn_blob, oam_off + 26 + cnt * 4)
        tiles = bytearray(jpn_blob[toff + fto : toff + fto + ftl])

        canvas = [[0] * cell for _ in range(cell)]
        pix_src: dict[tuple[int, int], tuple[int, int, int]] = {}
        for i in reversed(range(cnt)):
            x, y, a = xs[i], ys[i], attrs[i]
            sz, sh, tid = (a >> 12) & 3, (a >> 10) & 3, a & 0x3FF
            w, h = oam_dims[(sh, sz)]
            tx_n, ty_n = w // 8, h // 8
            for ty in range(ty_n):
                for tx in range(tx_n):
                    t_idx = tid + ty * tx_n + tx
                    tb_off = t_idx * 32
                    for py in range(8):
                        for px in range(8):
                            b = tiles[tb_off + py * 4 + (px >> 1)]
                            c = (b >> 4) if (px & 1) else (b & 0xF)
                            if c == 0:
                                continue
                            gx, gy = ox + x + tx * 8 + px, oy + y + ty * 8 + py
                            if 0 <= gx < cell and 0 <= gy < cell:
                                canvas[gy][gx] = c
                                pix_src[(gx, gy)] = (tb_off + py * 4 + (px >> 1), px & 1, c)

        nz = [(x, y) for y in range(cell) for x in range(cell) if canvas[y][x] != 0]
        if not nz:
            continue
        min_x, max_x = min(p[0] for p in nz), max(p[0] for p in nz)
        min_y, max_y = min(p[1] for p in nz), max(p[1] for p in nz)
        sw, sh_px = max(1, max_x - min_x), max(1, max_y - min_y)

        vis = [[False] * cell for _ in range(cell)]
        comps = []
        for y in range(cell):
            for x in range(cell):
                if canvas[y][x] in gold_set and not vis[y][x]:
                    q = deque([(x, y)])
                    vis[y][x] = True
                    pts = []
                    dark_cnt = 0
                    while q:
                        cx, cy = q.popleft()
                        pts.append((cx, cy))
                        if canvas[cy][cx] in (4, 5, 6):
                            dark_cnt += 1
                        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                            nx, ny = cx + dx, cy + dy
                            if 0 <= nx < cell and 0 <= ny < cell and canvas[ny][nx] in gold_set and not vis[ny][nx]:
                                vis[ny][nx] = True
                                q.append((nx, ny))
                    xs_c = [p[0] for p in pts]
                    ys_c = [p[1] for p in pts]
                    comps.append({
                        "pts": pts, "n": len(pts),
                        "cx": sum(xs_c) / len(pts), "cy": sum(ys_c) / len(pts),
                        "min_x": min(xs_c), "max_x": max(xs_c),
                        "min_y": min(ys_c), "max_y": max(ys_c),
                        "dark_ratio": dark_cnt / len(pts),
                    })

        new_canvas = [row[:] for row in canvas]
        if is_portrait:
            # Exact pixel regions of JPN[213] f2 (40x40 Custom Mode portrait) matching user's movie-accurate MKG:
            # - Top-left back wing blade (y<=15, x<=17) -> Warm Titanium Silver
            # - Middle head ONLY (y<=13, x>=17)         -> Warm Titanium Silver
            # - Chest armor (y>=26, x=7..31)            -> Warm Titanium Silver
            # - Lower-left front wing membrane (y>=22, x<=8) -> Metallic Bronze-Gold (idx 8..11 -> 2..5)
            # - Both outer heads (left & lower-right) stay Bright Movie Gold!
            s2g = {8: 2, 9: 3, 10: 4, 11: 5}
            for y in range(cell):
                for x in range(cell):
                    v = canvas[y][x]
                    if v in s2g and y >= 22 and x <= 8:
                        new_canvas[y][x] = s2g[v]
                        continue
                    if v == 13 and y <= 13 and x >= 17:
                        new_canvas[y][x] = 7  # emerald-green cyber-visor on middle head!
                        continue
                    if v not in gold_set:
                        continue
                    if y <= 15 and x <= 17 and v in (4, 5, 6):
                        new_canvas[y][x] = gold_to_gunmetal[v]
                    elif y <= 13 and x >= 17:
                        new_canvas[y][x] = gold_to_silver[v]
                    elif y >= 26 and 7 <= x <= 31:
                        new_canvas[y][x] = gold_to_silver[v]
        else:
            # 1. Back Wing ONLY: 4-connected DARK gold/rust (4, 5, 6) ONLY — never enters bright gold (1..3)
            #    of the outer heads, eliminating any vertical cut line on every single frame!
            vis_w = [[False] * cell for _ in range(cell)]
            wing_pts: set[tuple[int, int]] = set()
            for wy in range(cell):
                for wx in range(cell):
                    if canvas[wy][wx] in (4, 5, 6) and not vis_w[wy][wx]:
                        qw = deque([(wx, wy)])
                        vis_w[wy][wx] = True
                        wpts: list[tuple[int, int]] = []
                        while qw:
                            cxw, cyw = qw.popleft()
                            wpts.append((cxw, cyw))
                            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                                nx, ny = cxw + dx, cyw + dy
                                if 0 <= nx < cell and 0 <= ny < cell and canvas[ny][nx] in (4, 5, 6) and not vis_w[ny][nx]:
                                    vis_w[ny][nx] = True
                                    qw.append((nx, ny))
                        if len(wpts) >= 12:
                            rxw = (sum(p[0] for p in wpts) / len(wpts) - min_x) / sw
                            ryw = (sum(p[1] for p in wpts) / len(wpts) - min_y) / sh_px
                            if rxw < 0.56 and ryw < 0.50:
                                wing_pts.update(wpts)
                                for px, py in wpts:
                                    new_canvas[py][px] = gold_to_gunmetal[canvas[py][px]]

            # Recompute gold components excluding wing_pts
            vis2 = [[False] * cell for _ in range(cell)]
            comps2 = []
            for gy in range(cell):
                for gx in range(cell):
                    if canvas[gy][gx] in gold_set and (gx, gy) not in wing_pts and not vis2[gy][gx]:
                        q2 = deque([(gx, gy)])
                        vis2[gy][gx] = True
                        pts2: list[tuple[int, int]] = []
                        while q2:
                            cx2, cy2 = q2.popleft()
                            pts2.append((cx2, cy2))
                            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                                nx, ny = cx2 + dx, cy2 + dy
                                if (
                                    0 <= nx < cell and 0 <= ny < cell
                                    and canvas[ny][nx] in gold_set
                                    and (nx, ny) not in wing_pts
                                    and not vis2[ny][nx]
                                ):
                                    vis2[ny][nx] = True
                                    q2.append((nx, ny))
                        xs2 = [p[0] for p in pts2]
                        ys2 = [p[1] for p in pts2]
                        comps2.append({
                            "pts": pts2, "n": len(pts2),
                            "cx": sum(xs2) / len(pts2), "cy": sum(ys2) / len(pts2),
                            "min_x": min(xs2), "max_x": max(xs2),
                            "min_y": min(ys2), "max_y": max(ys2),
                        })

            # 2. STRICTLY ONE Silver Middle Head (highest head peak; NEVER >1 head!)
            head_cands = [
                c for c in comps2
                if c["n"] >= 8 and ((c["cy"] - min_y) / sh_px) < 0.38 and ((c["cx"] - min_x) / sw) > 0.26
            ]
            if head_cands:
                head_cands.sort(key=lambda c: c["min_y"])
                th = head_cands[0]
                top_pts = [p for p in th["pts"] if p[1] <= th["min_y"] + 2]
                px0 = sum(p[0] for p in top_pts) // len(top_pts)
                py0 = th["min_y"]
                mh_set: set[tuple[int, int]] = set()
                for x, y in th["pts"]:
                    if th["n"] <= 75 or (x - px0) ** 2 + (y - py0) ** 2 <= 14 * 14:
                        new_canvas[y][x] = gold_to_silver[canvas[y][x]]
                        mh_set.add((x, y))
                for x in range(th["min_x"], th["max_x"] + 1):
                    for y in range(th["min_y"], min(th["max_y"] + 1, th["min_y"] + 9)):
                        if canvas[y][x] == 13 and th["min_x"] + 2 <= x <= th["max_x"] - 2:
                            nbrs = sum(
                                1 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                                if 0 <= x + dx < cell and 0 <= y + dy < cell and (
                                    (x + dx, y + dy) in mh_set or canvas[y + dy][x + dx] == 14
                                )
                            )
                            if nbrs >= 3:
                                new_canvas[y][x] = 12
                # Also convert any thin gold neck-crest directly under the silver middle head (connecting head -> chest)
                for c in comps2:
                    if c is th or c["n"] > 28:
                        continue
                    if (
                        th["max_y"] - 2 <= c["min_y"] <= th["max_y"] + 10
                        and th["min_x"] - 8 <= c["cx"] <= th["max_x"] + 2
                        and ((c["cy"] - min_y) / sh_px) < 0.45
                    ):
                        for x, y in c["pts"]:
                            new_canvas[y][x] = gold_to_silver[canvas[y][x]]

            # 3. 100% Consistent Middle Section of Body (Armored Chest/Torso) across ALL 69 frames!
            mid_xs = [
                x for y in range(min_y + int(0.42 * sh_px), min_y + int(0.68 * sh_px) + 1)
                for x in range(min_x, max_x + 1)
                if canvas[y][x] in gold_set and (x, y) not in wing_pts
            ]
            body_cx = sum(mid_xs) / len(mid_xs) if mid_xs else (min_x + max_x) / 2
            ty_lo = min_y + int(0.38 * sh_px)
            ty_hi = min_y + int(0.64 * sh_px)
            tx_lo = int(body_cx - 0.21 * sw)
            tx_hi = int(body_cx + 0.21 * sw)
            for c in comps2:
                if c["n"] < 14:
                    continue
                ry = (c["cy"] - min_y) / sh_px
                if ry < 0.36:
                    continue
                if 0.38 <= ry <= 0.66 and abs(c["cx"] - body_cx) <= 0.22 * sw and (c["max_y"] - min_y) / sh_px < 0.72:
                    for x, y in c["pts"]:
                        new_canvas[y][x] = gold_to_silver[canvas[y][x]]
                else:
                    for x, y in c["pts"]:
                        if ty_lo <= y <= ty_hi and tx_lo <= x <= tx_hi:
                            new_canvas[y][x] = gold_to_silver[canvas[y][x]]

        # Write modified nibbles directly back into the frame's tile bytes
        for (gx, gy), (byte_off, hi_nib, orig_c) in pix_src.items():
            nc = new_canvas[gy][gx]
            if nc != orig_c:
                cur_b = tiles[byte_off]
                if hi_nib:
                    tiles[byte_off] = (cur_b & 0x0F) | ((nc & 0xF) << 4)
                else:
                    tiles[byte_off] = (cur_b & 0xF0) | (nc & 0xF)
        out[toff + fto : toff + fto + ftl] = tiles

    return bytes(out)


def ingest_mkg_sheet_1x(jpn33_blob: bytes, sheet_path: Path) -> bytes:
    """Ingest an editable 960x672 16-color indexed PNG (10x7 grid of 96x96 cells, origin (48,64))
    directly into JPN[33]'s 69-frame OAM/tile structure, preserving exact hitboxes & OAM layouts.
    """
    from PIL import Image

    img = Image.open(sheet_path)
    if img.mode != "P" or img.size != (960, 672):
        raise ValueError(f"{sheet_path} must be a 960x672 indexed (mode 'P') 16-color PNG, got {img.size} {img.mode}")
    pix = img.load()
    oam_dims = {
        (0, 0): (8, 8),   (0, 1): (16, 16), (0, 2): (32, 32), (0, 3): (64, 64),
        (1, 0): (16, 8),  (1, 1): (32, 8),  (1, 2): (32, 16), (1, 3): (64, 32),
        (2, 0): (8, 16),  (2, 1): (8, 32),  (2, 2): (16, 32), (2, 3): (32, 64),
    }
    _, _, _, nf, toff, _ = struct.unpack_from("<4H2I", jpn33_blob, 0)
    assert nf == 69
    out = bytearray(jpn33_blob)
    for f in range(nf):
        bx, by = (f % 10) * 96, (f // 10) * 96
        oam_off, fto, ftl = struct.unpack_from("<3I", jpn33_blob, 16 + f * 12)
        cnt = struct.unpack_from("<H", jpn33_blob, oam_off + 24)[0]
        xs = struct.unpack_from(f"<{cnt}h", jpn33_blob, oam_off + 26)
        ys = struct.unpack_from(f"<{cnt}h", jpn33_blob, oam_off + 26 + cnt * 2)
        attrs = struct.unpack_from(f"<{cnt}H", jpn33_blob, oam_off + 26 + cnt * 4)
        tiles = bytearray(ftl)
        for i in range(cnt):
            x, y, a = xs[i], ys[i], attrs[i]
            w, h = oam_dims[((a >> 10) & 3, (a >> 12) & 3)]
            tid = a & 0x3FF
            for ty in range(h // 8):
                for tx in range(w // 8):
                    tb = (tid + ty * (w // 8) + tx) * 32
                    for py in range(8):
                        for px in range(4):
                            gx0 = 48 + x + tx * 8 + px * 2
                            gx1 = gx0 + 1
                            gy = 64 + y + ty * 8 + py
                            c0 = pix[bx + gx0, by + gy] if (0 <= gx0 < 96 and 0 <= gy < 96) else 0
                            c1 = pix[bx + gx1, by + gy] if (0 <= gx1 < 96 and 0 <= gy < 96) else 0
                            if c0 > 15 or c1 > 15:
                                raise ValueError(f"Palette index >15 in {sheet_path} frame {f} ({c0}, {c1})")
                            tiles[tb + py * 4 + px] = (c0 & 0xF) | ((c1 & 0xF) << 4)
        out[toff + fto : toff + fto + ftl] = tiles
    return bytes(out)


def build_mkg_mini_icon_pack(blob212: bytes) -> bytes:
    """Remap King Ghidorah's middle head (y=4..11, x=13..20 in 24x24 icon) to metallic silver + red eye
    on JPN[212] / USA[73] frames 6..11 for Monster Select & Battle Results MKG mini portrait!
    """
    oam_dims = {(0,0):(8,8),(0,1):(16,16),(0,2):(32,32),(1,0):(16,8),(1,1):(32,8),(1,2):(32,16),(2,0):(8,16),(2,1):(8,32),(2,2):(16,32)}
    g2s = {1: 13, 2: 8, 3: 9, 4: 10, 5: 11, 6: 11, 7: 8}
    _, _, _, _, toff, _ = struct.unpack_from("<4H2I", blob212, 0)
    out = bytearray(blob212)
    for f in range(6, 12):
        oam_off, fto, ftl = struct.unpack_from("<3I", blob212, 16 + f * 12)
        cnt = struct.unpack_from("<H", blob212, oam_off + 24)[0]
        xs = struct.unpack_from(f"<{cnt}h", blob212, oam_off + 26)
        ys = struct.unpack_from(f"<{cnt}h", blob212, oam_off + 26 + cnt * 2)
        attrs = struct.unpack_from(f"<{cnt}H", blob212, oam_off + 26 + cnt * 4)
        tiles = bytearray(blob212[toff + fto : toff + fto + ftl])
        for i in range(cnt):
            x, y, a = xs[i], ys[i], attrs[i]
            w, h = oam_dims[((a >> 10) & 3, (a >> 12) & 3)]
            tid = a & 0x3FF
            for ty in range(h // 8):
                for tx in range(w // 8):
                    tb = (tid + ty * (w // 8) + tx) * 32
                    for py in range(8):
                        for px in range(4):
                            b = tiles[tb + py * 4 + px]
                            c0, c1 = b & 0xF, b >> 4
                            gy = 12 + y + ty * 8 + py
                            gx0 = 12 + x + tx * 8 + px * 2
                            gx1 = gx0 + 1
                            if 4 <= gy <= 11:
                                if 13 <= gx0 <= 20:
                                    c0 = g2s[c0] if c0 in g2s else (7 if (c0 == 13 and gy <= 8) else c0)
                                if 13 <= gx1 <= 20:
                                    c1 = g2s[c1] if c1 in g2s else (7 if (c1 == 13 and gy <= 8) else c1)
                            tiles[tb + py * 4 + px] = c0 | (c1 << 4)
        out[toff + fto : toff + fto + ftl] = tiles
    return bytes(out)


def build_big_nameplate_229_15f(usa147: bytes, kiryu_on_f3: bool) -> bytes:
    """Build 15-frame 4bpp Monster Select / 2P Giant VS Nameplates (JPN[229]) from USA[147] (9f):
    - Uses 100% authentic WayForward distressed Domination font letters sliced verbatim from USA[147]
      for KIRYU™, M-GHIDORAH™, FIRE RODAN™, GODZILLA '99, MOTHRA '92, and MEGALON-01!
    - Preserves official WayForward logos for f0..f7 (swapping f3 <-> official MECHAGODZILLA™ via SKIN_MASK bit 1).
    """
    bpp, mo, mt, nf, toff, _ = struct.unpack_from("<4H2I", usa147, 0)
    assert bpp == 0x0F00 and nf == 9

    oam_blocks: list[bytes] = []
    tile_blocks: list[bytes] = []
    for f in range(nf):
        oam_off, fto, ftl = struct.unpack_from("<3I", usa147, 16 + f * 12)
        cnt = struct.unpack_from("<H", usa147, oam_off + 24)[0]
        oam_blocks.append(usa147[oam_off : oam_off + 26 + cnt * 6])
        tile_blocks.append(usa147[toff + fto : toff + fto + ftl])

    hdr24 = oam_blocks[2][:24]
    oam_dims = {(0,0):(8,8),(0,1):(16,16),(0,2):(32,32),(1,0):(16,8),(1,1):(32,8),(1,2):(32,16),(2,0):(8,16),(2,1):(8,32),(2,2):(16,32)}

    def dec_u147(f_idx: int, ox_c: int) -> list[list[int]]:
        oam_o, fto_u, ftl_u = struct.unpack_from("<3I", usa147, 16 + f_idx * 12)
        cnt_u = struct.unpack_from("<H", usa147, oam_o + 24)[0]
        xs_u = struct.unpack_from(f"<{cnt_u}h", usa147, oam_o + 26)
        ys_u = struct.unpack_from(f"<{cnt_u}h", usa147, oam_o + 26 + cnt_u * 2)
        at_u = struct.unpack_from(f"<{cnt_u}H", usa147, oam_o + 26 + cnt_u * 4)
        t_u = usa147[toff + fto_u : toff + fto_u + ftl_u]
        g_u = [[0] * 200 for _ in range(24)]
        for i in reversed(range(cnt_u)):
            x, y, a = xs_u[i], ys_u[i], at_u[i]
            w, h = oam_dims[((a >> 10) & 3, (a >> 12) & 3)]
            tid = a & 0x3FF
            for ty in range(h // 8):
                for tx in range(w // 8):
                    tb = t_u[(tid + ty * (w // 8) + tx) * 32 : (tid + ty * (w // 8) + tx + 1) * 32]
                    for py in range(8):
                        for px in range(8):
                            b = tb[py * 4 + (px >> 1)]
                            v = (b >> 4) if (px & 1) else (b & 0xF)
                            gx, gy = ox_c + x + tx * 8 + px, 12 + y + ty * 8 + py
                            if v and 0 <= gx < 200 and 0 <= gy < 24:
                                g_u[gy][gx] = v
        return g_u

    g0 = dec_u147(0, 50)   # GODZILLA®
    g1 = dec_u147(1, 60)   # KING GHIDORAH™
    g2 = dec_u147(2, 40)   # RODAN™
    g3 = dec_u147(3, 60)   # MECHAGODZILLA™
    g4 = dec_u147(4, 40)   # MOTHRA™
    g5 = dec_u147(5, 45)   # MEGALON™
    g8 = dec_u147(8, 100)  # MECHA-KING GHIDORAH™

    def encode_96x24(grid: list[list[int]]) -> tuple[bytes, bytes]:
        # Center non-empty span inside 112x24 (matches official MECHAGODZILLA™ width!)
        # Encoded as 8 OBJs: 3x(32x16)+1x(16x16) + 3x(32x8)+1x(16x8) = 42 tiles (zero cramping/clipping!)
        cols = [x for x in range(len(grid[0])) if any(grid[y][x] for y in range(24))]
        if cols:
            x0, x1 = min(cols), max(cols)
            w_used = x1 - x0 + 1
            shift = max(0, (112 - w_used) // 2)
            cgrid = [[0] * 112 for _ in range(24)]
            for y in range(24):
                for x in range(x0, x1 + 1):
                    dx = shift + (x - x0)
                    if 0 <= dx < 112:
                        cgrid[y][dx] = grid[y][x]
        else:
            cgrid = [[0] * 112 for _ in range(24)]

        tiles = bytearray(42 * 32)
        for ox_px, oy_px, tw, th, base_t in (
            (0,  0, 4, 2,  0), (32, 0, 4, 2,  8), (64, 0, 4, 2, 16), (96, 0, 2, 2, 24),
            (0, 16, 4, 1, 28), (32,16, 4, 1, 32), (64,16, 4, 1, 36), (96,16, 2, 1, 40),
        ):
            for ty in range(th):
                for tx in range(tw):
                    tb = (base_t + ty * tw + tx) * 32
                    for py in range(8):
                        for px in range(4):
                            c0 = cgrid[oy_px + ty * 8 + py][ox_px + tx * 8 + px * 2] & 0xF
                            c1 = cgrid[oy_px + ty * 8 + py][ox_px + tx * 8 + px * 2 + 1] & 0xF
                            tiles[tb + py * 4 + px] = c0 | (c1 << 4)
        oam = hdr24 + struct.pack(
            "<H8h8h8H",
            8,
            -56, -24, 8, 40, -56, -24, 8, 40,
            -12, -12, -12, -12, 4, 4, 4, 4,
            0x2400, 0x2408, 0x2410, 0x1018, 0x141C, 0x1420, 0x1424, 0x0428,
        )
        return oam, bytes(tiles)

    def blit(dst: list[list[int]], src: list[list[int]], sx0: int, sx1: int, dx: int) -> int:
        for y in range(2, 22):
            for sx in range(sx0, sx1 + 1):
                v = src[y][sx]
                if v and 0 <= dx + (sx - sx0) < len(dst[0]):
                    dst[y][dx + (sx - sx0)] = v
        return dx + (sx1 - sx0 + 1)

    def blit_bmp(dst: list[list[int]], bmp: tuple[str, ...], dx: int, dy0: int = 3) -> int:
        for dy, row in enumerate(bmp):
            for lx, ch in enumerate(row):
                if ch != "." and 0 <= dx + lx < len(dst[0]):
                    dst[dy0 + dy][dx + lx] = int(ch, 16)
        return dx + len(bmp[0])

    # Distressed Domination-font custom glyphs matching USA[147] (idx 1=white, 4/6/8=grunge, F=outline)
    BMP_Y = (
        "FFFFFFFFF", "FDBFFFDBF", "F116F611F", "F116F611F",
        "F118F811F", "F4118114F", "FF11111FF", "FF61116FF",
        "FFF111FFF", "FFF111FFF", "FFF111FFF", "FFF111FFF",
        "FFF111FFF", "FFF111FFF", "FFF111FFF", "FFF848FFF",
        "FFFFFFFFF", ".FFFFFFF.",
    )
    BMP_APOS = (".FFF.", "F111F", "F111F", "F611F", ".F1FF", "..FF.")
    BMP_9 = (
        ".FFFFFFF.", "FDBBBBDBF", "F1111111F", "F1188111F",
        "F1188111F", "F1188111F", "F1144111F", "F6111111F",
        "FFBBBB11F", "FFFFFF11F", "FFFFFF11F", "FFFFFF11F",
        "FFFFFF11F", "F1111111F", "F1111111F", "F8444448F",
        ".FFFFFFF.", "..FFFFF..",
    )
    BMP_2 = (
        ".FFFFFFF.", "FDBBBBDBF", "F1111111F", "F1144111F",
        "F6FFFF11F", "FFFFFF11F", "FFFFFF11F", "FF111111F",
        "F1111116F", "F111FFFFF", "F11FFFFFF", "F11FFFFFF",
        "F11FFFFFF", "F1111111F", "F1111111F", "F8444448F",
        ".FFFFFFF.", "..FFFFF..",
    )
    BMP_0 = (
        ".FFFFFFF.", "FDBBBBDBF", "F1111111F", "F1188111F",
        "F11FF111F", "F11FF111F", "F11FF111F", "F11FF111F",
        "F11FF111F", "F11FF111F", "F11FF111F", "F11FF111F",
        "F1188111F", "F1111111F", "F1111111F", "F8444448F",
        ".FFFFFFF.", "..FFFFF..",
    )
    BMP_3 = (
        ".FFFFFFF.", "FDBBBBDBF", "F1111111F", "F1144111F",
        "F6FFFF11F", "FFFFFF11F", "FFF11111F", "FFF11111F",
        "FFFFFF11F", "FFFFFF11F", "FFFFFF11F", "F6FFFF11F",
        "F1144111F", "F1111111F", "F1111111F", "F8444448F",
        ".FFFFFFF.", "..FFFFF..",
    )
    BMP_1 = (
        "..FFFF...", ".FDBBBF..", "F11111F..", "F11811F..",
        "FFF111F..", "..F111F..", "..F111F..", "..F111F..",
        "..F111F..", "..F111F..", "..F111F..", "..F111F..",
        "..F111F..", "FF11111FF", "F1111111F", "F8444448F",
        "FFFFFFFFF", ".FFFFFFF.",
    )
    BMP_F = (
        "FFFFFFFFF", "FDBBBBBDF", "F1111111F", "F1114411F",
        "F111FFFFF", "F111FFFFF", "F111FFFFF", "F111111FF",
        "F1111118F", "F111FFFFF", "F111FFFFF", "F111FFFFF",
        "F111FFFFF", "F111FFFFF", "F111FFFFF", "F848FFFFF",
        "FFFFF....", ".FFF.....",
    )

    # 1. KIRYU™ (official K, I, R, O->U, ™ + distressed Y)
    gr_k = [[0] * 96 for _ in range(24)]
    cx = blit(gr_k, g1, 13, 22, 0)
    cx = blit(gr_k, g1, 23, 27, cx)
    cx = blit(gr_k, g2, 17, 25, cx)
    cx = blit_bmp(gr_k, BMP_Y, cx)
    u_x = cx
    for y in range(3, 21):
        for sx in range(26, 35):
            lx = sx - 26
            v = g2[y][sx]
            if 3 <= lx <= 5 and y <= 8:
                v = 0
            if v:
                gr_k[y][u_x + lx] = v
    for y in range(3, 10):
        gr_k[y][u_x + 4] = 0xF if y == 9 else 0
    for y in range(3, 9):
        gr_k[y][u_x + 3] = 0xF if y >= 5 else 0
        gr_k[y][u_x + 5] = 0xF if y >= 5 else 0
    cx = u_x + 11
    for y in range(3, 6):
        for sx in range(66, 73):
            if g2[y][sx]:
                gr_k[y][cx + (sx - 66)] = g2[y][sx]
    kiryu_oam, kiryu_t = encode_96x24(gr_k)

    # 2. M-GHIDORAH™ (official M from f3 + official '-' from f8 + official 'GHIDORAH™' from f1!)
    gr_mkg = [[0] * 112 for _ in range(24)]
    cx = blit(gr_mkg, g3, 12, 22, 0)
    cx = blit(gr_mkg, g8, 45, 51, cx)
    cx = blit(gr_mkg, g1, 47, 114, cx)
    mkg_oam, mkg_t = encode_96x24(gr_mkg)

    # 3. FIRE RODAN™ (distressed BMP_F + official I, R, E with crisp spacing + official RODAN™!)
    gr_fr = [[0] * 112 for _ in range(24)]
    cx = blit_bmp(gr_fr, BMP_F, 0, dy0=2)
    cx = blit(gr_fr, g1, 23, 27, cx) + 1
    cx = blit(gr_fr, g2, 17, 25, cx)
    e_start = cx
    cx = blit(gr_fr, g3, 22, 28, cx)
    for y in range(2, 22):
        if gr_fr[y][cx - 1] in (1, 4, 6, 8, 0xB, 0xD) and cx < 112:
            gr_fr[y][cx] = 0xF
    cx += 3
    cx = blit(gr_fr, g2, 15, 71, cx)
    fr_oam, fr_t = encode_96x24(gr_fr)

    # 4. GODZILLA '99 (official GODZILLA from f0 w/ full A outline + crisp distressed '99!)
    gr_g99 = [[0] * 112 for _ in range(24)]
    cx = blit(gr_g99, g0, 14, 82, 0) + 1
    cx = blit_bmp(gr_g99, BMP_APOS, cx, dy0=2)
    cx = blit_bmp(gr_g99, BMP_9, cx, dy0=2)
    cx = blit_bmp(gr_g99, BMP_9, cx, dy0=2)
    g99_oam, g99_t = encode_96x24(gr_g99)

    # 5. MOTHRA '92 (official MOTHRA from f4 w/ full A outline + crisp distressed '92!)
    gr_m92 = [[0] * 112 for _ in range(24)]
    cx = blit(gr_m92, g4, 10, 66, 0) + 1
    cx = blit_bmp(gr_m92, BMP_APOS, cx, dy0=2)
    cx = blit_bmp(gr_m92, BMP_9, cx, dy0=2)
    cx = blit_bmp(gr_m92, BMP_2, cx, dy0=2)
    m92_oam, m92_t = encode_96x24(gr_m92)

    # 6. MEGALON-01 (official MEGALON from f5 w/ full N outline + '-' + crisp distressed '0' & '1'!)
    gr_m01 = [[0] * 112 for _ in range(24)]
    cx = blit(gr_m01, g5, 11, 76, 0)
    cx = blit(gr_m01, g8, 45, 51, cx) + 1
    cx = blit_bmp(gr_m01, BMP_0, cx, dy0=2) + 1
    cx = blit_bmp(gr_m01, BMP_1, cx, dy0=2)
    m01_oam, m01_t = encode_96x24(gr_m01)

    # 4b. GODZILLA '03 (official GODZILLA from f0 w/ full A outline + crisp distressed '03!)
    gr_g03 = [[0] * 112 for _ in range(24)]
    cx = blit(gr_g03, g0, 14, 82, 0) + 1
    cx = blit_bmp(gr_g03, BMP_APOS, cx, dy0=2)
    cx = blit_bmp(gr_g03, BMP_0, cx, dy0=2)
    cx = blit_bmp(gr_g03, BMP_3, cx, dy0=2)
    g03_oam, g03_t = encode_96x24(gr_g03)

    # 5b. MOTHRA '03 (official MOTHRA from f4 w/ full A outline + crisp distressed '03!)
    gr_m03 = [[0] * 112 for _ in range(24)]
    cx = blit(gr_m03, g4, 10, 66, 0) + 1
    cx = blit_bmp(gr_m03, BMP_APOS, cx, dy0=2)
    cx = blit_bmp(gr_m03, BMP_0, cx, dy0=2)
    cx = blit_bmp(gr_m03, BMP_3, cx, dy0=2)
    m03_oam, m03_t = encode_96x24(gr_m03)

    orig_f3_oam, orig_f3_t = oam_blocks[3], tile_blocks[3]
    oam_blocks[0], tile_blocks[0] = g03_oam, g03_t
    oam_blocks[4], tile_blocks[4] = m03_oam, m03_t
    if kiryu_on_f3:
        oam_blocks[3], tile_blocks[3] = kiryu_oam, kiryu_t
    oam_blocks[8], tile_blocks[8] = mkg_oam, mkg_t

    for ob, tb in (
        (g99_oam, g99_t),        # f9  : GODZILLA '99
        (mkg_oam, mkg_t),        # f10 : M-GHIDORAH™
        (fr_oam, fr_t),          # f11 : FIRE RODAN™
        (orig_f3_oam, orig_f3_t),# f12 : official MECHAGODZILLA™
        (m92_oam, m92_t),        # f13 : MOTHRA '92
        (m01_oam, m01_t),        # f14 : MEGALON-01
    ):
        oam_blocks.append(ob)
        tile_blocks.append(tb)

    new_nf = len(oam_blocks)
    cur = 16 + new_nf * 12
    oam_offs: list[int] = []
    for ob in oam_blocks:
        oam_offs.append(cur)
        cur += len(ob)
    while cur % 4 != 0:
        cur += 1
    new_toff = cur
    tile_offs: list[int] = []
    tcur = 0
    for tb in tile_blocks:
        tile_offs.append(tcur)
        tcur += len(tb)

    out = bytearray()
    out.extend(struct.pack("<4H2I", bpp, mo, mt, new_nf, new_toff, tcur))
    for f in range(new_nf):
        out.extend(struct.pack("<3I", oam_offs[f], tile_offs[f], len(tile_blocks[f])))
    for ob in oam_blocks:
        out.extend(ob)
    while len(out) < new_toff:
        out.append(0)
    for tb in tile_blocks:
        out.extend(tb)
    return bytes(out)


def build_vs_3p4p_names_15f(usa119: bytes) -> bytes:
    """Build 15-frame 8bpp 3P/4P Pre-Battle VS Nameplates (JPN[216]) with crisp outlined era/variant
    names for all 12 fighters (f0..f5 = IDs 1..6, f6..f8 = pad, f9..f14 = IDs 7..12).
    Uses JPN[335]'s exact 8bpp VS palette indices: 17=white, 22=silver-gray bevel, 31=black outline.
    """
    bpp, _, _, _, _, _ = struct.unpack_from("<4H2I", usa119, 0)
    assert bpp == 0xFF00

    names_15 = (
        "GODZILLA '03",   # f0  (ID  1)
        "KING GHIDORAH",  # f1  (ID  2)
        "RODAN",          # f2  (ID  3)
        "KIRYU",          # f3  (ID  4)
        "MOTHRA '03",     # f4  (ID  5)
        "MEGALON",        # f5  (ID  6)
        "GODZILLA '03",   # f6  (pad)
        "GODZILLA '03",   # f7  (pad)
        "GODZILLA '03",   # f8  (pad)
        "GODZILLA '99",   # f9  (ID  7)
        "MECHA-GHIDORAH", # f10 (ID  8)
        "FIRE RODAN",     # f11 (ID  9)
        "MECHAGODZILLA",  # f12 (ID 10)
        "MOTHRA '92",     # f13 (ID 11)
        "MEGALON-01",     # f14 (ID 12)
    )

    oam_blocks: list[bytes] = []
    tile_blocks: list[bytes] = []
    # Template 24B bbox header from USA[119] f3 (56px wide, 3 OBJs: 32x8 + 16x8 + 8x8 at y=-6)
    oam3_off = struct.unpack_from("<I", usa119, 16 + 3 * 12)[0]
    hdr24 = usa119[oam3_off : oam3_off + 24]
    # Structure-of-Arrays OAM: cnt=3, xs=(-18, 14, 30) so 56px centered text never clips off the right (or left)
    # edge of the 240px screen on 3P/4P VS cards! In 8bpp (0xFF00), tile numbers step by 2: 32x8=0, 16x8=8, 8x8=12.
    oam_56x8 = hdr24 + struct.pack("<H3h3h3H", 3, -18, 14, 30, -6, -6, -6, 0x9400, 0x8408, 0x800C)

    for text in names_15:
        grid = [[0] * 56 for _ in range(8)]
        # Measure width to center nicely inside 56px
        tw = sum(len(_CUSTOM_FONT_3X7.get(ch, _CUSTOM_FONT_3X7[" "])[0]) + 1 for ch in text) - 1
        cx = max(1, (56 - tw) // 2)
        for ch in text:
            g = _CUSTOM_FONT_3X7.get(ch, _CUSTOM_FONT_3X7[" "])
            w = len(g[0])
            for gy, row in enumerate(g):
                for gx in range(w):
                    if row[gx] == "#" and 0 <= (cx + gx) < 55 and (gy + 1) < 8:
                        grid[gy + 1][cx + gx] = 22 if gy >= 5 else 17
            cx += w + 1
        outlined = [row[:] for row in grid]
        for y in range(8):
            for x in range(56):
                if grid[y][x] == 0:
                    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < 8 and 0 <= nx < 56 and grid[ny][nx] in (17, 22):
                            outlined[y][x] = 31
                            break
        # Encode 7 8x8 8bpp tiles (7 * 64 = 448 B)
        tbytes = bytearray(7 * 64)
        for t in range(7):
            tb = t * 64
            for py in range(8):
                for px in range(8):
                    tbytes[tb + py * 8 + px] = outlined[py][t * 8 + px]
        oam_blocks.append(oam_56x8)
        tile_blocks.append(bytes(tbytes))

    nf = len(oam_blocks)
    cur = 16 + nf * 12
    oam_offs: list[int] = []
    for ob in oam_blocks:
        oam_offs.append(cur)
        cur += len(ob)
    while cur % 4 != 0:
        cur += 1
    toff = cur

    tile_offs: list[int] = []
    tcur = 0
    for tb in tile_blocks:
        tile_offs.append(tcur)
        tcur += len(tb)

    out = bytearray()
    out.extend(struct.pack("<4H2I", bpp, 3, 448, nf, toff, tcur))
    for f in range(nf):
        out.extend(struct.pack("<3I", oam_offs[f], tile_offs[f], len(tile_blocks[f])))
    for ob in oam_blocks:
        out.extend(ob)
    while len(out) < toff:
        out.append(0)
    for tb in tile_blocks:
        out.extend(tb)
    return bytes(out)


def recolor_8bpp_pack_frames(pack_blob: bytes, vs_pal256: list[tuple[int, int, int]], frame_modes: dict[int, str]) -> bytes:
    """Recolor selected frames of an 8bpp sprite pack (JPN[231]/JPN[243]) using nearest colors in JPN[335]'s 256-color palette."""
    bpp, mo, mt, nf, toff, tsz = struct.unpack_from("<4H2I", pack_blob, 0)
    assert bpp == 0xFF00
    out = bytearray(pack_blob)

    def nearest_idx(r: int, g: int, b: int) -> int:
        best_i, best_d = 1, 10**9
        for i in range(1, 256):
            pr, pg, pb = vs_pal256[i]
            d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
            if d < best_d:
                best_d, best_i = d, i
        return best_i

    # Precompute 256-entry LUT per mode
    luts: dict[str, bytes] = {}
    for mode in set(frame_modes.values()):
        lut = bytearray(256)
        lut[0] = 0
        for i in range(1, 256):
            r, g, b = vs_pal256[i]
            if mode == "fire_rodan":
                # Shift warm browns/tans/yellows into blazing crimson-red & fiery orange-gold
                if r > 32 and r >= b + 16 and g < r:
                    nr = min(248, int(r * 1.25 + 24))
                    ng = int(g * 0.48) if g < r * 0.72 else min(240, int(g * 1.05))
                    nb = int(b * 0.25)
                    lut[i] = nearest_idx(nr, ng, nb)
                else:
                    lut[i] = i
            elif mode == "megalon01":
                # Swap emerald-green / teal-cyan carapace <-> purple/violet body (Eva Unit-01!)
                if (g > r + 10 and g >= b - 16) or (b > r + 14 and g > r + 8):
                    # Green / Teal carapace -> Rich Eva-01 Purple!
                    v = max(g, b)
                    lut[i] = nearest_idx(min(248, int(v * 0.80)), int(r * 0.65), min(248, int(v * 0.98)))
                elif r > g + 10 and b > g + 10:
                    # Purple/magenta -> Neon Eva-01 Emerald Green!
                    lut[i] = nearest_idx(int(g * 0.8), min(248, int(max(r, b) * 1.05)), min(248, int(b * 0.65)))
                else:
                    lut[i] = i
            elif mode == "news_fire_rodan":
                # Connie News Fire Rodan in JPN[365]'s 256-color palette:
                # Shift warm brown/ochre/gold skin & wings (r > b+28) -> fiery crimson-red/orange,
                # preserving pale cream beak/belly (r>190, g>180, b>125) and starry blue-purple sky!
                if r > 190 and g > 180 and b > 125:
                    lut[i] = i
                elif r > 40 and r >= b + 28 and g < r:
                    nr = min(248, int(r * 1.35 + 32))
                    ng = int(g * 0.42)
                    nb = int(b * 0.25)
                    lut[i] = nearest_idx(nr, ng, nb)
                else:
                    lut[i] = i
            elif mode == "news_megalon01":
                # Connie News Megalon-01 in JPN[365]'s 256-color palette:
                # Shift Megalon's emerald-green / teal carapace (g > r+10 and g >= b-8) -> rich Eva-01 purple,
                # leaving his orange eyes, silver drills, white border, and starry news sky 100% untouched!
                if g > r + 10 and g >= b - 8:
                    v = max(g, b)
                    lut[i] = nearest_idx(min(248, int(v * 0.82)), int(r * 0.55), min(248, int(v * 0.96)))
                else:
                    lut[i] = i
            elif mode == "news_shadow_mkg":
                # Connie News Shadow Mecha-King Ghidorah in JPN[365]'s 256-color palette:
                # Preserve the starry blue-purple news sky (b > r+12), crisp white border (r,g,b > 235),
                # and glowing red eyes (r > 160, g < 80, b < 80), while turning Ghidorah's golden heads
                # into an ominous dark shadow silhouette!
                if r > 235 and g > 235 and b > 235:
                    lut[i] = i
                elif b > r + 12 or (b > g + 16 and r > 80 and b > 100):
                    lut[i] = i  # preserve starry blue-purple news sky!
                elif r > 160 and g < 85 and b < 85:
                    lut[i] = i  # preserve glowing red eyes!
                else:
                    lum = (r * 30 + g * 59 + b * 11) // 100
                    v = min(40, lum // 6)
                    lut[i] = nearest_idx(v, v, min(56, v + 8))
            else:
                lut[i] = i
        luts[mode] = bytes(lut)

    for f_idx, mode in frame_modes.items():
        if f_idx >= nf:
            continue
        _, fto, ftl = struct.unpack_from("<3I", pack_blob, 16 + f_idx * 12)
        lut = luts[mode]
        start = toff + fto
        for k in range(start, start + ftl):
            out[k] = lut[out[k]]
    return bytes(out)


def build_shadow_mkg_3p4p_portrait(vs_portraits_15f: bytes, jpn_231: bytes, jpn_243: bytes, target_frame: int = 10) -> bytes:
    """Replace 3P/4P VS portrait `target_frame` (104x40 8bpp) with the official 2P Giant VS
    Shadow Mecha-King Ghidorah silhouette (`JPN[243]` f6) framed inside `JPN[231]`'s exact white card border.
    """
    oam_dims = {
        (0, 0): (8, 8),   (0, 1): (16, 16), (0, 2): (32, 32), (0, 3): (64, 64),
        (1, 0): (16, 8),  (1, 1): (32, 8),  (1, 2): (32, 16), (1, 3): (64, 32),
        (2, 0): (8, 16),  (2, 1): (8, 32),  (2, 2): (16, 32), (2, 3): (32, 64),
    }

    def decode_8bpp_frame(blob: bytes, f: int) -> list[list[int]]:
        _, _, _, _, toff, _ = struct.unpack_from("<4H2I", blob, 0)
        oam_off, fto, _ = struct.unpack_from("<3I", blob, 16 + f * 12)
        cnt = struct.unpack_from("<H", blob, oam_off + 24)[0]
        xs = struct.unpack_from(f"<{cnt}h", blob, oam_off + 26)
        ys = struct.unpack_from(f"<{cnt}h", blob, oam_off + 26 + cnt * 2)
        attrs = struct.unpack_from(f"<{cnt}H", blob, oam_off + 26 + cnt * 4)
        minx, miny = min(xs), min(ys)
        maxx = max(xs[i] + oam_dims[((attrs[i] >> 10) & 3, (attrs[i] >> 12) & 3)][0] for i in range(cnt))
        maxy = max(ys[i] + oam_dims[((attrs[i] >> 10) & 3, (attrs[i] >> 12) & 3)][1] for i in range(cnt))
        grid = [[0] * (maxx - minx) for _ in range(maxy - miny)]
        for i in range(cnt):
            x, y, a = xs[i] - minx, ys[i] - miny, attrs[i]
            w, h = oam_dims[((a >> 10) & 3, (a >> 12) & 3)]
            tid = a & 0x3FF
            for ty in range(h // 8):
                for tx in range(w // 8):
                    tb = toff + fto + tid * 32 + (ty * (w // 8) + tx) * 64
                    for py in range(8):
                        for px in range(8):
                            grid[y + ty * 8 + py][x + tx * 8 + px] = blob[tb + py * 8 + px]
        return grid

    g231 = decode_8bpp_frame(jpn_231, 1)  # 104x40 portrait card with crisp white/black border
    g243 = decode_8bpp_frame(jpn_243, 6)  # 104x128 official 2P Giant VS Shadow MKG
    H, W = len(g231), len(g231[0])
    card = [[0] * W for _ in range(H)]

    # Composite official Shadow MKG mechanical center head (transparent bg so VS stripes pop behind silhouette)
    for y in range(1, 38):
        for x in range(2, 99):
            sy = 55 + (y - 1)
            sx = 5 + (x - 2)
            if 0 <= sy < len(g243) and 0 <= sx < len(g243[0]):
                card[y][x] = g243[sy][sx]

    # Preserve exact white/black portrait card frame from JPN[231] (top y=0, bottom y=38..39, left x=0..1, right x=99)
    for y in range(H):
        for x in range(100):
            if y in (0, 38, 39) or x in (0, 1, 99):
                card[y][x] = g231[y][x]

    # Encode 104x40 8bpp grid back into target_frame's OAM tiles
    out = bytearray(vs_portraits_15f)
    _, _, _, _, toff, _ = struct.unpack_from("<4H2I", out, 0)
    oam_off, fto, _ = struct.unpack_from("<3I", out, 16 + target_frame * 12)
    cnt = struct.unpack_from("<H", out, oam_off + 24)[0]
    xs = struct.unpack_from(f"<{cnt}h", out, oam_off + 26)
    ys = struct.unpack_from(f"<{cnt}h", out, oam_off + 26 + cnt * 2)
    attrs = struct.unpack_from(f"<{cnt}H", out, oam_off + 26 + cnt * 4)
    minx, miny = min(xs), min(ys)
    for i in range(cnt):
        x, y, a = xs[i] - minx, ys[i] - miny, attrs[i]
        w, h = oam_dims[((a >> 10) & 3, (a >> 12) & 3)]
        tid = a & 0x3FF
        for ty in range(h // 8):
            for tx in range(w // 8):
                tb = toff + fto + tid * 32 + (ty * (w // 8) + tx) * 64
                for py in range(8):
                    for px in range(8):
                        out[tb + py * 8 + px] = card[y + ty * 8 + py][x + tx * 8 + px]
    return bytes(out)


def build_shadow_mkg_news_portrait(
    news_portraits_15f: bytes,
    jpn_230: bytes,
    jpn_243: bytes,
    news_pal256: list[tuple[int, int, int]],
    vs_pal256: list[tuple[int, int, int]],
    target_frame: int = 10,
) -> bytes:
    """Replace Connie News cutout `target_frame` (96x64 8bpp) with the official 2P Giant VS /
    Game Over Shadow Mecha-King Ghidorah silhouette (`JPN[243]` f6, facing left with glowing
    red organic eyes and cyan mechanical center eye) over the authentic starry purple news sky
    and crisp white border in `JPN[365]`'s 256-color palette.
    """
    oam_dims = {
        (0, 0): (8, 8),   (0, 1): (16, 16), (0, 2): (32, 32), (0, 3): (64, 64),
        (1, 0): (16, 8),  (1, 1): (32, 8),  (1, 2): (32, 16), (1, 3): (64, 32),
        (2, 0): (8, 16),  (2, 1): (8, 32),  (2, 2): (16, 32), (2, 3): (32, 64),
    }

    def decode_8bpp_frame(blob: bytes, f: int) -> list[list[int]]:
        _, _, _, _, toff, _ = struct.unpack_from("<4H2I", blob, 0)
        oam_off, fto, _ = struct.unpack_from("<3I", blob, 16 + f * 12)
        cnt = struct.unpack_from("<H", blob, oam_off + 24)[0]
        xs = struct.unpack_from(f"<{cnt}h", blob, oam_off + 26)
        ys = struct.unpack_from(f"<{cnt}h", blob, oam_off + 26 + cnt * 2)
        attrs = struct.unpack_from(f"<{cnt}H", blob, oam_off + 26 + cnt * 4)
        minx, miny = min(xs), min(ys)
        maxx = max(xs[i] + oam_dims[((attrs[i] >> 10) & 3, (attrs[i] >> 12) & 3)][0] for i in range(cnt))
        maxy = max(ys[i] + oam_dims[((attrs[i] >> 10) & 3, (attrs[i] >> 12) & 3)][1] for i in range(cnt))
        grid = [[0] * (maxx - minx) for _ in range(maxy - miny)]
        for i in range(cnt):
            x, y, a = xs[i] - minx, ys[i] - miny, attrs[i]
            w, h = oam_dims[((a >> 10) & 3, (a >> 12) & 3)]
            tid = a & 0x3FF
            for ty in range(h // 8):
                for tx in range(w // 8):
                    tb = toff + fto + tid * 32 + (ty * (w // 8) + tx) * 64
                    for py in range(8):
                        for px in range(8):
                            grid[y + ty * 8 + py][x + tx * 8 + px] = blob[tb + py * 8 + px]
        return grid

    g_f0 = decode_8bpp_frame(jpn_230, 0)
    g_f2 = decode_8bpp_frame(jpn_230, 2)
    g_f5 = decode_8bpp_frame(jpn_230, 5)
    g_f6 = decode_8bpp_frame(jpn_230, 6)
    g243 = decode_8bpp_frame(jpn_243, 6)  # 104x128 official Shadow MKG

    H, W = len(g_f0), len(g_f0[0])  # 64 x 96

    def is_sky(ci: int) -> bool:
        if ci == 0:
            return False
        r, g, b = news_pal256[ci]
        # True starry blue-purple news sky (excludes Megalon's gray/lavender drill!)
        return (b > r + 24 and b > g + 24) or (b > g + 34 and r < 165 and b > 110)

    # 1. Reconstruct clean 96x64 starry purple scanline sky + exact white border from JPN[230]
    card = [[0] * W for _ in range(H)]
    for y in range(H):
        row_sky = [0] * W
        for x in range(W):
            for src_g in (g_f6, g_f2, g_f0):
                ci = src_g[y][x]
                if is_sky(ci):
                    row_sky[x] = ci
                    break
        # Fill any gaps in this scanline by nearest sky pixel on the same row
        for x in range(W):
            if row_sky[x] == 0:
                best = 0
                for d in range(1, W):
                    if x - d >= 0 and row_sky[x - d] != 0:
                        best = row_sky[x - d]
                        break
                    if x + d < W and row_sky[x + d] != 0:
                        best = row_sky[x + d]
                        break
                row_sky[x] = best
        for x in range(W):
            card[y][x] = row_sky[x]

    # 2. Composite official Shadow MKG (JPN[243] f6, horizontally flipped to face LEFT like Game Over & news cutouts!)
    #    Scale 104x128 -> 68x58 inside the 92x58 interior, preserving glowing red & cyan eyes!
    src_h, src_w = len(g243), len(g243[0])
    dst_w, dst_h = 68, 57
    ox, oy = 25, 2
    IDX_BLACK = 247  # (0, 0, 0) in JPN[365]
    IDX_RED   = 244  # (232, 64, 64) in JPN[365]
    IDX_CYAN  = 124  # (112, 200, 208) in JPN[365]

    for dy in range(dst_h):
        sy0 = int(dy * src_h / dst_h)
        sy1 = max(sy0 + 1, int((dy + 1) * src_h / dst_h))
        for dx in range(dst_w):
            # Flip horizontally so all 3 heads face LEFT!
            fx = dst_w - 1 - dx
            sx0 = int(fx * src_w / dst_w)
            sx1 = max(sx0 + 1, int((fx + 1) * src_w / dst_w))
            has_body = False
            has_red = False
            has_cyan = False
            for sy in range(sy0, min(sy1, src_h)):
                for sx in range(sx0, min(sx1, src_w)):
                    ci = g243[sy][sx]
                    if ci == 0:
                        continue
                    r, g, b = vs_pal256[ci]
                    if b >= 140 and g >= 140 and r <= 120:
                        has_cyan = True
                    elif r >= 160 and g <= 80 and b <= 80:
                        has_red = True
                    else:
                        has_body = True
            tx, ty = ox + dx, oy + dy
            if 2 <= tx < W - 2 and 2 <= ty < H - 5:
                if has_cyan:
                    card[ty][tx] = IDX_CYAN
                elif has_red:
                    card[ty][tx] = IDX_RED
                elif has_body:
                    card[ty][tx] = IDX_BLACK

    # 3. Preserve exact white border from JPN[230] f0 (top y=0..1, bottom y=62..63, left x=0..1, right x=94..95)
    for y in range(H):
        for x in range(W):
            if g_f0[y][x] == 255 and (y <= 2 or y >= 57 or x <= 2 or x >= 91):
                card[y][x] = 255
            elif g_f0[y][x] == 0:
                card[y][x] = 0

    # 4. Encode 96x64 8bpp grid back into target_frame's OAM tiles
    out = bytearray(news_portraits_15f)
    _, _, _, _, toff, _ = struct.unpack_from("<4H2I", out, 0)
    oam_off, fto, _ = struct.unpack_from("<3I", out, 16 + target_frame * 12)
    cnt = struct.unpack_from("<H", out, oam_off + 24)[0]
    xs = struct.unpack_from(f"<{cnt}h", out, oam_off + 26)
    ys = struct.unpack_from(f"<{cnt}h", out, oam_off + 26 + cnt * 2)
    attrs = struct.unpack_from(f"<{cnt}H", out, oam_off + 26 + cnt * 4)
    minx, miny = min(xs), min(ys)
    for i in range(cnt):
        x, y, a = xs[i] - minx, ys[i] - miny, attrs[i]
        w, h = oam_dims[((a >> 10) & 3, (a >> 12) & 3)]
        tid = a & 0x3FF
        for ty in range(h // 8):
            for tx in range(w // 8):
                tb = toff + fto + tid * 32 + (ty * (w // 8) + tx) * 64
                for py in range(8):
                    for px in range(8):
                        out[tb + py * 8 + px] = card[y + ty * 8 + py][x + tx * 8 + px]
    return bytes(out)


def build_custom_stage_names_9f(usa126: bytes) -> bytes:
    """Expand USA[126] (7f Custom Mode stage names: Tokyo 2..Nova-b) -> 9f by appending:
      - f7: 'Tokyo 1' (spliced from f0 'Tokyo 2' + matching outlined '1' glyph)
      - f8: 'Random'  (rendered in USA[126]'s exact 2px-outlined bright-core bevel font)
    """
    bpp, mo, mt, nf, toff, _ = struct.unpack_from("<4H2I", usa126, 0)
    assert bpp == 0x0F00 and nf == 7
    oam_blocks: list[bytes] = []
    tile_blocks: list[bytes] = []
    for f in range(nf):
        oam_off, fto, ftl = struct.unpack_from("<3I", usa126, 16 + f * 12)
        cnt = struct.unpack_from("<H", usa126, oam_off + 24)[0]
        oam_blocks.append(usa126[oam_off : oam_off + 26 + cnt * 6])
        tile_blocks.append(usa126[toff + fto : toff + fto + ftl])

    oam_dims = {(0,0):(8,8),(0,1):(16,16),(0,2):(32,32),(1,0):(16,8),(1,1):(32,8),(1,2):(32,16),(2,0):(8,16),(2,1):(8,32),(2,2):(16,32)}

    def decode_f0() -> list[list[int]]:
        oam_off, fto, _ = struct.unpack_from("<3I", usa126, 16)
        cnt = struct.unpack_from("<H", usa126, oam_off + 24)[0]
        xs = struct.unpack_from(f"<{cnt}h", usa126, oam_off + 26)
        ys = struct.unpack_from(f"<{cnt}h", usa126, oam_off + 26 + cnt * 2)
        attrs = struct.unpack_from(f"<{cnt}H", usa126, oam_off + 26 + cnt * 4)
        minx, miny = min(xs), min(ys)
        g = [[0] * 56 for _ in range(16)]
        for i in range(cnt):
            x, y, a = xs[i] - minx, ys[i] - miny, attrs[i]
            w, h = oam_dims[((a >> 10) & 3, (a >> 12) & 3)]
            tid = a & 0x3FF
            for ty in range(h // 8):
                for tx in range(w // 8):
                    tb = toff + fto + (tid + ty * (w // 8) + tx) * 32
                    for py in range(8):
                        for px in range(4):
                            b = usa126[tb + py * 4 + px]
                            g[y + ty * 8 + py][x + tx * 8 + px * 2] = b & 0xF
                            g[y + ty * 8 + py][x + tx * 8 + px * 2 + 1] = (b >> 4) & 0xF
        return g

    def encode_56x16(grid: list[list[int]]) -> tuple[bytes, bytes]:
        tiles = bytearray(14 * 32)
        for ox, tw, base_t in ((0, 4, 0), (32, 2, 8), (48, 1, 12)):
            for ty in range(2):
                for tx in range(tw):
                    tb = (base_t + ty * tw + tx) * 32
                    for py in range(8):
                        for px in range(4):
                            c0 = grid[ty * 8 + py][ox + tx * 8 + px * 2] & 0xF
                            c1 = grid[ty * 8 + py][ox + tx * 8 + px * 2 + 1] & 0xF
                            tiles[tb + py * 4 + px] = c0 | (c1 << 4)
        return oam_blocks[0], bytes(tiles)

    def draw_outlined_text_56x16(glyphs: list[tuple[str, ...]], start_x: int, top_y: int = 3) -> list[list[int]]:
        core = [[0] * 56 for _ in range(16)]
        cx = start_x
        for gl in glyphs:
            for dy, row in enumerate(gl):
                for dx, ch in enumerate(row):
                    if ch == "#" and 0 <= top_y + dy < 16 and 0 <= cx + dx < 56:
                        core[top_y + dy][cx + dx] = 1
            cx += len(gl[0]) + 1
        g = [[0] * 56 for _ in range(16)]
        # Pure black-and-white matching vanilla 'Tokyo': idx 0xF = pure black letters, idx 1 = pure white outline
        for y in range(16):
            for x in range(56):
                if core[y][x]:
                    g[y][x] = 0xF
                else:
                    near1 = any(0 <= y+dy < 16 and 0 <= x+dx < 56 and core[y+dy][x+dx]
                                for dy in (-2, -1, 0, 1, 2) for dx in (-2, -1, 0, 1, 2)
                                if dx * dx + dy * dy <= 4)
                    if near1:
                        g[y][x] = 1
        return g

    # f7: "Tokyo 1" — exact "Tokyo " from f0 (x=0..38) + crisp outlined "1"
    g_t1 = decode_f0()
    for y in range(16):
        for x in range(39, 56):
            g_t1[y][x] = 0
    gl_1 = ("..##..", ".###..", "####..", "..##..", "..##..", "..##..", "..##..", "######")
    g1_tmp = draw_outlined_text_56x16([gl_1], start_x=42, top_y=3)
    for y in range(16):
        for x in range(39, 56):
            if g1_tmp[y][x]:
                g_t1[y][x] = g1_tmp[y][x]
    ob_t1, tb_t1 = encode_56x16(g_t1)
    oam_blocks.append(ob_t1)
    tile_blocks.append(tb_t1)

    # f8: "Random"
    gl_R = ("#####..", "##..##.", "##..##.", "#####..", "##.##..", "##..##.", "##..##.", "##..##.")
    gl_a = (".......", ".......", ".####..", "....##.", ".#####.", "##..##.", "##..##.", ".#####.")
    gl_n = (".......", ".......", "#####..", "##..##.", "##..##.", "##..##.", "##..##.", "##..##.")
    gl_d = ("....##.", "....##.", ".#####.", "##..##.", "##..##.", "##..##.", "##..##.", ".#####.")
    gl_o = (".......", ".......", ".####..", "##..##.", "##..##.", "##..##.", "##..##.", ".####..")
    gl_m = (".......", ".......", "########", "##.##.##", "##.##.##", "##.##.##", "##.##.##", "##.##.##")
    g_rnd = draw_outlined_text_56x16([gl_R, gl_a, gl_n, gl_d, gl_o, gl_m], start_x=4, top_y=3)
    ob_rnd, tb_rnd = encode_56x16(g_rnd)
    oam_blocks.append(ob_rnd)
    tile_blocks.append(tb_rnd)

    new_nf = len(oam_blocks)
    cur = 16 + new_nf * 12
    oam_offs: list[int] = []
    for ob in oam_blocks:
        oam_offs.append(cur)
        cur += len(ob)
    while cur % 4 != 0:
        cur += 1
    new_toff = cur
    tile_offs: list[int] = []
    tcur = 0
    for tb in tile_blocks:
        tile_offs.append(tcur)
        tcur += len(tb)
    out = bytearray()
    out.extend(struct.pack("<4H2I", bpp, mo, mt, new_nf, new_toff, tcur))
    for f in range(new_nf):
        out.extend(struct.pack("<3I", oam_offs[f], tile_offs[f], len(tile_blocks[f])))
    for ob in oam_blocks:
        out.extend(ob)
    while len(out) < new_toff:
        out.append(0)
    for tb in tile_blocks:
        out.extend(tb)
    return bytes(out)


def build_night_tokyo_bg_pal(jpn262: bytes) -> bytes:
    """Transform Tokyo 2's 512-byte BG palette (JPN[262][0:512]) into Nighttime Tokyo ('Tokyo 1'):
      - BG Pal 11 (daytime sky/clouds)   -> deep midnight-indigo night sky + moonlit clouds
      - BG Pal 13 (distant skyline)      -> midnight navy skyline + glowing warm-gold lights
      - BG Pal 0..10, 12 (streets/bldgs) -> cool moonlit slate-indigo + glowing warm-yellow windows
      - BG Pal 14..15 (Battle HUD)       -> UNTOUCHED!
    """
    cols = list(struct.unpack_from("<256H", jpn262, 0))
    out_cols = cols[:]
    for p in range(14):
        for i in range(16):
            c = cols[p * 16 + i]
            if i == 0:
                out_cols[p * 16 + i] = (7 << 10) | (2 << 5) | 1
                continue
            if c == 0:
                continue
            r, g, b = c & 31, (c >> 5) & 31, (c >> 10) & 31
            lum = (r * 30 + g * 59 + b * 11) // 100
            if p == 11:
                nr = max(1, min(31, int(r * 0.20)))
                ng = max(1, min(31, int(g * 0.24)))
                nb = max(4, min(31, int(b * 0.42)))
                out_cols[p * 16 + i] = (nb << 10) | (ng << 5) | nr
            elif p == 13:
                if lum >= 21:
                    out_cols[p * 16 + i] = (10 << 10) | (26 << 5) | 30
                else:
                    nr = max(1, min(31, int(r * 0.30)))
                    ng = max(2, min(31, int(g * 0.34)))
                    nb = max(5, min(31, int(b * 0.50)))
                    out_cols[p * 16 + i] = (nb << 10) | (ng << 5) | nr
            else:
                if p in (1, 2, 6, 7, 9, 10) and lum >= 24:
                    out_cols[p * 16 + i] = (12 << 10) | (27 << 5) | 31
                else:
                    nr = max(1, min(31, int(r * 0.38)))
                    ng = max(1, min(31, int(g * 0.44)))
                    nb = max(3, min(31, int(b * 0.62 + 3)))
                    out_cols[p * 16 + i] = (nb << 10) | (ng << 5) | nr
    return struct.pack("<256H", *out_cols)


def build_stat_bars_14f(usa131: bytes) -> bytes:
    """Expand Monster Select Speed/Power/Special stat bars (USA[131], 8f) -> 14f:
      - f0..f7 : Vanilla frames preserved verbatim
      - f8..f13: DX alt frames (Godzilla '99..Megalon-01) with Speed & Power(HP) bars shifted, Special untouched.
    """
    bpp, mo, mt, nf, toff, _ = struct.unpack_from("<4H2I", usa131, 0)
    assert bpp == 0x0F00 and nf == 8
    oam_blocks: list[bytes] = []
    tile_blocks: list[bytes] = []
    for f in range(nf):
        oam_off, fto, ftl = struct.unpack_from("<3I", usa131, 16 + f * 12)
        cnt = struct.unpack_from("<H", usa131, oam_off + 24)[0]
        oam_blocks.append(usa131[oam_off : oam_off + 26 + cnt * 6])
        tile_blocks.append(usa131[toff + fto : toff + fto + ftl])

    oam_dims = {(0,0):(8,8),(0,1):(16,16),(0,2):(32,32),(1,0):(16,8),(1,1):(32,8),(1,2):(32,16),(2,0):(8,16),(2,1):(8,32),(2,2):(16,32)}
    dx_bar_deltas = (
        (0, +5, -5),  # f8 : Godzilla '99   (Speed +1, Power -1)
        (1, -5, +6),  # f9 : Mini MKG       (Speed -1, Power +1)
        (2, +4, -4),  # f10: Fire Rodan     (Speed +1 max, Power -1)
        (3, -3, +4),  # f11: Classic MG     (Speed -1, Power +1)
        (4, +5, -4),  # f12: Mothra '92     (Speed +1, Power -1)
        (5, +5, -4),  # f13: Megalon-01     (Speed +1, Power -1)
    )
    for base_f, d_spd, d_pwr in dx_bar_deltas:
        oam_b = oam_blocks[base_f]
        tiles = bytearray(tile_blocks[base_f])
        cnt = struct.unpack_from("<H", oam_b, 24)[0]
        xs = struct.unpack_from(f"<{cnt}h", oam_b, 26)
        ys = struct.unpack_from(f"<{cnt}h", oam_b, 26 + cnt * 2)
        attrs = struct.unpack_from(f"<{cnt}H", oam_b, 26 + cnt * 4)
        g = [[0] * 48 for _ in range(28)]
        for i in range(cnt):
            if xs[i] < 0:
                continue
            x, y, a = xs[i], ys[i] + 12, attrs[i]
            w, h = oam_dims[((a >> 10) & 3, (a >> 12) & 3)]
            tid = a & 0x3FF
            for ty in range(h // 8):
                for tx in range(w // 8):
                    tb = (tid + ty * (w // 8) + tx) * 32
                    for py in range(8):
                        for px in range(4):
                            b = tiles[tb + py * 4 + px]
                            if 0 <= y + ty * 8 + py < 28:
                                g[y + ty * 8 + py][x + tx * 8 + px * 2] = b & 0xF
                                g[y + ty * 8 + py][x + tx * 8 + px * 2 + 1] = (b >> 4) & 0xF

        def shift_bar(row_top: int, delta: int) -> None:
            mid = g[row_top + 1]
            cur_end = max((x for x in range(1, 41) if mid[x] == 3), default=4)
            new_end = max(3, min(40, cur_end + delta))
            for x in range(1, 41):
                filled = (x <= new_end)
                g[row_top][x] = 5 if filled else 0
                g[row_top + 1][x] = 3 if filled else 0xF
                g[row_top + 2][x] = 3 if filled else 0xF
                g[row_top + 3][x] = 5 if filled else 0
            g[row_top][0] = g[row_top + 1][0] = g[row_top + 2][0] = g[row_top + 3][0] = 5

        shift_bar(1, d_spd)
        shift_bar(11, d_pwr)

        for i in range(cnt):
            if xs[i] < 0:
                continue
            x, y, a = xs[i], ys[i] + 12, attrs[i]
            w, h = oam_dims[((a >> 10) & 3, (a >> 12) & 3)]
            tid = a & 0x3FF
            for ty in range(h // 8):
                for tx in range(w // 8):
                    tb = (tid + ty * (w // 8) + tx) * 32
                    for py in range(8):
                        for px in range(4):
                            if 0 <= y + ty * 8 + py < 28:
                                c0 = g[y + ty * 8 + py][x + tx * 8 + px * 2] & 0xF
                                c1 = g[y + ty * 8 + py][x + tx * 8 + px * 2 + 1] & 0xF
                                tiles[tb + py * 4 + px] = c0 | (c1 << 4)
        oam_blocks.append(oam_b)
        tile_blocks.append(bytes(tiles))

    new_nf = len(oam_blocks)
    cur = 16 + new_nf * 12
    oam_offs: list[int] = []
    for ob in oam_blocks:
        oam_offs.append(cur)
        cur += len(ob)
    while cur % 4 != 0:
        cur += 1
    new_toff = cur
    tile_offs: list[int] = []
    tcur = 0
    for tb in tile_blocks:
        tile_offs.append(tcur)
        tcur += len(tb)
    out = bytearray()
    out.extend(struct.pack("<4H2I", bpp, mo, mt, new_nf, new_toff, tcur))
    for f in range(new_nf):
        out.extend(struct.pack("<3I", oam_offs[f], tile_offs[f], len(tile_blocks[f])))
    for ob in oam_blocks:
        out.extend(ob)
    while len(out) < new_toff:
        out.append(0)
    for tb in tile_blocks:
        out.extend(tb)
    return bytes(out)


def build_cave_code(
    skin_dispatch_table_addr: int,
    usa_pal2_addr: int,
    usa_pal4_addr: int,
    jpn_pal2_addr: int,
    jpn_pal4_addr: int,
    jpn_pal3_addr: int,
    mkg_pal3_addr: int,
    jpn_pal6_addr: int,
    fire_rodan_pal6_addr: int,
    jpn_pal7_addr: int,
    purple_megalon_pal7_addr: int,
    hud_name_tbl_addr: int,
    night_tokyo_bg_pal_addr: int,
    eng_text_base_addr: int,
    eng_text_alt_addr: int,
) -> tuple[bytes, dict[str, int]]:
    """Assemble all Thumb hook routines into the verified free-space cave at 0x083D2D00."""
    base = 0x08000000 + CAVE_BASE
    blob = bytearray()
    addrs: dict[str, int] = {}

    def align4() -> None:
        while len(blob) % 4 != 0:
            blob.append(0x00)

    # ------------------------------------------------------------------
    # Helper: copy_palettes_by_flag() — copies 32B OBJ Pal 2 (Godzilla, b0),
    # Pal 3 (KG/MKG, b3), Pal 4 (Mothra, b2), Pal 6 (Rodan/Fire Rodan, b4),
    # & Pal 7 (Megalon/Eva Purple Megalon, b5) independently into BOTH
    # shadow palette RAM (0x03002D50+) AND active scene descriptor (0x03004100+).
    # ------------------------------------------------------------------
    align4()
    addrs["copy_palettes"] = base + len(blob)
    src_copy = f"""
        push {{r0, r1, r2, r3, r4, r5, lr}}
        ldr  r0, =0x{SKIN_MASK_ADDR:08X}
        ldrb r2, [r0]               @ r2 = SKIN_MASK (b0=GZ, b1=MG, b2=MO, b3=MKG, b4=Rodan, b5=Megalon)

        @ Pal 2 (Godzilla): check bit 0
        movs r0, #1
        tst  r2, r0
        beq  gz_jpn_pal
        ldr  r1, =0x{usa_pal2_addr:08X}
        b    do_p2
    gz_jpn_pal:
        ldr  r1, =0x{jpn_pal2_addr:08X}
    do_p2:
        ldr  r3, =0x03002D90
        ldr  r5, =0x03004140
        bl   copy_32b

        @ Pal 3 (King Ghidorah / Mini MKG): check bit 3
        movs r0, #8
        tst  r2, r0
        beq  kg_jpn_pal
        ldr  r1, =0x{mkg_pal3_addr:08X}
        b    do_p3
    kg_jpn_pal:
        ldr  r1, =0x{jpn_pal3_addr:08X}
    do_p3:
        ldr  r3, =0x03002DB0
        ldr  r5, =0x03004160
        bl   copy_32b

        @ Pal 4 (Mothra): check bit 2
        movs r0, #4
        tst  r2, r0
        beq  mo_jpn_pal
        ldr  r1, =0x{usa_pal4_addr:08X}
        b    do_p4
    mo_jpn_pal:
        ldr  r1, =0x{jpn_pal4_addr:08X}
    do_p4:
        ldr  r3, =0x03002DD0
        ldr  r5, =0x03004180
        bl   copy_32b

        @ Pal 6 (Rodan / Fire Rodan): check bit 4
        movs r0, #16
        tst  r2, r0
        beq  ro_jpn_pal
        ldr  r1, =0x{fire_rodan_pal6_addr:08X}
        b    do_p6
    ro_jpn_pal:
        ldr  r1, =0x{jpn_pal6_addr:08X}
    do_p6:
        ldr  r3, =0x03002E10
        ldr  r5, =0x030041C0
        bl   copy_32b

        @ Pal 7 (Megalon / Eva Purple Megalon): check bit 5
        movs r0, #32
        tst  r2, r0
        beq  me_jpn_pal
        ldr  r1, =0x{purple_megalon_pal7_addr:08X}
        b    do_p7
    me_jpn_pal:
        ldr  r1, =0x{jpn_pal7_addr:08X}
    do_p7:
        ldr  r3, =0x03002E30
        ldr  r5, =0x030041E0
        bl   copy_32b
        pop  {{r0, r1, r2, r3, r4, r5, pc}}

    copy_32b:
        movs r4, #8
    c32_loop:
        ldr  r0, [r1]
        str  r0, [r3]
        str  r0, [r5]
        adds r1, #4
        adds r3, #4
        adds r5, #4
        subs r4, #1
        bne  c32_loop
        bx   lr
    """
    blob.extend(assemble_thumb(src_copy, addrs["copy_palettes"]))

    # ------------------------------------------------------------------
    # Hook 1: cave_archive_get_ptr(r0 = idx)
    # Tail-called from 0x08002C48 (preserves lr!).
    # Looks up r0 in skin_dispatch_table: entries of (u32 idx, u32 ptrs_table_addr)
    # terminated by 0. Each ptrs_table has 16 u32 pointers indexed by SKIN_MASK (0..15)!
    # ------------------------------------------------------------------
    align4()
    addrs["archive_get_ptr"] = base + len(blob)
    src_arch = f"""
        ldr  r1, =0x{SKIN_MASK_ADDR:08X}
        ldrb r3, [r1]
        movs r1, #15
        ands r3, r1                 @ r3 = SKIN_MASK & 15 (0..15)
        ldr  r1, =0x{skin_dispatch_table_addr:08X}
    swap_loop:
        ldr  r2, [r1]
        cmp  r2, #0
        beq  orig_lookup
        cmp  r2, r0
        beq  swap_hit
        adds r1, #8
        b    swap_loop
    swap_hit:
        ldr  r1, [r1, #4]           @ r1 = u32[16] table for this archive idx
        lsls r3, r3, #2
        ldr  r0, [r1, r3]           @ r0 = ptrs[SKIN_MASK]
        bx   lr
    orig_lookup:
        ldr  r1, =0x03001C34
        ldr  r1, [r1]
        lsls r0, r0, #2
        adds r0, r0, r1
        ldr  r0, [r0]
        adds r0, r1, r0
        bx   lr
    """
    blob.extend(assemble_thumb(src_arch, addrs["archive_get_ptr"]))

    # ------------------------------------------------------------------
    # Hook 2: cave_load_scene_pal()
    # Called via BL from 0x0801AA8E (replaces `str r0, [r1, #8]; ldr r0, [r1, #8]`).
    # ONLY overwrites OBJ Pal 2 & Pal 4 when the loaded scene actually contains
    # JPN's 4bpp monster palette (0x03002D90 == 0x739C2C40), so 8bpp 256-color
    # screens (Title Screen, Giant VS Matchup / Rodan / VS logo) are untouched!
    # ------------------------------------------------------------------
    align4()
    addrs["load_scene_pal"] = base + len(blob)
    src_scene_head = f"""
        str  r0, [r1, #8]
        ldr  r0, [r1, #8]
        push {{r0, r1, r2, r3, lr}}
        ldr  r1, =0x03002D90
        ldr  r0, [r1]
        ldr  r2, =0x739C2C40
        cmp  r0, r2
        bne  scene_done
        @ Populate OBJ Pal 9..13 ONLY on Custom Mode (0x62D8001F) or Battle Results (0x211F109F),
        @ so Battle buildings/vehicles/power-ups and Monster Select ?/Speed/Power/Special stay untouched!
        @ On Custom Mode entry, also clear SKIN_MASK (0x0203FFFE = 0) so Story Mode Select toggles
        @ never bleed onto Custom Mode IDs 1..6 (e.g. K.GHIDORAH vs M.GHIDORAH)!
        ldr  r1, =0x03002B54
        ldr  r0, [r1]
        ldr  r2, =0x62D8001F
        cmp  r0, r2
        bne  chk_results_scn
        ldr  r1, =0x{SKIN_MASK_ADDR:08X}
        movs r0, #0
        strb r0, [r1]
        ldr  r1, =0x{NIGHT_TOKYO_FLAG_ADDR:08X}
        strb r0, [r1]
        b    load_alt_pals
    chk_results_scn:
        ldr  r2, =0x211F109F
        cmp  r0, r2
        bne  chk_night_tokyo
        ldr  r1, =0x{NIGHT_TOKYO_FLAG_ADDR:08X}
        movs r0, #0
        strb r0, [r1]
        @ Battle Results uses OBJ Pal 10..13 for 1P/2P/3P/4P badges! Place alt icons in FREE Pal 8, 9, 14, 15!
        ldr  r0, =0x{usa_pal2_addr:08X}
        ldr  r1, =0x03002E50
        bl   copy_32b_scn
        ldr  r0, =0x{mkg_pal3_addr:08X}
        ldr  r1, =0x03002E70
        bl   copy_32b_scn
        ldr  r0, =0x{fire_rodan_pal6_addr:08X}
        ldr  r1, =0x03002F10
        bl   copy_32b_scn
        ldr  r0, =0x{purple_megalon_pal7_addr:08X}
        ldr  r1, =0x03002F30
        bl   copy_32b_scn
        b    chk_skin_mask
    chk_night_tokyo:
        ldr  r1, =0x{NIGHT_TOKYO_FLAG_ADDR:08X}
        ldrb r1, [r1]
        cmp  r1, #0
        beq  chk_skin_mask
        ldr  r1, =0x03002B50
        ldrh r0, [r1, #2]           @ BG[1] == 0x53BF on ALL battle stages (incl. CITY Tokyo)!
        ldr  r2, =0x000053BF
        cmp  r0, r2
        bne  chk_skin_mask
        @ In-place midnight-indigo transform of:
        @   1) BG Pal 1..15 (0x03002B70..0x03002D4F, 480 B) -> leaves BG Pal 0 (Battle HUD!) 100% untouched!
        @   2) OBJ Pal 8..9 (0x03002E50..0x03002E8F, 64 B: tall green skyscraper & gray buildings)
        @   3) OBJ Pal 11..12 (0x03002EB0..0x03002EEF, 64 B: tall orange/tan skyscrapers)
        @   -> Skips OBJ Pal 10 (0x03002E90: 1P tag & power-up icons stay 100% bright!)
        push {{r4, r5, r6}}
        ldr  r1, =0x03002B70        @ BG Pal 1..15 (skip BG Pal 0 Battle HUD!)
        ldr  r6, =480
        bl   nt_xform_range
        ldr  r1, =0x03002E50        @ OBJ Pal 8..9 (tall green skyscraper + gray buildings!)
        movs r6, #64
        bl   nt_xform_range
        ldr  r1, =0x03002EB0        @ OBJ Pal 11..12 (tall orange/tan skyscrapers; skips OBJ Pal 10 power-ups/1P tag!)
        movs r6, #64
        bl   nt_xform_range
        pop  {{r4, r5, r6}}
        b    chk_skin_mask
    nt_xform_range:
        movs r3, #0
    nt_loop:
        ldrh r0, [r1, r3]
        cmp  r0, #0
        beq  nt_next
        movs r2, #31
        movs r4, r0
        ands r4, r2                 @ r4 = R (0..31)
        lsrs r5, r0, #5
        ands r5, r2                 @ r5 = G (0..31)
        lsrs r0, r0, #10
        ands r0, r2                 @ r0 = B (0..31)
        @ Bright warm building windows/lights (R >= 24 and G >= 22 and B <= 18) -> glowing warm-yellow window!
        cmp  r4, #24
        blo  nt_darken
        cmp  r5, #22
        blo  nt_darken
        cmp  r0, #18
        bhi  nt_darken
        ldr  r0, =0x2B9F            @ (10<<10)|(28<<5)|31 glowing warm skyscraper light!
        b    nt_store
    nt_darken:
        lsrs r4, r4, #2             @ R = 25% (deep night)
        lsrs r2, r5, #2             @ G = ~37% (r5/4 + r5/8)
        lsrs r5, r5, #3
        adds r5, r5, r2
        lsrs r0, r0, #1             @ B = 50% + 4 (rich midnight indigo tint!)
        adds r0, #4
        cmp  r0, #31
        bls  nt_pack
        movs r0, #31
    nt_pack:
        lsls r0, r0, #10
        lsls r5, r5, #5
        orrs r0, r5
        orrs r0, r4
    nt_store:
        strh r0, [r1, r3]
    nt_next:
        adds r3, #2
        cmp  r3, r6
        blo  nt_loop
        bx   lr
    load_alt_pals:
        ldr  r0, =0x{usa_pal2_addr:08X}
        ldr  r1, =0x03002E70
        bl   copy_32b_scn
        ldr  r0, =0x{mkg_pal3_addr:08X}
        ldr  r1, =0x03002E90
        bl   copy_32b_scn
        ldr  r0, =0x{fire_rodan_pal6_addr:08X}
        ldr  r1, =0x03002EB0
        bl   copy_32b_scn
        ldr  r0, =0x{usa_pal4_addr:08X}
        ldr  r1, =0x03002ED0
        bl   copy_32b_scn
        ldr  r0, =0x{purple_megalon_pal7_addr:08X}
        ldr  r1, =0x03002EF0
        bl   copy_32b_scn
    chk_skin_mask:
        ldr  r0, =0x{SKIN_MASK_ADDR:08X}
        ldrb r0, [r0]
        cmp  r0, #0
        beq  scene_done
        ldr  r0, =0x{addrs['copy_palettes'] | 1:08X}
        bl   bx_r0_tramp1
    scene_done:
        pop  {{r0, r1, r2, r3, pc}}
    bx_r0_tramp1:
        bx   r0
    copy_32b_scn:
        movs r3, #0
    c32s_loop:
        ldr  r2, [r0, r3]
        str  r2, [r1, r3]
        adds r3, #4
        cmp  r3, #32
        blo  c32s_loop
        bx   lr
    """
    blob.extend(assemble_thumb(src_scene_head, addrs["load_scene_pal"]))

    # ------------------------------------------------------------------
    # Helper: toggle_monster_skin(r0 = monster_id in 1..6)
    # Toggles ONLY that monster's bit in SKIN_MASK_ADDR (1->bit0, 4->bit1, 5->bit2),
    # plays click SFX, updates OBJ Pal 2 & 4, re-DMAs loaded VRAM packs, AND
    # invalidates cached frame [actor, #0x28]=0xFFFF on all active actors in
    # 0x03002F60 (32 slots, stride 0x7C) so small icons & Custom portraits refresh
    # instantaneously on the exact frame Select is pressed!
    # ------------------------------------------------------------------
    align4()
    addrs["toggle_monster_skin"] = base + len(blob)
    src_refresh = f"""
        push {{r0, r1, r2, r3, r4, r5, r6, r7, lr}}
        cmp  r0, #1
        bne  chk_m2
        movs r1, #1                 @ Godzilla -> bit 0
        b    do_bit_tog
    chk_m2:
        cmp  r0, #2
        bne  chk_m3
        movs r1, #8                 @ King Ghidorah / Mini MKG -> bit 3
        b    do_bit_tog
    chk_m3:
        cmp  r0, #3
        bne  chk_m4
        movs r1, #16                @ Rodan / Fire Rodan -> bit 4
        b    do_bit_tog
    chk_m4:
        cmp  r0, #4
        bne  chk_m5
        movs r1, #2                 @ Mechagodzilla/Kiryu -> bit 1
        b    do_bit_tog
    chk_m5:
        cmp  r0, #5
        bne  chk_m6
        movs r1, #4                 @ Mothra -> bit 2
        b    do_bit_tog
    chk_m6:
        cmp  r0, #6
        bne  ref_exit               @ Random '?' -> no toggle
        movs r1, #32                @ Megalon / Eva Purple Megalon -> bit 5
    do_bit_tog:
        ldr  r2, =0x{SKIN_MASK_ADDR:08X}
        ldrb r0, [r2]
        eors r0, r1
        strb r0, [r2]

        @ 1. Play cursor click SFX (0x50, 1)
        movs r0, #0x50
        movs r1, #1
        ldr  r3, =0x08019141
        bl   bx_r3_ref

        @ 2. Live-update OBJ Pal 2 (Godzilla) & OBJ Pal 4 (Mothra)
        ldr  r3, =0x{addrs['copy_palettes'] | 1:08X}
        bl   bx_r3_ref

        @ 3. Live-refresh any swapped sprite packs currently loaded in OBJ VRAM (0x030043D0)
        ldr  r4, =0x03001AF0
        ldrb r4, [r4]
        cmp  r4, #0
        beq  inv_actors
        movs r5, #0
    vram_loop:
        ldr  r6, =0x030043D0
        lsls r0, r5, #1
        ldrh r6, [r6, r0]
        ldr  r7, =0x{skin_dispatch_table_addr:08X}
    chk_swap:
        ldr  r2, [r7]
        cmp  r2, #0
        beq  vram_next
        cmp  r2, r6
        beq  vram_reload
        adds r7, #8
        b    chk_swap
    vram_reload:
        adds r0, r6, #0
        ldr  r3, =0x{addrs['archive_get_ptr'] | 1:08X}
        bl   bx_r3_ref
        adds r6, r0, #0
        ldr  r2, =0x030043F0
        lsls r0, r5, #1
        ldrh r2, [r2, r0]
        ldr  r3, =0x06010000
        adds r2, r2, r3
        ldr  r0, [r6, #8]
        adds r0, r6, r0
        ldr  r3, =0x040000D4
        str  r0, [r3]
        str  r2, [r3, #4]
        ldr  r0, [r6, #12]
        lsrs r0, r0, #1
        movs r1, #0x80
        lsls r1, r1, #24
        orrs r0, r1
        str  r0, [r3, #8]
        ldr  r0, [r3, #8]
    vram_next:
        adds r5, #1
        cmp  r5, r4
        blt  vram_loop

        @ 4. Invalidate cached frame [actor, #0x28]=0xFFFF on all 32 active actors
        @    (base 0x03002F60, stride 0x7C) so streamed portraits/icons re-DMA immediately!
    inv_actors:
        ldr  r4, =0x03002F60
        movs r5, #32
        ldr  r6, =0x0000FFFF
    inv_loop:
        ldrh r0, [r4, #0x16]
        lsrs r0, r0, #15
        beq  inv_next
        strh r6, [r4, #0x28]
    inv_next:
        adds r4, #0x7C
        subs r5, #1
        bne  inv_loop

    ref_exit:
        pop  {{r0, r1, r2, r3, r4, r5, r6, r7, pc}}
    bx_r3_ref:
        bx   r3
    """
    blob.extend(assemble_thumb(src_refresh, addrs["toggle_monster_skin"]))

    # ------------------------------------------------------------------
    # Hook 3: cave_select_toggle()
    # Called via BL from 0x080128C4 (Story/VS Monster Select).
    # Reads currently hovered monster_id = u8[0x03001850] and toggles ONLY that monster!
    # ------------------------------------------------------------------
    align4()
    addrs["select_toggle"] = base + len(blob)
    src_sel = f"""
        push {{r0, r2, r3, lr}}
        ldr  r0, =0x03002F58
        ldrh r1, [r0]
        movs r0, #4
        tst  r1, r0
        beq  sel_exit
        ldr  r0, =0x03001850
        ldrb r0, [r0]
        ldr  r3, =0x{addrs['toggle_monster_skin'] | 1:08X}
        bl   bx_r3_sel
    sel_exit:
        ldr  r0, =0x03002F58
        ldrh r1, [r0]
        pop  {{r0, r2, r3, pc}}
    bx_r3_sel:
        bx   r3
    """
    blob.extend(assemble_thumb(src_sel, addrs["select_toggle"]))

    # ------------------------------------------------------------------
    # Hook 3b (v0.5): cave_custom_select_toggle()
    # Called via BL from 0x080135C0 (Custom Mode).
    # Reads cur_col = u8[0x030018F0] (0..3) and monster_id = u8[0x03001850 + cur_col*0x24],
    # then toggles ONLY that monster!
    # ------------------------------------------------------------------
    align4()
    addrs["custom_select_toggle"] = base + len(blob)
    src_csel = f"""
        push {{r0, r2, r3, lr}}
        ldr  r0, =0x03002F58
        ldrh r1, [r0]
        movs r0, #4
        tst  r1, r0
        beq  csel_exit
        ldr  r2, =0x030018F0
        ldrb r0, [r2]
        cmp  r0, #3
        ble  col_ok
        movs r0, #0
    col_ok:
        movs r2, #0x24
        muls r0, r2
        ldr  r2, =0x03001850
        ldrb r0, [r2, r0]
        ldr  r3, =0x{addrs['toggle_monster_skin'] | 1:08X}
        bl   bx_r3_csel
    csel_exit:
        ldr  r0, =0x03002F58
        ldrh r1, [r0]
        pop  {{r0, r2, r3, pc}}
    bx_r3_csel:
        bx   r3
    """
    blob.extend(assemble_thumb(src_csel, addrs["custom_select_toggle"]))

    # ------------------------------------------------------------------
    # Hook 4 (v0.2): cave_check_ptag()
    # Called via BL from 0x0800473A (replaces `ldr r0, =0x03001760; ldrb r0, [r0]`).
    # Returns r0 = 1 (skip 1P-4P tags) if [FLAG_HIDE_PTAG_ADDR] != 0, else u8 [0x03001760].
    # ------------------------------------------------------------------
    align4()
    addrs["check_ptag"] = base + len(blob)
    src_ptag = f"""
        ldr  r0, =0x{FLAG_HIDE_PTAG_ADDR:08X}
        ldrb r0, [r0]
        cmp  r0, #0
        bne  ptag_hide
        ldr  r0, =0x03001760
        ldrb r0, [r0]
        bx   lr
    ptag_hide:
        movs r0, #1
        bx   lr
    """
    blob.extend(assemble_thumb(src_ptag, addrs["check_ptag"]))

    # ------------------------------------------------------------------
    # Hook 5 (v0.2): cave_stage_order()
    # Called via BL from 0x08012780 (replaces `bl 0x080184AC` after Story stage shuffle).
    # Also resets BONUS_DONE_MASK_ADDR = 0 for the new Story Mode run!
    # If [FLAG_STAGE_US_ADDR] != 0, writes fixed US stage order [0,1,3,2,4,5,6] to 0x03001838.
    # ------------------------------------------------------------------
    align4()
    addrs["stage_order"] = base + len(blob)
    src_order = f"""
        push {{r0, r1, r2, r3, lr}}
        movs r0, #0
        ldr  r1, =0x{BONUS_DONE_MASK_ADDR:08X}
        strb r0, [r1]
        ldr  r1, =0x{FLAG_STAGE_US_ADDR:08X}
        ldrb r0, [r1]
        cmp  r0, #0
        beq  order_done
        ldr  r1, =0x03001838
        movs r0, #0
        strb r0, [r1, #0]
        movs r0, #1
        strb r0, [r1, #1]
        movs r0, #3
        strb r0, [r1, #2]
        movs r0, #2
        strb r0, [r1, #3]
        movs r0, #4
        strb r0, [r1, #4]
        movs r0, #5
        strb r0, [r1, #5]
        movs r0, #6
        strb r0, [r1, #6]
    order_done:
        pop  {{r0, r1, r2, r3}}
        ldr  r3, =0x080184AD
        bl   bx_r3_ord
        pop  {{pc}}
    bx_r3_ord:
        bx   r3
    """
    blob.extend(assemble_thumb(src_order, addrs["stage_order"]))

    # ------------------------------------------------------------------
    # Hook 6 (v0.2): cave_bonus_stage()
    # Called via BL from 0x0800D18A (replaces `bl 0x080184CC` with r0=0x11 after Story Results).
    # If [FLAG_BONUS_STAGE_ADDR] != 0:
    #   stage==2 & !(mask&1) -> set bit0, r0=0x20 (BONUS0 UFO Assault)
    #   stage==5 & !(mask&2) -> set bit1, r0=0x21 (BONUS1 SDF Jet Assault)
    # ------------------------------------------------------------------
    align4()
    addrs["bonus_stage"] = base + len(blob)
    src_bonus = f"""
        push {{r1, r2, r3, lr}}
        ldr  r1, =0x{FLAG_BONUS_STAGE_ADDR:08X}
        ldrb r1, [r1]
        cmp  r1, #0
        beq  bonus_go
        ldr  r1, =0x03001688
        ldrb r1, [r1]
        ldr  r2, =0x{BONUS_DONE_MASK_ADDR:08X}
        ldrb r3, [r2]
        cmp  r1, #2
        bne  chk_b1
        movs r1, #1
        tst  r3, r1
        bne  bonus_go
        orrs r3, r1
        strb r3, [r2]
        movs r0, #0x20
        b    bonus_go
    chk_b1:
        cmp  r1, #5
        bne  bonus_go
        movs r1, #2
        tst  r3, r1
        bne  bonus_go
        orrs r3, r1
        strb r3, [r2]
        movs r0, #0x21
    bonus_go:
        ldr  r3, =0x080184CD
        bl   bx_r3_bon
        pop  {{r1, r2, r3, pc}}
    bx_r3_bon:
        bx   r3
    """
    blob.extend(assemble_thumb(src_bonus, addrs["bonus_stage"]))

    # ------------------------------------------------------------------
    # Hook 7 (v0.2): cave_options_dx()
    # Called via BL from 0x08014884 (replaces `ldr r0, =0x03001760; ldr r2, =0x0300265C`).
    # Runs for every pill actor (pill_id = [0x0300265C] in 1..3) when in Options ([actor,#0x20]==0x5A).
    # - Select / L / R (checked once when pill_id == 1) toggles OPTIONS_PAGE_ADDR (0=Standard, 1=DX).
    # - Always syncs actor's pill frame [actor, #0x26] for current page.
    # - When page==1 and pill_id == cursor ([0x03001760]), Left/Right/A toggles the DX flag,
    #   and returns r0/r2 pointing to unequal bytes so vanilla Timer/Diff/AllyDMG handler is skipped!
    # ------------------------------------------------------------------
    align4()
    addrs["options_dx"] = base + len(blob)
    src_opt = f"""
        push {{r1, r3, r4, r5, r6, r7, lr}}
        ldr  r4, =0x03001C10
        ldr  r4, [r4]                   @ r4 = current pill actor
        ldr  r5, =0x0300265C
        ldrb r5, [r5]                   @ r5 = pill_id (1, 2, 3)
        ldr  r6, =0x{OPTIONS_PAGE_ADDR:08X}

        @ 1. If pill_id == 1, check Select(0x04) / R(0x100) / L(0x200) to flip page (0 <-> 1)
        cmp  r5, #1
        bne  opt_check_toggle
        ldr  r0, =0x03002F58
        ldrh r0, [r0]
        ldr  r1, =0x00000304
        tst  r0, r1
        beq  opt_check_toggle
        ldrb r0, [r6]
        movs r1, #1
        eors r0, r1
        strb r0, [r6]
        movs r0, #0x50
        movs r1, #1
        ldr  r3, =0x08019141
        bl   bx_r3_opt

    opt_check_toggle:
        @ 2. If page == 1 and pill_id == cursor, handle Left(0x20)/Right(0x10)/A(0x01)
        ldrb r7, [r6]
        cmp  r7, #0
        beq  opt_sync_std
        ldr  r0, =0x03001760
        ldrb r0, [r0]
        cmp  r0, r5
        bne  opt_sync_dx
        ldr  r0, =0x03002F58
        ldrh r0, [r0]
        movs r1, #0x31                  @ A(0x01) | Right(0x10) | Left(0x20)
        tst  r0, r1
        beq  opt_sync_dx
        @ Toggle DX flag for pill 1/2/3 (1P TAG / BONUS / STAGE)
        cmp  r5, #1
        bne  tog_p2
        ldr  r2, =0x{FLAG_HIDE_PTAG_ADDR:08X}
        b    do_dx_tog
    tog_p2:
        cmp  r5, #2
        bne  tog_p3
        ldr  r2, =0x{FLAG_BONUS_STAGE_ADDR:08X}
        b    do_dx_tog
    tog_p3:
        ldr  r2, =0x{FLAG_STAGE_US_ADDR:08X}
    do_dx_tog:
        ldrb r0, [r2]
        movs r1, #1
        eors r0, r1
        strb r0, [r2]
        movs r0, #0x54
        movs r1, #2
        ldr  r3, =0x08019141
        bl   bx_r3_opt

    opt_sync_dx:
        cmp  r5, #1
        bne  dx_f2
        ldr  r2, =0x{FLAG_HIDE_PTAG_ADDR:08X}
        ldrb r0, [r2]
        adds r0, #22
        b    dx_store
    dx_f2:
        cmp  r5, #2
        bne  dx_f3
        ldr  r2, =0x{FLAG_BONUS_STAGE_ADDR:08X}
        ldrb r0, [r2]
        adds r0, #24
        b    dx_store
    dx_f3:
        ldr  r2, =0x{FLAG_STAGE_US_ADDR:08X}
        ldrb r0, [r2]
        adds r0, #26
    dx_store:
        strh r0, [r4, #0x26]
        @ Return unequal byte pointers (0x08000000=0x2E vs 0x08000001=0x00) so vanilla Timer/Diff/AllyDMG is 100% skipped!
        ldr  r0, =0x08000000
        ldr  r2, =0x08000001
        pop  {{r1, r3, r4, r5, r6, r7, pc}}

    opt_sync_std:
        cmp  r5, #1
        bne  std_f2
        ldr  r2, =0x03001610
        ldrb r0, [r2]
        adds r0, #6
        b    std_store
    std_f2:
        cmp  r5, #2
        bne  std_f3
        ldr  r2, =0x03001600
        ldrb r0, [r2]
        adds r0, #8
        b    std_store
    std_f3:
        ldr  r2, =0x03001608
        ldrb r0, [r2]
        adds r0, #17
    std_store:
        strh r0, [r4, #0x26]
        ldr  r0, =0x03001760
        ldr  r2, =0x0300265C
        pop  {{r1, r3, r4, r5, r6, r7, pc}}
    bx_r3_opt:
        bx   r3
    """
    blob.extend(assemble_thumb(src_opt, addrs["options_dx"]))

    # ------------------------------------------------------------------
    # v0.8 Hybrid 12-Entity Custom Mode Tables & Hooks
    # ------------------------------------------------------------------
    align4()
    custom_pal_lut_addr = base + len(blob)
    #                    0  1  2  3  4  5  6  7   8   9  10  11  12  13(RANDOM)
    blob.extend(bytes([4, 2, 3, 6, 5, 4, 7, 9, 10, 11,  5, 12, 13,  4]))

    align4()
    battle_spawn_tbl_addr = base + len(blob)
    for actor_type, arch_idx, pal_ptr in (
        (0x0F, 392,  usa_pal2_addr),           # ID  7: Classic Godzilla
        (0x02, 395,  mkg_pal3_addr),           # ID  8: Canonical Mini Mecha-King Ghidorah (virtual ID 395)
        (0x0B, 0x26, fire_rodan_pal6_addr),    # ID  9: Fire Rodan
        (0x8F, 393,  0x030041A0),              # ID 10: Classic Mechagodzilla (Pal 5)
        (0x0A, 394,  usa_pal4_addr),           # ID 11: Classic Mothra
        (0x0C, 0x47, purple_megalon_pal7_addr),# ID 12: Purple Megalon
    ):
        blob.extend(struct.pack("<III", actor_type, arch_idx, pal_ptr))

    # Hook 8 (v0.8/v1.0): cave_custom_pal (at 0x013EB8; routes ALL IDs 0..13 via CUSTOM_PAL_LUT)
    align4()
    addrs["custom_pal"] = base + len(blob)
    src_cpal = f"""
        ldrb r0, [r1, #0x11]
        cmp  r0, #13
        bhi  cpal_ret
        ldr  r2, =0x{custom_pal_lut_addr:08X}
        ldrb r0, [r2, r0]
        strb r0, [r1, #3]
    cpal_ret:
        ldr  r2, =0x08013EFD
        bx   r2
    """
    blob.extend(assemble_thumb(src_cpal, addrs["custom_pal"]))

    # Hook 9 (v0.8): cave_custom_name (at 0x013F6C; leaves 0x013F74..0x013F7C intact!)
    align4()
    addrs["custom_name"] = base + len(blob)
    src_cname = """
        ldrb r0, [r1, #0x11]
        cmp  r0, #0
        bne  cname_nz
        ldr  r2, =0x080140F3
        bx   r2
    cname_nz:
        cmp  r0, #7
        blo  cname_std
        adds r0, #12                @ ID 7..12 -> frames 19..24 in JPN[167]!
        b    cname_call
    cname_std:
        subs r0, #1                 @ ID 1..6  -> frames 0..5 in JPN[167]
    cname_call:
        ldr  r2, =0x080134BD
        bl   tramp_r2_cn
        ldr  r2, =0x08013F85
        bx   r2
    tramp_r2_cn:
        bx   r2
    """
    blob.extend(assemble_thumb(src_cname, addrs["custom_name"]))

    # Shared 8-byte bitmask LUT for Story Mode SKIN_MASK (monster_id 0..6 -> bitmask)
    align4()
    vs_skin_bit_lut_addr = base + len(blob)
    blob.extend(bytes([0, 1, 8, 16, 2, 4, 32, 0]))

    # Hook 10 (v0.8/v0.9): cave_vs_frame (at 0x0159AC; fixes 2P Giant VS & 3P/4P VS nameplates + roar index
    # for BOTH Custom Mode IDs 7..12 AND Story Mode toggled IDs 1..6 via SKIN_MASK!)
    align4()
    addrs["vs_frame"] = base + len(blob)
    src_vs = f"""
        adds r0, r0, r3             @ r0 = &player[slot]
        ldrb r0, [r0]               @ r0 = monster_id (1..12)
        cmp  r0, #7
        blo  vs_std
        adds r2, r0, #2             @ Custom ID 7..12 -> frames 9..14 (preserves 0..8!)
        strh r2, [r4, #0x26]
        subs r0, #6                 @ wrap base monster_id (1..6) for VS roar!
        b    vs_roar
    vs_std:
        ldr  r1, =0x{SKIN_MASK_ADDR:08X}
        ldrb r1, [r1]
        ldr  r2, =0x{vs_skin_bit_lut_addr:08X}
        ldrb r2, [r2, r0]
        tst  r1, r2
        beq  vs_orig
        movs r2, r0
        adds r2, #8                 @ Story Mode toggled ID 1..6 -> frames 9..14! (valid 8-bit imm!)
        strh r2, [r4, #0x26]
        b    vs_roar
    vs_orig:
        subs r2, r0, #1             @ ID 1..6 -> frames 0..5
        strh r2, [r4, #0x26]
    vs_roar:
        ldrb r2, [r4, #0x11]
        adds r2, #0xff
        adds r2, r2, r0
        strb r2, [r4, #0x11]
        ldr  r2, =0x080159DD
        bx   r2
    """
    blob.extend(assemble_thumb(src_vs, addrs["vs_frame"]))

    # Hook 10b (v0.8/v0.9): cave_vs_portrait (at 0x01583C; maps Custom ID 7..12 -> 9..14 AND
    # Story Mode ID 1..6 with SKIN_MASK bit set -> 9..14 so Shadow MKG / Fire Rodan / Megalon-01 / Classic
    # skins all show properly on 2P Giant VS!)
    align4()
    addrs["vs_portrait"] = base + len(blob)
    src_vsp = f"""
        adds r0, r0, r6             @ r0 = &player[slot]
        ldrb r0, [r0]               @ r0 = monster_id (1..12)
        cmp  r0, #7
        blo  vsp_std
        adds r0, #2                 @ Custom ID 7..12 -> frames 9..14!
        b    vsp_ret
    vsp_std:
        push {{r2}}                 @ preserve live r2 (actor pointer for strh r0, [r2, #0x26]!)
        ldr  r1, =0x{SKIN_MASK_ADDR:08X}
        ldrb r1, [r1]
        ldr  r2, =0x{vs_skin_bit_lut_addr:08X}
        ldrb r2, [r2, r0]
        tst  r1, r2
        pop  {{r2}}
        beq  vsp_orig
        adds r0, #8                 @ Story Mode toggled ID 1..6 -> frames 9..14!
        b    vsp_ret
    vsp_orig:
        subs r0, #1                 @ ID 1..6 -> frames 0..5
    vsp_ret:
        ldr  r1, =0x0801584B
        bx   r1
    """
    blob.extend(assemble_thumb(src_vsp, addrs["vs_portrait"]))

    # Hook 11 (v0.8): cave_battle_spawn (at 0x0042E8; table-driven spawn for IDs 7..12!)
    align4()
    addrs["battle_spawn"] = base + len(blob)
    src_bspawn = f"""
        cmp  r1, #7
        bhs  spawn_ext
        cmp  r1, #1
        bne  not_id1
        movs r3, #0
        ldrsh r2, [r7, r3]
        ldr  r3, =0x080042F1
        bx   r3
    not_id1:
        ldr  r3, =0x08004341
        bx   r3
    spawn_ext:
        subs r1, #7
        lsls r0, r1, #1
        adds r0, r0, r1
        lsls r0, r0, #2
        ldr  r5, =0x{battle_spawn_tbl_addr:08X}
        adds r5, r5, r0             @ r5 = &BATTLE_SPAWN_TBL[monster_id - 7]
        movs r3, #0
        ldrsh r2, [r7, r3]
        movs r4, #2
        ldrsh r3, [r7, r4]
        movs r0, #0
        str  r0, [sp]
        movs r1, #1
        mov  r4, sb
        ands r1, r4
        lsls r0, r1, #6
        movs r1, #0x80
        lsls r1, r1, #7
        orrs r0, r1
        str  r0, [sp, #4]
        ldr  r4, =0x0000FFFE
        str  r4, [sp, #8]
        ldr  r0, [r5, #0]           @ actor_type
        ldr  r1, [r5, #4]           @ archive_idx
        ldr  r4, =0x080194F9
        bl   tramp_r4_bs
        ldr  r1, [sp, #0x18]
        strb r0, [r1, #3]
        ldr  r0, [r5, #8]           @ 32-byte palette ptr
        ldr  r3, =0x0800445F
        bx   r3
    tramp_r4_bs:
        bx   r4
    """
    blob.extend(assemble_thumb(src_bspawn, addrs["battle_spawn"]))

    # ------------------------------------------------------------------
    # v0.9 Polish: Power-Up Toggle, Subtle DX Stats (HP + Speed), & 12-Entity Battle HUD Names
    # ------------------------------------------------------------------
    align4()
    hp_lut_addr = base + len(blob)
    # Starting HP by monster_id (0..12): IDs 1..6 = vanilla 71 (0x47), IDs 7..12 = subtle lore trade-offs
    blob.extend(bytes([71, 71, 71, 71, 71, 71, 71, 67, 77, 65, 76, 68, 68]))

    align4()
    speed_lut_addr = base + len(blob)
    # Fixed-point 16.16 walk speeds by monster_id (0..12)
    for spd in (
        0x0E000,  #  0: fallback
        0x0E000,  #  1: Godzilla '03   (0.875)
        0x10000,  #  2: King Ghidorah  (1.000)
        0x12000,  #  3: Rodan          (1.125)
        0x0C000,  #  4: Kiryu          (0.750)
        0x10000,  #  5: Mothra '03     (1.000)
        0x0E000,  #  6: Megalon        (0.875)
        0x0F000,  #  7: Godzilla '99   (0.9375, nimbler rushdown)
        0x0E800,  #  8: Mecha-Ghidorah (0.90625, armored tank)
        0x13800,  #  9: Fire Rodan     (1.21875, blazing glass-cannon)
        0x0B800,  # 10: Mechagodzilla  (0.71875, heavy Heisei artillery)
        0x11000,  # 11: Mothra '92     (1.0625, agile classic guardian)
        0x0F000,  # 12: Megalon-01     (0.9375, berserk Eva-01 tempo)
    ):
        blob.extend(struct.pack("<I", spd))

    # Hook 12 (v0.9): cave_results_icon (BL from 0x013346; maps IDs 1..12 -> JPN[212] frame & OBJ pal!)
    align4()
    results_icon_lut_addr = base + len(blob)
    # 12 entries of (u8 frame, u8 obj_pal) for monster_id 1..12
    for fr, pal in (
        (5,  2),  #  1: Godzilla '03
        (11, 3),  #  2: King Ghidorah
        (17, 6),  #  3: Rodan
        (23, 5),  #  4: Kiryu
        (29, 4),  #  5: Mothra '03
        (35, 7),  #  6: Megalon
        (42, 8),  #  7: Godzilla '99  (Pal 8)
        (43, 9),  #  8: Mecha-Ghidorah (Pal 9)
        (44, 14), #  9: Fire Rodan     (Pal 14)
        (45, 5),  # 10: Mechagodzilla  (Pal 5)
        (46, 4),  # 11: Mothra '92     (Pal 4)
        (47, 15), # 12: Megalon-01     (Pal 15)
    ):
        blob.extend(bytes([fr, pal]))

    align4()
    addrs["results_icon"] = base + len(blob)
    src_ricon = f"""
        subs r0, #1
        cmp  r0, #11
        bhi  ricon_done
        lsls r0, r0, #1
        ldr  r2, =0x{results_icon_lut_addr:08X}
        adds r2, r2, r0
        ldr  r3, =0x03001C10
        ldr  r3, [r3]
        ldrb r1, [r2, #0]
        strh r1, [r3, #0x26]
        ldrb r1, [r2, #1]
        strb r1, [r3, #3]
    ricon_done:
        ldr  r1, =0x080133C5
        bx   r1
    """
    blob.extend(assemble_thumb(src_ricon, addrs["results_icon"]))

    # Hook 13 (v0.9/v1.0): cave_init_hp (BL from 0x0044E0; r6 = &player[slot], preserves live r2 = slot*0x24!)
    # Also checks SKIN_MASK for Story Mode IDs 1..6 so toggled DX variants get their DX HP in Story Mode too!
    align4()
    addrs["init_hp"] = base + len(blob)
    src_hp = f"""
        push {{r1, r2, r3}}
        ldrb r0, [r6]
        cmp  r0, #6
        bhi  hp_chk12
        ldr  r1, =0x{SKIN_MASK_ADDR:08X}
        ldrb r1, [r1]
        ldr  r3, =0x{vs_skin_bit_lut_addr:08X}
        ldrb r3, [r3, r0]
        tst  r1, r3
        beq  hp_ok
        adds r0, #6
        b    hp_ok
    hp_chk12:
        cmp  r0, #12
        bls  hp_ok
        movs r0, #1
    hp_ok:
        ldr  r2, =0x{hp_lut_addr:08X}
        ldrb r0, [r2, r0]
        strb r0, [r6, #8]
        pop  {{r1, r2, r3}}
        bx   lr
    """
    blob.extend(assemble_thumb(src_hp, addrs["init_hp"]))

    # Hook 14 (v0.9/v1.0): cave_walk_speed (at 0x01CAC0; returns SPEED_LUT[monster_id] for active monster actor,
    # checking SKIN_MASK for Story Mode IDs 1..6 so toggled DX variants get their DX speed in Story Mode too!)
    align4()
    addrs["walk_speed"] = base + len(blob)
    src_spd = f"""
        ldr  r0, =0x03001C10
        ldr  r0, [r0]
        ldrb r1, [r0, #0x11]        @ player slot 0..3
        cmp  r1, #3
        bhi  spd_def
        lsls r0, r1, #3
        adds r0, r0, r1
        lsls r0, r0, #2             @ slot * 0x24
        ldr  r2, =0x03001850
        ldrb r0, [r2, r0]           @ monster_id 1..12
        cmp  r0, #6
        bhi  spd_chk12
        ldr  r1, =0x{SKIN_MASK_ADDR:08X}
        ldrb r1, [r1]
        ldr  r2, =0x{vs_skin_bit_lut_addr:08X}
        ldrb r2, [r2, r0]
        tst  r1, r2
        beq  spd_lu
        adds r0, #6
        b    spd_lu
    spd_chk12:
        cmp  r0, #12
        bls  spd_lu
    spd_def:
        movs r0, #1
    spd_lu:
        lsls r0, r0, #2
        ldr  r2, =0x{speed_lut_addr:08X}
        ldr  r0, [r2, r0]
        bx   lr
    """
    blob.extend(assemble_thumb(src_spd, addrs["walk_speed"]))

    # Hook 15 (v0.9): cave_hud_name_r (at 0x01C7A0, right-aligned P2/P4) & cave_hud_name_l (at 0x01C830, left-aligned P1/P3)
    # Also checks SKIN_MASK for Story Mode IDs 1..6 so toggled skins show their DX names on the Battle HUD!
    align4()
    addrs["hud_name_r"] = base + len(blob)
    src_hudr = f"""
        subs r0, r4, #3
        ldrb r0, [r0]               @ monster_id 1..12
        cmp  r0, #6
        bhi  hudr_chk
        push {{r2, r3}}
        ldr  r1, =0x{SKIN_MASK_ADDR:08X}
        ldrb r1, [r1]
        ldr  r3, =0x{vs_skin_bit_lut_addr:08X}
        ldrb r3, [r3, r0]
        tst  r1, r3
        pop  {{r2, r3}}
        beq  hudr_chk
        adds r0, #6
    hudr_chk:
        subs r0, #1
        cmp  r0, #11
        bls  hudr_ok
        movs r0, #0
    hudr_ok:
        adds r0, #12                @ right-aligned entries 12..23
        lsls r0, r0, #3
        ldr  r1, =0x{hud_name_tbl_addr:08X}
        adds r0, r0, r1
        str  r0, [r2]
        ldr  r1, =0x0801C89F
        bx   r1
    """
    blob.extend(assemble_thumb(src_hudr, addrs["hud_name_r"]))

    align4()
    addrs["hud_name_l"] = base + len(blob)
    src_hudl = f"""
        subs r0, r4, #3
        ldrb r0, [r0]               @ monster_id 1..12
        cmp  r0, #6
        bhi  hudl_chk
        push {{r2, r3}}
        ldr  r1, =0x{SKIN_MASK_ADDR:08X}
        ldrb r1, [r1]
        ldr  r3, =0x{vs_skin_bit_lut_addr:08X}
        ldrb r3, [r3, r0]
        tst  r1, r3
        pop  {{r2, r3}}
        beq  hudl_chk
        adds r0, #6
    hudl_chk:
        subs r0, #1
        cmp  r0, #11
        bls  hudl_ok
        movs r0, #0
    hudl_ok:
        lsls r0, r0, #3             @ left-aligned entries 0..11
        ldr  r1, =0x{hud_name_tbl_addr:08X}
        adds r0, r0, r1
        str  r0, [r2]
        ldr  r1, =0x0801C89F
        bx   r1
    """
    blob.extend(assemble_thumb(src_hudl, addrs["hud_name_l"]))

    # ------------------------------------------------------------------
    # v1.0 Hooks: Custom 12-Fighter Random, Custom Nighttime Tokyo 1 & 8-Stage Random,
    #             Single-Player Live DX Stat Bars + 12 Big Nameplates + Story Text Table Swap
    # ------------------------------------------------------------------

    # Hook 16 (v1.0): cave_custom_resolve_random (replaces `bl #0x80157e0` at 0x01354C)
    # Loops over P1..P4 (0x03001850, stride 0x24): if monster_id == 13 (RANDOM), rolls 1..12 (allowing duplicates!)
    align4()
    addrs["custom_resolve_random"] = base + len(blob)
    src_crnd = """
        push {r0, r1, r2, r3, r4, r5, lr}
        movs r4, #0
        ldr  r5, =0x03001850
    crnd_loop:
        ldrb r0, [r5]
        cmp  r0, #13
        bne  crnd_next
        ldr  r3, =0x0801B905        @ rand()
        bl   tramp_r3_crnd
        movs r1, #12
        ldr  r3, =0x08030611        @ __aeabi_uidivmod -> remainder 0..11 in r0!
        bl   tramp_r3_crnd
        adds r0, #1                 @ 1..12
        strb r0, [r5]
    crnd_next:
        adds r5, #0x24
        adds r4, #1
        cmp  r4, #4
        blo  crnd_loop
        pop  {r0, r1, r2, r3, r4, r5}
        pop  {r3}
        mov  lr, r3
        ldr  r3, =0x080157E1        @ tail-call original Custom Mode match launch!
        bx   r3
    tramp_r3_crnd:
        bx   r3
    """
    blob.extend(assemble_thumb(src_crnd, addrs["custom_resolve_random"]))

    # Hook 17 (v1.0): cave_custom_stage_launch (BL from 0x00CBFE; returns &0x08032ED8[stage] in r0)
    # stage 0..6 = vanilla, stage 7 = Tokyo 1 (Nighttime Tokyo -> NIGHT_TOKYO_FLAG=1, scene 0x1E),
    # stage 8 = Random (rolls 0..7 across all 8 stages!)
    align4()
    addrs["custom_stage_launch"] = base + len(blob)
    src_cstg = f"""
        push {{r1, r2, r3, lr}}
        ldr  r1, =0x030017E4
        ldrb r0, [r1]
        cmp  r0, #8
        bne  cstg_chk7
        ldr  r3, =0x0801B905        @ rand()
        bl   tramp_r3_cstg
        movs r1, #7
        ands r0, r1                 @ 0..7 across all 8 stages!
    cstg_chk7:
        movs r2, #0
        cmp  r0, #7
        bne  cstg_store
        movs r2, #1                 @ Tokyo 1 -> Nighttime Tokyo!
        movs r0, #0                 @ route to Tokyo 2's scene (0x1E) & original BGM
    cstg_store:
        ldr  r1, =0x{NIGHT_TOKYO_FLAG_ADDR:08X}
        strb r2, [r1]
        ldr  r1, =0x08032ED8
        adds r0, r0, r1
        pop  {{r1, r2, r3, pc}}
    tramp_r3_cstg:
        bx   r3
    """
    blob.extend(assemble_thumb(src_cstg, addrs["custom_stage_launch"]))

    # Hook 18 (v1.0): cave_stat_bars (BL from 0x012F42; replaces `subs r0, #1; cmp r1, r0`)
    # Live registers: r0 = monster_id (1..6), r1 = current frame [r2, #0x26], r2 = actor ptr
    # - Updates Story Mode text table [0x030016EC] -> eng_text_alt if SKIN_MASK bit set, else eng_text_base
    # - Switches JPN[215] (0xD7 Stat Bars) 0..5 -> 8..13 and JPN[229] (0xE5 Big Nameplates) 0..5 -> 9..14!
    align4()
    addrs["stat_bars"] = base + len(blob)
    src_sbar = f"""
        push {{r3, r4, lr}}
        movs r4, #0                 @ skin_active = 0
        cmp  r0, #6
        bhi  sbar_txt
        ldr  r3, =0x{SKIN_MASK_ADDR:08X}
        ldrb r3, [r3]
        ldr  r4, =0x{vs_skin_bit_lut_addr:08X}
        ldrb r4, [r4, r0]
        ands r4, r3                 @ r4 != 0 if hovered monster's DX alt is active!
    sbar_txt:
        ldr  r3, =0x030016EC
        cmp  r4, #0
        beq  sbar_tbase
        ldr  r4, =0x{eng_text_alt_addr:08X}
        str  r4, [r3]
        movs r4, #1
        b    sbar_frame
    sbar_tbase:
        ldr  r4, =0x{eng_text_base_addr:08X}
        str  r4, [r3]
        movs r4, #0
    sbar_frame:
        subs r0, #1                 @ base frame 0..5
        cmp  r4, #0
        beq  sbar_done
        ldrh r3, [r2, #0x1E]        @ actor sprite archive ID
        cmp  r3, #215               @ JPN[215] Monster Select Stat Bars -> frames 8..13!
        bne  sbar_chk229
        adds r0, #8
        b    sbar_done
    sbar_chk229:
        cmp  r3, #229               @ JPN[229] Big Domination Nameplates -> frames 9..14!
        bne  sbar_done
        adds r0, #9
    sbar_done:
        pop  {{r3, r4}}
        cmp  r1, r0                 @ restore condition flags for `beq 0x08012F4A`!
        pop  {{pc}}
    """
    blob.extend(assemble_thumb(src_sbar, addrs["stat_bars"]))

    # Hook 19 (v1.0): cave_gameover_portrait (BL from 0x015D48, Actor 0x7C — the true Game Over portrait handler!)
    # Reads Story Mode monster_id (1..6) from 0x03001850 and checks SKIN_MASK:
    # - DX alt ON  -> JPN[243] f9..f14 (Godzilla '99, Shadow MKG, Fire Rodan, Classic MG, Mothra '92, Megalon-01)
    # - DX alt OFF -> ID 4 (Kiryu) = f7, others = mid - 1 (f0, f1, f2, f4, f5)
    align4()
    addrs["gameover_portrait"] = base + len(blob)
    src_go = f"""
        ldr  r1, =0x03001850
        ldrb r0, [r1]
        cmp  r0, #1
        blo  go_zero
        cmp  r0, #6
        bhi  go_zero
        ldr  r2, =0x{SKIN_MASK_ADDR:08X}
        ldrb r2, [r2]
        ldr  r3, =0x{vs_skin_bit_lut_addr:08X}
        ldrb r3, [r3, r0]
        tst  r2, r3
        beq  go_base
        adds r0, #8                 @ DX alt ON: 1..6 -> 9..14 in 15f JPN[243]!
        b    go_set
    go_base:
        cmp  r0, #4
        bne  go_sub1
        movs r0, #7                 @ Kiryu (ID 4, DX OFF) -> JPN[243] f7!
        b    go_set
    go_sub1:
        subs r0, #1                 @ Vanilla 1,2,3,5,6 -> JPN[243] f0,1,2,4,5!
        b    go_set
    go_zero:
        movs r0, #0
    go_set:
        ldr  r2, =0x03001C10
        ldr  r1, [r2]
        strh r0, [r1, #0x26]
        ldr  r3, =0x08016ADB        @ EndActorTick (same exit as 0x080134BE)
        bx   r3
    """
    blob.extend(assemble_thumb(src_go, addrs["gameover_portrait"]))

    # Hook 20 (v1.0): cave_nameplate_229 (BL from 0x012458; replaces `subs r1, #1; cmp r0, r1`)
    # Live registers: r0 = current frame [r2, #0x26], r1 = monster_id (1..6), r2 = JPN[229] actor ptr
    # Maps ALL 6 toggled DX variants (1..6 -> 9..14) on Single-Player Monster Select!
    align4()
    addrs["nameplate_229"] = base + len(blob)
    src_np229 = f"""
        push {{r3, r4}}
        cmp  r1, #6
        bhi  np229_std
        ldr  r3, =0x{SKIN_MASK_ADDR:08X}
        ldrb r3, [r3]
        ldr  r4, =0x{vs_skin_bit_lut_addr:08X}
        ldrb r4, [r4, r1]
        tst  r3, r4
        beq  np229_std
        adds r1, #8                 @ 1..6 -> 9..14 (GODZILLA '99, M-GHIDORAH, FIRE RODAN, MECHAGODZILLA, MOTHRA '92, MEGALON-01)
        b    np229_done
    np229_std:
        subs r1, #1                 @ 1..6 -> 0..5  (GODZILLA '03, KING GHIDORAH, RODAN, KIRYU, MOTHRA '03, MEGALON)
    np229_done:
        pop  {{r3, r4}}
        cmp  r0, r1                 @ restore condition flags for `beq 0x08012466`!
        bx   lr
    """
    blob.extend(assemble_thumb(src_np229, addrs["nameplate_229"]))

    # Hook 21 (v1.0): cave_news_portrait (BL from 0x00CD4C; maps Story Mode Connie News Cutout JPN[230] 1..6 -> 9..14)
    align4()
    addrs["news_portrait"] = base + len(blob)
    src_news = f"""
        push {{r3, r4}}
        cmp  r0, #0
        beq  news_done
        cmp  r0, #6
        bhi  news_std
        ldr  r3, =0x{SKIN_MASK_ADDR:08X}
        ldrb r3, [r3]
        ldr  r4, =0x{vs_skin_bit_lut_addr:08X}
        ldrb r4, [r4, r0]
        tst  r3, r4
        beq  news_std
        adds r0, #8                 @ 1..6 -> 9..14 (Godzilla '99, Shadow MKG, Fire Rodan, Classic MG, Mothra '92, Megalon-01)
        b    news_done
    news_std:
        subs r0, #1                 @ 1..6 -> 0..5
    news_done:
        pop  {{r3, r4}}
        bx   lr
    """
    blob.extend(assemble_thumb(src_news, addrs["news_portrait"]))

    return bytes(blob), addrs


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Godzilla: Domination! DX ROM & BPS patch.")
    parser.add_argument("--src", type=Path, required=True, help="Clean AG4J (Japan) base ROM")
    parser.add_argument("--usa", type=Path, required=True, help="Clean AG4E (USA) donor ROM")
    parser.add_argument("--out-rom", type=Path, required=True, help="Patched 8 MB ROM output path")
    parser.add_argument("--out-bps", type=Path, required=True, help="BPS patch output path")
    args = parser.parse_args()

    jpn_bytes = bytes(load_clean_rom(args.src, EXPECTED_JPN_CRC32, EXPECTED_JPN_SIZE))
    usa_bytes = bytes(load_clean_rom(args.usa, EXPECTED_USA_CRC32, EXPECTED_USA_SIZE))

    # Expand 4 MB -> 8 MB cleanly (zero-filled expansion region 0x400000..0x7FFFFF)
    rom = bytearray(jpn_bytes) + bytearray(EXPANDED_ROM_SIZE - len(jpn_bytes))

    # --- 1. Place Expansion Data at 0x400000+ ---
    cursor = EXPANSION_BASE

    def alloc_expansion(data: bytes, label: str) -> int:
        nonlocal cursor
        if cursor % 4 != 0:
            cursor += 4 - (cursor % 4)
        off = cursor
        if off + len(data) > EXPANDED_ROM_SIZE:
            raise RuntimeError(f"Expansion overflow allocating {label} ({len(data)} B)")
        rom[off : off + len(data)] = data
        cursor = off + len(data)
        return 0x08000000 + off

    # 1a. Dual English Text Tables (0x08400000 = Base w/ Kiryu, followed by DX Alt w/ DX monster names)
    eng_text, eng_text_alt = build_english_text_tables(usa_bytes)
    eng_text_addr = alloc_expansion(eng_text, "english_text_table_base")
    eng_text_alt_addr = alloc_expansion(eng_text_alt, "english_text_table_dx_alt")
    assert eng_text_addr == 0x08400000

    # 1b. USA, JPN & Custom MKG Monster OBJ Palettes (32 B each from battle scene packs USA[253] & JPN[262])
    usa_scene = get_archive_entry(usa_bytes, USA_ARCHIVE_BASE, 253)
    jpn_scene = get_archive_entry(jpn_bytes, JPN_ARCHIVE_BASE, 262)
    night_tokyo_bg_pal_addr = alloc_expansion(build_night_tokyo_bg_pal(jpn_scene), "night_tokyo_1_bg_pal_512b")
    usa_pal2_addr = alloc_expansion(usa_scene[512 + 2 * 32 : 512 + 3 * 32], "usa_obj_pal2_godzilla")
    usa_pal4_addr = alloc_expansion(usa_scene[512 + 4 * 32 : 512 + 5 * 32], "usa_obj_pal4_mothra")
    jpn_pal2_addr = alloc_expansion(jpn_scene[512 + 2 * 32 : 512 + 3 * 32], "jpn_obj_pal2_godzilla")
    jpn_pal4_addr = alloc_expansion(jpn_scene[512 + 4 * 32 : 512 + 5 * 32], "jpn_obj_pal4_mothra")
    jpn_pal3_addr = alloc_expansion(jpn_scene[512 + 3 * 32 : 512 + 4 * 32], "jpn_obj_pal3_king_ghidorah")
    mkg_pal3_addr = alloc_expansion(struct.pack("<16H", *MKG_PAL3_RGB555), "mkg_obj_pal3_mecha_king_ghidorah")
    jpn_pal6_addr = alloc_expansion(jpn_scene[512 + 6 * 32 : 512 + 7 * 32], "jpn_obj_pal6_rodan")
    fire_rodan_pal6_addr = alloc_expansion(struct.pack("<16H", *FIRE_RODAN_PAL6_RGB555), "fire_rodan_obj_pal6")
    jpn_pal7_addr = alloc_expansion(jpn_scene[512 + 7 * 32 : 512 + 8 * 32], "jpn_obj_pal7_megalon")
    purple_megalon_pal7_addr = alloc_expansion(struct.pack("<16H", *PURPLE_MEGALON_PAL7_RGB555), "purple_megalon_obj_pal7")

    # 1c. Per-Monster 4-Bit SKIN_MASK Dispatch Table (0..15: bit0=GZ, bit1=MG/Kiryu, bit2=Mothra, bit3=MKG)
    def jpn_entry_cpu_addr(idx: int) -> int:
        off = struct.unpack_from("<I", jpn_bytes, JPN_ARCHIVE_BASE + idx * 4)[0]
        return 0x08000000 + JPN_ARCHIVE_BASE + off

    dispatch_entries: list[tuple[int, int]] = []

    # Individual monster battle sprite packs (32=Godzilla bit0, 39=MG bit1, 51=Mothra bit2)
    # Plus virtual archive IDs 392/393/394 for Custom Mode independent Classic entities (IDs 7/10/11)
    monster_bits = {32: 0, 39: 1, 51: 2}
    virtual_ids = {32: 392, 39: 393, 51: 394}
    for jpn_idx, usa_idx, jpn_to_usa, label in CLASSIC_REMAPPED_MONSTERS:
        jpn_blob = get_archive_entry(jpn_bytes, JPN_ARCHIVE_BASE, jpn_idx)
        usa_blob = get_archive_entry(usa_bytes, USA_ARCHIVE_BASE, usa_idx)
        remapped = remap_sprite_pack_frames(jpn_blob, usa_blob, jpn_to_usa)
        classic_addr = alloc_expansion(remapped, f"classic_{label}")
        orig_addr = jpn_entry_cpu_addr(jpn_idx)
        bit = monster_bits[jpn_idx]
        ptrs16 = [classic_addr if (m & (1 << bit)) else orig_addr for m in range(16)]
        tbl_addr = alloc_expansion(struct.pack("<16I", *ptrs16), f"ptrs16_{label}")
        dispatch_entries.append((jpn_idx, tbl_addr))
        # Always-classic virtual archive entry (zero extra sprite data!)
        v_tbl_addr = alloc_expansion(struct.pack("<16I", *([classic_addr] * 16)), f"ptrs16_virt_{label}")
        dispatch_entries.append((virtual_ids[jpn_idx], v_tbl_addr))

    # Canonical Mini Mecha-King Ghidorah 69-frame sprite pack (JPN[33] bit 3 in Story Mode + virtual ID 395 in Custom Mode)
    # Ingests editable 1x sheet `sprite_sheets_to_mod/mini_mkg_template_1x.png` directly when present!
    jpn33_orig = get_archive_entry(jpn_bytes, JPN_ARCHIVE_BASE, 33)
    mkg_sheet_1x = PROJECT_DIR / "sprite_sheets_to_mod" / "mini_mkg_template_1x.png"
    if mkg_sheet_1x.exists():
        mkg_battle_blob = ingest_mkg_sheet_1x(jpn33_orig, mkg_sheet_1x)
    else:
        mkg_battle_blob = build_canonical_mkg_pack(jpn33_orig)
    mkg_battle_addr = alloc_expansion(mkg_battle_blob, "canonical_mini_mkg_battle_69f")
    orig_33_addr = jpn_entry_cpu_addr(33)
    ptrs16_33 = [mkg_battle_addr if (m & 8) else orig_33_addr for m in range(16)]
    dispatch_entries.append((33, alloc_expansion(struct.pack("<16I", *ptrs16_33), "ptrs16_mkg_33")))
    dispatch_entries.append((395, alloc_expansion(struct.pack("<16I", *([mkg_battle_addr] * 16)), "ptrs16_virt_mkg_395")))

    # Multi-monster composite packs (212 small icons, 229 nameplates 15f, 230 portraits)
    for jpn_idx, usa_idx, frame_bits, label in COMPOSITE_SKIN_PACKS:
        jpn_blob = get_archive_entry(jpn_bytes, JPN_ARCHIVE_BASE, jpn_idx)
        usa_blob = get_archive_entry(usa_bytes, USA_ARCHIVE_BASE, usa_idx)
        if jpn_idx == 212:
            # Remap MKG middle head on alt_blob f6..f11 (Story Mode Select bit 3) + Battle Results f43!
            mkg_icon_blob = build_mkg_mini_icon_pack(jpn_blob)
            usa_212_mkg = build_mkg_mini_icon_pack(usa_blob)
            extras_212 = [
                (usa_blob, 5),       # f42: ID  7 Godzilla '99
                (mkg_icon_blob, 11), # f43: ID  8 Mecha-Ghidorah (silver middle head!)
                (jpn_blob, 17),      # f44: ID  9 Fire Rodan
                (usa_blob, 23),      # f45: ID 10 Classic Mechagodzilla
                (usa_blob, 29),      # f46: ID 11 Mothra '92
                (jpn_blob, 35),      # f47: ID 12 Megalon-01
            ]
            base_blob = append_frames_to_pack(jpn_blob, extras_212)
            alt_blob = append_frames_to_pack(usa_212_mkg, extras_212)
            base_addr = alloc_expansion(base_blob, f"base_{label}_48f")
        elif jpn_idx == 229:
            # Base has f3='KIRYU' (default Monster Select & 2P VS ID 4); Alt has official f3='MECHAGODZILLA' (Story bit 1)!
            base_blob = build_big_nameplate_229_15f(usa_blob, kiryu_on_f3=True)
            alt_blob = build_big_nameplate_229_15f(usa_blob, kiryu_on_f3=False)
            base_addr = alloc_expansion(base_blob, f"base_{label}")
        else:
            base_blob = jpn_blob
            alt_blob = usa_blob
            base_addr = jpn_entry_cpu_addr(jpn_idx)
        active_mask = 0
        for b, _ in frame_bits.values():
            active_mask |= (1 << b)
        cache: dict[int, int] = {0: base_addr}
        ptrs16: list[int] = []
        for m in range(16):
            key = m & active_mask
            if key not in cache:
                comp = build_composite_skin_pack(base_blob, alt_blob, frame_bits, key)
                cache[key] = alloc_expansion(comp, f"comp_{label}_m{key}")
            ptrs16.append(cache[key])
        tbl_addr = alloc_expansion(struct.pack("<16I", *ptrs16), f"ptrs16_{label}")
        dispatch_entries.append((jpn_idx, tbl_addr))

    dispatch_table_bytes = bytearray()
    for jpn_idx, tbl_addr in dispatch_entries:
        dispatch_table_bytes.extend(struct.pack("<2I", jpn_idx, tbl_addr))
    dispatch_table_bytes.extend(struct.pack("<2I", 0, 0))
    skin_dispatch_table_addr = alloc_expansion(bytes(dispatch_table_bytes), "skin_dispatch_table")

    # 1d. Localized English UI Sprites (redirected via AG4J Archive Offset Table)
    for jpn_idx, usa_idx, label in UI_SPRITE_REDIRECTS:
        blob = get_archive_entry(usa_bytes, USA_ARCHIVE_BASE, usa_idx)
        cpu_addr = alloc_expansion(blob, label)
        new_rel_off = (cpu_addr - 0x08000000) - JPN_ARCHIVE_BASE
        table_off = JPN_ARCHIVE_BASE + jpn_idx * 4
        orig_bytes = jpn_bytes[table_off : table_off + 4]
        assert_and_patch(rom, table_off, orig_bytes, struct.pack("<I", new_rel_off), label=label)

    # 1e. Title Scene Pack (JPN[338]) + Title Logo with DX badge (JPN[236] <- USA[136] + DX)
    #     + Blank JPN[237] (remove title grid overlay); JPN[238] <- USA[197] (Licensed by Nintendo)
    blank_237 = build_blank_sprite_8bpp()
    blank_237_addr = alloc_expansion(blank_237, "ui_title_blank_grid_237")
    g_off = JPN_ARCHIVE_BASE + 237 * 4
    assert_and_patch(
        rom,
        g_off,
        jpn_bytes[g_off : g_off + 4],
        struct.pack("<I", (blank_237_addr - 0x08000000) - JPN_ARCHIVE_BASE),
        label="ui_title_blank_grid_237",
    )

    title_logo_dx = build_title_logo_dx(get_archive_entry(usa_bytes, USA_ARCHIVE_BASE, 136))
    logo_addr = alloc_expansion(title_logo_dx, "ui_title_logo_dx_236")
    l_off = JPN_ARCHIVE_BASE + 236 * 4
    assert_and_patch(
        rom,
        l_off,
        jpn_bytes[l_off : l_off + 4],
        struct.pack("<I", (logo_addr - 0x08000000) - JPN_ARCHIVE_BASE),
        label="ui_title_logo_dx_236",
    )

    jpn_title_scene = bytearray(get_archive_entry(jpn_bytes, JPN_ARCHIVE_BASE, 338))
    usa_title_scene = get_archive_entry(usa_bytes, USA_ARCHIVE_BASE, 332)
    jpn_title_scene[512:1024] = usa_title_scene[512:1024]
    title_scene_addr = alloc_expansion(bytes(jpn_title_scene), "title_scene_usa_obj_pal")
    t_off = JPN_ARCHIVE_BASE + 338 * 4
    assert_and_patch(
        rom,
        t_off,
        jpn_bytes[t_off : t_off + 4],
        struct.pack("<I", (title_scene_addr - 0x08000000) - JPN_ARCHIVE_BASE),
        label="title_scene_338_redirect",
    )

    # 1f. English 28-frame Mode/Rule/DX-Options Pills (JPN[228] <- USA[124] + 9 English pills)
    pills_28f = build_english_mode_pills_28f(get_archive_entry(usa_bytes, USA_ARCHIVE_BASE, 124))
    pills_addr = alloc_expansion(pills_28f, "english_mode_rule_dx_pills_28f")
    p_off = JPN_ARCHIVE_BASE + 228 * 4
    assert_and_patch(
        rom,
        p_off,
        jpn_bytes[p_off : p_off + 4],
        struct.pack("<I", (pills_addr - 0x08000000) - JPN_ARCHIVE_BASE),
        label="ui_mode_rule_pills_228",
    )

    # 1g. English 4-frame Mode & Rule Headers (JPN[234] <- USA[95] 3f + frame 0)
    hdrs_4f = build_english_mode_headers_4f(get_archive_entry(usa_bytes, USA_ARCHIVE_BASE, 95))
    hdrs_addr = alloc_expansion(hdrs_4f, "english_mode_rule_headers_4f")
    h_off = JPN_ARCHIVE_BASE + 234 * 4
    assert_and_patch(
        rom,
        h_off,
        jpn_bytes[h_off : h_off + 4],
        struct.pack("<I", (hdrs_addr - 0x08000000) - JPN_ARCHIVE_BASE),
        label="ui_mode_rule_headers_234",
    )

    # 1h. v0.8 Hybrid 12-Entity Custom Mode Packs:
    #     - JPN[213] (13f Custom Portraits: f0..f6 JPN + f7..f12 alt entities)
    #     - JPN[285] (Custom Mode Scene w/ OBJ Pal 9..13 = 5 alt monster palettes)
    #     - JPN[167] (25f Custom Name Labels: f3='KIRYU', f19..f24='CLASSIC G'..'P.MEGALON')
    #     - JPN[216] (15f 3P/4P VS Nameplates: USA[119] 6f + f6..f8 pad + f9..f14 IDs 7..12)
    def redirect_archive(jpn_idx: int, blob_data: bytes, label: str) -> None:
        addr = alloc_expansion(blob_data, label)
        t_off = JPN_ARCHIVE_BASE + jpn_idx * 4
        assert_and_patch(
            rom,
            t_off,
            jpn_bytes[t_off : t_off + 4],
            struct.pack("<I", (addr - 0x08000000) - JPN_ARCHIVE_BASE),
            label=label,
        )

    jpn_213 = get_archive_entry(jpn_bytes, JPN_ARCHIVE_BASE, 213)
    jpn_213_mkg = build_canonical_mkg_pack(jpn_213, only_frame=2, is_portrait=True)
    usa_70 = get_archive_entry(usa_bytes, USA_ARCHIVE_BASE, 70)
    portrait_14f = append_frames_to_pack(
        jpn_213,
        [
            (usa_70, 1),       # f7  : ID  7 Godzilla '99
            (jpn_213_mkg, 2),  # f8  : ID  8 Canonical Mini Mecha-King Ghidorah
            (jpn_213, 3),      # f9  : ID  9 Fire Rodan
            (usa_70, 4),       # f10 : ID 10 Classic Mechagodzilla (Heisei)
            (usa_70, 5),       # f11 : ID 11 Mothra '92
            (jpn_213, 6),      # f12 : ID 12 Megalon-01 (Eva Unit-01)
            (jpn_213, 0),      # f13 : ID 13 RANDOM ('?' portrait!)
        ],
    )
    redirect_archive(213, portrait_14f, "custom_mode_portraits_14f")

    # v1.0: 9-frame Custom Mode Stage Names (JPN[233] <- USA[126] 7f + 'Tokyo 1' + 'Random')
    stage_names_9f = build_custom_stage_names_9f(get_archive_entry(usa_bytes, USA_ARCHIVE_BASE, 126))
    redirect_archive(233, stage_names_9f, "custom_mode_stage_names_9f")

    # v1.0: 14-frame Single-Player Monster Select DX Stat Bars (JPN[215] <- USA[131] 8f + 6 DX alt stat bars)
    stat_bars_14f = build_stat_bars_14f(get_archive_entry(usa_bytes, USA_ARCHIVE_BASE, 131))
    redirect_archive(215, stat_bars_14f, "monster_select_stat_bars_14f")

    # Single 15-frame packs for JPN[231] (3P/4P VS Portraits) & JPN[243] (2P Giant VS Depictions)
    # Recolor Fire Rodan (f11), Megalon-01 (f14), and Shadow MKG (f10 on 3P/4P) in JPN[335]'s 256-color VS palette!
    scn335 = get_archive_entry(jpn_bytes, JPN_ARCHIVE_BASE, 335)
    vs_pal256 = [
        ((c & 31) * 8, ((c >> 5) & 31) * 8, ((c >> 10) & 31) * 8)
        for c in struct.unpack_from("<256H", scn335, 512)
    ]
    jpn_243 = get_archive_entry(jpn_bytes, JPN_ARCHIVE_BASE, 243)

    # v1.0: 15-frame Story Mode Connie News Cutout Portraits (JPN[230]):
    #   Connie News dynamically DMA-loads JPN[365] (512-byte 256-color OBJ palette) at 0x0800A4E6!
    #   f0..f6 = JPN base (f6 = Meteor!), f9..f14 = USA[143] Godzilla '99 / official Shadow MKG silhouette (JPN[243] f6) /
    #   recolored Fire Rodan / USA[143] Classic Mechagodzilla / USA[143] Mothra '92 / recolored Megalon-01!
    p365_news = get_archive_entry(jpn_bytes, JPN_ARCHIVE_BASE, 365)
    news_pal256 = [
        ((c & 31) * 8, ((c >> 5) & 31) * 8, ((c >> 10) & 31) * 8)
        for c in struct.unpack_from("<256H", p365_news, 0)
    ]
    jpn_230 = get_archive_entry(jpn_bytes, JPN_ARCHIVE_BASE, 230)
    usa_143 = get_archive_entry(usa_bytes, USA_ARCHIVE_BASE, 143)
    news_portraits_15f = append_frames_to_pack(
        jpn_230,
        [
            (jpn_230, 0), (jpn_230, 0),  # f7..f8 pad
            (usa_143, 0),  # f9  : Godzilla '99 (USA[143], native JPN[365] palette!)
            (jpn_230, 1),  # f10 : Shadow Mecha-King Ghidorah (composited w/ JPN[243] f6 below!)
            (jpn_230, 2),  # f11 : Fire Rodan (recolored in JPN[365] palette below!)
            (usa_143, 3),  # f12 : Classic Mechagodzilla (USA[143], native JPN[365] palette!)
            (usa_143, 4),  # f13 : Mothra '92 (USA[143], native JPN[365] palette!)
            (jpn_230, 5),  # f14 : Megalon-01 (recolored in JPN[365] palette below!)
        ],
    )
    news_portraits_15f = recolor_8bpp_pack_frames(
        news_portraits_15f, news_pal256, {11: "news_fire_rodan", 14: "news_megalon01"}
    )
    news_portraits_15f = build_shadow_mkg_news_portrait(
        news_portraits_15f, jpn_230, jpn_243, news_pal256, vs_pal256, target_frame=10
    )
    redirect_archive(230, news_portraits_15f, "story_news_portraits_15f")

    names_25f = build_custom_mode_names_25f(get_archive_entry(usa_bytes, USA_ARCHIVE_BASE, 67))
    redirect_archive(240, names_25f, "custom_mode_names_25f_from_usa_67")

    usa_119 = get_archive_entry(usa_bytes, USA_ARCHIVE_BASE, 119)
    vs_names_15f = build_vs_3p4p_names_15f(usa_119)
    redirect_archive(216, vs_names_15f, "vs_3p4p_nameplates_15f")

    jpn_231 = get_archive_entry(jpn_bytes, JPN_ARCHIVE_BASE, 231)
    usa_118 = get_archive_entry(usa_bytes, USA_ARCHIVE_BASE, 118)
    vs_portraits_15f = append_frames_to_pack(
        jpn_231,
        [
            (jpn_231, 0), (jpn_231, 0), (jpn_231, 0),  # f6..f8 pad
            (usa_118, 0),  # f9  : ID  7 Godzilla '99
            (jpn_231, 1),  # f10 : ID  8 Official 2P Giant VS Shadow Mecha-Ghidorah silhouette (composited below!)
            (jpn_231, 2),  # f11 : ID  9 Fire Rodan (recolored below!)
            (usa_118, 3),  # f12 : ID 10 Classic Mechagodzilla
            (usa_118, 4),  # f13 : ID 11 Mothra '92
            (jpn_231, 5),  # f14 : ID 12 Megalon-01 (recolored below!)
        ],
    )
    vs_portraits_15f = recolor_8bpp_pack_frames(
        vs_portraits_15f, vs_pal256, {11: "fire_rodan", 14: "megalon01"}
    )
    vs_portraits_15f = build_shadow_mkg_3p4p_portrait(vs_portraits_15f, jpn_231, jpn_243, target_frame=10)
    redirect_archive(231, vs_portraits_15f, "vs_3p4p_portraits_15f")

    usa_117 = build_classic_giant_monsters_8f(get_archive_entry(usa_bytes, USA_ARCHIVE_BASE, 117))
    vs_giant_15f = append_frames_to_pack(
        jpn_243,
        [
            (jpn_243, 0),  # f8  : pad
            (usa_117, 0),  # f9  : ID  7 Godzilla '99
            (jpn_243, 6),  # f10 : ID  8 Official Shadow Mecha-King Ghidorah!
            (jpn_243, 2),  # f11 : ID  9 Fire Rodan (recolored below!)
            (usa_117, 3),  # f12 : ID 10 Classic Mechagodzilla
            (usa_117, 4),  # f13 : ID 11 Mothra '92
            (jpn_243, 5),  # f14 : ID 12 Megalon-01 (recolored below!)
        ],
    )
    vs_giant_15f = recolor_8bpp_pack_frames(
        vs_giant_15f, vs_pal256, {11: "fire_rodan", 14: "megalon01"}
    )
    redirect_archive(243, vs_giant_15f, "vs_2p_giant_depictions_15f")

    # 1i. v0.9 12-Entity Battle HUD Tileset (JPN[25] <- USA[12] + 12 Left/Right outlined names)
    hud_blob, hud_name_tbl = build_battle_hud_12entity(get_archive_entry(usa_bytes, USA_ARCHIVE_BASE, 12))
    redirect_archive(25, hud_blob, "ui_battle_hud_tileset_12entity")
    hud_name_tbl_addr = alloc_expansion(hud_name_tbl, "battle_hud_name_tbl_12entity")

    print(f"Expansion usage: {cursor - EXPANSION_BASE:,} B ({(cursor - EXPANSION_BASE)/1024:.1f} KB) of 4,096 KB")

    # --- 2. Patch the 5 Language Slot-0 Text Pointers (0x08033530 -> 0x08400000) ---
    orig_txt_ptr = struct.pack("<I", 0x08033530)
    new_txt_ptr = struct.pack("<I", eng_text_addr)
    for off, label in [
        (0x0036D4, "ptr_text_slot0_lang_switch"),
        (0x006ABC, "ptr_text_slot0_game_init"),
        (0x006F64, "ptr_text_slot0_menu_a"),
        (0x008274, "ptr_text_slot0_menu_b"),
        (0x00C920, "ptr_text_slot0_menu_c"),
    ]:
        assert_and_patch(rom, off, orig_txt_ptr, new_txt_ptr, label=label)

    # --- 2b. Patch Battle HUD Monster Name Tile Table (0x0334B8..0x033517 <- USA 0x0327DC..0x03283B) ---
    assert_and_patch(
        rom,
        0x0334B8,
        jpn_bytes[0x0334B8:0x033518],
        usa_bytes[0x0327DC:0x03283C],
        label="battle_hud_monster_name_tiles",
    )

    # --- 3. Assemble & Write Thumb Cave at 0x3D2D00 ---
    cave_bytes, addrs = build_cave_code(
        skin_dispatch_table_addr=skin_dispatch_table_addr,
        usa_pal2_addr=usa_pal2_addr,
        usa_pal4_addr=usa_pal4_addr,
        jpn_pal2_addr=jpn_pal2_addr,
        jpn_pal4_addr=jpn_pal4_addr,
        jpn_pal3_addr=jpn_pal3_addr,
        mkg_pal3_addr=mkg_pal3_addr,
        jpn_pal6_addr=jpn_pal6_addr,
        fire_rodan_pal6_addr=fire_rodan_pal6_addr,
        jpn_pal7_addr=jpn_pal7_addr,
        purple_megalon_pal7_addr=purple_megalon_pal7_addr,
        hud_name_tbl_addr=hud_name_tbl_addr,
        night_tokyo_bg_pal_addr=night_tokyo_bg_pal_addr,
        eng_text_base_addr=eng_text_addr,
        eng_text_alt_addr=eng_text_alt_addr,
    )
    print(f"Thumb cave size: {len(cave_bytes)} B @ 0x{CAVE_BASE:06X}")
    for k, v in addrs.items():
        print(f"  {k:20s} = 0x{v:08X}")
    assert_and_patch(rom, CAVE_BASE, b"\x00" * len(cave_bytes), cave_bytes, label="cave_thumb_hooks")

    # --- 4. Install the 3 Guarded Hooks ---
    # Hook 1: ArchiveGetPtr (0x002C48): ldr r1, [pc, #0]; bx r1; .word (cave | 1)
    # Note: at 0x08002C48 (4-byte aligned), pc = 0x08002C4C, so `ldr r1, [pc, #0]` loads 0x08002C4C!
    hook_arch = struct.pack("<2HI", 0x4900, 0x4708, addrs["archive_get_ptr"] | 1)
    assert_and_patch(
        rom,
        0x002C48,
        bytes.fromhex("0349096880004018"),
        hook_arch,
        label="hook_archive_get_ptr",
    )

    # Hook 2: LoadScene palette DMA (0x01AA8E): BL cave_load_scene_pal
    hook_scene = encode_thumb_bl(0x0801AA8E, addrs["load_scene_pal"])
    assert_and_patch(
        rom,
        0x01AA8E,
        bytes.fromhex("88608868"),
        hook_scene,
        label="hook_load_scene_palette",
    )

    # Hook 3: Monster Select Select-button toggle (0x0128C4): BL cave_select_toggle
    hook_sel = encode_thumb_bl(0x080128C4, addrs["select_toggle"])
    assert_and_patch(
        rom,
        0x0128C4,
        bytes.fromhex("11480188"),
        hook_sel,
        label="hook_monster_select_input",
    )

    # Hook 3b (v0.5): Custom Mode per-monster Select toggle (0x0135C0): BL cave_custom_select_toggle
    assert_and_patch(
        rom,
        0x0135C0,
        bytes.fromhex("0b480188"),
        encode_thumb_bl(0x080135C0, addrs["custom_select_toggle"]),
        label="hook_custom_mode_select_input",
    )

    # Hook 4 (v0.2): 1P-4P Overhead Tag Toggle (0x00473A): BL cave_check_ptag
    assert_and_patch(
        rom,
        0x00473A,
        bytes.fromhex("4a480078"),
        encode_thumb_bl(0x0800473A, addrs["check_ptag"]),
        label="hook_player_tag_toggle",
    )

    # Hook 5 (v0.2): Story Mode Stage Order Toggle (0x012780): BL cave_stage_order
    assert_and_patch(
        rom,
        0x012780,
        bytes.fromhex("05f094fe"),
        encode_thumb_bl(0x08012780, addrs["stage_order"]),
        label="hook_stage_order_toggle",
    )

    # Hook 6 (v0.2): Story Mode Bonus Stages Toggle (0x00D18A): BL cave_bonus_stage
    assert_and_patch(
        rom,
        0x00D18A,
        bytes.fromhex("0bf09ff9"),
        encode_thumb_bl(0x0800D18A, addrs["bonus_stage"]),
        label="hook_bonus_stage_toggle",
    )

    # Hook 7 (v0.2): Options Menu DX Page Toggle (0x014884): BL cave_options_dx
    assert_and_patch(
        rom,
        0x014884,
        bytes.fromhex("1648174a"),
        encode_thumb_bl(0x08014884, addrs["options_dx"]),
        label="hook_options_dx_menu",
    )

    # --- 4b. v0.8/v1.0 Hybrid 12-Entity + Random Fighter + 8-Stage + Random Stage Custom Mode Bounds ---
    for col_max_off in (0x032F10, 0x032F4C, 0x032F88, 0x032FC4):
        assert_and_patch(
            rom,
            col_max_off,
            struct.pack("<I", 7),
            struct.pack("<I", 14),  # 0=OFF, 1..12=12 fighters, 13=RANDOM
            label=f"custom_mode_ui_max_{col_max_off:06X}",
        )
    for stg_max_off in (0x032EF8, 0x032F34, 0x032F70, 0x032FAC):
        assert_and_patch(
            rom,
            stg_max_off,
            struct.pack("<I", 7),
            struct.pack("<I", 9),   # 0..6=7 vanilla stages, 7=Tokyo 1 (Night), 8=Random
            label=f"custom_mode_stage_max_{stg_max_off:06X}",
        )
    assert_and_patch(rom, 0x013642, bytes.fromhex("0620"), bytes.fromhex("0d20"), label="custom_mode_wrap_left_13")
    assert_and_patch(rom, 0x0139F2, bytes.fromhex("0628"), bytes.fromhex("0d28"), label="custom_mode_wrap_right_13")

    # Hook 16 (v1.0): Resolve Custom Mode ID 13 (RANDOM) -> 1..12 on confirm (0x01354C)
    assert_and_patch(
        rom,
        0x01354C,
        bytes.fromhex("02f048f9"),
        encode_thumb_bl(0x0801354C, addrs["custom_resolve_random"]),
        label="hook_custom_resolve_random_12",
    )

    # Hook 17 (v1.0): Custom Mode Stage Launch (0x00CBFE..0x00CC05): BL cave_custom_stage_launch + 2x NOP
    assert_and_patch(
        rom,
        0x00CBFE,
        bytes.fromhex("0849084800784018"),
        encode_thumb_bl(0x0800CBFE, addrs["custom_stage_launch"]) + bytes.fromhex("c046c046"),
        label="hook_custom_stage_launch",
    )

    # Hook 18 (v1.0): Single-Player Monster Select Live DX Stat Bars + 12 Big Nameplates + Story Text Table (0x012F42)
    assert_and_patch(
        rom,
        0x012F42,
        bytes.fromhex("01388142"),
        encode_thumb_bl(0x08012F42, addrs["stat_bars"]),
        label="hook_monster_select_stat_bars_and_nameplates",
    )

    # Hook 19 (v1.0): Story Mode Game Over Giant Portrait SKIN_MASK Support (Actor 0x7C at 0x015D48)
    assert_and_patch(
        rom,
        0x015D48,
        bytes.fromhex("04490878"),
        encode_thumb_bl(0x08015D48, addrs["gameover_portrait"]),
        label="hook_gameover_portrait_skin",
    )

    # Hook 20 (v1.0): Single-Player Monster Select Big Domination Nameplates 1..6 -> 9..14 (0x012458)
    assert_and_patch(
        rom,
        0x012458,
        bytes.fromhex("01398842"),
        encode_thumb_bl(0x08012458, addrs["nameplate_229"]),
        label="hook_monster_select_big_nameplate_229",
    )

    # Hook 21 (v1.0): Story Mode Connie News Cutout Portraits 1..6 -> 9..14 (0x00CD4C..0x00CD51)
    assert_and_patch(
        rom,
        0x00CD4C,
        bytes.fromhex("002813d00138"),
        encode_thumb_bl(0x0800CD4C, addrs["news_portrait"]) + bytes.fromhex("c046"),
        label="hook_story_news_portrait_230",
    )

    # Hook 8 (v0.8): Custom Mode portrait palette LUT (0x013EB8)
    assert_and_patch(
        rom,
        0x013EB8,
        bytes.fromhex("487c002806d10420"),
        struct.pack("<2HI", 0x4A00, 0x4710, addrs["custom_pal"] | 1),
        label="hook_custom_mode_portrait_pal",
    )

    # Hook 9 (v0.8): Custom Mode name label 25f dispatcher (0x013F6C)
    assert_and_patch(
        rom,
        0x013F6C,
        bytes.fromhex("487c002800d1bee0"),
        struct.pack("<2HI", 0x4A00, 0x4710, addrs["custom_name"] | 1),
        label="hook_custom_mode_name_label",
    )

    # Hook 10 (v0.8): 2P Giant VS & 3P/4P VS 15f + roar index fix (0x0159AC)
    assert_and_patch(
        rom,
        0x0159AC,
        bytes.fromhex("c01800780138e084"),
        struct.pack("<2HI", 0x4A00, 0x4710, addrs["vs_frame"] | 1),
        label="hook_vs_screen_12entity",
    )

    # Hook 10b (v0.8): 2P Giant VS & 3P/4P VS Portraits 15f dispatcher (0x01583C + clamp 0x015852)
    assert_and_patch(
        rom,
        0x01583C,
        bytes.fromhex("80190078013802e0"),
        struct.pack("<2HI", 0x4900, 0x4708, addrs["vs_portrait"] | 1),
        label="hook_vs_portrait_12entity",
    )
    assert_and_patch(rom, 0x015852, bytes.fromhex("0728"), bytes.fromhex("0e28"), label="vs_portrait_clamp_14")

    # Hook 11 (v0.8): Battle Monster Spawn table dispatcher for IDs 7..12 (0x0042E8)
    assert_and_patch(
        rom,
        0x0042E8,
        bytes.fromhex("012929d10023fa5e"),
        struct.pack("<2HI", 0x4B00, 0x4718, addrs["battle_spawn"] | 1),
        label="hook_battle_spawn_12entity",
    )

    # --- 4c. v0.9 Polish Hooks: Battle Results 12-Entity Icons, Subtle DX Stats, & Battle HUD Names ---
    assert_and_patch(
        rom,
        0x013346,
        bytes.fromhex("01280cd1"),
        encode_thumb_bl(0x08013346, addrs["results_icon"]),
        label="hook_battle_results_icons_12entity",
    )
    assert_and_patch(
        rom,
        0x0044E0,
        bytes.fromhex("47203072"),
        encode_thumb_bl(0x080044E0, addrs["init_hp"]),
        label="hook_init_hp_12entity",
    )
    assert_and_patch(
        rom,
        0x01CAC0,
        bytes.fromhex("00b506480068008c"),
        struct.pack("<2HI", 0x4A00, 0x4710, addrs["walk_speed"] | 1),
        label="hook_walk_speed_12entity",
    )
    assert_and_patch(
        rom,
        0x01C7A0,
        bytes.fromhex("21784801401a8000"),
        struct.pack("<2HI", 0x4900, 0x4708, addrs["hud_name_r"] | 1),
        label="hook_battle_hud_name_right",
    )
    assert_and_patch(
        rom,
        0x01C830,
        bytes.fromhex("21784801401a8000"),
        struct.pack("<2HI", 0x4900, 0x4708, addrs["hud_name_l"] | 1),
        label="hook_battle_hud_name_left",
    )

    # --- 5. Strict Diff Gate on Original 4 MB Region ---
    verify_diff(jpn_bytes, rom[: len(jpn_bytes)], PROJECT_DIR / "allowed_ranges.json")

    args.out_rom.parent.mkdir(parents=True, exist_ok=True)
    args.out_rom.write_bytes(rom)
    bps_info = write_bps(jpn_bytes, rom, args.out_bps)
    print(format_checksums(jpn_bytes, rom, bps_info))

    for warning in check_version_sync(VERSION, [REPO_ROOT / "README.md"]):
        print(f"WARNING: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
