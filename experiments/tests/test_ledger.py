"""The ledger reader parses what the Monitor skills' logging script writes."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from agentic_cogwriter.analysis.ledger import ENTRY, parse_ledger, summarize

SCRIPT = (
    Path(__file__).parents[2]
    / "plugin/skills/agentic-cog-writer/scripts/writing_state.py"
)


def _script():
    spec = importlib.util.spec_from_file_location("writing_state", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reader_uses_the_script_entry_pattern() -> None:
    assert ENTRY.pattern == _script().LEDGER_ENTRY.pattern


def test_parse_ledger_reads_script_output() -> None:
    script = _script()
    decision = script.build_events(
        [
            {
                "event_type": "process_switch",
                "to_process": "planning",
                "regeneration_proposals": (
                    "G1.2 accepted (purpose; changed); G2 rejected (no evidence)"
                ),
                "decision": "Replace G1.2. Then plan.",
            }
        ],
        "reviewing",
        "2026-01-01T00:00:00+00:00",
    )[0]["decision"]
    assert parse_ledger(decision) == [
        {"goal_id": "G1.2", "outcome": "accepted", "reason": "purpose; changed"},
        {"goal_id": "G2", "outcome": "rejected", "reason": "no evidence"},
    ]
    assert parse_ledger("regeneration proposals: none. Stop.") == []
    assert parse_ledger("Draft the opening.") is None


def test_summarize_counts_ledgers_after_reviewing() -> None:
    events = [
        {"event_type": "process_switch", "from_process": None, "decision": "x"},
        {
            "event_type": "process_switch",
            "from_process": "reviewing",
            "decision": "regeneration proposals: none. Plan.",
        },
        {
            "event_type": "process_switch",
            "from_process": "reviewing",
            "decision": "regeneration proposals: G1 rejected (weak). Stop.",
        },
        {"event_type": "process_switch", "from_process": "reviewing", "decision": "x"},
    ]
    assert summarize(events) == {
        "ledgers": 2,
        "ledgers_with_proposal": 1,
        "missing_ledgers": 1,
        "accepted": 0,
        "rejected": 1,
    }
