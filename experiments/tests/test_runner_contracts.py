from __future__ import annotations

import difflib
import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import time
import tomllib
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from agentic_cogwriter.runner import runner as runner_module
from agentic_cogwriter.runner.adapters import PlatformAdapter
from agentic_cogwriter.runner.cli import build_parser
from agentic_cogwriter.runner.conditions import (
    PLATFORMS,
    load_condition_registry,
)
from agentic_cogwriter.runner.config import RuntimeConfig
from agentic_cogwriter.runner.errors import (
    BudgetExceeded,
    ConfigurationError,
    ExecutionError,
    ManifestError,
    RetrievalViolation,
)
from agentic_cogwriter.runner.execution import (
    ExecutionResult,
    SubprocessExecutor,
    _retrieval_marker,
    extract_subagent_spawn_count,
    extract_token_usage,
    reject_retrieval,
)
from agentic_cogwriter.runner.hashing import sha256_json
from agentic_cogwriter.runner.manifest import PromptRecord
from agentic_cogwriter.runner.runner import (
    ExperimentRunner,
    SessionSnapshot,
    _synthesized_codex_config,
)
from agentic_cogwriter.runner.trace import (
    TraceValidationError,
    assess_trace_timestamps,
    validate_trace,
)

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

REPO_ROOT = Path(__file__).parents[2]
CONTRACTS_ROOT = REPO_ROOT / "experiments/conditions/contracts"
PROMPT_SNAPSHOT_PATH = (
    REPO_ROOT
    / "experiments/tests/fixtures/plugin_prompts_before_contract_extraction.json"
)

SINGLE_TURN_CONTRACT = (
    "\n\n## Single-turn contract\n\n"
    "This is a single-turn task with no interactive user; never ask clarification "
    "questions. When the assignment underspecifies audience, purpose, or scope, "
    "apply genre-appropriate defaults without stating them in the deliverable. "
    "Do not change the deliverable's content contract."
)
SINGLE_TURN_CONTRACT_TEXT = SINGLE_TURN_CONTRACT.removeprefix("\n\n") + "\n"
DELEGATION_CONTRACT = (
    "## Delegation contract\n\n"
    "Native subagent delegation is available in this environment. Delegate every "
    "role the skill assigns to a role agent by spawning a Codex subagent as the "
    "skill's delegation brief instructs; performing a delegated role as the "
    "coordinator is not permitted in this run and fails the run."
)
DELEGATION_CONTRACT_TEXT = DELEGATION_CONTRACT + "\n"
DELEGATING_CONDITIONS = ("A3", "A4", "A5", "A6", "B1")

NO_GOAL_SKILL_PATHS = (
    REPO_ROOT / "experiments/baselines/skills/writing-linear/SKILL.md",
    REPO_ROOT / "experiments/baselines/skills/writing-storm-style/SKILL.md",
    REPO_ROOT / "experiments/baselines/skills/writing-cogwriter-style/SKILL.md",
    REPO_ROOT / "experiments/baselines/skills/writing-adaptive-task-planning/SKILL.md",
)
NO_GOAL_FILE_RULE = "Do not create or modify `.writing/goals.md`"
STAGE_SESSION_HEADER = (
    "The following {count} frozen stages run in order within this single session; "
    "each stage's output is the input of the next, and only the final stage's "
    "output is the final response."
)
SINGLE_STAGE_SESSION_HEADER = (
    "The following frozen stage runs within this single session; its output is the "
    "final response."
)


pytestmark = pytest.mark.usefixtures(  # noqa: V107
    "_keep_generator_config_out_of_system_temp"
)


@pytest.fixture  # noqa: V103
def _keep_generator_config_out_of_system_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path / "system-temp"))


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
        "codex_reasoning_effort": "xhigh",
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
        language="en",
        row_hash="row-hash",
    )


def _plugin_source(tmp_path: Path) -> Path:
    root = tmp_path / "plugin-source"
    skills = (
        "writing-single-shot",
        "writing-linear",
        "writing-storm-style",
        "agentic-cog-writer",
        "cognitive-writing-task-objective",
        "cognitive-writing-fixed-order",
        "cognitive-writing-single-writer",
        "cognitive-writing-single-context",
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


def test_subprocess_executor_forwards_the_child_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed: dict[str, object] = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed.update(kwargs)
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr("agentic_cogwriter.runner.execution.subprocess.run", fake_run)
    environment = {"CODEX_HOME": str(tmp_path / "generator-config")}

    result = SubprocessExecutor().run(
        ["codex", "exec"],
        cwd=tmp_path,
        timeout_seconds=5,
        env=environment,
    )

    assert result.returncode == 0
    assert observed["env"] == environment


def test_subprocess_executor_starts_the_child_with_stdin_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed: dict[str, object] = {}

    def fake_run(command, **kwargs):
        observed.update(kwargs)
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr("agentic_cogwriter.runner.execution.subprocess.run", fake_run)

    SubprocessExecutor().run(["codex", "exec"], cwd=tmp_path, timeout_seconds=5)

    # An open stdin pipe makes `codex exec` wait for additional input.
    assert observed["stdin"] is subprocess.DEVNULL


def _runner(tmp_path: Path, config: RuntimeConfig | None = None, **kwargs):
    kwargs.setdefault("codex_home", tmp_path / "codex-home")
    return ExperimentRunner(
        config or _config(),
        output_root=tmp_path,
        codex_plugin_root=_plugin_source(tmp_path),
        **kwargs,
    )


@pytest.mark.parametrize(
    ("platform", "variable", "allowlist"),
    [
        ("codex", "CODEX_HOME", ("config.toml", "auth.json")),
        ("claude-code", "CLAUDE_CONFIG_DIR", (".credentials.json",)),
    ],
)
def test_run_uses_per_run_generator_config_and_copies_only_allowlist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    variable: str,
    allowlist: tuple[str, ...],
) -> None:
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path / "system-temp"))
    source_root = tmp_path / "host-provider-config"
    source_root.mkdir()
    for relative in (*allowlist, "AGENTS.md", "CLAUDE.md", "settings.json"):
        if platform == "codex" and relative == "config.toml":
            continue
        (source_root / relative).write_text(relative, encoding="utf-8")
    if platform == "codex":
        (source_root / "config.toml").write_text(
            """
model_provider = "test-provider"
model_reasoning_effort = "host-value"
personality = "host personality"
instructions = "host instructions"
model_instructions_file = "host-instructions.md"
web_search = "live"

[agents]
reviewer = "host-agent"

[mcp_servers.host]
command = "host-mcp"

[features]
unstable = true

[model_providers.test-provider]
name = "test-provider"
base_url = "https://provider.invalid"
wire_api = "responses"
requires_openai_auth = true
http_headers = { "X-Header" = "header-value" }
env_http_headers = { "X-Env-Header" = "env-value" }
query_params = { "api-version" = "version-value" }

[model_providers.test-provider.auth]
command = "provider-auth"
args = ["--token", "token-value"]
refresh_interval_ms = 120000
""".strip()
            + "\n",
            encoding="utf-8",
        )
    (source_root / "plugins" / "ignored.plugin").mkdir(parents=True)
    (source_root / "plugins" / "ignored.plugin" / "manifest.json").write_text(
        "ignored", encoding="utf-8"
    )
    observed_config_dirs: list[Path] = []
    observed_config_files: list[set[str]] = []
    observed_config_modes: list[int] = []
    observed_config_contents: list[dict[str, object]] = []

    class InspectingExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds, env=None):
            assert env is not None
            config_root = Path(env[variable])
            observed_config_dirs.append(config_root)
            observed_config_modes.append(stat.S_IMODE(config_root.stat().st_mode))
            observed_config_files.append(
                {
                    path.relative_to(config_root).as_posix()
                    for path in config_root.rglob("*")
                    if path.is_file()
                }
            )
            if platform == "codex":
                observed_config_contents.append(
                    tomllib.loads(
                        (config_root / "config.toml").read_text(encoding="utf-8")
                    )
                )
            return super().run(
                command, cwd=cwd, timeout_seconds=timeout_seconds, env=env
            )

    executor = InspectingExecutor([_result()])
    runner_kwargs = {"executor": executor}
    if platform == "codex":
        runner_kwargs["codex_home"] = source_root
    else:
        runner_kwargs["claude_config_dir"] = source_root
    runner = _runner(tmp_path / "runs", **runner_kwargs)

    result = runner.run_prompt(_prompt(), condition_id="A1", platform=platform)

    manifest = json.loads(result.manifest_path.read_text())
    config_root = observed_config_dirs[0]
    assert executor.environments[0] is not None
    assert executor.environments[0][variable] == str(config_root.resolve())
    if platform == "codex":
        assert executor.environments[0]["HOME"] == str(config_root / "home")
    assert observed_config_files == [set(allowlist)]
    assert config_root == (tmp_path / "runs" / ".generator-config" / result.run_id)
    assert observed_config_modes == [0o700]
    if platform == "codex":
        assert observed_config_contents == [
            {
                "model_provider": "test-provider",
                "model_reasoning_effort": "xhigh",
                "model_providers": {
                    "test-provider": {
                        "name": "test-provider",
                        "base_url": "https://provider.invalid",
                        "wire_api": "responses",
                        "requires_openai_auth": True,
                        "http_headers": {"X-Header": "header-value"},
                        "env_http_headers": {"X-Env-Header": "env-value"},
                        "query_params": {"api-version": "version-value"},
                        "auth": {
                            "command": "env",
                            "args": [
                                f"HOME={Path.home()}",
                                "provider-auth",
                                "--token",
                                "token-value",
                            ],
                            "refresh_interval_ms": 120000,
                        },
                    }
                },
            }
        ]
    assert config_root not in result.run_dir.parents
    assert result.run_dir not in config_root.parents
    assert not config_root.exists()
    assert manifest["execution_paths"]["generator_config_dir"] == str(
        config_root.resolve()
    )
    assert not any(
        path.name in {"auth.json", ".credentials.json"}
        for path in result.run_dir.rglob("*")
        if path.is_file()
    )


@pytest.mark.parametrize(
    ("platform", "variable", "allowlist"),
    [
        ("codex", "CODEX_HOME", ("config.toml", "auth.json")),
        ("claude-code", "CLAUDE_CONFIG_DIR", (".credentials.json",)),
    ],
)
def test_run_removes_generator_config_after_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    variable: str,
    allowlist: tuple[str, ...],
) -> None:
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path / "system-temp"))
    source_root = tmp_path / "host-provider-config"
    source_root.mkdir()
    for relative in allowlist:
        if platform == "codex" and relative == "config.toml":
            (source_root / relative).write_text(
                'model_provider = "test"\n\n[model_providers.test]\nname = "test"\n',
                encoding="utf-8",
            )
            continue
        (source_root / relative).write_text(relative, encoding="utf-8")
    observed_config_dirs: list[Path] = []
    observed_config_files: list[set[str]] = []
    observed_config_modes: list[int] = []

    class InspectingExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds, env=None):
            assert env is not None
            config_root = Path(env[variable])
            observed_config_dirs.append(config_root)
            observed_config_modes.append(stat.S_IMODE(config_root.stat().st_mode))
            observed_config_files.append(
                {
                    path.relative_to(config_root).as_posix()
                    for path in config_root.rglob("*")
                    if path.is_file()
                }
            )
            return super().run(
                command, cwd=cwd, timeout_seconds=timeout_seconds, env=env
            )

    executor = InspectingExecutor([_result(returncode=1)])
    runner_kwargs = {"executor": executor}
    if platform == "codex":
        runner_kwargs["codex_home"] = source_root
    else:
        runner_kwargs["claude_config_dir"] = source_root
    runner = _runner(
        tmp_path / "runs",
        _config(retry_policy=0),
        **runner_kwargs,
    )

    with pytest.raises(ExecutionError, match="status 1"):
        runner.run_prompt(
            _prompt(), condition_id="A1", platform=platform, run_id="failure"
        )

    run_dir = tmp_path / "runs" / "WritingBench" / "A1" / platform / "failure"
    assert observed_config_files == [set(allowlist)]
    assert observed_config_dirs[0] == (
        tmp_path / "runs" / ".generator-config" / "failure"
    )
    assert observed_config_modes == [0o700]
    assert run_dir not in observed_config_dirs[0].parents
    assert observed_config_dirs[0] not in run_dir.parents
    assert not observed_config_dirs[0].exists()
    assert not any(
        path.name in {"auth.json", ".credentials.json"}
        for path in run_dir.rglob("*")
        if path.is_file()
    )


def test_run_removes_generator_config_when_preflight_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path / "system-temp"))
    source_root = tmp_path / "host-provider-config"
    source_root.mkdir()
    (source_root / "config.toml").write_text(
        'model_provider = "test"\n\n[model_providers.test]\nname = "test"\n',
        encoding="utf-8",
    )
    (source_root / "auth.json").write_text("{}", encoding="utf-8")
    runner = _runner(tmp_path / "runs", codex_home=source_root)
    observed_config_dirs: list[Path] = []
    prepare = runner._prepare_generator_environment

    def capture_config_dir(
        platform: str, *, run_id: str, lock_file=None
    ) -> tuple[Path, dict[str, str]]:
        config_dir, environment = prepare(platform, run_id=run_id, lock_file=lock_file)
        observed_config_dirs.append(config_dir)
        return config_dir, environment

    monkeypatch.setattr(runner, "_prepare_generator_environment", capture_config_dir)

    def fail_provenance(_benchmark_name: str) -> dict[str, object]:
        raise RuntimeError("provenance failure")

    monkeypatch.setattr(
        "agentic_cogwriter.runner.runner.load_benchmark_provenance",
        fail_provenance,
    )

    with pytest.raises(RuntimeError, match="provenance failure"):
        runner.run_prompt(_prompt(), condition_id="A1", platform="codex")

    assert len(observed_config_dirs) == 1
    assert not observed_config_dirs[0].exists()


def test_generator_config_collision_does_not_remove_existing_directory(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "runs"
    runner = _runner(output_root)
    existing_root = output_root / ".generator-config" / "collision"
    existing_root.mkdir(parents=True)
    sentinel = existing_root / "sentinel"
    sentinel.write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError):
        runner._prepare_generator_environment("codex", run_id="collision")

    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_generator_config_sweep_rejects_symlinked_parent(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "runs"
    output_root.mkdir()
    outside_root = tmp_path / "outside-generator-config"
    outside_root.mkdir()
    config_parent = output_root / ".generator-config"
    config_parent.symlink_to(outside_root, target_is_directory=True)
    runner = _runner(output_root)

    with pytest.raises(ConfigurationError, match="symlink"):
        runner.run_prompt(_prompt(), condition_id="A1", platform="codex")

    assert not (output_root / "WritingBench").exists()


def test_run_refuses_when_generator_config_lock_is_held(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "runs"
    config_parent = output_root / ".generator-config"
    config_parent.mkdir(parents=True)
    lock_path = config_parent / ".lock"
    runner = _runner(output_root)

    with lock_path.open("a+") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ConfigurationError, match="another run holds"):
            runner.run_prompt(
                _prompt(), condition_id="A1", platform="codex", run_id="locked"
            )

    assert not (output_root / "WritingBench" / "A1" / "codex" / "locked").exists()


@pytest.mark.parametrize("target_exists", [True, False])
def test_generator_config_lock_rejects_symlink(
    tmp_path: Path, target_exists: bool
) -> None:
    output_root = tmp_path / "runs"
    config_parent = output_root / ".generator-config"
    config_parent.mkdir(parents=True)
    outside_lock = tmp_path / "outside.lock"
    if target_exists:
        outside_lock.write_text("keep", encoding="utf-8")
    (config_parent / ".lock").symlink_to(outside_lock)
    runner = _runner(output_root)

    with pytest.raises(ConfigurationError, match="lock"):
        runner._acquire_generator_config_lock()

    assert outside_lock.exists() is target_exists
    if target_exists:
        assert outside_lock.read_text(encoding="utf-8") == "keep"


def test_runner_sweeps_stale_generator_config_before_new_root(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "runs"
    stale_root = output_root / ".generator-config" / "stale"
    stale_root.mkdir(parents=True)
    (stale_root / "auth.json").write_text("stale", encoding="utf-8")
    stale_time = time.time() - 60
    os.utime(stale_root, (stale_time, stale_time))
    runner = _runner(output_root)

    config_root, _environment = runner._prepare_generator_environment(
        "claude-code", run_id="fresh"
    )
    try:
        assert not stale_root.exists()
        assert config_root.exists()
    finally:
        shutil.rmtree(config_root, ignore_errors=True)


def test_codex_config_rejects_missing_selected_provider_table(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "host-provider-config"
    source_root.mkdir()
    (source_root / "config.toml").write_text(
        'model_provider = "missing"\n\n[model_providers.other]\nname = "other"\n',
        encoding="utf-8",
    )
    executor = _RetryExecutor([_result()])
    runner = _runner(tmp_path / "runs", codex_home=source_root, executor=executor)

    with pytest.raises(ConfigurationError, match="missing.*model_providers"):
        runner._prepare_generator_environment("codex", run_id="missing-provider")

    assert executor.calls == []
    assert not (tmp_path / "runs" / ".generator-config" / "missing-provider").exists()


def test_codex_config_rejects_unallowlisted_provider_key(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "host-provider-config"
    source_root.mkdir()
    (source_root / "config.toml").write_text(
        """
model_provider = "test"

[model_providers.test]
name = "test"
experimental_bearer_token = "secret"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    runner = _runner(tmp_path / "runs", codex_home=source_root)

    with pytest.raises(ConfigurationError, match="experimental_bearer_token"):
        runner._prepare_generator_environment("codex", run_id="rejected-key")

    assert not (tmp_path / "runs" / ".generator-config" / "rejected-key").exists()


def test_synthesized_codex_config_drops_known_provider_capabilities() -> None:
    source_config = {
        "model_provider": "test",
        "model_providers": {
            "test": {
                "name": "test",
                "supports_standalone_web_search": True,
                "supports_websockets": False,
            }
        },
    }

    parsed = tomllib.loads(_synthesized_codex_config(source_config, "xhigh"))

    assert parsed["model_providers"]["test"] == {"name": "test"}


def test_synthesized_codex_config_rejects_string_auth_args() -> None:
    source_config = {
        "model_provider": "p",
        "model_providers": {
            "p": {"name": "p", "auth": {"command": "helper", "args": "--flag"}}
        },
    }

    with pytest.raises(ConfigurationError, match="auth args must be an array"):
        _synthesized_codex_config(source_config, "xhigh")


def test_synthesized_codex_config_round_trips_escaped_unicode_values() -> None:
    source_config = {
        "model_provider": "quoted-provider",
        "model_providers": {
            "quoted-provider": {
                "name": 'name "quoted"',
                "base_url": r"https://provider.invalid/path\\segment",
                "wire_api": "responses",
                "env_key": "TOKEN_日本",
                "requires_openai_auth": True,
                "http_headers": {"X-Header": 'value "quoted" \\ 日本'},
                "env_http_headers": {"X-Env": "環境"},
                "query_params": {"q": "a\\b"},
                "auth": {
                    "command": r"auth\\helper",
                    "args": ["--label", '値 "quoted"'],
                    "refresh_interval_ms": 42,
                },
            }
        },
    }

    rendered = _synthesized_codex_config(source_config, "xhigh")
    parsed = tomllib.loads(rendered)

    provider = source_config["model_providers"]["quoted-provider"]
    assert parsed == {
        "model_provider": "quoted-provider",
        "model_reasoning_effort": "xhigh",
        "model_providers": {
            "quoted-provider": {
                **provider,
                "auth": {
                    "command": "env",
                    "args": [
                        f"HOME={Path.home()}",
                        r"auth\\helper",
                        "--label",
                        '値 "quoted"',
                    ],
                    "refresh_interval_ms": 42,
                },
            }
        },
    }


def test_run_rejects_generator_config_under_system_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    executor = _RetryExecutor([_result()])
    runner = _runner(tmp_path / "runs", executor=executor)
    expected_root = tmp_path / "runs" / ".generator-config" / "guard"

    with pytest.raises(
        ConfigurationError,
        match="system temporary directory",
    ) as error:
        runner.run_prompt(
            _prompt(), condition_id="A1", platform="codex", run_id="guard"
        )

    assert str(expected_root) in str(error.value)
    assert executor.calls == []


def test_codex_session_snapshot_uses_the_run_generator_config_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path / "system-temp"))
    host_codex_home = tmp_path / "host-codex"
    host_sessions = host_codex_home / "sessions"
    host_sessions.mkdir(parents=True)
    (host_sessions / "host-only.jsonl").write_text("host", encoding="utf-8")

    class SessionExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds, env=None):
            sessions = Path(env["CODEX_HOME"]) / "sessions"
            sessions.mkdir()
            (sessions / "run-only.jsonl").write_text("run", encoding="utf-8")
            return super().run(
                command, cwd=cwd, timeout_seconds=timeout_seconds, env=env
            )

    executor = SessionExecutor([_result()])
    runner = _runner(
        tmp_path / "runs",
        executor=executor,
        codex_home=host_codex_home,
    )

    result = runner.run_prompt(_prompt(), condition_id="A1", platform="codex")

    collected = result.run_dir / "sessions" / "attempt-001" / "run-only.jsonl"
    assert collected.read_text() == "run"
    assert not (
        result.run_dir / "sessions" / "attempt-001" / "host-only.jsonl"
    ).exists()


def test_runner_rejects_guidance_ancestor_before_starting_a_session(
    tmp_path: Path,
) -> None:
    blocked_root = tmp_path / "blocked"
    blocked_root.mkdir()
    (blocked_root / "CLAUDE.md").write_text("user guidance", encoding="utf-8")
    executor = _RetryExecutor([_result()])
    runner = _runner(blocked_root / "runs", executor=executor)

    with pytest.raises(ConfigurationError, match="CLAUDE.md"):
        runner.run_prompt(_prompt(), condition_id="A1", platform="codex")

    assert executor.calls == []
    assert not (blocked_root / "runs" / "WritingBench").exists()


def test_guidance_scan_root_bounds_only_the_test_suite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    host = tmp_path / "host"
    (host / ".codex").mkdir(parents=True)
    workspace = host / "runs" / "workspace"
    monkeypatch.setattr(runner_module, "_GUIDANCE_SCAN_ROOT", host / "runs")

    runner_module._assert_guidance_free_workspace(workspace)

    monkeypatch.setattr(runner_module, "_GUIDANCE_SCAN_ROOT", None)
    with pytest.raises(ConfigurationError, match=r"host/\.codex"):
        runner_module._assert_guidance_free_workspace(workspace)


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
    assert not hasattr(codex, "prompt_mode")
    assert codex_command[-1] == "prompt"
    assert "sandbox_workspace_write.network_access=false" in codex_command
    assert 'web_search="disabled"' in codex_command
    assert all("{" not in part and "}" not in part for part in codex_command)
    assert codex.control_status_dict["maximum_output_tokens"] == "monitored-only"

    claude = PlatformAdapter.load(adapter_root / "claude_print.toml")
    assert claude.platform == "claude-code"
    claude_command = claude.build_command(
        model_id="model-test", prompt="prompt", runtime_values=values
    )
    assert not hasattr(claude, "prompt_mode")
    assert claude_command[-1] == "prompt"
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
    assert "complete final text itself" not in prompt


def test_every_codex_wrapper_uses_file_reference_and_no_install_metadata() -> None:
    runner = ExperimentRunner(_config(), output_root=Path("runs"))
    for condition in load_condition_registry().values():
        wrapper = tomllib.loads(condition.plugin_config.read_text(encoding="utf-8"))
        invocation = wrapper["invocation"]["codex"]

        assert "{codex_plugin_root}" in invocation
        assert "SKILL.md" in invocation
        assert "codex" not in wrapper["install"]
        # Only a condition without a draft scores its final response.
        final_text_rule = not condition.product_requires_draft
        assert ("complete final text itself" in invocation) is final_text_rule
        prompt = runner._plugin_prompt(condition, _prompt(), "codex")
        assert f"plugin/skills/{condition.skill_name}/SKILL.md" in prompt
        assert ("complete final text itself" in prompt) is final_text_rule
        if condition.condition_id in DELEGATING_CONDITIONS:
            assert DELEGATION_CONTRACT in prompt
        else:
            assert DELEGATION_CONTRACT not in prompt


def test_claude_code_wrappers_do_not_receive_codex_delegation_contract() -> None:
    for condition in load_condition_registry().values():
        prompt = ExperimentRunner(_config(), output_root=Path("runs"))._plugin_prompt(
            condition, _prompt(), "claude-code"
        )
        assert DELEGATION_CONTRACT not in prompt


CLAUDE_WORKSPACE_CONTRACT = (
    "## Workspace contract\n\n"
    "Create and update every `.writing/` file under the session working "
    "directory, never under the plugin or skill directory. The final response "
    "must contain the complete final text itself, not a summary or a link to a "
    "workspace artifact."
)
CLAUDE_WORKSPACE_CONTRACT_TEXT = CLAUDE_WORKSPACE_CONTRACT + "\n"


def test_composed_prompts_match_the_composed_prompt_snapshot() -> None:
    expected = json.loads(PROMPT_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    runner = ExperimentRunner(_config(), output_root=Path("runs"))
    conditions = load_condition_registry()

    actual = {
        platform: {
            condition_id: runner._plugin_prompt(
                conditions[condition_id], _prompt(), platform
            )
            for condition_id in conditions
        }
        for platform in PLATFORMS
    }

    assert actual == expected


def test_contract_files_preserve_the_existing_paragraph_bytes() -> None:
    expected = {
        "single_turn": SINGLE_TURN_CONTRACT_TEXT,
        "workspace": CLAUDE_WORKSPACE_CONTRACT_TEXT,
        "delegation": DELEGATION_CONTRACT_TEXT,
    }

    assert {
        name: (CONTRACTS_ROOT / f"{name}.md").read_text(encoding="utf-8")
        for name in expected
    } == expected


def test_wrappers_leave_shared_contracts_to_prompt_composition() -> None:
    shared_contracts = (
        SINGLE_TURN_CONTRACT,
        CLAUDE_WORKSPACE_CONTRACT,
        DELEGATION_CONTRACT,
    )
    for condition in load_condition_registry().values():
        wrapper = tomllib.loads(condition.plugin_config.read_text(encoding="utf-8"))
        for platform in ("codex", "claude_code"):
            invocation = wrapper["invocation"][platform]
            assert all(contract not in invocation for contract in shared_contracts)


def test_every_claude_code_invocation_anchors_workspace_and_final_text() -> None:
    runner = ExperimentRunner(_config(), output_root=Path("runs"))
    for condition in load_condition_registry().values():
        prompt = runner._plugin_prompt(condition, _prompt(), "claude-code")
        assert CLAUDE_WORKSPACE_CONTRACT in prompt
        assert "complete final text itself" in prompt
        assert "session working directory" in prompt


def test_every_condition_prompt_has_the_uniform_single_turn_contract() -> None:
    runner = ExperimentRunner(_config(), output_root=Path("runs"))
    for condition in load_condition_registry().values():
        for platform in ("codex", "claude-code"):
            prompt = runner._plugin_prompt(condition, _prompt(), platform)
            assert SINGLE_TURN_CONTRACT in prompt


@pytest.mark.parametrize(("language", "name"), [("en", "English"), ("zh", "Chinese")])
def test_every_condition_prompt_states_the_manifest_output_language_once(
    language: str, name: str
) -> None:
    row = {
        "prompt_id": "writingbench-0001",
        "benchmark_name": "WritingBench",
        "source_version": "test",
        "prompt_text": "Write a memo about Hangzhou tea.",
        "requested_output_constraints": {},
        "language": language,
    }
    prompt = PromptRecord.from_mapping({**row, "hash": sha256_json(row)})
    section = f"## Output language\nWrite the deliverable in {name}."
    runner = ExperimentRunner(_config(), output_root=Path("runs"))
    conditions = load_condition_registry()
    assert sorted(conditions) == [*(f"A{n}" for n in range(1, 9)), "B1", "B2"]
    for condition in conditions.values():
        for platform in PLATFORMS:
            composed = runner._plugin_prompt(condition, prompt, platform)
            assert composed.count("## Output language") == 1
            assert section in composed


def test_no_goal_skills_forbid_creating_or_modifying_the_goals_file() -> None:
    occurrences = 0
    for path in NO_GOAL_SKILL_PATHS:
        text = path.read_text(encoding="utf-8")
        occurrences += text.count(NO_GOAL_FILE_RULE)
        assert "Leave `.writing/goals.md` untouched" not in text
        assert "Leave `goals.md` untouched" not in text
    assert occurrences == 4


def test_agentic_cog_writer_ends_with_the_draft_as_the_final_document() -> None:
    text = (REPO_ROOT / "plugin/skills/agentic-cog-writer/SKILL.md").read_text(
        encoding="utf-8"
    )
    assert (
        "Stop when no further process is needed; the draft in `.writing/draft.md` "
        "is the final document."
    ) in text


def test_single_context_skill_is_the_monitor_skill_running_roles_in_context() -> None:
    def body(path: str) -> str:
        return (REPO_ROOT / path).read_text(encoding="utf-8").split("---\n", 2)[2]

    a8_root = REPO_ROOT / "experiments/plugin/skills/cognitive-writing-single-context"
    monitor, *roles = body(
        "experiments/plugin/skills/cognitive-writing-single-context/SKILL.md"
    ).split("\n\n## ")
    a4 = body("plugin/skills/agentic-cog-writer/SKILL.md").rstrip("\n").splitlines()
    changed = {
        (old, new)
        for old, new in zip(a4, monitor.splitlines(), strict=True)
        if old != new
    }

    assert {(old.split(" ")[0], new) for old, new in changed} == {
        (
            "Role:",
            "Role: the Monitor. It selects the next writing process from the state, "
            "runs it in its own context, and records its decisions; outside a "
            "process it writes nothing but `.writing/history.md`.",
        ),
        (
            "4.",
            "4. Run the process, with its scope, in your own context by following "
            "its role section below; do not spawn an agent. The Reviewing scope is "
            "this sentence and nothing more: check `.writing/draft.md` against "
            "`.writing/task.md` and the active goals, correct existing prose, and "
            "report what is needed next. The Planning scope is this sentence and "
            "nothing more: read `.writing/task.md`, `.writing/draft.md`, and "
            "`.writing/goals.md`, and create or develop the goals so that every "
            "requirement in the task has a goal.",
        ),
        (
            "5.",
            "5. When the Reviewer recommends replacing a goal, decide whether to "
            "accept it, record the decision in `.writing/history.md`, and run an "
            "accepted replacement as `Planning`; the `Monitor` edits "
            "`.writing/goals.md` only while running `Planning`.",
        ),
    }
    # The role sections are the role skills' bodies, verbatim.
    assert roles == [
        f"{role.capitalize()}\n{body(f'plugin/skills/{role}/SKILL.md')}".rstrip("\n")
        + ("\n" if role == "reviewing" else "")
        for role in ("planning", "translating", "reviewing")
    ]
    assert [path.name for path in a8_root.rglob("*")] == ["SKILL.md"]


def test_single_writer_skill_is_single_context_with_one_paragraph_steps() -> None:
    def text(path: str) -> list[str]:
        return (REPO_ROOT / path).read_text(encoding="utf-8").splitlines()

    a7_root = REPO_ROOT / "experiments/plugin/skills/cognitive-writing-single-writer"
    a8 = text("experiments/plugin/skills/cognitive-writing-single-context/SKILL.md")
    a7 = text("experiments/plugin/skills/cognitive-writing-single-writer/SKILL.md")
    changed = {(old, new) for old, new in zip(a8, a7, strict=True) if old != new}

    assert {(old.split(" ")[0], new) for old, new in changed} == {
        ("name:", "name: cognitive-writing-single-writer"),
        (
            "description:",
            'description: "Experiment-comparison variant of the agentic-cog-writer '
            "skill that runs each selected `Planning`, `Translating`, or `Reviewing` "
            "process in the Monitor's own context instead of a subagent and limits "
            "each `Translating` step to one paragraph. For internal comparison use "
            "only, not the recommended default. Use when a controlled single-writer "
            'comparison is explicitly requested."',
        ),
        (
            "Kinds",
            "Kinds of work: Planning changes the goals; Translating adds one "
            "paragraph of prose for the goals; Reviewing corrects existing prose and "
            "reports what is needed next. A role reports work of another kind "
            "instead of doing it.",
        ),
        (
            "Write",
            "Write one paragraph in `.writing/draft.md` within the delegated draft "
            "scope.",
        ),
        (
            "4.",
            "4. Run the process, with its scope, in your own context by following "
            "its role section below; do not spawn an agent. The Reviewing scope is "
            "this sentence and nothing more: check `.writing/draft.md` against "
            "`.writing/task.md` and the active goals, correct existing prose, and "
            "report what is needed next. The Planning scope is this sentence and "
            "nothing more: read `.writing/task.md`, `.writing/draft.md`, and "
            "`.writing/goals.md`, and create or develop the goals so that every "
            "requirement in the task has a goal. The Translating scope is one "
            "paragraph, a single block of prose; each further paragraph takes a new "
            "pass through steps 1 to 4.",
        ),
    }
    assert [path.name for path in a7_root.rglob("*")] == ["SKILL.md"]


def test_fixed_order_skill_is_the_monitor_skill_with_a_fixed_cycle() -> None:
    def body(path: str) -> list[str]:
        return (
            (REPO_ROOT / path)
            .read_text(encoding="utf-8")
            .split("---\n", 2)[2]
            .splitlines()
        )

    a4 = body("plugin/skills/agentic-cog-writer/SKILL.md")
    a6 = body("experiments/plugin/skills/cognitive-writing-fixed-order/SKILL.md")
    changed = {(old, new) for old, new in zip(a4, a6, strict=True) if old != new}

    assert {(old.split(" ")[0], new) for old, new in changed} == {
        (
            "Role:",
            "Role: the Monitor. It selects the next writing process from the fixed "
            "order, delegates it, and records its decisions; it writes nothing but "
            "`.writing/history.md`.",
        ),
        (
            "2.",
            "2. Take the next process in the fixed `Planning`, `Translating`, then "
            "`Reviewing` order; each pass starts again with `Planning`. Checking the "
            "draft against the task is Reviewing's work.",
        ),
        (
            "5.",
            "5. When the Reviewer recommends replacing a goal, decide whether to "
            "accept it, record the decision in `.writing/history.md`, and delegate an "
            "accepted replacement to the next pass's `Planning`; the `Monitor` does "
            "not edit `.writing/goals.md`.",
        ),
        (
            "Stop",
            "Stop only after `Reviewing`, when no further process is needed; the "
            "draft in `.writing/draft.md` is the final document.",
        ),
    }


def test_task_objective_skills_are_the_a4_skills_without_goal_wording() -> None:
    def changes(a4: str, a5: str) -> list[str]:
        lines = difflib.unified_diff(
            (REPO_ROOT / a4).read_text(encoding="utf-8").splitlines(),
            (REPO_ROOT / a5).read_text(encoding="utf-8").splitlines(),
            n=0,
            lineterm="",
        )
        return [
            line
            for line in lines
            if line[:1] in "+-" and line[:3] not in {"+++", "---"}
        ]

    skills = "experiments/plugin/skills"
    agents = "experiments/plugin/task-objective-agents"
    assert changes(
        "plugin/skills/agentic-cog-writer/SKILL.md",
        f"{skills}/cognitive-writing-task-objective/SKILL.md",
    ) == [
        "-name: agentic-cog-writer",
        '-description: "Use when the user asks to write or draft a complete document '
        "end to end with Agentic CogWriter. Acts as the Monitor: delegates Planning, "
        "Translating, and Reviewing to subagents until the draft is final. Do not "
        "use inside a delegated Planner, Translator, or Reviewer task, or to edit a "
        'single passage."',
        "+name: cognitive-writing-task-objective",
        '+description: "Experiment-comparison variant of the agentic-cog-writer '
        "skill in which the task is the single implicit objective of every writing "
        "process. For internal comparison use only, not the recommended default. Use "
        'when a controlled task-objective comparison is explicitly requested."',
        "-State: the task in `.writing/task.md`, the draft in `.writing/draft.md` "
        "(the task may provide one), the goals in `.writing/goals.md`, and the "
        "history in `.writing/history.md`.",
        "+State: the task in `.writing/task.md`, the draft in `.writing/draft.md` "
        "(the task may provide one), and the history in `.writing/history.md`.",
        "-Kinds of work: Planning changes the goals; Translating adds prose for the "
        "goals; Reviewing corrects existing prose and reports what is needed next. A "
        "role reports work of another kind instead of doing it.",
        "+Kinds of work: Planning organizes the relevant material and reports it; "
        "Translating adds prose for the task's requirements; Reviewing corrects "
        "existing prose and reports what is needed next. A role reports work of "
        "another kind instead of doing it.",
        "-1. Read the four state files; a missing file counts as empty.",
        "-2. Choose the process from the kind of work the state calls for; a section "
        "without a goal needs Planning first. The Monitor reads the draft to choose; "
        "checking it against the task is Reviewing's work.",
        "+1. Read the three state files; a missing file counts as empty.",
        "+2. Choose the process from the kind of work the state calls for. The "
        "Monitor reads the draft to choose; checking it against the task is "
        "Reviewing's work.",
        "-4. Delegate the process, with its scope, to a fresh planning, translating, "
        "or reviewing agent, and wait for it. The Reviewing scope is this sentence "
        "and nothing more: check `.writing/draft.md` against `.writing/task.md` and "
        "the active goals, correct existing prose, and report what is needed next. "
        "The Planning scope is this sentence and nothing more: read "
        "`.writing/task.md`, `.writing/draft.md`, and `.writing/goals.md`, and "
        "create or develop the goals so that every requirement in the task has a "
        "goal.",
        "-5. When the Reviewer recommends replacing a goal, decide whether to accept "
        "it, record the decision in `.writing/history.md`, and delegate an accepted "
        "replacement to `Planning`; the `Monitor` does not edit `.writing/goals.md`.",
        "+4. Delegate the process, with its scope, to a fresh planning, translating, "
        "or reviewing agent, and wait for it. The Reviewing scope is this sentence "
        "and nothing more: check `.writing/draft.md` against `.writing/task.md`, "
        "correct existing prose, and report what is needed next. The Planning scope "
        "is this sentence and nothing more: read `.writing/task.md` and "
        "`.writing/draft.md`, organize the relevant material for the intended "
        "audience, and report the organization.",
        "+5. For Translating, once a Planner has reported an organization, end the "
        "step-3 line with a one-line summary of the most recent one, and append that "
        "organization, as reported, after the Translating scope in the delegation "
        "message.",
    ]
    assert changes(
        "plugin/skills/planning/SKILL.md", f"{skills}/task-objective-planning/SKILL.md"
    ) == [
        '-description: "Planner role of Agentic CogWriter. Creates or develops the '
        'writing goals."',
        '+description: "Planner role of Agentic CogWriter. Organizes the relevant '
        'material and reports the organization."',
        "-Role: the Planner. Planning changes the goals, not the prose.",
        "-Read `.writing/task.md`, `.writing/draft.md`, and `.writing/goals.md`.",
        "-Organize the relevant material for the intended audience, and create or "
        "develop the writing goals as a hierarchy in `.writing/goals.md`, within the "
        "delegated scope. When a goal conflicts with `.writing/task.md`, the task "
        "governs: replace the goal.",
        "+Role: the Planner. Planning organizes the material, not the prose; it "
        "writes no file.",
        "+Read `.writing/task.md` and `.writing/draft.md`.",
        "+Organize the relevant material for the intended audience and report the "
        "organization, within the delegated scope.",
    ]
    assert changes(
        "plugin/skills/translating/SKILL.md",
        f"{skills}/task-objective-translating/SKILL.md",
    ) == [
        '-description: "Translator role of Agentic CogWriter. Writes prose for the '
        'goals within the delegated draft scope."',
        '+description: "Translator role of Agentic CogWriter. Writes prose for the '
        "task's requirements within the delegated draft scope.\"",
        "-Role: the Translator. Translating adds prose for the goals; a section with "
        "no goal is reported, not written.",
        "-Read `.writing/task.md`, `.writing/draft.md`, and the active goals in "
        "`.writing/goals.md`.",
        "+Role: the Translator. Translating adds prose for the task's requirements; "
        "a section that no task requirement calls for is reported, not written.",
        "+Read `.writing/task.md` and `.writing/draft.md`.",
    ]
    assert changes(
        "plugin/skills/reviewing/SKILL.md",
        f"{skills}/task-objective-reviewing/SKILL.md",
    ) == [
        "-Role: the Reviewer. Reviewing corrects existing prose; a missing goal or a "
        "missing section is reported, not written. Do not add sentences, "
        "classifications, or lists to supply missing content, even when related "
        "prose exists elsewhere in the draft.",
        "-First, for each requirement in `.writing/task.md`, name the goal in "
        "`.writing/goals.md` that covers it; a goal covers a requirement only if it "
        "names that requirement's section, and a requirement with no such goal is "
        "reported for planning.",
        "-Check `.writing/draft.md` against `.writing/task.md` and the active goals "
        "in `.writing/goals.md`.",
        "+Role: the Reviewer. Reviewing corrects existing prose; a missing section "
        "is reported, not written. Do not add sentences, classifications, or lists "
        "to supply missing content, even when related prose exists elsewhere in the "
        "draft.",
        "+First, for each requirement in `.writing/task.md`, name the section of "
        "`.writing/draft.md` that covers it; a requirement with no such section is "
        "reported for drafting.",
        "+Check `.writing/draft.md` against `.writing/task.md`.",
        "-Report whether further planning, drafting, or review is needed: planning "
        "when a task requirement has no goal in `.writing/goals.md`, drafting when a "
        "goal has no prose yet, review when prose remains to check, and none when "
        "the draft meets the task and goals; you may also recommend replacing a goal.",
        "+Report whether further planning, drafting, or review is needed: planning "
        "when the material for a task requirement needs organizing, drafting when a "
        "task requirement has no prose yet, review when prose remains to check, and "
        "none when the draft meets the task.",
    ]
    assert changes("plugin/codex/agents/planning.toml", f"{agents}/planning.toml") == [
        '-description = "Spawn when the Agentic CogWriter Monitor needs writing '
        'goals created or developed. Runs $planning; does not draft or review prose."',
        '+description = "Spawn when the Agentic CogWriter Monitor needs the relevant '
        'material organized. Runs $planning; does not draft or review prose."',
    ]
    assert changes(
        "plugin/codex/agents/translating.toml", f"{agents}/translating.toml"
    ) == [
        '-description = "Spawn when the Monitor has goals and needs draft prose for '
        'a delegated scope. Runs $translating; does not set goals or review."',
        "+description = \"Spawn when the Monitor needs draft prose for the task's "
        "requirements within a delegated scope. Runs $translating; does not organize "
        'material or review."',
    ]
    assert changes(
        "plugin/codex/agents/reviewing.toml", f"{agents}/reviewing.toml"
    ) == [
        '-description = "Spawn when a draft exists and the Monitor needs it checked '
        "and revised within a delegated scope. Runs $reviewing; does not set goals "
        'or draft new sections."',
        '+description = "Spawn when a draft exists and the Monitor needs it checked '
        "and revised within a delegated scope. Runs $reviewing; does not organize "
        'material or draft new sections."',
    ]
    # The model reads every A5 skill, front matter included, and agent definition.
    a5_files = [
        *(
            REPO_ROOT / skills / name / "SKILL.md"
            for name in (
                "cognitive-writing-task-objective",
                "task-objective-planning",
                "task-objective-translating",
                "task-objective-reviewing",
            )
        ),
        *sorted((REPO_ROOT / agents).iterdir()),
    ]
    assert [path.name for path in a5_files[4:]] == [
        "planning.toml",
        "reviewing.toml",
        "translating.toml",
    ]
    for path in a5_files:
        assert "goal" not in path.read_text(encoding="utf-8").lower(), path
    for path in a5_files[:4]:
        assert [child.name for child in path.parent.rglob("*")] == ["SKILL.md"]


@pytest.mark.parametrize(
    ("condition_id", "stage_count", "first_heading", "expected_header"),
    (
        ("A1", 1, "## A1 single-shot", SINGLE_STAGE_SESSION_HEADER),
        ("A2", 3, "## A2 Pre-Write", STAGE_SESSION_HEADER.format(count=3)),
        (
            "B2",
            5,
            "## A3 perspective discovery",
            STAGE_SESSION_HEADER.format(count=5),
        ),
    ),
)
def test_composed_prompt_identifies_the_single_session_stage_chain(
    condition_id: str,
    stage_count: int,
    first_heading: str,
    expected_header: str,
) -> None:
    runner = ExperimentRunner(_config(), output_root=Path("runs"))
    prompt = runner._plugin_prompt(
        load_condition_registry()[condition_id], _prompt(), "codex"
    )
    assert prompt.count(expected_header) == 1
    assert prompt.index(expected_header) < prompt.index(first_heading)
    if stage_count == 1:
        assert STAGE_SESSION_HEADER.format(count=1) not in prompt


def test_composed_prompt_omits_the_stage_chain_header_without_frozen_paths() -> None:
    runner = ExperimentRunner(_config(), output_root=Path("runs"))
    prompt = runner._plugin_prompt(load_condition_registry()["A4"], _prompt(), "codex")

    assert "frozen stages run in order within this single session" not in prompt


@pytest.mark.parametrize(
    "condition_id",
    ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "B1", "B2"),
)
@pytest.mark.parametrize("platform", PLATFORMS)
def test_composed_prompt_has_one_rendered_shared_input_block(
    condition_id: str, platform: str
) -> None:
    runner = ExperimentRunner(_config(), output_root=Path("runs"))
    condition = load_condition_registry()[condition_id]
    prompt = runner._plugin_prompt(condition, _prompt(), platform)

    assert prompt.count("Write a memo.") == 1
    assert prompt.count("Provided facts only.") == 1
    assert prompt.count("{}") == 1
    assert prompt.count("Assignment\n") == 1
    assert prompt.count("Supplied context\n") == 1
    assert prompt.count("Requested output constraints\n") == 1
    assert "{{" not in prompt
    assert "}}" not in prompt


FROZEN_STAGE_HEADINGS = {
    "A1": [
        "## A1 single-shot",
        "### Assignment",
        "### Supplied context",
        "### Requested output constraints",
    ],
    "A2": [
        "## A2 Pre-Write",
        "### Assignment",
        "### Supplied context",
        "### Requested output constraints",
        "### Previous stage output",
        "## A2 Write",
        "### Pre-Write output",
        "## A2 Re-Write",
        "### Draft to revise",
    ],
    "B2": [
        "## A3 perspective discovery",
        "### Assignment",
        "### Supplied context",
        "### Requested output constraints",
        "## A3 simulated question answering",
        "### Discovered perspectives",
        "## A3 outline",
        "### Prior planning output",
        "## A3 draft",
        "### Outline",
        "## A3 polish",
        "### Draft",
    ],
}


def test_composed_prompt_uses_ordered_headings_without_label_lines() -> None:
    runner = ExperimentRunner(_config(), output_root=Path("runs"))
    conditions = load_condition_registry()

    for condition_id, condition in conditions.items():
        for platform in PLATFORMS:
            prompt = runner._plugin_prompt(condition, _prompt(), platform)
            headings = re.findall(r"(?m)^#{2,3} .+$", prompt)
            expected = (
                (["## Workspace contract"] if platform == "claude-code" else [])
                + ["## Single-turn contract"]
                + (
                    ["## Delegation contract"]
                    if platform == "codex" and condition.require_delegation
                    else []
                )
                + (
                    ["## Output language", *FROZEN_STAGE_HEADINGS[condition_id]]
                    if condition_id in FROZEN_STAGE_HEADINGS
                    else [
                        "## Assignment",
                        "## Supplied context",
                        "## Requested output constraints",
                        "## Output language",
                    ]
                )
            )

            assert not re.search(r"(?m)^[A-Z][A-Za-z -]+:$", prompt)
            assert headings == expected
            assert sum(heading.endswith("Assignment") for heading in headings) == 1


def test_composed_prompt_rejects_unknown_stage_token_before_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    condition = load_condition_registry()["A1"]
    stage_path = tmp_path / "unknown-token-stage.md"
    content = "Unknown value: {{unknown_token}}\n"
    stage_path.write_text(content, encoding="utf-8")
    stage = replace(
        condition.stages[0],
        path=stage_path,
        sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
    )
    condition = replace(condition, stages=(stage,))
    executor = _RetryExecutor([_result()])
    runner = _runner(
        tmp_path / "runs",
        condition_registry={"A1": condition},
        executor=executor,
    )
    monkeypatch.setattr(
        runner,
        "_probe_cli",
        lambda _adapter: pytest.fail("unknown tokens must fail before CLI probing"),
    )

    with pytest.raises(
        ConfigurationError,
        match=r"(?=.*unknown-token-stage\.md)(?=.*unknown_token)",
    ):
        runner.run_prompt(_prompt(), condition_id="A1", platform="codex")

    assert executor.calls == []


def test_tampered_stage_file_still_fails_hash_check_before_execution(
    tmp_path: Path,
) -> None:
    condition = load_condition_registry()["A1"]
    stage_path = tmp_path / "tampered-stage.md"
    assert condition.stages[0].path is not None
    stage_path.write_bytes(condition.stages[0].path.read_bytes() + b"tampered\n")
    stage = replace(condition.stages[0], path=stage_path)
    condition = replace(condition, stages=(stage,))
    executor = _RetryExecutor([_result()])
    runner = _runner(
        tmp_path / "runs",
        condition_registry={"A1": condition},
        executor=executor,
    )

    with pytest.raises(ManifestError, match="Frozen prompt hash mismatch"):
        runner.run_prompt(_prompt(), condition_id="A1", platform="codex")

    assert executor.calls == []


def test_codex_stages_skill_references_roles_and_hashes(tmp_path: Path) -> None:
    source_root = tmp_path / "plugin-source"
    files = {
        "skills/agentic-cog-writer/SKILL.md": "main skill\n",
        "skills/agentic-cog-writer/references/trace.md": "trace reference\n",
        "skills/planning/SKILL.md": "planning role\n",
        "skills/translating/SKILL.md": "translating role\n",
        "skills/reviewing/SKILL.md": "reviewing role\n",
    }
    adapter_files = {
        "agents/planning.toml": 'name = "planning"\n',
        "agents/translating.toml": 'name = "translating"\n',
        "agents/reviewing.toml": 'name = "reviewing"\n',
        "rules/deny.rules": 'prefix_rule(pattern=["git"], decision="forbidden")\n',
        "config.toml": 'developer_instructions = "Delegate."\n',
    }
    for relative, content in (
        *files.items(),
        *((f"codex/{name}", text) for name, text in adapter_files.items()),
    ):
        path = source_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    codex_source = tmp_path / "codex-home"
    codex_source.mkdir()
    (codex_source / "config.toml").write_text(
        'model_provider = "p"\n\n[model_providers.p]\nname = "p"\n'
    )
    observed_homes: list[dict[str, str]] = []
    observed_configs: list[dict[str, object]] = []

    class StageExecutor:
        def run(self, command, *, cwd, timeout_seconds, env=None):
            home = Path(env["CODEX_HOME"])
            observed_homes.append(
                {
                    path.relative_to(home).as_posix(): path.read_text()
                    for path in home.rglob("*")
                    if path.is_file()
                }
            )
            observed_configs.append(tomllib.loads((home / "config.toml").read_text()))
            (cwd / ".writing" / "draft.md").write_text("final output " * 10)
            result = _result(subagent_spawns=1)
            rollout = Path(env["CODEX_HOME"]) / "sessions" / "attempt.jsonl"
            rollout.parent.mkdir(parents=True, exist_ok=True)
            rollout.write_bytes(result.stdout)
            return result

    runner = ExperimentRunner(
        _config(),
        output_root=tmp_path / "runs",
        executor=StageExecutor(),
        codex_plugin_root=source_root,
        codex_home=codex_source,
    )

    result = runner.run_prompt(
        _prompt(), condition_id="A4", platform="codex", run_id="staged"
    )

    expected_home = {
        **files,
        **{name: text for name, text in adapter_files.items() if "/" in name},
    }
    [home] = observed_homes
    assert {
        name: text for name, text in home.items() if name != "config.toml"
    } == expected_home
    assert observed_configs == [
        {
            "developer_instructions": "Delegate.",
            "model_provider": "p",
            "model_reasoning_effort": "xhigh",
            "model_providers": {"p": {"name": "p"}},
        }
    ]
    manifest = json.loads(result.manifest_path.read_text())
    # A4 needs no plugin trace: the run reaches the fidelity gate without one.
    assert "failure" not in manifest
    assert "trace_hash" not in manifest
    assert "fidelity_gate" in manifest
    staged_files = manifest["staged_files"]
    task = (result.run_dir / "workspace" / ".writing" / "task.md").read_text()
    assert task == (
        "## Assignment\nWrite a memo.\n\n"
        "## Supplied context\nProvided facts only.\n\n"
        "## Requested output constraints\n{}\n\n"
        "## Output language\nWrite the deliverable in English.\n"
    )
    assert set(staged_files) == {
        *(f"plugin/{relative}" for relative in files),
        *(f"CODEX_HOME/{relative}" for relative in (*expected_home, "config.toml")),
        ".writing/task.md",
        ".writing/history.md",
    }
    assert (result.run_dir / "workspace" / ".writing" / "history.md").read_text() == ""
    assert staged_files["CODEX_HOME/config.toml"] == (
        "sha256:" + hashlib.sha256(home["config.toml"].encode()).hexdigest()
    )
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


@pytest.mark.parametrize(
    ("condition_id", "skill_name"),
    (
        ("A4", "agentic-cog-writer"),
        ("A5", "cognitive-writing-task-objective"),
        ("A6", "cognitive-writing-fixed-order"),
    ),
)
def test_monitor_conditions_install_the_repository_plugin_codex_adapter(
    tmp_path: Path, condition_id: str, skill_name: str
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    runner = ExperimentRunner(_config(), output_root=tmp_path / "runs")

    runner._stage_codex_plugin(
        load_condition_registry()[condition_id],
        tmp_path / "workspace",
        codex_home=home,
        prompt=_prompt(),
    )

    roles = ("planning", "translating", "reviewing")
    assert sorted(path.name for path in (home / "skills").iterdir()) == sorted(
        (skill_name, *roles)
    )
    assert all(
        (home / "skills" / name / "SKILL.md").is_file() for name in (skill_name, *roles)
    )
    # A5 and A6 stage the same layout as A4; A5 stages its own role copies.
    assert [path.name for path in (home / "skills" / skill_name).rglob("*")] == [
        "SKILL.md"
    ]
    role_root = (
        "experiments/plugin/skills/task-objective-"
        if condition_id == "A5"
        else ("plugin/skills/")
    )
    for role in roles:
        assert (home / "skills" / role / "SKILL.md").read_bytes() == (
            REPO_ROOT / f"{role_root}{role}/SKILL.md"
        ).read_bytes()
    assert sorted(path.name for path in (home / "agents").iterdir()) == sorted(
        f"{role}.toml" for role in roles
    )
    agents_root = (
        "experiments/plugin/task-objective-agents/"
        if condition_id == "A5"
        else "plugin/codex/agents/"
    )
    for role in roles:
        assert (home / "agents" / f"{role}.toml").read_bytes() == (
            REPO_ROOT / f"{agents_root}{role}.toml"
        ).read_bytes()
    assert [path.name for path in (home / "rules").iterdir()] == ["deny.rules"]
    assert "developer_instructions" in tomllib.loads((home / "config.toml").read_text())


@pytest.mark.parametrize(
    ("condition_id", "skill_name"),
    [
        ("A7", "cognitive-writing-single-writer"),
        ("A8", "cognitive-writing-single-context"),
    ],
)
def test_in_context_conditions_install_the_adapter_rules_without_delegation(
    tmp_path: Path, condition_id: str, skill_name: str
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.toml").write_text('model_reasoning_effort = "medium"\n')
    runner = ExperimentRunner(_config(), output_root=tmp_path / "runs")

    staged = runner._stage_codex_plugin(
        load_condition_registry()[condition_id],
        tmp_path / "workspace",
        codex_home=home,
        prompt=_prompt(),
    )

    skill = home / "skills" / skill_name
    assert sorted(path.name for path in home.iterdir()) == [
        "config.toml",
        "rules",
        "skills",
    ]
    assert [path.name for path in (home / "skills").iterdir()] == [skill.name]
    assert [path.name for path in skill.rglob("*")] == ["SKILL.md"]
    assert [path.name for path in (home / "rules").iterdir()] == ["deny.rules"]
    assert (home / "config.toml").read_text() == 'model_reasoning_effort = "medium"\n'
    assert ".writing/task.md" in staged


def test_codex_adapter_config_conflicting_with_runner_settings_is_rejected(
    tmp_path: Path,
) -> None:
    adapter = tmp_path / "plugin" / "codex"
    for relative in ("agents", "rules"):
        (adapter / relative).mkdir(parents=True)
    (adapter / "config.toml").write_text('model_reasoning_effort = "low"\n')
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.toml").write_text('model_reasoning_effort = "medium"\n')

    with pytest.raises(ConfigurationError, match="conflicts"):
        ExperimentRunner._install_codex_adapter(adapter, {}, home, delegated=True)
    assert (home / "config.toml").read_text() == 'model_reasoning_effort = "medium"\n'


def test_codex_stages_split_plugin_roots_with_explicit_experiment_root(
    tmp_path: Path,
) -> None:
    main_root = tmp_path / "main-plugin"
    experiment_root = tmp_path / "experiment-plugin"
    for skill in (
        "agentic-cog-writer",
        "planning",
        "translating",
        "reviewing",
    ):
        shutil.copytree(
            Path("plugin/skills") / skill,
            main_root / "skills" / skill,
        )
    shutil.copytree(
        Path("experiments/plugin/skills/cognitive-writing-fixed-order"),
        experiment_root / "skills" / "cognitive-writing-fixed-order",
    )
    wrapper_path = tmp_path / "a6-wrapper.toml"
    wrapper_path.write_text(
        "[plugins]\n"
        f"paths = [{json.dumps(str(main_root))}, {json.dumps(str(experiment_root))}]\n"
    )
    condition = replace(load_condition_registry()["A6"], plugin_config=wrapper_path)
    runner = ExperimentRunner(
        _config(),
        output_root=tmp_path / "runs",
        codex_plugin_root=experiment_root,
        codex_home=tmp_path / "codex-home",
    )

    staged_files = runner._stage_codex_plugin(condition, tmp_path / "workspace")

    assert set(staged_files) == {
        "plugin/skills/cognitive-writing-fixed-order/SKILL.md",
        "plugin/skills/planning/SKILL.md",
        "plugin/skills/reviewing/SKILL.md",
        "plugin/skills/translating/SKILL.md",
    }


def test_codex_explicit_root_must_contain_invoked_skill_before_execution(
    tmp_path: Path,
) -> None:
    explicit_root = tmp_path / "empty-plugin"
    explicit_root.mkdir()
    executor = _RetryExecutor([_result()])
    runner = ExperimentRunner(
        _config(),
        output_root=tmp_path / "runs",
        executor=executor,
        codex_plugin_root=explicit_root,
        codex_home=tmp_path / "codex-home",
    )

    with pytest.raises(ConfigurationError, match="Explicit Codex plugin root"):
        runner.run_prompt(
            _prompt(), condition_id="A4", platform="codex", run_id="missing-skill"
        )

    assert executor.calls == []


def test_run_records_unique_codex_subagent_spawns(tmp_path: Path) -> None:
    class SpawnRolloutExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds, env=None):
            result = super().run(
                command, cwd=cwd, timeout_seconds=timeout_seconds, env=env
            )
            rollout = Path(env["CODEX_HOME"]) / "sessions" / "attempt.jsonl"
            rollout.parent.mkdir(parents=True, exist_ok=True)
            rollout.write_bytes(result.stdout)
            return result

    executor = SpawnRolloutExecutor([_result(subagent_spawns=2)])
    condition = replace(load_condition_registry()["A1"], require_delegation=True)
    runner = _runner(
        tmp_path,
        condition_registry={"A1": condition},
        executor=executor,
    )

    result = runner.run_prompt(_prompt(), condition_id="A1", platform="codex")

    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["subagent_spawn_count"] == 2
    assert manifest["delegation_check"] == {
        "required": True,
        "spawn_count": 2,
        "execution_mode": "delegated",
        "passed": True,
    }


def test_a8_rejects_in_context_execution_with_spawn_event(tmp_path: Path) -> None:
    class SpawnRolloutExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds, env=None):
            result = super().run(
                command, cwd=cwd, timeout_seconds=timeout_seconds, env=env
            )
            rollout = Path(env["CODEX_HOME"]) / "sessions" / "attempt.jsonl"
            rollout.parent.mkdir(parents=True, exist_ok=True)
            rollout.write_bytes(result.stdout)
            return result

    runner = _runner(
        tmp_path,
        executor=SpawnRolloutExecutor([_result(subagent_spawns=1)]),
    )

    with pytest.raises(
        ExecutionError,
        match="Condition A8 requires in-context execution; 1 spawn_agent event",
    ):
        runner.run_prompt(_prompt(), condition_id="A8", platform="codex")

    run_dir = tmp_path / "WritingBench" / "A8" / "codex"
    manifest = json.loads(
        next(run_dir.iterdir()).joinpath("run-manifest.json").read_text()
    )
    assert manifest["delegation_check"] == {
        "required": False,
        "spawn_count": 1,
        "execution_mode": "in_context",
        "passed": False,
    }


def test_a8_accepts_in_context_execution_without_spawn_event(tmp_path: Path) -> None:
    runner = _runner(tmp_path, executor=_RetryExecutor([_result()]))

    result = runner.run_prompt(_prompt(), condition_id="A8", platform="codex")

    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["status"] == "unscored"
    assert manifest["scoring"] == {"status": "excluded"}
    assert manifest["fidelity_gate"] == {
        "status": "rejected",
        "reasons": ["Codex event stream has no thread.started event"],
    }
    assert manifest["subagent_spawn_count"] == 0
    assert manifest["delegation_check"] == {
        "required": False,
        "spawn_count": 0,
        "execution_mode": "in_context",
        "passed": True,
    }


@pytest.mark.parametrize(
    ("output", "units", "dominant", "mismatch"),
    [
        ("final output " * 10, (20, 0), "LATIN", False),
        ("最终输出" * 10, (0, 40), "CJK", True),
    ],
)
def test_codex_run_with_complete_clean_records_stays_scoring_eligible(
    tmp_path: Path,
    output: str,
    units: tuple[int, int],
    dominant: str,
    mismatch: bool,
) -> None:
    class RecordedExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds, env=None):
            rollout = Path(env["CODEX_HOME"]) / "sessions" / "rollout-session-1.jsonl"
            rollout.parent.mkdir(parents=True)
            rollout.write_text(
                json.dumps({"type": "session_meta", "payload": {"id": "session-1"}})
                + "\n"
            )
            return super().run(
                command, cwd=cwd, timeout_seconds=timeout_seconds, env=env
            )

    result = _result(output=output)
    started = json.dumps({"type": "thread.started", "thread_id": "session-1"})
    result = replace(result, stdout=f"{started}\n".encode() + result.stdout)
    runner = _runner(
        tmp_path / "runs",
        executor=RecordedExecutor([result]),
        codex_home=tmp_path / "codex-home",
    )

    run = runner.run_prompt(_prompt(), condition_id="A1", platform="codex")

    manifest = json.loads(run.manifest_path.read_text())
    assert manifest["fidelity_gate"] == {"status": "scorable", "reasons": []}
    assert manifest["status"] == "completed"
    assert manifest["scoring"] == {"status": "eligible"}
    # A language mismatch is recorded for the fidelity report, never rejected.
    assert manifest["output_language"] == {
        "expected_language": "en",
        "expected_script": "LATIN",
        "latin_words": units[0],
        "cjk_characters": units[1],
        "dominant_script": dominant,
        "dominant_share": 1.0,
        "mismatch": mismatch,
    }


def test_required_delegation_fails_closed_without_spawn_event(tmp_path: Path) -> None:
    condition = replace(load_condition_registry()["A1"], require_delegation=True)
    runner = _runner(
        tmp_path,
        condition_registry={"A1": condition},
        executor=_RetryExecutor([_result()]),
    )

    with pytest.raises(
        ExecutionError,
        match=(
            "Condition A1 requires native role delegation; no spawn_agent event "
            "was observed"
        ),
    ):
        runner.run_prompt(_prompt(), condition_id="A1", platform="codex")

    manifest = json.loads(
        (
            tmp_path
            / "WritingBench"
            / "A1"
            / "codex"
            / next((tmp_path / "WritingBench" / "A1" / "codex").iterdir()).name
            / "run-manifest.json"
        ).read_text()
    )
    assert manifest["delegation_check"] == {
        "required": True,
        "spawn_count": 0,
        "execution_mode": "delegated",
        "passed": False,
    }


def test_required_delegation_passes_with_spawn_events(tmp_path: Path) -> None:
    class SpawnRolloutExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds, env=None):
            result = super().run(
                command, cwd=cwd, timeout_seconds=timeout_seconds, env=env
            )
            rollout = Path(env["CODEX_HOME"]) / "sessions" / "attempt.jsonl"
            rollout.parent.mkdir(parents=True, exist_ok=True)
            rollout.write_bytes(result.stdout)
            return result

    condition = replace(load_condition_registry()["A1"], require_delegation=True)
    runner = _runner(
        tmp_path,
        condition_registry={"A1": condition},
        executor=SpawnRolloutExecutor([_result(subagent_spawns=2)]),
    )

    result = runner.run_prompt(_prompt(), condition_id="A1", platform="codex")

    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["delegation_check"] == {
        "required": True,
        "spawn_count": 2,
        "execution_mode": "delegated",
        "passed": True,
    }


def test_failed_spawn_event_fails_required_delegation(tmp_path: Path) -> None:
    class SpawnRolloutExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds, env=None):
            result = super().run(
                command, cwd=cwd, timeout_seconds=timeout_seconds, env=env
            )
            rollout = Path(env["CODEX_HOME"]) / "sessions" / "attempt.jsonl"
            rollout.parent.mkdir(parents=True, exist_ok=True)
            rollout.write_bytes(result.stdout)
            return result

    condition = replace(load_condition_registry()["A1"], require_delegation=True)
    runner = _runner(
        tmp_path,
        condition_registry={"A1": condition},
        executor=SpawnRolloutExecutor(
            [_result(subagent_spawns=1, spawn_status="failed")]
        ),
    )

    with pytest.raises(
        ExecutionError,
        match=(
            "Condition A1 requires native role delegation; no spawn_agent event "
            "was observed"
        ),
    ):
        runner.run_prompt(_prompt(), condition_id="A1", platform="codex")

    run_dir = tmp_path / "WritingBench" / "A1" / "codex"
    manifest = json.loads(
        next(run_dir.iterdir()).joinpath("run-manifest.json").read_text()
    )
    assert manifest["delegation_check"] == {
        "required": True,
        "spawn_count": 0,
        "execution_mode": "delegated",
        "passed": False,
    }


def test_extract_subagent_spawn_count_ignores_failed_completed_spawn() -> None:
    stream = (
        b'{"type":"item.completed","item":{"id":"collab-1",'
        b'"type":"collab_tool_call","tool":"spawn_agent",'
        b'"status":"failed","receiver_thread_ids":[]}}\n'
    )

    assert extract_subagent_spawn_count(stream) == 0


def test_extract_subagent_spawn_count_ignores_in_progress_spawn() -> None:
    stream = (
        b'{"type":"item.started","item":{"id":"collab-1",'
        b'"type":"collab_tool_call","tool":"spawn_agent",'
        b'"status":"in_progress","receiver_thread_ids":["thread-1"]}}\n'
        b'{"type":"item.updated","item":{"id":"collab-1",'
        b'"type":"collab_tool_call","tool":"spawn_agent",'
        b'"status":"in_progress","receiver_thread_ids":["thread-1"]}}\n'
    )

    assert extract_subagent_spawn_count(stream) == 0


def test_extract_subagent_spawn_count_accepts_completed_spawn_with_receiver() -> None:
    stream = (
        b'{"type":"item.started","item":{"id":"collab-1",'
        b'"type":"collab_tool_call","tool":"spawn_agent",'
        b'"status":"in_progress","receiver_thread_ids":[]}}\n'
        b'{"type":"item.completed","item":{"id":"collab-1",'
        b'"type":"collab_tool_call","tool":"spawn_agent",'
        b'"status":"completed","receiver_thread_ids":["thread-1"]}}\n'
    )

    assert extract_subagent_spawn_count(stream) == 1
    assert extract_subagent_spawn_count(b'{"type":"item.completed"}\n') == 0


def test_collects_only_new_or_changed_codex_rollouts_under_run_dir(
    tmp_path: Path,
) -> None:
    codex_home = tmp_path / "codex-home"

    class RolloutExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds, env=None):
            run_sessions = Path(env["CODEX_HOME"]) / "sessions"
            run_changed = run_sessions / "changed.jsonl"
            run_created = run_sessions / "2026" / "new.jsonl"
            run_changed.parent.mkdir(parents=True)
            run_changed.write_text("after")
            run_created.parent.mkdir(parents=True)
            run_created.write_text("created during attempt")
            return super().run(
                command, cwd=cwd, timeout_seconds=timeout_seconds, env=env
            )

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
    manifest = json.loads(result.manifest_path.read_text())
    evidence_hashes = manifest["evidence_hashes"]
    assert evidence_hashes["sessions/attempt-001/changed.jsonl"] == (
        "sha256:" + hashlib.sha256(b"after").hexdigest()
    )
    assert evidence_hashes["sessions/attempt-001/2026/new.jsonl"] == (
        "sha256:" + hashlib.sha256(b"created during attempt").hexdigest()
    )
    assert not (result.run_dir / "checksums.json").exists()


def test_rollout_status_remains_complete_across_retry_without_new_files(
    tmp_path: Path,
) -> None:
    codex_home = tmp_path / "codex-home"

    class FirstAttemptRolloutExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds, env=None):
            result = super().run(
                command, cwd=cwd, timeout_seconds=timeout_seconds, env=env
            )
            if len(self.calls) == 1:
                rollout = Path(env["CODEX_HOME"]) / "sessions" / "attempt.jsonl"
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


def test_trace_validation_skips_leading_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "process.jsonl"
    event = _event()
    path.write_text("\n  \n" + json.dumps(event) + "\n")

    assert validate_trace(
        path,
        condition_id="A1",
        declared_processes=WRITING_TRACE_PROCESSES,
        goal_events="forbidden",
        allowed_event_types=("process_switch",),
    ) == [event]


def test_trace_validation_skips_interior_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "process.jsonl"
    events = [_event(process="planning"), _event(process="generate")]
    path.write_text(json.dumps(events[0]) + "\n\n\t\n" + json.dumps(events[1]) + "\n")

    assert (
        validate_trace(
            path,
            condition_id="A1",
            declared_processes=WRITING_TRACE_PROCESSES,
            goal_events="forbidden",
            allowed_event_types=("process_switch",),
            min_events=2,
        )
        == events
    )


def test_trace_validation_rejects_trace_containing_only_blank_lines(
    tmp_path: Path,
) -> None:
    path = tmp_path / "process.jsonl"
    path.write_text("\n  \t\n")

    with pytest.raises(TraceValidationError, match=r"Trace .* is empty"):
        validate_trace(
            path,
            condition_id="A1",
            declared_processes=WRITING_TRACE_PROCESSES,
            goal_events="forbidden",
            allowed_event_types=("process_switch",),
        )


def test_trace_validation_reports_malformed_line_physical_line_number(
    tmp_path: Path,
) -> None:
    path = tmp_path / "process.jsonl"
    path.write_text(json.dumps(_event()) + "\n\nnot-json\n")

    with pytest.raises(
        TraceValidationError,
        match=r"process\.jsonl:3 is not standalone JSON",
    ):
        validate_trace(
            path,
            condition_id="A1",
            declared_processes=WRITING_TRACE_PROCESSES,
            goal_events="forbidden",
            allowed_event_types=("process_switch",),
        )


def test_trace_timestamp_plausibility_rejects_fabricated_midnight_values() -> None:
    events = [
        {"timestamp": "2026-09-08T00:00:00+00:00"},
        {"timestamp": "2026-09-08T00:00:00+00:00"},
    ]

    assert assess_trace_timestamps(
        events,
        started_at="2026-09-08T12:00:00+00:00",
        manifest_written_at="2026-09-08T12:00:30+00:00",
    ) == {
        "events": 2,
        "unparseable": 0,
        "out_of_window": 2,
        "non_monotonic": 0,
        "plausible": False,
    }


def test_trace_timestamp_plausibility_accepts_in_window_increasing_values() -> None:
    events = [
        {"timestamp": "2026-09-08T12:00:01+00:00"},
        {"timestamp": "2026-09-08T12:00:02+00:00"},
    ]

    assert assess_trace_timestamps(
        events,
        started_at="2026-09-08T12:00:00+00:00",
        manifest_written_at="2026-09-08T12:00:30+00:00",
    ) == {
        "events": 2,
        "unparseable": 0,
        "out_of_window": 0,
        "non_monotonic": 0,
        "plausible": True,
    }


def test_trace_timestamp_plausibility_skips_blank_lines_from_path(
    tmp_path: Path,
) -> None:
    path = tmp_path / "process.jsonl"
    events = [_event(), _event()]
    events[0]["timestamp"] = "2026-09-08T12:00:01+00:00"
    events[1]["timestamp"] = "2026-09-08T12:00:02+00:00"
    path.write_text("\n" + "\n".join(json.dumps(event) for event in events) + "\n")

    assert assess_trace_timestamps(
        path,
        started_at="2026-09-08T12:00:00+00:00",
        manifest_written_at="2026-09-08T12:00:30+00:00",
    ) == {
        "events": 2,
        "unparseable": 0,
        "out_of_window": 0,
        "non_monotonic": 0,
        "plausible": True,
    }


def test_trace_timestamp_plausibility_counts_unparseable_values() -> None:
    events = [
        {"timestamp": "not-a-timestamp"},
        {"timestamp": "2026-09-08T12:00:02+00:00"},
    ]

    assert assess_trace_timestamps(
        events,
        started_at="2026-09-08T12:00:00+00:00",
        manifest_written_at="2026-09-08T12:00:30+00:00",
    ) == {
        "events": 2,
        "unparseable": 1,
        "out_of_window": 0,
        "non_monotonic": 0,
        "plausible": False,
    }


def test_trace_timestamp_plausibility_counts_non_monotonic_values() -> None:
    events = [
        {"timestamp": "2026-09-08T12:00:02+00:00"},
        {"timestamp": "2026-09-08T12:00:01+00:00"},
    ]

    assert assess_trace_timestamps(
        events,
        started_at="2026-09-08T12:00:00+00:00",
        manifest_written_at="2026-09-08T12:00:30+00:00",
    ) == {
        "events": 2,
        "unparseable": 0,
        "out_of_window": 0,
        "non_monotonic": 1,
        "plausible": False,
    }


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
        def run(self, command, *, cwd, timeout_seconds, env=None):
            result = super().run(
                command, cwd=cwd, timeout_seconds=timeout_seconds, env=env
            )
            trace_path = cwd / ".writing" / "trace" / "process.jsonl"
            event = json.loads(trace_path.read_text())
            del event["evidence"]
            event["timestamp"] = "not-a-timestamp"
            trace_path.write_text(json.dumps(event) + "\n")
            return result

    runner = _runner(tmp_path, executor=InvalidTraceExecutor([_result()]))

    with pytest.raises(TraceValidationError, match="evidence"):
        runner.run_prompt(
            _prompt(),
            condition_id="A1",
            platform="codex",
            run_id="invalid-trace",
        )

    manifest = json.loads(
        (
            tmp_path
            / "WritingBench"
            / "A1"
            / "codex"
            / "invalid-trace"
            / "run-manifest.json"
        ).read_text()
    )
    assert manifest["trace_timestamps"] == {
        "events": 1,
        "unparseable": 1,
        "out_of_window": 0,
        "non_monotonic": 0,
        "plausible": False,
    }


def test_run_records_empty_trace_timestamp_summary_when_trace_is_missing(
    tmp_path: Path,
) -> None:
    class MissingTraceExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds, env=None):
            result = super().run(
                command, cwd=cwd, timeout_seconds=timeout_seconds, env=env
            )
            (cwd / ".writing" / "trace" / "process.jsonl").unlink()
            return result

    runner = _runner(tmp_path, executor=MissingTraceExecutor([_result()]))

    with pytest.raises(ExecutionError, match="produced no plugin trace"):
        runner.run_prompt(
            _prompt(),
            condition_id="A1",
            platform="codex",
            run_id="missing-trace",
        )

    manifest = json.loads(
        (
            tmp_path
            / "WritingBench"
            / "A1"
            / "codex"
            / "missing-trace"
            / "run-manifest.json"
        ).read_text()
    )
    assert manifest["trace_timestamps"] == {
        "events": 0,
        "unparseable": 0,
        "out_of_window": 0,
        "non_monotonic": 0,
        "plausible": True,
    }


class _RetryExecutor:
    def __init__(self, results: list[ExecutionResult]) -> None:
        self.results = results
        self.calls: list[list[str]] = []
        self.environments: list[dict[str, str] | None] = []

    def run(self, command, *, cwd, timeout_seconds, env=None):
        self.calls.append(command)
        self.environments.append(env)
        trace_path = cwd / ".writing" / "trace" / "process.jsonl"
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        if any("cognitive-writing-single-context" in argument for argument in command):
            (cwd / ".writing" / "draft.md").write_text("draft " * 10)
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
    spawn_status: str = "completed",
    receiver_thread_ids: list[str] | None = None,
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
            "status": spawn_status,
            "receiver_thread_ids": (
                receiver_thread_ids
                if receiver_thread_ids is not None
                else [f"receiver-{index}"]
            ),
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
        def run(self, command, *, cwd, timeout_seconds, env=None):
            result = super().run(
                command, cwd=cwd, timeout_seconds=timeout_seconds, env=env
            )
            goals = cwd / ".writing" / "goals.md"
            (cwd / ".writing" / "draft.md").write_text("final output " * 10)
            goals.write_text("should not exist")
            return result

    runner = _runner(tmp_path, executor=GoalWritingExecutor([_result()]))

    with pytest.raises(ExecutionError, match="goals.md"):
        runner.run_prompt(_prompt(), condition_id="A5", platform="codex")


def test_draft_product_scores_draft_md_verbatim(tmp_path: Path) -> None:
    draft_bytes = b"# Title\r\n\r\nBody text with trailing space.  \n\n"

    class DraftExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds, env=None):
            result = super().run(
                command, cwd=cwd, timeout_seconds=timeout_seconds, env=env
            )
            (cwd / ".writing" / "draft.md").write_bytes(draft_bytes)
            return result

    runner = _runner(
        tmp_path, executor=DraftExecutor([_result(output="short summary")])
    )

    result = runner.run_prompt(_prompt(), condition_id="A8", platform="codex")

    run_dir = result.run_dir
    assert (run_dir / "output.normalized.txt").read_bytes() == draft_bytes
    assert (run_dir / "output.raw").read_bytes() == draft_bytes
    manifest = json.loads(result.manifest_path.read_text())
    assert (
        manifest["output_hash"] == f"sha256:{hashlib.sha256(draft_bytes).hexdigest()}"
    )
    assert manifest["product_gate"]["rule"] == (
        "workspace/.writing/draft.md is the scored output, verbatim"
    )
    assert (
        "scored output is not workspace/.writing/draft.md"
        not in manifest["fidelity_gate"]["reasons"]
    )


@pytest.mark.parametrize(
    ("draft", "message"),
    [
        (
            None,
            "requires workspace/.writing/draft.md as its scored output; "
            "the workspace has no draft.md",
        ),
        ("  \n", "wrote an empty workspace/.writing/draft.md"),
    ],
)
def test_draft_product_without_draft_fails_with_reason(
    tmp_path: Path, draft: str | None, message: str
) -> None:
    class A2Executor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds, env=None):
            result = super().run(
                command, cwd=cwd, timeout_seconds=timeout_seconds, env=env
            )
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
            if draft is not None:
                (cwd / ".writing" / "draft.md").write_text(draft)
            return result

    runner = _runner(
        tmp_path, executor=A2Executor([_result(output="complete text " * 100)])
    )

    with pytest.raises(ExecutionError, match=re.escape(message)):
        runner.run_prompt(
            _prompt(), condition_id="A2", platform="codex", run_id="no-draft"
        )

    run_dir = tmp_path / "WritingBench" / "A2" / "codex" / "no-draft"
    assert not (run_dir / "output.raw").exists()
    assert not (run_dir / "output.normalized.txt").exists()
    manifest = json.loads((run_dir / "run-manifest.json").read_text())
    assert manifest["failure"]["type"] == "ExecutionError"
    assert message in manifest["failure"]["message"]


def test_runner_does_not_substitute_draft_for_empty_final_response(
    tmp_path: Path,
) -> None:
    class EmptyResponseExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds, env=None):
            result = super().run(
                command, cwd=cwd, timeout_seconds=timeout_seconds, env=env
            )
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
    assert manifest["inputs"]["platform"] == "codex"
    benchmark = manifest["inputs"]["benchmark_provenance"]
    assert benchmark["source_sha256"] == (
        "026e3f9482ff3474c802cd43f5cae9fd584e10d0848d3e0a152695434becbc98"
    )
    assert manifest["inputs"]["stage_prompt_hashes"]["single_shot"] == (
        "17f8982911d5087d60e901087f7e78bb1652e3443d285f1a8ebdc6d5f6f09728"
    )
    assert manifest["inputs"]["contract_hashes"] == {
        "delegation": hashlib.sha256(DELEGATION_CONTRACT_TEXT.encode()).hexdigest(),
        "single_turn": hashlib.sha256(SINGLE_TURN_CONTRACT_TEXT.encode()).hexdigest(),
        "workspace": hashlib.sha256(
            CLAUDE_WORKSPACE_CONTRACT_TEXT.encode()
        ).hexdigest(),
    }
    assert manifest["models_and_execution"]["judge_verification"] == {
        "declared_audit": {
            "generator_model_family_map": {
                "gpt-test": "gpt",
                "claude-test": "claude",
            }
        },
        "family_overlap_audit": "runtime-verified in the score manifest",
        "judge_families": "runtime-verified in the score manifest",
    }
    assert manifest["models_and_execution"]["generator_model_family"] == "gpt"
    assert (
        manifest["models_and_execution"]["decoding"]["codex_reasoning_effort"]
        == "xhigh"
    )


def test_runner_rejects_unmapped_generator_model_before_starting_run(
    tmp_path: Path,
) -> None:
    runner = _runner(
        tmp_path,
        config=_config(codex_generator_model="unmapped-generator"),
        executor=_RetryExecutor([_result()]),
    )

    with pytest.raises(
        ConfigurationError,
        match="generator model ID 'unmapped-generator' is not present in "
        "generator_model_family_map",
    ):
        runner.run_prompt(_prompt(), condition_id="A1", platform="codex")

    assert not (tmp_path / "WritingBench").exists()


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


def test_pre_trace_failure_records_trace_timestamp_summary(tmp_path: Path) -> None:
    runner = _runner(
        tmp_path,
        executor=_RetryExecutor(
            [_result(usage={"output_tokens": 80, "reasoning_output_tokens": 21})]
        ),
    )

    with pytest.raises(BudgetExceeded, match="budget"):
        runner.run_prompt(
            _prompt(),
            condition_id="A1",
            platform="codex",
            run_id="pre-trace-failure",
        )

    manifest = json.loads(
        (
            tmp_path
            / "WritingBench"
            / "A1"
            / "codex"
            / "pre-trace-failure"
            / "run-manifest.json"
        ).read_text()
    )
    assert manifest["trace_timestamps"]["events"] == 1


def test_non_draft_condition_accepts_short_output(tmp_path: Path) -> None:
    prompt = PromptRecord(
        prompt_id="p-1",
        benchmark_name="WritingBench",
        source_version="test",
        prompt_text="Write a memo.",
        requested_output_constraints={"min_words": 20},
        language="en",
        row_hash="row-hash",
    )

    class StrayDraftExecutor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds, env=None):
            result = super().run(
                command, cwd=cwd, timeout_seconds=timeout_seconds, env=env
            )
            (cwd / ".writing" / "draft.md").write_text("stray draft " * 50)
            return result

    runner = _runner(
        tmp_path,
        executor=StrayDraftExecutor(
            [_result(output="short", usage={"output_tokens": 2})]
        ),
    )

    result = runner.run_prompt(prompt, condition_id="A1", platform="codex")

    # A1 has no draft product, so its final response stays the scored output.
    assert (result.run_dir / "output.normalized.txt").read_text() == "short"
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["product_gate"] == {
        "requires_draft": False,
        "rule": "final response must be non-empty",
        "unit": "words",
    }


def test_a3_production_shaped_trace_and_draft_gate(tmp_path: Path) -> None:
    class A3Executor(_RetryExecutor):
        def run(self, command, *, cwd, timeout_seconds, env=None):
            result = super().run(
                command, cwd=cwd, timeout_seconds=timeout_seconds, env=env
            )
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
            rollout = Path(env["CODEX_HOME"]) / "sessions" / "attempt.jsonl"
            rollout.parent.mkdir(parents=True, exist_ok=True)
            rollout.write_bytes(result.stdout)
            return result

    output = "final " * 60
    runner = _runner(
        tmp_path,
        executor=A3Executor(
            [_result(output=output, usage={"output_tokens": 60}, subagent_spawns=1)]
        ),
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
        def run(self, command, *, cwd, timeout_seconds, env=None):
            result = super().run(
                command, cwd=cwd, timeout_seconds=timeout_seconds, env=env
            )
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
    monkeypatch.setattr(
        runner,
        "_snapshot_codex_sessions",
        lambda _codex_home: next(snapshots),
    )

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
