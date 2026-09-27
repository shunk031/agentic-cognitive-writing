from __future__ import annotations

import hashlib
import json
from pathlib import Path

from agentic_cogwriter.analysis.cross_family import aggregate_cross_family, main
from agentic_cogwriter.runner.hashing import sha256_json


def _run(root: Path, benchmark: str, condition: str, prompt: str) -> Path:
    path = root / benchmark / condition / "codex" / prompt
    path.mkdir(parents=True)
    prompt_row = {
        "prompt_id": prompt,
        "benchmark_name": benchmark,
        "source_version": "test@1",
        "prompt_text": "Write a memo.",
        "requested_output_constraints": {},
    }
    prompt_row["hash"] = sha256_json(prompt_row)
    manifest = {
        "schema_version": 1,
        "started_at": "2026-01-01T00:00:00+00:00",
        "status": "completed",
        "inputs": {
            "benchmark_name": benchmark,
            "condition_id": condition,
            "prompt_id": prompt,
            "platform": "codex",
            "prompt_hash": prompt_row["hash"],
            "prompt_manifest_hash": "test",
        },
    }
    (path / "run-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return path


def _run_hash(path: Path) -> str:
    return (
        "sha256:"
        + hashlib.sha256((path / "run-manifest.json").read_bytes()).hexdigest()
    )


def _pair(
    root: Path,
    source_runs: list[Path],
    judge_id: str,
    winners: tuple[str, str],
    *,
    model: str = "us.anthropic.claude-sonnet-5",
    effort: str = "medium",
) -> None:
    pair_id = (
        f"{source_runs[0].parent.parent.name}-{source_runs[1].parent.parent.name}-"
        f"{source_runs[0].name}"
    )
    path = root / "scores" / judge_id / pair_id
    path.mkdir(parents=True)
    records = [
        {"presentation": presentation, "winner": winner}
        for presentation, winner in zip(("A|B", "B|A"), winners, strict=True)
    ]
    (path / "scores.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    manifest = {
        "task": "pairwise",
        "judge": {
            "judge_id": judge_id,
            "model": model,
            "effort": effort,
            "seed": 20260908,
            "max_output_tokens": 8192,
        },
        "records": [{"usage": {}} for _ in records],
        "source_runs": [{"run_manifest_sha256": _run_hash(run)} for run in source_runs],
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
    (path / "scores-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _fixture(root: Path) -> None:
    for benchmark, prompt, outcomes in (
        ("WritingBench", "p1", (("A", "B"), ("A", "B"))),
        ("WritingBench", "p2", (("A", "B"), ("B", "A"))),
        ("WritingBench", "p3", (("tie", "B"), ("tie", "tie"))),
        ("HelloBench", "p4", (("B", "A"), ("B", "A"))),
    ):
        source_runs = [
            _run(root, benchmark, "A4", prompt),
            _run(root, benchmark, "A1", prompt),
        ]
        for judge_id, pair_outcomes in zip(("claude", "gpt"), outcomes, strict=True):
            _pair(root, source_runs, judge_id, pair_outcomes)


def test_aggregate_cross_family_groups_and_compares_both_levels(
    tmp_path: Path,
) -> None:
    _fixture(tmp_path)

    report = aggregate_cross_family(
        tmp_path,
        cross_family_judge_id="claude",
        reference_judge_id="gpt",
        contrasts=(("A4", "A1"),),
    )

    metric = report["contrasts"]["A4:A1"]
    assert metric["n"] == 4
    assert metric["wins"] == 2
    assert metric["losses"] == 1
    assert metric["ties"] == 1
    assert metric["commit_rate"]["numerator"] == 3
    assert metric["commit_rate"]["denominator"] == 4
    assert metric["win_rate"]["numerator"] == 2
    assert metric["win_rate"]["denominator"] == 3
    assert metric["presentation_agreement"] == {"numerator": 5, "denominator": 8}
    assert metric["prompt_collapsed_agreement"] == {
        "numerator": 3,
        "denominator": 4,
    }
    assert metric["direction_conflicts"] == 1
    assert metric["benchmarks"]["WritingBench"]["n"] == 3
    assert metric["benchmarks"]["HelloBench"]["losses"] == 1
    assert report["pooled"]["commit_rate"]["numerator"] == 3
    assert "holm" not in json.dumps(report).lower()


def test_cross_family_cli_writes_json(tmp_path: Path) -> None:
    _fixture(tmp_path / "runs")
    output = tmp_path / "summary.json"

    assert (
        main(
            [
                "--runs-root",
                str(tmp_path / "runs"),
                "--cross-family-judge",
                "claude",
                "--reference-judge",
                "gpt",
                "--contrasts",
                "A4:A1",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["provenance"]["cross_family_model_id"] == (
        "us.anthropic.claude-sonnet-5"
    )
    assert report["provenance"]["effort"] == "medium"
    assert report["provenance"]["seed"] == 20260908
    assert report["provenance"]["maximum_output_tokens"] == 8192
    assert "no multiplicity correction" in report["note"].lower()
