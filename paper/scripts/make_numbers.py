#!/usr/bin/env python3
"""Emit manuscript number macros from aggregation JSON files."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import json
import math
import re
import statistics
import sys
from pathlib import Path
from typing import Any, Iterable


CONDITION_WORDS = {
    "A1": "Aone",
    "A2": "Atwo",
    "A3": "Athree",
    "A4": "Afour",
    "A5": "Afive",
    "A6": "Asix",
    "A7": "Aseven",
}

BENCHMARK_WORDS = {
    "DoLoMiTes": "DoLo",
    "HelloBench": "Hello",
    "WritingBench": "Writing",
}

HABERMAS_SUMMARY = {
    "A1": ("10/10", "0", "0", "0", "0/0", "0.1258"),
    "A2": ("10/10", "0", "0", "0", "0/0", "0.1654"),
    "A3": ("9/10", "0", "0", "0", "0/0", "-0.2169"),
    "A4": ("10/10", "39", "37", "0", "15/0", "-0.0222"),
    "A5": ("10/10", "0", "0", "0", "0/0", "0.0529"),
    "A6": ("10/10", "12", "27", "0", "11/0", "0.1257"),
    "B1": ("10/10", "0", "0", "0", "0/0", "-0.1605"),
    "B2": ("9/10", "0", "0", "0", "0/0", "-0.1023"),
}

PROCESS_CONDITIONS = tuple(CONDITION_WORDS)
PROCESS_FIELDS = {
    "goal_created": "GoalCreated",
    "goal_developed": "GoalDeveloped",
    "goal_regenerated": "GoalRegenerated",
    "ledger_entries": "LedgerEntries",
    "ledger_no_proposal": "LedgerNoProposal",
    "ledger_with_proposal": "LedgerWithProposal",
    "median_output": "MedianOutput",
    "spawns": "Spawns",
    "output_tokens": "OutputTokens",
    "input_tokens": "InputTokens",
    "mean_seconds": "MeanSeconds",
}
PROCESS_SOURCE_FIELDS = {
    "goal_created": "goal_created",
    "goal_developed": "goal_developed",
    "goal_regenerated": "goal_regenerated",
    "ledger_entries": "ledger_entries_contract",
    "ledger_no_proposal": "ledger_entries_no_proposal",
    "ledger_with_proposal": "ledger_entries_with_proposal",
    "median_output": "median_output_units",
    "spawns": "mean_spawns_per_attempted_run",
    "output_tokens": "mean_output_plus_reasoning_tokens",
    "input_tokens": "mean_uncached_input_tokens",
    "mean_seconds": "mean_wall_clock_seconds_completed",
}
PROCESS_FIELD_DECIMALS = {
    "goal_created": 1,
    "goal_developed": 1,
    "goal_regenerated": 1,
    "ledger_entries": 1,
    "ledger_no_proposal": 1,
    "ledger_with_proposal": 1,
    "median_output": 0,
    "spawns": 2,
    "output_tokens": 0,
    "input_tokens": 0,
    "mean_seconds": 0,
}
PROCESS_GOAL_FIELDS = ("goal_created", "goal_developed", "goal_regenerated")
PROCESS_GENERIC_FIELDS = (
    "goal_created",
    "goal_developed",
    "goal_regenerated",
    "median_output",
    "spawns",
    "output_tokens",
    "input_tokens",
    "mean_seconds",
)
PROCESS_TRACE_CONDITIONS = ("A4", "A6")
PROCESS_COMPOSITE_SUFFIXES = {"Goals", "MedianSeconds"}
PROCESS_SEQUENCE_CONDITIONS = ("A4", "A6")
PROCESS_SEQUENCE_SUFFIXES = {
    "RunCount",
    "SingleCycleRate",
    "CycleCompliantRate",
    "CompliantOnePassRate",
    "CompliantTwoThreePassRate",
    "ReviewingToTranslatingRate",
    "ReviewingToPlanningRate",
    "RegenerationRuns",
    "LeadingReconstruction",
    "ExactCycleFixedOrderWinRate",
    "NonExactFixedOrderWinRate",
    "FixedOrderCycleSplitP",
    "ExactCycleSingleWriterWinRate",
    "NonExactSingleWriterWinRate",
    "SingleWriterCycleSplitP",
}

NUMBER_WORDS = {
    "A1": "One",
    "A2": "Two",
    "A3": "Three",
    "A4": "Four",
    "A5": "Five",
    "A6": "Six",
    "A7": "Seven",
}

RUN_WORDS = {1: "One", 2: "Two", 3: "Three"}

TOKEN_WORDS = {
    "winrate": "WinRate",
    "pooledwinrate": "PooledWinRate",
    "pooledwinratelower": "PooledWinRateLower",
    "pooledwinrateupper": "PooledWinRateUpper",
    "pooledwinrateinterval": "PooledWinRateInterval",
    "medianoutputunits": "MedianOutputUnits",
    "meanspawns": "MeanSpawns",
    "goalevents": "GoalEvents",
    "generationcostperrun": "GenerationCostPerRun",
}

TOKEN_METRICS = {
    "input": "InputTokens",
    "output": "OutputTokens",
}

ROBUSTNESS_CONTRASTS = {
    "A4:A1": "FullSinglePass",
    "A4:A3": "FullTaskPlanning",
    "A4:A5": "FullNoGoals",
}
ROBUSTNESS_BENCHMARKS = {
    "DoLoMiTes": "DoLo",
    "HelloBench": "Hello",
    "WritingBench": "Writing",
}
LENGTH_BANDS = {"5_percent": "Five", "10_percent": "Ten"}
LENGTH_RATIO_BINS = {
    "1.00-1.05": "OneToOneZeroFive",
    "1.05-1.10": "OneZeroFiveToOneTen",
    "1.10-1.25": "OneTenToOneTwentyFive",
    "1.25-1.50": "OneTwentyFiveToOneFifty",
    "1.50-2.00": "OneFiftyToTwo",
    "2.00+": "TwoPlus",
}
LENGTH_SOURCE_FIELDS = {
    "pair_count": "pair_count",
    "longer_side": "all_pairs_longer_side",
    "matched": "length_matched",
    "ratio_bins": "ratio_bins",
    "single_writer": "single_writer_at_least_10_percent_shorter",
}
CROSS_FAMILY_SOURCE_FIELDS = {
    "contrasts": "contrasts",
    "pooled": "pooled",
    "provenance": "provenance",
    "note": "note",
}


def _word(value: object) -> str:
    text = str(value)
    if text in CONDITION_WORDS:
        return CONDITION_WORDS[text]
    if text in TOKEN_WORDS:
        return TOKEN_WORDS[text]
    if text.isalpha() and any(character.isupper() for character in text[1:]):
        return text
    text = re.sub(r"[^A-Za-z0-9]+", " ", text).title().replace(" ", "")
    return text or "Value"


def _schema_name(kind: str, benchmark: str, *conditions: str) -> str:
    benchmark_word = BENCHMARK_WORDS.get(benchmark, _word(benchmark))
    condition_words = [CONDITION_WORDS.get(condition, _word(condition)) for condition in conditions]
    number_words = [NUMBER_WORDS.get(condition, _word(condition)) for condition in conditions]
    if kind in {"point", "native", "completion"}:
        return "\\" + benchmark_word + condition_words[0] + kind.capitalize()
    if kind == "wlt":
        return "\\" + benchmark_word + "".join(number_words) + "WLT"
    if kind == "rate":
        return "\\" + benchmark_word + "".join(number_words) + "Rate"
    if kind == "rate_mean":
        return "\\" + benchmark_word + "".join(number_words) + "RateMean"
    if kind == "rate_sd":
        return "\\" + benchmark_word + "".join(number_words) + "RateSD"
    if kind == "sig":
        return "\\" + benchmark_word + "".join(number_words) + "Sig"
    if kind == "table_win":
        return "\\" + benchmark_word + "".join(number_words) + "Win"
    raise ValueError(f"unknown schema macro kind: {kind}")


def _pooled_name(kind: str, *conditions: str) -> str:
    number_words = "".join(NUMBER_WORDS.get(condition, _word(condition)) for condition in conditions)
    suffix = {
        "wlt": "WLT",
        "rate": "Rate",
        "interval": "Interval",
        "table_rate": "TableRate",
        "table_interval": "TableInterval",
        "rate_mean": "RateMean",
        "rate_sd": "RateSD",
    }[kind]
    return "\\Pooled" + number_words + suffix


def _record_schema_name(kind: str, benchmark: str, *conditions: str) -> str:
    return "\\Record" + _schema_name(kind, benchmark, *conditions)[1:]


def _record_pooled_name(kind: str, *conditions: str) -> str:
    return "\\Record" + _pooled_name(kind, *conditions)[1:]


def _run_rate_name(benchmark: str, run_index: int, *conditions: str) -> str:
    return _schema_name("rate", benchmark, *conditions) + "Run" + RUN_WORDS[run_index]


def _record_run_rate_name(benchmark: str, run_index: int, *conditions: str) -> str:
    return _record_schema_name("rate", benchmark, *conditions) + "Run" + RUN_WORDS[run_index]


def _pooled_holm_cells_name(run_index: int, *conditions: str) -> str:
    number_words = "".join(NUMBER_WORDS.get(condition, _word(condition)) for condition in conditions)
    return "\\Pooled" + number_words + "HolmRun" + RUN_WORDS[run_index] + "Cells"


def _record_pooled_holm_cells_name(run_index: int, *conditions: str) -> str:
    return "\\RecordPooled" + "".join(NUMBER_WORDS.get(condition, _word(condition)) for condition in conditions) + "HolmRun" + RUN_WORDS[run_index] + "Cells"


def _pooled_holm_cells_total_name(*conditions: str) -> str:
    return "\\Pooled" + "".join(NUMBER_WORDS.get(condition, _word(condition)) for condition in conditions) + "HolmCellsTotal"


def _record_pooled_holm_cells_total_name(*conditions: str) -> str:
    return "\\RecordPooled" + "".join(NUMBER_WORDS.get(condition, _word(condition)) for condition in conditions) + "HolmCellsTotal"


def _missing_pairs_name(run_index: int) -> str:
    return "\\ReplicationRun" + RUN_WORDS[run_index] + "MissingPairs"


def _condition_name(condition: str, suffix: str) -> str:
    return "\\" + CONDITION_WORDS[condition] + suffix


_DURATION_KEYS = {"duration", "duration_seconds", "elapsed", "elapsed_seconds"}


def _attempt_durations(value: Any) -> list[float]:
    if isinstance(value, dict):
        durations = []
        for key, child in value.items():
            if key in _DURATION_KEYS:
                duration = _float(child)
                if duration is not None and duration >= 0:
                    durations.append(duration)
            elif isinstance(child, (dict, list)):
                durations.extend(_attempt_durations(child))
        return durations
    if isinstance(value, list):
        durations = []
        for child in value:
            durations.extend(_attempt_durations(child))
        return durations
    return []


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def elapsed_seconds(manifest: dict[str, Any]) -> float | None:
    recorded = _attempt_durations(manifest.get("attempts"))
    if recorded:
        return sum(recorded)
    started = _timestamp(manifest.get("started_at"))
    updated = _timestamp(manifest.get("updated_at"))
    if started is None or updated is None:
        return None
    elapsed = (updated - started).total_seconds()
    return elapsed if elapsed >= 0 else None


def timing_summaries(roots: list[Path] | tuple[Path, ...]) -> dict[str, tuple[int, int]]:
    project_root = Path(__file__).resolve().parents[2]
    experiments_src = project_root / "experiments" / "src"
    if str(experiments_src) not in sys.path:
        sys.path.insert(0, str(experiments_src))
    from agentic_cogwriter.analysis.common import select_canonical_runs

    values: dict[str, list[float]] = {condition: [] for condition in CONDITION_WORDS}
    for record in select_canonical_runs(list(roots)):
        if record.status != "completed" or record.condition not in values:
            continue
        seconds = elapsed_seconds(record.manifest)
        if seconds is not None:
            values[record.condition].append(seconds)
    return {
        condition: (round(statistics.mean(seconds)), round(statistics.median(seconds)))
        for condition, seconds in values.items()
        if seconds
    }


def macro_name(kind: str, *parts: object) -> str:
    """Return a direct, alphabetic LaTeX command name."""

    if kind in {"point", "native", "completion", "wlt", "rate", "rate_mean", "rate_sd", "sig", "table_win"}:
        return _schema_name(kind, str(parts[0]), *(str(part) for part in parts[1:]))
    prefix = _word(kind)
    prefix = prefix[:1].lower() + prefix[1:]
    return "\\" + prefix + "".join(_word(part) for part in parts)


def sign_test_pvalue(wins: int, losses: int) -> float:
    """Exact two-sided sign-test p-value, excluding ties."""

    n = wins + losses
    if n == 0:
        return 1.0
    lower = min(wins, losses)
    tail = sum(math.comb(n, k) for k in range(lower + 1)) / (2**n)
    return min(1.0, 2.0 * tail)


def exact_sign_test_power(n: int, true_win_rate: float, alpha: float = 0.05 / 24) -> float:
    """Return exact two-sided sign-test power at a true win rate."""

    if n < 1:
        raise ValueError("n must be positive")
    if not 0.0 <= true_win_rate <= 1.0:
        raise ValueError("true_win_rate must be between zero and one")
    return sum(
        math.comb(n, wins)
        * true_win_rate**wins
        * (1.0 - true_win_rate) ** (n - wins)
        for wins in range(n + 1)
        if sign_test_pvalue(wins, n - wins) <= alpha
    )


def minimum_true_win_rate_for_power(
    n: int,
    target_power: float = 0.8,
    alpha: float = 0.05 / 24,
) -> float:
    """Invert exact two-sided sign-test power for the upper alternative."""

    if not 0.0 < target_power < 1.0:
        raise ValueError("target_power must be between zero and one")
    lower, upper = 0.5, 1.0
    for _ in range(80):
        midpoint = (lower + upper) / 2.0
        if exact_sign_test_power(n, midpoint, alpha) < target_power:
            lower = midpoint
        else:
            upper = midpoint
    return upper


def holm_adjust(pvalues: Iterable[float]) -> list[float]:
    """Return Holm-adjusted p-values in input order."""

    values = list(pvalues)
    order = sorted(range(len(values)), key=lambda i: values[i])
    adjusted = [1.0] * len(values)
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, values[index] * (len(values) - rank)))
        adjusted[index] = running
    return adjusted


def _rows(data: dict[str, Any], section: str) -> list[dict[str, Any]]:
    value = data.get(section, {})
    rows = value.get("rows", []) if isinstance(value, dict) else []
    return [row for row in rows if isinstance(row, dict)]


def _row(data: dict[str, Any], section: str, benchmark: str, condition: str) -> dict[str, Any]:
    for row in _rows(data, section):
        if row.get("benchmark") == benchmark and row.get("condition") == condition:
            return row
    return {}


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _recursive_value(value: Any, names: set[str]) -> Any:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in names:
                return child
            found = _recursive_value(child, names)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _recursive_value(child, names)
            if found is not None:
                return found
    return None


def _metric(row: dict[str, Any], names: set[str]) -> Any:
    return _recursive_value(row, names)


def _format(value: Any, decimals: int = 3) -> str:
    if value is None:
        return r"\textemdash"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int):
        return str(value)
    number = _float(value)
    if number is None:
        return str(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.{decimals}f}".rstrip("0").rstrip(".")


def _percent(value: float | None) -> str:
    if value is None:
        return r"\textemdash"
    percent = f"{100 * value:.1f}".rstrip("0").rstrip(".")
    return percent + r"\%"


def _wilson_interval(wins: int, losses: int) -> tuple[float | None, float | None, float | None]:
    n = wins + losses
    if n == 0:
        return None, None, None
    p = wins / n
    z = 1.96
    denominator = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denominator
    half_width = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denominator
    return p, max(0.0, center - half_width), min(1.0, center + half_width)


def _estimand_metrics(
    data: dict[str, Any],
    benchmark: str,
    contrast: tuple[str, str],
    estimand: str,
) -> dict[str, Any] | None:
    left, right = contrast
    section = {
        "collapsed": "prompt_collapsed_across_judges",
        "record": "record_pooled",
    }[estimand]
    value = (
        data.get("pairwise", {})
        .get("benchmarks", {})
        .get(benchmark, {})
        .get("platforms", {})
        .get("codex", {})
        .get(section, {})
        .get(f"{left}:{right}")
    )
    if not isinstance(value, dict):
        return None
    try:
        metrics = {name: int(value[name]) for name in ("wins", "losses", "ties")}
    except (KeyError, TypeError, ValueError):
        return None
    metrics.update(
        {
            name: value[name]
            for name in (
                "prompt_total",
                "presentation_disagreements",
                "judge_disagreements",
                "n_non_tie",
                "win_rate",
                "p_raw",
                "p_holm",
                "wilson_low",
                "wilson_high",
            )
            if name in value
        }
    )
    if "win_rate" not in metrics:
        metrics["win_rate"] = _wilson_interval(metrics["wins"], metrics["losses"])[0]
    if "wilson_low" not in metrics or "wilson_high" not in metrics:
        _, low, high = _wilson_interval(metrics["wins"], metrics["losses"])
        metrics.setdefault("wilson_low", low)
        metrics.setdefault("wilson_high", high)
    return metrics


def _oriented_metrics(
    data: dict[str, Any],
    benchmark: str,
    contrast: tuple[str, str],
    estimand: str,
) -> dict[str, Any] | None:
    direct = _estimand_metrics(data, benchmark, contrast, estimand)
    if direct is not None:
        return direct
    reverse = _estimand_metrics(data, benchmark, _reversed_contrast(contrast), estimand)
    if reverse is None:
        return None
    oriented = dict(reverse)
    oriented["wins"], oriented["losses"] = reverse["losses"], reverse["wins"]
    if reverse.get("win_rate") is not None:
        oriented["win_rate"] = 1 - float(reverse["win_rate"])
    if reverse.get("wilson_low") is not None and reverse.get("wilson_high") is not None:
        oriented["wilson_low"] = 1 - float(reverse["wilson_high"])
        oriented["wilson_high"] = 1 - float(reverse["wilson_low"])
    return oriented


def _sum_metrics(
    data: dict[str, Any],
    benchmarks: Iterable[str],
    contrast: tuple[str, str],
    estimand: str,
) -> dict[str, Any] | None:
    total = {name: 0 for name in ("wins", "losses", "ties")}
    present = False
    for benchmark in benchmarks:
        stats = _oriented_metrics(data, benchmark, contrast, estimand)
        if stats is None:
            continue
        present = True
        for name in total:
            total[name] += stats[name]
    if not present:
        return None
    rate, low, high = _wilson_interval(total["wins"], total["losses"])
    total.update(win_rate=rate, wilson_low=low, wilson_high=high)
    return total


def _estimand_source(benchmark: str, contrast: tuple[str, str], estimand: str) -> str:
    left, right = contrast
    return f"pairwise.benchmarks.{benchmark}.platforms.codex.{_estimand_section(estimand)}.{left}:{right}"


def _estimand_section(estimand: str) -> str:
    return {
        "collapsed": "prompt_collapsed_across_judges",
        "record": "record_pooled",
    }[estimand]


def _estimand_schema_name(estimand: str, kind: str, benchmark: str, *conditions: str) -> str:
    return (
        _schema_name(kind, benchmark, *conditions)
        if estimand == "collapsed"
        else _record_schema_name(kind, benchmark, *conditions)
    )


def _estimand_pooled_name(estimand: str, kind: str, *conditions: str) -> str:
    return _pooled_name(kind, *conditions) if estimand == "collapsed" else _record_pooled_name(kind, *conditions)


def _generation_tokens_per_run(
    data: dict[str, Any], condition: str, token_name: str
) -> float | None:
    total_tokens = 0.0
    total_runs = 0.0
    for row in data.get("cost", {}).get("generation", []):
        if not isinstance(row, dict) or row.get("condition") != condition:
            continue
        tokens = row.get("tokens", {})
        if not isinstance(tokens, dict):
            continue
        token_count = _float(tokens.get(token_name))
        run_count = _float(row.get("run_count"))
        if token_count is None or run_count is None or run_count <= 0:
            continue
        total_tokens += token_count
        total_runs += run_count
    return total_tokens / total_runs if total_runs else None


def _generation_cost_per_run(
    data: dict[str, Any], condition: str, prices: dict[str, float]
) -> float | None:
    total_cost = 0.0
    total_runs = 0.0
    for row in data.get("cost", {}).get("generation", []):
        if not isinstance(row, dict) or row.get("condition") != condition:
            continue
        tokens = row.get("tokens", {})
        run_count = _float(row.get("run_count"))
        if not isinstance(tokens, dict) or run_count is None or run_count <= 0:
            continue
        total_cost += sum(
            (_float(tokens.get(name)) or 0.0) * prices[name]
            for name in ("input", "cached_input", "output")
        ) / 1_000_000
        total_runs += run_count
    return total_cost / total_runs if total_runs else None


def _public_prices(path: Path | None) -> dict[str, float] | None:
    if path is None:
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("public prices must be a JSON object")
    prices = {}
    for name in ("input", "cached_input", "output"):
        price = _float(value.get(name))
        if price is None or price < 0:
            raise ValueError(f"public prices must define non-negative {name}")
        prices[name] = price
    return prices


def _format_tokens(value: float | None) -> str | None:
    return f"{round(value):,}" if value is not None else None


def _format_process(value: Any, decimals: int = 1) -> str:
    number = _float(value)
    if number is None:
        raise ValueError(f"process summary value is not numeric: {value!r}")
    if decimals == 0:
        return f"{number:,.0f}"
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.{decimals}f}".rstrip("0").rstrip(".")


def _percent_fixed(value: Any, decimals: int) -> str:
    number = _float(value)
    if number is None:
        raise ValueError(f"percentage value is not numeric: {value!r}")
    return f"{100 * number:.{decimals}f}\\%"


def _cross_family_percent(value: Any, decimals: int = 1) -> str:
    number = _float(value)
    if number is None:
        raise ValueError(f"percentage value is not numeric: {value!r}")
    rounded = Decimal(str(100 * number)).quantize(
        Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP
    )
    return f"{rounded:.{decimals}f}\\%"


def _pvalue(value: Any) -> str:
    number = _float(value)
    if number is None or number < 0:
        raise ValueError(f"p-value is not a non-negative number: {value!r}")
    if number >= 0.001:
        return f"{number:.4f}".rstrip("0").rstrip(".")
    mantissa, exponent = f"{number:.2e}".split("e")
    return f"{float(mantissa):.2f}\\times 10^{{{int(exponent)}}}"


def _pvalue_two_decimals(value: Any) -> str:
    number = _float(value)
    if number is None or number < 0:
        raise ValueError(f"p-value is not a non-negative number: {value!r}")
    rounded = Decimal(str(number)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{rounded:.2f}"


def _required_mapping(data: dict[str, Any], key: str, source: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{source} is missing mapping field {key}")
    return value


def _required_value(data: dict[str, Any], key: str, source: str) -> Any:
    if key not in data:
        raise ValueError(f"{source} is missing field {key}")
    return data[key]


def _required_int(data: dict[str, Any], key: str, source: str) -> int:
    value = _required_value(data, key, source)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{source}.{key} is not an integer")
    return value


def _required_number(data: dict[str, Any], key: str, source: str) -> float:
    value = _float(_required_value(data, key, source))
    if value is None:
        raise ValueError(f"{source}.{key} is not numeric")
    return value


def _validate_outcome(data: dict[str, Any], source: str) -> None:
    for key in ("wins", "losses", "ties", "n_non_tie", "pairs", "selected_pairs"):
        _required_int(data, key, source)
    for key in ("win_rate", "wilson_low", "wilson_high", "sign_test_p"):
        _required_number(data, key, source)


def _validate_rate_block(data: dict[str, Any], source: str) -> None:
    for key in ("numerator", "denominator"):
        _required_int(data, key, source)
    for key in ("rate", "wilson_low", "wilson_high"):
        _required_number(data, key, source)


def _validate_count_block(data: dict[str, Any], source: str) -> None:
    for key in ("numerator", "denominator"):
        _required_int(data, key, source)


def _validate_length_report(report: dict[str, Any], run_label: str) -> dict[str, Any]:
    source = f"length-control JSON {run_label}"
    _required_int(report, LENGTH_SOURCE_FIELDS["pair_count"], source)
    longer = _required_mapping(report, LENGTH_SOURCE_FIELDS["longer_side"], source)
    _validate_outcome(longer, f"{source}.{LENGTH_SOURCE_FIELDS['longer_side']}")
    matched = _required_mapping(report, LENGTH_SOURCE_FIELDS["matched"], source)
    for band in LENGTH_BANDS:
        band_values = matched.get(band)
        if not isinstance(band_values, dict):
            raise ValueError(f"{source}.{LENGTH_SOURCE_FIELDS['matched']} is missing {band}")
        for contrast in ROBUSTNESS_CONTRASTS:
            stats = band_values.get(contrast)
            if not isinstance(stats, dict):
                raise ValueError(f"{source}.{band} is missing {contrast}")
            _validate_outcome(stats, f"{source}.{LENGTH_SOURCE_FIELDS['matched']}.{band}.{contrast}")
    ratio_bins = _required_mapping(report, LENGTH_SOURCE_FIELDS["ratio_bins"], source)
    for ratio_bin in LENGTH_RATIO_BINS:
        stats = ratio_bins.get(ratio_bin)
        if not isinstance(stats, dict):
            raise ValueError(f"{source}.{LENGTH_SOURCE_FIELDS['ratio_bins']} is missing {ratio_bin}")
        _validate_outcome(stats, f"{source}.{LENGTH_SOURCE_FIELDS['ratio_bins']}.{ratio_bin}")
    single_writer = _required_mapping(report, LENGTH_SOURCE_FIELDS["single_writer"], source)
    _validate_outcome(single_writer, f"{source}.{LENGTH_SOURCE_FIELDS['single_writer']}")
    return report


def _validate_cross_family(report: dict[str, Any]) -> dict[str, Any]:
    source = "cross-family JSON"
    contrasts = _required_mapping(report, CROSS_FAMILY_SOURCE_FIELDS["contrasts"], source)
    for contrast in ROBUSTNESS_CONTRASTS:
        pooled = contrasts.get(contrast)
        if not isinstance(pooled, dict):
            raise ValueError(f"{source}.contrasts is missing {contrast}")
        _validate_cross_result(pooled, f"{source}.contrasts.{contrast}")
        benchmarks = _required_mapping(pooled, "benchmarks", f"{source}.contrasts.{contrast}")
        for benchmark in ROBUSTNESS_BENCHMARKS:
            result = benchmarks.get(benchmark)
            if not isinstance(result, dict):
                raise ValueError(f"{source}.{contrast}.benchmarks is missing {benchmark}")
            _validate_cross_result(result, f"{source}.{contrast}.{benchmark}")
    pooled = _required_mapping(report, CROSS_FAMILY_SOURCE_FIELDS["pooled"], source)
    _validate_cross_result(pooled, f"{source}.{CROSS_FAMILY_SOURCE_FIELDS['pooled']}")
    provenance = _required_mapping(report, CROSS_FAMILY_SOURCE_FIELDS["provenance"], source)
    for key in ("cross_family_judge_id", "reference_judge_id", "effort"):
        value = _required_value(provenance, key, f"{source}.provenance")
        if not isinstance(value, str) or not value:
            raise ValueError(f"{source}.provenance.{key} is not a non-empty string")
    _required_int(provenance, "seed", f"{source}.provenance")
    note = _required_value(report, CROSS_FAMILY_SOURCE_FIELDS["note"], source)
    if not isinstance(note, str) or "No multiplicity correction" not in note:
        raise ValueError(f"{source}.note does not record the no-correction rule")
    return report


def _validate_cross_result(data: dict[str, Any], source: str) -> None:
    for key in ("n", "wins", "losses", "ties", "direction_conflicts"):
        _required_int(data, key, source)
    _validate_rate_block(_required_mapping(data, "commit_rate", source), f"{source}.commit_rate")
    _validate_rate_block(_required_mapping(data, "win_rate", source), f"{source}.win_rate")
    _validate_count_block(
        _required_mapping(data, "prompt_collapsed_agreement", source),
        f"{source}.prompt_collapsed_agreement",
    )
    _validate_count_block(
        _required_mapping(data, "presentation_agreement", source),
        f"{source}.presentation_agreement",
    )
    _required_number(data, "sign_test_p", source)


def _validate_process_sequence_rate(data: dict[str, Any], source: str) -> None:
    for key in ("count", "total"):
        _required_int(data, key, source)
    rate = _required_number(data, "rate", source)
    if data["count"] < 0 or data["total"] <= 0 or not 0.0 <= rate <= 1.0:
        raise ValueError(f"{source} contains an invalid count, total, or rate")


def _validate_process_sequences(report: dict[str, Any]) -> dict[str, Any]:
    source = "process-sequences JSON"
    conditions = _required_mapping(report, "conditions", source)
    for condition in PROCESS_SEQUENCE_CONDITIONS:
        condition_data = _required_mapping(conditions, condition, f"{source}.conditions")
        summary = _required_mapping(condition_data, "summary", f"{source}.conditions.{condition}")
        run_count = _required_int(summary, "run_count", f"{source}.conditions.{condition}.summary")
        if run_count <= 0:
            raise ValueError(f"{source}.conditions.{condition}.summary.run_count must be positive")
        for field in ("single_cycle_exact", "cycle_compliance"):
            _validate_process_sequence_rate(
                _required_mapping(summary, field, f"{source}.conditions.{condition}.summary"),
                f"{source}.conditions.{condition}.summary.{field}",
            )
        passes = summary.get("cycle_pass_distribution")
        if not isinstance(passes, list) or not passes:
            raise ValueError(f"{source}.conditions.{condition}.summary is missing cycle_pass_distribution")
        for index, item in enumerate(passes):
            if not isinstance(item, dict):
                raise ValueError(f"{source}.conditions.{condition}.summary.cycle_pass_distribution[{index}] is not an object")
            _required_int(item, "passes", f"{source}.conditions.{condition}.summary.cycle_pass_distribution[{index}]")
            _validate_process_sequence_rate(item, f"{source}.conditions.{condition}.summary.cycle_pass_distribution[{index}]")
        after_reviewing = _required_mapping(summary, "after_reviewing", f"{source}.conditions.{condition}.summary")
        per_run = _required_mapping(after_reviewing, "per_run", f"{source}.conditions.{condition}.summary.after_reviewing")
        for target in ("translating", "planning"):
            _validate_process_sequence_rate(per_run[target], f"{source}.conditions.{condition}.summary.after_reviewing.per_run.{target}")
        regeneration = _required_mapping(summary, "regeneration", f"{source}.conditions.{condition}.summary")
        _validate_process_sequence_rate(
            _required_mapping(regeneration, "runs", f"{source}.conditions.{condition}.summary.regeneration"),
            f"{source}.conditions.{condition}.summary.regeneration.runs",
        )
    prompt_association = _required_mapping(report, "prompt_association", source)
    combined = _required_mapping(prompt_association, "combined", f"{source}.prompt_association")
    for contrast in ("A4_vs_A6", "A4_vs_A7"):
        comparison = _required_mapping(combined, contrast, f"{source}.prompt_association.combined")
        splits = _required_mapping(comparison, "splits", f"{source}.prompt_association.combined.{contrast}")
        for split in ("single_cycle_exact", "not_single_cycle_exact"):
            split_data = _required_mapping(splits, split, f"{source}.prompt_association.combined.{contrast}.splits")
            split_source = f"{source}.prompt_association.combined.{contrast}.splits.{split}"
            for key in ("wins", "losses", "ties", "n_non_tie", "pairs"):
                _required_int(split_data, key, split_source)
            win_rate = _required_number(split_data, "win_rate", split_source)
            if not 0.0 <= win_rate <= 1.0:
                raise ValueError(f"{split_source}.win_rate is outside [0, 1]")
        fisher = _required_mapping(comparison, "fisher_exact_two_sided", f"{source}.prompt_association.combined.{contrast}")
        _required_number(fisher, "p_value", f"{source}.prompt_association.combined.{contrast}.fisher_exact_two_sided")
    provenance = _required_mapping(report, "provenance", source)
    leading = _required_mapping(provenance, "leading_process_analysis", f"{source}.provenance")
    leading_conditions = _required_mapping(leading, "conditions", f"{source}.provenance.leading_process_analysis")
    for condition in PROCESS_SEQUENCE_CONDITIONS:
        condition_leading = _required_mapping(leading_conditions, condition, f"{source}.provenance.leading_process_analysis.conditions")
        _validate_process_sequence_rate(
            _required_mapping(condition_leading, "logging_artifact_reconstructions", f"{source}.provenance.leading_process_analysis.conditions.{condition}"),
            f"{source}.provenance.leading_process_analysis.conditions.{condition}.logging_artifact_reconstructions",
        )
        _validate_process_sequence_rate(
            _required_mapping(condition_leading, "logging_artifact_reconstructions_among_raw_non_planning_starts", f"{source}.provenance.leading_process_analysis.conditions.{condition}"),
            f"{source}.provenance.leading_process_analysis.conditions.{condition}.logging_artifact_reconstructions_among_raw_non_planning_starts",
        )
    return report


def _process_conditions(data: dict[str, Any], run_index: int) -> dict[str, Any]:
    if isinstance(data.get("conditions"), dict):
        conditions = data["conditions"]
    else:
        runs = data.get("runs")
        run_key = f"run{run_index}"
        if not isinstance(runs, dict) or not isinstance(runs.get(run_key), dict):
            raise ValueError(f"process summary does not contain {run_key}.conditions")
        conditions = runs[run_key].get("conditions")
    if not isinstance(conditions, dict):
        raise ValueError("process summary conditions must be an object")
    return conditions


def _process_value(values: dict[str, Any], field: str, condition: str) -> Any:
    source_field = PROCESS_SOURCE_FIELDS[field]
    if source_field not in values:
        raise ValueError(f"process summary is missing {condition}.{source_field}")
    return values[source_field]


def _process_runs(summaries: list[dict[str, Any]] | None) -> list[dict[str, dict[str, Any]]]:
    if not summaries:
        return []
    runs = []
    for run_index, summary in enumerate(summaries, 1):
        conditions = _process_conditions(summary, run_index)
        run: dict[str, dict[str, Any]] = {}
        for condition in PROCESS_CONDITIONS:
            values = conditions.get(condition)
            if not isinstance(values, dict):
                raise ValueError(f"process summary is missing condition {condition}")
            fields = PROCESS_FIELDS if condition in PROCESS_TRACE_CONDITIONS else PROCESS_GENERIC_FIELDS
            for field in fields:
                value = _process_value(values, field, condition)
                if _float(value) is None:
                    raise ValueError(f"process summary {condition}.{field} is not numeric")
            run[condition] = {
                field: _process_value(values, field, condition)
                for field in fields
            }
        runs.append(run)
    return runs


def _is_process_macro(name: str) -> bool:
    if name in {r"\AfourGoalsAfterTranslate", r"\AfourDevelopedAfterTranslate"}:
        return True
    if any(name == f"\\{condition_word}{suffix}" for condition_word in ("Afour", "Asix") for suffix in PROCESS_SEQUENCE_SUFFIXES):
        return True
    for condition in PROCESS_CONDITIONS:
        prefix = _condition_name(condition, "")
        for suffix in (*PROCESS_FIELDS.values(), *PROCESS_COMPOSITE_SUFFIXES):
            base = prefix + suffix
            if name == base or any(name.startswith(base + extra) for extra in ("Run", "Mean", "SD")):
                return True
    return False


def _optional_condition_metric(
    data: dict[str, Any], benchmark: str, condition: str, metric: str
) -> Any:
    names = {
        "output_units": {"median_output_units", "output_units_median", "median_units"},
        "spawns": {"mean_spawns_per_run", "mean_spawn_count", "spawn_mean", "spawns_per_run"},
        "goals": {"goal_event_total", "goal_events", "goal_event_totals"},
    }[metric]
    for section in ("completion", "process", "trace", "metrics", "runs", "execution"):
        row = _row(data, section, benchmark, condition)
        found = _metric(row, names)
        if found is not None:
            return found
    return None


def _source_comment(source: str) -> str:
    return "% source: " + source


def _benchmarks(data: dict[str, Any]) -> list[str]:
    return sorted(
        {
            str(row.get("benchmark"))
            for section in ("completion", "native", "pointwise")
            for row in _rows(data, section)
            if row.get("benchmark")
        }
        | {str(name) for name in data.get("pairwise", {}).get("benchmarks", {})}
    )


def _reversed_contrast(contrast: tuple[str, str]) -> tuple[str, str]:
    return contrast[1], contrast[0]


def _existing_definitions(path: Path | None) -> dict[str, str]:
    if path is None or not path.is_file():
        return {}
    definitions = {}
    pattern = re.compile(r"^\\newcommand\{(\\[A-Za-z]+)\}\{(.*)\}$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line.strip())
        if match:
            definitions[match.group(1)] = match.group(2)
    return definitions


def _mark(adjusted_p: float) -> str:
    return r"\textsuperscript{**}" if adjusted_p < 0.01 else r"\textsuperscript{*}" if adjusted_p < 0.05 else ""


def _wlt(stats: dict[str, Any]) -> str:
    return f"{stats['wins']}/{stats['losses']}/{stats['ties']}"


def _emit_length_control_macros(
    add: Any,
    reports: list[dict[str, Any]],
) -> None:
    validated = [
        _validate_length_report(report, f"run {index}")
        for index, report in enumerate(reports, 1)
    ]
    first = validated[0]
    longer = first[LENGTH_SOURCE_FIELDS["longer_side"]]
    add("\\LengthPairCount", str(first[LENGTH_SOURCE_FIELDS["pair_count"]]), "length-control JSON run 1 pair_count")
    add("\\LengthLongerNonTie", str(longer["n_non_tie"]), "length-control JSON run 1 all_pairs_longer_side.n_non_tie")
    add("\\LengthLongerWLT", _wlt(longer), "length-control JSON run 1 all_pairs_longer_side W/L/T")
    add("\\LengthLongerRate", _percent_fixed(longer["win_rate"], 2), "length-control JSON run 1 all_pairs_longer_side.win_rate")
    add(
        "\\LengthLongerInterval",
        f"{_percent_fixed(longer['wilson_low'], 2)}--{_percent_fixed(longer['wilson_high'], 2)}",
        "length-control JSON run 1 all_pairs_longer_side Wilson interval",
    )
    for contrast, contrast_word in ROBUSTNESS_CONTRASTS.items():
        for band, band_word in LENGTH_BANDS.items():
            first_stats = first[LENGTH_SOURCE_FIELDS["matched"]][band][contrast]
            prefix = f"\\Length{contrast_word}{band_word}"
            add(prefix + "WLT", _wlt(first_stats), f"length-control JSON run 1 {band}.{contrast} W/L/T")
            add(prefix + "Rate", _percent_fixed(first_stats["win_rate"], 2), f"length-control JSON run 1 {band}.{contrast}.win_rate")
            add(prefix + "P", _pvalue(first_stats["sign_test_p"]), f"length-control JSON run 1 {band}.{contrast}.sign_test_p")
            for run_index, report in enumerate(validated, 1):
                stats = report[LENGTH_SOURCE_FIELDS["matched"]][band][contrast]
                add(
                    prefix + "RateRun" + RUN_WORDS[run_index],
                    _percent_fixed(stats["win_rate"], 1),
                    f"length-control JSON run {run_index} {band}.{contrast}.win_rate",
                )
    for ratio_bin, ratio_word in LENGTH_RATIO_BINS.items():
        stats = first[LENGTH_SOURCE_FIELDS["ratio_bins"]][ratio_bin]
        prefix = "\\LengthRatio" + ratio_word
        add(prefix + "WLT", _wlt(stats), f"length-control JSON run 1 ratio_bins.{ratio_bin} W/L/T")
        add(prefix + "Rate", _percent_fixed(stats["win_rate"], 2), f"length-control JSON run 1 ratio_bins.{ratio_bin}.win_rate")
    single_writer = first[LENGTH_SOURCE_FIELDS["single_writer"]]
    add("\\LengthSingleWriterShortWLT", _wlt(single_writer), "length-control JSON run 1 single_writer_at_least_10_percent_shorter W/L/T")
    add("\\LengthSingleWriterShortRate", _percent_fixed(single_writer["win_rate"], 2), "length-control JSON run 1 single_writer_at_least_10_percent_shorter.win_rate")
    add("\\LengthSingleWriterShortP", _pvalue(single_writer["sign_test_p"]), "length-control JSON run 1 single_writer_at_least_10_percent_shorter.sign_test_p")
    for run_index, report in enumerate(validated, 1):
        stats = report[LENGTH_SOURCE_FIELDS["single_writer"]]
        add(
            "\\LengthSingleWriterShortRateRun" + RUN_WORDS[run_index],
            _percent_fixed(stats["win_rate"], 1),
            f"length-control JSON run {run_index} single_writer_at_least_10_percent_shorter.win_rate",
        )


def _emit_cross_family_macros(add: Any, report: dict[str, Any]) -> None:
    report = _validate_cross_family(report)
    provenance = report[CROSS_FAMILY_SOURCE_FIELDS["provenance"]]
    pooled = report[CROSS_FAMILY_SOURCE_FIELDS["pooled"]]
    add("\\CrossFamilySeed", str(provenance["seed"]), "cross-family JSON provenance.seed")
    add("\\CrossFamilyPooledN", str(pooled["n"]), "cross-family JSON pooled.n")
    add("\\CrossFamilyPooledWLT", _wlt(pooled), "cross-family JSON pooled W/L/T")
    add("\\CrossFamilyPooledTies", str(pooled["ties"]), "cross-family JSON pooled.ties")
    add("\\CrossFamilyPooledCommitRate", _cross_family_percent(pooled["commit_rate"]["rate"]), "cross-family JSON pooled.commit_rate.rate")
    add("\\CrossFamilyPooledAgreement", f"{pooled['prompt_collapsed_agreement']['numerator']}/{pooled['prompt_collapsed_agreement']['denominator']}", "cross-family JSON pooled.prompt_collapsed_agreement numerator/denominator")
    add("\\CrossFamilyPooledConflicts", str(pooled["direction_conflicts"]), "cross-family JSON pooled.direction_conflicts")
    for contrast, contrast_word in ROBUSTNESS_CONTRASTS.items():
        pooled_contrast = report[CROSS_FAMILY_SOURCE_FIELDS["contrasts"]][contrast]
        prefix = "\\CrossFamily" + contrast_word
        add(prefix + "N", str(pooled_contrast["n"]), f"cross-family JSON contrasts.{contrast}.n")
        add(prefix + "WLT", _wlt(pooled_contrast), f"cross-family JSON contrasts.{contrast} W/L/T")
        add(prefix + "CommitRate", _cross_family_percent(pooled_contrast["commit_rate"]["rate"]), f"cross-family JSON contrasts.{contrast}.commit_rate.rate")
        add(prefix + "WinRate", _cross_family_percent(pooled_contrast["win_rate"]["rate"]), f"cross-family JSON contrasts.{contrast}.win_rate.rate")
        add(prefix + "Interval", f"{_percent_fixed(pooled_contrast['win_rate']['wilson_low'], 2)}--{_percent_fixed(pooled_contrast['win_rate']['wilson_high'], 2)}", f"cross-family JSON contrasts.{contrast}.win_rate Wilson interval")
        add(prefix + "P", _pvalue(pooled_contrast["sign_test_p"]), f"cross-family JSON contrasts.{contrast}.sign_test_p")
        add(prefix + "Conflicts", str(pooled_contrast["direction_conflicts"]), f"cross-family JSON contrasts.{contrast}.direction_conflicts")
        for benchmark, benchmark_word in ROBUSTNESS_BENCHMARKS.items():
            result = pooled_contrast["benchmarks"][benchmark]
            benchmark_prefix = "\\CrossFamily" + benchmark_word + contrast_word
            add(benchmark_prefix + "N", str(result["n"]), f"cross-family JSON contrasts.{contrast}.benchmarks.{benchmark}.n")
            add(benchmark_prefix + "WLT", _wlt(result), f"cross-family JSON contrasts.{contrast}.benchmarks.{benchmark} W/L/T")
            add(benchmark_prefix + "CommitRate", _percent_fixed(result["commit_rate"]["rate"], 2), f"cross-family JSON contrasts.{contrast}.benchmarks.{benchmark}.commit_rate.rate")
            add(benchmark_prefix + "WinRate", _percent_fixed(result["win_rate"]["rate"], 2), f"cross-family JSON contrasts.{contrast}.benchmarks.{benchmark}.win_rate.rate")
            agreement = result["prompt_collapsed_agreement"]
            add(benchmark_prefix + "Agreement", f"{agreement['numerator']}/{agreement['denominator']}", f"cross-family JSON contrasts.{contrast}.benchmarks.{benchmark}.prompt_collapsed_agreement numerator/denominator")


def _emit_process_sequence_macros(add: Any, report: dict[str, Any]) -> None:
    report = _validate_process_sequences(report)
    conditions = report["conditions"]
    prefixes = {"A4": "\\Afour", "A6": "\\Asix"}
    for condition in PROCESS_SEQUENCE_CONDITIONS:
        prefix = prefixes[condition]
        summary = conditions[condition]["summary"]
        add(prefix + "RunCount", str(summary["run_count"]), f"process-sequences JSON conditions.{condition}.summary.run_count")
        add(prefix + "SingleCycleRate", _percent_fixed(summary["single_cycle_exact"]["rate"], 1), f"process-sequences JSON conditions.{condition}.summary.single_cycle_exact.rate")
        add(prefix + "CycleCompliantRate", _percent_fixed(summary["cycle_compliance"]["rate"], 1), f"process-sequences JSON conditions.{condition}.summary.cycle_compliance.rate")
        pass_distribution = {item["passes"]: item for item in summary["cycle_pass_distribution"]}
        if condition == "A4":
            add(prefix + "CompliantOnePassRate", _percent_fixed(pass_distribution[1]["rate"], 1), f"process-sequences JSON conditions.{condition}.summary.cycle_pass_distribution.passes_1.rate")
        else:
            two_three_rate = sum(item["rate"] for passes, item in pass_distribution.items() if passes in (2, 3))
            add(prefix + "CompliantTwoThreePassRate", _percent_fixed(two_three_rate, 1), f"process-sequences JSON conditions.{condition}.summary.cycle_pass_distribution.passes_2_or_3.rate")
        after_reviewing = summary["after_reviewing"]["per_run"]
        add(prefix + "ReviewingToTranslatingRate", _percent_fixed(after_reviewing["translating"]["rate"], 1), f"process-sequences JSON conditions.{condition}.summary.after_reviewing.per_run.translating.rate")
        add(prefix + "ReviewingToPlanningRate", _percent_fixed(after_reviewing["planning"]["rate"], 1), f"process-sequences JSON conditions.{condition}.summary.after_reviewing.per_run.planning.rate")
        add(prefix + "RegenerationRuns", str(summary["regeneration"]["runs"]["count"]), f"process-sequences JSON conditions.{condition}.summary.regeneration.runs.count")
    combined = report["prompt_association"]["combined"]
    for contrast, suffix in (("A4_vs_A6", "FixedOrder"), ("A4_vs_A7", "SingleWriter")):
        splits = combined[contrast]["splits"]
        add("\\AfourExactCycle" + suffix + "WinRate", _percent_fixed(splits["single_cycle_exact"]["win_rate"], 1), f"process-sequences JSON prompt_association.combined.{contrast}.splits.single_cycle_exact.win_rate")
        add("\\AfourNonExact" + suffix + "WinRate", _percent_fixed(splits["not_single_cycle_exact"]["win_rate"], 1), f"process-sequences JSON prompt_association.combined.{contrast}.splits.not_single_cycle_exact.win_rate")
        add("\\Afour" + suffix + "CycleSplitP", _pvalue_two_decimals(combined[contrast]["fisher_exact_two_sided"]["p_value"]), f"process-sequences JSON prompt_association.combined.{contrast}.fisher_exact_two_sided.p_value")
    leading = report["provenance"]["leading_process_analysis"]["conditions"]
    for condition in PROCESS_SEQUENCE_CONDITIONS:
        block = leading[condition]["logging_artifact_reconstructions_among_raw_non_planning_starts"]
        add(prefixes[condition] + "LeadingReconstruction", f"{block['count']}/{block['total']}", f"process-sequences JSON provenance.leading_process_analysis.conditions.{condition}.logging_artifact_reconstructions count/total")


def emit_numbers(
    aggregations: list[dict[str, Any]],
    contrasts: list[tuple[str, str]],
    existing: dict[str, str] | None = None,
    process_summaries: list[dict[str, Any]] | None = None,
    public_prices: dict[str, float] | None = None,
    length_control_summaries: list[dict[str, Any]] | None = None,
    cross_family_summary: dict[str, Any] | None = None,
    process_sequences: dict[str, Any] | None = None,
) -> str:
    """Build a deterministic numbers.tex body using the published macro schema."""

    existing = existing or {}
    process_runs = _process_runs(process_summaries)
    first = aggregations[0]
    benchmarks = _benchmarks(first)
    native_benchmarks = {
        str(row.get("benchmark"))
        for row in _rows(first, "native")
        if row.get("benchmark")
    }
    suppressed_native_names = {
        _schema_name("native", benchmark, condition)
        for benchmark in benchmarks
        if benchmark not in native_benchmarks
        for condition in CONDITION_WORDS
    }
    lines = [
        "% Generated by paper/scripts/make_numbers.py.",
        "% Confirmatory pairwise values use prompt-collapsed outcomes; record-pooled values are sensitivity macros.",
    ]
    emitted: set[str] = set()

    def add(name: str, value: str | None, source: str) -> None:
        if value is None:
            value = existing.get(name, r"\textemdash")
        if name in emitted:
            return
        emitted.add(name)
        lines.extend([_source_comment(source), f"\\newcommand{{{name}}}{{{value}}}"])

    def preserved_or(name: str, fallback: str) -> str:
        value = existing.get(name)
        return fallback if value in {None, r"\textemdash"} else value

    def significant(stats: dict[str, Any]) -> bool:
        p_holm = _float(stats.get("p_holm"))
        return p_holm is not None and p_holm < 0.05

    for estimand in ("collapsed", "record"):
        for contrast in contrasts:
            left, right = contrast
            for benchmark in benchmarks:
                stats = _oriented_metrics(first, benchmark, contrast, estimand)
                if stats is None:
                    continue
                base_source = _estimand_source(benchmark, contrast, estimand)
                add(
                    _estimand_schema_name(estimand, "wlt", benchmark, left, right),
                    f"{stats['wins']}/{stats['losses']}/{stats['ties']}",
                    base_source,
                )
                add(
                    _estimand_schema_name(estimand, "rate", benchmark, left, right),
                    _percent(_float(stats.get("win_rate"))),
                    f"{base_source}.win_rate",
                )
                add(
                    _estimand_schema_name(estimand, "sig", benchmark, left, right),
                    _mark(_float(stats.get("p_holm")) if _float(stats.get("p_holm")) is not None else 1.0),
                    f"{base_source}.p_holm",
                )
                replicate_rates = [
                    _float(replicate["win_rate"])
                    for data in aggregations
                    if (replicate := _oriented_metrics(data, benchmark, contrast, estimand)) is not None
                    and _float(replicate.get("win_rate")) is not None
                ]
                if len(replicate_rates) > 1:
                    add(
                        _estimand_schema_name(estimand, "rate_mean", benchmark, left, right),
                        _percent(statistics.mean(replicate_rates)),
                        f"mean {estimand} win_rate across aggregation files",
                    )
                    add(
                        _estimand_schema_name(estimand, "rate_sd", benchmark, left, right),
                        _percent(statistics.stdev(replicate_rates)),
                        f"sample standard deviation of {estimand} win_rate across aggregation files",
                    )
                    for run_index, replicate_rate in enumerate(replicate_rates, 1):
                        run_name = (
                            _run_rate_name(benchmark, run_index, left, right)
                            if estimand == "collapsed"
                            else _record_run_rate_name(benchmark, run_index, left, right)
                        )
                        add(run_name, _percent(replicate_rate), f"{estimand} aggregation file {run_index}")

        for contrast in contrasts:
            left, right = contrast
            pooled = _sum_metrics(first, benchmarks, contrast, estimand)
            if pooled is None:
                continue
            pooled_source = f"sum of pairwise.benchmarks.*.platforms.codex.{_estimand_section(estimand)} W/L/T fields"
            add(
                _estimand_pooled_name(estimand, "wlt", left, right),
                f"{pooled['wins']}/{pooled['losses']}/{pooled['ties']}",
                pooled_source,
            )
            add(
                _estimand_pooled_name(estimand, "rate", left, right),
                _percent(_float(pooled.get("win_rate"))),
                f"{pooled_source}, ties excluded",
            )
            add(
                _estimand_pooled_name(estimand, "interval", left, right),
                f"{_percent(_float(pooled.get('wilson_low')))}--{_percent(_float(pooled.get('wilson_high')))}",
                f"{pooled_source}, Wilson 95 percent interval",
            )
            rates = [
                _float(replicate["win_rate"])
                for data in aggregations
                if (replicate := _sum_metrics(data, benchmarks, contrast, estimand)) is not None
                and _float(replicate.get("win_rate")) is not None
            ]
            if len(rates) > 1:
                add(
                    _estimand_pooled_name(estimand, "rate_mean", left, right),
                    _percent(statistics.mean(rates)),
                    f"mean {estimand} pooled win_rate across aggregation files",
                )
                add(
                    _estimand_pooled_name(estimand, "rate_sd", left, right),
                    _percent(statistics.stdev(rates)),
                    f"sample standard deviation of {estimand} pooled win_rate across aggregation files",
                )
                for run_index, replicate_rate in enumerate(rates, 1):
                    add(
                        _estimand_pooled_name(estimand, "rate", left, right) + "Run" + RUN_WORDS[run_index],
                        _percent(replicate_rate),
                        f"{estimand} pooled aggregation file {run_index}",
                    )

        if len(aggregations) > 1:
            for contrast in contrasts:
                counts = []
                for run_index, data in enumerate(aggregations, 1):
                    count = sum(
                        significant(stats)
                        for benchmark in _benchmarks(data)
                        if (stats := _oriented_metrics(data, benchmark, contrast, estimand)) is not None
                    )
                    cell_name = (
                        _pooled_holm_cells_name(run_index, *contrast)
                        if estimand == "collapsed"
                        else _record_pooled_holm_cells_name(run_index, *contrast)
                    )
                    add(
                        cell_name,
                        str(count),
                        f"count of {estimand} per-benchmark cells surviving Holm correction",
                    )
                    counts.append(count)
                total_name = (
                    _pooled_holm_cells_total_name(*contrast)
                    if estimand == "collapsed"
                    else _record_pooled_holm_cells_total_name(*contrast)
                )
                add(
                    total_name,
                    str(sum(counts)),
                    f"sum of {estimand} per-benchmark cells surviving Holm correction across runs",
                )

    for benchmark in benchmarks:
        run_rates = []
        total_disagreements = 0
        total_prompts = 0
        for run_index, data in enumerate(aggregations, 1):
            disagreements = 0
            prompts = 0
            for contrast in contrasts:
                stats = _oriented_metrics(data, benchmark, contrast, "collapsed")
                if stats is None:
                    continue
                disagreements += int(stats.get("presentation_disagreements", 0))
                prompts += int(stats.get("prompt_total", 0))
            if prompts:
                rate = disagreements / prompts
                run_rates.append(rate)
                total_disagreements += disagreements
                total_prompts += prompts
                base = "\\" + BENCHMARK_WORDS[benchmark] + "PresentationDisagreementRate"
                add(base + "Run" + RUN_WORDS[run_index], _percent(rate), f"collapsed presentation_disagreements/prompt_total, aggregation file {run_index}")
        if total_prompts:
            base = "\\" + BENCHMARK_WORDS[benchmark] + "PresentationDisagreementRate"
            add(base, _percent(total_disagreements / total_prompts), "sum of collapsed presentation_disagreements/prompt_total across aggregation files")
        if len(run_rates) > 1:
            add(base + "Mean", _percent(statistics.mean(run_rates)), "mean of collapsed presentation disagreement rates across aggregation files")
            add(base + "SD", _percent(statistics.stdev(run_rates)), "sample standard deviation of collapsed presentation disagreement rates across aggregation files")

    if len(aggregations) > 1:
        for run_index, data in enumerate(aggregations, 1):
            missing_pairs = data.get("pairwise", {}).get("missing_pairs")
            if missing_pairs is not None:
                add(
                    _missing_pairs_name(run_index),
                    _format(missing_pairs, decimals=0),
                    "pairwise.missing_pairs",
                )

    table_contrasts = (("A5", "A4"), ("A6", "A4"), ("A7", "A4"), ("A7", "A1"), ("A7", "A5"))
    for estimand in ("collapsed", "record"):
        for contrast in table_contrasts:
            left, right = contrast
            for benchmark in benchmarks:
                stats = _oriented_metrics(first, benchmark, contrast, estimand)
                if stats is None:
                    continue
                mark = _mark(_float(stats.get("p_holm")) if _float(stats.get("p_holm")) is not None else 1.0)
                add(
                    _estimand_schema_name(estimand, "table_win", benchmark, left, right),
                    f"{_percent(_float(stats.get('win_rate')))}{mark}",
                    f"{_estimand_source(benchmark, contrast, estimand)}.win_rate and p_holm",
                )
                table_rates = [
                    _float(replicate["win_rate"])
                    for data in aggregations
                    if (replicate := _oriented_metrics(data, benchmark, contrast, estimand)) is not None
                    and _float(replicate.get("win_rate")) is not None
                ]
                if len(table_rates) > 1:
                    add(
                        _estimand_schema_name(estimand, "rate_mean", benchmark, left, right),
                        _percent(statistics.mean(table_rates)),
                        f"mean {estimand} win_rate across aggregation files",
                    )
                    add(
                        _estimand_schema_name(estimand, "rate_sd", benchmark, left, right),
                        _percent(statistics.stdev(table_rates)),
                        f"sample standard deviation of {estimand} win_rate across aggregation files",
                    )
            pooled = _sum_metrics(first, benchmarks, contrast, estimand)
            if pooled is None:
                continue
            suffix_rate = "table_rate" if contrast[0] == "A7" else "rate"
            suffix_interval = "table_interval" if contrast[0] == "A7" else "interval"
            pooled_source = f"sum of pairwise.benchmarks.*.platforms.codex.{_estimand_section(estimand)} W/L/T fields"
            add(
                _estimand_pooled_name(estimand, suffix_rate, left, right),
                _percent(_float(pooled.get("win_rate"))),
                f"{pooled_source}, ties excluded",
            )
            add(
                _estimand_pooled_name(estimand, suffix_interval, left, right),
                f"{_percent(_float(pooled.get('wilson_low')))}--{_percent(_float(pooled.get('wilson_high')))}",
                f"{pooled_source}, Wilson 95 percent interval",
            )
            table_rates = [
                _float(replicate["win_rate"])
                for data in aggregations
                if (replicate := _sum_metrics(data, benchmarks, contrast, estimand)) is not None
                and _float(replicate.get("win_rate")) is not None
            ]
            if len(table_rates) > 1:
                add(
                    _estimand_pooled_name(estimand, "rate_mean", left, right),
                    _percent(statistics.mean(table_rates)),
                    f"mean {estimand} pooled win_rate across aggregation files",
                )
                add(
                    _estimand_pooled_name(estimand, "rate_sd", left, right),
                    _percent(statistics.stdev(table_rates)),
                    f"sample standard deviation of {estimand} pooled win_rate across aggregation files",
                )

    for benchmark in benchmarks:
        for condition in CONDITION_WORDS:
            point = _row(first, "pointwise", benchmark, condition)
            native = _row(first, "native", benchmark, condition)
            completion = _row(first, "completion", benchmark, condition)
            add(_schema_name("point", benchmark, condition), _format(point.get("z_scored_composite_mean")), f"pointwise.rows[{benchmark},{condition}].z_scored_composite_mean")
            if benchmark in native_benchmarks:
                add(_schema_name("native", benchmark, condition), _format(native.get("mean_score")), f"native.rows[{benchmark},{condition}].mean_score")
            completed, total = completion.get("completed_runs"), completion.get("run_count")
            percentage = None
            if _float(completed) is not None and _float(total):
                percentage = _percent(_float(completed) / _float(total))
            add(_schema_name("completion", benchmark, condition), percentage, f"completion.rows[{benchmark},{condition}].completed_runs/run_count")

    for condition in CONDITION_WORDS:
        completed = sum(int(_row(first, "completion", benchmark, condition).get("completed_runs", 0)) for benchmark in benchmarks)
        total = sum(int(_row(first, "completion", benchmark, condition).get("run_count", 0)) for benchmark in benchmarks)
        add(_condition_name(condition, "Completed"), f"{completed}/{total}", "sum of completion.rows[].completed_runs and run_count")
        if not process_runs:
            for token_name, suffix in TOKEN_METRICS.items():
                mean_tokens = _generation_tokens_per_run(first, condition, token_name)
                add(
                    _condition_name(condition, suffix),
                    _format_tokens(mean_tokens),
                    f"mean aggregation generation tokens.{token_name} / summed run_count",
                )
        if public_prices is not None:
            generation_cost = _generation_cost_per_run(first, condition, public_prices)
            add(
                _condition_name(condition, "Cost"),
                f"\\${generation_cost:.5f}" if generation_cost is not None else None,
                "public price table applied to aggregation generation token totals",
            )
    if process_runs:
        for condition in PROCESS_CONDITIONS:
            fields = PROCESS_FIELDS if condition in PROCESS_TRACE_CONDITIONS else PROCESS_GENERIC_FIELDS
            for field in fields:
                suffix = PROCESS_FIELDS[field]
                base = _condition_name(condition, suffix)
                values = [_float(run[condition][field]) for run in process_runs]
                source_field = PROCESS_SOURCE_FIELDS[field]
                decimals = PROCESS_FIELD_DECIMALS[field]
                add(
                    base,
                    _format_process(values[0], decimals),
                    f"process-summary JSON run 1 conditions.{condition}.{source_field}",
                )
                for run_index, value in enumerate(values, 1):
                    add(
                        base + "Run" + RUN_WORDS[run_index],
                        _format_process(value, decimals),
                        f"process-summary JSON run {run_index} conditions.{condition}.{source_field}",
                    )
                if len(values) > 1:
                    add(
                        base + "Mean",
                        _format_process(statistics.mean(values), decimals),
                        f"mean across process-summary JSON runs for {condition}.{field}",
                    )
                    add(
                        base + "SD",
                        _format_process(statistics.stdev(values), decimals),
                        f"sample standard deviation across process-summary JSON runs for {condition}.{field}",
                    )
            goals = "/".join(
                _format_process(process_runs[0][condition][field], PROCESS_FIELD_DECIMALS[field])
                for field in PROCESS_GOAL_FIELDS
            )
            add(
                _condition_name(condition, "Goals"),
                goals,
                f"process-summary JSON run 1 conditions.{condition}.goal_created/goal_developed/goal_regenerated",
            )
            for run_index, run in enumerate(process_runs, 1):
                run_goals = "/".join(
                    _format_process(run[condition][field], PROCESS_FIELD_DECIMALS[field])
                    for field in PROCESS_GOAL_FIELDS
                )
                add(
                    _condition_name(condition, "Goals") + "Run" + RUN_WORDS[run_index],
                    run_goals,
                    f"process-summary JSON run {run_index} conditions.{condition}.goal_created/goal_developed/goal_regenerated",
                )

    for condition, values in HABERMAS_SUMMARY.items():
        condition_word = CONDITION_WORDS.get(condition, {"B1": "Bone", "B2": "Btwo"}.get(condition, _word(condition)))
        prefix = "Hab" + condition_word
        suffixes = ("Completed", "Created", "Developed", "Regenerated", "Ledger", "Point")
        for suffix, value in zip(suffixes, values):
            name = "\\" + prefix + suffix
            add(name, preserved_or(name, value), "issue 56 Habermas pilot summary")

    if length_control_summaries is not None:
        if len(length_control_summaries) != 3:
            raise ValueError("length-control summaries must contain exactly three runs")
        _emit_length_control_macros(add, length_control_summaries)
    if cross_family_summary is not None:
        _emit_cross_family_macros(add, cross_family_summary)
    if process_sequences is not None:
        _emit_process_sequence_macros(add, process_sequences)

    # The power sentence uses the confirmed A4:A1 prompt-collapsed counts.
    # Keep raw counts for the power inversion and round only displayed counts.
    power_counts = []
    for benchmark in benchmarks:
        stats = _estimand_metrics(first, benchmark, ("A4", "A1"), "collapsed")
        if stats is not None:
            power_counts.append(stats)
    if power_counts:
        pooled_prompts = sum(stats["wins"] + stats["losses"] + stats["ties"] for stats in power_counts)
        pooled_decided = sum(stats["wins"] + stats["losses"] for stats in power_counts)
        mean_cell_decided = statistics.mean(stats["wins"] + stats["losses"] for stats in power_counts)

        add("\\PowerPooledEligible", str(pooled_prompts), "mean eligible pairs per contrast")
        add("\\PowerPooledDecided", str(pooled_decided // 10 * 10), "approximate decided count from prompt-collapsed aggregation counts")
        add(
            "\\PowerPooledDetectablePreference",
            f"{minimum_true_win_rate_for_power(pooled_decided) * 100:.0f}\\%",
            "minimum true win rate for 80 percent exact-sign-test power at the first Holm threshold",
        )
        add("\\PowerCellEligible", str(pooled_prompts // len(power_counts)), "mean eligible pairs per contrast")
        add("\\PowerCellDecided", str(round(mean_cell_decided)), "mean benchmark decided count from prompt-collapsed aggregation counts")
        add(
            "\\PowerCellDetectablePreference",
            f"{minimum_true_win_rate_for_power(mean_cell_decided) * 100:.0f}\\%",
            "minimum true win rate for 80 percent exact-sign-test power at the first Holm threshold",
        )

    for name, value in existing.items():
        if name not in emitted and name not in suppressed_native_names and not _is_process_macro(name) and (
            public_prices is not None or not name.endswith("Cost")
        ):
            lines.extend(["% preserved schema macro from the existing packet.", f"\\newcommand{{{name}}}{{{value}}}"])
    return "\n".join(lines) + "\n"


def parse_contrasts(value: str) -> list[tuple[str, str]]:
    result = []
    for item in value.split(","):
        left, separator, right = item.strip().partition(":")
        if not separator or not left or not right or left == right:
            raise argparse.ArgumentTypeError(f"invalid contrast: {item!r}")
        result.append((left, right))
    return result


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"could not read {label} JSON: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} JSON must contain an object: {path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("aggregations", nargs="+", type=Path)
    parser.add_argument("--contrasts", required=True, type=parse_contrasts)
    parser.add_argument("--process-summaries", nargs="+", type=Path, default=[])
    parser.add_argument("--length-control-summaries", nargs="+", type=Path, default=[])
    parser.add_argument("--cross-family-summary", type=Path)
    parser.add_argument("--process-sequences", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "numbers.tex")
    cost_group = parser.add_mutually_exclusive_group()
    cost_group.add_argument("--public-prices", type=Path)
    cost_group.add_argument("--no-cost", action="store_true")
    args = parser.parse_args()
    aggregations = [_read_json_object(path, "aggregation") for path in args.aggregations]
    existing = _existing_definitions(args.output)
    process_summaries = [_read_json_object(path, "process summary") for path in args.process_summaries]
    length_control_summaries = [_read_json_object(path, "length-control") for path in args.length_control_summaries]
    cross_family_summary = (
        _read_json_object(args.cross_family_summary, "cross-family")
        if args.cross_family_summary is not None
        else None
    )
    process_sequences = (
        _read_json_object(args.process_sequences, "process-sequences")
        if args.process_sequences is not None
        else None
    )
    public_prices = _public_prices(args.public_prices) if not args.no_cost else None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        emit_numbers(
            aggregations,
            args.contrasts,
            existing,
            process_summaries,
            public_prices,
            length_control_summaries or None,
            cross_family_summary,
            process_sequences,
        ),
        encoding="utf-8",
    )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
