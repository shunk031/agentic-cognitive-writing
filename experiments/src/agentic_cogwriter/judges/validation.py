"""Fail-closed validation for the generic and WritingBench-native contracts."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .errors import JudgeValidationError

POINTWISE_DIMENSIONS = (
    "instruction_fulfillment",
    "organization_global_coherence",
    "content_adequacy_depth",
    "style_voice_audience_fit",
    "factuality_constraint_fidelity",
)

_POINTWISE_KEYS = {
    "prompt_id",
    "condition_id",
    "platform",
    "judge_id",
    "judge_family",
    "scores",
    "evidence_quotes",
    "judge_level_composite",
    "uncertainties",
}
_PAIRWISE_KEYS = {
    "prompt_id",
    "platform",
    "judge_id",
    "judge_family",
    "pair_id",
    "presentation",
    "winner",
    "evidence_quotes",
    "reason",
}
_NATIVE_POINTWISE_KEYS = {"score", "reason"}


class _StrictRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)  # noqa: V107


class EvidenceQuote(_StrictRecord):
    """One pointwise evidence quote, before text-presence validation."""

    dimension: str
    quote: str

    @field_validator("quote")  # noqa: V105
    @classmethod
    def _valid_quote(cls, value: str) -> str:
        if not value or value != value.strip() or len(value) > 240:
            raise ValueError("quote must be a non-empty short string")
        return value


class PointwiseScores(_StrictRecord):
    """The five integer dimensions in the pointwise contract."""

    instruction_fulfillment: int = Field(ge=1, le=5)  # noqa: V107
    organization_global_coherence: int = Field(ge=1, le=5)  # noqa: V107
    content_adequacy_depth: int = Field(ge=1, le=5)  # noqa: V107
    style_voice_audience_fit: int = Field(ge=1, le=5)  # noqa: V107
    factuality_constraint_fidelity: int = Field(ge=1, le=5)  # noqa: V107


class PointwiseJudgeRecord(_StrictRecord):
    """Pydantic structured-output contract for one pointwise judgment."""

    prompt_id: str
    condition_id: str
    platform: str
    judge_id: str
    judge_family: str
    scores: PointwiseScores
    evidence_quotes: list[EvidenceQuote]  # noqa: V107
    judge_level_composite: float = Field(allow_inf_nan=False)  # noqa: V107
    uncertainties: list[str]


class NativePointwiseJudgeRecord(_StrictRecord):
    """The upstream WritingBench response object for one checklist criterion."""

    score: int = Field(ge=1, le=10)  # noqa: V107
    reason: str

    @field_validator("reason")  # noqa: V105
    @classmethod
    def _non_empty_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reason must be a non-empty string")
        return value


class PairwiseEvidence(_StrictRecord):
    """The two output-specific evidence lists in the pairwise contract."""

    A: list[str]  # noqa: V107
    B: list[str]  # noqa: V107

    @field_validator("A", "B")  # noqa: V105
    @classmethod
    def _valid_quotes(cls, value: list[str]) -> list[str]:
        if not value or any(
            not quote or quote != quote.strip() or len(quote) > 240 for quote in value
        ):
            raise ValueError("evidence quotes must contain one or more short strings")
        return value


class PairwiseJudgeRecord(_StrictRecord):
    """Pydantic structured-output contract for one pairwise judgment."""

    prompt_id: str
    platform: str
    judge_id: str
    judge_family: str
    pair_id: str
    presentation: str
    winner: str  # noqa: V107
    evidence_quotes: PairwiseEvidence  # noqa: V107
    reason: str


def _validated_mapping(
    value: Any, model: type[BaseModel], label: str
) -> Mapping[str, Any]:
    try:
        parsed = model.model_validate(value, strict=True)
    except ValidationError as exc:
        detail = "; ".join(
            ".".join(str(item) for item in error["loc"]) + ": " + error["msg"]
            for error in exc.errors()
        )
        raise JudgeValidationError(f"{label} has invalid fields: {detail}") from exc
    return parsed.model_dump()


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        missing = sorted(expected - set(value))
        extra = sorted(set(value) - expected)
        detail = []
        if missing:
            detail.append("missing " + ", ".join(missing))
        if extra:
            detail.append("unknown " + ", ".join(extra))
        raise JudgeValidationError(f"{label} has invalid fields: {'; '.join(detail)}")


def _metadata(value: Mapping[str, Any], expected: Mapping[str, str]) -> None:
    for field, expected_value in expected.items():
        if value.get(field) != expected_value:
            raise JudgeValidationError(f"{field} does not match the scored request")


def _quote_list(
    value: Any,
    *,
    label: str,
    searchable_texts: Sequence[str],
) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise JudgeValidationError(f"{label} must be a list")
    result: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, Mapping) or set(item) != {"dimension", "quote"}:
            raise JudgeValidationError(f"{label} has an invalid evidence item")
        dimension = item.get("dimension")
        quote = item.get("quote")
        if not isinstance(dimension, str) or not isinstance(quote, str):
            raise JudgeValidationError(f"{label} evidence fields must be strings")
        if not quote or quote != quote.strip() or len(quote) > 240:
            raise JudgeValidationError(f"{label} contains an invalid evidence quote")
        if not any(quote in text for text in searchable_texts):
            raise JudgeValidationError(
                f"Evidence quote for {dimension} was not found verbatim"
            )
        result.append({"dimension": dimension, "quote": quote})
    return result


def validate_pointwise(
    value: Any,
    *,
    expected: Mapping[str, str],
    searchable_texts: Sequence[str],
) -> dict[str, Any]:
    """Validate and return one exact protocol pointwise object."""

    value = _validated_mapping(value, PointwiseJudgeRecord, "Pointwise response")
    if not isinstance(value, Mapping):
        raise JudgeValidationError("Pointwise response must be a JSON object")
    _exact_keys(value, _POINTWISE_KEYS, "Pointwise response")
    _metadata(value, expected)

    scores = value["scores"]
    if not isinstance(scores, Mapping) or set(scores) != set(POINTWISE_DIMENSIONS):
        raise JudgeValidationError("Pointwise scores are missing dimensions")
    normalized_scores: dict[str, int] = {}
    for dimension in POINTWISE_DIMENSIONS:
        score = scores[dimension]
        if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 5:
            raise JudgeValidationError(
                f"Pointwise score for {dimension} must be an integer from 1 to 5"
            )
        normalized_scores[dimension] = score

    raw_quotes = _quote_list(
        value["evidence_quotes"],
        label="Pointwise evidence_quotes",
        searchable_texts=searchable_texts,
    )
    if len(raw_quotes) != len(POINTWISE_DIMENSIONS):
        raise JudgeValidationError(
            "Pointwise evidence_quotes must cover all dimensions"
        )
    dimensions = [item["dimension"] for item in raw_quotes]
    if set(dimensions) != set(POINTWISE_DIMENSIONS) or len(set(dimensions)) != len(
        dimensions
    ):
        raise JudgeValidationError(
            "Pointwise evidence_quotes must cover each dimension once"
        )

    composite = value["judge_level_composite"]
    if (
        isinstance(composite, bool)
        or not isinstance(composite, (int, float))
        or not math.isfinite(float(composite))
    ):
        raise JudgeValidationError("judge_level_composite must be a finite number")
    uncertainties = value["uncertainties"]
    if not isinstance(uncertainties, list) or not all(
        isinstance(item, str) for item in uncertainties
    ):
        raise JudgeValidationError("uncertainties must be a string list")
    return {
        **{field: value[field] for field in expected},
        "scores": normalized_scores,
        "evidence_quotes": raw_quotes,
        "judge_level_composite": float(composite),
        "uncertainties": list(uncertainties),
    }


def validate_native_pointwise(
    value: Any,
    *,
    expected: Mapping[str, str],
    criterion_name: str,
) -> dict[str, Any]:
    """Validate one WritingBench score and attach existing judge metadata."""

    value = _validated_mapping(
        value, NativePointwiseJudgeRecord, "WritingBench native response"
    )
    if not isinstance(value, Mapping):
        raise JudgeValidationError("WritingBench native response must be a JSON object")
    _exact_keys(value, _NATIVE_POINTWISE_KEYS, "WritingBench native response")
    if not criterion_name.strip():
        raise JudgeValidationError("WritingBench criterion name must be non-empty")
    return {
        **expected,
        "criterion": criterion_name,
        "score": value["score"],
        "reason": value["reason"],
    }


def _string_list(value: Any, label: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or not all(
            isinstance(item, str) and item and item == item.strip() and len(item) <= 240
            for item in value
        )
    ):
        raise JudgeValidationError(f"{label} must contain one or more short strings")
    return list(value)


def validate_pairwise(
    value: Any,
    *,
    expected: Mapping[str, str],
    output_a: str,
    output_b: str,
    context: str,
) -> dict[str, Any]:
    """Validate and return one exact protocol pairwise object."""

    value = _validated_mapping(value, PairwiseJudgeRecord, "Pairwise response")
    if not isinstance(value, Mapping):
        raise JudgeValidationError("Pairwise response must be a JSON object")
    _exact_keys(value, _PAIRWISE_KEYS, "Pairwise response")
    _metadata(value, expected)
    if value["winner"] not in {"A", "B", "tie"}:
        raise JudgeValidationError("winner must be A, B, or tie")
    if value["presentation"] not in {"A|B", "B|A"}:
        raise JudgeValidationError("presentation must be A|B or B|A")

    evidence = value["evidence_quotes"]
    if not isinstance(evidence, Mapping) or set(evidence) != {"A", "B"}:
        raise JudgeValidationError("Pairwise evidence_quotes must contain A and B")
    quotes_a = _string_list(evidence["A"], "Pairwise evidence_quotes.A")
    quotes_b = _string_list(evidence["B"], "Pairwise evidence_quotes.B")
    texts_a = (output_a, context) if context else (output_a,)
    texts_b = (output_b, context) if context else (output_b,)
    for quote in quotes_a:
        if not any(quote in text for text in texts_a):
            raise JudgeValidationError(
                "Evidence quote for output A was not found verbatim"
            )
    for quote in quotes_b:
        if not any(quote in text for text in texts_b):
            raise JudgeValidationError(
                "Evidence quote for output B was not found verbatim"
            )
    reason = value["reason"]
    if not isinstance(reason, str) or not reason.strip():
        raise JudgeValidationError("reason must be a non-empty string")
    return {
        **{field: value[field] for field in expected},
        "pair_id": value["pair_id"],
        "presentation": value["presentation"],
        "winner": value["winner"],
        "evidence_quotes": {"A": quotes_a, "B": quotes_b},
        "reason": reason,
    }
