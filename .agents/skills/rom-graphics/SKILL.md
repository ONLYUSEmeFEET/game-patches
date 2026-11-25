---
name: rom-graphics
description: >-
  Use this skill when converting sprite sheets, packing tiles, editing palettes, metasprites,
  title screens, HUD icons, or verifying display/VDP/LCD constraints for any ROM hack.
---

# Graphics, Tile & Palette Specialist (Zero-Blind-Edits Protocol)

Convert, pack, and visually verify art assets using the exact display hardware rules declared in the active project's `PROJECT_CONTEXT.md`. Never fly blind on graphics edits.

## Mandatory Protocol

1. **Verify Exact Hardware Format First**
   - Read `<project>/PROJECT_CONTEXT.md` before writing a single encoder byte.
   - Confirm:
     - **Tile bit layout** (e.g., NGPC chunky 2bpp `uint16` LE/row vs. GB/NES planar 2bpp vs. Genesis 4bpp vs. Game.com 2bpp framebuffer). Never assume planar if the hardware is chunky.
     - **Palette encoding** (bit depth, channel order, endianness, and transparent index—usually `0` on sprites).
     - **Layering / metasprite format** (single-layer vs. Base + Overlay multi-palette sprites, relative `dx/dy` signed offsets, tile deduplication IDs).
     - **Hardware limits** (max total sprites, per-scanline sprite cap, VBlank tile-streaming budget).

2. **Extract → Edit 1x PNG → Import (No Procedural Pixel Art in Code)**
   - **Never draw sprites, HUD icons, or title logos procedurally in Python** (no `rect()` letter rasterizers or ASCII pixel arrays) when a `1x` PNG template can be extracted and edited.
   - For new or modified ROM art:
     1. **Extract** the existing ROM tiles/tilemap + hardware palette into a `1x` editable PNG and a locked palette swatch (`patchkit.save_palette_swatch`).
     2. Let the user edit the `1x` PNG in Paint.NET / Aseprite (or supply a sprite sheet).
     3. **Import** deterministically with `patchkit.validate_palette_pixels()` so any unmapped RGB pixel fails loudly with exact `(x, y, rgb)` coordinates instead of silently corrupting colors.

3. **Title Screen & Multi-Plane Background Safety**
   - Before touching any title screen or background:
     1. Dump the **full composited screen** (all scroll planes + palettes) and inspect raw tilemap headers (e.g., 4-byte `w, h, cnt` prefixes) before indexing `(row, col)` offsets.
     2. Map **which tile IDs are shared** and **which upper VRAM tile IDs are reserved** for dynamically drawn text, fonts, or animated water/HUD tiles (never treat unreferenced upper tiles in a static map as free without verifying the static tile count boundary).
     3. Identify **every phase and loader** of that screen (intro/pop-up animations, settled idle loop, and menu variants such as `PRESS START` vs. `START/CONTINUE`) so earlier phases never flash unpatched assets.
     4. When tight on static tile slots, deduplicate repeated/cleared tiles and cull `SP2` background tiles that are 100% occluded by opaque `SP1` foreground pixels before expanding tile counts.

4. **Mandatory Decode-Back Visual Inspection (No Blind Commits)**
   - After encoding tiles/tilemaps/metasprites into the patched ROM, **decode those exact patched ROM bytes back** using the target hardware's palette and layer rules.
   - Render a `4x` nearest-neighbor contact sheet via `patchkit.build_preview_sheet()` into a local `work/` preview PNG:
     - **Sprites:** `Base Layer | Overlay Layer | Composited Right | Composited H-Flip Left`
     - **Screens / Title / HUD:** `Before (Clean ROM) | After (Patched ROM)`
   - **Visually inspect the generated preview PNG using `read_file`** before declaring the task complete. If there are stray pixels, clipped edges, palette bleeds, or flip misalignment, fix them before handing off to the user.

5. **Enforce Budgets & Diff Gate**
   - Verify tile count and byte footprint fit inside the declared ROM/VRAM cave in `allowed_ranges.json`.
   - Run the project build and confirm `patchkit.verify_diff()` reports `0` unauthorized bytes.
