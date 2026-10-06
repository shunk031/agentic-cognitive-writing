#!/usr/bin/env python3
"""Enforce reader-facing numeric-table conventions in the manuscript."""

from __future__ import annotations

import re
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (PAPER / path).read_text(encoding="utf-8")


def tabular_spec(text: str) -> str:
    match = re.search(r"\\begin\{tabular\}\{([^{}]+)\}", text)
    assert match, "could not find a simple tabular column specification"
    return match.group(1).replace(" ", "")


def tabular_body(text: str) -> str:
    return text.split(r"\toprule", 1)[1].split(r"\bottomrule", 1)[0]


def percentages(text: str) -> list[str]:
    return re.findall(r"(?<![A-Za-z0-9.])(-?\d+(?:\.\d+)?)\\%", text)


def assert_fixed_decimals(values: list[str], decimals: int, label: str) -> None:
    assert values, f"{label}: expected numeric values"
    bad = [value for value in values if "." not in value or len(value.rsplit(".", 1)[1]) != decimals]
    assert not bad, f"{label}: inconsistent decimal precision: {bad}"


def check() -> None:
    main = read("tab/main-results.tex")
    pairwise = read("tab/pairwise-results.tex")
    ablation = read("tab/ablation-results.tex")
    process = read("tab/process-dynamics.tex")
    trace = read("tab/trace-outcome.tex")

    # Numeric columns are right-aligned. Text columns remain left-aligned.
    expected_specs = {
        "tab/main-results.tex": "lrrrrrr",
        "tab/pairwise-results.tex": "lrrrr",
        "tab/ablation-results.tex": "lrrrr",
        "tab/process-dynamics.tex": "lr",
        "tab/trace-outcome.tex": "lrr",
        "tab/appendix-length-control.tex": "lrr",
        "tab/appendix-process.tex": "lrrrrrrr",
        "tab/appendix-record-pooled-pairwise.tex": "lrrrr",
        "tab/appendix-compute-control.tex": "llrrr",
        "tab/appendix-cross-family.tex": "llrrrrr",
        "tab/appendix-habermas.tex": "lrrrrr",
    }
    for path, expected in expected_specs.items():
        actual = tabular_spec(read(path))
        assert actual == expected, f"{path}: expected numeric columns right-aligned as {expected}, got {actual}"

    # Main quality scores use three decimals throughout the displayed table.
    main_values = re.findall(r"(?<![A-Za-z0-9])(-?\d+\.\d+)(?![A-Za-z0-9])", tabular_body(main))
    assert len(main_values) == 20, ("tab/main-results.tex: unexpected number of displayed scores", len(main_values))
    assert_fixed_decimals(main_values, 3, "tab/main-results.tex")
    assert "Best scores in each column are in \\textbf{bold}." in main
    assert "WritingBench native scores are divided by 10 for display" in main

    # Win-rate tables use one decimal place, including values that round to an integer.
    for path, text, count in (
        ("tab/pairwise-results.tex", pairwise, 12),
        ("tab/ablation-results.tex", ablation, 12),
        ("tab/process-dynamics.tex", process, 3),
        ("tab/trace-outcome.tex", trace, 4),
    ):
        values = percentages(tabular_body(text))
        assert len(values) == count, (f"{path}: unexpected number of displayed percentages", len(values))
        assert_fixed_decimals(values, 1, path)

    # Table 4 has no informative best-cell distinction because every displayed rate favors the focal system.
    pairwise_data = tabular_body(pairwise).split(r"\midrule", 1)[1]
    assert r"\textbf{" not in pairwise_data, "tab/pairwise-results.tex: do not bold every winning rate"

    # Grouped numeric headers use partial rules instead of visually heavy full-width rules.
    for path, text in (
        ("tab/main-results.tex", main),
        ("tab/pairwise-results.tex", pairwise),
        ("tab/ablation-results.tex", ablation),
        ("tab/trace-outcome.tex", trace),
    ):
        assert r"\cmidrule" in text, f"{path}: grouped columns require \\cmidrule"

    # A rate column must not mix percentages with count fractions such as 4/886.
    assert not re.search(r"\b\d+\s*/\s*\d+\b", tabular_body(process)), (
        "tab/process-dynamics.tex: do not mix count fractions with percentage rates"
    )

    # The two p-values in the trace/outcome table use two decimals.
    assert "& 0.60" in trace and "& 0.43" in trace, "tab/trace-outcome.tex: keep Fisher p-values at two decimals"

    print("Table-style guards: passed")


if __name__ == "__main__":
    check()
