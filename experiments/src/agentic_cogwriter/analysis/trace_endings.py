"""Describe how Agentic CogWriter runs end and how often the Monitor fallback was used.

For every completed canonical A4 run, the logged path is the sequence of
`process_switch` targets in the trace. A run whose logged path ends at Planning
or Translating is checked against the Codex event stream: when the last
`spawn_agent` call delegated the Reviewing role, a final review ran without a
logged switch. The Monitor fallback (performing a role itself when native
delegation is unavailable) is counted when a `process_switch` decision says so,
which the skill requires the Monitor to record.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .common import select_canonical_runs

FULL = "A4"
ROLE = re.compile(r"\$(planning|translating|reviewing)\b")
PROCESSES = ("planning", "translating", "reviewing")


def last_delegated_role(run_path: Path) -> str | None:
    """Return the role named by the last spawn_agent call, if any names one."""
    last: str | None = None
    for event_path in sorted(run_path.glob("attempt-*.events.jsonl")):
        for line in event_path.read_text(
            encoding="utf-8", errors="ignore"
        ).splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            item = value.get("item") if isinstance(value, dict) else None
            if (
                value.get("type") == "item.started"
                and isinstance(item, dict)
                and item.get("tool") == "spawn_agent"
            ):
                match = ROLE.search(item.get("prompt") or "")
                last = match.group(1) if match else None
    return last


def summarize_run(
    events: Sequence[dict[str, Any]], last_role: str | None
) -> dict[str, Any]:
    path = [
        event["to_process"]
        for event in events
        if event.get("event_type") == "process_switch"
        and event.get("to_process") in PROCESSES
    ]
    decisions = " ".join(str(event.get("decision", "")) for event in events).casefold()
    return {
        "last_logged_process": path[-1] if path else None,
        "last_delegated_role": last_role,
        "fallback_recorded": "fallback" in decisions,
    }


def analyze(runs: Sequence[dict[str, Any]]) -> dict[str, Any]:
    endings = Counter(run["last_logged_process"] for run in runs)
    early = [
        run for run in runs if run["last_logged_process"] in ("planning", "translating")
    ]
    return {
        "completed_runs": len(runs),
        "last_logged_process": dict(sorted((str(k), v) for k, v in endings.items())),
        "ending_before_reviewing": len(early),
        "ending_before_reviewing_last_delegated_reviewer": sum(
            run["last_delegated_role"] == "reviewing" for run in early
        ),
        "fallback_recorded_runs": sum(run["fallback_recorded"] for run in runs),
    }


def analyze_roots(roots: Sequence[Path]) -> dict[str, Any]:
    runs = []
    for root in roots:
        for run in select_canonical_runs([root]):
            if run.condition != FULL or run.status != "completed":
                continue
            trace = run.path / ".writing" / "trace" / "process.jsonl"
            events = [
                json.loads(line)
                for line in trace.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            runs.append(summarize_run(events, last_delegated_role(run.path)))
    return analyze(runs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs-root", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    text = json.dumps(analyze_roots(args.runs_root), indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
