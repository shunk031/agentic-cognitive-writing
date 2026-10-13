#!/usr/bin/env python3
"""Append trace events and check the writing state for the Agentic CogWriter skills.

Run from the project root. Subcommands:

``log [--no-goals]``
    Read events from standard input as ``key: value`` lines, one event per
    block, blocks separated by a ``---`` line. Keys are ``event_type``,
    ``to_process``, ``decision``, ``regeneration_proposals``, ``evidence`` and
    ``open_uncertainty`` (repeat the key, or list ``- item`` lines under it),
    ``goal_id``, ``parent_goal_id``, and an optional ``responsible_agent``.
    The script fills ``timestamp``, ``process``, and ``from_process``,
    requires the post-Reviewing ledger on a switch that leaves ``reviewing``,
    validates every event, and appends nothing unless all of them are valid.
    ``--no-goals`` refuses goal events and the ledger.
``check``
    Verify that the trace parses, print the logged process path, and print
    each goal in ``.writing/goals.md`` that has no goal event.
``append-paragraph --max N``
    Append the paragraph on standard input to ``.writing/draft.md``, or refuse
    it when it has more than N words, counting each CJK character as a word.
"""

from __future__ import annotations

import argparse
import datetime
import itertools
import json
import re
import sys
from pathlib import Path

TRACE = Path(".writing/trace/process.jsonl")
GOALS = Path(".writing/goals.md")
DRAFT = Path(".writing/draft.md")
PROCESSES = ("planning", "translating", "reviewing")
GOAL_EVENTS = ("goal_created", "goal_developed", "goal_regenerated")
GOAL_ID = re.compile(r"G\d+(?:\.\d+)*")
GOAL_LINE = re.compile(r"\[(G\d+(?:\.\d+)*)\]")
LEDGER_ENTRY = re.compile(r"G\d+(?:\.\d+)* (?:accepted|rejected) \(.+\)")
LIST_KEYS = ("evidence", "open_uncertainty")
KEYS = (
    "event_type",
    "to_process",
    "decision",
    "regeneration_proposals",
    *LIST_KEYS,
    "goal_id",
    "parent_goal_id",
    "responsible_agent",
)
CJK = re.compile("[぀-ヿ㐀-䶿一-鿿가-힯豈-﫿]")


def _null(value: str) -> str | None:
    return None if value.casefold() in {"null", "none"} else value


def parse_blocks(text: str) -> list[dict[str, object]]:
    """Parse ``key: value`` blocks; a line without a key continues the last value."""

    blocks: list[dict[str, object]] = []
    current: dict[str, object] = {}
    last: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line == "---":
            if current:
                blocks.append(current)
            current, last = {}, None
            continue
        if not line:
            continue
        key, sep, value = line.partition(":")
        key = key.strip()
        if sep and key in KEYS:
            value = value.strip()
            if key in LIST_KEYS:
                items = current.setdefault(key, [])
                if value and value != "[]":
                    items.append(value)  # type: ignore[union-attr]
            elif key in current:
                raise ValueError(f"{key} appears twice in one event")
            else:
                current[key] = value
            last = key
        elif last in LIST_KEYS and line.startswith("- "):
            current[last].append(line[2:].strip())  # type: ignore[union-attr,index]
        elif last is not None:
            previous = current[last]
            if isinstance(previous, list):
                if not previous:
                    raise ValueError(f"write {last} items as '- item' lines")
                previous[-1] = f"{previous[-1]} {line}"
            else:
                current[last] = f"{previous} {line}"
        else:
            raise ValueError(f"line has no known key: {raw!r}")
    if current:
        blocks.append(current)
    return blocks


def read_trace() -> list[dict[str, object]]:
    if not TRACE.is_file():
        return []
    events = []
    for number, line in enumerate(TRACE.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{TRACE} line {number} is not valid JSON: {exc}") from exc
        if not isinstance(event, dict):
            raise TypeError(f"{TRACE} line {number} is not a JSON object")
        events.append(event)
    return events


def _ledger(block: dict[str, object], where: str) -> str:
    value = str(block.get("regeneration_proposals", "")).strip().rstrip(".")
    if not value:
        raise ValueError(
            f"{where}: a switch that leaves reviewing needs regeneration_proposals: "
            "none, or entries such as 'G1.2 accepted (reason); G2 rejected (reason)'"
        )
    if value != "none" and not all(
        LEDGER_ENTRY.fullmatch(entry.strip()) for entry in value.split(";")
    ):
        raise ValueError(
            f"{where}: write each regeneration proposal as "
            "'<goal ID> accepted (<reason>)' or '<goal ID> rejected (<reason>)'"
        )
    return f"regeneration proposals: {value}."


def build_events(
    blocks: list[dict[str, object]],
    previous: str | None,
    now: str,
    *,
    goals: bool = True,
) -> list[dict[str, object]]:
    """Turn parsed blocks into complete trace events, or raise ValueError."""

    events = []
    for index, block in enumerate(blocks, 1):
        where = f"event {index}"
        kind = block.get("event_type")
        decision = block.get("decision")
        if not isinstance(decision, str) or not decision:
            raise ValueError(f"{where}: decision is required")
        event: dict[str, object] = {"timestamp": now, "event_type": kind}
        if kind == "process_switch":
            raw_target = str(block.get("to_process", "")).strip()
            if not raw_target:
                raise ValueError(
                    f"{where}: to_process needs a process name, or null to stop"
                )
            target = _null(raw_target)
            if target is not None and target not in PROCESSES:
                raise ValueError(f"{where}: to_process must be one of {PROCESSES}")
            if target is None and previous is None:
                raise ValueError(f"{where}: the first switch must enter a process")
            if goals and previous == "reviewing":
                decision = f"{_ledger(block, where)} {decision}"
            elif "regeneration_proposals" in block:
                raise ValueError(
                    f"{where}: regeneration_proposals belongs only on a switch "
                    "that leaves reviewing"
                    + ("" if goals else ", and this skill has no goals")
                )
            event["responsible_agent"] = "monitor"
            event["process"] = target or previous
            event["from_process"] = previous
            event["to_process"] = target
            previous = target
        elif kind in GOAL_EVENTS:
            if not goals:
                raise ValueError(f"{where}: this skill logs no goal events")
            goal = str(block.get("goal_id", ""))
            parent = _null(str(block.get("parent_goal_id", "")) or "null")
            if not GOAL_ID.fullmatch(goal):
                raise ValueError(f"{where}: goal_id must look like G1 or G1.2")
            if parent is not None and not GOAL_ID.fullmatch(parent):
                raise ValueError(f"{where}: parent_goal_id must be a goal ID or null")
            default = "monitor" if kind == "goal_regenerated" else "planner"
            event["responsible_agent"] = block.get("responsible_agent") or default
            event["process"] = "planning"
            event["goal_id"] = goal
            event["parent_goal_id"] = parent
        else:
            raise ValueError(
                f"{where}: event_type must be process_switch"
                + (f" or one of {GOAL_EVENTS}" if goals else "")
            )
        if event["responsible_agent"] not in {"monitor", "planner"}:
            raise ValueError(f"{where}: responsible_agent must be monitor or planner")
        event["decision"] = decision
        for key in LIST_KEYS:
            event[key] = list(block.get(key, []))  # type: ignore[call-overload]
        events.append(event)
    return events


def log(text: str, *, goals: bool = True) -> str:
    switches = [e for e in read_trace() if e.get("event_type") == "process_switch"]
    previous = switches[-1].get("to_process") if switches else None
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    events = build_events(
        parse_blocks(text),
        previous,  # type: ignore[arg-type]
        now,
        goals=goals,
    )
    if not events:
        raise ValueError("no events on standard input")
    TRACE.parent.mkdir(parents=True, exist_ok=True)
    with TRACE.open("a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    read_trace()
    return f"logged {len(events)} event(s)"


def check() -> tuple[list[str], list[str]]:
    """Return the logged path and the problems found in the trace and goals."""

    events = read_trace()
    switches = [e for e in events if e.get("event_type") == "process_switch"]
    path = [str(e.get("to_process")) for e in switches]
    problems = []
    if not switches:
        problems.append("no process switch is logged")
    elif switches[0].get("from_process") is not None:
        problems.append("the first process switch has a from_process")
    for before, after in itertools.pairwise(switches):
        if before.get("to_process") != after.get("from_process"):
            problems.append(f"switch chain breaks at {after.get('decision')!r}")
    if GOALS.is_file():
        logged = {
            e.get("goal_id") for e in events if e.get("event_type") in GOAL_EVENTS
        }
        for goal in dict.fromkeys(GOAL_LINE.findall(GOALS.read_text(encoding="utf-8"))):
            if goal not in logged:
                problems.append(f"goal {goal} has no goal event")
    return path, problems


def words(text: str) -> int:
    return len(CJK.findall(text)) + len(CJK.sub(" ", text).split())


def append_paragraph(text: str, limit: int) -> str:
    paragraph = text.strip()
    if not paragraph:
        raise ValueError("the paragraph is empty")
    if "\n\n" in paragraph:
        raise ValueError("write one paragraph, with no blank line inside it")
    count = words(paragraph)
    if count > limit:
        raise ValueError(f"the paragraph has {count} words; the limit is {limit}")
    existing = DRAFT.read_text(encoding="utf-8").rstrip() if DRAFT.is_file() else ""
    DRAFT.parent.mkdir(parents=True, exist_ok=True)
    separator = "\n\n" if existing else ""
    DRAFT.write_text(f"{existing}{separator}{paragraph}\n", encoding="utf-8")
    return f"appended a paragraph of {count} words"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    log_parser = sub.add_parser("log")
    log_parser.add_argument("--no-goals", action="store_true")
    sub.add_parser("check")
    paragraph = sub.add_parser("append-paragraph")
    paragraph.add_argument("--max", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "log":
            print(log(sys.stdin.read(), goals=not args.no_goals))
            return 0
        if args.command == "append-paragraph":
            print(append_paragraph(sys.stdin.read(), args.max))
            return 0
        path, problems = check()
        print("path: " + " > ".join(path))
        for problem in problems:
            print("problem: " + problem)
        return 1 if problems else 0
    except (OSError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
