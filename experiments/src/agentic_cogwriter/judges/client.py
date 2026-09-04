"""Pydantic AI client used by the OpenAI-compatible judge stage."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, NoReturn

from pydantic import ValidationError
from pydantic_ai import Agent, ModelResponse, ModelRetry, ModelSettings, RunUsage
from pydantic_ai.exceptions import (
    ModelAPIError,
    ModelHTTPError,
    UnexpectedModelBehavior,
    UserError,
)
from pydantic_ai.models import Model
from pydantic_ai.models.openai import (
    OpenAIChatModel,
    OpenAIModelProfile,
)
from pydantic_ai.providers.openai import OpenAIProvider

from .config import JudgeConfig
from .errors import JudgeConfigurationError, JudgeTransportError, JudgeValidationError
from .validation import PairwiseJudgeRecord, PointwiseJudgeRecord

JudgeOutput = PointwiseJudgeRecord | PairwiseJudgeRecord


@dataclass(frozen=True)
class JudgeResponse:
    """A validated structured output and pydantic-ai accounting."""

    content: str
    output: JudgeOutput
    usage: Mapping[str, int]
    reported_model_id: str
    attempts: int


def normalize_usage(value: Mapping[str, Any]) -> dict[str, int]:
    """Validate the token counters recorded for every accepted response."""

    result: dict[str, int] = {}
    for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
        token_value = value.get(field)
        if isinstance(token_value, bool) or not isinstance(token_value, int):
            raise JudgeTransportError(f"Judge usage is missing integer {field}")
        if token_value < 0:
            raise JudgeTransportError(f"Judge usage has negative {field}")
        result[field] = token_value
    for field in ("reasoning_tokens", "cached_tokens"):
        if field not in value:
            continue
        token_value = value[field]
        if (
            isinstance(token_value, bool)
            or not isinstance(token_value, int)
            or token_value < 0
        ):
            raise JudgeTransportError(f"Judge usage has invalid integer {field}")
        result[field] = token_value
    return result


def _usage(run_usage: RunUsage) -> dict[str, int]:
    """Map pydantic-ai usage names to the frozen score-manifest names."""

    values: dict[str, Any] = {
        "prompt_tokens": run_usage.input_tokens,
        "completion_tokens": run_usage.output_tokens,
        "total_tokens": run_usage.total_tokens,
    }
    reasoning_tokens = run_usage.details.get("reasoning_tokens")
    if "reasoning_tokens" in run_usage.details:
        values["reasoning_tokens"] = reasoning_tokens
    cached_tokens = run_usage.cache_read_tokens
    if cached_tokens:
        values["cached_tokens"] = cached_tokens
    return normalize_usage(values)


def _response_content(response: ModelResponse) -> str:
    """Return the raw structured arguments used for response hashing."""

    tool_calls = response.tool_calls
    if tool_calls:
        arguments = tool_calls[-1].args
        if isinstance(arguments, str):
            return arguments
        if isinstance(arguments, Mapping):
            return json.dumps(arguments, ensure_ascii=False, sort_keys=True)
    text = response.text
    if isinstance(text, str) and text:
        return text
    raise JudgeTransportError("Judge response has no structured output")


def _error_body(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _validation_detail(error: UnexpectedModelBehavior) -> str:
    cause = error.__cause__
    if isinstance(cause, ValidationError) and any(
        item.get("type") == "json_invalid" for item in cause.errors()
    ):
        return "Judge response is not valid JSON"
    return "Judge response failed structured-output validation"


def _raise_library_error(error: Exception) -> NoReturn:
    """Map every pydantic-ai failure to a judge-stage error type."""

    if isinstance(error, ModelHTTPError):
        raise JudgeTransportError(
            f"Judge endpoint returned HTTP status {error.status_code}",
            response_body=_error_body(error.body),
        ) from error
    if isinstance(error, UnexpectedModelBehavior):
        if "maximum output retries" in str(error):
            raise JudgeValidationError(_validation_detail(error)) from error
        raise JudgeTransportError(
            "Judge model returned unusable output",
            response_body=_error_body(error.body) or str(error),
        ) from error
    if isinstance(error, (ModelAPIError, UserError)):
        raise JudgeTransportError(
            "Judge model request failed",
            response_body=_error_body(getattr(error, "body", None)) or str(error),
        ) from error
    raise JudgeTransportError(
        "Judge model request failed", response_body=str(error)
    ) from error


class OpenAICompatibleClient:
    """Run one structured judge request through pydantic-ai."""

    def __init__(self, config: JudgeConfig, *, model: Model | None = None) -> None:
        self.config = config
        self.model = model

    def _configured_model(self) -> Model:
        base_url = os.environ.get(self.config.base_url_env)
        credential = os.environ.get(self.config.credential_env)
        if not base_url:
            raise JudgeConfigurationError(
                "Configured judge base URL environment variable is unset"
            )
        if not credential:
            raise JudgeConfigurationError(
                "Configured judge credential environment variable is unset"
            )
        return OpenAIChatModel(
            self.config.model,
            provider=OpenAIProvider(base_url=base_url, api_key=credential),
            profile=OpenAIModelProfile(
                openai_supports_reasoning=False,
                openai_reasoning_enabled_by_default=False,
                openai_chat_supports_max_completion_tokens=True,
            ),
        )

    def complete(
        self,
        prompt: str,
        *,
        output_type: type[JudgeOutput],
        output_validator: Callable[[JudgeOutput], None] | None = None,
    ) -> JudgeResponse:
        """Run one pydantic-ai request with bounded structured-output retries."""

        settings: ModelSettings = {
            "seed": self.config.seed,
            "timeout": self.config.timeout_seconds,
        }
        if self.config.stop_rules:
            settings["stop_sequences"] = list(self.config.stop_rules)
        if self.config.temperature is not None:
            settings["temperature"] = self.config.temperature
        if self.config.top_p is not None:
            settings["top_p"] = self.config.top_p
        if self.config.max_output_tokens is not None:
            settings["max_tokens"] = self.config.max_output_tokens

        model = self.model or self._configured_model()
        if output_type is PointwiseJudgeRecord:
            agent: Any = Agent(
                model,
                output_type=PointwiseJudgeRecord,
                system_prompt="Return only the JSON object requested by the user.",
                model_settings=settings,
                retries=self.config.max_retries,
            )
        else:
            agent = Agent(
                model,
                output_type=PairwiseJudgeRecord,
                system_prompt="Return only the JSON object requested by the user.",
                model_settings=settings,
                retries=self.config.max_retries,
            )
        if output_validator is not None:

            @agent.output_validator  # noqa: V103
            def _validate_output(output: JudgeOutput) -> JudgeOutput:
                try:
                    output_validator(output)
                except JudgeValidationError as error:
                    raise ModelRetry(str(error)) from error
                return output

        try:
            result = agent.run_sync(prompt)
        except (JudgeConfigurationError, JudgeTransportError, JudgeValidationError):
            raise
        except Exception as error:
            _raise_library_error(error)

        reported_model_id = result.response.model_name
        if not isinstance(reported_model_id, str) or not reported_model_id.strip():
            raise JudgeTransportError("Judge response has no reported model identifier")
        content = _response_content(result.response)
        usage = _usage(result.usage)
        output = result.output
        if not isinstance(output, (PointwiseJudgeRecord, PairwiseJudgeRecord)):
            raise JudgeTransportError("Judge response has an unexpected output type")
        return JudgeResponse(
            content=content,
            output=output,
            usage=usage,
            reported_model_id=reported_model_id.strip(),
            attempts=result.usage.requests,
        )
