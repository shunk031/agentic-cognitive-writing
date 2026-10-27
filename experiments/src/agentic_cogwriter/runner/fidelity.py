"""Fidelity gate: reject runs whose harness records show a measured defect."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from .execution import _json_objects
from .manifest import LANGUAGES

ROLES = ("planning", "translating", "reviewing")
THREAD_LIMIT_ERROR = "agent thread limit reached"
_ROLE_TOKEN = re.compile(r"\$(planning|translating|reviewing)\b")
_SKILL_ROOT = re.compile(r"(?m)^- `r\d+` = `([^`]+)`$")
# An absolute path, not the tail of a relative or variable-prefixed one.
_ABSOLUTE_SKILL_FILE = re.compile(r"(?<![\w.~$}-])/[^\s\"'`\\]*/SKILL\.md")
_SKILL_FILE_TOKEN = re.compile(r"[^\s\"'`\\]*SKILL\.md")
_PARENT_SEGMENT = re.compile(r"(?:^|[^\w.])\.\.(?:/|$)")
_CALL_TYPES = frozenset({"function_call", "custom_tool_call", "local_shell_call"})
_OUTPUT_TYPES = frozenset({"function_call_output", "custom_tool_call_output"})


def _script(char: str) -> str | None:
    if not char.isalpha():
        return None
    name = unicodedata.name(char, "")
    if name.startswith(("LATIN", "FULLWIDTH LATIN")):
        return "LATIN"
    if name.startswith("CJK"):
        return "CJK"
    return None


def check_output_language(text: str, language: str) -> dict[str, Any]:
    """Flag a deliverable whose dominant script is not the prompt's.

    A Latin word (a maximal run of Latin letters) and a CJK character each count
    as one unit, so English terms in Chinese prose do not outweigh it. Text with
    neither, or a tie, has no dominant script and no flag. The flag is recorded,
    never a rejection reason.
    """

    units: Counter[str] = Counter()
    previous = None
    for char in text:
        script = _script(char)
        if script == "CJK" or (script == "LATIN" and previous != "LATIN"):
            units[script] += 1
        previous = script
    ranked = units.most_common()
    dominant = (
        ranked[0][0]
        if ranked and (len(ranked) == 1 or ranked[0][1] > ranked[1][1])
        else None
    )
    expected = LANGUAGES[language][1]
    return {
        "expected_language": language,
        "expected_script": expected,
        "latin_words": units["LATIN"],
        "cjk_characters": units["CJK"],
        "dominant_script": dominant,
        "dominant_share": (
            round(units[dominant] / units.total(), 4) if dominant else None
        ),
        "mismatch": dominant != expected if dominant else None,
    }


def check_fidelity(
    run_dir: Path,
    *,
    platform: str,
    codex_home: Path | None,
    requires_draft: bool,
    monitor_writes_history_only: bool,
) -> dict[str, Any]:
    """Classify a finished run as scorable or rejected, with every reason.

    ``codex_home`` is the run's own Codex home. When given, every skill root that
    Codex listed must lie inside it, and every skill file read by absolute path
    inside it or the run's workspace; records from other harnesses pass ``None``.
    """

    if platform == "codex":
        reasons = _codex_reasons(run_dir, monitor_writes_history_only)
        if codex_home is not None:
            reasons.extend(_skill_isolation_reasons(run_dir, codex_home))
    else:
        reasons = [
            f"{platform} records expose no subagent or tool events, "
            "so fidelity cannot be verified"
        ]
    if requires_draft:
        draft = run_dir / "workspace" / ".writing" / "draft.md"
        output = run_dir / "output.normalized.txt"
        if not (
            draft.is_file()
            and output.is_file()
            and draft.read_bytes() == output.read_bytes()
        ):
            reasons.append("scored output is not workspace/.writing/draft.md")
    return {"status": "rejected" if reasons else "scorable", "reasons": reasons}


def _response_items(records: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    for record in records:
        payload = record.get("payload")
        if record.get("type") == "response_item" and isinstance(payload, dict):
            yield payload


def _read_own_skill(records: list[dict[str, Any]], role: str) -> bool:
    """Return whether Codex injected the role skill or the agent read its file."""

    injected = f"<skill>\n<name>{role}</name>"
    skill_path = f"skills/{role}/SKILL.md"
    # Known limit: a forked rollout replays parent messages, so a parent's injected
    # role skill would count here; the fork check rejects such runs anyway.
    for payload in _response_items(records):
        if payload.get("type") == "message" and payload.get("role") == "user":
            for part in payload.get("content") or []:
                if isinstance(part, dict) and injected in str(part.get("text", "")):
                    return True
        elif payload.get("type") in _CALL_TYPES and skill_path in json.dumps(payload):
            return True
    return False


def _codex_reasons(run_dir: Path, monitor_writes_history_only: bool) -> list[str]:
    events = [
        event
        for path in sorted(run_dir.glob("attempt-*.events.jsonl"))
        for event in _json_objects(path.read_bytes())
    ]
    if not events:
        return ["no Codex event stream was recorded"]
    reasons: list[str] = []

    metas: dict[str, dict[str, Any]] = {}
    records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in sorted(run_dir.glob("sessions/**/rollout-*.jsonl")):
        lines = _json_objects(path.read_bytes())
        first = lines[0] if lines else {}
        meta = first.get("payload")
        if first.get("type") != "session_meta" or not isinstance(meta, dict):
            reasons.append(f"rollout {path.name} does not start with session_meta")
            continue
        metas[str(meta.get("id"))] = meta
        records[str(meta.get("id"))].extend(lines[1:])

    # The events stream records only the top-level thread, which is the Monitor.
    top_level = {
        event["thread_id"]
        for event in events
        if event.get("type") == "thread.started"
        and isinstance(event.get("thread_id"), str)
    }
    if not top_level:
        reasons.append("Codex event stream has no thread.started event")
    items = [
        event["item"]
        for event in events
        if event.get("type") == "item.completed" and isinstance(event.get("item"), dict)
    ]
    spawned: set[str] = set()
    closed: set[str] = set()
    spawn_prompts: dict[str, str] = {}
    for item in items:
        if item.get("type") != "collab_tool_call":
            continue
        receivers = item.get("receiver_thread_ids") or []
        if item.get("tool") == "spawn_agent":
            spawned.update(receivers)
            spawn_prompts.update(dict.fromkeys(receivers, str(item.get("prompt"))))
        elif item.get("tool") == "close_agent" and item.get("status") == "completed":
            closed.update(receivers)

    for thread in sorted((top_level | spawned) - metas.keys()):
        reasons.append(f"no rollout was recorded for thread {thread}")

    for thread, meta in sorted(metas.items()):
        if meta.get("forked_from_id"):
            reasons.append(f"child {thread} was spawned with inherited context")
        if meta.get("parent_thread_id"):
            role = meta.get("agent_role")
            if role not in ROLES:
                match = _ROLE_TOKEN.search(spawn_prompts.get(thread, ""))
                role = match.group(1) if match else None
            if role and not _read_own_skill(records[thread], role):
                reasons.append(f"{role} agent {thread} did not read its own SKILL.md")

    if monitor_writes_history_only:
        # Known limit: only apply_patch writes become file_change items; a shell
        # redirect by the Monitor is not visible here.
        for item in items:
            if item.get("type") != "file_change" or item.get("status") != "completed":
                continue
            for change in item.get("changes") or []:
                path = str(change.get("path", ""))
                if PurePosixPath(path).parts[-2:] != (".writing", "history.md"):
                    reasons.append(f"Monitor wrote {path}")

    # Closing a child also closes its descendants, so top-level closes suffice.
    for thread in sorted(spawned - closed):
        reasons.append(f"child {thread} was never closed")
    for thread in sorted(records):
        if any(
            payload.get("type") in _OUTPUT_TYPES
            and THREAD_LIMIT_ERROR in json.dumps(payload)
            for payload in _response_items(records[thread])
        ):
            reasons.append(f"thread {thread} hit the agent thread limit")
    return list(dict.fromkeys(reasons))


def _skill_isolation_reasons(run_dir: Path, codex_home: Path) -> list[str]:
    """Reject skill roots or skill reads outside the run's staged skills."""

    def inside(path: str, *roots: Path) -> bool:
        return any(Path(os.path.normpath(path)).is_relative_to(r) for r in roots)

    reasons: list[str] = []
    for path in sorted(run_dir.glob("sessions/**/rollout-*.jsonl")):
        lines = _json_objects(path.read_bytes())
        meta = lines[0].get("payload") if lines else None
        thread = meta.get("id") if isinstance(meta, dict) else path.name
        for payload in _response_items(lines):
            if payload.get("type") == "message":
                for part in payload.get("content") or []:
                    text = str(part.get("text", "")) if isinstance(part, dict) else ""
                    for root in _SKILL_ROOT.findall(text):
                        if not inside(root, codex_home):
                            reasons.append(
                                f"thread {thread} lists skill root {root} "
                                "outside the run's Codex home"
                            )
            elif payload.get("type") in _CALL_TYPES:
                # Known limit: a relative path without a `..` segment passes even
                # after a `cd` out of the workspace, as in `cd /x && cat SKILL.md`.
                text = json.dumps(payload).replace("\\n", " ")
                for read in _ABSOLUTE_SKILL_FILE.findall(text):
                    if not inside(read, codex_home, run_dir / "workspace"):
                        reasons.append(
                            f"thread {thread} read {read} outside the staged skills"
                        )
                for read in _SKILL_FILE_TOKEN.findall(text):
                    if _PARENT_SEGMENT.search(read):
                        reasons.append(
                            f"thread {thread} read {read} through a parent directory"
                        )
    return list(dict.fromkeys(reasons))
