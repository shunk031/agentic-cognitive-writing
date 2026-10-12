import json

from agentic_cogwriter.analysis.delegation_fallback import (
    contrast_summary,
    fallback_recorded,
    summarize,
)


def test_fallback_recorded_reads_trace_decisions(tmp_path) -> None:
    trace = tmp_path / "process.jsonl"
    events = [
        {"event_type": "process_switch", "decision": "Planner unavailable; Monitor fallback."},
        {"event_type": "goal_created", "decision": "Draft the opening."},
    ]
    trace.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    assert fallback_recorded(trace)
    trace.write_text(json.dumps(events[1]) + "\n")
    assert not fallback_recorded(trace)


def test_summary_averages_per_run_rates_and_drops_fallback_pairs() -> None:
    rows = [
        {"run": "run-1", "left": "A4", "right": "A6", "verdict": "left", "left_fallback": False, "right_fallback": False},
        {"run": "run-1", "left": "A4", "right": "A6", "verdict": "right", "left_fallback": False, "right_fallback": True},
        {"run": "run-2", "left": "A4", "right": "A6", "verdict": "left", "left_fallback": True, "right_fallback": False},
    ]
    assert summarize(rows)["rate_mean_over_runs"] == 0.75
    kept = contrast_summary(rows)["A4:A6"]["without_fallback"]
    assert (kept["wins"], kept["losses"], kept["pairs"]) == (1, 0, 1)
