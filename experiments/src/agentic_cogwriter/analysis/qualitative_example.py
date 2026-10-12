"""Select one illustrative prompt where the full system beat Staged and extract short excerpts.

The prompt is drawn with a fixed seed from the generation-run-1 prompts whose
order-consistent pairwise outcome favors A4 over A2 and whose two outputs are in
English. The output holds the assignment opening, A4's logged process path, the
opening of each system's document, and the judge's stated reason for the
presentation in which A4 is response A. It contains no file paths.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from . import length_control as lc

SEED = 20260908
CONTRAST = ("A4", "A2")
JUDGE_ID = "gpt-5.6-sol-pairwise-v1"


def excerpt(text: str, words: int) -> str:
    """Keep the first `words` words, preserving line breaks between non-empty lines."""
    lines, left = [], words
    for line in text.splitlines():
        tokens = line.split()
        if not tokens:
            continue
        if len(tokens) >= left:
            lines.append(" ".join(tokens[:left]) + " ...")
            break
        lines.append(" ".join(tokens))
        left -= len(tokens)
    return "\n".join(lines)


def mostly_ascii(text: str) -> bool:
    return bool(text) and sum(ch.isascii() for ch in text) / len(text) > 0.97


def candidates(root: Path) -> list[dict[str, Any]]:
    index = lc._run_index([root])
    found: dict[tuple[str, str], dict[str, Any]] = {}
    for manifest_path in sorted(root.resolve().rglob("scores-manifest.json")):
        manifest = lc._json(manifest_path)
        if not manifest or manifest.get("task") != "pairwise":
            continue
        if (manifest.get("judge") or {}).get("judge_id") != JUDGE_ID:
            continue
        runs = [
            index.get(s.get("run_manifest_sha256"))
            for s in manifest.get("source_runs", [])
        ]
        if (
            len(runs) != 2
            or None in runs
            or {r.condition for r in runs} != set(CONTRAST)
        ):
            continue
        records = lc._records(manifest_path.parent / "scores.jsonl")
        if not records:
            continue
        mapping = lc._mapping(manifest)
        outcomes = tuple(
            lc._outcome_condition(records[p], runs, mapping[p]) for p in ("A|B", "B|A")
        )
        if lc.collapse_verdict(outcomes, *CONTRAST) != "left":
            continue
        by_condition = {run.condition: run for run in runs}
        texts = {
            condition: (run.path / "output.normalized.txt").read_text(
                encoding="utf-8", errors="ignore"
            )
            for condition, run in by_condition.items()
        }
        if not all(mostly_ascii(text) for text in texts.values()):
            continue
        # The presentation whose response A is A4, so the reason's "A" names our system.
        presentation = next(
            p for p in ("A|B", "B|A") if runs[mapping[p][0]].condition == CONTRAST[0]
        )
        full = by_condition["A4"]
        trace = full.path / ".writing" / "trace" / "process.jsonl"
        events = [
            json.loads(line)
            for line in trace.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        path = [
            e["to_process"]
            for e in events
            if e.get("event_type") == "process_switch" and e.get("to_process")
        ]
        assignment = full.path / "workspace" / ".writing" / "assignment.md"
        if not assignment.exists():
            assignment = full.path / ".writing" / "assignment.md"
        found[(full.benchmark, full.prompt)] = {
            "benchmark": full.benchmark,
            "prompt": full.prompt,
            "assignment_opening": excerpt(
                assignment.read_text(encoding="utf-8", errors="ignore").replace(
                    "# Assignment", ""
                ),
                60,
            ),
            "full_process_path": path,
            "full_opening": excerpt(texts["A4"], 70),
            "staged_opening": excerpt(texts["A2"], 70),
            "judge_reason": records[presentation]["reason"],
        }
    return [found[key] for key in sorted(found)]


def select(pool: list[dict[str, Any]], seed: int = SEED) -> dict[str, Any]:
    return random.Random(seed).choice(pool)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    pool = candidates(args.runs_root)
    report = {
        "selection": f"random.Random({SEED}).choice over generation-run-1 prompts where A4 beat A2 in both presentation orders and both outputs are English",
        "eligible_prompts": len(pool),
        "example": select(pool),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
