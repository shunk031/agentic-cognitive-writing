import random
import unittest

from make_human_eval import BENCHMARKS, CONTRASTS, PROMPT_LENGTHS, _select_candidates


class MakeHumanEvalTests(unittest.TestCase):
    def test_three_contrasts_are_balanced_and_do_not_reuse_prompts(self):
        candidates = []
        for contrast_index, (left, right) in enumerate(CONTRASTS):
            for benchmark in BENCHMARKS:
                for index in range(80):
                    candidates.append(
                        {
                            "benchmark": benchmark,
                            "prompt_id": f"{benchmark}-{index}",
                            "contrast": f"{left}:{right}",
                            "prompt_length": PROMPT_LENGTHS[index // 27],
                            "output_length_gap": f"gap-{index % 3}",
                            "automatic_decision_margin": str(index % 2),
                        }
                    )
        selected = _select_candidates(candidates, random.Random(20260929))
        self.assertEqual(set(selected), {f"{left}:{right}" for left, right in CONTRASTS})
        self.assertTrue(all(len(rows) == 72 for rows in selected.values()))
        for contrast, rows in selected.items():
            self.assertEqual({benchmark: sum(row["benchmark"] == benchmark for row in rows) for benchmark in BENCHMARKS}, {benchmark: 24 for benchmark in BENCHMARKS})
        seen = [(row["benchmark"], row["prompt_id"]) for rows in selected.values() for row in rows]
        self.assertEqual(len(seen), len(set(seen)))


if __name__ == "__main__":
    unittest.main()
