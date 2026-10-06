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


def check():
    method = (PAPER / "sec/03_method.tex").read_text()
    experiments = (PAPER / "sec/04_experiments.tex").read_text()
    results = (PAPER / "sec/05_results.tex").read_text()
    main_sources = "\n".join((PAPER / path).read_text() for path in MAIN_SECTIONS)

    match = re.search(r"\bwe ask\b", main_sources, flags=re.IGNORECASE)
    assert not match, (
        "reader-facing 'we ask' is banned in main text",
        match.group(0) if match else None,
    )

    assert r"Its action space $\mathcal{A}$ is" in method, (
        "name the Monitor action space before defining it"
    )
    assert r"$D_0,D_1,\ldots,D_t,\ldots$" in method, (
        "preserve the evolving-draft sequence beginning at D_0"
    )
    assert "After $t$ completed process invocations" not in method, (
        "do not define t using the opaque 'completed process invocations' wording"
    )
    assert "The notation" not in method, (
        "introduce mathematical notation where it is used instead of explaining it afterward"
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
        "Prompts used while developing the protocol are removed before subset selection"
        in experiments
    ), "explain protocol-development prompt exclusion in reader-facing language"
    assert "we report that rubric as the benchmark-native score" in experiments, (
        "define benchmark-native scoring when the term is introduced"
    )
    assert experiments.count(r"\modelCross") == 1, (
        "explain the cross-family evaluator once in Experimental Design",
        experiments.count(r"\modelCross"),
    )

    pointwise = (
        results.split(r"\label{sec:results-pointwise}", 1)[1]
        .strip()
        .split("\n\n", 1)[0]
    )
    assert pointwise.startswith(r"Table~\ref{tab:main-results}"), (
        "start the pointwise Results subsection from the table the reader is about to interpret"
    )

    print("Reader-facing source guards: passed")


if __name__ == "__main__":
    check()
