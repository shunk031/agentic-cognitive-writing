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
        "stage_event",
        "generation",
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
) -> list[dict[str, Any]]:
    """Validate event fields and the condition-specific trace contract."""

    if not declared_processes:
        raise TraceValidationError(
            f"{condition_id} must declare at least one trace process"
        )
    events = _read_trace_events(path)
    goal_event_count = 0
    observed_processes: list[str] = []
    for line_number, event in enumerate(events, start=1):
        event_type = event.get("event_type")
        if not isinstance(event_type, str) or event_type not in TRACE_EVENT_TYPES:
            raise TraceValidationError(
                f"Trace {path}:{line_number} has unknown event_type {event_type!r}"
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
        if event_type in GOAL_EVENT_TYPES:
            goal_event_count += 1
            _validate_goal_fields(event, path=path, line_number=line_number)
    if condition_id in {"A1", "A2", "B1", "B2"}:
        if len(events) != len(declared_processes):
            raise TraceValidationError(
                f"{condition_id} requires {len(declared_processes)} events, "
                f"observed {len(events)}"
            )
        if observed_processes != list(declared_processes):
            raise TraceValidationError(
                f"{condition_id} process order mismatch: "
                f"expected {declared_processes}, "
                f"observed {tuple(observed_processes)}"
            )
        if goal_event_count:
            raise TraceValidationError(f"{condition_id} must not contain goal events")
    elif condition_id in {"A3", "A4", "A5", "A6"} and not events:
        raise TraceValidationError(f"{condition_id} requires at least one event")
    if condition_id == "A3" and set(declared_processes) != {
        "task-decomposition",
        "task-execution",
        "task-revision",
    }:
        raise TraceValidationError(
            "A3 must declare task-decomposition, task-execution, and task-revision"
        )
    if condition_id in {"A4", "A6"} and goal_event_count == 0:
        raise TraceValidationError(
            f"{condition_id} requires goal fields in goal events"
        )
    if condition_id in {"A5", "B1", "B2"}:
        if goal_event_count:
            raise TraceValidationError(f"{condition_id} must not contain goal events")
        if any(
            field in event
            for event in events
            for field in ("goal_id", "parent_goal_id")
        ):
            raise TraceValidationError(f"{condition_id} must not contain goal fields")
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
