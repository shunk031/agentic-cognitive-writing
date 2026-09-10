"""Aggregate runner and score manifests into JSON and Markdown reports."""

from __future__ import annotations

import argparse
import itertools
import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PRICE_KEYS = ("input", "cached_input", "output")
DIMENSIONS = (
    "instruction_fulfillment",
    "organization_global_coherence",
    "content_adequacy_depth",
    "style_voice_audience_fit",
    "factuality_constraint_fidelity",
)


@dataclass(frozen=True)
class RunRecord:
    """A run manifest indexed by its content hash."""

    path: Path
    manifest: dict[str, Any]
    manifest_hash: str

    @property
    def benchmark(self) -> str:
        return str(self.manifest.get("inputs", {}).get("benchmark_name", "unknown"))

    @property
    def condition(self) -> str:
        return str(self.manifest.get("inputs", {}).get("condition_id", "unknown"))

    @property
    def prompt(self) -> str:
        return str(self.manifest.get("inputs", {}).get("prompt_id", "unknown"))

    @property
    def platform(self) -> str:
        return str(self.manifest.get("inputs", {}).get("platform", "unknown"))


@dataclass(frozen=True)
class ScoreArtifact:
    """One score JSON Lines file and its source runs."""

    path: Path
    manifest: dict[str, Any]
    records: tuple[dict[str, Any], ...]
    sources: tuple[RunRecord, ...]

    @property
    def task(self) -> str:
        return str(self.manifest.get("task", "unknown"))


def _manifest_hash(path: Path) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _json_object(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _runs(roots: Sequence[Path]) -> dict[str, RunRecord]:
    result: dict[str, RunRecord] = {}
    for root in roots:
        for path in sorted(root.resolve().rglob("run-manifest.json")):
            manifest = _json_object(path)
            if manifest is None:
                continue
            inputs = manifest.get("inputs")
            if not isinstance(inputs, dict):
                continue
            if not all(
                isinstance(inputs.get(field), str)
                for field in ("benchmark_name", "condition_id", "prompt_id")
            ):
                continue
            digest = _manifest_hash(path)
            result[digest] = RunRecord(path.parent, manifest, digest)
    return result


def _score_path(manifest_path: Path) -> Path:
    stem = manifest_path.name.removesuffix("-manifest.json")
    return manifest_path.with_name(stem + ".jsonl")


def _source_runs(
    manifest: Mapping[str, Any], run_index: Mapping[str, RunRecord]
) -> tuple[RunRecord, ...]:
    values = manifest.get("source_runs", [])
    if not isinstance(values, list):
        return ()
    result: list[RunRecord] = []
    for value in values:
        if not isinstance(value, Mapping):
            return ()
        digest = value.get("run_manifest_sha256")
        if isinstance(digest, str) and digest in run_index:
            result.append(run_index[digest])
        else:
            return ()
    return tuple(result)


def _score_artifacts(
    roots: Sequence[Path], run_index: Mapping[str, RunRecord]
) -> list[ScoreArtifact]:
    result: list[ScoreArtifact] = []
    seen: set[Path] = set()
    for root in roots:
        for manifest_path in sorted(root.resolve().rglob("scores-manifest.json")):
            if manifest_path in seen:
                continue
            seen.add(manifest_path)
            manifest = _json_object(manifest_path)
            score_path = _score_path(manifest_path)
            if manifest is None or not score_path.is_file():
                continue
            sources = _source_runs(manifest, run_index)
            if not sources or any(
                run.manifest.get("status") != "completed" for run in sources
            ):
                continue
            records: list[dict[str, Any]] = []
            try:
                lines = score_path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError):
                continue
            try:
                for line in lines:
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise ValueError
                    records.append(value)
            except (ValueError, json.JSONDecodeError):
                continue
            result.append(ScoreArtifact(score_path, manifest, tuple(records), sources))
    return result


def _failure_prefix(manifest: Mapping[str, Any]) -> str:
    failure = manifest.get("failure")
    if isinstance(failure, Mapping):
        message = failure.get("message", failure.get("error", "unknown failure"))
    else:
        message = "unknown failure"
    return str(message).splitlines()[0][:120]


def _completion_table(runs: Sequence[RunRecord]) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[RunRecord]] = defaultdict(list)
    for run in runs:
        grouped[(run.benchmark, run.condition)].append(run)
    rows: list[dict[str, Any]] = []
    for (benchmark, condition), values in sorted(grouped.items()):
        failures: dict[str, int] = defaultdict(int)
        for run in values:
            if run.manifest.get("status") != "completed":
                failures[_failure_prefix(run.manifest)] += 1
        rows.append(
            {
                "benchmark": benchmark,
                "condition": condition,
                "run_count": len(values),
                "completed_runs": sum(
                    run.manifest.get("status") == "completed" for run in values
                ),
                "failed_runs": sum(
                    run.manifest.get("status") != "completed" for run in values
                ),
                "failure_messages": dict(sorted(failures.items())),
            }
        )
    return {"rows": rows, "run_count": len(runs)}


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _pointwise_table(artifacts: Sequence[ScoreArtifact]) -> dict[str, Any]:
    observations: list[tuple[ScoreArtifact, RunRecord, dict[str, Any]]] = []
    for artifact in artifacts:
        if artifact.task != "pointwise" or len(artifact.sources) != 1:
            continue
        for record in artifact.records:
            if isinstance(record.get("scores"), Mapping) and all(
                isinstance(record["scores"].get(dimension), (int, float))
                and not isinstance(record["scores"].get(dimension), bool)
                for dimension in DIMENSIONS
            ):
                observations.append((artifact, artifact.sources[0], record))

    values: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for _artifact, run, record in observations:
        scores = record["scores"]
        for dimension in DIMENSIONS:
            values[
                (run.benchmark, str(record.get("judge_id", "unknown")), dimension)
            ].append(float(scores[dimension]))

    means: dict[tuple[str, str, str], float] = {}
    deviations: dict[tuple[str, str, str], float] = {}
    for key, items in values.items():
        mean = sum(items) / len(items)
        means[key] = mean
        deviations[key] = math.sqrt(
            sum((item - mean) ** 2 for item in items) / len(items)
        )

    grouped: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(
        lambda: {dimension: [] for dimension in DIMENSIONS} | {"composite": []}
    )
    run_ids: dict[tuple[str, str], set[Path]] = defaultdict(set)
    for _artifact, run, record in observations:
        group = (run.benchmark, run.condition)
        scores = record["scores"]
        z_scores: list[float] = []
        for dimension in DIMENSIONS:
            raw = float(scores[dimension])
            key = (run.benchmark, str(record.get("judge_id", "unknown")), dimension)
            grouped[group][dimension].append(raw)
            scale = deviations[key]
            z_scores.append((raw - means[key]) / scale if scale else 0.0)
        grouped[group]["composite"].append(sum(z_scores) / len(z_scores))
        run_ids[group].add(run.path)

    rows = []
    for (benchmark, condition), items in sorted(grouped.items()):
        rows.append(
            {
                "benchmark": benchmark,
                "condition": condition,
                "run_count": len(run_ids[(benchmark, condition)]),
                "record_count": len(items["composite"]),
                "dimension_means": {
                    dimension: _mean(items[dimension]) for dimension in DIMENSIONS
                },
                "z_scored_composite_mean": _mean(items["composite"]),
            }
        )
    return {"rows": rows, "run_count": len({run.path for _, run, _ in observations})}


def _native_table(artifacts: Sequence[ScoreArtifact]) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    run_ids: dict[tuple[str, str], set[Path]] = defaultdict(set)
    scales: dict[str, str] = {}
    for artifact in artifacts:
        if (
            artifact.task not in {"native-pointwise", "native-checklist"}
            or len(artifact.sources) != 1
        ):
            continue
        run = artifact.sources[0]
        values: list[float] = []
        if artifact.task == "native-pointwise":
            values = [
                float(record["score"])
                for record in artifact.records
                if isinstance(record.get("score"), (int, float))
                and not isinstance(record.get("score"), bool)
            ]
            scales[run.benchmark] = "1-10"
        else:
            for record in artifact.records:
                items = record.get("checklist_items")
                if isinstance(items, list):
                    values.extend(
                        float(item["evaluation_score"])
                        for item in items
                        if isinstance(item, Mapping)
                        and isinstance(item.get("evaluation_score"), (int, float))
                        and not isinstance(item.get("evaluation_score"), bool)
                    )
            scales[run.benchmark] = "0-1"
        if values:
            key = (run.benchmark, run.condition)
            grouped[key].append(sum(values) / len(values))
            run_ids[key].add(run.path)

    rows = [
        {
            "benchmark": benchmark,
            "condition": condition,
            "run_count": len(run_ids[(benchmark, condition)]),
            "mean_score": _mean(values),
            "scale": scales.get(benchmark, "unknown"),
        }
        for (benchmark, condition), values in sorted(grouped.items())
    ]
    return {"rows": rows, "run_count": sum(len(value) for value in run_ids.values())}


def _pair_mapping(artifact: ScoreArtifact) -> dict[str, tuple[int, int]]:
    mapping: dict[str, tuple[int, int]] = {}
    tournament = artifact.manifest.get("tournament")
    order_mapping = (
        tournament.get("order_mapping") if isinstance(tournament, Mapping) else None
    )
    if isinstance(order_mapping, list):
        for item in order_mapping:
            if not isinstance(item, Mapping) or not isinstance(
                item.get("presentation"), str
            ):
                continue
            first = 0 if item.get("first_output") == "first_run" else 1
            second = 0 if item.get("second_output") == "first_run" else 1
            mapping[item["presentation"]] = (first, second)
    return mapping or {"A|B": (0, 1), "B|A": (1, 0)}


def _pairwise_table(
    artifacts: Sequence[ScoreArtifact], runs: Sequence[RunRecord]
) -> dict[str, Any]:
    outcomes: dict[tuple[str, str, str, str, frozenset[str]], list[str]] = defaultdict(
        list
    )
    contrast_counts: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {"wins": 0, "ties": 0, "losses": 0, "run_count": 0}
    )
    contrast_runs: dict[tuple[str, str], set[Path]] = defaultdict(set)
    games: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    scored_pairs: set[tuple[str, str, str, frozenset[str]]] = set()
    feeding_runs: set[Path] = set()
    for artifact in artifacts:
        if artifact.task != "pairwise" or len(artifact.sources) != 2:
            continue
        first, second = artifact.sources
        if (
            first.benchmark != second.benchmark
            or first.prompt != second.prompt
            or first.platform != second.platform
        ):
            continue
        mapping = _pair_mapping(artifact)
        pair = frozenset((first.condition, second.condition))
        pair_key = (first.benchmark, first.prompt, first.platform, pair)
        scored_pairs.add(pair_key)
        feeding_runs.update(run.path for run in artifact.sources)
        left, right = sorted(pair)
        if "A4" in pair:
            left, right = (
                "A4",
                next(condition for condition in pair if condition != "A4"),
            )
        label = f"{left}:{right}"
        for record in artifact.records:
            presentation = str(record.get("presentation", "A|B"))
            first_index, second_index = mapping.get(presentation, (0, 1))
            winner = record.get("winner")
            if winner == "tie":
                canonical = "tie"
                outcome = "tie"
            elif winner in {"A", "B"}:
                winner_index = first_index if winner == "A" else second_index
                winner_condition = artifact.sources[winner_index].condition
                canonical = winner_condition
                outcome = "left" if winner_condition == left else "right"
            else:
                continue
            outcomes[
                (first.benchmark, first.prompt, first.platform, label, pair)
            ].append(canonical)
            games[first.benchmark].append((left, right, outcome))
            counts = contrast_counts[(first.benchmark, label)]
            contrast_runs[(first.benchmark, label)].update(
                run.path for run in artifact.sources
            )
            if outcome == "left":
                counts["wins"] += 1
            elif outcome == "right":
                counts["losses"] += 1
            else:
                counts["ties"] += 1
            counts["run_count"] = len(contrast_runs[(first.benchmark, label)])

    expected_pairs: set[tuple[str, str, str, frozenset[str]]] = set()
    grouped: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for run in runs:
        if run.manifest.get("status") == "completed":
            grouped[(run.benchmark, run.prompt, run.platform)].add(run.condition)
    for (benchmark, prompt, platform), conditions in grouped.items():
        for first, second in itertools.combinations(sorted(conditions), 2):
            expected_pairs.add(
                (benchmark, prompt, platform, frozenset((first, second)))
            )
    missing_by_benchmark: dict[str, int] = defaultdict(int)
    for benchmark, _prompt, _platform, _pair in expected_pairs - scored_pairs:
        missing_by_benchmark[benchmark] += 1

    benchmark_data: dict[str, Any] = {}
    for benchmark in sorted(
        set(benchmark for benchmark, _label in contrast_counts)
        | set(missing_by_benchmark)
    ):
        contrasts: dict[str, Any] = {}
        consistency_values: list[float] = []
        for (candidate_benchmark, label), counts in sorted(contrast_counts.items()):
            if candidate_benchmark != benchmark:
                continue
            pair_outcomes = [
                values
                for (
                    value_benchmark,
                    _prompt,
                    _platform,
                    value_label,
                    _pair,
                ), values in outcomes.items()
                if value_benchmark == benchmark and value_label == label
            ]
            available = sum(len(values) >= 2 for values in pair_outcomes)
            consistent = sum(
                len(set(values)) == 1 for values in pair_outcomes if len(values) >= 2
            )
            rate = consistent / available if available else None
            if rate is not None:
                consistency_values.append(rate)
            contrasts[label] = {
                **counts,
                "position_consistency_rate": rate,
            }
        strengths = fit_bradley_terry(games.get(benchmark, []))
        benchmark_data[benchmark] = {
            "contrasts": contrasts,
            "position_consistency_rate": (
                sum(consistency_values) / len(consistency_values)
                if consistency_values
                else None
            ),
            "strengths": strengths,
            "missing_pairs": missing_by_benchmark.get(benchmark, 0),
            "run_count": len(
                {
                    run.path
                    for run in runs
                    if run.benchmark == benchmark
                    and run.manifest.get("status") == "completed"
                }
            ),
        }
    return {
        "benchmarks": benchmark_data,
        "missing_pairs": sum(missing_by_benchmark.values()),
        "run_count": len(feeding_runs),
    }


def fit_bradley_terry(
    games: Sequence[tuple[str, str, str]], *, max_iterations: int = 10_000
) -> dict[str, float]:
    """Fit Bradley-Terry strengths with iterative MM and half-credit ties."""

    conditions = sorted(
        {condition for left, right, _outcome in games for condition in (left, right)}
    )
    strengths = {condition: 1.0 for condition in conditions}
    wins = defaultdict(float)
    played: dict[tuple[str, str], int] = defaultdict(int)
    for left, right, outcome in games:
        if left == right:
            continue
        pair: tuple[str, str] = (min(left, right), max(left, right))
        played[pair] += 1
        if outcome == "left":
            wins[left] += 1
        elif outcome == "right":
            wins[right] += 1
        elif outcome == "tie":
            wins[left] += 0.5
            wins[right] += 0.5
    for _ in range(max_iterations):
        updated: dict[str, float] = {}
        for condition in conditions:
            denominator = 0.0
            for (left, right), count in played.items():
                if condition in {left, right}:
                    other = right if condition == left else left
                    denominator += count / (strengths[condition] + strengths[other])
            updated[condition] = (
                wins[condition] / denominator if denominator else strengths[condition]
            )
        scale = (
            math.exp(
                sum(math.log(max(value, 1e-12)) for value in updated.values())
                / len(updated)
            )
            if updated
            else 1.0
        )
        updated = {condition: value / scale for condition, value in updated.items()}
        if (
            max(
                (
                    abs(updated[condition] - strengths[condition])
                    for condition in conditions
                ),
                default=0.0,
            )
            < 1e-10
        ):
            strengths = updated
            break
        strengths = updated
    return strengths


def _token_usage(value: Mapping[str, Any]) -> dict[str, int]:
    def integer(*names: str) -> int:
        for name in names:
            candidate = value.get(name)
            if (
                isinstance(candidate, int)
                and not isinstance(candidate, bool)
                and candidate >= 0
            ):
                return candidate
        return 0

    total_input = integer("input_tokens", "prompt_tokens")
    cached = integer("cached_input_tokens", "cached_tokens", "cache_read_tokens")
    output = integer("output_tokens", "completion_tokens")
    output += integer("reasoning_output_tokens", "reasoning_tokens")
    return {
        "input": max(total_input - cached, 0),
        "cached_input": cached,
        "output": output,
    }


def _add_tokens(target: dict[str, int], value: Mapping[str, Any]) -> None:
    usage = _token_usage(value)
    for key in PRICE_KEYS:
        target[key] += usage[key]


def _cost(tokens: Mapping[str, int], prices: Mapping[str, float]) -> float:
    return sum(tokens[key] * prices[key] for key in PRICE_KEYS) / 1_000_000


def _generation_cost(
    runs: Sequence[RunRecord], prices: Mapping[str, float]
) -> dict[str, Any]:
    grouped: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {key: 0 for key in PRICE_KEYS}
    )
    for run in runs:
        key = (run.benchmark, run.condition)
        for event_path in sorted(run.path.glob("attempt-*.events.jsonl")):
            try:
                lines = event_path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError):
                continue
            for line in lines:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if (
                    isinstance(event, Mapping)
                    and event.get("type") == "turn.completed"
                    and isinstance(event.get("usage"), Mapping)
                ):
                    _add_tokens(grouped[key], event["usage"])
    run_counts: dict[tuple[str, str], int] = defaultdict(int)
    for run in runs:
        run_counts[(run.benchmark, run.condition)] += 1
    rows = [
        {
            "benchmark": benchmark,
            "condition": condition,
            "run_count": run_counts[(benchmark, condition)],
            "tokens": tokens,
            "cost": _cost(tokens, prices),
        }
        for (benchmark, condition), tokens in sorted(grouped.items())
    ]
    totals = {key: sum(row["tokens"][key] for row in rows) for key in PRICE_KEYS}
    return {
        "rows": rows,
        "cost": sum(row["cost"] for row in rows),
        "tokens": totals,
    }


def _judge_cost(
    artifacts: Sequence[ScoreArtifact], prices: Mapping[str, float]
) -> dict[str, Any]:
    grouped: dict[str, dict[str, int]] = defaultdict(
        lambda: {key: 0 for key in PRICE_KEYS}
    )
    artifact_runs: dict[str, set[Path]] = defaultdict(set)
    record_counts: dict[str, int] = defaultdict(int)
    for artifact in artifacts:
        target = grouped[artifact.task]
        artifact_runs[artifact.task].update(run.path for run in artifact.sources)
        records = artifact.manifest.get("records")
        if not isinstance(records, list):
            continue
        for value in records:
            record_counts[artifact.task] += 1
            if isinstance(value, Mapping) and isinstance(value.get("usage"), Mapping):
                _add_tokens(target, value["usage"])
    rows = [
        {
            "task": task,
            "run_count": len(artifact_runs[task]),
            "record_count": record_counts[task],
            "tokens": tokens,
            "cost": _cost(tokens, prices),
        }
        for task, tokens in sorted(grouped.items())
    ]
    totals = {key: sum(row["tokens"][key] for row in rows) for key in PRICE_KEYS}
    return {
        "rows": rows,
        "cost": sum(row["cost"] for row in rows),
        "tokens": totals,
    }


def parse_prices(value: str | Mapping[str, Any]) -> dict[str, float]:
    """Parse a JSON object or JSON-file path containing per-million prices."""

    if isinstance(value, Mapping):
        document = value
    else:
        candidate = Path(value).expanduser()
        if candidate.is_file():
            document = json.loads(candidate.read_text(encoding="utf-8"))
        else:
            document = json.loads(value)
    if not isinstance(document, Mapping) or not set(PRICE_KEYS) <= set(document):
        raise ValueError("prices must contain input, cached_input, and output")
    prices: dict[str, float] = {}
    for key in PRICE_KEYS:
        number = document[key]
        if (
            isinstance(number, bool)
            or not isinstance(number, (int, float))
            or number < 0
        ):
            raise ValueError(f"price {key} must be a non-negative number")
        prices[key] = float(number)
    return prices


def _markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Aggregation report",
        "",
        "## Completion",
        "",
        "| Benchmark | Condition | Runs | Completed | Failed | Failure prefixes |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in report["completion"]["rows"]:
        failures = (
            "; ".join(
                f"{key} ({value})" for key, value in row["failure_messages"].items()
            )
            or "None"
        )
        row_text = (
            f"| {row['benchmark']} | {row['condition']} | {row['run_count']} | "
            f"{row['completed_runs']} | {row['failed_runs']} | {failures} |"
        )
        lines.append(row_text)
    lines.extend(
        [
            "",
            "## Generic pointwise",
            "",
            "| Benchmark | Condition | Runs | Record count | Dimension means | "
            "Z-scored composite |",
            "| --- | --- | ---: | ---: | --- | ---: |",
        ]
    )
    for row in report["pointwise"]["rows"]:
        dimensions = "; ".join(
            f"{key}={value:.3f}"
            for key, value in row["dimension_means"].items()
            if value is not None
        )
        composite = row["z_scored_composite_mean"]
        composite_text = f"{composite:.3f}" if composite is not None else "N/A"
        lines.append(
            f"| {row['benchmark']} | {row['condition']} | {row['run_count']} | "
            f"{row['record_count']} | {dimensions} | {composite_text} |"
        )
    lines.extend(
        [
            "",
            "## Native",
            "",
            "| Benchmark | Condition | Runs | Mean score | Scale |",
            "| --- | --- | ---: | ---: | --- |",
        ]
    )
    for row in report["native"]["rows"]:
        lines.append(
            f"| {row['benchmark']} | {row['condition']} | {row['run_count']} | "
            f"{row['mean_score']:.3f} | {row['scale']} |"
        )
    lines.extend(["", "## Pairwise", ""])
    for benchmark, value in report["pairwise"]["benchmarks"].items():
        position_rate = value["position_consistency_rate"]
        position_text = position_rate if position_rate is not None else "N/A"
        lines.extend(
            [
                f"### {benchmark}",
                "",
                f"Position-consistency rate: {position_text}",
                "",
                "| Contrast | Wins | Ties | Losses | Position consistency |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for label, counts in value["contrasts"].items():
            rate = counts["position_consistency_rate"]
            rate_text = rate if rate is not None else "N/A"
            lines.append(
                f"| {label} | {counts['wins']} | {counts['ties']} | "
                f"{counts['losses']} | {rate_text} |"
            )
        strengths = ", ".join(
            f"{key}={score:.3f}" for key, score in value["strengths"].items()
        )
        lines.append(f"\nBradley-Terry strengths: {strengths}")
        lines.append(f"Missing pairs: {value['missing_pairs']}")
    lines.extend(
        [
            "",
            "## Cost",
            "",
            "| Benchmark | Condition | Generation cost | Generation tokens |",
            "| --- | --- | ---: | --- |",
        ]
    )
    for row in report["cost"]["generation"]:
        tokens = ", ".join(f"{key}={value}" for key, value in row["tokens"].items())
        lines.append(
            f"| {row['benchmark']} | {row['condition']} | "
            f"{row['cost']:.6f} | {tokens} |"
        )
    lines.extend(
        ["", "| Judge task | Judge cost | Judge tokens |", "| --- | ---: | --- |"]
    )
    for row in report["cost"]["judge"]:
        tokens = ", ".join(f"{key}={value}" for key, value in row["tokens"].items())
        lines.append(f"| {row['task']} | {row['cost']:.6f} | {tokens} |")
    lines.append(
        f"\nTotal generation cost: {report['cost']['totals']['generation_cost']:.6f}"
    )
    lines.append(f"Total judge cost: {report['cost']['totals']['judge_cost']:.6f}")
    lines.append(f"Total cost: {report['cost']['totals']['total_cost']:.6f}")
    return "\n".join(lines) + "\n"


def aggregate_runs(
    runs_roots: Sequence[Path],
    *,
    generation_prices: Mapping[str, Any],
    judge_prices: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    """Build and write the complete aggregation report."""

    generation = parse_prices(generation_prices)
    judge = parse_prices(judge_prices)
    run_index = _runs(runs_roots)
    runs = list(run_index.values())
    artifacts = _score_artifacts(runs_roots, run_index)
    completion = _completion_table(runs)
    pointwise = _pointwise_table(artifacts)
    native = _native_table(artifacts)
    pairwise = _pairwise_table(artifacts, runs)
    generation_data = _generation_cost(runs, generation)
    judge_data = _judge_cost(artifacts, judge)
    report: dict[str, Any] = {
        "completion": completion,
        "pointwise": pointwise,
        "native": native,
        "pairwise": pairwise,
        "cost": {
            "generation": generation_data["rows"],
            "judge": judge_data["rows"],
            "totals": {
                "generation_cost": generation_data["cost"],
                "judge_cost": judge_data["cost"],
                "total_cost": generation_data["cost"] + judge_data["cost"],
                "generation_tokens": generation_data["tokens"],
                "judge_tokens": judge_data["tokens"],
                "total_tokens": {
                    key: generation_data["tokens"][key] + judge_data["tokens"][key]
                    for key in PRICE_KEYS
                },
            },
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "aggregation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "aggregation.md").write_text(_markdown(report), encoding="utf-8")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aggregate completed experiment scores."
    )
    parser.add_argument("--runs-root", type=Path, action="append", required=True)
    parser.add_argument("--generation-prices", required=True)
    parser.add_argument("--judge-prices", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = aggregate_runs(
        args.runs_root,
        generation_prices=parse_prices(args.generation_prices),
        judge_prices=parse_prices(args.judge_prices),
        output_dir=args.output_dir,
    )
    print(args.output_dir / "aggregation.md")
    print(f"run_count={report['completion']['run_count']}")
    return 0
