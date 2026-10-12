from __future__ import annotations

from agentic_cogwriter.analysis.trace_endings import analyze, summarize_run


def _switch(process: str, decision: str = "") -> dict:
    return {"event_type": "process_switch", "to_process": process, "decision": decision}


def test_runs_ending_before_reviewing_and_fallback_are_counted() -> None:
    runs = [
        summarize_run([_switch("planning"), _switch("translating"), _switch("reviewing")], "reviewing"),
        summarize_run([_switch("planning"), _switch("translating")], "reviewing"),
        summarize_run([_switch("planning", "Delegation unavailable; use the documented fallback.")], "planning"),
    ]
    report = analyze(runs)
    assert report["last_logged_process"] == {"planning": 1, "reviewing": 1, "translating": 1}
    assert report["ending_before_reviewing"] == 2
    assert report["ending_before_reviewing_last_delegated_reviewer"] == 1
    assert report["fallback_recorded_runs"] == 1
