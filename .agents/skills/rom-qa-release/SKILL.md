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

2. **Execute Emulator Verification**
   - If the project has a scripted emulator test runner (e.g., JSON frame/input scripts capturing PNGs), run it and visually inspect the captured screenshots.
   - Otherwise (or in addition), output a targeted save-state test checklist covering:
     - Core mechanic in neutral state
     - Facing left vs. right (`H-flip` / `V-flip` & sub-sprite alignment)
     - State transitions (springs, slopes, water, hurt/death/i-frames, bosses, act-clear/signpost)
     - Palette/HUD/title-screen visual sanity

3. **Prepare Release Packaging (BPS-Only)**
   - Verify no ROMs, scratch work, or ripped assets are staged in Git (`git status`).
   - Update version numbers, feature notes, and verified checksums (`CRC32`, `MD5`, `SHA-1`, BPS size & Patch CRC32) in:
     - `<project>/*README*.md`
     - Root `README.md`
   - Keep legacy `.ips` files untouched in older projects unless explicitly retiring them during a new release.
