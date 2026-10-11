#!/usr/bin/env python3
"""Fail when Figure 2 geometry drifts from the approved historical layout.

The canonical geometry is the last coherent pre-page-fit layout from commit
bd971d13e5aa6080da475f27cd1cb83392de2a94.  Keep the generated panel sizes and
the manuscript placement coupled so page-budget work cannot distort or detach
Figure 2 again.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIGURE_SOURCE = ROOT / "paper" / "scripts" / "make_figures.py"
RESULTS_SOURCE = ROOT / "paper" / "sec" / "05_results.tex"

EXPECTED_ASSIGNMENTS = {
    "ACL_TEXTWIDTH_IN": "16 / 2.54",
    "PROCESS_SEQUENCE_A_WIDTH_IN": "0.60 * ACL_TEXTWIDTH_IN",
    "PROCESS_SEQUENCE_A_HEIGHT_IN": "2.6",
    "PROCESS_SEQUENCE_MATRIX_WIDTH_IN": "0.37 * ACL_TEXTWIDTH_IN",
    "PROCESS_SEQUENCE_MATRIX_HEIGHT_IN": "1.13",
}


def fail(message: str) -> None:
    raise SystemExit(f"Figure 2 layout guard: {message}")


def check_generator_geometry() -> None:
    source = FIGURE_SOURCE.read_text(encoding="utf-8")
    for name, expected_rhs in EXPECTED_ASSIGNMENTS.items():
        matches = re.findall(rf"(?m)^{re.escape(name)}\s*=\s*(.+?)\s*$", source)
        if len(matches) != 1:
            fail(f"expected exactly one assignment to {name}; found {len(matches)}")
        if matches[0] != expected_rhs:
            fail(f"{name} must remain `{expected_rhs}`; found `{matches[0]}`")


def figure_block(source: str) -> str:
    label = r"\label{fig:process-sequences}"
    label_index = source.find(label)
    if label_index < 0:
        fail("could not find Figure 2 label")
    start = source.rfind(r"\begin{figure*}[t]", 0, label_index)
    end = source.find(r"\end{figure*}", label_index)
    if start < 0 or end < 0:
        fail("could not isolate Figure 2 environment")
    return source[start : end + len(r"\end{figure*}")]


def check_manuscript_geometry() -> None:
    block = figure_block(RESULTS_SOURCE.read_text(encoding="utf-8"))

    widths = re.findall(r"\\begin\{minipage\}\[c\]\{(0\.\d+)\\textwidth\}", block)
    if widths != ["0.60", "0.37"]:
        fail(f"Figure 2 minipage widths must remain 0.60/0.37; found {widths}")

    if block.count(r"\includegraphics[width=\linewidth]") != 3:
        fail("all three Figure 2 panels must remain placed at minipage linewidth")

    if r"\end{minipage}\hfill" not in block:
        fail("Figure 2 must retain the historical minipage + \\hfill placement")

    expected_gap = r"\small (b) \condAgenticCogWriter\\[0.5em]"
    if expected_gap not in block:
        fail("the (b)-(c) vertical gap must remain 0.5em")


def main() -> None:
    check_generator_geometry()
    check_manuscript_geometry()
    print(
        "Figure 2 layout guard: passed "
        "(generated 0.60x2.6 / 0.37x1.13; placement 0.60/0.37; b-c gap 0.5em)"
    )


if __name__ == "__main__":
    main()
