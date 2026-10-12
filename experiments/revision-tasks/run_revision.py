"""Run, score, and summarize the revision-task experiment.

Subcommands, each resumable:

    generate  Run each prompt and condition for two turns through the Docker runner.
    score     Judge A4 against each other condition with both presentations.
    report    Write the sanitized results JSON.

`generate` reads the generator credential from GATEWAY_API_KEY and passes it to
the container only through an anonymous env file. `score` reads the judge
endpoint and credential from GATEWAY_BASE_URL and GATEWAY_API_KEY.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from agentic_cogwriter.analysis.aggregate import exact_two_sided_sign_test
from agentic_cogwriter.analysis.common import select_canonical_runs
from agentic_cogwriter.analysis.process_sequences import (
    DELEGATED_PROCESS,
    analyze_trace_events,
)
from agentic_cogwriter.judges.config import JudgeConfig
from agentic_cogwriter.judges.scorer import score_run

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RUNS_MOUNT = REPO / "runs"  # experiments/docker/run.sh mounts this at /run-output
UV_ROOT = RUNS_MOUNT / "revtask-uv"
BENCHMARK_NAMES = {
    "writingbench": "WritingBench",
    "hellobench": "HelloBench",
    "dolomites": "DoLoMiTes",
}
FIXED_ORDER = ("planning", "translating", "reviewing")


def _changes() -> list[dict[str, Any]]:
    path = HERE / "changes.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _container_path(host: Path) -> str:
    return "/run-output/" + host.resolve().relative_to(RUNS_MOUNT.resolve()).as_posix()


def _runs(root: Path) -> dict[tuple[str, str], Any]:
    return {
        (run.prompt, run.condition): run
        for run in select_canonical_runs([root])
        if run.platform == "codex"
    }


def generate(args: argparse.Namespace) -> None:
    root = args.root.resolve()
    followups = root / "followups"
    followups.mkdir(parents=True, exist_ok=True)
    UV_ROOT.mkdir(exist_ok=True)
    rows = [
        row
        for row in _changes()
        if not args.prompts or row["prompt_id"] in args.prompts.split(",")
    ]
    existing = _runs(root)
    jobs = [
        (row, condition)
        for condition in args.conditions.split(",")
        for row in rows
        if not (
            (run := existing.get((row["prompt_id"], condition)))
            and run.status in {"completed", "started"}  # started: still in flight
        )
    ]
    print(f"{len(jobs)} jobs", flush=True)
    if "GATEWAY_API_KEY" not in os.environ:
        raise SystemExit("GATEWAY_API_KEY is not set")

    def worker(index: int) -> None:
        # Each shard holds the runner's output-root lock for one run at a time.
        shard = root / f"w{index + args.shard_offset:02d}"
        shard.mkdir(exist_ok=True)
        for row, condition in jobs[index :: args.workers]:
            followup = followups / f"{row['prompt_id']}.txt"
            followup.write_text(row["followup_message"], encoding="utf-8")
            command = [
                "bash",
                "-c",
                # The credential reaches Docker through an anonymous pipe, never a
                # file. The uv environment lives on the run volume, not the image
                # layer, so concurrent containers do not fill the root disk.
                'exec experiments/docker/run.sh --env-file <(printf "GW_TOKEN=%s\\n'
                'UV_CACHE_DIR=%s\\nUV_PROJECT_ENVIRONMENT=%s\\n" "$GATEWAY_API_KEY" '
                '"$1" "$2") --auth-command genai-gateway-credential '
                '--auth-env GW_TOKEN -- "${@:3}"',
                "run.sh",
                _container_path(UV_ROOT / "cache"),
                _container_path(UV_ROOT / f"venv-w{index:02d}"),
                "--manifest",
                f"experiments/prompts/manifests/{row['benchmark']}.jsonl",
                "--prompt-id",
                row["prompt_id"],
                "--condition",
                condition,
                "--platform",
                "codex",
                "--config",
                _container_path(root / "runtime-docker.json"),
                "--output-root",
                _container_path(shard),
                "--followup-file",
                _container_path(followup),
            ]
            with (shard / "driver.log").open("a", encoding="utf-8") as log:
                log.write(f"=== {row['prompt_id']} {condition}\n")
                log.flush()
                status = subprocess.run(
                    command, cwd=REPO, stdout=log, stderr=log, check=False
                ).returncode
            print(
                f"w{index:02d} {row['prompt_id']} {condition} exit={status}", flush=True
            )

    with ThreadPoolExecutor(args.workers) as pool:
        list(pool.map(worker, range(args.workers)))


def _pairs(root: Path, contrasts: list[str]) -> list[tuple[str, Any, Any]]:
    runs = _runs(root)
    pairs = []
    for row in _changes():
        for contrast in contrasts:
            left, right = contrast.split(":")
            a, b = (
                runs.get((row["prompt_id"], left)),
                runs.get((row["prompt_id"], right)),
            )
            if a and b and a.status == b.status == "completed":
                pairs.append((contrast, a, b))
    return pairs


def _score_path(config: JudgeConfig, left: Any, right: Any) -> Path:
    return (
        left.path
        / "scores"
        / "pairwise"
        / str(config.judge_id)
        / f"{left.prompt}-{right.condition}"
        / "scores.jsonl"
    )


def score(args: argparse.Namespace) -> None:
    config = JudgeConfig.load(args.judge_config)
    jobs = [
        (left, right)
        for _contrast, left, right in _pairs(
            args.root.resolve(), args.contrasts.split(",")
        )
        if not (
            _score_path(config, left, right).parent / "scores-manifest.json"
        ).is_file()
    ]
    print(f"{len(jobs)} pairs to score", flush=True)

    def one(pair: tuple[Any, Any]) -> None:
        left, right = pair
        try:
            score_run(
                left.path,
                config,
                compare_run_dir=right.path,
                output_path=_score_path(config, left, right),
            )
            print(
                f"scored {left.prompt} {left.condition}:{right.condition}", flush=True
            )
        except Exception as error:  # noqa: BLE001
            print(f"FAILED {left.prompt} {right.condition}: {error!r}", flush=True)

    with ThreadPoolExecutor(args.workers) as pool:
        list(pool.map(one, jobs))


def collapsed_winner(records: list[dict[str, Any]]) -> str:
    """Map both presentations to left/right/tie; any disagreement is a tie."""

    verdicts = set()
    for record in records:
        winner = record["winner"]
        if winner == "tie":
            verdicts.add("tie")
        elif record["presentation"] == "A|B":
            verdicts.add("left" if winner == "A" else "right")
        else:
            verdicts.add("right" if winner == "A" else "left")
    return verdicts.pop() if len(verdicts) == 1 else "tie"


def _sign(outcomes: list[str]) -> dict[str, Any]:
    wins, losses = outcomes.count("left"), outcomes.count("right")
    return {
        "wins": wins,
        "losses": losses,
        "ties": outcomes.count("tie"),
        "win_rate_excluding_ties": wins / (wins + losses) if wins + losses else None,
        "sign_test_p_two_sided": exact_two_sided_sign_test(wins, losses),
    }


def _events(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _turn_usage(run_path: Path, first_attempt: int) -> tuple[Counter[str], list[str]]:
    """Sum turn.completed usage and delegated roles from one turn's attempts."""

    usage: Counter[str] = Counter()
    roles: list[str] = []
    for path in sorted(run_path.glob("attempt-*.events.jsonl")):
        if int(path.name.split("-")[1].split(".")[0]) < first_attempt:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "turn.completed":
                usage.update(
                    {
                        k: v
                        for k, v in event.get("usage", {}).items()
                        if isinstance(v, int)
                    }
                )
            item = event.get("item") or {}
            if (
                event.get("type") == "item.started"
                and item.get("tool") == "spawn_agent"
                and (match := DELEGATED_PROCESS.search(str(item.get("prompt", ""))))
            ):
                roles.append(match.group(1).casefold())
    return usage, roles


def _trace_turns(run: Any) -> dict[str, Any]:
    followup = run.manifest["followup"]
    n = followup["turn1_trace_events"]
    full = _events(run.path / ".writing" / "trace" / "process.jsonl")
    turn1 = _events(run.path / "turn1.process.jsonl")
    # A session can rewrite its trace file, so turn-2 events are the events
    # absent from the turn-1 copy rather than a positional suffix.
    remaining = Counter(json.dumps(event, sort_keys=True) for event in turn1)
    turn2 = []
    for event in full:
        key = json.dumps(event, sort_keys=True)
        if remaining[key]:
            remaining[key] -= 1
        else:
            turn2.append(event)
    analysis = analyze_trace_events(turn2, fixed_order=FIXED_ORDER)
    usage, roles = _turn_usage(run.path, followup["turn1_attempts"] + 1)
    return {
        "turn1_prefix_preserved": full[:n] == turn1,
        "turn1_events_retained": not +remaining,
        "turn2_event_count": len(turn2),
        "turn2_sequence": analysis["sequence"],
        "turn2_planning": "planning" in analysis["sequence"],
        "turn2_goal_regenerated": analysis["regeneration"]["count"] > 0,
        "turn2_goal_events": analysis["goal_events"],
        "turn2_delegated_roles": roles,
        "turn2_usage": dict(usage),
    }


def report(args: argparse.Namespace) -> None:
    root = args.root.resolve()
    config = JudgeConfig.load(args.judge_config)
    changes = {row["prompt_id"]: row for row in _changes()}
    runs = _runs(root)
    conditions = sorted({condition for _prompt, condition in runs})

    completion = {
        condition: dict(
            Counter(
                run.status
                for (prompt, cond), run in runs.items()
                if cond == condition and prompt in changes
            )
        )
        for condition in conditions
    }
    usage: dict[str, Counter[str]] = defaultdict(Counter)
    for (_prompt, condition), run in runs.items():
        if run.status == "completed":
            usage[condition].update(_turn_usage(run.path, 1)[0])

    contrasts: dict[str, Any] = {}
    judge_usage: Counter[str] = Counter()
    for contrast in args.contrasts.split(","):
        per_prompt = {}
        for _name, left, right in _pairs(root, [contrast]):
            path = _score_path(config, left, right)
            if not (path.parent / "scores-manifest.json").is_file():
                continue
            per_prompt[left.prompt] = collapsed_winner(_events(path))
            manifest = json.loads((path.parent / "scores-manifest.json").read_text())
            for result in manifest["records"]:
                judge_usage.update(
                    {
                        k: v
                        for k, v in (result.get("usage") or {}).items()
                        if isinstance(v, int)
                    }
                )
        left_label, right_label = contrast.split(":")
        labels = {"left": left_label, "right": right_label, "tie": "tie"}
        by_benchmark = defaultdict(list)
        by_type = defaultdict(list)
        for prompt, outcome in per_prompt.items():
            by_benchmark[BENCHMARK_NAMES[changes[prompt]["benchmark"]]].append(outcome)
            by_type[changes[prompt]["change_type"]].append(outcome)
        contrasts[contrast] = {
            "scored_prompts": len(per_prompt),
            "overall": _sign(list(per_prompt.values())),
            "by_benchmark": {k: _sign(v) for k, v in sorted(by_benchmark.items())},
            "by_change_type": {k: _sign(v) for k, v in sorted(by_type.items())},
            "prompt_outcomes": {
                prompt: labels[outcome] for prompt, outcome in per_prompt.items()
            },
        }

    process: dict[str, Any] = {}
    for condition in ("A4", "A6"):
        details = {
            prompt: _trace_turns(run)
            for (prompt, cond), run in sorted(runs.items())
            if cond == condition and run.status == "completed"
        }
        values = list(details.values())
        total = len(values)

        def share(key: str, values: list[dict[str, Any]] = values) -> dict[str, Any]:
            count = sum(1 for value in values if value[key])
            return {
                "count": count,
                "total": len(values),
                "rate": count / len(values) if values else None,
            }

        process[condition] = {
            "completed_runs": total,
            "turn1_prefix_preserved": share("turn1_prefix_preserved"),
            "turn1_events_retained": share("turn1_events_retained"),
            "turn2_planning": share("turn2_planning"),
            "turn2_goal_regenerated": share("turn2_goal_regenerated"),
            "turn2_no_process_events": {
                "count": sum(1 for v in values if not v["turn2_event_count"]),
                "total": total,
            },
            "turn2_delegated_planning": {
                "count": sum(
                    1 for v in values if "planning" in v["turn2_delegated_roles"]
                ),
                "total": total,
            },
            "turn2_sequences": dict(
                Counter("->".join(v["turn2_sequence"]) or "(none)" for v in values)
            ),
            "per_prompt": {
                prompt: {k: v for k, v in value.items() if k != "turn2_usage"}
                for prompt, value in details.items()
            },
        }

    result = {
        "experiment": "revision-tasks",
        "design": "experiments/revision-tasks/README.md",
        "changes": "experiments/revision-tasks/changes.jsonl",
        "sample": {
            "prompts": len(changes),
            "by_benchmark": dict(
                Counter(BENCHMARK_NAMES[row["benchmark"]] for row in changes.values())
            ),
            "by_change_type": dict(
                Counter(row["change_type"] for row in changes.values())
            ),
        },
        "generator": {
            "model": "gpt-5.6-luna",
            "platform": "codex",
            "reasoning_effort": "medium",
        },
        "judge": {
            "model": config.model,
            "template": "experiments/prompts/judges/pairwise-revision-v1.md",
            "seed": config.seed,
            "presentation_seed": config.presentation_seed,
            "collapse": "both presentations agree, otherwise tie",
        },
        "completion": completion,
        "contrasts": contrasts,
        "turn2_process": process,
        "token_usage": {
            "generation_by_condition": {k: dict(v) for k, v in sorted(usage.items())},
            "judge": dict(judge_usage),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(args.output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("generate", "score", "report"):
        command = sub.add_parser(name)
        command.add_argument("--root", type=Path, required=True)
    sub.choices["generate"].add_argument("--conditions", default="A4,A6,A2")
    sub.choices["generate"].add_argument("--prompts", default="")
    sub.choices["generate"].add_argument("--shard-offset", type=int, default=0)
    for name in ("generate", "score"):
        sub.choices[name].add_argument("--workers", type=int, default=8)
    for name in ("score", "report"):
        sub.choices[name].add_argument("--judge-config", type=Path, required=True)
        sub.choices[name].add_argument("--contrasts", default="A4:A6,A4:A2")
    sub.choices["report"].add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    {"generate": generate, "score": score, "report": report}[args.command](args)


if __name__ == "__main__":
    main()
