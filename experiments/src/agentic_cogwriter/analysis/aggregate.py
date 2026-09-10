from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Any

from ..runner.hashing import sha256_file
from .common import CONTRASTS, RunRecord, select_canonical_runs

PRICE_KEYS = ("input", "cached_input", "output")
DIMENSIONS = (
    "instruction_fulfillment",
    "organization_global_coherence",
    "content_adequacy_depth",
    "style_voice_audience_fit",
    "factuality_constraint_fidelity",
)


@dataclass(frozen=True)
class ScoreArtifact:
    manifest: dict[str, Any]
    records: tuple[dict[str, Any], ...]
    sources: tuple[RunRecord, ...]

    @property
    def task(self) -> str:
        return str(self.manifest.get("task", "unknown"))

    @property
    def judge_id(self) -> str:
        judge = self.manifest.get("judge")
        return (
            str(judge.get("judge_id", "unknown"))
            if isinstance(judge, Mapping)
            else "unknown"
        )


def _json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _artifacts(roots: Sequence[Path], runs: Sequence[RunRecord]) -> list[ScoreArtifact]:
    index = {
        "sha256:" + sha256_file(run.path / "run-manifest.json"): run for run in runs
    }
    result: list[ScoreArtifact] = []
    seen: set[Path] = set()
    for root_value in roots:
        for manifest_path in sorted(root_value.resolve().rglob("scores-manifest.json")):
            if manifest_path in seen:
                continue
            seen.add(manifest_path)
            manifest = _json(manifest_path)
            score_path = manifest_path.parent / "scores.jsonl"
            if manifest is None or not score_path.is_file():
                continue
            sources: list[RunRecord] = []
            for source in manifest.get("source_runs", []):
                digest = (
                    source.get("run_manifest_sha256")
                    if isinstance(source, Mapping)
                    else None
                )
                if not isinstance(digest, str) or digest not in index:
                    sources = []
                    break
                sources.append(index[digest])
            if not sources or any(run.status != "completed" for run in sources):
                continue
            try:
                records = tuple(
                    value
                    for line in score_path.read_text(encoding="utf-8").splitlines()
                    if isinstance(value := json.loads(line), dict)
                )
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            result.append(ScoreArtifact(manifest, records, tuple(sources)))
    return result


def _rows(
    groups: Mapping[tuple[str, ...], Any],
    labels: tuple[str, ...],
    summarize: Callable[[Any], Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {**dict(zip(labels, key, strict=True)), **summarize(value)}
        for key, value in sorted(groups.items())
    ]


def _completion(runs: Sequence[RunRecord]) -> dict[str, Any]:
    groups: dict[tuple[str, str, str], list[RunRecord]] = defaultdict(list)
    for run in runs:
        groups[(run.benchmark, run.platform, run.condition)].append(run)

    def summary(values: Sequence[RunRecord]) -> Mapping[str, Any]:
        failures: dict[str, int] = defaultdict(int)
        for run in values:
            if run.status != "completed":
                failure = run.manifest.get("failure")
                message = (
                    failure.get("message", failure.get("error", "unknown failure"))
                    if isinstance(failure, Mapping)
                    else "unknown failure"
                )
                failures[str(message).splitlines()[0][:120]] += 1
        return {
            "run_count": len(values),
            "completed_runs": sum(run.status == "completed" for run in values),
            "failed_runs": sum(run.status != "completed" for run in values),
            "failure_messages": dict(sorted(failures.items())),
        }

    return {
        "rows": _rows(groups, ("benchmark", "platform", "condition"), summary),
        "run_count": len(runs),
    }


def _pointwise(artifacts: Sequence[ScoreArtifact]) -> dict[str, Any]:
    observations: list[tuple[RunRecord, Mapping[str, Any], str]] = []
    for artifact in artifacts:
        if artifact.task != "pointwise" or len(artifact.sources) != 1:
            continue
        for record in artifact.records:
            scores = record.get("scores")
            if isinstance(scores, Mapping) and all(
                isinstance(scores.get(dimension), (int, float))
                and not isinstance(scores.get(dimension), bool)
                for dimension in DIMENSIONS
            ):
                observations.append(
                    (
                        artifact.sources[0],
                        record,
                        str(record.get("judge_id", artifact.judge_id)),
                    )
                )

    values: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    for run, record, judge in observations:
        for dimension in DIMENSIONS:
            values[(run.platform, judge, run.benchmark, dimension)].append(
                float(record["scores"][dimension])
            )
    centers = {key: fmean(items) for key, items in values.items()}
    deviations = {
        key: math.sqrt(fmean([(x - centers[key]) ** 2 for x in items]))
        for key, items in values.items()
    }
    judges: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for run, record, judge in observations:
        key = (run.platform, run.benchmark, run.condition, judge)
        entry = judges.setdefault(
            key,
            {
                "dimensions": defaultdict(list),
                "composites": [],
                "runs": set(),
                "records": 0,
            },
        )
        z_scores = []
        for dimension in DIMENSIONS:
            raw = float(record["scores"][dimension])
            entry["dimensions"][dimension].append(raw)
            scale = deviations[(run.platform, judge, run.benchmark, dimension)]
            z_scores.append(
                (raw - centers[(run.platform, judge, run.benchmark, dimension)]) / scale
                if scale
                else 0.0
            )
        entry["composites"].append(fmean(z_scores))
        entry["runs"].add(run.path)
        entry["records"] += 1

    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for (platform, benchmark, condition, judge), entry in judges.items():
        groups[(platform, benchmark, condition)].append(
            {
                "judge": judge,
                "dimensions": {
                    dimension: fmean(entry["dimensions"][dimension])
                    for dimension in DIMENSIONS
                },
                "composite": fmean(entry["composites"]),
                "runs": entry["runs"],
                "records": entry["records"],
            }
        )

    def summary(entries: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
        return {
            "run_count": len(set().union(*(entry["runs"] for entry in entries))),
            "record_count": sum(entry["records"] for entry in entries),
            "dimension_means": {
                dimension: fmean(entry["dimensions"][dimension] for entry in entries)
                for dimension in DIMENSIONS
            },
            "judge_composites": {
                entry["judge"]: entry["composite"] for entry in entries
            },
            "z_scored_composite_mean": fmean(entry["composite"] for entry in entries),
        }

    return {
        "rows": _rows(groups, ("platform", "benchmark", "condition"), summary),
        "run_count": len({run.path for run, _record, _judge in observations}),
    }


def _native(artifacts: Sequence[ScoreArtifact]) -> dict[str, Any]:
    judges: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    runs: dict[tuple[str, str, str, str], set[Path]] = defaultdict(set)
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
            key = (run.platform, run.benchmark, run.condition, artifact.judge_id)
            judges[key].append(fmean(values))
            runs[key].add(run.path)

    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for (platform, benchmark, condition, judge), values in judges.items():
        groups[(platform, benchmark, condition)].append(
            {
                "judge": judge,
                "score": fmean(values),
                "runs": runs[(platform, benchmark, condition, judge)],
            }
        )

    def summary(entries: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
        return {
            "run_count": len(set().union(*(entry["runs"] for entry in entries))),
            "judge_scores": {entry["judge"]: entry["score"] for entry in entries},
            "mean_score": fmean(entry["score"] for entry in entries),
        }

    rows = _rows(groups, ("platform", "benchmark", "condition"), summary)
    for row in rows:
        row["scale"] = scales.get(row["benchmark"], "unknown")
    return {"rows": rows, "run_count": sum(len(value) for value in runs.values())}


def _mapping(artifact: ScoreArtifact) -> dict[str, tuple[int, int]]:
    tournament = artifact.manifest.get("tournament")
    result: dict[str, tuple[int, int]] = {}
    for item in (
        tournament.get("order_mapping", []) if isinstance(tournament, Mapping) else []
    ):
        if isinstance(item, Mapping) and isinstance(item.get("presentation"), str):
            result[item["presentation"]] = (
                0 if item.get("first_output") == "first_run" else 1,
                0 if item.get("second_output") == "first_run" else 1,
            )
    return result or {"A|B": (0, 1), "B|A": (1, 0)}


def fit_bradley_terry(
    games: Sequence[tuple[str, str, str]], *, max_iterations: int = 10_000
) -> dict[str, Any]:
    """Fit a tie-aware Bradley-Terry model with iterative MM updates."""

    conditions = sorted(
        {condition for left, right, _outcome in games for condition in (left, right)}
    )
    wins: dict[str, float] = defaultdict(float)
    losses: dict[str, float] = defaultdict(float)
    played: dict[tuple[str, str], int] = defaultdict(int)
    for left, right, outcome in games:
        if left == right:
            continue
        played[tuple(sorted((left, right)))] += 1
        if outcome == "left":
            wins[left] += 1
            losses[right] += 1
        elif outcome == "right":
            wins[right] += 1
            losses[left] += 1
        elif outcome == "tie":
            wins[left] += 0.5
            wins[right] += 0.5
            losses[left] += 0.5
            losses[right] += 0.5
    if not conditions or not played:
        return {"status": "no data", "strengths": {}}
    if any(wins[item] == 0 or losses[item] == 0 for item in conditions):
        return {"status": "complete separation", "strengths": {}}

    strengths = dict.fromkeys(conditions, 1.0)
    for iteration in range(1, max_iterations + 1):
        updated = {}
        for condition in conditions:
            denominator = sum(
                count / (strengths[condition] + strengths[other])
                for (left, right), count in played.items()
                if condition in {left, right}
                for other in (right if condition == left else left,)
            )
            updated[condition] = wins[condition] / denominator if denominator else 0.0
        if any(value <= 0 or not math.isfinite(value) for value in updated.values()):
            return {"status": "complete separation", "strengths": {}}
        scale = math.exp(fmean(math.log(value) for value in updated.values()))
        updated = {condition: value / scale for condition, value in updated.items()}
        if max(abs(updated[item] - strengths[item]) for item in conditions) < 1e-10:
            return {"status": "ok", "strengths": updated, "iterations": iteration}
        strengths = updated
    return {"status": "non-convergence", "strengths": {}, "iterations": max_iterations}


def _slot(data: dict[str, Any], benchmark: str, platform: str) -> dict[str, Any]:
    return (
        data.setdefault(benchmark, {})
        .setdefault("platforms", {})
        .setdefault(
            platform,
            {"judges": {}, "expected_pairs": 0, "scored": set(), "runs": set()},
        )
    )


def _pairwise(
    artifacts: Sequence[ScoreArtifact], runs: Sequence[RunRecord]
) -> dict[str, Any]:
    expected: dict[tuple[str, str], int] = defaultdict(int)
    completed_counts: dict[tuple[str, str], int] = defaultdict(int)
    for run in {(r.benchmark, r.prompt, r.platform) for r in runs}:
        expected[(run[0], run[2])] += len(CONTRASTS)
    for run in runs:
        if run.status == "completed":
            completed_counts[(run.benchmark, run.platform)] += 1
    pairs: dict[tuple[str, str, str, str, str, str], ScoreArtifact] = {}
    for artifact in artifacts:
        if artifact.task != "pairwise" or len(artifact.sources) != 2:
            continue
        first, second = artifact.sources
        if (first.benchmark, first.prompt, first.platform) != (
            second.benchmark,
            second.prompt,
            second.platform,
        ):
            continue
        contrast = next(
            (
                pair
                for pair in CONTRASTS
                if {first.condition, second.condition} == set(pair)
            ),
            None,
        )
        if contrast:
            pairs.setdefault(
                (
                    first.benchmark,
                    first.platform,
                    first.prompt,
                    *contrast,
                    artifact.judge_id,
                ),
                artifact,
            )

    judges: dict[tuple[str, str, str], dict[str, Any]] = {}
    for (benchmark, platform, prompt, left, right, judge), artifact in pairs.items():
        group = judges.setdefault(
            (benchmark, platform, judge),
            {
                "games": [],
                "counts": defaultdict(lambda: {"wins": 0, "ties": 0, "losses": 0}),
                "consistent": [],
                "pairs": set(),
                "runs": set(),
            },
        )
        mapping = _mapping(artifact)
        records: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for record in artifact.records:
            if record.get("presentation") in {"A|B", "B|A"} and record.get(
                "winner"
            ) in {"A", "B", "tie"}:
                records[record["presentation"]].append(record)
        if len(records["A|B"]) != 1 or len(records["B|A"]) != 1:
            continue
        outcomes: list[str] = []
        for presentation in ("A|B", "B|A"):
            record = records[presentation][0]
            first_index, second_index = mapping.get(presentation, (0, 1))
            winner = record["winner"]
            outcome = (
                "tie"
                if winner == "tie"
                else artifact.sources[
                    first_index if winner == "A" else second_index
                ].condition
            )
            outcomes.append(outcome)
            result = (
                "left" if outcome == left else "right" if outcome == right else "tie"
            )
            group["games"].append((left, right, result))
            group["counts"][f"{left}:{right}"][
                {"left": "wins", "right": "losses", "tie": "ties"}[result]
            ] += 1
        group["consistent"].append(float(outcomes[0] == outcomes[1]))
        group["pairs"].add((prompt, left, right))
        group["runs"].update(source.path for source in artifact.sources)

    report: dict[str, Any] = {}
    for (benchmark, platform, judge), group in judges.items():
        slot = _slot(report, benchmark, platform)
        fit = fit_bradley_terry(group["games"])
        slot["judges"][judge] = {
            "contrasts": dict(sorted(group["counts"].items())),
            "position_consistency_rate": fmean(group["consistent"])
            if group["consistent"]
            else None,
            "strengths": fit["strengths"],
            "fit_status": fit["status"],
            "scored_pairs": len(group["pairs"]),
            "run_count": len(group["runs"]),
        }
        slot["scored"].update(group["pairs"])
        slot["runs"].update(group["runs"])
    for key, count in expected.items():
        _slot(report, *key)["expected_pairs"] += count

    missing = 0
    total_runs: set[Path] = set()
    for benchmark, value in report.items():
        for platform, data in value["platforms"].items():
            data["missing_pairs"] = data["expected_pairs"] - len(data["scored"])
            data["scored_pairs"] = len(data.pop("scored"))
            data["run_count"] = completed_counts.get(
                (benchmark, platform), len(data["runs"])
            )
            total_runs.update(data.pop("runs"))
            positions = [
                judge["position_consistency_rate"]
                for judge in data["judges"].values()
                if judge["position_consistency_rate"] is not None
            ]
            data["position_consistency_rate"] = fmean(positions) if positions else None
            data["contrasts"] = {
                label: {
                    field: sum(
                        judge["contrasts"].get(label, {}).get(field, 0)
                        for judge in data["judges"].values()
                    )
                    for field in ("wins", "ties", "losses")
                }
                for label in (f"{left}:{right}" for left, right in CONTRASTS)
                if any(label in judge["contrasts"] for judge in data["judges"].values())
            }
            fits = [
                judge
                for judge in data["judges"].values()
                if judge["fit_status"] == "ok"
            ]
            statuses = {judge["fit_status"] for judge in data["judges"].values()}
            data["fit_status"] = (
                "ok"
                if statuses == {"ok"}
                else ", ".join(sorted(statuses))
                if statuses
                else "no data"
            )
            data["strengths"] = (
                {
                    condition: fmean(
                        judge["strengths"][condition]
                        for judge in fits
                        if condition in judge["strengths"]
                    )
                    for condition in sorted(
                        {
                            condition
                            for judge in fits
                            for condition in judge["strengths"]
                        }
                    )
                }
                if fits and len(fits) == len(data["judges"])
                else {}
            )
            missing += data["missing_pairs"]
    return {
        "benchmarks": report,
        "missing_pairs": missing,
        "run_count": len(total_runs),
    }


def _integer(value: Mapping[str, Any], names: tuple[str, ...]) -> int:
    for name in names:
        item = value.get(name)
        if isinstance(item, int) and not isinstance(item, bool) and item >= 0:
            return item
    return 0


def _priced_rows(
    groups: Mapping[Any, Any], labels: tuple[str, ...], prices: Mapping[str, float]
) -> tuple[list[dict[str, Any]], dict[str, int], float]:
    def summary(
        value: tuple[dict[str, int], set[Path], int | None],
    ) -> Mapping[str, Any]:
        tokens, paths, records = value
        return {
            "run_count": len(paths),
            **({"record_count": records} if records is not None else {}),
            "tokens": tokens,
            "cost": sum(tokens[key] * prices[key] for key in PRICE_KEYS) / 1_000_000,
        }

    rows = _rows(groups, labels, summary)
    total_tokens = {key: sum(row["tokens"][key] for row in rows) for key in PRICE_KEYS}
    return rows, total_tokens, sum(row["cost"] for row in rows)


def _generation(
    runs: Sequence[RunRecord], prices: Mapping[str, float]
) -> dict[str, Any]:
    groups: dict[tuple[str, str, str], tuple[dict[str, int], set[Path], None]] = {}
    for run in runs:
        key = (run.platform, run.benchmark, run.condition)
        if key not in groups:
            groups[key] = (dict.fromkeys(PRICE_KEYS, 0), set(), None)
        tokens, paths, _ = groups[key]
        paths.add(run.path)
        for event_path in run.path.glob("attempt-*.events.jsonl"):
            try:
                lines = event_path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError):
                continue
            for line in lines:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                usage = event.get("usage") if isinstance(event, Mapping) else None
                if (
                    not isinstance(event, Mapping)
                    or event.get("type") != "turn.completed"
                    or not isinstance(usage, Mapping)
                ):
                    continue
                cached = _integer(
                    usage, ("cached_input_tokens", "cached_tokens", "cache_read_tokens")
                )
                tokens["input"] += max(
                    _integer(usage, ("input_tokens", "prompt_tokens")) - cached, 0
                )
                tokens["cached_input"] += cached
                tokens["output"] += _integer(usage, ("output_tokens",)) + _integer(
                    usage, ("reasoning_output_tokens", "reasoning_tokens")
                )
    rows, total_tokens, cost = _priced_rows(
        groups, ("platform", "benchmark", "condition"), prices
    )
    return {"rows": rows, "tokens": total_tokens, "cost": cost}


def _judge_cost(
    artifacts: Sequence[ScoreArtifact], prices: Mapping[str, float]
) -> dict[str, Any]:
    groups: dict[str, tuple[dict[str, int], set[Path], int]] = {}
    for artifact in artifacts:
        if artifact.task not in groups:
            groups[artifact.task] = (dict.fromkeys(PRICE_KEYS, 0), set(), 0)
        tokens, paths, count = groups[artifact.task]
        paths.update(source.path for source in artifact.sources)
        for item in artifact.manifest.get("records", []):
            usage = item.get("usage") if isinstance(item, Mapping) else None
            if not isinstance(usage, Mapping):
                continue
            cached = _integer(
                usage, ("cached_tokens", "cached_input_tokens", "cache_read_tokens")
            )
            tokens["input"] += max(
                _integer(usage, ("prompt_tokens", "input_tokens")) - cached, 0
            )
            tokens["cached_input"] += cached
            tokens["output"] += _integer(usage, ("completion_tokens",))
            count += 1
        groups[artifact.task] = (tokens, paths, count)
    rows, total_tokens, cost = _priced_rows(
        {(key,): value for key, value in groups.items()}, ("task",), prices
    )
    return {"rows": rows, "tokens": total_tokens, "cost": cost}


def _prices(path: Path) -> dict[str, float]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping) or not set(PRICE_KEYS) <= set(value):
        raise ValueError("prices must contain input, cached_input, and output")
    result = {}
    for key in PRICE_KEYS:
        number = value[key]
        if (
            isinstance(number, bool)
            or not isinstance(number, (int, float))
            or number < 0
        ):
            raise ValueError(f"price {key} must be a non-negative number")
        result[key] = float(number)
    return result


def _markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Aggregation report",
        "",
        "The report uses canonical runs selected by the shared run selector.",
    ]
    for title, key in (
        ("Completion", "completion"),
        ("Generic pointwise", "pointwise"),
        ("Native", "native"),
    ):
        lines += [
            "",
            f"## {title}",
            "",
            "| Row | Runs | Details |",
            "| --- | ---: | --- |",
        ]
        for row in report[key]["rows"]:
            label = "/".join(
                str(row.get(field, ""))
                for field in ("platform", "benchmark", "condition")
            )
            detail = ", ".join(
                f"{field}={value}"
                for field, value in row.items()
                if field not in {"platform", "benchmark", "condition", "run_count"}
            )
            lines.append(f"| {label} | {row['run_count']} | {detail} |")
    lines += ["", "## Pairwise"]
    for benchmark, value in report["pairwise"]["benchmarks"].items():
        for platform, data in value["platforms"].items():
            lines.append(
                f"- {benchmark}/{platform}: expected={data['expected_pairs']}, "
                f"scored={data['scored_pairs']}, missing={data['missing_pairs']}, "
                f"fit={data['fit_status']}, "
                f"position_consistency={data['position_consistency_rate']}"
            )
            lines.append(f"  strengths={json.dumps(data['strengths'], sort_keys=True)}")
    lines += [
        "",
        "## Cost",
        "",
        "| Kind | Name | Runs | Cost | Tokens |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for row in report["cost"]["generation"]:
        label = "/".join(
            str(row.get(field, "")) for field in ("platform", "benchmark", "condition")
        )
        lines.append(
            f"| generation | {label} | {row['run_count']} | "
            f"{row['cost']:.6f} | {row['tokens']} |"
        )
    for row in report["cost"]["judge"]:
        lines.append(
            f"| judge | {row['task']} | {row['run_count']} | "
            f"{row['cost']:.6f} | {row['tokens']} |"
        )
    totals = report["cost"]["totals"]
    lines += ["", f"Total cost: {totals['total_cost']:.6f}", ""]
    return "\n".join(lines)


def aggregate_runs(
    runs_roots: Sequence[Path],
    *,
    generation_prices: Path,
    judge_prices: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Write aggregation.json and aggregation.md for canonical runs."""

    runs = select_canonical_runs(list(runs_roots))
    artifacts = _artifacts(runs_roots, runs)
    generation = _generation(runs, _prices(generation_prices))
    judge = _judge_cost(artifacts, _prices(judge_prices))
    report = {
        "completion": _completion(runs),
        "pointwise": _pointwise(artifacts),
        "native": _native(artifacts),
        "pairwise": _pairwise(artifacts, runs),
        "cost": {
            "generation": generation["rows"],
            "judge": judge["rows"],
            "totals": {
                "generation_cost": generation["cost"],
                "judge_cost": judge["cost"],
                "total_cost": generation["cost"] + judge["cost"],
                "generation_tokens": generation["tokens"],
                "judge_tokens": judge["tokens"],
                "total_tokens": {
                    key: generation["tokens"][key] + judge["tokens"][key]
                    for key in PRICE_KEYS
                },
            },
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "aggregation.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "aggregation.md").write_text(_markdown(report), encoding="utf-8")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aggregate completed experiment scores."
    )
    parser.add_argument("--runs-root", type=Path, action="append", required=True)
    parser.add_argument("--generation-prices", type=Path, required=True)
    parser.add_argument("--judge-prices", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = aggregate_runs(
        args.runs_root,
        generation_prices=args.generation_prices,
        judge_prices=args.judge_prices,
        output_dir=args.output_dir,
    )
    print(args.output_dir / "aggregation.md")
    print(
        f"run_count={report['completion']['run_count']} "
        f"missing_pairs={report['pairwise']['missing_pairs']}"
    )
    return 0
