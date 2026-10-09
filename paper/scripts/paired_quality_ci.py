"""Paired prompt-level bootstrap intervals for Table 3's native and pointwise scores.

For each benchmark and score, every prompt's three generation runs are averaged per
system first, so the prompt is the resampling unit. The interval is a percentile
bootstrap over prompts of the mean paired difference for every ordered pair of the
four systems in Table 3, using prompts scored for both systems in at least one run.

Run with the experiments package on the path, for example:
    uv run --project ../experiments python scripts/paired_quality_ci.py RUN1 RUN2 RUN3
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from pathlib import Path

from agentic_cogwriter.analysis.common import select_canonical_runs

SYSTEMS = ("A1", "A2", "A3", "A4", "A5", "A6", "A7")
FOCAL = "A4"
DISPLAYED = ("A1", "A2", "A3", "A4")
DIMENSIONS = (
    "content_adequacy_depth",
    "factuality_constraint_fidelity",
    "instruction_fulfillment",
    "organization_global_coherence",
    "style_voice_audience_fit",
)
NATIVE_TASKS = {"WritingBench": "native-pointwise", "HelloBench": "native-checklist"}


def _records(run_dir: Path, task: str) -> list[dict]:
    files = sorted((run_dir / "scores" / task).glob("*/scores.jsonl"))
    if len(files) > 1:
        raise ValueError(f"{run_dir}: expected one {task} judge, found {len(files)}")
    return [json.loads(line) for line in files[0].read_text().splitlines() if line.strip()] if files else []


def _native(benchmark: str, records: list[dict]) -> float | None:
    if not records:
        return None
    if benchmark == "WritingBench":
        return statistics.fmean(float(r["score"]) for r in records)
    return statistics.fmean(float(item["evaluation_score"]) for item in records[0]["checklist_items"])


def per_prompt_scores(roots: list[Path]) -> dict:
    """{benchmark: {score: {system: {prompt: [value per run]}}}}, composite z-scored per run and benchmark over all seven systems."""
    out: dict = {}
    for root in roots:
        pointwise: dict = {}
        for run in select_canonical_runs([root]):
            if run.condition not in SYSTEMS or run.status != "completed":
                continue
            bench = out.setdefault(run.benchmark, {"native": {}, "pointwise": {}})
            if run.benchmark in NATIVE_TASKS:
                value = _native(run.benchmark, _records(run.path, NATIVE_TASKS[run.benchmark]))
                if value is not None:
                    bench["native"].setdefault(run.condition, {}).setdefault(run.prompt, []).append(value)
            records = _records(run.path, "pointwise")
            if records:
                pointwise.setdefault(run.benchmark, []).append((run.condition, run.prompt, records[0]["scores"]))
        for benchmark, rows in pointwise.items():
            stats = {}
            for dim in DIMENSIONS:
                values = [float(scores[dim]) for _, _, scores in rows]
                stats[dim] = (statistics.fmean(values), statistics.pstdev(values) or 1.0)
            for condition, prompt, scores in rows:
                z = statistics.fmean((float(scores[d]) - stats[d][0]) / stats[d][1] for d in DIMENSIONS)
                out[benchmark]["pointwise"].setdefault(condition, {}).setdefault(prompt, []).append(z)
    return out


def paired_ci(focal: dict, other: dict, resamples: int, seed: int) -> dict:
    prompts = sorted(set(focal) & set(other))
    diffs = [statistics.fmean(focal[p]) - statistics.fmean(other[p]) for p in prompts]
    rng = random.Random(seed)
    boots = sorted(statistics.fmean(rng.choices(diffs, k=len(diffs))) for _ in range(resamples))
    return {
        "n_prompts": len(prompts),
        "mean_difference": statistics.fmean(diffs),
        "ci95": [boots[int(0.025 * resamples)], boots[int(0.975 * resamples) - 1]],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("roots", nargs=3, type=Path, help="generation runs 1, 2, and 3")
    parser.add_argument("--resamples", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "results/pointwise-three-runs/paired-bootstrap.json")
    args = parser.parse_args()
    data = per_prompt_scores(args.roots)
    report = {
        "method": __doc__.strip().split("\n\n")[1].replace("\n", " "),
        "focal_system": FOCAL,
        "resamples": args.resamples,
        "seed": args.seed,
        "contrasts": {
            benchmark: {
                score: {
                    f"{first}-{second}": paired_ci(by_system[first], by_system[second], args.resamples, args.seed)
                    for first in DISPLAYED
                    for second in DISPLAYED
                    if first != second
                }
                for score, by_system in scores.items()
                if all(system in by_system for system in DISPLAYED)
            }
            for benchmark, scores in sorted(data.items())
        },
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
