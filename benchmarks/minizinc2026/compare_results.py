#!/usr/bin/env python3
"""Compare two MiniZinc 2026 benchmark summaries without assuming objective direction."""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Any

TERMINAL = {"OPTIMAL", "FEASIBLE", "UNSAT"}
PROVEN = {"OPTIMAL", "UNSAT"}


def read_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {row["instance_id"]: row for row in rows}


def as_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def as_bool(value: str | None) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def geomean(values: list[float]) -> float | None:
    positive = [x for x in values if x > 0 and math.isfinite(x)]
    if not positive:
        return None
    return math.exp(sum(math.log(x) for x in positive) / len(positive))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--enhanced", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    baseline = read_rows(args.baseline)
    enhanced = read_rows(args.enhanced)
    common = sorted(set(baseline) & set(enhanced))
    only_baseline = sorted(set(baseline) - set(enhanced))
    only_enhanced = sorted(set(enhanced) - set(baseline))
    if only_baseline or only_enhanced:
        parser.error(
            f"instance sets differ; baseline-only={only_baseline}, enhanced-only={only_enhanced}"
        )
    if not common:
        parser.error("no common instances")

    identity_fields = [
        "dataset_commit", "minizinc_version", "threads",
        "time_limit_seconds", "seed",
    ]
    for field in identity_fields:
        bvals = {baseline[x].get(field, "") for x in common}
        evals = {enhanced[x].get(field, "") for x in common}
        if len(bvals) != 1 or len(evals) != 1 or bvals != evals:
            parser.error(f"baseline/enhanced benchmark identity mismatch for {field}: {bvals} vs {evals}")

    cutoff = float(next(iter({baseline[x]["time_limit_seconds"] for x in common})))
    rows: list[dict[str, Any]] = []
    speedups_terminal: list[float] = []
    speedups_proven: list[float] = []
    par2_terminal_base = 0.0
    par2_terminal_enh = 0.0
    par2_proven_base = 0.0
    par2_proven_enh = 0.0

    for instance_id in common:
        b = baseline[instance_id]
        e = enhanced[instance_id]
        bt = b.get("status", "UNKNOWN")
        et = e.get("status", "UNKNOWN")
        bw = as_float(b.get("wall_time_seconds")) or cutoff
        ew = as_float(e.get("wall_time_seconds")) or cutoff
        b_terminal = bt in TERMINAL
        e_terminal = et in TERMINAL
        b_proven = bt in PROVEN
        e_proven = et in PROVEN
        b_feasible = as_bool(b.get("has_solution")) or bt in {"FEASIBLE", "OPTIMAL"}
        e_feasible = as_bool(e.get("has_solution")) or et in {"FEASIBLE", "OPTIMAL"}

        par2_terminal_base += bw if b_terminal else 2.0 * cutoff
        par2_terminal_enh += ew if e_terminal else 2.0 * cutoff
        par2_proven_base += bw if b_proven else 2.0 * cutoff
        par2_proven_enh += ew if e_proven else 2.0 * cutoff

        speedup = (bw / ew) if b_terminal and e_terminal and ew > 0 else None
        if speedup is not None:
            speedups_terminal.append(speedup)
        if b_proven and e_proven and ew > 0:
            speedups_proven.append(bw / ew)

        rows.append({
            "instance_id": instance_id,
            "baseline_status": bt,
            "enhanced_status": et,
            "baseline_has_solution": b_feasible,
            "enhanced_has_solution": e_feasible,
            "baseline_wall_time_seconds": bw,
            "enhanced_wall_time_seconds": ew,
            "speedup_baseline_over_enhanced": speedup if speedup is not None else "",
            "baseline_objective": b.get("objective", ""),
            "enhanced_objective": e.get("objective", ""),
            "baseline_objective_bound": b.get("objectiveBound", ""),
            "enhanced_objective_bound": e.get("objectiveBound", ""),
            "baseline_nodes": b.get("nodes", ""),
            "enhanced_nodes": e.get("nodes", ""),
            "baseline_failures": b.get("failures", ""),
            "enhanced_failures": e.get("failures", ""),
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    n = len(common)
    b_terminal_count = sum(baseline[x].get("status") in TERMINAL for x in common)
    e_terminal_count = sum(enhanced[x].get("status") in TERMINAL for x in common)
    b_proven_count = sum(baseline[x].get("status") in PROVEN for x in common)
    e_proven_count = sum(enhanced[x].get("status") in PROVEN for x in common)
    b_feasible_count = sum(as_bool(baseline[x].get("has_solution")) or baseline[x].get("status") in {"FEASIBLE", "OPTIMAL"} for x in common)
    e_feasible_count = sum(as_bool(enhanced[x].get("has_solution")) or enhanced[x].get("status") in {"FEASIBLE", "OPTIMAL"} for x in common)

    print(f"Instances: {n}")
    print(f"Feasible: baseline {b_feasible_count}/{n}; enhanced {e_feasible_count}/{n}")
    print(f"Terminal: baseline {b_terminal_count}/{n}; enhanced {e_terminal_count}/{n}")
    print(f"Proven (optimal or unsat): baseline {b_proven_count}/{n}; enhanced {e_proven_count}/{n}")
    print(f"PAR-2 terminal: baseline {par2_terminal_base:.1f}; enhanced {par2_terminal_enh:.1f}")
    print(f"PAR-2 proven: baseline {par2_proven_base:.1f}; enhanced {par2_proven_enh:.1f}")
    print(f"Geomean speedup (joint terminal): {geomean(speedups_terminal)} over {len(speedups_terminal)} instances")
    print(f"Geomean speedup (joint proven): {geomean(speedups_proven)} over {len(speedups_proven)} instances")
    print(f"Per-instance comparison: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
