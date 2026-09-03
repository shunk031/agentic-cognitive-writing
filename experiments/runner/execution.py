"""Headless process execution and transport-output parsing."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ExecutionError, RetrievalViolation


@dataclass(frozen=True)
class ExecutionResult:
    """Captured output from one headless turn."""

    returncode: int
    stdout: bytes
    stderr: bytes
    session_id: str | None = None
    timed_out: bool = False
    duration_seconds: float = 0.0


class SubprocessExecutor:
    """Run argv directly with one common timeout."""

    def run(self, command: list[str], *, cwd: Path, timeout_seconds: float) -> ExecutionResult:
        """Execute one command without shell expansion."""

        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, bytes) else (exc.stdout or b"")
            stderr = exc.stderr if isinstance(exc.stderr, bytes) else (exc.stderr or b"")
            return ExecutionResult(
                returncode=-1,
                stdout=stdout,
                stderr=stderr,
                timed_out=True,
                duration_seconds=time.monotonic() - started,
            )
        except OSError as exc:
            raise ExecutionError(f"Cannot execute {command[0]}: {exc}") from exc
        return ExecutionResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration_seconds=time.monotonic() - started,
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


def _find_string(value: Any, names: set[str]) -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in names and isinstance(item, str) and item:
                return item
            found = _find_string(item, names)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_string(item, names)
            if found:
                return found
    return None


def extract_session_id(data: bytes) -> str | None:
    """Read Codex thread IDs or Claude session IDs from machine output."""

    for value in _json_objects(data):
        found = _find_string(value, {"session_id", "thread_id"})
        if found:
            return found
    return None


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
        if isinstance(item, dict):
            if item.get("type") in {"agent_message", "assistant_message"}:
                text = item.get("text")
                if isinstance(text, str):
                    candidates.append(text)
        for key in ("result", "text"):
            if isinstance(value.get(key), str):
                candidates.append(value[key])
    return candidates[-1] if candidates else decoded


def _retrieval_marker(value: Any) -> str | None:
    markers = {
        "web_search",
        "websearch",
        "browser",
        "mcp_tool_call",
        "retrieval",
        "network_request",
        "fetch",
        "wget",
        "curl",
    }
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"type", "tool", "tool_name", "event_type", "method"}:
                if isinstance(item, str) and any(marker in item.lower() for marker in markers):
                    return item
            if key == "command" and isinstance(item, str):
                command = item.lower()
                if any(token in command.split() for token in {"curl", "wget"}):
                    return item
            found = _retrieval_marker(item)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _retrieval_marker(item)
            if found:
                return found
    return None


def reject_retrieval(stdout: bytes, stderr: bytes) -> None:
    """Fail closed when structured headless output reports retrieval."""

    for payload in (stdout, stderr):
        for value in _json_objects(payload):
            marker = _retrieval_marker(value)
            if marker:
                raise RetrievalViolation(f"Unpermitted retrieval event observed: {marker}")
