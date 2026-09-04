"""Single-call judge execution with bounded fail-closed retries."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic_ai.models import Model

from .client import JudgeOutput, OpenAICompatibleClient
from .config import JudgeConfig, JudgeIdentity
from .errors import JudgeValidationError
from .templates import JudgeTemplate
from .validation import (
    NativePointwiseJudgeRecord,
    PairwiseJudgeRecord,
    PointwiseJudgeRecord,
    validate_native_pointwise,
    validate_pairwise,
    validate_pointwise,
)


@dataclass(frozen=True)
class JudgeResult:
    """Validated protocol record plus response accounting."""

    record: dict[str, Any]
    usage: dict[str, int]
    attempts: int
    response_sha256: str
    template_sha256: str
    judge_identity: JudgeIdentity


def _run(
    config: JudgeConfig,
    *,
    values: dict[str, Any],
    output_type: type[JudgeOutput],
    validator: Callable[[Any], dict[str, Any]],
    model: Model | None = None,
    prompt_cache_key: str = "judge-default",
    system_prompt: str | None = None,
) -> JudgeResult:
    template = JudgeTemplate.load(config.template_path)
    prompt = template.render(values)
    client = OpenAICompatibleClient(config, model=model)

    # Keep retries and final record normalization in one callback seam so the
    # native score/reason response needs no parallel judge engine.
    def validate_output(output: JudgeOutput) -> None:
        validator(output.model_dump())

    response = client.complete(
        prompt,
        output_type=output_type,
        output_validator=validate_output,
        system_prompt=system_prompt,
        # Reuse the caller's run-scoped cache namespace at the transport seam.
        prompt_cache_key=prompt_cache_key,
    )
    identity = config.resolve_model_identity(response.reported_model_id)
    record = validator(response.output.model_dump())
    record["judge_family"] = identity.judge_family
    return JudgeResult(
        record=record,
        usage=dict(response.usage),
        attempts=response.attempts,
        response_sha256=hashlib.sha256(response.content.encode("utf-8")).hexdigest(),
        template_sha256=template.sha256,
        judge_identity=identity,
    )


def judge_pointwise(
    config: JudgeConfig,
    *,
    assignment: str,
    context: str,
    output: str,
    prompt_id: str,
    blind_condition_id: str,
    platform: str,
    model: Model | None = None,
    prompt_cache_key: str = "judge-default",
) -> JudgeResult:
    """Score one output against the five protocol dimensions."""

    if config.task != "pointwise":
        raise JudgeValidationError("Judge configuration task is not pointwise")
    expected = {
        "prompt_id": prompt_id,
        "condition_id": blind_condition_id,
        "platform": platform,
        "judge_id": config.judge_id,
    }
    values = {
        "prompt_id": prompt_id,
        "condition_id": blind_condition_id,
        "platform": platform,
        "judge_id": config.judge_id,
        "judge_family": "runtime-verified",
        "assignment": assignment,
        "context": context or "(none)",
        "output": output,
    }
    response_expected = {
        field: value for field, value in expected.items() if field != "judge_family"
    }

    def validator(value: Any) -> dict[str, Any]:
        return validate_pointwise(
            value,
            expected=response_expected,
            searchable_texts=(output, context),
        )

    return _run(
        config,
        values=values,
        output_type=PointwiseJudgeRecord,
        validator=validator,
        model=model,
        # Keep pointwise calls on the same run-scoped cache namespace.
        prompt_cache_key=prompt_cache_key,
    )


def judge_pairwise(
    config: JudgeConfig,
    *,
    assignment: str,
    context: str,
    output_a: str,
    output_b: str,
    prompt_id: str,
    pair_id: str,
    presentation: str,
    platform: str,
    model: Model | None = None,
    prompt_cache_key: str = "judge-default",
) -> JudgeResult:
    """Compare two blinded outputs in the supplied presentation order."""

    if config.task != "pairwise":
        raise JudgeValidationError("Judge configuration task is not pairwise")
    if presentation not in {"A|B", "B|A"}:
        raise JudgeValidationError("presentation must be A|B or B|A")
    expected = {
        "prompt_id": prompt_id,
        "platform": platform,
        "judge_id": config.judge_id,
        "pair_id": pair_id,
        "presentation": presentation,
    }
    values = {
        "prompt_id": prompt_id,
        "pair_id": pair_id,
        "presentation": presentation,
        "platform": platform,
        "judge_id": config.judge_id,
        "judge_family": "runtime-verified",
        "assignment": assignment,
        "context": context or "(none)",
        "answer_a": output_a,
        "answer_b": output_b,
    }
    response_expected = {
        field: value for field, value in expected.items() if field != "judge_family"
    }

    def validator(value: Any) -> dict[str, Any]:
        return validate_pairwise(
            value,
            expected=response_expected,
            output_a=output_a,
            output_b=output_b,
            context=context,
        )

    return _run(
        config,
        values=values,
        output_type=PairwiseJudgeRecord,
        validator=validator,
        model=model,
        # Keep both pairwise presentations on the same run-scoped cache namespace.
        prompt_cache_key=prompt_cache_key,
    )


def judge_native_pointwise(
    config: JudgeConfig,
    *,
    assignment: str,
    output: str,
    criterion: Mapping[str, str],
    prompt_id: str,
    blind_condition_id: str,
    platform: str,
    model: Model | None = None,
    prompt_cache_key: str = "judge-default",
) -> JudgeResult:
    """Score one WritingBench checklist criterion with the upstream JSON shape."""

    if config.task != "native-pointwise":
        raise JudgeValidationError("Judge configuration task is not native-pointwise")
    criterion_name = criterion.get("name", "")
    if not criterion_name.strip():
        raise JudgeValidationError("WritingBench criterion name must be non-empty")
    expected = {
        "prompt_id": prompt_id,
        "condition_id": blind_condition_id,
        "platform": platform,
        "judge_id": config.judge_id,
    }
    response_expected = {
        field: value for field, value in expected.items() if field != "judge_family"
    }
    values = {
        "query": assignment,
        "response": output,
        "criteria": json.dumps(criterion, ensure_ascii=False, indent=2),
    }

    def validator(value: Any) -> dict[str, Any]:
        return validate_native_pointwise(
            value,
            expected=response_expected,
            criterion_name=criterion_name,
        )

    return _run(
        config,
        values=values,
        output_type=NativePointwiseJudgeRecord,
        validator=validator,
        model=model,
        system_prompt=(
            "You are an expert evaluator with extensive experience in evaluating "
            "response of given query."
        ),
        # Reuse the caller's run-scoped cache namespace across checklist criteria.
        prompt_cache_key=prompt_cache_key,
    )
