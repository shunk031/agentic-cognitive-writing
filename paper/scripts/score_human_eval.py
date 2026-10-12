#!/usr/bin/env python3
"""Score human-validation answer sheets and automatic-judge agreement."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path


def parse_contrast(value: str) -> tuple[str, str]:
    left, separator, right = value.partition(":")
    if not separator or not left or not right:
        raise ValueError(f"invalid contrast: {value!r}")
    return left, right


def human_to_condition(
    preference: str, key: dict[str, str], condition_a: str | None = None
) -> str:
    if preference == "tie":
        return "tie"
    if preference not in {"A", "B"}:
        raise ValueError(f"invalid preference: {preference!r}")
    condition_a = condition_a or key.get("condition_a", "")
    if not condition_a:
        raise ValueError("condition_a is required to map a human preference")
    left, right = parse_contrast(key["contrast"])
    return (
        condition_a if preference == "A" else (right if left == condition_a else left)
    )


def cohen_kappa(first: list[str], second: list[str]) -> float:
    if len(first) != len(second) or not first:
        raise ValueError("Cohen's kappa needs equally sized non-empty samples")
    observed = sum(a == b for a, b in zip(first, second)) / len(first)
    left = Counter(first)
    right = Counter(second)
    expected = sum(left[c] * right[c] for c in set(left) | set(right)) / (
        len(first) ** 2
    )
    return 1.0 if expected == 1.0 else (observed - expected) / (1 - expected)


def krippendorff_alpha(ratings: dict[str, list[str]]) -> float | None:
    """Nominal Krippendorff alpha, retaining tied and disagreeing ratings."""
    units = [values for values in ratings.values() if len(values) >= 2]
    if not units:
        return None
    total_pairs = 0
    observed_disagreement = 0.0
    overall = Counter()
    total_values = 0
    for values in units:
        counts = Counter(values)
        n = len(values)
        total_pairs += n * (n - 1)
        observed_disagreement += sum(count * (n - count) for count in counts.values())
        overall.update(values)
        total_values += n
    if total_pairs == 0:
        return None
    observed = observed_disagreement / total_pairs
    expected_pairs = total_values * (total_values - 1)
    expected = (
        sum(count * (total_values - count) for count in overall.values())
        / expected_pairs
        if expected_pairs
        else 0.0
    )
    if expected == 0:
        return 1.0 if observed == 0 else 0.0
    return 1 - observed / expected


def fleiss_kappa(ratings: dict[str, list[str]]) -> float | None:
    """Fleiss kappa for complete or partially completed comparison rows."""
    units = [values for values in ratings.values() if len(values) >= 2]
    if not units:
        return None
    categories = sorted({value for values in units for value in values})
    proportions = Counter(value for values in units for value in values)
    total_values = sum(proportions.values())
    p = {category: proportions[category] / total_values for category in categories}
    expected = sum(value * value for value in p.values())
    observed_values = []
    for values in units:
        n = len(values)
        counts = Counter(values)
        observed_values.append(sum(count * count for count in counts.values()) - n)
        observed_values[-1] /= n * (n - 1)
    observed = sum(observed_values) / len(observed_values)
    if expected == 1:
        return 1.0
    return (observed - expected) / (1 - expected)


def raw_agreement(ratings: dict[str, list[str]]) -> float | None:
    agreeing = 0
    possible = 0
    for values in ratings.values():
        for index, first in enumerate(values):
            for second in values[index + 1 :]:
                possible += 1
                agreeing += first == second
    return agreeing / possible if possible else None


def majority(values: Iterable[str]) -> str | None:
    counts = Counter(values)
    if not counts:
        return None
    highest = max(counts.values())
    winners = [value for value, count in counts.items() if count == highest]
    return winners[0] if len(winners) == 1 else "tie"


def _read_key(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = {"comparison_id", "benchmark", "contrast"}
    if rows and not required <= set(rows[0]):
        raise ValueError(f"key is missing columns: {sorted(required - set(rows[0]))}")
    return {row["comparison_id"]: row for row in rows if row.get("comparison_id")}


PROFILE_FIELDS = (
    "position",
    "position_other",
    "field",
    "native_language",
    "native_language_other",
    "english",
    "reads_chinese",
    "long_writing",
)


def _read_answers(
    paths: Iterable[Path],
) -> tuple[dict[tuple[str, str], dict[str, str]], dict[str, dict[str, str]]]:
    answers: dict[tuple[str, str], dict[str, str]] = {}
    profiles: dict[str, dict[str, str]] = {}
    for path in paths:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                comparison_id = (row.get("comparison_id") or "").strip()
                preference = (row.get("preference") or "").strip()
                if not comparison_id or not preference:
                    continue
                if preference not in {"A", "B", "tie"}:
                    raise ValueError(f"{path}: invalid preference {preference!r}")
                annotator = (row.get("annotator_id") or path.stem).strip()
                if not annotator:
                    raise ValueError(f"{path}: annotator_id is required")
                seed = (row.get("presentation_seed") or "").strip()
                if seed and not seed.isdigit():
                    raise ValueError(f"{path}: presentation_seed must be an integer")
                key = (annotator, comparison_id)
                if key in answers:
                    raise ValueError(
                        f"duplicate answer for {annotator!r}, {comparison_id!r}"
                    )
                answers[key] = {
                    "annotator_id": annotator,
                    "comparison_id": comparison_id,
                    "preference": preference,
                    "presentation_seed": seed,
                    "adjudication_status": (
                        row.get("adjudication_status") or ""
                    ).strip(),
                }
                if annotator not in profiles:
                    profile = {
                        field: (row.get(f"profile_{field}") or "").strip()
                        for field in PROFILE_FIELDS
                    }
                    profile["consent"] = (row.get("consent") or "").strip()
                    if any(profile.values()):
                        profiles[annotator] = profile
    return answers, profiles


def _condition_a(key: dict[str, str], annotator: str) -> str | None:
    suffix = annotator.rsplit("-", 1)[-1]
    value = key.get(f"condition_a_{suffix}")
    return value or key.get("condition_a")


def _metric_report(ratings: dict[str, list[str]]) -> dict[str, float | int]:
    agreement = raw_agreement(ratings)
    report: dict[str, float | int] = {
        "comparisons": len(ratings),
        "ratings": sum(len(values) for values in ratings.values()),
        "raw_agreement": agreement,
        "disagreement": 1 - agreement if agreement is not None else None,
        "krippendorff_alpha": krippendorff_alpha(ratings),
        "fleiss_kappa": fleiss_kappa(ratings),
    }
    return report


def _wilson(wins: int, losses: int) -> tuple[float | None, float | None]:
    experiments_src = Path(__file__).resolve().parents[2] / "experiments" / "src"
    if str(experiments_src) not in sys.path:
        sys.path.insert(0, str(experiments_src))
    from agentic_cogwriter.analysis.aggregate import wilson_interval

    return wilson_interval(wins, losses)


def preference(values: Iterable[str], left: str, right: str) -> dict[str, object]:
    """W/L/T for the left condition, with the win rate W/(W+L) and its Wilson interval."""
    counts = Counter(values)
    wins, losses, ties = counts[left], counts[right], counts["tie"]
    return {
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "win_rate": wins / (wins + losses) if wins + losses else None,
        "wilson_95": list(_wilson(wins, losses)),
    }


def _agreement(first: list[str], second: list[str]) -> dict[str, object]:
    return {
        "comparisons": len(first),
        "agreement": sum(a == b for a, b in zip(first, second)) / len(first)
        if first
        else None,
        "cohen_kappa": cohen_kappa(first, second) if first else None,
    }


def _paired(left: dict[str, str], right: dict[str, str]) -> tuple[list[str], list[str]]:
    shared = sorted(set(left) & set(right))
    return [left[item] for item in shared], [right[item] for item in shared]


def _mean(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return sum(present) / len(present) if present else None


def _subset_report(
    by_annotator: dict[str, dict[str, str]], keys: dict[str, dict[str, str]]
) -> dict[str, object]:
    ratings: dict[str, list[str]] = {}
    for comparison_id in keys:
        values = [
            rows[comparison_id]
            for _, rows in sorted(by_annotator.items())
            if comparison_id in rows
        ]
        if values:
            ratings[comparison_id] = values
    majority_votes = {
        comparison_id: majority(values) or "tie"
        for comparison_id, values in ratings.items()
    }

    pairs: dict[str, dict[str, object]] = {}
    annotators = sorted(by_annotator)
    for index, first in enumerate(annotators):
        for second in annotators[index + 1 :]:
            pairs[f"{first}|{second}"] = _agreement(
                *_paired(by_annotator[first], by_annotator[second])
            )
    human = _metric_report(ratings)
    human["annotator_pairs"] = pairs
    human["mean_pairwise_agreement"] = _mean(
        [pair["agreement"] for pair in pairs.values()]
    )
    human["mean_pairwise_cohen_kappa"] = _mean(
        [pair["cohen_kappa"] for pair in pairs.values()]
    )

    judges: dict[str, dict[str, object]] = {}
    for family, field in (
        ("same-family", "same_family_decision"),
        ("cross-family", "cross_family_decision"),
    ):
        decisions = {
            item: keys[item][field] for item in ratings if keys[item].get(field)
        }
        per_annotator = {
            annotator: _agreement(*_paired(decisions, rows))
            for annotator, rows in sorted(by_annotator.items())
        }
        judges[family] = {
            "annotators": per_annotator,
            "mean_agreement": _mean(
                [value["agreement"] for value in per_annotator.values()]
            ),
            "mean_cohen_kappa": _mean(
                [value["cohen_kappa"] for value in per_annotator.values()]
            ),
            "majority": _agreement(*_paired(decisions, majority_votes)),
        }

    preferences: dict[str, dict[str, object]] = {}
    for contrast in sorted({keys[item]["contrast"] for item in ratings}):
        left, right = parse_contrast(contrast)
        ids = [item for item in ratings if keys[item]["contrast"] == contrast]
        preferences[contrast] = {
            "annotators": {
                annotator: preference(
                    (rows[item] for item in ids if item in rows), left, right
                )
                for annotator, rows in sorted(by_annotator.items())
            },
            "pooled_judgments": preference(
                (value for item in ids for value in ratings[item]), left, right
            ),
            "majority": preference((majority_votes[item] for item in ids), left, right),
            "judges": {
                family: preference(
                    (keys[item][field] for item in ids if keys[item].get(field)),
                    left,
                    right,
                )
                for family, field in (
                    ("same-family", "same_family_decision"),
                    ("cross-family", "cross_family_decision"),
                )
            },
        }
    return {
        "human": human,
        "automatic_judge_agreement": judges,
        "preference": preferences,
    }


def score(
    answer_paths: list[Path], key_path: Path, judge_paths: list[Path] | None = None
) -> str:
    del judge_paths  # Automatic decisions are frozen in key.csv with the packet.
    keys = _read_key(key_path)
    answers, profiles = _read_answers(answer_paths)
    by_annotator: dict[str, dict[str, str]] = defaultdict(dict)
    for answer in answers.values():
        comparison_id = answer["comparison_id"]
        if comparison_id not in keys:
            continue
        key = keys[comparison_id]
        condition = human_to_condition(
            answer["preference"], key, _condition_a(key, answer["annotator_id"])
        )
        by_annotator[answer["annotator_id"]][comparison_id] = condition

    report: dict[str, object] = {
        "overall": _subset_report(by_annotator, keys),
        "breakdowns": {},
        "annotators": sorted(by_annotator),
        "profiles": profiles,
    }
    dimensions = (
        "benchmark",
        "mixed_language",
        "contrast",
        "output_length_gap",
        "automatic_decision_margin",
    )
    breakdowns: dict[str, dict[str, object]] = {}
    for dimension in (
        name for name in dimensions if any(name in key for key in keys.values())
    ):
        groups: dict[str, dict[str, dict[str, str]]] = defaultdict(
            lambda: defaultdict(dict)
        )
        for annotator, rows in by_annotator.items():
            for comparison_id, value in rows.items():
                groups[keys[comparison_id].get(dimension, "unknown")][annotator][
                    comparison_id
                ] = value
        breakdowns[dimension] = {
            group: _subset_report(group_rows, keys)
            for group, group_rows in sorted(groups.items())
        }
    report["breakdowns"] = breakdowns
    return json.dumps(report, indent=2, sort_keys=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("answers", nargs="+", type=Path)
    parser.add_argument("--key", required=True, type=Path)
    parser.add_argument("--judge-records", nargs="*", type=Path, default=[])
    args = parser.parse_args()
    print(score(args.answers, args.key, args.judge_records), end="")


if __name__ == "__main__":
    main()
