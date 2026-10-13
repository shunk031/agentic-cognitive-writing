"""Count English assignments answered mainly in Chinese, per condition.

A text is mainly Chinese when its Han characters outnumber its Latin letters,
the rule `make_numbers.py` uses to count Chinese prompts. For the given run roots
and each benchmark, the analysis counts completed outputs of English prompts that
are mainly Chinese, per condition, and lists the prompts that drift in every
condition.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .common import select_canonical_runs

HAN = re.compile(r"[一-鿿]")
LATIN = re.compile(r"[A-Za-z]")


def mainly_chinese(text: str) -> bool:
    return len(HAN.findall(text)) > len(LATIN.findall(text))


def prompt_texts(manifest_dir: Path, benchmark: str) -> dict[str, str]:
    path = manifest_dir / f"{benchmark.lower()}.jsonl"
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {row["prompt_id"]: row["prompt_text"] for row in rows}


def drift(
    outputs: dict[str, dict[str, str]], prompts: dict[str, str]
) -> dict[str, Any]:
    """`outputs` maps condition -> prompt -> output text for completed runs."""
    english = {p for p, text in prompts.items() if not mainly_chinese(text)}
    by_condition = {}
    drifted_sets = []
    for condition, texts in sorted(outputs.items()):
        scored = [p for p in texts if p in english]
        drifted = sorted(p for p in scored if mainly_chinese(texts[p]))
        by_condition[condition] = {
            "english_completed": len(scored),
            "drifted": len(drifted),
        }
        drifted_sets.append(set(drifted))
    always = sorted(set.intersection(*drifted_sets)) if drifted_sets else []
    return {
        "by_condition": by_condition,
        "drifted_in_every_condition": always,
        # English by script majority but with Chinese instructions or text in the prompt.
        "every_condition_with_han_in_prompt": [p for p in always if HAN.search(prompts[p])],
    }


def analyze(roots: Sequence[Path], manifest_dir: Path, benchmark: str) -> dict[str, Any]:
    outputs: dict[str, dict[str, str]] = {}
    for run in select_canonical_runs(list(roots)):
        if run.benchmark != benchmark or run.status != "completed":
            continue
        text = (run.path / "output.normalized.txt").read_text(
            encoding="utf-8", errors="ignore"
        )
        outputs.setdefault(run.condition, {})[run.prompt] = text
    prompts = prompt_texts(manifest_dir, benchmark)
    return drift(
        outputs,
        {p: t for p, t in prompts.items() if any(p in o for o in outputs.values())},
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs-root", type=Path, action="append", required=True)
    parser.add_argument("--manifest-dir", type=Path, required=True)
    parser.add_argument("--benchmark", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = {
        "rule": "Han characters outnumber Latin letters",
        "benchmarks": {
            b: analyze(args.runs_root, args.manifest_dir, b) for b in args.benchmark
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
