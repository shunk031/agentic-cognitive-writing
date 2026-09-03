"""Condition registry and frozen wrapper metadata."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .errors import ConfigurationError
from .hashing import sha256_bytes

CONDITION_IDS = ("A1", "A2", "A3", "A4", "A5", "A6", "B1", "B2")
BASELINE_IDS = ("A1", "A2", "A3")
EXPLORATORY_IDS = ("B1", "B2")
PLATFORMS = ("codex-primary", "claude-code-replication")


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

    @property
    def trace_policy_dict(self) -> dict[str, str]:
        """Return trace-policy metadata as a fresh mapping."""

        return dict(self.trace_policy)


def default_registry_path() -> Path:
    """Return the registry path relative to this source file."""

    return Path(__file__).resolve().parents[1] / "conditions" / "conditions.json"


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        value = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigurationError(f"Cannot read condition wrapper {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigurationError(f"Condition wrapper {path} must be a TOML object")
    return value


def _required_string(mapping: Mapping[str, Any], key: str, *, label: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{label}.{key} must be a non-empty string")
    return value


def _load_stages(entry: Mapping[str, Any], registry_path: Path, condition_id: str) -> tuple[StageSpec, ...]:
    stage_entries = entry.get("stages")
    if not isinstance(stage_entries, list) or not stage_entries:
        raise ConfigurationError(f"Condition {condition_id} must define ordered stages")
    stages: list[StageSpec] = []
    for stage_entry in stage_entries:
        if not isinstance(stage_entry, Mapping) or not isinstance(stage_entry.get("id"), str):
            raise ConfigurationError(f"Condition {condition_id} has an invalid stage")
        relative = stage_entry.get("path")
        stage_path = registry_path.parent / relative if isinstance(relative, str) else None
        expected = stage_entry.get("sha256")
        if stage_path is not None:
            if not stage_path.is_file():
                raise ConfigurationError(f"Missing frozen prompt file: {stage_path}")
            if not isinstance(expected, str) or sha256_bytes(stage_path.read_bytes()) != expected:
                raise ConfigurationError(f"Frozen prompt hash mismatch: {stage_path}")
        elif expected is not None:
            raise ConfigurationError(
                f"Condition {condition_id} stage {stage_entry['id']} has a hash without a path"
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
) -> tuple[str, str, tuple[tuple[str, str], ...]]:
    wrapper = _load_toml(wrapper_path)
    if wrapper.get("condition_id") != condition_id:
        raise ConfigurationError(f"Wrapper {wrapper_path} has the wrong condition_id")
    wrapper_family = wrapper.get("analysis_family")
    if wrapper_family != analysis_family:
        raise ConfigurationError(f"Wrapper {wrapper_path} has the wrong analysis_family")

    skill_name = _required_string(wrapper, "skill", label=str(wrapper_path))
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
        raise ConfigurationError(f"Wrapper {wrapper_path} must define an invocation table")
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

    install = wrapper.get("install")
    if not isinstance(install, Mapping):
        raise ConfigurationError(f"Wrapper {wrapper_path} must define an install table")
    for platform in PLATFORMS:
        commands = install.get(platform.replace("-", "_"))
        if not isinstance(commands, list) or not commands:
            raise ConfigurationError(
                f"Wrapper {wrapper_path} must define install commands for {platform}"
            )
        if not all(isinstance(command, str) and command.strip() for command in commands):
            raise ConfigurationError(f"Wrapper {wrapper_path} install commands must be strings")

    adapters = wrapper.get("adapters")
    if not isinstance(adapters, Mapping):
        raise ConfigurationError(f"Wrapper {wrapper_path} must define an adapters table")
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
    return skill_name, package_name, trace_policy


def load_condition_registry(path: Path | None = None) -> dict[str, ConditionSpec]:
    """Load all condition wrappers and verify frozen prompt hashes."""

    registry_path = path or default_registry_path()
    try:
        document = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Cannot read condition registry {registry_path}: {exc}") from exc
    entries = document.get("conditions") if isinstance(document, dict) else None
    if not isinstance(entries, dict) or set(entries) != set(CONDITION_IDS):
        raise ConfigurationError("Condition registry must define exactly A1 through A6, B1, and B2")

    result: dict[str, ConditionSpec] = {}
    for condition_id in CONDITION_IDS:
        entry = entries[condition_id]
        if not isinstance(entry, Mapping):
            raise ConfigurationError(f"Condition {condition_id} must be an object")
        if entry.get("kind") != "plugin" or entry.get("trace_mode") != "plugin_recorded":
            raise ConfigurationError(
                f"Condition {condition_id} must use a plugin_recorded wrapper"
            )
        analysis_family = entry.get("analysis_family")
        if analysis_family not in {"confirmatory", "exploratory"}:
            raise ConfigurationError(f"Condition {condition_id} has an invalid analysis_family")
        wrapper_relative = entry.get("wrapper_config")
        if not isinstance(wrapper_relative, str):
            raise ConfigurationError(f"Condition {condition_id} must define wrapper_config")
        wrapper_path = registry_path.parent / wrapper_relative
        if not wrapper_path.is_file():
            raise ConfigurationError(f"Missing condition wrapper config: {wrapper_path}")
        skill_name, package_name, trace_policy = _load_wrapper(
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
        )
    return result


def render_stage_prompt(
    template: str,
    *,
    prompt_text: str,
    supplied_context: str,
    output_constraints: Any,
    previous_stage_output: str,
    stage_id: str,
) -> str:
    """Render a frozen prompt for inspection without executing stage turns."""

    replacements = {
        "{{assignment}}": prompt_text,
        "{{supplied_context}}": supplied_context or "(No additional supplied context.)",
        "{{output_constraints}}": json.dumps(
            output_constraints,
            ensure_ascii=False,
            sort_keys=True,
        ),
        "{{previous_stage_output}}": previous_stage_output or "(No previous stage output.)",
        "{{stage_id}}": stage_id,
    }
    rendered = template
    for marker, value in replacements.items():
        rendered = rendered.replace(marker, value)
    if "{{" in rendered or "}}" in rendered:
        raise ConfigurationError(f"Unresolved placeholder in frozen prompt stage {stage_id}")
    return rendered
