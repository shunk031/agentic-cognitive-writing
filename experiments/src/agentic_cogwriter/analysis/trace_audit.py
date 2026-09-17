"""Judge-based audit of writing traces and active goal faithfulness."""
from __future__ import annotations
import argparse
import hashlib
import json
import random
import re
from collections.abc import Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field
from ..judges.client import OpenAICompatibleClient, normalize_usage
from ..judges.config import JudgeConfig
from ..judges.errors import JudgeConfigurationError, JudgeValidationError
from ..judges.templates import JudgeTemplate
from .common import RunRecord, select_canonical_runs
DEFAULT_PAIRWISE_JUDGE = "gpt-5.6-sol-pairwise-v1"
DEFAULT_SEED = 20260908
class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
class LocalizationRecord(_Strict):
    prompt_id: str
    condition: Literal["A4", "A5"]
    outcome: Literal["lost", "won"]
    rating: Literal["anticipated", "partially", "not"]
    trace_quote: str = Field(min_length=1)
    cited_deficiency: str = Field(min_length=1)
class GoalAssessment(_Strict):
    goal_id: str = Field(min_length=1)
    rating: Literal["satisfied", "partially", "not"]
    supporting_quote: str = Field(min_length=1)
class GoalRecord(_Strict):
    prompt_id: str
    assessments: list[GoalAssessment]
@dataclass(frozen=True)
class Pair:
    a4: RunRecord
    a5: RunRecord
    outcome: Literal["A4-win", "A4-loss"]
    reasons: tuple[dict[str, str], ...]
@dataclass(frozen=True)
class Job:
    kind: Literal["localization", "goals"]
    run: RunRecord
    pair: Pair | None = None
    condition: Literal["A4", "A5"] | None = None
    outcome: Literal["lost", "won"] | None = None
class AuditBlocked(RuntimeError):
    pass
def winner_condition(presentation: str, winner: str) -> str | None:
    if presentation not in {"A|B", "B|A"} or winner not in {"A", "B"}:
        return None
    return ("A4" if winner == "A" else "A5") if presentation == "A|B" else ("A5" if winner == "A" else "A4")
def decisive_outcome(records: Sequence[Mapping[str, Any]]) -> str | None:
    if len(records) != 2 or {r.get("presentation") for r in records} != {"A|B", "B|A"}:
        return None
    winners = {winner_condition(str(r["presentation"]), str(r["winner"])) for r in records}
    return {"A4": "A4-win", "A5": "A4-loss"}.get(next(iter(winners))) if len(winners) == 1 else None
def _compact(value: Any) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(_compact(item) for item in value) + "]"
    if isinstance(value, Mapping):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(value)
def render_trace(events: Sequence[Mapping[str, Any]]) -> str:
    lines = []
    for event in events:
        parts = [str(event.get("timestamp", "")), str(event.get("event_type", ""))]
        for field in ("process", "decision", "evidence", "open_uncertainty"):
            if field in event:
                parts.append(f"{field}={_compact(event[field])}")
        fields = ["goal_id", "parent_goal_id"] + sorted(key for key in event if key.startswith("goal_") and key not in {"goal_id", "parent_goal_id"})
        parts.extend(f"{field}={_compact(event[field])}" for field in fields if field in event)
        lines.append("- " + " | ".join(parts))
    return "\n".join(lines) or "(no trace events)"
def summarize_localization(
    records: Sequence[Mapping[str, Any]],
    expected: Mapping[tuple[str, str], int] | None = None,
    missing: Mapping[tuple[str, str], Sequence[str]] | None = None,
) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for condition in ("A4", "A5"):
        summary[condition] = {}
        for outcome in ("lost", "won"):
            cell = [r for r in records if r.get("condition") == condition and r.get("outcome") == outcome]
            total = len(cell)
            cell_summary: dict[str, Any] = {
                "n": total,
                "anticipated": sum(r.get("rating") == "anticipated" for r in cell) / total if total else 0.0,
                "partially": sum(r.get("rating") == "partially" for r in cell) / total if total else 0.0,
            }
            if expected is not None:
                expected_total = expected.get((condition, outcome), total)
                cell_summary.update(
                    {
                        "n": f"{total}/{expected_total}",
                        "completed": total,
                        "expected": expected_total,
                        "missing": list((missing or {}).get((condition, outcome), [])),
                    }
                )
            summary[condition][outcome] = cell_summary
    return summary
def summarize_goal_faithfulness(assessments: Sequence[Mapping[str, Any]], run_ratings: Mapping[str, Sequence[str]]) -> dict[str, Any]:
    total = len(assessments)
    return {
        "goal_count": total,
        "satisfied": sum(r.get("rating") == "satisfied" for r in assessments) / total if total else 0.0,
        "partially": sum(r.get("rating") == "partially" for r in assessments) / total if total else 0.0,
        "runs": len(run_ratings),
        "all_goals_at_least_partially": sum(bool(ratings) and all(r in {"satisfied", "partially"} for r in ratings) for ratings in run_ratings.values()) / len(run_ratings) if run_ratings else 0.0,
    }
def _manifest_hash(run: RunRecord) -> str:
    return "sha256:" + hashlib.sha256((run.path / "run-manifest.json").read_bytes()).hexdigest()
def _trace(run: RunRecord) -> str:
    path = run.path / "workspace" / ".writing" / "trace" / "process.jsonl"
    events = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not all(isinstance(event, Mapping) for event in events):
        raise ValueError(f"trace event is not an object: {path}")
    return render_trace(events)
def _goals(run: RunRecord) -> list[dict[str, str]]:
    path = run.path / "workspace" / ".writing" / "goals.md"
    active, goals = False, []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() == "## Active network":
            active = True
        elif active and line.startswith("## "):
            break
        elif active and line.lstrip().startswith("- ["):
            match = re.match(r"^\s*-\s+\[([^]]+)\]\s+(.+)$", line)
            if match:
                goals.append({"goal_id": match.group(1), "text": match.group(2).strip()})
        elif not active and line.strip() == "## History":
            break
        elif not active:
            match = re.match(r"^\s*-\s+([^\s]+)\s+\[[^]]+\]\s+(.+)$", line)
            if match:
                goals.append({"goal_id": match.group(1), "text": match.group(2).strip()})
    return goals
def _pair(a4: RunRecord, a5: RunRecord, judge_id: str) -> Pair | None:
    directory = a4.path / "scores" / "pairwise" / judge_id / f"{a4.prompt}-A5"
    scores, manifest = directory / "scores.jsonl", directory / "scores-manifest.json"
    if not scores.is_file() or not manifest.is_file():
        return None
    document = json.loads(manifest.read_text(encoding="utf-8"))
    if [item.get("run_manifest_sha256") for item in document.get("source_runs", [])] != [_manifest_hash(a4), _manifest_hash(a5)]:
        return None
    mapping = document.get("tournament", {}).get("order_mapping", [])
    expected = {
        ("A|B", "first_run", "compare_run"),
        ("B|A", "compare_run", "first_run"),
    }
    observed = {(item.get("presentation"), item.get("first_output"), item.get("second_output")) for item in mapping if isinstance(item, Mapping)}
    if observed != expected:
        return None
    records = [json.loads(line) for line in scores.read_text(encoding="utf-8").splitlines()]
    outcome = decisive_outcome(records)
    if outcome is None:
        return None
    reasons = tuple(
        {
            "presentation": str(r["presentation"]),
            "winner": str(r["winner"]),
            "reason": str(r.get("reason", "")),
        }
        for r in sorted(records, key=lambda r: str(r["presentation"]))
    )
    return Pair(a4, a5, outcome, reasons)
def _pairs(root: Path, judge_id: str) -> list[Pair]:
    runs = [r for r in select_canonical_runs([root]) if r.status == "completed" and r.platform == "codex"]
    index = {(r.benchmark, r.condition, r.prompt): r for r in runs}
    result = []
    for benchmark, prompt in sorted({(r.benchmark, r.prompt) for r in runs}):
        a4, a5 = (
            index.get((benchmark, "A4", prompt)),
            index.get((benchmark, "A5", prompt)),
        )
        if a4 and a5 and (pair := _pair(a4, a5, judge_id)):
            result.append(pair)
    return result
def _sample(root: Path, seed: int, size: int) -> list[RunRecord]:
    runs = [r for r in select_canonical_runs([root]) if r.status == "completed" and r.platform == "codex" and r.condition == "A4"]
    ordered = sorted(runs, key=lambda r: r.path.name)
    if len(ordered) < size:
        raise ValueError(f"only {len(ordered)} completed A4 runs are available")
    return random.Random(seed).sample(ordered, size)
def _artifact(job: Job, judge_id: str) -> Path:
    name = "trace-localization-v1" if job.kind == "localization" else "goal-faithfulness-v1"
    path = job.run.path / "audit" / judge_id / name
    return path / (f"{job.run.prompt}-{job.outcome}.json" if job.kind == "localization" else "result.json")
def _cost(usage: Mapping[str, int], prices: Mapping[str, float]) -> float:
    cached, prompt = usage.get("cached_tokens", 0), usage["prompt_tokens"]
    if cached > prompt:
        raise ValueError("cached tokens exceed prompt tokens")
    return ((prompt - cached) * prices["input"] + cached * prices["cached_input"] + usage["completion_tokens"] * prices["output"]) / 1_000_000
def _validate_localization(value: BaseModel, expected: Mapping[str, str], trace: str) -> None:
    record = LocalizationRecord.model_validate(value.model_dump(), strict=True)
    if any(record.model_dump()[key] != item for key, item in expected.items()) or record.trace_quote not in trace:
        raise JudgeValidationError("localization response does not match its request")
def _validate_goals(value: BaseModel, prompt_id: str, goal_ids: Sequence[str], output: str) -> None:
    record = GoalRecord.model_validate(value.model_dump(), strict=True)
    actual = [item.goal_id for item in record.assessments]
    if record.prompt_id != prompt_id or len(actual) != len(set(goal_ids)) or set(actual) != set(goal_ids):
        raise JudgeValidationError("goal response must cover every active goal once")
    if any(item.supporting_quote not in output for item in record.assessments):
        raise JudgeValidationError("goal quote is absent from the final text")
def _load_artifact(path: Path, model: type[BaseModel], prices: Mapping[str, float]) -> Any:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or data.get("status") != "completed":
        raise ValueError(f"invalid audit artifact: {path}")
    record = model.model_validate(data["record"], strict=True).model_dump()
    usage = normalize_usage(data["usage"])
    return SimpleNamespace(record=record, usage=usage, cost=_cost(usage, prices), reused=True)
def _write_artifact(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
def _call(job: Job, config: JudgeConfig, template_path: Path, prices: Mapping[str, float]) -> Any:
    artifact = _artifact(job, config.judge_id)
    model: type[BaseModel] = LocalizationRecord if job.kind == "localization" else GoalRecord
    if artifact.is_file():
        return _load_artifact(artifact, model, prices)
    if job.kind == "localization":
        assert job.pair and job.condition and job.outcome
        trace = _trace(job.run)
        goals = _goals(job.pair.a4) if job.condition == "A4" else []
        values = {
            "prompt_id": job.run.prompt,
            "condition": job.condition,
            "outcome": job.outcome,
            "pairwise_reasons": json.dumps(job.pair.reasons, ensure_ascii=False, indent=2),
            "trace": trace,
            "goals": json.dumps(goals, ensure_ascii=False, indent=2) if goals else "(not supplied for A5)",
        }
        def validator(value: BaseModel) -> None:
            _validate_localization(
                value,
                {
                    "prompt_id": job.run.prompt,
                    "condition": job.condition,
                    "outcome": job.outcome,
                },
                trace,
            )
    else:
        goals = _goals(job.run)
        output = (job.run.path / "output.normalized.txt").read_text(encoding="utf-8")
        values = {
            "prompt_id": job.run.prompt,
            "goals": json.dumps(goals, ensure_ascii=False, indent=2),
            "output": output,
        }
        def validator(value: BaseModel) -> None:
            _validate_goals(value, job.run.prompt, [g["goal_id"] for g in goals], output)
    template = JudgeTemplate.load(template_path)
    response = OpenAICompatibleClient(config).complete(
        template.render(values),
        output_type=model,
        output_validator=validator,
        prompt_cache_key="trace-audit-" + hashlib.sha256(str(job.run.path).encode()).hexdigest()[:32],
    )  # type: ignore[arg-type]
    identity = config.resolve_model_identity(response.reported_model_id)
    models = job.run.manifest.get("models_and_execution")
    family = models.get("generator_model_family") if isinstance(models, Mapping) else None
    if not isinstance(family, str) or not family.strip():
        raise JudgeConfigurationError("run manifest lacks generator model family")
    config.validate_family_audit(identity, family)
    usage, record = dict(response.usage), response.output.model_dump()
    result = SimpleNamespace(record=record, usage=usage, cost=_cost(usage, prices), reused=False)
    _write_artifact(
        artifact,
        {
            "schema_version": 1,
            "status": "completed",
            "kind": job.kind,
            "prompt_id": job.run.prompt,
            "record": record,
            "usage": usage,
            "cost": result.cost,
            "judge": {
                "judge_id": config.judge_id,
                "model": config.model,
                "reported_model_id": response.reported_model_id,
                "judge_family": identity.judge_family,
                "attempts": response.attempts,
            },
            "template_sha256": template.sha256,
            "response_sha256": hashlib.sha256(response.content.encode()).hexdigest(),
        },
    )
    return result
def _markdown(summary: Mapping[str, Any]) -> str:
    def pct(value: float) -> str:
        return f"{value:.1%}"
    lines = [
        "# Trace audit",
        "",
        "The audit uses completed canonical runs and makes no generation calls.",
        "",
        "## Question 1: failure localization",
        "",
        "Rates use completed calls; N is completed/expected.",
        "",
        "| Condition | Outcome | N | Anticipated | Partially |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for condition in ("A4", "A5"):
        for outcome in ("lost", "won"):
            cell = summary["question1"][condition][outcome]
            lines.append(f"| {condition} | {outcome} | {cell['n']} | {pct(cell['anticipated'])} | {pct(cell['partially'])} |")
    if summary.get("missing"):
        lines += ["", "Missing judge calls:", ""]
        lines.extend(
            f"- {item['benchmark']} {item['prompt_id']} {item['condition'] or item['kind']} {item['outcome'] or ''}".rstrip()
            for item in summary["missing"]
        )
    goals = summary["question2"]
    lines += [
        "",
        "## Question 2: goal faithfulness",
        "",
        "| Goal count | Runs | Satisfied | Partially | All goals at least partially |",
        "| ---: | ---: | ---: | ---: | ---: |",
        f"| {goals['goal_count']} | {goals['runs']} | {pct(goals['satisfied'])} | {pct(goals['partially'])} | {pct(goals['all_goals_at_least_partially'])} |",
        "",
        f"Judge calls: {summary['calls']['judge_calls']}",
        f"Judge cost: ${summary['calls']['judge_cost']:.6f}",
        "",
    ]
    return "\n".join(lines)
def run_audit(
    root: Path,
    config_path: Path,
    output_dir: Path,
    *,
    pairwise_judge_id: str = DEFAULT_PAIRWISE_JUDGE,
    concurrency: int = 4,
    seed: int = DEFAULT_SEED,
    sample_size: int = 100,
    max_cost: float = 40.0,
    allow_missing: bool = False,
    prices: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    if concurrency < 1 or sample_size < 1:
        raise ValueError("concurrency and sample_size must be positive")
    config = JudgeConfig.load(config_path)
    prices = prices or {"input": 2.50, "cached_input": 0.25, "output": 15.00}
    pairs = _pairs(root, pairwise_judge_id)
    jobs = [
        Job(
            "localization",
            run,
            pair,
            condition,
            "won" if (pair.outcome == "A4-win") == (condition == "A4") else "lost",
        )
        for pair in pairs
        for condition, run in (("A4", pair.a4), ("A5", pair.a5))
    ]
    jobs += [Job("goals", run) for run in _sample(root, seed, sample_size)]
    goal_template = config.template_path.with_name("goal-faithfulness-v1.md")
    fresh = sum(not _artifact(job, config.judge_id).is_file() for job in jobs)
    results: list[tuple[Job, Any]] = []
    failures = calls = successes = 0
    total_cost = 0.0
    new_cost = 0.0
    missing_jobs: list[Job] = []
    futures: dict[Future[Any], Job] = {}
    executor = ThreadPoolExecutor(max_workers=concurrency)
    try:
        for job in jobs:
            template = config.template_path if job.kind == "localization" else goal_template
            futures[
                executor.submit(
                    _call,
                    job,
                    replace(config, template_path=template),
                    template,
                    prices,
                )
            ] = job
        for future in as_completed(futures):
            job = futures[future]
            try:
                result = future.result()
            except Exception:
                if not _artifact(job, config.judge_id).is_file():
                    calls += 1
                    missing_jobs.append(job)
                failures += 1
                if fresh >= 20 and calls <= 20 and failures == calls:
                    raise AuditBlocked("the first 20 judge calls failed") from None
                continue
            results.append((job, result))
            total_cost += result.cost
            if not result.reused:
                calls += 1
                successes += 1
                new_cost += result.cost
            if successes and new_cost / successes * fresh > max_cost:
                raise AuditBlocked("projected judge cost exceeds the configured limit")
    finally:
        for future in futures:
            future.cancel()
        executor.shutdown(wait=True, cancel_futures=True)
    if failures and not allow_missing:
        raise RuntimeError(f"{failures} audit calls failed")
    loc = [result.record for job, result in results if job.kind == "localization"]
    assessments = [{"run_id": job.run.path.name, **assessment} for job, result in results if job.kind == "goals" for assessment in result.record["assessments"]]
    ratings = {job.run.path.name: [a["rating"] for a in result.record["assessments"]] for job, result in results if job.kind == "goals"}
    expected_cells = {
        (condition, outcome): sum(
            job.kind == "localization" and job.condition == condition and job.outcome == outcome
            for job in jobs
        )
        for condition in ("A4", "A5")
        for outcome in ("lost", "won")
    }
    missing_cells = {
        cell: [job.run.prompt for job in missing_jobs if job.condition == cell[0] and job.outcome == cell[1]]
        for cell in expected_cells
    }
    summary = {
        "schema_version": 1,
        "seed": seed,
        "sample_size": sample_size,
        "decisive_pairs": len(pairs),
        "allow_missing": allow_missing,
        "calls": {
            "planned": len(jobs),
            "judge_calls": len(jobs),
            "network_calls": calls,
            "reused": len(jobs) - calls,
            "failed": failures,
            "judge_cost": total_cost,
        },
        "missing": [
            {
                "kind": job.kind,
                "benchmark": job.run.benchmark,
                "prompt_id": job.run.prompt,
                "condition": job.condition,
                "outcome": job.outcome,
            }
            for job in missing_jobs
        ],
        "question1": summarize_localization(loc, expected_cells, missing_cells),
        "question2": summarize_goal_faithfulness(assessments, ratings),
        "judge": {
            "judge_id": config.judge_id,
            "model": config.model,
            "seed": config.seed,
            "max_output_tokens": config.max_output_tokens,
            "max_retries": config.max_retries,
            "allow_same_family_judge": config.allow_same_family_judge,
            "prices_per_million": dict(prices),
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "trace-audit-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "trace-audit-summary.md").write_text(_markdown(summary), encoding="utf-8")
    return summary
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit writing traces with a judge model.")
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--pairwise-judge-id", default=DEFAULT_PAIRWISE_JUDGE)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--max-cost", type=float, default=40.0)
    parser.add_argument("--allow-missing", action="store_true")
    return parser
def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = run_audit(
            args.runs_root,
            args.config,
            args.output_dir,
            pairwise_judge_id=args.pairwise_judge_id,
            concurrency=args.concurrency,
            seed=args.seed,
            sample_size=args.sample_size,
            max_cost=args.max_cost,
            allow_missing=args.allow_missing,
        )
    except AuditBlocked as error:
        print(f"BLOCKED: {error}")
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0
