"""Single-call judge execution with bounded fail-closed retries."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .client import ChatResponse, ChatTransport, OpenAICompatibleClient
from .config import JudgeConfig, JudgeIdentity
from .errors import JudgeError, JudgeValidationError
from .templates import JudgeTemplate
from .validation import validate_pairwise, validate_pointwise


@dataclass(frozen=True)
class JudgeResult:
    """Validated protocol record plus response accounting."""

    record: dict[str, Any]
    usage: dict[str, int]
    attempts: int
    response_sha256: str
    template_sha256: str
    judge_identity: JudgeIdentity


def _response_sha256(response: ChatResponse) -> str:
    return hashlib.sha256(response.content.encode("utf-8")).hexdigest()


def _parse_json(content: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise JudgeValidationError("Judge response is not valid JSON") from exc


def _run(
    config: JudgeConfig,
    *,
    values: dict[str, Any],
    expected: Mapping[str, str],
    validator: Any,
    searchable_texts: Sequence[str] | None = None,
    pairwise_texts: tuple[str, str, str] | None = None,
    transport: ChatTransport | None = None,
) -> JudgeResult:
    template = JudgeTemplate.load(config.template_path)
    prompt = template.render(values)
    client = OpenAICompatibleClient(config, transport=transport)
    last_error: JudgeError | None = None
    for attempt in range(1, config.max_retries + 2):
        try:
            response = client.complete(prompt)
            identity = config.resolve_model_identity(response.reported_model_id or "")
            payload = _parse_json(response.content)
            if not isinstance(payload, Mapping) or not isinstance(
                payload.get("judge_family"), str
            ):
                raise JudgeValidationError(
                    "Judge response must include a string judge_family field"
                )
            response_expected = {
                field: value
                for field, value in expected.items()
                if field != "judge_family"
            }
            if pairwise_texts is None:
                record = validator(
                    payload,
                    expected=response_expected,
                    searchable_texts=searchable_texts or (),
                )
            else:
                record = validator(
                    payload,
                    expected=response_expected,
                    output_a=pairwise_texts[0],
                    output_b=pairwise_texts[1],
                    context=pairwise_texts[2],
                )
            record["judge_family"] = identity.judge_family
            return JudgeResult(
                record=record,
                usage=dict(response.usage),
                attempts=attempt,
                response_sha256=_response_sha256(response),
                template_sha256=template.sha256,
                judge_identity=identity,
            )
        except JudgeValidationError as exc:
            last_error = exc
        except JudgeError:
            raise
    detail = str(last_error) if last_error is not None else "unknown validation error"
    raise JudgeValidationError(
        f"Judge response rejected after {config.max_retries + 1} attempts: {detail}"
    ) from last_error


def judge_pointwise(
    config: JudgeConfig,
    *,
    assignment: str,
    context: str,
    output: str,
    prompt_id: str,
    blind_condition_id: str,
    platform: str,
    transport: ChatTransport | None = None,
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
        transport=transport,
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
    transport: ChatTransport | None = None,
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
        transport=transport,
    )
