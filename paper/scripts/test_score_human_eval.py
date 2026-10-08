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
            self.assertAlmostEqual(report["overall"]["human"]["krippendorff_alpha"], 6 / 11)
            self.assertEqual(report["overall"]["automatic_judge_agreement"]["same-family"]["matches"], 2)
            self.assertEqual(report["overall"]["automatic_judge_agreement"]["cross-family"]["comparisons"], 1)
            self.assertEqual(set(report["breakdowns"]), {"benchmark", "contrast", "output_length_gap", "automatic_decision_margin"})


if __name__ == "__main__":
    unittest.main()
