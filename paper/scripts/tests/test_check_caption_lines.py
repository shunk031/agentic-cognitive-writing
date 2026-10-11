import importlib.util
import sys
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[2] / "tools" / "check-caption-lines.py"
spec = importlib.util.spec_from_file_location("check_caption_lines", TOOL)
check = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = check
spec.loader.exec_module(check)


def block(last: str, last_width: float, last_start: float = 0.0) -> "check.RenderedBlock":
    return check.RenderedBlock(
        page=1, block=0, segment=0, text="Body text. " + last,
        lines=["Body text continues across the full column width", last],
        widths=[200.0, last_width], starts=[11.0, last_start], ends=[211.0, last_start + last_width],
        x_min=0.0, x_max=211.0,
    )


class RuntTests(unittest.TestCase):
    def test_short_sentence_end_is_runt(self):
        self.assertTrue(check.is_runt(block("potheses.", 36.0)))
        self.assertTrue(check.is_runt(block("quality. 10", 36.0)))

    def test_three_words_filling_most_of_the_line_is_not_runt(self):
        self.assertFalse(check.is_runt(block("document-level control decision.", 130.0)))

    def test_display_math_lead_in_is_not_runt(self):
        self.assertFalse(check.is_runt(block("action space A:", 62.0)))

    def test_right_aligned_table_cell_is_not_runt(self):
        self.assertFalse(check.is_runt(block("0.5%", 20.0, last_start=160.0)))


class MainBodyTests(unittest.TestCase):
    def test_body_runs_through_unnumbered_sections_and_stops_at_references(self):
        texts = ["Introduction", "Limitations", "Ethical Considerations", "References", "Bai et al. 2025."]
        blocks = [block(text, 100.0) for text in texts]
        for item, text in zip(blocks, texts):
            item.text = text
        self.assertEqual([item.text for item in check.main_body(blocks)], texts[:3])


if __name__ == "__main__":
    unittest.main()
