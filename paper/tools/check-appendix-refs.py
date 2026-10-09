#!/usr/bin/env python3
"""Guard main-text references to appendix details.

Main-text prose should keep the reading flow local: when details are deferred to
an appendix, use a reader-facing `See Appendix ... for ...` sentence and point
only to a top-level appendix section, never directly to an appendix subsection.
The appendix may be split across input files; this guard follows those inputs
before collecting top-level section labels.
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
INPUT = re.compile(r"\\input\{([^}]+)\}")


def expand_inputs(text: str, seen: set[Path]) -> str:
    """Expand local TeX inputs so structural checks work across section files."""

    def replace(match: re.Match[str]) -> str:
        relative = Path(match.group(1))
        if not relative.suffix:
            relative = relative.with_suffix(".tex")
        path = (PAPER / relative).resolve()
        try:
            path.relative_to(PAPER.resolve())
        except ValueError:
            return match.group(0)
        if path in seen or not path.is_file():
            return match.group(0)
        seen.add(path)
        return expand_inputs(path.read_text(encoding="utf-8"), seen)

    return INPUT.sub(replace, text)


def main() -> None:
    root = (PAPER / "acl_latex.tex").read_text(encoding="utf-8")
    try:
        appendix_root = root.split(r"\appendix", 1)[1]
    except IndexError as exc:
        raise AssertionError("acl_latex.tex must contain \\appendix") from exc

    appendix = expand_inputs(appendix_root, set())
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
