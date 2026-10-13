"""Count Monitor delegation fallbacks by condition and recompute pairwise results without them.

A completed run records the fallback when a trace decision mentions it, the
same measure as `trace_endings`; the A4, A5, and A6 skills require the
Monitor to record it, while the A3 prompt has no fallback rule. Pairwise
results for A4 against each compared condition are recomputed after dropping
prompt pairs whose A4 run (or, for the ablations, either run) recorded a
fallback. Rates follow the main tables: order-consistent wins over decided
pairs, summed over benchmarks within a generation run, then averaged over runs.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from statistics import fmean
from typing import Any

from . import length_control as lc
from .common import select_canonical_runs

SUBAGENT_CONDITIONS = ("A3", "A4", "A5", "A6")
CONTRASTS = (("A4", "A1"), ("A4", "A2"), ("A4", "A3"), ("A4", "A5"), ("A4", "A6"))
JUDGE_ID = "gpt-5.6-sol-pairwise-v1"


def fallback_recorded(trace: Path) -> bool:
    if not trace.exists():
        return False
    events = [
        json.loads(line)
        for line in trace.read_text(encoding="utf-8", errors="ignore").splitlines()
        if line.strip()
    ]
    return "fallback" in " ".join(str(e.get("decision", "")) for e in events).casefold()


def summarize(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """W/L/T totals and the mean over generation runs of the per-run win rate."""
    rows = list(rows)
    per_run: dict[str, list[int]] = {}
    for row in rows:
        counts = per_run.setdefault(row["run"], [0, 0, 0])
        counts[("left", "right", "tie").index(row["verdict"])] += 1
    wins, losses, ties = (sum(c[i] for c in per_run.values()) for i in range(3))
    rates = [w / (w + l) for w, l, _ in per_run.values() if w + l]
    return {
        "pairs": len(rows),
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "rate_mean_over_runs": fmean(rates) if rates else None,
    }


def contrast_summary(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for left, right in CONTRASTS:
        selected = [r for r in rows if (r["left"], r["right"]) == (left, right)]
        ablation = right in SUBAGENT_CONDITIONS and right != "A3"
        kept = [
            r
            for r in selected
            if not r["left_fallback"] and not (ablation and r["right_fallback"])
        ]
        result[f"{left}:{right}"] = {
            "all": summarize(selected),
            "without_fallback": summarize(kept),
        }
    return result


def analyze_roots(roots: Sequence[Path]) -> dict[str, Any]:
    counts = {c: {"completed_runs": 0, "fallback_runs": 0} for c in SUBAGENT_CONDITIONS}
    rows: list[dict[str, Any]] = []
    for number, root in enumerate(roots, start=1):
        flags: dict[Path, bool] = {}
        for run in select_canonical_runs([root]):
            if run.status != "completed":
                continue
            flags[run.path] = fallback_recorded(
                run.path / ".writing" / "trace" / "process.jsonl"
            )
            if run.condition in counts:
                counts[run.condition]["completed_runs"] += 1
                counts[run.condition]["fallback_runs"] += flags[run.path]
        index = lc._run_index([root])
        seen: set[tuple[str, str, str, str]] = set()
        for manifest_path in sorted(root.resolve().rglob("scores-manifest.json")):
            manifest = lc._json(manifest_path)
            if not manifest or manifest.get("task") != "pairwise":
                continue
            if (manifest.get("judge") or {}).get("judge_id") != JUDGE_ID:
                continue
            runs = [
                index.get(s.get("run_manifest_sha256"))
                for s in manifest.get("source_runs", [])
            ]
            if len(runs) != 2 or None in runs:
                continue
            by_condition = {run.condition: run for run in runs}
            contrast = next((c for c in CONTRASTS if set(c) == set(by_condition)), None)
            records = lc._records(manifest_path.parent / "scores.jsonl")
            if contrast is None or not records:
                continue
            left, right = contrast
            key = (left, right, runs[0].benchmark, runs[0].prompt)
            if key in seen:
                continue
            seen.add(key)
            mapping = lc._mapping(manifest)
            outcomes = tuple(
                lc._outcome_condition(records[p], runs, mapping[p])
                for p in ("A|B", "B|A")
            )
            rows.append(
                {
                    "run": f"run-{number}",
                    "left": left,
                    "right": right,
                    "verdict": lc.collapse_verdict(outcomes, left, right),
                    "left_fallback": flags.get(by_condition[left].path, False),
                    "right_fallback": flags.get(by_condition[right].path, False),
                }
            )
    return {
        "measure": "a trace event decision mentions 'fallback'",
        "judge_id": JUDGE_ID,
        "fallback_by_condition": counts,
        "contrasts": contrast_summary(rows),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs-root", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = analyze_roots(args.runs_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
