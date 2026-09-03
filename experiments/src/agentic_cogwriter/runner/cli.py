"""Command-line entrypoint for prompt-manifest runs."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..paths import EXPERIMENTS_ROOT
from .conditions import CONDITION_IDS
from .config import RuntimeConfig
from .manifest import load_prompt_manifest
from .runner import ExperimentRunner


def build_parser() -> argparse.ArgumentParser:
    """Build the experimenter-facing command parser."""

    parser = argparse.ArgumentParser(description="Run one scored writing condition.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--prompt-id", required=True)
    parser.add_argument(
        "--condition",
        choices=CONDITION_IDS,
        required=True,
    )
    parser.add_argument(
        "--platform",
        choices=("codex-primary", "claude-code-replication"),
        required=True,
    )
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=Path("runs"))
    parser.add_argument(
        "--codex-plugin-root",
        type=Path,
        default=None,
        help=(
            "Filesystem root containing skills/<skill>/SKILL.md for Codex; "
            "defaults to the selected wrapper's configured plugin paths"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one prompt and return a process status."""

    args = build_parser().parse_args(argv)
    config_path = args.config or EXPERIMENTS_ROOT / "config" / "runtime.json"
    manifest = load_prompt_manifest(args.manifest)
    runner = ExperimentRunner(
        RuntimeConfig.load(config_path),
        output_root=args.output_root,
        codex_plugin_root=args.codex_plugin_root,
    )
    result = runner.run_prompt(
        manifest.get(args.prompt_id),
        condition_id=args.condition,
        platform=args.platform,
    )
    print(result.run_dir)
    return 0
