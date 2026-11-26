# Tails Pocket Adventure — Project Context

> Single source of truth for reverse-engineered addresses, NGPC hardware rules, hooks, caves, and build/test setup.

## 1. Target Platform & Toolchain
- **System**: Neo Geo Pocket Color (SNK)
- **CPU / ISA**: Toshiba TLCS-900/H (`96c141`, little-endian, `maxmode on`)
- **ROM-to-CPU Mapping**: Cart ROM `0x000000..0x1FFFFF` maps to CPU `0x200000..0x3FFFFF` (`cpu_addr = rom_offset + 0x200000`).
- **Display Hardware**: K2GE
  - **Tile Format**: 8x8 **chunky/packed 2bpp** (16 bytes/tile = 8 rows of little-endian `uint16`, 2 contiguous bits per pixel; **NOT** bitplane/planar).
  - **Palette Format**: 4 entries per sub-palette, 12-bit RGB (`0x0BGR`, 4 bits/channel, little-endian `uint16`). **Index `0` is always transparent on sprites.**
  - **Character Layering**: Characters use **2 stacked layers** (Base + Overlay) with separate 4-color palettes to exceed 3 colors per sprite. Place white sclera (`1`) or black shoe base (`3`) behind Overlay pixels to prevent background bleed-through.
- **Assembler**: Macro Assembler AS (`asw.exe` + `p2bin.exe`), configurable via `NGP_ASW` / `NGP_P2BIN` env vars or CLI flags (default: `s:\Misc Gaming\NGPDev\aswcurr\bin\`).
- **Build Command**:
  ```powershell
  python tails-pocket-adventure/build_patch.py
  ```

## 2. Clean Source ROM
- **Filename**: `Sonic The Hedgehog - Pocket Adventure (World).ngc`
- **Size**: `2,097,152` bytes (`0x200000`)
- **CRC32**: `356F0849`
- **MD5**: `B8A899AE2B0F1DFA0DB5417DE745A51E`
- **SHA-1**: `3FE15D4374C4CA073AA0393FCFCAD0055BD345AB`

## 3. Code & Data Caves (With Provenance)
| ROM Offset | CPU Address | Capacity | Provenance (How Verified Unused) | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `0x1F3000..0x1F4FFF` | `0x3F3000..0x3F4FFF` | 8,192 B | Upper bank `0xFF` padding region (`0x1F3000+`) | Custom Title Screen tileset ("TAILS") |
| `0x1F5000..0x1F52FF` | `0x3F5000..0x3F52FF` | 768 B | Upper bank `0xFF` padding region | Custom Title Screen Scroll Plane 1 map |
| `0x1F5300..0x1F55FF` | `0x3F5300..0x3F55FF` | 768 B | Upper bank `0xFF` padding region | Custom Title Screen Scroll Plane 2 map |
| `0x1FAC00..0x1FAFFF` | `0x3FAC00..0x3FAFFF` | 1,024 B | End-of-ROM `0xFF` padding region (`0x1FAC00..0x1FEFFF`) | Sequentially-packed TLCS-900/H routines + `fly_script` (`src/main.asm`; hook targets auto-resolved via `patchkit.assemble_asw`) |
| `0x1FB000..0x1FCFFF` | `0x3FB000..0x3FCFFF` | 8,192 B | End-of-ROM `0xFF` padding region | Custom 8x8 2bpp tiles (streamed via bit 15 tile ID flag `0x8000+`) |
| `0x1FD000..0x1FDFFF` | `0x3FD000..0x3FDFFF` | 4,096 B | End-of-ROM `0xFF` padding region | Custom OAM metasprite table (addressed via offsets `>= 0xD000`) |
| `0x1FE000..0x1FEFFF` | `0x3FE000..0x3FEFFF` | 4,096 B | End-of-ROM `0xFF` padding region | Relocated & extended Character Frame Table (145 entries: `0x00..0x90`, custom flight frames `0x85..0x90`) |

## 4. Installed Hooks & Key ROM Offsets
- `0x000024..0x00002F`: NGPC Cart Header Title (`TAILS POCKET`)
- `0x00CB34`: Base ROM tile bank (`TILE_BASE`). Patched tiles: HUD head (`tid 2195`), 1UP box (`tid 2211`), Goalpost (`tid 2434..2464`).
- `0x03AEBF`: Single Player character select init (`0x04` = Tails).
- `0x03B203..0x03B209`: **Hook 5** — Title Screen Option button → Debug / Level Select shortcut (`call 0x3FAE40`).
- `0x03BFFC..0x03C005`: **Hook 1** — VBlank Dynamic Tile Streamer (`call 0x3FAD00`; bit 15 routes to `0x3FB000`).
- `0x03C081..0x03C086`: **Hook 2** — Shadow OAM Metasprite Reader (`call 0x3FAD20`; offsets `>= 0xD000` route to `0x3F0000`).
- `0x03C748`: Palette table base (6 bytes per entry; entries `0x024A` and `0x0273` patched for Tornado swap).
- `0x19AAFD..0x19AB08`: **Hook 3** — Player 1 Airborne Loop (`call 0x3FAC00` -> `flight_hook_body`).
- `0x19C7EC..0x19C7EF`: **Hook 4** — Extra Tails draw call (`call 0x3FAD60`; hides separate tail overlay during flight).
- `0x19DC21..0x19DC2A`: HUD / 1UP Monitor palette branch fix for Single Player Tails.
- `0x1CA5DD..0x1CA5E4`, `0x1CA6AC..0x1CA6B3`: **Hook 7a/7b** — Special Stage Intro/Win Pose Tails Palette (`call 0x3FAE80` / `ss_tails_pal_hook`).
- `0x1CAB65..0x1CAB96`: Special Stage standing/pose animation script pointers (4 Tails frames streamed via `0xD000+`).
- `0x1CE458..0x1CE467`: **Hook 6** — Goalpost Signpost Palette (`call 0x3FAE60`).
- `0x1CFAD0..0x1CFADF`: Title Card silhouette animation script pointers (3 Tails silhouette frames streamed via `0xD000+`).
- `0x1D35F4`: Original 133-entry Character Frame Table (`0x00..0x84`; `0x84` is Tails looking up). Pointer/count patched at `0x1D3A31..0x1D3A3B`.
- `0x1E727D..0x1E728C`: Ending Cutscene Tails Palette hook (`call 0x3FAD40`).
- `0x1EAD8B`: SFX `0x00A2` (Tails flying helicopter SFX) volume (`0x0F` -> `0x08`).

## 5. Key RAM Addresses & Player Struct (`xiz`)
- `0x004D41`: Controller newly-pressed / input bitmask (`0x30` = A/B jump buttons, bit `6` = Option).
- `0x00506E`: Camera Y coordinate (screen top reference: `screen_Y_from_top = (00506Eh) + 0097h - (xiz+16h)`).
- `0x0067B1`: Active character ID (`0x04` = Tails).
- `0x006980`: Custom flight SFX cadence countdown timer (1 byte, in verified-free WRAM gap `0x697E..0x69BE`).
- `0x006982`: Custom 16-bit flight fatigue countdown timer (2 bytes, initialized to `0x012C` = 300 frames / 5.0s).
- `0x006984`: Custom flight fatigue lock flag (`0x01` once stamina expires; cleared only by `hide_tails_hook` when `(xiz+00h) != 0xAAF7`, i.e., upon landing/spring/hurt/stage reset).
- `xiz + 0x16`: Player Y position (word).
- `xiz + 0x1C`: Player Y velocity (signed word; positive = rising, `0xFD00` = active fall cap, `0xFC00` = tired fall cap).
- `xiz + 0x20`: Active animation script bank byte (`0x3F` = custom Tails flying / tired scripts in `0x3FAC00..0x3FAFFF`).
- `xiz + 0x40`: Engine control-lock word (guarded before reading jump input in `flight_hook`).
- `xiz + 0x49`: Player sub-state / damage flag (`0x00` = normal / tired vulnerable, `0x02` = active flight attack hitbox, `>= 0x04` = hurt `04` / dead `05` / Giant Ring & Goal warp).

## 6. Key Engine Routines (CPU Addresses)
- `0x237815`: Title → Debug/Level Select transition helper.
- `0x23E3B3`: Load palette (`wa` = palette ID, `c` = slot; Tails base = `0x01B9`, overlay = `0x01BA`).
- `0x23E4DA`: Start animation script (`xix` = script pointer; preserves `xix`/`xiy` around call).
- `0x23E88E`: Title screen audio/state cleanup helper.
- `0x39D296`: Underwater / gravity check (carry set = underwater `0x0020`, clear = normal `0x0080`).
- `0x39D4E4`: Draw extra separate tail overlay sprite.
- `0x3F1883`: Play SFX (`wa` = SFX ID; `0x00A2` = helicopter tail).

## 7. Hardware Budgets & Display Limits (K2GE)
- **Hardware Sprite Cap**: 64 sprites total (8x8 tiles, chainable via relative offsets); keep Base + Overlay metasprite tile count tight during flight to avoid per-scanline sprite dropout during boss fights / ring bursts.
- **VBlank Tile Streaming**: `tile_stream_hook` runs during VBlank; keep custom flight frame tile counts comparable to stock Sonic frames so dynamic VRAM streaming stays within VBlank budget.
- **Shared Palettes**: Tails uses Sprite Palettes `0x01B9` (Base) and `0x01BA` (Overlay). Check HUD, 1UP monitor, signpost, and Tornado ending scenes whenever altering palette slots.

## 8. Known Quirks & Guardrails
- Always guard flight logic with `cp (xiz+49h), 04h; jp uge, normal_grav` so flying never overrides hurt, death, or Giant Ring / Goal warp states.
- Top ceiling clamp during flight uses visible camera top (`(00506Eh) + 0087h`), which works in both normal stages and camera-locked boss arenas.
- Preserve frame `0x84` in the Character Frame Table (Tails looking up); custom flight frames start at `0x85..0x90`.
- **Two Separate Tornado Sprites**: `0x1E76E7` (`0x00C9D0..0x00CA36`) is the **Ending Cutscene OAM Tornado only**. Playable **Sky Chase (`5-1 SKY CHASE`)** draws the Tornado on **Scroll Plane 2** via object `0x1DDCF5` (`0x1DDCD5`), loading 44 uncompressed 2bpp tiles from `0x0440A6` (2-byte count `0x002C`, tile data at `0x0440A8` -> VDP tile `0x190`) and `8x6` tilemap `0x051AB2`. The 6 cockpit pilot tiles are `0x191..0x193` (`0x0440B8..0x0440E7`) and `0x196..0x198` (`0x044108..0x044137`), using BG palette `0x0207` (`0x03D372`).
- **Title Screen Portrait & Animations**: `0x08F5C8` (SP1) and `0x08F2CC` (SP2) each begin with a 4-byte header (`w=20, h=19, cnt`), followed by `20x19` little-endian tilemap entries (`764 B` total, relocated to `0x1F5000` & `0x1F5300`). Rows `1..7` pull the unbroken gold star ring from the intro tileset/maps (`0x08A3FA` / `0x08EC58` / `0x08E95C`) behind Tails's portrait on SP1 pal 7 (`0x025D` at `0x03D576`, `[Black, White, Tails Orange]`) with dark-brown mouth shading and preserved ring-rim dithering on SP2 pal 2 (`0x0258`). Intro hook at `0x1E7B21..0x1E7B2C` skips Sonic's pop-up & `"SONIC THE HEDGEHOG"` banner right after the ring-drop sparkles (`0x1E7B19`), jumping directly to `0x1E7CF9`. Title OAM script `0x1E3B5E` (`pal 0x025B` at `0x03D56A`) drives Tails's blinking overlay at anchor `(80, 76)`, while `0x1E3B22`, `0x1E3AE1`/`0x1E3B09`, and `0x1E7D9E..0x1E7E4F` point to an empty 0-tile metasprite.

## 9. Automated Emulator QA
- **QA Harness Contract**: Ready for `python -m patchkit.qa --suite tails-pocket-adventure/qa_suite.json --rom ...` once a headless/scripted NGPC emulator command is configured.
- **Core Regression Checks**: Flight entry (grounded/run-jump/quick-tap), facing left vs. right H-flip alignment, ceiling clamp in boss arenas, underwater physics, hurt/death/Giant Ring warp, HUD/1UP icon, goalpost signpost, and Title Screen Option shortcut.
