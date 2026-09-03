"""Headless process execution and transport-output parsing."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ExecutionError, RetrievalViolation

RETRIEVAL_EVENT_TYPES = frozenset(
    {
        "web_search",
        "websearch",
        "web_search_call",
        "web_search_preview",
        "web_fetch",
        "browser",
        "browser_call",
        "browser_search",
        "browser_fetch",
        "mcp_tool_call",
        "network_request",
        "retrieval",
        "fetch",
        "wget",
        "curl",
        "httpie",
        "nc",
        "netcat",
        "socat",
        "ssh",
        "file_search",
        "file_search_call",
    }
)
COMMAND_EVENT_TYPES = frozenset(
    {
        "command_execution",
        "command_execution_started",
        "command_execution_completed",
        "command_execution_failed",
    }
)
GENERIC_TOOL_EVENT_TYPES = frozenset(
    {"tool_call", "function_call", "custom_tool_call", "tool_search_call"}
)
ERROR_EVENT_TYPES = frozenset(
    {"error", "error_event", "response_error", "response_failed", "turn_failed"}
)
NETWORK_COMMAND_PATTERN = (
    r"(?i)\b(?:curl|wget|fetch|httpie|nc|netcat|socat|ssh)\b|"
    r"\b(?:git\s+clone|python\s+-m\s+http\.client)\b|"
    r"\b(?:urllib|requests\.get|socket\.create_connection)\b"
)
_NETWORK_COMMAND_RE = re.compile(NETWORK_COMMAND_PATTERN)


@dataclass(frozen=True)
class ExecutionResult:
    """Captured output from one headless turn."""

    returncode: int
    stdout: bytes
    stderr: bytes
    session_id: str | None = None
    timed_out: bool = False


class SubprocessExecutor:
    """Run argv directly with one common timeout."""

    def run(
        self, command: list[str], *, cwd: Path, timeout_seconds: float
    ) -> ExecutionResult:
        """Execute one command without shell expansion."""

        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = (
                exc.stdout if isinstance(exc.stdout, bytes) else (exc.stdout or b"")
            )
            stderr = (
                exc.stderr if isinstance(exc.stderr, bytes) else (exc.stderr or b"")
            )
            return ExecutionResult(
                returncode=-1,
                stdout=stdout,
                stderr=stderr,
                session_id=extract_session_id(stdout + stderr),
                timed_out=True,
            )
        except OSError as exc:
            raise ExecutionError(f"Cannot execute {command[0]}: {exc}") from exc
        return ExecutionResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            session_id=extract_session_id(completed.stdout + completed.stderr),
        )


def _json_objects(data: bytes) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for line in data.decode("utf-8", errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            objects.append(value)
    return objects


def extract_token_usage(data: bytes) -> dict[str, int] | None:
    """Sum generated-token usage reported by Codex turn-completion events."""

    totals = {
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
        "total_tokens": 0,
    }
    observed = False
    for value in _json_objects(data):
        if value.get("type") != "turn.completed":
            continue
        usage = value.get("usage")
        if not isinstance(usage, dict):
            continue
        output_tokens = usage.get("output_tokens")
        reasoning_tokens = usage.get("reasoning_output_tokens", 0)
        if (
            isinstance(output_tokens, bool)
            or not isinstance(output_tokens, int)
            or output_tokens < 0
            or isinstance(reasoning_tokens, bool)
            or not isinstance(reasoning_tokens, int)
            or reasoning_tokens < 0
        ):
            continue
        totals["output_tokens"] += output_tokens
        totals["reasoning_output_tokens"] += reasoning_tokens
        totals["total_tokens"] += output_tokens + reasoning_tokens
        observed = True
    return totals if observed else None


def extract_output(data: bytes) -> str:
    """Extract the model's final text while leaving transport bytes untouched."""

    decoded = data.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(decoded)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        for key in ("result", "text", "message"):
            if isinstance(parsed.get(key), str):
                return parsed[key]
    candidates: list[str] = []
    for value in _json_objects(data):
        item = value.get("item")
        if isinstance(item, dict) and item.get("type") in {
            "agent_message",
            "assistant_message",
        }:
            text = item.get("text")
            if isinstance(text, str):
                candidates.append(text)
        for key in ("result", "text"):
            if isinstance(value.get(key), str):
                candidates.append(value[key])
    return candidates[-1] if candidates else decoded


def extract_session_id(data: bytes) -> str | None:
    """Extract a resumable top-level session identifier from CLI JSONL."""

    for value in _json_objects(data):
        for key in ("session_id", "thread_id"):
            session_id = value.get(key)
            if isinstance(session_id, str) and session_id.strip():
                return session_id
        nested = value.get("thread")
        if isinstance(nested, dict):
            session_id = nested.get("id")
            if isinstance(session_id, str) and session_id.strip():
                return session_id
    return None


def _event_name(value: str) -> str:
    """Normalize an event or tool name without matching substrings."""

    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _subagent_spawn_ids(data: bytes) -> set[str]:
    """Return unique Codex collaboration spawn item IDs from JSONL events."""

    spawn_ids: set[str] = set()
    for value in _json_objects(data):
        if value.get("type") not in {
            "item.started",
            "item.updated",
            "item.completed",
        }:
            continue
        item = value.get("item")
        if not isinstance(item, dict):
            continue
        if _event_name(str(item.get("type", ""))) != "collab_tool_call":
            continue
        if _event_name(str(item.get("tool", ""))) != "spawn_agent":
            continue
        item_id = item.get("id")
        if isinstance(item_id, str) and item_id.strip():
            spawn_ids.add(item_id)
    return spawn_ids


def extract_subagent_spawn_count(data: bytes) -> int:
    """Count unique ``spawn_agent`` collaboration items in Codex JSONL."""

    return len(_subagent_spawn_ids(data))


def _is_error_event(value: dict[str, Any]) -> bool:
    """Return whether an event is a generic error envelope."""

    return any(
        isinstance(item, str) and _event_name(item) in ERROR_EVENT_TYPES
        for key, item in value.items()
        if key.casefold() in {"type", "event", "event_type"}
    )


def _command_marker(value: dict[str, Any]) -> str | None:
    """Find a network command in a typed command-execution item."""

    for key in ("command", "cmd", "shell_command"):
        command = value.get(key)
        if isinstance(command, str):
            match = _NETWORK_COMMAND_RE.search(command)
            if match:
                return match.group(0)
    return None


def _retrieval_marker(value: Any) -> str | None:
    """Find a genuine retrieval event in a parsed CLI event object.

    The function follows only event containers and typed tool items. It does
    not inspect arbitrary strings, assistant text, configuration echoes, or
    generic error payloads.
    """

    if isinstance(value, list):
        for item in value:
            found = _retrieval_marker(item)
            if found:
                return found
        return None
    if not isinstance(value, dict) or _is_error_event(value):
        return None

    event_type = value.get("type")
    event = value.get("event")
    event_type_name = value.get("event_type")
    for item in (event_type, event, event_type_name):
        if isinstance(item, str) and _event_name(item) in RETRIEVAL_EVENT_TYPES:
            return item

    if isinstance(event_type, str) and _event_name(event_type) in COMMAND_EVENT_TYPES:
        return _command_marker(value)

    if (
        isinstance(event_type, str)
        and _event_name(event_type) in GENERIC_TOOL_EVENT_TYPES
    ):
        for key in ("tool", "tool_name", "name", "method"):
            item = value.get(key)
            if isinstance(item, str) and _event_name(item) in RETRIEVAL_EVENT_TYPES:
                return item

    for key in ("item", "data", "payload"):
        nested = value.get(key)
        if isinstance(nested, (dict, list)):
            found = _retrieval_marker(nested)
            if found:
                return found
    return None


def reject_retrieval(
    stdout: bytes, stderr: bytes, *, scan_artifact_text: bool = False
) -> None:
    """Reject parsed retrieval events and explicit commands in fallback text.

    Generator transport streams are inspected as JSONL event streams. A
    fallback artifact is plain text, so callers may opt into the narrower
    explicit-network-command scan for that artifact only.
    """

    for stream, payload in (("stdout", stdout), ("stderr", stderr)):
        decoded = payload.decode("utf-8", errors="replace")
        for line in decoded.splitlines():
            if scan_artifact_text:
                match = _NETWORK_COMMAND_RE.search(line)
                if match:
                    raise RetrievalViolation(
                        "Unpermitted retrieval marker observed in artifact text",
                        matched_pattern=match.group(0),
                        matching_line=line,
                        stream=stream,
                        payload=payload,
                    )
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(value, dict):
                continue
            marker = _retrieval_marker(value)
            if marker:
                raise RetrievalViolation(
                    f"Unpermitted retrieval event observed: {marker}",
                    matched_pattern=marker,
                    matching_line=line,
                    stream=stream,
                    payload=payload,
                )
