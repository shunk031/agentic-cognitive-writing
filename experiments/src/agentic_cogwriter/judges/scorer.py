"""Load runner artifacts, call a judge, and write hashed score artifacts."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..runner.hashing import sha256_bytes, sha256_file, sha256_json
from .client import ChatTransport
from .config import JudgeConfig
from .engine import JudgeResult, judge_pairwise, judge_pointwise
from .errors import RunArtifactError


@dataclass(frozen=True)
class RunArtifacts:
    """The runner files required to score one completed output."""

    run_dir: Path
    prompt_id: str
    condition_id: str
    platform: str
    assignment: str
    context: str
    output: str
    manifest: Mapping[str, Any]
    blind_condition_id: str


@dataclass(frozen=True)
class ScoreRunResult:
    """Paths written by one scoring invocation."""

    scores_path: Path
    manifest_path: Path
    result: JudgeResult


def blind_condition_id(condition_id: str) -> str:
    """Create a stable opaque label that does not expose the condition name."""

    return "blind-" + sha256_bytes(condition_id.encode("utf-8"))[:16]


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RunArtifactError(f"run manifest needs a non-empty {field}")
    return value


def _platform(manifest: Mapping[str, Any], run_dir: Path) -> str:
    inputs = manifest.get("inputs")
    value = inputs.get("platform") if isinstance(inputs, Mapping) else None
    if value is None and run_dir.parent.name in {
        "codex-primary",
        "claude-code-replication",
    }:
        value = run_dir.parent.name
    mapping = {
        "codex-primary": "codex",
        "claude-code-replication": "claude-code",
        "codex": "codex",
        "claude-code": "claude-code",
    }
    if value not in mapping:
        raise RunArtifactError("run manifest does not identify a supported platform")
    return mapping[value]


def _prompt_parts(path: Path) -> tuple[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RunArtifactError(f"Cannot read runner prompt artifact {path}") from exc
    assignment_marker = "Assignment:\n"
    context_marker = "\n\nSupplied context:\n"
    constraints_marker = "\n\nRequested output constraints:\n"
    if assignment_marker not in text or context_marker not in text:
        raise RunArtifactError(
            "runner prompt artifact does not contain Assignment and Supplied context"
        )
    assignment = text.split(assignment_marker, 1)[1].split(context_marker, 1)[0]
    context_start = text.split(context_marker, 1)[1]
    context = (
        context_start.split(constraints_marker, 1)[0]
        if constraints_marker in context_start
        else context_start
    )
    if context == "(none)":
        context = ""
    if not assignment.strip():
        raise RunArtifactError("runner prompt artifact has an empty assignment")
    return assignment, context


def load_run_artifacts(run_dir: Path) -> RunArtifacts:
    """Load and check the immutable files needed by the judge prompt."""

    run_dir = run_dir.resolve()
    manifest_path = run_dir / "run-manifest.json"
    output_path = run_dir / "output.normalized.txt"
    prompt_path = run_dir / "prompt.txt"
    if (
        not manifest_path.is_file()
        or not output_path.is_file()
        or not prompt_path.is_file()
    ):
        raise RunArtifactError(
            "completed run needs run-manifest.json, output.normalized.txt, "
            "and prompt.txt"
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RunArtifactError(f"Cannot read run manifest {manifest_path}") from exc
    if not isinstance(manifest, Mapping):
        raise RunArtifactError("run manifest must be a JSON object")
    if manifest.get("status") != "completed":
        raise RunArtifactError("judge scorer accepts only completed runs")
    scoring = manifest.get("scoring")
    if isinstance(scoring, Mapping) and scoring.get("status") != "eligible":
        raise RunArtifactError("run manifest marks this run as ineligible for scoring")
    inputs = manifest.get("inputs")
    if not isinstance(inputs, Mapping):
        raise RunArtifactError("run manifest needs an inputs object")
    prompt_id = _required_text(inputs.get("prompt_id"), "prompt_id")
    condition_id = _required_text(inputs.get("condition_id"), "condition_id")
    try:
        output = output_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RunArtifactError(f"Cannot read normalized output {output_path}") from exc
    assignment, context = _prompt_parts(prompt_path)
    return RunArtifacts(
        run_dir=run_dir,
        prompt_id=prompt_id,
        condition_id=condition_id,
        platform=_platform(manifest, run_dir),
        assignment=assignment,
        context=context,
        output=output,
        manifest=manifest,
        blind_condition_id=blind_condition_id(condition_id),
    )


def _pair_id(first: RunArtifacts, second: RunArtifacts) -> str:
    labels = sorted((first.blind_condition_id, second.blind_condition_id))
    return "pair-" + sha256_bytes("|".join(labels).encode("utf-8"))[:16]


def _pair_presentation(
    first: RunArtifacts, second: RunArtifacts, presentation: str
) -> tuple[str, str]:
    if presentation == "A|B":
        return first.output, second.output
    if presentation == "B|A":
        return second.output, first.output
    raise RunArtifactError("pairwise presentation must be A|B or B|A")


def _manifest_path(scores_path: Path) -> Path:
    return scores_path.with_name(scores_path.stem + "-manifest.json")


def score_run(
    run_dir: Path,
    config: JudgeConfig,
    *,
    compare_run_dir: Path | None = None,
    presentation: str | None = None,
    output_path: Path | None = None,
    transport: ChatTransport | None = None,
) -> ScoreRunResult:
    """Score one run and write an exact protocol JSON Lines record plus manifest."""

    first = load_run_artifacts(run_dir)
    source_runs: tuple[RunArtifacts, ...]
    if config.task == "pointwise":
        if compare_run_dir is not None or presentation is not None:
            raise RunArtifactError("pointwise scoring does not accept a comparison run")
        result = judge_pointwise(
            config,
            assignment=first.assignment,
            context=first.context,
            output=first.output,
            prompt_id=first.prompt_id,
            blind_condition_id=first.blind_condition_id,
            platform=first.platform,
            transport=transport,
        )
        source_runs = (first,)
    else:
        if compare_run_dir is None or presentation is None:
            raise RunArtifactError(
                "pairwise scoring needs --compare-run-dir and --presentation"
            )
        second = load_run_artifacts(compare_run_dir)
        if first.prompt_id != second.prompt_id or first.platform != second.platform:
            raise RunArtifactError("pairwise runs must share prompt ID and platform")
        if first.assignment != second.assignment or first.context != second.context:
            raise RunArtifactError("pairwise runs must share assignment and context")
        output_a, output_b = _pair_presentation(first, second, presentation)
        result = judge_pairwise(
            config,
            assignment=first.assignment,
            context=first.context,
            output_a=output_a,
            output_b=output_b,
            prompt_id=first.prompt_id,
            pair_id=_pair_id(first, second),
            presentation=presentation,
            platform=first.platform,
            transport=transport,
        )
        source_runs = (first, second)

    scores_path = (output_path or first.run_dir / "scores.jsonl").resolve()
    manifest_path = _manifest_path(scores_path)
    if scores_path.exists() or manifest_path.exists():
        raise RunArtifactError(
            "scoring output already exists; choose a new output path"
        )
    record_bytes = (
        json.dumps(result.record, ensure_ascii=False, sort_keys=True) + "\n"
    ).encode("utf-8")
    scores_path.parent.mkdir(parents=True, exist_ok=True)
    scores_path.write_bytes(record_bytes)
    score_manifest = {
        "schema_version": 1,
        "task": config.task,
        "scores_sha256": "sha256:" + sha256_file(scores_path),
        "template_sha256": "sha256:" + result.template_sha256,
        "judge": {
            "model": config.model,
            "judge_id": config.judge_id,
            "judge_family": config.judge_family,
            "seed": config.seed,
            "temperature": config.temperature,
            "top_p": config.top_p,
            "max_output_tokens": config.max_output_tokens,
            "stop_rules": list(config.stop_rules),
            "max_retries": config.max_retries,
        },
        "source_runs": [
            {
                "run_manifest_sha256": "sha256:"
                + sha256_file(item.run_dir / "run-manifest.json"),
                "output_sha256": "sha256:"
                + sha256_file(item.run_dir / "output.normalized.txt"),
            }
            for item in source_runs
        ],
        "records": [
            {
                "line": 1,
                "record_sha256": "sha256:" + sha256_json(result.record),
                "response_sha256": "sha256:" + result.response_sha256,
                "attempts": result.attempts,
                "usage": result.usage,
            }
        ],
    }
    manifest_path.write_text(
        json.dumps(score_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return ScoreRunResult(
        scores_path=scores_path,
        manifest_path=manifest_path,
        result=result,
    )
