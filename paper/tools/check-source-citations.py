"""Require source citations when named external datasets, benchmarks, or methods are introduced."""

import re
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]

# Reader-facing source introductions that must stay explicitly attributed.
# Add new externally sourced datasets, benchmarks, or named method-derived
# baselines here when they are introduced into the manuscript.
SOURCE_CITATION_CONTRACTS = (
    ("sec/04_experiments.tex", "WritingBench", "wu2026writingbench"),
    ("sec/04_experiments.tex", "HelloBench", "que2024hellobench"),
    ("sec/04_experiments.tex", "DoLoMiTes", "malaviya2025dolomites"),
    ("acl_latex.tex", "Habermas Machine data", "tessler2024common"),
    ("acl_latex.tex", "CogWriter-style", "wan2025cognitive"),
    ("acl_latex.tex", "STORM-style", "shao2024assisting"),
)


def read(path: str) -> str:
    return (PAPER / path).read_text(encoding="utf-8")


def bibliography_keys() -> set[str]:
    text = "\n".join(read(path) for path in ("custom.bib", "agentic.bib"))
    return set(re.findall(r"@[A-Za-z]+\s*\{\s*([^,\s]+)\s*,", text))


def check() -> None:
    keys = bibliography_keys()
    for path, phrase, citation_key in SOURCE_CITATION_CONTRACTS:
        text = re.sub(r"(?m)%.*$", "", read(path))
        expected = rf"{phrase}~\citep{{{citation_key}}}"
        assert expected in text, (
            "named external datasets, benchmarks, and method-derived baselines must be cited at introduction",
            path,
            phrase,
            citation_key,
        )
        assert citation_key in keys, (
            "required source citation key is missing from the manuscript bibliographies",
            citation_key,
        )

    print("Named external-source citation guards: passed")


if __name__ == "__main__":
    check()
