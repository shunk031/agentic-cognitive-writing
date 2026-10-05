"""Check the rendered manuscript against its source and PDF auxiliary data."""

import re
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
MAIN_SECTIONS = [
    "sec/01_introduction.tex",
    "sec/02_related_work.tex",
    "sec/03_method.tex",
    "sec/04_experiments.tex",
    "sec/05_results.tex",
    "sec/06_discussion.tex",
    "sec/07_limitations.tex",
    "sec/08_conclusion.tex",
]


def _without_code_blocks(text):
    """Remove fenced/indented code so literal Appendix prompts are not manuscript syntax."""
    text = re.sub(r"(?ms)^```[^\n]*\n.*?^```\s*$", "", text)
    text = re.sub(r"(?ms)^~~~[^\n]*\n.*?^~~~\s*$", "", text)
    return re.sub(r"(?m)^(?: {4}|\t).*$", "", text)


def _main_prose_paragraphs():
    """Yield normalized prose paragraphs from the main paper."""
    for relative in MAIN_SECTIONS:
        path = PAPER / relative
        source = path.read_text()
        for paragraph in re.split(r"\n\s*\n", source):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            if any(
                token in paragraph
                for token in (
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

            prose = re.sub(
                r"\\begin\{equation\}.*?\\end\{equation\}",
                " MATH ",
                paragraph,
                flags=re.DOTALL,
            )
            prose = re.sub(r"^\\paragraph\{[^}]+\}\s*", "", prose)
            prose = re.sub(r"\\(?:cite[tp]?|ref|eqref)\{[^}]+\}", "CITATION", prose)
            prose = re.sub(r"\\[A-Za-z]+(?:\[[^]]*\])?\{([^{}]*)\}", r"\1", prose)
            prose = re.sub(r"\$[^$]*\$", "MATH", prose)
            prose = re.sub(r"\s+", " ", prose).strip()
            if prose:
                yield path.name, paragraph, prose


def _paragraph_style_offenders():
    """Return reader-facing paragraph problems guarded by this manuscript."""
    offenders = []
    for filename, original, prose in _main_prose_paragraphs():
        sentence_ends = re.findall(r"[.!?](?=\s|$)", prose)
        words = re.findall(r"\b[\w'-]+\b", prose)
        if len(sentence_ends) <= 1:
            offenders.append((filename, "single-sentence", prose[:180]))
        if len(sentence_ends) > 6 or len(words) > 150:
            offenders.append(
                (
                    filename,
                    f"too-long:{len(sentence_ends)} sentences/{len(words)} words",
                    prose[:180],
                )
            )
        if re.match(r"^(?:This|These|That|Those|It)\b", prose):
            offenders.append((filename, "vague-topic-sentence", prose[:180]))
        repeated = re.search(r"\b([A-Za-z]+)\s+\1\b", prose, flags=re.IGNORECASE)
        if repeated:
            offenders.append(
                (filename, f"adjacent-duplicate:{repeated.group(0)}", prose[:180])
            )
    return offenders


def _appendix_float_refs_in_main_text():
    """Return main-text references to tables or figures that live in the appendix."""

    def expand(text):
        def include(match):
            path = PAPER / (
                match[1] if match[1].endswith(".tex") else match[1] + ".tex"
            )
            return expand(path.read_text()) if path.exists() else ""

        return re.sub(r"\\input\{([^}]+)\}", include, text)

    source = (PAPER / "acl_latex.tex").read_text()
    body = source[source.index(r"\begin{document}") :]
    main, appendix = (
        re.sub(r"(?<!\\)%.*", "", expand(part))
        for part in body.split(r"\appendix", 1)
    )
    appendix_floats = {
        label
        for label in re.findall(r"\\label\{([^}]+)\}", appendix)
        if label.split(":")[0] in ("tab", "fig")
    }
    return [
        label.strip()
        for match in re.finditer(
            r"\\(?:ref|cref|Cref|autoref|subref)\{([^}]+)\}", main
        )
        for label in match[1].split(",")
        if label.strip() in appendix_floats
    ]


def check():
    text = (PAPER / "build" / "acl_latex.md").read_text()
    aux = (PAPER / "build" / "acl_latex.aux").read_text()
    structural_text = _without_code_blocks(text)

    source = (PAPER / "acl_latex.tex").read_text()
    abstract = re.search(
        r"\\begin\{abstract\}\s*(.*?)\s*\\end\{abstract\}", source, re.DOTALL
    )[1]
    abstract_words = re.findall(r"\b[\w'-]+\b", abstract)
    abstract_commands = re.findall(r"\\[A-Za-z]+", abstract)
    assert len(abstract_words) <= 200, len(abstract_words)
    assert not abstract_commands, ("LaTeX command in abstract", abstract_commands)

    controls = re.findall(r"\\[A-Za-z]+", structural_text)
    assert not controls, controls
    for residue in ("~", r"\%", r"\$", "--", r"\ref", r"\label"):
        prose = "\n".join(
            line
            for line in structural_text.splitlines()
            if not re.fullmatch(r"[| :\-]+", line)
        )
        assert residue not in prose, residue

    pdf_tables = re.findall(r"\\contentsline \{table\}\{\\numberline \{(\d+)\}", aux)
    md_tables = re.findall(r"^Table (\d+)\.", structural_text, re.MULTILINE)
    assert pdf_tables == md_tables == list(map(str, range(1, len(pdf_tables) + 1))), (
        pdf_tables,
        md_tables,
    )
    pipe_tables = re.findall(
        r"^\|(?=[ :\-|]*-)[ :\-|]+\|$", structural_text, re.MULTILINE
    )
    html_tables = re.findall(
        r"^<table(?:\s[^>]*)?>$", structural_text, re.MULTILINE
    )
    raw_tabulars = re.findall(
        r'^<div class="tabular">$', structural_text, re.MULTILINE
    )
    assert len(pipe_tables) + len(html_tables) + len(raw_tabulars) == len(pdf_tables), (
        len(pipe_tables),
        len(html_tables),
        len(raw_tabulars),
        len(pdf_tables),
    )

    pdf_headings = re.findall(
        r"\\contentsline \{(section|subsection|subsubsection|paragraph)\}", aux
    )
    headings = re.findall(r"^#{1,6} (.+)$", structural_text, re.MULTILINE)
    expected = len(pdf_headings) + 1
    actual = len(headings) - 3
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
    assert structural_text.index("## Abstract") < structural_text.index("## Introduction")
    assert "N annotators" not in structural_text
    assert "Flower and Hayes (1981)" in structural_text
    assert headings[-1] == "References"

    appendix_start = structural_text.index("## Prompt and experiment configuration")
    main_text = structural_text[:appendix_start]
    for sample_phrase in ("hard100", "100-prompt", "100 prompts", "300 prompts"):
        assert sample_phrase not in main_text, sample_phrase

    for banned in (
        r"\bit is\b",
        r"\bcell(?:s|wise)?\b",
        r"\bspecialists?\b",
        r"\bbookkeeping\b",
        r"\bLuna(?:--|-|–)Sol\b",
        r"\bThese approaches\b",
        r"\bComputational work\b",
        r"\bIndependent rubric-based scoring\b",
        r"\bHolm-surviving\b",
        r"\bdecided comparisons?\b",
        r"\bpooled over\b",
    ):
        match = re.search(banned, main_text, flags=re.IGNORECASE)
        assert not match, (banned, match.group(0) if match else None)

    proposal_architecture = re.search(
        r"\bAgentic CogWriter\b[^\n.]{0,60}\barchitecture\b",
        main_text,
        flags=re.IGNORECASE,
    )
    assert not proposal_architecture, (
        "call Agentic CogWriter a system; reserve architecture for generic structure",
        proposal_architecture.group(0) if proposal_architecture else None,
    )

    lowered = main_text.lower()
    for stale_phrase in (
        "no detectable loss",
        "longest-output",
        "independent replications",
    ):
        assert stale_phrase not in lowered, stale_phrase

    limitations = structural_text[
        structural_text.index("## Limitations") : structural_text.index("## References")
    ]
    assert "human" in limitations.lower() and "judge" in limitations.lower()
    method_start = structural_text.index("## Agentic CogWriter")
    method_end = structural_text.index("## Experimental Design")
    method = structural_text[method_start:method_end]
    assert "Monitor" in method and "Planning" in method and "Reviewing" in method

    paragraph_offenders = _paragraph_style_offenders()
    assert not paragraph_offenders, paragraph_offenders

    appendix_float_refs = _appendix_float_refs_in_main_text()
    assert not appendix_float_refs, (
        "main text cites appendix floats; cite the appendix section instead",
        appendix_float_refs,
    )

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
        assert value in structural_text, (name, value)
        checks.append(f"{name}: {value} (present in Markdown)")

    report = "\n".join(
        [
            "Unexpanded control sequences in manuscript prose: 0",
            f"Abstract words: {len(abstract_words)}/200; LaTeX commands: 0",
            f"Section headings: Markdown {actual}; PDF {expected} ({len(pdf_headings)} aux entries plus unnumbered Limitations)",
            "Title, Abstract, and References headings excluded from section count.",
            "Paragraph-style violations: 0",
            "Main-text references to appendix tables or figures: 0",
            "Banned reader-facing terms/patterns: 0",
            "Adjacent duplicate words in main-text prose: 0",
            "Explicit sample counts/internal hard100 label in main text: 0",
            "Stale review wording: 0",
            "Required adversarial-review macros referenced in source: 16/16",
            "Selected numbers spot-checked against numbers.tex:",
            *checks,
            f"Tables in PDF: {', '.join(pdf_tables)}",
            f"Tables in Markdown: {', '.join(md_tables)}",
            f"Table-count diff: 0; {len(pipe_tables)} Markdown pipe tables; {len(html_tables)} HTML tables; {len(raw_tabulars)} raw tabular blocks",
            f"Word count (manuscript Markdown, excluding literal prompt blocks): {len(structural_text.split())}",
            "Human-evaluation limitation present.",
            "",
        ]
    )
    (PAPER / "build" / "acl_latex.md.check.txt").write_text(report)
    print(report)


if __name__ == "__main__":
    check()
