#!/usr/bin/env python3
"""Guard the shared draw.io palette and semantic role-to-color mapping."""

from __future__ import annotations

import re
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]


def without_comments(text: str) -> str:
    return re.sub(r"(?m)(?<!\\)%.*$", "", text)


def compact(text: str) -> str:
    return re.sub(r"\s+", "", without_comments(text))


def require_literal(text: str, literal: str, message: str) -> None:
    if compact(literal) not in compact(text):
        raise SystemExit(f"color-semantics guard: {message}")


def require_regex(text: str, pattern: str, message: str) -> None:
    if re.search(pattern, without_comments(text), flags=re.DOTALL) is None:
        raise SystemExit(f"color-semantics guard: {message}")


def main() -> None:
    acl = (PAPER / "acl_latex.tex").read_text(encoding="utf-8")
    overview = (PAPER / "fig/tex/overview.tex").read_text(encoding="utf-8")
    prompts = (PAPER / "sec/09_prompt_configuration.tex").read_text(encoding="utf-8")

    palette = {
        "Gray": ("F5F5F5", "666666"),
        "Blue": ("DAE8FC", "6C8EBF"),
        "Green": ("D5E8D4", "82B366"),
        "Purple": ("E1D5E7", "9673A6"),
        "Red": ("F8CECC", "B85450"),
        "Orange": ("FFE6CC", "D79B00"),
        "Yellow": ("FFF2CC", "D6B656"),
    }
    for name, (fill, stroke) in palette.items():
        require_literal(
            acl,
            rf"\definecolor{{Drawio{name}Fill}}{{HTML}}{{{fill}}}",
            f"Drawio{name}Fill must remain #{fill}",
        )
        require_literal(
            acl,
            rf"\definecolor{{Drawio{name}Stroke}}{{HTML}}{{{stroke}}}",
            f"Drawio{name}Stroke must remain #{stroke}",
        )

    role_colors = {
        "Baseline": "Gray",
        "Monitor": "Blue",
        "Planner": "Green",
        "Translator": "Purple",
        "Reviewer": "Red",
        "Ablation": "Orange",
        "Evaluator": "Yellow",
    }
    for role, color in role_colors.items():
        require_literal(
            acl,
            rf"\colorlet{{Prompt{role}Fill}}{{Drawio{color}Fill}}",
            f"Prompt{role} fill must map to draw.io {color.lower()}",
        )
        require_literal(
            acl,
            rf"\colorlet{{Prompt{role}Stroke}}{{Drawio{color}Stroke}}",
            f"Prompt{role} stroke must map to draw.io {color.lower()}",
        )
        require_regex(
            acl,
            rf"\\colorlet\{{Prompt{role}Title\}}\{{Drawio{color}Stroke(?:![^}}]+)?\}}",
            f"Prompt{role} title must derive from the same draw.io {color.lower()} stroke",
        )

    for literal, message in [
        (r"colback=#1Fill", "prompt cards must use the semantic fill alias"),
        (r"colframe=#1Stroke", "prompt cards must use the semantic stroke alias"),
        (r"colbacktitle=#1Title", "prompt cards must use the semantic title alias"),
    ]:
        require_literal(acl, literal, message)

    figure_styles = [
        (
            r"input/.style={io, fill=DrawioGrayFill, draw=DrawioGrayStroke}",
            "Figure 1 input must remain neutral draw.io gray",
        ),
        (
            r"output/.style={io, fill=DrawioGrayFill, draw=DrawioGrayStroke, double, double distance=0.6pt}",
            "Figure 1 output must remain neutral draw.io gray",
        ),
        (
            r"mainagent/.style={agent, fill=PromptMonitorFill, draw=PromptMonitorStroke, line width=0.65pt}",
            "Figure 1 Monitor must use the Monitor semantic color",
        ),
        (
            r"planner/.style={agent, fill=PromptPlannerFill, draw=PromptPlannerStroke}",
            "Figure 1 Planner must use the Planner semantic color",
        ),
        (
            r"translator/.style={agent, fill=PromptTranslatorFill, draw=PromptTranslatorStroke}",
            "Figure 1 Translator must use the Translator semantic color",
        ),
        (
            r"reviewer/.style={agent, fill=PromptReviewerFill, draw=PromptReviewerStroke}",
            "Figure 1 Reviewer must use the Reviewer semantic color",
        ),
        (
            r"state/.style={box, rounded corners=1.5pt, dashed, fill=DrawioYellowFill, draw=DrawioYellowStroke, minimum width=0.82\columnwidth}",
            "Figure 1 persistent state must remain draw.io yellow",
        ),
    ]
    for literal, message in figure_styles:
        require_literal(overview, literal, message)

    figure_nodes = {
        "monitor": ("mainagent", "Monitor"),
        "planner": ("planner", "Planner"),
        "translator": ("translator", "Translator"),
        "reviewer": ("reviewer", "Reviewer"),
    }
    for node_id, (style, label) in figure_nodes.items():
        require_regex(
            overview,
            rf"\\node\[[^\]]*\b{style}\b[^\]]*\]\s*\({node_id}\)\s*\{{\\textbf\{{{label}\}}",
            f"Figure 1 {label} node must use the {style} style",
        )

    prompt_expectations = [
        (r"\promptinput{PromptBaseline}{\condSinglePass}", "Single-pass prompt must use baseline gray"),
        (r"\promptinput{PromptBaseline}{\condStaged: Pre-Write}", "Staged prompts must use baseline gray"),
        (r"\promptinput{PromptBaseline}{\condTaskPlanning}", "Task-planning prompt must use baseline gray"),
        (r"\promptinput{PromptMonitor}{Top-level Agent Skill}", "top-level Monitor prompt must use Monitor blue"),
        (r"\promptinput{PromptPlanner}{\texttt{Planner} Subagent Wrapper}", "Planner wrapper must use Planner green"),
        (r"\promptinput{PromptPlanner}{\texttt{Planner} Role Skill}", "Planner role skill must use Planner green"),
        (r"\promptinput{PromptTranslator}{\texttt{Translator} Subagent Wrapper}", "Translator wrapper must use Translator purple"),
        (r"\promptinput{PromptTranslator}{\texttt{Translator} Role Skill}", "Translator role skill must use Translator purple"),
        (r"\promptinput{PromptReviewer}{\texttt{Reviewer} Subagent Wrapper}", "Reviewer wrapper must use Reviewer red"),
        (r"\promptinput{PromptReviewer}{\texttt{Reviewer} Role Skill}", "Reviewer role skill must use Reviewer red"),
        (r"\promptinput{PromptAblation}{\condNoGoals}", "ablation prompts must use orange"),
        (r"\promptinput{PromptAblation}{\condFixedOrder}", "ablation prompts must use orange"),
        (r"\promptinput{PromptAblation}{\condSingleWriter}", "ablation prompts must use orange"),
        (r"\promptinput{PromptAblation}{\condSingleContext}", "ablation prompts must use orange"),
        (r"\promptinput{PromptEvaluator}{Common Pointwise Rubric}", "evaluator prompts must use yellow"),
        (r"\promptinput{PromptEvaluator}{Pairwise Comparison}", "evaluator prompts must use yellow"),
        (r"\promptinput{PromptEvaluator}{WritingBench-Native Evaluation}", "evaluator prompts must use yellow"),
        (r"\promptinput{PromptEvaluator}{HelloBench-Native Evaluation}", "evaluator prompts must use yellow"),
    ]
    for literal, message in prompt_expectations:
        require_literal(prompts, literal, message)

    print("Draw.io palette and semantic role-color guards: passed")


if __name__ == "__main__":
    main()
