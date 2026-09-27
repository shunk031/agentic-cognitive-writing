from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_judges import FakeTransport
from test_judges import _config as judge_config
from test_judges import _template as judge_template

from agentic_cogwriter.analysis import aggregate as aggregate_module
from agentic_cogwriter.analysis import batch as batch_module
from agentic_cogwriter.analysis import common as common_module
from agentic_cogwriter.analysis.common import parse_contrasts, select_canonical_runs
from agentic_cogwriter.judges import scorer as scorer_module
from agentic_cogwriter.judges.scorer import blind_condition_id
from agentic_cogwriter.runner.hashing import sha256_json

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
    prompt_row: dict[str, object] = {
        "prompt_id": prompt,
        "benchmark_name": benchmark,
        "source_version": "test@1",
        "prompt_text": "Write a memo.",
        "requested_output_constraints": {},
    }
    prompt_row["hash"] = sha256_json(prompt_row)
    manifest_path = root / "manifests" / f"{benchmark.casefold()}.jsonl"
    manifest_bytes = (
        json.dumps(prompt_row, ensure_ascii=False, sort_keys=True) + "\n"
    ).encode("utf-8")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(manifest_bytes)
    manifest = {
        "schema_version": 1,
        "started_at": started_at,
        "status": status,
        "inputs": {
            "benchmark_name": benchmark,
            "condition_id": condition,
            "prompt_id": prompt,
            "platform": platform,
            "prompt_hash": prompt_row["hash"],
            "prompt_manifest_hash": hashlib.sha256(manifest_bytes).hexdigest(),
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
    path.mkdir(parents=True, exist_ok=True)
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


def test_parse_contrasts_validates_condition_ids_and_pairs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        common_module, "CONDITION_IDS", (*common_module.CONDITION_IDS, "A7")
    )

    assert parse_contrasts("A7:A1,A7:A5") == (("A7", "A1"), ("A7", "A5"))
    for value in ("A7:A7", "A7:A1,A7:A1", "A7:A1,A1:A7", "A7:C1", "A7"):
        with pytest.raises(argparse.ArgumentTypeError):
            parse_contrasts(value)


@pytest.mark.parametrize(
    ("main", "required_args"),
    (
        (
            batch_module.main,
            (
                "--runs-root",
                "/runs",
                "--pointwise-config",
                "/pointwise.json",
                "--pairwise-config",
                "/pairwise.json",
            ),
        ),
        (
            aggregate_module.main,
            (
                "--runs-root",
                "/runs",
                "--generation-prices",
                "/generation.json",
                "--judge-prices",
                "/judge.json",
                "--output-dir",
                "/report",
            ),
        ),
    ),
)
@pytest.mark.parametrize(
    ("value", "reason"),
    (
        ("Z9:A1", "unknown condition in contrast 'Z9:A1'"),
        ("A1:A1", "contrast sides must differ: 'A1:A1'"),
        ("A4:A1,A4:A1", "duplicate contrast: 'A4:A1'"),
        ("A4:A1,A1:A4", "duplicate contrast: 'A1:A4'"),
        ("A4", "contrasts must be comma-separated LEFT:RIGHT pairs"),
    ),
)
def test_contrast_cli_reports_validation_reason(
    main: Callable[[list[str] | None], int],
    required_args: tuple[str, ...],
    value: str,
    reason: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main([*required_args, "--contrasts", value])

    assert error.value.code == 2
    assert f"argument --contrasts: {reason}" in capsys.readouterr().err


def test_configurable_contrasts_keep_artifacts_disjoint_and_aggregate_selected_pairs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        common_module, "CONDITION_IDS", (*common_module.CONDITION_IDS, "A7")
    )
    root = tmp_path / "runs"
    for condition in ("A1", "A2", "A3", "A4", "A5", "A6"):
        _run(root, "WritingBench", condition, "p1")
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

    def fake_score_run(
        run_dir: Path,
        config: object,
        *,
        compare_run_dir: Path | None = None,
        output_path: Path | None = None,
        model: object | None = None,
    ) -> object:
        del model
        assert output_path is not None
        records = (
            [
                {"presentation": "A|B", "winner": "A"},
                {"presentation": "B|A", "winner": "B"},
            ]
            if config.task == "pairwise"
            else []
        )
        _score_manifest(
            output_path.parent,
            config.task,
            [run_dir, compare_run_dir] if compare_run_dir else [run_dir],
            records,
            judge_id=config.judge_id,
        )
        return object()

    monkeypatch.setattr(batch_module, "score_run", fake_score_run)
    batch_args = [
        "--runs-root",
        str(root),
        "--pointwise-config",
        str(pointwise),
        "--pairwise-config",
        str(pairwise),
        "--concurrency",
        "1",
    ]
    assert batch_module.main(batch_args) == 0
    default_paths = {
        path.parent for path in root.rglob("scores.jsonl") if "pairwise" in path.parts
    }
    assert len(default_paths) == 5

    a7 = _run(root, "WritingBench", "A7", "p1")
    assert batch_module.main([*batch_args, "--contrasts", "A7:A1,A7:A5"]) == 0
    all_paths = {
        path.parent for path in root.rglob("scores.jsonl") if "pairwise" in path.parts
    }
    custom_paths = all_paths - default_paths
    assert custom_paths == {
        a7 / "scores" / "pairwise" / "judge-1" / "p1-A1",
        a7 / "scores" / "pairwise" / "judge-1" / "p1-A5",
    }
    assert default_paths.isdisjoint(custom_paths)

    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps({"input": 0, "cached_input": 0, "output": 0}))
    output_dir = tmp_path / "report"
    assert (
        aggregate_module.main(
            [
                "--runs-root",
                str(root),
                "--generation-prices",
                str(prices),
                "--judge-prices",
                str(prices),
                "--output-dir",
                str(output_dir),
                "--contrasts",
                "A7:A1,A7:A5",
            ]
        )
        == 0
    )
    report = json.loads((output_dir / "aggregation.json").read_text(encoding="utf-8"))
    pairwise_report = report["pairwise"]["benchmarks"]["WritingBench"]["platforms"][
        "codex"
    ]
    assert pairwise_report["contrasts"] == {
        "A7:A1": {"wins": 2, "ties": 0, "losses": 0},
        "A7:A5": {"wins": 2, "ties": 0, "losses": 0},
    }


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


def test_score_batch_removes_orphan_before_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "runs"
    monkeypatch.setattr(scorer_module, "MANIFESTS_DIR", root / "manifests")
    run = _run(root, "WritingBench", "A1", "p1")
    (run / "output.normalized.txt").write_text("Generated answer", encoding="utf-8")
    (run / "prompt.txt").write_text(
        "## Assignment\nWrite a memo.\n\n"
        "## Supplied context\nProvided fact.\n\n"
        "## Requested output constraints\n{}\n",
        encoding="utf-8",
    )
    manifest = json.loads((run / "run-manifest.json").read_text(encoding="utf-8"))
    manifest["models_and_execution"] = {
        "generator_model_id": "generator-model",
        "generator_model_family": "gpt",
    }
    manifest["scoring"] = {"status": "eligible"}
    (run / "run-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    pointwise = tmp_path / "pointwise.json"
    pairwise = tmp_path / "pairwise.json"
    pointwise_template = judge_template(tmp_path / "pointwise.txt", "pointwise")
    pairwise_template = judge_template(tmp_path / "pairwise.txt", "pairwise")
    configs = {
        pointwise: judge_config(tmp_path, pointwise_template),
        pairwise: judge_config(tmp_path, pairwise_template, task="pairwise"),
    }
    monkeypatch.setattr(batch_module.JudgeConfig, "load", lambda path: configs[path])
    response = {
        "prompt_id": "p1",
        "condition_id": blind_condition_id("A1"),
        "platform": "codex",
        "judge_id": "judge-1",
        "judge_family": "open_evaluator",
        "scores": dict.fromkeys(DIMENSIONS, 4),
        "evidence_quotes": [
            {"dimension": dimension, "quote": "Generated answer"}
            for dimension in DIMENSIONS
        ],
        "judge_level_composite": 0.0,
        "uncertainties": [],
    }
    transport = FakeTransport(
        [{"content": json.dumps(response)}, {"content": json.dumps(response)}]
    )
    real_atomic_write = scorer_module._atomic_write
    atomic_calls = 0

    def fail_manifest_write(path: Path, data: bytes) -> None:
        nonlocal atomic_calls
        atomic_calls += 1
        if atomic_calls == 2:
            raise OSError("manifest write failed")
        real_atomic_write(path, data)

    monkeypatch.setattr(scorer_module, "_atomic_write", fail_manifest_write)
    first = batch_module.run_batch(
        [root],
        pointwise_config=pointwise,
        pairwise_config=pairwise,
        native_configs=[],
        concurrency=1,
        model=transport.model,
    )
    assert first["failed"] == 1
    orphan = run / "scores" / "pointwise" / "judge-1" / "scores.jsonl"
    assert orphan.is_file()
    assert not orphan.with_name("scores-manifest.json").exists()

    monkeypatch.setattr(scorer_module, "_atomic_write", real_atomic_write)
    second = batch_module.run_batch(
        [root],
        pointwise_config=pointwise,
        pairwise_config=pairwise,
        native_configs=[],
        concurrency=1,
        model=transport.model,
    )

    assert second["scored"] == 1
    assert atomic_calls == 2
    assert orphan.is_file()
    assert orphan.with_name("scores-manifest.json").is_file()
    errors = (root / "scoring-errors.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(errors[-1])["error"] == "removed orphan scores.jsonl"


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


def _pairwise_records(*winners: tuple[str, str]) -> list[dict[str, object]]:
    return [
        record
        for first, second in winners
        for record in (
            {"pair_id": "pair", "presentation": "A|B", "winner": first},
            {"pair_id": "pair", "presentation": "B|A", "winner": second},
        )
    ]


def test_aggregate_reports_prompt_collapsed_pairwise_statistics(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps({"input": 0, "cached_input": 0, "output": 0}))
    # With the default order mapping, A|B=A4 and B|A=B means A4 again.
    outcomes = (
        ("A", "B"),  # agreeing A4 winner
        ("B", "A"),  # agreeing A1 winner
        ("A", "A"),  # winner flip: disagreement -> prompt tie
        ("tie", "A"),  # winner-versus-tie: disagreement -> prompt tie
    )
    for index, winners in enumerate(outcomes, start=1):
        a4 = _run(root, "WritingBench", "A4", f"p{index}")
        a1 = _run(root, "WritingBench", "A1", f"p{index}")
        pair = a4 / "scores" / "pairwise" / "judge-1" / f"pair-{index}"
        _score_manifest(pair, "pairwise", [a4, a1], _pairwise_records(winners))

    report = aggregate_module.aggregate_runs(
        [root],
        generation_prices=prices,
        judge_prices=prices,
        output_dir=tmp_path / "out",
        contrasts=(("A4", "A1"),),
    )
    cell = report["pairwise"]["benchmarks"]["WritingBench"]["platforms"]["codex"][
        "prompt_collapsed_across_judges"
    ]["A4:A1"]
    record_cell = report["pairwise"]["benchmarks"]["WritingBench"]["platforms"][
        "codex"
    ]["record_pooled"]["A4:A1"]

    assert report["pairwise"]["benchmarks"]["WritingBench"]["platforms"]["codex"][
        "contrasts"
    ]["A4:A1"] == {"wins": 3, "losses": 4, "ties": 1}
    assert cell["wins"] == 1
    assert cell["losses"] == 1
    assert cell["ties"] == 2
    assert cell["prompt_total"] == 4
    assert cell["presentation_disagreements"] == 2
    assert cell == {
        "wins": 1,
        "losses": 1,
        "ties": 2,
        "n_non_tie": 2,
        "win_rate": 0.5,
        "p_raw": 1.0,
        "p_holm_report_local": 1.0,
        "wilson_low": pytest.approx(0.094531205734, rel=1e-9),
        "wilson_high": pytest.approx(0.905468794266, rel=1e-9),
        "presentation_disagreements": 2,
        "judge_disagreements": 0,
        "judge_prompt_observations": 4,
        "prompt_total": 4,
    }
    assert record_cell["wins"] == 3
    assert record_cell["losses"] == 4
    assert record_cell["ties"] == 1


def test_aggregate_exposes_wilson_and_pooled_collapsed_significance_difference(
    tmp_path: Path,
) -> None:
    root = tmp_path / "runs"
    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps({"input": 0, "cached_input": 0, "output": 0}))
    for index in range(12):
        a4 = _run(root, "WritingBench", "A4", f"p{index}")
        a1 = _run(root, "WritingBench", "A1", f"p{index}")
        pair = a4 / "scores" / "pairwise" / "judge-1" / f"pair-{index}"
        # A4 wins one presentation and ties the other. The prompt-level
        # estimand therefore records a tie, while the pooled sensitivity
        # analysis retains one A4 win per pair.
        _score_manifest(
            pair,
            "pairwise",
            [a4, a1],
            _pairwise_records(("A", "tie")),
        )

    report = aggregate_module.aggregate_runs(
        [root],
        generation_prices=prices,
        judge_prices=prices,
        output_dir=tmp_path / "out",
        contrasts=(("A4", "A1"),),
    )
    cell = report["pairwise"]["benchmarks"]["WritingBench"]["platforms"]["codex"][
        "prompt_collapsed_across_judges"
    ]["A4:A1"]
    record_cell = report["pairwise"]["benchmarks"]["WritingBench"]["platforms"][
        "codex"
    ]["record_pooled"]["A4:A1"]

    assert cell["ties"] == 12
    assert cell["p_raw"] == 1.0
    assert record_cell["wins"] == 12
    assert record_cell["losses"] == 0
    assert record_cell["p_raw"] == pytest.approx(0.00048828125)
    assert record_cell["wilson_low"] == pytest.approx(0.7575, abs=0.01)


def test_prompt_collapse_is_one_unique_prompt_across_judges(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps({"input": 0, "cached_input": 0, "output": 0}))
    judge_outcomes = {
        "judge-1": (("A", "B"), ("B", "A"), ("B", "A"), ("A", "B")),
        "judge-2": (("A", "B"), ("A", "B"), ("B", "A"), ("A", "B")),
    }
    for index in range(4):
        a4 = _run(root, "WritingBench", "A4", f"p{index}")
        a1 = _run(root, "WritingBench", "A1", f"p{index}")
        for judge_id, outcomes in judge_outcomes.items():
            pair = a4 / "scores" / "pairwise" / judge_id / f"pair-{index}"
            _score_manifest(
                pair,
                "pairwise",
                [a4, a1],
                _pairwise_records(outcomes[index]),
                judge_id=judge_id,
            )

    report = aggregate_module.aggregate_runs(
        [root],
        generation_prices=prices,
        judge_prices=prices,
        output_dir=tmp_path / "out",
        contrasts=(("A4", "A1"),),
    )
    data = report["pairwise"]["benchmarks"]["WritingBench"]["platforms"]["codex"]
    collapsed = data["prompt_collapsed_across_judges"]["A4:A1"]

    assert collapsed["wins"] == 2
    assert collapsed["losses"] == 1
    assert collapsed["ties"] == 1
    assert collapsed["prompt_total"] == 4
    assert collapsed["judge_disagreements"] == 1
    assert collapsed["judge_prompt_observations"] == 8


def test_confirmatory_cli_wires_the_three_run_holm_family(tmp_path: Path) -> None:
    parser = aggregate_module.build_parser()
    args = parser.parse_args(
        [
            "--runs-root",
            str(tmp_path / "run-1"),
            "--holm-family-root",
            str(tmp_path / "run-1"),
            "--holm-family-root",
            str(tmp_path / "run-2"),
            "--holm-family-root",
            str(tmp_path / "run-3"),
            "--generation-prices",
            str(tmp_path / "generation.json"),
            "--judge-prices",
            str(tmp_path / "judge.json"),
            "--output-dir",
            str(tmp_path / "out"),
            "--contrasts",
            "A4:A1,A4:A2,A4:A3,A4:A5,A4:A6,A7:A1,A7:A4,A7:A5",
        ]
    )

    assert args.holm_family_root == [
        tmp_path / "run-1",
        tmp_path / "run-2",
        tmp_path / "run-3",
    ]
    assert args.contrasts == aggregate_module.CONFIRMATORY_CONTRASTS


def test_confirmatory_cli_accepts_documented_multi_root_example(
    tmp_path: Path,
) -> None:
    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps({"input": 0, "cached_input": 0, "output": 0}))
    output_dir = tmp_path / "out"

    assert (
        aggregate_module.main(
            [
                "--runs-root",
                str(tmp_path / "run-1"),
                "--holm-family-root",
                str(tmp_path / "run-1"),
                "--holm-family-root",
                str(tmp_path / "run-2"),
                "--holm-family-root",
                str(tmp_path / "run-3"),
                "--generation-prices",
                str(prices),
                "--judge-prices",
                str(prices),
                "--output-dir",
                str(output_dir),
                "--contrasts",
                "A4:A1,A4:A2,A4:A3,A4:A5,A4:A6,A7:A1,A7:A4,A7:A5",
            ]
        )
        == 0
    )
    assert (output_dir / "aggregation.json").is_file()
    assert (output_dir / "aggregation.md").is_file()


def test_confirmatory_cli_rejects_missing_holm_family(tmp_path: Path) -> None:
    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps({"input": 0, "cached_input": 0, "output": 0}))

    with pytest.raises(SystemExit):
        aggregate_module.main(
            [
                "--runs-root",
                str(tmp_path / "run-1"),
                "--generation-prices",
                str(prices),
                "--judge-prices",
                str(prices),
                "--output-dir",
                str(tmp_path / "out"),
                "--contrasts",
                "A4:A1,A4:A2,A4:A3,A4:A5,A4:A6,A7:A1,A7:A4,A7:A5",
            ]
        )


def test_confirmatory_cli_rejects_duplicate_holm_family_root(tmp_path: Path) -> None:
    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps({"input": 0, "cached_input": 0, "output": 0}))
    root = tmp_path / "run-1"

    with pytest.raises(ValueError, match="unique"):
        aggregate_module.main(
            [
                "--runs-root",
                str(root),
                "--holm-family-root",
                str(root),
                "--holm-family-root",
                str(root),
                "--holm-family-root",
                str(tmp_path / "run-3"),
                "--generation-prices",
                str(prices),
                "--judge-prices",
                str(prices),
                "--output-dir",
                str(tmp_path / "out"),
                "--contrasts",
                "A4:A1,A4:A2,A4:A3,A4:A5,A4:A6,A7:A1,A7:A4,A7:A5",
            ]
        )


def test_confirmatory_cli_rejects_current_root_outside_holm_family(
    tmp_path: Path,
) -> None:
    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps({"input": 0, "cached_input": 0, "output": 0}))

    with pytest.raises(ValueError, match="member of the Holm family"):
        aggregate_module.main(
            [
                "--runs-root",
                str(tmp_path / "run-1"),
                "--holm-family-root",
                str(tmp_path / "run-2"),
                "--holm-family-root",
                str(tmp_path / "run-3"),
                "--holm-family-root",
                str(tmp_path / "run-4"),
                "--generation-prices",
                str(prices),
                "--judge-prices",
                str(prices),
                "--output-dir",
                str(tmp_path / "out"),
                "--contrasts",
                "A4:A1,A4:A2,A4:A3,A4:A5,A4:A6,A7:A1,A7:A4,A7:A5",
            ]
        )


def test_holm_adjustment_handles_the_24_cell_family() -> None:
    raw = [0.001, 0.002] + [0.5] * 22

    adjusted = aggregate_module.holm_adjusted_pvalues(raw)

    assert adjusted[0] == pytest.approx(0.024)
    assert adjusted[1] == pytest.approx(0.046)
    assert all(value == 1.0 for value in adjusted[2:])
