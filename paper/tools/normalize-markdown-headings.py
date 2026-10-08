#!/usr/bin/env python3
"""Normalize Pandoc-only inline formatting in Markdown headings.

Pandoc renders LaTeX small caps in GFM as HTML spans. PDF auxiliary heading
text contains only the visible title, so strip the span wrapper from heading
lines before structural parity checks. Body text is left untouched.
"""

from pathlib import Path
import re

PAPER = Path(__file__).resolve().parents[1]
MARKDOWN = PAPER / "build" / "acl_latex.md"
SMALLCAPS = re.compile(r'<span class="smallcaps">(.*?)</span>')


def main() -> None:
    text = MARKDOWN.read_text()
    lines = []
    for line in text.splitlines(keepends=True):
        if re.match(r"^#{1,6}\s", line):
            line = SMALLCAPS.sub(r"\1", line)
        lines.append(line)
    MARKDOWN.write_text("".join(lines))


if __name__ == "__main__":
    main()
