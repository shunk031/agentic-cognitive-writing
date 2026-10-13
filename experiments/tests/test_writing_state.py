"""The Monitor skills' trace script writes valid JSON or nothing."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).parents[2]
    / "plugin/skills/agentic-cog-writer/scripts/writing_state.py"
)


def _run(cwd: Path, *args: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


def _trace(cwd: Path) -> list[dict[str, object]]:
    path = cwd / ".writing/trace/process.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_log_builds_valid_json_and_fills_derived_fields(tmp_path: Path) -> None:
    first = _run(
        tmp_path,
        "log",
        stdin=(
            "event_type: process_switch\n"
            "to_process: planning\n"
            'decision: Plan "the opening"; $HOME and \\n stay literal,\n'
            "  and this line continues the decision.\n"
            "evidence: .writing/assignment.md\n"
            "evidence: G1 is missing\n"
        ),
    )
    assert first.returncode == 0, first.stderr
    second = _run(
        tmp_path,
        "log",
        stdin=(
            "event_type: goal_created\ngoal_id: G1\nparent_goal_id: none\n"
            "decision: Planning created G1.\n---\n"
            "event_type: goal_regenerated\ngoal_id: G1.2\nparent_goal_id: G1\n"
            "decision: regeneration accepted\n---\n"
            "event_type: process_switch\nto_process: null\n"
            "decision: regeneration proposals: none\n"
        ),
    )
    assert second.returncode == 0, second.stderr

    switch, created, regenerated, stop = _trace(tmp_path)
    assert switch["decision"] == (
        'Plan "the opening"; $HOME and \\n stay literal, and this line continues '
        "the decision."
    )
    assert switch["evidence"] == [".writing/assignment.md", "G1 is missing"]
    assert (switch["from_process"], switch["process"]) == (None, "planning")
    assert created["parent_goal_id"] is None
    assert created["responsible_agent"] == "planner"
    assert regenerated["responsible_agent"] == "monitor"
    assert (stop["from_process"], stop["to_process"], stop["process"]) == (
        "planning",
        None,
        "planning",
    )


@pytest.mark.parametrize(
    "stdin",
    (
        "event_type: goal_created\ngoal_id: G1\nparent_goal_id: G0x\ndecision: d\n",
        "event_type: goal_created\ngoal_id: 1\nparent_goal_id: none\ndecision: d\n",
        "event_type: process_switch\nto_process: evaluate\ndecision: d\n",
        "event_type: process_switch\ndecision: d\n",
        "event_type: evaluate\ndecision: d\n",
    ),
)
def test_log_appends_nothing_when_an_event_is_invalid(
    tmp_path: Path, stdin: str
) -> None:
    valid = "event_type: process_switch\nto_process: planning\ndecision: d\n---\n"
    result = _run(tmp_path, "log", stdin=valid + stdin)
    assert result.returncode == 1
    assert not (tmp_path / ".writing/trace/process.jsonl").exists()


def test_check_reports_goals_without_events_and_broken_lines(tmp_path: Path) -> None:
    (tmp_path / ".writing").mkdir()
    (tmp_path / ".writing/goals.md").write_text(
        "- [G1] Top (parent: none)\n  - [G1.1] Child (parent: G1)\n", encoding="utf-8"
    )
    _run(
        tmp_path,
        "log",
        stdin=(
            "event_type: process_switch\nto_process: planning\ndecision: d\n---\n"
            "event_type: goal_created\ngoal_id: G1\nparent_goal_id: null\ndecision: d\n"
        ),
    )
    result = _run(tmp_path, "check")
    assert result.returncode == 1
    assert "path: planning" in result.stdout
    assert "goal G1.1 has no goal event" in result.stdout

    with (tmp_path / ".writing/trace/process.jsonl").open("a") as handle:
        handle.write('{"parent_goal_id":G0}\n')
    broken = _run(tmp_path, "check")
    assert broken.returncode == 1
    assert "line 3 is not valid JSON" in broken.stderr


def test_append_paragraph_refuses_over_limit_paragraphs(tmp_path: Path) -> None:
    draft = tmp_path / ".writing/draft.md"
    ok = _run(tmp_path, "append-paragraph", "--max", "5", stdin="日本語 and two\n")
    assert ok.returncode == 0, ok.stderr
    refused = _run(tmp_path, "append-paragraph", "--max", "4", stdin="日本語 and two")
    assert refused.returncode == 1
    assert "has 5 words; the limit is 4" in refused.stderr
    two = _run(tmp_path, "append-paragraph", "--max", "5", stdin="one\n\ntwo")
    assert two.returncode == 1
    second = _run(tmp_path, "append-paragraph", "--max", "5", stdin="Second one.")
    assert second.returncode == 0
    assert draft.read_text(encoding="utf-8") == "日本語 and two\n\nSecond one.\n"


def test_switch_after_reviewing_requires_and_formats_the_ledger(tmp_path: Path) -> None:
    review = "event_type: process_switch\nto_process: reviewing\ndecision: d\n"
    assert _run(tmp_path, "log", stdin=review).returncode == 0
    missing = _run(
        tmp_path,
        "log",
        stdin="event_type: process_switch\nto_process: translating\ndecision: d\n",
    )
    assert missing.returncode == 1
    assert "regeneration_proposals" in missing.stderr
    bad = _run(
        tmp_path,
        "log",
        stdin=(
            "event_type: process_switch\nto_process: null\n"
            "regeneration_proposals: G2 maybe\ndecision: d\n"
        ),
    )
    assert bad.returncode == 1
    good = _run(
        tmp_path,
        "log",
        stdin=(
            "event_type: process_switch\nto_process: planning\n"
            "regeneration_proposals: G1.2 accepted (purpose changed); "
            "G2 rejected (no evidence)\ndecision: Replace G1.2.\n"
        ),
    )
    assert good.returncode == 0, good.stderr
    assert _trace(tmp_path)[-1]["decision"] == (
        "regeneration proposals: G1.2 accepted (purpose changed); "
        "G2 rejected (no evidence). Replace G1.2."
    )


def test_no_goals_refuses_goal_events_and_the_ledger(tmp_path: Path) -> None:
    first = "event_type: process_switch\nto_process: reviewing\ndecision: d\n"
    assert _run(tmp_path, "log", "--no-goals", stdin=first).returncode == 0
    goal = "event_type: goal_created\ngoal_id: G1\ndecision: d\n"
    assert _run(tmp_path, "log", "--no-goals", stdin=goal).returncode == 1
    ledger = (
        "event_type: process_switch\nto_process: null\n"
        "regeneration_proposals: none\ndecision: d\n"
    )
    assert _run(tmp_path, "log", "--no-goals", stdin=ledger).returncode == 1
    stop = "event_type: process_switch\nto_process: null\ndecision: Stop.\n"
    assert _run(tmp_path, "log", "--no-goals", stdin=stop).returncode == 0
    assert _trace(tmp_path)[-1]["decision"] == "Stop."


def test_list_items_and_empty_targets(tmp_path: Path) -> None:
    listed = _run(
        tmp_path,
        "log",
        stdin=(
            "event_type: process_switch\nto_process: planning\ndecision: d\n"
            "evidence:\n- first item\n- second item\nopen_uncertainty:\n- open\n"
        ),
    )
    assert listed.returncode == 0, listed.stderr
    event = _trace(tmp_path)[0]
    assert event["evidence"] == ["first item", "second item"]
    assert event["open_uncertainty"] == ["open"]
    empty = _run(
        tmp_path,
        "log",
        stdin="event_type: process_switch\nto_process:\ndecision: d\n",
    )
    assert empty.returncode == 1
    assert "to_process needs a process name" in empty.stderr
    assert "Traceback" not in empty.stderr
    dangling = _run(
        tmp_path,
        "log",
        stdin="event_type: process_switch\nto_process: translating\n"
        "decision: d\nevidence:\nno dash here\n",
    )
    assert dangling.returncode == 1
    assert "Traceback" not in dangling.stderr
