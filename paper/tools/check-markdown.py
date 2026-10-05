"""Check the rendered manuscript against its source and PDF auxiliary data."""

import re
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]


def _single_sentence_main_paragraphs():
    """Return prose paragraphs in the main paper that contain only one sentence.

    The check is intentionally conservative: display math, figures/tables, input-only
    blocks, lists, and headings are ignored. Its purpose is to catch accidental
    one-line prose fragments, not to prescribe a universal paragraph length.
    """

    offenders = []
    for path in [
        PAPER / "sec/01_introduction.tex",
        PAPER / "sec/02_related_work.tex",
        PAPER / "sec/03_method.tex",
        PAPER / "sec/04_experiments.tex",
        PAPER / "sec/05_results.tex",
        PAPER / "sec/06_discussion.tex",
        PAPER / "sec/07_limitations.tex",
        PAPER / "sec/08_conclusion.tex",
    ]:
        source = path.read_text()
        for paragraph in re.split(r"\n\s*\n", source):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            if any(
                token in paragraph
                for token in (
                    r"\begin{equation}",
                    r"\begin{itemize}",
                    r"\begin{enumerate}",
                )
            ):
                continue
            if re.search(r"\\begin\{(?:figure|table)\*?\}", paragraph):
                continue
            if re.fullmatch(r"\\input\{[^}]+\}", paragraph):
                continue
            if re.match(
                r"^(?:\\clearpage\s*)?\\(?:section|subsection|subsubsection)\*?\{",
                paragraph,
            ):
                continue
            if paragraph.startswith(r"\label"):
                continue

            prose = re.sub(r"^\\paragraph\{[^}]+\}\s*", "", paragraph)
            prose = re.sub(r"\\(?:cite[tp]?|ref|eqref)\{[^}]+\}", "CITATION", prose)
            prose = re.sub(r"\\[A-Za-z]+(?:\[[^]]*\])?\{([^{}]*)\}", r"\1", prose)
            prose = re.sub(r"\$[^$]*\$", "MATH", prose)
            prose = re.sub(r"\s+", " ", prose).strip()
            if not prose:
                continue
            sentence_ends = re.findall(r"[.!?](?=\s|$)", prose)
            if len(sentence_ends) <= 1:
                offenders.append((path.name, paragraph.replace("\n", " ")[:180]))
    return offenders


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
    html_tables = re.findall(r"^<table(?:\s[^>]*)?>$", text, re.MULTILINE)
    raw_tabulars = re.findall(r'^<div class="tabular">$', text, re.MULTILINE)
    assert len(pipe_tables) + len(html_tables) + len(raw_tabulars) == len(pdf_tables), (
        len(pipe_tables),
        len(html_tables),
        len(raw_tabulars),
        len(pdf_tables),
    )
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
    assert "Flower and Hayes (1981)" in text
    assert headings[-1] == "References"

    # Keep explicit evaluation-set counts and the internal hard100 name in the appendix.
    appendix_start = text.index("## Prompt and experiment configuration")
    main_text = text[:appendix_start]
    for sample_phrase in ("hard100", "100-prompt", "100 prompts", "300 prompts"):
        assert sample_phrase not in main_text, sample_phrase

    # Guard reviewer-facing wording that previously misstated the design or result.
    lowered = text.lower()
    for stale_phrase in ("no detectable loss", "longest-output", "independent replications"):
        assert stale_phrase not in lowered, stale_phrase

    # Semantic safeguards without freezing the manuscript to one exact sentence.
    limitations = text[text.index("## Limitations") : text.index("## References")]
    assert "human" in limitations.lower() and "judge" in limitations.lower()
    method_start = text.index("## Agentic CogWriter")
    method_end = text.index("## Experimental Design")
    method = text[method_start:method_end]
    assert "Monitor" in method and "Planning" in method and "Reviewing" in method

    paragraph_offenders = _single_sentence_main_paragraphs()
    assert not paragraph_offenders, paragraph_offenders

    main_sources = "\n".join(
        (PAPER / path).read_text()
        for path in (
            "acl_latex.tex",
            "sec/01_introduction.tex",
            "sec/04_experiments.tex",
            "sec/05_results.tex",
            "sec/06_discussion.tex",
            "sec/07_limitations.tex",
            "sec/08_conclusion.tex",
        )
    )
    for required_macro in (
        "ClusteredFullFixedOrderRate",
        "ClusteredFullFixedOrderInterval",
        "ClusteredFullFixedOrderP",
        "ClusteredFullNoGoalsRate",
        "ClusteredFullNoGoalsInterval",
        "ClusteredFullNoGoalsP",
        "UncondFullSinglePassWinShare",
        "UncondFullStagedWinShare",
        "UncondFullTaskPlanningWinShare",
        "WorstCaseFullSinglePassRate",
        "WorstCaseFullStagedRate",
        "WorstCaseFullTaskPlanningRate",
        "SingleWriterLengthFiveRate",
        "SingleWriterLengthFiveP",
        "SingleWriterLengthTenRate",
        "SingleWriterLengthTenP",
    ):
        assert "\\" + required_macro in main_sources, required_macro

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
            "Single-sentence main-text prose paragraphs: 0",
            "Explicit sample counts/internal hard100 label in main text: 0",
            "Stale review wording: 0",
            "Required adversarial-review macros referenced in source: 16/16",
            "Selected numbers spot-checked against numbers.tex:",
            *checks,
            f"Tables in PDF: {', '.join(pdf_tables)}",
            f"Tables in Markdown: {', '.join(md_tables)}",
            f"Table-count diff: 0; {len(pipe_tables)} Markdown pipe tables; {len(html_tables)} HTML tables; {len(raw_tabulars)} raw tabular blocks",
            f"Word count (whitespace-delimited Markdown tokens): {len(text.split())}",
            "Human-evaluation limitation present.",
            "",
        ]
    )
    (PAPER / "build" / "acl_latex.md.check.txt").write_text(report)
    print(report)


if __name__ == "__main__":
    check()
