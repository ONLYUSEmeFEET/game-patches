"""Patch-agnostic graphics validation and visual round-trip preview helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

RGB = tuple[int, int, int]


def _require_pillow():
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise RuntimeError(
            "Pillow is required for patchkit.gfx: python -m pip install Pillow"
        ) from exc
    return Image, ImageDraw


def validate_palette_pixels(
    img,
    allowed_rgbs: Iterable[RGB],
    *,
    ignore_transparent: bool = True,
    max_errors: int = 10,
    label: str = "image",
) -> None:
    """Fail loudly if any opaque pixel in `img` falls outside `allowed_rgbs`."""
    allowed = set(allowed_rgbs)
    rgba = img.convert("RGBA")
    w, h = rgba.size
    px = rgba.load()

    bad: list[tuple[int, int, RGB]] = []
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if ignore_transparent and a == 0:
                continue
            rgb = (r, g, b)
            if rgb not in allowed:
                bad.append((x, y, rgb))
                if len(bad) >= max_errors:
                    break
        if len(bad) >= max_errors:
            break

    if bad:
        details = "\n".join(f"  ({x}, {y}): RGB{rgb}" for x, y, rgb in bad)
        raise ValueError(
            f"Unmapped palette pixel(s) in {label} "
            f"(showing up to {max_errors}):\n{details}"
        )


def make_checkerboard(
    width: int,
    height: int,
    *,
    cell: int = 4,
    color_a: RGB = (192, 192, 192),
    color_b: RGB = (144, 144, 144),
):
    """Create a checkerboard RGB image for visualizing sprite transparency."""
    Image, _ = _require_pillow()
    bg = Image.new("RGB", (width, height), color_a)
    px = bg.load()
    for y in range(height):
        for x in range(width):
            if ((x // cell) + (y // cell)) % 2 == 1:
                px[x, y] = color_b
    return bg


def build_preview_sheet(
    panels: Sequence[tuple[str, object]],
    out_path: str | Path,
    *,
    scale: int = 4,
    padding: int = 10,
    header_height: int = 18,
    checkerboard: bool = True,
) -> Path:
    """Render a labeled nearest-neighbor contact sheet (e.g., Before | After | H-Flip)."""
    Image, ImageDraw = _require_pillow()
    if not panels:
        raise ValueError("build_preview_sheet requires at least one (label, image) panel")

    scaled_panels: list[tuple[str, object]] = []
    for title, im in panels:
        rgba = im.convert("RGBA")
        sw, sh = rgba.width * scale, rgba.height * scale
        up = rgba.resize((sw, sh), resample=Image.NEAREST)
        if checkerboard:
            bg = make_checkerboard(sw, sh, cell=max(4, scale * 2)).convert("RGBA")
            up = Image.alpha_composite(bg, up)
        scaled_panels.append((title, up.convert("RGB")))

    total_w = padding + sum(im.width + padding for _, im in scaled_panels)
    max_h = max(im.height for _, im in scaled_panels)
    total_h = padding + header_height + max_h + padding

    canvas = Image.new("RGB", (total_w, total_h), (28, 28, 32))
    draw = ImageDraw.Draw(canvas)

    cur_x = padding
    for title, im in scaled_panels:
        draw.text((cur_x, padding), title, fill=(235, 235, 240))
        canvas.paste(im, (cur_x, padding + header_height))
        cur_x += im.width + padding

    dest = Path(out_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest)
    return dest


def save_palette_swatch(
    swatch_rgbs: Sequence[RGB],
    out_path: str | Path,
    *,
    block_size: int = 16,
) -> Path:
    """Save a crisp 1-row palette swatch PNG for eyedropper use in Paint.NET / Aseprite."""
    Image, _ = _require_pillow()
    if not swatch_rgbs:
        raise ValueError("swatch_rgbs must not be empty")
    im = Image.new("RGB", (len(swatch_rgbs) * block_size, block_size))
    for i, rgb in enumerate(swatch_rgbs):
        for y in range(block_size):
            for x in range(block_size):
                im.putpixel((i * block_size + x, y), rgb)
    dest = Path(out_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest)
    return dest
