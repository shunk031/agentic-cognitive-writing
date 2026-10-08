#!/usr/bin/env python3
"""Score human-validation answer sheets and automatic-judge agreement."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


def parse_contrast(value: str) -> tuple[str, str]:
    left, separator, right = value.partition(":")
    if not separator or not left or not right:
        raise ValueError(f"invalid contrast: {value!r}")
    return left, right


def human_to_condition(preference: str, key: dict[str, str], condition_a: str | None = None) -> str:
    if preference == "tie":
        return "tie"
    if preference not in {"A", "B"}:
        raise ValueError(f"invalid preference: {preference!r}")
    condition_a = condition_a or key.get("condition_a", "")
    if not condition_a:
        raise ValueError("condition_a is required to map a human preference")
    left, right = parse_contrast(key["contrast"])
    return condition_a if preference == "A" else (right if left == condition_a else left)


def cohen_kappa(first: list[str], second: list[str]) -> float:
    if len(first) != len(second) or not first:
        raise ValueError("Cohen's kappa needs equally sized non-empty samples")
    observed = sum(a == b for a, b in zip(first, second)) / len(first)
    left = Counter(first)
    right = Counter(second)
    expected = sum(left[c] * right[c] for c in set(left) | set(right)) / (len(first) ** 2)
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
        sum(count * (total_values - count) for count in overall.values()) / expected_pairs
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


def _read_answers(paths: Iterable[Path]) -> dict[tuple[str, str], dict[str, str]]:
    answers: dict[tuple[str, str], dict[str, str]] = {}
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
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
                    raise ValueError(f"duplicate answer for {annotator!r}, {comparison_id!r}")
                answers[key] = {
                    "annotator_id": annotator,
                    "comparison_id": comparison_id,
                    "preference": preference,
                    "presentation_seed": seed,
                    "adjudication_status": (row.get("adjudication_status") or "").strip(),
                }
    return answers


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


def _automatic_agreement(
    ratings: dict[str, list[str]], keys: dict[str, dict[str, str]]
) -> dict[str, dict[str, float | int]]:
    result: dict[str, dict[str, float | int]] = {}
    for family, field in (("same-family", "same_family_decision"), ("cross-family", "cross_family_decision")):
        matches = total = 0
        for comparison_id, values in ratings.items():
            decision = keys[comparison_id].get(field, "")
            human = majority(values)
            if decision and human is not None:
                total += 1
                matches += decision == human
        result[family] = {
            "matches": matches,
            "comparisons": total,
        "agreement": matches / total if total else None,
        }
    return result


def _subset_report(
    ratings: dict[str, list[str]], keys: dict[str, dict[str, str]]
) -> dict[str, object]:
    return {
        "human": _metric_report(ratings),
        "automatic_judge_agreement": _automatic_agreement(ratings, keys),
    }


def score(answer_paths: list[Path], key_path: Path, judge_paths: list[Path] | None = None) -> str:
    del judge_paths  # Automatic decisions are frozen in key.csv with the packet.
    keys = _read_key(key_path)
    answers = _read_answers(answer_paths)
    by_annotator: dict[str, dict[str, str]] = defaultdict(dict)
    for answer in answers.values():
        comparison_id = answer["comparison_id"]
        if comparison_id not in keys:
            continue
        key = keys[comparison_id]
        condition = human_to_condition(answer["preference"], key, _condition_a(key, answer["annotator_id"]))
        by_annotator[answer["annotator_id"]][comparison_id] = condition

    ratings: dict[str, list[str]] = {}
    for comparison_id in keys:
        values = [by_annotator[annotator][comparison_id] for annotator in sorted(by_annotator) if comparison_id in by_annotator[annotator]]
        if values:
            ratings[comparison_id] = values

    report: dict[str, object] = {
        "overall": _subset_report(ratings, keys),
        "breakdowns": {},
        "annotators": sorted(by_annotator),
    }
    dimensions = ("benchmark", "contrast", "output_length_gap", "automatic_decision_margin")
    breakdowns: dict[str, dict[str, object]] = {}
    for dimension in dimensions:
        groups: dict[str, dict[str, list[str]]] = defaultdict(dict)
        for comparison_id, values in ratings.items():
            group = keys[comparison_id].get(dimension, "unknown")
            groups[group][comparison_id] = values
        breakdowns[dimension] = {
            group: _subset_report(group_ratings, keys)
            for group, group_ratings in sorted(groups.items())
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
