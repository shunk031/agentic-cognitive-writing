"""Summarize existing pairwise judgments with the prompt as the unit.

Three analyses answer reviewer objections without any model call:

- ``prompt_level``: one test per main contrast and benchmark. Each prompt's
  outcomes (win 1, tie 0.5, loss 0) are averaged over generation runs; the mean
  over prompts gets a prompt bootstrap interval, and an exact sign test counts a
  prompt as a win above 0.5 and a loss below 0.5.
- ``length_logistic``: a logistic model of the order-consistent decided outcome
  on the log length ratio (focal over other). The intercept is the preference at
  equal length; intervals come from a prompt-cluster bootstrap.
- ``judge_agreement``: Cohen's kappa between the primary and cross-family judges
  over their shared prompt-level outcomes.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import cross_family, length_control

MAIN_CONTRASTS = (("A4", "A1"), ("A4", "A2"), ("A4", "A3"))
LENGTH_CONTRASTS = MAIN_CONTRASTS + (("A4", "A5"), ("A4", "A6"))
AGREEMENT_CONTRASTS = cross_family.DEFAULT_CONTRASTS
SCORE = {"left": 1.0, "tie": 0.5, "right": 0.0}
BOOTSTRAP_SEED = 20260908
PROMPT_RESAMPLES = 10_000
LOGISTIC_RESAMPLES = 2_000


def _label(contrast: tuple[str, str]) -> str:
    return f"{contrast[0]}:{contrast[1]}"


def _percentile(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    position = q * (len(ordered) - 1)
    low = math.floor(position)
    high = math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def prompt_level_summary(
    rows: Sequence[length_control.PairObservation], *, seed: int = BOOTSTRAP_SEED
) -> dict[str, Any]:
    """Tie-as-half rate and sign test over prompts averaged across runs."""
    by_prompt: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        by_prompt[(row.benchmark, row.prompt)].append(SCORE[row.verdict])
    means = [sum(values) / len(values) for values in by_prompt.values()]
    wins = sum(value > 0.5 for value in means)
    losses = sum(value < 0.5 for value in means)
    rng = random.Random(seed)
    resampled = [
        sum(rng.choice(means) for _ in means) / len(means)
        for _ in range(PROMPT_RESAMPLES)
    ]
    return {
        "pairs": len(rows),
        "prompts": len(means),
        "rate": sum(means) / len(means),
        "bootstrap_low": _percentile(resampled, 0.025),
        "bootstrap_high": _percentile(resampled, 0.975),
        "prompt_wins": wins,
        "prompt_losses": losses,
        "prompt_ties": len(means) - wins - losses,
        "sign_test_p": length_control._exact_two_sided_sign_test(wins, losses),
    }


def fit_logistic(points: Sequence[tuple[float, int]]) -> tuple[float, float]:
    """Return (intercept, slope) of a two-parameter logistic fit by Newton steps."""
    intercept = slope = 0.0
    for _ in range(50):
        g0 = g1 = h00 = h01 = h11 = 0.0
        for x, y in points:
            p = 1.0 / (1.0 + math.exp(-(intercept + slope * x)))
            w = p * (1.0 - p)
            g0 += y - p
            g1 += (y - p) * x
            h00 += w
            h01 += w * x
            h11 += w * x * x
        det = h00 * h11 - h01 * h01
        if det <= 0:
            raise ValueError("logistic fit is singular")
        step0 = (h11 * g0 - h01 * g1) / det
        step1 = (h00 * g1 - h01 * g0) / det
        intercept += step0
        slope += step1
        if abs(step0) < 1e-10 and abs(step1) < 1e-10:
            break
    return intercept, slope


def _decided_points(
    rows: Sequence[length_control.PairObservation],
) -> dict[tuple[str, str], list[tuple[float, int]]]:
    clusters: dict[tuple[str, str], list[tuple[float, int]]] = defaultdict(list)
    for row in rows:
        if row.verdict == "tie":
            continue
        x = math.log(row.left_length / row.right_length)
        clusters[(row.benchmark, row.prompt)].append((x, int(row.verdict == "left")))
    return clusters


def length_logistic_summary(
    rows: Sequence[length_control.PairObservation], *, seed: int = BOOTSTRAP_SEED
) -> dict[str, Any]:
    clusters = _decided_points(rows)
    keys = sorted(clusters)
    points = [point for key in keys for point in clusters[key]]
    intercept, slope = fit_logistic(points)
    rng = random.Random(seed)
    intercepts: list[float] = []
    slopes: list[float] = []
    for _ in range(LOGISTIC_RESAMPLES):
        sample = [
            point for key in rng.choices(keys, k=len(keys)) for point in clusters[key]
        ]
        b0, b1 = fit_logistic(sample)
        intercepts.append(b0)
        slopes.append(b1)

    def prob(value: float) -> float:
        return 1.0 / (1.0 + math.exp(-value))

    return {
        "decided_pairs": len(points),
        "prompts": len(keys),
        "intercept": intercept,
        "equal_length_preference": prob(intercept),
        "equal_length_preference_low": prob(_percentile(intercepts, 0.025)),
        "equal_length_preference_high": prob(_percentile(intercepts, 0.975)),
        "slope": slope,
        "slope_low": _percentile(slopes, 0.025),
        "slope_high": _percentile(slopes, 0.975),
    }


def cohen_kappa(pairs: Sequence[tuple[str, str]]) -> float:
    categories = sorted({value for pair in pairs for value in pair})
    total = len(pairs)
    observed = sum(first == second for first, second in pairs) / total
    expected = sum(
        (sum(first == category for first, _ in pairs) / total)
        * (sum(second == category for _, second in pairs) / total)
        for category in categories
    )
    return (observed - expected) / (1.0 - expected)


def judge_agreement(rows: Sequence[cross_family.PairObservation]) -> dict[str, Any]:
    outcomes = [(row.reference_collapsed, row.cross_family_collapsed) for row in rows]
    decided = [pair for pair in outcomes if "tie" not in pair]
    return {
        "pairs": len(outcomes),
        "agreeing_pairs": sum(first == second for first, second in outcomes),
        "kappa": cohen_kappa(outcomes),
        "both_decided_pairs": len(decided),
        "both_decided_agreeing_pairs": sum(
            first == second for first, second in decided
        ),
        "both_decided_kappa": cohen_kappa(decided),
    }


def analyze(
    runs: Mapping[str, Sequence[length_control.PairObservation]],
    agreement_rows: Sequence[cross_family.PairObservation],
) -> dict[str, Any]:
    rows = [row for run_rows in runs.values() for row in run_rows]

    def select(contrast: tuple[str, str], benchmark: str | None = None) -> list[Any]:
        return [
            row
            for row in rows
            if (row.left_condition, row.right_condition) == contrast
            and (benchmark is None or row.benchmark == benchmark)
        ]

    benchmarks = sorted({row.benchmark for row in rows})
    return {
        "schema_version": 1,
        "run_labels": list(runs),
        "prompt_level": {
            _label(contrast): {
                "across_benchmarks": prompt_level_summary(select(contrast)),
                "benchmarks": {
                    benchmark: prompt_level_summary(select(contrast, benchmark))
                    for benchmark in benchmarks
                },
            }
            for contrast in MAIN_CONTRASTS
        },
        "length_logistic": {
            _label(contrast): length_logistic_summary(select(contrast))
            for contrast in LENGTH_CONTRASTS
        },
        "judge_agreement": {
            "all_contrasts": judge_agreement(agreement_rows),
            "contrasts": {
                _label(contrast): judge_agreement(
                    [row for row in agreement_rows if row.contrast == contrast]
                )
                for contrast in AGREEMENT_CONTRASTS
            },
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs-root", type=Path, action="append", required=True)
    parser.add_argument("--run-label", action="append", required=True)
    parser.add_argument("--judge-id", required=True)
    parser.add_argument("--cross-family-runs-root", type=Path, required=True)
    parser.add_argument("--cross-family-judge", required=True)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if len(args.run_label) != len(args.runs_root):
        parser.error("each --runs-root needs one --run-label")
    contrasts = tuple(dict.fromkeys(LENGTH_CONTRASTS))
    runs = {
        label: length_control.load_judged_pairs(
            root, judge_id=args.judge_id, contrasts=contrasts
        )
        for label, root in zip(args.run_label, args.runs_root, strict=True)
    }
    agreement_rows, _ = cross_family._load_pair_rows(
        args.cross_family_runs_root,
        cross_family_judge_id=args.cross_family_judge,
        reference_judge_id=args.judge_id,
        contrasts=AGREEMENT_CONTRASTS,
    )
    report = analyze(runs, agreement_rows)
    report.update(
        {"judge_id": args.judge_id, "cross_family_judge_id": args.cross_family_judge}
    )
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
