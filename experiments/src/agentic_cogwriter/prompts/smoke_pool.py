"""Define the redesign's smoke pool and check that it avoids every scored set.

Usage: ``python -m agentic_cogwriter.prompts.smoke_pool``, before every smoke
iteration. The pool is the prompts ranked directly below the A10 calibration
set on the prompt-set difficulty key, ranks 105 to 112 of each benchmark, plus
three WritingBench prompts from the original pool. A benchmark's window
extends downward one rank at a time until WritingBench holds at least two
prompts with Chinese instructions or a Chinese topic, for the language check,
and HelloBench holds at least two long-input prompts. The check fails when a
smoke prompt is in the ``hard``, ``hard100``, or ``pilot`` lists or among the
twelve A10 calibration prompts (ranks 101 to 104), or when the pilot and
calibration sets overlap.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from functools import cache
from typing import Any

from agentic_cogwriter.paths import MANIFESTS_DIR, PROMPT_SETS_PATH
from agentic_cogwriter.prompts.prompt_sets import (
    BENCHMARKS,
    HARD100_COUNT,
    rank_by_difficulty,
)

CALIBRATION_PER_BENCHMARK = 4
FIRST_RANK, LAST_RANK = 105, 112
KEPT = ("writingbench-0210", "writingbench-0049", "writingbench-0051")
LONG_INPUT_WORDS = 1_000
MINIMUM = 2
_HAN = re.compile(r"[一-鿿]")


def chinese(row: dict[str, Any]) -> bool:
    """Chinese instructions (a Han majority) or a topic naming China."""

    text = row["prompt_text"]
    han = len(_HAN.findall(text))
    return han > len(text.split()) or bool(re.search(r"\bChin(a|ese)\b", text))


def long_input(row: dict[str, Any]) -> bool:
    return len(row["prompt_text"].split()) >= LONG_INPUT_WORDS


REQUIREMENTS: dict[str, Callable[[dict[str, Any]], bool]] = {
    "writingbench": chinese,
    "hellobench": long_input,
}


@cache
def _benchmark(name: str) -> tuple[dict[str, dict], list[str], dict[str, list[str]]]:
    lists = json.loads(PROMPT_SETS_PATH.read_text(encoding="utf-8"))["benchmarks"][name]
    rows = {
        row["prompt_id"]: row
        for row in (
            json.loads(line)
            for line in (MANIFESTS_DIR / f"{name}.jsonl")
            .read_text("utf-8")
            .splitlines()
        )
    }
    return rows, rank_by_difficulty(list(rows.values()), set(lists["pilot"])), lists


def ranked_window(name: str) -> list[str]:
    rows, ranked, _ = _benchmark(name)
    last = LAST_RANK
    test = REQUIREMENTS.get(name)
    while test and sum(test(rows[p]) for p in ranked[FIRST_RANK - 1 : last]) < MINIMUM:
        last += 1
    return ranked[FIRST_RANK - 1 : last]


def prompt_sets() -> dict[str, set[str]]:
    """Return the evaluation, pilot, and A10 calibration prompt sets."""

    evaluation: set[str] = set()
    pilot: set[str] = set()
    calibration: set[str] = set()
    for name in BENCHMARKS:
        _, ranked, lists = _benchmark(name)
        evaluation |= set(lists["hard"]) | set(lists["hard100"])
        pilot |= set(lists["pilot"])
        calibration |= set(
            ranked[HARD100_COUNT : HARD100_COUNT + CALIBRATION_PER_BENCHMARK]
        )
    return {"evaluation": evaluation, "pilot": pilot, "calibration": calibration}


def smoke_pool() -> list[str]:
    sets = prompt_sets()
    taken = set().union(*sets.values())
    window = [p for name in BENCHMARKS for p in ranked_window(name)]
    return window + [p for p in KEPT if p not in taken and p not in window]


def problems() -> list[str]:
    sets = prompt_sets()
    smoke = set(smoke_pool())
    found = [
        f"smoke and {name} share {sorted(smoke & members)}"
        for name, members in sets.items()
        if smoke & members
    ]
    if sets["pilot"] & sets["calibration"]:
        found.append("pilot and calibration overlap")
    return found


def main() -> int:
    found = problems()
    for problem in found:
        print(problem)
    print("smoke pool: " + ", ".join(smoke_pool()))
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
