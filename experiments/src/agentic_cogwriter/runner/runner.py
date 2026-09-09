"""Top-level condition execution and run-artifact production."""

from __future__ import annotations

import fcntl
import json
import math
import os
import re
import shutil
import stat
import tempfile
import time
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
    collect_plugin_trace,
    timestamp,
    validate_trace,
)


class Executor(Protocol):
    """Protocol implemented by real and test executors."""

    def run(
        self,
        command: list[str],
        *,
        cwd: Path,
        timeout_seconds: float,
        env: Mapping[str, str] | None = None,
    ) -> ExecutionResult:
        """Run one non-interactive command."""


@dataclass(frozen=True)
class RunResult:
    """Paths and metadata for one completed or failed run."""

    run_dir: Path
    manifest_path: Path
    output_path: Path
    trace_path: Path
    run_id: str


FINAL_OUTPUT_DRAFT_RATIO = 0.5
DEFAULT_PRODUCT_FLOOR = 10
_GENERATOR_CONFIG_ENV = {
    "codex": "CODEX_HOME",
    "claude-code": "CLAUDE_CONFIG_DIR",
}
_GENERATOR_CONFIG_ALLOWLIST = {
    "codex": ("config.toml", "auth.json"),
    "claude-code": (".credentials.json",),
}
_GUIDANCE_MARKERS = ("AGENTS.md", "CLAUDE.md", ".claude", ".codex")
_STAGE_TOKEN_PATTERN = re.compile(r"\{\{([^{}]+)\}\}")
_SHARED_STAGE_INPUT_BLOCK = re.compile(
    r"(?ms)^\s*Assignment:\n\{\{assignment\}\}\n\n"
    r"Supplied context:\n\{\{supplied_context\}\}\n\n"
    r"Requested output constraints:\n\{\{output_constraints\}\}\n?"
)
_SHARED_STAGE_TOKENS = (
    "assignment",
    "supplied_context",
    "output_constraints",
)
_STAGE_RENDERABLE_TOKENS = frozenset((*_SHARED_STAGE_TOKENS, "previous_stage_output"))


def _assert_guidance_free_workspace(workspace: Path) -> None:
    """Refuse a workspace whose ancestors can supply user or project guidance."""

    conflicts: list[Path] = []
    for ancestor in (workspace, *workspace.parents):
        for marker in _GUIDANCE_MARKERS:
            candidate = ancestor / marker
            try:
                mode = candidate.stat().st_mode
                present = (
                    stat.S_ISDIR(mode) if marker.startswith(".") else stat.S_ISREG(mode)
                )
            except FileNotFoundError:
                present = False
            except OSError as exc:
                raise ConfigurationError(
                    f"Cannot inspect guidance marker {candidate}"
                ) from exc
            if present:
                conflicts.append(candidate)
    if conflicts:
        markers = ", ".join(str(path) for path in conflicts)
        raise ConfigurationError(
            f"Refusing to start: workspace has guidance ancestors: {markers}"
        )


def _generator_model_family(runtime_config: RuntimeConfig, platform: str) -> str:
    """Resolve the selected generator model ID through the frozen family map."""

    return runtime_config.generator_model_family_for(platform)


def _safe_component(value: str) -> str:
    return "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value
    )


_TOML_BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")
_CODEX_PROVIDER_SCHEMA = {
    "name": "scalar",
    "base_url": "scalar",
    "wire_api": "scalar",
    "env_key": "scalar",
    "requires_openai_auth": "scalar",
    "http_headers": "string_map",
    "env_http_headers": "string_map",
    "query_params": "string_map",
    "auth": "table",
}
_CODEX_PROVIDER_DROPPED_KEYS = (
    "supports_standalone_web_search",
    "supports_websockets",
)
_CODEX_AUTH_SCHEMA = {
    "command": "string",
    "args": "string_array",
    "refresh_interval_ms": "integer",
}


def _toml_key(value: str, *, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigurationError(f"{context} must be a non-empty string")
    if _TOML_BARE_KEY.fullmatch(value):
        return value
    return json.dumps(value)


def _toml_scalar(value: Any, *, context: str) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value)
    raise ConfigurationError(
        f"{context} must be a string, boolean, or integer in the provider config"
    )


def _toml_string_map(value: Any, *, context: str) -> str:
    if not isinstance(value, Mapping):
        raise ConfigurationError(f"{context} must be a string-to-string map")
    entries: list[str] = []
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ConfigurationError(f"{context} must be a string-to-string map")
        entries.append(
            f"{_toml_key(key, context=f'{context} key')} = "
            f"{_toml_scalar(item, context=f'{context} value')}"
        )
    return "{ " + ", ".join(entries) + " }" if entries else "{}"


def _toml_string_array(value: Any, *, context: str) -> str:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ConfigurationError(f"{context} must be an array of strings")
    return (
        "["
        + ", ".join(_toml_scalar(item, context=f"{context} item") for item in value)
        + "]"
    )


def _toml_schema_value(value: Any, kind: str, *, context: str) -> str:
    if kind == "scalar":
        return _toml_scalar(value, context=context)
    if kind == "string":
        if not isinstance(value, str):
            raise ConfigurationError(f"{context} must be a string")
        return _toml_scalar(value, context=context)
    if kind == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ConfigurationError(f"{context} must be an integer")
        return str(value)
    if kind == "string_map":
        return _toml_string_map(value, context=context)
    if kind == "string_array":
        return _toml_string_array(value, context=context)
    raise ConfigurationError(f"Unknown Codex configuration schema kind {kind!r}")


def _synthesized_codex_config(
    source_config: Mapping[str, Any], reasoning_effort: str
) -> str:
    provider_name = source_config.get("model_provider")
    if not isinstance(provider_name, str) or not provider_name:
        raise ConfigurationError("Codex config must name a non-empty model_provider")
    providers = source_config.get("model_providers")
    if not isinstance(providers, Mapping) or provider_name not in providers:
        raise ConfigurationError(
            "Codex config model_provider "
            f"{provider_name!r} has no matching model_providers table"
        )
    provider = providers[provider_name]
    if not isinstance(provider, Mapping):
        raise ConfigurationError(
            f"Codex config model provider {provider_name!r} must be a table"
        )

    provider_key = _toml_key(provider_name, context="Codex config model_provider")
    lines = [
        f"model_provider = {_toml_scalar(provider_name, context='model_provider')}",
        "model_reasoning_effort = "
        f"{_toml_scalar(reasoning_effort, context='model_reasoning_effort')}",
        "",
        f"[model_providers.{provider_key}]",
    ]
    for key, value in provider.items():
        if key in _CODEX_PROVIDER_DROPPED_KEYS:
            continue
        kind = _CODEX_PROVIDER_SCHEMA.get(key)
        if kind is None:
            raise ConfigurationError(f"Codex provider key {key!r} is not allowed")
        if kind == "table":
            continue
        lines.append(
            f"{_toml_key(key, context='Codex provider key')} = "
            f"{_toml_schema_value(value, kind, context=f'Codex provider key {key!r}')}"
        )
    if "auth" in provider:
        auth = provider["auth"]
        if not isinstance(auth, Mapping):
            raise ConfigurationError("Codex provider auth must be a table")
        lines.extend(["", f"[model_providers.{provider_key}.auth]"])
        for key, value in auth.items():
            kind = _CODEX_AUTH_SCHEMA.get(key)
            if kind is None:
                raise ConfigurationError(
                    f"Codex provider auth key {key!r} is not allowed"
                )
            serialized_value = _toml_schema_value(
                value, kind, context=f"Codex provider auth key {key!r}"
            )
            lines.append(
                f"{_toml_key(key, context='Codex provider auth key')} = "
                f"{serialized_value}"
            )
    return "\n".join(lines) + "\n"


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
        claude_config_dir: Path | None = None,
    ):
        self.runtime_config = runtime_config
        self._process_started_at = time.time()
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
        configured_claude_config_dir = (
            claude_config_dir
            if claude_config_dir is not None
            else Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
        )
        self.claude_config_dir = configured_claude_config_dir.expanduser().resolve()

    def _load_adapters(self) -> dict[str, PlatformAdapter]:
        root = EXPERIMENTS_ROOT / "conditions" / "adapters"
        return {
            "codex": PlatformAdapter.load(root / "codex_exec.toml"),
            "claude-code": PlatformAdapter.load(root / "claude_print.toml"),
        }

    def _generator_config_parent(self) -> Path:
        config_parent = self.output_root / ".generator-config"
        try:
            parent_stat = config_parent.lstat()
        except FileNotFoundError:
            try:
                config_parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            except OSError as exc:
                raise ConfigurationError(
                    f"Cannot create generator configuration root {config_parent}"
                ) from exc
            try:
                parent_stat = config_parent.lstat()
            except OSError as exc:
                raise ConfigurationError(
                    f"Cannot inspect generator configuration root {config_parent}"
                ) from exc
        except OSError as exc:
            raise ConfigurationError(
                f"Cannot inspect generator configuration root {config_parent}"
            ) from exc

        if stat.S_ISLNK(parent_stat.st_mode):
            raise ConfigurationError(
                f"Generator configuration root {config_parent} must not be a symlink"
            )
        if not stat.S_ISDIR(parent_stat.st_mode):
            raise ConfigurationError(
                f"Generator configuration root {config_parent} must be a directory"
            )
        try:
            config_parent.resolve().relative_to(self.output_root.resolve())
        except ValueError as exc:
            raise ConfigurationError(
                "Generator configuration root "
                f"{config_parent} must remain inside output root {self.output_root}"
            ) from exc
        return config_parent

    def _acquire_generator_config_lock(self):
        config_parent = self._generator_config_parent()
        lock_path = config_parent / ".lock"
        try:
            lock_fd = os.open(
                lock_path,
                os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC,
                0o600,
            )
            if not stat.S_ISREG(os.fstat(lock_fd).st_mode):
                os.close(lock_fd)
                lock_fd = -1
                raise ConfigurationError(
                    f"Generator configuration lock {lock_path} must be a regular file"
                )
            lock_file = os.fdopen(lock_fd, "a+", encoding="utf-8")
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            if "lock_file" in locals():
                lock_file.close()
            elif "lock_fd" in locals():
                os.close(lock_fd)
            raise ConfigurationError(
                f"Cannot acquire generator configuration lock {lock_path}: "
                "another run holds the output root"
            ) from exc
        except OSError as exc:
            if "lock_file" in locals():
                lock_file.close()
            elif "lock_fd" in locals():
                os.close(lock_fd)
            raise ConfigurationError(
                f"Cannot acquire generator configuration lock {lock_path}"
            ) from exc
        return lock_file

    @staticmethod
    def _release_generator_config_lock(lock_file) -> None:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        finally:
            lock_file.close()

    def _prepare_generator_environment(
        self, platform: str, *, run_id: str, lock_file=None
    ) -> tuple[Path, dict[str, str]]:
        owns_lock = lock_file is None
        if owns_lock:
            lock_file = self._acquire_generator_config_lock()
        try:
            return self._prepare_generator_environment_locked(platform, run_id=run_id)
        finally:
            if owns_lock:
                self._release_generator_config_lock(lock_file)

    def _prepare_generator_environment_locked(
        self, platform: str, *, run_id: str
    ) -> tuple[Path, dict[str, str]]:
        """Build one per-run provider home and its child process environment."""

        config_root = self.output_root / ".generator-config" / _safe_component(run_id)
        temporary_root = Path(tempfile.gettempdir()).resolve()
        try:
            resolved_config_root = config_root.resolve()
            resolved_config_root.relative_to(temporary_root)
        except ValueError:
            pass
        else:
            raise ConfigurationError(
                "Generator configuration root "
                f"{resolved_config_root} is under the system temporary directory "
                f"{temporary_root}"
            )

        self._sweep_stale_generator_configs()
        source_root = self.codex_home if platform == "codex" else self.claude_config_dir
        created_config_root = False
        try:
            config_root.mkdir(mode=0o700, parents=True, exist_ok=False)
            created_config_root = True
            for filename in _GENERATOR_CONFIG_ALLOWLIST[platform]:
                source = source_root / filename
                try:
                    present = source.is_file()
                except OSError as exc:
                    raise ConfigurationError(
                        f"Cannot inspect provider file {source}"
                    ) from exc
                if not present:
                    continue
                try:
                    destination = config_root / filename
                    if platform == "codex" and filename == "config.toml":
                        try:
                            source_config = tomllib.loads(
                                source.read_text(encoding="utf-8")
                            )
                        except (OSError, tomllib.TOMLDecodeError) as exc:
                            raise ConfigurationError(
                                f"Cannot parse Codex config {source}"
                            ) from exc
                        destination.write_text(
                            _synthesized_codex_config(
                                source_config,
                                self.runtime_config.codex_reasoning_effort,
                            ),
                            encoding="utf-8",
                        )
                    else:
                        shutil.copy2(source, destination)
                except OSError as exc:
                    raise ConfigurationError(
                        f"Cannot copy provider file {source} to {config_root}"
                    ) from exc
        except Exception:
            if created_config_root:
                shutil.rmtree(config_root, ignore_errors=True)
            raise

        child_environment = dict(os.environ)
        child_environment[_GENERATOR_CONFIG_ENV[platform]] = str(config_root.resolve())
        return config_root, child_environment

    def _sweep_stale_generator_configs(self) -> None:
        """Remove provider roots left by an earlier process invocation."""

        config_parent = self._generator_config_parent()
        try:
            entries = tuple(config_parent.iterdir())
        except FileNotFoundError:
            return
        except OSError as exc:
            raise ConfigurationError(
                f"Cannot inspect generator configuration root {config_parent}"
            ) from exc

        for entry in entries:
            if entry.name == ".lock":
                continue
            try:
                entry_stat = entry.lstat()
            except FileNotFoundError:
                continue
            except OSError as exc:
                raise ConfigurationError(
                    f"Cannot inspect stale generator configuration {entry}"
                ) from exc
            if entry_stat.st_mtime >= self._process_started_at:
                continue
            try:
                if stat.S_ISDIR(entry_stat.st_mode):
                    shutil.rmtree(entry)
                else:
                    entry.unlink()
            except OSError as exc:
                raise ConfigurationError(
                    f"Cannot remove stale generator configuration {entry}"
                ) from exc

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
        _generator_model_family(self.runtime_config, platform)

        run_id = run_id or uuid.uuid4().hex
        generator_config_lock = self._acquire_generator_config_lock()
        try:
            run_dir = (
                self.output_root
                / _safe_component(prompt.benchmark_name)
                / _safe_component(condition_id)
                / _safe_component(platform)
                / _safe_component(run_id)
            ).resolve()
            workspace = run_dir / "workspace"
            _assert_guidance_free_workspace(workspace)
            run_dir.mkdir(parents=True, exist_ok=False)
            workspace.mkdir()
            # Pre-create the trace directory so skills anchor `.writing/` writes
            # to the workspace instead of the plugin or skill directory.
            (workspace / ".writing" / "trace").mkdir(parents=True)
            generator_config_dir, generator_environment = (
                self._prepare_generator_environment(
                    platform, run_id=run_id, lock_file=generator_config_lock
                )
            )
        except BaseException:
            self._release_generator_config_lock(generator_config_lock)
            raise
        preflight_ready = False
        try:
            manifest_path = run_dir / "run-manifest.json"
            output_path = run_dir / "output.raw"
            normalized_path = run_dir / "output.normalized.txt"
            trace_path = workspace / ".writing" / "trace" / "process.jsonl"
            prompt_path = run_dir / "prompt.txt"
            execution_paths = {
                "cwd": str(workspace.resolve()),
                "prompt": str(prompt_path.resolve()),
                "trace_path": str(trace_path.resolve()),
                "generator_config_dir": str(generator_config_dir.resolve()),
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
            command_prompt = self._plugin_prompt(
                condition,
                prompt,
                platform,
                codex_prompt_root=Path("plugin"),
            )
            benchmark_provenance = load_benchmark_provenance(prompt.benchmark_name)
            protected_goals = workspace / ".writing" / "goals.md"
            goals_before = (
                protected_goals.read_bytes() if protected_goals.is_file() else None
            )
            preflight_ready = True
        finally:
            if not preflight_ready:
                shutil.rmtree(generator_config_dir, ignore_errors=True)
                self._release_generator_config_lock(generator_config_lock)

        try:
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
            cli_version = self._probe_cli(adapter)
            expected_version = self._expected_cli_version(platform)
            if cli_version != expected_version:
                raise ConfigurationError(
                    f"Installed {platform} CLI version {cli_version!r} does not match "
                    f"pinned version {expected_version!r}"
                )
            if platform == "codex":
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
                if platform == "codex":
                    collection = self._collect_codex_sessions(
                        run_dir,
                        attempt_number,
                        session_before
                        or SessionSnapshot(files={}, present=False, error=None),
                        generator_config_dir,
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
                if result is not None and platform == "codex":
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
                env=generator_environment,
                attempts=attempts,
                plugin_dirs=(
                    self._plugin_dirs(condition) if platform != "codex" else ()
                ),
                record_attempt=record_attempt,
                snapshot_sessions=(
                    (lambda: self._snapshot_codex_sessions(generator_config_dir))
                    if platform == "codex"
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
                    output_hash=f"sha256:{sha256_file(output_path)}",
                    trace_hash=f"sha256:{sha256_file(copied_trace)}",
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
        finally:
            shutil.rmtree(generator_config_dir, ignore_errors=True)
            self._release_generator_config_lock(generator_config_lock)

    def _probe_cli(self, adapter: PlatformAdapter) -> str:
        if isinstance(self.executor, SubprocessExecutor):
            return adapter.probe_version(
                timeout_seconds=self.runtime_config.timeout_seconds
            )
        key = "codex_version" if adapter.platform == "codex" else "claude_code_version"
        return str(self.runtime_config.get(key))

    def _expected_cli_version(self, platform: str) -> str:
        key = "codex_version" if platform == "codex" else "claude_code_version"
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
        env: Mapping[str, str],
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
                    env=env,
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
        if platform == "codex":
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
        shared_values = {
            "assignment": prompt.input_text,
            "supplied_context": prompt.supplied_context or "(none)",
            "output_constraints": constraints,
        }
        stage_text, carried_tokens = self._stage_prompt_text(condition, shared_values)
        generic_values = [
            f"Assignment:\n{shared_values['assignment']}",
            f"Supplied context:\n{shared_values['supplied_context']}",
            f"Requested output constraints:\n{shared_values['output_constraints']}",
        ]
        generic_block = "\n\n".join(
            value
            for token, value in zip(_SHARED_STAGE_TOKENS, generic_values, strict=True)
            if token not in carried_tokens
        )
        if generic_block:
            generic_block = f"\n\n{generic_block}"
        return f"{invocation}{generic_block}{stage_text}"

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

    def _stage_prompt_text(
        self, condition: ConditionSpec, shared_values: Mapping[str, str]
    ) -> tuple[str, set[str]]:
        """Render committed stage instructions without changing their files."""

        chunks: list[str] = []
        carried_tokens: set[str] = set()
        for stage_index, stage in enumerate(condition.stages):
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
            tokens = _STAGE_TOKEN_PATTERN.findall(content)
            for token in tokens:
                if token not in _STAGE_RENDERABLE_TOKENS:
                    raise ConfigurationError(
                        f"Cannot render token {{{{{token}}}}} in frozen prompt file "
                        f"{stage.path}"
                    )

            stage_values = dict(shared_values)
            stage_values["previous_stage_output"] = (
                "(none; this is the first stage)"
                if stage_index == 0
                else "(the output produced by the preceding stage in this session)"
            )
            if carried_tokens & set(_SHARED_STAGE_TOKENS):
                content = _SHARED_STAGE_INPUT_BLOCK.sub("", content)

            def render_token(
                match: re.Match[str],
                *,
                stage_values: Mapping[str, str] = stage_values,
            ) -> str:
                token = match.group(1)
                if token in _SHARED_STAGE_TOKENS:
                    if token in carried_tokens:
                        return ""
                    carried_tokens.add(token)
                return stage_values[token]

            content = _STAGE_TOKEN_PATTERN.sub(render_token, content)
            chunks.append(f"\n\nFrozen stage {stage.stage_id}:\n{content}")
        return "".join(chunks), carried_tokens

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

        configured_roots = self._configured_plugin_paths(condition)
        if self.codex_plugin_root is None:
            return configured_roots
        explicit_root = self.codex_plugin_root.resolve()
        return (
            explicit_root,
            *tuple(root for root in configured_roots if root != explicit_root),
        )

    def _codex_plugin_root(self, condition: ConditionSpec) -> Path:
        """Select the root containing the skill file referenced by Codex."""

        skill_relative = Path("skills") / condition.skill_name / "SKILL.md"
        if self.codex_plugin_root is not None:
            explicit_root = self.codex_plugin_root.resolve()
            if not (explicit_root / skill_relative).is_file():
                raise ConfigurationError(
                    f"Explicit Codex plugin root {explicit_root} does not contain "
                    f"the invoked skill {condition.skill_name!r}"
                )
            return explicit_root

        paths = self._codex_source_roots(condition)
        for path in paths:
            if (path / skill_relative).is_file():
                return path
        if paths:
            return paths[0]
        raise ManifestError(
            f"Plugin wrapper {condition.plugin_config} has no configured plugin path"
        )

    _CODEX_ROLE_SKILL_DIRECTORIES = tuple(
        Path("skills") / role for role in ("planning", "translating", "reviewing")
    )
    _CODEX_DELEGATED_SKILL_DIRECTORIES = {
        "agentic-cog-writer": _CODEX_ROLE_SKILL_DIRECTORIES,
        "cognitive-writing-no-goal-network": _CODEX_ROLE_SKILL_DIRECTORIES,
        "cognitive-writing-fixed-order": _CODEX_ROLE_SKILL_DIRECTORIES,
    }

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
        required_directories = [
            Path("skills") / condition.skill_name,
            *self._CODEX_DELEGATED_SKILL_DIRECTORIES.get(condition.skill_name, ()),
        ]
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
        if platform == "codex":
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
                "platform": platform,
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
                "generator_model_family": _generator_model_family(
                    self.runtime_config, platform
                ),
                "frontier_judge_model_id": self.runtime_config.get(
                    "codex_frontier_judge"
                    if platform == "codex"
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
                    "codex_reasoning_effort": self.runtime_config.get(
                        "codex_reasoning_effort"
                    ),
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
                    "judge_side": (
                        "API judge client has no retrieval or tool interface; "
                        "score-stage validation is recorded in the score manifest"
                    ),
                },
                "judge_verification": {
                    "judge_families": "runtime-verified in the score manifest",
                    "family_overlap_audit": "runtime-verified in the score manifest",
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
        # Carry native criteria in the existing run-manifest input so the judge
        # can score the immutable row without reopening or refetching its source.
        if prompt.native_payload is not None:
            manifest["inputs"]["native_payload"] = prompt.native_payload
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

    def _snapshot_codex_sessions(
        self, codex_home: Path | None = None
    ) -> SessionSnapshot:
        """Hash readable files currently under CODEX_HOME/sessions."""

        sessions_root = (codex_home or self.codex_home) / "sessions"
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
        codex_home: Path,
    ) -> SessionCollection:
        """Copy only new or changed Codex rollout files into this run."""

        sessions_root = (codex_home / "sessions").resolve()
        after = self._snapshot_codex_sessions(codex_home)
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
