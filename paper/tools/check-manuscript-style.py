#!/usr/bin/env python3
"""Guard manuscript-wide display-name, evaluation, and run-scope terminology."""

from __future__ import annotations

import re
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
MAIN_SECTIONS = [
    "sec/01_introduction.tex",
    "sec/02_related_work.tex",
    "sec/03_method.tex",
    "sec/04_experiments.tex",
    "sec/05_results.tex",
    "sec/06_discussion.tex",
    "sec/07_limitations.tex",
    "sec/08_conclusion.tex",
]


def without_comments(text: str) -> str:
    return re.sub(r"(?m)(?<!\\)%.*$", "", text)


def check_display_name() -> None:
    offenders: list[str] = []
    for path in sorted(PAPER.rglob("*.tex")):
        if path.name == "numbers.tex" or "build" in path.parts:
            continue
        text = without_comments(path.read_text(encoding="utf-8"))
        # The macro definition may contain the literal name because it is
        # explicitly wrapped in \textsc{...}. All reader-facing uses should
        # go through \condAgenticCogWriter or an equally explicit textsc form.
        text = text.replace(r"\textsc{Agentic CogWriter}", "")
        if re.search(r"\bAgentic CogWriter\b", text):
            offenders.append(str(path.relative_to(PAPER)))
    assert not offenders, (
        "render Agentic CogWriter in small caps via \\condAgenticCogWriter; "
        "raw reader-facing occurrences found in",
        offenders,
    )


def check_display_name_repetition() -> None:
    """Keep the display name as an anchor, not a repeated paragraph subject."""
    offenders: list[str] = []
    for path in sorted((PAPER / "sec").glob("*.tex")):
        text = without_comments(path.read_text(encoding="utf-8"))
        paragraphs = re.split(r"\n[ \t]*\n+", text)
        for index, paragraph in enumerate(paragraphs, start=1):
            # Figure and table source can legitimately repeat condition labels in
            # panel names, captions, and legends; this guard targets prose.
            if r"\begin{figure" in paragraph or r"\begin{table" in paragraph:
                continue
            count = paragraph.count(r"\condAgenticCogWriter")
            if count > 1:
                offenders.append(f"{path.relative_to(PAPER)} paragraph {index}: {count} mentions")
    assert not offenders, (
        "use Agentic CogWriter at most once per prose paragraph; after the name anchors the referent, "
        "prefer 'our system', 'the full system' when contrasting ablations, or restructure the sentence",
        offenders,
    )


def check_pairwise_language() -> None:
    main = "\n".join(
        without_comments((PAPER / path).read_text(encoding="utf-8"))
        for path in MAIN_SECTIONS
    )
    for pattern in (r"\bagreed winner\b", r"\bagree(?:s|d)? on a winner\b"):
        match = re.search(pattern, main, flags=re.IGNORECASE)
        assert not match, (
            "describe the two-order filter as order-consistent comparisons rather than an agreed winner",
            match.group(0) if match else None,
        )

    experiments = without_comments((PAPER / "sec/04_experiments.tex").read_text(encoding="utf-8"))
    assert re.search(
        r"both orders select the same semantic response",
        experiments,
        flags=re.IGNORECASE,
    ), "pairwise evaluation must explain the two-order consistency rule"
    assert re.search(
        r"order-consistent comparisons",
        experiments,
        flags=re.IGNORECASE,
    ), "pairwise evaluation must name the filtered comparisons plainly"


def check_core_three_run_scope() -> None:
    """Prevent legacy run-1 appendix summaries from surviving a three-run study."""
    # The pre-specified study regenerates the same prompt set three times. If an
    # older run-1 resource or length table survives after all three runs are
    # available, a reviewer can reasonably read that as selective reporting or
    # incomplete propagation. Separately identified one-run exploratory checks
    # remain allowed; this guard targets only the core-study appendix artifacts.
    core_paths = (
        "sec/10_appendix.tex",
        "tab/appendix-process.tex",
        "tab/appendix-length-control.tex",
    )
    for relative in core_paths:
        text = without_comments((PAPER / relative).read_text(encoding="utf-8"))
        for stale in ("first generation run", "generation run 1 of 3"):
            assert stale not in text, (
                "core three-run appendix evidence must not silently fall back to run 1",
                relative,
                stale,
            )

    process = without_comments((PAPER / "tab/appendix-process.tex").read_text(encoding="utf-8"))
    assert any(
        phrase in process
        for phrase in ("across the three generation runs", "across all three generation runs")
    ), "the core process/resource table must state its three-run scope"
    for suffix in (
        "MedianOutputMean",
        "SpawnsMean",
        "OutputTokensMean",
        "InputTokensMean",
        "MeanSecondsMean",
    ):
        assert suffix in process, (
            "the core process/resource table must use three-run summary macros",
            suffix,
        )

    length = without_comments((PAPER / "tab/appendix-length-control.tex").read_text(encoding="utf-8"))
    for run in ("RunOne", "RunTwo", "RunThree"):
        assert run in length, (
            "the core output-length sensitivity table must expose every generation run",
            run,
        )
    assert r"\LengthRatio" not in length, (
        "run-1-only length-ratio macros must not be used in the core three-run sensitivity table"
    )


def main() -> None:
    check_display_name()
    check_display_name_repetition()
    check_pairwise_language()
    check_core_three_run_scope()
    print("Manuscript display-name, repetition, pairwise-language, and run-scope guards: passed")


if __name__ == "__main__":
    main()
