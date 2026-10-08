#!/usr/bin/env python3
"""Generate the manuscript's confirmatory and robustness figures from JSON."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt

plt.style.use("ggplot")
# Match the manuscript's Times body text; STIX is matplotlib's bundled Times-compatible face.
matplotlib.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "STIXGeneral"],
        "mathtext.fontset": "stix",
    }
)
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import PercentFormatter


CONTRASTS = (
    ("A4:A1", "Agentic CogWriter", "Single-pass"),
    ("A4:A2", "Agentic CogWriter", "Staged"),
    ("A4:A3", "Agentic CogWriter", "Task-planning"),
    ("A4:A5", "Agentic CogWriter", "No-goals"),
    ("A4:A6", "Agentic CogWriter", "Fixed-order"),
    ("A7:A1", "Single-writer", "Single-pass"),
    ("A7:A4", "Single-writer", "Agentic CogWriter"),
    ("A7:A5", "Single-writer", "No-goals"),
)
ROBUSTNESS_CONTRASTS = (
    ("A4:A1", "Agentic CogWriter", "Single-pass"),
    ("A4:A3", "Agentic CogWriter", "Task-planning"),
    ("A4:A5", "Agentic CogWriter", "No-goals"),
)
BENCHMARKS = ("WritingBench", "HelloBench", "DoLoMiTes")
REFERENCE_RATE = 0.5
HOLM_ALPHA = 0.05
RUN_COLORS = ("#0072B2", "#D55E00", "#009E73")
GTP_COLOR = "#0072B2"
SONNET_COLOR = "#CC79A7"


def require_mapping(data: dict[str, Any], key: str, source: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{source} is missing mapping field {key}")
    return value


def require_value(data: dict[str, Any], key: str, source: str) -> Any:
    if key not in data:
        raise ValueError(f"{source} is missing field {key}")
    return data[key]


def require_number(data: dict[str, Any], key: str, source: str) -> float:
    value = require_value(data, key, source)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{source}.{key} is not numeric")
    return float(value)


def require_int(data: dict[str, Any], key: str, source: str) -> int:
    value = require_value(data, key, source)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{source}.{key} is not an integer")
    return value


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"could not read {label} JSON: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} JSON must contain an object: {path}")
    return value


def nested(data: dict[str, Any], keys: tuple[str, ...], source: str) -> dict[str, Any]:
    current = data
    for key in keys:
        current = require_mapping(current, key, source)
    return current


def pairwise_outcome(
    aggregation: dict[str, Any], benchmark: str, contrast: str, run_label: str
) -> dict[str, float | int]:
    source = f"aggregation {run_label} {benchmark}.{contrast}.prompt_collapsed_across_judges"
    platform = nested(
        aggregation,
        ("pairwise", "benchmarks", benchmark, "platforms", "codex"),
        source,
    )
    collapsed = require_mapping(platform, "prompt_collapsed_across_judges", source)
    outcome = require_mapping(collapsed, contrast, source)
    return {
        "wins": require_int(outcome, "wins", source),
        "losses": require_int(outcome, "losses", source),
        "ties": require_int(outcome, "ties", source),
        "win_rate": require_number(outcome, "win_rate", source),
        "wilson_low": require_number(outcome, "wilson_low", source),
        "wilson_high": require_number(outcome, "wilson_high", source),
        "p_holm": require_number(outcome, "p_holm", source),
    }


def forest_rows(aggregations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for contrast, left, right in CONTRASTS:
        for benchmark in BENCHMARKS:
            runs = [
                pairwise_outcome(aggregation, benchmark, contrast, f"replication {run_index}")
                for run_index, aggregation in enumerate(aggregations, 1)
            ]
            rows.append(
                {
                    "label": f"{left} vs {right}, {benchmark}",
                    "runs": runs,
                    "mean": statistics.mean(run["win_rate"] for run in runs),
                }
            )
    return rows


def save_forest(rows: list[dict[str, Any]], output: Path) -> None:
    figure, axis = plt.subplots(figsize=(0.96 * ACL_TEXTWIDTH_IN, 6.0), layout="constrained")
    group_size = len(BENCHMARKS)
    group_gap = 0.45
    positions = [index + group_gap * (index // group_size) for index in range(len(rows))]
    axis.set_yticks(positions)
    axis.set_yticklabels([row["label"] for row in rows], fontsize=8)
    axis.invert_yaxis()
    offsets = (-0.13, 0.0, 0.13)
    for run_index, (offset, color) in enumerate(zip(offsets, RUN_COLORS), 1):
        for position, row in zip(positions, rows):
            run = row["runs"][run_index - 1]
            rate = run["win_rate"]
            lower = rate - run["wilson_low"]
            upper = run["wilson_high"] - rate
            y_position = position + offset
            axis.errorbar(
                rate,
                y_position,
                xerr=[[lower], [upper]],
                fmt="none",
                ecolor=color,
                elinewidth=0.8,
                capsize=2,
                zorder=2,
            )
            axis.scatter(
                rate,
                y_position,
                s=20,
                marker="o",
                facecolors=color if run["p_holm"] < HOLM_ALPHA else "white",
                edgecolors=color,
                linewidths=0.8,
                zorder=3,
            )
    axis.scatter(
        [row["mean"] for row in rows],
        positions,
        marker="D",
        s=22,
        color="black",
        label="Mean across generation runs",
        zorder=4,
    )
    axis.axvline(REFERENCE_RATE, color="#555555", linewidth=0.8, linestyle="--")
    axis.set_xlim(0.0, 1.0)
    axis.xaxis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=0))
    axis.set_xlabel("Win rate among decided prompts", fontsize=9)
    axis.grid(axis="x", color="#dddddd", linewidth=0.5)
    axis.set_axisbelow(True)
    for boundary_index in range(group_size, len(rows), group_size):
        boundary = (positions[boundary_index - 1] + positions[boundary_index]) / 2
        axis.axhline(boundary, color="#cccccc", linewidth=0.5, zorder=1)
    run_handles = [
        Line2D([0], [0], marker="o", color=color, linestyle="none", label=f"Generation run {run}")
        for run, color in enumerate(RUN_COLORS, 1)
    ]
    mark_handles = [
        Line2D([0], [0], marker="o", color="#333333", markerfacecolor="#333333", linestyle="none", label="Holm survives"),
        Line2D([0], [0], marker="o", color="#333333", markerfacecolor="white", linestyle="none", label="Holm does not survive"),
        Line2D([0], [0], marker="D", color="black", linestyle="none", label="Mean across generation runs"),
    ]
    figure.legend(handles=run_handles + mark_handles, loc="outside upper left", ncol=3, frameon=False, fontsize=8)
    figure.savefig(output, format="pdf")
    plt.close(figure)


def length_values(
    report: dict[str, Any], run_label: str
) -> tuple[list[str], list[float], list[int], list[tuple[str, float]]]:
    source_label = f"length-control JSON {run_label}"
    ratio_bins = require_mapping(report, "ratio_bins", source_label)
    labels = list(ratio_bins)
    rates = []
    counts = []
    for label in labels:
        source = f"{source_label} ratio_bins.{label}"
        stats = require_mapping(ratio_bins, label, f"{source_label} ratio_bins")
        rates.append(require_number(stats, "win_rate", source))
        counts.append(require_int(stats, "pairs", source))
    matched = require_mapping(report, "length_matched", source_label)
    markers = []
    for band in ("5_percent", "10_percent"):
        band_data = require_mapping(matched, band, f"{source_label} length_matched")
        stats = require_mapping(band_data, "A4:A1", f"{source_label} length_matched.{band}")
        markers.append((band.replace("_percent", "% match"), require_number(stats, "win_rate", f"{source_label} length_matched.{band}.A4:A1")))
    return labels, rates, counts, markers


def save_length(report: dict[str, Any], output: Path) -> None:
    labels, rates, counts, markers = length_values(report, "first replication")
    figure, axis = plt.subplots(figsize=(3.35, 3.75))
    positions = list(range(len(labels)))
    bars = axis.bar(positions, rates, color="#56B4E9", edgecolor="#333333", linewidth=0.5)
    for bar, count in zip(bars, counts):
        axis.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.025, f"n={count}", ha="center", va="bottom", fontsize=7)
    marker_positions = [len(labels) - 0.35, len(labels) + 0.35]
    marker_handles = []
    for marker_position, (label, rate) in zip(marker_positions, markers):
        axis.scatter(marker_position, rate, marker="D", s=26, color="#D55E00", zorder=4)
        marker_handles.append(
            Line2D([0], [0], marker="D", color="#D55E00", linestyle="none", label=label)
        )
    axis.axvline(len(labels) - 0.5, color="#aaaaaa", linewidth=0.6)
    axis.axhline(REFERENCE_RATE, color="#555555", linewidth=0.8, linestyle="--")
    axis.set_xticks(positions)
    display_labels = {
        "1.00-1.05": "1.00–\n1.05",
        "1.05-1.10": "1.05–\n1.10",
        "1.10-1.25": "1.10–\n1.25",
        "1.25-1.50": "1.25–\n1.50",
        "1.50-2.00": "1.50–\n2.00",
        "2.00+": "2+",
    }
    axis.set_xticklabels([display_labels.get(label, label) for label in labels], ha="center", fontsize=7, linespacing=0.9)
    axis.set_xlim(-0.6, len(labels) + 0.8)
    axis.set_ylim(0.0, 1.0)
    axis.yaxis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=0))
    axis.tick_params(axis="both", labelsize=7)
    axis.set_ylabel("Longer side win rate", fontsize=8)
    axis.set_xlabel("Output-length ratio")
    axis.grid(axis="y", color="#dddddd", linewidth=0.5)
    axis.set_axisbelow(True)
    axis.legend(handles=marker_handles, loc="lower left", bbox_to_anchor=(0.0, 1.01), ncol=2, frameon=False, fontsize=7)
    figure.subplots_adjust(left=0.16, right=0.99, top=0.84, bottom=0.23)
    figure.savefig(output, format="pdf")
    plt.close(figure)


def cross_family_values(
    aggregation: dict[str, Any], report: dict[str, Any]
) -> list[dict[str, Any]]:
    rows = []
    cross_contrasts = require_mapping(report, "contrasts", "cross-family JSON")
    for contrast, left, right in ROBUSTNESS_CONTRASTS:
        contrast_data = require_mapping(cross_contrasts, contrast, "cross-family JSON contrasts")
        benchmark_data = require_mapping(contrast_data, "benchmarks", f"cross-family JSON contrasts.{contrast}")
        for benchmark in BENCHMARKS:
            same_family = pairwise_outcome(aggregation, benchmark, contrast, "first replication")
            sonnet = require_mapping(benchmark_data, benchmark, f"cross-family JSON contrasts.{contrast}.benchmarks")
            sonnet_win = require_mapping(sonnet, "win_rate", f"cross-family JSON contrasts.{contrast}.benchmarks.{benchmark}")
            rows.append(
                {
                    "label": f"{left} vs {right}\n{benchmark}",
                    "same_family": same_family["win_rate"],
                    "sonnet": require_number(sonnet_win, "rate", f"cross-family JSON contrasts.{contrast}.benchmarks.{benchmark}.win_rate"),
                    "ties": require_int(sonnet, "ties", f"cross-family JSON contrasts.{contrast}.benchmarks.{benchmark}"),
                    "n": require_int(sonnet, "n", f"cross-family JSON contrasts.{contrast}.benchmarks.{benchmark}"),
                }
            )
    for row in rows:
        if row["n"] <= 0:
            raise ValueError(f"cross-family JSON has non-positive n for {row['label']}")
        row["tie_share"] = row["ties"] / row["n"]
    return rows


def save_cross_family(rows: list[dict[str, Any]], output: Path) -> None:
    figure, axis = plt.subplots(figsize=(3.35, 3.75))
    positions = list(range(len(rows)))
    bar_height = 0.34
    same_positions = [position - bar_height / 2 for position in positions]
    sonnet_positions = [position + bar_height / 2 for position in positions]
    axis.barh(same_positions, [row["same_family"] for row in rows], height=bar_height, color=GTP_COLOR, label="gpt-5.6-sol")
    sonnet_rates = [row["sonnet"] for row in rows]
    axis.barh(sonnet_positions, sonnet_rates, height=bar_height, color=SONNET_COLOR, label="Sonnet 5")
    axis.axvline(REFERENCE_RATE, color="#555555", linewidth=0.8, linestyle="--")
    axis.set_yticks(positions)
    axis.set_yticklabels([row["label"] for row in rows], fontsize=7)
    axis.invert_yaxis()
    axis.set_xlim(0.0, 1.0)
    axis.xaxis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=0))
    axis.tick_params(axis="both", labelsize=7)
    axis.set_xlabel("Win rate among non-tied pairs", fontsize=8)
    axis.grid(axis="x", color="#dddddd", linewidth=0.5)
    axis.set_axisbelow(True)
    for same_position, sonnet_position, row in zip(same_positions, sonnet_positions, rows):
        axis.annotate(
            f"{row['same_family']:.0%}",
            xy=(row["same_family"], same_position),
            xytext=(3, 0),
            textcoords="offset points",
            ha="left",
            va="center",
            fontsize=7,
            color=GTP_COLOR,
            clip_on=False,
        )
        axis.annotate(
            f"{row['sonnet']:.0%}",
            xy=(row["sonnet"], sonnet_position),
            xytext=(3, 0),
            textcoords="offset points",
            ha="left",
            va="center",
            fontsize=7,
            color="#8c3d70",
            clip_on=False,
        )
        axis.annotate(
            f"ties {row['tie_share']:.0%}",
            xy=(1.0, sonnet_position),
            xytext=(4, 0),
            textcoords="offset points",
            ha="left",
            va="center",
            fontsize=7,
            color="#8c3d70",
            clip_on=False,
        )
    axis.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2, frameon=False, fontsize=7)
    figure.subplots_adjust(left=0.34, right=0.85, top=0.91, bottom=0.23)
    figure.savefig(output, format="pdf")
    plt.close(figure)


PROCESS_LABELS = {
    "planning": "P",
    "translating": "T",
    "reviewing": "R",
}
PROCESS_SEQUENCE_CONDITIONS = (("A4", "Agentic CogWriter"), ("A6", "Fixed-order"))
PROCESS_STATES = ("planning", "translating", "reviewing", "END")
PROCESS_AXIS_LABELS = ("P", "T", "R", "E")
ACL_TEXTWIDTH_IN = 16 / 2.54
PROCESS_SEQUENCE_A_WIDTH_IN = 0.60 * ACL_TEXTWIDTH_IN
PROCESS_SEQUENCE_A_HEIGHT_IN = 2.2
PROCESS_SEQUENCE_MATRIX_WIDTH_IN = 0.37 * ACL_TEXTWIDTH_IN
PROCESS_SEQUENCE_MATRIX_HEIGHT_IN = 0.94


def process_sequence_values(report: dict[str, Any]) -> dict[str, Any]:
    conditions = require_mapping(report, "conditions", "process-sequences JSON")
    values = {}
    for condition, label in PROCESS_SEQUENCE_CONDITIONS:
        condition_data = require_mapping(conditions, condition, f"process-sequences JSON conditions.{condition}")
        summary = require_mapping(condition_data, "summary", f"process-sequences JSON conditions.{condition}")
        sequences = require_value(summary, "sequence_distribution", f"process-sequences JSON conditions.{condition}.summary")
        if not isinstance(sequences, list) or len(sequences) < 5:
            raise ValueError(f"process-sequences JSON conditions.{condition}.summary.sequence_distribution must have five rows")
        ranked = sorted(
            enumerate(sequences),
            key=lambda item: require_int(
                item[1],
                "count",
                f"process-sequences JSON conditions.{condition}.summary.sequence_distribution[{item[0]}]",
            ),
            reverse=True,
        )[:5]
        top = []
        for index, item in ranked:
            source = f"process-sequences JSON conditions.{condition}.summary.sequence_distribution[{index}]"
            sequence = require_value(item, "sequence", source)
            if not isinstance(sequence, list) or not sequence or not all(isinstance(name, str) for name in sequence):
                raise ValueError(f"{source}.sequence is not a non-empty string list")
            total = require_int(item, "total", source)
            count = require_int(item, "count", source)
            rate = require_number(item, "rate", source)
            if total <= 0 or count < 0 or not 0.0 <= rate <= 1.0:
                raise ValueError(f"{source} contains invalid count, total, or rate")
            top.append({"label": " → ".join(PROCESS_LABELS.get(name, name) for name in sequence), "count": count, "rate": rate})
        matrix = require_mapping(summary, "transition_matrix", f"process-sequences JSON conditions.{condition}.summary")
        transitions = []
        for state in PROCESS_STATES[:-1]:
            row = require_mapping(matrix, state, f"process-sequences JSON conditions.{condition}.summary.transition_matrix")
            transitions.append([
                require_int(row, target, f"process-sequences JSON conditions.{condition}.summary.transition_matrix.{state}")
                for target in PROCESS_STATES
            ])
        values[condition] = {"label": label, "sequences": top, "matrix": transitions}
    return values


def save_process_sequences_a(report: dict[str, Any], output: Path) -> None:
    values = process_sequence_values(report)
    # Saved at exactly the placed size so 8 pt text prints at 8 pt.
    figure, sequence_axis = plt.subplots(
        figsize=(PROCESS_SEQUENCE_A_WIDTH_IN, PROCESS_SEQUENCE_A_HEIGHT_IN), layout="constrained"
    )
    row_positions = []
    labels = []
    counts = []
    shares = []
    colors = ("#0072B2", "#D55E00")
    for condition_index, (condition, _) in enumerate(PROCESS_SEQUENCE_CONDITIONS):
        for row_index, row in enumerate(values[condition]["sequences"]):
            row_positions.append(9 - (condition_index * 5 + row_index))
            labels.append(row["label"])
            counts.append(row["count"])
            shares.append(row["rate"])
    sequence_axis.barh(row_positions, counts, color=[colors[index // 5] for index in range(10)], height=0.72, alpha=0.86)
    max_count = max(counts)
    for position, count, share in zip(row_positions, counts, shares):
        sequence_axis.text(count + max_count * 0.012, position, f"{count} ({share:.1%})", va="center", ha="left", fontsize=8)
    sequence_axis.set_yticks(row_positions)
    sequence_axis.set_yticklabels(labels, fontsize=8)
    sequence_axis.set_xlim(0, max_count * 1.42)
    sequence_axis.set_xlabel("Observed runs", fontsize=8)
    sequence_axis.grid(axis="x", color="#dddddd", linewidth=0.5)
    sequence_axis.set_axisbelow(True)
    sequence_axis.tick_params(axis="both", labelsize=8)
    sequence_axis.axhline(4.5, color="#888888", linewidth=0.7)
    sequence_axis.legend(
        handles=[
            Patch(facecolor=colors[0], label="Agentic CogWriter"),
            Patch(facecolor=colors[1], label="Fixed-order"),
        ],
        loc="lower center",
        bbox_to_anchor=(0.5, 1.01),
        ncol=2,
        frameon=False,
        fontsize=8,
        handlelength=1.1,
        handletextpad=0.4,
        columnspacing=1.0,
        borderaxespad=0.0,
    )
    sequence_axis.text(
        0.98,
        0.04,
        "P = Planning\nT = Translating\nR = Reviewing",
        transform=sequence_axis.transAxes,
        ha="right",
        multialignment="left",
        va="bottom",
        fontsize=8,
        bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5},
    )
    figure.savefig(output, format="pdf")
    plt.close(figure)


def save_process_sequence_matrix(values: dict[str, Any], condition: str, output: Path, matrix_max: int) -> None:
    matrix = values[condition]["matrix"]
    figure, axis = plt.subplots(
        figsize=(PROCESS_SEQUENCE_MATRIX_WIDTH_IN, PROCESS_SEQUENCE_MATRIX_HEIGHT_IN), layout="constrained"
    )
    axis.imshow(matrix, cmap="Blues", aspect="auto", vmin=0, vmax=matrix_max)
    axis.grid(False)
    for row_index, row in enumerate(matrix):
        for column_index, count in enumerate(row):
            axis.text(column_index, row_index, str(count), ha="center", va="center", fontsize=8, color="white" if count > matrix_max * 0.52 else "#222222")
    axis.set_xticks(range(len(PROCESS_STATES)), PROCESS_AXIS_LABELS, rotation=0, fontsize=8)
    axis.set_yticks(range(3), PROCESS_AXIS_LABELS[:3], fontsize=8)
    axis.set_xlabel("To", fontsize=8)
    axis.set_ylabel("From", fontsize=8)
    axis.tick_params(axis="both", labelsize=8, length=0)
    for spine in axis.spines.values():
        spine.set_visible(False)
    figure.savefig(output, format="pdf")
    plt.close(figure)


def save_process_sequences_b(report: dict[str, Any], output: Path) -> None:
    values = process_sequence_values(report)
    matrix_max = max(max(row) for condition in PROCESS_SEQUENCE_CONDITIONS for row in values[condition[0]]["matrix"])
    save_process_sequence_matrix(values, "A4", output, matrix_max)


def save_process_sequences_c(report: dict[str, Any], output: Path) -> None:
    values = process_sequence_values(report)
    matrix_max = max(max(row) for condition in PROCESS_SEQUENCE_CONDITIONS for row in values[condition[0]]["matrix"])
    save_process_sequence_matrix(values, "A6", output, matrix_max)


def generate(aggregations: list[dict[str, Any]], lengths: list[dict[str, Any]], cross_family: dict[str, Any], process_sequences: dict[str, Any], output_dir: Path) -> list[Path]:
    if len(aggregations) != 3:
        raise ValueError("exactly three aggregation JSON files are required")
    if len(lengths) != 3:
        raise ValueError("exactly three length-control JSON files are required")
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = [
        output_dir / "confirmatory-forest.pdf",
        output_dir / "length-control.pdf",
        output_dir / "cross-family.pdf",
        output_dir / "process-sequences-a.pdf",
        output_dir / "process-sequences-b.pdf",
        output_dir / "process-sequences-c.pdf",
    ]
    rows = forest_rows(aggregations)
    save_forest(rows, outputs[0])
    for run_index, report in enumerate(lengths, 1):
        length_values(report, f"replication {run_index}")
    save_length(lengths[0], outputs[1])
    save_cross_family(cross_family_values(aggregations[0], cross_family), outputs[2])
    save_process_sequences_a(process_sequences, outputs[3])
    save_process_sequences_b(process_sequences, outputs[4])
    save_process_sequences_c(process_sequences, outputs[5])
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aggregations", nargs=3, type=Path, required=True)
    parser.add_argument("--length-control", nargs=3, type=Path, required=True)
    parser.add_argument("--cross-family", type=Path, required=True)
    parser.add_argument("--process-sequences", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "fig")
    args = parser.parse_args()
    aggregations = [read_json(path, f"aggregation replication {index}") for index, path in enumerate(args.aggregations, 1)]
    lengths = [read_json(path, f"length-control replication {index}") for index, path in enumerate(args.length_control, 1)]
    cross_family = read_json(args.cross_family, "cross-family")
    process_sequences = read_json(args.process_sequences, "process-sequences")
    for path in generate(aggregations, lengths, cross_family, process_sequences, args.output_dir):
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
