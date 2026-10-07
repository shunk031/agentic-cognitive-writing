#!/usr/bin/env python3
"""Fail CI when a manuscript caption exceeds the reader-facing length cap."""

from __future__ import annotations

import re
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
MAX_CAPTION_WORDS = 70


def strip_comments(text: str) -> str:
    return re.sub(r"(?m)(?<!\\)%.*$", "", text)


def extract_braced(text: str, start: int) -> tuple[str, int]:
    """Return the balanced-brace payload beginning at text[start] == '{'."""
    assert text[start] == "{"
    depth = 0
    payload_start = start + 1
    for index in range(start, len(text)):
        char = text[index]
        if char == "{" and (index == 0 or text[index - 1] != "\\"):
            depth += 1
        elif char == "}" and (index == 0 or text[index - 1] != "\\"):
            depth -= 1
            if depth == 0:
                return text[payload_start:index], index + 1
    raise AssertionError("unclosed caption brace")


def captions(text: str):
    """Yield caption payloads, including optional short-caption syntax."""
    cleaned = strip_comments(text)
    pattern = re.compile(r"\\caption(?:\[[^\]]*\])?\s*\{")
    for match in pattern.finditer(cleaned):
        brace = match.end() - 1
        payload, end = extract_braced(cleaned, brace)
        line = cleaned.count("\n", 0, match.start()) + 1
        yield payload, line, end


def visible_word_count(caption: str) -> int:
    """Approximate rendered prose length while ignoring citation keys and math syntax."""
    text = re.sub(r"\\cite[tp]?\*?(?:\[[^\]]*\])?\{[^{}]*\}", " ", caption)
    text = re.sub(r"\$[^$]*\$", " MATH ", text)
    text = re.sub(r"\\(?:textbf|textit|emph|texttt|mbox)\s*", "", text)
    text = re.sub(r"\\[A-Za-z@]+", " MACRO ", text)
    text = re.sub(r"[{}~^_]", " ", text)
    return len(re.findall(r"\b[A-Za-z0-9]+(?:[-'’][A-Za-z0-9]+)*\b", text))


def main() -> None:
    offenders = []
    checked = 0
    for path in sorted(PAPER.rglob("*.tex")):
        text = path.read_text(encoding="utf-8")
        for caption, line, _ in captions(text):
            checked += 1
            words = visible_word_count(caption)
            if words > MAX_CAPTION_WORDS:
                preview = re.sub(r"\s+", " ", caption).strip()[:120]
                offenders.append((path.relative_to(PAPER), line, words, preview))

    assert checked > 0, "no manuscript captions found"
    assert not offenders, (
        f"captions must be <= {MAX_CAPTION_WORDS} words",
        offenders,
    )
    print(f"Caption length guard: {checked} captions <= {MAX_CAPTION_WORDS} words")


if __name__ == "__main__":
    main()
