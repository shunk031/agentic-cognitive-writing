"""Runner support for the CogWriter arms that run under ``cw``.

The runner writes ``.writing/task.md``, stages ``cw`` read-only, scores the
``cw stop`` snapshot, and judges the run from harness records only: the
attempt event streams, the collected rollouts, and the ``cw`` history. The
fidelity report reads the same records through the functions here.
"""

from __future__ import annotations

import json
import re
import shutil
import stat
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from ..paths import REPOSITORY_ROOT
from .hashing import sha256_file

CW_SOURCE = REPOSITORY_ROOT / "plugin/cw/cw.py"
BUDGET_OUTPUT_TOKENS = 64_000
PROVIDER_WINDOW_SECONDS = 1_500
_HAN = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
_LATIN = re.compile(r"[A-Za-z]")
_ROLE = re.compile(r"^\$(planning|translating|reviewing)\b")
_CODEX_COMMAND = re.compile(r"(?:^|[\s;&|(`'\"])codex(?:\s|$)")
_SPAWN_CALL = re.compile(r"spawn_agent\(\s*(\{.*?\})\s*\)", re.DOTALL)
_SPAWN_OVERRIDE = re.compile(r"\b(model|reasoning_effort|service_tier)\s*:")
_PROVIDER_EVENT = re.compile(r"Reconnecting|stream disconnected", re.IGNORECASE)
_TOKEN_FIELDS = ("output_tokens", "input_tokens", "cached_input_tokens")


# ---- inputs ----------------------------------------------------------------


def majority_script(text: str) -> str:
    """Return ``Chinese`` or ``English`` by the majority of Han and Latin letters."""

    return (
        "Chinese" if len(_HAN.findall(text)) > len(_LATIN.findall(text)) else "English"
    )


def resolve_language(language: str | None, assignment: str) -> dict[str, str]:
    """Return the output language of a prompt and where it came from.

    The manifest field is authoritative. Until the manifests carry it, the
    language is the majority script of the assignment; this placeholder does
    not implement the person-labelled rule for mixed-script prompts.
    """

    if language:
        return {"value": language, "source": "manifest"}
    return {
        "value": majority_script(assignment),
        "source": "placeholder: majority script of the assignment",
    }


def task_text(sections: str, information_contract: str, language: str) -> str:
    """Compose ``task.md``: the prompt's task sections, the contract, the language."""

    return (
        f"{sections.strip()}\n\n{information_contract.strip()}\n\n"
        f"## Output language\n{language}\n"
    )


def stage_cw(workspace: Path, keys: Mapping[str, Any], language: str) -> None:
    """Stage ``cw.py`` and its arm keys read-only under ``.agents/cw/``."""

    target = workspace / ".agents" / "cw"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CW_SOURCE, target / "cw.py")
    (target / "cw.json").write_text(
        json.dumps({**keys, "language": language}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for path in target.iterdir():
        path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


def runner_files(workspace: Path) -> dict[str, str]:
    """Hash every runner-owned file: the staged tree, task.md, and markers."""

    roots = [workspace / ".agents", workspace / "plugin"]
    paths = [p for root in roots if root.is_dir() for p in root.rglob("*")]
    writing = workspace / ".writing"
    paths.append(writing / "task.md")
    history = writing / "history"
    if history.is_dir():
        paths += list(history.glob("turn-*-request.md")) + list(history.glob("retry-*"))
    return {
        p.relative_to(workspace).as_posix(): sha256_file(p)
        for p in sorted(paths)
        if p.is_file()
    }


def write_retry_marker(workspace: Path) -> str:
    history = workspace / ".writing" / "history"
    history.mkdir(parents=True, exist_ok=True)
    name = f"retry-{len(list(history.glob('retry-*'))) + 1:02d}"
    (history / name).write_text("", encoding="utf-8")
    return name


# ---- harness records -------------------------------------------------------


def _json_lines(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            out.append(value)
    return out


def attempt_events(run_dir: Path) -> list[list[dict]]:
    return [_json_lines(p) for p in sorted(run_dir.glob("attempt-*.events.jsonl"))]


def attempt_meta(run_dir: Path) -> list[dict]:
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(run_dir.glob("attempt-*.meta.json"))
    ]


def history(run_dir: Path) -> list[dict]:
    path = run_dir / "workspace/.writing/history/history.jsonl"
    return [e for e in _json_lines(path) if "n" in e] if path.is_file() else []


def threads(run_dir: Path) -> dict[str, dict]:
    """Merge every collected rollout copy into one record list per thread.

    A thread's rollout is copied once per attempt that changed it; lines are
    deduplicated and ordered by timestamp.
    """

    merged: dict[str, dict] = {}
    for path in sorted(run_dir.glob("sessions/attempt-*/**/rollout-*.jsonl")):
        records = _json_lines(path)
        if not records or records[0].get("type") != "session_meta":
            continue
        meta = records[0]["payload"]
        entry = merged.setdefault(
            meta["id"],
            {
                "id": meta["id"],
                "parent": meta.get("parent_thread_id"),
                "started": records[0].get("timestamp"),
                "lines": {},
            },
        )
        for record in records:
            entry["lines"].setdefault(json.dumps(record, sort_keys=True), record)
    for entry in merged.values():
        entry["records"] = sorted(
            entry.pop("lines").values(), key=lambda r: str(r.get("timestamp", ""))
        )
    return merged


def _user_texts(records: Iterable[dict]) -> list[str]:
    texts = []
    for record in records:
        payload = record.get("payload") or {}
        if (
            record.get("type") == "response_item"
            and payload.get("type") == "message"
            and payload.get("role") == "user"
        ):
            texts += [
                c.get("text", "")
                for c in payload.get("content", [])
                if isinstance(c, dict)
            ]
    return texts


def _usage_series(records: Iterable[dict]) -> list[tuple[str, dict]]:
    series = []
    for record in records:
        payload = record.get("payload") or {}
        if record.get("type") == "event_msg" and payload.get("type") == "token_count":
            usage = (payload.get("info") or {}).get("total_token_usage")
            if usage:
                series.append((str(record.get("timestamp", "")), usage))
    return series


def _segments(series: list[tuple[str, dict]]) -> list[dict]:
    """Split running totals at every drop; keep each segment's field maxima."""

    segments: list[dict] = []
    previous: dict | None = None
    for _, usage in series:
        dropped = previous is not None and any(
            usage.get(f, 0) < previous.get(f, 0) for f in _TOKEN_FIELDS
        )
        if not segments or dropped:
            segments.append(dict.fromkeys(_TOKEN_FIELDS, 0))
        for field in _TOKEN_FIELDS:
            segments[-1][field] = max(segments[-1][field], usage.get(field, 0))
        previous = usage
    return segments


def forked(child: dict, parent_prompt: str) -> bool:
    """A forked child carries the parent's user prompt in its own history."""

    head = parent_prompt.strip()[:200]
    return bool(head) and any(head in text for text in _user_texts(child["records"]))


def token_report(run_dir: Path) -> dict[str, Any]:
    """Apply the per-thread token rule and report the parent budget statistic."""

    prompt_path = run_dir / "prompt.txt"
    prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.is_file() else ""
    all_threads = threads(run_dir)
    per_thread: dict[str, dict] = {}
    for thread_id, entry in all_threads.items():
        segments = _segments(_usage_series(entry["records"]))
        parent = all_threads.get(entry["parent"] or "")
        if segments and parent is not None and forked(entry, prompt):
            at_fork = [
                usage
                for ts, usage in _usage_series(parent["records"])
                if ts <= str(entry["started"])
            ]
            if at_fork:
                for field in _TOKEN_FIELDS:
                    segments[0][field] = max(
                        0, segments[0][field] - at_fork[-1].get(field, 0)
                    )
        per_thread[thread_id] = {
            field: sum(s[field] for s in segments) for field in _TOKEN_FIELDS
        } | {"role": "parent" if entry["parent"] is None else "child"}
    parent_turns = [
        e["usage"]["output_tokens"]
        for events in attempt_events(run_dir)
        for e in events
        if e.get("type") == "turn.completed" and isinstance(e.get("usage"), dict)
    ]
    totals = {f: sum(t[f] for t in per_thread.values()) for f in _TOKEN_FIELDS}
    return {
        "per_thread": per_thread,
        "child_inclusive": totals,
        "parent_output_per_turn": parent_turns,
        "budget_statistic": max(parent_turns, default=0),
        "budget_limit": BUDGET_OUTPUT_TOKENS,
    }


# ---- spawns and gates ------------------------------------------------------


def collab_calls(events: Iterable[dict]) -> list[dict]:
    return [
        e["item"]
        for e in events
        if e.get("type") == "item.completed"
        and isinstance(e.get("item"), dict)
        and e["item"].get("type") == "collab_tool_call"
    ]


def spawn_report(run_dir: Path) -> dict[str, Any]:
    """Spawns, forks, overrides, failures, unclosed children, and injection."""

    events = [e for attempt in attempt_events(run_dir) for e in attempt]
    calls = collab_calls(events)
    spawns = [c for c in calls if c.get("tool") == "spawn_agent"]
    succeeded = [c for c in spawns if c.get("receiver_thread_ids")]
    children = {c["receiver_thread_ids"][0]: c for c in succeeded}
    closed = {
        t
        for c in calls
        if c.get("tool") == "close_agent"
        for t in c["receiver_thread_ids"]
    }
    finished = {
        t
        for c in calls
        if c.get("tool") in ("wait", "close_agent")
        for t, s in (c.get("agents_states") or {}).items()
        if s.get("status") in ("completed", "errored", "shutdown")
    }
    prompt_path = run_dir / "prompt.txt"
    prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.is_file() else ""
    all_threads = threads(run_dir)
    forks, injected, codex_runs = [], [], []
    for thread_id, call in children.items():
        child = all_threads.get(thread_id)
        if child is None:
            continue
        if forked(child, prompt):
            forks.append(thread_id)
        match = _ROLE.match(call.get("prompt") or "")
        if match and any(
            text.startswith(f"<skill>\n<name>{match[1]}</name>")
            for text in _user_texts(child["records"])
        ):
            injected.append(thread_id)
        for record in child["records"]:
            payload = record.get("payload") or {}
            if payload.get("type") in ("function_call", "custom_tool_call"):
                text = str(payload.get("arguments") or payload.get("input") or "")
                if _CODEX_COMMAND.search(text):
                    codex_runs.append(thread_id)
                    break
    overrides = []
    for entry in all_threads.values():
        if entry["parent"] is not None:
            continue
        for record in entry["records"]:
            payload = record.get("payload") or {}
            if payload.get("type") not in ("function_call", "custom_tool_call"):
                continue
            code = str(payload.get("input") or payload.get("arguments") or "")
            for call in _SPAWN_CALL.findall(code):
                if _SPAWN_OVERRIDE.search(call):
                    overrides.append(call)
    return {
        "spawns": len(spawns),
        "children": sorted(children),
        "forked": forks,
        "overrides": overrides,
        "failed_spawns": len(spawns) - len(succeeded),
        "unclosed": sorted(set(children) - closed),
        "unfinished": sorted(set(children) - finished),
        "injected": injected,
        "codex_in_child": sorted(set(codex_runs)),
        "resume_agent": sum(c.get("tool") == "resume_agent" for c in calls),
        "prompts": [c.get("prompt") for c in succeeded],
    }


def nonce_report(run_dir: Path, prompts: list[str | None]) -> dict[str, Any]:
    entries = history(run_dir)
    retried = {
        e["step"]
        for e in entries
        if e.get("cmd") == "close" and e.get("reason") == "retry"
    }
    lines = {
        e["spawn"]: e["step"]
        for e in entries
        if e.get("cmd") == "step" and "refused" not in e and e.get("spawn")
    }
    counts = Counter(prompts)
    violations = [p for p in counts if p not in lines]
    violations += [
        line
        for line, step in lines.items()
        if counts[line] != 1 and not (step in retried and counts[line] == 0)
    ]
    return {"ok": not violations, "violations": len(violations)}


def top_level_writes(run_dir: Path) -> list[str]:
    """Top-level commands or file changes while a child is open, and .writing edits."""

    problems = []
    for events in attempt_events(run_dir):
        open_children: set[str] = set()
        for event in events:
            if event.get("type") != "item.completed":
                continue
            item = event.get("item") or {}
            kind = item.get("type")
            if kind == "collab_tool_call":
                if item.get("tool") == "spawn_agent":
                    open_children |= set(item.get("receiver_thread_ids") or [])
                elif item.get("tool") == "close_agent":
                    open_children -= set(item.get("receiver_thread_ids") or [])
            elif kind in ("command_execution", "file_change"):
                if open_children:
                    problems.append(f"{kind} {item.get('id')} while a child was open")
                if kind == "file_change" and any(
                    "/.writing/" in str(change.get("path", ""))
                    for change in item.get("changes") or []
                ):
                    problems.append(f"file_change {item.get('id')} under .writing/")
    return problems


def stop_reasons(run_dir: Path) -> dict[int, str]:
    return {e["turn"]: e["reason"] for e in history(run_dir) if e.get("cmd") == "stop"}


def gates(run_dir: Path, runner_hashes: Mapping[str, str] | None = None) -> dict:
    """Evaluate the A4 gate table; return gate results and the reported counts."""

    spawn = spawn_report(run_dir)
    nonce = nonce_report(run_dir, spawn["prompts"])
    writes = top_level_writes(run_dir)
    events = attempt_events(run_dir)
    completed = bool(events) and any(
        e.get("type") == "turn.completed" for e in events[-1]
    )
    stops = stop_reasons(run_dir)
    unchanged = runner_hashes is None or runner_files(run_dir / "workspace") == dict(
        runner_hashes
    )
    results = {
        "fork": not spawn["forked"],
        "spawn_args": not spawn["overrides"],
        "nonce": nonce["ok"],
        "codex_resume": not spawn["codex_in_child"] and not spawn["resume_agent"],
        "top_level_writes": not writes,
        "runner_files": unchanged,
        "completeness": completed
        and bool(stops)
        and all(reason in ("met", "cap") for reason in stops.values()),
    }
    return {
        "results": results,
        "reported": {
            "failed_spawns": spawn["failed_spawns"],
            "unclosed": len(spawn["unclosed"]),
            "unfinished": len(spawn["unfinished"]),
            "top_level_writes": writes,
            "nonce_violations": nonce["violations"],
        },
        "spawn": spawn,
    }


# ---- failure classification ------------------------------------------------


def _timestamp(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def provider_stall(run_dir: Path, events: list[dict], ended: float | None) -> bool:
    """A reconnect or stream error with no completed item after it, near the end.

    Stream errors carry no time in stdout, so the parent rollout's last record
    stands in for the time of the error: the error comes after it.
    """

    last_error = max(
        (
            i
            for i, e in enumerate(events)
            if e.get("type") == "error"
            and _PROVIDER_EVENT.search(str(e.get("message")))
        ),
        default=None,
    )
    if last_error is None or any(
        e.get("type") == "item.completed" for e in events[last_error + 1 :]
    ):
        return False
    if ended is None:
        return True
    parents = [t for t in threads(run_dir).values() if t["parent"] is None]
    stamps = [
        _timestamp(r["timestamp"])
        for t in parents
        for r in t["records"]
        if r.get("timestamp")
    ]
    return bool(stamps) and max(stamps) >= ended - PROVIDER_WINDOW_SECONDS


def classify_failure(
    run_dir: Path,
    *,
    harness_error: bool,
    gate_results: Mapping[str, bool] | None,
) -> dict[str, Any] | None:
    """Return the first matching ``failure.kind`` row, or None for a valid run."""

    events = attempt_events(run_dir)
    final = events[-1] if events else []
    meta = attempt_meta(run_dir)
    last = meta[-1] if meta else {}
    if harness_error:
        return {"kind": "harness_error", "class": "implementation"}
    if any(e.get("type") == "turn.failed" for e in final):
        return {"kind": "provider_error", "class": "implementation"}
    if last.get("timed_out"):
        if provider_stall(run_dir, final, last.get("ended")):
            return {"kind": "timeout_provider", "class": "implementation"}
        hang = bool(spawn_report(run_dir)["unfinished"])
        return {"kind": "timeout", "class": "model", "hang": hang}
    stops = [e for e in history(run_dir) if e.get("cmd") == "stop"]
    failed = [e for e in stops if e.get("reason") == "failure"]
    if failed:
        return {"kind": f"cw_failure:{failed[-1].get('failure')}", "class": "model"}
    for name, ok in (gate_results or {}).items():
        if not ok and name != "completeness":
            return {"kind": f"gate:{name}", "class": "model"}
    if token_report(run_dir)["budget_statistic"] > BUDGET_OUTPUT_TOKENS:
        return {"kind": "budget", "class": "model"}
    if gate_results is None or not gate_results.get("completeness"):
        return {"kind": "incomplete", "class": "model"}
    return None
