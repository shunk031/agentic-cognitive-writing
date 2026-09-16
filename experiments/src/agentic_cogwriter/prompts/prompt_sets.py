"""Write the committed pilot and hard prompt subsets without network access."""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path
from typing import Any

from agentic_cogwriter.paths import MANIFESTS_DIR, PROMPT_SETS_PATH
from agentic_cogwriter.prompts.materialize import pretty_json, write_immutable

BENCHMARKS = ("hellobench", "writingbench", "dolomites")
SEED = 20260908
PILOT_COUNT = 10
HARD_COUNT = 20
HELLOBENCH_PILOT_PER_CATEGORY = 2
MAX_LENGTH = 6000
REQUESTED_LENGTH_REGEX = r"(\d[\d,]{2,})\s*(?:-|\s)?(?:words?|字|tokens?)"


def write_prompt_sets(
    output_path: Path = PROMPT_SETS_PATH,
    manifest_dir: Path = MANIFESTS_DIR,
) -> bytes:
    """Generate the prompt-set artifact from the committed JSONL manifests."""

    manifests: dict[str, list[dict[str, Any]]] = {
        benchmark: [
            json.loads(line)
            for line in (manifest_dir / f"{benchmark}.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        for benchmark in BENCHMARKS
    }

    pilot: dict[str, list[str]] = {}
    shared_rng = random.Random(SEED)
    for benchmark in ("writingbench", "dolomites"):
        ids = sorted(row["prompt_id"] for row in manifests[benchmark])
        pilot[benchmark] = sorted(shared_rng.sample(ids, PILOT_COUNT))

    by_category: dict[str, list[str]] = {}
    for row in manifests["hellobench"]:
        category = row["prompt_id"].split("-", 1)[1].rsplit("_", 1)[0]
        by_category.setdefault(category, []).append(row["prompt_id"])
    hellobench_rng = random.Random(SEED)
    pilot["hellobench"] = []
    for category in sorted(by_category):
        pilot["hellobench"].extend(
            sorted(
                hellobench_rng.sample(
                    sorted(by_category[category]), HELLOBENCH_PILOT_PER_CATEGORY
                )
            )
        )

    requested_length_pattern = re.compile(REQUESTED_LENGTH_REGEX, re.IGNORECASE)
    hard: dict[str, list[str]] = {}
    for benchmark in BENCHMARKS:
        scored: list[tuple[int, int, int, str]] = []
        for row in manifests[benchmark]:
            if row["prompt_id"] in set(pilot[benchmark]):
                continue
            text = (
                row["prompt_text"]
                + " "
                + json.dumps(row.get("requested_output_constraints"))
            )
            requested_length = max(
                [
                    int(match.replace(",", ""))
                    for match in requested_length_pattern.findall(text)
                ]
                or [0]
            )
            prompt_words = len(row["prompt_text"].split())
            if requested_length > MAX_LENGTH or prompt_words > MAX_LENGTH:
                continue
            scored.append(
                (
                    prompt_words + requested_length,
                    prompt_words,
                    requested_length,
                    row["prompt_id"],
                )
            )
        scored.sort(reverse=True)
        hard[benchmark] = [prompt_id for *_, prompt_id in scored[:HARD_COUNT]]

    artifact = {
        "schema_version": "1.0",
        "rule": {
            "seed": SEED,
            "counts": {"pilot": PILOT_COUNT, "hard": HARD_COUNT},
            "hellobench_pilot_per_category": HELLOBENCH_PILOT_PER_CATEGORY,
            "difficulty": "prompt word count + requested output length",
            "difficulty_input": (
                "prompt_text plus the JSON dump of requested_output_constraints"
            ),
            "requested_length_units": ["words", "字", "tokens"],
            "requested_length_regex": REQUESTED_LENGTH_REGEX,
            "exclusion": {
                "pilot_ids": True,
                "max_prompt_words": MAX_LENGTH,
                "max_requested_length": MAX_LENGTH,
            },
            "sort_key": [
                "score",
                "prompt_words",
                "requested_length",
                "prompt_id",
            ],
            "sort_order": "descending",
        },
        "benchmarks": {
            benchmark: {"pilot": pilot[benchmark], "hard": hard[benchmark]}
            for benchmark in BENCHMARKS
        },
    }
    content = (pretty_json(artifact) + "\n").encode("utf-8")
    write_immutable(output_path, content)
    return content


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PROMPT_SETS_PATH)
    args = parser.parse_args(argv)
    content = write_prompt_sets(args.output)
    print(f"{args.output}: {len(content)} bytes")
    return 0
