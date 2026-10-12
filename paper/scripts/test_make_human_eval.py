import random
import unittest

from make_human_eval import (
    BENCHMARKS,
    CONTRASTS,
    PROMPT_LENGTHS,
    _html_page,
    _select_candidates,
    _select_per_benchmark,
    assignment_chinese,
    mainly_chinese,
)


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
        self.assertEqual(
            set(selected), {f"{left}:{right}" for left, right in CONTRASTS}
        )
        self.assertTrue(all(len(rows) == 72 for rows in selected.values()))
        for rows in selected.values():
            self.assertEqual(
                {
                    benchmark: sum(row["benchmark"] == benchmark for row in rows)
                    for benchmark in BENCHMARKS
                },
                {benchmark: 24 for benchmark in BENCHMARKS},
            )
        seen = [
            (row["benchmark"], row["prompt_id"])
            for rows in selected.values()
            for row in rows
        ]
        self.assertEqual(len(seen), len(set(seen)))

    def test_one_contrast_packet_is_balanced_reproducible_and_blinded(self):
        rows = [
            {"benchmark": benchmark, "prompt_id": f"{benchmark}-{index:02d}"}
            for benchmark in BENCHMARKS
            for index in range(40)
        ]
        first = _select_per_benchmark(rows, 5, random.Random(20260908))
        self.assertEqual(
            first,
            _select_per_benchmark(list(reversed(rows)), 5, random.Random(20260908)),
        )
        self.assertEqual(
            {
                benchmark: sum(row["benchmark"] == benchmark for row in first)
                for benchmark in BENCHMARKS
            },
            {benchmark: 5 for benchmark in BENCHMARKS},
        )
        self.assertTrue(mainly_chinese("请帮我写一个论文大纲。"))
        self.assertFalse(mainly_chinese("論文の構成を考えてください。"))
        self.assertFalse(mainly_chinese("Write a report on 智能制造 for the board."))
        self.assertTrue(
            assignment_chinese(
                "请根据下文撰写中文实习报告。\n" + "An English paper body. " * 50
            )
        )
        self.assertFalse(assignment_chinese("Summarize the article.\n" + "文章" * 5))
        page = _html_page(
            "annotator-2",
            [
                {
                    "comparison_id": "pair-001",
                    "assignment": "<b>task</b>",
                    "A": "# Title\n<script>x</script>",
                    "B": "",
                }
            ],
            1.0,
        )
        self.assertIn("<h1>Title</h1>", page)
        self.assertIn("&lt;script&gt;x&lt;/script&gt;", page)
        self.assertIn("&lt;b&gt;task&lt;/b&gt;", page)
        self.assertNotRegex(page, r"__[A-Z]+__")


if __name__ == "__main__":
    unittest.main()
