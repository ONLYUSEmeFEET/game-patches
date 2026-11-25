"""ROM byte-diff verification against allowed hook/cave ranges."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class AllowedRange:
    start: int
    end: int
    label: str
    kind: str = "cave"

    @property
    def capacity(self) -> int:
        return self.end - self.start + 1

    def contains(self, offset: int) -> bool:
        return self.start <= offset <= self.end


@dataclass
class DiffReport:
    total_changed: int
    allowed_changed: int
    unauthorized: list[tuple[int, int, int]] = field(default_factory=list)
    range_usage: dict[str, tuple[AllowedRange, int]] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return len(self.unauthorized) == 0


def _parse_addr(value: int | str) -> int:
    if isinstance(value, int):
        return value
    s = value.strip().lower()
    if s.startswith("0x"):
        return int(s, 16)
    if s.startswith("$"):
        return int(s[1:], 16)
    return int(s, 0)


def load_allowed_ranges(ranges_path: str | Path) -> list[AllowedRange]:
    """Load inclusive [start, end] byte ranges from JSON and verify no overlaps."""
    path = Path(ranges_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    raw_ranges = data.get("ranges", data if isinstance(data, list) else [])

    parsed: list[AllowedRange] = []
    for entry in raw_ranges:
        start = _parse_addr(entry["start"])
        end = _parse_addr(entry["end"])
        label = str(entry.get("label", f"0x{start:06X}-0x{end:06X}"))
        kind = str(entry.get("kind", "cave"))
        if end < start:
            raise ValueError(
                f"Invalid range '{label}': end (0x{end:X}) < start (0x{start:X})"
            )
        parsed.append(AllowedRange(start=start, end=end, label=label, kind=kind))

    # Detect overlapping declarations
    ordered = sorted(parsed, key=lambda r: (r.start, r.end))
    for prev, curr in zip(ordered, ordered[1:]):
        if curr.start <= prev.end:
            raise ValueError(
                f"Overlapping allowed ranges: '{prev.label}' "
                f"(0x{prev.start:06X}..0x{prev.end:06X}) overlaps '{curr.label}' "
                f"(0x{curr.start:06X}..0x{curr.end:06X})"
            )

    return ordered


def verify_diff(
    base: bytes | bytearray,
    patched: bytes | bytearray,
    ranges_path: str | Path,
    *,
    max_report: int = 40,
    print_report: bool = True,
) -> DiffReport:
    """Verify every modified byte in `patched` falls inside `ranges_path`."""
    if len(base) != len(patched):
        raise ValueError(
            f"ROM size mismatch: base={len(base)} B (0x{len(base):X}), "
            f"patched={len(patched)} B (0x{len(patched):X})"
        )

    ranges = load_allowed_ranges(ranges_path)
    usage_counts: dict[int, int] = {i: 0 for i in range(len(ranges))}
    unauthorized: list[tuple[int, int, int]] = []
    allowed_changed = 0

    # Walk ranges with an index pointer since ranges are sorted and non-overlapping
    r_idx = 0
    num_ranges = len(ranges)

    for offset, (b_byte, p_byte) in enumerate(zip(base, patched)):
        if b_byte == p_byte:
            continue
        while r_idx < num_ranges and ranges[r_idx].end < offset:
            r_idx += 1
        if r_idx < num_ranges and ranges[r_idx].contains(offset):
            allowed_changed += 1
            usage_counts[r_idx] += 1
        else:
            unauthorized.append((offset, b_byte, p_byte))

    range_usage = {
        ranges[i].label: (ranges[i], usage_counts[i]) for i in range(num_ranges)
    }
    report = DiffReport(
        total_changed=allowed_changed + len(unauthorized),
        allowed_changed=allowed_changed,
        unauthorized=unauthorized,
        range_usage=range_usage,
    )

    if print_report:
        print(
            f"Diff Gate: {report.total_changed} changed bytes "
            f"(allowed: {report.allowed_changed}, unauthorized: {len(report.unauthorized)})"
        )
        caves = [(r, used) for r, used in range_usage.values() if r.kind == "cave"]
        if caves:
            print("Cave Utilization:")
            for r, used in caves:
                pct = (used / r.capacity * 100.0) if r.capacity else 0.0
                print(
                    f"  0x{r.start:06X}..0x{r.end:06X}  "
                    f"{used:5d} / {r.capacity:5d} B ({pct:5.1f}%)  {r.label}"
                )

        if unauthorized:
            print("UNAUTHORIZED BYTE CHANGES DETECTED:", file=sys.stderr)
            for offset, b_byte, p_byte in unauthorized[:max_report]:
                print(
                    f"  0x{offset:06X}: base=0x{b_byte:02X} -> patched=0x{p_byte:02X}",
                    file=sys.stderr,
                )
            if len(unauthorized) > max_report:
                print(
                    f"  ... and {len(unauthorized) - max_report} more offsets.",
                    file=sys.stderr,
                )

    if not report.passed:
        raise AssertionError(
            f"Diff gate failed: {len(unauthorized)} unauthorized byte(s) modified outside {ranges_path}"
        )

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify ROM byte changes against allowed_ranges.json."
    )
    parser.add_argument("--base", required=True, type=Path, help="Clean base ROM path")
    parser.add_argument("--patched", required=True, type=Path, help="Built ROM path")
    parser.add_argument("--ranges", required=True, type=Path, help="allowed_ranges.json path")
    parser.add_argument("--max-report", type=int, default=40)
    args = parser.parse_args()

    try:
        verify_diff(
            args.base.read_bytes(),
            args.patched.read_bytes(),
            args.ranges,
            max_report=args.max_report,
            print_report=True,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
