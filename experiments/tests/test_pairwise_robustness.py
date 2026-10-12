from __future__ import annotations

import math

from agentic_cogwriter.analysis.length_control import PairObservation
from agentic_cogwriter.analysis.pairwise_robustness import (
    cohen_kappa,
    fit_logistic,
    prompt_level_summary,
)


def _pair(prompt: str, verdict: str) -> PairObservation:
    return PairObservation(
        benchmark="WritingBench",
        prompt=prompt,
        judge_id="judge",
        left_condition="A4",
        right_condition="A1",
        left_length=100,
        right_length=100,
        verdict=verdict,
    )


def test_prompt_level_summary_averages_each_prompt_over_runs() -> None:
    rows = [
        _pair("p1", "left"),
        _pair("p1", "tie"),  # p1 mean 0.75: a prompt-level win
        _pair("p2", "right"),
        _pair("p2", "left"),  # p2 mean 0.5: a prompt-level tie
        _pair("p3", "right"),  # p3 mean 0.0: a prompt-level loss
    ]
    summary = prompt_level_summary(rows)
    assert summary["prompts"] == 3
    assert math.isclose(summary["rate"], (0.75 + 0.5 + 0.0) / 3)
    assert (summary["prompt_wins"], summary["prompt_losses"], summary["prompt_ties"]) == (1, 1, 1)
    assert summary["sign_test_p"] == 1.0


def test_fit_logistic_recovers_intercept_and_slope() -> None:
    points = []
    for x in (-1.0, -0.5, 0.0, 0.5, 1.0):
        p = 1 / (1 + math.exp(-(0.4 + 2.0 * x)))
        wins = round(1000 * p)
        points += [(x, 1)] * wins + [(x, 0)] * (1000 - wins)
    intercept, slope = fit_logistic(points)
    assert math.isclose(intercept, 0.4, abs_tol=0.01)
    assert math.isclose(slope, 2.0, abs_tol=0.02)


def test_cohen_kappa_corrects_for_chance_agreement() -> None:
    assert cohen_kappa([("left", "left"), ("right", "right")]) == 1.0
    pairs = [("left", "left"), ("left", "right"), ("right", "left"), ("right", "right")]
    assert cohen_kappa(pairs) == 0.0
