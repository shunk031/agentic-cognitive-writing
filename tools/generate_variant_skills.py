#!/usr/bin/env python3
"""Generate the experiment variants of the Agentic CogWriter skills.

The ablation skills (no goal network, fixed order, single writer, single
context, and loop only) are the ``agentic-cog-writer`` skill with the sections
that carry the removed mechanism replaced, dropped, or added; every other
section is copied byte for byte. The A9 stage prompts are the A2 stage prompts
with a role section taken from the role skills by the removal rules below.

Run ``python3 tools/generate_variant_skills.py`` after editing the source
skills, and ``--check`` to fail when a committed file differs from the output.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
A4_DIR = ROOT / "plugin/skills/agentic-cog-writer"
ROLE_DIR = ROOT / "plugin/skills"
VARIANT_DIR = ROOT / "experiments/plugin/skills"
PROMPT_DIR = ROOT / "experiments/conditions/prompts"

TITLE = "# Agentic CogWriter"
SELECT = "## Select the next process"
STATE = "## State"
DELEGATE = "## Delegate the selected process"
BRIEF = "### Brief"
REPORTS = "## Role reports"
GOALS = "## Goals"
GOAL_EVENTS = "### Goal events"
LEDGER = "### Post-`Reviewing` ledger"
FINISH = "## Finish"
REFERENCES = "## References"
PARAGRAPH = "## Paragraph unit"

Sections = dict[str, str]


def split_sections(text: str) -> Sections:
    """Map each heading outside code fences to its text; the head is under ''."""

    sections: dict[str, list[str]] = {"": []}
    heading, fenced = "", False
    for line in text.splitlines(keepends=True):
        if line.startswith("```"):
            fenced = not fenced
        if not fenced and re.match(r"#{1,3} ", line):
            heading = line.rstrip("\n")
            sections[heading] = []
        sections[heading].append(line)
    return {key: "".join(lines) for key, lines in sections.items()}


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"generator: expected one occurrence of {old[:60]!r}")
    return text.replace(old, new)


def drop_lines(text: str, *needles: str) -> str:
    kept = [
        line
        for line in text.splitlines(keepends=True)
        if not any(needle in line for needle in needles)
    ]
    if len(kept) != len(text.splitlines()) - len(needles):
        raise SystemExit(f"generator: expected one line for each of {needles!r}")
    return "".join(kept)


# ---- section texts that replace A4's ---------------------------------------

NO_GOAL_SELECT = """## Select the next process

Before each step, read `.writing/assignment.md`, `.writing/draft.md`, the latest trace entries, and the latest role report. Select exactly one process, using the first row that matches:

| State | Next process |
| --- | --- |
| The stop rule holds | Stop |
| No `Planning` report exists yet, or a change request arrived after the latest role report | `Planning` |
| The latest report is from `Planning` | `Translating`, scoped to the parts of the plan without draft text |
| The latest report names a structural problem: a missing required section or a wrong organization | `Planning` |
| Part of the latest plan has no draft text yet, or the latest report names a problem localized to a passage | `Translating`, scoped to that part or passage |
| Any other state | `Reviewing` of the whole draft |

Because a `Planning` report always leads to `Translating`, `Planning` never runs twice in a row. A role's recommended next process is evidence for this choice; the `Monitor` alone selects the next process. Do not consult or construct a hierarchical goal network.

"""

FIXED_SELECT = """## Select the next process

Follow the fixed `Planning`, `Translating`, then `Reviewing` order: run the three processes in that order and repeat this cycle until the stop rule holds. Never change this order, even when a report recommends another process; a change request starts a new cycle with `Planning`. Before each step, read the writing state and the latest role report, and use them to scope the step: `Planning` addresses the open findings of the last `Reviewing` report, `Translating` writes what the plan or those findings require, and `Reviewing` covers the whole draft.

"""

NO_GOAL_FINISH = """## Finish

Before the final response:

1. Run `python3 <skill dir>/scripts/writing_state.py check`. The command verifies that the trace parses and prints the logged process path.
2. Compare the printed path with the role steps that ran. When the trace does not parse, report the problem in the last switch's `open_uncertainty`; never edit the trace by hand.
3. Log the last process switch described in Trace.
4. Read `.writing/draft.md` and return exactly its contents as the final response, with no preamble, summary, acknowledgment line, or code fence.

"""

NO_GOAL_REFERENCES = """## References

- [`references/trace-jsonl-schema.md`](references/trace-jsonl-schema.md) describes the trace fields for readers of the trace.
"""

IN_CONTEXT = """## Perform the selected process

Perform every selected process in your own context instead of delegating it. Do not call `spawn_agent`, do not run `codex` in the shell, and do not write a script that starts agents.

The first time a process is selected, read its role skill at `<project root>/.agents/skills/<role>/SKILL.md`, where `<role>` is `planning`, `translating`, or `reviewing`, and say the role skill's acknowledgment line in an assistant message of its own. When that file does not exist, read `skills/<role>/SKILL.md` in the `agentic-cognitive-writing` plugin. Each time the process runs:

1. Write the brief below in an assistant message.
2. Perform the role as its role skill and the brief describe, writing only the files that the process writes.
3. Write the role's report in an assistant message, in the role skill's report format without the acknowledgment line. Never repeat an acknowledgment line in a brief or a report.

"""

PARAGRAPH_UNIT = """## Paragraph unit

Each `Translating` step writes exactly one paragraph: one locally coherent block that serves one goal and has at most 120 words, counting each CJK character as one word. Scope each `Translating` step to that paragraph. Before writing the paragraph into `.writing/draft.md`, check its length with this command, which prints the count and fails above 120:

```sh
python3 <skill dir>/scripts/writing_state.py words --max 120 <<'EOF'
<the paragraph>
EOF
```

When the check fails, shorten the paragraph or keep only its first part, and check again.

"""


# ---- section transforms -----------------------------------------------------


def no_goal_state(text: str) -> str:
    text = drop_lines(text, "| `.writing/goals.md`")
    return replace_once(
        text,
        "The writing state lives in the project's `.writing/` directory.",
        "The writing state lives in the project's `.writing/` directory. Do not "
        "create or modify `.writing/goals.md`, whether it exists or not.",
    )


def no_goal_brief(text: str) -> str:
    text = drop_lines(text, "Active goals:")
    for old, new in (
        (
            "Goal-setting: <requested or not requested>",
            "Goal-setting: not requested. Do not create or modify .writing/goals.md.",
        ),
        ("<the goal IDs, sections, or passage", "<the sections or passage"),
        (
            (
                "<the work to do: the plan to follow, the findings to address, or the "
                "accepted replacement to apply>"
            ),
            "<the work to do: the plan to follow or the findings to address>",
        ),
        (
            "Request goal-setting in every `Planning` brief.",
            "Never request goal-setting.",
        ),
    ):
        text = replace_once(text, old, new)
    return text


def in_context_brief(text: str) -> str:
    text = drop_lines(
        text,
        "Follow the <role> skill",
        "This is a single-turn task",
        "Use only the assignment",
        "Your final message is your report",
    )
    for old, new in (
        (
            (
                "$<role> You are the <Role> role agent for a writing project. You are not "
                "the Monitor."
            ),
            "Process: <Role>",
        ),
        ("the agent may change", "this step may change"),
        (
            (
                "Write `<role>` in lowercase and `<Role>` capitalized: `planning` and "
                "`Planning`, `translating` and `Translating`, or `reviewing` and "
                "`Reviewing`."
            ),
            "Write `<Role>` as `Planning`, `Translating`, or `Reviewing`.",
        ),
    ):
        text = replace_once(text, old, new)
    return text


def no_goal_reports(text: str) -> str:
    return drop_lines(text, "`Goal changes`", "`Goal verdicts`")


def fixed_reports(text: str) -> str:
    text = text.replace("select the next process", "scope the next step in the cycle")
    if "select the next process" in text or "scope the next step" not in text:
        raise SystemExit("generator: role reports changed shape")
    if "`Goal verdicts`" in text:
        text = replace_once(
            text,
            "select `Planning` for `develop`; decide each",
            "address `develop` in the next `Planning` step; decide each",
        )
    return text


def fixed_goals(text: str) -> str:
    return replace_once(
        text,
        "After accepting one, the `Monitor` selects `Planning` and names the "
        "replacement in the brief's Request.",
        "After accepting one, the `Monitor` names the replacement in the next "
        "`Planning` brief's Request.",
    )


# ---- variant definitions ----------------------------------------------------

Change = str | Callable[[str], str] | None


def build(
    name: str,
    description: str,
    title: str,
    changes: dict[str, Change],
    *,
    insert_after: tuple[str, str] | None = None,
) -> str:
    """Apply section changes to A4; ``None`` drops a section."""

    base = split_sections((A4_DIR / "SKILL.md").read_text(encoding="utf-8"))
    unknown = set(changes) - set(base)
    if unknown:
        raise SystemExit(f"generator: unknown sections {sorted(unknown)}")
    parts = [
        (
            f"---\nname: {name}\ndescription: {description}\n---\n\n"
            f"> [!NOTE]\n> After reading this `SKILL.md`, say: `I read {name}.`\n\n"
        )
    ]
    for heading, body in base.items():
        if heading == "":
            continue
        if heading == TITLE:
            body = replace_once(body, TITLE, f"# {title}")
        change = changes.get(heading, body)
        if change is None:
            continue
        body = change(body) if callable(change) else change
        parts.append(body)
        if insert_after and heading == insert_after[0]:
            parts.append(insert_after[1])
    return "".join(parts).rstrip("\n") + "\n"


def _description(text: str) -> str:
    return (
        f'"Experiment variant of the agentic-cog-writer skill {text}. '
        'Use it only when a controlled comparison requests this variant."'
    )


NO_GOALS: dict[str, Change] = {
    SELECT: NO_GOAL_SELECT,
    STATE: no_goal_state,
    BRIEF: no_goal_brief,
    REPORTS: no_goal_reports,
    GOALS: None,
    GOAL_EVENTS: None,
    LEDGER: None,
    FINISH: NO_GOAL_FINISH,
    REFERENCES: NO_GOAL_REFERENCES,
}
IN_CONTEXT_CHANGES: dict[str, Change] = {DELEGATE: IN_CONTEXT, BRIEF: in_context_brief}
BOTH_REFERENCES = ("goals-format.md", "trace-jsonl-schema.md")

# skill name -> (description, title, changes, insert_after, references)
VARIANTS = {
    "cognitive-writing-no-goal-network": (
        _description("without the hierarchical goal network"),
        "Cognitive writing without a goal network",
        NO_GOALS,
        None,
        ("trace-jsonl-schema.md",),
    ),
    "cognitive-writing-fixed-order": (
        _description("with a fixed Planning, Translating, then Reviewing order"),
        "Fixed-order cognitive writing",
        {SELECT: FIXED_SELECT, REPORTS: fixed_reports, GOALS: fixed_goals},
        None,
        BOTH_REFERENCES,
    ),
    "cognitive-writing-single-context": (
        _description(
            "that performs each selected process in the Monitor's own context "
            "instead of delegating it"
        ),
        "Single-context cognitive writing",
        IN_CONTEXT_CHANGES,
        None,
        BOTH_REFERENCES,
    ),
    "cognitive-writing-single-writer": (
        _description(
            "that performs each selected process in the Monitor's own context "
            "and limits each Translating step to one paragraph"
        ),
        "Single-writer cognitive writing",
        IN_CONTEXT_CHANGES,
        (BRIEF, PARAGRAPH_UNIT),
        BOTH_REFERENCES,
    ),
    "cognitive-writing-loop-only": (
        _description(
            "without the goal network, with a fixed Planning, Translating, then "
            "Reviewing order, and with each process performed in the Monitor's "
            "own context"
        ),
        "Loop-only cognitive writing",
        {
            **NO_GOALS,
            SELECT: FIXED_SELECT,
            DELEGATE: IN_CONTEXT,
            BRIEF: lambda text: no_goal_brief(in_context_brief(text)),
            REPORTS: lambda text: fixed_reports(no_goal_reports(text)),
        },
        None,
        ("trace-jsonl-schema.md",),
    ),
}


# ---- A9 stage prompts -------------------------------------------------------


def _role_body(role: str) -> Sections:
    return split_sections((ROLE_DIR / role / "SKILL.md").read_text(encoding="utf-8"))


def _sub_processes(sections: Sections) -> str:
    return sections["## Sub-processes"].split("\n", 2)[2]


def _rhetorical_problem(sections: Sections) -> str:
    text = sections["## Read the state first"]
    start = text.index("Treat the assignment as the rhetorical problem")
    end = text.index("Where the assignment is silent")
    return text[start:end]


def planning_role() -> str:
    sections = _role_body("planning")
    sub = _sub_processes(sections)
    goal_setting = sub[sub.index("3. Goal-setting:") :]
    sub = sub.replace(
        goal_setting,
        "3. Goal-setting: create concrete sub-goals for the response. When the "
        "assignment sets a length, give each section a length target so that the "
        "targets add up to the requested length.\n\n",
    )
    return (
        "Turn the writing problem into grounded knowledge and useful organization.\n\n"
        + _rhetorical_problem(sections)
        + sub
        + "Do not invent facts, sources, quotations, or statistics.\n\n"
        "Return a concise plan with the proposed organization and why it fits the "
        "audience, the length target of each section, the generated knowledge "
        "separated by confidence, the sub-goals for the response, and unresolved "
        "uncertainty.\n"
    )


def translating_role() -> str:
    sections = _role_body("translating")
    read = sections["## Read the state first"]
    paragraph = read[read.index("Translate the selected ideas") :]
    for old, new in (
        ("Keep the scope's goals visible", "Keep the plan's sub-goals visible"),
        ("when it serves those goals", "when it serves those sub-goals"),
    ):
        paragraph = replace_once(paragraph, old, new)
    rules = sections["## Drafting rules"]
    kept = [
        line
        for line in rules.splitlines(keepends=True)
        if line.startswith("- ")
        and not any(
            skip in line
            for skip in (
                "output language that the brief",
                "brief's scope",
                "Do not write",
            )
        )
    ]
    rules = "".join(kept)
    for old, new in (
        (
            (
                "- Meet the length target that the goals or the plan set for each part "
                "of the scope, and the format constraints that apply to it."
            ),
            (
                "- Meet the length target that the plan sets for each part of the "
                "draft, and the format constraints that apply to it."
            ),
        ),
        (" Mark a gap in the report rather than filling it.", ""),
    ):
        rules = replace_once(rules, old, new)
    return "Turn selected meanings and plans into prose.\n\n" + paragraph + rules


def reviewing_role() -> str:
    sections = _role_body("reviewing")
    sub = _sub_processes(sections)
    revise = sub[sub.index("2. Revise:") :]
    sub = sub.replace(
        revise,
        "2. Revise: revise the draft to fix the problems that Evaluate finds.\n\n",
    )
    sub = replace_once(
        sub,
        "   - the active goals, when the brief lists them\n",
        "   - the plan's sub-goals\n",
    )
    return (
        "Evaluate the draft against the rhetorical problem, then revise it.\n\n"
        + sub
        + "Do not invent citations or claims.\n"
    )


A9_STAGES = {
    "a9_pre_write.md": ("a2_pre_write.md", "Planning", planning_role),
    "a9_write.md": ("a2_write.md", "Translating", translating_role),
    "a9_re_write.md": ("a2_re_write.md", "Reviewing", reviewing_role),
}


def a9_stage(a2_name: str, role: str, body: Callable[[], str]) -> str:
    a2 = (PROMPT_DIR / a2_name).read_text(encoding="utf-8")
    head, rest = a2.split("\n\n### Assignment", 1)
    head = head.replace("## A2 ", "## A9 ", 1)
    return f"{head}\n\n### {role} role\n\n{body().rstrip()}\n\n### Assignment{rest}"


# ---- output -----------------------------------------------------------------


def outputs() -> dict[Path, str]:
    files: dict[Path, str] = {}
    script = (A4_DIR / "scripts/writing_state.py").read_text(encoding="utf-8")
    for name, (
        description,
        title,
        changes,
        insert,
        references,
    ) in VARIANTS.items():
        directory = VARIANT_DIR / name
        files[directory / "SKILL.md"] = build(
            name, description, title, changes, insert_after=insert
        )
        files[directory / "scripts/writing_state.py"] = script
        for reference in references:
            files[directory / "references" / reference] = (
                A4_DIR / "references" / reference
            ).read_text(encoding="utf-8")
    for name, (a2_name, role, body) in A9_STAGES.items():
        files[PROMPT_DIR / name] = a9_stage(a2_name, role, body)
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail on any difference")
    args = parser.parse_args(argv)
    stale = []
    for path, text in outputs().items():
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current == text:
            continue
        stale.append(path.relative_to(ROOT).as_posix())
        if not args.check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            if path.suffix == ".py":
                path.chmod(0o755)
    verb = "differs from the generator output" if args.check else "written"
    for path in stale:
        print(f"{path}: {verb}")
    return 1 if args.check and stale else 0


if __name__ == "__main__":
    sys.exit(main())
