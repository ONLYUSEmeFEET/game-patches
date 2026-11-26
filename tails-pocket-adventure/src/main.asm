    cpu 96c141
    maxmode on
    include "symbols.inc"

    ; Single cave origin: all routines and data pack sequentially with zero manual org gaps.
    ; Hook sites in build_patch.py resolve label addresses automatically via ASW's .map output.
    org CAVE_ASM_BASE

; --- Custom Mid-Air Flight & 6.0s Fatigue Hook for Tails (called from ROM 0x19AAFD) ---
flight_hook:
    cp (RAM_CHAR_ID), CHAR_TAILS
    jp ne, normal_grav
    ; Do not run flight physics/animation if hurt (04), dead (05), or Giant Ring/Goal warp (>=04)
    cp (xiz+P_SUBSTATE), STATE_HURT_OR_WARP
    jp uge, normal_grav

    ; Respect engine control-lock timer (springs, boosters, cutscenes) before reading jump input
    cpw (xiz+P_CTRL_LOCK), 0000h
    jr ne, check_flying

    ; If fatigued (RAM_FLY_LOCKED != 0), ignore A presses completely until Tails leaves airborne state
    cp (RAM_FLY_LOCKED), 00h
    jr ne, check_flying

    ld a, (RAM_INPUT_PRESSED)
    and a, 30h
    jr z, check_flying

    cp (xiz+P_ANIM_ID), ANIM_TAILS_FLY
    jr eq, boost_vel

start_fly:
    push xix
    push xiy
    ld xix, fly_script
    call FN_START_ANIM
    pop xiy
    pop xix
    ldw (RAM_FLY_FATIGUE), FLY_MAX_FRAMES
    ld (RAM_FLY_SFX_TIMER), FLY_SFX_INTERVAL
    call play_fly_sfx

boost_vel:
    ld (xiz+P_SUBSTATE), STATE_FLIGHT_ACTIVE
    ldw (xiz+P_Y_VEL), FLY_BOOST_VEL

check_flying:
    cp (xiz+P_ANIM_ID), ANIM_TAILS_FLY
    jp ne, normal_grav

    ; Check whether Tails is already fatigued (RAM_FLY_LOCKED != 0)
    cp (RAM_FLY_LOCKED), 00h
    jr ne, tired_flying

    ; Active flight: decrement 16-bit fatigue countdown (sub updates Z flag reliably on TLCS-900/H)
    ld wa, (RAM_FLY_FATIGUE)
    sub wa, 0001h
    ld (RAM_FLY_FATIGUE), wa
    jr nz, active_fly_sfx

    ; Stamina just expired -> lock flight until landing/spring/hurt, disable attack hitbox, switch to tired anim
    ld (RAM_FLY_LOCKED), 01h
    ld (xiz+P_SUBSTATE), STATE_NORMAL
    push xix
    push xiy
    ld xix, fly_tired_script
    call FN_START_ANIM
    pop xiy
    pop xix
    ld (RAM_FLY_SFX_TIMER), FLY_TIRED_SFX_INT
    jr tired_cap_vel

active_fly_sfx:
    dec 1, (RAM_FLY_SFX_TIMER)
    jr nz, fly_cap_vel
    ld (RAM_FLY_SFX_TIMER), FLY_SFX_INTERVAL
    call play_fly_sfx

fly_cap_vel:
    cpw (xiz+P_Y_VEL), FLY_FALL_CAP
    jr ge, fly_grav
    ldw (xiz+P_Y_VEL), FLY_FALL_CAP

fly_grav:
    ; Top Ceiling Collision using visible camera screen top:
    ; screen_Y_from_top = (RAM_CAMERA_Y) + 0097h - (xiz+P_Y_POS)
    ; Clamp when rising ((xiz+P_Y_VEL) > 0) and (xiz+P_Y_POS) >= (RAM_CAMERA_Y) + 0087h (16px from screen top)
    cpw (xiz+P_Y_VEL), 0000h
    jr le, fly_grav_val
    ld bc, (RAM_CAMERA_Y)
    add bc, FLY_CEIL_OFFSET
    cp (xiz+P_Y_POS), bc
    jr lt, fly_grav_val
    ld (xiz+P_Y_POS), bc
    ldw (xiz+P_Y_VEL), 0000h

fly_grav_val:
    ld wa, FLY_GRAVITY
    ret

tired_flying:
    ld (xiz+P_SUBSTATE), STATE_NORMAL
    dec 1, (RAM_FLY_SFX_TIMER)
    jr nz, tired_cap_vel
    ld (RAM_FLY_SFX_TIMER), FLY_TIRED_SFX_INT
    call play_fly_sfx

tired_cap_vel:
    cpw (xiz+P_Y_VEL), FLY_TIRED_FALL_CAP
    jr ge, tired_grav_val
    ldw (xiz+P_Y_VEL), FLY_TIRED_FALL_CAP

tired_grav_val:
    ld wa, FLY_TIRED_GRAVITY
    ret

normal_grav:
    call FN_CHECK_WATER
    ld wa, NORM_GRAVITY
    jr nc, done_grav
    ld wa, WATER_GRAVITY
done_grav:
    ret

; --- Dynamic VBlank Tile Streamer Hook (called from ROM 0x03BFFC) ---
tile_stream_hook:
    sub xhl, xhl
    ld hl, (xix+)
    bit 15, hl
    jr nz, custom_tile
    sll 4, xhl
    add xhl, xiy
    ret
custom_tile:
    res 15, hl
    sll 4, xhl
    add xhl, CAVE_CUSTOM_TILES
    ret

; --- Shadow OAM Metasprite Pointer Hook (called from ROM 0x03C081) ---
oam_meta_hook:
    ld xiz, ROM_META_HI
    ld iz, (xix+8)
    cp iz, CUSTOM_META_THRESH
    jr ult, normal_meta
    ld xiz, CAVE_CUSTOM_META_HI
    ld iz, (xix+8)
normal_meta:
    ld bc, (xiz+)
    ret

; --- Ending Cutscene Tails Palette Helper (called from ROM 0x1E727D) ---
ending_tails_pal:
    ld wa, PAL_TAILS_BASE
    ld c, 00h
    call FN_LOAD_PALETTE
    ld wa, PAL_TAILS_OVER
    ld c, 01h
    call FN_LOAD_PALETTE
    ret

; --- Hide Extra Tails During Flight & Clear Fatigue Lock Outside Airborne State (called from ROM 0x19C7EC) ---
hide_tails_hook:
    cpw (xiz+P_STATE_FN), STATE_AIRBORNE_LO
    jr eq, check_hide_tail
    ld (RAM_FLY_LOCKED), 00h
check_hide_tail:
    cp (xiz+P_ANIM_ID), ANIM_TAILS_FLY
    jr eq, skip_extra_tails
    jp FN_DRAW_EXTRA_TAILS
skip_extra_tails:
    ret

; --- Tails Flying SFX Helper ---
play_fly_sfx:
    push xiz
    ld wa, SFX_TAILS_FLY
    call FN_PLAY_SFX
    pop xiz
    ret

; --- Title Screen Option -> Debug/Level Select Shortcut (called from ROM 0x03B203) ---
title_debug_hook:
    ld a, (RAM_INPUT_PRESSED)
    bit 6, a
    jr eq, no_title_debug
    pop xbc
    call FN_TITLE_CLEANUP
    call FN_TITLE_DEBUG_PREP
    ld xwa, ADDR_TITLE_DEBUG_JP
    db 0b6h, 60h
    ret
no_title_debug:
    and a, 1fh
    ret

; --- Goalpost Signpost Tails Palette Hook (called from ROM 0x1CE458) ---
signpost_pal_hook:
    cp (RAM_CHAR_ID), CHAR_TAILS
    jr ne, orig_signpost_pal
    ld wa, PAL_TAILS_BASE
    ld c, 00h
    call FN_LOAD_PALETTE
    ld wa, PAL_TAILS_OVER
    ld c, 01h
    call FN_LOAD_PALETTE
    ret
orig_signpost_pal:
    db 0d8h, 0ach, 23h, 00h, 1dh, 0b3h, 0e3h, 23h
    db 0d8h, 0adh, 23h, 01h, 1dh, 0b3h, 0e3h, 23h
    ret

; --- Special Stage Standing Pose Tails Palette Hook (called from 0x1CA5DE, 0x1CA6AD) ---
ss_tails_pal_hook:
    cp (RAM_CHAR_ID), CHAR_TAILS
    jr ne, orig_ss_pal
    ld wa, PAL_TAILS_BASE
    ld c, 00h
    call FN_LOAD_PALETTE
    ld wa, PAL_TAILS_OVER
    ld c, 01h
    call FN_LOAD_PALETTE
    ret
orig_ss_pal:
    db 0d8h, 0afh, 23h, 01h, 1dh, 0b3h, 0e3h, 23h
    ret

; --- 4-Frame Shimmer-Free NGPC-Style Tails Flying Animation Script (0x85..0x88) ---
fly_script:
    db 0ch, 00h, 85h, 00h,  03h, 02h
    db 0ch, 00h, 86h, 00h,  03h, 02h
    db 0ch, 00h, 87h, 00h,  03h, 02h
    db 0ch, 00h, 88h, 00h,  03h, 02h
    db 02h, fly_script & 0ffh, (fly_script >> 8) & 0ffh, (fly_script >> 16) & 0ffh

; --- 2-Frame NGPC-Style Tired Flying Animation Script (closed eyes, slower spin: 0x89..0x8A) ---
fly_tired_script:
    db 0ch, 00h, 89h, 00h,  03h, 06h
    db 0ch, 00h, 8ah, 00h,  03h, 06h
    db 02h, fly_tired_script & 0ffh, (fly_tired_script >> 8) & 0ffh, (fly_tired_script >> 16) & 0ffh
