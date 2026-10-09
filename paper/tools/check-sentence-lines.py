#!/usr/bin/env python3
"""Check manuscript prose for more than one sentence on a source line.

The policy is intentionally source-oriented: ordinary prose in ``acl_latex.tex``
and ``sec/*.tex`` should place at most one sentence on each physical line.  TeX
structure may still split a sentence around display equations or other block
environments, so this checker does not require every non-empty line to be a
complete sentence.

The check is dependency-free and conservative.  It looks for sentence-ending
punctuation followed on the same source line by the start of another sentence,
while excluding common scholarly abbreviations.
"""

from __future__ import annotations

import re
from pathlib import Path


PAPER_DIR = Path(__file__).resolve().parents[1]
TARGETS = (PAPER_DIR / "acl_latex.tex", *sorted((PAPER_DIR / "sec").glob("*.tex")))

# A sentence may close braces/parentheses/quotes before the following whitespace.
BOUNDARY_RE = re.compile(
    r"(?P<left>[.!?])(?P<closers>[}\])'\"]*)[ \t]+(?P<next>[A-Z]|\\[A-Za-z@]+)"
)

# Period-final abbreviations that routinely occur before an uppercase token or a
# TeX command and therefore should not be treated as sentence boundaries.
ABBREVIATIONS = (
    "e.g.",
    "i.e.",
    "et al.",
    "Fig.",
    "Figs.",
    "Eq.",
    "Eqs.",
    "Sec.",
    "Secs.",
    "App.",
    "Dr.",
    "Prof.",
    "vs.",
)


def strip_comment(line: str) -> str:
    """Remove an unescaped TeX comment from *line*."""
    for index, char in enumerate(line):
        if char != "%":
            continue
        backslashes = 0
        cursor = index - 1
        while cursor >= 0 and line[cursor] == "\\":
            backslashes += 1
            cursor -= 1
        if backslashes % 2 == 0:
            return line[:index]
    return line


def is_abbreviation(prefix: str) -> bool:
    stripped = prefix.rstrip("}])'\"")
    if any(stripped.endswith(item) for item in ABBREVIATIONS):
        return True
    # Initials such as "A. Smith" are not sentence boundaries.
    return bool(re.search(r"(?:^|\s)[A-Z]\.$", stripped))


def violations(path: Path) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = strip_comment(raw_line).rstrip()
        if not line:
            continue
        for match in BOUNDARY_RE.finditer(line):
            if match.group("left") == "." and is_abbreviation(line[: match.start("next")]):
                continue
            found.append((line_number, raw_line.strip()))
            break
    return found


def main() -> int:
    all_violations: list[tuple[Path, int, str]] = []
    for path in TARGETS:
        for line_number, line in violations(path):
            all_violations.append((path, line_number, line))

    if not all_violations:
        print("One-sentence-per-line check passed.")
        return 0

    print("One-sentence-per-line check failed:")
    for path, line_number, line in all_violations:
        relative = path.relative_to(PAPER_DIR.parent)
        print(f"  {relative}:{line_number}: multiple sentences share one source line")
        print(f"    {line}")
    print("Put each prose sentence on its own physical source line.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
