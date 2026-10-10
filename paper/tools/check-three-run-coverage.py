#!/usr/bin/env python3
"""Guard study-wide Appendix analyses against accidental first-run-only reporting."""

from pathlib import Path


PAPER = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (PAPER / path).read_text(encoding="utf-8")


def section(text: str, start: str, end: str) -> str:
    assert start in text, ("missing Appendix section marker", start)
    tail = text.split(start, 1)[1]
    assert end in tail, ("missing Appendix section boundary", end)
    return tail.split(end, 1)[0]


def check() -> None:
    process_table = read("tab/appendix-process.tex")
    length_table = read("tab/appendix-length-control.tex")
    appendix = read("sec/10_appendix.tex")

    # Reader-facing reason: the main study is described as three-run. If an
    # Appendix artifact silently reuses the first report after all three inputs
    # exist, a reviewer can reasonably infer selective run reporting. This guard
    # is deliberately scoped to the two study-wide analyses with three-run inputs;
    # intentionally single-run exploratory checks elsewhere remain allowed.
    for path, text in (
        ("tab/appendix-process.tex", process_table),
        ("tab/appendix-length-control.tex", length_table),
    ):
        assert "all three generation runs" in text, (
            "study-wide Appendix analyses with three-run inputs must identify all three runs",
            path,
        )
        assert "generation run 1 of 3" not in text, (
            "do not silently present the first report as a study-wide Appendix result",
            path,
        )

    process_section = section(
        appendix,
        r"\section{Additional Process and Resource Statistics}",
        r"\section{Sensitivity Analyses}",
    )
    length_section = section(
        appendix,
        r"\subsection{Output-Length Sensitivity}",
        r"\subsection{Compute-Stratified Sensitivity}",
    )
    for label, text in (
        ("process/resource Appendix prose", process_section),
        ("output-length Appendix prose", length_section),
    ):
        assert "first generation run" not in text, (
            "study-wide three-run analysis must not fall back to first-run-only prose",
            label,
        )

    for condition in ("Aone", "Atwo", "Athree", "Afour", "Afive", "Asix", "Aseven"):
        for suffix in (
            "MedianOutputMean",
            "SpawnsMean",
            "GoalCreatedMean",
            "GoalDevelopedMean",
            "GoalRegeneratedMean",
            "OutputTokensMean",
            "InputTokensMean",
            "MeanSecondsMean",
        ):
            macro = rf"\{condition}{suffix}"
            assert macro in process_table, (
                "process/resource table must use three-run mean macros",
                macro,
            )

    for comparison in ("SinglePass", "TaskPlanning", "NoGoals"):
        for band in ("Five", "Ten"):
            for run in ("One", "Two", "Three"):
                macro = rf"\LengthFull{comparison}{band}RateRun{run}"
                assert macro in length_table, (
                    "length sensitivity must expose every available generation run",
                    macro,
                )


if __name__ == "__main__":
    check()
