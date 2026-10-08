# Build the manuscript

The build script compiles `acl_latex.tex` with `pdflatex` and `bibtex` in Docker. The first run creates the local image `agentic-cognitive-writing/texlive:latest-small-inconsolata` from the official [`texlive/texlive:latest-small`](https://hub.docker.com/r/texlive/texlive) image and installs the manuscript's missing `inconsolata`, `dblfloatfix`, and `sttools` packages. The latter two packages provide `dblfloatfix.sty` and the bundled `stfloats.sty` for optional double-column float placement during appendix layout tests. The image follows the [TeX Live image repository](https://gitlab.com/islandoftex/images/texlive) scheme layout.

Run one command from `paper/`:

```bash
./tools/build-pdf.sh
```

The script writes the PDF and the `latexmk` log under `build/`, passes `HTTP_PROXY`, `HTTPS_PROXY`, and `NO_PROXY` from the environment to the image build and container, and prints page and warning counts. Remove generated files with:

```bash
./tools/build-pdf.sh --clean
```

## Build Markdown

Run the Markdown build from `paper/` with Docker and `uv` available:

```bash
./tools/build-markdown.sh
```

The [script](./build-markdown.sh) refreshes the PDF build, then uses `pandoc/core:3.6.4` to write [`acl_latex.md`](../build/acl_latex.md). No host Pandoc installation is required. The [preprocessor](./prepare-markdown.py) resolves manuscript inputs, expands [`numbers.tex`](../numbers.tex), and reads cross-reference numbers and ACL natbib author-year labels from the PDF build's auxiliary file. References come from the bibliography that BibTeX generates from [`custom.bib`](../custom.bib) with the manuscript's ACL style.

The rendering retains section order, the abstract, author block, footnotes, table captions, and figure captions. Tables use pipe syntax; spanning headings repeat across their columns. Math uses ASCII in code spans, including policy annotations from braces. Figure drawings are omitted, with captions left at their source positions. References appear after the appendices.

The [checker](./check-markdown.py) writes [`acl_latex.md.check.txt`](../build/acl_latex.md.check.txt) and fails on unresolved control sequences, residue, mismatched section or table counts, or failed numeric spot checks. The report includes ten values from `numbers.tex`, the word count, and the literal wording `N annotators`. Re-run the complete build after source changes so reference numbers match the PDF.
