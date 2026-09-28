from __future__ import annotations

from agentic_cogwriter.analysis.process_sequences import (
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
    assert observed["equals_fixed_order"] is True
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
    assert observed["equals_fixed_order"] is False
    assert observed["matches_fixed_order_up_to_single_process_repetition"] is False
    assert observed["after_reviewing"] == {
        "planning": 1,
        "translating": 0,
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
    assert summary["exact_fixed_order"] == {"count": 0, "total": 1, "rate": 0.0}
    assert summary["single_process_repetition"] == {"count": 0, "total": 1, "rate": 0.0}


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
