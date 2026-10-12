"""Sample the revision-task prompts and write one frozen mid-task change each.

Usage (the endpoint and credential come from the named environment variables):

    GATEWAY_BASE_URL=... GATEWAY_API_KEY=... \
    uv run --project experiments python experiments/revision-tasks/make_changes.py
"""

from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path

from openai import OpenAI

HERE = Path(__file__).resolve().parent
EXPERIMENTS = HERE.parent
SEED = 20260908
PER_BENCHMARK = 20
BENCHMARKS = ("writingbench", "hellobench", "dolomites")
TYPES = ("constraint", "evidence", "conflict")
MODEL = "gpt-5.6-sol"
REASONING_EFFORT = "medium"

TYPE_DESCRIPTIONS = {
    "constraint": (
        "A new or changed constraint: change the target audience, narrow or widen "
        "the scope, require a new section, or change the required format."
    ),
    "evidence": (
        "New evidence: state a specific new fact, figure, or finding that the "
        "document must incorporate, or one that contradicts a premise or claim "
        "the assignment invites the writer to make."
    ),
    "conflict": (
        "A conflicting requirement: add a requirement that conflicts with part of "
        "the original assignment and forces the writer to restructure the "
        "document, for example by changing its organizing principle, merging or "
        "reordering sections, or replacing one required part with another."
    ),
}

INSTRUCTION = """You write one realistic mid-task change request for a writing assignment. A writer has already delivered a complete first version. The change arrives afterwards and must require a substantive revision of the document, not a cosmetic edit.

Change type: {change_type}
{type_description}

Rules:
- Write in the same language as the assignment.
- Write two to five sentences addressed to the writer, phrased as the requester would phrase them.
- Keep the change self-contained. State any new fact, figure, or source in full so that the writer needs no outside research. Invented evidence must be plausible and consistent with the assignment's setting.
- The change must be satisfiable in one revision of the same document. Do not ask for a different document.
- Do not mention AI, models, benchmarks, or evaluation.

Return exactly one JSON object of the form {{"change": "<change text>"}}.

[Assignment]
{assignment}

[Requested output constraints]
{constraints}"""

FOLLOWUP_TEMPLATE = """The requester sent a change to the assignment after reading your first version.

[Change]
{change}

Revise your document so that it satisfies the original assignment as modified by this change. Where the change conflicts with the original assignment, the change takes precedence. The final response must contain the complete revised text itself, not a summary of the edits or a link to a workspace artifact."""


def sample() -> list[dict[str, str]]:
    """Draw the stratified prompt sample and assign one change type to each."""

    prompt_sets = json.loads(
        (EXPERIMENTS / "prompts" / "prompt_sets.json").read_text(encoding="utf-8")
    )["benchmarks"]
    rng = random.Random(SEED)
    rows: list[dict[str, str]] = []
    for benchmark in BENCHMARKS:
        chosen = rng.sample(sorted(prompt_sets[benchmark]["hard100"]), PER_BENCHMARK)
        order = sorted(chosen)
        rng.shuffle(order)
        types = {pid: TYPES[index % len(TYPES)] for index, pid in enumerate(order)}
        rows.extend(
            {"benchmark": benchmark, "prompt_id": pid, "change_type": types[pid]}
            for pid in sorted(chosen)
        )
    return rows


def main() -> int:
    manifests = {
        benchmark: {
            row["prompt_id"]: row
            for row in map(
                json.loads,
                (EXPERIMENTS / "prompts" / "manifests" / f"{benchmark}.jsonl")
                .read_text(encoding="utf-8")
                .splitlines(),
            )
        }
        for benchmark in BENCHMARKS
    }
    output = HERE / "changes.jsonl"
    done = (
        {json.loads(line)["prompt_id"] for line in output.read_text().splitlines()}
        if output.exists()
        else set()
    )
    client = OpenAI(
        base_url=os.environ["GATEWAY_BASE_URL"], api_key=os.environ["GATEWAY_API_KEY"]
    )
    with output.open("a", encoding="utf-8") as stream:
        for row in sample():
            if row["prompt_id"] in done:
                continue
            record = manifests[row["benchmark"]][row["prompt_id"]]
            instruction = INSTRUCTION.format(
                change_type=row["change_type"],
                type_description=TYPE_DESCRIPTIONS[row["change_type"]],
                assignment=record["prompt_text"],
                constraints="\n".join(record["requested_output_constraints"]),
            )
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": instruction}],
                seed=SEED,
                reasoning_effort=REASONING_EFFORT,
                response_format={"type": "json_object"},
            )
            change = json.loads(response.choices[0].message.content)["change"].strip()
            if not change:
                raise ValueError(f"empty change for {row['prompt_id']}")
            stream.write(
                json.dumps(
                    {
                        **row,
                        "prompt_hash": record["hash"],
                        "generator_model": response.model,
                        "change": change,
                        "followup_message": FOLLOWUP_TEMPLATE.format(change=change),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            stream.flush()
            print(row["prompt_id"], row["change_type"], file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
