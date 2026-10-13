"""Run with: python3 -m pytest tools/test_generate_variant_skills.py -q"""

from __future__ import annotations

import runpy
from pathlib import Path

GENERATOR = Path(__file__).resolve().with_name("generate_variant_skills.py")


def test_committed_variants_equal_the_generator_output() -> None:
    generator = runpy.run_path(str(GENERATOR))
    stale = [
        path
        for path, text in generator["outputs"]().items()
        if not path.is_file() or path.read_text(encoding="utf-8") != text
    ]
    assert stale == []
