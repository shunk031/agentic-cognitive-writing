from __future__ import annotations

from agentic_cogwriter.analysis.length_control import (
    PairObservation,
    analyze_pairs,
    collapse_verdict,
    length_ratio,
    ratio_bin,
    summarize_outcomes,
)


def _pair(
    left_length: int,
    right_length: int,
    verdict: str,
    *,
    left: str = "A4",
    right: str = "A1",
) -> PairObservation:
    return PairObservation(
        benchmark="WritingBench",
        prompt="p1",
        judge_id="judge",
        left_condition=left,
        right_condition=right,
        left_length=left_length,
        right_length=right_length,
        verdict=verdict,
    )


def test_collapse_requires_agreement_between_presentations() -> None:
    assert collapse_verdict(("A4", "A4"), "A4", "A1") == "left"
    assert collapse_verdict(("A1", "A1"), "A4", "A1") == "right"
    assert collapse_verdict(("A4", "A1"), "A4", "A1") == "tie"


def test_length_ratio_is_longer_over_shorter() -> None:
    assert length_ratio(100, 80) == 1.25
    assert length_ratio(80, 100) == 1.25


def test_outcome_summary_uses_focal_condition_and_excludes_length_ties() -> None:
    rows = [
        _pair(120, 100, "left"),
        _pair(100, 120, "left"),
        _pair(100, 100, "right"),
        _pair(120, 100, "tie"),
    ]

    summary = summarize_outcomes(rows, focal_condition="A4", longer_side=True)

    assert summary["pairs"] == 3
    assert summary["wins"] == 1
    assert summary["losses"] == 1
    assert summary["ties"] == 1
    assert summary["equal_length_pairs"] == 1
    assert summary["win_rate"] == 0.5


def test_ratio_bin_boundaries_are_stable() -> None:
    assert ratio_bin(1.0) == "1.00-1.05"
    assert ratio_bin(1.05) == "1.05-1.10"
    assert ratio_bin(1.10) == "1.10-1.25"
    assert ratio_bin(1.25) == "1.25-1.50"
    assert ratio_bin(1.50) == "1.50-2.00"
    assert ratio_bin(2.0) == "2.00+"


def test_outcome_summary_handles_large_exact_sign_test_samples() -> None:
    rows = [_pair(120, 100, "left") for _ in range(550)]
    rows.extend(_pair(100, 120, "left") for _ in range(450))

    summary = summarize_outcomes(rows, focal_condition="A4")

    assert summary["n_non_tie"] == 1000
    assert 0 < summary["sign_test_p"] < 1


def test_analysis_reports_single_writer_pairs_at_least_ten_percent_shorter() -> None:
    rows = [
        _pair(90, 100, "left", left="A7", right="A1"),
        _pair(91, 100, "right", left="A7", right="A1"),
        _pair(100, 100, "left", left="A7", right="A1"),
        _pair(80, 100, "tie", left="A7", right="A1"),
    ]

    summary = analyze_pairs(rows)["single_writer_at_least_10_percent_shorter"]

    assert summary["pairs"] == 2
    assert summary["wins"] == 1
    assert summary["losses"] == 0
    assert summary["ties"] == 1
