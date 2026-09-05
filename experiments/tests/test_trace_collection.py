import hashlib
import json
import tomllib

import pytest

from agentic_cogwriter.runner.conditions import load_condition_registry
from agentic_cogwriter.runner.config import RuntimeConfig
from agentic_cogwriter.runner.errors import (
    BudgetExceeded,
    ExecutionError,
    RetrievalViolation,
)
from agentic_cogwriter.runner.execution import ExecutionResult
from agentic_cogwriter.runner.manifest import PromptRecord
from agentic_cogwriter.runner.runner import ExperimentRunner


def _plugin_source(tmp_path):
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


def _runner(tmp_path, *, config=None, **kwargs):
    kwargs.setdefault("codex_home", tmp_path / "codex-home")
    return ExperimentRunner(
        config or _config(),
        output_root=tmp_path,
        codex_plugin_root=_plugin_source(tmp_path),
        **kwargs,
    )


class FakeExecutor:
    def __init__(
        self, *, output="final output " * 10, retrieval=False, write_trace=True
    ):
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
                        "writing-adaptive-task-planning",
                        "writing-storm-style",
                    )
                    if any(
                        f"skills/{skill_name}/SKILL.md" in argument
                        for argument in command
                    )
                ),
                "",
            )
            stages = {
                "writing-single-shot": (("generate",),),
                "writing-linear": (
                    ("pre-write",),
                    ("write",),
                    ("re-write",),
                ),
                "writing-adaptive-task-planning": (
                    ("task-decomposition",),
                    ("task-execution",),
                    ("task-revision",),
                ),
                "writing-storm-style": (
                    ("perspective-discovery",),
                    ("simulated-question-answering",),
                    ("outline",),
                    ("per-section-draft",),
                    ("polish",),
                ),
            }.get(skill, (("generate",),))
            trace_path.write_text(
                "".join(
                    json.dumps(
                        {
                            "event_type": "process_switch",
                            "timestamp": "2026-01-01T00:00:00+00:00",
                            "responsible_agent": "writer",
                            "process": process,
                            "from_process": (stages[index - 1][0] if index else None),
                            "to_process": process,
                            "decision": "continue",
                            "evidence": ["supplied context"],
                            "open_uncertainty": [],
                        }
                    )
                    + "\n"
                    for index, (process,) in enumerate(stages)
                )
            )
            if skill in {
                "writing-linear",
                "writing-adaptive-task-planning",
                "writing-storm-style",
            }:
                (cwd / ".writing" / "draft.md").write_text(self.output)
        session_id = "session-1"
        payload = {
            "thread_id": session_id,
            "type": "item.completed",
            "item": {"type": "agent_message", "text": self.output},
        }
        if self.retrieval:
            payload["type"] = "web_search"
        payload_stream = [
            payload,
            {"type": "turn.completed", "usage": {"output_tokens": 1}},
        ]
        return ExecutionResult(
            returncode=0,
            stdout=(
                "\n".join(json.dumps(event) for event in payload_stream) + "\n"
            ).encode(),
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
            "generator_and_judge_family_audit": {
                "generator_model_family_map": {
                    "gpt-test": "gpt",
                    "claude-test": "claude",
                }
            },
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
                "word_rule": (
                    "CJK codepoints plus Unicode-whitespace-separated non-CJK runs"
                ),
            },
        }
    )


def test_registry_uses_uniform_skill_wrappers_and_marks_exploratory_conditions():
    registry = load_condition_registry()

    assert set(registry) == {*(f"A{index}" for index in range(1, 7)), "B1", "B2"}
    assert [
        registry[condition].skill_name
        for condition in ("A1", "A2", "A3", "A4", "A5", "A6", "B1", "B2")
    ] == [
        "writing-single-shot",
        "writing-linear",
        "writing-adaptive-task-planning",
        "agentic-cog-writer",
        "cognitive-writing-no-goal-network",
        "cognitive-writing-fixed-order",
        "writing-cogwriter-style",
        "writing-storm-style",
    ]
    a3_wrapper = tomllib.loads(registry["A3"].plugin_config.read_text(encoding="utf-8"))
    assert a3_wrapper["title"] == "Adaptive Task Planning"
    assert a3_wrapper["trace"]["processes"] == [
        "task-decomposition",
        "task-execution",
        "task-revision",
    ]
    assert tuple(stage.stage_id for stage in registry["A3"].stages) == (
        "task-decomposition",
        "task-execution",
        "task-revision",
    )
    assert tuple(stage.stage_id for stage in registry["B2"].stages) == (
        "perspective_discovery",
        "simulated_qa",
        "outline",
        "draft",
        "polish",
    )
    assert registry["B2"].trace_policy_dict == {
        "citation": "N/A",
        "evidence": "N/A",
        "retrieval": "N/A",
    }
    assert all(
        registry[f"A{index}"].analysis_family == "confirmatory" for index in range(1, 7)
    )
    assert all(
        registry[condition].analysis_family == "exploratory"
        for condition in ("B1", "B2")
    )
    assert registry["A1"].trace_processes == ("generate",)
    assert registry["A2"].trace_processes == ("pre-write", "write", "re-write")
    assert registry["A3"].trace_processes == (
        "task-decomposition",
        "task-execution",
        "task-revision",
    )
    assert registry["B2"].trace_processes == (
        "perspective-discovery",
        "simulated-question-answering",
        "outline",
        "per-section-draft",
        "polish",
    )
    assert [registry[f"A{index}"].product_requires_draft for index in range(1, 7)] == [
        False,
        True,
        True,
        True,
        True,
        True,
    ]
    assert registry["A1"].goal_events == "forbidden"
    assert registry["A2"].goal_events == "forbidden"
    assert registry["A3"].goal_events == "forbidden"
    assert registry["A4"].goal_events == "allowed"
    assert registry["A4"].require_goal_events is True
    assert registry["A5"].goal_events == "forbidden"
    assert registry["A6"].goal_events == "allowed"
    assert registry["A6"].require_goal_events is True
    assert registry["A1"].event_types == ("process_switch",)
    assert registry["A4"].event_types == (
        "process_switch",
        "goal_created",
        "goal_developed",
        "goal_regenerated",
    )
    assert registry["A2"].process_order == (
        "pre-write",
        "write",
        "re-write",
    )
    assert registry["A3"].process_order is None


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
    runner = _runner(tmp_path, executor=executor)

    result = runner.run_prompt(prompt, condition_id="A2", platform="codex")

    events = [json.loads(line) for line in result.trace_path.read_text().splitlines()]
    assert [event["process"] for event in events] == [
        "pre-write",
        "write",
        "re-write",
    ]
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
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["output_hash"].startswith("sha256:")
    assert manifest["trace_hash"] == (
        "sha256:" + hashlib.sha256(result.trace_path.read_bytes()).hexdigest()
    )
    assert not (result.run_dir / "checksums.json").exists()


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
    runner = _runner(tmp_path, executor=FakeExecutor())

    result = runner.run_prompt(prompt, condition_id="A3", platform="codex")

    events = [json.loads(line) for line in result.trace_path.read_text().splitlines()]
    assert [event["process"] for event in events] == [
        "task-decomposition",
        "task-execution",
        "task-revision",
    ]
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["inputs"]["trace_policy"] == {
        "citation": "N/A",
        "evidence": "N/A",
        "retrieval": "N/A",
    }
    assert manifest["inputs"]["trace_contract"] == {
        "event_types": ["process_switch"],
        "goal_events": "forbidden",
        "max_events": None,
        "min_events": 1,
        "process_order": None,
        "processes": [
            "task-decomposition",
            "task-execution",
            "task-revision",
        ],
        "require_goal_events": False,
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
    runner = _runner(
        tmp_path,
        config=RuntimeConfig.from_dict(values),
        executor=FakeExecutor(output="two words"),
    )

    with pytest.raises(BudgetExceeded):
        runner.run_prompt(prompt, condition_id="A1", platform="codex")

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
    runner = _runner(tmp_path, executor=FakeExecutor(retrieval=True))

    with pytest.raises(RetrievalViolation):
        runner.run_prompt(prompt, condition_id="A1", platform="codex")


def test_runner_rejects_missing_plugin_trace(tmp_path):
    prompt = PromptRecord(
        prompt_id="p-1",
        benchmark_name="WritingBench",
        source_version="test",
        prompt_text="Write a memo.",
        requested_output_constraints={},
        row_hash="row-hash",
    )
    runner = _runner(tmp_path, executor=FakeExecutor(write_trace=False))

    with pytest.raises(RuntimeError, match="no plugin trace"):
        runner.run_prompt(prompt, condition_id="A1", platform="codex")


def test_missing_trace_preserves_transport_evidence_and_absolute_paths(tmp_path):
    prompt = PromptRecord(
        prompt_id="p-1",
        benchmark_name="WritingBench",
        source_version="test",
        prompt_text="Write a memo.",
        requested_output_constraints={},
        row_hash="row-hash",
    )
    runner = _runner(tmp_path, executor=FakeExecutor(write_trace=False))

    with pytest.raises(RuntimeError, match="no plugin trace"):
        runner.run_prompt(
            prompt,
            condition_id="A1",
            platform="codex",
            run_id="missing-trace",
        )

    run_dir = tmp_path / "WritingBench" / "A1" / "codex" / "missing-trace"
    stream = (run_dir / "attempt-001.events.jsonl").read_bytes()
    assert stream
    assert (run_dir / "attempt-001.stdout.raw").read_bytes() == stream
    assert (run_dir / "attempt-001.stderr.raw").read_bytes() == b""
    assert (
        (run_dir / "prompt.txt")
        .read_text(encoding="utf-8")
        .startswith("Read the skill file at")
    )

    manifest = json.loads((run_dir / "run-manifest.json").read_text())
    assert manifest["execution_paths"] == {
        "cwd": str((run_dir / "workspace").resolve()),
        "prompt": str((run_dir / "prompt.txt").resolve()),
        "trace_path": str(
            (run_dir / "workspace" / ".writing" / "trace" / "process.jsonl").resolve()
        ),
    }
    evidence_hashes = manifest["evidence_hashes"]
    assert evidence_hashes["attempt-001.events.jsonl"] == (
        "sha256:" + hashlib.sha256(stream).hexdigest()
    )
    assert (
        evidence_hashes["attempt-001.stdout.raw"]
        == evidence_hashes["attempt-001.events.jsonl"]
    )
    assert evidence_hashes["attempt-001.stderr.raw"] == (
        "sha256:" + hashlib.sha256(b"").hexdigest()
    )


def test_trace_path_is_derived_from_codex_cwd(tmp_path):
    prompt = PromptRecord(
        prompt_id="p-1",
        benchmark_name="WritingBench",
        source_version="test",
        prompt_text="Write a memo.",
        requested_output_constraints={},
        row_hash="row-hash",
    )
    executor = FakeExecutor()
    runner = _runner(tmp_path, executor=executor)

    result = runner.run_prompt(
        prompt,
        condition_id="A1",
        platform="codex",
        run_id="trace-cwd",
    )

    _, cwd, _ = executor.calls[0]
    manifest = json.loads(result.manifest_path.read_text())
    expected_trace = cwd / ".writing" / "trace" / "process.jsonl"
    assert manifest["execution_paths"]["cwd"] == str(cwd.resolve())
    assert manifest["execution_paths"]["trace_path"] == str(expected_trace.resolve())
    assert expected_trace.is_file()
    assert result.trace_path == result.run_dir / ".writing" / "trace" / "process.jsonl"


def test_executor_start_failure_preserves_empty_transport_evidence(tmp_path):
    class FailingExecutor:
        def run(self, command, *, cwd, timeout_seconds):
            raise ExecutionError("process could not start")

    runner = _runner(tmp_path, executor=FailingExecutor())

    prompt = PromptRecord(
        prompt_id="p-1",
        benchmark_name="WritingBench",
        source_version="test",
        prompt_text="Write a memo.",
        requested_output_constraints={},
        row_hash="row-hash",
    )

    with pytest.raises(ExecutionError, match="process could not start"):
        runner.run_prompt(
            prompt,
            condition_id="A1",
            platform="codex",
            run_id="executor-failure",
        )

    run_dir = tmp_path / "WritingBench" / "A1" / "codex" / "executor-failure"
    for suffix in ("events.jsonl", "stdout.raw", "stderr.raw"):
        assert (run_dir / f"attempt-001.{suffix}").read_bytes() == b""
    manifest = json.loads((run_dir / "run-manifest.json").read_text())
    assert manifest["evidence_hashes"]["attempt-001.events.jsonl"].startswith("sha256:")


def test_retry_failure_preserves_each_attempt_transport_evidence(tmp_path):
    first_stdout = b'{"thread_id":"session-1","type":"error"}\n'
    second_stdout = b'{"thread_id":"session-1","type":"turn.failed"}\n'

    class RetryFailureExecutor:
        def __init__(self):
            self.calls = []
            self.results = [
                ExecutionResult(
                    returncode=1,
                    stdout=first_stdout,
                    stderr=b"first failure",
                    session_id="session-1",
                ),
                ExecutionResult(
                    returncode=1,
                    stdout=second_stdout,
                    stderr=b"second failure",
                    session_id="session-1",
                ),
            ]

        def run(self, command, *, cwd, timeout_seconds):
            self.calls.append(command)
            return self.results.pop(0)

    prompt = PromptRecord(
        prompt_id="p-1",
        benchmark_name="WritingBench",
        source_version="test",
        prompt_text="Write a memo.",
        requested_output_constraints={},
        row_hash="row-hash",
    )
    executor = RetryFailureExecutor()
    runner = _runner(
        tmp_path,
        config=RuntimeConfig.from_dict({**_config().values, "retry_policy": 1}),
        executor=executor,
    )

    with pytest.raises(ExecutionError, match="status 1"):
        runner.run_prompt(
            prompt,
            condition_id="A1",
            platform="codex",
            run_id="retry-failure",
        )

    run_dir = tmp_path / "WritingBench" / "A1" / "codex" / "retry-failure"
    assert len(executor.calls) == 2
    assert (run_dir / "attempt-001.events.jsonl").read_bytes() == first_stdout
    assert (run_dir / "attempt-002.events.jsonl").read_bytes() == second_stdout
    assert (run_dir / "attempt-001.stdout.raw").read_bytes() == first_stdout
    assert (run_dir / "attempt-002.stdout.raw").read_bytes() == second_stdout
    assert (run_dir / "attempt-001.stderr.raw").read_bytes() == b"first failure"
    assert (run_dir / "attempt-002.stderr.raw").read_bytes() == b"second failure"
    manifest = json.loads((run_dir / "run-manifest.json").read_text())
    assert manifest["attempts"] == 2
    assert set(manifest["evidence_hashes"]) == {
        "prompt.txt",
        "attempt-001.events.jsonl",
        "attempt-001.stdout.raw",
        "attempt-001.stderr.raw",
        "attempt-002.events.jsonl",
        "attempt-002.stdout.raw",
        "attempt-002.stderr.raw",
    }


@pytest.mark.parametrize(
    ("result", "message"),
    [
        (
            ExecutionResult(
                returncode=1,
                stdout=b'{"type":"error"}\n',
                stderr=b"nonzero",
                session_id=None,
            ),
            "status 1",
        ),
        (
            ExecutionResult(
                returncode=-1,
                stdout=b'{"type":"turn.failed"}\n',
                stderr=b"timed out",
                session_id=None,
                timed_out=True,
            ),
            "timed out",
        ),
    ],
)
def test_final_execution_errors_preserve_transport_evidence(tmp_path, result, message):
    class FinalFailureExecutor:
        def run(self, command, *, cwd, timeout_seconds):
            return result

    prompt = PromptRecord(
        prompt_id="p-1",
        benchmark_name="WritingBench",
        source_version="test",
        prompt_text="Write a memo.",
        requested_output_constraints={},
        row_hash="row-hash",
    )
    runner = _runner(tmp_path, executor=FinalFailureExecutor())

    with pytest.raises(ExecutionError, match=message):
        runner.run_prompt(
            prompt,
            condition_id="A1",
            platform="codex",
            run_id="final-failure",
        )

    run_dir = tmp_path / "WritingBench" / "A1" / "codex" / "final-failure"
    assert (run_dir / "attempt-001.events.jsonl").read_bytes() == result.stdout
    assert (run_dir / "attempt-001.stdout.raw").read_bytes() == result.stdout
    assert (run_dir / "attempt-001.stderr.raw").read_bytes() == result.stderr
    manifest = json.loads((run_dir / "run-manifest.json").read_text())
    assert manifest["attempts"] == 1
    assert set(manifest["evidence_hashes"]) == {
        "prompt.txt",
        "attempt-001.events.jsonl",
        "attempt-001.stdout.raw",
        "attempt-001.stderr.raw",
    }
