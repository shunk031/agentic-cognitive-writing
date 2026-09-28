import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from make_figures import generate, require_number


class FigureSourceTests(unittest.TestCase):
    def test_outputs_are_panelized(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            output_dir = Path(temporary_dir)
            with mock.patch("make_figures.forest_rows", return_value=[]), mock.patch("make_figures.length_values"), mock.patch("make_figures.save_length"), mock.patch("make_figures.cross_family_values", return_value=[]), mock.patch("make_figures.save_cross_family"), mock.patch("make_figures.save_process_sequences_a"), mock.patch("make_figures.save_process_sequences_b"), mock.patch("make_figures.save_process_sequences_c"):
                outputs = generate([{}, {}, {}], [{}, {}, {}], {}, {}, output_dir)
        self.assertEqual([path.name for path in outputs], [
            "confirmatory-forest.pdf",
            "length-control.pdf",
            "cross-family.pdf",
            "process-sequences-a.pdf",
            "process-sequences-b.pdf",
            "process-sequences-c.pdf",
        ])

    def test_missing_field_fails_loudly(self):
        with self.assertRaisesRegex(ValueError, r"cross-family JSON\.win_rate is missing field rate"):
            require_number({}, "rate", "cross-family JSON.win_rate")


if __name__ == "__main__":
    unittest.main()
