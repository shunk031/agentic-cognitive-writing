# Dataset and benchmark survey for large language model (LLM) long-form writing quality evaluation

## Summary

This survey selects benchmarks and a judge setup for this repository's long-form writing experiment. The experiment compares six ways of producing long-form text with an LLM writing agent, from single-shot generation and linear pipelines to a cognitive-theory-based plugin and its two variants. See `docs/experiments/protocol.md` for the full condition definitions.

Answer: use exactly three primary benchmarks.

- WritingBench [^3] covers general-purpose writing. WritingBench has 1,000 real-world writing queries across 6 domains and 100 subdomains. Each query has 5 criteria. [Repo](https://github.com/X-PLUG/WritingBench) / [benchmark data](https://github.com/X-PLUG/WritingBench/blob/main/benchmark_query/benchmark_all.jsonl) / [evaluation prompt](https://github.com/X-PLUG/WritingBench/blob/main/prompt.py)
- HelloBench [^4] targets long text generation. HelloBench has 647 samples across 5 tasks and 38 subcategories. HelloBench selects or wraps question answering (QA), summarization, chat, completion, and heuristic generation for long text generation. [Repo](https://github.com/Quehry/HelloBench) / [judge code](https://github.com/Quehry/HelloBench/blob/main/llm_judge.py)
- DoLoMiTes [^7] is the closest surveyed match for structured expert writing because it uses expert-authored methodical tasks. DoLoMiTes fits research plans, reports, and design documents better than fiction-heavy benchmarks. [Repo](https://github.com/google-deepmind/dolomites) / [task data](https://dolomites-benchmark.s3.us-west-2.amazonaws.com/dolomites_tasks_anon.jsonl) / [examples archive](https://dolomites-benchmark.s3.us-west-2.amazonaws.com/dolomites_examples.zip)

Run rubric pointwise scoring plus balanced pairwise comparison.

Use PERSUADE 2.0 [^19] and International Corpus of Learner English++ (ICLE++) [^5] as prompt-source and human-anchor datasets, not as primary benchmarks. A prompt-source dataset supplies task prompts. A human-anchor dataset supplies human scores or traits for calibration. PERSUADE 2.0 provides argumentative prompts and human score distributions. ICLE++ provides persuasive-essay trait scores outside Automated Student Assessment Prize (ASAP) [^21].

Use the PERSUADE 2.0 [repo](https://github.com/scrosseye/persuade_corpus_2.0) and [Zenodo record](https://zenodo.org/records/8221504), plus the ICLE++ [repo](https://github.com/samlee946/ICLE-PlusPlus), when building calibration prompts.

Keep LongBench-Write [^6] outside the primary benchmark set, and use it only as an optional length-control axis after the team clears benchmark prompt-file license and provenance. A length-control axis tests whether results hold across target output lengths.

The planned comparison has 6 conditions. The settled condition specification lives in `docs/experiments/protocol.md`.

- A1: single-shot generation
- A2: linear Pre-Write/Write/Re-Write
- A3: Synthesis of Topic Outlines through Retrieval and Multi-perspective Question Asking (STORM) [^2]-style linear pipeline without retrieval
- A4: `cognitive-writing`, the cognitive-writing skill where the Monitor coordinates Planner, Translator, and Reviewer role skills
- A5: `cognitive-writing-no-goal-network`, the cognitive-writing ablation that removes the explicit goal network
- A6: `cognitive-writing-fixed-order`, the cognitive-writing ablation that keeps the goal network and prescribes process order

All conditions receive the same input context and no condition uses web access or retrieval.

Use at least two judge families. Each prompt has 15 condition pairs and 30 A/B plus B/A judgments per judge. Validate the automatic judges with about 180-240 human comparisons and 3 annotators per comparison.

Separate product quality from process analysis. Judges should see final outputs only. Analyze planning traces, revision behavior, goal references, and Monitor transitions separately.

## Long-form, creative, and general writing benchmarks

WritingBench [^3], HelloBench [^4], and DoLoMiTes [^7] are the primary benchmark choices; the other benchmarks are secondary, supplementary, or blocked by license/provenance risk.

| Benchmark | task types / prompt count | output length range | evaluation method | license | agentic system fairness |
|---|---|---|---|---|---|
| WritingBench [^3] | 1,000 real-world writing queries<br>6 primary domains<br>100 subdomains<br>First release: 1,239 queries<br>Later update: 1,000 reduced/curated queries<br>Domains: Academic & Engineering, Finance & Business, Politics & Law, Literature & Art, Education, Advertising & Marketing<br>Sources: [repo](https://github.com/X-PLUG/WritingBench) / [benchmark data](https://github.com/X-PLUG/WritingBench/blob/main/benchmark_query/benchmark_all.jsonl) | Average query length is 1,500+ tokens.<br>Generation config recommends max_length 16,000 or max allowed.<br>Source: [README](https://github.com/X-PLUG/WritingBench#-whats-new) | Each query has 5 instance-specific criteria.<br>The evaluator assigns a 1-10 score and reason per criterion.<br>The code supports Claude or critic model.<br>Sources: [evaluation prompt](https://github.com/X-PLUG/WritingBench/blob/main/prompt.py) / [evaluation script](https://github.com/X-PLUG/WritingBench/blob/main/evaluate_benchmark.py) | Repository LICENSE is Apache-2.0.<br>Source: [license](https://github.com/X-PLUG/WritingBench/blob/main/LICENSE) | We expect high fairness because each condition can submit a final response to the same query. If judges do not see internal traces, single-shot and agentic systems face the same product-level condition. |
| HelloBench / HelloEval [^4] | 647 testing samples<br>5 tasks<br>38 subcategories<br>The benchmark is dedicated to long text generation.<br>Task types selected or wrapped for long text generation: open-ended QA, summarization, chat, text completion, and heuristic text generation<br>Source: [repo](https://github.com/Quehry/HelloBench) | HelloBench selects/wraps tasks for long text generation.<br>Length-constrained heuristic generation includes 2k/4k/8k/16k variants in README.<br>Source: [README](https://github.com/Quehry/HelloBench#repository-contents) | HelloEval uses checklist-wise scoring from 0 to 1.<br>HelloEval reports an overall LLM eval score from 0-10.<br>The code runs GPT-4o three retries and stores checklist-wise evaluations.<br>Sources: [judge code](https://github.com/Quehry/HelloBench/blob/main/llm_judge.py) / [regression code](https://github.com/Quehry/HelloBench/blob/main/regression.py) | Repository LICENSE is Massachusetts Institute of Technology (MIT).<br>Source: [license](https://github.com/Quehry/HelloBench/blob/main/LICENSE) | We expect high fairness because long-output requirements should expose planner/reviewer effects. Main caveat: summarization and chat tasks can have long input context. Fix context windows and retrieval handling across conditions. |
| LongBench-Write / LongWrite-Ruler / LongWriter [^6] | LongWriter repo introduces LongBench-Write and LongWrite-Ruler.<br>Raw evaluation files contain 120 LongBench-Write prompts, 60 English subset prompts, and 48 LongWrite-Ruler prompts.<br>Sources: [repo](https://github.com/THUDM/LongWriter) / [LongBench-Write data](https://github.com/THUDM/LongWriter/blob/main/evaluation/longbench_write.jsonl) / [LongWrite-Ruler data](https://github.com/THUDM/LongWriter/blob/main/evaluation/longwrite_ruler.jsonl) | LongWriter-6k Supervised Fine-Tuning (SFT) data ranges 2k-32k words.<br>That license label applies to the SFT dataset, not automatically to benchmark prompt files.<br>Sources: [SFT data](https://huggingface.co/datasets/THUDM/LongWriter-6k) / [English evaluation data](https://github.com/THUDM/LongWriter/blob/main/evaluation/longbench_write_en.jsonl) | Quality score uses GPT-4o judge over Relevance, Accuracy, Coherence, Clarity, Breadth and Depth, and Reading Experience. Each dimension uses 1-5.<br>The script computes the length score separately from requested vs produced length.<br>The quality prompt explicitly excludes length compliance.<br>Sources: [quality script](https://github.com/THUDM/LongWriter/blob/main/evaluation/eval_quality.py) / [length script](https://github.com/THUDM/LongWriter/blob/main/evaluation/eval_length.py) / [judge prompt](https://github.com/THUDM/LongWriter/blob/main/evaluation/judge.txt) | Benchmark-file license/provenance remains unresolved.<br>The repository does not publish a license file in the expected GitHub LICENSE path.<br>The Hugging Face (HF) Apache-2.0 label covers LongWriter-6k SFT data rather than the `evaluation/*.jsonl` benchmark prompt files.<br>Before use, clear:<br>License for `evaluation/longbench_write*.jsonl` and `longwrite_ruler.jsonl`<br>Provenance of prompts and whether redistribution is allowed<br>Whether derived benchmark results can be published | After clearance, use it only for supplementary analysis of target output length.<br>Do not count it among the 3 primary benchmarks. |
| EQ-Bench Creative Writing v3 [^20] | 32 prompts × 3 iterations = 96 items.<br>Genres include historical fiction, epistolary, romance, comedy, and horror.<br>Sources: [repo](https://github.com/EQ-bench/creative-writing-bench) / [prompts](https://github.com/EQ-bench/creative-writing-bench/blob/main/data/creative_writing_prompts_v3.json) | Prompt examples commonly request about 1,000 words.<br>The harness truncates outputs to 4,000 characters for length-bias mitigation according to README.<br>Sources: [repo](https://github.com/EQ-bench/creative-writing-bench) / [judge prompt](https://github.com/EQ-bench/creative-writing-bench/blob/main/data/creative_writing_judging_prompt.txt) | Hybrid rubric score plus pairwise Elo/Glicko-2.<br>README states Sonnet 4.6 for leaderboard parity.<br>README lists mitigations for length, position, and verbosity/poetic incoherence.<br>Sources: [repo](https://github.com/EQ-bench/creative-writing-bench) / [script](https://github.com/EQ-bench/creative-writing-bench/blob/main/creative_writing_bench.py) | The repository does not publish a license file at the listed license URL. Confirm the license with the maintainers or repository metadata before using it. | We expect medium fit because creative writing is central, but 32 prompts is small and Elo requires historical run files for comparability. Use it as a secondary benchmark for subjective/literary quality. |
| WildBench v2 [^17] writing-relevant subset | HF dataset v2 has 1,024 test examples.<br>V2-hard has 256 examples.<br>Fields include `checklist`, `primary_tag`, `secondary_tags`, and `intent`.<br>Sources: [HF data](https://huggingface.co/datasets/allenai/WildBench) / [repo](https://github.com/allenai/WildBench) | Not a pure long-form benchmark.<br>The WildBench authors collected real-user tasks, including long and writing-like tasks.<br>Source: [repo](https://github.com/allenai/WildBench) | V2 uses 5-10 example-specific checklist questions, GPT-4-turbo scoring, pairwise reward, and length-penalized Elo/reward-mix.<br>Sources: [repo](https://github.com/allenai/WildBench) / [HF data](https://huggingface.co/datasets/allenai/WildBench) | HF card says Creative Commons Attribution (CC BY) 4.0 for dataset.<br>Repo LICENSE is Apache-2.0.<br>Sources: [HF data](https://huggingface.co/datasets/allenai/WildBench) / [license](https://github.com/allenai/WildBench/blob/main/LICENSE) | We expect medium fit because real-user diversity is useful, but writing tasks must be filtered by `primary_tag`/`intent`. Otherwise the benchmark measures broad assistant behavior rather than writing quality. |
| DoLoMiTes [^7] | 519 methodical tasks from 266 experts across 25 fields.<br>1,857 expert post-edited examples.<br>The sources disagree on split size.<br>Paper/archive-derived reporting gives 820 dev / 1,037 test.<br>Repo README says 830 dev examples and 1,037 test examples.<br>Use 820/1,037 only after recomputing from the released archive in the experiment repository.<br>Sources: [released archive](https://dolomites-benchmark.s3.us-west-2.amazonaws.com/dolomites_examples.zip) / [conflicting README](https://github.com/google-deepmind/dolomites/blob/main/README.md) | Reference outputs average 341.42 tokens.<br>Tasks are methodical long-form writing with structured output sections.<br>Generation uses up to 4,096 tokens.<br>Source: [repo](https://github.com/google-deepmind/dolomites) | Evaluation includes pairwise language model (LM) preference against GPT-4 and fine-grained 1-5 absolute evaluation.<br>Absolute dimensions are task adherence, factual correctness, depth, completeness, and coherence.<br>Human validation used 200 pairs.<br>Two annotators agreed on 75% of 100 examples.<br>Claude-3 Opus agreement was 67% with ties and 77% without ties.<br>Source: [repo](https://github.com/google-deepmind/dolomites) | Software Apache-2.0.<br>Other materials CC-BY 4.0.<br>Source: [README](https://github.com/google-deepmind/dolomites/blob/main/README.md) | We expect high fit for research/report tasks because DoLoMiTes uses structured expert tasks. We expect medium fit for creative writing because the task set is not fiction-centered. |
| WritingPreferenceBench [^8] | 1,800 human-validated preference pairs<br>1,200 English pairs<br>600 Chinese pairs<br>8 creative writing genres<br>51 categories<br>Sources: [project](https://WritingPreferenceBench.github.io/) / [HF data](https://huggingface.co/datasets/m-a-p/Writing-Preference-Bench) / [repo](https://github.com/WritingPreferenceBench/Writing-Preference-Bench) | The HF card and repo report mean response lengths around 1,450 words for English chosen and 840 for English rejected.<br>Pair data include completion_tokens and word_len.<br>Sources: [HF data](https://huggingface.co/datasets/m-a-p/Writing-Preference-Bench) / [repo](https://github.com/WritingPreferenceBench/Writing-Preference-Bench) | Construction uses human-in-the-loop preference construction, 11 expert annotators, 8-hour rubric calibration, a 0-3 creative-writing scale, and retained pairs with >=2/3 agreement and score gap >=1.<br>LLM-as-judge chooses the preferred response based on creativity, emotional resonance, and stylistic flair.<br>Sources: [HF data](https://huggingface.co/datasets/m-a-p/Writing-Preference-Bench) / [repo](https://github.com/WritingPreferenceBench/Writing-Preference-Bench) | License metadata disagrees.<br>GitHub README says Open Data Commons Attribution License (ODC-BY).<br>HF metadata says Apache-2.0.<br>Resolve the license before redistribution.<br>Sources: [repo](https://github.com/WritingPreferenceBench/Writing-Preference-Bench) / [HF data](https://huggingface.co/datasets/m-a-p/Writing-Preference-Bench) | We expect medium fit as a primary benchmark because WritingPreferenceBench validates judge sensitivity to subjective style, but WritingPreferenceBench is not a clean generation benchmark. WritingPreferenceBench labels are preference pairs of existing model outputs. |
| LongGenBench [^9] | LongGenBench evaluates long-form generation in long-context language models.<br>LongGenBench uses four scenarios.<br>Prompt lengths are 16K/32K.<br>Task examples include urban planning, diary entries, and menu-planning-like constrained long outputs.<br>Sources: [repo](https://github.com/mozhu621/LongGenBench) / [HF data](https://huggingface.co/datasets/mozhu/LongGenBench) | Focus is long-context prompt instruction following, not only output length.<br>HF license is Creative Commons Attribution-NoDerivatives (CC BY-ND) 4.0.<br>Sources: [repo](https://github.com/mozhu621/LongGenBench) / [HF data](https://huggingface.co/datasets/mozhu/LongGenBench) | Repo has evaluation scripts under `Evalution`.<br>The detailed judge rubric needs further inspection before use.<br>Source: [repo](https://github.com/mozhu621/LongGenBench) | HF card says CC-BY-ND-4.0.<br>Source: [HF data](https://huggingface.co/datasets/mozhu/LongGenBench) | We expect medium-low fit as a primary benchmark because LongGenBench stresses long instruction adherence more than writing process quality. Use LongGenBench only for supplementary robustness. |
| LongJudgeBench [^10] | Not a generation benchmark.<br>LongJudgeBench is a 2026 meta-evaluation benchmark for LLM-as-a-judge on long-form outputs.<br>LongJudgeBench has 6 datasets, pointwise/pairwise/listwise protocols, 4 prompt modes, and 8 judge models.<br>Source: [repo](https://github.com/cjj826/LongJudgeBench) | Documents range from avg 3,053 to 28,758 tokens depending on source dataset.<br>Source: [repo](https://github.com/cjj826/LongJudgeBench) | Metrics include pairwise accuracy (ACC), Spearman, and Kendall's tau. Prompt modes include vanilla, rubric, reference, and rubric+reference. README reports that rubric/reference can help or hurt depending on task.<br>Sources: [repo](https://github.com/cjj826/LongJudgeBench) / [reliability script](https://github.com/cjj826/LongJudgeBench/blob/main/src/evaluation/compute_reliability.py) | Repository LICENSE is MIT.<br>Source: [license](https://github.com/cjj826/LongJudgeBench/blob/main/LICENSE) | We expect LongJudgeBench to work for judge validation only. LongJudgeBench should not replace product-quality benchmarks, but LongJudgeBench directly informs judge choice for long outputs. |

## Essay and argumentative writing datasets with quality annotations

Use essay datasets as prompt sources and human-score references, not as primary generation benchmarks.

| Dataset | claims and sources | usefulness for this paper |
|---|---|---|
| ASAP Automated Essay Scoring (ASAP AES) [^21] | Kaggle hosts "The Hewlett Foundation: Automated Essay Scoring" competition page for student-written essay scoring.<br>Source: [Kaggle data page](https://www.kaggle.com/c/asap-aes/data)<br>The widely used AES setup is often described as 8 prompts and about 13k essays with human scores, but the exact count and license need confirmation from a direct readable source. | Use as a prompt source and historical AES baseline only. Access often requires Kaggle terms, so do not make it a primary reproducibility dependency unless the paper can state the access terms clearly. |
| PERSUADE 2.0 [^19] | Over 25,000 argumentative essays from United States grades 6-12<br>15 prompts<br>Two writing tasks: independent and source-based.<br>Provides holistic essay scores and discourse/argumentative element effectiveness scores.<br>Sources: [repo](https://github.com/scrosseye/persuade_corpus_2.0) / [Zenodo record](https://zenodo.org/records/8221504) | Strong prompt-source dataset and human-quality anchor. PERSUADE 2.0 gives realistic argumentative prompts and a distribution of student quality, but use a new rubric to judge generated LLM outputs because student-score scales are not directly comparable to LLM long-form quality. |
| ICLE / ICLE++ [^5] | ICLE++ is a corpus of persuasive student essays annotated with holistic and trait-specific scores. ICLE++ tests generalization beyond Automated Student Assessment Prize (ASAP) [^21] and supports multi-trait/cross-prompt AES.<br>Source: [repo](https://github.com/samlee946/ICLE-PlusPlus) | Good held-out human-quality anchor outside ASAP and PERSUADE 2.0 [^19]. Use ICLE++ to calibrate rubrics on persuasive writing traits, not as a main generation benchmark unless ICLE base-text access/license is cleared. |
| ArgRewrite V.2 [^11] | Annotated argumentative revisions corpus.<br>ArgRewrite V.2 studies student interactions with a natural language processing (NLP)-based revision assistant and whether feedback forms encourage effective revisions.<br>Source: [repo](https://github.com/omidkashefi/ArgRewrite) | Process-level precedent rather than prompt bank. Useful for defining revision intent categories and for evaluating whether our reviewer/monitor produces useful revision operations. |
| Revision Quality Prediction [^12] | Predicts whether argumentative revisions are successful.<br>Revision Quality Prediction uses annotated elementary essays and a college revision desirability corpus.<br>Code asks users to obtain data from PETAL Pittsburgh.<br>Sources: [repo](https://github.com/ZhexiongLiu/Revision-Quality-Prediction) / [PETAL data page](https://petal-cs-pitt.github.io/data.html) | Useful for process trace analysis. Compare agent reviewer actions against human notions of successful argument revision. Revision Quality Prediction is not a primary product-quality benchmark. |

## LLM-as-judge methodology for writing quality

The judge design should pair rubric scoring with balanced pairwise comparisons, then validate the automatic judges against a human validation sample.

### Biases and mitigations

- MT-Bench / Chatbot Arena [^13] paper identifies position bias, verbosity bias, self-enhancement bias, and limited reasoning ability.

  GPT-4 matched human preferences above 80% agreement in their studied setup. The released setup included 80 MT-Bench questions, 3K expert votes, and 30K arena conversations.

  Source: [FastChat judge code](https://github.com/lm-sys/FastChat/tree/main/fastchat/llm_judge)
- The judge prompt file in the FastChat repository explicitly instructs the judge to avoid position bias, length influence, and assistant-name bias.

  The implementation supports single grading, pairwise-baseline mode, and pairwise-all mode.

  Sources: [judge prompts](https://github.com/lm-sys/FastChat/blob/main/fastchat/llm_judge/data/judge_prompts.jsonl) / [judgment script](https://github.com/lm-sys/FastChat/blob/main/fastchat/llm_judge/gen_judgment.py)
- G-Eval [^14] uses task definition, criteria, Chain-of-Thought (CoT)-generated evaluation steps, and form-filling scores.

  G-Eval reports stronger Spearman correlation with human judgments on summarization than prior metrics. G-Eval also warns that LLM evaluators can prefer LLM-generated summaries over human-written summaries. Source: [repo](https://github.com/nlpyang/geval)
- Prometheus 2 [^15] supports direct assessment and pairwise ranking with user-defined rubrics.

  The paper and repository emphasize open evaluator transparency and report human/proprietary-judge correlation/agreement. Source: [eval repo](https://github.com/prometheus-eval/prometheus-eval)
- LongJudgeBench [^10] specifically studies long-form judge reliability. LongJudgeBench reports task-specific length sensitivity, mixed effects from rubric/reference modes, and no universally reliable judge.

  Source: [repo](https://github.com/cjj826/LongJudgeBench)

### Recommended judge design for our experiment

Recommended protocol:

1. Product-quality pointwise score. For each output, ask two judge families to score independently on Instruction Fulfillment, Organization/Global Coherence, Content Adequacy/Depth, Style/Voice/Audience Fit, and Factuality/Constraint Fidelity. Use a 1-5 anchored rubric with JSON output and a short evidence quote/rationale.
2. Pairwise preference score. For every prompt, compare the 6 conditions in a balanced tournament: 15 unordered condition pairs, A/B and B/A orders, and 30 pairwise judgments per prompt per judge. Count ties explicitly. Balanced ordering controls position bias and reduces scale compression.
3. Blinding and presentation controls. Hide condition names from judges and human annotators. Use neutral labels such as Output A/B or randomized anonymous identifiers (IDs). The human annotation user interface (UI) should randomize output order per comparison and hide benchmark/source names when feasible.
4. Judge/generator separation. Pin the exact run details: judge model versions, prompts, decoding parameters, and seeds. Prefer judge models that are not used as generators. If overlap is unavoidable, run an explicit self-preference test by comparing judge-family outputs against non-overlapping outputs under swapped order.
5. Length control. Record word/token length. Report quality both raw and length-stratified. Add length-matched sensitivity analysis where possible. Otherwise include output length as a covariate in regression or Bradley-Terry [^18] analysis, a paired-comparison model that estimates relative strength from wins and losses. Do not include length compliance in the same score as literary/content quality unless the benchmark requires it.
6. Multi-judge aggregation. Use one strong proprietary judge and one open evaluator or smaller verifier. If budgets allow, add a third judge specialized in writing. Aggregate pointwise scores by z-scored dimension average, meaning the evaluator standardizes each dimension before averaging. Aggregate pairwise scores by majority vote or Bradley-Terry analysis.
7. Human validation. Sample 180-240 pairwise comparisons. Stratify the sample by benchmark, condition pair, prompt length, output length gap, and close-vs-clear automatic decisions. With 6 conditions, the sample gives 12-16 human-checked examples for each of the 15 condition pairs. Use 3 annotators per comparison. Report human-human agreement, judge-human agreement, and disagreement analysis. The scale mirrors the 200-pair DoLoMiTes [^7] validation scale and the MT-Bench [^13] controlled preference protocol without making human annotation the whole experiment.

## Process-level evaluation precedents

Product-only evaluation misses the central claim of a Flower & Hayes [^1]-inspired writing agent. Evaluate the process trace separately from final product quality.

- IteraTeR [^16] is a large-scale, multi-domain, edit-intention annotated corpus of iteratively revised text. IteraTeR models revision depths, granularities, and edit intentions. IteraTeR connects edit intentions to writing quality. Sources: [repo](https://github.com/vipulraheja/IteraTeR) / [dataset README](https://github.com/vipulraheja/IteraTeR/blob/main/dataset/README.md)
- IteraTeR-HUMAN [^16] document-level split includes 481 train, 27 dev, and 51 test documents. Sentence-level split includes 3,254 train, 400 dev, and 364 test examples. Edit actions include add/delete/replace, spans, majority intent, and raw intents from 3 annotators. Source: [IteraTeR dataset README](https://github.com/vipulraheja/IteraTeR/blob/main/dataset/README.md)
- ArgRewrite V.2 [^11] centers on student-driven revision sessions for argumentative writing, including interaction with an NLP-based revision assistant. Source: [repo](https://github.com/omidkashefi/ArgRewrite)
- Revision Quality Prediction [^12] frames argumentative revision quality as success/failure dependent on argument context and uses chain-of-thought generated argument contexts for prediction. Source: [repo](https://github.com/ZhexiongLiu/Revision-Quality-Prediction)

Process fairness policy: all 6 conditions receive identical input context, tools, and output budget.

The protocol in `docs/experiments/protocol.md` makes the equality rule and no-retrieval rule binding for all 6 conditions.

No condition uses web access or retrieval. Condition A3, the STORM [^2]-style condition, follows the protocol's five stages: Perspective discovery, Simulated question answering, Outline, Draft, and Polish.

Condition A3 is not the full retrieval-based STORM system. Retrieval, evidence gathering, and citation tracing are not applicable (N/A) by design for every condition.

For the six-condition experiment, the process metrics should follow the protocol-backed trace contracts:

- Planning trace. Count goals and rate their specificity. Check whether goals cover audience, purpose, content, organization, and style. Check whether later steps refer back to goals.
- Translation trace. Check whether drafts ground claims in plan items, expand sections in a coherent order, and preserve constraints.
- Review trace. Count detected issues and issue types. Map revision intent to clarity, fluency, coherence, style, and meaning change. Check whether fixes improve final rubric scores.
- Monitor trace. Measure process order entropy, meaning how varied the sequence of planning, translating, and reviewing steps is. Check whether transitions respond to detected problems rather than a fixed sequence.
- Condition A3 STORM [^2]-style trace. Record completion of the five protocol stages: Perspective discovery, Simulated question answering, Outline, Draft, and Polish. Retrieval/evidence/citation traces are explicitly N/A under the no-retrieval policy.
- A5 `cognitive-writing-no-goal-network` trace. Leave `goals.md` untouched. Record process switches under the shared trace contract. Record no goal events or goal fields.
- A6 `cognitive-writing-fixed-order` trace. Keep the ordinary goal network. Record process switches and goal events under the shared trace contract. Permit Generate and Evaluate interruptions, then return to the prescribed order.
- Hypotheses to test. The no-goal-network condition should show fewer explicit goal references. The fixed-process-order condition should show lower adaptive transitions even if final quality is similar.

## Final recommendation

Use WritingBench [^3], HelloBench [^4], and DoLoMiTes [^7] as the primary benchmark set, with PERSUADE 2.0 [^19] and ICLE++ [^5] as calibration datasets.

### Primary benchmark shortlist

1. WritingBench [^3]
   - Why: closest match to general-purpose writing among the surveyed benchmarks because it has broad domains, explicit criteria, and current leaderboard/evaluation scripts
   - Fairness: high; all 6 conditions can submit final outputs to the same query set under the equal-context/no-retrieval policy
   - Risk: some prompts include long materials and domain-specific details; ensure identical input context and output budget

2. HelloBench [^4]
   - Why: closest match to long text generation among the surveyed benchmarks because it has checklist-wise evaluation plus human annotation/regression tooling
   - Fairness: high; use the same wrapped prompt and fixed generation budget for all systems
   - Risk: contains multiple task types; report subtask breakdown and avoid overclaiming "writing" from summarization/chat alone

3. DoLoMiTes [^7]
   - Why: closest match to structured expert writing among the surveyed benchmarks because it uses planning-heavy, methodical tasks
   - Fairness: high; all 6 conditions get the same task description and input example, with retrieval disabled
   - Risk: recompute the released archive before final reporting to resolve the split-size conflict

Optional supplementary axis: LongBench-Write [^6]

- Use only for length-control analysis after clearing benchmark prompt-file license/provenance.
- Do not count it as a primary benchmark.

### Prompt-source and human-anchor datasets

1. PERSUADE 2.0 [^19]
   - Use 15 prompts as argumentative writing prompt templates.
   - Use holistic score distribution to calibrate human quality anchors.
   - Do not train on student essays for this paper unless the project team reviews license and consent scope.

2. ICLE++ [^5]
   - Use as external validation of essay-trait rubrics and cross-prompt generalization
   - Good for argumentative/persuasive writing traits, weaker for creative/general writing

### Judge setup

- Run pointwise rubric with JSON schema on all outputs.
- Run pairwise A/B and B/A on all 15 condition pairs for the primary subset: 30 judgments per prompt per judge.
- Blind condition labels and randomize presentation order for human annotators.
- Use at least two judges: a strong frontier judge for main numbers and a Prometheus 2 [^15]-style open evaluator for reproducibility/sensitivity.
- Pin the exact run details: model versions, prompts, decoding parameters, and seeds.
- Avoid judge/generator overlap where possible; otherwise run a self-preference diagnostic.
- Automatic evaluation reports should include per-dimension scores, the aggregate score, pairwise win rate, a length-normalized or covariate-adjusted score, and judge agreement.
- Human validation should use 180-240 pairwise comparisons with 3 annotators each. Stratify by benchmark, condition pair, automatic-decision margin, and output-length gap. Report Krippendorff's alpha, Fleiss' kappa, raw agreement, and judge-human agreement.

## Inaccessible and unresolved items

The main unresolved items are benchmark-file licensing, source-count conflicts, and raw-path reliability.

- HelloBench [^4] raw data file paths listed in README are not reliable. Do not rely on raw file path names until the experiment team checks cloning or HF/OpenCompass integration.
- Keep the dataset previously labeled `ASAP++` out of the dataset table until the team verifies a direct official paper/code/data URL.
- DoLoMiTes [^7] split size has a source conflict. Paper/archive-derived reporting gives 820 dev / 1,037 test, while the repo README says 830 dev / 1,037 test. The final experiment should recompute the split from the released archive and cite that reproducible count.
- Keep the LongBench-Write / LongWriter-6k [^6] family as optional supplementary use because the SFT dataset's Apache-2.0 metadata does not clear `evaluation/*.jsonl` benchmark prompt-file license/provenance.
- Confirm the EQ-Bench Creative Writing [^20] license before using prompts in a paper artifact. The repository does not publish a license file at the [expected EQ-Bench Creative Writing license path](https://github.com/EQ-bench/creative-writing-bench/blob/main/LICENSE).
- WritingPreferenceBench [^8] has inconsistent license metadata. GitHub README says ODC-BY, while Hugging Face metadata says Apache-2.0. Reconcile before redistribution.

## References

[^1]: Flower, Linda, and John R. Hayes. "A Cognitive Process Theory of Writing." College Composition and Communication, 1981. DOI: 10.2307/356600. https://doi.org/10.2307/356600
[^2]: Yijia Shao, Yucheng Jiang, Theodore A. Kanell, Peter Xu, Omar Khattab, and Monica S. Lam. "Assisting in Writing Wikipedia-like Articles From Scratch with Large Language Models." Proceedings of the 2024 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies, 2024. https://aclanthology.org/2024.naacl-long.347/ arXiv: https://arxiv.org/abs/2402.14207
[^3]: Yuning Wu, Jiahao Mei, Ming Yan, Chenliang Li, Shaopeng Lai, Yuran Ren, Zijia Wang, Ji Zhang, Mengyue Wu, Qin Jin, and Fei Huang. "WritingBench: A Comprehensive Benchmark for Generative Writing." arXiv, 2025. https://arxiv.org/abs/2503.05244
[^4]: Haoran Que, Feiyu Duan, Liqun He, Yutao Mou, Wangchunshu Zhou, Jiaheng Liu, Wenge Rong, Zekun Moore Wang, Jian Yang, Ge Zhang, Junran Peng, Zhaoxiang Zhang, Songyang Zhang, and Kai Chen. "HelloBench: Evaluating Long Text Generation Capabilities of Large Language Models." arXiv, 2024. https://arxiv.org/abs/2409.16191
[^5]: Shengjie Li and Vincent Ng. "ICLE++: Modeling Fine-Grained Traits for Holistic Essay Scoring." Proceedings of the 2024 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies, 2024. DOI: 10.18653/v1/2024.naacl-long.468. https://aclanthology.org/2024.naacl-long.468/
[^6]: Yushi Bai, Jiajie Zhang, Xin Lv, Linzhi Zheng, Siqi Zhu, Lei Hou, Yuxiao Dong, Jie Tang, and Juanzi Li. "LongWriter: Unleashing 10,000+ Word Generation from Long Context LLMs." arXiv, 2024. https://arxiv.org/abs/2408.07055
[^7]: Chaitanya Malaviya, Priyanka Agrawal, Kuzman Ganchev, Pranesh Srinivasan, Fantine Huot, Jonathan Berant, Mark Yatskar, Dipanjan Das, Mirella Lapata, and Chris Alberti. "DOLOMITES: Domain-Specific Long-Form Methodical Tasks." arXiv, 2024. https://arxiv.org/abs/2405.05938
[^8]: Shuangshuang Ying, Yunwen Li, Xingwei Qu, Xin Li, Sheng Jin, Minghao Liu, Zhoufutu Wen, Xeron Du, Tianyu Zheng, Yichi Zhang, Letian Ni, Yuyang Cheng, Zhenzhu Yang, Qiguang Chen, Jingzhe Ding, Shengda Long, Wangchunshu Zhou, Jiazhan Feng, Wanjun Zhong, Libo Qin, Ge Zhang, Wenhao Huang, Wanxiang Che, and Chenghua Lin. "Beyond Correctness: Evaluating Subjective Writing Preferences Across Cultures." arXiv, 2025. https://arxiv.org/abs/2510.14616
[^9]: Yuhao Wu, Ming Shan Hee, Zhiqing Hu, and Roy Ka-Wei Lee. "LongGenBench: Benchmarking Long-Form Generation in Long Context LLMs." International Conference on Learning Representations (ICLR), 2025. https://arxiv.org/abs/2409.02076
[^10]: Junjie Chen, Yuxi Dong, Haitao Li, Weihang Su, Yujia Zhou, Min Zhang, Yiqun Liu, and Qingyao Ai. "Benchmarking LLM-as-a-Judge for Long-Form Output Evaluation." Empirical Methods in Natural Language Processing (EMNLP), 2026. https://arxiv.org/abs/2606.01629
[^11]: Omid Kashefi, Tazin Afrin, Meghan Dale, Christopher Olshefski, Amanda Godley, Diane Litman, and Rebecca Hwa. "ArgRewrite V.2: An Annotated Argumentative Revisions Corpus." Language Resources and Evaluation, 2022. DOI: 10.1007/s10579-021-09567-z. https://doi.org/10.1007/s10579-021-09567-z
[^12]: Zhexiong Liu, Diane Litman, Elaine Wang, Lindsay Matsumura, and Richard Correnti. "Predicting the Quality of Revisions in Argumentative Writing." Proceedings of the 18th Workshop on Innovative Use of Natural Language Processing for Building Educational Applications, 2023. https://aclanthology.org/2023.bea-1.24/
[^13]: Lianmin Zheng, Wei-Lin Chiang, Ying Sheng, Siyuan Zhuang, Zhanghao Wu, Yonghao Zhuang, Zi Lin, Zhuohan Li, Dacheng Li, Eric P. Xing, Hao Zhang, Joseph E. Gonzalez, and Ion Stoica. "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena." arXiv, 2023. https://arxiv.org/abs/2306.05685
[^14]: Yang Liu, Dan Iter, Yichong Xu, Shuohang Wang, Ruochen Xu, and Chenguang Zhu. "G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment." Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing, 2023. https://aclanthology.org/2023.emnlp-main.153/ arXiv: https://arxiv.org/abs/2303.16634
[^15]: Seungone Kim, Juyoung Suk, Shayne Longpre, Bill Yuchen Lin, Jamin Shin, Sean Welleck, Graham Neubig, Moontae Lee, Kyungjae Lee, and Minjoon Seo. "Prometheus 2: An Open Source Language Model Specialized in Evaluating Other Language Models." Proceedings of the 2024 Conference on Empirical Methods in Natural Language Processing, 2024. DOI: 10.18653/v1/2024.emnlp-main.248. https://aclanthology.org/2024.emnlp-main.248/ arXiv: https://arxiv.org/abs/2405.01535
[^16]: Wanyu Du, Vipul Raheja, Dhruv Kumar, Zae Myung Kim, Melissa Lopez, and Dongyeop Kang. "Understanding Iterative Revision from Human-Written Text." Proceedings of the 60th Annual Meeting of the Association for Computational Linguistics, 2022. DOI: 10.18653/v1/2022.acl-long.250. https://aclanthology.org/2022.acl-long.250/
[^17]: Bill Yuchen Lin, Yuntian Deng, Khyathi Chandu, Faeze Brahman, Abhilasha Ravichander, Valentina Pyatkin, Nouha Dziri, Ronan Le Bras, and Yejin Choi. "WildBench: Benchmarking LLMs with Challenging Tasks from Real Users in the Wild." arXiv, 2024. https://arxiv.org/abs/2406.04770
[^18]: Bradley, Ralph Allan, and Milton E. Terry. "Rank Analysis of Incomplete Block Designs: I. The Method of Paired Comparisons." Biometrika, 1952. DOI: 10.1093/biomet/39.3-4.324. https://doi.org/10.1093/biomet/39.3-4.324
[^19]: Crossley, S.A., Yu Tian, Perpetual Baffour, Alex Franklin, Meg Benner, and Ulrich Boser. "A large-scale corpus for assessing written argumentation: PERSUADE 2.0." Assessing Writing, 2024. DOI: 10.1016/j.asw.2024.100865. https://doi.org/10.1016/j.asw.2024.100865
[^20]: Samuel J. Paech. "EQ-Bench: An Emotional Intelligence Benchmark for Large Language Models." arXiv, 2023. https://arxiv.org/abs/2312.06281
[^21]: The Hewlett Foundation. "The Hewlett Foundation: Automated Essay Scoring." Kaggle competition, 2012. https://www.kaggle.com/c/asap-aes/data
