"""Invariants of the ``cw`` state tool, run as the staged script in a workspace."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from agentic_cogwriter.analysis.ledger import ledgers
from agentic_cogwriter.paths import REPOSITORY_ROOT

CW = REPOSITORY_ROOT / "plugin/cw/cw.py"
TASK = (
    "## Assignment\nWrite a book proposal of about 1000 words. "
    "What gap does the book\n  seek to fill?\n"
)
GOALS = (
    '- [G1] The proposal states the gap | src: "What gap does the book seek to fill"\n'
    "  - [G1.1] The gap is named in the first section | src: G1\n"
    '- [G2] About 1000 words | src: "about 1000 words"\n'
)
DRAFT = "The gap is clear. The book fills it.\n\nIt has about 1000 words.\n"
MET = {
    "verdicts": [
        {"goal": g, "met": True, "evidence": "The gap is clear.", "where": "p1"}
        for g in ("G1", "G1.1", "G2")
    ],
    "proposals": [],
    "findings": [],
}
ARMS = {
    "A4": {"goals": True, "order": "adaptive", "execution": "delegated"},
    "A5": {"goals": False, "order": "adaptive", "execution": "delegated"},
    "A6": {"goals": True, "order": "fixed", "execution": "delegated"},
    "A7": {"goals": True, "order": "adaptive", "execution": "paragraph"},
    "A8": {"goals": True, "order": "adaptive", "execution": "in_context"},
}


class Workspace:
    def __init__(self, root: Path, arm: str) -> None:
        self.root = root
        self.arm = arm
        staged = root / ".agents/cw"
        staged.mkdir(parents=True)
        shutil.copyfile(CW, staged / "cw.py")
        (staged / "cw.json").write_text(
            json.dumps({**ARMS[arm], "language": "English"}), encoding="utf-8"
        )
        self.w = root / ".writing"
        self.w.mkdir()
        (self.w / "task.md").write_text(TASK, encoding="utf-8")

    def cw(self, *args: str, stdin: str = "", thread: str = "M"):
        env = {**os.environ, "CODEX_THREAD_ID": thread}
        return subprocess.run(
            [sys.executable, str(self.root / ".agents/cw/cw.py"), *args],
            input=stdin,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

    def ok(self, *args: str, stdin: str = "", thread: str = "M") -> dict:
        result = self.cw(*args, stdin=stdin, thread=thread)
        assert result.returncode == 0, result.stderr + result.stdout
        return json.loads(result.stdout.splitlines()[0])

    def refused(self, *args: str, stdin: str = "", thread: str = "M") -> str:
        result = self.cw(*args, stdin=stdin, thread=thread)
        assert result.returncode == 1, result.stdout
        return result.stderr

    def history(self) -> list[dict]:
        text = (self.w / "history/history.jsonl").read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines()]

    def write(self, name: str, text: str) -> None:
        (self.w / name).write_text(text, encoding="utf-8")

    def plan(self, goals: str = GOALS, flags: tuple[str, ...] = ("--goals",)) -> int:
        entry = self.ok("step", "planning", *flags, "--why", "plan")
        if "--goals" in flags:
            self.write("goals.md", goals)
        self.write(f"history/step-{entry['step']:02d}/plan.md", "Plan.\n")
        return entry["step"]

    def translate(self, text: str = DRAFT, scope: str = "G1") -> int:
        entry = self.ok("step", "translating", "--scope", scope, "--why", "draft")
        if self.arm == "A7":
            self.ok("para", "--append", stdin=text.split("\n\n")[0])
        else:
            self.write("draft.md", text)
        return entry["step"]

    def review(self, verdict: dict | None = None) -> int:
        entry = self.ok("step", "reviewing", "--why", "check")
        thread = "M" if self.arm in ("A7", "A8") else "R"
        self.ok("review", stdin=json.dumps(verdict or MET), thread=thread)
        return entry["step"]

    def last_close(self, *args: str) -> dict:
        """Run a coordinator command, whatever its outcome; return the last close."""

        self.cw(*args)
        return self.closes()[-1]

    def closes(self) -> list[dict]:
        return [e for e in self.history() if e.get("cmd") == "close"]


@pytest.fixture
def ws(tmp_path: Path) -> Workspace:
    return Workspace(tmp_path, "A4")


def make(tmp_path: Path, arm: str) -> Workspace:
    return Workspace(tmp_path, arm)


def test_cw_caller(ws: Workspace) -> None:
    ws.plan()
    for args in (
        ("step", "translating", "--scope", "G1", "--why", "x"),
        ("decide", "G1", "accept", "--why", "x"),
        ("stop", "--reason", "met", "--why", "x"),
        ("para", "--append"),
    ):
        assert "Monitor only" in ws.refused(*args, thread="child")
    # A caller violation fails the open step at its close.
    assert ws.last_close("step", "planning", "--goals", "--why", "x")["reason"] == (
        "caller"
    )
    ws.write("history/step-02/plan.md", "Plan.\n")
    ws.write("goals.md", GOALS)
    ws.translate()
    ws.ok("step", "reviewing", "--why", "x")
    assert "Reviewer" in ws.refused("review", stdin=json.dumps(MET))
    assert ws.last_close("step", "reviewing", "--why", "x")["reason"] == "caller"


def test_cw_allowance(ws: Workspace, tmp_path: Path) -> None:
    ws.plan()
    ws.translate()
    ws.ok("step", "reviewing", "--why", "check")
    ws.write("draft.md", "Edited by the Reviewer.\n")
    second = ws.ok("step", "reviewing", "--why", "reissue")
    close = ws.closes()[-1]
    assert close["ok"] is False and close["reason"] == "allowance"
    assert close["restored"] == ["draft.md"]
    assert (ws.w / "draft.md").read_text(encoding="utf-8") == DRAFT
    assert second["attempt"] == 2
    ws.write("draft.md", "Edited again.\n")
    assert "only `cw stop --reason failure`" in ws.refused(
        "step", "reviewing", "--why", "x"
    )
    ws.ok("stop", "--reason", "failure", "--why", "two failures")
    # Runner-owned files and free files under .writing/ are ignored.
    other = Workspace(tmp_path / "other", "A4")
    other.plan()
    other.write("history/turn-02-request.md", "")
    other.write("source.md", "notes")
    other.ok("step", "translating", "--scope", "G1", "--why", "x")
    assert other.closes()[-1]["ok"] is True


def test_cw_output_check(tmp_path: Path) -> None:
    ws = make(tmp_path, "A4")
    ws.ok("step", "planning", "--goals", "--why", "plan")
    ws.write("goals.md", GOALS)
    ws.ok("step", "planning", "--goals", "--why", "reissue")
    close = ws.closes()[-1]
    assert close["reason"] == "output" and "plan.md" in close["detail"]
    # The reissue brief carries cw's refusal reason verbatim.
    brief = (ws.w / "history/step-02/brief.md").read_text()
    assert f"- Previous attempt refused by cw: {close['detail']}\n" in brief
    assert not (ws.w / "goals.md").exists()
    other = make(tmp_path / "t", "A4")
    other.plan()
    other.ok("step", "translating", "--scope", "G1", "--why", "x")
    assert other.last_close("step", "reviewing", "--why", "x")["reason"] == "output"
    third = make(tmp_path / "r", "A4")
    third.plan()
    third.translate()
    third.ok("step", "reviewing", "--why", "x")
    assert "no review" in third.last_close("step", "planning", "--why", "x")["detail"]


def test_cw_retry_marker(ws: Workspace) -> None:
    ws.plan()
    ws.ok("step", "translating", "--scope", "G1", "--why", "x")
    ws.write("draft.md", DRAFT)
    ws.write("history/retry-01", "")
    ws.ok("step", "translating", "--scope", "G1", "--why", "reissue")
    close = ws.closes()[-1]
    assert close["ok"] is False and close["reason"] == "retry"
    assert not (ws.w / "draft.md").exists()
    ws.write("draft.md", DRAFT)
    ws.write("history/turn-02-request.md", "change")
    ws.ok("step", "reviewing", "--why", "x")
    assert ws.closes()[-1]["ok"] is True


def test_cw_order(tmp_path: Path) -> None:
    fixed = make(tmp_path / "f", "A6")
    fixed.plan()
    assert "fixed order" in fixed.refused("step", "reviewing", "--why", "x")
    fixed.translate()
    fixed.review(
        {**MET, "verdicts": [{**v, "met": False, "fix": "f"} for v in MET["verdicts"]]}
    )
    assert "fixed order" in fixed.refused(
        "step", "translating", "--scope", "G1", "--why", "x"
    )
    fixed.ok("step", "planning", "--why", "x")
    adaptive = make(tmp_path / "a", "A4")
    adaptive.plan()
    adaptive.translate()
    adaptive.review({**MET, "findings": [{"kind": "local", "where": "p1", "fix": "f"}]})
    adaptive.translate(text=DRAFT + "\nMore.\n")
    adaptive.ok("step", "planning", "--why", "x")


def test_cw_first_step(tmp_path: Path) -> None:
    ws = make(tmp_path, "A4")
    assert "planning --goals" in ws.refused(
        "step", "translating", "--scope", "x", "--why", "x"
    )
    assert "planning --goals" in ws.refused("step", "planning", "--why", "x")
    ws.plan()
    ws.translate()
    ws.review()
    ws.ok("stop", "--reason", "met", "--why", "done")
    ws.write("history/turn-02-request.md", "Shorten it.")
    ws.ok("step", "translating", "--scope", "G2", "--why", "free first choice")
    no_goals = make(tmp_path / "a5", "A5")
    assert "no requirements" in no_goals.refused(
        "step", "planning", "--goals", "--why", "x"
    )
    no_goals.ok("step", "translating", "--scope", "opening", "--why", "x")


def test_cw_scope(ws: Workspace) -> None:
    ws.plan()
    assert "--scope" in ws.refused("step", "translating", "--why", "x")
    assert "G9" in ws.refused("step", "translating", "--scope", "G9", "--why", "x")
    ws.ok("step", "translating", "--scope", "G1.1", "opening section", "--why", "x")


@pytest.mark.parametrize(
    ("goals", "message"),
    [
        ('- [G1] Gap | src: "a gap nobody asked for"\n', "does not occur"),
        ('- [G1] Gap | src: "about 1000 words"\n- [G2] Other | src: G1\n', "ancestor"),
        ('- [G1] Gap | src: "about 1000 words"\n  - [G2.1] Bad | src: G1\n', "extend"),
        (
            '- [G1] Gap | src: "about 1000 words" | status: replaced by G4\n',
            "does not exist",
        ),
        ("- G1 no brackets\n", "grammar"),
    ],
)
def test_cw_goals_grammar(tmp_path: Path, goals: str, message: str) -> None:
    ws = make(tmp_path, "A4")
    ws.plan(goals)
    ws.ok("step", "planning", "--goals", "--why", "reissue")
    close = ws.closes()[-1]
    assert close["reason"] == "output" and message in close["detail"]


def test_cw_goals_vanished_id_and_events(ws: Workspace) -> None:
    ws.plan()
    ws.plan('- [G1] Gap | src: "about 1000 words"\n')
    close = ws.last_close("step", "planning", "--goals", "--why", "reissue")
    assert close["ok"] is False and "disappeared" in close["detail"]
    ws.write(
        "goals.md",
        '- [G1] The proposal names a gap | src: "What gap does the book seek to fill"\n'
        "  - [G1.1] The gap is named in the first section | src: G1\n"
        '- [G2] About 1000 words | src: "about 1000 words" | status: replaced by G3\n'
        '- [G3] Roughly 1000 words | src: "about 1000 words"\n',
    )
    ws.write("history/step-03/plan.md", "Plan.\n")
    ws.ok("step", "translating", "--scope", "G3", "--why", "x")
    events = {e["goal_id"]: e for e in ws.history() if e.get("cmd") == "goal"}
    assert events["G1"]["event_type"] == "goal_developed"
    assert events["G3"]["event_type"] == "goal_regenerated"
    assert events["G3"]["origin"] == "planner" and events["G3"]["replaced"] == "G2"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda r: r["verdicts"].pop(), "no verdict for G2"),
        (lambda r: r["verdicts"][0].update(evidence=""), "met evidence"),
        (
            lambda r: r["verdicts"][0].update(evidence="Not in the draft."),
            "met evidence",
        ),
        (lambda r: r["verdicts"][0].update(met=False, fix=""), "needs a fix"),
        (
            lambda r: r["findings"].append({"kind": "local", "where": "p", "fix": ""}),
            "finding",
        ),
        (
            lambda r: r["proposals"].append({"goal": "G9", "replacement": "x"}),
            "inactive",
        ),
    ],
)
def test_cw_review(ws: Workspace, change, message: str) -> None:
    ws.plan()
    ws.translate()
    ws.ok("step", "reviewing", "--why", "x")
    review = json.loads(json.dumps(MET))
    change(review)
    assert message in ws.refused("review", stdin=json.dumps(review), thread="R")
    ws.ok("review", stdin=json.dumps(MET), thread="R")


def test_cw_proposals(ws: Workspace) -> None:
    ws.plan()
    ws.translate()
    proposal = {"goal": "G2", "replacement": "Roughly 1000 words", "reason": "r"}
    ws.review({**MET, "proposals": [proposal]})
    assert "decide every proposal" in ws.refused("step", "planning", "--why", "x")
    assert "decide every proposal" in ws.refused(
        "stop", "--reason", "met", "--why", "x"
    )
    ws.ok("decide", "G2", "accept", "--why", "the count is approximate")
    step = ws.ok("step", "planning", "--goals", "--why", "apply the replacement")
    brief = (ws.w / f"history/step-{step['step']:02d}/brief.md").read_text()
    assert "Replace G2 with: Roughly 1000 words" in brief
    assert "the count is approximate" not in brief
    ws.write(
        "goals.md",
        GOALS.replace('words"\n', 'words" | status: replaced by G3\n')
        + '- [G3] Roughly 1000 words | src: "about 1000 words"\n',
    )
    ws.write(f"history/step-{step['step']:02d}/plan.md", "Plan.\n")
    ws.translate(text=DRAFT + "Applied.\n")
    ws.review(
        {
            **MET,
            "proposals": [{"goal": "G1", "replacement": "x", "reason": "r"}],
            "verdicts": [
                {**v, "goal": g}
                for v, g in zip(MET["verdicts"], ("G1", "G1.1", "G3"), strict=True)
            ],
        }
    )
    ws.ok("decide", "G1", "reject", "--why", "the gap is required")
    ws.ok("stop", "--reason", "met", "--why", "all met")
    history = ws.history()
    regenerated = [e for e in history if e.get("event_type") == "goal_regenerated"]
    assert regenerated[0]["origin"] == "proposal"
    parsed = ledgers(history)
    assert parsed == [
        [
            {
                "goal_id": "G2",
                "outcome": "accepted",
                "reason": "the count is approximate",
            }
        ],
        [{"goal_id": "G1", "outcome": "rejected", "reason": "the gap is required"}],
    ]


def test_cw_cap(ws: Workspace) -> None:
    unmet = {
        **MET,
        "verdicts": [{**v, "met": False, "fix": "f"} for v in MET["verdicts"]],
    }
    ws.plan()
    ws.translate()
    proposal = {"goal": "G2", "replacement": "Roughly 1000 words", "reason": "r"}
    for index in range(4):
        ws.review(unmet if index < 3 else {**unmet, "proposals": [proposal]})
        if index < 3:
            ws.translate(text=DRAFT + "x" * (index + 1) + "\n")
    assert "only `cw stop`" in ws.refused(
        "step", "translating", "--scope", "G1", "--why", "x"
    )
    # At the cap, a refused stop points to --reason cap, not to another step.
    message = ws.refused("stop", "--reason", "met", "--why", "x")
    assert "stop with `--reason cap`" in message and "cw step" not in message
    # A cap stops the run even with an undecided proposal, which it reports.
    stop = ws.ok("stop", "--reason", "cap", "--why", "four passes")
    assert stop["undecided_proposals"] == ["G2"]
    assert ledgers([stop]) == [[]]
    ws.write("history/turn-02-request.md", "Again.")
    ws.translate(text=DRAFT + "turn two\n")
    ws.review(unmet)
    assert "needs 4" in ws.refused("stop", "--reason", "cap", "--why", "x")


def test_cw_stop(tmp_path: Path) -> None:
    ws = make(tmp_path, "A4")
    ws.plan()
    ws.translate()
    assert "successful Reviewing" in ws.refused("stop", "--reason", "met", "--why", "x")
    assert "failed reissue" in ws.refused("stop", "--reason", "failure", "--why", "x")
    ws.review(
        {**MET, "findings": [{"kind": "structure", "where": "end", "fix": "add"}]}
    )
    assert "findings" in ws.refused("stop", "--reason", "met", "--why", "x")
    ws.translate(text=DRAFT + "End.\n")
    unmet = json.loads(json.dumps(MET))
    unmet["verdicts"][2] = {
        "goal": "G2",
        "met": False,
        "fix": "lengthen",
        "where": "all",
    }
    ws.review(unmet)
    assert "unmet" in ws.refused("stop", "--reason", "met", "--why", "x")
    ws.translate(text=DRAFT + "End again.\n")
    ws.review()
    stop = ws.ok("stop", "--reason", "met", "--why", "done")
    assert stop["from_process"] == "reviewing" and stop["to_process"] is None
    assert stop["decision"].startswith("regeneration proposals: none. ")
    # A failed step after a met review: met needs the latest step to be that review.
    failing = make(tmp_path / "failing", "A4")
    failing.plan()
    failing.translate()
    failing.review()
    failing.ok("step", "translating", "--scope", "G1", "--why", "no change")
    assert "successful Reviewing" in failing.refused(
        "stop", "--reason", "met", "--why", "closes the failed step"
    )
    failing.ok("step", "translating", "--scope", "G1", "--why", "reissue")
    # After the reissue fails too, only failure is accepted.
    for reason in ("met", "cap"):
        assert "only `--reason failure`" in failing.refused(
            "stop", "--reason", reason, "--why", "x"
        )
    failing.ok("stop", "--reason", "failure", "--why", "two failures")
    no_goals = make(tmp_path / "a5", "A5")
    no_goals.translate(scope="all")
    no_goals.review({"findings": []})
    no_goals.ok("stop", "--reason", "met", "--why", "no findings")


def test_cw_para(tmp_path: Path) -> None:
    ws = make(tmp_path, "A7")
    ws.plan()
    ws.ok("step", "translating", "--scope", "G1", "--why", "x")
    ws.ok("para", "--append", stdin="First paragraph.")
    assert "already wrote" in ws.refused("para", "--append", stdin="Second.")
    ws.ok("step", "translating", "--scope", "G1", "--why", "x")
    assert "blank line" in ws.refused("para", "--append", stdin="One.\n\nTwo.")
    assert "limit is 200" in ws.refused("para", "--append", stdin="w " * 201)
    warned = ws.ok("para", "--replace-last", stdin="w " * 121)
    assert "warning" in warned
    assert (ws.w / "draft.md").read_text().count("\n\n") == 0
    ws.ok("step", "translating", "--scope", "G1", "--why", "x")
    ws.ok("para", "--append", stdin="Second paragraph.")
    ws.write("draft.md", (ws.w / "draft.md").read_text() + "\nHand edit.\n")
    assert ws.last_close("step", "reviewing", "--why", "x")["reason"] == "allowance"
    assert "no paragraph unit" in make(tmp_path / "a4", "A4").refused(
        "para", "--append", stdin="x"
    )


def test_cw_turn_requests_are_requirement_sources(ws: Workspace) -> None:
    ws.plan()
    ws.translate()
    ws.review()
    ws.ok("stop", "--reason", "met", "--why", "done")
    ws.write("history/turn-02-request.md", "Add a closing call to action.\n")
    step = ws.plan(
        GOALS
        + '- [G3] It ends with a call to action | src: "a closing call to action"\n'
    )
    ws.translate(text=DRAFT + "Act now.\n", scope="G3")
    assert ws.closes()[-1]["step"] == step and ws.closes()[-1]["ok"] is True


def test_cw_snapshot(ws: Workspace) -> None:
    ws.plan()
    ws.translate()
    ws.review()
    ws.ok("stop", "--reason", "met", "--why", "done")
    final = ws.w / "history/final"
    assert (final / "turn-01/draft.md").read_text() == DRAFT
    ws.write("history/turn-02-request.md", "Change.")
    ws.translate(text="Turn two text.\n", scope="G2")
    ws.review(
        {
            **MET,
            "verdicts": [{**v, "evidence": "Turn two text."} for v in MET["verdicts"]],
        }
    )
    ws.ok("stop", "--reason", "met", "--why", "done")
    assert (final / "turn-01/draft.md").read_text() == DRAFT
    assert (final / "turn-02/draft.md").read_text() == "Turn two text.\n"


def test_cw_prints_the_spawn_line_and_keeps_why_out_of_the_brief(ws: Workspace) -> None:
    result = ws.cw("step", "planning", "--goals", "--why", "secret reason")
    entry = json.loads(result.stdout.splitlines()[0])
    brief = ws.w / "history/step-01/brief.md"
    line = f"$planning Read {brief} and follow it. [{entry['nonce']}]"
    assert entry["spawn"] == line
    # cw prints the complete delegation call; the Monitor copies it verbatim.
    call = result.stdout.split("\n", 2)[2]
    assert call.startswith(
        "const { agent_id } = await tools.multi_agent_v1__spawn_agent("
        f"{{ fork_context: false, message: {json.dumps(line)} }});\n"
    )
    for required in ("wait_agent(", "timeout_ms: 300000", "while (r.timed_out)"):
        assert required in call
    assert "close_agent({ target: agent_id })" in call
    for forbidden in ("model", "reasoning_effort", "service_tier", "items"):
        assert forbidden not in call
    text = brief.read_text()
    assert "secret reason" not in text
    for field in (
        "Nonce",
        "Role skill",
        "Task",
        "Output language: English",
        "Goal-setting: requested",
    ):
        assert field in text


def test_cw_history_tampering_fails_the_step(ws: Workspace) -> None:
    ws.plan()
    with (ws.w / "history/history.jsonl").open("a") as handle:
        handle.write('{"event_type": "process_switch"}\n')
    assert ws.last_close("step", "planning", "--goals", "--why", "x")["reason"] == (
        "allowance"
    )
    ws.write("goals.md", GOALS)
    ws.write("history/step-02/plan.md", "Plan.\n")
    ws.ok("step", "translating", "--scope", "G1", "--why", "x")
    assert ws.closes()[-1]["ok"] is True


def test_cw_refusal_lists_every_invalid_requirement_line(ws: Workspace) -> None:
    ws.plan(
        '- [G1] Gap | src: "a gap nobody asked for"\n'
        '  - [G2.1] Bad child | src: "about 1000 words"\n'
        '- [G3] Count | src: "\\"about 1000 words\\""\n'
        "- G4 no brackets\n"
    )
    close = ws.last_close("step", "planning", "--goals", "--why", "reissue")
    for problem in (
        "goals.md line 4 does not match the grammar",
        "G2.1 does not extend its parent's ID",
        "G1: the quoted src does not occur",
        "G3: the quoted src does not occur",
    ):
        assert problem in close["detail"], problem
    brief = (ws.w / "history/step-02/brief.md").read_text()
    assert close["detail"] in brief


def test_cw_unescapes_quote_characters_before_matching_a_source(tmp_path: Path) -> None:
    ws = make(tmp_path, "A4")
    task = ws.w / "task.md"
    task.write_text(TASK + 'Cite the "Labor Law" and the author\'s note.\n')
    ws.plan(
        '- [G1] Cites the law | src: "Cite the \\"Labor Law\\" '
        "and the author\\'s note.\"\n"
        '- [G2] Exact otherwise | src: "Cite the \\"Labour Law\\""\n'
    )
    close = ws.last_close("step", "planning", "--goals", "--why", "check")
    assert "G1:" not in close["detail"]
    assert "G2: the quoted src does not occur" in close["detail"]


def test_cw_refused_stop_says_the_turn_is_not_over(ws: Workspace) -> None:
    ws.plan()
    ws.translate()
    review = json.loads(json.dumps(MET))
    review["verdicts"][2] = {
        "goal": "G2",
        "met": False,
        "fix": "lengthen",
        "where": "all",
    }
    review["findings"] = [{"kind": "local", "where": "end", "fix": "add a close"}]
    ws.review(review)
    message = ws.refused("stop", "--reason", "met", "--why", "done")
    for part in (
        "the turn is not over",
        "G2 unmet: lengthen",
        "finding at end: add a close",
        "Open the next step with `cw step`",
    ):
        assert part in message, part
    assert "the turn is not over" in ws.refused("stop", "--reason", "cap", "--why", "x")
