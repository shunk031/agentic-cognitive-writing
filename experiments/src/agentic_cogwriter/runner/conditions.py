"""Condition registry and frozen wrapper metadata."""

from __future__ import annotations

import json
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..paths import EXPERIMENTS_ROOT
from .errors import ConfigurationError
from .hashing import sha256_bytes

CONDITION_IDS = ("A1", "A2", "A3", "A4", "A5", "A6", "B1", "B2")
PLATFORMS = ("codex-primary", "claude-code-replication")
KNOWN_TRACE_EVENT_TYPES = frozenset(
    {
        "process_switch",
        "goal_created",
        "goal_developed",
        "goal_regenerated",
    }
)
GOAL_EVENT_POLICIES = frozenset({"allowed", "forbidden"})


@dataclass(frozen=True)
class StageSpec:
    """One frozen prompt specification retained for condition provenance."""

    stage_id: str
    path: Path | None
    sha256: str | None


@dataclass(frozen=True)
class ConditionSpec:
    """One condition wrapper and the package skill it invokes."""

    condition_id: str
    kind: str
    analysis_family: str
    trace_mode: str
    skill_name: str
    package_name: str
    stages: tuple[StageSpec, ...]
    plugin_config: Path
    trace_policy: tuple[tuple[str, str], ...]
    trace_processes: tuple[str, ...]
    goal_events: str
    event_types: tuple[str, ...]
    min_events: int
    max_events: int | None
    process_order: tuple[str, ...] | None
    require_goal_events: bool
    product_requires_draft: bool

    @property
    def trace_policy_dict(self) -> dict[str, str]:
        """Return trace-policy metadata as a fresh mapping."""

        return dict(self.trace_policy)


def default_registry_path() -> Path:
    """Return the registry path relative to this source file."""

    return EXPERIMENTS_ROOT / "conditions" / "conditions.json"


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        value = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigurationError(
            f"Cannot read condition wrapper {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise ConfigurationError(f"Condition wrapper {path} must be a TOML object")
    return value


def _required_string(mapping: Mapping[str, Any], key: str, *, label: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{label}.{key} must be a non-empty string")
    return value


def _load_stages(
    entry: Mapping[str, Any], registry_path: Path, condition_id: str
) -> tuple[StageSpec, ...]:
    stage_entries = entry.get("stages")
    if not isinstance(stage_entries, list) or not stage_entries:
        raise ConfigurationError(f"Condition {condition_id} must define ordered stages")
    stages: list[StageSpec] = []
    for stage_entry in stage_entries:
        if not isinstance(stage_entry, Mapping) or not isinstance(
            stage_entry.get("id"), str
        ):
            raise ConfigurationError(f"Condition {condition_id} has an invalid stage")
        relative = stage_entry.get("path")
        stage_path = (
            registry_path.parent / relative if isinstance(relative, str) else None
        )
        expected = stage_entry.get("sha256")
        if stage_path is not None:
            if not stage_path.is_file():
                raise ConfigurationError(f"Missing frozen prompt file: {stage_path}")
            if (
                not isinstance(expected, str)
                or sha256_bytes(stage_path.read_bytes()) != expected
            ):
                raise ConfigurationError(f"Frozen prompt hash mismatch: {stage_path}")
        elif expected is not None:
            raise ConfigurationError(
                f"Condition {condition_id} stage {stage_entry['id']} has a hash "
                "without a path"
            )
        stages.append(
            StageSpec(
                stage_id=stage_entry["id"],
                path=stage_path,
                sha256=expected if isinstance(expected, str) else None,
            )
        )
    return tuple(stages)


def _load_wrapper(
    wrapper_path: Path,
    *,
    condition_id: str,
    analysis_family: str,
) -> tuple[
    str,
    str,
    tuple[tuple[str, str], ...],
    tuple[str, ...],
    str,
    tuple[str, ...],
    int,
    int | None,
    tuple[str, ...] | None,
    bool,
    bool,
]:
    wrapper = _load_toml(wrapper_path)
    if wrapper.get("condition_id") != condition_id:
        raise ConfigurationError(f"Wrapper {wrapper_path} has the wrong condition_id")
    wrapper_family = wrapper.get("analysis_family")
    if wrapper_family != analysis_family:
        raise ConfigurationError(
            f"Wrapper {wrapper_path} has the wrong analysis_family"
        )

    skill_name = _required_string(wrapper, "skill", label=str(wrapper_path))
    product_requires_draft = wrapper.get("product_requires_draft")
    if not isinstance(product_requires_draft, bool):
        raise ConfigurationError(
            f"Wrapper {wrapper_path} product_requires_draft must be a boolean"
        )
    package = wrapper.get("package")
    if not isinstance(package, Mapping):
        raise ConfigurationError(f"Wrapper {wrapper_path} must define a package table")
    package_name = _required_string(package, "name", label=f"{wrapper_path} package")

    plugins = wrapper.get("plugins")
    if not isinstance(plugins, Mapping):
        raise ConfigurationError(f"Wrapper {wrapper_path} must define a plugins table")
    plugin_paths = plugins.get("paths")
    if not isinstance(plugin_paths, list) or not plugin_paths:
        raise ConfigurationError(f"Wrapper {wrapper_path} must define plugin paths")
    if not all(isinstance(path, str) and path.strip() for path in plugin_paths):
        raise ConfigurationError(f"Wrapper {wrapper_path} plugin paths must be strings")

    invocation = wrapper.get("invocation")
    if not isinstance(invocation, Mapping):
        raise ConfigurationError(
            f"Wrapper {wrapper_path} must define an invocation table"
        )
    for platform in PLATFORMS:
        invocation_value = _required_string(
            invocation,
            platform.replace("-", "_"),
            label=f"{wrapper_path} invocation",
        )
        if skill_name not in invocation_value:
            raise ConfigurationError(
                f"Wrapper {wrapper_path} invocation must name skill {skill_name}"
            )
        if platform == "codex-primary" and (
            "{codex_plugin_root}" not in invocation_value
            or "SKILL.md" not in invocation_value
        ):
            raise ConfigurationError(
                f"Wrapper {wrapper_path} Codex invocation must reference "
                "{codex_plugin_root}/skills/<skill>/SKILL.md"
            )

    install = wrapper.get("install")
    if not isinstance(install, Mapping):
        raise ConfigurationError(f"Wrapper {wrapper_path} must define an install table")
    commands = install.get("claude_code_replication")
    if not isinstance(commands, list) or not commands:
        raise ConfigurationError(
            f"Wrapper {wrapper_path} must define install metadata for "
            "claude-code-replication"
        )
    if not all(isinstance(command, str) and command.strip() for command in commands):
        raise ConfigurationError(
            f"Wrapper {wrapper_path} install commands must be strings"
        )

    adapters = wrapper.get("adapters")
    if not isinstance(adapters, Mapping):
        raise ConfigurationError(
            f"Wrapper {wrapper_path} must define an adapters table"
        )
    expected_adapters = {
        "codex_primary": "codex_exec",
        "claude_code_replication": "claude_print",
    }
    for key, expected in expected_adapters.items():
        if adapters.get(key) != expected:
            raise ConfigurationError(
                f"Wrapper {wrapper_path} must map {key} to {expected}"
            )

    trace = wrapper.get("trace", {})
    if not isinstance(trace, Mapping):
        raise ConfigurationError(f"Wrapper {wrapper_path} trace must be a table")
    trace_policy = tuple(
        (key, str(trace.get(key, "not_applicable")))
        for key in ("retrieval", "evidence", "citation")
    )
    goal_events = trace.get("goal_events")
    if goal_events not in GOAL_EVENT_POLICIES:
        raise ConfigurationError(
            f"Wrapper {wrapper_path} trace.goal_events must be allowed or forbidden"
        )
    event_types = trace.get("event_types")
    if not isinstance(event_types, list) or not event_types:
        raise ConfigurationError(
            f"Wrapper {wrapper_path} trace.event_types must be a non-empty list"
        )
    if not all(isinstance(event_type, str) for event_type in event_types):
        raise ConfigurationError(
            f"Wrapper {wrapper_path} trace.event_types must contain strings"
        )
    unknown_event_types = set(event_types) - KNOWN_TRACE_EVENT_TYPES
    if unknown_event_types:
        raise ConfigurationError(
            f"Wrapper {wrapper_path} has unknown trace event types: "
            + ", ".join(sorted(unknown_event_types))
        )
    min_events = trace.get("min_events", 1)
    if (
        isinstance(min_events, bool)
        or not isinstance(min_events, int)
        or min_events < 1
    ):
        raise ConfigurationError(
            f"Wrapper {wrapper_path} trace.min_events must be a positive integer"
        )
    max_events = trace.get("max_events")
    if max_events is not None and (
        isinstance(max_events, bool)
        or not isinstance(max_events, int)
        or max_events < min_events
    ):
        raise ConfigurationError(
            f"Wrapper {wrapper_path} trace.max_events must be at least min_events"
        )
    processes = trace.get("processes")
    if not isinstance(processes, list) or not processes:
        raise ConfigurationError(
            f"Wrapper {wrapper_path} trace.processes must be a non-empty list"
        )
    if not all(isinstance(process, str) and process.strip() for process in processes):
        raise ConfigurationError(
            f"Wrapper {wrapper_path} trace.processes must contain strings"
        )
    process_order = trace.get("process_order")
    if process_order is not None:
        if not isinstance(process_order, list) or not process_order:
            raise ConfigurationError(
                f"Wrapper {wrapper_path} trace.process_order must be a non-empty list"
            )
        if not all(
            isinstance(process, str) and process.strip() for process in process_order
        ):
            raise ConfigurationError(
                f"Wrapper {wrapper_path} trace.process_order must contain strings"
            )
        if any(process not in processes for process in process_order):
            raise ConfigurationError(
                f"Wrapper {wrapper_path} trace.process_order must use "
                "declared processes"
            )
    require_goal_events = trace.get("require_goal_events", False)
    if not isinstance(require_goal_events, bool):
        raise ConfigurationError(
            f"Wrapper {wrapper_path} trace.require_goal_events must be a boolean"
        )
    if require_goal_events and goal_events != "allowed":
        raise ConfigurationError(
            f"Wrapper {wrapper_path} cannot require forbidden goal events"
        )
    return (
        skill_name,
        package_name,
        trace_policy,
        tuple(processes),
        goal_events,
        tuple(event_types),
        min_events,
        max_events,
        tuple(process_order) if process_order is not None else None,
        require_goal_events,
        product_requires_draft,
    )


def load_condition_registry(path: Path | None = None) -> dict[str, ConditionSpec]:
    """Load all condition wrappers and verify frozen prompt hashes."""

    registry_path = path or default_registry_path()
    try:
        document = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(
            f"Cannot read condition registry {registry_path}: {exc}"
        ) from exc
    entries = document.get("conditions") if isinstance(document, dict) else None
    if not isinstance(entries, dict) or set(entries) != set(CONDITION_IDS):
        raise ConfigurationError(
            "Condition registry must define exactly A1 through A6, B1, and B2"
        )

    result: dict[str, ConditionSpec] = {}
    for condition_id in CONDITION_IDS:
        entry = entries[condition_id]
        if not isinstance(entry, Mapping):
            raise ConfigurationError(f"Condition {condition_id} must be an object")
        if (
            entry.get("kind") != "plugin"
            or entry.get("trace_mode") != "plugin_recorded"
        ):
            raise ConfigurationError(
                f"Condition {condition_id} must use a plugin_recorded wrapper"
            )
        analysis_family = entry.get("analysis_family")
        if analysis_family not in {"confirmatory", "exploratory"}:
            raise ConfigurationError(
                f"Condition {condition_id} has an invalid analysis_family"
            )
        wrapper_relative = entry.get("wrapper_config")
        if not isinstance(wrapper_relative, str):
            raise ConfigurationError(
                f"Condition {condition_id} must define wrapper_config"
            )
        wrapper_path = registry_path.parent / wrapper_relative
        if not wrapper_path.is_file():
            raise ConfigurationError(
                f"Missing condition wrapper config: {wrapper_path}"
            )
        (
            skill_name,
            package_name,
            trace_policy,
            trace_processes,
            goal_events,
            event_types,
            min_events,
            max_events,
            process_order,
            require_goal_events,
            product_requires_draft,
        ) = _load_wrapper(
            wrapper_path,
            condition_id=condition_id,
            analysis_family=analysis_family,
        )
        result[condition_id] = ConditionSpec(
            condition_id=condition_id,
            kind="plugin",
            analysis_family=analysis_family,
            trace_mode="plugin_recorded",
            skill_name=skill_name,
            package_name=package_name,
            stages=_load_stages(entry, registry_path, condition_id),
            plugin_config=wrapper_path,
            trace_policy=trace_policy,
            trace_processes=trace_processes,
            goal_events=goal_events,
            event_types=event_types,
            min_events=min_events,
            max_events=max_events,
            process_order=process_order,
            require_goal_events=require_goal_events,
            product_requires_draft=product_requires_draft,
        )
    return result
