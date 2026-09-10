from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agentic_cogwriter.analysis import aggregate as aggregate_module
from agentic_cogwriter.analysis import batch as batch_module

DIMENSIONS = (
    "instruction_fulfillment",
    "organization_global_coherence",
    "content_adequacy_depth",
    "style_voice_audience_fit",
    "factuality_constraint_fidelity",
)


def _run(
    root: Path,
    benchmark: str,
    condition: str,
    prompt: str,
    *,
    status: str = "completed",
    output_tokens: int = 10,
    input_tokens: int = 20,
    cached_input_tokens: int = 0,
) -> Path:
    path = root / benchmark / condition / "codex" / prompt
    path.mkdir(parents=True)
    manifest = {
        "schema_version": 1,
        "run_id": prompt,
        "status": status,
        "inputs": {
            "benchmark_name": benchmark,
            "condition_id": condition,
            "prompt_id": prompt,
            "platform": "codex",
        },
        "models_and_execution": {
            "generator_model_id": "gpt-5.6-luna",
            "generator_model_family": "gpt",
        },
        "budget_used_tokens": output_tokens,
    }
    if status != "completed":
        manifest["failure"] = {"message": "executor failed: synthetic"}
    (path / "run-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (path / "prompt.txt").write_text(
        "Assignment:\nWrite a memo.\n\nSupplied context:\nFact.\n",
        encoding="utf-8",
    )
    (path / "output.normalized.txt").write_text(
        f"{condition} response", encoding="utf-8"
    )
    (path / "attempt-001.events.jsonl").write_text(
        json.dumps(
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": input_tokens,
                    "cached_input_tokens": cached_input_tokens,
                    "output_tokens": output_tokens,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _run_hash(path: Path) -> str:
    return (
        "sha256:"
        + hashlib.sha256((path / "run-manifest.json").read_bytes()).hexdigest()
    )


def _score_manifest(
    path: Path,
    task: str,
    source_runs: list[Path],
    records: list[dict[str, object]],
    *,
    tournament: dict[str, object] | None = None,
    usages: list[dict[str, int]] | None = None,
) -> None:
    path.mkdir(parents=True)
    (path / "scores.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    document: dict[str, object] = {
        "schema_version": 1,
        "task": task,
        "source_runs": [{"run_manifest_sha256": _run_hash(run)} for run in source_runs],
        "records": [
            {"line": index, "usage": usage}
            for index, usage in enumerate(
                usages
                or [
                    {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110}
                ]
                * len(records),
                start=1,
            )
        ],
    }
    if tournament is not None:
        document["tournament"] = tournament
    (path / "scores-manifest.json").write_text(json.dumps(document), encoding="utf-8")


def _pointwise_record(condition: str, value: int) -> dict[str, object]:
    return {
        "prompt_id": "p1",
        "condition_id": f"blind-{condition}",
        "platform": "codex",
        "judge_id": "judge-1",
        "judge_family": "open_evaluator",
        "scores": dict.fromkeys(DIMENSIONS, value),
        "evidence_quotes": [],
        "judge_level_composite": 0,
        "uncertainties": [],
    }


def test_score_batch_is_idempotent_and_drops_failed_pair_members(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "runs"
    a4 = _run(root, "WritingBench", "A4", "p1")
    a1 = _run(root, "WritingBench", "A1", "p1")
    _run(root, "WritingBench", "A2", "p1", status="failed")
    existing = a4 / "scores" / "pointwise"
    _score_manifest(
        existing,
        "pointwise",
        [a4],
        [_pointwise_record("A4", 4)],
    )

    pointwise = tmp_path / "pointwise.json"
    pairwise = tmp_path / "pairwise.json"
    pointwise.write_text("{}", encoding="utf-8")
    pairwise.write_text("{}", encoding="utf-8")
    configs = {
        pointwise: SimpleNamespace(
            task="pointwise", template_path=Path("pointwise-v1.md")
        ),
        pairwise: SimpleNamespace(
            task="pairwise", template_path=Path("pairwise-v1.md")
        ),
    }
    monkeypatch.setattr(batch_module.JudgeConfig, "load", lambda path: configs[path])
    calls: list[tuple[str, str | None, str]] = []

    def fake_score_run(
        run_dir: Path,
        config: object,
        *,
        compare_run_dir: Path | None = None,
        output_path: Path | None = None,
        model: object | None = None,
    ) -> object:
        del model
        calls.append(
            (
                run_dir.name,
                compare_run_dir.name if compare_run_dir else None,
                config.task,
            )
        )
        if run_dir == a1 and config.task == "pointwise":
            raise RuntimeError("synthetic transport failure")
        assert output_path is not None
        _score_manifest(
            output_path.parent,
            config.task,
            [run_dir, compare_run_dir] if compare_run_dir else [run_dir],
            [],
        )
        return object()

    monkeypatch.setattr(batch_module, "score_run", fake_score_run)
    summary = batch_module.run_batch(
        [root],
        pointwise_config=pointwise,
        pairwise_config=pairwise,
        native_configs=[],
        concurrency=1,
    )

    assert summary == {"scored": 1, "skipped": 1, "failed": 1}
    assert (a4 / "scores" / "pointwise" / "scores-manifest.json").is_file()
    assert any(task == "pairwise" for _, _, task in calls)
    errors = (root / "scoring-errors.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(errors) == 1
    assert json.loads(errors[0])["task"] == "pointwise"
    assert all("A2" not in call for call in calls)


def test_aggregate_report_covers_quality_pairwise_and_cost_tables(
    tmp_path: Path,
) -> None:
    root = tmp_path / "runs"
    a4 = _run(root, "WritingBench", "A4", "p1", output_tokens=30, input_tokens=100)
    a1 = _run(root, "WritingBench", "A1", "p1", output_tokens=10, input_tokens=50)
    _run(root, "WritingBench", "A2", "p1", output_tokens=12, input_tokens=40)
    _run(root, "WritingBench", "A2", "p2", status="failed")
    hello = _run(root, "HelloBench", "A1", "p1", output_tokens=8, input_tokens=30)

    _score_manifest(
        a4 / "scores" / "pointwise",
        "pointwise",
        [a4],
        [_pointwise_record("A4", 5)],
        usages=[
            {
                "prompt_tokens": 100,
                "cached_tokens": 20,
                "completion_tokens": 10,
                "total_tokens": 110,
            }
        ],
    )
    _score_manifest(
        a1 / "scores" / "pointwise",
        "pointwise",
        [a1],
        [_pointwise_record("A1", 3)],
    )
    _score_manifest(
        a4 / "scores" / "native-pointwise",
        "native-pointwise",
        [a4],
        [{"score": 8, "reason": "good"}],
    )
    _score_manifest(
        a1 / "scores" / "native-pointwise",
        "native-pointwise",
        [a1],
        [{"score": 4, "reason": "weak"}],
    )
    _score_manifest(
        hello / "scores" / "native-checklist",
        "native-checklist",
        [hello],
        [
            {
                "checklist_items": [
                    {"checklist_id": 0, "evaluation_score": 1, "reason": "yes"},
                    {"checklist_id": 1, "evaluation_score": 0.5, "reason": "partial"},
                ]
            }
        ],
    )
    tournament = {
        "order_mapping": [
            {
                "presentation": "A|B",
                "first_output": "first_run",
                "second_output": "compare_run",
            },
            {
                "presentation": "B|A",
                "first_output": "compare_run",
                "second_output": "first_run",
            },
        ]
    }
    pair_records = [
        {"pair_id": "pair", "presentation": "A|B", "winner": "A"},
        {"pair_id": "pair", "presentation": "B|A", "winner": "B"},
    ]
    _score_manifest(
        a4 / "scores" / "pairwise" / "pair",
        "pairwise",
        [a4, a1],
        pair_records,
        tournament=tournament,
    )

    output_dir = tmp_path / "report"
    report = aggregate_module.aggregate_runs(
        [root],
        generation_prices={"input": 1, "cached_input": 2, "output": 3},
        judge_prices={"input": 4, "cached_input": 5, "output": 6},
        output_dir=output_dir,
    )

    assert sum(row["failed_runs"] for row in report["completion"]["rows"]) == 1
    pointwise = report["pointwise"]["rows"]
    assert {row["condition"] for row in pointwise} == {"A1", "A4"}
    pair = report["pairwise"]["benchmarks"]["WritingBench"]
    assert pair["position_consistency_rate"] == 1.0
    assert pair["strengths"]["A4"] > pair["strengths"]["A1"]
    assert pair["missing_pairs"] == 2
    assert any(row["benchmark"] == "HelloBench" for row in report["native"]["rows"])
    generation = report["cost"]["generation"]
    a4_generation = next(row for row in generation if row["condition"] == "A4")
    assert a4_generation["tokens"]["output"] == 30
    assert a4_generation["cost"] == pytest.approx(0.00019)
    pointwise_judge = next(
        row for row in report["cost"]["judge"] if row["task"] == "pointwise"
    )
    assert pointwise_judge["tokens"]["cached_input"] == 20
    assert report["cost"]["totals"]["generation_cost"] == pytest.approx(0.00045)
    assert report["cost"]["totals"]["generation_cost"] > 0
    assert (output_dir / "aggregation.json").is_file()
    assert (output_dir / "aggregation.md").is_file()
