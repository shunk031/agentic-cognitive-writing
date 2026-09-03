"""Configuration for one API judge assignment."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .errors import JudgeConfigurationError

JudgeTask = Literal["pointwise", "pairwise"]
JudgeFamily = Literal["claude_frontier", "gpt_frontier", "open_evaluator"]


def _required_string(values: Mapping[str, Any], *names: str) -> str:
    for name in names:
        value = values.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    joined = " or ".join(names)
    raise JudgeConfigurationError(f"Judge configuration needs {joined}")


def _integer(value: Any, field: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise JudgeConfigurationError(f"{field} must be an integer")
    if minimum is not None and value < minimum:
        raise JudgeConfigurationError(f"{field} must be at least {minimum}")
    return value


def _number(value: Any, field: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise JudgeConfigurationError(f"{field} must be numeric")
    result = float(value)
    if minimum is not None and result < minimum:
        raise JudgeConfigurationError(f"{field} must be at least {minimum}")
    return result


def _decoding_value(
    values: Mapping[str, Any], decoding: Mapping[str, Any], *names: str
) -> Any:
    for name in names:
        if name in decoding:
            return decoding[name]
        if name in values:
            return values[name]
    return None


@dataclass(frozen=True)
class JudgeConfig:
    """Immutable settings for one pointwise or pairwise judge."""

    task: JudgeTask
    model: str
    judge_id: str
    judge_family: JudgeFamily
    base_url_env: str
    credential_env: str
    template_path: Path
    seed: int
    temperature: float
    top_p: float | None
    max_output_tokens: int | None
    stop_rules: tuple[str, ...]
    timeout_seconds: float
    max_retries: int
    source_path: Path | None = None

    @classmethod
    def load(cls, path: Path) -> JudgeConfig:
        """Load a JSON judge configuration without reading credentials."""

        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise JudgeConfigurationError(
                f"Cannot read judge configuration {path}: {exc}"
            ) from exc
        if not isinstance(document, dict):
            raise JudgeConfigurationError("Judge configuration must be a JSON object")
        return cls.from_mapping(document, source_path=path)

    @classmethod
    def from_mapping(
        cls, values: Mapping[str, Any], *, source_path: Path | None = None
    ) -> JudgeConfig:
        """Validate a mapping whose decoding fields mirror runtime configuration."""

        task_value = values.get("task", "pointwise")
        if task_value not in {"pointwise", "pairwise"}:
            raise JudgeConfigurationError("task must be 'pointwise' or 'pairwise'")
        task: JudgeTask = task_value

        model = _required_string(values, "model")
        judge_id = str(values.get("judge_id", model)).strip()
        if not judge_id:
            raise JudgeConfigurationError("judge_id must be a non-empty string")
        family_value = values.get("judge_family", "open_evaluator")
        if family_value not in {
            "claude_frontier",
            "gpt_frontier",
            "open_evaluator",
        }:
            raise JudgeConfigurationError(
                "judge_family must be claude_frontier, gpt_frontier, or open_evaluator"
            )
        family: JudgeFamily = family_value

        base_url_env = _required_string(values, "base_url_env", "base_url_env_name")
        credential_env = _required_string(
            values, "credential_env", "credential_env_name"
        )
        template_value = _required_string(values, "template_path")
        template_path = Path(template_value).expanduser()
        if not template_path.is_absolute() and source_path is not None:
            template_path = source_path.parent / template_path
        template_path = template_path.resolve()

        seed = _integer(values.get("seed"), "seed")
        decoding_value = values.get("decoding", {})
        if decoding_value is None:
            decoding_value = {}
        if not isinstance(decoding_value, Mapping):
            raise JudgeConfigurationError("decoding must be an object")

        temperature_value = _decoding_value(values, decoding_value, "temperature")
        if temperature_value is None:
            raise JudgeConfigurationError("temperature is required")
        temperature = _number(temperature_value, "temperature")
        if temperature != 0:
            raise JudgeConfigurationError("temperature must be exactly 0")

        top_p_value = _decoding_value(
            values, decoding_value, "top_p_or_equivalent", "top_p"
        )
        if top_p_value is None:
            raise JudgeConfigurationError("top_p_or_equivalent is required")
        top_p = _number(top_p_value, "top_p_or_equivalent", minimum=0)
        if top_p > 1:
            raise JudgeConfigurationError("top_p_or_equivalent cannot exceed 1")

        max_tokens_value = _decoding_value(
            values,
            decoding_value,
            "maximum_output_tokens",
            "max_output_tokens",
            "max_tokens",
        )
        if max_tokens_value is None:
            raise JudgeConfigurationError("maximum_output_tokens is required")
        max_output_tokens = _integer(
            max_tokens_value, "maximum_output_tokens", minimum=1
        )

        stop_value = _decoding_value(values, decoding_value, "stop_rules", "stop")
        if stop_value is None:
            raise JudgeConfigurationError("stop_rules is required")
        if isinstance(stop_value, str):
            stop_rules = (stop_value,)
        elif isinstance(stop_value, list) and all(
            isinstance(item, str) for item in stop_value
        ):
            stop_rules = tuple(stop_value)
        else:
            raise JudgeConfigurationError("stop_rules must be a string list")

        timeout_value = values.get("timeout", values.get("timeout_seconds", 120))
        timeout_seconds = _number(timeout_value, "timeout", minimum=0.001)

        retry_value = values.get("max_retries")
        retry_policy = values.get("retry_policy")
        if retry_value is None and isinstance(retry_policy, Mapping):
            retry_value = retry_policy.get("max_retries")
        if retry_value is None:
            retry_value = retry_policy
        if retry_value is None:
            retry_value = 0
        max_retries = _integer(retry_value, "max_retries", minimum=0)

        return cls(
            task=task,
            model=model,
            judge_id=judge_id,
            judge_family=family,
            base_url_env=base_url_env,
            credential_env=credential_env,
            template_path=template_path,
            seed=seed,
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=max_output_tokens,
            stop_rules=stop_rules,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            source_path=source_path,
        )
