"""Check the rendered manuscript against its source and PDF auxiliary data."""

import re
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]


def check():
    text = (PAPER / "build" / "acl_latex.md").read_text()
    aux = (PAPER / "build" / "acl_latex.aux").read_text()
    controls = re.findall(r"\\[A-Za-z]+", text)
    assert not controls, controls
    for residue in ("~", r"\%", r"\$", "--", r"\ref", r"\label"):
        # Pipe-table separators are Markdown syntax, not prose dashes.
        prose = "\n".join(
            line for line in text.splitlines() if not re.fullmatch(r"[| :\-]+", line)
        )
        assert residue not in prose, residue
    pdf_tables = re.findall(r"\\contentsline \{table\}\{\\numberline \{(\d+)\}", aux)
    md_tables = re.findall(r"^Table (\d+)\.", text, re.MULTILINE)
    assert pdf_tables == md_tables == list(map(str, range(1, len(pdf_tables) + 1))), (
        pdf_tables,
        md_tables,
    )
    pipe_tables = re.findall(r"^\|(?=[ :\-|]*-)[ :\-|]+\|$", text, re.MULTILINE)
    assert len(pipe_tables) == len(pdf_tables), len(pipe_tables)
    pdf_headings = re.findall(
        r"\\contentsline \{(section|subsection|subsubsection|paragraph)\}", aux
    )
    headings = re.findall(r"^#{1,6} (.+)$", text, re.MULTILINE)
    # Limitations is unnumbered and absent from the PDF table of contents.
    expected = len(pdf_headings) + 1
    actual = len(headings) - 3  # title, abstract, references
    assert actual == expected, (actual, expected, headings)
    pdf_titles = re.findall(
        r"\\contentsline \{(?:section|subsection|subsubsection|paragraph)\}"
        r"\{(?:\\numberline \{[^}]+\})?([^{}]+)\}",
        re.sub(r"\\texttt\s*\{([^{}]*)\}", r"\1", aux),
    )
    pdf_titles.insert(pdf_titles.index("Conclusion") + 1, "Limitations")
    normalized_headings = [heading.replace(chr(96), "") for heading in headings]
    assert normalized_headings[2:-1] == pdf_titles, (
        normalized_headings[2:-1],
        pdf_titles,
    )
    assert text.index("## Abstract") < text.index("## Introduction")
    assert "N annotators" not in text
    assert "human raters is unknown" in text
    assert "(Flower and Hayes, 1981)" in text
    assert "Table 3" in text
    assert "process-selection policy" in text
    assert headings[-1] == "References"
    names = [
        "PooledFourOneRateMean",
        "PooledFourTwoRateMean",
        "PooledFourThreeRateMean",
        "DoLoFourOneRateMean",
        "HelloFourOneRateMean",
        "WritingFourOneRateMean",
        "AfourOutputTokens",
        "AfourInputTokens",
        "AfourGoalRegenerated",
        "AfourLedgerEntriesMean",
        "AfourLedgerWithProposalMean",
        "AfourGoalCreatedMean",
        "AfourGoalDevelopedMean",
        "ReplicationRunOneMissingPairs",
    ]
    numbers = (PAPER / "numbers.tex").read_text()
    checks = []
    for name in names:
        value = re.search(r"\\newcommand\{\\" + name + r"\}\{([^{}]*)\}", numbers)[1]
        value = value.replace(r"\%", "%").replace(r"\$", "$").replace("--", "–")
        assert value in text, (name, value)
        checks.append(f"{name}: {value} (present in Markdown)")
    report = "\n".join(
        [
            "Unexpanded control sequences: 0",
            f"Section headings: Markdown {actual}; PDF {expected} ({len(pdf_headings)} aux entries plus unnumbered Limitations)",
            "Title, Abstract, and References headings excluded from section count.",
            "Ten numbers spot-checked against numbers.tex:",
            *checks,
            f"Tables in PDF: {', '.join(pdf_tables)}",
            f"Tables in Markdown: {', '.join(md_tables)}",
            f"Table-count diff: 0; {len(pipe_tables)} Markdown pipe tables",
            f"Word count (whitespace-delimited Markdown tokens): {len(text.split())}",
            "Human-evaluation wording: no human evaluation; agreement with human raters is unknown",
            "",
        ]
    )
    (PAPER / "build" / "acl_latex.md.check.txt").write_text(report)
    print(report)


if __name__ == "__main__":
    check()
