import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from make_numbers import (
    _cross_family_percent,
    emit_numbers,
    exact_sign_test_power,
    holm_adjust,
    macro_name,
    minimum_true_win_rate_for_power,
    sign_test_pvalue,
    timing_summaries,
)


def _aggregation() -> dict:
    return {
        "completion": {
            "rows": [
                {"benchmark": "WritingBench", "condition": "A1", "completed_runs": 2, "run_count": 3},
                {"benchmark": "WritingBench", "condition": "A4", "completed_runs": 3, "run_count": 4},
            ]
        },
        "cost": {
            "generation": [
                {"condition": "A1", "run_count": 3, "tokens": {"input": 9, "output": 12}},
                {"condition": "A4", "run_count": 4, "tokens": {"input": 20, "output": 28}},
            ]
        },
        "pairwise": {"benchmarks": {}},
    }


def _pairwise_aggregation(
    wins: int,
    losses: int,
    missing_pairs: int = 0,
    collapsed_wins: int | None = None,
    collapsed_losses: int | None = None,
) -> dict:
    collapsed_wins = wins if collapsed_wins is None else collapsed_wins
    collapsed_losses = losses if collapsed_losses is None else collapsed_losses
    record = {"wins": wins, "losses": losses, "ties": 0, "p_holm": 0.01}
    collapsed = {
        "wins": collapsed_wins,
        "losses": collapsed_losses,
        "ties": 0,
        "prompt_total": collapsed_wins + collapsed_losses,
        "presentation_disagreements": 0,
        "judge_disagreements": 0,
        "n_non_tie": collapsed_wins + collapsed_losses,
        "win_rate": collapsed_wins / (collapsed_wins + collapsed_losses),
        "p_raw": 0.01,
        "p_holm": 0.01,
        "wilson_low": 0.0,
        "wilson_high": 1.0,
    }
    return {
        "pairwise": {
            "missing_pairs": missing_pairs,
            "benchmarks": {
                "WritingBench": {
                    "platforms": {
                        "codex": {
                            "contrasts": {
                                "A4:A1": record
                            },
                            "prompt_collapsed_across_judges": {
                                "A4:A1": collapsed
                            },
                            "record_pooled": {"A4:A1": record},
                        }
                    }
                }
            }
        }
    }


def _length_stats() -> dict:
    return {
        "pairs": 3,
        "selected_pairs": 3,
        "equal_length_pairs": 0,
        "wins": 1,
        "losses": 1,
        "ties": 1,
        "n_non_tie": 2,
        "win_rate": 0.5,
        "wilson_low": 0.1,
        "wilson_high": 0.9,
        "sign_test_p": 1.0,
    }


def _length_summary() -> dict:
    contrasts = {"A4:A1": "x", "A4:A3": "x", "A4:A5": "x"}
    bands = {
        band: {contrast: _length_stats() for contrast in contrasts}
        for band in ("5_percent", "10_percent")
    }
    ratio_bins = {
        ratio_bin: _length_stats()
        for ratio_bin in ("1.00-1.05", "1.05-1.10", "1.10-1.25", "1.25-1.50", "1.50-2.00", "2.00+")
    }
    return {
        "pair_count": 6,
        "all_pairs_longer_side": _length_stats(),
        "length_matched": bands,
        "ratio_bins": ratio_bins,
        "single_writer_at_least_10_percent_shorter": _length_stats(),
    }


def _compute_outcome() -> dict:
    return {
        "wins": 2,
        "losses": 1,
        "ties": 1,
        "n_non_tie": 3,
        "pairs": 4,
        "win_rate": 2 / 3,
        "wilson_low": 0.2,
        "wilson_high": 0.9,
        "sign_test_p": 0.25,
    }


def _compute_summary() -> dict:
    contrasts = ("A4:A2", "A4:A3", "A7:A4", "A4:A1")
    bands = ("within_1.25", "within_1.5")
    ratio_bins = (
        "0.00-0.50",
        "0.50-0.67",
        "0.67-0.80",
        "0.80-0.91",
        "0.91-0.95",
        "0.95-1.05",
        "1.05-1.10",
        "1.10-1.25",
        "1.25-1.50",
        "1.50-2.00",
        "2.00+",
    )

    def contrast_data() -> dict:
        return {
            "compute_matched": {band: _compute_outcome() for band in bands},
            "ratio_bins": {ratio_bin: _compute_outcome() for ratio_bin in ratio_bins},
            "spearman": {"n": 4, "rho": 0.125},
        }

    by_contrast = {contrast: contrast_data() for contrast in contrasts}
    return {
        "matched_bands": [1.25, 1.5],
        "ratio_bin_upper_bounds": [0.5, 2 / 3, 0.8, 10 / 11, 20 / 21, 1.05, 1.1, 1.25, 1.5, 2.0],
        "pooled": {"pair_count": 16, "by_contrast": by_contrast},
        "per_replication": {
            replication: {
                "pair_count": 16,
                "by_contrast": {
                    contrast: {
                        "compute_matched": {band: _compute_outcome() for band in bands}
                    }
                    for contrast in contrasts
                },
            }
            for replication in ("run-1", "replication-2", "replication-3")
        },
    }


def _cross_rate() -> dict:
    return {
        "numerator": 1,
        "denominator": 2,
        "rate": 0.5,
        "wilson_low": 0.1,
        "wilson_high": 0.9,
    }


def _cross_result() -> dict:
    return {
        "n": 3,
        "wins": 1,
        "losses": 1,
        "ties": 1,
        "direction_conflicts": 0,
        "commit_rate": _cross_rate(),
        "win_rate": _cross_rate(),
        "presentation_agreement": _cross_rate(),
        "prompt_collapsed_agreement": _cross_rate(),
        "sign_test_p": 1.0,
    }


def _cross_family_summary() -> dict:
    contrasts = {}
    for contrast in ("A4:A1", "A4:A3", "A4:A5"):
        result = _cross_result()
        result["benchmarks"] = {
            benchmark: _cross_result()
            for benchmark in ("DoLoMiTes", "HelloBench", "WritingBench")
        }
        contrasts[contrast] = result
    return {
        "contrasts": contrasts,
        "pooled": _cross_result(),
        "provenance": {
            "cross_family_judge_id": "judge",
            "reference_judge_id": "reference",
            "effort": "medium",
            "seed": 1,
        },
        "note": "No multiplicity correction is applied to this robustness check.",
    }


def _process_summary(missing: str | None = None) -> dict:
    fields = {
        "goal_created": 1,
        "goal_developed": 2,
        "goal_regenerated": 3,
        "ledger_entries_contract": 10,
        "ledger_entries_no_proposal": 4,
        "ledger_entries_with_proposal": 6,
        "ledger_entries_phrase_scan": 100,
        "ledger_no_proposal_phrase_scan": 99,
        "ledger_with_proposal_phrase_scan": 1,
        "median_output_units": 1200,
        "mean_spawns_per_attempted_run": 8.09,
        "mean_output_plus_reasoning_tokens": 18000,
        "mean_uncached_input_tokens": 63000,
        "mean_wall_clock_seconds_completed": 300,
    }
    return {
        "conditions": {
            condition: {
                key: value
                for key, value in fields.items()
                if key != missing
            }
            for condition in ("A1", "A2", "A3", "A4", "A5", "A6", "A7")
        }
    }


def _process_sequences() -> dict:
    def rate(count: int, total: int, value: float) -> dict:
        return {"count": count, "total": total, "rate": value}

    def summary(total: int, exact: float, compliant: float, translating: float, planning: float, regeneration: int, passes: list[dict]) -> dict:
        matrix = {
            state: {target: 1 for target in ("END", "START", "planning", "reviewing", "translating")}
            for state in ("END", "START", "planning", "reviewing", "translating")
        }
        sequences = [
            {"count": 10 - index, "rate": (10 - index) / total, "sequence": ["planning", "translating", "reviewing"], "total": total}
            for index in range(5)
        ]
        return {
            "run_count": total,
            "single_cycle_exact": rate(round(exact * total), total, exact),
            "cycle_compliance": rate(round(compliant * total), total, compliant),
            "cycle_pass_distribution": passes,
            "after_reviewing": {
                "per_run": {
                    "translating": rate(round(translating * total), total, translating),
                    "planning": rate(round(planning * total), total, planning),
                }
            },
            "regeneration": {"runs": rate(regeneration, total, regeneration / total)},
            "sequence_distribution": sequences,
            "transition_matrix": matrix,
        }

    return {
        "conditions": {
            "A4": {"summary": summary(886, 0.564, 0.746, 0.148, 0.003, 4, [{"passes": 1, "count": 1, "total": 1, "rate": 0.992}, {"passes": 2, "count": 1, "total": 1, "rate": 0.008}])},
            "A6": {"summary": summary(874, 0.508, 0.898, 0.010, 0.097, 10, [{"passes": 1, "count": 1, "total": 1, "rate": 0.915}, {"passes": 2, "count": 1, "total": 1, "rate": 0.073}, {"passes": 3, "count": 1, "total": 1, "rate": 0.012}])},
        },
        "prompt_association": {
            "combined": {
                "A4_vs_A6": {
                    "splits": {
                        "single_cycle_exact": {"wins": 1, "losses": 1, "ties": 0, "n_non_tie": 2, "pairs": 2, "win_rate": 0.574},
                        "not_single_cycle_exact": {"wins": 1, "losses": 1, "ties": 0, "n_non_tie": 2, "pairs": 2, "win_rate": 0.549},
                    },
                    "fisher_exact_two_sided": {"p_value": 0.60},
                },
                "A4_vs_A7": {
                    "splits": {
                        "single_cycle_exact": {"wins": 1, "losses": 1, "ties": 0, "n_non_tie": 2, "pairs": 2, "win_rate": 0.722},
                        "not_single_cycle_exact": {"wins": 1, "losses": 1, "ties": 0, "n_non_tie": 2, "pairs": 2, "win_rate": 0.752},
                    },
                    "fisher_exact_two_sided": {"p_value": 0.43},
                },
            }
        },
        "provenance": {
            "leading_process_analysis": {
                "conditions": {
                    "A4": {
                        "logging_artifact_reconstructions": rate(23, 886, 23 / 886),
                        "logging_artifact_reconstructions_among_raw_non_planning_starts": rate(23, 39, 23 / 39),
                    },
                    "A6": {
                        "logging_artifact_reconstructions": rate(103, 874, 103 / 874),
                        "logging_artifact_reconstructions_among_raw_non_planning_starts": rate(103, 103, 1.0),
                    },
                }
            }
        },
    }


def _expand_schema_pattern(pattern: str) -> set[str]:
    match = re.search(r"\{([^{}]+)\}", pattern)
    if match is None:
        return {pattern}
    values = set()
    for option in match.group(1).split(","):
        values.update(
            _expand_schema_pattern(pattern[: match.start()] + option + pattern[match.end() :])
        )
    return values


def _schema_patterns(path: Path) -> set[str]:
    patterns = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("| `"):
            patterns.add(line.split("|", 2)[1].strip().strip("`"))
    expanded = set()
    for pattern in patterns:
        expanded.update(_expand_schema_pattern(pattern))
    return expanded


class TokenMacroTests(unittest.TestCase):
    def test_token_macros_are_means_per_attempted_run(self):
        output = emit_numbers([_aggregation()], [("A4", "A1")])
        self.assertIn(r"\newcommand{\AoneOutputTokens}{4}", output)
        self.assertIn(r"\newcommand{\AoneInputTokens}{3}", output)
        self.assertIn(r"\newcommand{\AfourOutputTokens}{7}", output)
        self.assertIn(r"\newcommand{\AfourInputTokens}{5}", output)

    def test_cost_macros_are_omitted_without_public_prices(self):
        output = emit_numbers([_aggregation()], [("A4", "A1")])
        self.assertNotIn(r"\AoneCost", output)
        self.assertNotIn(r"\AfourCost", output)

    def test_replicate_rates_and_holm_counts_are_emitted(self):
        output = emit_numbers(
            [_pairwise_aggregation(10, 0), _pairwise_aggregation(9, 1), _pairwise_aggregation(8, 2)],
            [("A4", "A1")],
        )
        self.assertIn(r"\newcommand{\WritingFourOneRateMean}{90\%}", output)
        self.assertIn(r"\newcommand{\WritingFourOneRateSD}{10\%}", output)
        self.assertIn(r"\newcommand{\WritingFourOneRateRunThree}{80\%}", output)
        self.assertIn(r"\newcommand{\PooledFourOneHolmRunOneCells}{1}", output)

    def test_confirmatory_macros_use_collapsed_fields_not_record_pooled(self):
        output = emit_numbers(
            [_pairwise_aggregation(10, 0, collapsed_wins=2, collapsed_losses=8)],
            [("A4", "A1")],
        )
        source = re.search(
            r"% source: ([^\n]+)\n\\newcommand\{\\WritingFourOneRate\}",
            output,
        )
        self.assertIsNotNone(source)
        self.assertIn("prompt_collapsed_across_judges", source.group(1))
        self.assertNotIn("record_pooled", source.group(1))
        self.assertIn(r"\newcommand{\WritingFourOneRate}{20\%}", output)
        self.assertIn(r"\newcommand{\RecordWritingFourOneRate}{100\%}", output)

    def test_length_control_macros_fail_closed_on_missing_fields(self):
        summary = _length_summary()
        del summary["ratio_bins"]["2.00+"]["win_rate"]
        with self.assertRaisesRegex(ValueError, r"ratio_bins\.2\.00\+.*win_rate"):
            emit_numbers(
                [_aggregation()],
                [("A4", "A1")],
                length_control_summaries=[summary, _length_summary(), _length_summary()],
            )

    def test_compute_stratified_macros_are_source_backed(self):
        output = emit_numbers(
            [_aggregation()],
            [("A4", "A1")],
            compute_stratified_sensitivity=_compute_summary(),
        )
        self.assertIn(r"\newcommand{\ComputePooledEligible}{16}", output)
        self.assertIn(r"\newcommand{\ComputeFullStagedWithinOneTwentyFiveWLT}{2/1/1}", output)
        self.assertIn(r"\newcommand{\ComputeFullStagedWithinOneTwentyFiveRate}{66.7\%}", output)
        self.assertIn(r"\newcommand{\ComputeFullStagedWithinOneTwentyFiveRateReplicationThree}{66.7\%}", output)
        self.assertIn(r"\newcommand{\ComputeFullStagedSpearmanRho}{0.1250}", output)
        self.assertIn(r"\newcommand{\ComputeFullSinglePassBinTwoPlusP}{0.25}", output)

    def test_compute_stratified_macros_fail_closed_on_missing_fields(self):
        summary = _compute_summary()
        del summary["pooled"]["by_contrast"]["A4:A2"]["spearman"]["rho"]
        with self.assertRaisesRegex(ValueError, r"pooled\.A4:A2\.spearman.*rho"):
            emit_numbers(
                [_aggregation()],
                [("A4", "A1")],
                compute_stratified_sensitivity=summary,
            )

    def test_compute_stratified_macros_fail_closed_on_missing_ratio_bin(self):
        summary = _compute_summary()
        del summary["pooled"]["by_contrast"]["A4:A2"]["ratio_bins"]["2.00+"]
        with self.assertRaisesRegex(ValueError, r"ratio_bins must contain the locked bins"):
            emit_numbers(
                [_aggregation()],
                [("A4", "A1")],
                compute_stratified_sensitivity=summary,
            )

    def test_cross_family_macros_fail_closed_on_missing_fields(self):
        summary = _cross_family_summary()
        del summary["contrasts"]["A4:A1"]["benchmarks"]["WritingBench"]["prompt_collapsed_agreement"]
        with self.assertRaisesRegex(ValueError, r"A4:A1\.WritingBench.*prompt_collapsed_agreement"):
            emit_numbers(
                [_aggregation()],
                [("A4", "A1")],
                cross_family_summary=summary,
            )

    def test_robustness_macros_use_json_source_fields(self):
        output = emit_numbers(
            [_aggregation()],
            [("A4", "A1")],
            length_control_summaries=[_length_summary(), _length_summary(), _length_summary()],
            cross_family_summary=_cross_family_summary(),
        )
        self.assertIn(r"% source: length-control JSON run 1 all_pairs_longer_side.win_rate", output)
        self.assertIn(r"\newcommand{\LengthLongerRate}{50.00\%}", output)
        self.assertIn(r"% source: cross-family JSON pooled.commit_rate.rate", output)
        self.assertIn(r"\newcommand{\CrossFamilyPooledCommitRate}{50.0\%}", output)

    def test_length_control_macros_do_not_use_existing_fallback_values(self):
        output = emit_numbers(
            [_aggregation()],
            [("A4", "A1")],
            existing={r"\LengthLongerNonTie": "999", r"\LengthLongerRate": r"99\%"},
            length_control_summaries=[_length_summary(), _length_summary(), _length_summary()],
        )
        self.assertIn(r"% source: length-control JSON run 1 all_pairs_longer_side.n_non_tie", output)
        self.assertIn(r"\newcommand{\LengthLongerNonTie}{2}", output)
        self.assertIn(r"\newcommand{\LengthLongerRate}{50.00\%}", output)
        self.assertNotIn(r"\newcommand{\LengthLongerRate}{99\%}", output)

    def test_cross_family_macros_do_not_use_existing_fallback_values(self):
        output = emit_numbers(
            [_aggregation()],
            [("A4", "A1")],
            existing={r"\CrossFamilyPooledTies": "999", r"\CrossFamilyPooledCommitRate": r"99\%"},
            cross_family_summary=_cross_family_summary(),
        )
        self.assertIn(r"% source: cross-family JSON pooled.ties", output)
        self.assertIn(r"\newcommand{\CrossFamilyPooledTies}{1}", output)
        self.assertIn(r"\newcommand{\CrossFamilyPooledCommitRate}{50.0\%}", output)
        self.assertNotIn(r"\newcommand{\CrossFamilyPooledCommitRate}{99\%}", output)

    def test_replicate_missing_pair_macros_are_emitted(self):
        output = emit_numbers(
            [
                _pairwise_aggregation(10, 0, 161),
                _pairwise_aggregation(9, 1, 33),
                _pairwise_aggregation(8, 2, 36),
            ],
            [("A4", "A1")],
        )
        self.assertIn(r"\newcommand{\ReplicationRunOneMissingPairs}{161}", output)
        self.assertIn(r"\newcommand{\ReplicationRunTwoMissingPairs}{33}", output)
        self.assertIn(r"\newcommand{\ReplicationRunThreeMissingPairs}{36}", output)

    def test_process_macro_requires_its_source_field(self):
        with self.assertRaisesRegex(ValueError, r"A4\.ledger_entries_contract"):
            emit_numbers(
                [_aggregation()],
                [("A4", "A1")],
                process_summaries=[_process_summary("ledger_entries_contract")],
            )

    def test_process_macros_ignore_phrase_scan_fields(self):
        output = emit_numbers(
            [_aggregation()],
            [("A4", "A1")],
            process_summaries=[_process_summary()],
        )
        self.assertIn(r"\newcommand{\AfourLedgerEntries}{10}", output)
        self.assertIn(r"\newcommand{\AfourLedgerNoProposal}{4}", output)
        self.assertIn(r"\newcommand{\AfourLedgerWithProposal}{6}", output)

    def test_process_summary_emits_three_run_mean_and_sd_macros(self):
        summaries = []
        for spawns, output_tokens in ((8.09, 17851.5), (8.47, 18388.7), (7.96, 18699.3)):
            summary = _process_summary()
            for condition in summary["conditions"]:
                summary["conditions"][condition]["mean_spawns_per_attempted_run"] = spawns
                summary["conditions"][condition]["mean_output_plus_reasoning_tokens"] = output_tokens
            summaries.append(summary)
        output = emit_numbers(
            [_aggregation()],
            [("A4", "A1")],
            process_summaries=summaries,
        )
        self.assertIn(r"\newcommand{\AthreeSpawnsMean}{8.17}", output)
        self.assertIn(r"\newcommand{\AthreeSpawnsSD}{0.27}", output)
        self.assertIn(r"\newcommand{\AthreeOutputTokensMean}{18,313}", output)
        self.assertIn(r"\newcommand{\AthreeOutputTokensSD}{429}", output)
        self.assertIn(r"\newcommand{\AthreeInputTokensMean}{63,000}", output)

    def test_process_sequences_emit_rq3_macros_from_json(self):
        output = emit_numbers(
            [_aggregation()],
            [("A4", "A1")],
            process_sequences=_process_sequences(),
        )
        self.assertIn(r"\newcommand{\AfourRunCount}{886}", output)
        self.assertIn(r"\newcommand{\AfourCycleCompliantRate}{74.6\%}", output)
        self.assertIn(r"\newcommand{\AsixCompliantTwoThreePassRate}{8.5\%}", output)
        self.assertIn(r"\newcommand{\AfourExactCycleFixedOrderWinRate}{57.4\%}", output)
        self.assertIn(r"\newcommand{\AfourSingleWriterCycleSplitP}{0.43}", output)
        self.assertIn(r"\newcommand{\AfourLeadingReconstruction}{23/39}", output)

    def test_process_sequences_fail_closed_on_missing_fields(self):
        source = _process_sequences()
        del source["conditions"]["A4"]["summary"]["cycle_compliance"]
        with self.assertRaisesRegex(ValueError, r"A4\.summary.*cycle_compliance"):
            emit_numbers([_aggregation()], [("A4", "A1")], process_sequences=source)

    def test_exact_two_sided_sign_test(self):
        self.assertAlmostEqual(sign_test_pvalue(8, 2), 0.109375)
        self.assertEqual(sign_test_pvalue(0, 0), 1.0)

    def test_exact_sign_test_power_inversion(self):
        self.assertAlmostEqual(exact_sign_test_power(10, 0.9, alpha=0.05), 0.7360989382, places=9)
        self.assertAlmostEqual(minimum_true_win_rate_for_power(220), 0.6340920079, places=9)
        self.assertAlmostEqual(minimum_true_win_rate_for_power(75), 0.7295249913, places=9)

    def test_holm_adjustment(self):
        self.assertEqual(holm_adjust([0.01, 0.04, 0.2]), [0.03, 0.08, 0.2])

    def test_cross_family_percent_rounds_once(self):
        self.assertEqual(_cross_family_percent(76 / 101), r"75.2\%")

    def test_macro_name_is_latex_safe_and_stable(self):
        self.assertEqual(
            macro_name("point", "DoLoMiTes", "A4"),
            "\\DoLoAfourPoint",
        )
        self.assertRegex(
            macro_name("native", "A7", "WritingBench", "mean"),
            r"^\\[A-Za-z]+$",
        )

    def test_table_aliases_cover_a7_against_a5(self):
        aggregation = {
            "pairwise": {
                "benchmarks": {
                    "WritingBench": {
                        "platforms": {
                            "codex": {
                                "contrasts": {
                                    "A7:A5": {"wins": 1, "losses": 2, "ties": 0}
                                },
                                "prompt_collapsed_across_judges": {
                                    "A7:A5": {
                                        "wins": 1,
                                        "losses": 2,
                                        "ties": 0,
                                        "prompt_total": 3,
                                        "presentation_disagreements": 0,
                                        "p_holm": 0.5,
                                        "win_rate": 1 / 3,
                                        "wilson_low": 0.1,
                                        "wilson_high": 0.8,
                                    }
                                },
                                "record_pooled": {
                                    "A7:A5": {"wins": 1, "losses": 2, "ties": 0}
                                },
                            }
                        }
                    }
                }
            }
        }
        output = emit_numbers([aggregation], [("A7", "A5")])
        self.assertIn(r"\newcommand{\PooledSevenFiveTableRate}", output)
        self.assertIn(r"\newcommand{\PooledSevenFiveTableInterval}", output)

    def test_native_macros_only_cover_benchmarks_with_native_rows(self):
        aggregation = {
            "native": {
                "rows": [{"benchmark": "HelloBench", "condition": "A1", "mean_score": 4.0}]
            },
            "pairwise": {
                "benchmarks": {
                    "HelloBench": {
                        "platforms": {
                            "codex": {
                                "contrasts": {
                                    "A7:A5": {"wins": 1, "losses": 2, "ties": 0}
                                }
                            }
                        }
                    },
                    "WritingBench": {
                        "platforms": {
                            "codex": {
                                "contrasts": {
                                    "A7:A5": {"wins": 1, "losses": 2, "ties": 0}
                                }
                            }
                        }
                    },
                }
            },
        }
        output = emit_numbers([aggregation], [("A7", "A5")])
        self.assertIn(r"\newcommand{\HelloAoneNative}", output)
        self.assertNotIn(r"\newcommand{\WritingAoneNative}", output)

    def test_timing_summaries_use_attempt_durations_then_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            common = {
                "inputs": {
                    "benchmark_name": "WritingBench",
                    "condition_id": "A1",
                    "prompt_id": "prompt-1",
                    "platform": "codex",
                },
                "status": "completed",
            }
            duration_manifest = {
                **common,
                "attempts": [{"duration_seconds": 2.25}, {"elapsed_seconds": 3.75}],
                "started_at": "2026-09-20T00:00:00Z",
                "updated_at": "2026-09-20T00:10:00Z",
            }
            timestamp_manifest = {
                **common,
                "inputs": {**common["inputs"], "prompt_id": "prompt-2", "condition_id": "A2"},
                "started_at": "2026-09-20T00:00:00+00:00",
                "updated_at": "2026-09-20T00:01:30+00:00",
            }
            for index, manifest in enumerate((duration_manifest, timestamp_manifest), 1):
                path = root / "WritingBench" / manifest["inputs"]["condition_id"] / "codex" / str(index)
                path.mkdir(parents=True)
                (path / "run-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            self.assertEqual(
                timing_summaries([root]),
                {"A1": (6, 6), "A2": (90, 90)},
            )

    def test_every_numbers_macro_is_covered_by_schema_pattern(self):
        numbers_path = Path(__file__).resolve().parents[2] / "numbers.tex"
        macros = {
            match.group(1)
            for match in re.finditer(
                r"^\\newcommand\{(\\[A-Za-z]+)\}",
                numbers_path.read_text(encoding="utf-8"),
                re.MULTILINE,
            )
        }
        covered = _schema_patterns(numbers_path.with_name("numbers-schema.md"))
        self.assertTrue(macros <= covered, sorted(macros - covered))
