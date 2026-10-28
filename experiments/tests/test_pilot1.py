import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from agentic_cogwriter.analysis.pilot1 import (
    ITEMS,
    MONITOR_SKILLS,
    SINGLE_SECTION_ITEMS,
    SKILL_HASHES,
    analyze,
    leaks,
    load_runs,
    schedule,
    sign_flip_p,
    simulate,
)
from agentic_cogwriter.paths import REPOSITORY_ROOT
from agentic_cogwriter.runner.runner import followup_message

PRESERVED = {"locality": 0.0, "mean_similarity": 1.0}
REWRITTEN = {"locality": 1.0, "mean_similarity": 0.6}
STAGED_TASK = b"## Assignment\nWrite a memo.\n"
RESUME = ["exec", "resume", "--config", 'sandbox_mode="workspace-write"']


def _sha(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _event(tool: str, thread: str, prompt: str) -> str:
    item = {
        "type": "collab_tool_call",
        "tool": tool,
        "receiver_thread_ids": [thread],
        "status": "completed",
        "prompt": prompt,
    }
    return json.dumps({"type": "item.completed", "item": item}) + "\n"


def _message(item: str) -> str:
    return f"Apply change {ITEMS.index(item)}.\n"


def _write_run(root: Path, run: dict[str, Any], sections: dict) -> dict[str, Any]:
    """Write one counted two-turn run, its check, and its map entry."""

    arm, item = run["arm"], run["item"]
    run_dir = root / "out" / run["label"] / "DoLoMiTes" / arm / "codex" / "r1"
    (run_dir / "workspace" / ".writing").mkdir(parents=True)
    (run_dir / "attempt-001.events.jsonl").write_text(
        _event("spawn_agent", "p1", "$planning goals")
    )
    (run_dir / "attempt-002.events.jsonl").write_text(
        _event("spawn_agent", "p2", "$planning change")
        + _event("spawn_agent", "r2", "$reviewing check")
    )
    skill = MONITOR_SKILLS[arm]
    change = followup_message(_message(item))
    sent = f"{change}\nRead the skill file at plugin/skills/{skill}/SKILL.md."
    (run_dir / "followup.txt").write_text(sent)
    task = STAGED_TASK + f"\n{change}".encode()
    (run_dir / "workspace" / ".writing" / "task.md").write_bytes(task)
    manifest = {
        "inputs": {"condition_id": arm, "prompt_id": item.split(".")[0]},
        "fidelity_gate": {"status": "scorable", "reasons": []},
        "followup": {
            "message_hash": _sha(sent.encode()),
            "task_hash": _sha(task),
            "turn1_attempts": 1,
            "turn2_started_at": "1970-01-01T00:01:00+00:00",
            "rollout_token_usage": {"turn2": {"total_tokens": 1000}},
        },
        "staged_files": {
            ".writing/task.md": _sha(STAGED_TASK),
            **{
                f"plugin/skills/{name}/SKILL.md": f"sha256:{SKILL_HASHES[name]}"
                for name in (skill, "planning", "translating", "reviewing")
            },
        },
        "models_and_execution": {
            "generator_model_id": "model",
            "decoding": {"codex_reasoning_effort": "medium"},
            "cli_version": "codex-cli 1",
            "main_plugin_commit": "c1",
            "experiments_plugin_commit": "c1",
            "command_flags": {"continuation_args": RESUME},
        },
    }
    (run_dir / "run-manifest.json").write_text(json.dumps(manifest))
    check = {
        "item": item,
        "run_dir": str(run_dir),
        "incorporated": True,
        "break_rate": 0.0,
        **(dict.fromkeys(PRESERVED) if item in SINGLE_SECTION_ITEMS else sections),
    }
    out = root / "checks" / f"{run['label']}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(check))
    return {**run, "run_dir": str(run_dir), "check": str(out)}


def _files(tmp_path: Path, a6: dict) -> tuple[list[dict[str, Any]], Path]:
    entries = [
        _write_run(tmp_path, run, a6 if run["arm"] == "A6" else PRESERVED)
        for run in schedule()
    ]
    items = tmp_path / "items.json"
    items.write_text(json.dumps([{"id": i, "message": _message(i)} for i in ITEMS]))
    return entries, items


def _load(tmp_path: Path, entries: list[dict[str, Any]], items: Path) -> list:
    run_map = tmp_path / "run-map.jsonl"
    run_map.write_text("".join(json.dumps(entry) + "\n" for entry in entries))
    return load_runs(run_map, items, "c1")


def test_sign_flip_p_enumerates_every_sign_assignment() -> None:
    assert sign_flip_p([1, 1, 1]) == 0.25
    assert sign_flip_p([0.5, -0.5]) == 1.0
    assert sign_flip_p([1] * 12) == pytest.approx(2 / 2**12)


def test_schedule_orders_the_84_runs_with_neutral_labels() -> None:
    runs = schedule()

    assert runs == schedule()
    assert len({(r["arm"], r["item"], r["replicate"]) for r in runs}) == 84
    assert [r["label"] for r in runs][:2] == ["p1-01", "p1-02"]
    assert runs[-1]["label"] == "p1-84"


def test_pinned_skill_hashes_match_the_repository() -> None:
    paths = {
        "agentic-cog-writer": "plugin/skills/agentic-cog-writer",
        "cognitive-writing-fixed-order": (
            "experiments/plugin/skills/cognitive-writing-fixed-order"
        ),
        "cognitive-writing-fixed-order-skip": (
            "experiments/plugin/skills/cognitive-writing-fixed-order-skip"
        ),
        **{role: f"plugin/skills/{role}" for role in ("planning", "translating")},
        "reviewing": "plugin/skills/reviewing",
    }

    assert {
        name: hashlib.sha256(
            (REPOSITORY_ROOT / path / "SKILL.md").read_bytes()
        ).hexdigest()
        for name, path in paths.items()
    } == SKILL_HASHES


def test_leaks_flags_prompt_and_class_names_in_run_paths() -> None:
    assert leaks(Path("/runs/dolomites-673/DoLoMiTes/A4/codex/ab12"))
    assert leaks(Path("/runs/remove-batch/DoLoMiTes/A4/codex/ab12"))
    assert leaks(Path("/runs/p1_term/DoLoMiTes/A4/codex/ab12"))
    assert not leaks(Path("/runs/p1-01/DoLoMiTes/A4/codex/add1"))


def test_pilot_passes_when_a4_preserves_more_than_a6(tmp_path: Path) -> None:
    result = analyze(_load(tmp_path, *_files(tmp_path, REWRITTEN)))

    assert result["runs"]["A4"] == {"total": 28, "counted": 28}
    assert result["excluded"] == []
    assert result["means"]["A6"]["U"] == 1.0
    assert result["means"]["A4"]["K_delegations"] == 2
    assert result["means"]["A4"]["K_tokens"] == 1000
    u = result["contrasts"]["A4-A6"]["U"]
    assert (u["items"], u["mean"]) == (12, -1.0)
    assert u["p_two_sided"] == pytest.approx(2 / 2**12)
    assert result["contrasts"]["A4-A6"]["C"]["items"] == 14
    assert (result["G1"], result["G2"], result["G3"]) == (True, True, "no_difference")
    assert result["decision"] == "GO"


def test_pilot_fails_when_a6_preserves_as_much(tmp_path: Path) -> None:
    result = analyze(_load(tmp_path, *_files(tmp_path, PRESERVED)))

    assert result["G1"] is False
    assert result["decision"] == "NO-GO"


def test_g2_is_a_point_estimate_guard(tmp_path: Path) -> None:
    entries, items = _files(tmp_path, REWRITTEN)
    a4 = [e for e in entries if e["arm"] == "A4"]

    def miss(runs: list[dict[str, Any]]) -> bool:
        for entry in runs:
            _edit_json(Path(entry["check"]), incorporated=False)
        return analyze(_load(tmp_path, entries, items))["G2"]

    # Each miss lowers A4's mean C by 0.5 / 14: three misses stay within 0.15.
    assert miss(a4[:3]) is True
    assert miss(a4[3:6]) is False


def _edit_json(path: Path, **fields: Any) -> None:
    path.write_text(json.dumps({**json.loads(path.read_text()), **fields}))


def test_runs_are_excluded_with_every_reason(tmp_path: Path) -> None:
    entries, items = _files(tmp_path, REWRITTEN)
    a4 = [Path(e["run_dir"]) for e in entries if e["arm"] == "A4"]
    refused = next(e for e in entries if e["arm"] == "A6")
    Path(refused["check"]).unlink()
    refused["check_error"] = "exposure scan refused the run"
    (a4[0] / "followup.txt").write_text("no change block")
    (a4[1] / "workspace" / ".writing" / "task.md").write_text("edited")
    manifest = json.loads((a4[2] / "run-manifest.json").read_text())
    manifest["staged_files"]["plugin/skills/planning/SKILL.md"] = "sha256:0"
    manifest["models_and_execution"]["command_flags"]["continuation_args"] = []
    (a4[2] / "run-manifest.json").write_text(json.dumps(manifest))
    _edit_json(a4[3] / "run-manifest.json", followup=None)
    _edit_json(
        a4[4] / "run-manifest.json",
        fidelity_gate={"status": "rejected", "reasons": ["unclosed child"]},
    )
    leaked = a4[5].parents[4] / "x-remove"
    a4[5].parents[3].rename(leaked)
    entry = next(e for e in entries if Path(e["run_dir"]) == a4[5])
    entry["run_dir"] = str(leaked / a4[5].relative_to(a4[5].parents[3]))

    result = analyze(_load(tmp_path, entries, items))
    reasons = {Path(e["run_dir"]).parts[-5]: e["reasons"] for e in result["excluded"]}

    assert reasons == {
        Path(refused["run_dir"]).parts[-5]: ["exposure scan refused the run"],
        a4[0].parts[-5]: [
            "turn-2 message is not the item's change and the arm's clause"
        ],
        a4[1].parts[-5]: ["task.md is not the staged task and the item's change"],
        a4[2].parts[-5]: [
            "staged planning skill differs from the pinned hash",
            "resume does not keep the workspace-write sandbox",
        ],
        a4[3].parts[-5]: ["no follow-up turn"],
        a4[4].parts[-5]: ["gate: unclosed child"],
        "x-remove": [
            "run directory names a prompt or a change class",
            "checker output is for another run or item",
        ],
    }
    assert result["runs"]["A4"] == {"total": 28, "counted": 22}
    assert result["decision"] == "INVALID"


def test_the_run_map_must_be_complete_and_unique(tmp_path: Path) -> None:
    entries, items = _files(tmp_path, REWRITTEN)

    with pytest.raises(ValueError, match="84 expected runs"):
        _load(tmp_path, entries[1:], items)
    with pytest.raises(ValueError, match="more than once"):
        _load(
            tmp_path,
            [*entries[:-1], {**entries[-1], "run_dir": entries[0]["run_dir"]}],
            items,
        )


def test_runs_must_share_one_configuration(tmp_path: Path) -> None:
    entries, items = _files(tmp_path, REWRITTEN)
    path = Path(entries[0]["run_dir"]) / "run-manifest.json"
    manifest = json.loads(path.read_text())
    manifest["models_and_execution"]["cli_version"] = "codex-cli 2"
    path.write_text(json.dumps(manifest))

    with pytest.raises(ValueError, match="differ in configuration"):
        _load(tmp_path, entries, items)


def test_simulation_passes_g1_when_a6_always_rewrites() -> None:
    assert simulate(1.0, 0.0, sims=5)["G1"] == 1.0


def test_runs_must_use_the_run_commit(tmp_path: Path) -> None:
    entries, items = _files(tmp_path, REWRITTEN)
    run_map = tmp_path / "run-map.jsonl"
    run_map.write_text("".join(json.dumps(entry) + "\n" for entry in entries))

    with pytest.raises(ValueError, match="run commit c2"):
        load_runs(run_map, items, "c2")
