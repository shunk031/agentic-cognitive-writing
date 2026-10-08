#!/usr/bin/env python3
"""Check rendered caption length and report sparse paragraph endings.

Captions remain a hard CI guard. Paragraph density is report-only for now: the
report highlights likely runt final lines so authors can decide whether a small
rewrite or a local ``\\looseness=-1`` improves the page without degrading prose.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

MAX_CAPTION_LINES = 5  # target ~4 lines; allow one line of layout variation
RUNT_MAX_WORDS = 2
RUNT_MAX_FILL = 0.25
CAPTION_RE = re.compile(r"^(Table|Figure)\s+\d+:\s")
LINE_NUMBER_BLOCK_RE = re.compile(r"^(?:\d{3}\s*)+$")
XHTML = {"x": "http://www.w3.org/1999/xhtml"}


@dataclass
class RenderedBlock:
    page: int
    block: int
    text: str
    lines: list[str]
    widths: list[float]
    x_min: float
    x_max: float

    @property
    def line_count(self) -> int:
        return len(self.lines)

    @property
    def last_words(self) -> int:
        return len(self.lines[-1].split()) if self.lines else 0

    @property
    def last_fill(self) -> float:
        if not self.widths or max(self.widths) <= 0:
            return 1.0
        return self.widths[-1] / max(self.widths)

    @property
    def preview(self) -> str:
        return self.text[:88]


def line_words(line: ET.Element) -> list[ET.Element]:
    return [word for word in line.findall("x:word", XHTML) if (word.text or "").strip()]


def rendered_block(page: int, index: int, block: ET.Element) -> RenderedBlock | None:
    lines: list[str] = []
    widths: list[float] = []
    all_words: list[ET.Element] = []
    for line in block.findall("x:line", XHTML):
        words = line_words(line)
        if not words:
            continue
        all_words.extend(words)
        lines.append(" ".join((word.text or "").strip() for word in words))
        widths.append(float(words[-1].attrib["xMax"]) - float(words[0].attrib["xMin"]))
    if not lines:
        return None
    return RenderedBlock(
        page=page,
        block=index,
        text=" ".join(lines).strip(),
        lines=lines,
        widths=widths,
        x_min=min(float(word.attrib["xMin"]) for word in all_words),
        x_max=max(float(word.attrib["xMax"]) for word in all_words),
    )


def is_prose_candidate(block: RenderedBlock) -> bool:
    """Heuristically keep body-width prose and exclude line numbers/table cells."""
    if block.line_count < 2 or CAPTION_RE.match(block.text):
        return False
    if LINE_NUMBER_BLOCK_RE.fullmatch(block.text):
        return False
    if block.x_max - block.x_min < 175:
        return False
    visible = sum(not char.isspace() for char in block.text)
    alphabetic = sum(char.isalpha() for char in block.text)
    return bool(visible and alphabetic / visible >= 0.45)


def main_body_end_page(root: ET.Element) -> int:
    pages = root.findall(".//x:page", XHTML)
    for page_number, page in enumerate(pages, 1):
        words = " ".join((word.text or "") for word in page.findall(".//x:word", XHTML))
        if re.search(r"\bLimitations\b", words):
            return page_number - 1
    return len(pages)


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

    blocks: list[RenderedBlock] = []
    for page_number, page in enumerate(root.findall(".//x:page", XHTML), 1):
        for block_index, block in enumerate(page.findall(".//x:block", XHTML)):
            parsed = rendered_block(page_number, block_index, block)
            if parsed is not None:
                blocks.append(parsed)

    captions = [block for block in blocks if CAPTION_RE.match(block.text)]
    assert captions, "no rendered figure/table captions found in PDF"
    offenders = [
        (CAPTION_RE.match(block.text).group(0).strip(), block.line_count, block.text[:160])
        for block in captions
        if block.line_count > MAX_CAPTION_LINES
    ]
    summary = ", ".join(
        f"{CAPTION_RE.match(block.text).group(0).strip()} {block.line_count}"
        for block in captions
    )
    print(f"Rendered caption lines (max {MAX_CAPTION_LINES}): {summary}")
    assert not offenders, (
        f"rendered captions must be <= {MAX_CAPTION_LINES} lines (target about four)",
        offenders,
    )

    main_end = main_body_end_page(root)
    prose = [block for block in blocks if block.page <= main_end and is_prose_candidate(block)]
    runts = [
        block
        for block in prose
        if block.last_words <= RUNT_MAX_WORDS or block.last_fill < RUNT_MAX_FILL
    ]
    caption_runts = [
        block
        for block in captions
        if block.page <= main_end
        and (block.last_words <= RUNT_MAX_WORDS or block.last_fill < RUNT_MAX_FILL)
    ]

    report_lines = [
        f"Main-body pages scanned: 1-{main_end}",
        "",
        "Rendered prose blocks:",
    ]
    for block in prose:
        report_lines.append(
            f"p{block.page:02d} b{block.block:03d} lines={block.line_count:2d} "
            f"last_words={block.last_words:2d} last_fill={block.last_fill:5.1%} | "
            f"{block.preview}"
        )
    report_lines.extend(["", "Rendered captions:"])
    for block in captions:
        report_lines.append(
            f"p{block.page:02d} lines={block.line_count:2d} "
            f"last_words={block.last_words:2d} last_fill={block.last_fill:5.1%} | "
            f"{block.preview}"
        )
    report_path = pdf.parent / "layout-density.txt"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(
        f"Layout density report: {len(prose)} prose-like blocks; "
        f"{len(runts)} potential runt endings; {len(caption_runts)} caption runt endings."
    )
    for block in runts:
        print(
            f"  WARN p{block.page:02d} b{block.block:03d}: "
            f"lines={block.line_count}, last_words={block.last_words}, "
            f"last_fill={block.last_fill:.0%}, last='{block.lines[-1][:70]}'"
        )
    for block in caption_runts:
        label = CAPTION_RE.match(block.text).group(0).strip()
        print(
            f"  WARN {label}: lines={block.line_count}, "
            f"last_words={block.last_words}, last_fill={block.last_fill:.0%}, "
            f"last='{block.lines[-1][:70]}'"
        )
    print(f"Full layout report: {report_path}")


if __name__ == "__main__":
    main()
