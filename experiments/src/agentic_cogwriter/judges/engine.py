"""Single-call judge execution with bounded fail-closed retries."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic_ai.models import Model

from .client import JudgeOutput, OpenAICompatibleClient
from .config import JudgeConfig, JudgeIdentity
from .errors import JudgeValidationError
from .templates import JudgeTemplate
from .validation import (
    PairwiseJudgeRecord,
    PointwiseJudgeRecord,
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
    expected: Mapping[str, str],
    validator: Any,
    searchable_texts: Sequence[str] | None = None,
    pairwise_texts: tuple[str, str, str] | None = None,
    model: Model | None = None,
    prompt_cache_key: str = "judge-default",
) -> JudgeResult:
    template = JudgeTemplate.load(config.template_path)
    prompt = template.render(values)
    client = OpenAICompatibleClient(config, model=model)
    response_expected = {
        field: value for field, value in expected.items() if field != "judge_family"
    }

    def validate_output(output: JudgeOutput) -> None:
        payload = output.model_dump()
        if pairwise_texts is None:
            validator(
                payload,
                expected=response_expected,
                searchable_texts=searchable_texts or (),
            )
        else:
            validator(
                payload,
                expected=response_expected,
                output_a=pairwise_texts[0],
                output_b=pairwise_texts[1],
                context=pairwise_texts[2],
            )

    response = client.complete(
        prompt,
        output_type=(
            PointwiseJudgeRecord if pairwise_texts is None else PairwiseJudgeRecord
        ),
        output_validator=validate_output,
        # Reuse the caller's run-scoped cache namespace at the transport seam.
        prompt_cache_key=prompt_cache_key,
    )
    identity = config.resolve_model_identity(response.reported_model_id)
    if pairwise_texts is None:
        record = validator(
            response.output.model_dump(),
            expected=response_expected,
            searchable_texts=searchable_texts or (),
        )
    else:
        record = validator(
            response.output.model_dump(),
            expected=response_expected,
            output_a=pairwise_texts[0],
            output_b=pairwise_texts[1],
            context=pairwise_texts[2],
        )
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
    return _run(
        config,
        values=values,
        expected=expected,
        validator=validate_pointwise,
        searchable_texts=(output, context),
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
    return _run(
        config,
        values=values,
        expected=expected,
        validator=validate_pairwise,
        pairwise_texts=(output_a, output_b, context),
        model=model,
        # Keep both pairwise presentations on the same run-scoped cache namespace.
        prompt_cache_key=prompt_cache_key,
    )
