# Godzilla: Domination! DX — Classic (USA) Frame Remapping Log

> Diagnostic reference for tweaking or troubleshooting any individual monster animation frame in Classic (USA) mode.

## How Frame Remapping & Hitbox Preservation Work
- `AG4J` (Japan) and `AG4E` (USA) have **identical frame counts** for all three changed monsters:
  - **Godzilla**: `65` frames (`JPN[32]` ↔ `USA[27]`)
  - **Mechagodzilla / Kiryu**: `86` frames (`JPN[39]` ↔ `USA[34]`)
  - **Mothra**: `42` frames (`JPN[51]` ↔ `USA[46]`)
- However, WayForward **re-ordered the contiguous animation blocks** when re-exporting these three sprite packs for `AG4J`.
- In `build_patch.py`, `remap_sprite_pack_frames()` rebuilds each Classic (USA) sprite pack in `AG4J`'s exact frame index order while **preserving `AG4J`'s 24-byte per-frame header (`oam_off + 0..23`)**, which holds the frame's hitbox / hurtbox / bounding-box coordinates. As a result, Classic (USA) mode has **100% identical hitboxes and hurtboxes** to Tokyo S.O.S. (JPN) mode.
- **All three mappings below are complete 1-to-1 bijections** (every single USA frame is used exactly once; no frames were dropped or duplicated). If any specific move looks slightly off during playtesting, look up the `AG4J` frame range below and adjust the corresponding entry in `build_patch.py`.

---

## 1. Godzilla (`JPN[32]` ← `USA[27]`, 65 Frames)
Verified `65/65` frames with silhouette IoU `0.88–1.00`:

| `AG4J` Frame Range | `AG4E` (USA) Frame Range | Count | Notes |
| :---: | :---: | :---: | :--- |
| `0..1` | `63..64` | 2 | Exact match (`IoU = 1.000`) |
| `2..7` | `25..30` | 6 | Idle / Walk (`IoU = 1.000`) |
| `8..32` | `0..24` | 25 | Roar / Bite / Tail / Attacks (`IoU = 0.88–1.00`) |
| `33..45` | `31..43` | 13 | Attacks / Hurt (`IoU = 0.996–1.000`) |
| `46..48` | `60..62` | 3 | Exact match (`IoU = 0.996–1.000`) |
| `49..64` | `44..59` | 16 | Jump / Grab / Knockdown (`IoU = 0.993–1.000`) |

---

## 2. Mechagodzilla / Kiryu (`JPN[39]` ← `USA[34]`, 86 Frames)
Verified `85/86` frames with silhouette IoU `>= 0.70` + visual contact-sheet confirmation on blocks `12..21` and `30..31`:

| `AG4J` Frame Range | `AG4E` (USA) Frame Range | Count | Notes |
| :---: | :---: | :---: | :--- |
| `0..2` | `0..2` | 3 | Shield Block |
| `3` | `50` | 1 | Single transition pose |
| `4..11` | `3..10` | 8 | Walk cycle |
| `12..14` | `51..53` | 3 | Punch / Arm attack (visually verified) |
| `15..21` | `69..75` | 7 | Chest Beam / Mega-Buster / Absolute Zero charge & cooldown (visually verified) |
| `22..29` | `11..18` | 8 | Attacks |
| `30..31` | `68, 67` | 2 | Shoulder-cannon / chest flash (order `68, 67` visually verified) |
| `32..39` | `19..26` | 8 | Attacks (`JPN[37] -> USA[24]` had lower IoU `0.566` due to Kiryu vs Heisei silhouette difference inside contiguous block `19..26` — **watch this frame during playtesting**) |
| `40..41` | `54..55` | 2 | 2-frame pose |
| `42..45` | `46..49` | 4 | 4-frame pose |
| `46..50` | `76..80` | 5 | 5-frame pose |
| `51..53` | `56..58` | 3 | 3-frame pose (`IoU = 0.956–0.969`) |
| `54..55` | `33..34` | 2 | 2-frame pose |
| `56..60` | `81..85` | 5 | 5-frame pose |
| `61..68` | `59..66` | 8 | 8-frame pose |
| `69..79` | `35..45` | 11 | 11-frame pose |
| `80..85` | `27..32` | 6 | 6-frame pose |

---

## 3. Mothra (`JPN[51]` ← `USA[46]`, 42 Frames)
Verified `38/42` frames with silhouette IoU `>= 0.70` + visual contact-sheet confirmation on `JPN[0..6]`:

| `AG4J` Frame Range | `AG4E` (USA) Frame Range | Count | Notes |
| :---: | :---: | :---: | :--- |
| `0..6` | `28, 29, 30, 31, 32, 40, 41` | 7 | Flight / Dive / Wing poses (all 7 visually verified pose-for-pose) |
| `7..8` | `6..7` | 2 | Front-facing hover (`IoU = 0.952–1.000`) |
| `9..11` | `0..2` | 3 | Wing flap (`IoU = 0.976–0.995`) |
| `12..14` | `3..5` | 3 | Wing flap / Attack (`IoU = 0.989–0.995`) |
| `15..24` | `8..17` | 10 | Attack / Hurt animations (`IoU = 0.71–0.93`) |
| `25..29` | `18..22` | 5 | Dive / Special (`JPN[25] -> USA[18]` in contiguous block `18..22` — **watch `JPN[25..26]` during playtesting**) |
| `30..31` | `33..34` | 2 | 2-frame pose |
| `32..33` | `23..24` | 2 | 2-frame pose |
| `34..36` | `37..39` | 3 | 3-frame pose |
| `37..39` | `25..27` | 3 | 3-frame pose |
| `40..41` | `35..36` | 2 | 2-frame pose |

---

## 4. Giant Monster Depictions (`JPN[243]` ← `USA[117]`, 8 Frames)
- `JPN[243]` has 8 frames (`0=Godzilla, 1=Ghidorah, 2=Rodan, 3=Kiryu, 4=Mothra, 5=Megalon, 6=MKG, 7=Kiryu duplicate`), whereas `USA[117]` has 7 frames (`0..6`).
- `build_classic_giant_monsters_8f()` expands `USA[117]` to 8 frames by duplicating Classic Mechagodzilla frame `3` into slot `7`. Both `JPN[335]`/`USA[326]` and `JPN[368]`/`USA[359]` share identical 256-color OBJ palettes.
