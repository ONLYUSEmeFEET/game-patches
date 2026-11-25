"""Shared, patch-agnostic ROM hacking build & verification toolkit (BPS-only)."""

from .asm import AsmBuildResult, SymbolTable, assemble_asw, parse_asw_map, write_sym_file
from .bps import build_bps, format_checksums, verify_bps, write_bps
from .diff import AllowedRange, DiffReport, load_allowed_ranges, verify_diff
from .gfx import (
    build_preview_sheet,
    make_checkerboard,
    save_palette_swatch,
    validate_palette_pixels,
)
from .qa import ImageDiffResult, QACaseResult, compare_images, run_qa_suite
from .release import check_version_sync, format_readme_checksums
from .rom import assert_and_patch, hash_bytes, load_clean_rom

__all__ = [
    "AllowedRange",
    "AsmBuildResult",
    "DiffReport",
    "ImageDiffResult",
    "QACaseResult",
    "SymbolTable",
    "assemble_asw",
    "assert_and_patch",
    "build_bps",
    "build_preview_sheet",
    "check_version_sync",
    "compare_images",
    "format_checksums",
    "format_readme_checksums",
    "hash_bytes",
    "load_allowed_ranges",
    "load_clean_rom",
    "make_checkerboard",
    "parse_asw_map",
    "run_qa_suite",
    "save_palette_swatch",
    "validate_palette_pixels",
    "verify_bps",
    "verify_diff",
    "write_bps",
    "write_sym_file",
]
