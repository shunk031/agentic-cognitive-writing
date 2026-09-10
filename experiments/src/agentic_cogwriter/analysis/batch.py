from __future__ import annotations

import argparse
import json
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic_ai.models import Model

from ..judges.config import JudgeConfig
from ..judges.scorer import score_run
from .common import CONTRASTS, RunRecord, select_canonical_runs

TASK_ROOT = "scores"


@dataclass(frozen=True)
class ScoreJob:
    root: Path
    task: str
    run: RunRecord
    compare: RunRecord | None
    output_path: Path
    config: JudgeConfig


def _native_target(config: JudgeConfig) -> str:
    name = config.template_path.name.casefold()
    if "writingbench" in name and config.task == "native-pointwise":
        return "writingbench"
    if "hellobench" in name and config.task == "native-checklist":
        return "hellobench"
    raise ValueError(
        "native template filename must identify its benchmark and match its task"
    )


def _output_path(
    run: RunRecord, task: str, config: JudgeConfig, compare: RunRecord | None = None
) -> Path:
    directory = run.path / TASK_ROOT / task / str(config.judge_id)
    if compare is not None:
        directory /= f"{run.prompt}-{compare.condition}"
    return directory / "scores.jsonl"


def _jobs(
    runs: list[RunRecord],
    *,
    pointwise: JudgeConfig,
    pairwise: JudgeConfig,
    native: tuple[tuple[str, JudgeConfig], ...],
) -> tuple[list[ScoreJob], int, dict[str, int]]:
    jobs: list[ScoreJob] = []
    skipped = 0
    scheduled = {"pointwise": 0, "native": 0, "pairwise": 0}

    def add(
        task: str, run: RunRecord, config: JudgeConfig, compare: RunRecord | None
    ) -> None:
        nonlocal skipped
        output_path = _output_path(run, task, config, compare)
        if (output_path.parent / "scores-manifest.json").is_file():
            skipped += 1
            return
        jobs.append(ScoreJob(run.root, task, run, compare, output_path, config))
        scheduled["native" if task.startswith("native-") else task] += 1

    for run in runs:
        if run.status != "completed":
            continue
        add("pointwise", run, pointwise, None)
        for target, config in native:
            if run.benchmark.casefold() == target:
                add(config.task, run, config, None)

    index = {
        (run.benchmark, run.condition, run.prompt, run.platform): run for run in runs
    }
    groups = {(run.benchmark, run.prompt, run.platform) for run in runs}
    for benchmark, prompt, platform in sorted(groups):
        for left, right in CONTRASTS:
            first = index.get((benchmark, left, prompt, platform))
            second = index.get((benchmark, right, prompt, platform))
            if first is None or second is None:
                continue
            if first.status != "completed" or second.status != "completed":
                continue
            add("pairwise", first, pairwise, second)
    return jobs, skipped, scheduled


def run_batch(
    runs_roots: list[Path],
    *,
    pointwise_config: Path,
    pairwise_config: Path,
    native_configs: list[Path],
    concurrency: int = 4,
    dry_run: bool = False,
    model: Model | None = None,
) -> dict[str, int]:
    """Score one canonical run per key and continue after individual failures."""

    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")
    pointwise = JudgeConfig.load(pointwise_config)
    pairwise = JudgeConfig.load(pairwise_config)
    if pointwise.task != "pointwise":
        raise ValueError("--pointwise-config must have task pointwise")
    if pairwise.task != "pairwise":
        raise ValueError("--pairwise-config must have task pairwise")
    native = tuple(
        (_native_target(config), config)
        for config in (JudgeConfig.load(path) for path in native_configs)
    )
    totals = {
        "scored": 0,
        "skipped": 0,
        "failed": 0,
        "pointwise": 0,
        "native": 0,
        "pairwise": 0,
    }
    canonical = select_canonical_runs(runs_roots)
    jobs, skipped, scheduled = _jobs(
        canonical, pointwise=pointwise, pairwise=pairwise, native=native
    )
    totals["skipped"] += skipped
    for task, count in scheduled.items():
        totals[task] += count

    if dry_run:
        for job in jobs:
            print(f"would score {job.task}: {job.run.path} -> {job.output_path}")
        return totals

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures: dict[Future[Any], ScoreJob] = {
            executor.submit(
                score_run,
                job.run.path,
                job.config,
                compare_run_dir=job.compare.path if job.compare else None,
                output_path=job.output_path,
                model=model,
            ): job
            for job in jobs
        }
        for future in as_completed(futures):
            job = futures[future]
            try:
                future.result()
            except Exception as error:  # noqa: BLE001
                totals["failed"] += 1
                with (job.root / "scoring-errors.jsonl").open(
                    "a", encoding="utf-8"
                ) as stream:
                    stream.write(
                        json.dumps(
                            {
                                "timestamp": datetime.now(UTC).isoformat(),
                                "task": job.task,
                                "run_dir": str(job.run.path),
                                "compare_run_dir": str(job.compare.path)
                                if job.compare
                                else None,
                                "error_type": type(error).__name__,
                                "error": str(error),
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
            else:
                totals["scored"] += 1
    return totals


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Score canonical completed runs in batches."
    )
    parser.add_argument("--runs-root", type=Path, action="append", required=True)
    parser.add_argument("--pointwise-config", type=Path, required=True)
    parser.add_argument("--pairwise-config", type=Path, required=True)
    parser.add_argument("--native-config", type=Path, action="append", default=[])
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
        concurrency=args.concurrency,
        dry_run=args.dry_run,
    )
    print(
        "scored={scored} skipped={skipped} failed={failed} "
        "pointwise={pointwise} native={native} pairwise={pairwise}".format(**summary)
    )
    return 0
