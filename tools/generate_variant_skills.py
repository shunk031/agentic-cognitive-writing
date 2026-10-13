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
STOP = "## Stop"
TRACE = "## Trace"
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
| The latest report is from `Planning` | `Translating`, scoped to the sections that report planned or reorganized |
| The latest report names a structural problem: a missing required section or a wrong organization | `Planning` |
| Part of the latest plan has no draft text yet, or the latest report names a problem localized to a passage | `Translating`, scoped to that part or passage |
| Any other state | `Reviewing` of the whole draft |

`Planning` runs twice in a row only when a change request arrives after its report; otherwise a `Planning` report leads to `Translating`. A role's recommended next process is evidence for this choice; the `Monitor` alone selects the next process.

"""

FIXED_SELECT = """## Select the next process

Follow the fixed `Planning`, `Translating`, then `Reviewing` order: run the three processes in that order and repeat this cycle until the stop rule holds. Never change this order, even when a report recommends another process; a change request starts a new cycle with `Planning`. Before each step, read the writing state and the latest role report, and use them to scope the step: `Planning` addresses the open findings of the last `Reviewing` report, `Translating` writes what the plan or those findings require, and `Reviewing` covers the whole draft.

"""

NO_GOAL_FINISH = """## Finish

Before the final response:

1. Run `python3 <skill dir>/scripts/writing_state.py check`. The command verifies that the trace parses, and prints the logged process path.
2. Log the last process switch described in Trace.
3. Read `.writing/draft.md` and return exactly its contents as the final response, with no preamble, summary, acknowledgment line, or code fence.

"""

NO_GOAL_REFERENCES = """## References

- [`references/trace-jsonl-schema.md`](references/trace-jsonl-schema.md) describes the trace fields for readers of the trace.
"""

NO_GOAL_TRACE_REFERENCE = """# Trace JSON Lines schema

The `Monitor` alone writes `.writing/trace/process.jsonl`, one JSON object per line, through the skill's `scripts/writing_state.py log --no-goals` command, which builds each line with a JSON encoder, validates it, and refuses goal events. The log is append-only, so a reader can reconstruct the process path and the evidence for each decision without the chat transcript.

## Fields

Every event is a process switch with these fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `timestamp` | string | ISO 8601 time with a UTC offset, written by the logging script at append time |
| `event_type` | string | `process_switch` |
| `responsible_agent` | string | `monitor` |
| `process` | string | The process entered, or the process left when the run stops |
| `decision` | string | The decision and its reason in plain language |
| `evidence` | array of strings | File paths, draft excerpts, or report fields that support the decision |
| `open_uncertainty` | array of strings | Questions or unsupported claims left open; empty when none remains |
| `from_process` | string or null | The previous switch's `to_process`; `null` for the first switch |
| `to_process` | string or null | `planning`, `translating`, or `reviewing`; `null` when the run stops |

## Reading the trace

The process path is the sequence of `to_process` values of the process switches, in line order.

## Example

```json
{"timestamp":"2026-01-15T09:00:00+09:00","event_type":"process_switch","responsible_agent":"monitor","process":"planning","from_process":null,"to_process":"planning","decision":"Plan the document from the assignment.","evidence":[".writing/assignment.md"],"open_uncertainty":[]}
{"timestamp":"2026-01-15T09:04:00+09:00","event_type":"process_switch","responsible_agent":"monitor","process":"translating","from_process":"planning","to_process":"translating","decision":"Draft the opening section, which has no draft text yet.","evidence":[".writing/draft.md has no opening section"],"open_uncertainty":[]}
```
"""

IN_CONTEXT = """## Perform the selected process

Perform every selected process in your own context instead of delegating it. Do not call `multi_agent_v1__spawn_agent`, do not run `codex` in the shell, and do not write a script that starts agents.

The first time a process is selected, read its role skill at `<project root>/.agents/skills/<role>/SKILL.md`, where `<role>` is `planning`, `translating`, or `reviewing`, and say the role skill's acknowledgment line immediately after reading it, in the same response as your next tool call. The role skill's instructions about its acknowledgment line and its final message address delegated role agents; here, the report goes to `.writing/reports.md`. Each time a process runs:

1. Log its switch and open its section in `.writing/reports.md` with this command, which takes the keys of a process switch except `event_type` and `to_process`:

   ```sh
   python3 <skill dir>/scripts/writing_state.py step <role> <<'EOF'
   decision: Draft the opening section, which has no draft text yet.
   evidence:
   - .writing/draft.md has no opening section
   EOF
   ```

2. Append the brief below to `.writing/reports.md` under that section.
3. Perform the role as its role skill and the brief describe, writing only the files that the process writes.
4. Append the role's report, in the role skill's report format but without the acknowledgment line, under the same section.

The `Monitor` alone writes `.writing/reports.md`. Write briefs and reports only to that file, never as assistant messages, and never put an acknowledgment line in it. Once `.writing/reports.md` exists, the `log` command refuses role switches, and Finish checks that every section has its switch.

"""

PARAGRAPH_MAX_WORDS: int | None = None
"""A7's paragraph cap in words; None means one paragraph with no numeric cap."""


def paragraph_unit(limit: int | None = PARAGRAPH_MAX_WORDS) -> str:
    length = (
        f" and at most {limit} words, counting each CJK character as one word"
        if limit is not None
        else ""
    )
    flag = f" --max {limit}" if limit is not None else ""
    return f"""## Paragraph unit

Each `Translating` step writes exactly one paragraph: one locally coherent block that serves one goal, with no blank line inside it{length}. Every write to `.writing/draft.md` goes through this command; editing `.writing/draft.md` with `apply_patch`, a shell redirect, or any other tool is forbidden. Use `--append` for a new paragraph at the end, `--insert-before N` for a new paragraph before paragraph N, or `--replace N` to rewrite paragraph N, counting paragraphs from 1:

```sh
python3 <skill dir>/scripts/writing_state.py paragraph --append{flag} <<'EOF'
<the paragraph>
EOF
```

The command refuses a second paragraph in the same `Translating` step, and a `Reviewing` step may use only `--replace` for its local revisions. After each paragraph, select the next process as usual; when the scope is not fully drafted yet, the next step is another `Translating` step on the same scope. For the twelve-step cap in the stop rule, an unbroken run of `Translating` steps counts as one role step; each of them still gets its own process switch.

"""


# ---- section transforms -----------------------------------------------------


def no_goal_state(text: str) -> str:
    text = drop_lines(text, "| `.writing/goals.md`")
    return replace_once(
        text,
        "The writing state lives in the project's `.writing/` directory.",
        "The writing state lives in the project's `.writing/` directory. Do not "
        "create or modify `.writing/goals.md`, whether it exists or not. Do not "
        "consult or construct a hierarchical goal network.",
    )


def no_goal_stop(text: str) -> str:
    return replace_once(
        text, ", the `Monitor` accepted none of its `regenerate` verdicts,", ""
    )


def in_context_stop(text: str) -> str:
    return drop_lines(text, "A role step failed twice")


REPORTS_ROW = (
    "| `.writing/reports.md` | the brief and the report of each role step, "
    "one `## Step N: Process` section per role switch | the `Monitor`, through "
    "`<skill dir>/scripts/writing_state.py step` |\n"
)


def in_context_state(text: str) -> str:
    lines = text.splitlines(keepends=True)
    trace_row = next(
        i for i, line in enumerate(lines) if line.startswith("| `.writing/trace/")
    )
    lines.insert(trace_row + 1, REPORTS_ROW)
    return "".join(lines)


def in_context_trace(text: str, *, goals: bool = True) -> str:
    text = replace_once(
        text,
        "Log every event with this one command, and with no other command.",
        "Log each role switch with the `step` command that Perform the selected "
        "process shows, and every other event, such as goal events and the last "
        "switch, with this command and no other.",
    )
    example = (
        "event_type: goal_created\ngoal_id: G1.3\nparent_goal_id: G1\n"
        "decision: Planning created G1.3 for the closing section.\n"
        if goals
        else "event_type: process_switch\nto_process: null\n"
        "decision: Stop after the fourth pass.\n"
    )
    return replace_once(
        text,
        "event_type: process_switch\nto_process: translating\n"
        "decision: Draft the opening section, which has no draft text yet.\n"
        "evidence:\n- .writing/draft.md has no opening section\n",
        example,
    )


def in_context_goal_events(text: str) -> str:
    return replace_once(
        text,
        "After closing the `Planning` agent, log",
        "After writing the `Planning` report, log",
    )


def in_context_finish(text: str) -> str:
    return replace_once(
        text,
        "writing_state.py check`. The command verifies that the trace parses,",
        "writing_state.py check --reports`. The command verifies that the trace "
        "parses and that `.writing/reports.md` has one step section per role "
        "switch,",
    )


def no_goal_steps(text: str) -> str:
    return replace_once(
        text,
        "writing_state.py step <role> <<'EOF'",
        "writing_state.py step <role> --no-goals <<'EOF'",
    )


def no_goal_trace(text: str) -> str:
    return replace_once(
        text, "writing_state.py log <<'EOF'", "writing_state.py log --no-goals <<'EOF'"
    )


def no_goal_brief(text: str) -> str:
    text = drop_lines(text, "Active goals:", "Rejected proposals:")
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
    STOP: no_goal_stop,
    TRACE: no_goal_trace,
    STATE: no_goal_state,
    BRIEF: no_goal_brief,
    REPORTS: no_goal_reports,
    GOALS: None,
    GOAL_EVENTS: None,
    LEDGER: None,
    FINISH: NO_GOAL_FINISH,
    REFERENCES: NO_GOAL_REFERENCES,
}
IN_CONTEXT_CHANGES: dict[str, Change] = {
    STOP: in_context_stop,
    STATE: in_context_state,
    DELEGATE: IN_CONTEXT,
    BRIEF: in_context_brief,
    TRACE: in_context_trace,
    GOAL_EVENTS: in_context_goal_events,
    FINISH: in_context_finish,
}
BOTH_REFERENCES = {
    "goals-format.md": None,
    "trace-jsonl-schema.md": None,
}
NO_GOAL_TRACE_ONLY = {"trace-jsonl-schema.md": NO_GOAL_TRACE_REFERENCE}

# skill name -> (description, title, changes, insert_after, references)
VARIANTS = {
    "cognitive-writing-no-goal-network": (
        _description("without the hierarchical goal network"),
        "Cognitive writing without a goal network",
        NO_GOALS,
        None,
        NO_GOAL_TRACE_ONLY,
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
            "and writes exactly one paragraph in each Translating step"
        ),
        "Single-writer cognitive writing",
        IN_CONTEXT_CHANGES,
        (BRIEF, paragraph_unit()),
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
            STOP: lambda text: in_context_stop(no_goal_stop(text)),
            STATE: lambda text: in_context_state(no_goal_state(text)),
            DELEGATE: no_goal_steps(IN_CONTEXT),
            TRACE: lambda text: in_context_trace(no_goal_trace(text), goals=False),
            FINISH: in_context_finish(NO_GOAL_FINISH),
            BRIEF: lambda text: no_goal_brief(in_context_brief(text)),
            REPORTS: lambda text: fixed_reports(no_goal_reports(text)),
        },
        None,
        NO_GOAL_TRACE_ONLY,
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
    # Pre-Write runs before any draft exists.
    sub = replace_once(sub, "   - the current draft\n", "")
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
        (
            (
                "Keep the scope's goals visible while drafting. Preserve a useful "
                "existing sentence when it serves those goals; do not let"
            ),
            "Keep the plan's sub-goals visible while drafting, and do not let",
        ),
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
    # Re-Write receives the draft but not the Pre-Write plan.
    sub = replace_once(sub, "   - the active goals, when the brief lists them\n", "")
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
        for reference, text in references.items():
            files[directory / "references" / reference] = text or (
                A4_DIR / "references" / reference
            ).read_text(encoding="utf-8")
    for name, (a2_name, role, body) in A9_STAGES.items():
        files[PROMPT_DIR / name] = a9_stage(a2_name, role, body)
    return files


def extra_files(files: dict[Path, str]) -> list[Path]:
    """Return files in a variant directory that the generator does not write."""

    return sorted(
        path
        for name in VARIANTS
        for path in (VARIANT_DIR / name).rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path not in files
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail on any difference")
    args = parser.parse_args(argv)
    stale = []
    files = outputs()
    extra = extra_files(files)
    for path, text in files.items():
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
    for path in extra:
        print(f"{path.relative_to(ROOT).as_posix()}: not written by the generator")
    return 1 if extra or (args.check and stale) else 0


if __name__ == "__main__":
    sys.exit(main())
