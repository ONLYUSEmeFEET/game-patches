# Game Patches — Universal ROM-Hacking Rules

These rules apply to every ROM hack project in this repository, regardless of console, CPU, or game.

## 1. Read Ground Truth First
- Before proposing or writing any ROM edit, assembly routine, or graphics patch, read the active project's `PROJECT_CONTEXT.md` and `allowed_ranges.json` (if present).
- Never guess RAM addresses, ROM offsets, tile bitplane formats, or calling conventions—verify them from `PROJECT_CONTEXT.md`, existing build scripts, or disassembly first.
- Explicitly separate **confirmed facts** from **hypotheses** to test in an emulator.

## 2. Clean ROM & Patch Hygiene (BPS-Only)
- **Never modify a clean base ROM in place.** Always load a clean copy verified against its expected CRC32 and byte length via `tools/patchkit` (`load_clean_rom`).
- **Always assert original bytes before patching** (`assert_and_patch`) so edits fail loudly if run against the wrong ROM revision or conflicting offset.
- **BPS-only for new builds and releases.** Do not add `.ips` generation to `tools/patchkit` or new build scripts (leave legacy `.ips` files in untouched folders alone until those projects are rebuilt).
- **Never commit ROMs, ripped sprite sheets, or scratch/work directories.** Keep the root `.gitignore` whitelist intact.

## 3. Diff Gate, Cave Safety & Visual Verification
- Every modified byte in a built ROM must fall inside a range declared in the project's `allowed_ranges.json` and pass `patchkit.verify_diff()`.
- Before claiming a new code cave or expanding a hook, check `allowed_ranges.json` for collisions and verify remaining cave capacity.
- **No blind graphics edits:** Never draw sprites/logos procedurally in Python when a `1x` PNG template can be extracted/edited, validate pixels loudly (`patchkit.validate_palette_pixels`), and always decode patched ROM graphics back into a `4x` preview (`patchkit.build_preview_sheet`) and inspect it with `read_file` before reporting done.
- Never weaken or bypass `verify_diff`, byte assertions, or BPS round-trip checks to make a build pass.

## 4. Keep Documentation Synced
- Whenever you discover a new RAM address, struct offset, hook, or cave, update the project's `PROJECT_CONTEXT.md` and `allowed_ranges.json`.
- When cutting a release, update the version and verified checksums in both the project's README and the root `README.md`.

## 5. Specialist Skills (`.agents/skills/`)
Activate the matching workspace skill based on the task:
- `rom-recon` — Read-only disassembly, RAM/struct tracing, and cave discovery.
- `rom-asm-hooks` — CPU-accurate assembly hooks, physics/gameplay logic, and register/stack safety.
- `rom-graphics` — Tile encoding, palettes, metasprites, title screens, and HUD assets.
- `rom-qa-release` — Emulator testing, regression checklists, diff-gate verification, and BPS releases.
