"""Score completed runs with the existing judge scorer."""

from __future__ import annotations

import argparse
import hashlib
import json
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic_ai.models import Model

from ..judges.config import JudgeConfig
from ..judges.scorer import score_run

DEFAULT_CONTRASTS = "A4:A1,A2,A3,A5,A6"
TASK_ROOT = "scores"


@dataclass(frozen=True)
class CompletedRun:
    """A completed run and the root that owns its scoring error log."""

    root: Path
    path: Path
    manifest: dict[str, Any]

    @property
    def benchmark(self) -> str:
        return str(self.manifest["inputs"]["benchmark_name"])

    @property
    def condition(self) -> str:
        return str(self.manifest["inputs"]["condition_id"])

    @property
    def prompt(self) -> str:
        return str(self.manifest["inputs"]["prompt_id"])

    @property
    def platform(self) -> str:
        return str(self.manifest["inputs"].get("platform", "codex"))


@dataclass(frozen=True)
class ScoreJob:
    """One idempotent scorer invocation."""

    root: Path
    task: str
    run: CompletedRun
    compare: CompletedRun | None
    output_path: Path
    config: JudgeConfig


def _completed_runs(root: Path) -> list[CompletedRun]:
    """Find completed run manifests below one output root."""

    result: list[CompletedRun] = []
    for manifest_path in sorted(root.resolve().rglob("run-manifest.json")):
        try:
            value = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(value, dict) or value.get("status") != "completed":
            continue
        inputs = value.get("inputs")
        if not isinstance(inputs, dict):
            continue
        required = ("benchmark_name", "condition_id", "prompt_id")
        if not all(isinstance(inputs.get(field), str) for field in required):
            continue
        result.append(CompletedRun(root.resolve(), manifest_path.parent, value))
    return result


def _native_target(config: JudgeConfig) -> str:
    """Infer the benchmark targeted by a native template filename."""

    name = config.template_path.name.casefold()
    if "writingbench" in name:
        if config.task != "native-pointwise":
            raise ValueError("WritingBench native templates need native-pointwise")
        return "writingbench"
    if "hellobench" in name:
        if config.task != "native-checklist":
            raise ValueError("HelloBench native templates need native-checklist")
        return "hellobench"
    raise ValueError(
        "native config template filename must identify WritingBench or HelloBench"
    )


def _parse_contrasts(value: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Parse ``A4:A1,A2`` groups, with semicolons separating more groups."""

    groups: list[tuple[str, tuple[str, ...]]] = []
    for group in value.split(";"):
        group = group.strip()
        if not group:
            continue
        if ":" not in group:
            raise ValueError("contrasts must use LEFT:RIGHT[,RIGHT...]")
        left, right_text = group.split(":", 1)
        left = left.strip()
        rights = tuple(item.strip() for item in right_text.split(",") if item.strip())
        if not left or not rights:
            raise ValueError(
                "contrasts must name one left and at least one right condition"
            )
        groups.append((left, rights))
    if not groups:
        raise ValueError("contrasts cannot be empty")
    return tuple(groups)


def _safe_pair_key(first: CompletedRun, second: CompletedRun) -> str:
    values = "|".join(
        sorted(
            (
                f"{first.benchmark}:{first.prompt}:{first.platform}:{first.condition}",
                f"{second.benchmark}:{second.prompt}:{second.platform}:{second.condition}",
            )
        )
    )
    return "pair-" + hashlib.sha256(values.encode("utf-8")).hexdigest()[:16]


def _output_path(run: CompletedRun, task: str, compare: CompletedRun | None) -> Path:
    base = run.path / TASK_ROOT / task
    if compare is not None:
        base /= _safe_pair_key(run, compare)
    return base / "scores.jsonl"


def _manifest_for(output_path: Path) -> Path:
    return output_path.with_name(output_path.stem + "-manifest.json")


def _error_record(job: ScoreJob, error: BaseException) -> dict[str, object]:
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "task": job.task,
        "run_dir": str(job.run.path),
        "compare_run_dir": str(job.compare.path) if job.compare else None,
        "error_type": type(error).__name__,
        "error": str(error),
    }


def _append_error(job: ScoreJob, error: BaseException) -> None:
    path = job.root / "scoring-errors.jsonl"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(_error_record(job, error), ensure_ascii=False) + "\n")


def _run_job(job: ScoreJob, model: Model | None) -> None:
    score_run(
        job.run.path,
        job.config,
        compare_run_dir=job.compare.path if job.compare else None,
        output_path=job.output_path,
        model=model,
    )


def _make_jobs(
    root: Path,
    runs: list[CompletedRun],
    *,
    pointwise_config: JudgeConfig,
    pairwise_config: JudgeConfig,
    native_configs: tuple[tuple[str, JudgeConfig], ...],
    contrasts: tuple[tuple[str, tuple[str, ...]], ...],
) -> tuple[list[ScoreJob], int]:
    jobs: list[ScoreJob] = []
    skipped = 0
    seen_pairs: set[tuple[Path, Path]] = set()

    for run in runs:
        candidates = [("pointwise", pointwise_config)]
        candidates.extend(
            (config.task, config)
            for target, config in native_configs
            if run.benchmark.casefold() == target
        )
        for task, config in candidates:
            output_path = _output_path(run, task, None)
            if _manifest_for(output_path).is_file():
                skipped += 1
            else:
                jobs.append(ScoreJob(root, task, run, None, output_path, config))

    by_key: dict[tuple[str, str, str, str], list[CompletedRun]] = {}
    for run in runs:
        by_key.setdefault(
            (run.benchmark, run.prompt, run.platform, run.condition), []
        ).append(run)
    for left, rights in contrasts:
        for right in rights:
            if left == right:
                continue
            matching_groups = {key[:3] for key in by_key if key[3] in {left, right}}
            for group in matching_groups:
                left_runs = by_key.get((*group, left), [])
                right_runs = by_key.get((*group, right), [])
                for first in left_runs:
                    for second in right_runs:
                        ordered = tuple(
                            sorted((first, second), key=lambda item: str(item.path))
                        )
                        pair_key = (ordered[0].path, ordered[1].path)
                        if pair_key in seen_pairs:
                            continue
                        seen_pairs.add(pair_key)
                        output_path = _output_path(ordered[0], "pairwise", ordered[1])
                        if _manifest_for(output_path).is_file():
                            skipped += 1
                        else:
                            jobs.append(
                                ScoreJob(
                                    root,
                                    "pairwise",
                                    ordered[0],
                                    ordered[1],
                                    output_path,
                                    pairwise_config,
                                )
                            )
    return jobs, skipped


def run_batch(
    runs_roots: list[Path],
    *,
    pointwise_config: Path,
    pairwise_config: Path,
    native_configs: list[Path],
    contrasts: str = DEFAULT_CONTRASTS,
    concurrency: int = 4,
    dry_run: bool = False,
    model: Model | None = None,
) -> dict[str, int]:
    """Score completed runs and return scored, skipped, and failed counts."""

    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")
    pointwise = JudgeConfig.load(pointwise_config)
    pairwise = JudgeConfig.load(pairwise_config)
    if pointwise.task != "pointwise":
        raise ValueError("--pointwise-config must have task pointwise")
    if pairwise.task != "pairwise":
        raise ValueError("--pairwise-config must have task pairwise")
    native_configs_loaded = tuple(JudgeConfig.load(path) for path in native_configs)
    native = tuple((_native_target(config), config) for config in native_configs_loaded)
    parsed_contrasts = _parse_contrasts(contrasts)

    totals = {"scored": 0, "skipped": 0, "failed": 0}
    for root_value in runs_roots:
        root = root_value.resolve()
        runs = _completed_runs(root)
        jobs, skipped = _make_jobs(
            root,
            runs,
            pointwise_config=pointwise,
            pairwise_config=pairwise,
            native_configs=native,
            contrasts=parsed_contrasts,
        )
        totals["skipped"] += skipped
        if dry_run:
            for job in jobs:
                print(f"would score {job.task}: {job.run.path} -> {job.output_path}")
            continue
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures: dict[Future[None], ScoreJob] = {
                executor.submit(_run_job, job, model): job for job in jobs
            }
            for future in as_completed(futures):
                job = futures[future]
                try:
                    future.result()
                except Exception as error:  # noqa: BLE001
                    totals["failed"] += 1
                    _append_error(job, error)
                else:
                    totals["scored"] += 1
    return totals


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score completed runs in batches.")
    parser.add_argument("--runs-root", type=Path, action="append", required=True)
    parser.add_argument("--pointwise-config", type=Path, required=True)
    parser.add_argument("--pairwise-config", type=Path, required=True)
    parser.add_argument("--native-config", type=Path, action="append", default=[])
    parser.add_argument("--contrasts", default=DEFAULT_CONTRASTS)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run_batch(
        args.runs_root,
        pointwise_config=args.pointwise_config,
        pairwise_config=args.pairwise_config,
        native_configs=args.native_config,
        contrasts=args.contrasts,
        concurrency=args.concurrency,
        dry_run=args.dry_run,
    )
    print("scored={scored} skipped={skipped} failed={failed}".format(**summary))
    return 0
