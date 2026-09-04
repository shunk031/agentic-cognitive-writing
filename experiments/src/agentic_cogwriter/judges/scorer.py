"""Load runner artifacts, call a judge, and write hashed score artifacts."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic_ai.models import Model

from ..runner.hashing import sha256_bytes, sha256_file, sha256_json
from .config import JudgeConfig
from .engine import (
    JudgeResult,
    judge_native_pointwise,
    judge_pairwise,
    judge_pointwise,
)
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
    generator_model_id: str
    generator_family: str
    native_payload: Any | None


@dataclass(frozen=True)
class ScoreRunResult:
    """Paths written by one scoring invocation."""

    scores_path: Path
    manifest_path: Path
    result: JudgeResult
    results: tuple[JudgeResult, ...]


def blind_condition_id(condition_id: str) -> str:
    """Create a stable opaque label that does not expose the condition name."""

    return "blind-" + sha256_bytes(condition_id.encode("utf-8"))[:16]


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RunArtifactError(f"run manifest needs a non-empty {field}")
    return value


def _platform(manifest: Mapping[str, Any]) -> str:
    inputs = manifest.get("inputs")
    value = inputs.get("platform") if isinstance(inputs, Mapping) else None
    if value not in {"codex", "claude-code"}:
        raise RunArtifactError("run manifest does not identify a supported platform")
    return value


def _generator_evidence(manifest: Mapping[str, Any]) -> tuple[str, str]:
    models = manifest.get("models_and_execution")
    if not isinstance(models, Mapping):
        raise RunArtifactError("run manifest needs models_and_execution evidence")
    model_id = _required_text(models.get("generator_model_id"), "generator_model_id")
    family = _required_text(
        models.get("generator_model_family"), "generator_model_family"
    )
    return model_id, family


def _native_criteria(run: RunArtifacts) -> tuple[dict[str, str], ...]:
    """Validate the WritingBench checklist before making any native calls."""

    inputs = run.manifest.get("inputs")
    benchmark_name = (
        inputs.get("benchmark_name") if isinstance(inputs, Mapping) else None
    )
    if benchmark_name != "WritingBench":
        raise RunArtifactError("native-pointwise scoring requires a WritingBench run")
    payload = run.native_payload
    required = {
        "name",
        "criteria_description",
        "1-2",
        "3-4",
        "5-6",
        "7-8",
        "9-10",
    }
    if not isinstance(payload, list) or not payload:
        raise RunArtifactError("WritingBench run manifest needs a native checklist")
    criteria: list[dict[str, str]] = []
    for criterion in payload:
        if not isinstance(criterion, Mapping) or set(criterion) != required:
            raise RunArtifactError("WritingBench native checklist has invalid fields")
        if not all(
            isinstance(value, str) and value.strip() for value in criterion.values()
        ):
            raise RunArtifactError("WritingBench native checklist has invalid values")
        criteria.append({key: criterion[key] for key in required})
    return tuple(criteria)


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
    generator_model_id, generator_family = _generator_evidence(manifest)
    return RunArtifacts(
        run_dir=run_dir,
        prompt_id=prompt_id,
        condition_id=condition_id,
        platform=_platform(manifest),
        assignment=assignment,
        context=context,
        output=output,
        manifest=manifest,
        blind_condition_id=blind_condition_id(condition_id),
        generator_model_id=generator_model_id,
        generator_family=generator_family,
        native_payload=inputs.get("native_payload"),
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


def _presentation_orders(pair_id: str, seed: int) -> tuple[str, str]:
    """Derive a stable invocation order while retaining both presentations."""

    orders = ("A|B", "B|A")
    digest = sha256_bytes(f"{seed}:{pair_id}".encode())
    return orders if int(digest[-1], 16) % 2 == 0 else (orders[1], orders[0])


def _family_audit(
    config: JudgeConfig, result: JudgeResult, run: RunArtifacts
) -> dict[str, str]:
    config.validate_family_audit(result.judge_identity, run.generator_family)
    return {
        "reported_model_id": result.judge_identity.reported_model_id,
        "mapped_family": result.judge_identity.mapped_family,
        "judge_family": result.judge_identity.judge_family,
        "generator_model_id": run.generator_model_id,
        "generator_family": run.generator_family,
    }


def _score_pairwise_presentation(
    first: RunArtifacts,
    second: RunArtifacts,
    config: JudgeConfig,
    *,
    pair_id: str,
    presentation: str,
    model: Model | None,
    prompt_cache_key: str,
) -> JudgeResult:
    output_a, output_b = _pair_presentation(first, second, presentation)
    return judge_pairwise(
        config,
        assignment=first.assignment,
        context=first.context,
        output_a=output_a,
        output_b=output_b,
        prompt_id=first.prompt_id,
        pair_id=pair_id,
        presentation=presentation,
        platform=first.platform,
        model=model,
        # Share one cache namespace across A|B and B|A for this run pair.
        prompt_cache_key=prompt_cache_key,
    )


def _write_score_artifacts(
    scores_path: Path,
    config: JudgeConfig,
    source_runs: tuple[RunArtifacts, ...],
    results: tuple[JudgeResult, ...],
    family_audit: dict[str, str],
    tournament: dict[str, Any] | None = None,
) -> ScoreRunResult:
    """Write score records only after every required judgment has succeeded."""

    manifest_path = _manifest_path(scores_path)
    if scores_path.exists() or manifest_path.exists():
        raise RunArtifactError(
            "scoring output already exists; choose a new output path"
        )
    record_bytes = b"".join(
        (json.dumps(result.record, ensure_ascii=False, sort_keys=True) + "\n").encode(
            "utf-8"
        )
        for result in results
    )
    scores_path.parent.mkdir(parents=True, exist_ok=True)
    scores_path.write_bytes(record_bytes)
    first_result = results[0]
    score_manifest: dict[str, Any] = {
        "schema_version": 1,
        "task": config.task,
        "scores_sha256": "sha256:" + sha256_file(scores_path),
        "template_sha256": "sha256:" + first_result.template_sha256,
        "judge": {
            "model": config.model,
            "judge_id": config.judge_id,
            "judge_family": first_result.judge_identity.judge_family,
            "reported_model_id": first_result.judge_identity.reported_model_id,
            "seed": config.seed,
            "temperature": (
                config.temperature
                if config.temperature is not None
                else "provider-default"
            ),
            "top_p": config.top_p if config.top_p is not None else "provider-default",
            "max_output_tokens": config.max_output_tokens,
            "stop_rules": list(config.stop_rules),
            "max_retries": config.max_retries,
        },
        "family_audit": family_audit,
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
                "line": line,
                "record_sha256": "sha256:" + sha256_json(result.record),
                "response_sha256": "sha256:" + result.response_sha256,
                "attempts": result.attempts,
                "usage": result.usage,
            }
            for line, result in enumerate(results, start=1)
        ],
    }
    if tournament is not None:
        score_manifest["tournament"] = tournament
    manifest_path.write_text(
        json.dumps(score_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return ScoreRunResult(
        scores_path=scores_path,
        manifest_path=manifest_path,
        result=first_result,
        results=results,
    )


def _manifest_path(scores_path: Path) -> Path:
    return scores_path.with_name(scores_path.stem + "-manifest.json")


def score_run(
    run_dir: Path,
    config: JudgeConfig,
    *,
    compare_run_dir: Path | None = None,
    output_path: Path | None = None,
    model: Model | None = None,
) -> ScoreRunResult:
    """Score one run or a complete pairwise tournament and write its manifest."""

    first = load_run_artifacts(run_dir)
    # Hash the run identity so both pairwise presentations share one stable
    # gateway cache key.
    prompt_cache_key = (
        "judge-"
        + sha256_bytes(
            f"{config.task}:{config.template_path}:{first.run_dir}".encode()
        )[:32]
    )
    if config.task == "pointwise":
        if compare_run_dir is not None:
            raise RunArtifactError("pointwise scoring does not accept a comparison run")
        result = judge_pointwise(
            config,
            assignment=first.assignment,
            context=first.context,
            output=first.output,
            prompt_id=first.prompt_id,
            blind_condition_id=first.blind_condition_id,
            platform=first.platform,
            model=model,
            # Scope the pointwise request cache to this run directory.
            prompt_cache_key=prompt_cache_key,
        )
        return _write_score_artifacts(
            (output_path or first.run_dir / "scores.jsonl").resolve(),
            config,
            (first,),
            (result,),
            _family_audit(config, result, first),
        )

    if config.task == "native-pointwise":
        if compare_run_dir is not None:
            raise RunArtifactError(
                "native-pointwise scoring does not accept a comparison run"
            )
        # Keep one criterion per request and defer aggregation to the analysis
        # stage, matching the native benchmark's checklist-wise contract.
        results = tuple(
            judge_native_pointwise(
                config,
                assignment=first.assignment,
                output=first.output,
                criterion=criterion,
                prompt_id=first.prompt_id,
                blind_condition_id=first.blind_condition_id,
                platform=first.platform,
                model=model,
                prompt_cache_key=prompt_cache_key,
            )
            for criterion in _native_criteria(first)
        )
        family_audit = _family_audit(config, results[0], first)
        for result in results[1:]:
            if result.judge_identity != results[0].judge_identity:
                raise RunArtifactError(
                    "native-pointwise criteria reported different judge model "
                    "identities"
                )
            _family_audit(config, result, first)
        return _write_score_artifacts(
            (output_path or first.run_dir / "scores.jsonl").resolve(),
            config,
            (first,),
            results,
            family_audit,
        )

    if compare_run_dir is None:
        raise RunArtifactError(
            "pairwise scoring needs --compare-run-dir for both presentations"
        )
    if config.presentation_seed is None:
        raise RunArtifactError("pairwise scoring needs a presentation seed")
    second = load_run_artifacts(compare_run_dir)
    if first.prompt_id != second.prompt_id or first.platform != second.platform:
        raise RunArtifactError("pairwise runs must share prompt ID and platform")
    if first.assignment != second.assignment or first.context != second.context:
        raise RunArtifactError("pairwise runs must share assignment and context")
    if (
        first.generator_model_id != second.generator_model_id
        or first.generator_family != second.generator_family
    ):
        raise RunArtifactError("pairwise runs must share generator model evidence")

    pair_id = _pair_id(first, second)
    orders = _presentation_orders(pair_id, config.presentation_seed)
    results = tuple(
        _score_pairwise_presentation(
            first,
            second,
            config,
            pair_id=pair_id,
            presentation=order,
            model=model,
            # Reuse the run-directory namespace for both tournament presentations.
            prompt_cache_key=prompt_cache_key,
        )
        for order in orders
    )
    family_audit = _family_audit(config, results[0], first)
    for result in results[1:]:
        if result.judge_identity != results[0].judge_identity:
            raise RunArtifactError(
                "pairwise presentations reported different judge model identities"
            )
        _family_audit(config, result, first)
    tournament = {
        "presentation_seed": config.presentation_seed,
        "orders": list(orders),
        "order_mapping": [
            {
                "presentation": order,
                "first_output": "first_run" if order == "A|B" else "compare_run",
                "second_output": "compare_run" if order == "A|B" else "first_run",
            }
            for order in orders
        ],
    }
    return _write_score_artifacts(
        (output_path or first.run_dir / "scores.jsonl").resolve(),
        config,
        (first, second),
        results,
        family_audit,
        tournament=tournament,
    )
