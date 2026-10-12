#!/usr/bin/env python3
"""Write appendix display copies of prompts with marked elisions.

The repository keeps each prompt exactly as the scored runs used it. Appendix A
shows a display copy in which passages that only address an interactive user or
local resources absent from the non-interactive, isolated runs are replaced by
"[...]". Every elided passage must occur exactly once, so a changed source fails
the build instead of silently showing the full or a wrong text.
"""

from __future__ import annotations

from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
ROOT = PAPER.parent
OUTPUT = PAPER / "build" / "prompt-display"
MARK = "[...]"
ELISIONS = {
    "plugin/skills/agentic-cog-writer/SKILL.md": (
        " and ask the user when a choice materially changes the rhetorical problem or a claim",
        " and tell the user about proposals that affect intent, factual claims, or a major goal. Let the user override any agent decision.",
        "If `.writing/assignment.md` is missing or underspecified, ask the user for:\n\n   - topic\n   - audience\n   - exigency\n   - writer's goals\n   - genre\n   - constraints",
        "6. Tell the user:\n\n   - what changed\n   - which goal is active\n   - what remains uncertain\n   - which process the `Monitor` recommends next\n\n   Ask for a decision when the next move depends on the user's intent or factual authority.",
    ),
    "experiments/plugin/skills/cognitive-writing-single-writer/SKILL.md": (
        "Follow the repository writing contract for structure, links, claims, and plain English. Apply the `unslop` skill before finishing. ",
    ),
}


def main() -> None:
    for relative, passages in ELISIONS.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        for passage in passages:
            count = text.count(passage)
            if count != 1:
                raise SystemExit(
                    f"{relative}: elided passage found {count} times: {passage[:60]!r}"
                )
            # Keep the surrounding spacing so the mark reads as part of the sentence.
            mark = (
                (" " if passage.startswith(" ") else "")
                + MARK
                + (" " if passage.endswith(" ") else "")
            )
            text = text.replace(passage, mark)
        target = OUTPUT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    print(
        f"Prompt display copies: {sum(len(p) for p in ELISIONS.values())} passages elided in {len(ELISIONS)} files"
    )


if __name__ == "__main__":
    main()
