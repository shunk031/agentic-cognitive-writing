#!/usr/bin/env python3
"""Score canonical pairwise jobs without pointwise or native jobs."""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _load_experiment_modules() -> tuple[Any, Any, Any, Any]:
    repository_root = Path(__file__).resolve().parents[2]
    experiments_source = repository_root / "experiments" / "src"
    if str(experiments_source) not in sys.path:
        sys.path.insert(0, str(experiments_source))
    from agentic_cogwriter.analysis.common import parse_contrasts, select_canonical_runs
    from agentic_cogwriter.judges.config import JudgeConfig
    from agentic_cogwriter.judges.scorer import score_run

    return parse_contrasts, select_canonical_runs, JudgeConfig, score_run


@dataclass(frozen=True)
class PairwiseJob:
    root: Path
    first: Any
    second: Any
    output_path: Path
    config: Any


def pairwise_jobs(
    roots: list[Path], config: Any, contrasts: tuple[tuple[str, str], ...]
) -> tuple[list[PairwiseJob], int]:
    _, select_canonical_runs, _, _ = _load_experiment_modules()
    canonical = [run for run in select_canonical_runs(roots) if run.status == "completed"]
    index = {
        (run.benchmark, run.condition, run.prompt, run.platform): run
        for run in canonical
    }
    groups = sorted({(run.benchmark, run.prompt, run.platform) for run in canonical})
    jobs: list[PairwiseJob] = []
    skipped = 0
    for benchmark, prompt, platform in groups:
        for left, right in contrasts:
            first = index.get((benchmark, left, prompt, platform))
            second = index.get((benchmark, right, prompt, platform))
            if first is None or second is None:
                continue
            output_path = (
                first.path
                / "scores"
                / "pairwise"
                / str(config.judge_id)
                / f"{prompt}-{second.condition}"
                / "scores.jsonl"
            )
            if (output_path.parent / "scores-manifest.json").is_file():
                skipped += 1
                continue
            jobs.append(PairwiseJob(first.root, first, second, output_path, config))
    return jobs, skipped


def run_pairwise(
    roots: list[Path],
    config_path: Path,
    contrasts: tuple[tuple[str, str], ...],
    concurrency: int,
    dry_run: bool,
) -> dict[str, int]:
    _, _, judge_config_type, score_run = _load_experiment_modules()
    config = judge_config_type.load(config_path)
    if config.task != "pairwise":
        raise ValueError("--pairwise-config must have task pairwise")
    jobs, skipped = pairwise_jobs(roots, config, contrasts)
    if dry_run:
        for job in jobs:
            print(f"would score pairwise: {job.first.path} -> {job.output_path}")
        return {"scored": 0, "skipped": skipped, "failed": 0, "pairwise": len(jobs)}

    totals = {"scored": 0, "skipped": skipped, "failed": 0, "pairwise": len(jobs)}
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures: dict[Future[Any], PairwiseJob] = {
            executor.submit(
                score_run,
                job.first.path,
                job.config,
                compare_run_dir=job.second.path,
                output_path=job.output_path,
            ): job
            for job in jobs
        }
        for future in as_completed(futures):
            job = futures[future]
            try:
                future.result()
            except Exception as error:  # noqa: BLE001
                totals["failed"] += 1
                with (job.root / "scoring-errors.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(
                        json.dumps(
                            {
                                "timestamp": datetime.now(UTC).isoformat(),
                                "task": "pairwise",
                                "run_dir": str(job.first.path),
                                "compare_run_dir": str(job.second.path),
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


def main(argv: list[str] | None = None) -> int:
    parse_contrasts, _, _, _ = _load_experiment_modules()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, action="append", required=True)
    parser.add_argument("--pairwise-config", type=Path, required=True)
    parser.add_argument(
        "--contrasts",
        type=parse_contrasts,
        required=True,
        metavar="LEFT:RIGHT,...",
    )
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.concurrency < 1:
        parser.error("--concurrency must be at least 1")
    summary = run_pairwise(
        args.runs_root,
        args.pairwise_config,
        args.contrasts,
        args.concurrency,
        args.dry_run,
    )
    print(
        "scored={scored} skipped={skipped} failed={failed} pairwise={pairwise}".format(
            **summary
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
