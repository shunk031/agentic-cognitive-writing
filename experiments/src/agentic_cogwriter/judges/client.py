"""Pydantic AI client used by the OpenAI-compatible judge stage."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from pydantic_ai import (
    Agent,
    CachePoint,
    ModelResponse,
    ModelRetry,
    ModelSettings,
    PromptedOutput,
    RunUsage,
    UserContent,
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
    """Return the raw JSON text used for response hashing."""

    text = response.text
    if isinstance(text, str) and text:
        return text
    raise JudgeTransportError("Judge response has no structured output")


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
                # The configured judge gateway uses GPT-5.6's explicit cache
                # breakpoint contract.
                openai_supports_prompt_cache_breakpoints=self.config.model.casefold().startswith(
                    "gpt-5.6"
                ),
            ),
        )

    def complete(
        self,
        prompt: str,
        *,
        output_type: type[JudgeOutput],
        output_validator: Callable[[JudgeOutput], None] | None = None,
        prompt_cache_key: str = "judge-default",
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
        if self.config.model.casefold().startswith("gpt-5.6"):
            # Keep the run-directory key and explicit 30-minute policy on every retry.
            typed_settings = cast(dict[str, Any], settings)
            typed_settings["openai_prompt_cache_key"] = prompt_cache_key
            typed_settings["openai_prompt_cache_options"] = {
                "mode": "explicit",
                "ttl": "30m",
            }

        model = self.model or self._configured_model()
        agent: Agent[object, JudgeOutput] = Agent(
            model,
            # Templates carry the JSON contract; parse their text without
            # output tools.
            output_type=PromptedOutput(output_type, template=False),
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

        # Reassemble at the existing transport seam so judged text stays in the
        # cached block while rubric and format text follows it.
        format_marker = "\nReturn this JSON shape"
        prompt_content: str | list[UserContent] = prompt
        if (
            self.config.model.casefold().startswith("gpt-5.6")
            and format_marker in prompt
        ):
            prefix, format_suffix = prompt.rsplit(format_marker, 1)
            rubric_marker = (
                "\nUse the five dimensions below."
                if "\nUse the five dimensions below." in prefix
                else "\nReturn exactly one valid JSON object."
            )
            data_marker = "\n[Prompt ID]"
            if rubric_marker in prefix and data_marker in prefix:
                static_prefix, rubric_and_data = prefix.split(rubric_marker, 1)
                rubric, judged_data = rubric_and_data.split(data_marker, 1)
                prefix = static_prefix + data_marker + judged_data
                suffix = rubric_marker + rubric + format_marker + format_suffix
            else:
                suffix = format_marker + format_suffix
            prompt_content = [prefix, CachePoint(), suffix]
        result = agent.run_sync(prompt_content)

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
