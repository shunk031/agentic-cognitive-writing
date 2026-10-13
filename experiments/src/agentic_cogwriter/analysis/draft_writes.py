"""Count how many runs write their draft file more than once.

A write is a Codex `file_change` item that touches the file, the measure that
reproduces the plain-agent (A11) draft-revision count. For A11 every workspace
file counts except `.writing/assumptions.md` and the trace; for other
conditions only `.writing/draft.md` counts. A run counts as rewriting when it
writes one counted file two or more times.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from .common import select_canonical_runs

EXCLUDED = (".writing/assumptions.md", ".writing/trace/")


def file_writes(events: Iterable[dict[str, Any]], any_file: bool) -> Counter[str]:
    counts: Counter[str] = Counter()
    for event in events:
        item = event.get("item") or {}
        if event.get("type") != "item.completed" or item.get("type") != "file_change":
            continue
        for change in item.get("changes", []):
            path = change.get("path", "").split("/workspace/", 1)[-1]
            if path.startswith(EXCLUDED) or (not any_file and path != ".writing/draft.md"):
                continue
            counts[path] += 1
    return counts


def summarize(per_run: Sequence[Counter[str]]) -> dict[str, int]:
    rewrote = sum(1 for c in per_run if c and max(c.values()) >= 2)
    return {"completed_runs": len(per_run), "wrote_draft": sum(1 for c in per_run if c), "rewrote_draft": rewrote}


def analyze(roots: Sequence[Path], condition: str) -> dict[str, int]:
    per_run = []
    for run in select_canonical_runs(list(roots)):
        if run.condition != condition or run.status != "completed":
            continue
        events = []
        for path in sorted(run.path.glob("attempt-*.events.jsonl")):
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        per_run.append(file_writes(events, any_file=condition == "A11"))
    return summarize(per_run)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--condition", action="append", required=True, help="condition=root[,root...]")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = {}
    for spec in args.condition:
        condition, roots = spec.split("=", 1)
        report[condition] = analyze([Path(r) for r in roots.split(",")], condition)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
