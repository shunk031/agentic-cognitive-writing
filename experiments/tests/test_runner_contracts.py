from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentic_cogwriter.runner.adapters import PlatformAdapter
from agentic_cogwriter.runner.config import RuntimeConfig
from agentic_cogwriter.runner.errors import ExecutionError, RetrievalViolation
from agentic_cogwriter.runner.execution import (
    ExecutionResult,
    _retrieval_marker,
    reject_retrieval,
)
from agentic_cogwriter.runner.manifest import PromptRecord
from agentic_cogwriter.runner.runner import ExperimentRunner
from agentic_cogwriter.runner.trace import TraceValidationError, validate_trace


def _runtime_values() -> dict[str, object]:
    return {
        "codex_generator_model": "gpt-test",
        "claude_code_generator_model": "claude-test",
        "codex_frontier_judge": "claude-judge",
        "claude_code_frontier_judge": "gpt-judge",
        "shared_open_evaluator": "mistral-judge",
        "generator_system_and_condition_prompts": "frozen",
        "judge_prompts_and_json_schemas": "frozen",
        "temperature": 0,
        "top_p_or_equivalent": 1,
        "maximum_output_tokens": 100,
        "stop_rules": [],
        "timeout": 60,
        "generation_seed": 1,
        "judge_seed": 2,
        "sampling_seed": 3,
        "presentation_seed": 4,
        "codex_version": "test",
        "claude_code_version": "test",
        "main_plugin_commit": "test",
        "experiments_plugin_commit": "test",
        "runner_commit": "test",
        "generator_and_judge_family_audit": "test",
        "retry_policy": 0,
        "length_strata": "test",
        "minimum_cell_size": 1,
        "covariate_model": "test",
        "length_unit": "words",
        "zero_variance_rule": "test",
        "statistical_lock": "test",
        "output_counting": {
            "unit": "words",
            "tokenizer": None,
            "word_rule": "unicode-whitespace",
        },
    }


def _config(**updates: object) -> RuntimeConfig:
    values = _runtime_values()
    values.update(updates)
    return RuntimeConfig.from_dict(values)


def _prompt() -> PromptRecord:
    return PromptRecord(
        prompt_id="writingbench-0001",
        benchmark_name="WritingBench",
        source_version="test",
        prompt_text="Write a memo.",
        supplied_context="Provided facts only.",
        requested_output_constraints={},
        row_hash="row-hash",
    )


def _event(
    event_type: str = "process_switch", *, stage_id: str | None = None
) -> dict[str, object]:
    event: dict[str, object] = {
        "event_type": event_type,
        "timestamp": "2026-01-01T00:00:00+00:00",
        "responsible_agent": "writer",
        "process": "writing",
        "decision": "continue",
        "evidence": ["supplied context"],
        "open_uncertainty": [],
    }
    if event_type == "process_switch":
        event.update({"from_process": "Planning", "to_process": "Translating"})
    if event_type in {"goal_created", "goal_developed", "goal_regenerated"}:
        event.update({"goal_id": "g1", "parent_goal_id": None})
    if stage_id is not None:
        event["stage_id"] = stage_id
    return event


def test_adapter_commands_expand_runtime_controls_and_deny_network() -> None:
    adapter_root = Path("experiments/conditions/adapters")
    values = {
        "model_id": "model-test",
        "maximum_output_tokens": 17,
        "temperature": 0,
        "top_p_or_equivalent": 1,
        "generation_seed": 23,
        "stop_rules": [],
    }

    codex = PlatformAdapter.load(adapter_root / "codex_exec.toml")
    codex_command = codex.build_command(
        model_id="model-test", prompt="prompt", runtime_values=values
    )
    assert "sandbox_workspace_write.network_access=false" in codex_command
    assert 'web_search="disabled"' in codex_command
    assert all("{" not in part and "}" not in part for part in codex_command)
    assert codex.control_status_dict["maximum_output_tokens"] == "monitored-only"

    claude = PlatformAdapter.load(adapter_root / "claude_print.toml")
    claude_command = claude.build_command(
        model_id="model-test", prompt="prompt", runtime_values=values
    )
    settings = json.loads(claude_command[claude_command.index("--settings") + 1])
    assert settings["env"]["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] == "17"
    assert settings["sandbox"]["network"]["allowedDomains"] == []
    assert settings["sandbox"]["network"]["strictAllowlist"] is True
    assert settings["sandbox"]["failIfUnavailable"] is True
    assert settings["sandbox"]["allowUnsandboxedCommands"] is False
    assert claude.control_status_dict["maximum_output_tokens"] == "enforced"


def test_codex_adapter_argv_passes_installed_cli_parser() -> None:
    adapter = PlatformAdapter.load(
        Path("experiments/conditions/adapters/codex_exec.toml")
    )
    executable = shutil.which(adapter.executable)
    if executable is None:
        pytest.skip("codex CLI is not installed")

    for session_id in (None, "session-1"):
        command = adapter.build_command(
            model_id="model-test",
            prompt="prompt",
            session_id=session_id,
            plugin_dirs=("/tmp/plugin",),
            runtime_values={
                "maximum_output_tokens": 17,
                "temperature": 0,
                "top_p_or_equivalent": 1,
                "generation_seed": 23,
                "stop_rules": [],
            },
        )
        assert "--ask-for-approval" not in command
        assert "--skip-git-repo-check" in command
        if session_id is None:
            assert "--sandbox" in command
        else:
            assert "--sandbox" not in command
        assert "--plugin-dir" not in command
        assert 'approval_policy="never"' in command
        parser_probe = subprocess.run(
            [executable, *command[1:-1], "--help"],
            capture_output=True,
            check=False,
            text=True,
        )
        assert parser_probe.returncode == 0, parser_probe.stderr


@pytest.mark.parametrize(
    "payload",
    [
        b"https://example.test/source",
        b"curl https://example.test",
        b"wget file",
        b"web_search",
    ],
)
def test_raw_retrieval_tripwire_rejects_urls_and_network_commands(
    payload: bytes,
) -> None:
    with pytest.raises(RetrievalViolation, match="retrieval marker"):
        reject_retrieval(payload, b"")


def test_retrieval_tripwire_recognizes_generic_event_key() -> None:
    assert _retrieval_marker({"event": "web_search"}) == "web_search"
    with pytest.raises(RetrievalViolation, match="retrieval marker"):
        reject_retrieval(b'{"event":"web_search"}', b"")


def test_trace_validation_requires_contract_fields(tmp_path: Path) -> None:
    path = tmp_path / "process.jsonl"
    path.write_text(json.dumps({"event_type": "process_switch"}) + "\n")

    with pytest.raises(TraceValidationError, match="evidence"):
        validate_trace(path, condition_id="A4")


def test_trace_validation_enforces_stage_counts_and_goal_rules(tmp_path: Path) -> None:
    a2_path = tmp_path / "a2.jsonl"
    a2_path.write_text(
        "".join(
            json.dumps(_event("stage_event", stage_id=stage)) + "\n"
            for stage in ("pre_write", "write", "re_write")
        )
    )
    validate_trace(
        a2_path,
        condition_id="A2",
        expected_stage_ids=("pre_write", "write", "re_write"),
    )

    a4_path = tmp_path / "a4.jsonl"
    a4_path.write_text(json.dumps(_event("process_switch")) + "\n")
    with pytest.raises(TraceValidationError, match="A4 requires goal fields"):
        validate_trace(a4_path, condition_id="A4")

    valid_a4_events = _event("process_switch")
    valid_a4_path = tmp_path / "a4-valid.jsonl"
    valid_a4_path.write_text(
        json.dumps(valid_a4_events) + "\n" + json.dumps(_event("goal_created")) + "\n"
    )
    validate_trace(valid_a4_path, condition_id="A4")

    invalid_goal_path = tmp_path / "a4-invalid-goal.jsonl"
    invalid_goal = _event("goal_created")
    invalid_goal.pop("parent_goal_id")
    invalid_goal_path.write_text(
        json.dumps(_event("process_switch")) + "\n" + json.dumps(invalid_goal) + "\n"
    )
    with pytest.raises(
        TraceValidationError, match="goal-aware event needs parent_goal_id"
    ):
        validate_trace(invalid_goal_path, condition_id="A4")

    a5_path = tmp_path / "a5.jsonl"
    a5_path.write_text(json.dumps(_event("goal_created")) + "\n")
    with pytest.raises(TraceValidationError, match="A5"):
        validate_trace(a5_path, condition_id="A5")


def test_run_fails_on_schema_invalid_plugin_trace(tmp_path: Path) -> None:
    class InvalidTraceExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds):
            result = super().run(command, cwd=cwd, timeout_seconds=timeout_seconds)
            trace_path = cwd / ".writing" / "trace" / "process.jsonl"
            event = json.loads(trace_path.read_text())
            del event["evidence"]
            trace_path.write_text(json.dumps(event) + "\n")
            return result

    runner = ExperimentRunner(
        _config(), output_root=tmp_path, executor=InvalidTraceExecutor([_result()])
    )

    with pytest.raises(TraceValidationError, match="evidence"):
        runner.run_prompt(_prompt(), condition_id="A1", platform="codex-primary")


class _RetryExecutor:
    def __init__(self, results: list[ExecutionResult]) -> None:
        self.results = results
        self.calls: list[list[str]] = []

    def run(self, command, *, cwd, timeout_seconds):
        self.calls.append(command)
        trace_path = cwd / ".writing" / "trace" / "process.jsonl"
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace_path.write_text(
            json.dumps(_event("stage_event", stage_id="single_shot")) + "\n"
        )
        return self.results.pop(0)


def _result(
    *, output: str = "final", returncode: int = 0, timed_out: bool = False
) -> ExecutionResult:
    payload = {
        "type": "item.completed",
        "item": {"type": "agent_message", "text": output},
        "thread_id": "session-1",
    }
    return ExecutionResult(
        returncode=returncode,
        stdout=(json.dumps(payload) + "\n").encode(),
        stderr=b"failed" if returncode else b"",
        session_id="session-1",
        timed_out=timed_out,
    )


@pytest.mark.parametrize(
    "first",
    [_result(timed_out=True), _result(returncode=1)],
)
def test_retry_reuses_the_returned_session_id(
    tmp_path: Path, first: ExecutionResult
) -> None:
    executor = _RetryExecutor([first, _result()])
    runner = ExperimentRunner(
        _config(retry_policy=1), output_root=tmp_path, executor=executor
    )

    runner.run_prompt(_prompt(), condition_id="A1", platform="codex-primary")

    assert len(executor.calls) == 2
    assert executor.calls[1][0:3] == ["codex", "exec", "resume"]
    assert "session-1" in executor.calls[1]


def test_retry_exhaustion_fails_after_fixed_attempt_count(tmp_path: Path) -> None:
    executor = _RetryExecutor([_result(returncode=1), _result(returncode=1)])
    runner = ExperimentRunner(
        _config(retry_policy=1), output_root=tmp_path, executor=executor
    )

    with pytest.raises(ExecutionError, match="status 1"):
        runner.run_prompt(_prompt(), condition_id="A1", platform="codex-primary")
    assert len(executor.calls) == 2


def test_failed_turn_without_session_preserves_cli_stderr(tmp_path: Path) -> None:
    executor = _RetryExecutor(
        [
            ExecutionResult(
                returncode=1,
                stdout=b"",
                stderr=b"workspace is not trusted",
                session_id=None,
            )
        ]
    )
    runner = ExperimentRunner(
        _config(retry_policy=1), output_root=tmp_path, executor=executor
    )

    with pytest.raises(
        ExecutionError,
        match=r"return code 1\): workspace is not trusted",
    ):
        runner.run_prompt(_prompt(), condition_id="A1", platform="codex-primary")


def test_a5_rejects_a_new_goals_file(tmp_path: Path) -> None:
    class GoalWritingExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds):
            result = super().run(command, cwd=cwd, timeout_seconds=timeout_seconds)
            goals = cwd / ".writing" / "goals.md"
            goals.write_text("should not exist")
            return result

    runner = ExperimentRunner(
        _config(), output_root=tmp_path, executor=GoalWritingExecutor([_result()])
    )

    with pytest.raises(ExecutionError, match="goals.md"):
        runner.run_prompt(_prompt(), condition_id="A5", platform="codex-primary")


def test_runner_rejects_retrieval_in_draft_fallback(tmp_path: Path) -> None:
    class DraftRetrievalExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds):
            result = super().run(command, cwd=cwd, timeout_seconds=timeout_seconds)
            draft = cwd / ".writing" / "draft.md"
            draft.write_text("Evidence gathered with curl https://example.test/source")
            return result

    runner = ExperimentRunner(
        _config(),
        output_root=tmp_path,
        executor=DraftRetrievalExecutor([_result(output="")]),
    )

    with pytest.raises(RetrievalViolation, match="retrieval marker"):
        runner.run_prompt(_prompt(), condition_id="A1", platform="codex-primary")


def test_frozen_stage_contents_and_provenance_are_recorded(tmp_path: Path) -> None:
    executor = _RetryExecutor([_result()])
    runner = ExperimentRunner(_config(), output_root=tmp_path, executor=executor)

    result = runner.run_prompt(_prompt(), condition_id="A1", platform="codex-primary")

    command_prompt = executor.calls[0][-1]
    assert "Use only the assignment and supplied context" in command_prompt
    manifest = json.loads(result.manifest_path.read_text())
    benchmark = manifest["inputs"]["benchmark_provenance"]
    assert benchmark["source_sha256"] == (
        "026e3f9482ff3474c802cd43f5cae9fd584e10d0848d3e0a152695434becbc98"
    )
    assert manifest["inputs"]["stage_prompt_hashes"]["single_shot"] == (
        "99964b369a76d8cb88ec375cda4e553a5b993483ca05b14e46c3c3fb3d3014cf"
    )
    assert manifest["models_and_execution"]["judge_verification"] == {
        "declared_audit": "test",
        "family_overlap_audit": "declared-unverified pending judge module",
        "judge_families": "declared-unverified pending judge module",
    }


def test_public_config_constructor_does_not_accept_non_strict_mode() -> None:
    with pytest.raises(TypeError):
        RuntimeConfig.from_dict({}, strict=False)  # type: ignore[call-arg]
