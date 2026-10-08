#!/usr/bin/env python3
"""Fail CI when a rendered figure/table caption exceeds the visual line cap."""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_CAPTION_LINES = 5  # target ~4 lines; allow one line of layout variation
CAPTION_RE = re.compile(r"^(Table|Figure)\s+\d+:\s")
XHTML = {"x": "http://www.w3.org/1999/xhtml"}


def block_text(block: ET.Element) -> tuple[str, list[str]]:
    lines = []
    for line in block.findall("x:line", XHTML):
        words = [word.text or "" for word in line.findall("x:word", XHTML)]
        lines.append(" ".join(words).strip())
    return " ".join(lines).strip(), lines


def main() -> None:
    pdf = Path(sys.argv[1] if len(sys.argv) > 1 else "build/acl_latex.pdf")
    assert pdf.exists(), f"missing PDF: {pdf}"

    with tempfile.TemporaryDirectory() as tmp:
        bbox = Path(tmp) / "bbox.html"
        subprocess.run(
            ["pdftotext", "-bbox-layout", str(pdf), str(bbox)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        root = ET.parse(bbox).getroot()

    captions = []
    for block in root.findall(".//x:block", XHTML):
        text, lines = block_text(block)
        if CAPTION_RE.match(text):
            label = CAPTION_RE.match(text).group(0).strip()
            captions.append((label, len(lines), text))

    assert captions, "no rendered figure/table captions found in PDF"
    offenders = [
        (label, line_count, text[:160])
        for label, line_count, text in captions
        if line_count > MAX_CAPTION_LINES
    ]
    summary = ", ".join(f"{label} {count}" for label, count, _ in captions)
    print(f"Rendered caption lines (max {MAX_CAPTION_LINES}): {summary}")
    assert not offenders, (
        f"rendered captions must be <= {MAX_CAPTION_LINES} lines (target about four)",
        offenders,
    )


if __name__ == "__main__":
    main()
