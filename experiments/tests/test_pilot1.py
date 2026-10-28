import json
from pathlib import Path
from typing import Any

import pytest

from agentic_cogwriter.analysis.pilot1 import analyze, load_runs, sign_flip_p

PRESERVED = {"locality": 0.0, "mean_similarity": 1.0}
REWRITTEN = {"locality": 1.0, "mean_similarity": 0.6}


def _event(tool: str, thread: str, **item: Any) -> str:
    item = {
        "type": "collab_tool_call",
        "tool": tool,
        "receiver_thread_ids": [thread],
        "status": "completed",
        **item,
    }
    return json.dumps({"type": "item.completed", "item": item}) + "\n"


def _run(
    root: Path, arm: str, item: str, k: int, sections: dict, gate: str = "scorable"
) -> None:
    """Write one two-turn run with two turn-2 delegations and its check."""

    run_dir = root / "runs" / f"{arm}-{item}-{k}"
    run_dir.mkdir(parents=True)
    (run_dir / "attempt-001.events.jsonl").write_text(
        _event("spawn_agent", "p1", prompt="$planning goals")
    )
    (run_dir / "attempt-002.events.jsonl").write_text(
        _event("spawn_agent", "p2", prompt="$planning change")
        + _event("spawn_agent", "r2", prompt="$reviewing check")
    )
    manifest = {
        "inputs": {"condition_id": arm, "prompt_id": item.split(".")[0]},
        "fidelity_gate": {
            "status": gate,
            "reasons": [] if gate == "scorable" else ["x"],
        },
        "followup": {
            "turn1_attempts": 1,
            "turn2_started_at": "1970-01-01T00:01:00+00:00",
            "rollout_token_usage": {"turn2": {"total_tokens": 1000}},
        },
    }
    (run_dir / "run-manifest.json").write_text(json.dumps(manifest))
    check = {
        "item": item,
        "run_dir": str(run_dir),
        "incorporated": True,
        "break_rate": 0.0,
        **(sections if item.startswith("multi") else dict.fromkeys(PRESERVED)),
    }
    out = root / "checks" / f"{arm}-{item}-{k}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(check))


ITEMS = [f"multi{i}.term" for i in range(12)] + ["single0.term", "single1.term"]


def _pilot(tmp_path: Path, a6: dict) -> dict[str, Any]:
    for item in ITEMS:
        for k in range(2):
            _run(tmp_path, "A4", item, k, PRESERVED)
            _run(tmp_path, "A6", item, k, a6)
            _run(tmp_path, "A6s", item, k, PRESERVED)
    _run(tmp_path, "A4", ITEMS[0], 2, REWRITTEN, gate="rejected")
    return analyze(load_runs(tmp_path / "checks"))


def test_sign_flip_p_enumerates_every_sign_assignment() -> None:
    assert sign_flip_p([1, 1, 1]) == 0.25
    assert sign_flip_p([1, 1, 1], alternative="greater") == 0.125
    assert sign_flip_p([0, 0, 0], null=-0.15, alternative="greater") == 0.125
    assert sign_flip_p([0, 0, 0], null=0.05, alternative="less") == 0.125
    assert sign_flip_p([0.5, -0.5]) == 1.0


def test_pilot_passes_when_a4_preserves_more_than_a6(tmp_path: Path) -> None:
    result = _pilot(tmp_path, REWRITTEN)

    assert result["runs"]["A4"] == {"total": 29, "scorable": 28}
    assert [e["reasons"] for e in result["excluded"]] == [["x"]]
    assert result["means"]["A6"]["U"] == 1.0
    assert result["means"]["A4"]["K_delegations"] == 2
    assert result["means"]["A4"]["K_tokens"] == 1000
    u = result["contrasts"]["A4-A6"]["U"]
    assert u["items"] == 12
    assert u["mean"] == -1.0
    assert u["p_two_sided"] == pytest.approx(2 / 2**12)
    assert result["contrasts"]["A4-A6"]["C"]["items"] == 14
    assert (result["G1"], result["G2"], result["G3"]) == (True, True, "no_difference")
    assert result["decision"] == "GO"


def test_pilot_fails_when_a6_preserves_as_much(tmp_path: Path) -> None:
    result = _pilot(tmp_path, PRESERVED)

    assert result["G1"] is False
    assert result["decision"] == "NO-GO"


def test_pilot_is_invalid_when_an_arm_has_too_few_counted_runs(
    tmp_path: Path,
) -> None:
    for item in ITEMS[:12]:
        for arm in ("A4", "A6", "A6s"):
            for k in range(2):
                _run(tmp_path, arm, item, k, PRESERVED if arm != "A6" else REWRITTEN)

    assert analyze(load_runs(tmp_path / "checks"))["decision"] == "INVALID"
