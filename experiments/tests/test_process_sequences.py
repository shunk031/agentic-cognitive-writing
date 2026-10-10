from __future__ import annotations

import json

from agentic_cogwriter.analysis.process_sequences import (
    _first_delegated_process,
    analyze_trace_events,
    fisher_exact_two_sided,
    read_fixed_order,
    summarize_observations,
)


def _switch(
    process: str,
    from_process: str | None,
    to_process: str | None,
) -> dict[str, object]:
    return {
        "event_type": "process_switch",
        "process": process,
        "from_process": from_process,
        "to_process": to_process,
    }


def _goal_regenerated(process: str = "reviewing") -> dict[str, object]:
    return {
        "event_type": "goal_regenerated",
        "process": process,
        "goal_id": "G2",
        "parent_goal_id": "G0",
    }


def test_trace_observation_keeps_process_switch_destinations_and_locations() -> None:
    exact = [
        _switch("planning", None, "planning"),
        _switch("translating", "planning", "translating"),
        _switch("reviewing", "translating", "reviewing"),
        _switch("reviewing", "reviewing", None),
    ]
    observed = analyze_trace_events(
        exact, fixed_order=("planning", "translating", "reviewing")
    )

    assert observed["sequence"] == ["planning", "translating", "reviewing"]
    assert observed["sequence_length"] == 3
    assert observed["single_cycle_exact"] is True
    assert observed["matches_fixed_order_up_to_single_process_repetition"] is True
    assert observed["transitions"] == {
        "START->planning": 1,
        "planning->translating": 1,
        "translating->reviewing": 1,
        "reviewing->END": 1,
    }
    assert observed["after_reviewing"] == {
        "planning": 0,
        "translating": 0,
        "reviewing": 0,
        "termination": 1,
    }
    assert observed["regeneration"]["count"] == 0


def test_summary_distinguishes_non_linear_return_and_regeneration() -> None:
    non_linear = [
        _switch("planning", None, "planning"),
        _switch("translating", "planning", "translating"),
        _switch("reviewing", "translating", "reviewing"),
        _goal_regenerated(),
        _switch("planning", "reviewing", "planning"),
        _switch("translating", "planning", "translating"),
        _switch("reviewing", "translating", "reviewing"),
        _switch("reviewing", "reviewing", None),
    ]
    observed = analyze_trace_events(
        non_linear, fixed_order=("planning", "translating", "reviewing")
    )
    summary = summarize_observations([observed])

    assert observed["sequence"] == [
        "planning",
        "translating",
        "reviewing",
        "planning",
        "translating",
        "reviewing",
    ]
    assert observed["single_cycle_exact"] is False
    assert observed["matches_fixed_order_up_to_single_process_repetition"] is False
    assert observed["after_reviewing"] == {
        "planning": 1,
        "translating": 0,
        "reviewing": 0,
        "termination": 1,
    }
    assert observed["regeneration"]["count"] == 1
    assert observed["regeneration"]["locations"] == [
        {
            "event_process": "reviewing",
            "active_process": "reviewing",
            "sequence_index": 3,
        }
    ]
    assert summary["run_count"] == 1
    assert summary["single_cycle_exact"] == {"count": 0, "total": 1, "rate": 0.0}
    assert summary["single_process_repetition"] == {"count": 0, "total": 1, "rate": 0.0}
    assert summary["after_reviewing"] == {
        "planning": {"count": 1, "total": 2, "rate": 0.5},
        "translating": {"count": 0, "total": 2, "rate": 0.0},
        "reviewing": {"count": 0, "total": 2, "rate": 0.0},
        "termination": {"count": 1, "total": 2, "rate": 0.5},
        "total": 2,
        "per_run": {
            "planning": {"count": 1, "total": 1, "rate": 1.0},
            "translating": {"count": 0, "total": 1, "rate": 0.0},
            "reviewing": {"count": 0, "total": 1, "rate": 0.0},
            "termination": {"count": 1, "total": 1, "rate": 1.0},
            "total": 1,
            "categories_overlap": True,
        },
    }


def test_cycle_compliance_collapses_repeats_and_reconstructs_leading_planning(
    tmp_path,
) -> None:
    two_pass = [
        _switch("planning", None, "planning"),
        _switch("translating", "planning", "translating"),
        _switch("reviewing", "translating", "reviewing"),
        _switch("reviewing", "reviewing", "reviewing"),
        _switch("planning", "reviewing", "planning"),
        _switch("translating", "planning", "translating"),
        _switch("reviewing", "translating", "reviewing"),
        _switch("reviewing", "reviewing", None),
    ]
    observed = analyze_trace_events(
        two_pass, fixed_order=("planning", "translating", "reviewing")
    )
    assert observed["cycle_compliant"] is True
    assert observed["cycle_passes"] == 2
    assert observed["collapsed_sequence"] == [
        "planning",
        "translating",
        "reviewing",
        "planning",
        "translating",
        "reviewing",
    ]

    missing_leading = [
        _switch("planning", "planning", "translating"),
        _switch("reviewing", "translating", "reviewing"),
        _switch("reviewing", "reviewing", None),
    ]
    reconstructed = analyze_trace_events(
        missing_leading,
        fixed_order=("planning", "translating", "reviewing"),
        first_delegated_process="planning",
    )
    assert reconstructed["sequence"] == ["translating", "reviewing"]
    assert reconstructed["sequence_for_cycle_compliance"] == [
        "planning",
        "translating",
        "reviewing",
    ]
    assert reconstructed["leading_process"]["reconstructed"] is True
    assert reconstructed["single_cycle_exact"] is True
    assert reconstructed["matches_fixed_order_up_to_single_process_repetition"] is True
    assert reconstructed["cycle_compliant"] is True
    assert reconstructed["cycle_passes"] == 1

    events_path = tmp_path / "attempt-001.events.jsonl"
    events_path.write_text(
        json.dumps(
            {
                "type": "item.started",
                "item": {
                    "type": "collab_tool_call",
                    "tool": "spawn_agent",
                    "prompt": "You are the Planning role agent.",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert _first_delegated_process(tmp_path) == "planning"


def test_cycle_compliance_rejects_reviewing_return_and_early_end() -> None:
    reviewing_to_translating = [
        _switch("planning", None, "planning"),
        _switch("translating", "planning", "translating"),
        _switch("reviewing", "translating", "reviewing"),
        _switch("translating", "reviewing", "translating"),
        _switch("reviewing", "translating", "reviewing"),
        _switch("reviewing", "reviewing", None),
    ]
    returned = analyze_trace_events(
        reviewing_to_translating,
        fixed_order=("planning", "translating", "reviewing"),
    )
    assert returned["cycle_compliant"] is False
    assert returned["cycle_passes"] is None
    assert returned["reviewing_to_translating"] is True

    ends_before_reviewing = [
        _switch("planning", None, "planning"),
        _switch("translating", "planning", "translating"),
        _switch("translating", "translating", None),
    ]
    early_end = analyze_trace_events(
        ends_before_reviewing,
        fixed_order=("planning", "translating", "reviewing"),
    )
    assert early_end["cycle_compliant"] is False
    assert early_end["cycle_passes"] is None


def test_fixed_order_is_read_from_condition_and_skill() -> None:
    order = read_fixed_order()

    assert order["canonical"] == ["planning", "translating", "reviewing"]
    assert order["condition_id"] == "A6"
    assert order["condition_processes"][:3] == ["planning", "generate", "organize"]
    assert (
        "fixed `Planning`, `Translating`, then `Reviewing` order" in order["skill_text"]
    )


def test_fisher_exact_two_sided_is_dependency_free() -> None:
    assert fisher_exact_two_sided([[1, 3], [3, 1]]) == 0.4857142857142857
