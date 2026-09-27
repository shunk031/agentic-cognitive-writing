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
from .common import CONTRASTS, RunRecord, parse_contrasts, select_canonical_runs

PRICE_KEYS = ("input", "cached_input", "output")
CONFIRMATORY_CONTRASTS = (
    ("A4", "A1"),
    ("A4", "A2"),
    ("A4", "A3"),
    ("A4", "A5"),
    ("A4", "A6"),
    ("A7", "A1"),
    ("A7", "A4"),
    ("A7", "A5"),
)
CONFIRMATORY_HOLM_RUN_COUNT = 3
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


def exact_two_sided_sign_test(wins: int, losses: int) -> float:
    """Return the exact two-sided sign-test p-value, excluding ties."""

    non_ties = wins + losses
    if non_ties == 0:
        return 1.0
    lower_tail = sum(
        math.comb(non_ties, index) for index in range(min(wins, losses) + 1)
    )
    return min(1.0, 2.0 * lower_tail / (2**non_ties))


def wilson_interval(
    wins: int, losses: int, *, confidence: float = 0.95
) -> tuple[float | None, float | None]:
    """Return a Wilson score interval for the win rate, excluding ties."""

    non_ties = wins + losses
    if non_ties == 0:
        return None, None
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between zero and one")
    # The confirmatory analysis uses the standard normal 95 percent critical
    # value. Keep the calculation dependency-free so the aggregation command
    # remains usable in the frozen experiment environment.
    z = 1.959963984540054
    rate = wins / non_ties
    denominator = 1 + z**2 / non_ties
    center = (rate + z**2 / (2 * non_ties)) / denominator
    margin = (
        z
        * math.sqrt(rate * (1 - rate) / non_ties + z**2 / (4 * non_ties**2))
        / denominator
    )
    return center - margin, center + margin


def holm_adjusted_pvalues(pvalues: Sequence[float]) -> list[float]:
    """Apply Holm's step-down correction while preserving input order."""

    if not pvalues:
        return []
    if any(not 0 <= value <= 1 for value in pvalues):
        raise ValueError("p-values must be between zero and one")
    ordered = sorted(enumerate(pvalues), key=lambda item: (item[1], item[0]))
    adjusted = [0.0] * len(pvalues)
    running = 0.0
    size = len(pvalues)
    for rank, (index, value) in enumerate(ordered):
        running = max(running, min(1.0, (size - rank) * value))
        adjusted[index] = running
    return adjusted


def _sign_statistics(
    wins: int,
    losses: int,
    ties: int,
    *,
    holm_pvalue: float | None = None,
) -> dict[str, Any]:
    low, high = wilson_interval(wins, losses)
    p_raw = exact_two_sided_sign_test(wins, losses)
    return {
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "n_non_tie": wins + losses,
        "win_rate": wins / (wins + losses) if wins + losses else None,
        "p_raw": p_raw,
        "p_holm": p_raw if holm_pvalue is None else holm_pvalue,
        "wilson_low": low,
        "wilson_high": high,
    }


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
    artifacts: Sequence[ScoreArtifact],
    runs: Sequence[RunRecord],
    *,
    contrasts: tuple[tuple[str, str], ...] = CONTRASTS,
    holm_pvalues: Mapping[tuple[str, str, str, str], float] | None = None,
) -> dict[str, Any]:
    expected: dict[tuple[str, str], int] = defaultdict(int)
    completed_counts: dict[tuple[str, str], int] = defaultdict(int)
    for run in {(r.benchmark, r.prompt, r.platform) for r in runs}:
        expected[(run[0], run[2])] += len(contrasts)
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
                for pair in contrasts
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
                "collapsed_outcomes": defaultdict(dict),
                "presentation_disagreement_prompts": defaultdict(set),
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
        # One prompt contributes a winner only when both semantic outcomes
        # agree; every disagreement, including winner-versus-tie, is a tie.
        collapsed_result = (
            "left"
            if outcomes[0] == outcomes[1] == left
            else "right"
            if outcomes[0] == outcomes[1] == right
            else "tie"
        )
        label = f"{left}:{right}"
        group["collapsed_outcomes"][label][prompt] = collapsed_result
        if outcomes[0] != outcomes[1]:
            group["presentation_disagreement_prompts"][label].add(prompt)
        group["consistent"].append(float(outcomes[0] == outcomes[1]))
        group["pairs"].add((prompt, left, right))
        group["runs"].update(source.path for source in artifact.sources)

    report: dict[str, Any] = {}
    for (benchmark, platform, judge), group in judges.items():
        slot = _slot(report, benchmark, platform)
        fit = fit_bradley_terry(group["games"])
        slot["judges"][judge] = {
            "contrasts": dict(sorted(group["counts"].items())),
            "_collapsed_prompt_outcomes": dict(
                sorted(
                    {
                        label: dict(sorted(prompts.items()))
                        for label, prompts in group["collapsed_outcomes"].items()
                    }.items()
                )
            ),
            "_presentation_disagreement_prompts": dict(
                sorted(
                    {
                        label: sorted(prompts)
                        for label, prompts in group[
                            "presentation_disagreement_prompts"
                        ].items()
                    }.items()
                )
            ),
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
            cells: dict[str, dict[str, int]] = {}
            record_cells: dict[str, dict[str, Any]] = {}
            collapsed_cells: dict[str, dict[str, Any]] = {}
            for left, right in contrasts:
                label = f"{left}:{right}"
                if not any(
                    label in judge["contrasts"] for judge in data["judges"].values()
                ):
                    continue
                record_counts = {
                    field: sum(
                        judge["contrasts"].get(label, {}).get(field, 0)
                        for judge in data["judges"].values()
                    )
                    for field in ("wins", "ties", "losses")
                }
                prompt_outcomes: defaultdict[str, list[str]] = defaultdict(list)
                presentation_disagreements = 0
                for judge in data["judges"].values():
                    for prompt, outcome in (
                        judge["_collapsed_prompt_outcomes"].get(label, {}).items()
                    ):
                        prompt_outcomes[prompt].append(outcome)
                    presentation_disagreements += len(
                        judge["_presentation_disagreement_prompts"].get(label, [])
                    )
                collapsed_counts = {"wins": 0, "ties": 0, "losses": 0}
                for outcomes in prompt_outcomes.values():
                    collapsed_result = (
                        "left"
                        if len(set(outcomes)) == 1 and outcomes[0] == "left"
                        else "right"
                        if len(set(outcomes)) == 1 and outcomes[0] == "right"
                        else "tie"
                    )
                    collapsed_counts[
                        {"left": "wins", "right": "losses", "tie": "ties"}[
                            collapsed_result
                        ]
                    ] += 1
                prompt_total = len(prompt_outcomes)
                judge_disagreements = sum(
                    len(set(outcomes)) > 1 for outcomes in prompt_outcomes.values()
                )
                record_stats = _sign_statistics(
                    record_counts["wins"],
                    record_counts["losses"],
                    record_counts["ties"],
                )
                collapsed_stats = _sign_statistics(
                    collapsed_counts["wins"],
                    collapsed_counts["losses"],
                    collapsed_counts["ties"],
                )
                if holm_pvalues is not None:
                    record_stats["p_holm"] = holm_pvalues.get(
                        (benchmark, platform, label, "record_pooled"),
                        record_stats["p_raw"],
                    )
                    collapsed_stats["p_holm"] = holm_pvalues.get(
                        (
                            benchmark,
                            platform,
                            label,
                            "prompt_collapsed_across_judges",
                        ),
                        collapsed_stats["p_raw"],
                    )
                cells[label] = record_counts
                record_cells[label] = record_stats
                collapsed_cells[label] = {
                    **collapsed_stats,
                    "presentation_disagreements": presentation_disagreements,
                    "judge_disagreements": judge_disagreements,
                    "judge_prompt_observations": sum(
                        len(outcomes) for outcomes in prompt_outcomes.values()
                    ),
                    "prompt_total": prompt_total,
                }
            data["contrasts"] = cells
            data["record_pooled"] = record_cells
            data["prompt_collapsed_across_judges"] = collapsed_cells
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
    if holm_pvalues is None:
        for _benchmark, value in report.items():
            for data in value["platforms"].values():
                for method in ("record_pooled", "prompt_collapsed_across_judges"):
                    labels = list(data[method])
                    adjusted = holm_adjusted_pvalues(
                        [data[method][label]["p_raw"] for label in labels]
                    )
                    for label, pvalue in zip(labels, adjusted, strict=True):
                        data[method][label]["p_holm_report_local"] = pvalue
                        data[method][label].pop("p_holm", None)
    for value in report.values():
        for data in value["platforms"].values():
            for judge in data["judges"].values():
                judge.pop("_collapsed_prompt_outcomes", None)
                judge.pop("_presentation_disagreement_prompts", None)
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
            lines.append(
                f"  holm_family={json.dumps(data['holm_family'], sort_keys=True)}"
            )
            for label, pooled in data["record_pooled"].items():
                collapsed = data["prompt_collapsed_across_judges"][label]
                holm_field = "p_holm" if "p_holm" in pooled else "p_holm_report_local"
                lines.append(
                    f"  {label}: record_pooled={pooled['wins']}/{pooled['losses']}/"
                    f"{pooled['ties']} p={pooled['p_raw']} "
                    f"{holm_field}={pooled[holm_field]} "
                    f"CI=({pooled['wilson_low']},{pooled['wilson_high']}); "
                    "prompt_collapsed_across_judges="
                    f"{collapsed['wins']}/{collapsed['losses']}/"
                    f"{collapsed['ties']} p={collapsed['p_raw']} "
                    f"{holm_field}={collapsed[holm_field]} "
                    f"CI=({collapsed['wilson_low']},{collapsed['wilson_high']}) "
                    f"disagreements={collapsed['presentation_disagreements']} "
                    f"prompts={collapsed['prompt_total']}"
                )
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


def _holm_family_for_root(
    family_roots: Sequence[Path],
    current_root: Path,
    *,
    contrasts: tuple[tuple[str, str], ...],
) -> dict[tuple[str, str, str, str], float]:
    """Get per-cell Holm values from a family of independent run roots."""

    raw: dict[tuple[str, str, str], list[tuple[Path, str, float]]] = defaultdict(list)
    for root_value in family_roots:
        root = root_value.resolve()
        runs = select_canonical_runs([root])
        pairwise = _pairwise(
            _artifacts([root], runs),
            runs,
            contrasts=contrasts,
        )
        for benchmark, benchmark_data in pairwise["benchmarks"].items():
            for platform, data in benchmark_data["platforms"].items():
                for label, cell in data.get("record_pooled", {}).items():
                    raw[(benchmark, platform, "record_pooled")].append(
                        (root, label, cell["p_raw"])
                    )
                for label, cell in data.get(
                    "prompt_collapsed_across_judges", {}
                ).items():
                    raw[(benchmark, platform, "prompt_collapsed_across_judges")].append(
                        (root, label, cell["p_raw"])
                    )

    adjusted_for_current: dict[tuple[str, str, str, str], float] = {}
    current_root = current_root.resolve()
    for (benchmark, platform, method), values in raw.items():
        adjusted = holm_adjusted_pvalues([value[2] for value in values])
        for (root, label, _pvalue), adjusted_value in zip(
            values, adjusted, strict=True
        ):
            if root == current_root:
                adjusted_for_current[(benchmark, platform, label, method)] = (
                    adjusted_value
                )
    return adjusted_for_current


def _validate_holm_family(
    runs_roots: Sequence[Path],
    holm_family_roots: Sequence[Path] | None,
    *,
    contrasts: tuple[tuple[str, str], ...],
) -> tuple[Path, ...] | None:
    if holm_family_roots is None:
        return None
    if len(runs_roots) != 1:
        raise ValueError(
            "confirmatory run-level aggregation requires exactly one runs root"
        )
    family = tuple(root.resolve() for root in holm_family_roots)
    if len(set(family)) != len(family):
        raise ValueError("Holm family roots must be unique")
    if len(family) != CONFIRMATORY_HOLM_RUN_COUNT:
        raise ValueError(
            "the confirmatory Holm family requires exactly three run roots"
        )
    if runs_roots[0].resolve() not in family:
        raise ValueError("the current runs root must be a member of the Holm family")
    if tuple(contrasts) != CONFIRMATORY_CONTRASTS:
        raise ValueError(
            "the 24-cell confirmatory Holm family requires the eight locked contrasts"
        )
    return family


def _holm_family_metadata(
    family: Sequence[Path] | None,
    *,
    contrasts: tuple[tuple[str, str], ...],
) -> dict[str, Any]:
    if family is None:
        return {
            "name": "report_local",
            "size": len(contrasts),
            "member_labels": [f"report:{left}:{right}" for left, right in contrasts],
            "derivation": (
                "Holm correction over the contrasts present in this aggregation "
                "report after canonical-run selection; not the confirmatory family."
            ),
        }
    member_labels = [
        f"run-{run_index}:{left}:{right}"
        for run_index, _root in enumerate(family, start=1)
        for left, right in contrasts
    ]
    return {
        "name": "confirmatory_24_cell" if len(member_labels) == 24 else "explicit",
        "size": len(member_labels),
        "member_labels": member_labels,
        "derivation": (
            "Holm correction over one raw p-value for each contrast in each "
            "independent run root, computed separately per benchmark and estimand."
        ),
    }


def aggregate_runs(
    runs_roots: Sequence[Path],
    *,
    generation_prices: Path,
    judge_prices: Path,
    output_dir: Path,
    contrasts: tuple[tuple[str, str], ...] = CONTRASTS,
    holm_family_roots: Sequence[Path] | None = None,
) -> dict[str, Any]:
    """Write aggregation.json and aggregation.md for canonical runs.

    ``holm_family_roots`` supplies independent run roots whose raw p-values
    form the confirmatory Holm family. The output remains scoped to
    ``runs_roots``; callers should provide one current root and the full
    family when reporting separate run-level files.
    """

    runs = select_canonical_runs(list(runs_roots))
    artifacts = _artifacts(runs_roots, runs)
    generation = _generation(runs, _prices(generation_prices))
    judge = _judge_cost(artifacts, _prices(judge_prices))
    family = _validate_holm_family(
        runs_roots,
        holm_family_roots,
        contrasts=contrasts,
    )
    holm_pvalues = None
    if family:
        holm_pvalues = _holm_family_for_root(
            family,
            runs_roots[0],
            contrasts=contrasts,
        )
    holm_metadata = _holm_family_metadata(family, contrasts=contrasts)
    report = {
        "completion": _completion(runs),
        "pointwise": _pointwise(artifacts),
        "native": _native(artifacts),
        "pairwise": _pairwise(
            artifacts,
            runs,
            contrasts=contrasts,
            holm_pvalues=holm_pvalues,
        ),
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
    for value in report["pairwise"]["benchmarks"].values():
        for data in value["platforms"].values():
            data["holm_family"] = holm_metadata
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
    parser.add_argument(
        "--contrasts",
        type=parse_contrasts,
        default=CONTRASTS,
        metavar="LEFT:RIGHT,...",
    )
    parser.add_argument(
        "--holm-family-root",
        type=Path,
        action="append",
        help="independent run root included in the confirmatory Holm family",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.contrasts == CONFIRMATORY_CONTRASTS and not args.holm_family_root:
        parser.error(
            "the eight-contrast confirmatory report requires three "
            "--holm-family-root arguments"
        )
    report = aggregate_runs(
        args.runs_root,
        generation_prices=args.generation_prices,
        judge_prices=args.judge_prices,
        output_dir=args.output_dir,
        contrasts=args.contrasts,
        holm_family_roots=args.holm_family_root,
    )
    print(args.output_dir / "aggregation.md")
    print(
        f"run_count={report['completion']['run_count']} "
        f"missing_pairs={report['pairwise']['missing_pairs']}"
    )
    return 0
