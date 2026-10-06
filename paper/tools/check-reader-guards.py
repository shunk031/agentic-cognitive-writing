"""Guard reader-facing manuscript decisions that should not silently regress."""

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


def read(path: str) -> str:
    return (PAPER / path).read_text(encoding="utf-8")


def check_appendix_sections(acl: str) -> None:
    appendix = acl.split(r"\appendix", 1)[1]
    headings = list(re.finditer(r"\\(section|subsection)\{([^}]*)\}", appendix))
    assert headings, "appendix must contain sections"
    for index, match in enumerate(headings):
        level, title = match.group(1), match.group(2)
        # A top-level section may act as a container for substantive subsections.
        if (
            level == "section"
            and index + 1 < len(headings)
            and headings[index + 1].group(1) == "subsection"
        ):
            continue
        start = match.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(appendix)
        body = appendix[start:end]
        if title == "Prompt and Experiment Configuration":
            body += "\n" + read("sec/09_prompt_configuration.tex")
        prose = re.sub(r"%.*", "", body)
        prose = re.sub(r"\\(?:label|input)\{[^}]*\}", "", prose)
        prose = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^]]*\])?", "", prose)
        prose = re.sub(r"[{}$~\\]", " ", prose)
        words = re.findall(r"\b[A-Za-z][A-Za-z'-]*\b", prose)
        assert len(words) >= 8, (
            "appendix sections/subsections must contain explanatory prose, not only a table/figure input",
            title,
            len(words),
        )


def check():
    method = read("sec/03_method.tex")
    experiments = read("sec/04_experiments.tex")
    results = read("sec/05_results.tex")
    conclusion = read("sec/08_conclusion.tex")
    acl = read("acl_latex.tex")
    main_sources = "\n".join(read(path) for path in MAIN_SECTIONS)

    match = re.search(r"\bwe ask\b", main_sources, flags=re.IGNORECASE)
    assert not match, (
        "reader-facing 'we ask' is banned in main text",
        match.group(0) if match else None,
    )

    assert r"action space $A$" in method, (
        "name the Monitor action space A before defining it"
    )
    assert r"A=\{\texttt{Planning},\texttt{Translating},\texttt{Reviewing}\}" in method, (
        "define action space A explicitly"
    )
    assert r"a_t\in A" in method, "keep the selected action tied to action space A"
    assert r"$D_0$" in method and r"$G_0$" in method, (
        "preserve the initial draft and initial goal state"
    )
    assert "After $t$ completed process invocations" not in method, (
        "do not define t using the opaque 'completed process invocations' wording"
    )
    assert "The notation" not in method, (
        "introduce mathematical notation where it is used instead of explaining it afterward"
    )
    assert r"\pi_{\mathrm{Monitor}}" not in method, (
        "do not describe the runtime Monitor as a learned-policy notation"
    )
    assert method.count(r"\subsection{") == 2, (
        "keep Method to Persistent Writing State and Process-Level Control and Execution",
        method.count(r"\subsection{"),
    )
    assert r"\subsection{Agent Roles and State Updates}" not in method, (
        "keep role execution with process-level control rather than a detached subsection"
    )
    for required in (
        r"If \texttt{Planning} is selected",
        r"If \texttt{Translating} is selected",
        r"If \texttt{Reviewing} is selected",
    ):
        assert required in method, (
            "explain what each selected writing process does",
            required,
        )

    assert experiments.startswith("In this experimental design, we consider"), (
        "open Experimental Design with an author-led description of what we consider"
    )
    assert "Seven systems were" not in experiments, (
        "use active author-led prose for the compared systems"
    )
    numbered_systems = (
        (1, r"\condSinglePass"),
        (2, r"\condStaged"),
        (3, r"\condTaskPlanning"),
        (4, r"\condNoGoals"),
        (5, r"\condFixedOrder"),
        (6, r"\condSingleWriter"),
        (7, r"\condAgenticCogWriter"),
    )
    positions = []
    for number, macro in numbered_systems:
        token = f"({number}) {macro}"
        assert token in experiments, ("number all seven pre-specified systems", token)
        positions.append(experiments.index(token))
    assert positions == sorted(positions), (
        "number the seven pre-specified systems in order",
        positions,
    )

    for token in (
        r"(1) WritingBench~\citep",
        r"(2) HelloBench~\citep",
        r"(3) DoLoMiTes~\citep",
    ):
        assert token in experiments, ("number the three benchmarks explicitly", token)

    assert "gateway entry point" not in experiments.lower(), (
        "keep infrastructure-specific launch details out of the main experimental narrative"
    )
    assert (
        "We first reserve any prompts used while developing or debugging the evaluation protocol and never score those prompts."
        in experiments
    ), "explain development-prompt exclusion before describing subset selection"
    assert "benchmark authors' original criteria rather than our shared rubric" in experiments, (
        "define benchmark-native scoring in plain language when the term is introduced"
    )
    assert experiments.count(r"\modelCross") == 1, (
        "name the cross-family evaluator once in Experimental Design",
        experiments.count(r"\modelCross"),
    )

    # Preserve the model-choice rationale when generator/evaluator wording is consolidated.
    implementation = experiments.split(r"\subsection{Implementation}", 1)[1].split(r"\subsection{Evaluation}", 1)[0]
    assert r"\footnote{" in implementation, "Implementation must retain the generator/evaluator selection rationale footnote"
    assert "cost-sensitive, high-volume workloads" in implementation, "explain why Luna is used for high-volume generation"
    assert "flagship for complex professional work" in implementation, "explain why Sol is used for primary evaluation"
    assert "shared model family motivates the cross-family check" in implementation, (
        "connect the model-choice rationale to the cross-family robustness check"
    )

    pointwise = (
        results.split(r"\label{sec:results-pointwise}", 1)[1]
        .strip()
        .split("\n\n", 1)[0]
    )
    assert pointwise.startswith(r"Table~\ref{tab:main-results}"), (
        "start the pointwise Results subsection from the table the reader is about to interpret"
    )
    assert "shows that no" not in results, "avoid awkward 'Table X shows that no ...' constructions"
    for label in (
        "app:record-pooled",
        "app:length-control",
        "app:compute-control",
        "app:single-context",
        "app:cross-family",
    ):
        assert f"Appendix~\\ref{{{label}}}" not in main_sources, (
            "main text should point readers to the containing sensitivity appendix rather than Appendix E.x",
            label,
        )
    assert r"Appendix~\ref{app:sensitivity-analyses}" in results, (
        "refer to the sensitivity analyses collectively as Appendix E"
    )

    assert conclusion.startswith(r"\condAgenticCogWriter\ reframes long-form writing for AI agents"), (
        "keep the conclusion contribution-first rather than opening with 'We use'"
    )

    # Appendix organization and terminology are reader-facing contracts.
    assert r"\section{Prompt and Experiment Configuration}" in acl, (
        "Appendix A must be titled exactly 'Prompt and Experiment Configuration'"
    )
    assert r"\section{Prompt and experiment configuration}" not in acl
    prompt_pos = acl.index(r"\section{Prompt and Experiment Configuration}")
    runtime_pos = acl.index(r"\section{Runtime Configuration}")
    assert r"\onecolumn" in acl[:prompt_pos][-100:], "render the full prompt appendix in one-column mode"
    assert r"\twocolumn" in acl[prompt_pos:runtime_pos], "return to two-column layout after the prompt appendix"
    assert "The Habermas table" not in acl, "describe the Habermas pilot directly rather than referring to 'the Habermas table'"
    check_appendix_sections(acl)

    runtime_table = read("tab/appendix-runtime-settings.tex")
    assert "Generator sandbox" not in runtime_table and "workspace-write" not in runtime_table, (
        "omit the redundant generator sandbox row from the runtime table"
    )

    single_context = read("tab/appendix-single-context.tex")
    assert r"\condSingleContext\\vs.~\condAgenticCogWriter" in single_context, (
        "break Single-context / vs. Agentic CogWriter across two lines in the appendix table"
    )

    print("Reader-facing source guards: passed")


if __name__ == "__main__":
    check()
