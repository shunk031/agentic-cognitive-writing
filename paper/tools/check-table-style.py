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


def macro_value(numbers: str, name: str) -> str:
    match = re.search(rf"\\newcommand\{{\\{re.escape(name)}\}}\{{([^}}]*)\}}", numbers)
    assert match, f"numbers.tex: missing \\{name}"
    return match.group(1)


def numeric_macro(numbers: str, name: str) -> float:
    value = macro_value(numbers, name).replace(r"\%", "").replace(",", "")
    try:
        return float(value)
    except ValueError as error:
        raise AssertionError(f"numbers.tex: \\{name} is not a scalar numeric value: {value!r}") from error


def percent_macro(numbers: str, name: str) -> float:
    value = macro_value(numbers, name)
    assert value.endswith(r"\%"), f"numbers.tex: \\{name} is not a percentage: {value!r}"
    return float(value[:-2])


def check() -> None:
    numbers = read("numbers.tex")
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

    # Main quality scores use three decimals and remain synchronized with numbers.tex.
    main_values = re.findall(r"(?<![A-Za-z0-9])(-?\d+\.\d+)(?![A-Za-z0-9])", tabular_body(main))
    assert len(main_values) == 20, ("tab/main-results.tex: unexpected number of displayed scores", len(main_values))
    assert_fixed_decimals(main_values, 3, "tab/main-results.tex")
    expected_main: list[str] = []
    for condition in ("Aone", "Atwo", "Athree", "Afour"):
        expected_main.extend(
            [
                f"{numeric_macro(numbers, f'Writing{condition}Native') / 10:.3f}",
                f"{numeric_macro(numbers, f'Writing{condition}Point'):.3f}",
                f"{numeric_macro(numbers, f'Hello{condition}Native'):.3f}",
                f"{numeric_macro(numbers, f'Hello{condition}Point'):.3f}",
                f"{numeric_macro(numbers, f'DoLo{condition}Point'):.3f}",
            ]
        )
    assert main_values == expected_main, ("tab/main-results.tex: displayed scores are stale relative to numbers.tex", main_values, expected_main)
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

    expected_pairwise = [
        f"{percent_macro(numbers, name):.1f}"
        for suffix in ("One", "Two", "Three")
        for name in (
            f"WritingFour{suffix}RateMean",
            f"HelloFour{suffix}RateMean",
            f"DoLoFour{suffix}RateMean",
            f"PooledFour{suffix}RateMean",
        )
    ]
    assert percentages(tabular_body(pairwise)) == expected_pairwise, (
        "tab/pairwise-results.tex: displayed rates are stale relative to numbers.tex"
    )

    expected_ablation = [
        f"{percent_macro(numbers, name):.1f}"
        for suffix in ("Five", "Six", "Seven")
        for name in (
            f"WritingFour{suffix}RateMean",
            f"HelloFour{suffix}RateMean",
            f"DoLoFour{suffix}RateMean",
            f"PooledFour{suffix}RateMean",
        )
    ]
    assert percentages(tabular_body(ablation)) == expected_ablation, (
        "tab/ablation-results.tex: displayed rates are stale relative to numbers.tex"
    )

    expected_process = [
        f"{percent_macro(numbers, 'AfourCycleCompliantRate'):.1f}",
        f"{percent_macro(numbers, 'AfourReviewingToPlanningRate'):.1f}",
        f"{100 * numeric_macro(numbers, 'AfourRegenerationRuns') / numeric_macro(numbers, 'AfourRunCount'):.1f}",
    ]
    assert percentages(tabular_body(process)) == expected_process, (
        "tab/process-dynamics.tex: displayed rates are stale relative to numbers.tex"
    )

    expected_trace = [
        f"{percent_macro(numbers, name):.1f}"
        for name in (
            "AfourExactCycleFixedOrderWinRate",
            "AfourExactCycleSingleWriterWinRate",
            "AfourNonExactFixedOrderWinRate",
            "AfourNonExactSingleWriterWinRate",
        )
    ]
    assert percentages(tabular_body(trace)) == expected_trace, (
        "tab/trace-outcome.tex: displayed rates are stale relative to numbers.tex"
    )
    expected_p = [
        f"{numeric_macro(numbers, 'AfourFixedOrderCycleSplitP'):.2f}",
        f"{numeric_macro(numbers, 'AfourSingleWriterCycleSplitP'):.2f}",
    ]
    fisher_row = tabular_body(trace).split("Fisher $p$", 1)[1].split(r"\\", 1)[0]
    displayed_p = re.findall(r"&\s*(\d+\.\d+)", fisher_row)
    assert displayed_p == expected_p, ("tab/trace-outcome.tex: Fisher p-values are stale relative to numbers.tex", displayed_p, expected_p)

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

    print("Table-style guards: passed")


if __name__ == "__main__":
    check()
