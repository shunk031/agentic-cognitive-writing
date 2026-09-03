"""Command-line entry point for scoring completed runner artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from .config import JudgeConfig
from .scorer import score_run


def build_parser() -> argparse.ArgumentParser:
    """Build the scorer command parser."""

    parser = argparse.ArgumentParser(
        description="Score a completed Agentic CogWriter run with one API judge."
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--task", choices=("pointwise", "pairwise"), default=None)
    parser.add_argument("--compare-run-dir", type=Path, default=None)
    parser.add_argument("--presentation", choices=("A|B", "B|A"), default=None)
    parser.add_argument("--output", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Score one run and print the resulting JSONL path."""

    args = build_parser().parse_args(argv)
    config = JudgeConfig.load(args.config)
    if args.task is not None and args.task != config.task:
        raise SystemExit("--task does not match the judge configuration")
    result = score_run(
        args.run_dir,
        config,
        compare_run_dir=args.compare_run_dir,
        presentation=args.presentation,
        output_path=args.output,
    )
    print(result.scores_path)
    return 0
