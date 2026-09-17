from __future__ import annotations

import json
from pathlib import Path

from agentic_cogwriter.analysis.trace_audit import (
    decisive_outcome,
    render_trace,
    summarize_goal_faithfulness,
    summarize_localization,
    winner_condition,
)

FIXTURE = Path(__file__).parent / "fixtures" / "trace_audit.json"


def test_winner_condition_maps_both_presentations() -> None:
    assert winner_condition("A|B", "A") == "A4"
    assert winner_condition("A|B", "B") == "A5"
    assert winner_condition("B|A", "A") == "A5"
    assert winner_condition("B|A", "B") == "A4"


def test_decisive_outcome_requires_two_matching_records() -> None:
    assert (
        decisive_outcome(
            [
                {"presentation": "A|B", "winner": "A"},
                {"presentation": "B|A", "winner": "B"},
            ]
        )
        == "A4-win"
    )
    assert (
        decisive_outcome(
            [
                {"presentation": "A|B", "winner": "B"},
                {"presentation": "B|A", "winner": "A"},
            ]
        )
        == "A4-loss"
    )
    assert (
        decisive_outcome(
            [
                {"presentation": "A|B", "winner": "A"},
                {"presentation": "B|A", "winner": "A"},
            ]
        )
        is None
    )


def test_render_trace_keeps_requested_fields_compactly() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rendered = render_trace(fixture["events"])
    assert rendered == (
        "- 2026-01-01T00:00:00Z | goal_created | process=planning | "
        "decision=Create G1. | evidence=[assignment.md] | "
        "open_uncertainty=[Missing source.] | goal_id=G1 | parent_goal_id=G0"
    )


def test_summary_arithmetic_uses_goal_and_run_denominators() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    localization = summarize_localization(fixture["localization_records"])
    assert localization["A4"]["lost"] == {
        "n": 2,
        "anticipated": 0.5,
        "partially": 0.5,
    }
    assert localization["A4"]["won"] == {
        "n": 1,
        "anticipated": 0.0,
        "partially": 0.0,
    }

    goals = summarize_goal_faithfulness(
        fixture["goal_assessments"], fixture["run_ratings"]
    )
    assert goals == {
        "goal_count": 3,
        "satisfied": 2 / 3,
        "partially": 1 / 3,
        "runs": 2,
        "all_goals_at_least_partially": 1.0,
    }
