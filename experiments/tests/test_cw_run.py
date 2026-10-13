"""Runner support for cw arms: end-to-end gates, the token rule, failure kinds."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from test_runner_contracts import _config, _prompt

from agentic_cogwriter.runner import cw_run
from agentic_cogwriter.runner.errors import ExecutionError
from agentic_cogwriter.runner.execution import ExecutionResult
from agentic_cogwriter.runner.runner import ExperimentRunner

DRAFT = "The memo states the provided facts.\n"
DRAFT_TWO = "The memo now states the provided facts in full.\n"


def _rollout(
    path: Path,
    thread: str,
    parent: str | None,
    records: list[dict],
    started: str = "2026-10-13T00:00:00Z",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {"id": thread, **({"parent_thread_id": parent} if parent else {})}
    lines = [{"timestamp": started, "type": "session_meta", "payload": meta}]
    path.write_text("".join(json.dumps(r) + "\n" for r in lines + records))


def _tokens(ts: str, output: int, inputs: int = 100, cached: int = 50) -> dict:
    usage = {
        "output_tokens": output,
        "input_tokens": inputs,
        "cached_input_tokens": cached,
    }
    return {
        "timestamp": ts,
        "type": "event_msg",
        "payload": {"type": "token_count", "info": {"total_token_usage": usage}},
    }


def _user(text: str) -> dict:
    return {
        "timestamp": "2026-10-13T00:00:01Z",
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
        },
    }


def _settings(model: str = "gpt-5.6-luna") -> dict:
    return {
        "timestamp": "2026-10-13T00:00:01Z",
        "type": "turn_context",
        "payload": {"model": model, "effort": "medium", "service_tier": None},
    }


class SimulatedMonitor:
    """Plays an A4 run: runs the staged cw and emits Codex-shaped records."""

    def __init__(
        self,
        *,
        fork: bool = False,
        write_while_open: bool = False,
        child_model: str = "gpt-5.6-luna",
        stop_turn_two: bool = True,
    ) -> None:
        self.fork = fork
        self.write_while_open = write_while_open
        self.child_model = child_model
        self.stop_turn_two = stop_turn_two
        self.turn = 0
        self.parent_records: list[dict] = []

    def cw(self, cwd: Path, thread: str, *args: str, stdin: str = "") -> list[str]:
        result = subprocess.run(
            [sys.executable, str(cwd / ".agents/cw/cw.py"), *args],
            cwd=cwd,
            input=stdin,
            capture_output=True,
            text=True,
            env={**os.environ, "CODEX_THREAD_ID": thread},
            check=True,
        )
        return result.stdout.splitlines()

    def run(self, command, *, cwd, timeout_seconds, env=None):
        self.turn += 1
        writing = cwd / ".writing"
        sessions = Path(env["CODEX_HOME"]) / "sessions"
        prompt = command[-1]
        events: list[dict] = [{"type": "thread.started", "thread_id": "parent"}]
        if self.turn == 1:
            self.parent_records = [_settings(), _user(prompt)]
        self.parent_records.append(_tokens(f"2026-10-13T0{self.turn}:00:02Z", 10))

        def item(kind: str, **fields) -> None:
            events.append(
                {
                    "type": "item.completed",
                    "item": {"id": f"i{len(events)}", "type": kind, **fields},
                }
            )

        steps = [
            ("planning", ["--goals"]),
            ("translating", ["--scope", "G1"]),
            ("reviewing", []),
        ][self.turn - 1 :]
        draft = DRAFT if self.turn == 1 else DRAFT_TWO
        for index, (process, flags) in enumerate(steps):
            out = self.cw(cwd, "parent", "step", process, *flags, "--why", "state")
            item(
                "command_execution", command="cw step", aggregated_output="\n".join(out)
            )
            child = f"child-{self.turn}-{index}"
            spawn_line = json.loads(out[0])["spawn"]
            item(
                "collab_tool_call",
                tool="spawn_agent",
                prompt=spawn_line,
                receiver_thread_ids=[child],
            )
            n = json.loads(out[0])["step"]
            if process == "planning":
                (writing / "goals.md").write_text(
                    '- [G1] The memo uses the facts | src: "Write a memo."\n'
                )
                (writing / f"history/step-{n:02d}/plan.md").write_text("Plan.\n")
            elif process == "translating":
                (writing / "draft.md").write_text(draft)
            else:
                review = {
                    "verdicts": [
                        {
                            "goal": "G1",
                            "met": True,
                            "evidence": "states the provided facts",
                        }
                    ],
                    "proposals": [],
                    "findings": [],
                }
                self.cw(cwd, child, "review", stdin=json.dumps(review))
            if self.write_while_open:
                item("command_execution", command="cat .writing/draft.md")
            state = {child: {"status": "completed", "message": "done"}}
            item(
                "collab_tool_call",
                tool="wait",
                receiver_thread_ids=[child],
                agents_states=state,
            )
            item(
                "collab_tool_call",
                tool="close_agent",
                receiver_thread_ids=[child],
                agents_states=state,
            )
            records = [
                _settings(self.child_model),
                _user(f"<skill>\n<name>{process}</name>\n"),
                _user(spawn_line),
            ]
            if self.fork:
                records.insert(1, _user(prompt))
            records.append(_tokens(f"2026-10-13T0{self.turn}:0{index + 1}:00Z", 5))
            _rollout(sessions / f"rollout-{child}.jsonl", child, "parent", records)
        if self.turn == 1 or self.stop_turn_two:
            out = self.cw(cwd, "parent", "stop", "--reason", "met", "--why", "all met")
            item(
                "command_execution", command="cw stop", aggregated_output="\n".join(out)
            )
        item("agent_message", text=f"Stopped turn {self.turn}.")
        events.append({"type": "turn.completed", "usage": {"output_tokens": 30}})
        self.parent_records.append(_tokens(f"2026-10-13T0{self.turn}:09:00Z", 30))
        _rollout(sessions / "rollout-parent.jsonl", "parent", None, self.parent_records)
        stdout = "".join(json.dumps(e) + "\n" for e in events).encode()
        return ExecutionResult(
            returncode=0, stdout=stdout, stderr=b"", session_id="parent"
        )


def _run(tmp_path: Path, executor: SimulatedMonitor, followup: str | None = None):
    # The runner refuses provider homes under the system temporary directory.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr("tempfile.gettempdir", lambda: str(tmp_path / "system-temp"))
        return _run_patched(tmp_path, executor, followup)


def _run_patched(tmp_path: Path, executor: SimulatedMonitor, followup: str | None):
    runner = ExperimentRunner(
        _config(),
        output_root=tmp_path / "runs",
        executor=executor,
        codex_home=tmp_path / "codex-home",
    )
    return runner.run_prompt(
        _prompt(), condition_id="A4", platform="codex", run_id="r", followup=followup
    )


def test_a4_run_scores_the_stop_snapshot_and_passes_every_gate(tmp_path: Path) -> None:
    result = _run(tmp_path, SimulatedMonitor())
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["status"] == "completed"
    assert manifest["cw"]["gates"] == dict.fromkeys(manifest["cw"]["gates"], True)
    assert manifest["cw"]["stop_reasons"] == {"1": "met"}
    assert manifest["language"] == {
        "value": "English",
        "source": "placeholder: majority script of the assignment",
    }
    assert (result.run_dir / "output.normalized.txt").read_text() == DRAFT
    assert (result.run_dir / "final-message.txt").read_text() == "Stopped turn 1."
    workspace = result.run_dir / "workspace"
    task = (workspace / ".writing/task.md").read_text()
    assert task.startswith("## Assignment\nWrite a memo.\n\n## Supplied context\n")
    # Roles quote the language line as a requirement source, so it is one line.
    assert task.endswith("\n\nOutput language: English\n")
    assert (
        (result.run_dir / "prompt.txt")
        .read_text()
        .endswith("\n\nOutput language: English")
    )
    assert not (workspace / "plugin/skills/agentic-cog-writer/scripts").exists()
    assert (workspace / ".agents/cw/cw.json").stat().st_mode & 0o222 == 0
    tokens = manifest["cw"]["tokens"]
    assert tokens["budget_statistic"] == 30
    assert tokens["child_inclusive"]["output_tokens"] == 45


@pytest.mark.parametrize(
    ("executor", "kind"),
    [
        (SimulatedMonitor(fork=True), "gate:fork"),
        (SimulatedMonitor(write_while_open=True), "gate:top_level_writes"),
        (SimulatedMonitor(child_model="gpt-5.6-sol"), "gate:spawn_args"),
    ],
)
def test_a4_gate_failures_set_the_failure_kind(
    tmp_path: Path, executor: SimulatedMonitor, kind: str
) -> None:
    with pytest.raises(ExecutionError, match=kind):
        _run(tmp_path, executor)
    manifest_path = tmp_path / "runs/WritingBench/A4/codex/r/run-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["status"] == "failed"
    assert manifest["failure"]["kind"] == kind


def test_a4_follow_up_scores_each_turn_from_its_own_snapshot(tmp_path: Path) -> None:
    result = _run(tmp_path, SimulatedMonitor(), followup="State the facts in full.")
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["status"] == "completed"
    assert manifest["cw"]["stop_reasons"] == {"1": "met", "2": "met"}
    assert (result.run_dir / "turn1.output.normalized.txt").read_text() == DRAFT
    assert (result.run_dir / "output.normalized.txt").read_text() == DRAFT_TWO
    request = result.run_dir / "workspace/.writing/history/turn-02-request.md"
    assert request.read_text() == "State the facts in full."


def test_a4_turn_without_its_own_stop_is_incomplete(tmp_path: Path) -> None:
    with pytest.raises(ExecutionError, match="incomplete"):
        _run(tmp_path, SimulatedMonitor(stop_turn_two=False), followup="Change it.")
    manifest_path = tmp_path / "runs/WritingBench/A4/codex/r/run-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["failure"]["kind"] == "incomplete"
    assert manifest["cw"]["gates"]["completeness"] is False


def test_fidelity_counts_returns_within_each_turn() -> None:
    from agentic_cogwriter.analysis import fidelity

    # Trimmed records of a real two-turn A4 run (smoke iteration 10). Turn 1
    # ends in R and turn 2 opens with P; that boundary is not an R>P return.
    row = fidelity.run_row(Path(__file__).parent / "fixtures/fidelity-run/A4/run")
    assert row["path"] == {1: "PTR", 2: "PTRTTR"}
    assert row["returns"] == {"R>T": 1, "R>P": 0}
    # Its turn 2 changed no requirement, so none quotes the change request.
    assert row["request_src"] == {2: (0, 0)}
    assert all(row["gates"].values())


# ---- token rule ------------------------------------------------------------


def _run_dir(tmp_path: Path) -> Path:
    run_dir = tmp_path / "run"
    (run_dir / "sessions").mkdir(parents=True)
    (run_dir / "prompt.txt").write_text("Read the skill file and follow it.")
    return run_dir


FIXTURES = Path(__file__).parent / "fixtures/token-replay"


def test_token_rule_replays_a4_hbchat047() -> None:
    # Trimmed real records of smoke run a4-hbchat047: a resumed follow-up turn
    # whose parent rollout is copied once per attempt.
    report = cw_run.token_report(FIXTURES / "a4-hbchat047")
    assert report["child_inclusive"]["output_tokens"] == 121_265
    assert report["parent_output_per_turn"] == [12_923, 27_791]
    assert report["budget_statistic"] == 27_791


def test_token_rule_subtracts_the_parent_at_the_fork() -> None:
    # Trimmed real records of an executed A3 run: the forked child's rollout
    # repeats the parent's totals (189, 325, ..., 1,476) before its own.
    report = cw_run.token_report(FIXTURES / "a3-fork")
    child = report["per_thread"]["01a0c310-60f0-7421-9d6b-46b2139d10b6"]
    assert child["output_tokens"] == 2_860 - 1_476
    assert child["input_tokens"] == 113_227 - 84_557


def test_token_rule_splits_segments_at_a_context_reset(tmp_path: Path) -> None:
    # No executed rollout contains a context reset, so this series is
    # synthetic: the reset zeroes the running totals and the segments add up.
    run_dir = _run_dir(tmp_path)
    reset = [
        _tokens("2026-10-13T00:01:00Z", 50, 500, 100),
        _tokens("2026-10-13T00:02:00Z", 5, 50, 0),
        _tokens("2026-10-13T00:03:00Z", 30, 300, 10),
    ]
    _rollout(run_dir / "sessions/attempt-001/rollout-c.jsonl", "c", None, reset)
    thread = cw_run.token_report(run_dir)["per_thread"]["c"]
    assert thread["output_tokens"] == 80
    assert thread["input_tokens"] == 800


# ---- failure classification ------------------------------------------------


def _attempt(run_dir: Path, events: list[dict], **meta) -> None:
    n = len(list(run_dir.glob("attempt-*.events.jsonl"))) + 1
    (run_dir / f"attempt-{n:03d}.events.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in events)
    )
    (run_dir / f"attempt-{n:03d}.meta.json").write_text(json.dumps(meta))


def _history(run_dir: Path, *entries: dict) -> None:
    path = run_dir / "workspace/.writing/history/history.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps({"n": 1, **e}) + "\n" for e in entries))


DONE = {"type": "turn.completed", "usage": {"output_tokens": 10}}
GATES = {"fork": True, "completeness": True}
RECONNECT = {"type": "error", "message": "Reconnecting... 1/5 (stream disconnected)"}


def _kind(run_dir: Path, **kwargs) -> str | None:
    kwargs.setdefault("harness_error", False)
    kwargs.setdefault("gate_results", GATES)
    failure = cw_run.classify_failure(run_dir, **kwargs)
    return failure and failure["kind"]


def test_failure_classifier(tmp_path: Path) -> None:
    run_dir = _run_dir(tmp_path)
    _attempt(run_dir, [DONE], timed_out=False)
    _history(run_dir, {"cmd": "stop", "turn": 1, "reason": "met"})
    assert _kind(run_dir) is None
    assert _kind(run_dir, harness_error=True) == "harness_error"
    assert _kind(run_dir, gate_results={"fork": False, "completeness": True}) == (
        "gate:fork"
    )
    assert _kind(run_dir, gate_results={"completeness": False}) == "incomplete"
    _history(
        run_dir,
        {"cmd": "stop", "refused": "the latest review lists findings"},
        {"cmd": "stop", "turn": 1, "reason": "failure", "failure": "allowance"},
    )
    # A refused stop is not a stop.
    assert cw_run.stop_reasons(run_dir) == {1: "failure"}
    assert _kind(run_dir) == "cw_failure:allowance"
    over = tmp_path / "budget"
    over.mkdir()
    _attempt(over, [{"type": "turn.completed", "usage": {"output_tokens": 64_001}}])
    assert _kind(over) == "budget"
    failed = tmp_path / "provider"
    failed.mkdir()
    _attempt(failed, [{"type": "turn.failed", "error": {"message": "429"}}])
    assert _kind(failed) == "provider_error"


def test_failure_classifier_timeouts(tmp_path: Path) -> None:
    stalled = _run_dir(tmp_path / "a")
    _rollout(
        stalled / "sessions/attempt-001/rollout-p.jsonl",
        "p",
        None,
        [_tokens("2026-10-13T00:20:00Z", 5)],
    )
    end = cw_run._timestamp("2026-10-13T00:30:00Z")
    item = {"type": "item.completed", "item": {"type": "agent_message"}}
    _attempt(stalled, [item, RECONNECT], timed_out=True, ended=end)
    assert _kind(stalled) == "timeout_provider"
    recovered = _run_dir(tmp_path / "b")
    _attempt(recovered, [RECONNECT, item], timed_out=True, ended=end)
    failure = cw_run.classify_failure(
        recovered, harness_error=False, gate_results=GATES
    )
    assert failure == {"kind": "timeout", "class": "model", "hang": False}
    hung = _run_dir(tmp_path / "c")
    spawn = {
        "type": "item.completed",
        "item": {
            "type": "collab_tool_call",
            "tool": "spawn_agent",
            "prompt": "$planning Read b and follow it. [n]",
            "receiver_thread_ids": ["child"],
        },
    }
    _attempt(hung, [spawn], timed_out=True, ended=end)
    assert cw_run.classify_failure(hung, harness_error=False, gate_results=GATES)[
        "hang"
    ]


def test_fidelity_report_reads_the_simulated_run(tmp_path: Path, capsys) -> None:
    from agentic_cogwriter.analysis import fidelity

    _run(tmp_path, SimulatedMonitor())
    assert fidelity.main([str(tmp_path / "runs")]) == 0
    table = capsys.readouterr().out
    assert "| A4 | writingbench-0001 | pass | 3/0/0/0/0 | 3/3 | yes |" in table
    assert "t1:PTR" in table and "t1:met" in table
