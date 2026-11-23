================================================================================
Tails Pocket Adventure (v3.1)
ROM Hack for Sonic The Hedgehog - Pocket Adventure (Neo Geo Pocket Color)
================================================================================

Overview
--------
Play through Single Player mode as Miles "Tails" Prower, complete with his
signature flight ability, custom Sonic Advance-style flying sprites, Tails HUD
& 1UP icon, Tornado role swaps, and a custom TAILS title screen logo.

Features (v3.1)
---------------
1. Playable Tails in Single Player
   - Single Player starts with Tails instead of Sonic.
   - Tails can fly by pressing A (Jump) again at any point while airborne
     (including while moving left/right or quick-tapping mid-jump).
   - Balanced flight physics (3x ascent height, gravity & fall speed cap),
     visible-screen top ceiling collision (works in normal stages & boss
     arenas), and upward/downward flight damage against enemies.
   - Custom 1:1 Sonic Advance flying sprite set (frames 0x85..0x90, preserving
     frame 0x84 for looking up) with 2x3 blue eyes & white sclera, plus
     lowered-volume helicopter tail SFX.
   - Extra separate tail overlay sprite is hidden cleanly during flight.

2. Tornado & Ending Swaps
   - In Single Player Tornado sequences and ending scenes, Sonic pilots the
     Tornado while Tails rides on the wing.

3. HUD, Title Screen, Goalpost & Quality-of-Life
   - Tails orange 1UP lives / HUD face icon.
   - End-of-Act Goalpost / Signpost updated with custom Tails signpost art.
   - Title Screen logo updated to "TAILS POCKET ADVENTURE" (on both the
     PRESS "A" BUTTON and START/CONTINUE/GO TO ROOM screens).
   - NGPC ROM header cart title updated to "TAILS POCKET" (12-byte header
     limit at 0x24..0x2F).
   - Title Screen Shortcut: Press Option on the Title Screen to open the
     Debug / Level Select menu directly.

Controls
--------
- D-Pad          : Move / Crouch / Look
- A              : Jump / Spin Dash; press A again mid-jump or mid-roll to Fly
                   (tap/hold A while flying to ascend)
- B              : Secondary action / Cancel
- Option         : Pause (in-game) / Open Debug & Level Select (Title Screen)

Patching Instructions
---------------------
Apply either `Tails Pocket Adventure v3.1.bps` (recommended, verifies source
checksums) or `Tails Pocket Adventure v3.1.ips` using Floating IPS (Flips),
RomPatcher.js, or a compatible patcher to an unmodified clean copy of:

  Sonic The Hedgehog - Pocket Adventure (World).ngc

Checksums (Verified)
--------------------
Source ROM: Sonic The Hedgehog - Pocket Adventure (World).ngc (2,097,152 bytes)
  CRC32 : 356F0849
  MD5   : B8A899AE2B0F1DFA0DB5417DE745A51E
  SHA-1 : 3FE15D4374C4CA073AA0393FCFCAD0055BD345AB

Patched ROM: Tails Pocket Adventure v3.1.ngc (2,097,152 bytes)
  CRC32 : 24C88D6A
  MD5   : 7F95C3D6367D3EDE3555EA7C2F4CC331
  SHA-1 : 7A1344246D3BD1C5A5941E5961404E6B6B45DE9E

Patch Files:
  Tails Pocket Adventure v3.1.bps (13,987 bytes, Patch CRC32: D2D0F406)
  Tails Pocket Adventure v3.1.ips (14,199 bytes)

Credits
-------
- Original Game        : SNK / Dimps / Sega (Sonic The Hedgehog - Pocket Adventure)
- Flying Sprite Source : Sonic Advance (GBA) Tails flying sprite sheet
- ROM Hack, Assembly,
  Title Logo & Tooling : Created with Antigravity AI (TLCS-900/H via ASW)
