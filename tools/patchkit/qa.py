"""Emulator-agnostic headless QA runner and golden-frame screenshot comparator."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ImageDiffResult:
    actual: Path
    golden: Path
    diff_pixels: int
    total_pixels: int
    passed: bool
    diff_image: Path | None = None


@dataclass(frozen=True)
class QACaseResult:
    name: str
    passed: bool
    message: str
    image_diffs: tuple[ImageDiffResult, ...] = ()


def compare_images(
    actual_path: str | Path,
    golden_path: str | Path,
    *,
    max_diff_pixels: int = 0,
    diff_out_path: str | Path | None = None,
) -> ImageDiffResult:
    """Compare two screenshots pixel-by-pixel using Pillow."""
    try:
        from PIL import Image, ImageChops
    except ImportError as exc:
        raise RuntimeError(
            "Pillow is required for screenshot comparison: python -m pip install Pillow"
        ) from exc

    act_p = Path(actual_path)
    gld_p = Path(golden_path)
    with Image.open(act_p) as a_im, Image.open(gld_p) as g_im:
        a_rgb = a_im.convert("RGB")
        g_rgb = g_im.convert("RGB")
        if a_rgb.size != g_rgb.size:
            return ImageDiffResult(
                actual=act_p,
                golden=gld_p,
                diff_pixels=max(a_rgb.width * a_rgb.height, g_rgb.width * g_rgb.height),
                total_pixels=a_rgb.width * a_rgb.height,
                passed=False,
            )

        diff = ImageChops.difference(a_rgb, g_rgb)
        # Count pixels where any RGB channel differs
        diff_pixels = sum(1 for r, g, b in diff.getdata() if (r | g | b) != 0)
        total = a_rgb.width * a_rgb.height
        passed = diff_pixels <= max_diff_pixels

        saved_diff: Path | None = None
        if not passed and diff_out_path is not None:
            saved_diff = Path(diff_out_path)
            saved_diff.parent.mkdir(parents=True, exist_ok=True)
            diff.save(saved_diff)

        return ImageDiffResult(
            actual=act_p,
            golden=gld_p,
            diff_pixels=diff_pixels,
            total_pixels=total,
            passed=passed,
            diff_image=saved_diff,
        )


def run_qa_suite(
    suite_path: str | Path,
    rom_path: str | Path,
    *,
    out_dir: str | Path | None = None,
) -> list[QACaseResult]:
    """Run a declarative JSON emulator QA suite against a built ROM."""
    suite_file = Path(suite_path).resolve()
    suite_dir = suite_file.parent
    cfg = json.loads(suite_file.read_text(encoding="utf-8"))

    cmd_template: str = cfg["emulator_cmd"]
    base_out = Path(out_dir).resolve() if out_dir else (suite_dir / "work" / "qa_out")
    base_out.mkdir(parents=True, exist_ok=True)
    rom_abs = Path(rom_path).resolve()

    results: list[QACaseResult] = []
    for case in cfg.get("cases", []):
        name = str(case["name"])
        case_out = base_out / name
        case_out.mkdir(parents=True, exist_ok=True)
        script_rel = case.get("script", "")
        script_abs = (suite_dir / script_rel).resolve() if script_rel else ""

        formatted = cmd_template.format(
            rom=str(rom_abs),
            script=str(script_abs),
            out_dir=str(case_out),
            case=name,
        )
        proc = subprocess.run(
            shlex.split(formatted, posix=False),
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            results.append(
                QACaseResult(
                    name=name,
                    passed=False,
                    message=f"Emulator exited with code {proc.returncode}: {proc.stderr.strip()}",
                )
            )
            continue

        missing = [
            f for f in case.get("expected_files", []) if not (case_out / f).is_file()
        ]
        if missing:
            results.append(
                QACaseResult(
                    name=name,
                    passed=False,
                    message=f"Missing expected output file(s): {', '.join(missing)}",
                )
            )
            continue

        diffs: list[ImageDiffResult] = []
        golden_dir = case.get("golden_dir")
        if golden_dir:
            g_dir = (suite_dir / golden_dir).resolve()
            max_px = int(case.get("max_diff_pixels", 0))
            for g_png in sorted(g_dir.glob("*.png")):
                actual_png = case_out / g_png.name
                if not actual_png.is_file():
                    diffs.append(
                        ImageDiffResult(
                            actual=actual_png,
                            golden=g_png,
                            diff_pixels=-1,
                            total_pixels=0,
                            passed=False,
                        )
                    )
                else:
                    diffs.append(
                        compare_images(
                            actual_png,
                            g_png,
                            max_diff_pixels=max_px,
                            diff_out_path=case_out / f"diff_{g_png.name}",
                        )
                    )

        failed_diffs = [d for d in diffs if not d.passed]
        if failed_diffs:
            summary = ", ".join(
                f"{d.golden.name} ({d.diff_pixels} px diff)" for d in failed_diffs
            )
            results.append(
                QACaseResult(
                    name=name,
                    passed=False,
                    message=f"Golden frame mismatch: {summary}",
                    image_diffs=tuple(diffs),
                )
            )
        else:
            results.append(
                QACaseResult(
                    name=name,
                    passed=True,
                    message="OK",
                    image_diffs=tuple(diffs),
                )
            )

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a declarative emulator QA suite.")
    parser.add_argument("--suite", required=True, type=Path, help="Path to qa_suite.json")
    parser.add_argument("--rom", required=True, type=Path, help="Path to built ROM")
    parser.add_argument("--out-dir", type=Path, default=None, help="Output directory for captures")
    args = parser.parse_args()

    results = run_qa_suite(args.suite, args.rom, out_dir=args.out_dir)
    failed = 0
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.name}: {r.message}")
        if not r.passed:
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
