================================================================================
Tails Pocket Adventure (v3.4)
ROM Hack for Sonic The Hedgehog - Pocket Adventure (Neo Geo Pocket Color)
================================================================================

Overview
--------
Play through Single Player mode as Miles "Tails" Prower, complete with his
signature flight ability, 5-second flight fatigue mechanics, shimmer-free
NGPC-style flying & tired sprites, a brand-new Tails title screen with blinking
animation, full Special Stage Tails conversion (behind-view running, clean
orange Spin Ball, Win/Lose poses, Half-Pipe & Results Tally banners), Tails
HUD / 1UP / Goalpost / Title Card art, and Sonic & Tails Tornado role swaps.

Features (v3.4)
---------------
1. Playable Tails in Single Player, Flight & Fatigue Mechanics
   - Single Player starts with Tails instead of Sonic.
   - Tails can fly by pressing A (Jump) again at any point while airborne
     (including while moving left/right or quick-tapping mid-jump).
   - Balanced 5.0-second (300-frame) flight fatigue system: once stamina runs
     out, Tails switches to a closed-eye tired descent with a slower propeller
     sputter SFX, loses his flight attack hitbox (vulnerable), ignores A lift
     presses, and retains horizontal steering until landing, hitting a spring,
     grabbing a bar, or taking damage.
   - Balanced flight physics (3x ascent height, gravity & fall speed cap),
     visible-screen top ceiling collision (works in normal stages & boss
     arenas), and upward/downward flight damage against enemies while active.
   - Custom shimmer-free NGPC-style flying & tired sprite set (4 active frames
     0x85..0x88 + 2 tired closed-eye frames 0x89..0x8A, preserving frame 0x84
     for looking up) with crisp 3-stack SkyBlue/Black/DarkBlue eyes, plus
     cleanly timed helicopter tail SFX with engine control-lock guards.
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
   - Special Stage Full Tails Conversion:
     * 5 custom behind-view Tails running sprites (inspired by Sonic Triple
       Trouble, with fox ears, smooth back, and twin swaying orange-and-white
       tails) across all 8 half-pipe angles + hurt/tumble frames (94 remapped
       metasprite pointers) with Tails's palette locked throughout gameplay.
     * Clean orange Spin Ball (Sonic's blue center diamond removed).
     * 4 custom Tails Intro / Win / Lose poses with restored red+white shoes.
     * Compact 35-sprite Half-Pipe "TAILS GOT A CHAOS EMERALD!" OAM banner
       (staying safely under NGPC's 64-sprite OAM cap so Tails stays visible
       when winning) AND native two-tone BG "TAILS GOT A CHAOS EMERALD!" text
       on the Results Tally screen.

Controls
--------
- D-Pad          : Move / Crouch / Look
- A              : Jump / Spin Dash; press A again mid-jump or mid-roll to Fly
                   (tap/hold A while flying to ascend for up to 5.0 seconds)
- B              : Secondary action / Cancel
- Option         : Pause (in-game) / Open Debug & Level Select (Title Screen)

Patching Instructions
---------------------
Official Download: https://www.romhacking.net/hacks/10425/
(ROMhacking.net and GitHub are the official homes for all of my patches;
third-party mirror sites may host outdated versions.)

Apply `Tails Pocket Adventure v3.4.bps` using Floating IPS (Flips),
RomPatcher.js, or any BPS-compatible patcher to an unmodified clean copy of:

  Sonic The Hedgehog - Pocket Adventure (World).ngc

(Older patches have been moved into the `archived/` folder.)

Checksums (Verified)
--------------------
Source ROM: Sonic The Hedgehog - Pocket Adventure (World).ngc (2,097,152 bytes)
  CRC32 : 356F0849
  MD5   : B8A899AE2B0F1DFA0DB5417DE745A51E
  SHA-1 : 3FE15D4374C4CA073AA0393FCFCAD0055BD345AB

Patched ROM: Tails Pocket Adventure v3.4.ngc (2,097,152 bytes)
  CRC32 : 1480DCC5
  MD5   : F4A3E0F9A0018355A8A4D47288D74A39
  SHA-1 : FC0FEE953906D1416502377E159D556BF3E83A99

Patch File:
  Tails Pocket Adventure v3.4.bps (19,992 bytes, Patch CRC32: 2144DF1C)

Changelog
---------
v3.4
- Full Special Stage Tails conversion: added 5 custom behind-view Tails running
  sprites (fox ears, smooth back, swaying twin tails) across all 8 half-pipe
  angles & hurt frames (94 remapped metasprite pointers) plus gameplay palette
  hooks (0x1CA3B0, 0x1CA7C6).
- Removed Sonic's blue center diamond from Tails's Special Stage Spin Ball.
- Restored full red+white shoes and cleaned stray outline pixels on Tails's
  Special Stage Win and Lose poses.
- Rebuilt Half-Pipe "TAILS GOT A CHAOS EMERALD!" OAM banner into a crisp,
  opaque 35-sprite font (preventing 64-sprite OAM overflow so Tails no longer
  vanishes while winning).
- Patched the Special Stage Results Tally Scroll Plane BG tileset (0x050464)
  and tilemap (0x056D52) so the Results screen displays "TAILS GOT A CHAOS
  EMERALD!" in the authentic White/Mint/Teal gradient.
- Archived v3.3.bps into `archived/` for a clean download.

v3.3
- Added 5.0-second (300-frame) flight fatigue system with dedicated WRAM lock
  flag (cannot re-fly mid-air until landing, hitting a spring, or taking damage).
- Upgraded Tails's flying sprites to a shimmer-free, NGPC-style 4-frame active
  + 2-frame closed-eye tired sprite set with crisp 3-stack SkyBlue/Black/DarkBlue
  eyes (reducing custom tile footprint from 302 to 233 tiles).
- Fixed flying SFX RAM collision (moved out of colliding xiz+0x3C into verified-
  free WRAM 0x006980..0x006984), added engine control-lock guard (xiz+0x40),
  and tuned active (20-frame) and tired sputter (36-frame) SFX cadence.
- Archived older patches (v3.1, v3.2) into `archived/` for a clean download.

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
- Flying Sprite Ref    : Sonic Advance (GBA) adapted to NGPC flat-color style
- Assembly & Tooling   : TLCS-900/H (Macro Assembler AS) & Python BPS patchkit
                         built with Antigravity AI
