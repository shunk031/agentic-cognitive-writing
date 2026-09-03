from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from agentic_cogwriter.runner.adapters import PlatformAdapter
from agentic_cogwriter.runner.cli import build_parser
from agentic_cogwriter.runner.conditions import PLATFORMS, load_condition_registry
from agentic_cogwriter.runner.config import RuntimeConfig
from agentic_cogwriter.runner.errors import (
    BudgetExceeded,
    ExecutionError,
    RetrievalViolation,
)
from agentic_cogwriter.runner.execution import (
    ExecutionResult,
    _retrieval_marker,
    extract_subagent_spawn_count,
    extract_token_usage,
    reject_retrieval,
)
from agentic_cogwriter.runner.manifest import PromptRecord
from agentic_cogwriter.runner.runner import ExperimentRunner, SessionSnapshot
from agentic_cogwriter.runner.trace import TraceValidationError, validate_trace

WRITING_TRACE_PROCESSES = (
    "planning",
    "generate",
    "organize",
    "goal-setting",
    "translating",
    "reviewing",
    "evaluate",
    "revise",
)


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


def _plugin_source(tmp_path: Path) -> Path:
    root = tmp_path / "plugin-source"
    skills = (
        "writing-single-shot",
        "writing-linear",
        "writing-storm-style",
        "agentic-cog-writer",
        "cognitive-writing-no-goal-network",
        "cognitive-writing-fixed-order",
        "writing-cogwriter-style",
        "writing-adaptive-task-planning",
        "planning",
        "translating",
        "reviewing",
    )
    for skill in skills:
        path = root / "skills" / skill / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(skill)
    return root


def test_platform_identifiers_use_public_codex_and_claude_code_values() -> None:
    assert PLATFORMS == ("codex", "claude-code")
    parser = build_parser()
    common = (
        "--manifest",
        "manifest.jsonl",
        "--prompt-id",
        "writingbench-0001",
        "--condition",
        "A1",
    )
    assert parser.parse_args((*common, "--platform", "codex")).platform == "codex"
    assert (
        parser.parse_args((*common, "--platform", "claude-code")).platform
        == "claude-code"
    )
    with pytest.raises(SystemExit):
        parser.parse_args((*common, "--platform", "unsupported-codex"))
    with pytest.raises(SystemExit):
        parser.parse_args((*common, "--platform", "unsupported-claude"))


def _runner(tmp_path: Path, config: RuntimeConfig | None = None, **kwargs):
    kwargs.setdefault("codex_home", tmp_path / "codex-home")
    return ExperimentRunner(
        config or _config(),
        output_root=tmp_path,
        codex_plugin_root=_plugin_source(tmp_path),
        **kwargs,
    )


def _event(
    event_type: str = "process_switch",
    *,
    process: str = "planning",
    stage_id: str | None = None,
    from_process: str | None = None,
    to_process: str | None = None,
) -> dict[str, object]:
    event: dict[str, object] = {
        "event_type": event_type,
        "timestamp": "2026-01-01T00:00:00+00:00",
        "responsible_agent": "writer",
        "process": process,
        "decision": "continue",
        "evidence": ["supplied context"],
        "open_uncertainty": [],
    }
    if event_type == "process_switch":
        event.update(
            {
                "from_process": from_process,
                "to_process": to_process or process,
            }
        )
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
    assert codex.platform == "codex"
    codex_command = codex.build_command(
        model_id="model-test", prompt="prompt", runtime_values=values
    )
    assert "sandbox_workspace_write.network_access=false" in codex_command
    assert 'web_search="disabled"' in codex_command
    assert all("{" not in part and "}" not in part for part in codex_command)
    assert codex.control_status_dict["maximum_output_tokens"] == "monitored-only"

    claude = PlatformAdapter.load(adapter_root / "claude_print.toml")
    assert claude.platform == "claude-code"
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


def test_codex_prompt_references_workspace_skill_file_without_plugin_install(
    tmp_path: Path,
) -> None:
    runner = ExperimentRunner(
        _config(), output_root=tmp_path, codex_plugin_root=Path("/plugin")
    )

    prompt = runner._plugin_prompt(load_condition_registry()["A4"], _prompt(), "codex")

    assert "Read the skill file at plugin/skills/agentic-cog-writer/SKILL.md" in prompt
    assert "follow it" in prompt
    assert "$agentic-cog-writer" not in prompt
    assert "codex plugin add" not in prompt
    assert "complete final text itself" in prompt


def test_every_codex_wrapper_uses_file_reference_and_no_install_metadata() -> None:
    runner = ExperimentRunner(_config(), output_root=Path("runs"))
    for condition in load_condition_registry().values():
        wrapper = tomllib.loads(condition.plugin_config.read_text(encoding="utf-8"))
        invocation = wrapper["invocation"]["codex"]

        assert "{codex_plugin_root}" in invocation
        assert "SKILL.md" in invocation
        assert "codex" not in wrapper["install"]
        assert "complete final text itself" in invocation
        prompt = runner._plugin_prompt(condition, _prompt(), "codex")
        assert f"plugin/skills/{condition.skill_name}/SKILL.md" in prompt
        assert "complete final text itself" in prompt


def test_codex_stages_skill_references_roles_and_hashes(tmp_path: Path) -> None:
    source_root = tmp_path / "plugin-source"
    files = {
        "skills/agentic-cog-writer/SKILL.md": "main skill\n",
        "skills/agentic-cog-writer/references/trace.md": "trace reference\n",
        "skills/planning/SKILL.md": "planning role\n",
        "skills/translating/SKILL.md": "translating role\n",
        "skills/reviewing/SKILL.md": "reviewing role\n",
    }
    for relative, content in files.items():
        path = source_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    class StageExecutor:
        def run(self, command, *, cwd, timeout_seconds):
            trace_path = cwd / ".writing" / "trace" / "process.jsonl"
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            trace_path.write_text(
                json.dumps(_event("process_switch"))
                + "\n"
                + json.dumps(_event("goal_created"))
                + "\n"
            )
            (cwd / ".writing" / "draft.md").write_text("final output " * 10)
            return _result()

    runner = ExperimentRunner(
        _config(),
        output_root=tmp_path / "runs",
        executor=StageExecutor(),
        codex_plugin_root=source_root,
        codex_home=tmp_path / "codex-home",
    )

    result = runner.run_prompt(
        _prompt(), condition_id="A4", platform="codex", run_id="staged"
    )

    manifest = json.loads(result.manifest_path.read_text())
    staged_files = manifest["staged_files"]
    assert set(staged_files) == {
        "plugin/skills/agentic-cog-writer/SKILL.md",
        "plugin/skills/agentic-cog-writer/references/trace.md",
        "plugin/skills/planning/SKILL.md",
        "plugin/skills/translating/SKILL.md",
        "plugin/skills/reviewing/SKILL.md",
    }
    for relative, content in files.items():
        staged = result.run_dir / "workspace" / "plugin" / relative
        assert staged.read_text() == content
        assert staged_files[f"plugin/{relative}"] == (
            "sha256:" + hashlib.sha256(content.encode()).hexdigest()
        )

    prompt_text = (result.run_dir / "prompt.txt").read_text()
    assert (
        "Read the skill file at plugin/skills/agentic-cog-writer/SKILL.md"
        in prompt_text
    )
    assert str(source_root) not in prompt_text
    assert manifest["execution_paths"]["cwd"] == str(
        (result.run_dir / "workspace").resolve()
    )
    assert manifest["execution_paths"]["trace_path"] == str(
        (
            result.run_dir / "workspace" / ".writing" / "trace" / "process.jsonl"
        ).resolve()
    )


def test_run_records_unique_codex_subagent_spawns(tmp_path: Path) -> None:
    class SpawnRolloutExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds):
            result = super().run(command, cwd=cwd, timeout_seconds=timeout_seconds)
            rollout = tmp_path / "codex-home" / "sessions" / "attempt.jsonl"
            rollout.parent.mkdir(parents=True, exist_ok=True)
            rollout.write_bytes(result.stdout)
            return result

    executor = SpawnRolloutExecutor([_result(subagent_spawns=2)])
    runner = _runner(tmp_path, executor=executor)

    result = runner.run_prompt(_prompt(), condition_id="A1", platform="codex")

    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["subagent_spawn_count"] == 2


def test_extract_subagent_spawn_count_deduplicates_started_and_completed_events() -> (
    None
):
    stream = (
        b'{"type":"item.started","item":{"id":"collab-1",'
        b'"type":"collab_tool_call","tool":"spawn_agent"}}\n'
        b'{"type":"item.completed","item":{"id":"collab-1",'
        b'"type":"collab_tool_call","tool":"spawn_agent"}}\n'
        b'{"type":"item.completed","item":{"id":"collab-2",'
        b'"type":"collab_tool_call","tool":"spawn_agent"}}\n'
    )

    assert extract_subagent_spawn_count(stream) == 2
    assert extract_subagent_spawn_count(b'{"type":"item.completed"}\n') == 0


def test_collects_only_new_or_changed_codex_rollouts_under_run_dir(
    tmp_path: Path,
) -> None:
    codex_home = tmp_path / "codex-home"
    sessions = codex_home / "sessions"
    unchanged = sessions / "old.jsonl"
    changed = sessions / "changed.jsonl"
    unchanged.parent.mkdir(parents=True)
    unchanged.write_text("pre-existing")
    changed.write_text("before")
    created = sessions / "2026" / "new.jsonl"

    class RolloutExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds):
            changed.write_text("after")
            created.parent.mkdir(parents=True)
            created.write_text("created during attempt")
            return super().run(command, cwd=cwd, timeout_seconds=timeout_seconds)

    runner = _runner(
        tmp_path / "runs",
        executor=RolloutExecutor([_result()]),
        codex_home=codex_home,
    )

    result = runner.run_prompt(_prompt(), condition_id="A1", platform="codex")

    collected_root = result.run_dir / "sessions" / "attempt-001"
    assert (collected_root / "changed.jsonl").read_text() == "after"
    assert (collected_root / "2026" / "new.jsonl").read_text() == (
        "created during attempt"
    )
    assert not (collected_root / "old.jsonl").exists()
    collected_files = [path for path in collected_root.rglob("*") if path.is_file()]
    assert collected_files
    assert all(
        result.run_dir.resolve() in path.resolve().parents for path in collected_files
    )
    checksums = json.loads(result.checksums_path.read_text())
    assert checksums["sessions/attempt-001/changed.jsonl"] == (
        "sha256:" + hashlib.sha256(b"after").hexdigest()
    )
    assert checksums["sessions/attempt-001/2026/new.jsonl"] == (
        "sha256:" + hashlib.sha256(b"created during attempt").hexdigest()
    )


def test_rollout_status_remains_complete_across_retry_without_new_files(
    tmp_path: Path,
) -> None:
    codex_home = tmp_path / "codex-home"

    class FirstAttemptRolloutExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds):
            result = super().run(command, cwd=cwd, timeout_seconds=timeout_seconds)
            if len(self.calls) == 1:
                rollout = codex_home / "sessions" / "attempt.jsonl"
                rollout.parent.mkdir(parents=True, exist_ok=True)
                rollout.write_bytes(result.stdout)
            return result

    runner = _runner(
        tmp_path / "runs",
        config=_config(retry_policy=1),
        executor=FirstAttemptRolloutExecutor([_result(returncode=1), _result()]),
        codex_home=codex_home,
    )

    result = runner.run_prompt(_prompt(), condition_id="A1", platform="codex")

    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["rollout_collection"]["status"] == "complete"
    assert (result.run_dir / "sessions" / "attempt-001" / "attempt.jsonl").is_file()


@pytest.mark.parametrize(
    "payload",
    [
        b"https://example.test/source",
        b"curl https://example.test",
        b"wget file",
        b"web_search",
        b'codex --config web_search="disabled"',
        b'{"type":"config","value":"web_search=\\"disabled\\""}',
        b'{"type":"error","message":"request failed: https://api.openai.com/v1/responses"}',
        b'{"type":"error","event":"web_search","message":"disabled"}',
        b'{"type":"item.completed","item":{"type":"agent_message",'
        b'"text":"try web_search at https://example.test"}}',
    ],
)
def test_tripwire_ignores_non_invocation_text(payload: bytes) -> None:
    reject_retrieval(payload, b"")


def test_genuine_web_search_tool_invocation_is_rejected() -> None:
    payload = (
        b'{"type":"item.completed","item":{"type":"web_search_call",'
        b'"status":"completed"}}\n'
    )
    with pytest.raises(RetrievalViolation, match="retrieval event"):
        reject_retrieval(payload, b"")


def test_network_command_in_executed_command_event_is_rejected() -> None:
    payload = (
        b'{"type":"item.started","item":{"type":"command_execution",'
        b'"command":"curl https://example.test"}}\n'
    )
    with pytest.raises(RetrievalViolation, match="retrieval event"):
        reject_retrieval(payload, b"")


def test_fallback_artifact_still_rejects_explicit_network_commands() -> None:
    with pytest.raises(RetrievalViolation, match="retrieval marker"):
        reject_retrieval(
            b"Evidence gathered with curl https://example.test/source",
            b"",
            scan_artifact_text=True,
        )


def test_retrieval_tripwire_recognizes_generic_event_key() -> None:
    assert _retrieval_marker({"event": "web_search"}) == "web_search"
    with pytest.raises(RetrievalViolation, match="retrieval event"):
        reject_retrieval(b'{"event":"web_search"}', b"")


def test_runner_preserves_retrieval_evidence_in_artifact_and_manifest(
    tmp_path: Path,
) -> None:
    rejected = b'{"event":"web_search","query":"example"}\n'
    result = ExecutionResult(
        returncode=0,
        stdout=rejected,
        stderr=b"",
        session_id="session-1",
    )
    runner = _runner(tmp_path, executor=_RetryExecutor([result]))

    with pytest.raises(RetrievalViolation) as captured:
        runner.run_prompt(
            _prompt(), condition_id="A1", platform="codex", run_id="evidence"
        )

    violation = captured.value
    assert violation.matched_pattern == "web_search"
    assert violation.matching_line == rejected.decode().rstrip("\n")
    assert "matched_pattern='web_search'" in str(violation)
    run_dir = tmp_path / "WritingBench" / "A1" / "codex" / "evidence"
    artifact = run_dir / "rejected-output.stdout"
    assert artifact.read_bytes() == rejected
    manifest = json.loads((run_dir / "run-manifest.json").read_text())
    assert manifest["failure"]["retrieval"] == {
        "artifact": "rejected-output.stdout",
        "matched_pattern": "web_search",
        "matching_line": rejected.decode().rstrip("\n"),
        "sha256": "sha256:" + hashlib.sha256(rejected).hexdigest(),
        "stream": "stdout",
        "artifact_source": "transport",
    }


def test_trace_validation_requires_contract_fields(tmp_path: Path) -> None:
    path = tmp_path / "process.jsonl"
    path.write_text(json.dumps({"event_type": "process_switch"}) + "\n")

    with pytest.raises(TraceValidationError, match="evidence"):
        validate_trace(
            path,
            condition_id="A4",
            declared_processes=WRITING_TRACE_PROCESSES,
        )


def test_trace_validation_enforces_stage_counts_and_goal_rules(tmp_path: Path) -> None:
    a2_path = tmp_path / "a2.jsonl"
    a2_path.write_text(
        "".join(
            json.dumps(
                _event(
                    "process_switch",
                    process=stage,
                    from_process=previous,
                )
            )
            + "\n"
            for previous, stage in (
                (None, "pre-write"),
                ("pre-write", "write"),
                ("write", "re-write"),
            )
        )
    )
    validate_trace(
        a2_path,
        condition_id="A2",
        declared_processes=("pre-write", "write", "re-write"),
        goal_events="forbidden",
        allowed_event_types=("process_switch",),
        min_events=3,
        max_events=3,
        process_order=("pre-write", "write", "re-write"),
    )

    a3_path = tmp_path / "a3.jsonl"
    a3_path.write_text(
        "".join(
            json.dumps(_event("process_switch", process=process)) + "\n"
            for process in (
                "task-decomposition",
                "task-execution",
                "task-revision",
            )
        )
    )
    validate_trace(
        a3_path,
        condition_id="A3",
        declared_processes=(
            "task-decomposition",
            "task-execution",
            "task-revision",
        ),
        goal_events="forbidden",
        allowed_event_types=("process_switch",),
    )

    invalid_a3 = tmp_path / "a3-invalid-process.jsonl"
    invalid_a3.write_text(
        json.dumps(_event("process_switch", process="writing")) + "\n"
    )
    with pytest.raises(TraceValidationError, match="not declared"):
        validate_trace(
            invalid_a3,
            condition_id="A3",
            declared_processes=(
                "task-decomposition",
                "task-execution",
                "task-revision",
            ),
            goal_events="forbidden",
            allowed_event_types=("process_switch",),
        )

    invalid_a3_event_type = tmp_path / "a3-invalid-event-type.jsonl"
    invalid_a3_event_type.write_text(
        json.dumps(_event("stage_event", process="task-decomposition")) + "\n"
    )
    with pytest.raises(TraceValidationError, match="not allowed"):
        validate_trace(
            invalid_a3_event_type,
            condition_id="A3",
            declared_processes=(
                "task-decomposition",
                "task-execution",
                "task-revision",
            ),
            goal_events="forbidden",
            allowed_event_types=("process_switch",),
        )

    a4_path = tmp_path / "a4.jsonl"
    a4_path.write_text(json.dumps(_event("process_switch")) + "\n")
    with pytest.raises(
        TraceValidationError, match="A4 requires at least one goal event"
    ):
        validate_trace(
            a4_path,
            condition_id="A4",
            declared_processes=WRITING_TRACE_PROCESSES,
            goal_events="allowed",
            allowed_event_types=(
                "process_switch",
                "goal_created",
                "goal_developed",
                "goal_regenerated",
            ),
            require_goal_events=True,
        )

    valid_a4_events = _event("process_switch", process="planning")
    valid_a4_path = tmp_path / "a4-valid.jsonl"
    valid_a4_path.write_text(
        json.dumps(valid_a4_events) + "\n" + json.dumps(_event("goal_created")) + "\n"
    )
    validate_trace(
        valid_a4_path,
        condition_id="A4",
        declared_processes=WRITING_TRACE_PROCESSES,
        goal_events="allowed",
        allowed_event_types=(
            "process_switch",
            "goal_created",
            "goal_developed",
            "goal_regenerated",
        ),
        require_goal_events=True,
    )

    invalid_goal_path = tmp_path / "a4-invalid-goal.jsonl"
    invalid_goal = _event("goal_created", process="goal-setting")
    invalid_goal.pop("parent_goal_id")
    invalid_goal_path.write_text(
        json.dumps(_event("process_switch")) + "\n" + json.dumps(invalid_goal) + "\n"
    )
    with pytest.raises(
        TraceValidationError, match="goal-aware event needs parent_goal_id"
    ):
        validate_trace(
            invalid_goal_path,
            condition_id="A4",
            declared_processes=WRITING_TRACE_PROCESSES,
            goal_events="allowed",
            allowed_event_types=(
                "process_switch",
                "goal_created",
                "goal_developed",
                "goal_regenerated",
            ),
            require_goal_events=True,
        )

    a5_path = tmp_path / "a5.jsonl"
    a5_path.write_text(
        json.dumps(_event("goal_created", process="goal-setting")) + "\n"
    )
    with pytest.raises(TraceValidationError, match="A5"):
        validate_trace(
            a5_path,
            condition_id="A5",
            declared_processes=WRITING_TRACE_PROCESSES,
            goal_events="forbidden",
            allowed_event_types=(
                "process_switch",
                "goal_created",
                "goal_developed",
                "goal_regenerated",
            ),
        )


@pytest.mark.parametrize(
    ("condition_id", "process"),
    (("A1", "generate"), ("A3", "task-decomposition")),
)
def test_trace_validation_rejects_undeclared_process_switch_endpoints(
    tmp_path: Path, condition_id: str, process: str
) -> None:
    for name, endpoint_kwargs in (
        (
            "from",
            {"from_process": "not-declared", "to_process": process},
        ),
        (
            "to",
            {"from_process": None, "to_process": "also-not-declared"},
        ),
    ):
        path = tmp_path / f"{condition_id}-{name}.jsonl"
        path.write_text(
            json.dumps(
                _event(
                    "process_switch",
                    process=process,
                    **endpoint_kwargs,
                )
            )
            + "\n"
        )
        with pytest.raises(
            TraceValidationError,
            match=f"process_switch {name}_process .*not declared",
        ):
            validate_trace(
                path,
                condition_id=condition_id,
                declared_processes=(
                    ("generate",)
                    if condition_id == "A1"
                    else (
                        "task-decomposition",
                        "task-execution",
                        "task-revision",
                    )
                ),
                goal_events="forbidden",
                allowed_event_types=("process_switch",),
            )


def test_run_fails_on_schema_invalid_plugin_trace(tmp_path: Path) -> None:
    class InvalidTraceExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds):
            result = super().run(command, cwd=cwd, timeout_seconds=timeout_seconds)
            trace_path = cwd / ".writing" / "trace" / "process.jsonl"
            event = json.loads(trace_path.read_text())
            del event["evidence"]
            trace_path.write_text(json.dumps(event) + "\n")
            return result

    runner = _runner(tmp_path, executor=InvalidTraceExecutor([_result()]))

    with pytest.raises(TraceValidationError, match="evidence"):
        runner.run_prompt(_prompt(), condition_id="A1", platform="codex")


class _RetryExecutor:
    def __init__(self, results: list[ExecutionResult]) -> None:
        self.results = results
        self.calls: list[list[str]] = []

    def run(self, command, *, cwd, timeout_seconds):
        self.calls.append(command)
        trace_path = cwd / ".writing" / "trace" / "process.jsonl"
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace_path.write_text(
            json.dumps(_event("process_switch", process="generate")) + "\n"
        )
        return self.results.pop(0)


def _result(
    *,
    output: str = "final output " * 10,
    returncode: int = 0,
    timed_out: bool = False,
    usage: dict[str, int] | None = None,
    subagent_spawns: int = 0,
    include_usage: bool = True,
) -> ExecutionResult:
    payload = {
        "type": "item.completed",
        "item": {"type": "agent_message", "text": output},
        "thread_id": "session-1",
    }
    stream = [payload]
    for index in range(subagent_spawns):
        item = {
            "id": f"collab-{index}",
            "type": "collab_tool_call",
            "tool": "spawn_agent",
        }
        stream.extend(
            [
                {"type": "item.started", "item": item},
                {"type": "item.completed", "item": item},
            ]
        )
    if include_usage:
        usage = usage or {"output_tokens": 1}
        stream.append({"type": "turn.completed", "usage": usage})
    return ExecutionResult(
        returncode=returncode,
        stdout=("\n".join(json.dumps(event) for event in stream) + "\n").encode(),
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
    runner = _runner(tmp_path, _config(retry_policy=1), executor=executor)

    runner.run_prompt(_prompt(), condition_id="A1", platform="codex")

    assert len(executor.calls) == 2
    assert executor.calls[1][0:3] == ["codex", "exec", "resume"]
    assert "session-1" in executor.calls[1]


def test_retry_exhaustion_fails_after_fixed_attempt_count(tmp_path: Path) -> None:
    executor = _RetryExecutor([_result(returncode=1), _result(returncode=1)])
    runner = _runner(tmp_path, _config(retry_policy=1), executor=executor)

    with pytest.raises(ExecutionError, match="status 1"):
        runner.run_prompt(_prompt(), condition_id="A1", platform="codex")
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
    runner = _runner(tmp_path, _config(retry_policy=1), executor=executor)

    with pytest.raises(
        ExecutionError,
        match=r"return code 1\): workspace is not trusted",
    ):
        runner.run_prompt(_prompt(), condition_id="A1", platform="codex")


def test_a5_rejects_a_new_goals_file(tmp_path: Path) -> None:
    class GoalWritingExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds):
            result = super().run(command, cwd=cwd, timeout_seconds=timeout_seconds)
            goals = cwd / ".writing" / "goals.md"
            (cwd / ".writing" / "draft.md").write_text("final output " * 10)
            goals.write_text("should not exist")
            return result

    runner = _runner(tmp_path, executor=GoalWritingExecutor([_result()]))

    with pytest.raises(ExecutionError, match="goals.md"):
        runner.run_prompt(_prompt(), condition_id="A5", platform="codex")


def test_runner_rejects_retrieval_in_draft_fallback(tmp_path: Path) -> None:
    class DraftRetrievalExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds):
            result = super().run(command, cwd=cwd, timeout_seconds=timeout_seconds)
            draft = cwd / ".writing" / "draft.md"
            draft.write_text("Evidence gathered with curl https://example.test/source")
            return result

    runner = _runner(tmp_path, executor=DraftRetrievalExecutor([_result(output="")]))

    with pytest.raises(RetrievalViolation, match="retrieval marker"):
        runner.run_prompt(_prompt(), condition_id="A1", platform="codex")

    run_dir = tmp_path / "WritingBench" / "A1" / "codex"
    manifest = json.loads(
        next(run_dir.iterdir()).joinpath("run-manifest.json").read_text()
    )
    assert manifest["failure"]["retrieval"]["artifact_source"] == "draft"
    assert manifest["failure"]["retrieval"]["artifact"] == "rejected-output.draft"
    assert (next(run_dir.iterdir()) / "rejected-output.draft").is_file()


def test_runner_rejects_a_summary_when_workspace_draft_is_the_product(
    tmp_path: Path,
) -> None:
    class SummaryExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds):
            result = super().run(command, cwd=cwd, timeout_seconds=timeout_seconds)
            draft = cwd / ".writing" / "draft.md"
            draft.write_text("draft " * 100)
            return result

    runner = _runner(
        tmp_path,
        executor=SummaryExecutor([_result(output="short summary")]),
    )

    with pytest.raises(ExecutionError, match="less than 50% of draft.md"):
        runner.run_prompt(
            _prompt(),
            condition_id="A3",
            platform="codex",
            run_id="summary-output",
        )

    run_dir = tmp_path / "WritingBench" / "A3" / "codex" / "summary-output"
    assert not (run_dir / "output.raw").exists()
    assert (
        (run_dir / "workspace" / ".writing" / "draft.md")
        .read_text()
        .startswith("draft")
    )
    manifest = json.loads((run_dir / "run-manifest.json").read_text())
    assert manifest["failure"]["type"] == "ExecutionError"
    assert manifest["failure"]["message"].endswith("final_chars=13, draft_chars=599")


def test_a2_rejects_short_response_against_its_draft(tmp_path: Path) -> None:
    class A2DraftExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds):
            result = super().run(command, cwd=cwd, timeout_seconds=timeout_seconds)
            trace_path = cwd / ".writing" / "trace" / "process.jsonl"
            trace_path.write_text(
                "".join(
                    json.dumps(
                        _event(
                            "process_switch",
                            process=process,
                            from_process=previous,
                        )
                    )
                    + "\n"
                    for previous, process in (
                        (None, "pre-write"),
                        ("pre-write", "write"),
                        ("write", "re-write"),
                    )
                )
            )
            (cwd / ".writing" / "draft.md").write_text("draft " * 300)
            return result

    runner = _runner(
        tmp_path,
        executor=A2DraftExecutor(
            [_result(output="one two three four five six seven eight nine ten")]
        ),
    )

    with pytest.raises(ExecutionError, match="less than 50% of draft.md"):
        runner.run_prompt(_prompt(), condition_id="A2", platform="codex")


def test_runner_does_not_substitute_draft_for_empty_final_response(
    tmp_path: Path,
) -> None:
    class EmptyResponseExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds):
            result = super().run(command, cwd=cwd, timeout_seconds=timeout_seconds)
            (cwd / ".writing" / "draft.md").write_text("complete draft")
            return result

    runner = _runner(
        tmp_path,
        executor=EmptyResponseExecutor([_result(output="")]),
    )

    with pytest.raises(
        ExecutionError, match="draft.md is not accepted as a substitute"
    ):
        runner.run_prompt(
            _prompt(),
            condition_id="A1",
            platform="codex",
            run_id="empty-output",
        )

    run_dir = tmp_path / "WritingBench" / "A1" / "codex" / "empty-output"
    assert not (run_dir / "output.raw").exists()


def test_frozen_stage_contents_and_provenance_are_recorded(tmp_path: Path) -> None:
    executor = _RetryExecutor([_result()])
    runner = _runner(tmp_path, executor=executor)

    result = runner.run_prompt(_prompt(), condition_id="A1", platform="codex")

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


def test_runner_accounts_for_codex_event_usage_and_marks_missing_usage(
    tmp_path: Path,
) -> None:
    executor = _RetryExecutor(
        [
            _result(
                usage={
                    "output_tokens": 11,
                    "reasoning_output_tokens": 4,
                }
            )
        ]
    )
    runner = _runner(tmp_path, executor=executor)

    result = runner.run_prompt(_prompt(), condition_id="A1", platform="codex")

    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["budget_used_tokens"] == 15
    assert manifest["token_accounting"] == {
        "status": "observed",
        "source": "Codex turn.completed usage",
        "output_tokens": 11,
        "reasoning_output_tokens": 4,
        "total_tokens": 15,
    }
    usage_stream = (
        b'{"type":"turn.completed","usage":{"output_tokens":2}}\n'
        b'{"type":"turn.completed","usage":{"output_tokens":3,'
        b'"reasoning_output_tokens":1}}\n'
    )
    assert extract_token_usage(usage_stream) == {
        "output_tokens": 5,
        "reasoning_output_tokens": 1,
        "total_tokens": 6,
    }
    with pytest.raises(ExecutionError, match="missing token usage"):
        extract_token_usage(b'{"type":"item.completed"}\n')

    no_usage_runner = _runner(
        tmp_path / "no-usage",
        executor=_RetryExecutor([_result(include_usage=False)]),
    )
    with pytest.raises(ExecutionError, match="token usage"):
        no_usage_runner.run_prompt(_prompt(), condition_id="A1", platform="codex")
    no_usage_manifest = json.loads(
        (
            tmp_path
            / "no-usage"
            / "WritingBench"
            / "A1"
            / "codex"
            / next(
                path.name
                for path in (
                    tmp_path / "no-usage" / "WritingBench" / "A1" / "codex"
                ).iterdir()
                if path.is_dir()
            )
            / "run-manifest.json"
        ).read_text()
    )
    assert no_usage_manifest["status"] == "unscored"
    assert no_usage_manifest["scoring"]["status"] == "excluded"
    assert no_usage_manifest["budget_used_tokens"] is None
    assert no_usage_manifest["subagent_spawn_count"] == 0
    assert no_usage_manifest["token_accounting"] == {
        "status": "unscored",
        "source": "Codex turn.completed usage",
        "output_tokens": None,
        "reasoning_output_tokens": None,
        "total_tokens": None,
        "error": "missing token usage: Codex stream contains no turn.completed event",
    }


def test_extract_token_usage_rejects_missing_or_malformed_usage() -> None:
    with pytest.raises(ExecutionError, match="token usage"):
        extract_token_usage(b'{"type":"item.completed"}\n')
    with pytest.raises(ExecutionError, match="malformed"):
        extract_token_usage(
            b'{"type":"turn.completed","usage":{"output_tokens":"many"}}\n'
        )


def test_runner_fails_on_over_budget_turn_usage(tmp_path: Path) -> None:
    runner = _runner(
        tmp_path,
        executor=_RetryExecutor(
            [_result(usage={"output_tokens": 80, "reasoning_output_tokens": 21})]
        ),
    )

    with pytest.raises(BudgetExceeded, match="budget"):
        runner.run_prompt(_prompt(), condition_id="A1", platform="codex")


def test_non_draft_condition_has_a_nontrivial_product_floor(tmp_path: Path) -> None:
    prompt = PromptRecord(
        prompt_id="p-1",
        benchmark_name="WritingBench",
        source_version="test",
        prompt_text="Write a memo.",
        requested_output_constraints={"min_words": 20},
        row_hash="row-hash",
    )
    runner = _runner(
        tmp_path,
        executor=_RetryExecutor(
            [_result(output="too short", usage={"output_tokens": 2})]
        ),
    )

    with pytest.raises(ExecutionError, match="completeness floor"):
        runner.run_prompt(prompt, condition_id="A1", platform="codex")

    run_dir = tmp_path / "WritingBench" / "A1" / "codex"
    manifest = json.loads(
        next(run_dir.iterdir()).joinpath("run-manifest.json").read_text()
    )
    assert manifest["product_gate"] == {
        "requires_draft": False,
        "rule": "at least 50% of the requested length, with a 10-unit minimum",
        "minimum_units": 10,
        "unit": "words",
    }


def test_a3_production_shaped_trace_and_draft_gate(tmp_path: Path) -> None:
    class A3Executor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds):
            result = super().run(command, cwd=cwd, timeout_seconds=timeout_seconds)
            trace_path = cwd / ".writing" / "trace" / "process.jsonl"
            trace_path.write_text(
                "".join(
                    json.dumps(
                        _event(
                            "process_switch",
                            process=process,
                        )
                    )
                    + "\n"
                    for process in (
                        "task-decomposition",
                        "task-execution",
                        "task-revision",
                    )
                )
            )
            (cwd / ".writing" / "draft.md").write_text("final " * 60)
            return result

    output = "final " * 60
    runner = _runner(
        tmp_path,
        executor=A3Executor([_result(output=output, usage={"output_tokens": 60})]),
    )
    result = runner.run_prompt(_prompt(), condition_id="A3", platform="codex")
    events = [json.loads(line) for line in result.trace_path.read_text().splitlines()]
    assert [event["process"] for event in events] == [
        "task-decomposition",
        "task-execution",
        "task-revision",
    ]


def test_a3_rejects_goal_events_and_goal_fields(tmp_path: Path) -> None:
    trace_path = tmp_path / "a3-goal.jsonl"
    trace_path.write_text(
        json.dumps(_event("goal_created", process="task-decomposition")) + "\n"
    )
    with pytest.raises(TraceValidationError, match="forbids goal events"):
        validate_trace(
            trace_path,
            condition_id="A3",
            declared_processes=(
                "task-decomposition",
                "task-execution",
                "task-revision",
            ),
            goal_events="forbidden",
            allowed_event_types=(
                "process_switch",
                "goal_created",
                "goal_developed",
                "goal_regenerated",
            ),
        )


def test_a3_rejects_created_goals_file(tmp_path: Path) -> None:
    class A3GoalsExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds):
            result = super().run(command, cwd=cwd, timeout_seconds=timeout_seconds)
            trace_path = cwd / ".writing" / "trace" / "process.jsonl"
            trace_path.write_text(
                json.dumps(_event("process_switch", process="task-decomposition"))
                + "\n"
            )
            (cwd / ".writing" / "draft.md").write_text("final " * 20)
            (cwd / ".writing" / "goals.md").write_text("should not exist")
            return result

    runner = _runner(tmp_path, executor=A3GoalsExecutor([_result()]))

    with pytest.raises(TraceValidationError, match="protected file goals.md"):
        runner.run_prompt(_prompt(), condition_id="A3", platform="codex")


def test_spawn_count_without_rollout_is_unscored(tmp_path: Path) -> None:
    runner = _runner(
        tmp_path,
        executor=_RetryExecutor(
            [_result(subagent_spawns=1, usage={"output_tokens": 1})]
        ),
    )

    with pytest.raises(ExecutionError, match="rollout"):
        runner.run_prompt(_prompt(), condition_id="A1", platform="codex")

    run_dir = tmp_path / "WritingBench" / "A1" / "codex"
    manifest = json.loads(
        next(run_dir.iterdir()).joinpath("run-manifest.json").read_text()
    )
    assert manifest["status"] == "unscored"
    assert manifest["rollout_collection"]["status"] == "absent"
    assert manifest["spawn_extraction"]["status"] == "complete"


def test_spawn_extraction_rejects_malformed_spawn_agent_event() -> None:
    malformed = (
        b'{"type":"item.completed","item":{"type":"collab_tool_call",'
        b'"tool":"spawn_agent"}}\n'
    )
    with pytest.raises(ExecutionError, match="malformed spawn_agent"):
        extract_subagent_spawn_count(malformed)


def test_unreadable_rollout_file_marks_run_unscored(
    tmp_path: Path, monkeypatch
) -> None:
    runner = _runner(tmp_path, executor=_RetryExecutor([_result()]))
    snapshots = iter(
        [
            SessionSnapshot(files={}, present=True, error=None),
            SessionSnapshot(files={}, present=True, error="rollout is unreadable"),
        ]
    )
    monkeypatch.setattr(runner, "_snapshot_codex_sessions", lambda: next(snapshots))

    with pytest.raises(ExecutionError, match="rollout"):
        runner.run_prompt(
            _prompt(),
            condition_id="A1",
            platform="codex",
            run_id="unreadable-rollout",
        )

    manifest = json.loads(
        (
            tmp_path
            / "WritingBench"
            / "A1"
            / "codex"
            / "unreadable-rollout"
            / "run-manifest.json"
        ).read_text()
    )
    assert manifest["status"] == "unscored"
    assert manifest["rollout_collection"] == {
        "status": "error",
        "reason": "rollout is unreadable",
        "source": "CODEX_HOME/sessions",
    }


def test_public_config_constructor_does_not_accept_non_strict_mode() -> None:
    with pytest.raises(TypeError):
        RuntimeConfig.from_dict({}, strict=False)  # type: ignore[call-arg]
