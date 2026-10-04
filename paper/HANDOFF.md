# Paper handoff

This note records the public-safe standing rules for the manuscript in this directory.

## Manuscript decisions

- The pre-specified study compares seven writers on the most demanding prompts from WritingBench, HelloBench, and DoLoMiTes; the manuscript also reports a post-hoc exploratory `Single-context` condition used only to test the attribution of the `Single-writer` gap.
- The study uses three independent replications. The confirmatory outcome collapses the two presentation orders to one prompt-level outcome, excludes ties from the exact sign test, and applies Holm correction to the locked benchmark-by-contrast family. The `Single-context` check sits outside that confirmatory family.
- The manuscript distinguishes the `Monitor`, `Planner`, `Translator`, and `Reviewer` agents from the `Planning`, `Translating`, and `Reviewing` processes.
- The coding-agent harness, the instruction-based ablations, and the three benchmark sources are documented in the manuscript and in the repository's experiment protocol.

## Writing rules

These rules come from the author's reviews of earlier drafts; each names a defect class that recurred.

- **Model the venue.** Follow how published ACL and NAACL long-form generation and agent papers phrase each section, and introduce no term those papers do not use. Undefined coinages that confused readers and must not return: "prompt-collapsed outcome", "product quality" or "product-level", "controlled system", "host agent", "component intervention", "matched-output comparison", "realized sequence". Use "ablation", "document quality", and a plain description of the two-order judgment instead.
- **Paragraph writing.** Every body paragraph opens with a topic sentence that states its point and continues with support. A one-sentence paragraph is a defect, and `tools/check-markdown.py` fails on one. A paragraph that starts after a break cannot open with "this" or "these" referring to the previous paragraph.
- **Results paragraphs open with their evidence.** A Results paragraph opens with the figure or table it discusses ("Table 3 shows ..."), states the finding in that sentence, and supports it after. The Discussion cites the same figures and tables.
- **Citations.** Use `\citet` for textual citations so the output reads "Flower and Hayes (1981)", and `\citep` for parenthetical ones. A named theory, system, or benchmark carries its citation at first mention, as in "The cognitive process theory of writing~\citep{flower1981cognitive}". The first sentence of each Introduction paragraph cites the line of work it summarizes, and broad claims cite several papers across the fields involved. Match the citation density of recent ACL and NAACL long-form generation papers; the manuscript currently cites 30 distinct works.
- **Datasets by purpose.** Wherever the benchmarks appear, including the abstract and introduction, say what kind of writing each one tests and why, before or instead of the bare names: "To evaluate X, we use WritingBench~\citep{...}, which covers ...". Describe the hard slice with the facts in [`DESIGN-RATIONALE.md`](DESIGN-RATIONALE.md).
- **Proposal and method.** The abstract and introduction use "we propose Agentic CogWriter". The method section is titled "Agentic CogWriter", opens by introducing the system and pointing to Figure 1, and defines the inputs, outputs, state, and each module formally; the earlier formulation is recorded in [`DESIGN-RATIONALE.md`](DESIGN-RATIONALE.md).
- **Figures and tables.** Figure 1 sits at the top of the right column of page 1 and is cited from the Introduction. Every figure is rendered and inspected after each change. Result tables mark the best score in each column in bold and say "Best scores in bold." in the caption. Narrow tables fit one column; a multi-panel figure uses one PDF per panel arranged with minipages.
- **Placement.** Asides such as the non-comparability of native scores with published numbers go in footnotes, not body sentences. Appendix references name a top-level appendix ("Appendix E"); each appendix topic gets its own top-level appendix section. Avoid "primary" for the pairwise evaluation; motivate pointwise and pairwise evaluation in their own paragraphs instead.

## Build and review rules

- Numbers in the manuscript come from `scripts/make_numbers.py` and the recorded analysis inputs.
- Every source change requires the PDF and Markdown builds, the Markdown checker, and rendering of changed pages with `tools/render-pages.sh`.
- A successful build has zero diagnostics, defined references and citations, and consistent symbol, name, and notation ledgers.
- Public artifacts report tokens and timings where they are study results. They do not publish private operational details or derived prices.
- The human-evaluation packet is retained as a deferred study artifact; raw response passages are not part of the public manuscript commit.

## Source records

- Benchmark selection and licensing are recorded in [`writing-eval-datasets.md`](../docs/research/writing-eval-datasets.md).
- Experimental conditions and analysis rules are recorded in [`protocol.md`](../docs/experiments/protocol.md).
- Prompt materialization and the DoLoMiTes split are recorded in [`prompts/README.md`](../experiments/prompts/README.md).
- The pilot and estimand decision are recorded in [issue 32](https://github.com/shunk031/agentic-cognitive-writing/issues/32).
Operational notes that cannot be committed live in .local/paper-handoff-private.md (gitignored)
