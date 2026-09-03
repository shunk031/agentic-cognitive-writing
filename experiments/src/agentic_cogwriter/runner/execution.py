"""Headless process execution and transport-output parsing."""

from __future__ import annotations

import json
import re
import subprocess
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
            if isinstance(item, str) and (
                key.lower()
                in {
                    "type",
                    "tool",
                    "tool_name",
                    "event",
                    "event_type",
                    "method",
                    "name",
                }
                and any(marker in item.lower() for marker in markers)
            ):
                return item
            if key.lower() in {"command", "cmd", "shell_command"} and isinstance(
                item, str
            ):
                command = item.lower()
                if re.search(
                    r"\b(?:curl|wget|fetch|httpie|nc|netcat|socat|ssh)\b|"
                    r"\b(?:git\s+clone|python\s+-m\s+http\.client)\b",
                    command,
                ):
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
    """Fail closed on raw URL/network markers and structured retrieval events."""

    for payload in (stdout, stderr):
        decoded = payload.decode("utf-8", errors="replace")
        if re.search(
            r"(?i)https?://|www\.|\b(?:web[_-]?search|websearch|browser|"
            r"mcp[_-]?tool[_-]?call|network[_-]?request)\b|"
            r"\b(?:curl|wget|fetch|httpie|nc|netcat|socat|ssh)\b|"
            r"\b(?:git\s+clone|python\s+-m\s+http\.client|urllib|requests\.get|"
            r"socket\.create_connection)\b",
            decoded,
        ):
            raise RetrievalViolation(
                "Unpermitted retrieval marker observed in raw output"
            )
        for value in _json_objects(payload):
            marker = _retrieval_marker(value)
            if marker:
                raise RetrievalViolation(
                    f"Unpermitted retrieval event observed: {marker}"
                )
