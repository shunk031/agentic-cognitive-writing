"""Append-only trace writing, validation, and artifact hashing."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .errors import TraceValidationError
from .hashing import sha256_file

TRACE_EVENT_TYPES = frozenset(
    {
        "process_switch",
        "goal_created",
        "goal_developed",
        "goal_regenerated",
    }
)
GOAL_EVENT_TYPES = frozenset({"goal_created", "goal_developed", "goal_regenerated"})
BASE_TRACE_FIELDS = (
    "timestamp",
    "responsible_agent",
    "process",
    "decision",
    "evidence",
    "open_uncertainty",
)


def timestamp() -> str:
    """Return a timezone-aware ISO 8601 timestamp."""

    return datetime.now(UTC).isoformat()


def _read_trace_events(path: Path) -> list[dict[str, Any]]:
    """Read trace lines as objects and retain line numbers for diagnostics."""

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise TraceValidationError(f"Cannot read trace {path}: {exc}") from exc
    if not lines:
        raise TraceValidationError(f"Trace {path} is empty")
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            raise TraceValidationError(f"Trace {path}:{line_number} is blank")
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TraceValidationError(
                f"Trace {path}:{line_number} is not standalone JSON: {exc}"
            ) from exc
        if not isinstance(value, dict):
            raise TraceValidationError(
                f"Trace {path}:{line_number} must contain an object"
            )
        events.append(value)
    return events


def validate_trace(
    path: Path,
    *,
    condition_id: str,
    declared_processes: tuple[str, ...],
    goal_events: str = "allowed",
    allowed_event_types: tuple[str, ...] = tuple(TRACE_EVENT_TYPES),
    min_events: int = 1,
    max_events: int | None = None,
    process_order: tuple[str, ...] | None = None,
    require_goal_events: bool = False,
) -> list[dict[str, Any]]:
    """Validate event fields and the wrapper-declared trace contract."""

    if not declared_processes:
        raise TraceValidationError(
            f"{condition_id} must declare at least one trace process"
        )
    if goal_events not in {"allowed", "forbidden"}:
        raise TraceValidationError(
            f"{condition_id} has an invalid goal event policy: {goal_events!r}"
        )
    if min_events < 1 or (max_events is not None and max_events < min_events):
        raise TraceValidationError(f"{condition_id} has invalid event count bounds")
    allowed = set(allowed_event_types)
    if not allowed or not allowed <= TRACE_EVENT_TYPES:
        raise TraceValidationError(
            f"{condition_id} has unsupported allowed trace event types"
        )
    if process_order is not None:
        if not process_order:
            raise TraceValidationError(f"{condition_id} has an empty process order")
        if any(process not in declared_processes for process in process_order):
            raise TraceValidationError(
                f"{condition_id} process order uses undeclared processes"
            )
    if require_goal_events and goal_events != "allowed":
        raise TraceValidationError(
            f"{condition_id} cannot require forbidden goal events"
        )
    events = _read_trace_events(path)
    if len(events) < min_events or (
        max_events is not None and len(events) > max_events
    ):
        limit = (
            f"at most {max_events}"
            if max_events is not None
            else "at least the minimum"
        )
        raise TraceValidationError(
            f"{condition_id} requires {min_events} events and {limit}; "
            f"observed {len(events)}"
        )
    goal_event_count = 0
    observed_processes: list[str] = []
    for line_number, event in enumerate(events, start=1):
        event_type = event.get("event_type")
        if not isinstance(event_type, str) or event_type not in allowed:
            raise TraceValidationError(
                f"Trace {path}:{line_number} event_type {event_type!r} is not "
                f"allowed for {condition_id}"
            )
        missing = [field for field in BASE_TRACE_FIELDS if field not in event]
        if missing:
            raise TraceValidationError(
                f"Trace {path}:{line_number} is missing {', '.join(missing)}"
            )
        for field in ("timestamp", "responsible_agent", "process", "decision"):
            if not isinstance(event[field], str) or not event[field].strip():
                raise TraceValidationError(
                    f"Trace {path}:{line_number} field {field} must be a string"
                )
        if event["process"] not in declared_processes:
            raise TraceValidationError(
                f"Trace {path}:{line_number} process {event['process']!r} is not "
                f"declared for {condition_id}"
            )
        observed_processes.append(event["process"])
        for field in ("evidence", "open_uncertainty"):
            if not isinstance(event[field], list):
                raise TraceValidationError(
                    f"Trace {path}:{line_number} field {field} must be an array"
                )
        if "artifacts" in event and not isinstance(event["artifacts"], list):
            raise TraceValidationError(
                f"Trace {path}:{line_number} field artifacts must be an array"
            )

        if event_type == "process_switch":
            for field in ("from_process", "to_process"):
                if field not in event:
                    raise TraceValidationError(
                        f"Trace {path}:{line_number} process_switch needs {field}"
                    )
                if event[field] is not None and not isinstance(event[field], str):
                    raise TraceValidationError(
                        f"Trace {path}:{line_number} process_switch needs {field}"
                    )
                if isinstance(event.get(field), str) and not event[field].strip():
                    raise TraceValidationError(
                        f"Trace {path}:{line_number} process_switch needs {field}"
                    )
                if event[field] is not None and event[field] not in declared_processes:
                    raise TraceValidationError(
                        f"Trace {path}:{line_number} process_switch {field} "
                        f"{event[field]!r} is not declared for {condition_id}"
                    )
        has_goal_fields = any(field in event for field in ("goal_id", "parent_goal_id"))
        if goal_events == "forbidden" and (
            event_type in GOAL_EVENT_TYPES or has_goal_fields
        ):
            raise TraceValidationError(
                f"{condition_id} forbids goal events and goal fields"
            )
        if event_type in GOAL_EVENT_TYPES:
            goal_event_count += 1
            _validate_goal_fields(event, path=path, line_number=line_number)
        elif has_goal_fields and goal_events == "allowed":
            _validate_goal_fields(event, path=path, line_number=line_number)

    if process_order is not None:
        expected_transitions = [
            (None, process_order[0]),
            *zip(process_order, process_order[1:], strict=False),
        ]
        observed_transitions = [
            (event["from_process"], event["to_process"]) for event in events
        ]
        if observed_transitions != expected_transitions:
            raise TraceValidationError(
                f"{condition_id} process transition order mismatch: expected "
                f"{tuple(expected_transitions)}, observed {tuple(observed_transitions)}"
            )
        if observed_processes != list(process_order):
            raise TraceValidationError(
                f"{condition_id} process order mismatch: expected {process_order}, "
                f"observed {tuple(observed_processes)}"
            )
        if any(event["process"] != event["to_process"] for event in events):
            raise TraceValidationError(
                f"{condition_id} process values must match transition destinations"
            )
    if require_goal_events and goal_event_count == 0:
        raise TraceValidationError(f"{condition_id} requires at least one goal event")
    return events


def _validate_goal_fields(
    event: dict[str, Any], *, path: Path, line_number: int
) -> None:
    """Validate conditional goal identifiers for goal-aware conditions."""

    for field in ("goal_id", "parent_goal_id"):
        if field not in event:
            raise TraceValidationError(
                f"Trace {path}:{line_number} goal-aware event needs {field}"
            )
    if not isinstance(event["goal_id"], str) or not event["goal_id"].strip():
        raise TraceValidationError(
            f"Trace {path}:{line_number} goal_id must be a string"
        )
    if event["parent_goal_id"] is not None and not isinstance(
        event["parent_goal_id"], str
    ):
        raise TraceValidationError(
            f"Trace {path}:{line_number} parent_goal_id must be a string or null"
        )


def assert_untouched(path: Path, before: bytes | None) -> None:
    """Reject a file created or changed by a condition that must leave it alone."""

    after = path.read_bytes() if path.is_file() else None
    if after != before:
        raise TraceValidationError(f"Condition changed protected file {path.name}")


def collect_plugin_trace(source_root: Path, run_root: Path) -> list[str]:
    """Copy plugin-owned trace and state files without synthesizing events."""

    copied: list[str] = []
    for relative in (
        Path(".writing/trace/process.jsonl"),
        Path(".writing/goals.md"),
        Path(".writing/draft.md"),
    ):
        source = source_root / relative
        if source.is_file():
            destination = run_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            copied.append(relative.as_posix())
    return copied


def checksums_for_files(root: Path, relative_paths: list[str]) -> dict[str, str]:
    """Hash named run artifacts with a stable ``sha256:`` prefix."""

    return {
        relative: f"sha256:{sha256_file(root / relative)}"
        for relative in relative_paths
        if (root / relative).is_file()
    }
