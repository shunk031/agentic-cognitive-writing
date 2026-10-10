#!/usr/bin/env python3
"""Require every main-text figure/table to be referenced from main prose.

Reader-facing reason: a float that remains in the main paper but loses its only
prose reference becomes an orphaned result or comparison. This can happen during
"navigation" cleanup even though LaTeX still builds successfully. The checker
expands the manuscript before ``\\appendix``, removes float bodies, and verifies
that every labeled main-text figure/table is referenced at least once from the
remaining main-text prose.
"""

from __future__ import annotations

import re
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
ENTRY = PAPER / "acl_latex.tex"

INPUT_RE = re.compile(r"\\(?:input|include)\{([^}]+)\}")
FLOAT_RE = re.compile(
    r"\\begin\{(?P<env>figure\*?|table\*?)\}(?P<body>.*?)\\end\{(?P=env)\}",
    re.DOTALL,
)
LABEL_RE = re.compile(r"\\label\{((?:fig|tab):[^}]+)\}")
REF_RE = re.compile(r"\\(?:ref|autoref|cref|Cref)\{([^}]+)\}")


def strip_comments(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        out: list[str] = []
        i = 0
        while i < len(line):
            if line[i] == "%":
                backslashes = 0
                j = i - 1
                while j >= 0 and line[j] == "\\":
                    backslashes += 1
                    j -= 1
                if backslashes % 2 == 0:
                    break
            out.append(line[i])
            i += 1
        lines.append("".join(out))
    return "\n".join(lines)


def resolve_input(token: str) -> Path:
    path = Path(token)
    if path.suffix == "":
        path = path.with_suffix(".tex")
    if path.is_absolute():
        return path
    # Manuscript inputs are resolved from paper/, which is also the build cwd.
    return PAPER / path


def expand_inputs(text: str, stack: tuple[Path, ...] = ()) -> str:
    def replace(match: re.Match[str]) -> str:
        path = resolve_input(match.group(1))
        if not path.exists():
            # Leave package/generated inputs that are irrelevant to float
            # references untouched rather than guessing another resolution rule.
            return match.group(0)
        resolved = path.resolve()
        if resolved in stack:
            cycle = " -> ".join(str(p) for p in (*stack, resolved))
            raise SystemExit(f"main-float reference guard: input cycle: {cycle}")
        content = strip_comments(path.read_text(encoding="utf-8"))
        return expand_inputs(content, (*stack, resolved))

    previous = None
    while previous != text:
        previous = text
        text = INPUT_RE.sub(replace, text)
    return text


def main() -> None:
    source = strip_comments(ENTRY.read_text(encoding="utf-8"))
    before_appendix = source.split(r"\appendix", 1)[0]
    expanded = expand_inputs(before_appendix, (ENTRY.resolve(),))

    floats = list(FLOAT_RE.finditer(expanded))
    labels: list[str] = []
    for match in floats:
        labels.extend(LABEL_RE.findall(match.group(0)))

    # A main-text float must be introduced or discussed by prose outside floats.
    # References that appear only inside captions or other float bodies do not
    # satisfy the reader-facing requirement.
    prose = FLOAT_RE.sub("", expanded)
    referenced: set[str] = set()
    for match in REF_RE.finditer(prose):
        referenced.update(
            label.strip()
            for label in match.group(1).split(",")
            if label.strip()
        )

    orphaned = [label for label in labels if label not in referenced]
    if orphaned:
        details = "\n".join(f"  - {label}" for label in orphaned)
        raise SystemExit(
            "main-float reference guard: every main-text figure/table must be "
            "referenced from main prose; orphaned labels:\n" + details
        )

    print(
        f"main-float reference guard: {len(labels)} labeled main-text "
        "figures/tables are referenced from main prose"
    )


if __name__ == "__main__":
    main()
