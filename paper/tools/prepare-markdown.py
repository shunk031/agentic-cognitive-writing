"""Normalize manuscript constructs that Pandoc's LaTeX reader cannot retain."""

import re
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]


def group(text, start):
    """Read a balanced TeX brace group, including nested macro arguments."""
    assert text[start] == "{", text[start : start + 40]
    depth = 1
    pos = start + 1
    while depth:
        if text[pos] == "\\":
            pos += 2
            continue
        depth += (text[pos] == "{") - (text[pos] == "}")
        pos += 1
    return text[start + 1 : pos - 1], pos


def commands(text, name, transform):
    pattern = re.compile(r"\\" + name + r"\s*(?=\{)")
    while match := pattern.search(text):
        value, end = group(text, match.end())
        text = text[: match.start()] + transform(value) + text[end:]
    return text


def epigraph_blocks(text):
    pattern = re.compile(r"\\epigraph\s*(?=\{)")
    while match := pattern.search(text):
        quotation, end = group(text, match.end())
        attribution_start = re.match(r"\s*(?=\{)", text[end:])
        assert attribution_start, text[match.start() : match.start() + 120]
        attribution, stop = group(text, end + attribution_start.end())
        replacement = (
            f"\n\n\\begin{{quote}}\n{quotation}\n\n"
            f"{attribution}\n\\end{{quote}}\n\n"
        )
        text = text[: match.start()] + replacement + text[stop:]
    return text


def source(path):
    text = re.sub(r"(?<!\\)%[^\n]*", "", path.read_text())
    text = re.sub(
        r"\\input\{([^}]+)\}",
        lambda m: source(PAPER.joinpath(*m[1].split("/")).with_suffix(".tex")),
        text,
    )

    def verbatim_input(match):
        prompt_path = (PAPER / match[1]).resolve()
        prompt = prompt_path.read_text()
        return "\n\\begin{verbatim}\n" + prompt + "\n\\end{verbatim}\n"

    return re.sub(
        r"\\VerbatimInput(?:\[[^\]]*\])?\{([^}]+)\}",
        verbatim_input,
        text,
    )


def math_ascii(text):
    notes = []
    pattern = re.compile(r"\\(?:underbrace|overbrace)\s*(?=\{)")
    while match := pattern.search(text):
        value, end = group(text, match.end())
        suffix = re.match(r"\s*[_^]\s*", text[end:])
        if suffix:
            note, stop = group(text, end + suffix.end())
            notes.append(math_ascii(note))
            end = stop
        text = text[: match.start()] + value + text[end:]

    replacements = {
        "pi": "pi",
        "sigma": "sigma",
        "rightarrow": " -> ",
        "uparrow": "↑",
        "in": " in ",
        "times": " x ",
        "checkmark": "yes",
        "quad": " ",
        "qquad": " ",
        "ldots": "...",
        "cdots": "...",
        "dots": "...",
    }
    text = re.sub(
        r"\\([A-Za-z]+)",
        lambda m: replacements.get(m[1], m[0]),
        text,
    )
    for name in ("mathrm", "text", "texttt", "mathclap", "mathbf", "mathcal"):
        text = commands(text, name, lambda value: value)

    unknown = re.search(r"\\([A-Za-z]+)", text)
    if unknown:
        raise KeyError(unknown[1])

    text = text.replace(r"\{", "(").replace(r"\}", ")")
    text = re.sub(
        r"([_^])\{([^{}]+)\}",
        lambda m: m[1] + ("(" + m[2] + ")" if "+" in m[2] else m[2]),
        text,
    )
    text = text.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", text).strip() + "".join(
        f" [{note}]" for note in notes
    )


def main():
    text = source(PAPER / "acl_latex.tex")
    title = group(text, text.index("{", text.index(r"\title")))[0]
    author = group(text, text.index("{", text.index(r"\author")))[0]
    definitions = {}
    numbers = source(PAPER / "numbers.tex")
    for match in re.finditer(r"\\newcommand\{\\([A-Za-z]+)\}", numbers):
        definitions[match[1]] = group(numbers, match.end())[0]
    preamble = text.split(r"\begin{document}", 1)[0]
    for match in re.finditer(
        r"\\newcommand\{\\((?:cond|model)[A-Za-z]+)\}(?:\[[^\]]+\])?\s*(?=\{)",
        preamble,
    ):
        definitions[match[1]] = group(preamble, match.end())[0]

    text = text.split(r"\begin{document}", 1)[1].split(r"\end{document}", 1)[0]
    text = "\\section*{" + title + "}\n" + author + "\n" + text
    text = epigraph_blocks(text)

    verbatim_blocks = []

    def stash_verbatim(match):
        token = f"VERBATIMBLOCKTOKEN{len(verbatim_blocks)}ENDTOKEN"
        verbatim_blocks.append(match[0])
        return token

    text = re.sub(
        r"\\begin\{verbatim\}.*?\\end\{verbatim\}",
        stash_verbatim,
        text,
        flags=re.DOTALL,
    )

    text = re.sub(r"\\([A-Za-z]+)", lambda m: definitions.get(m[1], m[0]), text)
    aux = (PAPER / "build" / "acl_latex.aux").read_text()
    labels = dict(re.findall(r"\\newlabel\{([^}]+)\}\{\{([^}]+)\}", aux))
    citations = {}
    for key, year, author in re.findall(
        r"\\bibcite\{([^}]+)\}\{\{[^{}]*\}\{((?:[^{}]|\{[^{}]*\})*)\}\{\{([^{}]*)\}\}",
        aux,
    ):
        year = re.sub(r"\{\\natexlab\{([^}]+)\}\}", r"\1", year)
        citations[key] = (author, year)

    def citation(match):
        entries = [citations[key.strip()] for key in match[2].split(",")]
        if match[1] == "citet":
            return "; ".join(f"{author} ({year})" for author, year in entries)
        return "(" + "; ".join(f"{author}, {year}" for author, year in entries) + ")"

    text = re.sub(r"\\(cite|citep|citet)\{([^}]+)\}", citation, text)
    text = re.sub(r"\\ref\{([^}]+)\}", lambda m: labels[m[1]], text)

    def float_body(match):
        kind, body = match[1], match[2]
        captions = []
        for caption_match in re.finditer(r"\\caption(?:of\{figure\})?\s*(?=\{)", body):
            caption, _ = group(body, caption_match.end())
            captions.append(caption)
        figure_labels = re.findall(r"\\label\{([^}]+)\}", body)
        if len(captions) != len(figure_labels):
            raise ValueError(
                f"{kind} captions and labels differ: {len(captions)} vs {len(figure_labels)}"
            )
        if kind.startswith("figure"):
            rendered = []
            for caption, label in zip(captions, figure_labels):
                rendered.append(f"Figure {labels[label]}. {caption}")
            return "\n\n" + "\n\n".join(rendered) + "\n\n"
        caption, label = captions[0], figure_labels[0]
        prefix = "Table " + labels[label] + ". "
        table = re.search(r"\\begin\{tabular\}.*?\\end\{tabular\}", body, re.DOTALL)[0]
        table = re.sub(r"\\cmidrule(?:\([^)]*\))?\{[^}]*\}", "", table)
        for name in ("lcell", "ccell", "shortstack"):
            table = commands(table, name, lambda value: value.replace(r"\\", "; "))
        pattern = re.compile(r"\\multicolumn\{(\d+)\}\{[^}]*\}")
        while span := pattern.search(table):
            value, end = group(table, span.end())
            table = table[: span.start()] + " & ".join([value] * int(span[1])) + table[end:]
        return "\n\n" + table + "\n\n" + prefix + caption + "\n\n"

    text = re.sub(
        r"\\begin\{(table\*?|figure\*?)\}(.*?)\\end\{\1\}",
        float_body,
        text,
        flags=re.DOTALL,
    )
    text = re.sub(r"\\label\{[^}]+\}", "", text)
    text = text.replace(r"\maketitle", "").replace(r"\appendix", "")
    text = text.replace(r"\begin{abstract}", r"\section*{Abstract}").replace(r"\end{abstract}", "")
    text = re.sub(r"\\bibliography\{[^}]+\}", "", text)
    bbl = (PAPER / "build" / "acl_latex.bbl").read_text()
    entries = re.split(r"\\bibitem\[.*?\]\{[^}]+\}", bbl, flags=re.DOTALL)[1:]
    bibliography = "\n\n".join(entries).replace(r"\end{thebibliography}", "").replace(r"\newblock", "")
    text += "\n\\section*{References}\n" + bibliography
    for name, value in {
        "yes": "yes",
        "no": "–",
        "partly": "Partial",
        "checkmark": "yes",
    }.items():
        text = re.sub(r"\\" + name + r"\b(?:\{\})?", lambda _, value=value: value, text)

    text = commands(text, "textsuperscript", lambda value: r"\texttt{" + value + "}")

    def math_code(value):
        value = math_ascii(value).replace("_", r"\_").replace("%", r"\%")
        return r"\texttt{" + value + "}"

    text = re.sub(
        r"\\begin\{equation\}(.*?)\\end\{equation\}",
        lambda m: "\n\n" + math_code(m[1]) + "\n\n",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"(?<!\\)\$([^$]*?)(?<!\\)\$",
        lambda m: math_code(m[1]),
        text,
        flags=re.DOTALL,
    )
    text = text.replace("~", " ").replace("---", "—").replace("--", "–")

    for index, block in enumerate(verbatim_blocks):
        text = text.replace(f"VERBATIMBLOCKTOKEN{index}ENDTOKEN", block)

    (PAPER / "build" / "markdown-source.tex").write_text(text)


if __name__ == "__main__":
    main()
