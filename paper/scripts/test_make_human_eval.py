import random
import unittest

from make_human_eval import _select_candidates


class MakeHumanEvalTests(unittest.TestCase):
    def test_contrast_sets_do_not_reuse_prompt_ids(self):
        candidates = []
        for benchmark in ("DoLoMiTes", "HelloBench", "WritingBench"):
            for index in range(20):
                for contrast in ("A4:A5", "A4:A1"):
                    candidates.append({"benchmark": benchmark, "prompt_id": f"{benchmark}-{index}", "contrast": contrast})
        selected = _select_candidates(candidates, random.Random(20260908))
        first = {(row["benchmark"], row["prompt_id"]) for row in selected["A4:A5"]}
        second = {(row["benchmark"], row["prompt_id"]) for row in selected["A4:A1"]}
        self.assertEqual(len(selected["A4:A5"]), 30)
        self.assertEqual(len(selected["A4:A1"]), 30)
        self.assertTrue(first.isdisjoint(second))


if __name__ == "__main__":
    unittest.main()
