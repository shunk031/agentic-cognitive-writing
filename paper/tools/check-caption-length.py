#!/usr/bin/env python3
"""Fail CI when compiled-manuscript captions violate reader-facing constraints."""

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


def manuscript_sources() -> list[Path]:
    """Return TeX sources reachable from the manuscript entry point."""
    pending = [PAPER / "acl_latex.tex"]
    seen: set[Path] = set()
    sources: list[Path] = []
    include_pattern = re.compile(r"\\(?:input|include)\{([^}]+)\}")

    while pending:
        path = pending.pop()
        path = path.resolve()
        if path in seen or not path.exists():
            continue
        seen.add(path)
        sources.append(path)
        text = strip_comments(path.read_text(encoding="utf-8"))
        for target in include_pattern.findall(text):
            relative = Path(target)
            if relative.suffix != ".tex":
                relative = relative.with_suffix(".tex")
            candidates = [PAPER / relative, path.parent / relative]
            child = next((candidate for candidate in candidates if candidate.exists()), None)
            if child is not None:
                pending.append(child)

    return sorted(sources)


def visible_word_count(caption: str) -> int:
    """Approximate rendered prose length while ignoring citation keys and math syntax."""
    text = re.sub(r"\\cite[tp]?\*?(?:\[[^\]]*\])?\{[^{}]*\}", " ", caption)
    text = re.sub(r"\$[^$]*\$", " MATH ", text)
    text = re.sub(r"\\(?:textbf|textit|emph|texttt|mbox)\s*", "", text)
    text = re.sub(r"\\[A-Za-z@]+", " MACRO ", text)
    text = re.sub(r"[{}~^_]", " ", text)
    return len(re.findall(r"\b[A-Za-z0-9]+(?:[-'’][A-Za-z0-9]+)*\b", text))


def first_caption(path: str) -> str:
    found = list(captions((PAPER / path).read_text(encoding="utf-8")))
    assert found, ("expected a caption", path)
    return found[0][0]


def check_semantic_caption_guards() -> None:
    overview = first_caption("fig/tex/overview.tex")
    assert overview.startswith(r"Overview of \condAgenticCogWriter."), (
        "Figure 1 caption must retain the 'Overview of Agentic CogWriter.' lead",
        overview,
    )

    comparison = first_caption("tab/appendix-comparison.tex")
    named_prior_methods = (
        r"Re\$\^3\$",
        r"\bSTORM\b",
        r"\bWriteHERE\b",
        r"\bCogWriter\b",
        r"yang2022re3",
        r"shao2024assisting",
        r"wan2025cognitive",
        r"xiong2025beyond",
    )
    offenders = [pattern for pattern in named_prior_methods if re.search(pattern, comparison)]
    assert not offenders, (
        "Table 1 caption should explain the comparison without naming individual prior methods",
        offenders,
        comparison,
    )


def main() -> None:
    offenders = []
    checked = 0
    for path in manuscript_sources():
        text = path.read_text(encoding="utf-8")
        for caption, line, _ in captions(text):
            checked += 1
            words = visible_word_count(caption)
            if words > MAX_CAPTION_WORDS:
                preview = re.sub(r"\s+", " ", caption).strip()[:120]
                offenders.append((path.relative_to(PAPER), line, words, preview))

    assert checked > 0, "no compiled-manuscript captions found"
    assert not offenders, (
        f"captions must be <= {MAX_CAPTION_WORDS} words",
        offenders,
    )
    check_semantic_caption_guards()
    print(
        f"Caption guard: {checked} compiled captions <= {MAX_CAPTION_WORDS} words; "
        "Figure 1 overview lead and Table 1 generic comparison preserved"
    )


if __name__ == "__main__":
    main()
