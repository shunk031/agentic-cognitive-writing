"""Agreement between the pairwise judge and an always-prefer-the-longer-output rule.

Following the length check in DoLoMiTes, each order-consistent decided pair of
the pre-specified contrasts counts as agreeing when the judge's winner is the
longer output. Pairs of equal length and judge ties are left out, because the
rule makes no choice on the former and the judge makes none on the latter.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from .length_control import PairObservation, load_judged_pairs

JUDGE_ID = "gpt-5.6-sol-pairwise-v1"


def agreement(rows: Iterable[PairObservation]) -> dict[str, Any]:
    by_benchmark: dict[str, list[int]] = {}
    for row in rows:
        outcome = row.longer_verdict
        if outcome not in ("win", "loss"):
            continue
        counts = by_benchmark.setdefault(row.benchmark, [0, 0])
        counts[0] += outcome == "win"
        counts[1] += 1
    result = {
        benchmark: {"agreeing": agree, "decided_pairs": total, "rate": agree / total}
        for benchmark, (agree, total) in sorted(by_benchmark.items())
    }
    agree = sum(v["agreeing"] for v in result.values())
    total = sum(v["decided_pairs"] for v in result.values())
    result["all_benchmarks"] = {"agreeing": agree, "decided_pairs": total, "rate": agree / total if total else None}
    return result


def analyze_roots(roots: Sequence[Path]) -> dict[str, Any]:
    rows = [row for root in roots for row in load_judged_pairs(root, judge_id=JUDGE_ID)]
    return {"judge_id": JUDGE_ID, "agreement_with_longer_rule": agreement(rows)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs-root", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.write_text(json.dumps(analyze_roots(args.runs_root), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
