# Paper handoff

This note records the public-safe standing rules for the manuscript in this directory.

## Manuscript decisions

- The pre-specified study compares seven writers on the most demanding prompts from WritingBench, HelloBench, and DoLoMiTes; the manuscript also reports a post-hoc exploratory `Single-context` condition used only to test the attribution of the `Single-writer` gap.
- The study uses three independent replications. The confirmatory outcome collapses the two presentation orders to one prompt-level outcome, excludes ties from the exact sign test, and applies Holm correction to the locked benchmark-by-contrast family. The `Single-context` check sits outside that confirmatory family.
- The manuscript distinguishes the `Monitor`, `Planner`, `Translator`, and `Reviewer` agents from the `Planning`, `Translating`, and `Reviewing` processes.
- The coding-agent harness, the instruction-based ablations, and the three benchmark sources are documented in the manuscript and in the repository's experiment protocol.

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
