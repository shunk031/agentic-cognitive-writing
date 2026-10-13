"""Process-fidelity and mechanism-exercise report for cw-arm runs.

Usage: ``python -m agentic_cogwriter.analysis.fidelity <run-root>``

The report reads only harness records: attempt events, collected rollouts,
the ``cw`` history and snapshots, ``review.json`` files, run manifests, and
the scored artifact's script. It never reads output text for quality.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from ..runner import cw_run

LETTER = {"planning": "P", "translating": "T", "reviewing": "R"}
GOAL_LINE = re.compile(r"^\s*- \[(G[\d.]+)\] .+$")
GOAL_SOURCE = re.compile(
    r"^\s*- \[(G[\d.]+)\] .+? \| src: \"(.+?)\"(?: \| status: .*)?$"
)


def _norm(text: str) -> str:
    return " ".join(text.replace('\\"', '"').replace("\\'", "'").split())


def request_sources(run_dir: Path, entries: list[dict]) -> dict[int, tuple[int, int]]:
    """Per follow-up turn: requirements changed in it, and how many quote its request.

    A requirement counts as changed in turn N when a goal event of a step in
    turn N names it; it quotes the request when its final ``src`` quote occurs
    in ``history/turn-NN-request.md``.
    """

    writing = run_dir / "workspace/.writing"
    goals = writing / "goals.md"
    quotes = {
        m[1]: m[2]
        for line in (
            goals.read_text(encoding="utf-8").splitlines() if goals.is_file() else []
        )
        if (m := GOAL_SOURCE.match(line))
    }
    turn_of = {
        e["step"]: e["turn"]
        for e in entries
        if e.get("cmd") == "step" and "refused" not in e
    }
    out: dict[int, tuple[int, int]] = {}
    for request in sorted((writing / "history").glob("turn-*-request.md")):
        turn = int(request.name.split("-")[1])
        text = _norm(request.read_text(encoding="utf-8"))
        changed = {
            e["goal_id"]
            for e in entries
            if e.get("cmd") == "goal" and turn_of.get(e.get("step")) == turn
        }
        quoting = sum(1 for g in changed if g in quotes and _norm(quotes[g]) in text)
        out[turn] = (len(changed), quoting)
    return out


def _manifest(run_dir: Path) -> dict:
    return json.loads((run_dir / "run-manifest.json").read_text(encoding="utf-8"))


def paths(entries: list[dict]) -> dict[int, str]:
    """Process letters per turn; a failed step shows as a lowercase letter."""

    closes = {e["step"]: e for e in entries if e.get("cmd") == "close"}
    out: dict[int, str] = {}
    for step in (e for e in entries if e.get("cmd") == "step" and "refused" not in e):
        letter = LETTER[step["process"]]
        if not closes.get(step["step"], {}).get("ok", False):
            letter = letter.lower()
        out[step["turn"]] = out.get(step["turn"], "") + letter
    return out


def returns(path: str) -> Counter[str]:
    ok = [c for c in path if c.isupper()]
    return Counter(a + b for a, b in zip(ok, ok[1:], strict=False) if a == "R")


def run_row(run_dir: Path) -> dict[str, Any]:
    manifest = _manifest(run_dir)
    entries = cw_run.history(run_dir, refused=True)
    gate = cw_run.gates(run_dir, manifest.get("runner_files"))
    spawn = gate["spawn"]
    tokens = cw_run.token_report(run_dir)
    turn_paths = paths(entries)
    live = [e for e in entries if "refused" not in e]
    reviews = [e for e in live if e.get("cmd") == "review"]
    closes = [e for e in live if e.get("cmd") == "close"]
    goal_events = Counter(
        e["event_type"] + (f":{e['origin']}" if "origin" in e else "")
        for e in live
        if e.get("cmd") == "goal"
    )
    decisions = Counter(e["outcome"] for e in live if e.get("cmd") == "decide")
    artifact = run_dir / "output.normalized.txt"
    language = (manifest.get("language") or {}).get("value")
    script = (
        cw_run.majority_script(artifact.read_text()) if artifact.is_file() else None
    )
    goals_path = run_dir / "workspace/.writing/goals.md"
    goal_lines = [
        line.strip()
        for line in (
            goals_path.read_text().splitlines() if goals_path.is_file() else []
        )
        if GOAL_LINE.match(line)
    ]
    # Returns are counted within each turn, never across a turn boundary.
    ret = sum((returns(path) for path in turn_paths.values()), Counter())
    return {
        "run": run_dir.name,
        "condition": manifest["inputs"]["condition_id"],
        "prompt": manifest["inputs"]["prompt_id"],
        "gates": gate["results"],
        "spawn": {
            "spawns": spawn["spawns"],
            "forked": len(spawn["forked"]),
            "model_args": len(spawn["overrides"]),
            "failed": spawn["failed_spawns"],
            "unclosed": len(spawn["unclosed"]),
        },
        "inject": f"{len(spawn['injected'])}/{len(spawn['children'])}",
        "nonce": gate["results"]["nonce"],
        "nonce_violations": gate["reported"]["nonce_violations"],
        "allowance": sum(c.get("reason") == "allowance" for c in closes),
        "restores": sum(bool(c.get("restored")) for c in closes),
        "failed_steps": sum(not c["ok"] for c in closes),
        "refusals": sum("refused" in e for e in entries),
        "stop": cw_run.stop_reasons(run_dir),
        "path": turn_paths,
        "returns": {"R>T": ret["RT"], "R>P": ret["RP"]},
        "reviews": len(reviews),
        "unmet": [(r["unmet"], r["findings"]) for r in reviews],
        "goals": dict(goal_events),
        "proposals": dict(decisions),
        "lang": f"{script}/{language}",
        "tokens": {
            "budget": tokens["budget_statistic"],
            "parent_turns": tokens["parent_output_per_turn"],
            "child_inclusive": tokens["child_inclusive"],
        },
        "failure": (manifest.get("failure") or {}).get("kind"),
        "samples": goal_lines[:3],
        "request_src": request_sources(run_dir, entries),
    }


def _cell(row: dict) -> list[str]:
    failed = [name for name, ok in row["gates"].items() if not ok]
    first = row["unmet"][0] if row["unmet"] else None
    goals = ", ".join(f"{k} {v}" for k, v in sorted(row["goals"].items())) or "-"
    return [
        row["condition"],
        row["prompt"],
        "pass" if not failed else "FAIL " + ",".join(failed),
        "{spawns}/{forked}/{model_args}/{failed}/{unclosed}".format(**row["spawn"]),
        row["inject"],
        "yes" if row["nonce"] else f"no ({row['nonce_violations']})",
        f"{row['allowance']}/{row['restores']}",
        " ".join(f"t{t}:{r}" for t, r in sorted(row["stop"].items())) or "-",
        " ".join(f"t{t}:{p}" for t, p in sorted(row["path"].items())) or "-",
        f"{row['returns']['R>T']}/{row['returns']['R>P']}",
        (f"first {first[0]}u/{first[1]}f; " if first else "")
        + f"all {sum(u for u, _ in row['unmet'])}u/{sum(f for _, f in row['unmet'])}f",
        goals + f"; acc {row['proposals'].get('accept', 0)}"
        f"/rej {row['proposals'].get('reject', 0)}",
        row["lang"],
        "{} / {}".format(
            row["tokens"]["budget"], row["tokens"]["child_inclusive"]["output_tokens"]
        ),
        " ".join(
            f"t{turn}:{quoting}/{changed}"
            for turn, (changed, quoting) in sorted(row["request_src"].items())
        )
        or "-",
        row["failure"] or "-",
    ]


HEADER = [
    "cond",
    "prompt",
    "gates",
    "spawn s/fork/model/fail/unclosed",
    "inject",
    "nonce",
    "allow/restore",
    "stop",
    "path",
    "R>T/R>P",
    "unmet",
    "goals; proposals",
    "lang out/manifest",
    "tokens parent/child-incl",
    "request src quoting/changed",
    "failure",
]


def _table(rows: list[list[str]], header: list[str]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def summary(rows: list[dict]) -> list[list[str]]:
    out = []
    for condition in sorted({r["condition"] for r in rows}):
        group = [r for r in rows if r["condition"] == condition]
        ok = sum(all(r["gates"].values()) and not r["failure"] for r in group)
        multi = sum(r["reviews"] > 1 for r in group)
        first_open = sum(bool(r["unmet"]) and sum(r["unmet"][0]) > 0 for r in group)
        rt = sum(r["returns"]["R>T"] for r in group)
        rp = sum(r["returns"]["R>P"] for r in group)
        developed = sum(
            v for r in group for k, v in r["goals"].items() if k == "goal_developed"
        )
        regenerated = sum(
            v for r in group for k, v in r["goals"].items() if "regenerated" in k
        )
        out.append(
            [
                condition,
                str(len(group)),
                str(ok),
                str(multi),
                str(first_open),
                f"{rt}/{rp}",
                f"{developed}/{regenerated}",
                str(sum(r["failed_steps"] for r in group)),
            ]
        )
    return out


def find_runs(root: Path) -> list[Path]:
    return sorted(
        p.parent
        for p in root.rglob("run-manifest.json")
        if (p.parent / "workspace/.agents/cw").is_dir()
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", type=Path)
    parser.add_argument("--json", action="store_true", help="print rows as JSON")
    args = parser.parse_args(argv)
    rows = [run_row(run_dir) for run_dir in find_runs(args.root)]
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    print(_table([_cell(r) for r in rows], HEADER))
    print()
    print(
        _table(
            summary(rows),
            [
                "cond",
                "runs",
                "valid",
                ">1 review",
                "first review open",
                "R>T/R>P",
                "developed/regenerated",
                "failed steps",
            ],
        )
    )
    print()
    for row in rows:
        print(f"{row['condition']} {row['prompt']} samples:")
        for line in row["samples"]:
            print(f"  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
