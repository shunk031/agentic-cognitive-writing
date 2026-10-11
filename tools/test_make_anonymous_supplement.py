"""Run with: python3 -m pytest tools/test_make_anonymous_supplement.py -q"""

from __future__ import annotations

import runpy
import unittest
from pathlib import Path

SCRIPT = runpy.run_path(
    str(Path(__file__).resolve().with_name("make-anonymous-supplement.py"))
)
REPLACEMENTS = {
    "jane.doe@example.org": "anonymous@example.com",
    "Jane Doe": "Anonymous Authors",
    "janedoe": "anonymous",
}


class AnonymousSupplementTests(unittest.TestCase):
    def test_text_identity_is_replaced_case_insensitively(self):
        text = b"Copyright Jane DOE <jane.doe@example.org>, https://github.com/JaneDoe/repo"
        self.assertEqual(
            SCRIPT["anonymize"](text, REPLACEMENTS),
            b"Copyright Anonymous Authors <anonymous@example.com>, https://github.com/anonymous/repo",
        )

    def test_binary_content_is_left_for_the_scan(self):
        binary = b"\xff\xfeJane Doe"
        self.assertEqual(SCRIPT["anonymize"](binary, REPLACEMENTS), binary)
        self.assertEqual(
            SCRIPT["leaks"]({"fig.pdf": binary}, ["Doe"]), ["fig.pdf:1: 'Doe'"]
        )

    def test_scan_reports_paths_and_partial_names(self):
        self.assertEqual(
            SCRIPT["leaks"]({"a.txt": b"ok\nby J. Doe"}, ["Doe"]), ["a.txt:2: 'Doe'"]
        )
        self.assertEqual(
            SCRIPT["leaks"]({"janedoe/a.txt": b""}, ["janedoe"]),
            ["janedoe/a.txt:0: 'janedoe'"],
        )
        self.assertEqual(SCRIPT["leaks"]({"a.txt": b"anonymous"}, ["Doe"]), [])

    def test_development_paths_are_excluded(self):
        self.assertFalse(SCRIPT["included"](".github/workflows/paper.yml"))
        self.assertFalse(SCRIPT["included"]("paper/HANDOFF.md"))
        self.assertTrue(SCRIPT["included"]("experiments/README.md"))


if __name__ == "__main__":
    unittest.main()
