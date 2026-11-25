---
name: rom-recon
description: >-
  Use this skill when reverse-engineering a ROM, tracing RAM flags, player/object structs,
  pointers, data tables, free-space code caves, or hardware/emulator quirks before making edits.
---

# ROM Recon & Memory Mapper (Read-Only)

Perform disciplined, read-only reconnaissance on any retro console ROM so subsequent ASM or graphics edits are grounded in verified addresses.

## Procedure

1. **Load Project Context**
   - Read `<project>/PROJECT_CONTEXT.md` and `<project>/allowed_ranges.json` first.
   - Note the target CPU/ISA, endianness, banking/memory map (ROM file offset vs. CPU virtual address), and already-claimed caves.

2. **Trace Before Proposing Changes**
   - Inspect existing build scripts, `.asm` files, or disassemblies to find relevant routines, tables, and callers.
   - **Enumerate all instances & rendering paths:** Never assume a cutscene OAM sprite is reused in playable gameplay (or vice versa). Before patching a recurring asset (vehicle, portrait, boss, title screen), check both OAM tables and Scroll Plane / BG tilemaps across every stage, cutscene, and intro phase.
   - For every address or symbol discovered, record:
     - **File offset** and **CPU address** (when banked or mapped, e.g., `ROM 0x1FAC00` = `CPU 0x3FAC00`).
     - **Exact original bytes** at candidate hook sites (needed for `assert_and_patch`).
     - **RAM / struct layout** (size, signedness, known enum values).

3. **Separate Facts from Hypotheses**
   - Present findings in two clear sections:
     - **Verified** (cited from ROM bytes, disassembly, or confirmed emulator trace).
     - **Hypotheses to Verify** (candidates to confirm via emulator watchpoint/breakpoint or test script).

4. **Identify Free Space Safely**
   - Never assume `0x00` or `0xFF` padding is unused without checking references and nearby tables.
   - Cross-check candidate caves against `allowed_ranges.json` to ensure zero overlap.

5. **Update Ground Truth**
   - Once confirmed, record newly mapped addresses, hooks, and caves in `<project>/PROJECT_CONTEXT.md` (and `src/symbols.inc` if the project uses assembly symbol files).
