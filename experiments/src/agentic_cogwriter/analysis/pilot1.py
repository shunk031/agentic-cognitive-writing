"""Compute the preregistered Pilot 1 statistics from the run map and its runs.

The preregistration in ``experiments/preregistration/pilot1.md`` fixes every
rule below.

Run map. A JSON Lines file kept outside every output root lists the 84
expected runs, one line each with ``arm``, ``item``, ``replicate``,
``run_dir``, ``check`` (the path of the run's ``requirement_change check``
output), and, when the check refused or the run crashed, ``check_error``.
``schedule`` prints the seeded run order and neutral output-root labels the
map starts from. A map that misses or repeats an expected run, or names one
run directory twice, is refused.

Exclusions. A run counts only when all of these hold; otherwise it is
excluded with every reason that applies:

- its directory has a run manifest with a follow-up record, and a checker
  output for the same run and item exists;
- its fidelity gate, which covers turn 1 and the whole run, is ``scorable``;
- ``followup.txt`` has the manifest's message hash, opens with the item's
  change block, and continues with the arm's own skill invocation;
- the workspace ``task.md`` has the manifest's task hash and is the staged
  task followed by the change block;
- the staged ``Monitor`` and role skills have the pinned ``SKILL_HASHES``;
- the resume command keeps the workspace-write sandbox;
- no component of the run directory names a prompt or a change class.

Every manifest present must record one generator model, reasoning effort,
and Codex version, none of them missing, and the given run commit as both
plugin commits; otherwise the analysis stops.

Measures, all of turn 2: U, the share of untargeted sections changed
(``locality``); S, their mean word-level similarity (``mean_similarity``); B,
the share of turn-1-passing unchanged requirements broken (``break_rate``); C,
whether every changed requirement passes (``incorporated``); and K, turn 2's
delegations, from the mechanism report's ``analyze_run``, and all-thread total
tokens. A run without a value for a measure is skipped for it.

Comparisons are paired by item: each arm's value for an item is the mean over
its counted runs, and an item enters a comparison when both arms have a value.
The test is the exact two-sided sign-flip permutation test of the mean item
difference, enumerating all 2^n sign assignments.

Gates. G1 passes when, against A6, U is lower for A4 by at least ``U_MARGIN``
or S is higher for A4 by at least ``S_MARGIN``, with p below ``G1_ALPHA``, over
at least ``G1_MIN_ITEMS`` items. G2 is a point-estimate guard: against each of
A6 and A6s, over at least ``G2_MIN_ITEMS`` items, A4's mean C is at least the
other's minus ``C_MARGIN`` and A4's mean B at most the other's plus
``B_MARGIN``; its sign-flip tests are reported only. G3 classifies A4 against
A6s with the G1 rule applied in both directions: ``monitor_better``,
``rule_better``, or ``no_difference``. GO is G1 and G2; the pilot is INVALID
when an arm has fewer than ``MIN_COUNTED_RUNS`` counted runs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from collections import defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any

from ..requirement_change import CLASSES, PROMPT_IDS
from ..runner.runner import followup_message
from .mechanism import analyze_run

ARMS = ("A4", "A6", "A6s")
# The Stage 0 items: every term and remove item the generator makes.
ITEMS = (
    "dolomites-1453.term",
    "dolomites-1453.remove",
    "dolomites-53.term",
    "dolomites-53.remove",
    "dolomites-673.term",
    "dolomites-673.remove",
    "dolomites-1705.term",
    "dolomites-1705.remove",
    "dolomites-247.term",
    "dolomites-247.remove",
    "dolomites-626.term",
    "dolomites-881.term",
    "dolomites-881.remove",
    "dolomites-296.term",
)
REPLICATES = 2
SEED = 20261029
MEASURES = ("U", "S", "B", "C", "K_delegations", "K_tokens")
U_MARGIN, S_MARGIN, C_MARGIN, B_MARGIN = 0.15, 0.05, 0.15, 0.05
G1_ALPHA = 0.025
G1_MIN_ITEMS, G2_MIN_ITEMS = 10, 12
MIN_COUNTED_RUNS = 26
MONITOR_SKILLS = {
    "A4": "agentic-cog-writer",
    "A6": "cognitive-writing-fixed-order",
    "A6s": "cognitive-writing-fixed-order-skip",
}
SKILL_HASHES = {
    "agentic-cog-writer": (
        "f3fd53e017c993b56d660da7b577b6b3f4d43da0078caf24cbd1397dc290f543"
    ),
    "cognitive-writing-fixed-order": (
        "74f90030fcd91d8f4e0816b01fc0eea603ca15a4902a6ca92a58bd17f32df26f"
    ),
    "cognitive-writing-fixed-order-skip": (
        "1298588eca30dbd7652abdda292c165f8268ed947e39be4647d1bf1556b7e4f7"
    ),
    "planning": "806703406b38adf238e18b3df5fe085537f8d66735526a673bc3ebdafeffa3fc",
    "translating": "e8b22453cda82552c15cf790dbe554461f7b21bae485742ace8ed20883276a55",
    "reviewing": "1eaf68966c667daee6ac5b73a7979b66f245972d21ac8fea409304532b64a9dd",
}
# Stage 0's per-run U of unedited A4 on the 12 multi-section items, and its
# per-run share of runs that missed the change.
STAGE0_A4_U = (0.0,) * 9 + (1 / 3, 0.5, 0.5)
STAGE0_C_MISS = 1 / 14
SINGLE_SECTION_ITEMS = ("dolomites-626.term", "dolomites-296.term")
_EPS = 1e-9


def sign_flip_p(diffs: list[float]) -> float:
    """Return the exact two-sided sign-flip p-value of the mean of ``diffs``."""

    sums = [0.0]
    for d in diffs:
        sums = [s + d for s in sums] + [s - d for s in sums]
    observed = abs(sum(diffs))
    return sum(abs(s) >= observed - _EPS for s in sums) / len(sums)


def schedule(seed: int = SEED) -> list[dict[str, Any]]:
    """Return the 84 runs in their seeded order, each with a neutral label."""

    runs = [
        {"arm": arm, "item": item, "replicate": replicate}
        for item in ITEMS
        for arm in ARMS
        for replicate in range(REPLICATES)
    ]
    random.Random(seed).shuffle(runs)
    return [{"label": f"p1-{n:02d}", **run} for n, run in enumerate(runs, 1)]


def leaks(run_dir: Path) -> bool:
    """Return whether a component of ``run_dir`` names a prompt or a class."""

    for part in run_dir.parts:
        lowered = part.lower()
        if any(prompt in lowered for prompt in PROMPT_IDS):
            return True
        if set(re.split(r"[^a-z0-9]+", lowered)) & set(CLASSES):
            return True
    return False


def _sha(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _input_reasons(manifest: dict, run_dir: Path, arm: str, message: str) -> list:
    """Return why a run's turn-2 input or staged skills differ from the plan."""

    followup = manifest["followup"]
    change = followup_message(message)
    reasons = []
    sent_path = run_dir / "followup.txt"
    sent = sent_path.read_bytes() if sent_path.is_file() else b""
    clause = sent.decode("utf-8").removeprefix(f"{change}\n")
    if (
        _sha(sent) != followup.get("message_hash")
        or clause == sent.decode("utf-8")
        or f"skills/{MONITOR_SKILLS[arm]}/SKILL.md" not in clause
    ):
        reasons.append("turn-2 message is not the item's change and the arm's clause")
    staged = manifest.get("staged_files") or {}
    task_path = run_dir / "workspace" / ".writing" / "task.md"
    task = task_path.read_bytes() if task_path.is_file() else b""
    suffix = f"\n{change}".encode()
    if not (
        _sha(task) == followup.get("task_hash")
        and task.endswith(suffix)
        and _sha(task[: -len(suffix)]) == staged.get(".writing/task.md")
    ):
        reasons.append("task.md is not the staged task and the item's change")
    for skill in (MONITOR_SKILLS[arm], "planning", "translating", "reviewing"):
        if staged.get(f"plugin/skills/{skill}/SKILL.md") != (
            f"sha256:{SKILL_HASHES[skill]}"
        ):
            reasons.append(f"staged {skill} skill differs from the pinned hash")
    flags = (manifest.get("models_and_execution") or {}).get("command_flags") or {}
    resume = flags.get("continuation_args") or []
    # Either form the Codex adapter accepts.
    if not {"workspace-write", 'sandbox_mode="workspace-write"'} & set(resume):
        reasons.append("resume does not keep the workspace-write sandbox")
    return reasons


def _configuration(manifest: dict) -> tuple:
    execution = manifest.get("models_and_execution") or {}
    return (
        execution.get("generator_model_id"),
        (execution.get("decoding") or {}).get("codex_reasoning_effort"),
        execution.get("cli_version"),
        execution.get("main_plugin_commit"),
        execution.get("experiments_plugin_commit"),
    )


def load_runs(run_map: Path, items_path: Path, commit: str) -> list[dict[str, Any]]:
    """Return one record per expected run of ``run_map``, counted or excluded."""

    entries = [json.loads(line) for line in run_map.read_text().splitlines() if line]
    keys = sorted((e["arm"], e["item"], e["replicate"]) for e in entries)
    expected = sorted((r["arm"], r["item"], r["replicate"]) for r in schedule())
    if keys != expected:
        raise ValueError("The run map must list each of the 84 expected runs once")
    dirs = [str(Path(e["run_dir"]).resolve()) for e in entries]
    if len(set(dirs)) != len(dirs):
        raise ValueError("The run map names one run directory more than once")
    messages = {
        item["id"]: item["message"]
        for item in json.loads(items_path.read_text(encoding="utf-8"))
    }
    runs, configurations = [], set()
    for entry, resolved in zip(entries, dirs, strict=True):
        run_dir, arm, item = Path(resolved), entry["arm"], entry["item"]
        manifest = _json(run_dir / "run-manifest.json")
        check = _json(Path(entry["check"])) if entry.get("check") else None
        reasons = []
        if leaks(Path(entry["run_dir"])):
            reasons.append("run directory names a prompt or a change class")
        if not isinstance(manifest, dict):
            reasons.append(entry.get("check_error") or "no run manifest")
        elif not manifest.get("followup"):
            reasons.append("no follow-up turn")
        if check is None:
            reasons.append(entry.get("check_error") or "no checker output")
        elif check.get("item") != item or (
            str(Path(check.get("run_dir", "")).resolve()) != resolved
        ):
            reasons.append("checker output is for another run or item")
        if isinstance(manifest, dict):
            configurations.add(_configuration(manifest))
            gate = manifest.get("fidelity_gate") or {}
            if gate.get("status") != "scorable":
                reasons += [f"gate: {r}" for r in gate.get("reasons") or ["rejected"]]
            if manifest.get("followup"):
                reasons += _input_reasons(manifest, run_dir, arm, messages[item])
        record = {
            "arm": arm,
            "item": item,
            "run_dir": resolved,
            "scorable": not reasons,
            "reasons": list(dict.fromkeys(reasons)),
            **dict.fromkeys(MEASURES),
        }
        if not reasons:
            followup = manifest.get("followup")
            turn2 = analyze_run(run_dir, followup)["turn2_processes"]
            tokens = (followup.get("rollout_token_usage") or {}).get("turn2") or {}
            record |= {
                "U": check["locality"],
                "S": check["mean_similarity"],
                "B": check["break_rate"],
                "C": float(check["incorporated"]),
                "K_delegations": len(turn2),
                "K_tokens": tokens.get("total_tokens"),
            }
        runs.append(record)
    if len(configurations) > 1:
        raise ValueError(f"Runs differ in configuration: {sorted(configurations)}")
    if any(None in config[:3] for config in configurations):
        raise ValueError("A manifest lacks the model, effort, or Codex version")
    if any(config[3:] != (commit, commit) for config in configurations):
        raise ValueError(f"Runs did not use the run commit {commit}")
    return runs


def item_means(runs: list[dict[str, Any]], arm: str, measure: str) -> dict:
    values: dict[str, list[float]] = defaultdict(list)
    for run in runs:
        if run["arm"] == arm and run["scorable"] and run[measure] is not None:
            values[run["item"]].append(run[measure])
    return {item: fmean(v) for item, v in values.items()}


def paired(runs: list[dict[str, Any]], a: str, b: str, measure: str) -> list[float]:
    """Return the item differences ``a`` minus ``b``, in item order."""

    left, right = item_means(runs, a, measure), item_means(runs, b, measure)
    return [left[item] - right[item] for item in sorted(left.keys() & right.keys())]


def _summary(diffs: list[float]) -> dict[str, Any]:
    return {
        "items": len(diffs),
        "mean": fmean(diffs) if diffs else None,
        "p_two_sided": sign_flip_p(diffs) if diffs else None,
    }


def _better(runs: list[dict[str, Any]], a: str, b: str) -> bool:
    """Return whether ``a`` preserves more than ``b`` by the G1 rule."""

    for diffs, margin in (
        (paired(runs, b, a, "U"), U_MARGIN),
        (paired(runs, a, b, "S"), S_MARGIN),
    ):
        if (
            len(diffs) >= G1_MIN_ITEMS
            and fmean(diffs) >= margin
            and sign_flip_p(diffs) < G1_ALPHA
        ):
            return True
    return False


def _not_worse(runs: list[dict[str, Any]], other: str) -> bool:
    """Return whether A4 passes the G2 point-estimate guard against ``other``."""

    c = paired(runs, "A4", other, "C")
    b = paired(runs, "A4", other, "B")
    return (
        len(c) >= G2_MIN_ITEMS
        and len(b) >= G2_MIN_ITEMS
        and fmean(c) >= -C_MARGIN
        and fmean(b) <= B_MARGIN
    )


def analyze(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the preregistered comparisons, gates, and decision."""

    counted = {
        arm: sum(r["arm"] == arm and r["scorable"] for r in runs) for arm in ARMS
    }
    g1 = _better(runs, "A4", "A6")
    g2 = _not_worse(runs, "A6") and _not_worse(runs, "A6s")
    g3 = (
        "monitor_better"
        if _better(runs, "A4", "A6s")
        else "rule_better"
        if _better(runs, "A6s", "A4")
        else "no_difference"
    )
    return {
        "runs": {
            arm: {"total": sum(r["arm"] == arm for r in runs), "counted": counted[arm]}
            for arm in ARMS
        },
        "excluded": [
            {"run_dir": r["run_dir"], "reasons": r["reasons"]}
            for r in runs
            if not r["scorable"]
        ],
        "means": {
            arm: {
                measure: fmean(m.values())
                if (m := item_means(runs, arm, measure))
                else None
                for measure in MEASURES
            }
            for arm in ARMS
        },
        "contrasts": {
            f"A4-{other}": {
                measure: _summary(paired(runs, "A4", other, measure))
                for measure in MEASURES
            }
            for other in ("A6", "A6s")
        },
        "G1": g1,
        "G2": g2,
        "G3": g3,
        "decision": "INVALID"
        if min(counted.values()) < MIN_COUNTED_RUNS
        else "GO"
        if g1 and g2
        else "NO-GO",
    }


def simulate(
    a6_u: float | None, break_rate: float, sims: int, seed: int = SEED
) -> dict[str, float]:
    """Return the simulated rates at which G1, G2, and GO pass.

    A4 and A6s runs draw U from ``STAGE0_A4_U``; an A6 run does too when
    ``a6_u`` is None, and otherwise rewrites every untargeted section (U = 1)
    with probability ``a6_u`` and none (U = 0) otherwise. Every arm's run misses
    the change with probability ``STAGE0_C_MISS`` and breaks each of three
    unchanged requirements with probability ``break_rate``. S is absent, so G1
    passes on U only. Runs and items are independent.
    """

    rng = random.Random(seed)
    passed = {"G1": 0, "G2": 0, "GO": 0}
    for _ in range(sims):
        runs = []
        for item in ITEMS:
            for arm in ARMS:
                for _ in range(REPLICATES):
                    if item in SINGLE_SECTION_ITEMS:
                        u = None
                    elif arm == "A6" and a6_u is not None:
                        u = float(rng.random() < a6_u)
                    else:
                        u = rng.choice(STAGE0_A4_U)
                    runs.append(
                        {
                            "arm": arm,
                            "item": item,
                            "scorable": True,
                            "U": u,
                            "S": None,
                            "C": float(rng.random() >= STAGE0_C_MISS),
                            "B": sum(rng.random() < break_rate for _ in range(3)) / 3,
                        }
                    )
        g1 = _better(runs, "A4", "A6")
        g2 = _not_worse(runs, "A6") and _not_worse(runs, "A6s")
        passed["G1"] += g1
        passed["G2"] += g2
        passed["GO"] += g1 and g2
    return {gate: count / sims for gate, count in passed.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    analyzer = commands.add_parser("analyze")
    analyzer.add_argument("--run-map", type=Path, required=True)
    analyzer.add_argument("--items", type=Path, required=True)
    analyzer.add_argument("--commit", required=True, help="the pinned run commit")
    commands.add_parser("schedule")
    simulator = commands.add_parser("power")
    simulator.add_argument(
        "--a6-u", nargs="+", required=True, help="A6 mean U values, or 'equal'"
    )
    simulator.add_argument("--break-rate", type=float, nargs="+", default=[0.0])
    simulator.add_argument("--sims", type=int, default=2000)
    args = parser.parse_args(argv)
    if args.command == "analyze":
        runs = load_runs(args.run_map, args.items, args.commit)
        print(json.dumps(analyze(runs), indent=2))
    elif args.command == "schedule":
        print("".join(json.dumps(run) + "\n" for run in schedule()), end="")
    else:
        for value in args.a6_u:
            for rate in args.break_rate:
                a6_u = None if value == "equal" else float(value)
                result = simulate(a6_u, rate, args.sims)
                print(value, rate, *(f"{result[g]:.3f}" for g in ("G1", "G2", "GO")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
