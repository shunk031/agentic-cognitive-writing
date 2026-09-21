from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from agentic_cogwriter.judges.client import OpenAICompatibleClient
from agentic_cogwriter.judges.config import JudgeConfig
from agentic_cogwriter.judges.errors import JudgeConfigurationError
from agentic_cogwriter.judges.validation import HelloBenchChecklistRecord


class _FakeEvents:
    def register_first(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class _FakeServiceModel:
    def shape_for(self, _name: str) -> None:
        return None


class _FakeMeta:
    endpoint_url = "https://gateway.test/"
    events = _FakeEvents()
    service_model = _FakeServiceModel()


class _FakeBedrockClient:
    meta = _FakeMeta()

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def converse(self, **request: Any) -> dict[str, Any]:
        self.requests.append(request)
        return {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "text": json.dumps(
                                {
                                    "checklist_items": [
                                        {
                                            "checklist_id": 0,
                                            "reason": (
                                                "The response meets the criterion."
                                            ),
                                            "evaluation_score": 1.0,
                                        }
                                    ]
                                }
                            )
                        }
                    ],
                }
            },
            "stopReason": "end_turn",
            "usage": {
                "inputTokens": 100,
                "outputTokens": 20,
                "totalTokens": 120,
                "cacheReadInputTokens": 7,
                "cacheWriteInputTokens": 3,
            },
            "ResponseMetadata": {"RequestId": "request-1"},
        }


def _config(tmp_path: Path, **overrides: object) -> JudgeConfig:
    template = tmp_path / "judge.md"
    template.write_text("{prompt}", encoding="utf-8")
    values: dict[str, object] = {
        "task": "native-checklist",
        "model": "us.anthropic.claude-opus-5",
        "judge_id": "judge-1",
        "model_family_map": {
            "us.anthropic.claude-opus-5": {
                "family": "claude",
                "role": "frontier",
            }
        },
        "base_url_env": "TEST_JUDGE_BASE_URL",
        "credential_env": "TEST_JUDGE_CREDENTIAL",
        "template_path": str(template),
        "seed": 19,
        "presentation_seed": 23,
        "temperature": None,
        "top_p_or_equivalent": 1,
        "maximum_output_tokens": 120,
        "stop_rules": [],
        "timeout": 10,
        "retry_policy": {"max_retries": 1},
    }
    values.update(overrides)
    return JudgeConfig.from_mapping(values, source_path=tmp_path / "judge.json")


def test_bedrock_transport_builds_request_and_maps_cache_usage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import boto3

    fake_client = _FakeBedrockClient()
    captured: dict[str, Any] = {}

    def fake_boto3_client(*args: Any, **kwargs: Any) -> _FakeBedrockClient:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return fake_client

    monkeypatch.setattr(boto3, "client", fake_boto3_client)
    monkeypatch.setenv("TEST_JUDGE_BASE_URL", "https://gateway.test/")
    monkeypatch.setenv("TEST_JUDGE_CREDENTIAL", "token-is-not-printed")
    config = _config(
        tmp_path,
        transport="bedrock",
        region_name="us-west-2",
        maximum_output_tokens=64,
    )

    response = OpenAICompatibleClient(config).complete(
        "Return one checklist item.",
        output_type=HelloBenchChecklistRecord,
        text_output=True,
    )

    assert captured == {
        "args": ("bedrock-runtime",),
        "kwargs": {
            "endpoint_url": "https://gateway.test/",
            "region_name": "us-west-2",
            "aws_access_key_id": "test",
            "aws_secret_access_key": "test",
            "aws_session_token": "token-is-not-printed",
        },
    }
    request = fake_client.requests[0]
    assert request["modelId"] == "us.anthropic.claude-opus-5"
    assert request["inferenceConfig"]["maxTokens"] == 64
    assert "topP" not in request["inferenceConfig"]
    assert response.output.checklist_items[0].checklist_id == 0
    assert response.usage == {
        "prompt_tokens": 110,
        "completion_tokens": 20,
        "total_tokens": 130,
        "cached_tokens": 7,
        "cache_write_tokens": 3,
    }


@pytest.mark.parametrize("transport", ["anthropic", "bedrock-runtime", 1, None])
def test_judge_config_rejects_unknown_transport(
    tmp_path: Path, transport: object
) -> None:
    with pytest.raises(JudgeConfigurationError, match="transport"):
        _config(tmp_path, transport=transport)


def test_claude_family_is_distinct_from_gpt_generator(tmp_path: Path) -> None:
    config = _config(tmp_path)

    identity = config.resolve_model_identity("us.anthropic.claude-opus-5")

    assert identity.mapped_family == "claude"
    assert identity.judge_family == "claude_frontier"
    assert config.validate_family_audit(identity, "gpt") == "enforced"
