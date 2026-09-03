"""Top-level condition execution and run-artifact production."""

from __future__ import annotations

import json
import os
import shutil
import tomllib
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ..paths import EXPERIMENTS_ROOT, REPOSITORY_ROOT
from .adapters import PlatformAdapter
from .budget import OutputBudget
from .conditions import ConditionSpec, load_condition_registry
from .config import RuntimeConfig
from .errors import (
    ConfigurationError,
    ExecutionError,
    ManifestError,
    RetrievalViolation,
)
from .execution import (
    ExecutionResult,
    SubprocessExecutor,
    _subagent_spawn_ids,
    extract_output,
    extract_token_usage,
    reject_retrieval,
)
from .hashing import sha256_bytes, sha256_file
from .manifest import PromptRecord, load_benchmark_provenance
from .trace import (
    assert_untouched,
    checksums_for_files,
    collect_plugin_trace,
    timestamp,
    validate_trace,
)


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


FINAL_OUTPUT_DRAFT_RATIO = 0.5


def _safe_component(value: str) -> str:
    return "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value
    )


def _validate_final_product(
    output: str, draft: str | None, *, condition_id: str
) -> None:
    """Require the response channel to carry the complete product text."""

    final_chars = len(output.strip())
    if not final_chars:
        raise ExecutionError(
            f"Condition {condition_id} produced no final response; "
            "draft.md is not accepted as a substitute"
        )
    if draft is None:
        return
    draft_chars = len(draft.strip())
    if final_chars < draft_chars * FINAL_OUTPUT_DRAFT_RATIO:
        raise ExecutionError(
            f"Condition {condition_id} final response is less than "
            f"{FINAL_OUTPUT_DRAFT_RATIO:.0%} of draft.md; "
            f"final_chars={final_chars}, draft_chars={draft_chars}"
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
        codex_plugin_root: Path | None = None,
        codex_home: Path | None = None,
    ):
        self.runtime_config = runtime_config
        self.output_root = output_root.resolve()
        self.executor = executor or SubprocessExecutor()
        self.conditions = condition_registry or load_condition_registry()
        self.adapters = adapters or self._load_adapters()
        self.codex_plugin_root = codex_plugin_root
        configured_codex_home = (
            codex_home
            if codex_home is not None
            else Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        )
        self.codex_home = configured_codex_home.expanduser().resolve()

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
        trace_path = workspace / ".writing" / "trace" / "process.jsonl"
        checksums_path = run_dir / "checksums.json"
        prompt_path = run_dir / "prompt.txt"
        execution_paths = {
            "cwd": str(workspace.resolve()),
            "prompt": str(prompt_path.resolve()),
            "trace_path": str(trace_path.resolve()),
        }
        started_at = timestamp()
        budget = OutputBudget(self.runtime_config.output_budget_tokens)
        attempts = 0
        evidence_hashes: dict[str, str] = {}
        staged_files: dict[str, str] = {}
        token_usage: dict[str, int] | None = None
        subagent_spawn_ids: set[str] = set()
        cli_version = "not_probed"
        stage_prompt_hashes = self._stage_prompt_hashes(condition)
        benchmark_provenance = load_benchmark_provenance(prompt.benchmark_name)
        protected_goals = workspace / ".writing" / "goals.md"
        goals_before = (
            protected_goals.read_bytes() if protected_goals.is_file() else None
        )

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
                stage_prompt_hashes=stage_prompt_hashes,
                benchmark_provenance=benchmark_provenance,
                execution_paths=execution_paths,
                evidence_hashes=evidence_hashes,
                staged_files=staged_files,
                token_usage=token_usage,
                subagent_spawn_count=len(subagent_spawn_ids),
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
            if platform == "codex-primary":
                staged_files = self._stage_codex_plugin(condition, workspace)
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
                    stage_prompt_hashes=stage_prompt_hashes,
                    benchmark_provenance=benchmark_provenance,
                    execution_paths=execution_paths,
                    evidence_hashes=evidence_hashes,
                    staged_files=staged_files,
                    token_usage=token_usage,
                    subagent_spawn_count=len(subagent_spawn_ids),
                ),
            )
            command_prompt = self._plugin_prompt(
                condition,
                prompt,
                platform,
                codex_prompt_root=Path("plugin"),
            )

            prompt_path.write_text(command_prompt, encoding="utf-8")
            evidence_hashes["prompt.txt"] = f"sha256:{sha256_file(prompt_path)}"
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
                    stage_prompt_hashes=stage_prompt_hashes,
                    benchmark_provenance=benchmark_provenance,
                    execution_paths=execution_paths,
                    evidence_hashes=evidence_hashes,
                    staged_files=staged_files,
                    token_usage=token_usage,
                ),
            )

            def record_attempt(
                attempt_number: int,
                result: ExecutionResult | None,
                session_before: Mapping[Path, str] | None,
            ) -> None:
                nonlocal attempts, token_usage
                attempts = max(attempts, attempt_number)
                evidence_hashes.update(
                    self._persist_attempt_evidence(run_dir, attempt_number, result)
                )
                if platform == "codex-primary":
                    evidence_hashes.update(
                        self._collect_codex_sessions(
                            run_dir, attempt_number, session_before or {}
                        )
                    )
                attempt_events_path = (
                    run_dir / f"attempt-{attempt_number:03d}.events.jsonl"
                )
                subagent_spawn_ids.update(
                    _subagent_spawn_ids(attempt_events_path.read_bytes())
                )
                if result is not None:
                    observed_usage = extract_token_usage(result.stdout)
                    if observed_usage is not None:
                        if token_usage is None:
                            token_usage = {
                                "output_tokens": 0,
                                "reasoning_output_tokens": 0,
                                "total_tokens": 0,
                            }
                        for key, value in observed_usage.items():
                            token_usage[key] += value
                self._write_json(
                    checksums_path,
                    checksums_for_files(run_dir, ["prompt.txt", *evidence_hashes]),
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
                        attempts=attempts,
                        budget=budget,
                        stage_prompt_hashes=stage_prompt_hashes,
                        benchmark_provenance=benchmark_provenance,
                        execution_paths=execution_paths,
                        evidence_hashes=evidence_hashes,
                        staged_files=staged_files,
                        token_usage=token_usage,
                        subagent_spawn_count=len(subagent_spawn_ids),
                    ),
                )

            result, attempts = self._run_turn_with_retry(
                adapter,
                model_id=self.runtime_config.model_for(platform),
                prompt=command_prompt,
                cwd=workspace,
                attempts=attempts,
                plugin_dirs=(
                    self._plugin_dirs(condition) if platform != "codex-primary" else ()
                ),
                record_attempt=record_attempt,
                snapshot_sessions=(
                    self._snapshot_codex_sessions
                    if platform == "codex-primary"
                    else None
                ),
            )
            output = extract_output(result.stdout)
            draft_path = workspace / ".writing" / "draft.md"
            draft = None
            if draft_path.is_file():
                try:
                    draft = draft_path.read_text(encoding="utf-8")
                except (OSError, UnicodeError) as exc:
                    raise ExecutionError(
                        f"Cannot read workspace draft {draft_path}: {exc}"
                    ) from exc
                reject_retrieval(draft.encode("utf-8"), b"", scan_artifact_text=True)
            reject_retrieval(output.encode("utf-8"), b"")
            _validate_final_product(output, draft, condition_id=condition.condition_id)
            budget.consume(
                self.runtime_config.count_output_units(output), stage="final_output"
            )

            if condition.condition_id == "A5":
                assert_untouched(protected_goals, goals_before)
            required_trace = ".writing/trace/process.jsonl"
            if not trace_path.is_file():
                raise ExecutionError(
                    f"Condition {condition.condition_id} produced no plugin trace at "
                    f"{trace_path}"
                )
            trace_files = collect_plugin_trace(workspace, run_dir)
            copied_trace = run_dir / required_trace
            if required_trace not in trace_files or not copied_trace.is_file():
                raise ExecutionError(
                    f"Condition {condition.condition_id} could not collect plugin "
                    f"trace from {trace_path}"
                )
            reject_retrieval(copied_trace.read_bytes(), b"")
            validate_trace(
                copied_trace,
                condition_id=condition.condition_id,
                expected_stage_ids=tuple(stage.stage_id for stage in condition.stages),
            )

            output_path.write_bytes(output.encode("utf-8"))
            normalized_path.write_text(output, encoding="utf-8")
            artifact_paths = [
                "output.raw",
                "output.normalized.txt",
                required_trace,
                *trace_files,
                *evidence_hashes,
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
                    stage_prompt_hashes=stage_prompt_hashes,
                    benchmark_provenance=benchmark_provenance,
                    execution_paths=execution_paths,
                    evidence_hashes=evidence_hashes,
                    staged_files=staged_files,
                    token_usage=token_usage,
                    subagent_spawn_count=len(subagent_spawn_ids),
                ),
            )
            return RunResult(
                run_dir,
                manifest_path,
                output_path,
                copied_trace,
                checksums_path,
                run_id,
            )
        except Exception as exc:
            if isinstance(exc, ExecutionError) and attempts == 0:
                attempts = 1
                evidence_hashes.update(
                    self._persist_attempt_evidence(run_dir, attempts, None)
                )
            failure: dict[str, Any] = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
            if isinstance(exc, RetrievalViolation):
                stream = exc.stream or "stdout"
                artifact_name = f"rejected-output.{stream}"
                artifact_path = run_dir / artifact_name
                artifact_path.write_bytes(exc.payload)
                failure["retrieval"] = {
                    "artifact": artifact_name,
                    "matched_pattern": exc.matched_pattern,
                    "matching_line": exc.matching_line,
                    "sha256": f"sha256:{sha256_bytes(exc.payload)}",
                    "stream": stream,
                }
            failure_artifacts = ["prompt.txt", *evidence_hashes]
            if isinstance(exc, RetrievalViolation):
                failure_artifacts.append(f"rejected-output.{exc.stream or 'stdout'}")
            failure_checksums = checksums_for_files(
                run_dir, list(dict.fromkeys(failure_artifacts))
            )
            if failure_checksums:
                self._write_json(checksums_path, failure_checksums)
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
                    stage_prompt_hashes=stage_prompt_hashes,
                    benchmark_provenance=benchmark_provenance,
                    execution_paths=execution_paths,
                    evidence_hashes=evidence_hashes,
                    staged_files=staged_files,
                    token_usage=token_usage,
                    subagent_spawn_count=len(subagent_spawn_ids),
                    failure=failure,
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
        record_attempt: Callable[[int, ExecutionResult | None], None] | None = None,
        snapshot_sessions: Callable[[], dict[Path, str]] | None = None,
    ) -> tuple[ExecutionResult, int]:
        """Run one skill turn, retrying only with the identical command policy."""

        max_attempts = self.runtime_config.retry_count + 1
        local_attempts = 0
        session_id: str | None = None
        while local_attempts < max_attempts:
            local_attempts += 1
            attempts += 1
            command = adapter.build_command(
                model_id=model_id,
                prompt=prompt,
                session_id=session_id,
                plugin_dirs=plugin_dirs,
                output_budget_tokens=self.runtime_config.output_budget_tokens,
                decoding={
                    "temperature": self.runtime_config.get("temperature"),
                    "top_p_or_equivalent": self.runtime_config.get(
                        "top_p_or_equivalent"
                    ),
                    "generation_seed": self.runtime_config.get("generation_seed"),
                    "stop_rules": self.runtime_config.get("stop_rules"),
                },
            )
            session_before = (
                snapshot_sessions() if snapshot_sessions is not None else None
            )
            try:
                result = self.executor.run(
                    command,
                    cwd=cwd,
                    timeout_seconds=self.runtime_config.timeout_seconds,
                )
            except Exception:
                if record_attempt is not None:
                    record_attempt(attempts, None, session_before)
                raise
            if record_attempt is not None:
                record_attempt(attempts, result, session_before)
            reject_retrieval(result.stdout, result.stderr)
            if result.session_id:
                session_id = result.session_id
            if result.timed_out:
                if local_attempts < max_attempts:
                    if session_id is None:
                        detail = result.stderr.decode("utf-8", errors="replace").strip()
                        suffix = f": {detail}" if detail else ""
                        raise ExecutionError(
                            "Cannot retry a timed-out turn without its session_id"
                            + suffix
                        )
                    continue
                raise ExecutionError("Headless turn timed out")
            if result.returncode != 0:
                if local_attempts < max_attempts:
                    if session_id is None:
                        detail = result.stderr.decode("utf-8", errors="replace").strip()
                        suffix = f": {detail}" if detail else ""
                        raise ExecutionError(
                            "Cannot retry a failed turn without its session_id"
                            f" (return code {result.returncode})" + suffix
                        )
                    continue
                message = result.stderr.decode("utf-8", errors="replace").strip()
                raise ExecutionError(
                    f"Headless turn failed with status {result.returncode}: {message}"
                )
            return result, attempts
        raise ExecutionError("Headless turn exhausted retry policy")

    def _plugin_prompt(
        self,
        condition: ConditionSpec,
        prompt: PromptRecord,
        platform: str,
        *,
        codex_prompt_root: str | Path | None = None,
    ) -> str:
        wrapper = self._wrapper(condition)
        key = platform.replace("-", "_")
        invocation = wrapper.get("invocation", {}).get(key)
        if not isinstance(invocation, str) or not invocation.strip():
            raise ManifestError(
                f"Plugin wrapper {condition.plugin_config} has no {key} invocation"
            )
        if platform == "codex-primary":
            prompt_root = Path(codex_prompt_root or "plugin")
            if prompt_root.is_absolute():
                raise ManifestError(
                    "Codex skill prompt path must be workspace-relative"
                )
            invocation = invocation.replace(
                "{codex_plugin_root}", prompt_root.as_posix()
            )
            if "{codex_plugin_root}" in invocation:
                raise ManifestError(
                    f"Plugin wrapper {condition.plugin_config} has an unresolved "
                    "Codex plugin root"
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
            f"{self._stage_prompt_text(condition)}"
        )

    def _stage_prompt_hashes(self, condition: ConditionSpec) -> dict[str, str | None]:
        """Re-read frozen stage files and verify the bytes used for the prompt."""

        hashes: dict[str, str | None] = {}
        for stage in condition.stages:
            if stage.path is None:
                hashes[stage.stage_id] = None
                continue
            raw = stage.path.read_bytes()
            observed = sha256_bytes(raw)
            if stage.sha256 != observed:
                raise ManifestError(f"Frozen prompt hash mismatch: {stage.path}")
            hashes[stage.stage_id] = observed
        return hashes

    def _stage_prompt_text(self, condition: ConditionSpec) -> str:
        """Include committed A1-A3 stage instructions in the scored prompt."""

        chunks: list[str] = []
        for stage in condition.stages:
            if stage.path is None:
                continue
            try:
                content = stage.path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise ManifestError(
                    f"Cannot read frozen prompt file {stage.path}: {exc}"
                ) from exc
            if sha256_bytes(content.encode("utf-8")) != stage.sha256:
                raise ManifestError(f"Frozen prompt hash mismatch: {stage.path}")
            chunks.append(f"\n\nFrozen stage {stage.stage_id}:\n{content}")
        return "".join(chunks)

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

    def _configured_plugin_paths(self, condition: ConditionSpec) -> tuple[Path, ...]:
        wrapper = self._wrapper(condition)
        plugins = wrapper.get("plugins")
        paths = plugins.get("paths") if isinstance(plugins, Mapping) else None
        if not isinstance(paths, list) or not all(
            isinstance(path, str) and path.strip() for path in paths
        ):
            raise ManifestError(
                "Plugin wrapper plugins.paths must be a list of strings"
            )
        return tuple(
            (REPOSITORY_ROOT / path).resolve()
            if not Path(path).is_absolute()
            else Path(path).resolve()
            for path in paths
        )

    def _plugin_dirs(self, condition: ConditionSpec) -> tuple[str, ...]:
        """Return configured plugin directories for Claude's plugin loader."""

        return tuple(str(path) for path in self._configured_plugin_paths(condition))

    def _codex_source_roots(self, condition: ConditionSpec) -> tuple[Path, ...]:
        """Return configured roots from which Codex skill files can be staged."""

        if self.codex_plugin_root is not None:
            return (self.codex_plugin_root.resolve(),)
        return self._configured_plugin_paths(condition)

    def _codex_plugin_root(self, condition: ConditionSpec) -> Path:
        """Select the root containing the skill file referenced by Codex."""

        paths = self._codex_source_roots(condition)
        skill_relative = Path("skills") / condition.skill_name / "SKILL.md"
        for path in paths:
            if (path / skill_relative).is_file():
                return path
        if paths:
            return paths[0]
        raise ManifestError(
            f"Plugin wrapper {condition.plugin_config} has no configured plugin path"
        )

    def _stage_codex_plugin(
        self, condition: ConditionSpec, workspace: Path
    ) -> dict[str, str]:
        """Stage the invoked skill and delegated role skills inside the workspace."""

        selected_root = self._codex_plugin_root(condition)
        source_roots = (
            selected_root,
            *tuple(
                root
                for root in self._codex_source_roots(condition)
                if root != selected_root
            ),
        )
        required_directories = [Path("skills") / condition.skill_name]
        if condition.skill_name == "agentic-cog-writer":
            required_directories.extend(
                Path("skills") / role
                for role in ("planning", "translating", "reviewing")
            )
        sources: dict[Path, Path] = {}
        for relative in required_directories:
            source = next(
                (
                    root / relative
                    for root in source_roots
                    if (root / relative).is_dir()
                ),
                None,
            )
            if source is None:
                raise ManifestError(
                    f"Cannot stage required Codex skill directory: {relative}"
                )
            sources[relative] = source

        staged_root = workspace / "plugin"
        for relative, source in sources.items():
            shutil.copytree(
                source,
                staged_root / relative,
                dirs_exist_ok=True,
            )
        return {
            path.relative_to(workspace).as_posix(): f"sha256:{sha256_file(path)}"
            for path in sorted(staged_root.rglob("*"))
            if path.is_file()
        }

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
        stage_prompt_hashes: Mapping[str, str | None] | None = None,
        benchmark_provenance: Mapping[str, Any] | None = None,
        output_hash: str | None = None,
        trace_hash: str | None = None,
        failure: Mapping[str, Any] | None = None,
        execution_paths: Mapping[str, str] | None = None,
        evidence_hashes: Mapping[str, str] | None = None,
        staged_files: Mapping[str, str] | None = None,
        token_usage: Mapping[str, int] | None = None,
        subagent_spawn_count: int = 0,
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
                    stage.stage_id: (stage_prompt_hashes or {}).get(stage.stage_id)
                    for stage in condition.stages
                },
                "trace_policy": condition.trace_policy_dict,
                "benchmark_provenance": dict(benchmark_provenance or {}),
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
                "output_budget_unit": self.runtime_config.output_unit,
                "tool_policy": {
                    "context": "local supplied context only",
                    "network": adapter.network_enforcement,
                },
                "no_retrieval": {
                    "generator": adapter.network_enforcement,
                    "secondary_tripwire": "raw URL and network-command scan",
                    "judge_side": "out-of-scope pending judge module",
                },
                "judge_verification": {
                    "judge_families": "declared-unverified pending judge module",
                    "family_overlap_audit": (
                        "declared-unverified pending judge module"
                    ),
                    "declared_audit": self.runtime_config.get(
                        "generator_and_judge_family_audit"
                    ),
                },
                "generation_control_status": adapter.control_status_dict,
                "command_flags": {
                    "first_args": list(adapter.first_args),
                    "continuation_args": list(adapter.continuation_args),
                    "runtime_args": list(adapter.runtime_args),
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
            "budget_used_tokens": (
                token_usage.get("total_tokens") if token_usage is not None else None
            ),
            "output_units_used": budget.used if budget else 0,
            "subagent_spawn_count": subagent_spawn_count,
            "token_accounting": {
                "status": "observed" if token_usage is not None else "monitored-only",
                "source": "Codex turn.completed usage",
                "output_tokens": (
                    token_usage.get("output_tokens")
                    if token_usage is not None
                    else None
                ),
                "reasoning_output_tokens": (
                    token_usage.get("reasoning_output_tokens")
                    if token_usage is not None
                    else None
                ),
                "total_tokens": (
                    token_usage.get("total_tokens") if token_usage is not None else None
                ),
            },
            "execution_paths": dict(execution_paths or {}),
            "evidence_hashes": dict(evidence_hashes or {}),
            "staged_files": dict(staged_files or {}),
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

    @staticmethod
    def _persist_attempt_evidence(
        run_dir: Path, attempt_number: int, result: ExecutionResult | None
    ) -> dict[str, str]:
        """Persist the complete transport streams for one executor attempt."""

        stdout = result.stdout if result is not None else b""
        stderr = result.stderr if result is not None else b""
        prefix = f"attempt-{attempt_number:03d}"
        payloads = {
            f"{prefix}.events.jsonl": stdout,
            f"{prefix}.stdout.raw": stdout,
            f"{prefix}.stderr.raw": stderr,
        }
        hashes: dict[str, str] = {}
        for name, payload in payloads.items():
            (run_dir / name).write_bytes(payload)
            hashes[name] = f"sha256:{sha256_bytes(payload)}"
        return hashes

    def _snapshot_codex_sessions(self) -> dict[Path, str]:
        """Hash regular files currently under CODEX_HOME/sessions."""

        sessions_root = self.codex_home / "sessions"
        if not sessions_root.is_dir():
            return {}
        snapshot: dict[Path, str] = {}
        for path in sessions_root.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            try:
                snapshot[path.resolve()] = sha256_file(path)
            except OSError:
                continue
        return snapshot

    def _collect_codex_sessions(
        self,
        run_dir: Path,
        attempt_number: int,
        before: Mapping[Path, str],
    ) -> dict[str, str]:
        """Copy only new or changed Codex rollout files into this run."""

        sessions_root = (self.codex_home / "sessions").resolve()
        after = self._snapshot_codex_sessions()
        run_root = run_dir.resolve()
        hashes: dict[str, str] = {}
        for source, digest in sorted(after.items(), key=lambda item: str(item[0])):
            if before.get(source) == digest:
                continue
            try:
                relative = source.relative_to(sessions_root)
            except ValueError:
                continue
            relative_destination = (
                Path("sessions") / f"attempt-{attempt_number:03d}" / relative
            )
            destination = (run_dir / relative_destination).resolve()
            if run_root not in destination.parents:
                raise ExecutionError(
                    f"Refusing to collect a Codex session outside run directory: "
                    f"{source}"
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            key = relative_destination.as_posix()
            hashes[key] = f"sha256:{sha256_file(destination)}"
        return hashes
