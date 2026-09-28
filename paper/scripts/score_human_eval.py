#!/usr/bin/env python3
"""Score blinded human answer sheets against pairwise judge records."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


def _load_canonical_runs(root: Path) -> list[Any]:
    project_root = Path(__file__).resolve().parents[2]
    experiments_src = project_root / "experiments" / "src"
    if str(experiments_src) not in sys.path:
        sys.path.insert(0, str(experiments_src))
    from agentic_cogwriter.analysis.common import select_canonical_runs

    return select_canonical_runs([root])


def parse_contrast(value: str) -> tuple[str, str]:
    left, separator, right = value.partition(":")
    if not separator or not left or not right:
        raise ValueError(f"invalid contrast: {value!r}")
    return left, right


def human_to_condition(preference: str, key: dict[str, str]) -> str:
    if preference == "tie":
        return "tie"
    if preference == "A":
        return key["condition_a"]
    left, right = parse_contrast(key["contrast"])
    return right if left == key["condition_a"] else left


def _record_to_condition(record: dict[str, Any], contrast: str) -> str | None:
    left, right = parse_contrast(contrast)
    presentation = record.get("presentation")
    winner = record.get("winner")
    if winner == "tie":
        return "tie"
    if presentation not in {"A|B", "B|A"} or winner not in {"A", "B"}:
        return None
    a4_position = "A" if presentation == "A|B" else "B"
    winner_condition = left if winner == a4_position else right
    return winner_condition


def judge_condition(records: Iterable[dict[str, Any]], contrast: str) -> str | None:
    values = [
        value
        for record in records
        if (value := _record_to_condition(record, contrast)) is not None
    ]
    if not values:
        return None
    counts = Counter(values)
    highest = max(counts.values())
    winners = [value for value, count in counts.items() if count == highest]
    return winners[0] if len(winners) == 1 else "tie"


def cohen_kappa(first: list[str], second: list[str]) -> float:
    if len(first) != len(second) or not first:
        raise ValueError("Cohen's kappa needs equally sized non-empty samples")
    observed = sum(a == b for a, b in zip(first, second)) / len(first)
    left = Counter(first)
    right = Counter(second)
    categories = set(left) | set(right)
    expected = sum(left[c] * right[c] for c in categories) / (len(first) ** 2)
    return 1.0 if expected == 1.0 and observed == 1.0 else (observed - expected) / (1 - expected)


def _read_key(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = {"pair_id", "prompt_id", "benchmark", "contrast", "condition_a"}
    if rows and not required <= set(rows[0]):
        raise ValueError(f"key is missing columns: {sorted(required - set(rows[0]))}")
    return {row["pair_id"]: row for row in rows if row.get("pair_id")}


def _read_answers(paths: Iterable[Path]) -> dict[str, dict[str, str]]:
    answers: dict[str, dict[str, str]] = {}
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                pair_id = (row.get("pair_id") or "").strip()
                preference = (row.get("preference") or "").strip()
                if not pair_id or not preference:
                    continue
                if preference not in {"A", "B", "tie"}:
                    raise ValueError(f"{path}: invalid preference {preference!r}")
                confidence = (row.get("confidence") or "").strip()
                if confidence and confidence not in {"1", "2", "3"}:
                    raise ValueError(f"{path}: confidence must be 1, 2, or 3")
                annotator = (row.get("annotator") or path.stem).strip()
                key = f"{annotator}\0{pair_id}"
                if key in answers:
                    raise ValueError(f"duplicate answer for {annotator!r}, {pair_id!r}")
                answers[key] = {
                    "annotator": annotator,
                    "pair_id": pair_id,
                    "preference": preference,
                }
    return answers


def _judge_files_for_root(root: Path, key_rows: Iterable[dict[str, str]]) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    canonical = {
        (record.benchmark, record.condition, record.prompt): record
        for record in _load_canonical_runs(root)
    }
    found: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in key_rows:
        left, right = parse_contrast(row["contrast"])
        a4 = canonical.get((row["benchmark"], "A4", row["prompt_id"]))
        other = right if left == "A4" else left
        if a4 is None or canonical.get((row["benchmark"], other, row["prompt_id"])) is None:
            continue
        candidates = sorted(
            a4.path.glob(f"scores/pairwise/*/{row['prompt_id']}-{other}/scores.jsonl"),
            key=lambda path: ("gpt-5.6-sol-pairwise-v1" not in str(path), str(path)),
        )
        if not candidates:
            continue
        selected = candidates[0]
        records = [json.loads(line) for line in selected.read_text(encoding="utf-8").splitlines() if line.strip()]
        found[(row["benchmark"], row["prompt_id"], row["contrast"])] = records
    return found


def _judge_files_direct(paths: Iterable[Path], key_rows: Iterable[dict[str, str]]) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    wanted = {(row["benchmark"], row["prompt_id"], row["contrast"]) for row in key_rows}
    found: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for path in paths:
        files = [path] if path.is_file() else sorted(path.rglob("scores.jsonl"))
        for file in files:
            records = [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines() if line.strip()]
            if not records:
                continue
            prompt_id = str(records[0].get("prompt_id", ""))
            parent = file.parent.name
            other = parent.rsplit("-", 1)[-1]
            benchmark = next((row["benchmark"] for row in key_rows if row["prompt_id"] == prompt_id), "")
            contrast = f"A4:{other}"
            key = (benchmark, prompt_id, contrast)
            if key in wanted:
                found[key] = records
    return found


def _judge_map(paths: Iterable[Path], key_rows: list[dict[str, str]]) -> dict[tuple[str, str, str], str | None]:
    result: dict[tuple[str, str, str], str | None] = {}
    for path in paths:
        if path.is_dir() and (path / "DoLoMiTes").is_dir():
            records = _judge_files_for_root(path, key_rows)
        else:
            records = _judge_files_direct([path], key_rows)
        for key, rows in records.items():
            result[key] = judge_condition(rows, key[2])
    return result


def _agreement(first: list[str], second: list[str]) -> float:
    return sum(a == b for a, b in zip(first, second)) / len(first) if first else float("nan")


def score(answer_paths: list[Path], key_path: Path, judge_paths: list[Path]) -> str:
    key = _read_key(key_path)
    answers = _read_answers(answer_paths)
    judges = _judge_map(judge_paths, list(key.values()))
    by_annotator: dict[str, dict[str, str]] = defaultdict(dict)
    for answer in answers.values():
        if answer["pair_id"] in key:
            by_annotator[answer["annotator"]][answer["pair_id"]] = answer["preference"]

    lines = []
    judge_pairs: dict[str, str] = {}
    for pair_id, row in key.items():
        judge_pairs[pair_id] = judges.get((row["benchmark"], row["prompt_id"], row["contrast"]), "") or ""
    for annotator in sorted(by_annotator):
        compared = []
        for pair_id, preference in by_annotator[annotator].items():
            if judge_pairs.get(pair_id):
                compared.append(human_to_condition(preference, key[pair_id]) == judge_pairs[pair_id])
        lines.append(f"{annotator} vs judge: {sum(compared)}/{len(compared)} ({_agreement(compared, [True] * len(compared)):.1%})")

    annotators = sorted(by_annotator)
    for index, first_name in enumerate(annotators):
        for second_name in annotators[index + 1 :]:
            common = sorted(set(by_annotator[first_name]) & set(by_annotator[second_name]))
            first = [by_annotator[first_name][pair] for pair in common]
            second = [by_annotator[second_name][pair] for pair in common]
            lines.append(f"{first_name} vs {second_name}: {sum(a == b for a, b in zip(first, second))}/{len(common)} ({_agreement(first, second):.1%})")
            if common:
                lines.append(f"Cohen's kappa ({first_name}, {second_name}): {cohen_kappa(first, second):.4f}")
    if not lines:
        lines.append("No completed answers were found.")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("answers", nargs="+", type=Path)
    parser.add_argument("--key", required=True, type=Path)
    parser.add_argument("--judge-records", required=True, nargs="+", type=Path)
    args = parser.parse_args()
    print(score(args.answers, args.key, args.judge_records), end="")


if __name__ == "__main__":
    main()
