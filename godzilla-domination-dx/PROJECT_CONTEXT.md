# Godzilla: Domination! DX — Project Context

> Single source of truth for reverse-engineered addresses, hardware rules, code caves, and build/test commands.

## 1. Target Platform & Toolchain
- **System**: Game Boy Advance (GBA)
- **CPU / ISA**: ARM7TDMI (32-bit ARM / 16-bit Thumb, little-endian)
- **Memory Map**: ROM mapped at `0x08000000` (Wait State 0), IWRAM `0x03000000..0x03007FFF`, EWRAM `0x02000000..0x0203FFFF`, Palette RAM `0x05000000` (BG) / `0x05000200` (OBJ), OBJ VRAM `0x06010000`
- **Display / Tile Format**: 8x8 4bpp (16-color) & 8bpp (256-color) chunky LE tiles
- **Palette Format**: 15-bit `0BGR` (`RGB555`) LE, index 0 = transparent
- **Assembler / Disassembler**: Python `keystone-engine` (Thumb/ARM) & `capstone`
- **Emulator QA**: Portable `mGBA 0.10.5` (`C:\Users\onlyu\.local\mgba\mGBA-0.10.5-win64\mGBA.exe`) & `mGBA-dev` (Lua `--script` CLI)
- **Build Command**: `python godzilla-domination-dx/build_patch.py --src "roms/Gojira - Kaijuu Dairantou Advance (Japan).gba" --usa "roms/Godzilla - Domination! (USA).gba" --out-rom "roms/Godzilla Domination DX.gba" --out-bps "godzilla-domination-dx/Godzilla Domination DX.bps"`

## 2. Clean Source ROMs
- **Base ROM (Target)**: `Gojira - Kaijuu Dairantou Advance (Japan).gba` (`AG4J`)
  - **Size**: `4,194,304` bytes (`0x400000`, expanded to `0x800000` / 8 MB)
  - **CRC32**: `3157A4FC`
  - **MD5**: `f05f356facb38a1c330fa3d80ff3bd28`
  - **SHA-1**: `985599e9f65d58d67170ca9ad3eb406c6ed25217`
- **Donor Asset ROM (USA)**: `Godzilla - Domination! (USA).gba` (`AG4E`)
  - **Size**: `4,194,304` bytes (`0x400000`)
  - **CRC32**: `EADE083F`
  - **MD5**: `fb0b9d0db44ec7de4a534c2849f8b756`
  - **SHA-1**: `dfcfc6d1ad2bc629429d9ebaae0e9452efa8d0d6`

## 3. Code & Data Caves (With Provenance)
| Range | Kind | Capacity | Provenance (How Verified Unused) | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `0x3D2D00..0x3FFFFF` | cave | `~180 KB` | Trailing `0x00` padding after final archive entry `0x3D2CB5` | Thumb ASM hooks & lookup tables |
| `0x400000..0x7FFFFF` | expansion | `4 MB` | Clean GBA 4 MB → 8 MB ROM expansion (`0x08400000..0x087FFFFF`) | English text table, USA Classic Godzilla/Mechagodzilla/Mothra sprite packs, USA palettes & localized UI graphics |

## 4. Key ROM Functions & Tables (`AG4J`)
- **Archive Table Base**: `ROM 0x111A18` (`CPU 0x08111A18`), `391` entries (USA: `ROM 0x111D38`, `383` entries).
- **`0x08002C3C`**: `ArchiveInit(r0 = archive_base)` — stores base in IWRAM `0x03001C34`.
- **`0x08002C48`**: `ArchiveGetPtr(r0 = entry_idx)` — returns `archive_base + archive_base[entry_idx]`.
- **`0x08002C5C`**: `ArchiveGetSize(r0 = entry_idx)`.
- **`0x08002C74`**: `LZSSDecomp` (ring buffer `0x030005D0`).
- **`0x08006A20`**: Game Init — initializes archive (`0x08111A18`) and sets default text table (`0x08033530` → `0x030016EC`).
- **`0x08019458`**: `LoadSpriteToVRAM(r0 = archive_idx)` — DMAs sprite tiles to `0x06010000+` and registers in `0x030043D0`/`0x030043F0`.
- **`0x080194F8`**: `SpawnSprite(...)` — spawns sprite actor; monster spawn dispatcher at `0x08004300..0x08004460`:
  - Godzilla: `JPN[32]` (`0x20`) vs `USA[27]` (`136,764 B`)
  - King Ghidorah: `JPN[33]` (`0x21`) == `USA[28]`
  - Rodan: `JPN[38]` (`0x26`) == `USA[33]`
  - Mechagodzilla / Kiryu: `JPN[39]` (`0x27`) vs `USA[34]` (`182,008 B`)
  - Mothra: `JPN[51]` (`0x33`) vs `USA[46]` (`70,492 B`)
  - Megalon: `JPN[71]` (`0x47`) == `USA[72]`
  - Mecha-King Ghidorah (Boss): `JPN[76]` (`0x4C`) == `USA[78]`
- **`0x0801AA0C`**: `LoadScene(r0 = scene_pack_idx)` — DMAs 1072-byte scene descriptor into `0x03003F00`, then DMAs 1024-byte BG+OBJ palette (`512 + 512 B`) into shadow palette RAM `0x03002B50` (`0x03002D50` = OBJ palettes).
  - `OBJ Pal 2` (`0x03002D90`, 32 B): **Godzilla** (USA green vs JPN slate-gray).
  - `OBJ Pal 3` (`0x03002DB0`, 32 B): **King Ghidorah / Mini Mecha-King Ghidorah** (gold vs metallic silver-steel + gold wings + cyber-red).
  - `OBJ Pal 4` (`0x03002DD0`, 32 B): **Mothra** (USA vs Tokyo S.O.S.).
  - `OBJ Pal 6` (`0x03002E10`, 32 B): **Rodan / Fire Rodan** (brown vs crimson-red + blazing orange-gold wings).
  - `OBJ Pal 7` (`0x03002E30`, 32 B): **Megalon / Eva Unit-01 Purple Megalon** (green/purple swap of ramps `1..5` ↔ `6..10`).
- **`0x0801B978`**: `DrawText(...)` — maps ASCII `< 0xA0` via `tile = ch - 0x20` directly into `JPN[1]` (identical to `USA[1]` font!); `0x40` (`@`) is a JPN toggle.
- **`0x0801BD44`**: `IndexLanguageStrings()` — scans active text table (`[0x030016EC]`, 32 B/line) for `#` (`0x23`) section markers and populates `0x030064A0[47]`, stopping at `~` (`0x7E`).
- **`0x08009498`**: Monster Select scene init (`LoadScene(9)`).
- **`0x080128C4`** (Monster Select): Per-monster `Select` toggle hook (`cave_select_toggle`) — toggles hovered monster's bit in `SKIN_MASK_ADDR` (`0x0203FFFE`: bit 0 = Godzilla, bit 1 = Mechagodzilla/Kiryu, bit 2 = Mothra, bit 3 = Mini Mecha-King Ghidorah, bit 4 = Fire Rodan, bit 5 = Eva Unit-01 Purple Megalon), updating OBJ Pal 2/3/4/6/7 independently and invalidating `[actor, #0x28] = 0xFFFF` across all 32 active actors (`0x03002F60`, stride `0x7C`).
- **v0.8/v0.9 Hybrid 12-Entity Custom Mode (`IDs 1..12`)**:
  - Custom Mode UI cycle max (`0x032F10, 0x032F4C, 0x032F88, 0x032FC4`) bumped `7 → 13` (`0..12`), active-slot Left/Right wrap (`0x013642`, `0x0139F2`) bumped `6 → 12`.
  - **`0x08013EB8`** (`cave_custom_pal`): Routes all 13 Custom Mode portrait IDs (`0..12`) through `CUSTOM_PAL_LUT` (`OBJ Pal 2..7` for `1..6`, `OBJ Pal 9..13` populated by `cave_load_scene_pal` ONLY on Custom Mode `*(u32*)0x03002B54 == 0x62D8001F` for `7..12`, `JPN[213]` expanded to 13f with canonical Mini MKG portrait at f8).
  - **`0x08013F6C`** (`cave_custom_name`): Maps `ID 1..6 → 0..5` and `ID 7..12 → 19..24` in 25-frame `JPN[240]` rendered in a condensed `3x7` arcade font (`GODZILLA03`, `K.GHIDORAH`, `RODAN`, `KIRYU`, `MOTHRA '03`, `MEGALON`, `GODZILLA99`, `M.GHIDORAH`, `FIRE RODAN`, `M-GODZILLA`, `MOTHRA '92`, `MEGALON-01`), preserving `0x013F74..0x013F7C` for its `0x08015D74` caller.
  - **`0x0801583C` + `0x08015852`** (`cave_vs_portrait`, clamp `7 → 14`) & **`0x080159AC`** (`cave_vs_frame` + roar wrap): Maps `ID 7..12 → frames 9..14` in single 15-frame packs (`JPN[243]` 2P Giant VS, `JPN[229]` 2P Nameplates, `JPN[231]` 3P/4P Portraits, `JPN[216]` 3P/4P Nameplates), leaving `0..8` untouched and recoloring Fire Rodan, Shadow MKG, and Eva-01 Megalon-01 in `JPN[335]`'s 256-color VS palette.
  - **`0x080042E8`** (`cave_battle_spawn`): Table-driven Battle Spawn dispatcher for `IDs 7..12` using virtual archive IDs `392/393/394` (remapped `USA[27/34/46]`) and **`395`** (canonical 69-frame Mini Mecha-King Ghidorah built losslessly from `JPN[33]` with metallic silver middle head/chest/wings & golden outer heads/legs/tails) + per-player Battle OBJ palette DMA (`0x0800445E`).
- **v0.9 Gameplay & HUD Polish Hooks**:
  - **`0x08013346`** (`cave_results_icon` + `RESULTS_ICON_LUT`): Maps all 12 fighters (`IDs 1..12`) to their own mini portrait icon & OBJ palette (`JPN[212]` expanded `42f → 48f`, using free `OBJ Pal 8, 9, 14, 15` on Battle Results `0x03002B54 == 0x211F109F` so `OBJ Pal 10..13` stay untouched for the `1P/2P/3P/4P` badges).
  - **`0x080044E0`** (`cave_init_hp` + `HP_LUT`, preserving live `r2 = slot*0x24`): Initializes starting HP per `monster_id` (`1..6` = vanilla `71`, `7..12` = subtle lore trade-offs `67/77/65/76/68/68`).
  - **`0x0801CAC0`** (`cave_walk_speed` + `SPEED_LUT`): Returns 16.16 fixed-point walk speed per `monster_id` (`1..6` = vanilla, `7..12` = subtle lore trade-offs matching HP).
  - **`0x0801C7A0`** (`cave_hud_name_r`) & **`0x0801C830`** (`cave_hud_name_l`): Dispatches 12 unique outlined Battle HUD names packed in-place inside `USA[12]`'s vanilla name slots `0x26..0x5C` (tile 0 at byte offset `494` / `0x1EE`, keeping exact `4,304 B` / `0x77` tile count; right-aligned strip uses cols `0..6` with `0` in off-screen col `7`).
  - **`JPN[216]` (3P/4P Pre-Battle VS Nameplates)**: 15-frame 8bpp pack rendered with all 12 outlined era/variant names (`GODZILLA '03`..`MEGALON-01`) using `JPN[335]` colors `17` (white), `22` (silver bevel), `31` (black outline).

### Master OBJ Palette Allocation Map (Verified Zero-Collision)
| OBJ Pal | Battle Mode | Monster Select | Custom Mode (`0x03002B54 == 0x62D8001F`) |
| :--- | :--- | :--- | :--- |
| `0..1` | HUD / FX / explosions | UI cursors / headers | UI cursors / headers |
| `2` | Godzilla '03 (or Story `Select` bit 0) | Godzilla | Godzilla '03 (`ID 1`) |
| `3` | King Ghidorah (or Story `Select` bit 3) | King Ghidorah | King Ghidorah (`ID 2`) |
| `4` | Mothra '03 (or Story `Select` bit 2) | Mothra | Mothra '03 (`ID 5`) & Random (`ID 0`) |
| `5` | Kiryu / Mechagodzilla | Kiryu / MG | Kiryu (`ID 4`) & Mechagodzilla (`ID 10`) |
| `6` | Rodan (or Story `Select` bit 4) | Rodan | Rodan (`ID 3`) |
| `7` | Megalon (or Story `Select` bit 5) | Megalon | Megalon (`ID 6`) |
| `8` | Stage props / FX | UI | UI |
| `9` | **Untouched** (buildings/vehicles) | **Untouched** (`?` / Speed/Power/Special) | Godzilla '99 (`ID 7`, USA Pal 2) |
| `10` | **Untouched** (buildings/power-ups) | **Untouched** | Mini Mecha-King Ghidorah (`ID 8`) |
| `11` | **Untouched** (buildings/power-ups) | **Untouched** | Fire Rodan (`ID 9`) |
| `12` | **Untouched** (buildings/power-ups) | **Untouched** | Mothra '92 (`ID 11`, USA Pal 4) |
| `13` | **Untouched** (buildings/power-ups) | **Untouched** | Megalon-01 (`ID 12`, Eva-01 Purple) |
| `14..15` | **Untouched** (P1..P4 battle slots DMA'd directly by `0x0800445E`) | **Untouched** | **Untouched** |
- **16-State Composite Multi-Monster Packs**: `JPN[212]` (small Monster Select icons), `JPN[213]` (Custom Mode 7f portraits: Kiryu/Mechagodzilla frame 4, Godzilla frame 1, Mothra frame 5), `JPN[229]` (9f Monster Select nameplates: `KING GHIDORAH™` ↔ official `MECHA-KING GHIDORAH™` frame 8), `JPN[230]` (7f portraits: MKG frame 6), `JPN[231]` (6f portraits), and `JPN[243]` (8f Giant VS depictions: MKG frame 6) are pre-composited across `SKIN_MASK` (`0..15`) in the 8 MB expansion and dispatched by `cave_archive_get_ptr`.
- **`0x0801AA8E`**: `LoadScene` palette hook (`cave_load_scene_pal`) — guarded by `*(u32*)(0x03002D90) == 0x739C2C40` so 8bpp 256-color screens (Title Screen, Giant VS Matchup / Rodan / `VS` logo) are never clobbered.
- **`JPN[220]` / `JPN[223]` / `JPN[241]`**: `JPN[220]` → `USA[93]` (`CUSTOM MODE:`), `JPN[223]` → `USA[57]` (`TOTAL SCORE`), and `JPN[241]` → `USA[207]` (`RAGE ATTACKS` `Lev 1 / Lev 2 / Lev 3`).
- **`0x0800473A`**: Overhead `1P`–`4P` player tag spawn check — hooked (`cave_check_ptag`) to suppress player tags when `0x0203FFFD == 1`.
- **`0x0800D18A`**: Story Mode stage progression / next-scene router — hooked (`cave_bonus_stage`) to route Stage 2 → `0x20` (`BONUS0` UFO Assault) and Stage 5 → `0x21` (`BONUS1` SDF Jet Assault) when `0x0203FFFC == 1`, tracked by `0x0203FFFA`.
- **`0x08012780`**: Story Mode stage-order array initializer — hooked (`cave_stage_order`) to write fixed USA order `[0, 1, 3, 2, 4, 5, 6]` when `0x0203FFFB == 1` instead of JPN randomized order.
- **`0x08014884`**: Options menu per-frame handler — hooked (`cave_options_dx`) so `Select` / `L` / `R` flips between Standard (`Timer`, `Difficulty`, `Ally DMG`) and DX Options (`1P TAG`, `BONUS`, `STAGE`) using 28-frame pill sprite pack `JPN[228]`.
- **`JPN[236]` (Title Logo)**: Replaced with `USA[136]` + prepended `32x16` 8bpp fiery **`DX`** OBJ at OAM index 0 (`x=50, y=-12`, tile `428`, palette from `USA[332]` copied into `JPN[338]`). `JPN[237]` (Title grid) is blanked; `JPN[238]` (`Licensed by Nintendo`) is redirected to `USA[197]`; `JPN[239]` (`Press Start`) is redirected to `USA[137]`.
- **`JPN[243]` (Giant Monster Depictions)**: 8-frame 8bpp matchup sprites swapped with 8-frame expanded `USA[117]` (frame 3 duplicated into slot 7) when `[0x0203FFFE] == 1`.
- **`JPN[32/39/51]` (Classic Monster Frame Remapping)**: `USA[27/34/46]` frames are reordered to match `AG4J`'s animation indices while preserving `AG4J`'s 24-byte hitbox/hurtbox headers (see `frame_mappings.md`).
- **`JPN[25]` (Battle HUD)**: Replaced with `USA[12]` (`4,304 B`) matching `USA[253]` BG layer 3.

## 5. Key RAM Addresses & Structs (`AG4J`)
- `0x03001C34` (u32): Active archive table base pointer (`0x08111A18`).
- `0x030016EC` (u32): Active language text table pointer (default `0x08033530`, redirected to expanded English table in `0x08400000+`).
- `0x030064A0` (u16[47]): Dynamically indexed `#` text section offsets.
- `0x03001A58` (u16[4]): Active `~KEYINPUT` button state (`Select` = `0x0004`).
- `0x03001A70`: Newly pressed button state.
- `0x03003F00` (1072 B): Active scene descriptor (512 B BG pal, 512 B OBJ pal, 48 B BG layer metadata).
- `0x03002B50` (1024 B): Shadow Palette RAM (`0x03002B50` BG, `0x03002D50` OBJ; `0x03002D90` = OBJ Pal 2, `0x03002DD0` = OBJ Pal 4).
- `0x0203FFFF` (u8): Stored language ID (`0..4`).
- `0x0203FFFE` (u8, **hack-allocated**): Per-monster 6-bit `SKIN_MASK` (`bit0`=Godzilla, `bit1`=Mechagodzilla/Kiryu, `bit2`=Mothra, `bit3`=Mini Mecha-King Ghidorah, `bit4`=Fire Rodan, `bit5`=Eva Unit-01 Purple Megalon; `0`=JPN, `1`=Alt).
- `0x0203FFFD` (u8, **hack-allocated**): `1P TAG` toggle (`0` = ON [JPN default], `1` = OFF [USA behavior]).
- `0x0203FFFC` (u8, **hack-allocated**): `BONUS` stages toggle (`0` = OFF [JPN default], `1` = ON [USA Bonus Stages]).
- `0x0203FFFB` (u8, **hack-allocated**): `STAGE` order toggle (`0` = JP Random, `1` = US Fixed).
- `0x0203FFFA` (u8, **hack-allocated**): Story Mode Bonus Stage completion bitmask (bit 0 = Stage 2 UFO Assault, bit 1 = Stage 5 SDF Jet Assault).
- `0x0203FFF9` (u8, **hack-allocated**): Active Options screen page (`0` = Standard, `1` = DX Options: `1P TAG` / `BONUS` / `STAGE`).

## 6. Confirmed Facts vs. Open Checks
- **Confirmed**: Zero hidden/unreleased playable monsters (no Gigan/Anguirus), zero hidden playable stages beyond the 2 restored USA Bonus Stages, 20 BGM tracks (`0x1119C8`), 127 SFX/roar entries, and zero unused Connie Matsu art/strings.
- **Confirmed**: Monster Select `Speed/Power/Special` bars (`0x08012F3C`) are a 6-frame cosmetic sprite; real movement speeds (`0x0801CAC0`) and starting HP (`0x080044E0`) are now differentiated across all 12 fighters.
- **Confirmed (mGBA QA)**: Top-of-EWRAM hack flags (`0x0203FFF9..0x0203FFFE`) are untouched by the game engine; all v0.9 features (12-entity Custom Mode, movie-accurate 69-frame Mini MKG ingested from `sprite_sheets_to_mod/mini_mkg_template_1x.png`, official Domination-font `JPN[229]` nameplates, Shadow MKG & Eva-01 Megalon-01 VS portraits, Battle Results 12-entity mini portrait icons on `OBJ Pal 8/9/14/15`, 12-entity Battle HUD names, immediate post-`FIGHT!` attacks, and zero palette leaks) verified visually in mGBA.

## 7. v1.0 Roadmap / Wishlist
- **Training Mode**: Hitboxes/hurtboxes overlay, frame data, and damage readouts.
- **Random Select**: Enhanced random fighter & random stage selection.
- **Nighttime Stage Variants**: Dusk/night alternate stage palettes.
- **Bug Fixes & Community Polish**: Address any edge cases reported during v0.9 playtesting.
