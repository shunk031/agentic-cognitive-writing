"""OpenAI-compatible chat-completions transport used by the judge stage."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from .config import JudgeConfig
from .errors import JudgeConfigurationError, JudgeTransportError


@dataclass(frozen=True)
class ChatResponse:
    """The response text, usage counters, and raw API response."""

    content: str
    usage: Mapping[str, int]
    raw: Mapping[str, Any]
    reported_model_id: str | None = None


class ChatTransport(Protocol):
    """Transport boundary that tests can replace without network access."""

    def complete(
        self,
        *,
        base_url: str,
        api_key: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> ChatResponse:
        """Send one OpenAI-compatible chat-completions request."""


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


def _usage(response: Mapping[str, Any]) -> dict[str, int]:
    value = response.get("usage")
    if not isinstance(value, Mapping):
        raise JudgeTransportError("Judge response has no usage object")
    return normalize_usage(value)


def _content(response: Mapping[str, Any]) -> str:
    output_text = response.get("output_text")
    if isinstance(output_text, str):
        return output_text
    choices = response.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        message = choices[0].get("message")
        if isinstance(message, Mapping):
            content = message.get("content")
            if isinstance(content, str):
                return content
        text = choices[0].get("text")
        if isinstance(text, str):
            return text
    output = response.get("output")
    if isinstance(output, list):
        chunks: list[str] = []
        for item in output:
            if not isinstance(item, Mapping):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if isinstance(part, Mapping) and isinstance(part.get("text"), str):
                    chunks.append(part["text"])
        if chunks:
            return "".join(chunks)
    raise JudgeTransportError("Judge response has no text content")


def _reported_model(response: Mapping[str, Any]) -> str:
    model = response.get("model")
    if not isinstance(model, str) or not model.strip():
        raise JudgeTransportError("Judge response has no reported model identifier")
    return model.strip()


def _http_error_body(error: urllib.error.HTTPError) -> str | None:
    try:
        raw = error.read(JudgeTransportError.MAX_RESPONSE_BODY_LENGTH)
    except (OSError, ValueError):
        return None
    if not raw:
        return None
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return str(raw)


class UrllibChatTransport:
    """Send JSON over the OpenAI-compatible ``/chat/completions`` endpoint."""

    def complete(
        self,
        *,
        base_url: str,
        api_key: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> ChatResponse:
        url = base_url.rstrip("/") + "/chat/completions"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise JudgeTransportError(
                f"Judge endpoint returned HTTP status {exc.code}",
                response_body=_http_error_body(exc),
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise JudgeTransportError("Judge endpoint request failed") from exc
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise JudgeTransportError("Judge endpoint returned invalid JSON") from exc
        if not isinstance(decoded, Mapping):
            raise JudgeTransportError("Judge endpoint returned a non-object response")
        return ChatResponse(
            content=_content(decoded),
            usage=_usage(decoded),
            raw=decoded,
            reported_model_id=_reported_model(decoded),
        )


class OpenAICompatibleClient:
    """Build one deterministic API request from a validated judge config."""

    def __init__(
        self, config: JudgeConfig, *, transport: ChatTransport | None = None
    ) -> None:
        self.config = config
        self.transport = transport or UrllibChatTransport()

    def complete(self, prompt: str) -> ChatResponse:
        """Send one request while resolving endpoint credentials at call time."""

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
        payload: dict[str, object] = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Return only the JSON object requested by the user.",
                },
                {"role": "user", "content": prompt},
            ],
            "seed": self.config.seed,
            "response_format": {"type": "json_object"},
        }
        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature
        if self.config.top_p is not None:
            payload["top_p"] = self.config.top_p
        if self.config.max_output_tokens is not None:
            payload["max_completion_tokens"] = self.config.max_output_tokens
        if self.config.stop_rules:
            payload["stop"] = list(self.config.stop_rules)
        response = self.transport.complete(
            base_url=base_url,
            api_key=credential,
            payload=payload,
            timeout_seconds=self.config.timeout_seconds,
        )
        try:
            usage = normalize_usage(response.usage)
        except (AttributeError, TypeError) as exc:
            raise JudgeTransportError("Judge response has invalid usage") from exc
        reported_model_id = response.reported_model_id
        if not isinstance(reported_model_id, str) or not reported_model_id.strip():
            reported_model_id = _reported_model(response.raw)
        return ChatResponse(
            content=response.content,
            usage=usage,
            raw=response.raw,
            reported_model_id=reported_model_id.strip(),
        )
