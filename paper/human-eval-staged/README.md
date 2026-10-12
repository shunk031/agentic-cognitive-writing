# Human evaluation: Agentic CogWriter versus Staged

This packet tests the primary pairwise judge against human readers on one contrast: Agentic CogWriter (`A4`) versus the Staged baseline (`A2`), using the outputs of generation run 1. Each annotator opens one offline HTML page, compares 15 blinded pairs, and returns one answer CSV. The selection rule below was fixed and committed before the pairs were drawn.

## Pre-specified selection

The draw uses seed `20260908` and selects 5 pairs per benchmark, 15 pairs in total, with no length cap. Every annotator rates every pair.

**Population.** A prompt is eligible when all of the following hold:

- DoLoMiTes, HelloBench, or WritingBench prompt with a completed canonical `A4` run and a completed canonical `A2` run
- non-empty normalized output on both sides
- primary judge (`gpt-5.6-sol`, pairwise prompt v1) records for both presentation orders, so the order-consistent outcome exists; the outcome is the winner when both orders agree and a tie otherwise

**Language rule.** The annotators read English and Japanese, and no assignment or response in the pool is mainly Japanese. A text counts as mainly Chinese when its Han characters are at least as many as its Latin letters and its kana number fewer than a tenth of its Han characters. The draw excludes a prompt in either of these cases:

- The assignment is mainly Chinese, or its first non-empty line is. The first-line check catches Chinese instructions followed by long English reference material.
- Both responses are mainly Chinese.

A pair with an English assignment and exactly one Chinese response stays eligible. The instructions tell annotators that a response in a language other than the assignment's fails the assignment's language requirement, and that they can judge it so without reading the foreign-language text. Excluding these pairs would bias the sample toward `A4`: among the 18 mixed-language pairs, `A4` wrote the Chinese response in 16 and `A2` in 2. The key records each response's language and a `mixed_language` flag, and the scoring script reports that breakdown.

**Eligible pool.** The language rule removes 33 WritingBench pairs with Chinese assignments and 12 with two Chinese responses, and nothing from DoLoMiTes or HelloBench. The pool holds DoLoMiTes 98, HelloBench 99, and WritingBench 51 pairs, and 18 of the WritingBench pairs are mixed-language.

**Draw.** Within each benchmark, the generator sorts the eligible pairs by prompt identifier and draws a simple random sample with Python's `random.Random(20260908).sample`. The sample is stratified only by benchmark. It does not use judge outcomes, judge margins, lengths, or response languages.

## Blinding and randomization

The pages show the assignment, Response A, Response B, and a pair number. System names, judge outcomes, and lengths stay in [`key.csv`](./key.csv), which annotators must not receive. The generator derives every random choice from the master seed, in this order:

1. Shuffle the selected pairs and number them `pair-001` onward.
2. Per pair and annotator, draw a presentation seed; `A4` is Response A when the seed is even. The key records the seed as `presentation_seed_k` and the Response A condition as `condition_a_k`.
3. Per annotator, draw an order seed and shuffle that annotator's pair order. The key records the display position as `position_k`.

## Files

- [`annotator-1.html`](./annotator-1.html) / [`annotator-2.html`](./annotator-2.html) / [`annotator-3.html`](./annotator-3.html): self-contained form pages that need no network
- [`key.csv`](./key.csv): prompt, benchmark, word counts, estimated minutes, response languages, primary (`same_family_decision`) and cross-family judge outcomes, and per-annotator presentation fields
- [`STUDY-RECORD.md`](./STUDY-RECORD.md): recruitment, consent, and review record for the author to complete

**Form flow.** Each page opens with English and Japanese instructions and the estimated time, followed by a Start button. Each pair then gets its own page:

- a progress bar
- the assignment
- Response A and Response B as Markdown-rendered cards, side by side on wide screens and stacked on narrow ones, each scrolling on its own
- a required A / B / tie question; Next stays disabled until it is answered
- an optional reason field

Answers save automatically to the browser's local storage, so an annotator can close the tab and resume in the same browser. The final page lists every answer, highlights unanswered pairs, and offers Submit. The instruction text is defined in [`human_eval_page.html`](../scripts/human_eval_page.html).

**Answer CSV.** Submit downloads `answers-annotator-k.csv` with the header `comparison_id,annotator_id,preference,reason`. The `preference` column holds `A`, `B`, or `tie`, and an empty value marks an unanswered pair. The file starts with a UTF-8 byte-order mark so that spreadsheet software shows Japanese reasons correctly. When a browser blocks the download, the final page shows the same CSV text for copying.

## Scoring

Save the returned files in this directory and run:

```bash
python3 paper/scripts/score_human_eval.py paper/human-eval-staged/answers-annotator-*.csv --key paper/human-eval-staged/key.csv
```

The JSON report contains an overall block and breakdowns by benchmark and by `mixed_language`:

- **Human preference.** `preference["A4:A2"]` gives W/L/T for `A4` per annotator, pooled over all judgments, and by majority vote. The win rate is W/(W+L) with a Wilson 95% interval, matching the paper's judge win rate. A pair without a unique plurality counts as a majority tie, so with two annotators every disagreement is a tie.
- **Human–human agreement.** `human.annotator_pairs` reports the percent agreement and Cohen's kappa for each annotator pair over the three labels `A4`, `A2`, and tie, together with the pair means. `human.fleiss_kappa` and `human.krippendorff_alpha` cover all annotators.
- **Judge–human agreement.** `automatic_judge_agreement["same-family"]` compares the primary judge's order-consistent outcome with each annotator and with the majority vote. It uses the same percent-agreement and Cohen's-kappa definitions, so it reads directly against the human–human values. The `cross-family` block repeats the comparison for the `claude-sonnet-5` robustness judge.

## Regeneration

From the repository root, with the generation-run-1 run directory as `RUNS_ROOT`:

```bash
uv run --no-project --with markdown-it-py python paper/scripts/make_human_eval.py "$RUNS_ROOT" --seed 20260908 --html-contrast A4:A2 --per-benchmark 5 --output paper/human-eval-staged
```
