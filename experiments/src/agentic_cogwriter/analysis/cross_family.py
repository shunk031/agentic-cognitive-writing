from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..runner.hashing import sha256_file
from .aggregate import exact_two_sided_sign_test, wilson_interval
from .common import RunRecord, parse_contrasts, select_canonical_runs

DEFAULT_CONTRASTS = (("A4", "A1"), ("A4", "A3"), ("A4", "A5"))
PRESENTATIONS = ("A|B", "B|A")


@dataclass(frozen=True)
class PairObservation:
    benchmark: str
    prompt: str
    contrast: tuple[str, str]
    cross_family_presentations: tuple[str, str]
    reference_presentations: tuple[str, str]

    @property
    def cross_family_collapsed(self) -> str:
        return _collapse(self.cross_family_presentations, self.contrast)

    @property
    def reference_collapsed(self) -> str:
        return _collapse(self.reference_presentations, self.contrast)


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
    grouped: dict[str, list[Mapping[str, Any]]] = {key: [] for key in PRESENTATIONS}
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(value, Mapping):
            continue
        presentation = value.get("presentation")
        if presentation in grouped and value.get("winner") in {"A", "B", "tie"}:
            grouped[presentation].append(value)
    if any(len(grouped[key]) != 1 for key in PRESENTATIONS):
        return {}
    return {key: grouped[key][0] for key in PRESENTATIONS}


def _run_index(runs_root: Path) -> dict[str, RunRecord]:
    return {
        "sha256:" + sha256_file(run.path / "run-manifest.json"): run
        for run in select_canonical_runs([runs_root])
        if run.status == "completed"
    }


def _pair_source_runs(
    manifest: Mapping[str, Any],
    source_index: Mapping[str, RunRecord],
    contrast: tuple[str, str],
) -> tuple[tuple[RunRecord, ...], tuple[tuple[str, str], ...]] | None:
    source_runs: list[RunRecord] = []
    source_hashes: list[str] = []
    for source in manifest.get("source_runs", []):
        if not isinstance(source, Mapping):
            return None
        digest = source.get("run_manifest_sha256")
        if not isinstance(digest, str) or digest not in source_index:
            return None
        source_hashes.append(digest)
        source_runs.append(source_index[digest])
    if len(source_runs) != 2:
        return None
    first, second = source_runs
    if (first.benchmark, first.prompt, first.platform) != (
        second.benchmark,
        second.prompt,
        second.platform,
    ) or {first.condition, second.condition} != set(contrast):
        return None
    by_condition = {
        run.condition: digest
        for run, digest in zip(source_runs, source_hashes, strict=True)
    }
    return tuple(source_runs), tuple(
        (condition, by_condition[condition]) for condition in contrast
    )


def _semantic_outcomes(
    manifest: Mapping[str, Any],
    source_runs: Sequence[RunRecord],
    records: Mapping[str, Mapping[str, Any]],
) -> tuple[str, str]:
    mapping = _mapping(manifest)
    outcomes: list[str] = []
    for presentation in PRESENTATIONS:
        winner = records[presentation]["winner"]
        if winner == "tie":
            outcomes.append("tie")
            continue
        first_index, second_index = mapping.get(presentation, (0, 1))
        outcomes.append(
            source_runs[first_index if winner == "A" else second_index].condition
        )
    return outcomes[0], outcomes[1]


def _collapse(outcomes: tuple[str, str], contrast: tuple[str, str]) -> str:
    if outcomes[0] == outcomes[1] == contrast[0]:
        return contrast[0]
    if outcomes[0] == outcomes[1] == contrast[1]:
        return contrast[1]
    return "tie"


def _load_pair_rows(
    runs_root: Path,
    *,
    cross_family_judge_id: str,
    reference_judge_id: str,
    contrasts: Sequence[tuple[str, str]],
) -> tuple[list[PairObservation], list[Mapping[str, Any]]]:
    source_index = _run_index(runs_root)
    requested = tuple(contrasts)
    pair_key = tuple[str, str, str, tuple[tuple[str, str], ...]]
    by_judge: dict[str, dict[pair_key, tuple[PairObservation, Mapping[str, Any]]]] = {
        cross_family_judge_id: {},
        reference_judge_id: {},
    }
    for manifest_path in sorted(runs_root.resolve().rglob("scores-manifest.json")):
        manifest = _json(manifest_path)
        if manifest is None or manifest.get("task") != "pairwise":
            continue
        judge = manifest.get("judge")
        observed_judge = judge.get("judge_id") if isinstance(judge, Mapping) else None
        if observed_judge not in by_judge:
            continue
        records = _records(manifest_path.parent / "scores.jsonl")
        if not records:
            continue
        for contrast in requested:
            resolved = _pair_source_runs(manifest, source_index, contrast)
            if resolved is None:
                continue
            source_runs, source_key = resolved
            key = (
                source_runs[0].benchmark,
                source_runs[0].prompt,
                source_runs[0].platform,
                source_key,
            )
            observation = PairObservation(
                benchmark=source_runs[0].benchmark,
                prompt=source_runs[0].prompt,
                contrast=contrast,
                cross_family_presentations=_semantic_outcomes(
                    manifest, source_runs, records
                ),
                reference_presentations=_semantic_outcomes(
                    manifest, source_runs, records
                ),
            )
            by_judge[observed_judge].setdefault(key, (observation, manifest))
    rows: list[PairObservation] = []
    cross_manifests: list[Mapping[str, Any]] = []
    cross_pairs = by_judge[cross_family_judge_id]
    reference_pairs = by_judge[reference_judge_id]
    for key in sorted(cross_pairs):
        if key not in reference_pairs:
            continue
        cross_observation, cross_manifest = cross_pairs[key]
        reference_observation, _reference_manifest = reference_pairs[key]
        rows.append(
            PairObservation(
                benchmark=cross_observation.benchmark,
                prompt=cross_observation.prompt,
                contrast=cross_observation.contrast,
                cross_family_presentations=cross_observation.cross_family_presentations,
                reference_presentations=reference_observation.cross_family_presentations,
            )
        )
        cross_manifests.append(cross_manifest)
    return rows, cross_manifests


def _rate(wins: int, total: int) -> dict[str, Any]:
    low, high = wilson_interval(wins, total - wins)
    return {
        "numerator": wins,
        "denominator": total,
        "rate": wins / total if total else None,
        "wilson_low": low,
        "wilson_high": high,
    }


def _metric(rows: Sequence[PairObservation]) -> dict[str, Any]:
    if not rows:
        return {
            "n": 0,
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "commit_rate": _rate(0, 0),
            "win_rate": _rate(0, 0),
            "sign_test_p": 1.0,
            "presentation_agreement": {"numerator": 0, "denominator": 0},
            "prompt_collapsed_agreement": {"numerator": 0, "denominator": 0},
            "direction_conflicts": 0,
        }
    wins = sum(row.cross_family_collapsed == row.contrast[0] for row in rows)
    losses = sum(row.cross_family_collapsed == row.contrast[1] for row in rows)
    ties = len(rows) - wins - losses
    presentation_agreement = sum(
        left == right
        for row in rows
        for left, right in zip(
            row.cross_family_presentations,
            row.reference_presentations,
            strict=True,
        )
    )
    prompt_agreement = sum(
        row.cross_family_collapsed == row.reference_collapsed for row in rows
    )
    direction_conflicts = sum(
        row.cross_family_collapsed in row.contrast
        and row.reference_collapsed in row.contrast
        and row.cross_family_collapsed != row.reference_collapsed
        for row in rows
    )
    return {
        "n": len(rows),
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "commit_rate": _rate(wins + losses, len(rows)),
        "win_rate": _rate(wins, wins + losses),
        "sign_test_p": exact_two_sided_sign_test(wins, losses),
        "presentation_agreement": {
            "numerator": presentation_agreement,
            "denominator": 2 * len(rows),
        },
        "prompt_collapsed_agreement": {
            "numerator": prompt_agreement,
            "denominator": len(rows),
        },
        "direction_conflicts": direction_conflicts,
    }


def _provenance(
    manifests: Sequence[Mapping[str, Any]], judge_ids: tuple[str, str]
) -> dict[str, Any]:
    if not manifests:
        raise ValueError("no matching cross-family pair manifests found")
    judges = [manifest.get("judge") for manifest in manifests]
    if not all(isinstance(judge, Mapping) for judge in judges):
        raise ValueError("cross-family manifests lack judge metadata")
    fields = {
        "cross_family_model_id": "model",
        "effort": "effort",
        "seed": "seed",
        "maximum_output_tokens": "max_output_tokens",
    }
    result: dict[str, Any] = {
        "cross_family_judge_id": judge_ids[0],
        "reference_judge_id": judge_ids[1],
        "eligible_pair_rule": (
            "A pair is eligible only when both judges have one complete pairwise "
            "manifest with two valid presentation records for the same canonical, "
            "completed source runs and requested contrast."
        ),
    }
    for output_key, manifest_key in fields.items():
        values = {judge[manifest_key] for judge in judges if manifest_key in judge}
        if len(values) != 1:
            raise ValueError(f"inconsistent cross-family judge field: {manifest_key}")
        result[output_key] = values.pop()
    return result


def aggregate_cross_family(
    runs_root: Path,
    *,
    cross_family_judge_id: str,
    reference_judge_id: str,
    contrasts: Sequence[tuple[str, str]] = DEFAULT_CONTRASTS,
) -> dict[str, Any]:
    rows, manifests = _load_pair_rows(
        runs_root,
        cross_family_judge_id=cross_family_judge_id,
        reference_judge_id=reference_judge_id,
        contrasts=contrasts,
    )
    if not rows:
        raise ValueError("no eligible pairs matched both judges")
    contrast_reports: dict[str, dict[str, Any]] = {}
    for contrast in contrasts:
        contrast_rows = [row for row in rows if row.contrast == contrast]
        report = _metric(contrast_rows)
        report["benchmarks"] = {
            benchmark: _metric(
                [row for row in contrast_rows if row.benchmark == benchmark]
            )
            for benchmark in sorted({row.benchmark for row in contrast_rows})
        }
        contrast_reports[f"{contrast[0]}:{contrast[1]}"] = report
    report = {
        "schema_version": 1,
        "note": "No multiplicity correction is applied to this robustness check.",
        "provenance": _provenance(
            manifests, (cross_family_judge_id, reference_judge_id)
        ),
        "contrasts": contrast_reports,
        "pooled": _metric(rows),
    }
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aggregate cross-family pairwise judge agreement."
    )
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--cross-family-judge", required=True)
    parser.add_argument("--reference-judge", required=True)
    parser.add_argument(
        "--contrasts",
        type=parse_contrasts,
        default=DEFAULT_CONTRASTS,
        metavar="LEFT:RIGHT,...",
    )
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = aggregate_cross_family(
        args.runs_root,
        cross_family_judge_id=args.cross_family_judge,
        reference_judge_id=args.reference_judge,
        contrasts=args.contrasts,
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
