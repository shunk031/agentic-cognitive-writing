"""Report the writing mechanisms each run exercised, from Codex harness records.

The process sequence is the role of each child the Monitor spawned, in spawn
order. File changes come from the completed ``FileChange`` items of every
rollout that touch ``.writing/goals.md`` or ``.writing/draft.md``, in
completion order. A change by a delegated child, or by a descendant of one,
belongs to that delegation; a change by the Monitor itself belongs to the
interval after the last delegation spawned before it.

A goal line is a non-blank line of ``goals.md`` that is a Markdown heading or
list item. The goal lines are replayed through every change (an added file sets
them, a diff removes its ``-`` lines and adds its ``+`` lines, a deleted file
empties them), and each delegation interval that changes ``goals.md`` is
classified by its goal lines before and after; one interval can show several
events:

- created: ``goals.md`` first appears, or the interval gains a goal line and
  removes none;
- developed: goal lines existed before and none was removed;
- replaced: a goal line before is missing after, so it was removed or rewritten.

A section is a Markdown heading line. ``Planning`` precedes the first section
when a ``Planning`` delegation precedes the first change that adds a heading to
``draft.md``; a run that adds no heading has no value. ``Reviewing`` is followed
by ``Planning`` when the delegation right after a ``Reviewing`` delegation is
``Planning``.

Only ``apply_patch`` writes become ``FileChange`` items. Each run therefore
lists the shell commands that mention ``goals.md`` or ``draft.md`` and look like
writes (a redirection, ``tee``, ``sed -i``, ``cp``, ``mv``, ``rm``, ``touch``,
an interpreter, or a ``git`` checkout); the match is textual, so a listed
command may not have written, and its effect is missing from the events above.
Goal lines supplied with the task are unknown, so the first change to a seeded
``goals.md`` counts as creation.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from datetime import datetime
from itertools import groupby
from operator import attrgetter
from pathlib import Path, PurePosixPath
from typing import Any, NamedTuple

from ..runner.fidelity import completed_items, read_codex_records, spawn_role
from .aggregate import wilson_interval

TRACKED = ("goals.md", "draft.md")
GOAL_EVENTS = ("created", "developed", "replaced")
RATES = (
    "planning_before_first_section",
    "reviewing_then_planning",
    *(f"goal_{event}" for event in GOAL_EVENTS),
)
_GOAL_LINE = re.compile(r"^(?:#{1,6}|[-*+]|\d+[.)])\s")
_HEADING = re.compile(r"^#{1,6}\s")
_COMMAND = re.compile(r"""\bcmd"?\s*:\s*(["'`])((?:(?!\1)[^\\]|\\.)*)\1""")
_TARGET = re.compile(r"\b(?:goals|draft)\.md\b")
_HARMLESS_REDIRECT = re.compile(r"\d*>\s*/dev/null|\d*>&\d")
_WRITE = re.compile(
    r">|\b(?:tee|cp|mv|rm|touch|truncate|dd|install|python3?|perl|ruby|node)\b"
    r"|\bsed\s+(?:-\w+\s+)*-i|\bgit\s+(?:checkout|restore|apply|reset|stash)\b"
)


class _Change(NamedTuple):
    at: int
    file: str
    change: dict[str, Any]
    delegation: int
    preceding: int


def _lines(lines: Iterable[str], pattern: re.Pattern[str]) -> Counter[str]:
    return Counter(line.strip() for line in lines if pattern.match(line.strip()))


def _diff(change: dict[str, Any], sign: str, pattern: re.Pattern[str]) -> Counter:
    diff = str(change.get("unified_diff", "")).splitlines()
    return _lines((line[1:] for line in diff if line.startswith(sign)), pattern)


def _apply(goals: Counter[str], exists: bool, change: dict[str, Any]):
    kind = change.get("type")
    if kind == "add":
        content = str(change.get("content", "")).splitlines()
        return _lines(content, _GOAL_LINE), True
    if kind == "update":
        removed = _diff(change, "-", _GOAL_LINE)
        return goals - removed + _diff(change, "+", _GOAL_LINE), True
    if kind == "delete":
        return Counter(), False
    return goals, exists


def classify_goal_intervals(
    intervals: Iterable[Iterable[dict[str, Any]]],
) -> list[list[str]]:
    """Classify each ordered interval of ``goals.md`` changes."""

    result: list[list[str]] = []
    goals: Counter[str] = Counter()
    exists = False
    for changes in intervals:
        before, existed = goals, exists
        for change in changes:
            goals, exists = _apply(goals, exists, change)
        events = []
        if (exists and not existed) or (goals - before and not before - goals):
            events.append("created")
        if before and not before - goals:
            events.append("developed")
        if before - goals:
            events.append("replaced")
        result.append(events)
    return result


def adds_section(change: dict[str, Any]) -> bool:
    """Return whether a ``draft.md`` change adds a Markdown heading line."""

    if change.get("type") == "add":
        return bool(_lines(str(change.get("content", "")).splitlines(), _HEADING))
    if change.get("type") == "update":
        return bool(_diff(change, "+", _HEADING) - _diff(change, "-", _HEADING))
    return False


def _commands(payload: dict[str, Any]) -> list[str]:
    kind = payload.get("type")
    if kind == "custom_tool_call":
        commands = []
        for quote, text in _COMMAND.findall(str(payload.get("input", ""))):
            try:
                commands.append(json.loads(f'"{text}"') if quote == '"' else text)
            except json.JSONDecodeError:
                commands.append(text)
        return commands
    if kind == "function_call":
        try:
            arguments = json.loads(payload.get("arguments") or "{}")
        except json.JSONDecodeError:
            return []
        command = arguments.get("cmd") or arguments.get("command")
    elif kind == "local_shell_call":
        command = (payload.get("action") or {}).get("command")
    else:
        return []
    if isinstance(command, list):
        command = " ".join(map(str, command))
    return [command] if isinstance(command, str) else []


def unrecorded_writes(records: Iterable[dict[str, Any]]) -> list[str]:
    """Return shell commands that look like writes to ``goals.md`` or ``draft.md``."""

    return [
        command
        for record in records
        if record.get("type") == "response_item"
        and isinstance(record.get("payload"), dict)
        for command in _commands(record["payload"])
        if _TARGET.search(command)
        and "apply_patch" not in command
        and _WRITE.search(_HARMLESS_REDIRECT.sub("", command))
    ]


def _ms(timestamp: Any) -> float:
    try:
        return datetime.fromisoformat(str(timestamp)).timestamp() * 1000
    except ValueError:
        return float("inf")


def analyze_run(run_dir: Path) -> dict[str, Any]:
    """Return one run's processes, goal intervals, and mechanism flags."""

    events, metas, records, _ = read_codex_records(run_dir)
    delegations = [
        (thread, spawn_role(metas.get(thread, {}), str(item.get("prompt"))) or "other")
        for item in completed_items(events)
        if item.get("type") == "collab_tool_call" and item.get("tool") == "spawn_agent"
        for thread in item.get("receiver_thread_ids") or []
    ]
    processes = [role for _, role in delegations]
    index = {thread: k for k, (thread, _) in enumerate(delegations)}
    starts = [_ms(metas.get(thread, {}).get("timestamp")) for thread in index]

    def position(thread: str | None, at: int) -> tuple[int, int]:
        # The delegation interval a change falls in, and the delegations before it.
        while thread in metas and thread not in index:
            thread = metas[thread].get("parent_thread_id")
        if thread in index:
            return index[thread], index[thread]
        started = sum(start <= at for start in starts)
        return started - 1, started

    changes = []
    for thread, thread_records in records.items():
        for record in thread_records:
            payload = record.get("payload")
            item = payload.get("item") if isinstance(payload, dict) else None
            if (
                not isinstance(item, dict)
                or record.get("type") != "event_msg"
                or payload.get("type") != "item_completed"
                or item.get("type") != "FileChange"
                or item.get("status") != "completed"
            ):
                continue
            at = int(payload.get("completed_at_ms") or 0)
            for path, change in (item.get("changes") or {}).items():
                parts = PurePosixPath(path).parts[-2:]
                if parts[0] == ".writing" and parts[-1] in TRACKED:
                    changes.append(
                        _Change(at, parts[-1], change, *position(thread, at))
                    )
    changes.sort(key=attrgetter("at"))

    intervals = [
        (delegation, [c.change for c in group])
        for delegation, group in groupby(
            (c for c in changes if c.file == "goals.md"), key=attrgetter("delegation")
        )
    ]
    goal_intervals = [
        {"delegation": delegation, "events": events}
        for (delegation, _), events in zip(
            intervals,
            classify_goal_intervals(group for _, group in intervals),
            strict=True,
        )
    ]
    first_section = next(
        (c for c in changes if c.file == "draft.md" and adds_section(c.change)), None
    )
    writes = [
        {"thread": thread, "command": command}
        for thread, thread_records in records.items()
        for command in unrecorded_writes(thread_records)
    ]
    return {
        "processes": processes,
        "goal_intervals": goal_intervals,
        "planning_before_first_section": None
        if first_section is None
        else "planning" in processes[: first_section.preceding],
        "reviewing_then_planning": any(
            pair == ("reviewing", "planning")
            for pair in zip(processes, processes[1:], strict=False)
        ),
        **{
            f"goal_{event}": any(event in i["events"] for i in goal_intervals)
            for event in GOAL_EVENTS
        },
        "unrecorded_writes": writes,
    }


def _rate(values: Sequence[bool]) -> dict[str, Any]:
    count, total = sum(values), len(values)
    low, high = wilson_interval(count, total - count)
    return {
        "count": count,
        "total": total,
        "rate": count / total if total else None,
        "ci95": [low, high],
    }


def summarize(runs: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate completed runs: each mechanism's rate with a 95% Wilson interval."""

    completed = [run for run in runs if run["status"] == "completed"]
    return {
        "runs": len(runs),
        "completed": len(completed),
        "scorable": sum(run["fidelity"] == "scorable" for run in runs),
        **{
            metric: _rate([run[metric] for run in completed if run[metric] is not None])
            for metric in RATES
        },
        "mean_processes": (
            sum(len(run["processes"]) for run in completed) / len(completed)
            if completed
            else None
        ),
        "runs_with_unrecorded_writes": sum(
            bool(run["unrecorded_writes"]) for run in runs
        ),
        "unrecorded_writes": sum(len(run["unrecorded_writes"]) for run in runs),
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
    if isinstance(value, dict):
        if not value["total"]:
            return "0/0"
        low, high = value["ci95"]
        return (
            f"{value['count']}/{value['total']} {value['rate']:.2f} "
            f"[{low:.2f}, {high:.2f}]"
        )
    return f"{value:.2f}" if isinstance(value, float) else str(value)


def format_table(summary: dict[str, dict[str, Any]]) -> str:
    """Render per-condition summaries as a Markdown table."""

    columns = (
        "runs",
        "completed",
        "scorable",
        *RATES,
        "mean_processes",
        "runs_with_unrecorded_writes",
        "unrecorded_writes",
    )
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
