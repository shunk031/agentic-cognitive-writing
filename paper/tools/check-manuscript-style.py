#!/usr/bin/env python3
"""Guard manuscript-wide display-name and pairwise-evaluation terminology."""

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


def main() -> None:
    check_display_name()
    check_pairwise_language()
    print("Manuscript display-name and pairwise-language guards: passed")


if __name__ == "__main__":
    main()
