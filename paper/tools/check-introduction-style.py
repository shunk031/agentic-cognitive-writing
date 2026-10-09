#!/usr/bin/env python3
"""Guard reader-facing Introduction choices that should not regress."""

from __future__ import annotations

import re
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]


def main() -> None:
    intro = (PAPER / "sec/01_introduction.tex").read_text(encoding="utf-8")
    lowered = intro.lower()

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
        (r"our \condAgenticCogWriter", "after the proposal introduces the name, refer to the contribution as 'our system'"),
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

    # Introduce and define the proposal in one sentence without freezing its
    # exact wording.
    proposal_sentence = next(
        (sentence for sentence in re.split(r"(?<=\.)\s+", intro) if r"we propose \condAgenticCogWriter" in sentence),
        "",
    )
    assert proposal_sentence and "a long-form writing system" in proposal_sentence, (
        "Introduce Agentic CogWriter and identify it as a long-form writing system in the proposal sentence"
    )
    assert "Agentic CogWriter is a long-form writing system" not in intro, (
        "Avoid immediately repeating the system name in a second definition sentence"
    )

    # Cite multiple adaptive-structure systems rather than calling a single
    # paper 'others'. CogWriter and IS-CoT both adapt structure during writing.
    adaptive = re.search(
        r"adapt plans or structural reasoning during generation~\\citep\{([^}]+)\}",
        intro,
    )
    assert adaptive, "Name adaptive plans or structural reasoning explicitly"
    adaptive_keys = {key.strip() for key in adaptive.group(1).split(",")}
    assert {"wan2025cognitive", "sun2026cot"} <= adaptive_keys, (
        "Support adaptive structural reasoning with both CogWriter and IS-CoT citations",
        adaptive_keys,
    )

    # Present the two evaluation views symmetrically without freezing sentence case.
    assert "pointwise rubric scoring" in lowered and "pairwise same-prompt preference evaluation" in lowered, (
        "Name both pointwise and pairwise evaluation in the Introduction"
    )
    assert "we evaluate our system" in lowered, (
        "After introducing Agentic CogWriter, refer to the evaluated contribution as 'our system'"
    )

    # Keep the headline mechanism interpretation reader-facing while leaving
    # detailed statistical qualification to Results.
    assert "system-level interpretation" in lowered, (
        "Frame the ablations at the system level rather than as a failed mechanism search"
    )
    assert re.search(r"adaptive ordering[^.]*used selectively", intro, re.IGNORECASE), (
        "Explain that adaptive ordering is available but used selectively"
    )

    assert "we compare our system" in lowered, (
        "Contribution list should say 'we compare our system'"
    )

    print("Introduction reader-flow and framing guards: passed")


if __name__ == "__main__":
    main()
