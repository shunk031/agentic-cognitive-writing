"""Configuration for one API judge assignment."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from .errors import JudgeConfigurationError

JudgeTask = Literal["pointwise", "pairwise", "native-pointwise"]
JudgeFamily = Literal["claude_frontier", "gpt_frontier", "open_evaluator"]
JudgeRole = Literal["frontier", "open_evaluator"]


@dataclass(frozen=True)
class ModelFamilyMapping:
    """One frozen model identifier, family, and judging role mapping."""

    family: str
    role: JudgeRole


@dataclass(frozen=True)
class JudgeIdentity:
    """The family identity derived from the endpoint-reported model ID."""

    reported_model_id: str
    mapped_family: str
    role: JudgeRole
    judge_family: JudgeFamily


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


def _mapping_entry(value: Any, model_id: str) -> ModelFamilyMapping:
    if isinstance(value, str):
        family = value.strip()
        normalized = family.casefold()
        if normalized.endswith("_frontier"):
            base_family = normalized.removesuffix("_frontier")
            if base_family not in {"claude", "gpt"}:
                raise JudgeConfigurationError(
                    f"model_family_map entry {model_id} has an invalid frontier family"
                )
            return ModelFamilyMapping(family=base_family, role="frontier")
        if normalized == "open_evaluator":
            return ModelFamilyMapping(family=family, role="open_evaluator")
        inferred_role: JudgeRole = (
            "frontier" if normalized in {"claude", "gpt"} else "open_evaluator"
        )
        return ModelFamilyMapping(family=family, role=inferred_role)
    if not isinstance(value, Mapping):
        raise JudgeConfigurationError(
            f"model_family_map entry {model_id} must be a family string or object"
        )
    family = _required_string(value, "family", "model_family")
    normalized = family.casefold()
    role_value = value.get("role")
    if role_value is None:
        role_value = (
            "frontier"
            if normalized in {"claude", "gpt", "claude_frontier", "gpt_frontier"}
            else "open_evaluator"
        )
    if not isinstance(role_value, str) or role_value not in {
        "frontier",
        "open_evaluator",
    }:
        raise JudgeConfigurationError(
            f"model_family_map entry {model_id} has an invalid role"
        )
    mapping_role = cast(JudgeRole, role_value)
    if mapping_role == "frontier":
        normalized_frontier_family = {
            "claude": "claude",
            "claude_frontier": "claude",
            "gpt": "gpt",
            "gpt_frontier": "gpt",
        }.get(normalized)
        if normalized_frontier_family is None:
            raise JudgeConfigurationError(
                f"model_family_map entry {model_id} has an invalid frontier family"
            )
        return ModelFamilyMapping(family=normalized_frontier_family, role=mapping_role)
    return ModelFamilyMapping(family=family, role=mapping_role)


def _model_family_map(
    values: Mapping[str, Any],
) -> tuple[tuple[str, ModelFamilyMapping], ...]:
    raw = values.get("model_family_map", values.get("model_id_to_family"))
    if not isinstance(raw, Mapping) or not raw:
        raise JudgeConfigurationError(
            "model_family_map must map reported model IDs to families"
        )
    result: list[tuple[str, ModelFamilyMapping]] = []
    for model_id, value in raw.items():
        if not isinstance(model_id, str) or not model_id.strip():
            raise JudgeConfigurationError(
                "model_family_map keys must be non-empty model IDs"
            )
        result.append((model_id.strip(), _mapping_entry(value, model_id)))
    return tuple(result)


def _base_family(value: str) -> str:
    normalized = value.strip().casefold()
    return {
        "claude_frontier": "claude",
        "gpt_frontier": "gpt",
    }.get(normalized, normalized)


@dataclass(frozen=True)
class JudgeConfig:
    """Immutable settings for one generic or benchmark-native judge."""

    task: JudgeTask
    model: str
    judge_id: str
    model_family_map: tuple[tuple[str, ModelFamilyMapping], ...]
    base_url_env: str
    credential_env: str
    template_path: Path
    seed: int
    temperature: float | None
    top_p: float | None
    max_output_tokens: int | None
    stop_rules: tuple[str, ...]
    timeout_seconds: float
    max_retries: int
    presentation_seed: int | None
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
        if task_value not in {"pointwise", "pairwise", "native-pointwise"}:
            raise JudgeConfigurationError(
                "task must be 'pointwise', 'pairwise', or 'native-pointwise'"
            )
        task: JudgeTask = task_value

        model = _required_string(values, "model")
        judge_id = str(values.get("judge_id", model)).strip()
        if not judge_id:
            raise JudgeConfigurationError("judge_id must be a non-empty string")
        model_family_map = _model_family_map(values)

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
        temperature = (
            None
            if temperature_value is None
            else _number(temperature_value, "temperature")
        )
        if temperature is not None and temperature != 0:
            raise JudgeConfigurationError("temperature must be exactly 0")

        top_p_value = _decoding_value(
            values, decoding_value, "top_p_or_equivalent", "top_p"
        )
        top_p = (
            None
            if top_p_value is None
            else _number(top_p_value, "top_p_or_equivalent", minimum=0)
        )
        if top_p is not None and top_p > 1:
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

        presentation_seed_value = values.get("presentation_seed")
        if task == "pairwise" and presentation_seed_value is None:
            raise JudgeConfigurationError(
                "presentation_seed is required for pairwise judging"
            )
        presentation_seed = (
            _integer(presentation_seed_value, "presentation_seed")
            if presentation_seed_value is not None
            else None
        )

        return cls(
            task=task,
            model=model,
            judge_id=judge_id,
            model_family_map=model_family_map,
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
            presentation_seed=presentation_seed,
            source_path=source_path,
        )

    def resolve_model_identity(self, reported_model_id: str) -> JudgeIdentity:
        """Map the endpoint's reported model ID to a protocol judge family."""

        mapping = dict(self.model_family_map).get(reported_model_id)
        if mapping is None:
            raise JudgeConfigurationError(
                "reported model is not present in model_family_map"
            )
        base_family = _base_family(mapping.family)
        if mapping.role == "frontier":
            if base_family not in {"claude", "gpt"}:
                raise JudgeConfigurationError(
                    "model_family_map has an invalid frontier family"
                )
            judge_family = cast(JudgeFamily, f"{base_family}_frontier")
        else:
            judge_family = "open_evaluator"
        return JudgeIdentity(
            reported_model_id=reported_model_id,
            mapped_family=base_family,
            role=mapping.role,
            judge_family=judge_family,
        )

    def validate_family_audit(
        self, identity: JudgeIdentity, generator_family: str
    ) -> None:
        """Reject empty generator families and family overlap."""

        generator_base = _base_family(generator_family)
        if not generator_base:
            raise JudgeConfigurationError(
                "run manifest needs a non-empty generator model family"
            )
        if identity.mapped_family == generator_base:
            raise JudgeConfigurationError("judge and generator model families overlap")
