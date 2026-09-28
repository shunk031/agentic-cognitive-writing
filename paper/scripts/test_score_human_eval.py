import unittest
import csv
import json
import tempfile
from pathlib import Path

from score_human_eval import cohen_kappa, human_to_condition, judge_condition, score


class ScoreHumanEvalTests(unittest.TestCase):
    def test_synthetic_judge_and_human_mapping(self):
        key = {"condition_a": "A4", "contrast": "A4:A1"}
        self.assertEqual(human_to_condition("A", key), "A4")
        self.assertEqual(human_to_condition("B", key), "A1")
        self.assertEqual(
            judge_condition(
                [
                    {"presentation": "A|B", "winner": "A"},
                    {"presentation": "B|A", "winner": "B"},
                ],
                "A4:A1",
            ),
            "A4",
        )

    def test_cohen_kappa(self):
        self.assertAlmostEqual(
            cohen_kappa(["A", "B", "tie", "A"], ["A", "B", "A", "tie"]),
            0.2,
        )

    def test_synthetic_answer_sheet_against_judge_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key = root / "key.csv"
            answers = root / "answers.csv"
            judge = root / "p1-A1" / "scores.jsonl"
            judge.parent.mkdir()
            with key.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["pair_id", "prompt_id", "benchmark", "contrast", "condition_a"])
                writer.writeheader()
                writer.writerow({"pair_id": "pair-001", "prompt_id": "p1", "benchmark": "DoLoMiTes", "contrast": "A4:A1", "condition_a": "A4"})
            with answers.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["pair_id", "annotator", "preference", "confidence", "note"])
                writer.writeheader()
                writer.writerow({"pair_id": "pair-001", "annotator": "ann", "preference": "A", "confidence": "3", "note": ""})
            judge.write_text(json.dumps({"prompt_id": "p1", "presentation": "A|B", "winner": "A"}) + "\n")
            report = score([answers], key, [judge])
            self.assertIn("ann vs judge: 1/1 (100.0%)", report)


if __name__ == "__main__":
    unittest.main()
