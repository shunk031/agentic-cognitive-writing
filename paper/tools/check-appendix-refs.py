#!/usr/bin/env python3
"""Guard main-text references to appendix details.

Main-text prose should keep the reading flow local: when details are deferred to
an appendix, use a reader-facing `See Appendix ... for ...` sentence and point
only to a top-level appendix section, never directly to an appendix subsection.
"""

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
APPENDIX_REF = re.compile(r"Appendix~\\ref\{([^}]+)\}")


def main() -> None:
    root = (PAPER / "acl_latex.tex").read_text(encoding="utf-8")
    try:
        appendix = root.split(r"\appendix", 1)[1]
    except IndexError as exc:
        raise AssertionError("acl_latex.tex must contain \\appendix") from exc

    top_level_labels = set(
        re.findall(
            r"\\section\*?\{[^}]+\}\s*\\label\{([^}]+)\}",
            appendix,
        )
    )
    assert top_level_labels, "no top-level appendix labels found"

    offenders: list[tuple[str, str, str]] = []
    for relative in MAIN_SECTIONS:
        path = PAPER / relative
        text = path.read_text(encoding="utf-8")

        for match in APPENDIX_REF.finditer(text):
            label = match.group(1)
            if label not in top_level_labels:
                offenders.append(
                    (
                        relative,
                        "non-parent appendix reference",
                        f"Appendix~\\ref{{{label}}}",
                    )
                )

        normalized = re.sub(r"\s+", " ", text)
        for sentence in re.split(r"(?<=\.)\s+", normalized):
            if APPENDIX_REF.search(sentence) and not re.search(
                r"\bSee Appendix~\\ref\{", sentence
            ):
                offenders.append(
                    (
                        relative,
                        "appendix detail reference must use 'See Appendix ... for ...'",
                        sentence[:240],
                    )
                )

    assert not offenders, offenders
    print(
        "Appendix reference guard: passed "
        f"({len(top_level_labels)} parent appendices)"
    )


if __name__ == "__main__":
    main()
