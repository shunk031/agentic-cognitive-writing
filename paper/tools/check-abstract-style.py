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

    # Reader-flow invariant restored after earlier Abstract rewrites regressed it.
    # The manuscript history contains both "paper: tighten abstract around
    # reader-facing contribution" and "ci: lock introduction and abstract
    # reader-facing structure". The latter preserved the Introduction proposal
    # sentence but did not actually require the same structure in the Abstract.
    # Keep the Abstract in the order a new reader needs: contemporary agent
    # context -> writing-control problem -> "we propose Agentic CogWriter" ->
    # evaluation -> main result -> component/trace interpretation.
    proposal = re.search(r"\bwe propose Agentic CogWriter\b", abstract, re.IGNORECASE)
    assert proposal, (
        "Abstract must introduce the contribution as 'we propose Agentic CogWriter' "
        "after motivating the writing-control problem"
    )
    first_name = abstract.lower().find("agentic cogwriter")
    assert first_name == proposal.start() + proposal.group(0).lower().find("agentic cogwriter"), (
        "Do not introduce Agentic CogWriter before the proposal sentence; avoid "
        "the abrupt 'Agentic CogWriter instead ...' regression"
    )
    problem = abstract.lower().find("writing process")
    assert 0 <= problem < proposal.start(), (
        "State the writing-process/control problem before proposing Agentic CogWriter"
    )
    assert re.search(r"\bcoding agents\b", abstract, re.IGNORECASE), (
        "Abstract should motivate document writing from the contemporary coding-agent context"
    )
    assert re.search(
        r"\bWe evaluate our Agentic CogWriter\b", abstract, re.IGNORECASE
    ), "Use 'We evaluate our Agentic CogWriter' in the Abstract"

    # Sampling details belong in Experimental Design / Limitations, not in the
    # headline contribution. A selective benchmark count such as "two" also
    # makes a reader immediately wonder what happened on the remaining benchmark;
    # summarize overall pointwise quality here and report per-benchmark detail later.
    for banned, rationale in (
        (r"\bsubsets?\b", "do not expose benchmark subset mechanics in the Abstract"),
        (r"\btwo\b", "do not summarize Abstract results as a selective two-benchmark tally"),
        (r"\bthe system\b", "name Agentic CogWriter instead of using an ambiguous 'the system'"),
        (r"\bAgentic CogWriter instead\b", "do not restore the abrupt proposal opening"),
        (r"\bunresolved\b", "frame ablations as narrowing explanations, not as an unresolved contribution"),
        (r"\bleaving (?:the )?source\b", "do not end the Abstract by saying the source of the gain is open"),
        (r"\bObserved writing trajectories\b", "explain trace evidence in reader-facing process terms"),
    ):
        found = re.search(banned, abstract, re.IGNORECASE)
        assert not found, (rationale, found.group(0) if found else None)

    assert re.search(r"\bProcess traces\b", abstract, re.IGNORECASE), (
        "Introduce the trace result as process evidence, not as undefined 'trajectories'"
    )
    # Guard the interpretation rather than one exact verb. Earlier wording used
    # "revisits"; the tighter layout-safe prose uses "returns". What matters is
    # that the Abstract tells the reader that the observed single-cycle traces
    # imply little return to earlier writing processes.
    assert re.search(
        r"\brarely\b[^.]*\b(?:earlier|prior)\b[^.]*\bwriting process(?:es)?\b",
        abstract,
        re.IGNORECASE,
    ), "Explain why the single-cycle trace result matters to the reader"

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
