import json

import pytest

from agentic_cogwriter.runner.conditions import load_condition_registry
from agentic_cogwriter.runner.config import RuntimeConfig
from agentic_cogwriter.runner.errors import BudgetExceeded, RetrievalViolation
from agentic_cogwriter.runner.execution import ExecutionResult
from agentic_cogwriter.runner.manifest import PromptRecord
from agentic_cogwriter.runner.runner import ExperimentRunner


class FakeExecutor:
    def __init__(self, *, output="final output", retrieval=False, write_trace=True):
        self.calls = []
        self.output = output
        self.retrieval = retrieval
        self.write_trace = write_trace

    def run(self, command, *, cwd, timeout_seconds):
        self.calls.append((command, cwd, timeout_seconds))
        if self.write_trace:
            trace_path = cwd / ".writing" / "trace" / "process.jsonl"
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            skill = next(
                (
                    skill_name
                    for skill_name in (
                        "writing-single-shot",
                        "writing-linear",
                        "writing-storm-style",
                    )
                    if any(
                        f"/skills/{skill_name}/SKILL.md" in argument
                        for argument in command
                    )
                ),
                "",
            )
            stages = {
                "writing-single-shot": ("single_shot",),
                "writing-linear": ("pre_write", "write", "re_write"),
                "writing-storm-style": (
                    "perspective_discovery",
                    "simulated_qa",
                    "outline",
                    "draft",
                    "polish",
                ),
            }.get(skill, ("single_shot",))
            trace_path.write_text(
                "".join(
                    json.dumps(
                        {
                            "event_type": "stage_event",
                            "stage_id": stage,
                            "timestamp": "2026-01-01T00:00:00+00:00",
                            "responsible_agent": "writer",
                            "process": "writing",
                            "decision": "continue",
                            "evidence": ["supplied context"],
                            "open_uncertainty": [],
                        }
                    )
                    + "\n"
                    for stage in stages
                )
            )
        session_id = "session-1"
        payload = {
            "thread_id": session_id,
            "type": "item.completed",
            "item": {"type": "agent_message", "text": self.output},
        }
        if self.retrieval:
            payload["type"] = "web_search"
        return ExecutionResult(
            returncode=0,
            stdout=(json.dumps(payload) + "\n").encode(),
            stderr=b"",
            session_id=session_id,
        )


def _config():
    return RuntimeConfig.from_dict(
        {
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
    )


def test_registry_uses_uniform_skill_wrappers_and_marks_exploratory_conditions():
    registry = load_condition_registry()

    assert set(registry) == {*(f"A{index}" for index in range(1, 7)), "B1", "B2"}
    assert all(condition.kind == "plugin" for condition in registry.values())
    assert all(
        condition.trace_mode == "plugin_recorded" for condition in registry.values()
    )
    assert [
        registry[condition].skill_name
        for condition in ("A1", "A2", "A3", "A4", "A5", "A6", "B1", "B2")
    ] == [
        "writing-single-shot",
        "writing-linear",
        "writing-storm-style",
        "agentic-cog-writer",
        "cognitive-writing-no-goal-network",
        "cognitive-writing-fixed-order",
        "writing-cogwriter-style",
        "writing-writehere-style",
    ]
    assert all(
        registry[f"A{index}"].analysis_family == "confirmatory" for index in range(1, 7)
    )
    assert all(
        registry[condition].analysis_family == "exploratory"
        for condition in ("B1", "B2")
    )


def test_runner_uses_one_top_level_turn_and_plugin_trace_for_a2(tmp_path):
    prompt = PromptRecord(
        prompt_id="p-1",
        benchmark_name="WritingBench",
        source_version="test",
        prompt_text="Write a memo.",
        supplied_context="Provided facts only.",
        requested_output_constraints={},
        row_hash="row-hash",
    )
    executor = FakeExecutor()
    runner = ExperimentRunner(_config(), output_root=tmp_path, executor=executor)

    result = runner.run_prompt(prompt, condition_id="A2", platform="codex-primary")

    events = [json.loads(line) for line in result.trace_path.read_text().splitlines()]
    assert [event["stage_id"] for event in events] == ["pre_write", "write", "re_write"]
    assert len(executor.calls) == 1
    assert "resume" not in executor.calls[0][0]
    assert any(
        "/skills/writing-linear/SKILL.md" in argument
        for argument in executor.calls[0][0]
    )
    assert (
        result.trace_path.relative_to(result.run_dir).as_posix()
        == ".writing/trace/process.jsonl"
    )
    checksums = json.loads(result.checksums_path.read_text())
    assert checksums[".writing/trace/process.jsonl"].startswith("sha256:")


def test_a3_manifest_keeps_na_trace_policy_without_runner_events(tmp_path):
    prompt = PromptRecord(
        prompt_id="p-1",
        benchmark_name="WritingBench",
        source_version="test",
        prompt_text="Write a memo.",
        supplied_context="Provided facts only.",
        requested_output_constraints={},
        row_hash="row-hash",
    )
    runner = ExperimentRunner(_config(), output_root=tmp_path, executor=FakeExecutor())

    result = runner.run_prompt(prompt, condition_id="A3", platform="codex-primary")

    events = [json.loads(line) for line in result.trace_path.read_text().splitlines()]
    assert [event["stage_id"] for event in events] == [
        "perspective_discovery",
        "simulated_qa",
        "outline",
        "draft",
        "polish",
    ]
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["inputs"]["trace_policy"] == {
        "citation": "N/A",
        "evidence": "N/A",
        "retrieval": "N/A",
    }


def test_runner_rejects_output_over_shared_budget(tmp_path):
    prompt = PromptRecord(
        prompt_id="p-1",
        benchmark_name="WritingBench",
        source_version="test",
        prompt_text="Write a memo.",
        requested_output_constraints={},
        row_hash="row-hash",
    )
    config = _config()
    values = dict(config.values)
    values["maximum_output_tokens"] = 1
    runner = ExperimentRunner(
        RuntimeConfig.from_dict(values),
        output_root=tmp_path,
        executor=FakeExecutor(output="two words"),
    )

    with pytest.raises(BudgetExceeded):
        runner.run_prompt(prompt, condition_id="A1", platform="codex-primary")

    assert len(runner.executor.calls) == 1


def test_runner_fails_closed_on_retrieval_event(tmp_path):
    prompt = PromptRecord(
        prompt_id="p-1",
        benchmark_name="WritingBench",
        source_version="test",
        prompt_text="Write a memo.",
        requested_output_constraints={},
        row_hash="row-hash",
    )
    runner = ExperimentRunner(
        _config(), output_root=tmp_path, executor=FakeExecutor(retrieval=True)
    )

    with pytest.raises(RetrievalViolation):
        runner.run_prompt(prompt, condition_id="A1", platform="codex-primary")


def test_runner_rejects_missing_plugin_trace(tmp_path):
    prompt = PromptRecord(
        prompt_id="p-1",
        benchmark_name="WritingBench",
        source_version="test",
        prompt_text="Write a memo.",
        requested_output_constraints={},
        row_hash="row-hash",
    )
    runner = ExperimentRunner(
        _config(), output_root=tmp_path, executor=FakeExecutor(write_trace=False)
    )

    with pytest.raises(RuntimeError, match="no plugin trace"):
        runner.run_prompt(prompt, condition_id="A1", platform="codex-primary")
