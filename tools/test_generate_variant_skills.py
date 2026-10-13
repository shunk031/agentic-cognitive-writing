"""Run with: python3 -m pytest tools/test_generate_variant_skills.py -q"""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest

# The generator reads the pre-redesign A4 and role skills; slice 2 of the
# redesign (docs/experiments/redesign/design.md) rebuilds it on the cw template.
pytestmark = pytest.mark.skip(reason="slice 2 rebuilds the generator on cw")

GENERATOR = Path(__file__).resolve().with_name("generate_variant_skills.py")


def test_committed_variants_equal_the_generator_output() -> None:
    generator = runpy.run_path(str(GENERATOR))
    stale = [
        path
        for path, text in generator["outputs"]().items()
        if not path.is_file() or path.read_text(encoding="utf-8") != text
    ]
    assert stale == []


def test_variant_directories_hold_only_generated_files() -> None:
    generator = runpy.run_path(str(GENERATOR))
    assert generator["extra_files"](generator["outputs"]()) == []
