#!/usr/bin/env python3
"""Guard reader-facing Abstract decisions that have previously regressed."""

from __future__ import annotations

import re
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]


def main() -> None:
    source = (PAPER / "acl_latex.tex").read_text(encoding="utf-8")
    match = re.search(
        r"\\begin\{abstract\}\s*(.*?)\s*\\end\{abstract\}",
        source,
        flags=re.DOTALL,
    )
    assert match, "abstract environment not found"
    abstract = re.sub(r"\s+", " ", match.group(1)).strip()

    # Keep the Abstract in the order a new reader needs: contemporary agent
    # context -> writing-control problem -> proposal -> evaluation -> results ->
    # component/trace interpretation.
    proposal = re.search(r"\bwe propose Agentic CogWriter\b", abstract, re.IGNORECASE)
    assert proposal, (
        "Abstract must introduce the contribution as 'we propose Agentic CogWriter' "
        "after motivating the writing-control problem"
    )
    first_name = abstract.lower().find("agentic cogwriter")
    assert first_name == proposal.start() + proposal.group(0).lower().find("agentic cogwriter"), (
        "Do not introduce Agentic CogWriter before the proposal sentence"
    )
    problem = abstract.lower().find("writing process")
    assert 0 <= problem < proposal.start(), (
        "State the writing-process/control problem before proposing Agentic CogWriter"
    )
    assert re.search(r"\brecent coding agents\b", abstract, re.IGNORECASE), (
        "Open the Abstract from the contemporary coding-agent context"
    )
    assert not re.search(
        r"\bcoding agents\b[^.]*,\s+and\s+AI agents\b",
        abstract,
        re.IGNORECASE,
    ), "Do not coordinate coding agents with the broader category 'AI agents'"
    assert re.search(
        r"\bWe evaluate our Agentic CogWriter\b", abstract, re.IGNORECASE
    ), "Use 'We evaluate our Agentic CogWriter' in the Abstract"
    assert re.search(r"\bpointwise\b[^.]*\bpairwise\b", abstract, re.IGNORECASE), (
        "Name pointwise and pairwise evaluation together in the Abstract"
    )

    # Sampling details belong in Experimental Design / Limitations, not in the
    # headline contribution. Avoid wording that makes the Abstract undersell the
    # evidence or introduces opaque shorthand.
    for banned, rationale in (
        (r"\bsubsets?\b", "do not expose benchmark subset mechanics in the Abstract"),
        (r"\btwo\b", "do not summarize Abstract results as a selective two-benchmark tally"),
        (r"\bthe system\b", "name Agentic CogWriter instead of using an ambiguous 'the system'"),
        (r"\bAgentic CogWriter instead\b", "do not restore the abrupt proposal opening"),
        (r"\bunresolved\b", "frame ablations as narrowing explanations, not as an unresolved contribution"),
        (r"\bleaving (?:the )?source\b", "do not end the Abstract by saying the source of the gain is open"),
        (r"\bObserved writing trajectories\b", "explain trace evidence in reader-facing process terms"),
        (r"\bexploratory analysis suggests\b", "do not foreground a weak exploratory effect in the Abstract"),
    ):
        found = re.search(banned, abstract, re.IGNORECASE)
        assert not found, (rationale, found.group(0) if found else None)

    assert re.search(r"\bProcess traces\b", abstract, re.IGNORECASE), (
        "Introduce the trace result as process evidence, not as undefined 'trajectories'"
    )
    assert re.search(
        r"\bdepartures?\b[^.]*\bselectively\b",
        abstract,
        re.IGNORECASE,
    ), "Explain that adaptive departures are used selectively on the evaluated tasks"

    words = re.findall(r"\b[\w'-]+\b", abstract)
    assert len(words) <= 200, f"Abstract exceeds 200 words: {len(words)}"
    commands = re.findall(r"\\[A-Za-z]+", abstract)
    assert not commands, ("LaTeX command in Abstract", commands)

    print(
        "Abstract reader-flow guards passed: context -> problem -> proposal -> "
        f"evaluation -> results ({len(words)}/200 words)."
    )


if __name__ == "__main__":
    main()
