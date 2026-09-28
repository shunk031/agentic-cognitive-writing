"""Recover Monitor process sequences and relate them to pairwise outcomes."""

from __future__ import annotations

import argparse
import json
import math
import re
import tomllib
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .aggregate import _artifacts, prompt_collapsed_outcomes, wilson_interval
from .common import RunRecord, select_canonical_runs

START = "START"
END = "END"
FULL = "A4"
FIXED_ORDER = "A6"
SINGLE_PASS = "A7"
CONTRASTS = ((FULL, SINGLE_PASS), (FULL, FIXED_ORDER))
PROCESS_SWITCH = "process_switch"
REGENERATION = "goal_regenerated"


def _rate(count: int, total: int) -> dict[str, int | float | None]:
    return {"count": count, "total": total, "rate": count / total if total else None}


def _json_events(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read trace: {path}") from exc
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in {path}:{line_number}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"trace event is not an object: {path}:{line_number}")
        events.append(value)
    if not events:
        raise ValueError(f"trace is empty: {path}")
    return events


def _single_process_repetition(
    sequence: Sequence[str], fixed_order: Sequence[str]
) -> bool:
    if tuple(sequence) == tuple(fixed_order):
        return True
    for index, process in enumerate(fixed_order):
        for repetition_count in range(2, len(sequence) + 1):
            candidate = (
                tuple(fixed_order[:index])
                + (process,) * repetition_count
                + tuple(fixed_order[index + 1 :])
            )
            if tuple(sequence) == candidate:
                return True
    return False


def analyze_trace_events(
    events: Sequence[Mapping[str, Any]],
    *,
    fixed_order: Sequence[str],
) -> dict[str, Any]:
    """Extract one run's process sequence and trace-derived metrics."""

    sequence: list[str] = []
    transitions: Counter[str] = Counter()
    after_reviewing: Counter[str] = Counter()
    event_types: Counter[str] = Counter()
    process_values: Counter[str] = Counter()
    process_event_counts: defaultdict[str, Counter[str]] = defaultdict(Counter)
    goal_events: Counter[str] = Counter()
    regeneration_locations: list[dict[str, Any]] = []
    active_process: str | None = None
    sequence_index = 0
    process_occurrences: dict[str, int] = defaultdict(int)

    for event in events:
        event_type = event.get("event_type")
        process = event.get("process")
        if isinstance(event_type, str):
            event_types[event_type] += 1
        if isinstance(process, str):
            process_values[process] += 1
            if isinstance(event_type, str):
                process_event_counts[event_type][process] += 1
        if event_type in {"goal_created", "goal_developed", REGENERATION}:
            goal_events[str(event_type)] += 1
        if event_type == PROCESS_SWITCH:
            target = event.get("to_process")
            source = event.get("from_process")
            if target is not None and (
                not isinstance(target, str) or not target.strip()
            ):
                raise ValueError("process_switch to_process must be a string or null")
            if source is not None and (
                not isinstance(source, str) or not source.strip()
            ):
                raise ValueError("process_switch from_process must be a string or null")
            if source == "reviewing":
                after_reviewing["termination" if target is None else str(target)] += 1
            if target is not None:
                target = str(target)
                previous = sequence[-1] if sequence else START
                transitions[f"{previous}->{target}"] += 1
                sequence.append(target)
                active_process = target
                sequence_index += 1
                process_occurrences[target] += 1
            else:
                previous = sequence[-1] if sequence else START
                transitions[f"{previous}->{END}"] += 1
        elif event_type == REGENERATION:
            regeneration_locations.append(
                {
                    "event_process": process,
                    "active_process": active_process or process,
                    "sequence_index": sequence_index or None,
                }
            )

    regeneration_count = len(regeneration_locations)
    after_reviewing_result = {
        process: after_reviewing.get(process, 0)
        for process in ("planning", "translating", "termination")
    }
    extra_reviewing_targets = sorted(set(after_reviewing) - set(after_reviewing_result))
    if extra_reviewing_targets:
        after_reviewing_result["other"] = sum(
            after_reviewing[target] for target in extra_reviewing_targets
        )
    return {
        "sequence": sequence,
        "sequence_length": len(sequence),
        "equals_fixed_order": sequence == list(fixed_order),
        "matches_fixed_order_up_to_single_process_repetition": (
            _single_process_repetition(sequence, fixed_order)
        ),
        "transitions": dict(sorted(transitions.items())),
        "after_reviewing": after_reviewing_result,
        "after_reviewing_total": sum(after_reviewing.values()),
        "regeneration": {
            "count": regeneration_count,
            "locations": regeneration_locations,
        },
        "event_types": dict(sorted(event_types.items())),
        "process_values": dict(sorted(process_values.items())),
        "process_event_counts": {
            event_type: dict(sorted(counts.items()))
            for event_type, counts in sorted(process_event_counts.items())
        },
        "goal_events": dict(sorted(goal_events.items())),
        "switch_count": event_types.get(PROCESS_SWITCH, 0),
        "active_process_occurrences": dict(sorted(process_occurrences.items())),
    }


def _matrix(
    transitions: Mapping[str, int], states: Sequence[str]
) -> dict[str, dict[str, int]]:
    matrix = {row: dict.fromkeys(states, 0) for row in states}
    for transition, count in transitions.items():
        source, target = transition.split("->", 1)
        if source in matrix and target in matrix[source]:
            matrix[source][target] += count
    return matrix


def summarize_observations(
    observations: Sequence[Mapping[str, Any]],
    *,
    fixed_order: Sequence[str] = ("planning", "translating", "reviewing"),
) -> dict[str, Any]:
    """Aggregate per-run observations without reading run artifacts."""

    total = len(observations)
    sequence_counts: Counter[tuple[str, ...]] = Counter(
        tuple(observation["sequence"]) for observation in observations
    )
    lengths = Counter(
        int(observation["sequence_length"]) for observation in observations
    )
    transitions: Counter[str] = Counter()
    event_types: Counter[str] = Counter()
    process_values: Counter[str] = Counter()
    process_event_counts: defaultdict[str, Counter[str]] = defaultdict(Counter)
    goal_events: Counter[str] = Counter()
    after_reviewing = Counter()
    regeneration_events = 0
    regeneration_locations: Counter[tuple[Any, Any, Any]] = Counter()
    for observation in observations:
        transitions.update(observation["transitions"])
        event_types.update(observation["event_types"])
        process_values.update(observation["process_values"])
        for event_type, counts in observation["process_event_counts"].items():
            process_event_counts[event_type].update(counts)
        goal_events.update(observation["goal_events"])
        after_reviewing.update(observation["after_reviewing"])
        regeneration_events += observation["regeneration"]["count"]
        for location in observation["regeneration"]["locations"]:
            regeneration_locations[
                (
                    location.get("event_process"),
                    location.get("active_process"),
                    location.get("sequence_index"),
                )
            ] += 1

    switch_processes = {process for sequence in sequence_counts for process in sequence}
    states = [START, *fixed_order]
    extras = sorted(switch_processes - set(states) - {END})
    states.extend(process for process in extras if process not in states)
    states.append(END)
    return {
        "run_count": total,
        "sequence_distribution": [
            {
                "sequence": list(sequence),
                "count": count,
                "total": total,
                "rate": count / total if total else None,
            }
            for sequence, count in sorted(
                sequence_counts.items(), key=lambda item: (len(item[0]), item[0])
            )
        ],
        "sequence_length_distribution": [
            {"length": length, **_rate(count, total)}
            for length, count in sorted(lengths.items())
        ],
        "transitions": dict(sorted(transitions.items())),
        "transition_states": states,
        "transition_matrix": _matrix(transitions, states),
        "exact_fixed_order": _rate(
            sum(observation["equals_fixed_order"] for observation in observations),
            total,
        ),
        "single_process_repetition": _rate(
            sum(
                observation["matches_fixed_order_up_to_single_process_repetition"]
                for observation in observations
            ),
            total,
        ),
        "after_reviewing": {
            **{
                target: _rate(
                    after_reviewing.get(target, 0),
                    sum(after_reviewing.values()),
                )
                for target in ("planning", "translating", "termination")
            },
            "total": sum(after_reviewing.values()),
        },
        "regeneration": {
            "runs": _rate(
                sum(
                    observation["regeneration"]["count"] > 0
                    for observation in observations
                ),
                total,
            ),
            "events": regeneration_events,
            "locations": [
                {
                    "event_process": event_process,
                    "active_process": active_process,
                    "sequence_index": sequence_index,
                    "count": count,
                }
                for (event_process, active_process, sequence_index), count in sorted(
                    regeneration_locations.items(), key=str
                )
            ],
        },
        "event_types": dict(sorted(event_types.items())),
        "process_values": dict(sorted(process_values.items())),
        "process_event_counts": {
            event_type: dict(sorted(counts.items()))
            for event_type, counts in sorted(process_event_counts.items())
        },
        "goal_events": dict(sorted(goal_events.items())),
    }


def read_fixed_order(repo_root: Path | None = None) -> dict[str, Any]:
    """Read A6's declared vocabulary and fixed-order skill text."""

    root = repo_root or Path(__file__).parents[3].parent
    condition_path = root / "experiments" / "conditions" / "a6_plugin.toml"
    skill_path = (
        root
        / "experiments"
        / "plugin"
        / "skills"
        / "cognitive-writing-fixed-order"
        / "SKILL.md"
    )
    condition = tomllib.loads(condition_path.read_text(encoding="utf-8"))
    skill_text = skill_path.read_text(encoding="utf-8")
    trace = condition.get("trace", {})
    condition_processes = trace.get("processes")
    if not isinstance(condition_processes, list) or not all(
        isinstance(process, str) for process in condition_processes
    ):
        raise ValueError("A6 condition does not declare process vocabulary")
    match = re.search(r"fixed `([^`]+)`, `([^`]+)`, then `([^`]+)` order", skill_text)
    if match is None:
        raise ValueError("fixed-order skill does not state its canonical order")
    canonical = [value.casefold() for value in match.groups()]
    return {
        "condition_id": condition.get("condition_id"),
        "condition_path": str(condition_path),
        "condition_processes": condition_processes,
        "condition_process_order": trace.get("process_order"),
        "skill_path": str(skill_path),
        "skill_text": skill_text,
        "canonical": canonical,
    }


def fisher_exact_two_sided(table: Sequence[Sequence[int]]) -> float:
    """Return the two-sided Fisher exact p-value for a 2x2 table."""

    if len(table) != 2 or any(len(row) != 2 for row in table):
        raise ValueError("Fisher exact test needs a 2x2 table")
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for row in table
        for value in row
    ):
        raise ValueError("Fisher exact table entries must be non-negative integers")
    a, b = table[0]
    c, d = table[1]
    row_one, row_two = a + b, c + d
    column_one, total = a + c, a + b + c + d
    if total == 0:
        return 1.0

    def probability(first_cell: int) -> float:
        return (
            math.comb(row_one, first_cell)
            * math.comb(row_two, column_one - first_cell)
            / math.comb(total, column_one)
        )

    lower = max(0, column_one - row_two)
    upper = min(row_one, column_one)
    observed = probability(a)
    return min(
        1.0,
        sum(
            probability(first_cell)
            for first_cell in range(lower, upper + 1)
            if probability(first_cell) <= observed + 1e-15
        ),
    )


def _run_detail(
    run: RunRecord,
    *,
    run_set: str,
    run_role: str,
    fixed_order: Sequence[str],
) -> dict[str, Any]:
    trace_path = run.path / ".writing" / "trace" / "process.jsonl"
    observed = analyze_trace_events(_json_events(trace_path), fixed_order=fixed_order)
    return {
        "run_set": run_set,
        "run_role": run_role,
        "benchmark": run.benchmark,
        "condition": run.condition,
        "prompt": run.prompt,
        "platform": run.platform,
        "run_path": str(run.path),
        "status": run.status,
        "subagent_spawn_count": run.manifest.get("subagent_spawn_count", 0),
        **observed,
    }


def _association_cell(values: Sequence[str]) -> dict[str, Any]:
    counts = Counter(values)
    wins = counts.get("left", 0)
    losses = counts.get("right", 0)
    ties = counts.get("tie", 0)
    low, high = wilson_interval(wins, losses)
    return {
        "pairs": len(values),
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "n_non_tie": wins + losses,
        "win_rate": wins / (wins + losses) if wins + losses else None,
        "wilson_low": low,
        "wilson_high": high,
    }


def _association(
    outcomes: Mapping[tuple[str, str, str, str], str],
    full_details: Mapping[tuple[str, str, str], Mapping[str, Any]],
    *,
    contrast: tuple[str, str],
) -> dict[str, Any]:
    split_values: dict[str, list[str]] = {
        "fixed_order_exact": [],
        "not_fixed_order_exact": [],
    }
    label = f"{contrast[0]}:{contrast[1]}"
    for (benchmark, platform, observed_label, prompt), outcome in outcomes.items():
        if observed_label != label:
            continue
        detail = full_details.get((benchmark, platform, prompt))
        if detail is None:
            continue
        split = (
            "fixed_order_exact"
            if detail["equals_fixed_order"]
            else "not_fixed_order_exact"
        )
        split_values[split].append(outcome)
    cells = {split: _association_cell(values) for split, values in split_values.items()}
    table = [
        [cells["fixed_order_exact"]["wins"], cells["fixed_order_exact"]["losses"]],
        [
            cells["not_fixed_order_exact"]["wins"],
            cells["not_fixed_order_exact"]["losses"],
        ],
    ]
    return {
        "full_condition": contrast[0],
        "comparison_condition": contrast[1],
        "splits": cells,
        "fisher_exact_two_sided": {
            "table": table,
            "p_value": fisher_exact_two_sided(table),
        },
    }


def analyze_run_roots(
    roots: Sequence[Path], *, repo_root: Path | None = None
) -> dict[str, Any]:
    """Analyze canonical completed traces from primary and direction roots."""

    if not roots:
        raise ValueError("at least one runs root is required")
    fixed = read_fixed_order(repo_root)
    fixed_order = fixed["canonical"]
    detail_by_condition: dict[str, list[dict[str, Any]]] = {FULL: [], FIXED_ORDER: []}
    run_sets: list[dict[str, Any]] = []
    for index, root_value in enumerate(roots, start=1):
        root = root_value.resolve()
        run_set = f"run-{index}"
        run_role = "primary" if index == 1 else "direction-check"
        canonical = select_canonical_runs([root])
        set_output: dict[str, Any] = {
            "label": run_set,
            "role": run_role,
            "root": str(root),
            "conditions": {},
        }
        for condition in (FULL, FIXED_ORDER):
            condition_runs = [run for run in canonical if run.condition == condition]
            completed = [run for run in condition_runs if run.status == "completed"]
            observations: list[dict[str, Any]] = []
            details: list[dict[str, Any]] = []
            for run in completed:
                detail = _run_detail(
                    run,
                    run_set=run_set,
                    run_role=run_role,
                    fixed_order=fixed_order,
                )
                details.append(detail)
                observations.append(detail)
                detail_by_condition[condition].append(detail)
            set_output["conditions"][condition] = {
                "canonical_runs": len(condition_runs),
                "completed_runs": len(completed),
                "failed_runs": len(condition_runs) - len(completed),
                "summary": summarize_observations(
                    observations, fixed_order=fixed_order
                ),
                "runs": details,
            }
        run_sets.append(set_output)

    condition_summaries = {
        condition: {
            "summary": summarize_observations(
                detail_by_condition[condition], fixed_order=fixed_order
            ),
            "runs": detail_by_condition[condition],
        }
        for condition in (FULL, FIXED_ORDER)
    }
    fixed_comparison = {
        "fixed_order": fixed,
        "full": condition_summaries[FULL]["summary"]["exact_fixed_order"],
        "fixed_order_condition": condition_summaries[FIXED_ORDER]["summary"][
            "exact_fixed_order"
        ],
        "full_single_process_repetition": condition_summaries[FULL]["summary"][
            "single_process_repetition"
        ],
    }

    associations: dict[str, Any] = {}
    for run_set in run_sets:
        root = Path(run_set["root"])
        canonical = select_canonical_runs([root])
        artifacts = _artifacts([root], canonical)
        outcomes = prompt_collapsed_outcomes(
            artifacts,
            canonical,
            contrasts=CONTRASTS,
        )
        full_details = {
            (detail["benchmark"], detail["platform"], detail["prompt"]): detail
            for detail in run_set["conditions"][FULL]["runs"]
        }
        associations[run_set["label"]] = {
            f"{left}_vs_{right}": _association(
                outcomes,
                full_details,
                contrast=(left, right),
            )
            for left, right in CONTRASTS
        }

    combined_outcomes: dict[str, Any] = {}
    all_values: dict[str, list[str]] = defaultdict(list)
    for run_set in run_sets:
        for label, association in associations[run_set["label"]].items():
            for split, cell in association["splits"].items():
                all_values[f"{label}:{split}"].extend(
                    ["left"] * cell["wins"]
                    + ["right"] * cell["losses"]
                    + ["tie"] * cell["ties"]
                )
    for left, right in CONTRASTS:
        label = f"{left}_vs_{right}"
        values = {
            split: all_values[f"{label}:{split}"]
            for split in ("fixed_order_exact", "not_fixed_order_exact")
        }
        cells = {split: _association_cell(items) for split, items in values.items()}
        table = [
            [cells["fixed_order_exact"]["wins"], cells["fixed_order_exact"]["losses"]],
            [
                cells["not_fixed_order_exact"]["wins"],
                cells["not_fixed_order_exact"]["losses"],
            ],
        ]
        combined_outcomes[label] = {
            "full_condition": left,
            "comparison_condition": right,
            "splits": cells,
            "fisher_exact_two_sided": {
                "table": table,
                "p_value": fisher_exact_two_sided(table),
            },
        }

    return {
        "provenance": {
            "run_roots": [
                {
                    "label": f"run-{index}",
                    "role": "primary" if index == 1 else "direction-check",
                    "path": str(root.resolve()),
                }
                for index, root in enumerate(roots, start=1)
            ],
            "event_types": sorted(
                set(
                    event_type
                    for condition in condition_summaries.values()
                    for event_type in condition["summary"]["event_types"]
                )
            ),
            "process_values": sorted(
                set(
                    process
                    for condition in condition_summaries.values()
                    for process in condition["summary"]["process_values"]
                )
            ),
            "sequence_source": (
                "process_switch.to_process in trace line order; termination is "
                "excluded from the sequence and included as END."
            ),
            "goal_event_source": (
                "goal_created, goal_developed, and goal_regenerated trace events; "
                "goal_regenerated is treated as accepted regeneration."
            ),
        },
        "fixed_order_comparison": fixed_comparison,
        "conditions": condition_summaries,
        "run_sets": run_sets,
        "prompt_association": {
            "primary_run_set": associations.get("run-1", {}),
            "direction_checks": {
                label: value
                for label, value in associations.items()
                if label != "run-1"
            },
            "combined": combined_outcomes,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze Monitor process sequences from canonical run traces."
    )
    parser.add_argument("--runs-root", type=Path, action="append", required=True)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if len(args.runs_root) < 1:
        raise SystemExit("at least one --runs-root is required")
    report = analyze_run_roots(args.runs_root, repo_root=args.repo_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
