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

    # Header and row-group separators are split column by column. Multi-column
    # cmidrules are reserved for genuine grouped headers created with
    # \multicolumn; broad 1--N rules are intentionally disallowed. Counts track
    # the reader-facing schema, so removing a run-specific column requires the
    # guard to follow the replacement table rather than preserve a deleted field.
    expected_columns = {
        "tab/ablation-results.tex": [5],
        "tab/appendix-comparison.tex": [5],
        "tab/appendix-compute-control.tex": [5],
        "tab/appendix-cross-family.tex": [7],
        "tab/appendix-habermas.tex": [6],
        "tab/appendix-length-control.tex": [5],
        "tab/appendix-process.tex": [7],
        "tab/appendix-record-pooled-pairwise.tex": [5],
        "tab/appendix-runtime-settings.tex": [2],
        "tab/appendix-single-context.tex": [7, 4],
        "tab/architecture-comparison.tex": [5],
        "tab/experiments-architecture-comparison.tex": [5],
        "tab/main-results.tex": [7],
        "tab/pairwise-results.tex": [5],
        "tab/process-dynamics.tex": [2],
        "tab/trace-outcome.tex": [3],
    }
    allowed_group_spans = {
        "tab/main-results.tex": {(2, 3), (4, 5), (6, 7)},
        "tab/pairwise-results.tex": {(2, 5)},
        "tab/ablation-results.tex": {(2, 5)},
        "tab/trace-outcome.tex": {(2, 3)},
    }
    rule_pattern = re.compile(r"\\cmidrule\(lr\)\{(\d+)-(\d+)\}")

    for relative_path, column_counts in expected_columns.items():
        text = read(relative_path)
        tabulars = re.findall(
            r"\\begin\{tabular\}\{.*?\}(.*?)\\end\{tabular\}",
            text,
            flags=re.DOTALL,
        )
        assert len(tabulars) == len(column_counts), (
            f"{relative_path}: expected {len(column_counts)} tabular(s), got {len(tabulars)}"
        )
        for index, (tabular, column_count) in enumerate(zip(tabulars, column_counts), start=1):
            assert r"\midrule" not in tabular, (
                f"{relative_path} tabular {index}: use \\cmidrule for header and row-group separators"
            )
            for column in range(1, column_count + 1):
                rule = rf"\cmidrule(lr){{{column}-{column}}}"
                assert rule in tabular, (
                    f"{relative_path} tabular {index}: missing column-wise {rule}"
                )
            for match in rule_pattern.finditer(tabular):
                start, end = map(int, match.groups())
                if start == end:
                    continue
                assert (start, end) in allowed_group_spans.get(relative_path, set()), (
                    f"{relative_path} tabular {index}: broad \\cmidrule(lr){{{start}-{end}}} is not a grouped header; "
                    "split separators column by column"
                )

    # Table 1 keeps each comparison-axis label to two rendered lines. Longer
    # prose belongs in the caption or surrounding Related Work discussion.
    comparison = read("tab/appendix-comparison.tex")
    comparison_header = comparison.split(r"\toprule", 1)[1].split(r"\cmidrule", 1)[0]
    for header_cell in (
        r"\ccell{\textbf{Unit of}\\\textbf{progress}}",
        r"\ccell{\textbf{Adaptive}\\\textbf{next step}}",
        r"\ccell{\textbf{Evolving}\\\textbf{structure}}",
        r"\ccell{\textbf{Online process}\\\textbf{selection}}",
    ):
        assert header_cell in comparison_header, (
            "tab/appendix-comparison.tex: keep Table 1 comparison headers to two lines",
            header_cell,
        )
    for old_header in (
        "Explicit planning structure",
        "Persistent writing state",
        "Adaptive next-step selection",
        "Evolving control structure",
        "Online writing-operation selection",
    ):
        assert old_header not in comparison_header, (
            "tab/appendix-comparison.tex: do not restore long Table 1 headers",
            old_header,
        )

    # Numeric columns are right-aligned. Text columns remain left-aligned.
    expected_specs = {
        "tab/main-results.tex": "lrrrrrr",
        "tab/pairwise-results.tex": "lrrrr",
        "tab/ablation-results.tex": "lrrrr",
        "tab/process-dynamics.tex": "lr",
        "tab/trace-outcome.tex": "lrr",
        "tab/appendix-length-control.tex": "llrrr",
        "tab/appendix-process.tex": "lrrrrrr",
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
    assert len(main_values) == 40, ("tab/main-results.tex: unexpected number of displayed scores", len(main_values))
    assert_fixed_decimals(main_values, 3, "tab/main-results.tex")
    expected_main: list[str] = []
    for condition in ("SinglePass", "Staged", "TaskPlanning", "Full"):
        for cell in (f"Writing{condition}Native", f"Writing{condition}Pointwise", f"Hello{condition}Native", f"Hello{condition}Pointwise", f"DoLo{condition}Pointwise"):
            expected_main.extend(f"{numeric_macro(numbers, f'ThreeRun{cell}{stat}'):.3f}" for stat in ("Mean", "SD"))
    assert main_values == expected_main, ("tab/main-results.tex: displayed scores are stale relative to numbers.tex", main_values, expected_main)
    assert "Bold marks the highest mean in each column." in main
    assert tabular_body(main).count(r"\tnote{\dag}") == main.count(r"\textcolor{tiedgray}"), "tab/main-results.tex: every gray leader carries the dagger note"
    assert main.count(r"\uparrow") == 6, "tab/main-results.tex: mark every score column as higher-is-better"
    assert "divided by 10" not in main, "tab/main-results.tex: keep display-rescaling detail out of the caption"

    # Win-rate tables use one decimal place, including values that round to an integer.
    for path, text, count in (
        ("tab/pairwise-results.tex", pairwise, 12),
        ("tab/ablation-results.tex", ablation, 12),
    ):
        values = percentages(tabular_body(text))
        assert len(values) == count, (f"{path}: unexpected number of displayed rates", len(values))
        assert_fixed_decimals(values, 1, path)
        assert r"\%" in text

    # Table 4 and Table 5 values come from the generated three-run macros rather
    # than stale literals. The `Across` cells are the mean of the three run-level
    # rates after summing benchmark wins and losses within each run.
    for path, comparisons in (
        ("tab/pairwise-results.tex", (("FourOne", "FullSinglePass"), ("FourTwo", "FullStaged"), ("FourThree", "FullTaskPlanning"))),
        ("tab/ablation-results.tex", (("FourFive", "FullNoGoals"), ("FourSix", "FullFixedOrder"), ("FourSeven", "FullSingleWriter"))),
    ):
        body = tabular_body(read(path))
        for old_suffix, new_suffix in comparisons:
            assert f"\\DoLo{old_suffix}RateMean" not in body
            assert f"\\Hello{old_suffix}RateMean" not in body
            assert f"\\Writing{old_suffix}RateMean" not in body
            for benchmark in ("DoLo", "Hello", "Writing"):
                assert f"\\ThreeRun{benchmark}{new_suffix}RateMean" in body
            assert f"\\ThreeRunAcross{new_suffix}RateMean" in body

    # Table 6 reports a partition plus non-exclusive indicators. The first two
    # rows sum to 100%; later rows are behavioral rates and need not sum with them.
    process_values = percentages(tabular_body(process))
    assert_fixed_decimals(process_values, 1, "tab/process-dynamics.tex")
    assert "Cycle-compliant P$\\rightarrow$T$\\rightarrow$R path" in process
    assert "Any other complete process path" in process
    assert "Review followed by renewed Translating" in process
    assert "Review followed by renewed Planning" in process
    assert "Accepted goal replacement" in process
    assert r"\AfourCycleCompliantRate" in process
    assert r"\AfourCycleNonCompliantRate" in process
    assert r"\AfourReviewingToTranslatingRate" in process
    assert r"\AfourReviewingToPlanningRate" in process
    assert r"\AfourGoalReplacementRate" in process
    assert abs(percent_macro(numbers, "AfourCycleCompliantRate") + percent_macro(numbers, "AfourCycleNonCompliantRate") - 100.0) < 1e-9

    # Table 7's four rate cells are generated from the same three-run process
    # analysis as the narrative rather than preserving earlier hard-coded values.
    trace_body = tabular_body(trace)
    for macro in (
        r"\AfourExactCycleFixedOrderWinRate",
        r"\AfourExactCycleSingleWriterWinRate",
        r"\AfourNonExactFixedOrderWinRate",
        r"\AfourNonExactSingleWriterWinRate",
    ):
        assert macro in trace_body, ("tab/trace-outcome.tex: missing generated three-run rate macro", macro)
    assert not percentages(trace_body), "tab/trace-outcome.tex: do not hard-code percentage values"

    # All table captions identify the best-score convention where relevant.
    for path in ("tab/main-results.tex", "tab/pairwise-results.tex", "tab/ablation-results.tex"):
        text = read(path)
        assert "Best scores in bold." in text or "Bold marks the highest mean in each column." in text


if __name__ == "__main__":
    check()
