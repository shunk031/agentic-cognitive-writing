#!/usr/bin/env python3
"""Create a blinded human-evaluation packet from canonical completed runs."""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path
from typing import Any


CONTRASTS = (("A4", "A5"), ("A4", "A1"))
BENCHMARKS = ("DoLoMiTes", "HelloBench", "WritingBench")


def _canonical_runs(root: Path) -> dict[tuple[str, str, str], Any]:
    project_root = Path(__file__).resolve().parents[2]
    experiments_src = project_root / "experiments" / "src"
    if str(experiments_src) not in sys.path:
        sys.path.insert(0, str(experiments_src))
    from agentic_cogwriter.analysis.common import select_canonical_runs

    return {
        (record.benchmark, record.condition, record.prompt): record
        for record in select_canonical_runs([root])
        if record.status == "completed"
    }


def _manifest_rows(project_root: Path) -> dict[tuple[str, str], dict[str, Any]]:
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for benchmark in BENCHMARKS:
        path = project_root / "experiments" / "prompts" / "manifests" / f"{benchmark.lower()}.jsonl"
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    row = json.loads(line)
                    rows[(benchmark, row["prompt_id"])] = row
    return rows


def _judge_rows(record: Any, prompt_id: str, other: str) -> list[dict[str, Any]]:
    paths = sorted(
        record.path.glob(f"scores/pairwise/*/{prompt_id}-{other}/scores.jsonl"),
        key=lambda path: ("gpt-5.6-sol-pairwise-v1" not in str(path), str(path)),
    )
    if not paths:
        return []
    return [
        json.loads(line)
        for line in paths[0].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _candidates(root: Path) -> list[dict[str, Any]]:
    canonical = _canonical_runs(root)
    result = []
    for benchmark in BENCHMARKS:
        prompts = sorted(
            {
                prompt
                for (candidate_benchmark, condition, prompt) in canonical
                if candidate_benchmark == benchmark and condition == "A4"
            }
        )
        for left, right in CONTRASTS:
            for prompt in prompts:
                left_run = canonical.get((benchmark, left, prompt))
                right_run = canonical.get((benchmark, right, prompt))
                if left_run is None or right_run is None:
                    continue
                output_a = left_run.path / "output.normalized.txt"
                output_b = right_run.path / "output.normalized.txt"
                if not output_a.is_file() or not output_b.is_file():
                    continue
                rows = _judge_rows(left_run, prompt, right)
                if not any(row.get("winner") in {"A", "B", "tie"} for row in rows):
                    continue
                result.append(
                    {
                        "benchmark": benchmark,
                        "prompt_id": prompt,
                        "contrast": f"{left}:{right}",
                        "left": left,
                        "right": right,
                        "left_output": output_a,
                        "right_output": output_b,
                    }
                )
    return result


def _pick(candidates: list[dict[str, Any]], count: int, rng: random.Random) -> list[dict[str, Any]]:
    by_benchmark = {benchmark: [row for row in candidates if row["benchmark"] == benchmark] for benchmark in BENCHMARKS}
    if all(len(rows) >= count // len(BENCHMARKS) for rows in by_benchmark.values()) and count % len(BENCHMARKS) == 0:
        selected = []
        per_benchmark = count // len(BENCHMARKS)
        for benchmark in BENCHMARKS:
            rows = by_benchmark[benchmark][:]
            rng.shuffle(rows)
            selected.extend(rows[:per_benchmark])
        rng.shuffle(selected)
        return selected
    if len(candidates) < count:
        raise RuntimeError(f"only {len(candidates)} eligible candidates, need {count}")
    return rng.sample(candidates, count)


def _write_pair(path: Path, pair_id: str, row: dict[str, Any], manifest: dict[str, Any], condition_a: str, rng: random.Random) -> None:
    left = row["left"]
    right = row["right"]
    outputs = {
        left: row["left_output"].read_text(encoding="utf-8"),
        right: row["right_output"].read_text(encoding="utf-8"),
    }
    output_a, output_b = outputs[condition_a], outputs[right if condition_a == left else left]
    context = manifest.get("supplied_context")
    if not isinstance(context, str) or not context:
        context = "No separate supplied context was recorded in the prompt manifest."
    path.write_text(
        "\n".join(
            [
                f"# Pair {pair_id}",
                "",
                "## Assignment",
                "",
                str(manifest.get("prompt_text", "")),
                "",
                "## Supplied context",
                "",
                context,
                "",
                "## Response A",
                "",
                output_a or "(empty response)",
                "",
                "## Response B",
                "",
                output_b or "(empty response)",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _select_candidates(candidates: list[dict[str, Any]], rng: random.Random) -> dict[str, list[dict[str, Any]]]:
    selected: dict[str, list[dict[str, Any]]] = {}
    used: set[tuple[str, str]] = set()
    for contrast in CONTRASTS:
        contrast_name = f"{contrast[0]}:{contrast[1]}"
        pool = [row for row in candidates if row["contrast"] == contrast_name]
        fresh = [row for row in pool if (row["benchmark"], row["prompt_id"]) not in used]
        picked = _pick(fresh if len(fresh) >= 30 else pool, 30, rng)
        selected[contrast_name] = picked
        used.update((row["benchmark"], row["prompt_id"]) for row in picked)
    return selected


def generate(runs_root: Path, seed: int, output_root: Path) -> dict[str, dict[str, int]]:
    project_root = Path(__file__).resolve().parents[2]
    manifests = _manifest_rows(project_root)
    rng = random.Random(seed)
    candidates = _candidates(runs_root)
    selected = _select_candidates(candidates, rng)

    pairs_dir = output_root / "pairs"
    pairs_dir.mkdir(parents=True, exist_ok=True)
    key_rows = []
    summary = {contrast: {benchmark: 0 for benchmark in BENCHMARKS} for contrast in selected}
    pair_number = 1
    for contrast in CONTRASTS:
        contrast_name = f"{contrast[0]}:{contrast[1]}"
        for row in selected[contrast_name]:
            pair_id = f"pair-{pair_number:03d}"
            condition_a = row["left"] if rng.randrange(2) == 0 else row["right"]
            manifest = manifests[(row["benchmark"], row["prompt_id"])]
            _write_pair(pairs_dir / f"{pair_id}.md", pair_id, row, manifest, condition_a, rng)
            key_rows.append(
                {
                    "pair_id": pair_id,
                    "prompt_id": row["prompt_id"],
                    "benchmark": row["benchmark"],
                    "contrast": contrast_name,
                    "condition_a": condition_a,
                }
            )
            summary[contrast_name][row["benchmark"]] += 1
            pair_number += 1

    with (output_root / "key.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["pair_id", "prompt_id", "benchmark", "contrast", "condition_a"])
        writer.writeheader()
        writer.writerows(key_rows)
    with (output_root / "answers-template.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["pair_id", "annotator", "preference", "confidence", "note"])
    (output_root / "INSTRUCTIONS.md").write_text(
        """# Human evaluation

Read each assignment and both responses. Judge the overall quality of each response for the assignment. Consider correctness, relevance, completeness, clarity, and usefulness together.

The response labels are blinded. Record whether Response A, Response B, or neither response is better. Use `tie` when the responses are equal in overall quality. Record confidence as 1 (low), 2 (medium), or 3 (high), and add a short note when a reason needs recording.

There is no time limit. Work independently and use only the assignment, supplied context, and responses in the packet. Do not open `key.csv`; the file contains the hidden condition mapping.
""",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("runs_root", type=Path)
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "human-eval")
    args = parser.parse_args()
    summary = generate(args.runs_root, args.seed, args.output)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
