#!/usr/bin/env python3
"""Normalize styled markup used in manuscript headings.

Pandoc renders LaTeX small caps in GFM as HTML spans, while LaTeX preserves
formatting commands and grouping braces in auxiliary heading records.
Structural parity checks compare visible heading text, so normalize only those
heading representations; body text and manuscript source are left untouched.
"""

from pathlib import Path
import re

PAPER = Path(__file__).resolve().parents[1]
MARKDOWN = PAPER / "build" / "acl_latex.md"
AUX = PAPER / "build" / "acl_latex.aux"
HTML_SMALLCAPS = re.compile(r'<span class="smallcaps">(.*?)</span>')
AUX_HEADING = re.compile(
    r"\\contentsline \{(?:section|subsection|subsubsection|paragraph)\}"
)
AUX_TEXT_STYLE = re.compile(
    r"(?:\\protect\s*)?\\text(?:sc|tt)\s*\{([^{}]*)\}"
)


def _extract_braced(text: str, start: int) -> tuple[str, int]:
    """Return one balanced braced group and the position after its closing brace."""
    assert text[start] == "{", (start, text[start : start + 20])
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        escaped = index > 0 and text[index - 1] == "\\"
        if char == "{" and not escaped:
            depth += 1
        elif char == "}" and not escaped:
            depth -= 1
            if depth == 0:
                return text[start + 1 : index], index + 1
    raise ValueError("unbalanced braced group in LaTeX auxiliary data")


def _visible_heading_payload(payload: str) -> str:
    """Flatten formatting groups in a contentsline title while preserving numbering."""
    number_prefix = ""
    title = payload
    numberline = re.match(r"\\numberline\s*", title)
    if numberline:
        brace_start = title.find("{", numberline.end())
        if brace_start == -1:
            raise ValueError(f"numberline without braced number: {payload!r}")
        _, number_end = _extract_braced(title, brace_start)
        number_prefix = title[:number_end]
        title = title[number_end:]

    title = re.sub(r"\\protect\s*", "", title)
    previous = None
    while title != previous:
        previous = title
        title = AUX_TEXT_STYLE.sub(r"\1", title)

    # Remaining braces in this slice only group heading text (for example,
    # ``{\textsc{Agentic CogWriter}}``).  Removing them exposes the same visible
    # title that Pandoc writes to the Markdown heading.
    title = title.replace("{", "").replace("}", "")
    title = re.sub(r"\s+", " ", title).strip()
    return number_prefix + title


def _normalize_aux_headings(aux: str) -> str:
    """Normalize only the title argument of section-like contentsline records."""
    pieces = []
    cursor = 0
    search_from = 0
    while True:
        match = AUX_HEADING.search(aux, search_from)
        if not match:
            break

        title_start = match.end()
        while title_start < len(aux) and aux[title_start].isspace():
            title_start += 1
        if title_start >= len(aux) or aux[title_start] != "{":
            search_from = match.end()
            continue

        payload, title_end = _extract_braced(aux, title_start)
        pieces.append(aux[cursor : title_start + 1])
        pieces.append(_visible_heading_payload(payload))
        pieces.append("}")
        cursor = title_end
        search_from = title_end

    pieces.append(aux[cursor:])
    return "".join(pieces)


def main() -> None:
    markdown = MARKDOWN.read_text()
    lines = []
    for line in markdown.splitlines(keepends=True):
        if re.match(r"^#{1,6}\s", line):
            line = HTML_SMALLCAPS.sub(r"\1", line)
        lines.append(line)
    MARKDOWN.write_text("".join(lines))

    aux = AUX.read_text()
    AUX.write_text(_normalize_aux_headings(aux))


if __name__ == "__main__":
    main()
