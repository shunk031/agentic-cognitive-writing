"""Compute the preregistered Pilot 1 statistics from checker outputs and runs.

The preregistration in ``experiments/preregistration/pilot1.md`` fixes every
rule below. Each checker output of ``requirement_change check`` names its run
directory; the run manifest gives the arm, the fidelity gate, and turn 2's
all-thread tokens, and the mechanism report's ``analyze_run`` gives turn 2's
delegations. Only gate-passing runs count.

Measures, all of turn 2: U, the share of untargeted sections changed
(``locality``); S, their mean word-level similarity (``mean_similarity``); B,
the share of turn-1-passing unchanged requirements broken (``break_rate``); C,
whether every changed requirement passes (``incorporated``); and K, turn 2's
delegations and all-thread total tokens. A run without a value for a measure
is skipped for it.

Comparisons are paired by item: each arm's value for an item is the mean over
its runs, and an item enters a comparison when both arms have a value. The
test is the exact sign-flip permutation test of the mean item difference,
enumerating all 2^n sign assignments of the differences minus the null value.

Gates. G1 passes when, against A6, U is lower for A4 by at least
``U_MARGIN`` or S is higher for A4 by at least ``S_MARGIN``, with a two-sided
p below ``G1_ALPHA`` at a null of zero, over at least ``G1_MIN_ITEMS`` items.
G2 passes when, against each of A6 and A6s, a one-sided test rejects that C is
lower for A4 by ``C_MARGIN`` or more and that B is higher for A4 by ``B_MARGIN``
or more, each at p below ``G2_ALPHA`` over at least ``G2_MIN_ITEMS`` items. G3
classifies A4 against A6s with the G1 rule applied in both directions:
``monitor_better``, ``rule_better``, or ``no_difference``. GO is G1 and G2;
the pilot is INVALID when an arm has fewer than ``MIN_SCORABLE_RUNS`` counted
runs, and a run without a checker output does not count.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any

from .mechanism import analyze_run

ARMS = ("A4", "A6", "A6s")
MEASURES = ("U", "S", "B", "C", "K_delegations", "K_tokens")
U_MARGIN, S_MARGIN, C_MARGIN, B_MARGIN = 0.15, 0.05, 0.15, 0.05
G1_ALPHA, G2_ALPHA = 0.025, 0.025
G1_MIN_ITEMS, G2_MIN_ITEMS = 10, 12
MIN_SCORABLE_RUNS = 26
# Stage 0's per-run U of unedited A4 on the 12 multi-section items.
STAGE0_A4_U = (0.0,) * 9 + (1 / 3, 0.5, 0.5)
_EPS = 1e-9


def sign_flip_p(
    diffs: list[float], null: float = 0.0, alternative: str = "two-sided"
) -> float:
    """Return the exact sign-flip p-value of the mean of ``diffs`` against ``null``.

    ``alternative`` is ``two-sided``, ``greater`` (the mean exceeds ``null``),
    or ``less``.
    """

    centered = [d - null for d in diffs]
    sums = [0.0]
    for d in centered:
        sums = [s + d for s in sums] + [s - d for s in sums]
    observed = sum(centered)
    if alternative == "greater":
        hits = sum(s >= observed - _EPS for s in sums)
    elif alternative == "less":
        hits = sum(s <= observed + _EPS for s in sums)
    else:
        hits = sum(abs(s) >= abs(observed) - _EPS for s in sums)
    return hits / len(sums)


def load_runs(checks: Path) -> list[dict[str, Any]]:
    """Return one record per checker output under ``checks``."""

    runs = []
    for path in sorted(checks.rglob("*.json")):
        check = json.loads(path.read_text(encoding="utf-8"))
        run_dir = Path(check["run_dir"])
        manifest = json.loads(
            (run_dir / "run-manifest.json").read_text(encoding="utf-8")
        )
        followup = manifest.get("followup") or {}
        gate = manifest.get("fidelity_gate") or {}
        turn2 = analyze_run(run_dir, followup)["turn2_processes"]
        tokens = (followup.get("rollout_token_usage") or {}).get("turn2") or {}
        runs.append(
            {
                "arm": manifest["inputs"]["condition_id"],
                "item": check["item"],
                "run_dir": str(run_dir),
                "scorable": gate.get("status") == "scorable",
                "reasons": gate.get("reasons", []),
                "U": check["locality"],
                "S": check["mean_similarity"],
                "B": check["break_rate"],
                "C": float(check["incorporated"]),
                "K_delegations": None if turn2 is None else len(turn2),
                "K_tokens": tokens.get("total_tokens"),
            }
        )
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
    c = paired(runs, "A4", other, "C")
    b = paired(runs, "A4", other, "B")
    return (
        len(c) >= G2_MIN_ITEMS
        and len(b) >= G2_MIN_ITEMS
        and sign_flip_p(c, -C_MARGIN, "greater") < G2_ALPHA
        and sign_flip_p(b, B_MARGIN, "less") < G2_ALPHA
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
            arm: {
                "total": sum(r["arm"] == arm for r in runs),
                "scorable": counted[arm],
            }
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
        if min(counted.values()) < MIN_SCORABLE_RUNS
        else "GO"
        if g1 and g2
        else "NO-GO",
    }


def power(a6_rewrite: float, sims: int, seed: int, items: int = 12) -> float:
    """Return the simulated rate at which G1 passes on U alone.

    Each A4 run draws U from ``STAGE0_A4_U``; each A6 run rewrites every
    untargeted section (U = 1) with probability ``a6_rewrite`` and otherwise
    none (U = 0), as in the follow-up smoke. Runs and items are independent.
    """

    rng = random.Random(seed)
    passed = 0
    for _ in range(sims):
        diffs = [
            fmean(float(rng.random() < a6_rewrite) for _ in range(2))
            - fmean(rng.choice(STAGE0_A4_U) for _ in range(2))
            for _ in range(items)
        ]
        passed += fmean(diffs) >= U_MARGIN and sign_flip_p(diffs) < G1_ALPHA
    return passed / sims


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    analyzer = commands.add_parser("analyze")
    analyzer.add_argument("--checks", type=Path, required=True)
    simulator = commands.add_parser("power")
    simulator.add_argument("--a6-rewrite", type=float, nargs="+", required=True)
    simulator.add_argument("--sims", type=int, default=2000)
    simulator.add_argument("--seed", type=int, default=20261029)
    args = parser.parse_args(argv)
    if args.command == "analyze":
        print(json.dumps(analyze(load_runs(args.checks)), indent=2))
    else:
        for rate in args.a6_rewrite:
            print(f"{rate}\t{power(rate, args.sims, args.seed):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
