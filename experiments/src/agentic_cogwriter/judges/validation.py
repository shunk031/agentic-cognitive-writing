"""Fail-closed validation for the frozen pointwise and pairwise contracts."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

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
