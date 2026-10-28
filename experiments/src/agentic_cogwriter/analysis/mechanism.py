"""Report the writing mechanisms each run exercised, from Codex harness records.

Delegations. The event stream's completed ``spawn_agent`` and ``send_input``
items addressed to a child are the Monitor's delegations, in stream order; items
with any other status are ignored. ``resume_agent`` carries only a thread id,
and the task arrives with the next ``send_input``, so it is not a delegation. A
delegation's process is the child's role, from its agent type or the ``$role``
token of the prompt that spawned it, so reusing a child repeats its role. The
n-th delegation to a child starts at the child's n-th ``task_started`` record. A
delegation ends at a completed ``close_agent`` for the child, even one that is
still running, or at a completed ``wait`` that reports the child as completed. A
delegation issued before the previous one ended overlaps it; runs with
overlapping or reused delegations are counted.

File changes. The completed ``FileChange`` items of every rollout that touch
``.writing/goals.md`` or ``.writing/draft.md`` are ordered by completion time. A
change by a delegated child, or by a descendant of one, belongs to that child's
latest delegation started before the change. A change by the Monitor itself
belongs to the interval after the latest delegation started before it. When a
delegation has no matching ``task_started`` record, its start is unknown but
no earlier than the start of any delegation issued before it, so a change that
could belong to it is unattributed: it still updates the goal
lines but counts toward no interval-based measure, and runs with unattributed
changes are counted.

Goal lines. A goal line is a Markdown heading, bullet, or numbered item of
``goals.md``. It is compared in normalized form: heading marks, list markers,
numbering such as ``2.1.``, and checkboxes are removed and whitespace is
collapsed, so renumbering, a heading-level change, a marker swap, a ticked box,
or respacing changes nothing. Leading numbers are removed even when they are
part of the goal's text, so goals that differ only in such a number compare
equal, and a change to that number alone is not counted as a replacement. The
normalized goal lines are replayed through
every change (an added file sets them, a diff removes its ``-`` lines and adds
its ``+`` lines, a deleted file empties them), and each interval that changes
``goals.md`` gets at most one event from its goal lines before and after:

- created: no goal line before, at least one after;
- developed: goal lines before, at least one added, none removed;
- replaced: at least one goal line removed, which includes a rewrite;
- none: any other change, such as a prose-only edit.

Each replaced interval records its removed and added goal lines, normalized and
raw, for a manual audit. A replacement after review is a replaced interval in a
``Planning`` delegation that directly follows a ``Reviewing`` delegation that
had ended; it is the measure comparable to the executed study's accepted goal
replacement.

Process order. ``Planning`` precedes the first ``Translating`` when the first
``Planning`` delegation comes before the first ``Translating`` delegation, or
there is none. ``Planning`` precedes the first section when a ``Planning``
delegation precedes the first ``draft.md`` change that adds a normalized heading;
a run that adds no heading, or whose first such change is unattributed, has no
value. ``Reviewing`` is followed by
``Planning`` when a ``Planning`` delegation directly follows a ``Reviewing``
delegation that had ended.

Aggregation. Rates count runs that pass the fidelity gate, with a 95% Wilson
interval. A condition whose wrapper does not require delegation, such as A8,
which runs every process in the Monitor's own context, reports its
process-derived values as missing; any other condition reports them even when a
run never delegates. The declaration is the run manifest's
``delegation_check.required``; a manifest without it counts as not requiring
delegation.

Unrecorded writes. Only ``apply_patch`` writes become ``FileChange`` items. Each
run therefore lists the shell commands whose write targets ``goals.md``,
``draft.md``, ``.writing`` itself, or a glob under it, by the rules of the
fidelity gate's ``_writes_tracked``, which also counts any ``git reset --hard``,
``git stash`` other than ``list`` or ``show``, ``git apply``, or ``patch -p``. A
script run with a tracked argument is listed although it may not have written,
and a listed command's effect is missing from the events above.
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

from ..runner.fidelity import (
    completed_items,
    read_codex_records,
    spawn_role,
    unrecorded_writes,
)
from .aggregate import wilson_interval

TRACKED = ("goals.md", "draft.md")
DELEGATING_TOOLS = ("spawn_agent", "send_input")
GOAL_EVENTS = ("created", "developed", "replaced")
RATES = (
    "planning_before_first_translating",
    "planning_before_first_section",
    "reviewing_then_planning",
    *(f"goal_{event}" for event in GOAL_EVENTS),
    "goal_replaced_after_review",
)
# Values that need delegations; missing for conditions that declare none.
PROCESS_DERIVED = frozenset(
    {
        "planning_before_first_translating",
        "planning_before_first_section",
        "reviewing_then_planning",
        "goal_replaced_after_review",
        "mean_processes",
        "runs_with_reused_children",
        "runs_with_overlapping_delegations",
        "runs_with_unattributed_changes",
    }
)
COUNTS = (
    "runs_with_unrecorded_writes",
    "unrecorded_writes",
    "runs_with_reused_children",
    "runs_with_overlapping_delegations",
    "runs_with_unattributed_changes",
)
_GOAL_LINE = re.compile(r"^(?:#{1,6}|[-*+]|\d+(?:\.\d+)*[.)])\s")
_HEADING = re.compile(r"^#{1,6}\s")
_PREFIX = re.compile(r"^(?:#{1,6}\s+|[-*+]\s+|\[[ xX]\]\s*|\d+(?:\.\d+)*[.)]?\s+)+")


class _Change(NamedTuple):
    at: float
    file: str
    change: dict[str, Any]
    delegation: int | None
    by_monitor: bool


def normalize(line: str) -> str:
    """Return a goal or heading line without markers, numbering, or extra spaces."""

    return " ".join(_PREFIX.sub("", line.strip()).split())


def _lines(lines: Iterable[str], pattern: re.Pattern[str]) -> dict[str, list[str]]:
    """Map each normalized matching line to its raw forms, in order."""

    found: dict[str, list[str]] = defaultdict(list)
    for line in lines:
        if pattern.match(line.strip()) and normalize(line):
            found[normalize(line)].append(line.strip())
    return found


def _counter(found: dict[str, list[str]]) -> Counter[str]:
    return Counter({key: len(raws) for key, raws in found.items()})


def _diff(change: dict[str, Any], sign: str, pattern: re.Pattern[str]):
    diff = str(change.get("unified_diff", "")).splitlines()
    return _lines((line[1:] for line in diff if line.startswith(sign)), pattern)


def _content(change: dict[str, Any], pattern: re.Pattern[str]):
    return _lines(str(change.get("content", "")).splitlines(), pattern)


def classify_goal_intervals(
    intervals: Iterable[Iterable[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Give each ordered interval of ``goals.md`` changes at most one event."""

    result: list[dict[str, Any]] = []
    goals: Counter[str] = Counter()
    raw: dict[str, str] = {}
    for changes in intervals:
        before, raw_before = goals, dict(raw)
        for change in changes:
            kind = change.get("type")
            if kind == "add":
                added = _content(change, _GOAL_LINE)
                goals = _counter(added)
            elif kind == "update":
                added = _diff(change, "+", _GOAL_LINE)
                goals = goals - _counter(_diff(change, "-", _GOAL_LINE))
                goals += _counter(added)
            elif kind == "delete":
                added, goals = {}, Counter()
            else:
                continue
            raw.update({key: raws[-1] for key, raws in added.items()})
        removed, gained = before - goals, goals - before
        interval: dict[str, Any] = {"event": None}
        if removed:
            interval = {
                "event": "replaced",
                "removed": [
                    {"normalized": key, "raw": raw_before.get(key)} for key in removed
                ],
                "added": [{"normalized": key, "raw": raw.get(key)} for key in gained],
            }
        elif gained:
            interval["event"] = "developed" if before else "created"
        result.append(interval)
    return result


def adds_section(change: dict[str, Any]) -> bool:
    """Return whether a ``draft.md`` change adds a normalized heading line."""

    if change.get("type") == "add":
        return bool(_content(change, _HEADING))
    if change.get("type") == "update":
        added = _counter(_diff(change, "+", _HEADING))
        return bool(added - _counter(_diff(change, "-", _HEADING)))
    return False


def _ms(timestamp: Any) -> float:
    try:
        return datetime.fromisoformat(str(timestamp)).timestamp() * 1000
    except ValueError:
        return float("inf")


def _ended(item: dict[str, Any], thread: str) -> bool:
    if item.get("status") != "completed" or thread not in (
        item.get("receiver_thread_ids") or []
    ):
        return False
    if item.get("tool") == "close_agent":
        return True
    state = (item.get("agents_states") or {}).get(thread)
    return item.get("tool") == "wait" and (
        isinstance(state, dict) and state.get("status") == "completed"
    )


def analyze_run(run_dir: Path) -> dict[str, Any]:
    """Return one run's delegations, goal intervals, and mechanism flags."""

    events, metas, records, _ = read_codex_records(run_dir)
    prompts: dict[str, str] = {}
    delegations: list[dict[str, Any]] = []
    for item in completed_items(events):
        if item.get("type") != "collab_tool_call":
            continue
        for thread in item.get("receiver_thread_ids") or []:
            if item.get("tool") in DELEGATING_TOOLS:
                if item.get("status") != "completed":
                    continue
                prompts.setdefault(thread, str(item.get("prompt")))
                delegations.append(
                    {
                        "thread": thread,
                        "tool": item["tool"],
                        "ended": False,
                        # Issued while an earlier delegation was still open.
                        "overlaps": any(not d["ended"] for d in delegations),
                        "previous_ended": bool(delegations)
                        and delegations[-1]["ended"],
                    }
                )
            elif _ended(item, thread):
                for delegation in delegations:
                    if delegation["thread"] == thread:
                        delegation["ended"] = True
    for delegation in delegations:
        thread = delegation["thread"]
        delegation["process"] = (
            spawn_role(metas.get(thread, {}), prompts[thread]) or "other"
        )
    processes = [d["process"] for d in delegations]

    # The n-th delegation to a child starts with the child's n-th turn.
    turns = {
        thread: [
            _ms(record.get("timestamp"))
            for record in thread_records
            if record.get("type") == "event_msg"
            and (record.get("payload") or {}).get("type") == "task_started"
        ]
        for thread, thread_records in records.items()
    }
    starts: list[float] = []
    seen: Counter[str] = Counter()
    for delegation in delegations:
        thread = delegation["thread"]
        thread_turns = turns.get(thread, [])
        n = seen[thread]
        starts.append(thread_turns[n] if n < len(thread_turns) else float("inf"))
        seen[thread] += 1

    # A delegation starts no earlier than any delegation issued before it.
    earliest = [
        max((start for start in starts[: k + 1] if start != float("inf")), default=0)
        for k in range(len(starts))
    ]
    delegated = {d["thread"] for d in delegations}

    def position(thread: str | None, at: float) -> tuple[int | None, bool]:
        """Return the change's delegation, or None, and whether the Monitor made it."""
        while thread in metas and thread not in delegated:
            thread = metas[thread].get("parent_thread_id")
        by_monitor = thread not in delegated
        candidates = (
            range(len(delegations))
            if by_monitor
            else [k for k, d in enumerate(delegations) if d["thread"] == thread]
        )
        started = [k for k in candidates if starts[k] <= at]
        k = started[-1] if started else (-1 if by_monitor else candidates[0])
        # A delegation with an unknown start that may have begun may own it.
        if any(
            starts[j] == float("inf") and earliest[j] <= at
            for j in candidates
            if j >= k
        ):
            return None, by_monitor
        return k, by_monitor

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
            at = float(payload.get("completed_at_ms") or 0)
            for path, change in (item.get("changes") or {}).items():
                parts = PurePosixPath(path).parts[-2:]
                if parts[0] == ".writing" and parts[-1] in TRACKED:
                    changes.append(
                        _Change(at, parts[-1], change, *position(thread, at))
                    )
    changes.sort(key=attrgetter("at"))

    intervals = [
        (delegation, by_monitor, [c.change for c in group])
        for (delegation, by_monitor), group in groupby(
            (c for c in changes if c.file == "goals.md"),
            key=attrgetter("delegation", "by_monitor"),
        )
    ]
    goal_intervals = [
        {
            "delegation": delegation,
            "process": "unattributed"
            if delegation is None
            else "monitor"
            if by_monitor
            else processes[delegation],
            **interval,
        }
        for (delegation, by_monitor, _), interval in zip(
            intervals,
            classify_goal_intervals(group for *_, group in intervals),
            strict=True,
        )
    ]

    def after_review(k: int) -> bool:
        """Return whether delegation k is Planning right after an ended Reviewing."""
        return (
            k > 0
            and processes[k] == "planning"
            and processes[k - 1] == "reviewing"
            and delegations[k]["previous_ended"]
        )

    first_section = next(
        (c for c in changes if c.file == "draft.md" and adds_section(c.change)), None
    )
    preceding = (
        None
        if first_section is None or first_section.delegation is None
        else first_section.delegation + first_section.by_monitor
    )
    translating = processes.index("translating") if "translating" in processes else None
    writes = [
        {"thread": thread, "command": command}
        for thread, thread_records in records.items()
        for command in unrecorded_writes(thread_records)
    ]
    return {
        "processes": processes,
        "delegations": [
            {key: d[key] for key in ("thread", "tool", "process", "overlaps")}
            for d in delegations
        ],
        "goal_intervals": goal_intervals,
        "planning_before_first_translating": "planning" in processes[:translating],
        "planning_before_first_section": None
        if preceding is None
        else "planning" in processes[:preceding],
        "reviewing_then_planning": any(map(after_review, range(len(processes)))),
        **{
            f"goal_{event}": any(
                i["event"] == event and i["process"] != "unattributed"
                for i in goal_intervals
            )
            for event in GOAL_EVENTS
        },
        "goal_replaced_after_review": any(
            i["event"] == "replaced"
            and i["process"] not in ("monitor", "unattributed")
            and after_review(i["delegation"])
            for i in goal_intervals
        ),
        "reused_children": sum(d["tool"] != "spawn_agent" for d in delegations),
        "overlapping_delegations": sum(d["overlaps"] for d in delegations),
        "unattributed_changes": sum(c.delegation is None for c in changes),
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
    """Aggregate gate-passing runs: each rate with a 95% Wilson interval."""

    scorable = [run for run in runs if run["fidelity"] == "scorable"]
    summary = {
        "runs": len(runs),
        "completed": sum(run["status"] == "completed" for run in runs),
        "scorable": len(scorable),
        **{
            metric: _rate([run[metric] for run in scorable if run[metric] is not None])
            for metric in RATES
        },
        "no_first_section_runs": sum(
            run["planning_before_first_section"] is None for run in scorable
        ),
        "mean_processes": (
            sum(len(run["processes"]) for run in scorable) / len(scorable)
            if scorable
            else None
        ),
        "runs_with_unrecorded_writes": sum(
            bool(run["unrecorded_writes"]) for run in scorable
        ),
        "unrecorded_writes": sum(len(run["unrecorded_writes"]) for run in scorable),
        "runs_with_reused_children": sum(
            bool(run["reused_children"]) for run in scorable
        ),
        "runs_with_overlapping_delegations": sum(
            bool(run["overlapping_delegations"]) for run in scorable
        ),
        "runs_with_unattributed_changes": sum(
            bool(run["unattributed_changes"]) for run in scorable
        ),
    }
    if not any(run["delegation_required"] for run in runs):
        summary.update(dict.fromkeys(PROCESS_DERIVED))
    return summary


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
                "delegation_required": bool(
                    (manifest.get("delegation_check") or {}).get("required")
                ),
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
    """Render per-condition summaries as a Markdown table with its notes."""

    columns = ("runs", "completed", "scorable", *RATES, "mean_processes", *COUNTS)
    lines = [
        "| condition | " + " | ".join(columns) + " |",
        "|---|" + "---:|" * len(columns),
    ]
    for condition, row in summary.items():
        cells = " | ".join(_cell(row[column]) for column in columns)
        lines.append(f"| {condition} | {cells} |")
    excluded = ", ".join(
        f"{condition} {row['no_first_section_runs']}"
        for condition, row in summary.items()
    )
    lines += [
        "",
        "Rates and counts cover scorable runs. goal_replaced_after_review is "
        "comparable to the executed study's accepted goal replacement; "
        "goal_replaced counts every removed or rewritten goal. "
        "planning_before_first_section excludes runs without an attributed "
        "first heading "
        f"({excluded}). n/a: the condition does not delegate.",
    ]
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
