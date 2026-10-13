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
ROLES = ("planning", "translating", "reviewing")
SKILL_ROOTS = (
    REPO_ROOT / "plugin/skills",
    EXPERIMENT_SKILLS,
    REPO_ROOT / "experiments/baselines/skills",
)

TITLE = "# Agentic CogWriter"
DELEGATE = "## Delegate the selected process"
IN_CONTEXT = "## Perform the selected process"
GOAL_SECTIONS = {
    "## Goals",
    "### Goal events",
    "### Post-`Reviewing` ledger",
    "## References",
}
NO_GOAL_CHANGES = {
    "## Select the next process",
    "## Stop",
    "## State",
    "### Brief",
    "## Role reports",
    "## Finish",
}
# Sections each ablation may change, drop, or rename relative to A4.
ABLATIONS = {
    "cognitive-writing-no-goal-network": (NO_GOAL_CHANGES, GOAL_SECTIONS, {}),
    "cognitive-writing-fixed-order": (
        {"## Select the next process"},
        {"## References"},
        {},
    ),
    "cognitive-writing-single-context": (
        {"### Brief"},
        set(),
        {DELEGATE: IN_CONTEXT},
    ),
    "cognitive-writing-loop-only": (
        NO_GOAL_CHANGES,
        GOAL_SECTIONS,
        {DELEGATE: IN_CONTEXT},
    ),
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
    # A dropped trailing section leaves its predecessor last; ignore that newline.
    return {key: "".join(lines).rstrip("\n") for key, lines in sections.items()}


def _skill(name: str) -> str:
    return (EXPERIMENT_SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ABLATIONS)
def test_ablations_differ_from_a4_only_in_declared_sections(name: str) -> None:
    a4 = _sections(A4_SKILL.read_text(encoding="utf-8"))
    ablation = _sections(_skill(name))
    changed, dropped, renamed = ABLATIONS[name]

    title = next(heading for heading in ablation if heading.startswith("# "))
    expected = [
        title if heading == TITLE else renamed.get(heading, heading)
        for heading in a4
        if heading not in dropped
    ]
    assert list(ablation) == expected
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

    assert (
        loop_only["## Select the next process"]
        == (fixed_order["## Select the next process"])
    )
    assert loop_only[IN_CONTEXT] == single_context[IN_CONTEXT]
    for heading in NO_GOAL_CHANGES - {"## Select the next process", "### Brief"}:
        assert loop_only[heading] == no_goals[heading], heading
    brief = loop_only["### Brief"]
    assert "Process: <Role>" in brief
    assert "Active goals" not in brief
    assert "Never request goal-setting." in brief


def test_a6_keeps_the_a4_goal_logging_check() -> None:
    a4 = _sections(A4_SKILL.read_text(encoding="utf-8"))
    fixed_order = _sections(_skill("cognitive-writing-fixed-order"))
    assert fixed_order["## Finish"] == a4["## Finish"]
    assert "has a goal event" in a4["## Finish"]


def test_single_writer_drops_the_extra_writing_guidance() -> None:
    text = _skill("cognitive-writing-single-writer")
    assert "repository writing contract" not in text
    assert "AI-pattern phrasing" not in text
    assert "Each `Translating` step appends exactly one paragraph" in text


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
    assert "Findings:" in report
    assert "Next process:" in report


def _cogwriter_texts() -> list[Path]:
    return [
        A4_SKILL,
        *sorted((A4_SKILL.parent / "references").glob("*.md")),
        *(REPO_ROOT / f"plugin/skills/{role}/SKILL.md" for role in ROLES),
        *sorted(EXPERIMENT_SKILLS.glob("*/SKILL.md")),
        *sorted(
            (EXPERIMENT_SKILLS / "cognitive-writing-single-context").glob("*/*.md")
        ),
        *sorted((REPO_ROOT / "experiments/conditions/contracts").glob("*.md")),
    ]


@pytest.mark.parametrize(
    "path", _cogwriter_texts(), ids=lambda path: path.relative_to(REPO_ROOT).as_posix()
)
def test_prompts_never_mention_a_fallback(path: Path) -> None:
    # The delegation analyses count runs whose trace decisions mention a
    # fallback, so a prompt that uses the word would plant false positives.
    assert "fallback" not in path.read_text(encoding="utf-8").casefold()


@pytest.mark.parametrize(
    "path", _cogwriter_texts(), ids=lambda path: path.relative_to(REPO_ROOT).as_posix()
)
def test_prompts_have_no_memory_interruptions_or_user_questions(path: Path) -> None:
    if path.parent.name == "cognitive-writing-single-writer":
        pytest.skip("single-writer keeps its paragraph-scale interrupting design")
    text = path.read_text(encoding="utf-8")
    for removed in (
        ".writing/memory",
        "memory/",
        "may interrupt",
        "under the user's control",
        "Ask the user",
        "Tell the user",
    ):
        assert removed not in text, removed


@pytest.mark.parametrize("role", ROLES)
def test_brief_names_its_own_role_first_for_the_trace_analyses(role: str) -> None:
    brief = _sections(A4_SKILL.read_text(encoding="utf-8"))["### Brief"]
    template = brief.split("```text\n", 1)[1].split("```", 1)[0]
    filled = template.replace("<role>", role).replace("<Role>", role.capitalize())
    assert filled.startswith(f"${role} ")
    assert ROLE.findall(filled) == [role]
    match = DELEGATED_PROCESS.search(filled)
    assert match is not None and match.group(1).casefold() == role
    for required in (
        "You are not the Monitor.",
        f".agents/skills/{role}/SKILL.md",
        "do not spawn agents",
        "do not run codex",
        "do not write .writing/trace/process.jsonl",
        "Output language:",
        "Length and format:",
        "Scope:",
        "Active goals:",
        ".writing/assignment.md",
    ):
        assert required in filled, required


def test_monitor_spawns_without_forked_context_and_closes_agents() -> None:
    delegate = _sections(A4_SKILL.read_text(encoding="utf-8"))[DELEGATE]
    for required in ("`fork_context: false`", "`wait_agent`", "`close_agent`"):
        assert required in delegate, required


def test_stop_rule_and_pass_budget_match_the_reviewer_verdict() -> None:
    a4 = _sections(A4_SKILL.read_text(encoding="utf-8"))
    reviewing = (REPO_ROOT / "plugin/skills/reviewing/SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "`Verdict: no required change`" in a4["## Stop"]
    assert "After the fourth pass, stop" in a4["## Stop"]
    assert "Write `Verdict: no required change` only when" in reviewing
