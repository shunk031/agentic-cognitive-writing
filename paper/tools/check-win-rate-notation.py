#!/usr/bin/env python3
"""Reject reader-facing win-rate formulas in manuscript TeX."""

from __future__ import annotations

import re
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]

PATTERNS = (
    re.compile(r"\bW\s*/\s*\(\s*W\s*\+\s*L\s*\)", re.IGNORECASE),
    re.compile(r"\\frac\s*\{\s*W\s*\}\s*\{\s*W\s*\+\s*L\s*\}", re.IGNORECASE),
)


def strip_comments(text: str) -> str:
    return re.sub(r"(?m)(?<!\\)%.*$", "", text)


def main() -> None:
    violations: list[tuple[Path, int, str]] = []

    for path in sorted(PAPER.rglob("*.tex")):
        if "build" in path.parts:
            continue
        text = strip_comments(path.read_text(encoding="utf-8"))
        for pattern in PATTERNS:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                violations.append((path.relative_to(PAPER.parent), line, match.group(0)))

    if violations:
        for path, line, token in violations:
            print(f"{path}:{line}: forbidden reader-facing win-rate formula: {token}")
        raise SystemExit(
            "Do not write W/(W+L)-style formulas in manuscript text. "
            "Describe the win-rate computation in plain language instead."
        )

    print("Win-rate notation guard: passed")


if __name__ == "__main__":
    main()
