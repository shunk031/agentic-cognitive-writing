#!/usr/bin/env python3
"""Keep one canonical win-rate definition and reject formula repetition elsewhere."""

from __future__ import annotations

import re
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
DEFINITION_PATH = PAPER / "sec/04_experiments.tex"
CANONICAL_DEFINITION = (
    "We report each system contrast as wins/losses/ties (W/L/T) for the first-named "
    "system and compute its win rate over non-tied order-consistent comparisons as "
    "$W/(W+L)$."
)

PATTERNS = (
    re.compile(r"\bW\s*/\s*\(\s*W\s*\+\s*L\s*\)", re.IGNORECASE),
    re.compile(r"\\frac\s*\{\s*W\s*\}\s*\{\s*W\s*\+\s*L\s*\}", re.IGNORECASE),
)


def strip_comments(text: str) -> str:
    return re.sub(r"(?m)(?<!\\)%.*$", "", text)


def main() -> None:
    definition_text = strip_comments(DEFINITION_PATH.read_text(encoding="utf-8"))
    definition_count = definition_text.count(CANONICAL_DEFINITION)
    if definition_count != 1:
        raise SystemExit(
            "The Pairwise evaluation section must contain exactly one canonical "
            "win-rate definition using W/(W+L)."
        )

    definition_start = definition_text.index(CANONICAL_DEFINITION)
    definition_end = definition_start + len(CANONICAL_DEFINITION)
    violations: list[tuple[Path, int, str]] = []

    for path in sorted(PAPER.rglob("*.tex")):
        if "build" in path.parts:
            continue
        text = strip_comments(path.read_text(encoding="utf-8"))
        for pattern in PATTERNS:
            for match in pattern.finditer(text):
                allowed = (
                    path == DEFINITION_PATH
                    and definition_start <= match.start() < definition_end
                )
                if allowed:
                    continue
                line = text.count("\n", 0, match.start()) + 1
                violations.append((path.relative_to(PAPER.parent), line, match.group(0)))

    if violations:
        for path, line, token in violations:
            print(f"{path}:{line}: repeated win-rate formula outside the definition: {token}")
        raise SystemExit(
            "Define W/(W+L) once in Experimental Design only. "
            "Do not repeat the formula in captions, tables, appendices, or other prose."
        )

    print("Win-rate notation guard: canonical definition present exactly once; no repetitions")


if __name__ == "__main__":
    main()
