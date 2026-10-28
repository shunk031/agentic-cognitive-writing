import json
from pathlib import Path
from typing import Any

import pytest

from agentic_cogwriter.runner.fidelity import check_fidelity, check_output_language

FIXTURES = Path(__file__).parent / "fixtures" / "fidelity"
MONITOR = "monitor-thread"
CHILD = "child-thread"
CODEX_HOME = Path("/runs/.generator-config/run")
TOUCH = "mkdir -p .writing && touch .writing/history.md .writing/draft.md"


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


def _read(command: str) -> dict[str, Any]:
    return {
        "type": "response_item",
        "payload": {"type": "custom_tool_call", "input": command},
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


def _monitor_touches_state(run: dict[str, Any]) -> None:
    run["rollouts"][MONITOR].append(_read(f"exec_command({{cmd:{json.dumps(TOUCH)}}})"))


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
        (_monitor_touches_state, f"Monitor ran shell write {TOUCH!r}"),
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


def _baseline_run(*, read: bool) -> dict[str, Any]:
    """An A3-style run whose child is a default agent told to read its skill."""

    run = _clean_run()
    skill = "plugin/skills/task-node/SKILL.md"
    run["events"][2] = _collab(
        "spawn_agent", prompt=f"Read the skill file at {skill} and follow it. Task r1."
    )
    run["rollouts"][CHILD][0]["payload"]["agent_role"] = "default"
    run["rollouts"][CHILD][1] = _read(f"sed -n '1,200p' {skill}" if read else "ls")
    return run


A3_ROLES = ("task-node", "task-execution")


@pytest.mark.parametrize(
    ("read", "reasons"),
    [
        (True, []),
        (False, [f"task-node agent {CHILD} did not read its own SKILL.md"]),
    ],
)
def test_baseline_child_must_read_the_skill_its_spawn_names(
    tmp_path: Path, read: bool, reasons: list[str]
) -> None:
    run_dir = _materialize(tmp_path, _baseline_run(read=read))

    assert (
        _gate(run_dir, monitor_writes_history_only=False, roles=A3_ROLES)["reasons"]
        == reasons
    )


def test_child_spawned_without_a_role_skill_rejects_the_run(tmp_path: Path) -> None:
    run = _baseline_run(read=True)
    run["events"][2] = _collab("spawn_agent", prompt="Decompose task r1.")

    assert _gate(
        _materialize(tmp_path, run), monitor_writes_history_only=False, roles=A3_ROLES
    )["reasons"] == [f"child {CHILD} was spawned without a role skill"]


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


def _output(call_id: str, text: str) -> dict[str, Any]:
    return {
        "type": "response_item",
        "payload": {
            "type": "custom_tool_call_output",
            "call_id": call_id,
            "output": [{"type": "input_text", "text": text}],
        },
    }


@pytest.mark.parametrize(
    ("output", "status"),
    [
        ("sed: can't read {path}: No such file or directory\n", "scorable"),
        ("Role: the Reviewer.\n", "rejected"),
    ],
)
def test_skill_read_outside_the_staged_skills_counts_only_if_the_path_exists(
    tmp_path: Path, output: str, status: str
) -> None:
    path = f"{CODEX_HOME.parent}/skills/planning/SKILL.md"
    run = _clean_run()
    read = _read(f'exec_command({{cmd:"sed -n 1,240p {path}"}})')
    read["payload"]["call_id"] = "call-1"
    run["rollouts"][CHILD] += [read, _output("call-1", output.format(path=path))]

    assert _gate(_materialize(tmp_path, run))["status"] == status


def test_a_missing_longer_path_does_not_hide_a_read_of_its_suffix(
    tmp_path: Path,
) -> None:
    run = _clean_run()
    read = _read('exec_command({cmd:"cat /x/elsewhere/SKILL.md /elsewhere/SKILL.md"})')
    read["payload"]["call_id"] = "call-1"
    error = "cat: /x/elsewhere/SKILL.md: No such file or directory\nRole: other.\n"
    run["rollouts"][CHILD] += [read, _output("call-1", error)]

    assert _gate(_materialize(tmp_path, run))["reasons"] == [
        f"thread {CHILD} read /elsewhere/SKILL.md outside the staged skills"
    ]


OUTSIDE = "/home/user/.agents/skills/x/SKILL.md"
PATCH = f"*** Begin Patch\\n*** Update File: {OUTSIDE}\\n*** End Patch"


@pytest.mark.parametrize(
    ("call", "status"),
    [
        # A patch header names a file to write, as in a failed apply_patch.
        (f'apply_patch("{PATCH}")', "scorable"),
        (f'apply_patch("{PATCH}"); cat {OUTSIDE}', "rejected"),
        (f"cat <<'EOF'\\n*** Begin Patch\\nEOF\\ncat {OUTSIDE}", "rejected"),
        (f"echo '*** Begin Patch'; cat {OUTSIDE}; echo '*** End Patch'", "rejected"),
        (f"grep -n '*** Begin Patch' a.md; sed -n 1p {OUTSIDE}", "rejected"),
    ],
)
def test_only_patch_header_paths_are_not_skill_reads(
    tmp_path: Path, call: str, status: str
) -> None:
    run = _clean_run()
    run["rollouts"][CHILD].append(_read(call))

    assert _gate(_materialize(tmp_path, run))["status"] == status


STAGES = (
    ".writing/baselines/linear/pre-write.md",
    ".writing/baselines/linear/write.md",
    ".writing/draft.md",
)


def _staged_run(*paths: str) -> dict[str, Any]:
    run = _clean_run()
    run["events"] = [
        {"type": "thread.started", "thread_id": MONITOR},
        *(_write(f"/run/workspace/{path}") for path in paths),
    ]
    del run["rollouts"][CHILD]
    return run


def _stage_gate(run_dir: Path, **overrides: Any) -> dict[str, Any]:
    return _gate(
        run_dir,
        **{"stage_files": STAGES, "monitor_writes_history_only": False, **overrides},
    )


def test_stage_writes_once_each_in_order_are_scorable(tmp_path: Path) -> None:
    run = _staged_run(*STAGES, ".writing/notes.md")

    assert _stage_gate(_materialize(tmp_path, run))["status"] == "scorable"


@pytest.mark.parametrize(
    "paths",
    [STAGES[:2], (STAGES[1], STAGES[0], STAGES[2]), (*STAGES, STAGES[2])],
)
def test_missing_reordered_or_repeated_stage_writes_reject_the_run(
    tmp_path: Path, paths: tuple[str, ...]
) -> None:
    gate = _stage_gate(_materialize(tmp_path, _staged_run(*paths)))

    assert gate["reasons"] == [f"stage writes were {list(paths)}, not {list(STAGES)}"]


def test_shell_write_to_a_stage_file_rejects_the_run(tmp_path: Path) -> None:
    run = _staged_run(*STAGES)
    command = "cat > .writing/baselines/linear/write.md <<'EOF'\nx\nEOF"
    run["rollouts"][MONITOR].append(
        _read(f"exec_command({{cmd:{json.dumps(command)}}})")
    )
    run_dir = _materialize(tmp_path, run)

    assert _stage_gate(run_dir)["reasons"] == [
        f"thread {MONITOR} ran shell write {command!r}"
    ]
    assert _stage_gate(run_dir, stage_files=())["status"] == "scorable"


@pytest.mark.parametrize(
    "path",
    [
        "../../../../home/user/.agents/skills/x/SKILL.md",
        "plugin/../../x/SKILL.md",
        "--file=../SKILL.md",
        "<../SKILL.md",
        "$(<../h/SKILL.md)",
        "true;../h/SKILL.md",
    ],
)
def test_relative_skill_read_through_a_parent_directory_rejects_the_run(
    tmp_path: Path, path: str
) -> None:
    run = _clean_run()
    run["rollouts"][CHILD].append(_read(f"cat {path}"))

    assert _gate(_materialize(tmp_path, run))["reasons"] == [
        f"thread {CHILD} read {path.rstrip(')')} through a parent directory"
    ]


def test_relative_skill_read_after_cd_out_of_the_workspace_passes(
    tmp_path: Path,
) -> None:
    """Known limit: the gate does not track the working directory of a call."""

    run = _clean_run()
    run["rollouts"][CHILD].append(
        _read("cd /home/user/.agents/skills/x && cat SKILL.md")
    )

    assert _gate(_materialize(tmp_path, run))["status"] == "scorable"


def test_staged_and_relative_skill_reads_are_scorable(tmp_path: Path) -> None:
    run = _clean_run()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    run["rollouts"][MONITOR].extend(
        [
            _read("sed -n '1,240p' plugin/skills/agentic-cog-writer/SKILL.md"),
            _read(f"cat {run_dir}/workspace/plugin/skills/planning/SKILL.md"),
            _read("cat ~/.agents/skills/x/SKILL.md $HOME/y/SKILL.md"),
            _read("cat a..b/SKILL.md ./plugin/skills/planning/SKILL.md"),
        ]
    )

    assert _gate(_materialize(run_dir, run))["status"] == "scorable"


def test_monitor_shell_append_to_the_history_is_scorable(tmp_path: Path) -> None:
    run = _clean_run()
    run["rollouts"][MONITOR].append(
        _read('exec_command({cmd:"printf x >> .writing/history.md"})')
    )

    assert _gate(_materialize(tmp_path, run))["status"] == "scorable"


@pytest.mark.parametrize("defect", [_monitor_writes_goals, _monitor_touches_state])
def test_monitor_write_rule_applies_only_to_monitor_conditions(
    tmp_path: Path, defect: Any
) -> None:
    run = _clean_run()
    defect(run)

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


@pytest.mark.parametrize(
    ("text", "language", "words", "characters", "dominant", "mismatch"),
    [
        # English terms inside Chinese prose: 21 Latin letters but 5 words.
        (
            "蔚来的BaaS模式与Tesla相比，gross margin在Q4有所改善。",
            "zh",
            5,
            13,
            "CJK",
            False,
        ),
        (
            "蔚来的BaaS模式与Tesla相比，gross margin在Q4有所改善。",
            "en",
            5,
            13,
            "CJK",
            True,
        ),
        # English drifting into Chinese: more Latin letters, fewer units.
        (
            "The report covers revenue. 报告显示营收增长，毛利率提升。",
            "en",
            4,
            13,
            "CJK",
            True,
        ),
        ("A memo about Hangzhou (杭州) tea.", "en", 5, 2, "LATIN", False),
        # Fullwidth Latin counts as Latin.
        ("ＴＨＥ ＲＥＰＯＲＴ ＣＯＶＥＲＳ 杭州", "en", 3, 2, "LATIN", False),
        ("A memo about tea.", "zh", 4, 0, "LATIN", True),
        ("Tea 杭州", "en", 1, 2, "CJK", True),
        ("Hangzhou tea 杭州", "en", 2, 2, None, None),
        ("123 456", "en", 0, 0, None, None),
    ],
)
def test_output_language_compares_latin_words_with_cjk_characters(
    text: str,
    language: str,
    words: int,
    characters: int,
    dominant: str | None,
    mismatch: bool | None,
) -> None:
    result = check_output_language(text, language)

    assert result["expected_language"] == language
    assert (result["latin_words"], result["cjk_characters"]) == (words, characters)
    assert result["dominant_script"] == dominant
    assert result["mismatch"] is mismatch
