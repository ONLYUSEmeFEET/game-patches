; ==============================================================================
; Tails Pocket Adventure — TLCS-900/H Shared Symbols & Hardware Constants
; ==============================================================================

; --- RAM Addresses ---
RAM_INPUT_PRESSED   equ 004d41h
RAM_CAMERA_Y        equ 00506eh
RAM_CHAR_ID         equ 0067b1h

; --- Character IDs & States ---
CHAR_TAILS          equ 04h
ANIM_TAILS_FLY      equ 3fh
STATE_FLIGHT_ACTIVE equ 02h
STATE_HURT_OR_WARP  equ 04h

; --- Player Struct Offsets (base in xiz) ---
P_Y_POS             equ 16h
P_Y_VEL             equ 1ch
P_ANIM_ID           equ 20h
P_FLY_SFX_TIMER     equ 3ch
P_SUBSTATE          equ 49h

; --- Physics & Audio Constants ---
FLY_BOOST_VEL       equ 0440h
FLY_FALL_CAP        equ 0fd00h
FLY_GRAVITY         equ 0030h
NORM_GRAVITY        equ 0080h
WATER_GRAVITY       equ 0020h
FLY_CEIL_OFFSET     equ 0087h
FLY_SFX_INTERVAL    equ 0ch
SFX_TAILS_FLY       equ 00a2h

; --- Palettes ---
PAL_TAILS_BASE      equ 01b9h
PAL_TAILS_OVER      equ 01bah

; --- Engine Routines (CPU Addresses) ---
FN_TITLE_DEBUG_PREP equ 237815h
FN_LOAD_PALETTE     equ 23e3b3h
FN_START_ANIM       equ 23e4dah
FN_TITLE_CLEANUP    equ 23e88eh
FN_CHECK_WATER      equ 39d296h
FN_DRAW_EXTRA_TAILS equ 39d4e4h
FN_PLAY_SFX         equ 3f1883h
ADDR_TITLE_DEBUG_JP equ 0023b243h

; --- Custom Cave Addresses (CPU Addresses = ROM + 0x200000) ---
CAVE_ASM_BASE       equ 3fac00h
CAVE_CUSTOM_TILES   equ 003fb000h
CAVE_CUSTOM_META_HI equ 003f0000h
ROM_META_HI         equ 00200000h
CUSTOM_META_THRESH  equ 0d000h
