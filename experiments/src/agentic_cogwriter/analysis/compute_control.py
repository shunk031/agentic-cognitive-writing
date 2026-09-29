from __future__ import annotations

import argparse
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .aggregate import CONFIRMATORY_CONTRASTS, wilson_interval
from .common import RunRecord, parse_contrasts
from .length_control import (
    _json,
    _records,
    _run_index,
    collapse_verdict,
)

COMPUTE_CONTRASTS = (
    CONFIRMATORY_CONTRASTS[0],
    CONFIRMATORY_CONTRASTS[1],
    CONFIRMATORY_CONTRASTS[2],
    CONFIRMATORY_CONTRASTS[6],
)
RATIO_BINS = (1.05, 1.10, 1.25, 1.50, 2.00)
RATIO_BIN_UPPER_BOUNDS = (
    0.50,
    2 / 3,
    0.80,
    1 / 1.10,
    1 / 1.05,
    *RATIO_BINS,
)
MATCHED_BANDS = (1.25, 1.50)


@dataclass(frozen=True)
class PairObservation:
    benchmark: str
    prompt: str
    judge_id: str
    left_condition: str
    right_condition: str
    left_compute_tokens: float
    right_compute_tokens: float
    verdict: str

    @property
    def compute_ratio(self) -> float:
        return compute_ratio(self.left_compute_tokens, self.right_compute_tokens)

    @property
    def relative_compute_ratio(self) -> float:
        return max(self.compute_ratio, 1 / self.compute_ratio)


def compute_ratio(left_tokens: float, right_tokens: float) -> float:
    if left_tokens <= 0 or right_tokens <= 0:
        raise ValueError("compute tokens must be positive")
    return left_tokens / right_tokens


def ratio_bin(ratio: float) -> str:
    if ratio <= 0:
        raise ValueError("compute ratio must be positive")
    lower = 0.0
    for upper in RATIO_BIN_UPPER_BOUNDS:
        if ratio < upper:
            return f"{lower:.2f}-{upper:.2f}"
        lower = upper
    return f"{lower:.2f}+"


def _condition_outcome(row: PairObservation, condition: str) -> str:
    if row.verdict == "tie":
        return "tie"
    winner = row.left_condition if row.verdict == "left" else row.right_condition
    return "win" if winner == condition else "loss"


def _exact_two_sided_sign_test(wins: int, losses: int) -> float:
    non_ties = wins + losses
    if non_ties == 0:
        return 1.0
    limit = min(wins, losses)
    term = math.ldexp(1.0, -non_ties)
    tail = term
    for index in range(limit):
        term *= (non_ties - index) / (index + 1)
        tail += term
    return min(1.0, 2.0 * tail)


def summarize_outcomes(
    rows: Sequence[PairObservation],
    *,
    focal_condition: str,
    max_ratio: float | None = None,
) -> dict[str, Any]:
    if max_ratio is not None and max_ratio <= 0:
        raise ValueError("max_ratio must be positive")
    selected = [
        row
        for row in rows
        if max_ratio is None or row.relative_compute_ratio <= max_ratio
    ]
    counts = {"wins": 0, "losses": 0, "ties": 0}
    for row in selected:
        outcome = _condition_outcome(row, focal_condition)
        counts[{"win": "wins", "loss": "losses", "tie": "ties"}[outcome]] += 1
    non_ties = counts["wins"] + counts["losses"]
    low, high = wilson_interval(counts["wins"], counts["losses"])
    return {
        "pairs": len(selected),
        **counts,
        "n_non_tie": non_ties,
        "win_rate": counts["wins"] / non_ties if non_ties else None,
        "wilson_low": low,
        "wilson_high": high,
        "sign_test_p": _exact_two_sided_sign_test(counts["wins"], counts["losses"]),
    }


def _rank(values: Sequence[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][1] == ordered[index][1]:
            end += 1
        rank = (index + end + 1) / 2
        for position in range(index, end):
            ranks[ordered[position][0]] = rank
        index = end
    return ranks


def _spearman(rows: Sequence[PairObservation], focal_condition: str) -> dict[str, Any]:
    ratios = [row.compute_ratio for row in rows]
    outcomes = [
        {"win": 1.0, "tie": 0.5, "loss": 0.0}[_condition_outcome(row, focal_condition)]
        for row in rows
    ]
    x_ranks = _rank(ratios)
    y_ranks = _rank(outcomes)
    if len(rows) < 2:
        rho = None
    else:
        x_mean = sum(x_ranks) / len(x_ranks)
        y_mean = sum(y_ranks) / len(y_ranks)
        numerator = sum(
            (x - x_mean) * (y - y_mean) for x, y in zip(x_ranks, y_ranks, strict=True)
        )
        denominator = math.sqrt(
            sum((x - x_mean) ** 2 for x in x_ranks)
            * sum((y - y_mean) ** 2 for y in y_ranks)
        )
        rho = numerator / denominator if denominator else None
    return {
        "n": len(rows),
        "rho": rho,
        "outcome_encoding": "first-listed win=1, tie=0.5, loss=0",
    }


def _mapping(manifest: Mapping[str, Any]) -> dict[str, tuple[int, int]] | None:
    tournament = manifest.get("tournament")
    items = tournament.get("order_mapping") if isinstance(tournament, Mapping) else None
    if not isinstance(items, list):
        return {"A|B": (0, 1), "B|A": (1, 0)}
    result: dict[str, tuple[int, int]] = {}
    for item in items:
        if not isinstance(item, Mapping):
            return None
        presentation = item.get("presentation")
        first = item.get("first_output")
        second = item.get("second_output")
        if presentation not in {"A|B", "B|A"}:
            return None
        if first not in {"first_run", "second_run"}:
            return None
        if second not in {"first_run", "second_run"}:
            return None
        result[presentation] = (
            0 if first == "first_run" else 1,
            0 if second == "first_run" else 1,
        )
    return result if set(result) == {"A|B", "B|A"} else None


def _outcome_condition(
    record: Mapping[str, Any],
    source_runs: Sequence[RunRecord],
    mapping: tuple[int, int],
) -> str:
    winner = record["winner"]
    if winner == "tie":
        return "tie"
    source_index = mapping[0 if winner == "A" else 1]
    return source_runs[source_index].condition


def _compute_tokens(run: RunRecord) -> float | None:
    attempts = run.manifest.get("attempts")
    accounting = run.manifest.get("token_accounting")
    if (
        not isinstance(attempts, int)
        or isinstance(attempts, bool)
        or attempts <= 0
        or not isinstance(accounting, Mapping)
        or accounting.get("status") != "observed"
    ):
        return None
    output_tokens = accounting.get("output_tokens")
    reasoning_tokens = accounting.get("reasoning_output_tokens")
    total_tokens = accounting.get("total_tokens")
    if not all(
        isinstance(value, int) and not isinstance(value, bool) and value >= 0
        for value in (output_tokens, reasoning_tokens, total_tokens)
    ):
        return None
    if total_tokens <= 0 or output_tokens + reasoning_tokens != total_tokens:
        return None
    budget_used = run.manifest.get("budget_used_tokens")
    if budget_used != total_tokens:
        return None
    return total_tokens / attempts


def load_judged_pairs(
    runs_root: Path,
    *,
    judge_id: str,
    contrasts: tuple[tuple[str, str], ...] = COMPUTE_CONTRASTS,
) -> list[PairObservation]:
    source_index = _run_index([runs_root])
    observations: dict[tuple[str, str, str, str, str], PairObservation] = {}
    for manifest_path in sorted(runs_root.resolve().rglob("scores-manifest.json")):
        manifest = _json(manifest_path)
        if manifest is None or manifest.get("task") != "pairwise":
            continue
        judge = manifest.get("judge")
        observed_judge = judge.get("judge_id") if isinstance(judge, Mapping) else None
        if observed_judge != judge_id:
            continue
        sources = manifest.get("source_runs")
        if not isinstance(sources, list):
            continue
        source_runs: list[RunRecord] = []
        for source in sources:
            digest = (
                source.get("run_manifest_sha256")
                if isinstance(source, Mapping)
                else None
            )
            if not isinstance(digest, str) or digest not in source_index:
                source_runs = []
                break
            source_runs.append(source_index[digest])
        if len(source_runs) != 2:
            continue
        first, second = source_runs
        if (first.benchmark, first.prompt, first.platform) != (
            second.benchmark,
            second.prompt,
            second.platform,
        ):
            continue
        contrast = next(
            (
                pair
                for pair in contrasts
                if {first.condition, second.condition} == set(pair)
            ),
            None,
        )
        if contrast is None:
            continue
        records = _records(manifest_path.parent / "scores.jsonl")
        mapping = _mapping(manifest)
        if not records or mapping is None:
            continue
        outcomes = tuple(
            _outcome_condition(
                records[presentation], source_runs, mapping[presentation]
            )
            for presentation in ("A|B", "B|A")
        )
        by_condition = {run.condition: run for run in source_runs}
        tokens = {
            condition: _compute_tokens(by_condition[condition])
            for condition in contrast
        }
        left_tokens = tokens[contrast[0]]
        right_tokens = tokens[contrast[1]]
        if left_tokens is None or right_tokens is None:
            continue
        row = PairObservation(
            benchmark=first.benchmark,
            prompt=first.prompt,
            judge_id=judge_id,
            left_condition=contrast[0],
            right_condition=contrast[1],
            left_compute_tokens=left_tokens,
            right_compute_tokens=right_tokens,
            verdict=collapse_verdict(outcomes, *contrast),
        )
        key = (
            row.benchmark,
            row.prompt,
            row.judge_id,
            row.left_condition,
            row.right_condition,
        )
        observations.setdefault(key, row)
    return sorted(
        observations.values(),
        key=lambda row: (
            row.benchmark,
            row.left_condition,
            row.right_condition,
            row.prompt,
        ),
    )


def analyze_pairs(rows: Sequence[PairObservation]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "pair_count": len(rows),
        "by_contrast": {},
        "pairs": [],
    }
    for row in rows:
        item = asdict(row)
        item.update(
            {
                "compute_ratio": row.compute_ratio,
                "relative_compute_ratio": row.relative_compute_ratio,
                "ratio_bin": ratio_bin(row.compute_ratio),
            }
        )
        result["pairs"].append(item)

    labels = sorted({f"{row.left_condition}:{row.right_condition}" for row in rows})
    for label in labels:
        contrast_rows = [
            row
            for row in rows
            if f"{row.left_condition}:{row.right_condition}" == label
        ]
        focal = contrast_rows[0].left_condition
        result["by_contrast"][label] = {
            "focal_condition": focal,
            "focal": summarize_outcomes(contrast_rows, focal_condition=focal),
            "compute_matched": {
                f"within_{band:g}": summarize_outcomes(
                    contrast_rows, focal_condition=focal, max_ratio=band
                )
                for band in MATCHED_BANDS
            },
            "ratio_bins": {
                bin_label: summarize_outcomes(
                    [
                        row
                        for row in contrast_rows
                        if ratio_bin(row.compute_ratio) == bin_label
                    ],
                    focal_condition=focal,
                )
                for bin_label in sorted(
                    {ratio_bin(row.compute_ratio) for row in contrast_rows}
                )
            },
            "spearman": _spearman(contrast_rows, focal),
        }
    return result


def analyze_replicates(
    replications: Mapping[str, Sequence[PairObservation]],
) -> dict[str, Any]:
    pooled = [row for rows in replications.values() for row in rows]
    return {
        "pooled": analyze_pairs(pooled),
        "per_replication": {
            label: analyze_pairs(rows) for label, rows in replications.items()
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze pairwise verdicts conditional on inference-time compute."
    )
    parser.add_argument("--runs-root", type=Path, action="append", required=True)
    parser.add_argument("--judge-id", required=True)
    parser.add_argument("--replication-label", action="append", default=[])
    parser.add_argument(
        "--contrasts",
        type=parse_contrasts,
        default=COMPUTE_CONTRASTS,
        metavar="LEFT:RIGHT,...",
    )
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    labels = args.replication_label or [
        f"replication-{index}" for index in range(1, len(args.runs_root) + 1)
    ]
    if len(labels) != len(args.runs_root):
        parser.error("each --runs-root needs one --replication-label")
    if len(set(labels)) != len(labels):
        parser.error("replication labels must be unique")
    replications = {
        label: load_judged_pairs(
            root,
            judge_id=args.judge_id,
            contrasts=args.contrasts,
        )
        for label, root in zip(labels, args.runs_root, strict=True)
    }
    report = analyze_replicates(replications)
    report.update(
        {
            "judge_id": args.judge_id,
            "compute_unit": (
                "Codex output-plus-reasoning tokens per attempted run from "
                "run-manifest.json token_accounting.total_tokens / attempts"
            ),
            "ratio_bin_upper_bounds": RATIO_BIN_UPPER_BOUNDS,
            "matched_bands": MATCHED_BANDS,
        }
    )
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
