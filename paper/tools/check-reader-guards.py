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


def check_caption_takeaways() -> None:
    required = {
        "fig/tex/overview.tex": (
            "cognitive process theory of writing",
            "coding-agent-style control loop",
            "selected online from the evolving document state",
        ),
        "tab/appendix-comparison.tex": (
            "only compared system",
            "online selection among heterogeneous writing operations",
        ),
        "tab/experiments-architecture-comparison.tex": (
            "central difference in what advances next",
            "whole document, a fixed stage, a task node, or a writing process",
        ),
        "tab/main-results.tex": (
            "higher is better",
            "scores highest on both measures for WritingBench and HelloBench",
        ),
        "tab/pairwise-results.tex": (
            "preferred on every benchmark against every alternative",
            "largest overall margin over \\condSinglePass",
        ),
        "tab/ablation-results.tex": (
            "remain close to the full system",
            "shows a substantially larger gap",
        ),
        "tab/process-dynamics.tex": (
            "accounts for 74.6\\% of runs",
            "only rarely exercises its ability",
        ),
        "sec/05_results.tex": (
            "mostly follows the same forward",
            "consistent with the small exploratory advantage of adaptive ordering",
        ),
        "tab/trace-outcome.tex": (
            "Win rates are similar",
            "describes association rather than a causal effect",
        ),
    }
    for path, phrases in required.items():
        text = read(path)
        for phrase in phrases:
            assert phrase in text, (
                "main figure/table captions must state the intended reader takeaway",
                path,
                phrase,
            )


def check():
    method = read("sec/03_method.tex")
    experiments = read("sec/04_experiments.tex")
    results = read("sec/05_results.tex")
    conclusion = read("sec/08_conclusion.tex")
    acl = read("acl_latex.tex")
    main_sources = "\n".join(read(path) for path in MAIN_SECTIONS)
    reader_tex_sources = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(PAPER.rglob("*.tex"))
    )
    reader_tex_sources = re.sub(r"(?m)%.*$", "", reader_tex_sources)

    match = re.search(r"\bwe ask\b", main_sources, flags=re.IGNORECASE)
    assert not match, (
        "reader-facing 'we ask' is banned in main text",
        match.group(0) if match else None,
    )

    for pattern, label in (
        (r"\bpilot\b", "pilot"),
        (r"\bboundary[ -]condition\b", "boundary condition"),
        (r"\bcontract\b", "contract"),
    ):
        match = re.search(pattern, reader_tex_sources, flags=re.IGNORECASE)
        assert not match, (
            f"reader-facing '{label}' wording is banned in manuscript TeX",
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

    # Preserve the substance of the model-choice rationale without freezing its prose.
    implementation = experiments.split(r"\subsection{Implementation}", 1)[1].split(r"\subsection{Evaluation}", 1)[0]
    assert r"\modelGenBare\ as the generator" in implementation, (
        "identify the generator model in Implementation"
    )
    assert r"\modelJudgeBare\ as the primary evaluator" in implementation, (
        "identify the primary evaluator model in Implementation"
    )
    assert r"\footnote{" in implementation, (
        "Implementation must retain the generator/evaluator selection rationale footnote"
    )
    for citation in ("openai2026luna", "openai2026sol", "openai2026gpt56"):
        assert citation in implementation, (
            "model-selection rationale must retain its supporting citations",
            citation,
        )
    assert "high-volume long-form generation" in implementation, (
        "explain why Luna is used for high-volume generation"
    )
    assert "higher-capability tier" in implementation and "evaluation" in implementation, (
        "explain why the higher-capability model tier is assigned to evaluation"
    )
    assert "shared model family" in implementation and "cross-family check" in implementation, (
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

    check_caption_takeaways()

    assert conclusion.startswith(r"\condAgenticCogWriter\ reframes long-form writing for AI agents"), (
        "keep the conclusion contribution-first rather than opening with 'We use'"
    )

    # Appendix organization and terminology are reader-facing constraints.
    assert r"\section{Prompt and Experiment Configuration}" in acl, (
        "Appendix A must be titled exactly 'Prompt and Experiment Configuration'"
    )
    assert r"\section{Prompt and experiment configuration}" not in acl
    assert r"\section{Consensus-Writing Evaluation on Habermas Machine Data}" in acl, (
        "name the Habermas-derived appendix by the evaluation task itself"
    )
    assert r"\section{Habermas Machine Pilot}" not in acl
    appendix = acl.split(r"\appendix", 1)[1]
    prompt_pos = appendix.index(r"\section{Prompt and Experiment Configuration}")
    onecolumn_pos = appendix.index(r"\onecolumn")
    assert onecolumn_pos < prompt_pos, (
        "switch to one-column layout before the first appendix section"
    )
    assert r"\twocolumn" not in appendix, (
        "keep the entire appendix in the intentional one-column layout"
    )
    assert "The Habermas table" not in acl, "describe the Habermas evaluation directly rather than referring to 'the Habermas table'"
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
