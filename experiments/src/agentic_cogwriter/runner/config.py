"""Runtime gate and immutable experiment settings."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ConfigurationError

PLACEHOLDER = "REQUIRED_AT_RUNTIME"

# Agentic CogWriter settings mirror the protocol's runtime table and pre-scoring gates.
REQUIRED_RUNTIME_FIELDS = (
    "codex_generator_model",
    "claude_code_generator_model",
    "codex_frontier_judge",
    "claude_code_frontier_judge",
    "shared_open_evaluator",
    "generator_system_and_condition_prompts",
    "judge_prompts_and_json_schemas",
    "temperature",
    "top_p_or_equivalent",
    "maximum_output_tokens",
    "stop_rules",
    "timeout",
    "generation_seed",
    "judge_seed",
    "sampling_seed",
    "presentation_seed",
    "codex_version",
    "claude_code_version",
    "main_plugin_commit",
    "experiments_plugin_commit",
    "runner_commit",
    "generator_and_judge_family_audit",
    "retry_policy",
    "length_strata",
    "minimum_cell_size",
    "covariate_model",
    "length_unit",
    "zero_variance_rule",
    "statistical_lock",
)


def _contains_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        return value == PLACEHOLDER or value.startswith(f"{PLACEHOLDER}:")
    if isinstance(value, Mapping):
        return any(_contains_placeholder(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_placeholder(item) for item in value)
    return False


@dataclass(frozen=True)
class RuntimeConfig:
    """Loaded settings that are required before a scored run can start."""

    values: Mapping[str, Any]
    strict: bool = True
    path: Path | None = None

    @classmethod
    def load(cls, path: Path) -> RuntimeConfig:
        """Load a JSON runtime configuration and keep its source path."""

        try:
            values = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigurationError(
                f"Cannot read runtime config {path}: {exc}"
            ) from exc
        if not isinstance(values, dict):
            raise ConfigurationError("Runtime config must be a JSON object")
        return cls(copy.deepcopy(values), strict=True, path=path)

    @classmethod
    def from_dict(
        cls, values: Mapping[str, Any], *, strict: bool = True
    ) -> RuntimeConfig:
        """Build settings directly, useful for isolated tests and callers."""

        return cls(copy.deepcopy(dict(values)), strict=strict)

    def unresolved_fields(self) -> list[str]:
        """Return required fields that remain absent or placeholder-valued."""

        unresolved: list[str] = []
        fields = REQUIRED_RUNTIME_FIELDS if self.strict else tuple(self.values)
        for field in fields:
            if field not in self.values or _contains_placeholder(self.values[field]):
                unresolved.append(field)
        return unresolved

    def require_scored_run(self) -> None:
        """Stop before process creation when any runtime gate remains open."""

        unresolved = self.unresolved_fields()
        if unresolved:
            joined = ", ".join(unresolved)
            raise ConfigurationError(
                "Scored runs are blocked until REQUIRED_AT_RUNTIME values are filled: "
                + joined
            )

    def get(self, name: str, default: Any = None) -> Any:
        """Read one setting without exposing the underlying mutable mapping."""

        return self.values.get(name, default)

    @property
    def output_budget_tokens(self) -> int:
        """Return the shared output budget after the runtime gate is closed."""

        value = self.values.get("maximum_output_tokens")
        try:
            budget = int(value)
        except (TypeError, ValueError) as exc:
            raise ConfigurationError(
                "maximum_output_tokens must be an integer"
            ) from exc
        if budget <= 0:
            raise ConfigurationError("maximum_output_tokens must be positive")
        return budget

    @property
    def timeout_seconds(self) -> float:
        """Return the common command timeout in seconds."""

        value = self.values.get("timeout")
        try:
            timeout = float(value)
        except (TypeError, ValueError) as exc:
            raise ConfigurationError("timeout must be numeric") from exc
        if timeout <= 0:
            raise ConfigurationError("timeout must be positive")
        return timeout

    @property
    def retry_count(self) -> int:
        """Return the fixed retry count without allowing per-condition changes."""

        policy = self.values.get("retry_policy")
        value = policy.get("max_retries", 0) if isinstance(policy, Mapping) else policy
        try:
            retries = int(value)
        except (TypeError, ValueError) as exc:
            raise ConfigurationError(
                "retry_policy must contain an integer retry count"
            ) from exc
        if retries < 0:
            raise ConfigurationError("retry_policy retry count cannot be negative")
        return retries

    def model_for(self, platform: str) -> str:
        """Return the generator model assigned to a platform."""

        if platform == "codex-primary":
            return str(self.values["codex_generator_model"])
        if platform == "claude-code-replication":
            return str(self.values["claude_code_generator_model"])
        raise ConfigurationError(f"Unknown platform: {platform}")
