"""Skill-loading and role-delegation evidence read from one run's artifacts.

Every staged skill opens with a note asking the agent to say ``I read <skill>.``
after reading it. The top-level agent says its line in an assistant message,
and a delegated role agent begins its report with its role skill's line, so the
lines show in the Codex event stream and rollouts which skills were read. The
lines must never reach the scored final response.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from ..paths import EXPERIMENTS_ROOT, REPOSITORY_ROOT
from .execution import _json_objects

ROLE_SKILLS = ("planning", "translating", "reviewing")
_ROLE_MENTION = re.compile(r"\$(planning|translating|reviewing)\b")
_SKILL_ROOTS = (
    REPOSITORY_ROOT / "plugin/skills",
    EXPERIMENTS_ROOT / "plugin/skills",
    EXPERIMENTS_ROOT / "baselines/skills",
)


def ack_token(skill: str) -> str:
    """Return the acknowledgment line a skill asks its reader to say."""

    return f"I read {skill}."


def known_skills(roots: Iterable[Path] = _SKILL_ROOTS) -> tuple[str, ...]:
    """Return every skill name the runner can stage."""

    return tuple(
        sorted(
            path.parent.name
            for root in roots
            if root.is_dir()
            for path in root.glob("*/SKILL.md")
        )
    )


def ack_counts(texts: Iterable[str], skills: Sequence[str]) -> dict[str, int]:
    """Count acknowledgment lines per skill across texts, omitting zeros."""

    counts: Counter[str] = Counter()
    for text in texts:
        for skill in skills:
            counts[skill] += text.count(ack_token(skill))
    return {skill: count for skill, count in sorted(counts.items()) if count}


def _agent_messages(events: bytes) -> list[str]:
    return [
        item["text"]
        for value in _json_objects(events)
        if value.get("type") == "item.completed"
        and isinstance(item := value.get("item"), dict)
        and item.get("type") == "agent_message"
        and isinstance(item.get("text"), str)
    ]


def spawned_roles(events: bytes) -> Counter[str]:
    """Count completed ``spawn_agent`` calls per role their brief names as ``$role``.

    A spawn counts once, when its ``item.completed`` event reports a completed
    call with a receiver thread, as ``_subagent_spawn_ids`` counts spawns.
    """

    roles: dict[str, str] = {}
    for value in _json_objects(events):
        item = value.get("item")
        if (
            value.get("type") == "item.completed"
            and isinstance(item, dict)
            and item.get("type") == "collab_tool_call"
            and item.get("tool") == "spawn_agent"
            and item.get("status") == "completed"
            and item.get("receiver_thread_ids")
            and isinstance(item.get("prompt"), str)
            and (match := _ROLE_MENTION.search(item["prompt"]))
        ):
            roles[str(item.get("id"))] = match.group(1)
    return Counter(roles.values())


def selected_roles(trace: Path) -> Counter[str]:
    """Count the process switches that enter each role process."""

    roles: Counter[str] = Counter()
    if not trace.is_file():
        return roles
    for line in trace.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (
            isinstance(event, dict)
            and event.get("event_type") == "process_switch"
            and event.get("to_process") in ROLE_SKILLS
        ):
            roles[event["to_process"]] += 1
    return roles


def _role_agent(rollout: Path, skills: Sequence[str]) -> dict[str, Any] | None:
    """Summarize one child rollout, or return None for a top-level thread."""

    role: str | None = None
    messages: list[str] = []
    lines = rollout.read_text(encoding="utf-8", errors="replace").splitlines()
    for number, line in enumerate(lines):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload = value.get("payload") if isinstance(value, dict) else None
        if not isinstance(payload, dict):
            continue
        if number == 0:
            if value.get("type") != "session_meta" or not payload.get(
                "parent_thread_id"
            ):
                return None
            continue
        if value.get("type") != "event_msg" or not isinstance(
            payload.get("message"), str
        ):
            continue
        if payload.get("type") == "user_message" and role is None:
            match = _ROLE_MENTION.search(payload["message"])
            role = match.group(1) if match else None
        elif payload.get("type") == "agent_message":
            messages.append(payload["message"])
    acknowledgments = ack_counts(messages, skills)
    return {
        "role": role,
        "acknowledgments": acknowledgments,
        "acknowledged": role is not None and role in acknowledgments,
    }


def summarize_acknowledgments(
    run_dir: Path,
    *,
    invoked_skill: str,
    in_context_roles: Iterable[str] = (),
    skills: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Count acknowledgment lines per expected skill for one Codex run.

    The top-level counts come from the attempt event streams. Each collected
    rollout of a spawned agent counts as one role agent, whose role is the
    ``$role`` its brief names.
    """

    skills = known_skills() if skills is None else skills
    events = b"".join(
        path.read_bytes() for path in sorted(run_dir.glob("attempt-*.events.jsonl"))
    )
    top_level = ack_counts(_agent_messages(events), skills)
    expected = [invoked_skill, *sorted(set(in_context_roles))]
    role_agents = [
        {"rollout": path.relative_to(run_dir).as_posix(), **summary}
        for path in sorted(run_dir.glob("sessions/attempt-*/**/*.jsonl"))
        if (summary := _role_agent(path, skills)) is not None
    ]
    return {
        "expected_top_level": expected,
        "top_level": top_level,
        "missing_top_level": [skill for skill in expected if skill not in top_level],
        "role_agents": role_agents,
        "role_agents_acknowledged": sum(agent["acknowledged"] for agent in role_agents),
    }


def leaked_acknowledgments(text: str, skills: Sequence[str] | None = None) -> list[str]:
    """Return the acknowledgment lines that appear in a product text."""

    skills = known_skills() if skills is None else skills
    return [ack_token(skill) for skill in skills if ack_token(skill) in text]
