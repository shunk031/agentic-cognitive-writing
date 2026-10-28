import json
from pathlib import Path
from typing import Any

import pytest

from agentic_cogwriter.analysis.mechanism import (
    adds_section,
    classify_goal_intervals,
    main,
    translating_steps,
    unrecorded_writes,
)

GOALS = "/workspace/.writing/goals.md"
DRAFT = "/workspace/.writing/draft.md"
FIRST_GOALS = (
    "# Goals\n\n## 1. Parties\nName both parties.\n\n## 2. Terms\n- [ ] Rent\n"
)
REWRITE = "@@ -6 +6 @@\n-## 2. Terms\n+## 2. Payment\n"


def _add(content: str) -> dict[str, Any]:
    return {"type": "add", "content": content}


def _update(diff: str) -> dict[str, Any]:
    return {"type": "update", "unified_diff": diff, "move_path": None}


def _swap(old: str, new: str) -> dict[str, Any]:
    return _update(f"@@ -6 +6 @@\n-{old}\n+{new}\n")


@pytest.mark.parametrize(
    ("intervals", "expected"),
    [
        ([[_add(FIRST_GOALS)]], ["created"]),
        # A goals.md without goal lines creates nothing.
        ([[_add("")]], [None]),
        # An empty goals.md created by `touch` and then patched.
        ([[_update("@@ -0,0 +1,2 @@\n+# Goals\n+- Parties\n")]], ["created"]),
        (
            [
                [_add(FIRST_GOALS)],
                [_update("@@ -4 +4 @@\n-Name both parties.\n+Name them.\n")],
            ],
            ["created", None],
        ),
        (
            [[_add(FIRST_GOALS)], [_update("@@ -7 +7,2 @@\n - [ ] Rent\n+- Law\n")]],
            ["created", "developed"],
        ),
        # A goal moved within one diff is unchanged.
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
            ["created", None],
        ),
        # Renumbering, a heading-level change, a marker swap, a ticked box, and
        # respacing are not replacements.
        (
            [[_add(FIRST_GOALS)], [_swap("## 2. Terms", "## 3. Terms")]],
            ["created", None],
        ),
        (
            [[_add(FIRST_GOALS)], [_swap("## 2. Terms", "### 2.1 Terms")]],
            ["created", None],
        ),
        ([[_add(FIRST_GOALS)], [_swap("- [ ] Rent", "* [x] Rent")]], ["created", None]),
        (
            [[_add(FIRST_GOALS)], [_swap("## 2. Terms", "##  2.  Terms ")]],
            ["created", None],
        ),
        ([[_add(FIRST_GOALS)], [_update(REWRITE)]], ["created", "replaced"]),
        (
            [[_add(FIRST_GOALS)], [_update("@@ -6 +5,0 @@\n-## 2. Terms\n")]],
            ["created", "replaced"],
        ),
        ([[_add(FIRST_GOALS)], [{"type": "delete"}]], ["created", "replaced"]),
        # One delegation that creates and then rewrites its own goals only creates.
        ([[_add(FIRST_GOALS), _update(REWRITE)]], ["created"]),
    ],
)
def test_goal_intervals_get_at_most_one_event(
    intervals: list[list[dict[str, Any]]], expected: list[str | None]
) -> None:
    assert [i["event"] for i in classify_goal_intervals(intervals)] == expected


def test_replaced_intervals_record_the_goal_lines_for_audit() -> None:
    replaced = classify_goal_intervals([[_add(FIRST_GOALS)], [_update(REWRITE)]])[1]

    assert replaced["removed"] == [{"normalized": "Terms", "raw": "## 2. Terms"}]
    assert replaced["added"] == [{"normalized": "Payment", "raw": "## 2. Payment"}]


def test_a_section_is_an_added_normalized_heading() -> None:
    assert adds_section(_add("# Title\n\nText.\n"))
    assert adds_section(_update("@@ -2 +2,2 @@\n Text.\n+## Terms\n"))
    assert not adds_section(_add("Text without headings.\n"))
    assert not adds_section(_update("@@ -2 +2 @@\n-Text.\n+Better text.\n"))
    assert not adds_section(_update("@@ -2 +2 @@\n-## 2. Terms\n+## 3. Terms\n"))


def _exec(command: str) -> dict[str, Any]:
    code = "const r = await tools.exec_command({cmd:" + json.dumps(command) + "});"
    return {
        "type": "response_item",
        "payload": {"type": "custom_tool_call", "name": "exec", "input": code},
    }


FLAGGED = [
    "cat > .writing/draft.md <<'EOF'\n# Title\nEOF",
    "touch .writing/goals.md",
    "git reset --hard",
    "git checkout -- .writing",
    "rm -rf .writing",
    "sed -i 's/a/b/' .writing/*.md",
    "patch -p1 < fix.diff",
    "git apply fix.diff",
    "sed --in-place 's/a/b/' .writing/draft.md",
    "sed -Ei 's/a/b/' .writing/goals.md",
    "fmt .writing/draft.md | sponge .writing/draft.md",
    "printf '1d\\nw\\n' | ed .writing/goals.md",
    "mkdir -p .writing && touch .writing/history.md .writing/draft.md",
    "echo x >> .writing/draft.md",
    "cat <<'EOF' > .writing/draft.md\nIt's done.\nEOF",
    "bash -c 'echo x > .writing/goals.md'",
    "git stash",
    "perl -pi -e 's/a/b/' .writing/draft.md",
    "dd if=/dev/zero of=.writing/goals.md",
    "perl -0pi -e 's/a/b/' .writing/draft.md",
    'for f in .writing/goals.md .writing/draft.md; do touch "$f"; done',
    'f=.writing/draft.md; printf x > "$f"',
    "python3 -c \"open('.writing/goals.md', 'w').write('')\"",
    "python3 - <<'EOF'\nfrom pathlib import Path\n"
    "Path('.writing/draft.md').write_text('x')\nEOF",
]
NOT_FLAGGED = [
    "sed -n '1,20p' .writing/goals.md 2>/dev/null",
    "echo note > notes.md",
    "ls .writing && cat .writing/task.md",
    "printf '...draft.md section 2' >> .writing/history.md",
    "mkdir -p .writing && printf x >> .writing/history.md",
    "python3 -c \"open('.writing/draft.md').read()\"",
    "wc -w .writing/draft.md > /tmp/x",
    "rg '->' .writing/draft.md",
    "rg 'cp ' .writing/draft.md",
    "git stash list",
    "for f in .writing/*.md; do cat $f; done > all.md",
    "cp .writing/draft.md /tmp/draft.md",
    "echo x | tee -a .writing/history.md",
    "git log --grep apply -- .writing/draft.md",
    "perl -Mstrict -ne 'print' .writing/draft.md",
    'f=.writing/history.md; printf x >> "$f"',
    'out=notes.md; printf x > "$out"',
    "cat .writing/draft.md | python3 -c \"open('/tmp/x', 'w').write('')\"",
]


def test_shell_writes_to_tracked_files_are_flagged() -> None:
    records = [_exec(command) for command in FLAGGED + NOT_FLAGGED] + [
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
        *FLAGGED,
        "python3 fix.py .writing/draft.md",
        "bash -lc cp old.md .writing/draft.md",
    ]


def _history(line: str) -> dict[str, Any]:
    return {"/w/.writing/history.md": _update(f"@@ -1 +1,2 @@\n old\n+{line}\n")}


def test_translating_steps_count_draft_paragraphs_under_translating() -> None:
    steps = translating_steps(
        [
            # A Planning change creating an empty draft is not a step.
            {**_history("Planning — goals"), "/w/.writing/draft.md": _add("")},
            {
                **_history("Translating — title and opening"),
                "/w/.writing/draft.md": _add("## Terms\n\nOne.\nStill one.\n"),
            },
            {
                "/w/.writing/draft.md": _update(
                    "@@ -4 +4,4 @@\n Still one.\n+Two.\n+\n+## 2. Fees\n+Three.\n"
                ),
                **_history("- **Translating**: fees"),
            },
            {**_history("Reviewing — fixes"), "/w/.writing/draft.md": _add("A.\n")},
        ]
    )

    # A heading line alone is not a paragraph; an unchanged line ends a block.
    assert steps == [1, 2]


def _jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def _collab(tool: str, thread: str, status: str = "completed", **item: Any) -> dict:
    return {
        "type": "item.completed",
        "item": {
            "type": "collab_tool_call",
            "tool": tool,
            "receiver_thread_ids": [thread],
            "status": status,
            **item,
        },
    }


def _spawn(thread: str, prompt: str, status: str = "completed") -> dict[str, Any]:
    return _collab("spawn_agent", thread, status, prompt=prompt)


def _wait(thread: str) -> dict[str, Any]:
    states = {thread: {"status": "completed", "message": "done"}}
    return _collab("wait", thread, agents_states=states)


def _second(seconds: int) -> str:
    return f"1970-01-01T00:{seconds // 60:02d}:{seconds % 60:02d}.000Z"


def _rollout(
    thread: str,
    *changes: tuple[int, str, dict[str, Any]],
    parent: str | None = "monitor",
    role: str | None = None,
    turns: tuple[int, ...] = (0,),
    ends: tuple[int, ...] = (),
) -> list[dict[str, Any]]:
    meta = {"id": thread, "parent_thread_id": parent, "agent_role": role}
    return [
        {"type": "session_meta", "payload": meta},
        *(
            {
                "type": "event_msg",
                "timestamp": _second(turn),
                "payload": {"type": "task_started"},
            }
            for turn in turns
        ),
        *(
            {
                "type": "event_msg",
                "timestamp": _second(end),
                "payload": {"type": "task_complete"},
            }
            for end in ends
        ),
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


def _run(
    root: Path,
    events: list,
    rollouts: dict,
    *,
    condition: str = "A4",
    run_id: str = "run-1",
    fidelity: str = "scorable",
    delegation_required: bool = True,
) -> Path:
    run_dir = root / "WritingBench" / condition / "codex" / run_id
    _jsonl(run_dir / "attempt-001.events.jsonl", events)
    for thread, rows in rollouts.items():
        _jsonl(run_dir / "sessions" / "attempt-001" / f"rollout-{thread}.jsonl", rows)
    (run_dir / "run-manifest.json").write_text(
        json.dumps(
            {
                "inputs": {"condition_id": condition, "prompt_id": "p1"},
                "status": "completed",
                "fidelity_gate": {"status": fidelity, "reasons": []},
                "delegation_check": {"required": delegation_required},
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
            _wait("p1"),
            _spawn("t1", "$translating write"),
            _wait("t1"),
            _spawn("r1", "$reviewing check"),
            _wait("r1"),
            # A failed spawn is not a delegation.
            _spawn("x1", "$translating write", status="failed"),
            # No agent type recorded: the role comes from the prompt.
            _spawn("p2", "$planning replace goal 2"),
            _wait("p2"),
        ],
        {
            "monitor": _rollout("monitor", parent=None),
            # Rollouts are read in file order; changes sort by completion time.
            "p2": _rollout("p2", (40_000, GOALS, _update(REWRITE)), turns=(40,)),
            "p1": _rollout("p1", (10_000, GOALS, _add(FIRST_GOALS)), role="planning"),
            "t1": _rollout("t1", role="translating", turns=(20,)),
            # A child of the Translator writes the first section for its delegation.
            "t1-helper": _rollout(
                "t1-helper", (25_000, DRAFT, _add("# Title\n")), parent="t1"
            ),
            "r1": _rollout("r1", role="reviewing", turns=(30,)),
        },
    )

    assert detail["processes"] == ["planning", "translating", "reviewing", "planning"]
    assert [
        (i["delegation"], i["process"], i["event"]) for i in detail["goal_intervals"]
    ] == [
        (0, "planning", "created"),
        (3, "planning", "replaced"),
    ]
    assert detail["planning_before_first_translating"] is True
    assert detail["planning_before_first_section"] is True
    assert detail["reviewing_then_planning"] is True
    assert detail["goal_replaced_after_review"] is True
    assert detail["reused_children"] == 0
    assert detail["overlapping_delegations"] == 0
    assert detail["unrecorded_writes"] == []
    assert (
        "| A4 | 1 | 1 | 1 | 1/1 1.00 [0.21, 1.00] | 1/1 1.00 [0.21, 1.00] "
        "| 1/1 1.00 [0.21, 1.00] | 1/1 1.00 [0.21, 1.00] | 0/1 0.00 [0.00, 0.79] "
        "| 1/1 1.00 [0.21, 1.00] | 1/1 1.00 [0.21, 1.00] | 4.00 | 0 | 0 | 0 | 0 | 0 |"
    ) in capsys.readouterr().out


def test_a_replacement_after_translating_is_not_after_review(tmp_path: Path) -> None:
    detail = _detail(
        tmp_path,
        [
            _spawn("t1", "$translating write"),
            _wait("t1"),
            _spawn("p1", "$planning plan"),
            _wait("p1"),
        ],
        {
            "t1": _rollout(
                "t1",
                (3_000, GOALS, _add(FIRST_GOALS)),
                (5_000, DRAFT, _add("# Title\n")),
                turns=(1,),
            ),
            "p1": _rollout("p1", (9_000, GOALS, _update(REWRITE)), turns=(8,)),
        },
    )

    assert detail["planning_before_first_translating"] is False
    assert detail["planning_before_first_section"] is False
    assert detail["goal_replaced"] is True
    assert detail["goal_replaced_after_review"] is False


def test_a_reused_child_starts_a_new_delegation(tmp_path: Path) -> None:
    detail = _detail(
        tmp_path,
        [
            _spawn("p1", "$planning create the goals"),
            _wait("p1"),
            _spawn("r1", "$reviewing check"),
            _collab("close_agent", "r1"),
            _collab("send_input", "p1", prompt="replace goal 2"),
            _wait("p1"),
        ],
        {
            "p1": _rollout(
                "p1",
                (5_000, GOALS, _add(FIRST_GOALS)),
                (35_000, GOALS, _update(REWRITE)),
                turns=(0, 30),
            ),
            "r1": _rollout("r1", turns=(10,)),
        },
    )

    assert detail["processes"] == ["planning", "reviewing", "planning"]
    assert [(i["delegation"], i["event"]) for i in detail["goal_intervals"]] == [
        (0, "created"),
        (2, "replaced"),
    ]
    assert detail["reused_children"] == 1
    assert detail["goal_replaced_after_review"] is True


def test_resume_agent_is_not_a_delegation(tmp_path: Path) -> None:
    detail = _detail(
        tmp_path,
        [
            _spawn("p1", "$planning create the goals"),
            _wait("p1"),
            _collab("resume_agent", "p1"),
            _collab("send_input", "p1", prompt="develop the goals"),
            _wait("p1"),
        ],
        {"p1": _rollout("p1", turns=(0, 30))},
    )

    assert [d["tool"] for d in detail["delegations"]] == ["spawn_agent", "send_input"]
    assert detail["reused_children"] == 1


def test_a_change_after_an_untimed_reuse_is_unattributed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    detail = _detail(
        tmp_path,
        [
            _spawn("p1", "$planning create the goals"),
            _wait("p1"),
            _spawn("r1", "$reviewing check"),
            _collab("close_agent", "r1"),
            _collab("send_input", "p1", prompt="replace goal 2"),
            _wait("p1"),
        ],
        {
            # The child's second turn has no task_started record.
            "p1": _rollout(
                "p1",
                (5_000, GOALS, _add(FIRST_GOALS)),
                (35_000, GOALS, _update(REWRITE)),
                (36_000, GOALS, _update("@@ -6 +6,2 @@\n ## 2. Payment\n+- Law\n")),
            ),
            "r1": _rollout("r1", turns=(10,)),
        },
    )

    assert [
        (i["delegation"], i["process"], i["event"]) for i in detail["goal_intervals"]
    ] == [(None, "unattributed", "created")]
    # Every change of the child from its first turn on may belong to the reuse.
    assert detail["unattributed_changes"] == 3
    assert detail["goal_created"] is False
    assert detail["goal_replaced"] is False
    assert detail["goal_replaced_after_review"] is False
    assert (
        capsys.readouterr()
        .out.splitlines()[2]
        .endswith("| 0 | 0 | 1 | 0 | 1 | 0 | 0 | n/a |")
    )


def test_planning_before_reviewing_ends_is_an_overlap(tmp_path: Path) -> None:
    detail = _detail(
        tmp_path,
        [
            _spawn("p1", "$planning create the goals"),
            _wait("p1"),
            _spawn("r1", "$reviewing check"),
            _spawn("p2", "$planning replace goal 2"),
            _wait("r1"),
            _wait("p2"),
        ],
        {
            "p1": _rollout("p1", (5_000, GOALS, _add(FIRST_GOALS))),
            "r1": _rollout("r1", turns=(10,)),
            "p2": _rollout("p2", (20_000, GOALS, _update(REWRITE)), turns=(15,)),
        },
    )

    assert detail["overlapping_delegations"] == 1
    assert detail["reviewing_then_planning"] is False
    assert detail["goal_replaced_after_review"] is False


def test_monitor_changes_fall_between_its_delegations(tmp_path: Path) -> None:
    detail = _detail(
        tmp_path,
        [_spawn("p1", "$planning plan"), _wait("p1")],
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
            "p1": _rollout("p1", (5_000, GOALS, _add(FIRST_GOALS)), turns=(2,)),
        },
    )

    assert [
        (i["delegation"], i["process"], i["event"]) for i in detail["goal_intervals"]
    ] == [
        (-1, "monitor", None),
        (0, "planning", "created"),
    ]
    # The Monitor wrote the section after the Planning delegation started.
    assert detail["planning_before_first_section"] is True
    assert detail["unrecorded_writes"] == [
        {"thread": "monitor", "command": "touch .writing/goals.md"}
    ]


def test_n_a_follows_the_declaration_and_rates_cover_scorable_runs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monitor_only = {
        "monitor": _rollout("monitor", (1_000, GOALS, _add(FIRST_GOALS)), parent=None)
    }
    _run(tmp_path, [], monitor_only, condition="A8", delegation_required=False)
    # A delegating condition whose run never delegates still reports zero.
    _run(tmp_path, [], monitor_only, condition="A4")
    _run(
        tmp_path, [], monitor_only, condition="A4", run_id="run-2", fidelity="rejected"
    )

    assert main(["--runs-root", str(tmp_path)]) == 0

    out = capsys.readouterr().out
    created = "1/1 1.00 [0.21, 1.00]"
    zero = "0/1 0.00 [0.00, 0.79]"
    assert (
        f"| A4 | 2 | 2 | 1 | {zero} | 0/0 | {zero} | {created} | {zero} | {zero} "
        f"| {zero} | 0.00 | 0 | 0 | 0 | 0 | 0 |"
    ) in out
    assert (
        f"| A8 | 1 | 1 | 1 | n/a | n/a | n/a | {created} | {zero} | {zero} "
        "| n/a | n/a | 0 | 0 | n/a | n/a | n/a |"
    ) in out
    assert "excludes runs without an attributed first heading (A4 1, A8 1)" in out


def test_a_queued_delegation_cannot_move_a_change_after_review(
    tmp_path: Path,
) -> None:
    detail = _detail(
        tmp_path,
        [
            _spawn("r1", "$reviewing check"),
            _wait("r1"),
            _spawn("p1", "$planning create the goals"),
            _wait("p1"),
            # The Translator is not waited for, so the reuse is queued behind it.
            _spawn("t1", "$translating write"),
            _collab("send_input", "t1", prompt="continue"),
            _collab("send_input", "p1", prompt="replace goal 2"),
            _wait("t1"),
            _wait("p1"),
        ],
        {
            "r1": _rollout("r1"),
            # The Planner's second turn has no task_started record.
            "p1": _rollout(
                "p1",
                (2_000, GOALS, _add(FIRST_GOALS)),
                (30_000, GOALS, _update(REWRITE)),
                turns=(1,),
                ends=(3,),
            ),
            "t1": _rollout("t1", (10_000, DRAFT, _add("# Title\n")), turns=(5, 40)),
        },
    )

    assert [
        (i["delegation"], i["process"], i["event"]) for i in detail["goal_intervals"]
    ] == [(None, "unattributed", "created")]
    assert detail["goal_replaced_after_review"] is False
    # The Translator's turns are all recorded, so its section stays attributed.
    assert detail["planning_before_first_section"] is True


def test_monitor_changes_keep_goal_events_after_an_unknown_start(
    tmp_path: Path,
) -> None:
    detail = _detail(
        tmp_path,
        [
            _spawn("p1", "$planning create the goals"),
            _wait("p1"),
            _collab("send_input", "p1", prompt="develop the goals"),
            _wait("p1"),
        ],
        {
            "monitor": _rollout(
                "monitor",
                (20_000, GOALS, _update("@@ -7 +7,2 @@\n - [ ] Rent\n+- Law\n")),
                (25_000, DRAFT, _add("# Title\n")),
                parent=None,
            ),
            "p1": _rollout(
                "p1", (2_000, GOALS, _add(FIRST_GOALS)), turns=(1,), ends=(3,)
            ),
        },
    )

    # The Planner's own change may belong to the untimed reuse; the Monitor's
    # change keeps its interval.
    assert [
        (i["delegation"], i["process"], i["event"]) for i in detail["goal_intervals"]
    ] == [(None, "unattributed", "created"), (0, "monitor", "developed")]
    assert detail["goal_developed"] is True
    assert detail["unattributed_changes"] == 1
    # The section may follow the untimed delegation, so its position is unknown.
    assert detail["planning_before_first_section"] is None


GOAL_LIST = "# Goals\n\n1. Parties\n2. Terms\n"
LIST_REWRITE = _update("@@ -4 +4 @@\n-2. Terms\n+2. Payment\n")
LIST_ADD = _update("@@ -4 +4,2 @@\n 2. Terms\n+3. Rent\n")


def _close(thread: str) -> dict[str, Any]:
    return _collab("close_agent", thread)


def _after_review(tmp_path: Path, events: list, rollouts: dict) -> bool:
    return _detail(tmp_path, events, rollouts)["goal_replaced_after_review"]


def test_a_queued_input_merged_into_a_running_turn_is_not_after_review(
    tmp_path: Path,
) -> None:
    # The input queued to the busy Planner joins its first turn, so the later
    # reuse after the Translator has no turn record of its own.
    events = [
        _spawn("p0", "$planning"),
        _spawn("r1", "$reviewing"),
        _wait("r1"),
        _close("r1"),
        _collab("send_input", "p0", prompt="queued"),
        _wait("p0"),
        _spawn("t3", "$translating"),
        _wait("t3"),
        _close("t3"),
        _collab("send_input", "p0", prompt="replace"),
        _wait("p0"),
    ]
    rollouts = {
        "p0": _rollout(
            "p0",
            (3_000, GOALS, _add(GOAL_LIST)),
            (35_000, GOALS, LIST_REWRITE),
            role="planning",
            turns=(1, 30),
            ends=(20, 40),
        ),
        "r1": _rollout("r1", role="reviewing", turns=(2,), ends=(5,)),
        "t3": _rollout(
            "t3", (25_000, GOALS, LIST_ADD), role="translating", turns=(22,), ends=(28,)
        ),
    }

    assert _after_review(tmp_path, events, rollouts) is False


def test_a_task_complete_after_close_does_not_shift_a_change(tmp_path: Path) -> None:
    # The Translator is closed while running and its task_complete comes later.
    events = [
        _spawn("r0", "$reviewing"),
        _wait("r0"),
        _close("r0"),
        _spawn("p1", "$planning"),
        _wait("p1"),
        _close("p1"),
        _spawn("t2", "$translating"),
        _close("t2"),
        _collab("send_input", "p1", prompt="replace"),
        _wait("p1"),
    ]
    rollouts = {
        "r0": _rollout("r0", role="reviewing", ends=(2,)),
        "p1": _rollout(
            "p1",
            (5_000, GOALS, _add(GOAL_LIST)),
            (35_000, GOALS, LIST_REWRITE),
            role="planning",
            turns=(3,),
            ends=(8, 40),
        ),
        "t2": _rollout(
            "t2", (15_000, GOALS, LIST_ADD), role="translating", turns=(10,), ends=(50,)
        ),
    }

    assert _after_review(tmp_path, events, rollouts) is False


REUSE_AFTER_TRANSLATING = [
    _spawn("r0", "$reviewing"),
    _wait("r0"),
    _spawn("p1", "$planning"),
    _wait("p1"),
    _spawn("t2", "$translating"),
    _wait("t2"),
    _collab("send_input", "p1", prompt="replace"),
    _wait("p1"),
]


@pytest.mark.parametrize(
    ("planner_turns", "attributed"),
    [
        # The reused Planner's turn is recorded: its rewrite follows Translating.
        ((1, 8), True),
        # Case K: the reused turn has no record, so the rewrite is unattributed.
        ((1,), False),
    ],
)
def test_a_reuse_after_translating_is_not_after_review(
    tmp_path: Path, planner_turns: tuple[int, ...], attributed: bool
) -> None:
    detail = _detail(
        tmp_path,
        REUSE_AFTER_TRANSLATING,
        {
            "r0": _rollout("r0", role="reviewing"),
            "p1": _rollout(
                "p1",
                (2_000, GOALS, _add(GOAL_LIST)),
                (9_000, GOALS, LIST_REWRITE),
                role="planning",
                turns=planner_turns,
            ),
            "t2": _rollout("t2", role="translating", turns=(4,)),
        },
    )

    assert detail["goal_replaced"] is attributed
    assert detail["goal_replaced_after_review"] is False


def test_a_reuse_right_after_review_is_after_review(tmp_path: Path) -> None:
    # Case L: Reviewing ends, then the Planner is resumed and given the task.
    events = [
        _spawn("p1", "$planning"),
        _wait("p1"),
        _close("p1"),
        _spawn("r1", "$reviewing"),
        _wait("r1"),
        _collab("resume_agent", "p1"),
        _collab("send_input", "p1", prompt="replace"),
        _wait("p1"),
    ]
    rollouts = {
        "p1": _rollout(
            "p1",
            (1_000, GOALS, _add(GOAL_LIST)),
            (9_000, GOALS, LIST_REWRITE),
            role="planning",
            turns=(0, 8),
        ),
        "r1": _rollout("r1", role="reviewing", turns=(2,)),
    }

    assert _after_review(tmp_path, events, rollouts) is True


def _monitor_adds_a_goal() -> list[dict[str, Any]]:
    return _rollout("monitor", (25_000, GOALS, LIST_ADD), parent=None, turns=())


def test_two_missing_turn_records_leave_the_replacement_unattributed(
    tmp_path: Path,
) -> None:
    # Case Z: the Translator's first turn and the Planner's reuse have no
    # task_started record, so the Translator's recorded reuse at 60 s maps onto
    # its first delegation by position.
    events = [
        _spawn("r0", "$reviewing"),
        _wait("r0"),
        _close("r0"),
        _spawn("p1", "$planning"),
        _wait("p1"),
        _close("p1"),
        _spawn("a2", "$translating"),
        _wait("a2"),
        _collab("send_input", "p1", prompt="replace"),
        _wait("p1"),
        _collab("send_input", "a2", prompt="more"),
        _wait("a2"),
    ]
    rollouts = {
        "r0": _rollout("r0", role="reviewing", ends=(2,)),
        "p1": _rollout(
            "p1",
            (5_000, GOALS, _add(GOAL_LIST)),
            (30_000, GOALS, LIST_REWRITE),
            role="planning",
            turns=(3,),
            ends=(8, 35),
        ),
        "a2": _rollout("a2", role="translating", turns=(60,), ends=(15, 70)),
        "monitor": _monitor_adds_a_goal(),
    }

    assert _after_review(tmp_path, events, rollouts) is False


def test_an_overlap_and_a_late_task_complete_together_are_not_after_review(
    tmp_path: Path,
) -> None:
    # Case Z2: a queued Translator starts late, another Translator closed while
    # running records task_complete late, and the Planner's reuse has no record.
    events = [
        _spawn("r0", "$reviewing"),
        _wait("r0"),
        _close("r0"),
        _spawn("p1", "$planning"),
        _wait("p1"),
        _close("p1"),
        _spawn("t2", "$translating"),
        _close("t2"),
        _spawn("a3", "$translating"),
        _collab("send_input", "a3", prompt="queued"),
        _collab("send_input", "p1", prompt="replace"),
        _wait("p1"),
        _wait("a3"),
    ]
    rollouts = {
        "r0": _rollout("r0", role="reviewing", ends=(2,)),
        "p1": _rollout(
            "p1",
            (5_000, GOALS, _add(GOAL_LIST)),
            (30_000, GOALS, LIST_REWRITE),
            role="planning",
            turns=(3,),
            ends=(8, 35),
        ),
        "t2": _rollout("t2", role="translating", turns=(10,), ends=(50,)),
        "a3": _rollout("a3", role="translating", turns=(12, 50), ends=(45, 55)),
        "monitor": _monitor_adds_a_goal(),
    }

    assert _after_review(tmp_path, events, rollouts) is False
