#!/usr/bin/env python3
"""Keep the W/(W+L) win-rate formula to its single definition in Experimental Design."""

import re
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
DEFINITION = Path("sec/04_experiments.tex")
FORMULA = re.compile(r"W\s*/\s*\(\s*W\s*\+\s*L\s*\)|\\frac\s*\{\s*W\s*\}\s*\{\s*W\s*\+\s*L\s*\}")


def main() -> None:
    hits = []
    for path in sorted(PAPER.rglob("*.tex")):
        if "build" in path.parts:
            continue
        text = re.sub(r"(?m)(?<!\\)%.*$", "", path.read_text(encoding="utf-8"))
        for match in FORMULA.finditer(text):
            hits.append((path.relative_to(PAPER), text.count("\n", 0, match.start()) + 1))
    if [path for path, _ in hits] != [DEFINITION]:
        for path, line in hits:
            print(f"paper/{path}:{line}: W/(W+L)")
        raise SystemExit(
            f"define the win rate as W/(W+L) exactly once, in paper/{DEFINITION}, "
            "and refer to it as the win rate elsewhere"
        )
    print("Win-rate notation guard: W/(W+L) appears once, in the Experimental Design definition.")


if __name__ == "__main__":
    main()
