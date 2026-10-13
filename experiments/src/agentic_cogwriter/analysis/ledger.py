"""Read the post-Reviewing regeneration ledger from Monitor traces.

The Monitor skills' logging script writes the ledger at the start of the
decision of the first process switch after each ``reviewing`` step, as
``regeneration proposals: none.`` or ``regeneration proposals: G1.2 accepted
(<reason>); G2 rejected (<reason>).``, followed by the rest of the decision.
The entry pattern below is the one the script validates.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

PREFIX = "regeneration proposals: "
ENTRY = re.compile(r"(G\d+(?:\.\d+)*) (accepted|rejected) \((.+)\)")
SPLIT = re.compile(r";\s*(?=G\d+(?:\.\d+)* (?:accepted|rejected) \()")


def _entries(value: str) -> list[dict[str, str]] | None:
    entries = []
    for part in SPLIT.split(value):
        match = ENTRY.fullmatch(part.strip())
        if match is None:
            return None
        entries.append({"goal_id": match[1], "outcome": match[2], "reason": match[3]})
    return entries


def parse_ledger(decision: str) -> list[dict[str, str]] | None:
    """Return the ledger's entries, ``[]`` for ``none``, or None without a ledger.

    The ledger ends at the first ``).`` (or ``none.``) after which the entries
    parse; a reason that itself contains ``).`` is cut at that point.
    """

    if not decision.startswith(PREFIX):
        return None
    body = decision[len(PREFIX) :]
    if re.match(r"none\.(?:\s|$)", body):
        return []
    for match in re.finditer(r"\)\.(?:\s|$)", body):
        entries = _entries(body[: match.start() + 1])
        if entries is not None:
            return entries
    return None


def ledgers(events: Iterable[Mapping[str, Any]]) -> list[list[dict[str, str]] | None]:
    """Return one parsed ledger per process switch that leaves ``reviewing``."""

    return [
        parse_ledger(str(event.get("decision", "")))
        for event in events
        if event.get("event_type") == "process_switch"
        and event.get("from_process") == "reviewing"
    ]


def summarize(events: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """Count ledgers, ledgers with a proposal, missing ledgers, and outcomes."""

    parsed = ledgers(events)
    entries = [entry for ledger in parsed if ledger for entry in ledger]
    return {
        "ledgers": sum(ledger is not None for ledger in parsed),
        "ledgers_with_proposal": sum(bool(ledger) for ledger in parsed),
        "missing_ledgers": sum(ledger is None for ledger in parsed),
        "accepted": sum(entry["outcome"] == "accepted" for entry in entries),
        "rejected": sum(entry["outcome"] == "rejected" for entry in entries),
    }
