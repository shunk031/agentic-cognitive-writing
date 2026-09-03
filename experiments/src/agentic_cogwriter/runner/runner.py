"""Top-level condition execution and run-artifact production."""

from __future__ import annotations

import json
import tomllib
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ..paths import EXPERIMENTS_ROOT, REPOSITORY_ROOT
from .adapters import PlatformAdapter
from .budget import OutputBudget, estimate_output_tokens
from .conditions import ConditionSpec, load_condition_registry
from .config import RuntimeConfig
from .errors import ConfigurationError, ExecutionError, ManifestError
from .execution import (
    ExecutionResult,
    SubprocessExecutor,
    extract_output,
    reject_retrieval,
)
from .hashing import sha256_file
from .manifest import PromptRecord
from .trace import checksums_for_files, collect_plugin_trace, timestamp, validate_jsonl


class Executor(Protocol):
    """Protocol implemented by real and test executors."""

    def run(
        self, command: list[str], *, cwd: Path, timeout_seconds: float
    ) -> ExecutionResult:
        """Run one non-interactive command."""


@dataclass(frozen=True)
class RunResult:
    """Paths and metadata for one completed or failed run."""

    run_dir: Path
    manifest_path: Path
    output_path: Path
    trace_path: Path
    checksums_path: Path
    run_id: str


def _safe_component(value: str) -> str:
    return "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value
    )


class ExperimentRunner:
    """Run one condition and prompt with immutable policy settings."""

    def __init__(
        self,
        runtime_config: RuntimeConfig,
        *,
        output_root: Path,
        executor: Executor | None = None,
        condition_registry: dict[str, ConditionSpec] | None = None,
        adapters: dict[str, PlatformAdapter] | None = None,
    ):
        self.runtime_config = runtime_config
        self.output_root = output_root
        self.executor = executor or SubprocessExecutor()
        self.conditions = condition_registry or load_condition_registry()
        self.adapters = adapters or self._load_adapters()

    def _load_adapters(self) -> dict[str, PlatformAdapter]:
        root = EXPERIMENTS_ROOT / "conditions" / "adapters"
        return {
            "codex-primary": PlatformAdapter.load(root / "codex_exec.toml"),
            "claude-code-replication": PlatformAdapter.load(root / "claude_print.toml"),
        }

    def run_prompt(
        self,
        prompt: PromptRecord,
        *,
        condition_id: str,
        platform: str,
        run_id: str | None = None,
    ) -> RunResult:
        """Run one top-level skill session and copy its plugin-owned trace."""

        self.runtime_config.require_scored_run()
        condition = self.conditions.get(condition_id)
        if condition is None:
            raise ManifestError(f"Unknown condition: {condition_id}")
        adapter = self.adapters.get(platform)
        if adapter is None:
            raise ManifestError(f"Unknown platform: {platform}")
        if adapter.platform != platform:
            raise ManifestError(f"Adapter platform mismatch for {platform}")

        run_id = run_id or uuid.uuid4().hex
        run_dir = (
            self.output_root
            / _safe_component(prompt.benchmark_name)
            / _safe_component(condition_id)
            / _safe_component(platform)
            / _safe_component(run_id)
        )
        run_dir.mkdir(parents=True, exist_ok=False)
        workspace = run_dir / "workspace"
        workspace.mkdir()
        manifest_path = run_dir / "run-manifest.json"
        output_path = run_dir / "output.raw"
        normalized_path = run_dir / "output.normalized.txt"
        trace_path = run_dir / ".writing" / "trace" / "process.jsonl"
        checksums_path = run_dir / "checksums.json"
        started_at = timestamp()
        budget = OutputBudget(self.runtime_config.output_budget_tokens)
        attempts = 0
        cli_version = "not_probed"

        # The started manifest exists before CLI probing or model process creation.
        self._write_json(
            manifest_path,
            self._manifest(
                prompt=prompt,
                condition=condition,
                platform=platform,
                adapter=adapter,
                run_id=run_id,
                status="started",
                started_at=started_at,
                cli_version=cli_version,
                budget=budget,
            ),
        )

        try:
            cli_version = self._probe_cli(adapter)
            expected_version = self._expected_cli_version(platform)
            if cli_version != expected_version:
                raise ConfigurationError(
                    f"Installed {platform} CLI version {cli_version!r} does not match "
                    f"pinned version {expected_version!r}"
                )
            self._write_json(
                manifest_path,
                self._manifest(
                    prompt=prompt,
                    condition=condition,
                    platform=platform,
                    adapter=adapter,
                    run_id=run_id,
                    status="started",
                    started_at=started_at,
                    cli_version=cli_version,
                    budget=budget,
                ),
            )
            command_prompt = self._plugin_prompt(condition, prompt, platform)
            result, attempts = self._run_turn_with_retry(
                adapter,
                model_id=self.runtime_config.model_for(platform),
                prompt=command_prompt,
                cwd=workspace,
                attempts=attempts,
                plugin_dirs=self._plugin_dirs(condition),
            )
            output = extract_output(result.stdout)
            if not output.strip():
                draft_path = workspace / ".writing" / "draft.md"
                if draft_path.is_file():
                    output = draft_path.read_text(encoding="utf-8")
            budget.consume(estimate_output_tokens(output), stage="final_output")

            trace_files = collect_plugin_trace(workspace, run_dir)
            required_trace = ".writing/trace/process.jsonl"
            if required_trace not in trace_files:
                raise ExecutionError(
                    f"Condition {condition.condition_id} produced no plugin trace at "
                    f"{required_trace}"
                )
            copied_trace = run_dir / required_trace
            reject_retrieval(copied_trace.read_bytes(), b"")
            validate_jsonl(copied_trace)

            output_path.write_bytes(output.encode("utf-8"))
            normalized_path.write_text(output, encoding="utf-8")
            artifact_paths = [
                "output.raw",
                "output.normalized.txt",
                required_trace,
                *trace_files,
            ]
            checksums = checksums_for_files(run_dir, artifact_paths)
            self._write_json(checksums_path, checksums)
            self._write_json(
                manifest_path,
                self._manifest(
                    prompt=prompt,
                    condition=condition,
                    platform=platform,
                    adapter=adapter,
                    run_id=run_id,
                    status="completed",
                    started_at=started_at,
                    cli_version=cli_version,
                    attempts=attempts,
                    budget=budget,
                    output_hash=checksums.get("output.raw"),
                    trace_hash=checksums.get(required_trace),
                ),
            )
            return RunResult(
                run_dir, manifest_path, output_path, trace_path, checksums_path, run_id
            )
        except Exception as exc:
            self._write_json(
                manifest_path,
                self._manifest(
                    prompt=prompt,
                    condition=condition,
                    platform=platform,
                    adapter=adapter,
                    run_id=run_id,
                    status="failed",
                    started_at=started_at,
                    cli_version=cli_version,
                    attempts=attempts,
                    budget=budget,
                    failure={"type": type(exc).__name__, "message": str(exc)},
                ),
            )
            raise

    def _probe_cli(self, adapter: PlatformAdapter) -> str:
        if isinstance(self.executor, SubprocessExecutor):
            return adapter.probe_version(
                timeout_seconds=self.runtime_config.timeout_seconds
            )
        key = (
            "codex_version"
            if adapter.platform == "codex-primary"
            else "claude_code_version"
        )
        return str(self.runtime_config.get(key))

    def _expected_cli_version(self, platform: str) -> str:
        key = "codex_version" if platform == "codex-primary" else "claude_code_version"
        value = self.runtime_config.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ConfigurationError(f"{key} must be a pinned version string")
        return value.strip()

    def _run_turn_with_retry(
        self,
        adapter: PlatformAdapter,
        *,
        model_id: str,
        prompt: str,
        cwd: Path,
        attempts: int,
        plugin_dirs: tuple[str, ...] = (),
    ) -> tuple[ExecutionResult, int]:
        """Run one skill turn, retrying only with the identical command policy."""

        max_attempts = self.runtime_config.retry_count + 1
        local_attempts = 0
        while local_attempts < max_attempts:
            local_attempts += 1
            attempts += 1
            command = adapter.build_command(
                model_id=model_id,
                prompt=prompt,
                plugin_dirs=plugin_dirs,
            )
            result = self.executor.run(
                command,
                cwd=cwd,
                timeout_seconds=self.runtime_config.timeout_seconds,
            )
            reject_retrieval(result.stdout, result.stderr)
            if result.timed_out:
                if local_attempts < max_attempts:
                    continue
                raise ExecutionError("Headless turn timed out")
            if result.returncode != 0:
                if local_attempts < max_attempts:
                    continue
                message = result.stderr.decode("utf-8", errors="replace").strip()
                raise ExecutionError(
                    f"Headless turn failed with status {result.returncode}: {message}"
                )
            return result, attempts
        raise ExecutionError("Headless turn exhausted retry policy")

    def _plugin_prompt(
        self, condition: ConditionSpec, prompt: PromptRecord, platform: str
    ) -> str:
        wrapper = self._wrapper(condition)
        key = platform.replace("-", "_")
        invocation = wrapper.get("invocation", {}).get(key)
        if not isinstance(invocation, str) or not invocation.strip():
            raise ManifestError(
                f"Plugin wrapper {condition.plugin_config} has no {key} invocation"
            )
        constraints = json.dumps(
            prompt.requested_output_constraints,
            ensure_ascii=False,
            sort_keys=True,
        )
        return (
            f"{invocation}\n\nAssignment:\n{prompt.input_text}\n\n"
            f"Supplied context:\n{prompt.supplied_context or '(none)'}\n\n"
            "Requested output constraints:\n"
            f"{constraints}"
        )

    def _wrapper(self, condition: ConditionSpec) -> dict[str, Any]:
        try:
            wrapper = tomllib.loads(condition.plugin_config.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ManifestError(
                f"Cannot read plugin wrapper {condition.plugin_config}: {exc}"
            ) from exc
        if not isinstance(wrapper, dict):
            raise ManifestError(
                f"Plugin wrapper {condition.plugin_config} must be a TOML object"
            )
        return wrapper

    def _plugin_dirs(self, condition: ConditionSpec) -> tuple[str, ...]:
        paths = self._wrapper(condition).get("plugins", {}).get("paths", [])
        if not isinstance(paths, list) or not all(
            isinstance(path, str) for path in paths
        ):
            raise ManifestError(
                "Plugin wrapper plugins.paths must be a list of strings"
            )
        return tuple(
            str((REPOSITORY_ROOT / path).resolve())
            if not Path(path).is_absolute()
            else str(Path(path).resolve())
            for path in paths
        )

    def _manifest(
        self,
        *,
        prompt: PromptRecord,
        condition: ConditionSpec,
        platform: str,
        adapter: PlatformAdapter,
        run_id: str,
        status: str,
        started_at: str,
        cli_version: str,
        attempts: int = 0,
        budget: OutputBudget | None = None,
        output_hash: str | None = None,
        trace_hash: str | None = None,
        failure: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        wrapper_hash = f"sha256:{sha256_file(condition.plugin_config)}"
        manifest: dict[str, Any] = {
            "schema_version": 1,
            "run_id": run_id,
            "status": status,
            "started_at": started_at,
            "updated_at": timestamp(),
            "inputs": {
                "benchmark_name": prompt.benchmark_name,
                "source_version": prompt.source_version,
                "prompt_id": prompt.prompt_id,
                "prompt_hash": prompt.row_hash,
                "prompt_manifest_hash": prompt.manifest_hash,
                "condition_id": condition.condition_id,
                "analysis_family": condition.analysis_family,
                "selected_variant": condition.condition_id,
                "selected_skill": condition.skill_name,
                "wrapper_config_hash": wrapper_hash,
                "stage_prompt_hashes": {
                    stage.stage_id: stage.sha256 for stage in condition.stages
                },
                "trace_policy": condition.trace_policy_dict,
            },
            "models_and_execution": {
                "cli": adapter.executable,
                "cli_version": cli_version,
                "generator_model_id": self.runtime_config.model_for(platform),
                "frontier_judge_model_id": self.runtime_config.get(
                    "codex_frontier_judge"
                    if platform == "codex-primary"
                    else "claude_code_frontier_judge"
                ),
                "judge_model_ids": {
                    "codex_frontier": self.runtime_config.get("codex_frontier_judge"),
                    "claude_code_frontier": self.runtime_config.get(
                        "claude_code_frontier_judge"
                    ),
                    "shared_open_evaluator": self.runtime_config.get(
                        "shared_open_evaluator"
                    ),
                },
                "shared_open_evaluator": self.runtime_config.get(
                    "shared_open_evaluator"
                ),
                "main_plugin_commit": self.runtime_config.get("main_plugin_commit"),
                "experiments_plugin_commit": self.runtime_config.get(
                    "experiments_plugin_commit"
                ),
                "generator_system_and_condition_prompts": self.runtime_config.get(
                    "generator_system_and_condition_prompts"
                ),
                "judge_prompts_and_json_schemas": self.runtime_config.get(
                    "judge_prompts_and_json_schemas"
                ),
                "generator_prompt_hashes": self.runtime_config.get(
                    "generator_system_and_condition_prompts"
                ),
                "judge_prompt_hashes": self.runtime_config.get(
                    "judge_prompts_and_json_schemas"
                ),
                "decoding": {
                    "temperature": self.runtime_config.get("temperature"),
                    "top_p_or_equivalent": self.runtime_config.get(
                        "top_p_or_equivalent"
                    ),
                    "stop_rules": self.runtime_config.get("stop_rules"),
                },
                "output_budget_tokens": self.runtime_config.output_budget_tokens,
                "tool_policy": "local supplied context only",
                "no_retrieval_check": "fail closed",
                "command_flags": {
                    "first_args": list(adapter.first_args),
                    "continuation_args": list(adapter.continuation_args),
                },
            },
            "reproducibility_and_environment": {
                "seeds": {
                    "generation": self.runtime_config.get("generation_seed"),
                    "judge": self.runtime_config.get("judge_seed"),
                    "sampling": self.runtime_config.get("sampling_seed"),
                    "presentation": self.runtime_config.get("presentation_seed"),
                },
                "retry_policy": self.runtime_config.get("retry_policy"),
                "timeout_seconds": self.runtime_config.timeout_seconds,
                "runner_commit": self.runtime_config.get("runner_commit"),
                "generator_and_judge_family_audit": self.runtime_config.get(
                    "generator_and_judge_family_audit"
                ),
            },
            "attempts": attempts,
            "budget_used_tokens": budget.used if budget else 0,
        }
        if output_hash is not None:
            manifest["output_hash"] = output_hash
        if trace_hash is not None:
            manifest["trace_hash"] = trace_hash
        if failure is not None:
            manifest["failure"] = failure
        return manifest

    @staticmethod
    def _write_json(path: Path, value: Any) -> None:
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
