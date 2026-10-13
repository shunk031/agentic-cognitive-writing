"""Mean subagent spawns per attempted run, per condition.

Each canonical run's manifest records `subagent_spawn_count` from its Codex
event stream; the mean covers attempted runs, completed or not, the same unit
as the process summary's `mean_spawns_per_attempted_run`.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from statistics import fmean

from .common import select_canonical_runs


def mean_spawns(counts: dict[str, list[int]]) -> dict[str, dict[str, float]]:
    return {c: {"attempted_runs": len(v), "mean_spawns": fmean(v)} for c, v in sorted(counts.items()) if v}


def analyze(roots: Sequence[Path], conditions: Sequence[str]) -> dict[str, dict[str, float]]:
    counts: dict[str, list[int]] = {}
    for run in select_canonical_runs(list(roots)):
        if run.condition in conditions:
            counts.setdefault(run.condition, []).append(int(run.manifest.get("subagent_spawn_count") or 0))
    return mean_spawns(counts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs-root", type=Path, action="append", required=True)
    parser.add_argument("--condition", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.write_text(json.dumps(analyze(args.runs_root, args.condition), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
