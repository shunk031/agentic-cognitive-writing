import json
from pathlib import Path
from typing import Any

import pytest

from agentic_cogwriter.analysis.mechanism import (
    adds_section,
    classify_goal_intervals,
    main,
    unrecorded_writes,
)

GOALS = "/workspace/.writing/goals.md"
DRAFT = "/workspace/.writing/draft.md"
FIRST_GOALS = "# Goals\n\n## 1. Parties\nName both parties.\n\n## 2. Terms\n"
REWRITE = "@@ -6 +6 @@\n-## 2. Terms\n+## 2. Payment\n"


def _add(content: str) -> dict[str, Any]:
    return {"type": "add", "content": content}


def _update(diff: str) -> dict[str, Any]:
    return {"type": "update", "unified_diff": diff, "move_path": None}


@pytest.mark.parametrize(
    ("intervals", "expected"),
    [
        ([[_add(FIRST_GOALS)]], [["created"]]),
        ([[_add("")]], [["created"]]),
        # An empty goals.md created by `touch` and then patched.
        ([[_update("@@ -0,0 +1,2 @@\n+# Goals\n+- Parties\n")]], [["created"]]),
        # Prose under a goal changes; no goal line is gained or lost.
        (
            [
                [_add(FIRST_GOALS)],
                [_update("@@ -4 +4 @@\n-Name both parties.\n+Name them.\n")],
            ],
            [["created"], ["developed"]],
        ),
        (
            [[_add(FIRST_GOALS)], [_update("@@ -6 +6,2 @@\n ## 2. Terms\n+- Rent\n")]],
            [["created"], ["created", "developed"]],
        ),
        # A goal moved within one diff is kept.
        (
            [
                [_add(FIRST_GOALS)],
                [
                    _update(
                        "@@ -3,4 +3,4 @@\n-## 1. Parties\n+## 2. Terms\n"
                        " Name both parties.\n \n-## 2. Terms\n+## 1. Parties\n"
                    )
                ],
            ],
            [["created"], ["developed"]],
        ),
        ([[_add(FIRST_GOALS)], [_update(REWRITE)]], [["created"], ["replaced"]]),
        (
            [[_add(FIRST_GOALS)], [_update("@@ -6 +5,0 @@\n-## 2. Terms\n")]],
            [["created"], ["replaced"]],
        ),
        ([[_add(FIRST_GOALS)], [{"type": "delete"}]], [["created"], ["replaced"]]),
        # One delegation that creates and then rewrites its own goals only creates.
        ([[_add(FIRST_GOALS), _update(REWRITE)]], [["created"]]),
    ],
)
def test_goal_intervals_are_classified_by_goal_lines(
    intervals: list[list[dict[str, Any]]], expected: list[list[str]]
) -> None:
    assert classify_goal_intervals(intervals) == expected


def test_a_section_is_an_added_heading() -> None:
    assert adds_section(_add("# Title\n\nText.\n"))
    assert adds_section(_update("@@ -2 +2,2 @@\n Text.\n+## Terms\n"))
    assert not adds_section(_add("Text without headings.\n"))
    assert not adds_section(_update("@@ -2 +2 @@\n-Text.\n+Better text.\n"))


def _exec(command: str) -> dict[str, Any]:
    code = "const r = await tools.exec_command({cmd:" + json.dumps(command) + "});"
    return {
        "type": "response_item",
        "payload": {"type": "custom_tool_call", "name": "exec", "input": code},
    }


def test_shell_writes_to_tracked_files_are_flagged() -> None:
    records = [
        _exec("cat > .writing/draft.md <<'EOF'\n# Title\nEOF"),
        _exec("touch .writing/goals.md"),
        _exec("sed -n '1,20p' .writing/goals.md 2>/dev/null"),
        _exec("echo note > notes.md"),
        {
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "exec_command",
                "arguments": json.dumps({"cmd": "python3 fix.py .writing/draft.md"}),
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "local_shell_call",
                "action": {"command": ["bash", "-lc", "cp old.md .writing/draft.md"]},
            },
        },
    ]

    assert unrecorded_writes(records) == [
        "cat > .writing/draft.md <<'EOF'\n# Title\nEOF",
        "touch .writing/goals.md",
        "python3 fix.py .writing/draft.md",
        "bash -lc cp old.md .writing/draft.md",
    ]


def _jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def _spawn(thread: str, prompt: str) -> dict[str, Any]:
    return {
        "type": "item.completed",
        "item": {
            "type": "collab_tool_call",
            "tool": "spawn_agent",
            "receiver_thread_ids": [thread],
            "prompt": prompt,
            "status": "completed",
        },
    }


def _rollout(
    thread: str,
    *changes: tuple[int, str, dict[str, Any]],
    parent: str | None = "monitor",
    role: str | None = None,
    started: int = 0,
) -> list[dict[str, Any]]:
    meta = {
        "id": thread,
        "parent_thread_id": parent,
        "agent_role": role,
        "timestamp": f"1970-01-01T00:00:{started:02d}.000Z",
    }
    return [
        {"type": "session_meta", "payload": meta},
        *(
            {
                "type": "event_msg",
                "payload": {
                    "type": "item_completed",
                    "item": {
                        "type": "FileChange",
                        "changes": {path: change},
                        "status": "completed",
                    },
                    "completed_at_ms": at,
                },
            }
            for at, path, change in changes
        ),
    ]


def _run(root: Path, events: list, rollouts: dict) -> Path:
    run_dir = root / "WritingBench" / "A4" / "codex" / "run-1"
    _jsonl(run_dir / "attempt-001.events.jsonl", events)
    for thread, rows in rollouts.items():
        _jsonl(run_dir / "sessions" / "attempt-001" / f"rollout-{thread}.jsonl", rows)
    (run_dir / "run-manifest.json").write_text(
        json.dumps(
            {
                "inputs": {"condition_id": "A4", "prompt_id": "p1"},
                "status": "completed",
                "fidelity_gate": {"status": "scorable", "reasons": []},
            }
        )
    )
    return run_dir


def _detail(tmp_path: Path, events: list, rollouts: dict) -> dict[str, Any]:
    run_dir = _run(tmp_path, events, rollouts)
    assert main(["--runs-root", str(tmp_path)]) == 0
    return json.loads((run_dir / "mechanism.json").read_text())


def test_report_derives_processes_and_goal_events_from_rollouts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    detail = _detail(
        tmp_path,
        [
            {"type": "thread.started", "thread_id": "monitor"},
            _spawn("p1", "$planning create the goals"),
            _spawn("t1", "$translating write"),
            _spawn("r1", "$reviewing check"),
            # No agent type recorded: the role comes from the prompt.
            _spawn("p2", "$planning replace goal 2"),
        ],
        {
            "monitor": _rollout("monitor", parent=None),
            # Rollouts are read in file order; changes sort by completion time.
            "p2": _rollout("p2", (40_000, GOALS, _update(REWRITE)), started=40),
            "p1": _rollout("p1", (10_000, GOALS, _add(FIRST_GOALS)), role="planning"),
            "t1": _rollout("t1", role="translating", started=20),
            # A child of the Translator writes the first section for its delegation.
            "t1-helper": _rollout(
                "t1-helper", (25_000, DRAFT, _add("# Title\n")), parent="t1"
            ),
            "r1": _rollout("r1", role="reviewing", started=30),
        },
    )

    assert detail["processes"] == ["planning", "translating", "reviewing", "planning"]
    assert detail["goal_intervals"] == [
        {"delegation": 0, "events": ["created"]},
        {"delegation": 3, "events": ["replaced"]},
    ]
    assert detail["planning_before_first_section"] is True
    assert detail["reviewing_then_planning"] is True
    assert detail["unrecorded_writes"] == []
    assert (
        "| A4 | 1 | 1 | 1 | 1/1 1.00 [0.21, 1.00] | 1/1 1.00 [0.21, 1.00] "
        "| 1/1 1.00 [0.21, 1.00] | 0/1 0.00 [0.00, 0.79] | 1/1 1.00 [0.21, 1.00] "
        "| 4.00 | 0 | 0 |"
    ) in capsys.readouterr().out


def test_a_section_written_before_planning_is_not_planning_first(
    tmp_path: Path,
) -> None:
    detail = _detail(
        tmp_path,
        [_spawn("t1", "$translating write"), _spawn("p1", "$planning plan")],
        {
            "t1": _rollout("t1", (5_000, DRAFT, _add("# Title\n")), started=1),
            "p1": _rollout("p1", (9_000, GOALS, _add(FIRST_GOALS)), started=8),
        },
    )

    assert detail["planning_before_first_section"] is False
    assert detail["goal_intervals"] == [{"delegation": 1, "events": ["created"]}]


def test_monitor_changes_fall_between_its_delegations(tmp_path: Path) -> None:
    detail = _detail(
        tmp_path,
        [_spawn("p1", "$planning plan")],
        {
            "monitor": [
                *_rollout(
                    "monitor",
                    (1_000, GOALS, _add("")),
                    (9_000, DRAFT, _add("# Title\n")),
                    parent=None,
                ),
                _exec("touch .writing/goals.md"),
            ],
            "p1": _rollout("p1", (5_000, GOALS, _add(FIRST_GOALS)), started=2),
        },
    )

    assert detail["goal_intervals"] == [
        {"delegation": -1, "events": ["created"]},
        {"delegation": 0, "events": ["created"]},
    ]
    # The Monitor wrote the section after the Planning delegation started.
    assert detail["planning_before_first_section"] is True
    assert detail["unrecorded_writes"] == [
        {"thread": "monitor", "command": "touch .writing/goals.md"}
    ]
