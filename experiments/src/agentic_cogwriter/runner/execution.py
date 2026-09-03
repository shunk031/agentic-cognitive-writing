"""Headless process execution and transport-output parsing."""

from __future__ import annotations

import json
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
                timed_out=True,
            )
        except OSError as exc:
            raise ExecutionError(f"Cannot execute {command[0]}: {exc}") from exc
        return ExecutionResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
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
            if key in {"type", "tool", "tool_name", "event_type", "method"} and (
                isinstance(item, str)
                and any(marker in item.lower() for marker in markers)
            ):
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
                raise RetrievalViolation(
                    f"Unpermitted retrieval event observed: {marker}"
                )
