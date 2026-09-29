#!/usr/bin/env python3
"""Create a blinded, stratified human-evaluation packet."""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


CONTRASTS = (("A4", "A1"), ("A7", "A4"), ("A4", "A3"))
BENCHMARKS = ("DoLoMiTes", "HelloBench", "WritingBench")
ANNOTATORS = ("annotator-1", "annotator-2", "annotator-3")
SAME_FAMILY = "same-family"
CROSS_FAMILY = "cross-family"
PROMPT_LENGTHS = ("short", "medium", "long")
RATIO_BINS = (1.05, 1.10, 1.25, 1.50, 2.00)


def _source_modules() -> None:
    experiments_src = Path(__file__).resolve().parents[2] / "experiments" / "src"
    if str(experiments_src) not in sys.path:
        sys.path.insert(0, str(experiments_src))


def _output_units(text: str) -> int:
    _source_modules()
    from agentic_cogwriter.runner.budget import estimate_output_tokens

    return estimate_output_tokens(text)


def _ratio_bin(ratio: float) -> str:
    lower = 1.0
    for upper in RATIO_BINS:
        if ratio < upper:
            return f"{lower:.2f}-{upper:.2f}"
        lower = upper
    return f"{lower:.2f}+"


def _canonical_runs(root: Path) -> dict[tuple[str, str, str], Any]:
    _source_modules()
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


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _judge_paths(first: Any, second: Any, prompt_id: str) -> list[Path]:
    paths: list[Path] = []
    for source, other in ((first, second.condition), (second, first.condition)):
        paths.extend(source.path.glob(f"scores/pairwise/*/{prompt_id}-{other}/scores.jsonl"))
    return sorted(set(paths), key=lambda path: ("gpt-5.6-sol" not in str(path), str(path)))


def _order_mapping(manifest: dict[str, Any]) -> dict[str, tuple[int, int]]:
    tournament = manifest.get("tournament")
    items = tournament.get("order_mapping", []) if isinstance(tournament, dict) else []
    mapping: dict[str, tuple[int, int]] = {}
    for item in items:
        if not isinstance(item, dict) or item.get("presentation") not in {"A|B", "B|A"}:
            continue
        mapping[item["presentation"]] = (
            0 if item.get("first_output") == "first_run" else 1,
            0 if item.get("second_output") == "first_run" else 1,
        )
    return mapping or {"A|B": (0, 1), "B|A": (1, 0)}


def _decision(
    score_path: Path,
    first: Any,
    second: Any,
    left: str,
    right: str,
) -> tuple[str, str, list[str]] | None:
    manifest = _read_json(score_path.with_name("scores-manifest.json"))
    source_hashes = {
        str(item.get("run_manifest_sha256")): index
        for index, item in enumerate(manifest.get("source_runs", []))
        if isinstance(item, dict)
    }
    run_hashes: dict[str, int] = {}
    _source_modules()
    from agentic_cogwriter.runner.hashing import sha256_file

    for index, run in enumerate((first, second)):
        run_hashes["sha256:" + sha256_file(run.path / "run-manifest.json")] = index
    source_order = [run_hashes.get(digest) for digest in source_hashes]
    if len(source_order) != 2 or any(index is None for index in source_order):
        return None
    source_order = [int(index) for index in source_order]
    records = [
        json.loads(line)
        for line in score_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    outcomes: dict[str, str] = {}
    for record in records:
        presentation = record.get("presentation")
        winner = record.get("winner")
        if presentation not in {"A|B", "B|A"} or winner not in {"A", "B", "tie"}:
            continue
        if winner == "tie":
            outcomes[presentation] = "tie"
            continue
        mapping = _order_mapping(manifest).get(presentation, (0, 1))
        source_index = mapping[0 if winner == "A" else 1]
        condition_index = source_order[source_index]
        outcomes[presentation] = (left, right)[condition_index]
    if set(outcomes) != {"A|B", "B|A"}:
        return None
    values = (outcomes["A|B"], outcomes["B|A"])
    collapsed = values[0] if values[0] == values[1] else "tie"
    judge = manifest.get("judge")
    judge_id = str(judge.get("judge_id", "")) if isinstance(judge, dict) else ""
    mode = manifest.get("family_audit", {}).get("mode")
    family = SAME_FAMILY if mode == "exploratory-same-family" or "gpt-5.6-sol" in judge_id else CROSS_FAMILY
    return family, collapsed, list(values)


def _judge_decisions(first: Any, second: Any, prompt_id: str, left: str, right: str) -> dict[str, dict[str, Any]]:
    decisions: dict[str, dict[str, Any]] = {}
    for path in _judge_paths(first, second, prompt_id):
        value = _decision(path, first, second, left, right)
        if value is not None and value[0] not in decisions:
            decisions[value[0]] = {"decision": value[1], "votes": value[2]}
    return decisions


def _assign_prompt_strata(rows: list[dict[str, Any]]) -> None:
    ordered = sorted(rows, key=lambda row: (row["prompt_length_units"], row["prompt_id"]))
    for index, row in enumerate(ordered):
        row["prompt_length"] = PROMPT_LENGTHS[min(2, index * 3 // len(ordered))]


def _candidates(root: Path, manifests: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    canonical = _canonical_runs(root)
    result: list[dict[str, Any]] = []
    for benchmark in BENCHMARKS:
        for left, right in CONTRASTS:
            rows: list[dict[str, Any]] = []
            for (candidate_benchmark, condition, prompt_id), left_run in canonical.items():
                if candidate_benchmark != benchmark or condition != left:
                    continue
                right_run = canonical.get((benchmark, right, prompt_id))
                manifest = manifests.get((benchmark, prompt_id))
                if right_run is None or manifest is None:
                    continue
                output_paths = {
                    left: left_run.path / "output.normalized.txt",
                    right: right_run.path / "output.normalized.txt",
                }
                if not all(path.is_file() for path in output_paths.values()):
                    continue
                decisions = _judge_decisions(left_run, right_run, prompt_id, left, right)
                if SAME_FAMILY not in decisions:
                    continue
                lengths = {
                    condition_name: int(run.manifest.get("output_units_used") or _output_units(output_paths[condition_name].read_text(encoding="utf-8")))
                    for condition_name, run in ((left, left_run), (right, right_run))
                }
                ratio = max(lengths.values()) / min(lengths.values()) if min(lengths.values()) > 0 else 0
                if ratio <= 0:
                    continue
                decisions_for_margin = list(decisions[SAME_FAMILY]["votes"])
                if CROSS_FAMILY in decisions:
                    decisions_for_margin.append(decisions[CROSS_FAMILY]["decision"])
                counts = Counter(decisions_for_margin)
                ordered = sorted(counts.values(), reverse=True)
                margin = ordered[0] - (ordered[1] if len(ordered) > 1 else 0)
                prompt_text = str(manifest.get("prompt_text", ""))
                rows.append(
                    {
                        "benchmark": benchmark,
                        "prompt_id": prompt_id,
                        "contrast": f"{left}:{right}",
                        "left": left,
                        "right": right,
                        "left_output": output_paths[left],
                        "right_output": output_paths[right],
                        "prompt_length_units": _output_units(prompt_text),
                        "output_length_left": lengths[left],
                        "output_length_right": lengths[right],
                        "output_length_gap": _ratio_bin(ratio),
                        "same_family_decision": decisions[SAME_FAMILY]["decision"],
                        "cross_family_decision": decisions.get(CROSS_FAMILY, {}).get("decision", ""),
                        "automatic_decision_margin": str(margin),
                    }
                )
            if rows:
                _assign_prompt_strata(rows)
                result.extend(rows)
    return result


def _stratified_pick(rows: list[dict[str, Any]], count: int, rng: random.Random) -> list[dict[str, Any]]:
    if len(rows) < count:
        raise RuntimeError(f"only {len(rows)} eligible candidates, need {count}")
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["output_length_gap"], row["automatic_decision_margin"])].append(row)
    total = len(rows)
    quotas = {group: int(count * len(values) / total) for group, values in groups.items()}
    remaining = count - sum(quotas.values())
    ranked = sorted(
        groups,
        key=lambda group: (-(count * len(groups[group]) / total - quotas[group]), group),
    )
    for group in ranked[:remaining]:
        quotas[group] += 1
    selected: list[dict[str, Any]] = []
    for group in sorted(groups):
        values = groups[group][:]
        rng.shuffle(values)
        selected.extend(values[: quotas[group]])
    rng.shuffle(selected)
    return selected


def _select_candidates(candidates: list[dict[str, Any]], rng: random.Random) -> dict[str, list[dict[str, Any]]]:
    selected: dict[str, list[dict[str, Any]]] = {}
    used: set[tuple[str, str]] = set()
    per_benchmark = 24
    for left, right in CONTRASTS:
        contrast = f"{left}:{right}"
        selected_rows: list[dict[str, Any]] = []
        for benchmark in BENCHMARKS:
            pool = [row for row in candidates if row["contrast"] == contrast and row["benchmark"] == benchmark]
            benchmark_rows: list[dict[str, Any]] = []
            for prompt_length in PROMPT_LENGTHS:
                prompt_pool = [row for row in pool if row["prompt_length"] == prompt_length]
                fresh = [row for row in prompt_pool if (benchmark, row["prompt_id"]) not in used]
                benchmark_rows.extend(_stratified_pick(fresh if len(fresh) >= 8 else prompt_pool, 8, rng))
            selected_rows.extend(benchmark_rows)
        selected[contrast] = selected_rows
        used.update((row["benchmark"], row["prompt_id"]) for row in selected_rows)
    return selected


def _write_pair(path: Path, comparison_id: str, row: dict[str, Any], manifest: dict[str, Any], condition_a: str, presentation_seed: int) -> None:
    left = row["left"]
    right = row["right"]
    outputs = {
        left: row["left_output"].read_text(encoding="utf-8"),
        right: row["right_output"].read_text(encoding="utf-8"),
    }
    condition_b = right if condition_a == left else left
    context = manifest.get("supplied_context")
    if not isinstance(context, str) or not context:
        context = "No separate supplied context was recorded in the prompt manifest."
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                f"# Comparison {comparison_id}",
                "",
                f"Presentation seed: {presentation_seed}",
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
                outputs[condition_a] or "(empty response)",
                "",
                "## Response B",
                "",
                outputs[condition_b] or "(empty response)",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _answer_fields() -> list[str]:
    return ["comparison_id", "annotator_id", "preference", "reason", "presentation_seed", "adjudication_status"]


def generate(runs_root: Path, seed: int, output_root: Path) -> dict[str, dict[str, int]]:
    project_root = Path(__file__).resolve().parents[2]
    manifests = _manifest_rows(project_root)
    rng = random.Random(seed)
    selected = _select_candidates(_candidates(runs_root, manifests), rng)

    pairs_dir = output_root / "pairs"
    pairs_dir.mkdir(parents=True, exist_ok=True)
    for old_pair in pairs_dir.glob("pair-*.md"):
        old_pair.unlink()
    for annotator in ANNOTATORS:
        annotator_dir = pairs_dir / annotator
        annotator_dir.mkdir(parents=True, exist_ok=True)
        for old_pair in annotator_dir.glob("comparison-*.md"):
            old_pair.unlink()

    key_rows: list[dict[str, str]] = []
    answer_rows: dict[str, list[dict[str, str]]] = {annotator: [] for annotator in ANNOTATORS}
    summary = {f"{left}:{right}": {benchmark: 0 for benchmark in BENCHMARKS} for left, right in CONTRASTS}
    comparison_number = 1
    for left, right in CONTRASTS:
        contrast = f"{left}:{right}"
        for row in selected[contrast]:
            comparison_id = f"comparison-{comparison_number:03d}"
            key_row = {
                "comparison_id": comparison_id,
                "prompt_id": row["prompt_id"],
                "benchmark": row["benchmark"],
                "contrast": contrast,
                "prompt_length": row["prompt_length"],
                "prompt_length_units": str(row["prompt_length_units"]),
                "output_length_gap": row["output_length_gap"],
                "output_length_left": str(row["output_length_left"]),
                "output_length_right": str(row["output_length_right"]),
                "automatic_decision_margin": row["automatic_decision_margin"],
                "same_family_decision": row["same_family_decision"],
                "cross_family_decision": row["cross_family_decision"],
            }
            manifest = manifests[(row["benchmark"], row["prompt_id"])]
            for index, annotator in enumerate(ANNOTATORS, start=1):
                presentation_seed = rng.randrange(1, 2**31)
                condition_a = left if presentation_seed % 2 == 0 else right
                key_row[f"condition_a_{index}"] = condition_a
                key_row[f"presentation_seed_{index}"] = str(presentation_seed)
                _write_pair(
                    pairs_dir / annotator / f"{comparison_id}.md",
                    comparison_id,
                    row,
                    manifest,
                    condition_a,
                    presentation_seed,
                )
                answer_rows[annotator].append(
                    {
                        "comparison_id": comparison_id,
                        "annotator_id": annotator,
                        "preference": "",
                        "reason": "",
                        "presentation_seed": str(presentation_seed),
                        "adjudication_status": "pending",
                    }
                )
            key_rows.append(key_row)
            summary[contrast][row["benchmark"]] += 1
            comparison_number += 1

    key_fields = list(key_rows[0]) if key_rows else ["comparison_id"]
    with (output_root / "key.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=key_fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(key_rows)
    for annotator, rows in answer_rows.items():
        with (output_root / f"answers-{annotator}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=_answer_fields(), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    with (output_root / "answers-template.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=_answer_fields(), lineterminator="\n")
        writer.writeheader()
    (output_root / "INSTRUCTIONS.md").write_text(
        """# Human evaluation

Read each assignment and both anonymized responses. Judge the overall quality of each response for the assignment, considering correctness, relevance, completeness, clarity, and usefulness together.

Record `A`, `B`, or `tie` in the assigned answer sheet. Add an optional short reason. Work independently: do not discuss cases with another annotator, and do not open `key.csv`, which contains condition mappings and automatic decisions. The presentation seed and adjudication status are recorded in the answer sheet; update the status only according to the study's adjudication procedure.
""",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("runs_root", type=Path)
    parser.add_argument("--seed", type=int, default=20260929)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "human-eval")
    args = parser.parse_args()
    print(json.dumps(generate(args.runs_root, args.seed, args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
