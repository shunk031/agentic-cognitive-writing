"""Skill-text invariants that the ablation design and the trace analyses rely on."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

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
STOP = "## Stop"
TRACE = "## Trace"
NO_GOAL_CHANGES = {SELECT, STOP, STATE, BRIEF, REPORTS, TRACE, FINISH, REFERENCES}
IN_CONTEXT_CHANGES = {STOP, STATE, BRIEF, TRACE, "### Goal events", FINISH}
IN_CONTEXT = {DELEGATE: PERFORM}
# skill -> (sections that change, sections dropped, renamed sections, added sections)
ABLATIONS = {
    "cognitive-writing-no-goal-network": (NO_GOAL_CHANGES, GOAL_SECTIONS, {}, []),
    "cognitive-writing-fixed-order": ({SELECT, REPORTS, "## Goals"}, set(), {}, []),
    "cognitive-writing-single-context": (IN_CONTEXT_CHANGES, set(), IN_CONTEXT, []),
    "cognitive-writing-single-writer": (
        IN_CONTEXT_CHANGES,
        set(),
        IN_CONTEXT,
        [PARAGRAPH],
    ),
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


SLICE_2 = pytest.mark.skip(
    reason="slice 2 regenerates the ablations from the cw template "
    "(docs/experiments/redesign/design.md)"
)
# The redesign removes the acknowledgment lines from these skills.
REDESIGNED = {"agentic-cog-writer", *ROLES}


def _skill(name: str) -> str:
    return (EXPERIMENT_SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


def _a4() -> dict[str, str]:
    return _sections(A4_SKILL.read_text(encoding="utf-8"))


@SLICE_2
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
    assert loop_only[PERFORM] == single_context[PERFORM].replace(
        "step <role> <<'EOF'", "step <role> --no-goals <<'EOF'"
    )
    assert loop_only[REFERENCES] == no_goals[REFERENCES]
    reports_row = next(
        line
        for line in single_context[STATE].splitlines()
        if line.startswith("| `.writing/reports.md`")
    )
    assert reports_row in loop_only[STATE]
    assert (
        "Do not consult or construct a hierarchical goal network." in (loop_only[STATE])
    )
    assert "check --reports" in loop_only[FINISH]
    assert "log --no-goals" in loop_only[TRACE]
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


@SLICE_2
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
    description = sections[""].split("description:", 1)[1].split("\n", 1)[0]
    assert "writes exactly one paragraph in each Translating step" in description
    unit = sections[PARAGRAPH]
    for required in (
        "Each `Translating` step writes exactly one paragraph",
        "with no blank line inside it",
        "writing_state.py paragraph --append",
        "`--insert-before N`",
        "`--replace N`",
        "editing `.writing/draft.md` with `apply_patch`",
        "is forbidden",
        "an unbroken run of `Translating` steps counts as one role step",
    ):
        assert required in unit, required
    assert "document order" not in unit
    assert "words --max" not in text
    assert "repository writing" not in text
    assert "AI-pattern phrasing" not in text


def test_in_context_variants_write_reports_to_the_workspace() -> None:
    for name in (
        "cognitive-writing-single-context",
        "cognitive-writing-single-writer",
        "cognitive-writing-loop-only",
    ):
        text = _skill(name)
        assert "`.writing/reports.md`" in text
        assert "never as assistant messages" in text
        assert "A role step failed twice" not in text
        assert "When that file does not exist" not in text


def _skill_files() -> list[Path]:
    return sorted(path for root in SKILL_ROOTS for path in root.glob("*/SKILL.md"))


@pytest.mark.parametrize(
    "path",
    [p for p in _skill_files() if p.parent.name not in REDESIGNED],
    ids=lambda path: path.parent.name,
)
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


def test_redesigned_skills_have_no_acknowledgment_note() -> None:
    for name in REDESIGNED:
        root = "plugin/skills"
        text = (REPO_ROOT / root / name / "SKILL.md").read_text(encoding="utf-8")
        assert "I read" not in text and "[!NOTE]" not in text


def test_monitor_spawns_without_forked_context_and_waits_until_final() -> None:
    text = A4_SKILL.read_text(encoding="utf-8")
    code = text.split("```js\n", 1)[1].split("```", 1)[0]
    for required in (
        "fork_context: false",
        'message: "<the spawn line, verbatim>"',
        "timeout_ms: 300000",
        "while (r.timed_out)",
        "multi_agent_v1__close_agent({ target: agent_id })",
    ):
        assert required in code, required
    for forbidden in ("model", "reasoning_effort", "service_tier", "items"):
        assert forbidden not in code


@pytest.mark.parametrize("role", ROLES)
def test_role_skills_keep_a_separable_guidance_block(role: str) -> None:
    text = (REPO_ROOT / f"plugin/skills/{role}/SKILL.md").read_text(encoding="utf-8")
    guidance = text.split("\n## Guidance\n", 1)[1]
    assert "\n## " not in guidance
    for operational in ("cw", "brief", "Monitor", "goals.md", "requirements file"):
        assert operational not in guidance, operational
    policy = (REPO_ROOT / f"plugin/skills/{role}/agents/openai.yaml").read_text()
    assert "allow_implicit_invocation: false" in policy


@SLICE_2
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


RECIPE_BASELINES = (
    "writing-single-shot",
    "writing-linear",
    "writing-self-refine",
    "writing-storm-style",
    "writing-cogwriter-style",
    "writing-adaptive-task-planning",
)


@pytest.mark.parametrize("name", RECIPE_BASELINES)
def test_baselines_read_the_prompt_and_append_their_own_trace(name: str) -> None:
    text = (BASELINE_SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    assert "Read the Assignment, Supplied context, and Requested output" in text
    assert "Do not create `.writing/assignment.md`" in text
    assert "Read `.writing/assignment.md`" not in text
    assert "## Trace recipe" in text
    assert "json.dumps(event, ensure_ascii=False)" in text
    for removed in (
        "date -Is",
        "runner owns",
        "runner-designated",
        "runner's fixed",
        "Run condition A2",
        "a parallel runner change",
    ):
        assert removed not in text, removed


@pytest.mark.parametrize(
    "name", ("writing-cogwriter-style", "writing-adaptive-task-planning")
)
def test_delegating_baselines_spawn_without_forked_context(name: str) -> None:
    text = (BASELINE_SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    procedure = text.split("## Subagent procedure", 1)[1]
    for required in (
        "`multi_agent_v1__spawn_agent` with `fork_context: false`",
        "Keep at most five agents open at a time.",
        "`multi_agent_v1__close_agent`",
        "This is a single-turn task with no interactive user",
        "Do not search the web",
        "Output language:",
        "Length:",
        "Scope:",
    ):
        assert required in procedure, required


def test_storm_style_forbids_subagents_and_caps_are_concrete() -> None:
    storm = (BASELINE_SKILLS / "writing-storm-style/SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "may be separate subagents" not in storm
    assert "do not spawn subagents" in storm
    cogwriter = (BASELINE_SKILLS / "writing-cogwriter-style/SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "at most two revision attempts per segment" in cogwriter
    assert "within 10 percent of its target length" in cogwriter
    adaptive = (BASELINE_SKILLS / "writing-adaptive-task-planning/SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "at most three levels below the root" in adaptive
    assert "no more than 30 tasks" in adaptive


@pytest.mark.parametrize("name", RECIPE_BASELINES)
def test_baseline_recipes_validate_and_run_at_stage_start(name: str) -> None:
    text = (BASELINE_SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    recipe = text.split("## Trace recipe", 1)[1]
    assert "immediately when that" in recipe
    assert "never from a loop or script" in recipe
    assert "allowed = (" in recipe
    assert 'sys.exit("invalid trace event; nothing was appended")' in recipe
    procedure = text.split("## Procedure", 1)[1].split("## Trace recipe", 1)[0]
    final = procedure.index("final response")
    assert procedure.index("event") < final
    assert "with nothing before or after it" in text
