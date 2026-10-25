import json
from pathlib import Path
from typing import Any

import pytest

from agentic_cogwriter.runner.fidelity import check_fidelity

FIXTURES = Path(__file__).parent / "fixtures" / "fidelity"
MONITOR = "monitor-thread"
CHILD = "child-thread"
CODEX_HOME = Path("/runs/.generator-config/run")


def _item(**item: Any) -> dict[str, Any]:
    return {"type": "item.completed", "item": {"status": "completed", **item}}


def _collab(tool: str, **item: Any) -> dict[str, Any]:
    return _item(
        type="collab_tool_call", tool=tool, receiver_thread_ids=[CHILD], **item
    )


def _write(name: str) -> dict[str, Any]:
    return _item(type="file_change", changes=[{"path": name, "kind": "update"}])


def _message(text: str) -> dict[str, Any]:
    return {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
        },
    }


def _clean_run() -> dict[str, Any]:
    """A delegating run with no measured defect."""

    return {
        "events": [
            {"type": "thread.started", "thread_id": MONITOR},
            _write("/workspace/.writing/history.md"),
            _collab("spawn_agent", prompt="$planning create the goals"),
            _collab("close_agent", prompt=None),
        ],
        "rollouts": {
            MONITOR: [{"type": "session_meta", "payload": {"id": MONITOR}}],
            CHILD: [
                {
                    "type": "session_meta",
                    "payload": {
                        "id": CHILD,
                        "parent_thread_id": MONITOR,
                        "agent_role": "planning",
                    },
                },
                _message("<skill>\n<name>planning</name>\n<path>x</path>"),
            ],
        },
        "draft": "Final text.\n",
        "output": "Final text.\n",
    }


def _materialize(tmp_path: Path, run: dict[str, Any]) -> Path:
    def jsonl(rows: list[dict[str, Any]]) -> str:
        return "".join(json.dumps(row) + "\n" for row in rows)

    (tmp_path / "attempt-001.events.jsonl").write_text(jsonl(run["events"]))
    sessions = tmp_path / "sessions" / "attempt-001" / "2026" / "10" / "23"
    sessions.mkdir(parents=True)
    for thread, rows in run["rollouts"].items():
        (sessions / f"rollout-{thread}.jsonl").write_text(jsonl(rows))
    writing = tmp_path / "workspace" / ".writing"
    writing.mkdir(parents=True)
    (writing / "draft.md").write_text(run["draft"])
    (tmp_path / "output.normalized.txt").write_text(run["output"])
    return tmp_path


def _gate(run_dir: Path, **overrides: Any) -> dict[str, Any]:
    options = {
        "platform": "codex",
        "codex_home": CODEX_HOME,
        "requires_draft": True,
        "monitor_writes_history_only": True,
        **overrides,
    }
    return check_fidelity(run_dir, **options)


def test_clean_delegating_run_is_scorable(tmp_path: Path) -> None:
    assert _gate(_materialize(tmp_path, _clean_run())) == {
        "status": "scorable",
        "reasons": [],
    }


def _fork(run: dict[str, Any]) -> None:
    run["rollouts"][CHILD][0]["payload"]["forked_from_id"] = MONITOR


def _skip_skill(run: dict[str, Any]) -> None:
    del run["rollouts"][CHILD][1]


def _read_other_skill_without_role(run: dict[str, Any]) -> None:
    run["rollouts"][CHILD][0]["payload"]["agent_role"] = None
    run["rollouts"][CHILD][1] = {
        "type": "response_item",
        "payload": {
            "type": "custom_tool_call",
            "input": "sed -n '1,240p' plugin/skills/agentic-cog-writer/SKILL.md",
        },
    }


def _monitor_writes_goals(run: dict[str, Any]) -> None:
    run["events"].append(_write("/workspace/.writing/goals.md"))


def _leave_child_open(run: dict[str, Any]) -> None:
    run["events"].pop()


def _hit_thread_limit(run: dict[str, Any]) -> None:
    run["rollouts"][MONITOR].append(
        {
            "type": "response_item",
            "payload": {
                "type": "custom_tool_call_output",
                "output": "collab spawn failed: agent thread limit reached",
            },
        }
    )


def _score_retyped_message(run: dict[str, Any]) -> None:
    run["output"] = "Final text."


def _lose_child_rollout(run: dict[str, Any]) -> None:
    del run["rollouts"][CHILD]


@pytest.mark.parametrize(
    ("defect", "reason"),
    [
        (_fork, f"child {CHILD} was spawned with inherited context"),
        (_skip_skill, f"planning agent {CHILD} did not read its own SKILL.md"),
        (
            _read_other_skill_without_role,
            f"planning agent {CHILD} did not read its own SKILL.md",
        ),
        (_monitor_writes_goals, "Monitor wrote /workspace/.writing/goals.md"),
        (_leave_child_open, f"child {CHILD} was never closed"),
        (_hit_thread_limit, f"thread {MONITOR} hit the agent thread limit"),
        (_score_retyped_message, "scored output is not workspace/.writing/draft.md"),
        (_lose_child_rollout, f"no rollout was recorded for thread {CHILD}"),
    ],
)
def test_each_measured_defect_rejects_the_run(
    tmp_path: Path, defect: Any, reason: str
) -> None:
    run = _clean_run()
    defect(run)

    assert _gate(_materialize(tmp_path, run)) == {
        "status": "rejected",
        "reasons": [reason],
    }


def test_explicit_read_of_the_role_skill_file_counts_as_loading(
    tmp_path: Path,
) -> None:
    run = _clean_run()
    run["rollouts"][CHILD][1] = {
        "type": "response_item",
        "payload": {
            "type": "custom_tool_call",
            "input": f"sed -n '1,240p' {CODEX_HOME}/skills/planning/SKILL.md",
        },
    }

    assert _gate(_materialize(tmp_path, run))["status"] == "scorable"


def _skills_message(*roots: str) -> dict[str, Any]:
    table = "".join(f"- `r{index}` = `{root}`\n" for index, root in enumerate(roots))
    return _message(f"<skills_instructions>\n### Skill roots\n{table}")


def test_skill_roots_inside_the_run_codex_home_are_scorable(tmp_path: Path) -> None:
    run = _clean_run()
    run["rollouts"][MONITOR].append(
        _skills_message(f"{CODEX_HOME}/skills", f"{CODEX_HOME}/skills/.system")
    )

    assert _gate(_materialize(tmp_path, run))["status"] == "scorable"


def test_host_skill_root_rejects_the_run(tmp_path: Path) -> None:
    run = _clean_run()
    run["rollouts"][CHILD].append(
        _skills_message(f"{CODEX_HOME}/skills", "/home/user/.agents/skills")
    )

    assert _gate(_materialize(tmp_path, run))["reasons"] == [
        f"thread {CHILD} lists skill root /home/user/.agents/skills "
        "outside the run's Codex home"
    ]


def test_skill_root_escaping_the_run_codex_home_rejects_the_run(
    tmp_path: Path,
) -> None:
    run = _clean_run()
    run["rollouts"][CHILD].append(_skills_message(f"{CODEX_HOME}/../other/skills"))

    assert _gate(_materialize(tmp_path, run))["status"] == "rejected"


def _read(command: str) -> dict[str, Any]:
    return {
        "type": "response_item",
        "payload": {"type": "custom_tool_call", "input": command},
    }


def test_skill_read_outside_the_staged_skills_rejects_the_run(
    tmp_path: Path,
) -> None:
    run = _clean_run()
    run["rollouts"][CHILD].append(
        _read("cat /a\nsed -n '1,80p' /home/user/.agents/skills/unslop/SKILL.md")
    )

    assert _gate(_materialize(tmp_path, run))["reasons"] == [
        f"thread {CHILD} read /home/user/.agents/skills/unslop/SKILL.md "
        "outside the staged skills"
    ]


def test_staged_and_relative_skill_reads_are_scorable(tmp_path: Path) -> None:
    run = _clean_run()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    run["rollouts"][MONITOR].extend(
        [
            _read("sed -n '1,240p' plugin/skills/agentic-cog-writer/SKILL.md"),
            _read(f"cat {run_dir}/workspace/plugin/skills/planning/SKILL.md"),
            _read("cat ~/.agents/skills/x/SKILL.md $HOME/y/SKILL.md"),
        ]
    )

    assert _gate(_materialize(run_dir, run))["status"] == "scorable"


def test_monitor_write_rule_applies_only_to_monitor_conditions(
    tmp_path: Path,
) -> None:
    run = _clean_run()
    _monitor_writes_goals(run)

    gate = _gate(_materialize(tmp_path, run), monitor_writes_history_only=False)

    assert gate["status"] == "scorable"


def test_single_turn_product_is_not_compared_with_a_draft(tmp_path: Path) -> None:
    run = _clean_run()
    _score_retyped_message(run)

    assert _gate(_materialize(tmp_path, run), requires_draft=False)["status"] == (
        "scorable"
    )


def test_missing_event_stream_rejects_the_run(tmp_path: Path) -> None:
    assert _gate(tmp_path, requires_draft=False)["reasons"] == [
        "no Codex event stream was recorded"
    ]


def test_platform_without_tool_records_is_rejected_as_unverifiable(
    tmp_path: Path,
) -> None:
    gate = _gate(_materialize(tmp_path, _clean_run()), platform="claude-code")

    assert gate["reasons"] == [
        "claude-code records expose no subagent or tool events, "
        "so fidelity cannot be verified"
    ]


def test_recorded_rebuilt_plugin_run_is_scorable() -> None:
    """Trimmed records of one rebuilt-plugin A4 run with a seeded missing section.

    The harness that produced the run stored the draft but no runner output, so
    the fixture scores the draft itself, as the gate requires.
    """

    assert _gate(FIXTURES / "monitor-loopback", codex_home=None) == {
        "status": "scorable",
        "reasons": [],
    }


def test_recorded_executed_study_run_shows_every_measured_defect() -> None:
    """Trimmed records of one executed-study A4 run, with excerpts of its files."""

    planning = "01a0c3e8-2fe4-7c62-be53-7105d23be907"
    translating = "01a0c3e8-d569-75f3-9240-8ceb92ef96cf"
    reviewing = "01a0c3ea-2993-7651-af43-6e355ebcff75"

    assert _gate(FIXTURES / "executed-a4", codex_home=None)["reasons"] == [
        f"child {planning} was spawned with inherited context",
        f"planning agent {planning} did not read its own SKILL.md",
        f"child {translating} was spawned with inherited context",
        f"translating agent {translating} did not read its own SKILL.md",
        f"child {reviewing} was spawned with inherited context",
        "Monitor wrote /workspace/.writing/assignment.md",
        "Monitor wrote /workspace/.writing/assumptions.md",
        "Monitor wrote /workspace/.writing/draft.md",
        "Monitor wrote /workspace/.writing/goals.md",
        "Monitor wrote /workspace/.writing/trace/process.jsonl",
        f"child {planning} was never closed",
        f"child {translating} was never closed",
        f"child {reviewing} was never closed",
        "scored output is not workspace/.writing/draft.md",
    ]
