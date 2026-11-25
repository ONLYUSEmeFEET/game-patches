================================================================================
Tails Pocket Adventure (v3.2)
ROM Hack for Sonic The Hedgehog - Pocket Adventure (Neo Geo Pocket Color)
================================================================================

Overview
--------
Play through Single Player mode as Miles "Tails" Prower, complete with his
signature flight ability, custom Sonic Advance-style flying sprites, a brand-new
Tails title screen with blinking animation, Tails HUD / 1UP / Goalpost / Title
Card / Special Stage art, and Sonic & Tails Tornado role swaps.

Features (v3.2)
---------------
1. Playable Tails in Single Player & Flight Mechanics
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

2. Brand-New Tails Title Screen
   - Custom hand-drawn Tails portrait popping out of the unbroken gold star
     ring, complete with a smooth eye-blinking OAM animation.
   - "TAILS POCKET ADVENTURE" logo with a deep Tails-orange badge (on both the
     PRESS "A" BUTTON and START / CONTINUE / GO TO ROOM screens).
   - Clean intro transition: the gold star ring drops and sparkles, then flows
     directly into Tails inside the ring without Sonic ever flashing on screen.
   - NGPC ROM header cart title updated to "TAILS POCKET" (0x24..0x2F).
   - Title Screen Shortcut: Press Option on the Title Screen to open the
     Debug / Level Select menu directly.

3. Tornado, Special Stage, HUD & Act Art Swaps
   - Sky Chase (5-1) & Ending Cutscene Tornado Swap: Sonic pilots the Tornado
     cockpit (both playable Scroll Plane 2 BG cockpit and Ending OAM sprites)
     while Tails rides on the wing.
   - HUD / Lives Icon & 1UP Monitor updated with Tails's orange face icon.
   - End-of-Act Goalpost / Signpost updated with custom Tails signpost art and
     Tails palette.
   - Level Title Card silhouette updated with 3 custom Tails silhouette frames.
   - Special Stage Intro / Win Pose updated with 4 custom Tails standing/pose
     frames, Tails palette hooks, and "TAILS GOT A CHAOS EMERALD!" text.
     (Note: Special Stage running sprites remain stock blue Sonic for now.)

Controls
--------
- D-Pad          : Move / Crouch / Look
- A              : Jump / Spin Dash; press A again mid-jump or mid-roll to Fly
                   (tap/hold A while flying to ascend)
- B              : Secondary action / Cancel
- Option         : Pause (in-game) / Open Debug & Level Select (Title Screen)

Patching Instructions
---------------------
Apply `Tails Pocket Adventure v3.2.bps` using Floating IPS (Flips),
RomPatcher.js, or any BPS-compatible patcher to an unmodified clean copy of:

  Sonic The Hedgehog - Pocket Adventure (World).ngc

Checksums (Verified)
--------------------
Source ROM: Sonic The Hedgehog - Pocket Adventure (World).ngc (2,097,152 bytes)
  CRC32 : 356F0849
  MD5   : B8A899AE2B0F1DFA0DB5417DE745A51E
  SHA-1 : 3FE15D4374C4CA073AA0393FCFCAD0055BD345AB

Patched ROM: Tails Pocket Adventure v3.2.ngc (2,097,152 bytes)
  CRC32 : 9F8B45A4
  MD5   : F1F26011C57C630E49B27246A23FEDE9
  SHA-1 : B4C70D5BD9C1D45C1D0A53E4001E3AA0CC27FF0D

Patch File:
  Tails Pocket Adventure v3.2.bps (17,341 bytes, Patch CRC32: 2144DF1C)

Changelog
---------
v3.2
- Added custom Tails Title Screen portrait inside the unbroken gold star ring
  with eye-blinking OAM animation and deep Tails-orange logo badge.
- Removed Sonic's pop-up & "SONIC THE HEDGEHOG" intro flash so the dropping
  gold star ring transitions directly into Tails.
- Fixed playable Sky Chase (5-1) Tornado cockpit by patching the Scroll Plane 2
  cockpit tiles directly with custom Sonic pilot art.
- Added 4 custom Tails Special Stage standing/pose frames + palette hooks and
  3 custom Tails Title Card silhouette frames.
- Replaced "SONIC GOT A CHAOS EMERALD!" with "TAILS GOT A CHAOS EMERALD!".
- Replaced End-of-Act Goalpost / Signpost with custom Tails signpost art.

Credits
-------
- Author & Custom Art  : AJ Ryan (@ONLYUSEmeFEET)
- Original Game        : SNK / Dimps / Sega (Sonic The Hedgehog - Pocket Adventure)
- Flying Sprite Source : Sonic Advance (GBA) Tails flying sprite sheet
- Assembly & Tooling   : TLCS-900/H (Macro Assembler AS) & Python BPS patchkit
                         built with Antigravity AI
