"""Skill-text invariants that the ablation design and the trace analyses rely on."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from agentic_cogwriter.analysis.process_sequences import DELEGATED_PROCESS
from agentic_cogwriter.analysis.trace_endings import ROLE
from agentic_cogwriter.runner.skill_checks import ack_token, known_skills

REPO_ROOT = Path(__file__).parents[2]
A4_SKILL = REPO_ROOT / "plugin/skills/agentic-cog-writer/SKILL.md"
EXPERIMENT_SKILLS = REPO_ROOT / "experiments/plugin/skills"
BASELINE_SKILLS = REPO_ROOT / "experiments/baselines/skills"
PROMPTS = REPO_ROOT / "experiments/conditions/prompts"
ROLES = ("planning", "translating", "reviewing")
SKILL_ROOTS = (REPO_ROOT / "plugin/skills", EXPERIMENT_SKILLS, BASELINE_SKILLS)

TITLE = "# Agentic CogWriter"
SELECT = "## Select the next process"
STATE = "## State"
DELEGATE = "## Delegate the selected process"
PERFORM = "## Perform the selected process"
BRIEF = "### Brief"
REPORTS = "## Role reports"
FINISH = "## Finish"
REFERENCES = "## References"
PARAGRAPH = "## Paragraph unit"
GOAL_SECTIONS = {"## Goals", "### Goal events", "### Post-`Reviewing` ledger"}
NO_GOAL_CHANGES = {SELECT, STATE, BRIEF, REPORTS, FINISH, REFERENCES}
IN_CONTEXT = {DELEGATE: PERFORM}
# skill -> (sections that change, sections dropped, renamed sections, added sections)
ABLATIONS = {
    "cognitive-writing-no-goal-network": (NO_GOAL_CHANGES, GOAL_SECTIONS, {}, []),
    "cognitive-writing-fixed-order": ({SELECT, REPORTS, "## Goals"}, set(), {}, []),
    "cognitive-writing-single-context": ({BRIEF}, set(), IN_CONTEXT, []),
    "cognitive-writing-single-writer": ({BRIEF}, set(), IN_CONTEXT, [PARAGRAPH]),
    "cognitive-writing-loop-only": (NO_GOAL_CHANGES, GOAL_SECTIONS, IN_CONTEXT, []),
}


def _sections(text: str) -> dict[str, str]:
    """Map each heading outside code fences to its text, frontmatter under ''."""

    sections: dict[str, list[str]] = {"": []}
    heading, fenced = "", False
    for line in text.splitlines(keepends=True):
        if line.startswith("```"):
            fenced = not fenced
        if not fenced and re.match(r"#{1,3} ", line):
            heading = line.rstrip("\n")
            assert heading not in sections, heading
            sections[heading] = []
        sections[heading].append(line)
    # The last section of a file has no blank line after it; ignore that.
    return {key: "".join(lines).rstrip("\n") for key, lines in sections.items()}


def _skill(name: str) -> str:
    return (EXPERIMENT_SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


def _a4() -> dict[str, str]:
    return _sections(A4_SKILL.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ABLATIONS)
def test_ablations_differ_from_a4_only_in_declared_sections(name: str) -> None:
    a4 = _a4()
    ablation = _sections(_skill(name))
    changed, dropped, renamed, added = ABLATIONS[name]

    title = next(heading for heading in ablation if heading.startswith("# "))
    expected = [
        title if heading == TITLE else renamed.get(heading, heading)
        for heading in a4
        if heading not in dropped
    ]
    assert [heading for heading in ablation if heading not in added] == expected
    for heading in a4:
        if heading in dropped or heading == "":
            continue
        own = title if heading == TITLE else renamed.get(heading, heading)
        if heading == TITLE:
            assert ablation[own].split("\n", 1)[1] == a4[heading].split("\n", 1)[1]
        elif heading in changed or heading in renamed:
            assert ablation[own] != a4[heading], f"{heading} is declared but equal"
        else:
            assert ablation[own] == a4[heading], heading


def test_loop_only_takes_each_change_from_its_single_ablation() -> None:
    loop_only = _sections(_skill("cognitive-writing-loop-only"))
    no_goals = _sections(_skill("cognitive-writing-no-goal-network"))
    fixed_order = _sections(_skill("cognitive-writing-fixed-order"))
    single_context = _sections(_skill("cognitive-writing-single-context"))

    assert loop_only[SELECT] == fixed_order[SELECT]
    assert loop_only[PERFORM] == single_context[PERFORM]
    for heading in (STATE, FINISH, REFERENCES):
        assert loop_only[heading] == no_goals[heading], heading
    assert "scope the next step in the cycle" in loop_only[REPORTS]
    assert "Goal" not in loop_only[REPORTS]
    brief = loop_only[BRIEF]
    assert "Process: <Role>" in brief
    assert "Active goals" not in brief
    assert "Never request goal-setting." in brief


def test_fixed_order_wording_never_selects_against_the_cycle() -> None:
    for name in ("cognitive-writing-fixed-order", "cognitive-writing-loop-only"):
        text = _skill(name)
        assert "select the next process" not in text
        assert "selects `Planning`" not in text
        assert "fixed `Planning`, `Translating`, then `Reviewing` order" in text
    assert "the agent may change" not in _skill("cognitive-writing-loop-only")


def test_a6_keeps_the_a4_goal_logging_check() -> None:
    fixed_order = _sections(_skill("cognitive-writing-fixed-order"))
    assert fixed_order[FINISH] == _a4()[FINISH]
    assert "has no goal event" in fixed_order[FINISH]


def test_single_writer_is_single_context_plus_the_paragraph_unit() -> None:
    text = _skill("cognitive-writing-single-writer")
    sections = _sections(text)
    single_context = _sections(_skill("cognitive-writing-single-context"))
    for heading, body in single_context.items():
        if heading and not heading.startswith("# "):
            assert sections[heading] == body, heading
    unit = sections[PARAGRAPH]
    assert "at most 120 words, counting each CJK character as one word" in unit
    assert "writing_state.py words --max 120" in unit
    # A Translating step covers its whole scope as successive paragraphs, so the
    # pass and step caps count scopes, as in A4, not paragraphs.
    assert "covers its whole scope" in unit
    assert "log one process switch before the step, not one per paragraph" in unit
    assert "exactly one paragraph" not in unit
    assert "repository writing" not in text
    assert "AI-pattern phrasing" not in text


def _skill_files() -> list[Path]:
    return sorted(path for root in SKILL_ROOTS for path in root.glob("*/SKILL.md"))


@pytest.mark.parametrize("path", _skill_files(), ids=lambda path: path.parent.name)
def test_every_staged_skill_opens_with_its_acknowledgment_note(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    body = text.split("\n---\n", 1)[1].lstrip("\n")
    assert body.startswith(
        "> [!NOTE]\n"
        f"> After reading this `SKILL.md`, say: `{ack_token(path.parent.name)}`\n"
    )
    assert "immediately after reading this skill" in text
    assert "before any tool call" not in text
    assert "never appears in `.writing/draft.md`" in text or (
        "never goes into `.writing/draft.md`" in text
    )


def test_acknowledgment_tokens_are_distinct_and_cover_every_skill() -> None:
    names = known_skills()
    assert sorted(path.parent.name for path in _skill_files()) == list(names)
    tokens = [ack_token(name) for name in names]
    assert len(set(tokens)) == len(tokens)
    for token in tokens:
        assert sum(other in token for other in tokens) == 1, token


@pytest.mark.parametrize("role", ROLES)
def test_role_reports_begin_with_the_acknowledgment_line(role: str) -> None:
    text = (REPO_ROOT / f"plugin/skills/{role}/SKILL.md").read_text(encoding="utf-8")
    report = text.split("## Report format", 1)[1].split("```text\n", 1)[1]
    assert report.startswith(f"{ack_token(role)}\n")
    assert "indings:" in report
    assert "Next process:" in report
    assert "never repeats it in a written report" in text


def _prompt_texts() -> list[Path]:
    return [
        A4_SKILL,
        *sorted((A4_SKILL.parent / "references").glob("*.md")),
        *(REPO_ROOT / f"plugin/skills/{role}/SKILL.md" for role in ROLES),
        *sorted(EXPERIMENT_SKILLS.glob("*/SKILL.md")),
        *sorted(EXPERIMENT_SKILLS.glob("*/references/*.md")),
        *sorted(BASELINE_SKILLS.glob("*/SKILL.md")),
        *sorted(PROMPTS.glob("a9_*.md")),
        *sorted((REPO_ROOT / "experiments/conditions/contracts").glob("*.md")),
    ]


def _ids(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


@pytest.mark.parametrize("path", _prompt_texts(), ids=_ids)
def test_prompts_never_mention_a_fallback(path: Path) -> None:
    # The delegation analyses count runs whose trace decisions mention a
    # fallback, so a prompt that uses the word would plant false positives.
    assert "fallback" not in path.read_text(encoding="utf-8").casefold()


@pytest.mark.parametrize("path", _prompt_texts(), ids=_ids)
def test_prompts_have_no_memory_interruptions_or_user_control(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for removed in (
        ".writing/memory",
        "memory/",
        "may interrupt",
        "under the user's control",
        "The user owns",
        "user intent",
        "user's top-level intent",
        "Ask the user",
        "Tell the user",
    ):
        assert removed not in text, removed


@pytest.mark.parametrize("role", ROLES)
def test_brief_names_its_own_role_first_for_the_trace_analyses(role: str) -> None:
    template = _a4()[BRIEF].split("```text\n", 1)[1].split("```", 1)[0]
    filled = template.replace("<role>", role).replace("<Role>", role.capitalize())
    assert filled.startswith(f"${role} ")
    assert ROLE.findall(filled) == [role]
    match = DELEGATED_PROCESS.search(filled)
    assert match is not None and match.group(1).casefold() == role
    assert "SKILL.md" not in filled
    for required in (
        "You are not the Monitor.",
        f"Follow the {role} skill that this message loads.",
        "do not spawn agents",
        "do not run codex",
        "do not write .writing/trace/process.jsonl",
        "never ask questions",
        "Do not search the web",
        "Output language:",
        "Length and format:",
        "Scope:",
        "Active goals: <the IDs of the active goals",
        ".writing/assignment.md",
    ):
        assert required in filled, required


def test_monitor_spawns_without_forked_context_and_bounds_the_wait() -> None:
    delegate = _a4()[DELEGATE]
    for required in (
        "`fork_context: false`",
        "`timeout_ms: 300000`",
        "at most three calls in all",
        "Call `close_agent` on that agent immediately",
        "Delegate a failed step once more",
    ):
        assert required in delegate, required


def test_selection_has_a_default_row_and_the_stop_rule_has_caps() -> None:
    a4 = _a4()
    rows = [line for line in a4[SELECT].splitlines() if line.startswith("| ")][2:]
    assert rows[-1].startswith("| Any other state")
    assert any(row.startswith("| The latest report is from `Planning`") for row in rows)
    for required in (
        "`Verdict: no required change`",
        "Four passes have ended.",
        "Twelve role steps have run.",
        "no change request arrived after it",
    ):
        assert required in a4["## Stop"], required
    reviewing = (REPO_ROOT / "plugin/skills/reviewing/SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "Compute the Verdict from Open findings alone" in reviewing


def test_trace_is_written_only_through_the_logging_script() -> None:
    trace = _a4()["## Trace"]
    assert "python3 <skill dir>/scripts/writing_state.py log <<'EOF'" in trace
    assert "date -Is" not in A4_SKILL.read_text(encoding="utf-8")
    for name in ABLATIONS:
        script = EXPERIMENT_SKILLS / name / "scripts/writing_state.py"
        assert (
            script.read_bytes()
            == (A4_SKILL.parent / "scripts/writing_state.py").read_bytes()
        )
