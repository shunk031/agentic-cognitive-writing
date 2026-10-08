#!/usr/bin/env python3
"""Normalize small-caps markup used in manuscript headings.

Pandoc renders LaTeX small caps in GFM as HTML spans, while LaTeX preserves
``\textsc{...}`` markup in auxiliary heading records. Structural parity checks
compare visible heading text, so normalize only those heading representations;
body text and manuscript source are left untouched.
"""

from pathlib import Path
import re

PAPER = Path(__file__).resolve().parents[1]
MARKDOWN = PAPER / "build" / "acl_latex.md"
AUX = PAPER / "build" / "acl_latex.aux"
HTML_SMALLCAPS = re.compile(r'<span class="smallcaps">(.*?)</span>')
AUX_SMALLCAPS = re.compile(r"(?:\\protect\s*)?\\textsc\s*\{([^{}]*)\}")


def main() -> None:
    markdown = MARKDOWN.read_text()
    lines = []
    for line in markdown.splitlines(keepends=True):
        if re.match(r"^#{1,6}\s", line):
            line = HTML_SMALLCAPS.sub(r"\1", line)
        lines.append(line)
    MARKDOWN.write_text("".join(lines))

    aux = AUX.read_text()
    AUX.write_text(AUX_SMALLCAPS.sub(r"\1", aux))


if __name__ == "__main__":
    main()
