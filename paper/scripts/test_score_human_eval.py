import csv
import json
import tempfile
import unittest
from pathlib import Path

from score_human_eval import (
    fleiss_kappa,
    human_to_condition,
    krippendorff_alpha,
    raw_agreement,
    score,
)


class ScoreHumanEvalTests(unittest.TestCase):
    def test_human_mapping_and_agreement_functions(self):
        key = {"condition_a": "A4", "contrast": "A4:A1"}
        self.assertEqual(human_to_condition("A", key), "A4")
        self.assertEqual(human_to_condition("B", key), "A1")
        ratings = {"one": ["A4", "A4", "tie"], "two": ["A1", "A1", "A1"]}
        self.assertAlmostEqual(raw_agreement(ratings), 4 / 6)
        self.assertAlmostEqual(fleiss_kappa(ratings), 5 / 11)
        self.assertAlmostEqual(krippendorff_alpha(ratings), 6 / 11)

    def test_synthetic_three_annotator_report_and_breakdowns(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key = root / "key.csv"
            answers = []
            key_fields = [
                "comparison_id",
                "benchmark",
                "contrast",
                "output_length_gap",
                "automatic_decision_margin",
                "same_family_decision",
                "cross_family_decision",
                "condition_a_1",
                "condition_a_2",
                "condition_a_3",
            ]
            with key.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=key_fields)
                writer.writeheader()
                writer.writerows(
                    [
                        {
                            "comparison_id": "comparison-001",
                            "benchmark": "DoLoMiTes",
                            "contrast": "A4:A1",
                            "output_length_gap": "1.00-1.05",
                            "automatic_decision_margin": "2",
                            "same_family_decision": "A4",
                            "cross_family_decision": "A4",
                            "condition_a_1": "A4",
                            "condition_a_2": "A4",
                            "condition_a_3": "A4",
                        },
                        {
                            "comparison_id": "comparison-002",
                            "benchmark": "HelloBench",
                            "contrast": "A7:A4",
                            "output_length_gap": "1.10-1.25",
                            "automatic_decision_margin": "1",
                            "same_family_decision": "A7",
                            "cross_family_decision": "",
                            "condition_a_1": "A4",
                            "condition_a_2": "A4",
                            "condition_a_3": "A4",
                        },
                    ]
                )
            preferences = {
                "annotator-1": {"comparison-001": "A", "comparison-002": "B"},
                "annotator-2": {"comparison-001": "A", "comparison-002": "B"},
                "annotator-3": {"comparison-001": "tie", "comparison-002": "B"},
            }
            for annotator, rows in preferences.items():
                path = root / f"{annotator}.csv"
                answers.append(path)
                with path.open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(
                        handle,
                        fieldnames=[
                            "comparison_id",
                            "annotator_id",
                            "preference",
                            "reason",
                            "presentation_seed",
                            "adjudication_status",
                        ],
                    )
                    writer.writeheader()
                    for comparison_id, preference in rows.items():
                        writer.writerow(
                            {
                                "comparison_id": comparison_id,
                                "annotator_id": annotator,
                                "preference": preference,
                                "reason": "",
                                "presentation_seed": "1",
                                "adjudication_status": "pending",
                            }
                        )
            report = json.loads(score(answers, key))
            self.assertAlmostEqual(report["overall"]["human"]["raw_agreement"], 4 / 6)
            self.assertAlmostEqual(report["overall"]["human"]["fleiss_kappa"], 5 / 11)
            self.assertAlmostEqual(
                report["overall"]["human"]["krippendorff_alpha"], 6 / 11
            )
            self.assertEqual(
                report["overall"]["automatic_judge_agreement"]["same-family"][
                    "majority"
                ]["agreement"],
                1.0,
            )
            self.assertEqual(
                report["overall"]["automatic_judge_agreement"]["cross-family"][
                    "majority"
                ]["comparisons"],
                1,
            )
            self.assertEqual(
                set(report["breakdowns"]),
                {
                    "benchmark",
                    "contrast",
                    "output_length_gap",
                    "automatic_decision_margin",
                },
            )

    def test_two_annotator_staged_preference_and_judge_agreement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key = root / "key.csv"
            judge = {
                "staged-001": "A4",
                "staged-002": "A4",
                "staged-003": "A2",
                "staged-004": "A2",
            }
            with key.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(
                    [
                        "comparison_id",
                        "benchmark",
                        "contrast",
                        "same_family_decision",
                        "condition_a_1",
                        "condition_a_2",
                    ]
                )
                for comparison_id, decision in judge.items():
                    writer.writerow(
                        [comparison_id, "DoLoMiTes", "A4:A2", decision, "A4", "A2"]
                    )
            answers = []
            for annotator, preferences in (
                ("annotator-1", "A A B tie"),
                ("annotator-2", "B A A tie"),
            ):
                path = root / f"answers-{annotator}.csv"
                answers.append(path)
                with path.open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.writer(handle)
                    writer.writerow(
                        ["comparison_id", "annotator_id", "preference", "reason"]
                    )
                    for comparison_id, value in zip(judge, preferences.split()):
                        writer.writerow(
                            [comparison_id, annotator, value, "a, quoted\nreason"]
                        )
            overall = json.loads(score(answers, key))["overall"]
            pair = overall["human"]["annotator_pairs"]["annotator-1|annotator-2"]
            self.assertAlmostEqual(pair["agreement"], 3 / 4)
            self.assertAlmostEqual(pair["cohen_kappa"], 7 / 11)
            primary = overall["automatic_judge_agreement"]["same-family"]
            self.assertAlmostEqual(
                primary["annotators"]["annotator-1"]["agreement"], 3 / 4
            )
            self.assertAlmostEqual(
                primary["annotators"]["annotator-1"]["cohen_kappa"], 0.6
            )
            self.assertAlmostEqual(primary["majority"]["agreement"], 2 / 4)
            preference = overall["preference"]["A4:A2"]
            first = preference["annotators"]["annotator-1"]
            self.assertEqual((first["wins"], first["losses"], first["ties"]), (2, 1, 1))
            self.assertAlmostEqual(first["win_rate"], 2 / 3)
            self.assertAlmostEqual(first["wilson_95"][0], 0.2077, places=3)
            self.assertAlmostEqual(first["wilson_95"][1], 0.9385, places=3)
            majority = preference["majority"]
            self.assertEqual(
                (majority["wins"], majority["losses"], majority["ties"]), (1, 1, 2)
            )
            self.assertEqual(preference["judges"]["same-family"]["wins"], 2)


if __name__ == "__main__":
    unittest.main()
