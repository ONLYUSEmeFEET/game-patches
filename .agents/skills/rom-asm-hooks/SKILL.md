---
name: rom-asm-hooks
description: >-
  Use this skill when writing or modifying retro console assembly routines, ROM hooks,
  physics/state-machine patches, or relocating code into free-space caves across any CPU/ISA.
---

# ASM & Hook Engineer (Patch-Agnostic)

Write safe, maintainable assembly routines and ROM hooks tailored to the CPU/ISA declared in the active project's `PROJECT_CONTEXT.md`.

## Procedure

1. **Read Target ISA & Memory Map**
   - Open `<project>/PROJECT_CONTEXT.md` and `<project>/allowed_ranges.json`.
   - Confirm: CPU/ISA, assembler syntax & command, ROM-to-CPU address mapping, existing hooks, and available cave capacity.

2. **Use Named Symbols, Not Magic Hex**
   - Prefer placing assembly in `<project>/src/*.asm` with shared constants in `<project>/src/symbols.inc` rather than embedding raw hex blobs in Python.

3. **Enforce ISA & Hook Safety**
   - **Displaced instructions:** Verify exact byte length of the overwritten instruction sequence. Relocate displaced instructions cleanly into the hook body and pad leftover hook bytes with ISA-correct `NOP`s.
   - **Register & stack discipline:** Explicitly list register inputs, outputs, and clobbered registers; preserve all non-return registers (`PUSH`/`POP`) and verify balanced stack exits on every branch.
   - **Branch & bank bounds:** Check relative jump/branch reach, endianness, and bank boundaries.
   - **Guarded injection:** Every hook site in Python must use `patchkit.assert_and_patch()` against the exact unmodified ROM bytes.

4. **Check State-Machine Edge Cases**
   - Whenever modifying player movement, physics, abilities, or object state transitions, explicitly guard against collisions with:
     - Grounded vs. airborne vs. rolling/special states
     - Springs, slopes, moving platforms, and water/underwater physics
     - Hurt/invulnerability, death, cutscenes, warps, bosses, and end-of-act transitions
   - **Custom RAM & Control-Lock Discipline:**
     - Never repurpose unverified player-struct offsets for custom timers/flags (engine transitions may silently clear them). Allocate custom state in a **verified-free WRAM gap** documented in `PROJECT_CONTEXT.md`, and use explicit latch flags cleared only when leaving the target state.
     - Respect engine control-lock timers (e.g., `P_CTRL_LOCK`) before reading ability inputs or firing ability SFX.

5. **Verify Build & Diff Gate**
   - Assemble and run the project's build script.
   - Confirm `patchkit.verify_diff()` passes with `0` unauthorized bytes and check cave utilization.
   - Update `PROJECT_CONTEXT.md` and `allowed_ranges.json` for any new hook or cave.
