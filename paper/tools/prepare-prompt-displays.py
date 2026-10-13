#!/usr/bin/env python3
"""Write the prompt copies that the appendix displays.

The appendix lists each generation and evaluation prompt from
build/prompt-display/<repository path>. The copies drop repository-internal
file paths and one development note: readers cannot open those paths, and the
note describes the runner rather than the prompt. The source prompt and skill
files stay unchanged because the experiments run them. Each removal must match
its source exactly once, so a prompt edit that moves or rewrites the removed
text fails the build instead of silently displaying it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
REPO = PAPER.parent
DISPLAY = "build/prompt-display/"
ENGINE_PATH = " in `experiments/src/agentic_cogwriter/judges/engine.py`"

REMOVALS = {
    "experiments/prompts/judges/pointwise-v1.md": (
        "Protocol source: docs/experiments/protocol.md, descriptive pointwise quality\n",
        ENGINE_PATH,
    ),
    "experiments/prompts/judges/pairwise-v1.md": (
        "Protocol source: docs/experiments/protocol.md, Balanced pairwise tournament\n",
        ENGINE_PATH,
    ),
}


def main() -> None:
    config = (PAPER / "sec/09_prompt_configuration.tex").read_text(encoding="utf-8")
    listed = re.findall(
        r"\\promptinput\{[^}]*\}\{.*\}\{" + re.escape(DISPLAY) + r"([^}]+)\}", config
    )
    unlisted = sorted(set(REMOVALS) - set(listed))
    if unlisted:
        sys.exit(
            f"prompt display: removals target prompts the appendix does not list: {unlisted}"
        )
    for relative in listed:
        text = (REPO / relative).read_text(encoding="utf-8")
        for target in REMOVALS.get(relative, ()):
            count = text.count(target)
            if count != 1:
                sys.exit(
                    f"prompt display: {relative} contains the removal target {count} times: {target!r}"
                )
            text = text.replace(target, "")
        output = PAPER / DISPLAY / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(f"prompt display: wrote {len(listed)} prompt copies under paper/{DISPLAY}")


if __name__ == "__main__":
    main()
