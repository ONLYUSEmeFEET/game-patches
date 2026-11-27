---
name: rom-qa-release
description: >-
  Use this skill when running emulator tests, inspecting captured frames, building regression
  checklists, verifying BPS patches, or preparing a release and updating README checksums.
---

# Emulator QA & BPS Release Manager (Patch-Agnostic)

Verify patched ROM behavior, enforce automated build/diff gates, and cut clean, reproducible BPS releases.

## Procedure

1. **Run Automated Build & Integrity Gates**
   - Run the project build script from an unmodified clean source ROM verified by `patchkit.load_clean_rom()`.
   - Confirm:
     - `patchkit.verify_diff()` reports `0` unauthorized bytes and healthy cave headroom.
     - `patchkit.write_bps()` passes full BPS1 round-trip verification (source CRC32, target CRC32, patch CRC32, and byte-for-byte reconstructed ROM match).
   - Never weaken assertions, diff ranges, or tests just to make a run pass.

1b. **Goldfish Diff Review (required for releases)**
   - After the gates pass, run the `rom-egm-review` Phase 4 diff review (fresh `ground_truth` + `hook_safety` subagents) over everything changed since the last release commit, against the approved spec(s) in `<project>/specs/`.
   - Resolve every Blocker/Major (Fix, or Reject with evidence) and log the results in the spec's Review Log before you package.

2. **Execute Emulator Verification**
   - **Scripted RAM checks first:** `python -m tools.emu.ramcheck --script <project>/qa/ramchecks/<x>.json --rom <built>`
     for every script in the project (exit 0 = PASS). These run headless in a libretro core in under a second, with no window. See `tools/emu/README.md`.
   - **Never rely solely on offline tile decode-back for user-reported visual bugs or multi-phase screens.** Boot the built ROM in a headless emulator capture and inspect live frames with `read_file` across both **transition/intro frames** and **settled frames** (after copyright/menu text appears).
   - **Sync Multi-Screen Captures on Pixel/Screen State:** When driving headless libretro cores (`S:\Retroarch\cores\<core>_libretro.dll`) across menus or cutscenes to capture release screenshots, gate button taps on pixel/screen-state predicates (logo settled, menu cursor highlighted, portrait visible) instead of blind fixed frame counts, and inspect every captured PNG via `read_file` before committing.
   - **Windows / PowerShell Headless RetroArch Recipe:**
     ```powershell
     $rom = "`"C:\path\to\patched.ngc`""  # Always double-quote paths with spaces inside ArgumentList
     $p = Start-Process "S:\Retroarch\retroarch.exe" -ArgumentList @(
       "-L", "S:\Retroarch\cores\<core>_libretro.dll", $rom,
       "--max-frames=700", "--max-frames-ss", "--max-frames-ss-path=$outPng"
     ) -PassThru
     $p.WaitForExit(25000) | Out-Null
     ```
   - When automated frame captures are unavailable or in addition to them, output a targeted save-state test checklist covering:
     - Core mechanic in neutral state
     - Facing left vs. right (`H-flip` / `V-flip` & sub-sprite alignment)
     - State transitions (springs, slopes, water, hurt/death/i-frames, bosses, act-clear/signpost)
     - Palette/HUD/title-screen visual sanity

3. **Prepare Release Packaging (BPS-Only)**
   - **Archive previous patches cleanly:** Move superseded `.bps` releases into `<project>/archived/` so only the latest `.bps` sits in the project root. If live test builds overwrote the previous `.bps` in the working tree, restore the authentic previous patch via `git checkout HEAD -- <old.bps>` before moving it to `archived/`.
   - Verify no ROMs, scratch work, or ripped assets are staged in Git (`git status`).
   - Update version numbers, feature notes, and verified checksums (`CRC32`, `MD5`, `SHA-1`, BPS size & Patch CRC32) in:
     - `<project>/*README*.md`
     - Root `README.md`
   - Keep official release links (e.g., ROMhacking.net) and `**/screenshots/*.png` galleries synced in `README.md` without weakening `.gitignore` blocks on ROMs or `sprite_sheets_to_mod/`.
   - Keep legacy `.ips` files untouched in older projects unless explicitly retiring them during a new release.
