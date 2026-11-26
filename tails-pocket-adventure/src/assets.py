"""NGPC K2GE 2bpp tile encoders, metasprite allocator, and Tails art converters."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Callable

from PIL import Image

TILE_BASE = 0x00CB34
BG_COLORS = {(71, 124, 83), (122, 182, 135), (0, 0, 0)}


def encode_2bpp_tile(px_fn: Callable[[int, int], int]) -> bytes:
    """Encode an 8x8 tile into 16 bytes of NGPC K2GE chunky 2bpp (LE uint16/row)."""
    tb = bytearray(16)
    for y in range(8):
        w = 0
        for x in range(8):
            w |= (px_fn(x, y) & 3) << (14 - x * 2)
        struct.pack_into("<H", tb, y * 2, w)
    return bytes(tb)


def pack_layer_columns(pixels: dict[tuple[int, int], int]) -> list[tuple[int, int, bytes]]:
    """Greedily pack sparse (dx, dy) -> color_idx pixels into 8x8 K2GE 2bpp tiles."""
    remaining = dict(pixels)
    placed: list[tuple[int, int, bytes]] = []
    while remaining:
        cur_min_x = min(x for x, _ in remaining)
        while True:
            col_ys = [y for (x, y) in remaining if cur_min_x <= x < cur_min_x + 8]
            if not col_ys:
                break
            top_y = min(col_ys)
            box_xs = [
                x
                for (x, y) in remaining
                if cur_min_x <= x < cur_min_x + 8 and top_y <= y < top_y + 8
            ]
            dx = min(box_xs)
            dy = top_y
            tile_bytes = bytearray(16)
            for r in range(8):
                b0 = 0
                b1 = 0
                py = dy + r
                for c in range(4):
                    vL = remaining.pop((dx + c, py), 0)
                    vR = remaining.pop((dx + 4 + c, py), 0)
                    b1 |= (vL & 3) << (6 - c * 2)
                    b0 |= (vR & 3) << (6 - c * 2)
                tile_bytes[r * 2] = b0
                tile_bytes[r * 2 + 1] = b1
            placed.append((dx, dy, bytes(tile_bytes)))
    return placed


class TileAndMetaAllocator:
    """Deduplicates custom 8x8 2bpp tiles (IDs 0x8000+) and packs OAM metasprites (0xD000+)."""

    def __init__(self) -> None:
        self.unique_tile_map: dict[bytes, int] = {}
        self.unique_tiles: list[bytes] = []
        self.meta_blob = bytearray()

    def get_custom_tile_id(self, tbytes: bytes) -> int:
        if tbytes not in self.unique_tile_map:
            tid = 0x8000 + len(self.unique_tiles)
            self.unique_tile_map[tbytes] = tid
            self.unique_tiles.append(tbytes)
        return self.unique_tile_map[tbytes]

    def add_metasprite(self, tile_list: list[tuple[int, int, bytes]]) -> int:
        moff = 0xD000 + len(self.meta_blob)
        buf = bytearray(struct.pack("<H", len(tile_list)))
        for dx, dy, tb in tile_list:
            tid = self.get_custom_tile_id(tb)
            buf.extend(struct.pack("<Hbb", tid, dx, dy))
        self.meta_blob.extend(buf)
        return moff

    @property
    def tile_blob(self) -> bytes:
        return b"".join(self.unique_tiles)


def _convert_side_frame(
    fw: int, fh: int, grid: dict[tuple[int, int], tuple[int, int, int]]
) -> tuple[dict[tuple[int, int], int], dict[tuple[int, int], int]]:
    red_xs = [px for (px, _), c in grid.items() if c == (255, 33, 33)]
    anchor_rx = min(red_xs)
    anchor_ry = fh - 1

    body_pixels: dict[tuple[int, int], int] = {}
    over_pixels: dict[tuple[int, int], int] = {}

    for (px, py), rgb in grid.items():
        rx = px - (anchor_rx + 8)
        ry = py - anchor_ry + 13
        is_outer = any(
            (px + dx, py + dy) not in grid for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
        )

        if -3 <= ry <= 0 and 0 <= rx <= 6 and rgb in ((239, 140, 33), (255, 189, 33)):
            body_pixels[(rx, ry)] = 1
            continue
        if -11 <= ry <= -8 and -2 <= rx <= 2 and rgb == (189, 82, 16):
            body_pixels[(rx, ry)] = 3
            continue
        if ry == -3 and rx == 9 and rgb == (0, 156, 255):
            body_pixels[(rx, ry)] = 3
            continue
        if -5 <= ry <= -2 and rx == 7 and rgb == (189, 82, 16):
            if grid.get((px - 1, py)) in ((255, 255, 255), (0, 156, 255), (16, 16, 16)):
                body_pixels[(rx, ry)] = 1
                continue
        if ry == -3 and rx == 6 and rgb == (0, 156, 255):
            over_pixels[(rx, ry)] = 2
            body_pixels[(rx, ry)] = 1
            over_pixels[(rx - 1, ry)] = 2
            body_pixels[(rx - 1, ry)] = 1
            continue
        if ry == -2 and rx == 6 and rgb == (16, 16, 16) and grid.get((px, py - 1)) == (0, 156, 255):
            over_pixels[(rx, ry)] = 3
            body_pixels[(rx, ry)] = 1
            over_pixels[(rx - 1, ry)] = 3
            body_pixels[(rx - 1, ry)] = 1
            continue
        if ry == -1 and rx == 6 and rgb == (33, 66, 255):
            over_pixels[(rx, ry)] = 3
            body_pixels[(rx, ry)] = 1
            if grid.get((px, py - 2)) != (0, 156, 255):
                over_pixels[(rx - 1, ry)] = 3
                body_pixels[(rx - 1, ry)] = 1
            continue

        if rgb in ((16, 16, 16), (115, 115, 115), (156, 156, 156)):
            body_pixels[(rx, ry)] = 3
        elif rgb == (255, 255, 255):
            body_pixels[(rx, ry)] = 1
        elif rgb == (173, 206, 222):
            body_pixels[(rx, ry)] = 3 if is_outer else 1
        elif rgb in ((255, 189, 33), (239, 140, 33)):
            body_pixels[(rx, ry)] = 2
        elif rgb == (189, 82, 16):
            body_pixels[(rx, ry)] = 3 if is_outer else 2
        elif rgb in ((255, 33, 33), (173, 0, 0)):
            over_pixels[(rx, ry)] = 1
            body_pixels[(rx, ry)] = 3
        elif rgb == (0, 156, 255):
            over_pixels[(rx, ry)] = 2
            body_pixels[(rx, ry)] = 1
        elif rgb == (33, 66, 255):
            over_pixels[(rx, ry)] = 3
            body_pixels[(rx, ry)] = 1

    return body_pixels, over_pixels


def _convert_turn_frame(
    fw: int, fh: int, grid: dict[tuple[int, int], tuple[int, int, int]]
) -> tuple[dict[tuple[int, int], int], dict[tuple[int, int], int]]:
    anchor_cx = fw // 2
    anchor_ry = fh - 1
    body_pixels: dict[tuple[int, int], int] = {}
    over_pixels: dict[tuple[int, int], int] = {}

    for (px, py), rgb in grid.items():
        rx = px - anchor_cx
        ry = py - anchor_ry + 13
        is_outer = any(
            (px + dx, py + dy) not in grid for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
        )

        if py == 17 and rgb == (0, 156, 255):
            over_pixels[(rx, ry)] = 2
            body_pixels[(rx, ry)] = 1
            continue
        if py == 18 and rgb == (16, 16, 16) and grid.get((px, 17)) == (0, 156, 255):
            over_pixels[(rx, ry)] = 3
            body_pixels[(rx, ry)] = 1
            continue
        if py == 19 and rgb in ((33, 66, 255), (173, 206, 222), (239, 140, 33)) and 6 <= px <= 23:
            body_pixels[(rx, ry)] = 1
            continue

        if rgb in ((16, 16, 16), (115, 115, 115), (156, 156, 156)):
            body_pixels[(rx, ry)] = 3
        elif rgb == (255, 255, 255):
            body_pixels[(rx, ry)] = 1
        elif rgb == (173, 206, 222):
            body_pixels[(rx, ry)] = 3 if is_outer else 1
        elif rgb in ((255, 189, 33), (239, 140, 33)):
            body_pixels[(rx, ry)] = 2
        elif rgb == (189, 82, 16):
            body_pixels[(rx, ry)] = 3 if is_outer else 2
        elif rgb in ((255, 33, 33), (173, 0, 0)):
            over_pixels[(rx, ry)] = 1
            body_pixels[(rx, ry)] = 3
        elif rgb == (0, 156, 255):
            over_pixels[(rx, ry)] = 2
            body_pixels[(rx, ry)] = 1
        elif rgb == (33, 66, 255):
            over_pixels[(rx, ry)] = 3
            body_pixels[(rx, ry)] = 1

    return body_pixels, over_pixels


def pack_flying_frames(sheet_path: Path, alloc: TileAndMetaAllocator) -> list[tuple[int, int]]:
    """Extract all 11 Sonic Advance flying frames + turn frame and allocate tiles/metasprites."""
    im = Image.open(sheet_path).convert("RGB")
    w, h = im.size
    box_ys = [y for y in range(h) if any(im.getpixel((x, y)) == (122, 182, 135) for x in range(w))]
    y_min, y_max = min(box_ys), max(box_ys)

    col_has_fg = [
        any(im.getpixel((x, y)) not in BG_COLORS for y in range(y_min, y_max + 1))
        for x in range(w)
    ]
    spans: list[tuple[int, int]] = []
    in_f = False
    sx = 0
    for x, fg in enumerate(col_has_fg):
        if fg and not in_f:
            in_f = True
            sx = x
        elif not fg and in_f:
            in_f = False
            spans.append((sx, x - 1))
    if in_f:
        spans.append((sx, w - 1))

    assert len(spans) == 13, f"Expected 13 frames in sprite sheet, found {len(spans)}"

    frames_raw = []
    for x0, x1 in spans:
        f_ys = [
            y
            for y in range(y_min, y_max + 1)
            if any(im.getpixel((x, y)) not in BG_COLORS for x in range(x0, x1 + 1))
        ]
        y0, y1 = min(f_ys), max(f_ys)
        fw, fh = x1 - x0 + 1, y1 - y0 + 1
        grid = {}
        for py in range(fh):
            for px in range(fw):
                c = im.getpixel((x0 + px, y0 + py))
                if c not in BG_COLORS:
                    grid[(px, py)] = c
        frames_raw.append((fw, fh, grid))

    selected_frames = [_convert_side_frame(*frames_raw[i]) for i in range(11)] + [
        _convert_turn_frame(*frames_raw[12])
    ]

    frame_ptrs: list[tuple[int, int]] = []
    for bp, op in selected_frames:
        b_moff = alloc.add_metasprite(pack_layer_columns(bp))
        o_moff = alloc.add_metasprite(pack_layer_columns(op))
        frame_ptrs.append((b_moff, o_moff))
    return frame_ptrs


def pack_ngpc_style_flying_frames(
    sheet_path: Path, alloc: TileAndMetaAllocator
) -> list[tuple[int, int]]:
    """Import 4 active + 2 tired NGPC-style flying frames (cells 1..6) from tails_flying_ngpc_style_1x.png."""
    im = Image.open(sheet_path).convert("RGB")
    base_pal = {
        (255, 255, 255): 1,
        (240, 240, 240): 1,
        (255, 136, 0): 2,
        (240, 128, 0): 2,
        (0, 0, 0): 3,
    }
    over_pal = {
        (255, 68, 0): 1,
        (240, 64, 0): 1,
        (85, 204, 255): 2,
        (80, 192, 240): 2,
        (0, 0, 255): 3,
        (0, 0, 240): 3,
    }
    cw, ch, pad, y_top = 44, 42, 2, 10
    ox, oy = 22, 25
    bg = {(71, 124, 83), (122, 182, 135)}

    frame_ptrs: list[tuple[int, int]] = []
    # Cell 0 is Stock NGPC Tails Standing scale ruler; Cells 1..4 = Active (0x85..0x88), Cells 5..6 = Tired (0x89..0x8A)
    for idx in range(1, 7):
        x0 = pad + idx * (cw + pad)
        bp: dict[tuple[int, int], int] = {}
        op: dict[tuple[int, int], int] = {}
        for py in range(ch):
            for px in range(cw):
                rgb = im.getpixel((x0 + px, y_top + py))
                if rgb in bg:
                    continue
                rx, ry = px - ox, py - oy
                if rgb in base_pal:
                    bp[(rx, ry)] = base_pal[rgb]
                elif rgb in over_pal:
                    ov = over_pal[rgb]
                    op[(rx, ry)] = ov
                    bp[(rx, ry)] = 3 if ov == 1 else 1
                else:
                    raise ValueError(f"Unmapped pixel in {sheet_path} cell {idx} ({px},{py}): {rgb}")
        frame_ptrs.append((alloc.add_metasprite(pack_layer_columns(bp)), alloc.add_metasprite(pack_layer_columns(op))))
    return frame_ptrs


def pack_ngpc_native_flying_frames(
    sheet_path: Path, alloc: TileAndMetaAllocator
) -> list[tuple[int, int]]:
    """Import 6 native 1x NGPC Tails flying frames (3 active + 3 tired) from tails_flying_ngpc_native_1x.png."""
    im = Image.open(sheet_path).convert("RGB")
    base_pal = {
        (255, 255, 255): 1,
        (240, 240, 240): 1,
        (255, 136, 0): 2,
        (240, 128, 0): 2,
        (0, 0, 0): 3,
    }
    over_pal = {
        (255, 68, 0): 1,
        (240, 64, 0): 1,
        (85, 204, 255): 2,
        (80, 192, 240): 2,
        (0, 0, 255): 3,
        (0, 0, 240): 3,
    }
    cw, ch, pad, y_top = 36, 38, 2, 10
    bg = {(71, 124, 83), (122, 182, 135)}

    frame_ptrs: list[tuple[int, int]] = []
    for idx in range(6):
        x0 = pad + idx * (cw + pad)
        bp: dict[tuple[int, int], int] = {}
        op: dict[tuple[int, int], int] = {}
        for py in range(ch):
            for px in range(cw):
                rgb = im.getpixel((x0 + px, y_top + py))
                if rgb in bg:
                    continue
                rx, ry = px - 18, py - 22  # feet at +14, exact match to stock NGPC Tails!
                if rgb in base_pal:
                    bp[(rx, ry)] = base_pal[rgb]
                elif rgb in over_pal:
                    ov = over_pal[rgb]
                    op[(rx, ry)] = ov
                    bp[(rx, ry)] = 3 if ov == 1 else 1
                else:
                    raise ValueError(f"Unmapped pixel in {sheet_path} cell {idx} ({px},{py}): {rgb}")
        frame_ptrs.append((alloc.add_metasprite(pack_layer_columns(bp)), alloc.add_metasprite(pack_layer_columns(op))))
    return frame_ptrs


def pack_chaos_gg_flying_frames(
    sheet_path: Path, alloc: TileAndMetaAllocator
) -> list[tuple[int, int]]:
    """Convert 3 native 1x Sonic Chaos (Game Gear) flying frames + 3 closed-eye tired frames to NGPC 2-layer OAM."""
    im = Image.open(sheet_path).convert("RGB")
    bg_cols = {(0, 72, 0), (182, 72, 182), (255, 182, 255)}
    cell_x0s = (2, 38, 74)

    def convert_cell(x0: int, tired: bool) -> tuple[dict[tuple[int, int], int], dict[tuple[int, int], int]]:
        fg: dict[tuple[int, int], tuple[int, int, int]] = {}
        for y in range(34):
            for x in range(32):
                c = im.getpixel((x0 + x, y))
                if c not in bg_cols:
                    fg[(x, y)] = c

        bp: dict[tuple[int, int], int] = {}
        op: dict[tuple[int, int], int] = {}
        # Anchor: horizontally centered at x=13, bottom of shoes (y=26) at ry=+14 (matches stock NGPC Tails!)
        ox, oy = 13, 12
        for (x, y), c in fg.items():
            rx, ry = x - ox, y - oy
            is_outer = any((x + dx, y + dy) not in fg for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)))
            if c == (255, 72, 0):
                # Red shoe on Overlay 1 + opaque Black Base 3 underneath
                op[(rx, ry)] = 1
                bp[(rx, ry)] = 3
            elif c == (0, 0, 0):
                if x <= 21 and 14 <= y <= 16:
                    # Eye top -> Sky Blue (2) on Overlay + White (1) sclera on Base
                    op[(rx, ry)] = 2
                    bp[(rx, ry)] = 1
                else:
                    bp[(rx, ry)] = 3  # Nose tip
            elif c in ((72, 0, 0), (72, 72, 72)):
                # Bottom half of left eye (x=18, y=16) -> Dark Blue (3) on Overlay + White Base
                if x == 18 and y == 16:
                    op[(rx, ry)] = 3
                    bp[(rx, ry)] = 1
                else:
                    bp[(rx, ry)] = 3
            elif c == (255, 255, 255):
                bp[(rx, ry)] = 1
            elif c == (145, 145, 145):
                if x == 20 and y == 16:
                    # Bottom half of right eye -> Dark Blue (3) on Overlay + White Base
                    op[(rx, ry)] = 3
                    bp[(rx, ry)] = 1
                elif y <= 7:
                    bp[(rx, ry)] = 1  # Keep overhead white spinning tail fluffy
                else:
                    bp[(rx, ry)] = 3 if is_outer else 1
            elif c == (255, 145, 72):
                bp[(rx, ry)] = 2
            elif c == (145, 72, 0):
                if y <= 7:
                    bp[(rx, ry)] = 2  # Keep overhead orange spinning tail bright
                else:
                    bp[(rx, ry)] = 3 if is_outer else 2

        if tired:
            # Close both eyes cleanly (orange eyelids on top + crisp 1px black lash line)
            for ex in (17, 18, 20):
                op.pop((ex - ox, 15 - oy), None)
                op.pop((ex - ox, 16 - oy), None)
                bp[(ex - ox, 14 - oy)] = 2
                bp[(ex - ox, 15 - oy)] = 2
                bp[(ex - ox, 16 - oy)] = 3
            # Also close upper white sclera on both eyes
            bp[(17 - ox, 13 - oy)] = 2
            bp[(18 - ox, 13 - oy)] = 2
            bp[(20 - ox, 13 - oy)] = 2

        return bp, op

    frame_ptrs: list[tuple[int, int]] = []
    # 3 active flying frames (0x85..0x87) + 3 tired flying frames (0x88..0x8A)
    for tired in (False, True):
        for x0 in cell_x0s:
            bp, op = convert_cell(x0, tired=tired)
            frame_ptrs.append((alloc.add_metasprite(pack_layer_columns(bp)), alloc.add_metasprite(pack_layer_columns(op))))
    return frame_ptrs


def pack_compact_flying_frames(sheet_path: Path, alloc: TileAndMetaAllocator) -> list[tuple[int, int]]:
    """Import 12 compact NGPC-scale flying frames from tails_flying_compact_template_1x.png."""
    im = Image.open(sheet_path).convert("RGB")
    base_pal = {
        (255, 255, 255): 1,
        (240, 240, 240): 1,
        (255, 136, 0): 2,
        (240, 128, 0): 2,
        (0, 0, 0): 3,
    }
    over_pal = {
        (255, 68, 0): 1,
        (240, 64, 0): 1,
        (85, 204, 255): 2,
        (80, 192, 240): 2,
        (0, 0, 255): 3,
        (0, 0, 240): 3,
    }
    cw, ch, pad, y_top = 40, 40, 2, 10
    bg = {(71, 124, 83), (122, 182, 135)}

    frame_ptrs: list[tuple[int, int]] = []
    for idx in range(12):
        x0 = pad + idx * (cw + pad)
        bp: dict[tuple[int, int], int] = {}
        op: dict[tuple[int, int], int] = {}
        for py in range(ch):
            for px in range(cw):
                rgb = im.getpixel((x0 + px, y_top + py))
                if rgb in bg:
                    continue
                rx, ry = px - (cw // 2), py - (ch - 3) + 14  # feet aligned with stock Tails (+14)
                if rgb in base_pal:
                    bp[(rx, ry)] = base_pal[rgb]
                elif rgb in over_pal:
                    ov = over_pal[rgb]
                    op[(rx, ry)] = ov
                    bp[(rx, ry)] = 3 if ov == 1 else 1  # opaque base behind red shoe / blue eye
                else:
                    raise ValueError(f"Unmapped pixel in {sheet_path} cell {idx} ({px},{py}): {rgb}")
        b_moff = alloc.add_metasprite(pack_layer_columns(bp))
        o_moff = alloc.add_metasprite(pack_layer_columns(op))
        frame_ptrs.append((b_moff, o_moff))
    return frame_ptrs


def patch_goalpost_from_sheet(data: bytearray, sheet_path: Path, alloc: TileAndMetaAllocator) -> None:
    """Patch end-of-act goalpost/signpost base tiles and overlay metasprite pointers."""
    sheet = Image.open(sheet_path).convert("RGB")
    base_pal = {
        (255, 255, 255): 1,
        (240, 240, 240): 1,
        (255, 136, 0): 2,
        (240, 128, 0): 2,
        (0, 0, 0): 3,
    }
    over_pal = {
        (255, 68, 0): 1,
        (240, 64, 0): 1,
        (85, 204, 255): 2,
        (80, 192, 240): 2,
        (0, 0, 255): 3,
        (0, 0, 240): 3,
    }

    specs = [
        (4, 32, -15, 2434, 0x2D32),    # Front R
        (40, 24, -11, 2443, 0x2D50),   # Angle R
        (80, 24, -11, 2451, 0x2D68),   # Angle L
        (108, 32, -15, 2457, 0x2D7E),  # Front L
    ]

    meta_remap: dict[int, int] = {}
    for x0, fw, base_dx0, base_tid_start, old_over_meta_off in specs:
        cols = fw // 8
        for col in range(cols):
            for half in range(2):
                tid = base_tid_start + col * 2 + half

                def px_val(x: int, y: int, c: int = col, h: int = half, sx0: int = x0) -> int:
                    rgb = sheet.getpixel((sx0 + c * 8 + x, 2 + h * 8 + y))
                    return base_pal.get(rgb, 1)

                data[TILE_BASE + tid * 16 : TILE_BASE + (tid + 1) * 16] = encode_2bpp_tile(px_val)

        opixels = {}
        for py in range(16):
            for px in range(fw):
                rgb = sheet.getpixel((x0 + px, 2 + py))
                if rgb in over_pal:
                    opixels[(base_dx0 + px, -23 + py)] = over_pal[rgb]

        meta_remap[old_over_meta_off] = alloc.add_metasprite(pack_layer_columns(opixels))

    for off in range(0x1CE59B, 0x1CE600):
        if data[off : off + 2] == b"\x0e\x01":
            old_m = struct.unpack_from("<H", data, off + 2)[0]
            if old_m in meta_remap:
                struct.pack_into("<H", data, off + 2, meta_remap[old_m])


def patch_chaos_emerald_text(data: bytearray, ce_path: Path, alloc: TileAndMetaAllocator) -> None:
    """Replace Special Stage 'SONIC GOT A CHAOS EMERALD!' with Tails version."""
    im_ce = Image.open(ce_path).convert("RGB")
    cmap = {
        (0, 255, 170): 1,
        (0, 204, 153): 1,
        (0, 0, 0): 2,
    }
    w, h = im_ce.size
    pixels = {}
    for py in range(h):
        for px in range(w):
            rgb = im_ce.getpixel((px, py))
            if rgb in cmap:
                pixels[(px - w // 2, py - h // 2)] = cmap[rgb]

    ce_moff = alloc.add_metasprite(pack_layer_columns(pixels))
    assert data[0x1D4563:0x1D4567] == b"\x01\x00\xec\x31"
    struct.pack_into("<H", data, 0x1D4565, ce_moff)


def patch_title_card_silhouettes(
    data: bytearray, sheet_path: Path, alloc: TileAndMetaAllocator
) -> None:
    """Replace the 3 Title Card Sonic silhouette frames (0x1CFAD0..0x1CFADF) with Tails."""
    im = Image.open(sheet_path).convert("RGB")
    w, h = im.size
    bg = (71, 124, 83)
    cmap = {
        (255, 255, 255): 1,
        (0, 0, 0): 3,
    }

    col_fg = [any(im.getpixel((x, y)) != bg for y in range(h)) for x in range(w)]
    spans: list[tuple[int, int]] = []
    in_f = False
    sx = 0
    for x, fg in enumerate(col_fg):
        if fg and not in_f:
            in_f, sx = True, x
        elif not fg and in_f:
            in_f = False
            spans.append((sx, x - 1))
    if in_f:
        spans.append((sx, w - 1))

    assert len(spans) == 3, f"Expected 3 silhouette frames in {sheet_path}, found {len(spans)}"

    frame_moffs: list[int] = []
    for x0, x1 in spans:
        fw = x1 - x0 + 1
        pixels: dict[tuple[int, int], int] = {}
        for py in range(h):
            for px in range(fw):
                rgb = im.getpixel((x0 + px, py))
                if rgb in cmap:
                    pixels[(px - fw // 2, py - h)] = cmap[rgb]
        frame_moffs.append(alloc.add_metasprite(pack_layer_columns(pixels)))

    expected = b"\x01\x00\x68\x2f\x01\x0a\x68\x2f\x01\x01\xd2\x2f\x01\x00\x92\x2f"
    assert data[0x1CFAD0:0x1CFAE0] == expected
    m0, m1, m2 = frame_moffs
    struct.pack_into("<H", data, 0x1CFAD2, m0)
    struct.pack_into("<H", data, 0x1CFAD6, m0)
    struct.pack_into("<H", data, 0x1CFADA, m1)
    struct.pack_into("<H", data, 0x1CFADE, m2)


def patch_special_stage_standing(
    data: bytearray, sheet_path: Path, alloc: TileAndMetaAllocator
) -> None:
    """Replace the 4 Special Stage standing/pose Sonic frames (0x1CAB65..0x1CAB9A) with Tails."""
    im = Image.open(sheet_path).convert("RGB")
    base_pal = {
        (255, 255, 255): 1,
        (240, 240, 240): 1,
        (255, 136, 0): 2,
        (240, 128, 0): 2,
        (0, 0, 0): 3,
    }
    over_pal = {
        (255, 68, 0): 1,
        (240, 64, 0): 1,
        (85, 204, 255): 2,
        (80, 192, 240): 2,
        (0, 0, 255): 3,
        (0, 0, 240): 3,
    }

    cell_w, cell_h, pad = 36, 36, 2
    frame_ptrs: list[tuple[int, int]] = []
    for idx in range(5, 9):
        ox = pad + idx * (cell_w + pad) + cell_w // 2
        oy = pad + 24
        x_start = pad + idx * (cell_w + pad)
        bp: dict[tuple[int, int], int] = {}
        op: dict[tuple[int, int], int] = {}
        for py in range(pad, pad + cell_h):
            for px in range(x_start, x_start + cell_w):
                rgb = im.getpixel((px, py))
                rx, ry = px - ox, py - oy
                if rgb in base_pal:
                    bp[(rx, ry)] = base_pal[rgb]
                elif rgb in over_pal:
                    ov = over_pal[rgb]
                    op[(rx, ry)] = ov
                    bp[(rx, ry)] = 3 if ov == 1 else 1  # opaque base behind red/blue overlay
        b_moff = alloc.add_metasprite(pack_layer_columns(bp))
        o_moff = alloc.add_metasprite(pack_layer_columns(op))
        frame_ptrs.append((b_moff, o_moff))

    expected = (
        b"\x0e\x01\x54\x17\x0e\x00\xc4\x16\x03\x00"
        b"\x0e\x01\x6e\x17\x0e\x00\xe6\x16\x03\x06"
        b"\x0e\x01\x84\x17\x0e\x00\x0c\x17\x03\x06"
        b"\x0e\x01\x9e\x17\x0e\x00\x36\x17\x03\x06"
        b"\x0e\x01\x84\x17\x0e\x00\x0c\x17\x03\x06"
    )
    assert data[0x1CAB65:0x1CAB97] == expected
    (b0, o0), (b1, o1), (b2, o2), (b3, o3) = frame_ptrs
    for off, (bm, om) in (
        (0x1CAB65, (b0, o0)),
        (0x1CAB6F, (b1, o1)),
        (0x1CAB79, (b2, o2)),
        (0x1CAB83, (b3, o3)),
        (0x1CAB8D, (b2, o2)),
    ):
        struct.pack_into("<H", data, off + 2, om)
        struct.pack_into("<H", data, off + 6, bm)


def patch_title_tails_text(
    data: bytearray, portrait_path: Path, alloc: TileAndMetaAllocator
) -> None:
    """Replace 'SONIC' logo and Sonic title portrait with Tails (relocated to 0x1F3000..0x1F55FF)."""
    orig_tcnt = struct.unpack_from("<H", data, 0x08BD98)[0]
    assert orig_tcnt == 412
    title_tiles = bytearray(data[0x08BD98 : 0x08BD98 + 2 + orig_tcnt * 16])
    sp1_map = bytearray(data[0x08F5C8 : 0x08F5C8 + 4 + 20 * 19 * 2])
    sp2_map = bytearray(data[0x08F2CC : 0x08F2CC + 4 + 20 * 19 * 2])

    for tid in range(44, 78):
        tb = bytearray(title_tiles[2 + tid * 16 : 2 + (tid + 1) * 16])
        for i in range(16):
            b = tb[i]
            nb = 0
            for sh in (0, 2, 4, 6):
                px = (b >> sh) & 3
                if px in (1, 3):
                    px = 2
                nb |= px << sh
            tb[i] = nb
        title_tiles[2 + tid * 16 : 2 + (tid + 1) * 16] = tb

    title_tiles[2 + 44 * 16 + 3 * 2 : 2 + 44 * 16 + 4 * 2] = b"\x00\x00"
    for y in (3, 4, 5):
        title_tiles[2 + 61 * 16 + y * 2 : 2 + 61 * 16 + (y + 1) * 2] = b"\x00\x00"

    # Deduplicate rows 8..18 of SP1/SP2 (collapses identical solid-blue tiles from cleared 'THE HEDGEHOG' bar)
    canon_tid: dict[bytes, int] = {}
    for m in (sp1_map, sp2_map):
        for r in range(8, 19):
            for c in range(20):
                off = 4 + (r * 20 + c) * 2
                entry = struct.unpack_from("<H", m, off)[0]
                tid = entry & 0x1FF
                if 1 <= tid < 373:
                    key = bytes(title_tiles[2 + tid * 16 : 2 + (tid + 1) * 16])
                    if key not in canon_tid:
                        canon_tid[key] = tid
                    elif canon_tid[key] != tid:
                        struct.pack_into("<H", m, off, (entry & 0xFE00) | canon_tid[key])

    # Clear Sonic portrait + cut-out ring from SP1 rows 0..7 and SP2 rows 0..8 (preserving 4-byte map headers)
    for r in range(8):
        for c in range(20):
            struct.pack_into("<H", sp1_map, 4 + (r * 20 + c) * 2, 0x0000)
    for r in range(9):
        for c in range(20):
            struct.pack_into("<H", sp2_map, 4 + (r * 20 + c) * 2, 0x0000)

    for r in (8, 9, 10):
        for c in range(3, 20):
            struct.pack_into("<H", sp1_map, (r * 20 + c) * 2, 0x0000)
    for r in (9, 10, 11):
        struct.pack_into("<H", sp1_map, (r * 20 + 0) * 2, 0x0000)

    used = {0}
    for r in range(19):
        for c in range(20):
            used.add(struct.unpack_from("<H", sp1_map, 4 + (r * 20 + c) * 2)[0] & 0x1FF)
            used.add(struct.unpack_from("<H", sp2_map, 4 + (r * 20 + c) * 2)[0] & 0x1FF)
    # Strictly stay within static title tiles 1..372; tiles 373..411 hold PRESS A BUTTON / menu text!
    free_slots = [t for t in range(1, 373) if t not in used]

    def alloc_title_tile(key: bytes, uniq_map: dict[bytes, int]) -> int:
        if key not in uniq_map:
            assert free_slots, "Out of Title Screen tile slots (412 VDP font limit)!"
            tid = free_slots.pop(0)
            uniq_map[key] = tid
            title_tiles[2 + tid * 16 : 2 + (tid + 1) * 16] = key
        return uniq_map[key]

    W, H = 128, 24
    grid = [[0] * W for _ in range(H)]

    def rect(x0: int, y0: int, x1: int, y1: int, slant: bool = True) -> None:
        for y in range(y0, y1 + 1):
            dx = (18 - y) // 6 if slant else 0
            for x in range(x0 + dx, x1 + dx + 1):
                if 0 <= x < W and 0 <= y < H:
                    grid[y][x] = 3

    rect(6, 3, 25, 6)
    rect(13, 7, 18, 18)

    for y in range(3, 19):
        dx = (18 - y) // 6
        t = (y - 3) / 15.0
        lx = int(round(37 - t * 8))
        rx = int(round(41 + t * 8))
        for x in range(lx + dx, lx + 5 + dx):
            grid[y][x] = 3
        for x in range(rx - 4 + dx, rx + 1 + dx):
            grid[y][x] = 3
        if 12 <= y <= 14:
            for x in range(lx + dx, rx + 1 + dx):
                grid[y][x] = 3

    rect(57, 3, 68, 6)
    rect(60, 7, 65, 14)
    rect(57, 15, 68, 18)

    rect(74, 3, 79, 18)
    rect(74, 15, 92, 18)

    rect(100, 3, 117, 6)
    rect(97, 5, 102, 11)
    rect(99, 9, 115, 12)
    rect(112, 11, 117, 17)
    rect(97, 15, 115, 18)

    shadow = [row[:] for row in grid]
    for y in range(H):
        for x in range(W):
            if grid[y][x] == 3:
                for ox, oy in ((1, 0), (0, 1), (1, 1)):
                    nx, ny = x + ox, y + oy
                    if 0 <= nx < W and 0 <= ny < H and shadow[ny][nx] == 0:
                        shadow[ny][nx] = 1
    grid = shadow

    badge = [row[:] for row in grid]
    for y in range(H):
        for x in range(W):
            if grid[y][x] in (1, 3):
                for dy in range(-3, 4):
                    for dx in range(-3, 4):
                        if dx * dx + dy * dy <= 11:
                            nx, ny = x + dx, y + dy
                            if 0 <= nx < W and 0 <= ny < 19 and badge[ny][nx] == 0:
                                badge[ny][nx] = 2

    for y in range(0, 19):
        xs = [x for x in range(W) if badge[y][x] != 0]
        if xs:
            for x in range(xs[0], xs[-1] + 1):
                if badge[y][x] == 0:
                    badge[y][x] = 2

    for y, x0, x1 in ((16, 4, 124), (17, 2, 126), (18, 0, 127)):
        for x in range(x0, x1 + 1):
            if badge[y][x] == 0:
                badge[y][x] = 2

    # Pre-populate uniq_map with existing used static tiles (1..372) for free deduplication
    uniq_map: dict[bytes, int] = {}
    for t in sorted(used):
        if 1 <= t < 373:
            uniq_map[bytes(title_tiles[2 + t * 16 : 2 + (t + 1) * 16])] = t

    for ty in range(3):
        for tx in range(16):
            tb = bytearray(16)
            has_px = False
            for r in range(8):
                b0 = 0
                b1 = 0
                for c in range(4):
                    vL = badge[ty * 8 + r][tx * 8 + c]
                    vR = badge[ty * 8 + r][tx * 8 + 4 + c]
                    if vL or vR:
                        has_px = True
                    b1 |= (vL & 3) << (6 - c * 2)
                    b0 |= (vR & 3) << (6 - c * 2)
                tb[r * 2] = b0
                tb[r * 2 + 1] = b1
            if has_px:
                tid = alloc_title_tile(bytes(tb), uniq_map)
                struct.pack_into(
                    "<H", sp1_map, ((8 + ty) * 20 + (4 + tx)) * 2, 0x1000 | tid
                )

    # Import custom Tails portrait (rows 0..7, y=0..63) FIRST so we never waste tile slots on
    # ring SP1 pal 6 tiles that Tails covers.
    im = Image.open(portrait_path).convert("RGB")
    assert im.size == (160, 152), f"Expected 160x152 title PNG, got {im.size}"
    sky = (85, 170, 255)
    sp1_cmap = {
        sky: 0,
        (0, 0, 0): 1,
        (255, 255, 255): 2,
        (255, 136, 0): 3,
        (170, 68, 0): 0,  # transparent on SP1 so SP2 dark brown shows through
    }
    tails_sp1_grids: dict[tuple[int, int], list[list[int]]] = {}
    tails_sp2_cells: set[tuple[int, int]] = set()
    for ty in range(8):
        for tx in range(20):
            sp1_px = [[0] * 8 for _ in range(8)]
            sp2_px = [[0] * 8 for _ in range(8)]
            has_sp1 = False
            has_sp2 = False
            for r in range(8):
                for c in range(8):
                    px_x, px_y = tx * 8 + c, ty * 8 + r
                    if px_x < 32 and px_y < 10:
                        continue  # ignore top-left palette swatch
                    rgb = im.getpixel((px_x, px_y))
                    if rgb not in sp1_cmap:
                        raise ValueError(
                            f"Unmapped pixel in {portrait_path} at ({px_x}, {px_y}): {rgb}"
                        )
                    v1 = sp1_cmap[rgb]
                    if v1:
                        sp1_px[r][c] = v1
                        has_sp1 = True
                    if rgb == (170, 68, 0):
                        sp2_px[r][c] = 2  # SP2 pal 2 (0x0258) index 2 = (170, 85, 0)
                        has_sp2 = True
            if has_sp1:
                tid = alloc_title_tile(encode_2bpp_tile(lambda x, y, g=sp1_px: g[y][x]), uniq_map)
                struct.pack_into("<H", sp1_map, 4 + (ty * 20 + tx) * 2, (7 << 9) | tid)
                tails_sp1_grids[(tx, ty)] = sp1_px
            if has_sp2:
                tid = alloc_title_tile(encode_2bpp_tile(lambda x, y, g=sp2_px: g[y][x]), uniq_map)
                struct.pack_into("<H", sp2_map, 4 + (ty * 20 + tx) * 2, (2 << 9) | tid)
                tails_sp2_cells.add((tx, ty))

    # Copy the COMPLETE, UNBROKEN gold star ring from the intro tileset/maps (0x08A3FA / 0x08EC58 / 0x08E95C)
    # into rows 1..7 of SP2 (pal 3) and uncovered cells of SP1 (pal 6), skipping SP2 ring tiles that are
    # 100% occluded by Tails's SP1 pixels so we stay strictly inside tiles 1..372 (preserving 373..411 text!).
    for r in range(1, 8):
        for c in range(20):
            t_grid = tails_sp1_grids.get((c, r))
            if (c, r) not in tails_sp2_cells:
                e2 = struct.unpack_from("<H", data, 0x08E95C + 4 + (r * 20 + c) * 2)[0]
                if e2 & 0x1FF:
                    src_tb2 = data[0x08A3FA + 2 + (e2 & 0x1FF) * 16 : 0x08A3FA + 2 + ((e2 & 0x1FF) + 1) * 16]
                    visible = True
                    if t_grid is not None:
                        visible = False
                        for ry in range(8):
                            w = struct.unpack_from("<H", src_tb2, ry * 2)[0]
                            for rx in range(8):
                                if ((w >> (14 - rx * 2)) & 3) and t_grid[ry][rx] == 0:
                                    visible = True
                                    break
                            if visible:
                                break
                    if visible:
                        struct.pack_into("<H", sp2_map, 4 + (r * 20 + c) * 2, (e2 & 0xFE00) | alloc_title_tile(bytes(src_tb2), uniq_map))
            e1 = struct.unpack_from("<H", data, 0x08EC58 + 4 + (r * 20 + c) * 2)[0]
            if e1 & 0x1FF:
                src_tb = data[0x08A3FA + 2 + (e1 & 0x1FF) * 16 : 0x08A3FA + 2 + ((e1 & 0x1FF) + 1) * 16]
                if t_grid is None:
                    struct.pack_into("<H", sp1_map, 4 + (r * 20 + c) * 2, (e1 & 0xFE00) | alloc_title_tile(bytes(src_tb), uniq_map))
                elif (c, r) not in tails_sp2_cells and (struct.unpack_from("<H", sp2_map, 4 + (r * 20 + c) * 2)[0] & 0x1FF) == 0:
                    rim_px = [[0] * 8 for _ in range(8)]
                    has_rim = False
                    for ry in range(8):
                        w = struct.unpack_from("<H", src_tb, ry * 2)[0]
                        for rx in range(8):
                            v = (w >> (14 - rx * 2)) & 3
                            if v in (2, 3) and t_grid[ry][rx] == 0:
                                rim_px[ry][rx] = v
                                has_rim = True
                    if has_rim:
                        rtid = alloc_title_tile(encode_2bpp_tile(lambda x, y, g=rim_px: g[y][x]), uniq_map)
                        struct.pack_into("<H", sp2_map, 4 + (r * 20 + c) * 2, (2 << 9) | rtid)

    assert len(title_tiles) == 2 + orig_tcnt * 16
    data[0x1F3000 : 0x1F3000 + len(title_tiles)] = title_tiles
    data[0x1F5000 : 0x1F5000 + len(sp1_map)] = sp1_map
    data[0x1F5300 : 0x1F5300 + len(sp2_map)] = sp2_map

    # Patch SP1 pal 7 (0x025D -> [Black, White, Tails Orange]) & OAM pal 0x025B ([White, Tails Orange, Black])
    assert data[0x03D576:0x03D57C] == b"\x00\x00\x44\x0f\x00\x0b"
    struct.pack_into("<3H", data, 0x03D576, 0x0000, 0x0FFF, 0x008F)
    assert data[0x03D56A:0x03D570] == b"\xff\x0f\x80\x00\x00\x00"
    struct.pack_into("<3H", data, 0x03D56A, 0x0FFF, 0x008F, 0x0000)

    # Recolor Title badge dark blue (0x0930) in SP2 pal 4 (0x025E) and SP1 pal 8 (0x025F) to deep Tails orange (0x004C)
    assert data[0x03D57E:0x03D580] == b"\x30\x09"
    struct.pack_into("<H", data, 0x03D57E, 0x004C)
    assert data[0x03D584:0x03D586] == b"\x30\x09"
    struct.pack_into("<H", data, 0x03D584, 0x004C)

    # Build Tails blink overlay OAM metasprites (anchor X=80, Y=76; pal 0x025B: 1=White, 2=Orange, 3=Black)
    empty_moff = alloc.add_metasprite([])
    eye_mask = [
        (x, y)
        for y in range(19, 34)
        for x in range(64, 83)
        if im.getpixel((x, y)) in ((255, 255, 255), (0, 0, 0))
        and not (y >= 33 and x < 70)
        and not (y >= 32 and x < 65)
    ]
    half_px: dict[tuple[int, int], int] = {}
    closed_px: dict[tuple[int, int], int] = {}
    for x, y in eye_mask:
        dx, dy = x - 80, y - 76
        if y <= 25:
            half_px[(dx, dy)] = 2
        elif y == 26:
            half_px[(dx, dy)] = 3
        if y <= 29:
            closed_px[(dx, dy)] = 2
        elif y == 30:
            closed_px[(dx, dy)] = 3
        elif y == 31 and x in (65, 66, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80):
            closed_px[(dx, dy)] = 3
        else:
            closed_px[(dx, dy)] = 2

    blink_half_moff = alloc.add_metasprite(pack_layer_columns(half_px))
    blink_closed_moff = alloc.add_metasprite(pack_layer_columns(closed_px))

    # Disable Sonic skin OAM script (0x1E3B22) and static fade-in OAM pointers (0x1E3AE1, 0x1E3B09)
    for off in range(0x1E3B22, 0x1E3B5A, 8):
        assert data[off : off + 2] == b"\x04\x00"
        struct.pack_into("<H", data, off + 2, empty_moff)
    assert data[0x1E3AE0:0x1E3AE5] == b"\x43\xa6\x92\x20\x00"
    struct.pack_into("<I", data, 0x1E3AE1, 0x003F0000 + empty_moff)
    assert data[0x1E3B08:0x1E3B0D] == b"\x43\x5e\x93\x20\x00"
    struct.pack_into("<I", data, 0x1E3B09, 0x003F0000 + empty_moff)

    # Replace Sonic waving-glove OAM script (0x1E3B5E) with Tails blinking loop
    blink_frames = [
        (empty_moff, 0x30),
        (empty_moff, 0x78),
        (blink_half_moff, 0x03),
        (blink_closed_moff, 0x06),
        (blink_half_moff, 0x03),
        (empty_moff, 0x78),
        (empty_moff, 0x02),
    ]
    for i, (moff, delay) in enumerate(blink_frames):
        off = 0x1E3B5E + i * 8
        assert data[off : off + 2] == b"\x04\x00"
        struct.pack_into("<H", data, off + 2, moff)
        data[off + 7] = delay

    # Skip Sonic's intro pop-up & "SONIC THE HEDGEHOG" banner (0x1E7B21):
    # Right after the gold star ring finishes dropping and sparkling (0x1E7B19: call 237815h),
    # jump straight to 0x1E7CF9 (Title Screen proper with Tails inside the gold star ring).
    assert data[0x1E7B21:0x1E7B2D] == b"\x43\x5a\xd7\x28\x00\x32\x83\x00\x1d\x3f\xed\x23"
    data[0x1E7B21:0x1E7B2D] = b"\x1d\x8e\xe8\x23\x40\xf9\x7c\x3e\x00\xb6\x60\x0e"

    # Clear Sonic pop-up intro OAM scripts (0x1E7D9E, 0x1E7DCF, 0x1E7E18) as defense-in-depth
    for start, count in ((0x1E7D9E, 6), (0x1E7DCF, 9), (0x1E7E18, 7)):
        for i in range(count):
            off = start + i * 8
            assert data[off : off + 2] == b"\x04\x00"
            struct.pack_into("<H", data, off + 2, empty_moff)

    for off, expected, replacement in (
        (0x1E3890, b"\x43\x98\xbd\x28\x00", b"\x43\x00\x30\x3f\x00"),
        (0x1E38A4, b"\x44\xc8\xf5\x28\x00", b"\x44\x00\x50\x3f\x00"),
        (0x1E38B8, b"\x44\xcc\xf2\x28\x00", b"\x44\x00\x53\x3f\x00"),
        (0x1E7CF9, b"\x43\x98\xbd\x28\x00", b"\x43\x00\x30\x3f\x00"),
        (0x1E7D04, b"\x44\xc8\xf5\x28\x00", b"\x44\x00\x50\x3f\x00"),
        (0x1E7D18, b"\x44\xcc\xf2\x28\x00", b"\x44\x00\x53\x3f\x00"),
    ):
        assert data[off : off + len(expected)] == expected
        data[off : off + len(replacement)] = replacement


def patch_hud_tails_head(data: bytearray) -> None:
    """Replace HUD/Lives face tile (tid 2195) and 1UP Monitor face tile (tid 2211) with Tails."""
    rows = [
        "O...OO.O",
        "W.OOOOO.",
        "WOOOOOOO",
        "WOOOWOW.",
        ".OOW.O..",
        "WWOO.W..",
        ".WWWWWWW",
        "WOWWWWW.",
    ]
    cmap = {".": 0, "W": 1, "O": 2, "K": 3}
    head_tile = encode_2bpp_tile(lambda x, y: cmap[rows[y][x]])
    data[TILE_BASE + 2195 * 16 : TILE_BASE + 2195 * 16 + 16] = head_tile
    data[TILE_BASE + 2211 * 16 : TILE_BASE + 2211 * 16 + 16] = head_tile


def patch_tornado_sonic_cockpit(
    data: bytearray, sheet_path: Path, alloc: TileAndMetaAllocator
) -> None:
    """Replace Ending Cutscene OAM Tornado frames (0x1E76E7) and Sky Chase BG Tornado cockpit (0x0440A8)."""
    im = Image.open(sheet_path).convert("RGB")
    cmap = {
        (0, 0, 0): 1,
        (0, 128, 0): 1,
        (255, 255, 255): 2,
        (240, 240, 240): 2,
        (240, 192, 32): 2,
        (85, 85, 255): 3,
        (80, 80, 240): 3,
        (24, 60, 92): 3,
    }
    cell_w, cell_h, pad = 52, 56, 2
    frame_moffs: list[int] = []
    for idx in range(4):
        ox = pad + idx * (cell_w + pad) + 24
        oy = pad + 22
        x_start = pad + idx * (cell_w + pad)
        pixels: dict[tuple[int, int], int] = {}
        for py in range(pad, pad + cell_h):
            for px in range(x_start, x_start + cell_w):
                rgb = im.getpixel((px, py))
                if rgb in cmap:
                    pixels[(px - ox, py - oy)] = cmap[rgb]
        frame_moffs.append(alloc.add_metasprite(pack_layer_columns(pixels)))

    expected = b"\x01\x01\xd0\xc9\x01\x01\xf2\xc9\x01\x01\x14\xca\x01\x01\x36\xca"
    assert data[0x1E76E7:0x1E76F7] == expected
    for idx, moff in enumerate(frame_moffs):
        struct.pack_into("<H", data, 0x1E76E9 + idx * 4, moff)

    # Patch playable Sky Chase Tornado BG cockpit tiles directly at 0x0440A8 (tiles 0x191..0x193, 0x196..0x198).
    # Decode original 24x16 cockpit area, preserve plane rim (x<=4, y>=14) and windshield (x>=17, y>=12),
    # then composite Sonic's head from cell 0 (sx=9..30, sy=11..21) H-flipped facing right.
    tbase = 0x0440A8
    grid = [[0] * 24 for _ in range(16)]
    for r, idxs in ((0, (1, 2, 3)), (1, (6, 7, 8))):
        for c, tidx in enumerate(idxs):
            t = data[tbase + tidx * 16 : tbase + (tidx + 1) * 16]
            for y in range(8):
                b0, b1 = t[y * 2], t[y * 2 + 1]
                for x in range(4):
                    px, py = c * 8 + x, r * 8 + y
                    px2 = px + 4
                    if (px <= 4 and py >= 14) or (px >= 17 and py >= 12):
                        grid[py][px] = (b1 >> (6 - x * 2)) & 3
                    if (px2 <= 4 and py >= 14) or (px2 >= 17 and py >= 12):
                        grid[py][px2] = (b0 >> (6 - x * 2)) & 3

    for sy in range(11, 22):
        for sx in range(27, 49):
            c = cmap.get(im.getpixel((pad + sx, pad + sy)), 0)
            if c:
                dx = -3 + (48 - sx)  # H-flipped facing right, nose right behind windshield
                dy = 5 + (sy - 11)   # Flush with cockpit rim at y=16
                if 0 <= dx < 24 and 0 <= dy < 16:
                    grid[dy][dx] = c

    for r, idxs in ((0, (1, 2, 3)), (1, (6, 7, 8))):
        for c, tidx in enumerate(idxs):
            tb = encode_2bpp_tile(lambda x, y, r=r, c=c: grid[r * 8 + y][c * 8 + x])
            data[tbase + tidx * 16 : tbase + (tidx + 1) * 16] = tb
