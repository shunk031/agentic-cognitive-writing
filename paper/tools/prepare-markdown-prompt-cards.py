#!/usr/bin/env python3
"""Run prepare-markdown with prompt-card-aware source expansion."""
import importlib.util
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("prepare_markdown_base", HERE / "prepare-markdown.py")
assert spec and spec.loader
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
PAPER = base.PAPER


def source(path: Path) -> str:
    text = re.sub(r"(?<!\\)%[^\n]*", "", path.read_text(encoding="utf-8"))
    text = re.sub(
        r"\\input\{([^}]+)\}",
        lambda m: source(PAPER.joinpath(*m[1].split("/")).with_suffix(".tex")),
        text,
    )

    def expand_verbatim(match):
        name = match[1]
        if "#" in name:
            return match[0]
        prompt = (PAPER / name).resolve().read_text(encoding="utf-8")
        return "\n\\begin{verbatim}\n" + prompt + "\n\\end{verbatim}\n"

    text = re.sub(
        r"\\VerbatimInput(?:\[[^\]]*\])?\{([^}]+)\}",
        expand_verbatim,
        text,
    )

    pattern = re.compile(r"\\promptinput\s*(?=\{)")
    while match := pattern.search(text):
        _, end = base.group(text, match.end())
        gap = re.match(r"\s*(?=\{)", text[end:])
        assert gap
        title, end = base.group(text, end + gap.end())
        gap = re.match(r"\s*(?=\{)", text[end:])
        assert gap
        name, stop = base.group(text, end + gap.end())
        prompt = (PAPER / name).resolve().read_text(encoding="utf-8")
        replacement = f"\n\\paragraph{{{title}}}\n\\begin{{verbatim}}\n{prompt}\n\\end{{verbatim}}\n"
        text = text[:match.start()] + replacement + text[stop:]
    return text


base.source = source
base.main()
