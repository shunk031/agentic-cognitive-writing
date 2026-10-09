#!/usr/bin/env python3
"""Guard the shared editorial palette and semantic role-to-color mapping."""

from __future__ import annotations

import re
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]

EXPECTED_COLORS = {
    "EditorialGray": "666666",
    "EditorialIndigo": "332288",
    "EditorialTeal": "44AA99",
    "EditorialPurple": "AA4499",
    "EditorialRose": "CC6677",
    "EditorialOlive": "999933",
    "EditorialCyan": "88CCEE",
    "EditorialSand": "DDCC77",
}

EXPECTED_ALIASES = {
    "PromptBaselineStroke": "EditorialGray",
    "PromptBaselineFill": "EditorialGray!7!white",
    "PromptBaselineTitle": "EditorialGray!65!black",
    "PromptMonitorStroke": "EditorialIndigo",
    "PromptMonitorFill": "EditorialIndigo!16!white",
    "PromptMonitorTitle": "EditorialIndigo!65!black",
    "PromptPlannerStroke": "EditorialTeal",
    "PromptPlannerFill": "EditorialTeal!16!white",
    "PromptPlannerTitle": "EditorialTeal!65!black",
    "PromptTranslatorStroke": "EditorialPurple",
    "PromptTranslatorFill": "EditorialPurple!16!white",
    "PromptTranslatorTitle": "EditorialPurple!65!black",
    "PromptReviewerStroke": "EditorialRose",
    "PromptReviewerFill": "EditorialRose!16!white",
    "PromptReviewerTitle": "EditorialRose!65!black",
    "PromptAblationStroke": "EditorialOlive",
    "PromptAblationFill": "EditorialOlive!16!white",
    "PromptAblationTitle": "EditorialOlive!65!black",
    "PromptEvaluatorStroke": "EditorialCyan",
    "PromptEvaluatorFill": "EditorialCyan!16!white",
    "PromptEvaluatorTitle": "EditorialCyan!55!black",
    "WritingStateStroke": "EditorialSand!68!black",
    "WritingStateFill": "EditorialSand!24!white",
    "EndpointStroke": "EditorialGray",
    "EndpointFill": "EditorialGray!7!white",
}

EXPECTED_PROMPTS = {
    "../experiments/conditions/prompts/a1_single_shot.md": "PromptBaseline",
    "../experiments/conditions/prompts/a2_pre_write.md": "PromptBaseline",
    "../experiments/conditions/prompts/a2_write.md": "PromptBaseline",
    "../experiments/conditions/prompts/a2_re_write.md": "PromptBaseline",
    "../experiments/baselines/skills/writing-adaptive-task-planning/SKILL.md": "PromptBaseline",
    "../plugin/skills/agentic-cog-writer/SKILL.md": "PromptMonitor",
    "../plugin/agents/planner.md": "PromptPlanner",
    "../plugin/skills/planning/SKILL.md": "PromptPlanner",
    "../plugin/agents/translator.md": "PromptTranslator",
    "../plugin/skills/translating/SKILL.md": "PromptTranslator",
    "../plugin/agents/reviewer.md": "PromptReviewer",
    "../plugin/skills/reviewing/SKILL.md": "PromptReviewer",
    "../experiments/plugin/skills/cognitive-writing-no-goal-network/SKILL.md": "PromptAblation",
    "../experiments/plugin/skills/cognitive-writing-fixed-order/SKILL.md": "PromptAblation",
    "../experiments/plugin/skills/cognitive-writing-single-writer/SKILL.md": "PromptAblation",
    "../experiments/plugin/skills/cognitive-writing-single-context/SKILL.md": "PromptAblation",
    "../experiments/prompts/judges/pointwise-v1.md": "PromptEvaluator",
    "../experiments/prompts/judges/pairwise-v1.md": "PromptEvaluator",
    "../experiments/prompts/judges/writingbench-native-v1.md": "PromptEvaluator",
    "../experiments/prompts/judges/hellobench-native-v1.md": "PromptEvaluator",
}


def fail(message: str) -> None:
    raise SystemExit(f"role-color guard: {message}")


def check_palette(main: str) -> None:
    defined = dict(
        re.findall(r"\\definecolor\{([^}]+)\}\{HTML\}\{([0-9A-Fa-f]{6})\}", main)
    )
    for name, value in EXPECTED_COLORS.items():
        if defined.get(name, "").upper() != value:
            fail(f"{name} must remain #{value}, found {defined.get(name)!r}")

    colorlets = dict(re.findall(r"\\colorlet\{([^}]+)\}\{([^}]+)\}", main))
    for alias, target in EXPECTED_ALIASES.items():
        if colorlets.get(alias) != target:
            fail(f"{alias} must map to {target}, found {colorlets.get(alias)!r}")

    for snippet in (
        "colback=#1Fill,",
        "colframe=#1Stroke,",
        "colbacktitle=#1Title,",
    ):
        if snippet not in main:
            fail(f"promptbox must use semantic role colors: missing {snippet}")


def check_figure(figure: str) -> None:
    required = (
        "input/.style={io, fill=EndpointFill, draw=EndpointStroke}",
        "output/.style={io, fill=EndpointFill, draw=EndpointStroke, double, double distance=0.6pt}",
        "mainagent/.style={agent, fill=PromptMonitorFill, draw=PromptMonitorStroke, line width=0.65pt}",
        "planner/.style={agent, fill=PromptPlannerFill, draw=PromptPlannerStroke}",
        "translator/.style={agent, fill=PromptTranslatorFill, draw=PromptTranslatorStroke}",
        "reviewer/.style={agent, fill=PromptReviewerFill, draw=PromptReviewerStroke}",
        "state/.style={box, rounded corners=1.5pt, dashed, fill=WritingStateFill, draw=WritingStateStroke, minimum width=0.82\\columnwidth}",
        "\\node[translator, below=7mm of monitor] (translator) {\\textbf{Translator}};",
        "\\node[planner, left=2.5mm of translator] (planner) {\\textbf{Planner}};",
        "\\node[reviewer, right=2.5mm of translator] (reviewer) {\\textbf{Reviewer}};",
    )
    for snippet in required:
        if snippet not in figure:
            fail(f"Figure 1 role/color contract changed: missing {snippet}")

    for redundant_process_label in (
        r"\texttt{Planning}",
        r"\texttt{Translating}",
        r"\texttt{Reviewing}",
    ):
        if redundant_process_label in figure:
            fail(
                "Figure 1 must not restore redundant process node labels: "
                + redundant_process_label
            )


def check_prompt_assignments(prompts: str) -> None:
    found: dict[str, str] = {}
    pattern = re.compile(r"\\promptinput\{([^}]+)\}\{.*\}\{([^}]+)\}")
    for line in prompts.splitlines():
        match = pattern.fullmatch(line.strip())
        if not match:
            continue
        role, path = match.groups()
        if path in found:
            fail(f"duplicate prompt entry for {path}")
        found[path] = role

    missing = sorted(set(EXPECTED_PROMPTS) - set(found))
    extra = sorted(set(found) - set(EXPECTED_PROMPTS))
    if missing or extra:
        fail(f"prompt inventory changed; missing={missing}, extra={extra}")

    for path, expected_role in EXPECTED_PROMPTS.items():
        if found[path] != expected_role:
            fail(f"{path} must use {expected_role}, found {found[path]}")


def main() -> None:
    main_tex = (PAPER / "acl_latex.tex").read_text(encoding="utf-8")
    figure = (PAPER / "fig/tex/overview.tex").read_text(encoding="utf-8")
    prompts = (PAPER / "sec/09_prompt_configuration.tex").read_text(encoding="utf-8")

    check_palette(main_tex)
    check_figure(figure)
    check_prompt_assignments(prompts)
    print("Editorial palette and semantic role-color mapping guard: passed")


if __name__ == "__main__":
    main()
