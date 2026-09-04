from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from agentic_cogwriter.judges.client import ChatResponse, normalize_usage
from agentic_cogwriter.judges.config import JudgeConfig
from agentic_cogwriter.judges.errors import (
    JudgeConfigurationError,
    JudgeTransportError,
    JudgeValidationError,
)
from agentic_cogwriter.judges.scorer import blind_condition_id, score_run
from agentic_cogwriter.judges.templates import JudgeTemplate
from agentic_cogwriter.judges.validation import (
    POINTWISE_DIMENSIONS,
    validate_pairwise,
    validate_pointwise,
)


class FakeTransport:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = responses
        self.requests: list[dict[str, object]] = []

    def complete(
        self,
        *,
        base_url: str,
        api_key: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> ChatResponse:
        assert base_url == "https://judge.invalid/v1"
        assert api_key
        assert timeout_seconds == 10.0
        self.requests.append(payload)
        response = self.responses.pop(0)
        return ChatResponse(
            content=str(response["content"]),
            usage={
                "prompt_tokens": 11,
                "completion_tokens": 7,
                "total_tokens": 18,
            },
            raw={**response, "model": response.get("model", "open-model")},
        )


def _template(path: Path, task: str) -> None:
    if task == "pointwise":
        path.write_text(
            "Judge {prompt_id} {condition_id} {platform} {judge_id} "
            "{judge_family}: {assignment}\n{context}\n{output}\n",
            encoding="utf-8",
        )
    else:
        path.write_text(
            "Compare {prompt_id} {pair_id} {presentation} {platform} "
            "{judge_id} {judge_family} {assignment}\n"
            "{context}\nA={answer_a}\nB={answer_b}\n",
            encoding="utf-8",
        )


def _config(
    tmp_path: Path,
    template: Path,
    task: str = "pointwise",
    *,
    model: str = "open-model",
    model_family_map: dict[str, object] | None = None,
) -> JudgeConfig:
    values: dict[str, object] = {
        "task": task,
        "model": model,
        "judge_id": "judge-1",
        "model_family_map": model_family_map
        or {
            "claude-frontier": {"family": "claude", "role": "frontier"},
            "gpt-frontier": {"family": "gpt", "role": "frontier"},
            "open-model": {"family": "prometheus", "role": "open_evaluator"},
        },
        "base_url_env": "FAKE_JUDGE_URL",
        "credential_env": "FAKE_JUDGE_TOKEN",
        "template_path": str(template),
        "seed": 19,
        "presentation_seed": 23,
        "temperature": 0,
        "top_p_or_equivalent": 1,
        "maximum_output_tokens": 120,
        "stop_rules": [],
        "timeout": 10,
        "retry_policy": {"max_retries": 1},
    }
    return JudgeConfig.from_mapping(
        values,
        source_path=tmp_path / "judge.json",
    )


def _pointwise_record(judge_family: str = "open_evaluator") -> dict[str, object]:
    return {
        "prompt_id": "p-1",
        "condition_id": "blind-condition",
        "platform": "codex",
        "judge_id": "judge-1",
        "judge_family": judge_family,
        "scores": dict.fromkeys(POINTWISE_DIMENSIONS, 4),
        "evidence_quotes": [
            {"dimension": dimension, "quote": "evidence"}
            for dimension in POINTWISE_DIMENSIONS
        ],
        "judge_level_composite": 0.0,
        "uncertainties": [],
    }


def _pairwise_record() -> dict[str, object]:
    return {
        "prompt_id": "p-1",
        "platform": "codex",
        "judge_id": "judge-1",
        "judge_family": "open_evaluator",
        "pair_id": "pair-1",
        "presentation": "A|B",
        "winner": "tie",
        "evidence_quotes": {"A": ["alpha"], "B": ["beta"]},
        "reason": "Both answers address the assignment equally well.",
    }


def _generator_family_audit() -> dict[str, object]:
    return {
        "generator_model_id": "generator-model",
        "generator_model_family": "gpt",
    }


def test_pointwise_validation_rejects_unknown_or_out_of_range_scores() -> None:
    record = _pointwise_record()
    record["scores"]["instruction_fulfillment"] = 6  # type: ignore[index]

    with pytest.raises(JudgeValidationError, match="score"):
        validate_pointwise(
            record,
            expected={
                "prompt_id": "p-1",
                "condition_id": "blind-condition",
                "platform": "codex",
                "judge_id": "judge-1",
                "judge_family": "open_evaluator",
            },
            searchable_texts=("evidence",),
        )


@pytest.mark.parametrize("field", ["reasoning_tokens", "cached_tokens"])
@pytest.mark.parametrize("value", [-1, True, "1", None])
def test_usage_rejects_invalid_optional_counter(field: str, value: object) -> None:
    usage: dict[str, object] = {
        "prompt_tokens": 1,
        "completion_tokens": 2,
        "total_tokens": 3,
        field: value,
    }

    with pytest.raises(JudgeTransportError, match=field):
        normalize_usage(usage)


def test_pairwise_validation_requires_verbatim_evidence_for_both_outputs() -> None:
    record = _pairwise_record()

    with pytest.raises(JudgeValidationError, match="output B"):
        validate_pairwise(
            record,
            expected={
                "prompt_id": "p-1",
                "platform": "codex",
                "judge_id": "judge-1",
                "judge_family": "open_evaluator",
                "pair_id": "pair-1",
                "presentation": "A|B",
            },
            output_a="alpha text",
            output_b="different text",
            context="",
        )


def test_judge_config_rejects_nonzero_temperature(tmp_path: Path) -> None:
    template = tmp_path / "judge.txt"
    _template(template, "pointwise")

    with pytest.raises(JudgeConfigurationError, match="temperature"):
        JudgeConfig.from_mapping(
            {
                "model": "judge-model",
                "model_family_map": {
                    "open-model": {
                        "family": "prometheus",
                        "role": "open_evaluator",
                    }
                },
                "base_url_env": "FAKE_JUDGE_URL",
                "credential_env": "FAKE_JUDGE_TOKEN",
                "template_path": str(template),
                "seed": 19,
                "temperature": 0.1,
            }
        )


def test_family_audit_rejects_frontier_generator_overlap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template = tmp_path / "judge.txt"
    _template(template, "pointwise")
    config = _config(tmp_path, template, model="gpt-frontier")
    run_dir = _run_dir(tmp_path, "A1", "evidence")
    monkeypatch.setenv("FAKE_JUDGE_URL", "https://judge.invalid/v1")
    monkeypatch.setenv("FAKE_JUDGE_TOKEN", "placeholder-only")
    response = _pointwise_record("gpt_frontier")
    response["condition_id"] = blind_condition_id("A1")
    response["evidence_quotes"] = [
        {"dimension": dimension, "quote": "evidence"}
        for dimension in POINTWISE_DIMENSIONS
    ]

    with pytest.raises(JudgeConfigurationError, match="overlap"):
        score_run(
            run_dir,
            config,
            transport=FakeTransport(
                [{"content": json.dumps(response), "model": "gpt-frontier"}]
            ),
        )

    assert not (run_dir / "scores.jsonl").exists()


def test_family_audit_allows_incomplete_non_overlapping_map(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template = tmp_path / "judge.txt"
    _template(template, "pointwise")
    config = _config(
        tmp_path,
        template,
        model_family_map={
            "open-model": {"family": "prometheus", "role": "open_evaluator"},
        },
    )
    run_dir = _run_dir(tmp_path, "A1", "evidence")
    monkeypatch.setenv("FAKE_JUDGE_URL", "https://judge.invalid/v1")
    monkeypatch.setenv("FAKE_JUDGE_TOKEN", "placeholder-only")
    response = _pointwise_record()
    response["condition_id"] = blind_condition_id("A1")
    response["evidence_quotes"] = [
        {"dimension": dimension, "quote": "evidence"}
        for dimension in POINTWISE_DIMENSIONS
    ]

    result = score_run(
        run_dir,
        config,
        transport=FakeTransport(
            [{"content": json.dumps(response), "model": "open-model"}]
        ),
    )

    assert result.scores_path.is_file()


def test_family_audit_rejects_unmappable_reported_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template = tmp_path / "judge.txt"
    _template(template, "pointwise")
    config = _config(tmp_path, template)
    run_dir = _run_dir(tmp_path, "A1", "evidence")
    monkeypatch.setenv("FAKE_JUDGE_URL", "https://judge.invalid/v1")
    monkeypatch.setenv("FAKE_JUDGE_TOKEN", "placeholder-only")
    response = _pointwise_record()
    response["condition_id"] = blind_condition_id("A1")
    response["evidence_quotes"] = [
        {"dimension": dimension, "quote": "evidence"}
        for dimension in POINTWISE_DIMENSIONS
    ]

    with pytest.raises(JudgeConfigurationError, match="reported model"):
        score_run(
            run_dir,
            config,
            transport=FakeTransport(
                [{"content": json.dumps(response), "model": "unknown-model"}]
            ),
        )


def test_committed_judge_templates_render_without_unresolved_fields() -> None:
    root = Path(__file__).parents[1]
    pointwise = JudgeTemplate.load(root / "prompts/judges/pointwise-v1.txt")
    pairwise = JudgeTemplate.load(root / "prompts/judges/pairwise-v1.txt")

    rendered_pointwise = pointwise.render(
        {
            "prompt_id": "p-1",
            "condition_id": "blind-condition",
            "platform": "codex",
            "judge_id": "judge-1",
            "judge_family": "open_evaluator",
            "assignment": "Write a memo.",
            "context": "Provided fact.",
            "output": "Provided fact.",
        }
    )
    rendered_pairwise = pairwise.render(
        {
            "prompt_id": "p-1",
            "pair_id": "pair-1",
            "presentation": "A|B",
            "platform": "codex",
            "judge_id": "judge-1",
            "judge_family": "open_evaluator",
            "assignment": "Write a memo.",
            "context": "Provided fact.",
            "answer_a": "alpha",
            "answer_b": "beta",
        }
    )

    assert "{prompt_id}" not in rendered_pointwise
    assert "{answer_a}" not in rendered_pairwise
    assert (
        b"fd283293406d024f44c174b094ef48031d0687a4682fd3a56b29b138f80281b6"
        in pointwise.raw
    )


def test_fake_transport_receives_deterministic_zero_temperature_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template = tmp_path / "judge.txt"
    _template(template, "pointwise")
    config = _config(tmp_path, template)
    monkeypatch.setenv("FAKE_JUDGE_URL", "https://judge.invalid/v1")
    monkeypatch.setenv("FAKE_JUDGE_TOKEN", "placeholder-only")
    transport = FakeTransport([{"content": json.dumps(_pointwise_record())}])

    from agentic_cogwriter.judges.engine import judge_pointwise

    result = judge_pointwise(
        config,
        assignment="Write a memo.",
        context="evidence",
        output="evidence",
        prompt_id="p-1",
        blind_condition_id="blind-condition",
        platform="codex",
        transport=transport,
    )

    assert result.record["prompt_id"] == "p-1"
    assert result.usage["total_tokens"] == 18
    payload = transport.requests[0]
    assert payload["temperature"] == 0
    assert payload["seed"] == 19
    assert payload["top_p"] == 1
    assert payload["max_tokens"] == 120
    assert payload["response_format"] == {"type": "json_object"}


def test_invalid_json_retries_with_identical_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template = tmp_path / "judge.txt"
    _template(template, "pointwise")
    config = _config(tmp_path, template)
    monkeypatch.setenv("FAKE_JUDGE_URL", "https://judge.invalid/v1")
    monkeypatch.setenv("FAKE_JUDGE_TOKEN", "placeholder-only")
    transport = FakeTransport(
        [
            {"content": "not json"},
            {"content": json.dumps(_pointwise_record())},
        ]
    )

    from agentic_cogwriter.judges.engine import judge_pointwise

    result = judge_pointwise(
        config,
        assignment="Write a memo.",
        context="evidence",
        output="evidence",
        prompt_id="p-1",
        blind_condition_id="blind-condition",
        platform="codex",
        transport=transport,
    )

    assert result.attempts == 2
    assert len(transport.requests) == 2
    assert transport.requests[0] == transport.requests[1]


def test_pairwise_score_run_uses_the_caller_selected_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template = tmp_path / "judge.txt"
    _template(template, "pairwise")
    config = _config(tmp_path, template, task="pairwise")
    run_a = _run_dir(tmp_path, "A1", "alpha")
    run_b = _run_dir(tmp_path, "A2", "beta")
    monkeypatch.setenv("FAKE_JUDGE_URL", "https://judge.invalid/v1")
    monkeypatch.setenv("FAKE_JUDGE_TOKEN", "placeholder-only")
    labels = sorted((blind_condition_id("A1"), blind_condition_id("A2")))
    pair_id = "pair-" + hashlib.sha256("|".join(labels).encode()).hexdigest()[:16]
    response_a = _pairwise_record()
    response_a.update({"pair_id": pair_id, "presentation": "A|B"})
    response_a["evidence_quotes"] = {"A": ["alpha"], "B": ["beta"]}
    response_b = _pairwise_record()
    response_b.update({"pair_id": pair_id, "presentation": "B|A"})
    response_b["evidence_quotes"] = {"A": ["beta"], "B": ["alpha"]}
    transport = FakeTransport(
        [
            {"content": json.dumps(response_a)},
            {"content": json.dumps(response_b)},
        ]
    )

    result = score_run(
        run_a,
        config,
        compare_run_dir=run_b,
        output_path=tmp_path / "pairwise.jsonl",
        transport=transport,
    )

    assert len(transport.requests) == 2
    records = [
        json.loads(line)
        for line in result.scores_path.read_text(encoding="utf-8").splitlines()
    ]
    assert {record["presentation"] for record in records} == {"A|B", "B|A"}
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["tournament"]["presentation_seed"] == 23
    assert manifest["tournament"]["orders"] == [
        record["presentation"] for record in records
    ]
    assert manifest["tournament"]["order_mapping"] == [
        {
            "presentation": order,
            "first_output": "first_run" if order == "A|B" else "compare_run",
            "second_output": "compare_run" if order == "A|B" else "first_run",
        }
        for order in manifest["tournament"]["orders"]
    ]
    assert len(manifest["records"]) == 2


def test_pairwise_score_run_writes_no_output_until_both_presentations_validate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template = tmp_path / "judge.txt"
    _template(template, "pairwise")
    config = _config(tmp_path, template, task="pairwise")
    run_a = _run_dir(tmp_path, "A1", "alpha")
    run_b = _run_dir(tmp_path, "A2", "beta")
    monkeypatch.setenv("FAKE_JUDGE_URL", "https://judge.invalid/v1")
    monkeypatch.setenv("FAKE_JUDGE_TOKEN", "placeholder-only")
    labels = sorted((blind_condition_id("A1"), blind_condition_id("A2")))
    pair_id = "pair-" + hashlib.sha256("|".join(labels).encode()).hexdigest()[:16]
    response = _pairwise_record()
    response.update({"pair_id": pair_id, "presentation": "A|B"})
    response["evidence_quotes"] = {"A": ["alpha"], "B": ["beta"]}
    output_path = tmp_path / "pairwise.jsonl"

    with pytest.raises(JudgeValidationError, match="not valid JSON"):
        score_run(
            run_a,
            config,
            compare_run_dir=run_b,
            output_path=output_path,
            transport=FakeTransport(
                [
                    {"content": json.dumps(response)},
                    {"content": "not json"},
                    {"content": "not json"},
                ]
            ),
        )

    assert not output_path.exists()
    assert not output_path.with_name("pairwise-manifest.json").exists()


def _run_dir(tmp_path: Path, condition_id: str, output: str) -> Path:
    run_dir = tmp_path / condition_id
    run_dir.mkdir()
    (run_dir / "output.normalized.txt").write_text(output, encoding="utf-8")
    (run_dir / "prompt.txt").write_text(
        "Assignment:\nWrite a memo.\n\n"
        "Supplied context:\nProvided fact.\n\n"
        "Requested output constraints:\n{}\n",
        encoding="utf-8",
    )
    (run_dir / "run-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "completed",
                "run_id": condition_id,
                "inputs": {
                    "prompt_id": "p-1",
                    "condition_id": condition_id,
                    "platform": "codex-primary",
                },
                "models_and_execution": _generator_family_audit(),
                "scoring": {"status": "eligible"},
            }
        ),
        encoding="utf-8",
    )
    return run_dir


def test_score_run_writes_protocol_jsonl_and_hashed_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template = tmp_path / "judge.txt"
    _template(template, "pointwise")
    config = _config(tmp_path, template)
    run_dir = _run_dir(tmp_path, "A1", "Provided fact.")
    monkeypatch.setenv("FAKE_JUDGE_URL", "https://judge.invalid/v1")
    monkeypatch.setenv("FAKE_JUDGE_TOKEN", "placeholder-only")
    transport = FakeTransport(
        [
            {
                "content": json.dumps(
                    {
                        **_pointwise_record(),
                        "prompt_id": "p-1",
                        "condition_id": blind_condition_id("A1"),
                        "judge_family": "runtime-verified",
                        "evidence_quotes": [
                            {"dimension": dimension, "quote": "Provided fact."}
                            for dimension in POINTWISE_DIMENSIONS
                        ],
                    }
                )
            }
        ]
    )

    result = score_run(run_dir, config, transport=transport)

    assert result.scores_path == run_dir / "scores.jsonl"
    record = json.loads(result.scores_path.read_text(encoding="utf-8"))
    assert set(record) == {
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
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert record["judge_family"] == "open_evaluator"
    assert manifest["records"][0]["record_sha256"].startswith("sha256:")
    assert manifest["records"][0]["usage"]["total_tokens"] == 18
    assert manifest["family_audit"] == {
        "reported_model_id": "open-model",
        "mapped_family": "prometheus",
        "judge_family": "open_evaluator",
        "generator_model_id": "generator-model",
        "generator_family": "gpt",
    }
