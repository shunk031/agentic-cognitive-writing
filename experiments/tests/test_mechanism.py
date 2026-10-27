import json
from pathlib import Path
from typing import Any

import pytest

from agentic_cogwriter.analysis.mechanism import classify_goal_changes, main

GOALS = "/workspace/.writing/goals.md"
FIRST_GOALS = "# Goals\n\n## 1. Parties\nName both parties.\n\n## 2. Terms\n"


def _add(content: str) -> dict[str, Any]:
    return {"type": "add", "content": content}


def _update(diff: str) -> dict[str, Any]:
    return {"type": "update", "unified_diff": diff, "move_path": None}


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ([_add(FIRST_GOALS)], ["created"]),
        # An empty goals.md created by `touch` and then patched.
        ([_update("@@ -0,0 +1,2 @@\n+# Goals\n+- Parties\n")], ["created"]),
        # Prose under a goal changes and a goal is added; no goal line is lost.
        (
            [
                _add(FIRST_GOALS),
                _update(
                    "@@ -3,2 +3,2 @@\n ## 1. Parties\n-Name both parties.\n"
                    "+Name both parties and their addresses.\n"
                    "@@ -6 +6,2 @@\n ## 2. Terms\n+### 2.1 Rent\n"
                ),
            ],
            ["created", "developed"],
        ),
        # A goal moved within one diff is kept.
        (
            [
                _add(FIRST_GOALS),
                _update(
                    "@@ -3,4 +3,4 @@\n-## 1. Parties\n+## 2. Terms\n"
                    " Name both parties.\n \n-## 2. Terms\n+## 1. Parties\n"
                ),
            ],
            ["created", "developed"],
        ),
        (
            [_add(FIRST_GOALS), _update("@@ -6 +6 @@\n-## 2. Terms\n+## 2. Payment\n")],
            ["created", "replaced"],
        ),
        (
            [_add(FIRST_GOALS), _update("@@ -6 +5,0 @@\n-## 2. Terms\n")],
            ["created", "replaced"],
        ),
        ([_add(FIRST_GOALS), {"type": "delete"}], ["created", "replaced"]),
        # Re-adding the file over existing goals compares the goal lines.
        (
            [_add(FIRST_GOALS), _add(FIRST_GOALS + "## 3. Law\n")],
            ["created", "developed"],
        ),
        (
            [_add(FIRST_GOALS), _add("# Goals\n\n## 1. Parties\n")],
            ["created", "replaced"],
        ),
    ],
)
def test_goal_changes_are_classified_by_goal_lines(
    changes: list[dict[str, Any]], expected: list[str]
) -> None:
    assert classify_goal_changes(changes) == expected


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


def _rollout(thread: str, role: str | None, *changes: tuple[int, dict]) -> list:
    meta = {"id": thread, "parent_thread_id": "monitor", "agent_role": role}
    return [
        {"type": "session_meta", "payload": meta},
        *(
            {
                "type": "event_msg",
                "payload": {
                    "type": "item_completed",
                    "item": {
                        "type": "FileChange",
                        "changes": {GOALS: change},
                        "status": "completed",
                    },
                    "completed_at_ms": at,
                },
            }
            for at, change in changes
        ),
    ]


def _run(root: Path, condition: str, events: list, rollouts: dict) -> Path:
    run_dir = root / "WritingBench" / condition / "codex" / "run-1"
    _jsonl(run_dir / "attempt-001.events.jsonl", events)
    for thread, rows in rollouts.items():
        _jsonl(run_dir / "sessions" / "attempt-001" / f"rollout-{thread}.jsonl", rows)
    (run_dir / "run-manifest.json").write_text(
        json.dumps(
            {
                "inputs": {"condition_id": condition, "prompt_id": "p1"},
                "status": "completed",
                "fidelity_gate": {"status": "scorable", "reasons": []},
            }
        )
    )
    return run_dir


def test_report_derives_processes_and_goal_events_from_rollouts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    replan = _update("@@ -6 +6 @@\n-## 2. Terms\n+## 2. Payment\n")
    run_dir = _run(
        tmp_path,
        "A4",
        [
            {"type": "thread.started", "thread_id": "monitor"},
            _spawn("p1", "$planning create the goals"),
            _spawn("t1", "$translating write"),
            _spawn("r1", "$reviewing check"),
            # No agent type recorded: the role comes from the prompt.
            _spawn("p2", "$planning replace goal 2"),
        ],
        {
            "monitor": [{"type": "session_meta", "payload": {"id": "monitor"}}],
            # The later replacement sorts after the creation by completion time.
            "p2": _rollout("p2", None, (300, replan)),
            "p1": _rollout("p1", "planning", (100, _add(FIRST_GOALS))),
            "t1": _rollout("t1", "translating"),
            "r1": _rollout("r1", "reviewing"),
        },
    )

    assert main(["--runs-root", str(tmp_path)]) == 0

    detail = json.loads((run_dir / "mechanism.json").read_text())
    assert detail["processes"] == ["planning", "translating", "reviewing", "planning"]
    assert detail["goal_events"] == ["created", "replaced"]
    assert detail["planning_before_first_translating"] is True
    assert detail["reviewing_then_planning"] is True
    assert (
        "| A4 | 1 | 1 | 1 | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | 4.00 |"
        in capsys.readouterr().out
    )


def test_translating_before_planning_is_not_planning_first(tmp_path: Path) -> None:
    run_dir = _run(
        tmp_path,
        "A4",
        [_spawn("t1", "$translating write"), _spawn("p1", "$planning plan")],
        {"t1": _rollout("t1", "translating"), "p1": _rollout("p1", "planning")},
    )

    main(["--runs-root", str(tmp_path)])

    detail = json.loads((run_dir / "mechanism.json").read_text())
    assert detail["planning_before_first_translating"] is False
    assert detail["goal_events"] == []
