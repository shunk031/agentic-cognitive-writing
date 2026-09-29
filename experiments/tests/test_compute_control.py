from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from agentic_cogwriter.analysis.compute_control import (
    PairObservation,
    analyze_pairs,
    analyze_replicates,
    load_judged_pairs,
    ratio_bin,
)


def _run(
    root: Path, condition: str, prompt: str, total: int, attempts: int = 1
) -> Path:
    path = root / "WritingBench" / condition / "codex" / prompt
    path.mkdir(parents=True)
    manifest = {
        "status": "completed",
        "started_at": "2026-01-01T00:00:00+00:00",
        "attempts": attempts,
        "budget_used_tokens": total,
        "token_accounting": {
            "status": "observed",
            "output_tokens": total - 100,
            "reasoning_output_tokens": 100,
            "total_tokens": total,
        },
        "inputs": {
            "benchmark_name": "WritingBench",
            "condition_id": condition,
            "prompt_id": prompt,
            "platform": "codex",
        },
    }
    (path / "run-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return path


def _score(root: Path, runs: list[Path], winners: tuple[str, str]) -> None:
    score_dir = root / "scores" / "pairwise" / "judge"
    score_dir.mkdir(parents=True)

    def digest(run: Path) -> str:
        return (
            "sha256:"
            + hashlib.sha256((run / "run-manifest.json").read_bytes()).hexdigest()
        )

    (score_dir / "scores.jsonl").write_text(
        "".join(
            json.dumps({"presentation": presentation, "winner": winner}) + "\n"
            for presentation, winner in zip(("A|B", "B|A"), winners, strict=True)
        ),
        encoding="utf-8",
    )
    (score_dir / "scores-manifest.json").write_text(
        json.dumps(
            {
                "task": "pairwise",
                "judge": {"judge_id": "judge"},
                "source_runs": [{"run_manifest_sha256": digest(run)} for run in runs],
                "tournament": {
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
                },
            }
        ),
        encoding="utf-8",
    )


def _pair(left_tokens: float, right_tokens: float, verdict: str) -> PairObservation:
    return PairObservation(
        benchmark="WritingBench",
        prompt="p1",
        judge_id="judge",
        left_condition="A4",
        right_condition="A1",
        left_compute_tokens=left_tokens,
        right_compute_tokens=right_tokens,
        verdict=verdict,
    )


def test_load_judged_pairs_reads_real_manifest_and_score_fixture(
    tmp_path: Path,
) -> None:
    root = tmp_path / "runs"
    left = _run(root, "A4", "p1", 200)
    right = _run(root, "A1", "p1", 100, attempts=2)
    _score(root, [left, right], ("A", "B"))

    rows = load_judged_pairs(root, judge_id="judge")

    assert len(rows) == 1
    assert rows[0].left_compute_tokens == 200
    assert rows[0].right_compute_tokens == 50
    assert rows[0].compute_ratio == 4
    assert rows[0].verdict == "left"


def test_hand_computed_spearman_and_matched_band_summary() -> None:
    rows = [
        _pair(100, 100, "left"),
        _pair(200, 100, "left"),
        _pair(300, 100, "right"),
        _pair(400, 100, "right"),
    ]

    report = analyze_pairs(rows)["by_contrast"]["A4:A1"]

    assert report["compute_matched"]["within_1.25"]["pairs"] == 1
    assert report["compute_matched"]["within_1.25"]["win_rate"] == 1
    assert report["spearman"]["rho"] == pytest.approx(-0.8944271909999159)
    assert ratio_bin(0.5) == "0.50-0.67"
    assert ratio_bin(0.8) == "0.80-0.91"


def test_replication_analysis_pools_rows_without_deduplicating_replicates() -> None:
    first = [_pair(100, 100, "left")]
    second = [_pair(100, 100, "right")]

    report = analyze_replicates({"one": first, "two": second})

    assert report["pooled"]["pair_count"] == 2
    assert report["per_replication"]["one"]["pair_count"] == 1
    assert (
        report["per_replication"]["two"]["by_contrast"]["A4:A1"]["focal"]["losses"] == 1
    )


def test_analysis_keeps_requested_contrasts_when_no_pairs_are_eligible() -> None:
    report = analyze_replicates({"one": []})["pooled"]

    assert set(report["by_contrast"]) == {
        "A4:A1",
        "A4:A2",
        "A4:A3",
        "A7:A4",
    }
    assert report["by_contrast"]["A7:A4"]["focal"]["pairs"] == 0
