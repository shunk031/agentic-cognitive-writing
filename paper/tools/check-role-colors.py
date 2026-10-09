#!/usr/bin/env python3
"""Guard the shared role-to-color mapping used by Figure 1 and Appendix prompts."""

from __future__ import annotations

import re
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]

EXPECTED_COLORS = {
    "DrawioGrayFill": "F5F5F5",
    "DrawioGrayStroke": "666666",
    "DrawioBlueFill": "DAE8FC",
    "DrawioBlueStroke": "6C8EBF",
    "DrawioGreenFill": "D5E8D4",
    "DrawioGreenStroke": "82B366",
    "DrawioPurpleFill": "E1D5E7",
    "DrawioPurpleStroke": "9673A6",
    "DrawioRedFill": "F8CECC",
    "DrawioRedStroke": "B85450",
    "DrawioOrangeFill": "FFE6CC",
    "DrawioOrangeStroke": "D79B00",
    "DrawioYellowFill": "FFF2CC",
    "DrawioYellowStroke": "D6B656",
}

ROLE_FAMILIES = {
    "PromptBaseline": "Gray",
    "PromptMonitor": "Blue",
    "PromptPlanner": "Green",
    "PromptTranslator": "Purple",
    "PromptReviewer": "Red",
    "PromptAblation": "Orange",
    "PromptEvaluator": "Yellow",
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
    for role, family in ROLE_FAMILIES.items():
        expected = {
            f"{role}Fill": f"Drawio{family}Fill",
            f"{role}Stroke": f"Drawio{family}Stroke",
            f"{role}Title": f"Drawio{family}Stroke!65!black",
        }
        for alias, target in expected.items():
            if colorlets.get(alias) != target:
                fail(f"{alias} must map to {target}, found {colorlets.get(alias)!r}")

    for snippet in (
        "colback=#1Fill,",
        "colframe=#1Stroke,",
        "colbacktitle=#1Title,",
    ):
        if snippet not in main:
            fail(f"promptbox must use shared role colors: missing {snippet}")


def check_figure(figure: str) -> None:
    required = (
        "input/.style={io, fill=DrawioGrayFill, draw=DrawioGrayStroke}",
        "output/.style={io, fill=DrawioGrayFill, draw=DrawioGrayStroke, double, double distance=0.6pt}",
        "mainagent/.style={agent, fill=PromptMonitorFill, draw=PromptMonitorStroke, line width=0.65pt}",
        "planner/.style={agent, fill=PromptPlannerFill, draw=PromptPlannerStroke}",
        "translator/.style={agent, fill=PromptTranslatorFill, draw=PromptTranslatorStroke}",
        "reviewer/.style={agent, fill=PromptReviewerFill, draw=PromptReviewerStroke}",
        "state/.style={box, rounded corners=1.5pt, dashed, fill=DrawioYellowFill, draw=DrawioYellowStroke, minimum width=0.82\\columnwidth}",
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
            fail(f"Figure 1 must not restore redundant process node labels: {redundant_process_label}")


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
    print("Figure 1 and Appendix role-color mapping guard: passed")


if __name__ == "__main__":
    main()
