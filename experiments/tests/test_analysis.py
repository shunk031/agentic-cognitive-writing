from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agentic_cogwriter.analysis import aggregate as aggregate_module
from agentic_cogwriter.analysis import batch as batch_module
from agentic_cogwriter.analysis.common import select_canonical_runs

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
    run_id: str | None = None,
    started_at: str = "2026-01-01T00:00:00+00:00",
    output_tokens: int = 10,
    input_tokens: int = 20,
    platform: str = "codex",
) -> Path:
    run_id = run_id or prompt
    path = root / benchmark / condition / platform / run_id
    path.mkdir(parents=True)
    manifest = {
        "schema_version": 1,
        "started_at": started_at,
        "status": status,
        "inputs": {
            "benchmark_name": benchmark,
            "condition_id": condition,
            "prompt_id": prompt,
            "platform": platform,
        },
    }
    if status != "completed":
        manifest["failure"] = {"message": "executor failed: synthetic"}
    (path / "run-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (path / "attempt-001.events.jsonl").write_text(
        json.dumps(
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": input_tokens,
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
    judge_id: str = "judge-1",
    usages: list[dict[str, int]] | None = None,
) -> None:
    path.mkdir(parents=True)
    (path / "scores.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    document: dict[str, object] = {
        "task": task,
        "judge": {"judge_id": judge_id},
        "source_runs": [{"run_manifest_sha256": _run_hash(run)} for run in source_runs],
        "records": [
            {"usage": usage}
            for usage in (
                usages
                or [
                    {
                        "prompt_tokens": 100,
                        "completion_tokens": 10,
                        "reasoning_tokens": 99,
                    }
                ]
                * len(records)
            )
        ],
    }
    (path / "scores-manifest.json").write_text(json.dumps(document), encoding="utf-8")


def _pointwise_record(value: int, judge_id: str = "judge-1") -> dict[str, object]:
    return {"judge_id": judge_id, "scores": dict.fromkeys(DIMENSIONS, value)}


def test_canonical_selection_prefers_latest_completed_then_latest_failed(
    tmp_path: Path,
) -> None:
    root = tmp_path / "runs"
    _run(root, "HelloBench", "A1", "p1", run_id="old", started_at="2026-01-01")
    _run(
        root,
        "HelloBench",
        "A1",
        "p1",
        status="failed",
        run_id="failed",
        started_at="2026-01-03",
    )
    latest = _run(
        root,
        "HelloBench",
        "A1",
        "p1",
        run_id="latest",
        started_at="2026-01-02",
    )
    only_failed = _run(
        root,
        "HelloBench",
        "A2",
        "p1",
        status="failed",
        run_id="only-failed",
        started_at="2026-01-02",
    )

    selected = select_canonical_runs([root])

    assert {run.path for run in selected} == {latest, only_failed}


def test_score_batch_is_idempotent_and_drops_failed_pair_members(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "runs"
    old_a4 = _run(
        root, "WritingBench", "A4", "p1", run_id="old", started_at="2026-01-01"
    )
    a4 = _run(
        root,
        "WritingBench",
        "A4",
        "p1",
        status="failed",
        run_id="new-failed",
        started_at="2026-01-02",
    )
    a1 = _run(root, "WritingBench", "A1", "p1")
    failed = _run(root, "WritingBench", "A2", "p1", status="failed", run_id="failed")

    pointwise = tmp_path / "pointwise.json"
    pairwise = tmp_path / "pairwise.json"
    pointwise.write_text("{}", encoding="utf-8")
    pairwise.write_text("{}", encoding="utf-8")
    configs = {
        pointwise: SimpleNamespace(
            task="pointwise", judge_id="judge-1", template_path=Path("pointwise-v1.md")
        ),
        pairwise: SimpleNamespace(
            task="pairwise", judge_id="judge-1", template_path=Path("pairwise-v1.md")
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
            judge_id=config.judge_id,
        )
        return object()

    monkeypatch.setattr(batch_module, "score_run", fake_score_run)
    existing = old_a4 / "scores" / "pointwise" / "judge-1"
    _score_manifest(existing, "pointwise", [old_a4], [], judge_id="judge-1")

    summary = batch_module.run_batch(
        [root],
        pointwise_config=pointwise,
        pairwise_config=pairwise,
        native_configs=[],
        concurrency=1,
    )

    assert summary["scored"] == 1
    assert summary["failed"] == 1
    assert summary["skipped"] == 1
    assert summary["pairwise"] == 1
    assert summary["pointwise"] == 1
    assert (
        old_a4 / "scores" / "pointwise" / "judge-1" / "scores-manifest.json"
    ).is_file()
    errors = (root / "scoring-errors.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(errors) == 1
    assert json.loads(errors[0])["task"] == "pointwise"
    assert all(failed.name not in call for call in calls)
    assert all(a4.name not in call for call in calls)


def test_aggregate_uses_expected_pairs_judge_groups_and_completion_only_tokens(
    tmp_path: Path,
) -> None:
    root = tmp_path / "runs"
    writing_runs = {
        condition: _run(root, "WritingBench", condition, "p1", output_tokens=10)
        for condition in ("A1", "A2", "A3", "A4", "A5", "A6")
    }
    _run(root, "WritingBench", "A2", "p2", status="failed")
    hello = _run(root, "HelloBench", "A1", "p1", output_tokens=8, input_tokens=30)

    for condition, run in writing_runs.items():
        _score_manifest(
            run / "scores" / "pointwise" / "judge-1",
            "pointwise",
            [run],
            [_pointwise_record(5 if condition == "A4" else 3)],
            judge_id="judge-1",
        )
    _score_manifest(
        writing_runs["A4"] / "scores" / "pointwise" / "judge-2",
        "pointwise",
        [writing_runs["A4"]],
        [_pointwise_record(7, "judge-2")],
        judge_id="judge-2",
    )
    for condition, score in (("A4", 8), ("A1", 4)):
        _score_manifest(
            writing_runs[condition] / "scores" / "native-pointwise" / "judge-1",
            "native-pointwise",
            [writing_runs[condition]],
            [{"score": score, "reason": "synthetic"}],
        )
    _score_manifest(
        hello / "scores" / "native-checklist" / "judge-1",
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
    _score_manifest(
        writing_runs["A4"] / "scores" / "pairwise" / "judge-1" / "pair-a4-a1",
        "pairwise",
        [writing_runs["A4"], writing_runs["A1"]],
        [
            {"pair_id": "pair", "presentation": "A|B", "winner": "A"},
            {"pair_id": "pair", "presentation": "B|A", "winner": "B"},
        ],
    )

    generation_prices = tmp_path / "generation-prices.json"
    judge_prices = tmp_path / "judge-prices.json"
    generation_prices.write_text(
        json.dumps({"input": 1, "cached_input": 2, "output": 3})
    )
    judge_prices.write_text(json.dumps({"input": 4, "cached_input": 5, "output": 6}))
    output_dir = tmp_path / "report"

    report = aggregate_module.aggregate_runs(
        [root],
        generation_prices=generation_prices,
        judge_prices=judge_prices,
        output_dir=output_dir,
    )

    assert report["completion"]["run_count"] == 8
    pointwise = report["pointwise"]["rows"]
    assert {row["condition"] for row in pointwise} == {
        "A1",
        "A2",
        "A3",
        "A4",
        "A5",
        "A6",
    }
    writing_pair = report["pairwise"]["benchmarks"]["WritingBench"]
    codex_pair = writing_pair["platforms"]["codex"]
    assert codex_pair["expected_pairs"] == 10
    assert codex_pair["scored_pairs"] == 1
    assert codex_pair["missing_pairs"] == 9
    assert codex_pair["run_count"] == 6
    assert codex_pair["judges"]["judge-1"]["position_consistency_rate"] == 1.0
    assert report["native"]["rows"][-1]["scale"] in {"1-10", "0-1"}
    generation = report["cost"]["generation"]
    a4_generation = next(row for row in generation if row["condition"] == "A4")
    assert a4_generation["tokens"]["output"] == 10
    assert a4_generation["cost"] == pytest.approx(0.00005)
    pointwise_judge = next(
        row for row in report["cost"]["judge"] if row["task"] == "pointwise"
    )
    assert pointwise_judge["tokens"]["output"] == 70
    assert (output_dir / "aggregation.json").is_file()
    assert (output_dir / "aggregation.md").is_file()


def test_position_consistency_requires_exactly_two_presentations(
    tmp_path: Path,
) -> None:
    root = tmp_path / "runs"
    a4 = _run(root, "WritingBench", "A4", "p1")
    a1 = _run(root, "WritingBench", "A1", "p1")
    _score_manifest(
        a4 / "scores" / "pairwise" / "judge-1" / "pair",
        "pairwise",
        [a4, a1],
        [{"presentation": "A|B", "winner": "A"}],
    )
    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps({"input": 0, "cached_input": 0, "output": 0}))
    report = aggregate_module.aggregate_runs(
        [root],
        generation_prices=prices,
        judge_prices=prices,
        output_dir=tmp_path / "out",
    )
    judge = report["pairwise"]["benchmarks"]["WritingBench"]["platforms"]["codex"][
        "judges"
    ]["judge-1"]
    assert judge["position_consistency_rate"] is None
    assert judge["scored_pairs"] == 0


def test_bradley_terry_reports_separation_and_fits_known_case() -> None:
    fit = aggregate_module.fit_bradley_terry(
        [
            ("A4", "A1", "left"),
            ("A4", "A1", "left"),
            ("A4", "A1", "right"),
            ("A4", "A2", "left"),
            ("A4", "A2", "right"),
            ("A4", "A2", "tie"),
        ]
    )
    assert fit["status"] == "ok"
    assert fit["strengths"]["A4"] > fit["strengths"]["A1"]

    separated = aggregate_module.fit_bradley_terry(
        [("A4", "A1", "left"), ("A4", "A1", "left")]
    )
    assert separated["status"] == "complete separation"
    assert separated["strengths"] == {}
