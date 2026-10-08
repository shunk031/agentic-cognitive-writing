#!/usr/bin/env python3
"""Guard reader-facing Introduction choices that should not regress."""

from __future__ import annotations

import re
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]


def main() -> None:
    intro = (PAPER / "sec/01_introduction.tex").read_text(encoding="utf-8")

    assert "Recent coding agents" in intro, (
        "Introduce coding agents as a recent development in the Introduction"
    )
    for banned, rationale in (
        ("autonomous research agents", "do not narrow document-producing agent workflows to autonomous research agents"),
        ("others interleave structural reasoning", "do not use an unsupported catch-all 'others' category for one citation"),
        ("progress is usually defined", "describe what the next step denotes instead of introducing undefined 'progress'"),
        ("with a Monitor", "use lowercase 'monitor' for the generic Flower-Hayes construct"),
        ("Every system", "state the experimental control directly rather than referring to an undefined set of systems"),
        ("component analyses do not isolate a single source", "do not frame the Introduction around failure to isolate a mechanism"),
        ("Exploratory analysis suggests", "do not foreground a weak exploratory effect in the Introduction"),
        ("we compare this system", "refer to the contribution as 'our system'"),
    ):
        assert banned not in intro, (rationale, banned)

    # Uppercase Monitor is reserved for our named agent role. Generic cognitive
    # theory uses lowercase monitor.
    for match in re.finditer(r"\bMonitor\b", intro):
        tail = intro[match.end() : match.end() + 12]
        assert re.match(r"\s+agent\b", tail), (
            "Uppercase 'Monitor' in the Introduction must name our Monitor agent; "
            "use lowercase 'monitor' for the generic cognitive-theory construct",
            intro[max(0, match.start() - 30) : match.end() + 30],
        )
    assert "with a monitor deciding" in intro, (
        "Describe Flower and Hayes with a lowercase generic monitor"
    )

    # The proposal sentence should introduce and define the system in one pass,
    # rather than repeating the name in a second sentence.
    assert re.search(
        r"we propose \\condAgenticCogWriter,[^.]*a long-form writing system",
        intro,
    ), "Introduce Agentic CogWriter and its role in one proposal sentence"
    assert not re.search(
        r"we propose \\condAgenticCogWriter[^.]*\.\s+Agentic CogWriter is",
        intro,
    ), "Avoid repeating the system name immediately after the proposal sentence"

    # Cite multiple adaptive-structure systems rather than calling a single
    # paper 'others'. CogWriter and IS-CoT both adapt structure during writing.
    assert re.search(
        r"adapt plans or structural reasoning during generation~\\citep\{[^}]*wan2025cognitive[^}]*sun2026cot[^}]*\}",
        intro,
    ), "Support adaptive structural reasoning with both CogWriter and IS-CoT citations"

    # Present the two evaluation views symmetrically.
    assert "pointwise rubric scoring" in intro and "pairwise same-prompt preference evaluation" in intro, (
        "Name both pointwise and pairwise evaluation in the Introduction"
    )

    # The headline mechanism interpretation should be system-level and
    # reader-facing; statistical caveats remain in Results.
    assert "supporting a system-level interpretation of the gain" in intro, (
        "Frame the ablations as supporting a system-level interpretation"
    )
    assert "adaptive ordering is available but used selectively" in intro, (
        "Explain the process traces as selective use of adaptivity"
    )

    assert "we compare our system" in intro, (
        "Contribution list should say 'we compare our system'"
    )

    print("Introduction reader-flow and framing guards: passed")


if __name__ == "__main__":
    main()
