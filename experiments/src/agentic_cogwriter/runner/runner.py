"""Top-level condition execution and run-artifact production."""

from __future__ import annotations

import json
import math
import os
import re
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
    BudgetExceeded,
    ConfigurationError,
    ExecutionError,
    ManifestError,
    RetrievalViolation,
    UnscoredRun,
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
DEFAULT_PRODUCT_FLOOR = 10


def _safe_component(value: str) -> str:
    return "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value
    )


def _validate_final_product(
    output: str,
    draft: str | None,
    *,
    condition_id: str,
    requires_draft: bool,
    minimum_units: int | None,
    count_units: Callable[[str], int],
) -> None:
    """Require the response channel to carry the complete product text."""

    final_chars = len(output.strip())
    if not final_chars:
        raise ExecutionError(
            f"Condition {condition_id} produced no final response; "
            "draft.md is not accepted as a substitute"
        )
    if requires_draft and draft is None:
        raise ExecutionError(
            f"Condition {condition_id} requires workspace/.writing/draft.md; "
            "the final response cannot substitute for a missing draft"
        )
    if requires_draft and draft is not None:
        draft_chars = len(draft.strip())
        if final_chars < draft_chars * FINAL_OUTPUT_DRAFT_RATIO:
            raise ExecutionError(
                f"Condition {condition_id} final response is less than "
                f"{FINAL_OUTPUT_DRAFT_RATIO:.0%} of draft.md; "
                f"final_chars={final_chars}, draft_chars={draft_chars}"
            )
    if requires_draft or minimum_units is None:
        return
    output_units = count_units(output)
    if output_units < minimum_units:
        raise ExecutionError(
            f"Condition {condition_id} final response fails the completeness floor; "
            f"output_units={output_units}, minimum_units={minimum_units}"
        )


def _requested_length(prompt: PromptRecord) -> int | None:
    """Extract a numeric requested length from constraints or assignment text."""

    candidates: list[str] = []
    constraints = prompt.requested_output_constraints
    if isinstance(constraints, Mapping):
        for key in (
            "min_words",
            "minimum_words",
            "target_words",
            "word_count",
            "max_words",
            "min_tokens",
            "minimum_tokens",
            "target_tokens",
            "max_tokens",
        ):
            value = constraints.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return max(1, math.ceil(value))
    candidates.append(json.dumps(constraints, ensure_ascii=False))
    if prompt.prompt_text is not None:
        candidates.append(prompt.prompt_text)
    match = re.search(
        r"(?i)\b(\d[\d,]*)\s*[- ]?(?:word|words|token|tokens)\b",
        "\n".join(candidates),
    )
    if match is None:
        return None
    return int(match.group(1).replace(",", ""))


def _product_gate(
    prompt: PromptRecord, condition: ConditionSpec, config: RuntimeConfig
) -> dict[str, Any]:
    """Describe the product completeness rule persisted in each run manifest."""

    if condition.product_requires_draft:
        return {
            "requires_draft": True,
            "rule": (
                "workspace/.writing/draft.md must exist and the final response "
                "must be at least 50% of its characters"
            ),
            "minimum_units": None,
            "unit": config.output_unit,
        }
    requested_length = _requested_length(prompt)
    if requested_length is None:
        return {
            "requires_draft": False,
            "rule": (
                "at least 10 output units when the assignment has no requested length"
            ),
            "minimum_units": DEFAULT_PRODUCT_FLOOR,
            "unit": config.output_unit,
        }
    return {
        "requires_draft": False,
        "rule": "at least 50% of the requested length, with a 10-unit minimum",
        "minimum_units": max(DEFAULT_PRODUCT_FLOOR, math.ceil(requested_length * 0.5)),
        "unit": config.output_unit,
    }


@dataclass(frozen=True)
class SessionSnapshot:
    """State of the Codex rollout directory at one attempt boundary."""

    files: Mapping[Path, str]
    present: bool
    error: str | None


@dataclass(frozen=True)
class SessionCollection:
    """Result of collecting rollout files created or changed by an attempt."""

    hashes: dict[str, str]
    status: str
    reason: str | None = None


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
        product_gate = _product_gate(prompt, condition, self.runtime_config)
        attempts = 0
        evidence_hashes: dict[str, str] = {}
        staged_files: dict[str, str] = {}
        token_usage: dict[str, int] | None = None
        token_accounting_error: str | None = None
        subagent_spawn_ids: set[str] = set()
        rollout_collection: dict[str, Any] = {
            "status": "absent",
            "reason": "no Codex rollout files collected",
            "source": "CODEX_HOME/sessions",
        }
        spawn_extraction: dict[str, Any] = {
            "status": "absent",
            "reason": "no attempt event stream collected",
            "source": "Codex JSONL event stream",
        }
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
                product_gate=product_gate,
                token_accounting_error=token_accounting_error,
                rollout_collection=rollout_collection,
                spawn_extraction=spawn_extraction,
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
                    product_gate=product_gate,
                    token_accounting_error=token_accounting_error,
                    rollout_collection=rollout_collection,
                    spawn_extraction=spawn_extraction,
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
                    product_gate=product_gate,
                    token_usage=token_usage,
                    token_accounting_error=token_accounting_error,
                    subagent_spawn_count=len(subagent_spawn_ids),
                    rollout_collection=rollout_collection,
                    spawn_extraction=spawn_extraction,
                ),
            )

            def record_attempt(
                attempt_number: int,
                result: ExecutionResult | None,
                session_before: SessionSnapshot | None,
            ) -> None:
                nonlocal attempts, rollout_collection, spawn_extraction
                nonlocal token_usage, token_accounting_error
                attempts = max(attempts, attempt_number)
                evidence_hashes.update(
                    self._persist_attempt_evidence(run_dir, attempt_number, result)
                )
                if platform == "codex-primary":
                    collection = self._collect_codex_sessions(
                        run_dir,
                        attempt_number,
                        session_before
                        or SessionSnapshot(files={}, present=False, error=None),
                    )
                    evidence_hashes.update(collection.hashes)
                    if collection.status == "error":
                        rollout_collection = {
                            "status": collection.status,
                            "reason": collection.reason,
                            "source": "CODEX_HOME/sessions",
                        }
                        raise UnscoredRun(
                            collection.reason or "Codex rollout collection failed"
                        )
                    elif rollout_collection["status"] != "error":
                        if collection.status == "complete":
                            rollout_collection = {
                                "status": "complete",
                                "reason": None,
                                "source": "CODEX_HOME/sessions",
                            }
                        elif rollout_collection["status"] != "complete":
                            rollout_collection = {
                                "status": "absent",
                                "reason": collection.reason,
                                "source": "CODEX_HOME/sessions",
                            }
                attempt_events_path = (
                    run_dir / f"attempt-{attempt_number:03d}.events.jsonl"
                )
                if result is None:
                    spawn_extraction = {
                        "status": "absent",
                        "reason": "executor produced no event stream",
                        "source": "Codex JSONL event stream",
                    }
                else:
                    reject_retrieval(result.stdout, result.stderr)
                    try:
                        subagent_spawn_ids.update(
                            _subagent_spawn_ids(attempt_events_path.read_bytes())
                        )
                    except ExecutionError as exc:
                        spawn_extraction = {
                            "status": "error",
                            "reason": str(exc),
                            "source": "Codex JSONL event stream",
                        }
                        raise
                    spawn_extraction = {
                        "status": "complete",
                        "reason": None,
                        "source": "Codex JSONL event stream",
                    }
                if result is not None and platform == "codex-primary":
                    try:
                        observed_usage = extract_token_usage(result.stdout)
                    except ExecutionError as exc:
                        token_accounting_error = str(exc)
                        observed_usage = None
                    if observed_usage is not None:
                        if token_usage is None:
                            token_usage = {
                                "output_tokens": 0,
                                "reasoning_output_tokens": 0,
                                "total_tokens": 0,
                            }
                        for key, value in observed_usage.items():
                            token_usage[key] += value
                        if token_usage["total_tokens"] > budget.limit:
                            raise BudgetExceeded(
                                "Codex turn usage exceeds the shared output "
                                f"budget: used={token_usage['total_tokens']}, "
                                f"limit={budget.limit}"
                            )
                    if (
                        result.returncode == 0
                        and not result.timed_out
                        and token_accounting_error is not None
                    ):
                        raise UnscoredRun(token_accounting_error)
                if subagent_spawn_ids and rollout_collection["status"] != "complete":
                    raise UnscoredRun(
                        "Subagent spawn events were observed but no complete "
                        "Codex rollout collection is available"
                    )
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
                        product_gate=product_gate,
                        token_accounting_error=token_accounting_error,
                        rollout_collection=rollout_collection,
                        spawn_extraction=spawn_extraction,
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
                reject_retrieval(
                    draft.encode("utf-8"),
                    b"",
                    scan_artifact_text=True,
                    artifact_source="draft",
                )
            reject_retrieval(output.encode("utf-8"), b"")
            budget.consume(
                self.runtime_config.count_output_units(output), stage="final_output"
            )
            _validate_final_product(
                output,
                draft,
                condition_id=condition.condition_id,
                requires_draft=condition.product_requires_draft,
                minimum_units=product_gate["minimum_units"],
                count_units=self.runtime_config.count_output_units,
            )
            if condition.goal_events == "forbidden":
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
                declared_processes=condition.trace_processes,
                goal_events=condition.goal_events,
                allowed_event_types=condition.event_types,
                min_events=condition.min_events,
                max_events=condition.max_events,
                process_order=condition.process_order,
                require_goal_events=condition.require_goal_events,
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
                    product_gate=product_gate,
                    token_accounting_error=token_accounting_error,
                    rollout_collection=rollout_collection,
                    spawn_extraction=spawn_extraction,
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
                artifact_suffix = (
                    exc.artifact_source
                    if exc.artifact_source != "transport"
                    else stream
                )
                artifact_name = f"rejected-output.{artifact_suffix}"
                artifact_path = run_dir / artifact_name
                artifact_path.write_bytes(exc.payload)
                failure["retrieval"] = {
                    "artifact": artifact_name,
                    "matched_pattern": exc.matched_pattern,
                    "matching_line": exc.matching_line,
                    "sha256": f"sha256:{sha256_bytes(exc.payload)}",
                    "stream": stream,
                    "artifact_source": exc.artifact_source,
                }
            failure_artifacts = ["prompt.txt", *evidence_hashes]
            if isinstance(exc, RetrievalViolation):
                artifact_suffix = (
                    exc.artifact_source
                    if exc.artifact_source != "transport"
                    else (exc.stream or "stdout")
                )
                failure_artifacts.append(f"rejected-output.{artifact_suffix}")
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
                    status=(
                        "unscored"
                        if isinstance(exc, UnscoredRun)
                        or token_accounting_error is not None
                        or rollout_collection["status"] == "error"
                        or spawn_extraction["status"] == "error"
                        else "failed"
                    ),
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
                    product_gate=product_gate,
                    token_accounting_error=token_accounting_error,
                    rollout_collection=rollout_collection,
                    spawn_extraction=spawn_extraction,
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
        record_attempt: Callable[
            [int, ExecutionResult | None, SessionSnapshot | None], None
        ]
        | None = None,
        snapshot_sessions: Callable[[], SessionSnapshot] | None = None,
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
        product_gate: Mapping[str, Any] | None = None,
        token_accounting_error: str | None = None,
        rollout_collection: Mapping[str, Any] | None = None,
        spawn_extraction: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        wrapper_hash = f"sha256:{sha256_file(condition.plugin_config)}"
        if platform == "codex-primary":
            if token_accounting_error is not None:
                token_accounting_status = "unscored"
            elif token_usage is not None:
                token_accounting_status = "observed"
            else:
                token_accounting_status = "monitored-only"
        else:
            token_accounting_status = "not_applicable"
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
                "trace_contract": {
                    "goal_events": condition.goal_events,
                    "event_types": list(condition.event_types),
                    "min_events": condition.min_events,
                    "max_events": condition.max_events,
                    "processes": list(condition.trace_processes),
                    "process_order": (
                        list(condition.process_order)
                        if condition.process_order is not None
                        else None
                    ),
                    "require_goal_events": condition.require_goal_events,
                },
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
                    "secondary_tripwire": (
                        "parsed retrieval/tool-invocation and executed-command "
                        "scan; explicit network-command scan for draft artifacts"
                    ),
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
                "status": token_accounting_status,
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
            "product_gate": dict(
                product_gate or _product_gate(prompt, condition, self.runtime_config)
            ),
            "rollout_collection": dict(
                rollout_collection
                or {
                    "status": "absent",
                    "reason": "no Codex rollout files collected",
                    "source": "CODEX_HOME/sessions",
                }
            ),
            "spawn_extraction": dict(
                spawn_extraction
                or {
                    "status": "absent",
                    "reason": "no attempt event stream collected",
                    "source": "Codex JSONL event stream",
                }
            ),
            "scoring": {
                "status": (
                    "eligible"
                    if status == "completed"
                    else "pending"
                    if status == "started"
                    else "excluded"
                )
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
        if token_accounting_error is not None:
            manifest["token_accounting"]["error"] = token_accounting_error
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

    def _snapshot_codex_sessions(self) -> SessionSnapshot:
        """Hash readable files currently under CODEX_HOME/sessions."""

        sessions_root = self.codex_home / "sessions"
        try:
            present = sessions_root.is_dir()
        except OSError as exc:
            return SessionSnapshot(files={}, present=True, error=str(exc))
        if not present:
            return SessionSnapshot(files={}, present=False, error=None)
        snapshot: dict[Path, str] = {}
        error: str | None = None
        try:
            paths = sessions_root.rglob("*")
            for path in paths:
                if not path.is_file() or path.is_symlink():
                    continue
                try:
                    snapshot[path.resolve()] = sha256_file(path)
                except OSError as exc:
                    error = error or f"Cannot read rollout {path}: {exc}"
        except OSError as exc:
            error = error or f"Cannot inspect rollout directory {sessions_root}: {exc}"
        return SessionSnapshot(files=snapshot, present=True, error=error)

    def _collect_codex_sessions(
        self,
        run_dir: Path,
        attempt_number: int,
        before: SessionSnapshot,
    ) -> SessionCollection:
        """Copy only new or changed Codex rollout files into this run."""

        sessions_root = (self.codex_home / "sessions").resolve()
        after = self._snapshot_codex_sessions()
        if before.error is not None or after.error is not None:
            return SessionCollection(
                hashes={},
                status="error",
                reason=before.error or after.error,
            )
        if not after.present:
            return SessionCollection(
                hashes={},
                status="absent",
                reason="CODEX_HOME/sessions is absent",
            )
        run_root = run_dir.resolve()
        hashes: dict[str, str] = {}
        for source, digest in sorted(
            after.files.items(), key=lambda item: str(item[0])
        ):
            if before.files.get(source) == digest:
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
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
            except OSError as exc:
                return SessionCollection(
                    hashes=hashes,
                    status="error",
                    reason=f"Cannot collect rollout {source}: {exc}",
                )
            key = relative_destination.as_posix()
            try:
                hashes[key] = f"sha256:{sha256_file(destination)}"
            except OSError as exc:
                return SessionCollection(
                    hashes=hashes,
                    status="error",
                    reason=f"Cannot hash collected rollout {destination}: {exc}",
                )
        if not hashes:
            return SessionCollection(
                hashes={},
                status="absent",
                reason="No new or changed Codex rollout files were collected",
            )
        return SessionCollection(hashes=hashes, status="complete")
