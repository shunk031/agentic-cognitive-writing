from __future__ import annotations

import argparse
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..runner.hashing import sha256_file
from .aggregate import (
    CONFIRMATORY_CONTRASTS,
    wilson_interval,
)
from .common import RunRecord, select_canonical_runs

RATIO_BINS = (1.05, 1.10, 1.25, 1.50, 2.00)


@dataclass(frozen=True)
class PairObservation:
    benchmark: str
    prompt: str
    judge_id: str
    left_condition: str
    right_condition: str
    left_length: int
    right_length: int
    verdict: str

    @property
    def ratio(self) -> float:
        return length_ratio(self.left_length, self.right_length)

    @property
    def longer_condition(self) -> str | None:
        if self.left_length == self.right_length:
            return None
        return (
            self.left_condition
            if self.left_length > self.right_length
            else self.right_condition
        )

    @property
    def longer_verdict(self) -> str | None:
        if self.longer_condition is None:
            return None
        return _condition_outcome(self, self.longer_condition)


def length_ratio(left_length: int, right_length: int) -> float:
    if left_length <= 0 or right_length <= 0:
        raise ValueError("output lengths must be positive")
    return max(left_length, right_length) / min(left_length, right_length)


def collapse_verdict(
    outcomes: tuple[str, str], left_condition: str, right_condition: str
) -> str:
    first, second = outcomes
    if first == second == left_condition:
        return "left"
    if first == second == right_condition:
        return "right"
    return "tie"


def ratio_bin(ratio: float) -> str:
    lower = 1.0
    for upper in RATIO_BINS:
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
    focal_condition: str | None = None,
    longer_side: bool = False,
    max_ratio: float | None = None,
) -> dict[str, Any]:
    selected = [row for row in rows if max_ratio is None or row.ratio <= max_ratio]
    equal_length_pairs = sum(row.longer_condition is None for row in selected)
    if longer_side:
        selected_for_outcomes = [
            row for row in selected if row.longer_condition is not None
        ]
        condition = None
    else:
        selected_for_outcomes = selected
        condition = focal_condition

    counts = {"wins": 0, "losses": 0, "ties": 0}
    for row in selected_for_outcomes:
        outcome = (
            row.longer_verdict if longer_side else _condition_outcome(row, condition)  # type: ignore[arg-type]
        )
        counts[{"win": "wins", "loss": "losses", "tie": "ties"}[outcome]] += 1
    non_ties = counts["wins"] + counts["losses"]
    low, high = wilson_interval(counts["wins"], counts["losses"])
    return {
        "pairs": len(selected_for_outcomes),
        "selected_pairs": len(selected),
        "equal_length_pairs": equal_length_pairs,
        **counts,
        "n_non_tie": non_ties,
        "win_rate": counts["wins"] / non_ties if non_ties else None,
        "wilson_low": low,
        "wilson_high": high,
        "sign_test_p": _exact_two_sided_sign_test(counts["wins"], counts["losses"]),
    }


def _single_writer_shorter_summary(
    rows: Sequence[PairObservation],
) -> dict[str, Any]:
    selected = [
        row
        for row in rows
        if row.left_condition == "A7"
        and row.right_condition == "A1"
        and row.left_length * 10 <= row.right_length * 9
    ]
    return summarize_outcomes(selected, focal_condition="A7")


def _json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _mapping(manifest: Mapping[str, Any]) -> dict[str, tuple[int, int]]:
    tournament = manifest.get("tournament")
    result: dict[str, tuple[int, int]] = {}
    items = (
        tournament.get("order_mapping", []) if isinstance(tournament, Mapping) else []
    )
    for item in items:
        if not isinstance(item, Mapping):
            continue
        presentation = item.get("presentation")
        if not isinstance(presentation, str):
            continue
        result[presentation] = (
            0 if item.get("first_output") == "first_run" else 1,
            0 if item.get("second_output") == "first_run" else 1,
        )
    return result or {"A|B": (0, 1), "B|A": (1, 0)}


def _records(path: Path) -> dict[str, Mapping[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return {}
    grouped: dict[str, list[Mapping[str, Any]]] = {"A|B": [], "B|A": []}
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(value, Mapping):
            continue
        presentation = value.get("presentation")
        winner = value.get("winner")
        if presentation in grouped and winner in {"A", "B", "tie"}:
            grouped[presentation].append(value)
    if any(len(grouped[key]) != 1 for key in grouped):
        return {}
    return {key: grouped[key][0] for key in grouped}


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


def _run_index(roots: Sequence[Path]) -> dict[str, RunRecord]:
    runs = select_canonical_runs(list(roots))
    return {
        "sha256:" + sha256_file(run.path / "run-manifest.json"): run
        for run in runs
        if run.status == "completed"
    }


def load_judged_pairs(
    runs_root: Path,
    *,
    judge_id: str,
    contrasts: tuple[tuple[str, str], ...] = CONFIRMATORY_CONTRASTS,
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
        source_runs: list[RunRecord] = []
        for source in manifest.get("source_runs", []):
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
        if not records:
            continue
        mapping = _mapping(manifest)
        outcomes = tuple(
            _outcome_condition(
                records[presentation], source_runs, mapping[presentation]
            )
            for presentation in ("A|B", "B|A")
        )
        verdict = collapse_verdict(outcomes, *contrast)
        by_condition = {run.condition: run for run in source_runs}
        lengths = {
            condition: by_condition[condition].manifest.get("output_units_used")
            for condition in contrast
        }
        if not all(
            isinstance(value, int) and not isinstance(value, bool) and value > 0
            for value in lengths.values()
        ):
            continue
        row = PairObservation(
            benchmark=first.benchmark,
            prompt=first.prompt,
            judge_id=judge_id,
            left_condition=contrast[0],
            right_condition=contrast[1],
            left_length=lengths[contrast[0]],
            right_length=lengths[contrast[1]],
            verdict=verdict,
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
        "all_pairs_longer_side": summarize_outcomes(rows, longer_side=True),
        "by_contrast": {},
        "length_matched": {"5_percent": {}, "10_percent": {}},
        "ratio_bins": {},
        "single_writer_at_least_10_percent_shorter": (
            _single_writer_shorter_summary(rows)
        ),
        "pairs": [],
    }
    for row in rows:
        item = asdict(row)
        item.update(
            {
                "length_ratio": row.ratio,
                "longer_condition": row.longer_condition,
                "longer_verdict": row.longer_verdict,
                "ratio_bin": ratio_bin(row.ratio),
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
            "longer_side": summarize_outcomes(contrast_rows, longer_side=True),
            "focal": summarize_outcomes(contrast_rows, focal_condition=focal),
        }
        for name, ratio in (("5_percent", 1.05), ("10_percent", 1.10)):
            result["length_matched"][name][label] = {
                "focal_condition": focal,
                **summarize_outcomes(
                    contrast_rows, focal_condition=focal, max_ratio=ratio
                ),
            }

    for label in sorted({ratio_bin(row.ratio) for row in rows}):
        bin_rows = [row for row in rows if ratio_bin(row.ratio) == label]
        result["ratio_bins"][label] = summarize_outcomes(bin_rows, longer_side=True)
    return result


def _process_summary(path: Path) -> dict[str, Any]:
    value = _json(path)
    if value is None or not isinstance(value.get("conditions"), Mapping):
        raise ValueError(f"invalid process summary: {path}")
    return {
        "run_label": value.get("run_label", path.stem),
        "median_output_units": {
            condition: details["median_output_units"]
            for condition, details in value["conditions"].items()
            if isinstance(details, Mapping) and "median_output_units" in details
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze pairwise verdicts conditional on output length."
    )
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--judge-id", required=True)
    parser.add_argument("--run-label", required=True)
    parser.add_argument("--process-summary", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows = load_judged_pairs(args.runs_root, judge_id=args.judge_id)
    report = analyze_pairs(rows)
    report.update(
        {
            "run_label": args.run_label,
            "judge_id": args.judge_id,
            "length_unit": (
                "output units from run-manifest.json output_units_used; "
                "the process summaries derive median_output_units from this field"
            ),
            "process_summaries": [
                _process_summary(path) for path in args.process_summary
            ],
        }
    )
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
