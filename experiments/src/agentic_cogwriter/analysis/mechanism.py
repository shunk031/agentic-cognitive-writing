"""Report the writing mechanisms each run exercised, from Codex harness records.

The process sequence is the role of each child the Monitor spawned, in spawn
order. Goal events come from the completed ``FileChange`` items of every
rollout that touch ``.writing/goals.md``, in completion order.

A goal line is a non-blank line of ``goals.md`` that is a Markdown heading or
list item. Each change updates the multiset of goal lines (an added file sets
it, a diff removes its ``-`` lines and adds its ``+`` lines, a deleted file
empties it) and is classified by the goal lines before and after it:

- created: no goal line before, at least one after;
- replaced: a goal line before is missing after, so it was removed or rewritten;
- developed: goal lines before and none missing after.

Known limits: a write outside ``apply_patch``, such as a shell redirect, makes
no ``FileChange`` item; goals written without headings or list items have no
goal lines; and goal lines supplied with the task are unknown, so the first
change to a seeded ``goals.md`` counts as creation.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from ..runner.fidelity import completed_items, read_codex_records, spawn_role

GOALS = (".writing", "goals.md")
GOAL_EVENTS = ("created", "developed", "replaced")
_GOAL_LINE = re.compile(r"^(?:#{1,6}|[-*+]|\d+[.)])\s")
METRICS = (
    "planning_before_first_translating",
    "reviewing_then_planning",
    *(f"goal_{event}" for event in GOAL_EVENTS),
)


def _goal_lines(lines: Iterable[str]) -> Counter[str]:
    return Counter(line.strip() for line in lines if _GOAL_LINE.match(line.strip()))


def classify_goal_changes(changes: Iterable[dict[str, Any]]) -> list[str]:
    """Classify ordered ``goals.md`` changes as created, developed, or replaced."""

    events: list[str] = []
    goals: Counter[str] = Counter()
    for change in changes:
        kind = change.get("type")
        if kind == "add":
            after = _goal_lines(str(change.get("content", "")).splitlines())
        elif kind == "update":
            diff = str(change.get("unified_diff", "")).splitlines()
            after = (
                goals
                - _goal_lines(line[1:] for line in diff if line.startswith("-"))
                + _goal_lines(line[1:] for line in diff if line.startswith("+"))
            )
        elif kind == "delete":
            after = Counter()
        else:
            continue
        if not goals:
            if after:
                events.append("created")
        elif goals - after:
            events.append("replaced")
        else:
            events.append("developed")
        goals = after
    return events


def _goals_changes(records: Iterable[dict[str, Any]]) -> list[tuple[int, dict]]:
    changes = []
    for record in records:
        payload = record.get("payload")
        if record.get("type") != "event_msg" or not isinstance(payload, dict):
            continue
        item = payload.get("item")
        if (
            payload.get("type") != "item_completed"
            or not isinstance(item, dict)
            or item.get("type") != "FileChange"
            or item.get("status") != "completed"
        ):
            continue
        for path, change in (item.get("changes") or {}).items():
            if PurePosixPath(path).parts[-2:] == GOALS and isinstance(change, dict):
                changes.append((int(payload.get("completed_at_ms") or 0), change))
    return changes


def analyze_run(run_dir: Path) -> dict[str, Any]:
    """Return one run's process sequence, goal events, and mechanism flags."""

    events, metas, records, _ = read_codex_records(run_dir)
    processes = [
        spawn_role(metas.get(thread, {}), str(item.get("prompt"))) or "other"
        for item in completed_items(events)
        if item.get("type") == "collab_tool_call" and item.get("tool") == "spawn_agent"
        for thread in item.get("receiver_thread_ids") or []
    ]
    changes = sorted(
        (
            change
            for thread_records in records.values()
            for change in _goals_changes(thread_records)
        ),
        key=lambda change: change[0],
    )
    goal_events = classify_goal_changes(change for _, change in changes)
    translating = processes.index("translating") if "translating" in processes else None
    return {
        "processes": processes,
        "goal_events": goal_events,
        "planning_before_first_translating": "planning" in processes[:translating],
        "reviewing_then_planning": any(
            pair == ("reviewing", "planning")
            for pair in zip(processes, processes[1:], strict=False)
        ),
        **{f"goal_{event}": event in goal_events for event in GOAL_EVENTS},
    }


def summarize(runs: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate completed runs: the share showing each mechanism."""

    completed = [run for run in runs if run["status"] == "completed"]
    total = len(completed)
    return {
        "runs": len(runs),
        "completed": total,
        "scorable": sum(run["fidelity"] == "scorable" for run in runs),
        **{
            metric: sum(run[metric] for run in completed) / total if total else None
            for metric in METRICS
        },
        "mean_processes": (
            sum(len(run["processes"]) for run in completed) / total if total else None
        ),
    }


def report(roots: Sequence[Path]) -> dict[str, dict[str, Any]]:
    """Write ``mechanism.json`` next to each run manifest and aggregate by condition."""

    by_condition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for root in roots:
        for manifest_path in sorted(root.rglob("run-manifest.json")):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            run = {
                "condition": manifest["inputs"]["condition_id"],
                "prompt": manifest["inputs"]["prompt_id"],
                "status": manifest.get("status"),
                "fidelity": (manifest.get("fidelity_gate") or {}).get("status"),
                **analyze_run(manifest_path.parent),
            }
            (manifest_path.parent / "mechanism.json").write_text(
                json.dumps(run, indent=2) + "\n", encoding="utf-8"
            )
            by_condition[run["condition"]].append(run)
    return {
        condition: summarize(runs) for condition, runs in sorted(by_condition.items())
    }


def _cell(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}" if isinstance(value, float) else str(value)


def format_table(summary: dict[str, dict[str, Any]]) -> str:
    """Render per-condition summaries as a Markdown table."""

    columns = ("runs", "completed", "scorable", *METRICS, "mean_processes")
    lines = [
        "| condition | " + " | ".join(columns) + " |",
        "|---|" + "---:|" * len(columns),
    ]
    for condition, row in summary.items():
        cells = " | ".join(_cell(row[column]) for column in columns)
        lines.append(f"| {condition} | {cells} |")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report Monitor processes and goal events from harness records."
    )
    parser.add_argument("--runs-root", type=Path, action="append", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(format_table(report(args.runs_root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
