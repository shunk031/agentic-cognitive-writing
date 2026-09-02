# Dataset and benchmark survey for large language model (LLM) long-form writing quality evaluation

## Summary

This survey chooses the benchmark set and judge setup for this repository's six-condition experiment on LLM long-form writing. The experiment compares single-shot generation, linear pipelines, the main cognitive-writing plugin, and two comparison variants in the experiments package. See [`docs/experiments/protocol.md`](../experiments/protocol.md) for the full condition definitions.

Use exactly three primary benchmarks because they cover general-purpose writing, long text generation, and structured expert writing without mixing in unresolved license risk.

- WritingBench [^3] covers general-purpose writing. WritingBench has 1,000 real-world writing queries across 6 domains and 100 subdomains. Each query has 5 criteria. [Repo](https://github.com/X-PLUG/WritingBench) / [benchmark data](https://github.com/X-PLUG/WritingBench/blob/main/benchmark_query/benchmark_all.jsonl) / [evaluation prompt](https://github.com/X-PLUG/WritingBench/blob/main/prompt.py)
- HelloBench [^4] targets long text generation. HelloBench has 647 samples across 5 tasks and 38 subcategories. HelloBench selects or wraps question answering (QA), summarization, chat, completion, and heuristic generation for long text generation. [Repo](https://github.com/Quehry/HelloBench) / [judge code](https://github.com/Quehry/HelloBench/blob/main/llm_judge.py)
- DoLoMiTes [^7] is the closest surveyed match for structured expert writing because it uses expert-authored methodical tasks. DoLoMiTes fits research plans, reports, and design documents better than fiction-heavy benchmarks. [Repo](https://github.com/google-deepmind/dolomites) / [task data](https://dolomites-benchmark.s3.us-west-2.amazonaws.com/dolomites_tasks_anon.jsonl) / [examples archive](https://dolomites-benchmark.s3.us-west-2.amazonaws.com/dolomites_examples.zip)

Use PERSUADE 2.0 [^19] and International Corpus of Learner English++ (ICLE++) [^5] as prompt-source and human-anchor datasets, not as primary benchmarks. A prompt-source dataset supplies task prompts. A human-anchor dataset supplies human scores or traits for calibration. PERSUADE 2.0 provides argumentative prompts and human score distributions. ICLE++ provides persuasive-essay trait scores outside Automated Student Assessment Prize (ASAP) [^21]. Use the PERSUADE 2.0 [repo](https://github.com/scrosseye/persuade_corpus_2.0) and [Zenodo record](https://zenodo.org/records/8221504), plus the ICLE++ [repo](https://github.com/samlee946/ICLE-PlusPlus), when building calibration prompts.

Keep LongBench-Write [^6] outside the primary benchmark set, and use it only as an optional length-control axis after the team clears benchmark prompt-file license and provenance. A length-control axis tests whether results hold across target output lengths.

The planned comparison has 6 conditions, and [`docs/experiments/protocol.md`](../experiments/protocol.md) defines their settled behavior.

- A1: single-shot generation
- A2: linear Pre-Write/Write/Re-Write
- A3: Synthesis of Topic Outlines through Retrieval and Multi-perspective Question Asking (STORM) [^2]-style linear pipeline without retrieval
- A4: `cognitive-writing`, the main plugin skill where the Monitor coordinates Planner, Translator, and Reviewer role skills
- A5: `cognitive-writing-no-goal-network`, the experiments package skill that removes the explicit goal network
- A6: `cognitive-writing-fixed-order`, the experiments package skill that keeps the goal network and prescribes process order

The repository ships two plugin packages for the main skill and comparison variants. The main plugin lives under [`plugin/`](https://github.com/shunk031/agentic-cognitive-writing/tree/d0d6da7d0607f9d54b35973c2cf4e10d779a15dd/plugin/) with `cognitive-writing`, `planning`, `translating`, and `reviewing`. The comparison package lives under [`experiments/plugin/`](https://github.com/shunk031/agentic-cognitive-writing/tree/d0d6da7d0607f9d54b35973c2cf4e10d779a15dd/experiments/plugin/) and requires the main plugin. The manifests and README record that split: [`plugin/.codex-plugin/plugin.json`](https://github.com/shunk031/agentic-cognitive-writing/blob/d0d6da7d0607f9d54b35973c2cf4e10d779a15dd/plugin/.codex-plugin/plugin.json) / [`experiments/plugin/.codex-plugin/plugin.json`](https://github.com/shunk031/agentic-cognitive-writing/blob/d0d6da7d0607f9d54b35973c2cf4e10d779a15dd/experiments/plugin/.codex-plugin/plugin.json) / [`experiments/plugin/README.md`](https://github.com/shunk031/agentic-cognitive-writing/blob/d0d6da7d0607f9d54b35973c2cf4e10d779a15dd/experiments/plugin/README.md)

The evaluation design should judge products and processes separately under the same input and tool policy. All conditions receive the same input context, and no condition uses web access or retrieval. Use at least two judge families for product quality. Each prompt has 15 condition pairs and 30 A/B plus B/A judgments per judge. Validate the automatic judges with about 180-240 human comparisons and 3 annotators per comparison. Judges should see final outputs only. Analyze planning traces, revision behavior, goal references, and Monitor transitions separately.

## Long-form, creative, and general writing benchmarks

WritingBench [^3], HelloBench [^4], and DoLoMiTes [^7] are the primary benchmark choices; the other benchmarks are secondary, supplementary, or blocked by license/provenance risk.

| Benchmark | role | scale | license signal | fit for the six-condition experiment |
|---|---|---|---|---|
| WritingBench [^3] | Primary | 1,000 queries | Apache-2.0 | High |
| HelloBench / HelloEval [^4] | Primary | 647 samples | MIT | High |
| DoLoMiTes [^7] | Primary | 519 tasks / 1,857 examples | Apache-2.0 software / CC-BY 4.0 materials | High for structured expert writing |
| LongBench-Write / LongWrite-Ruler / LongWriter [^6] | Optional length analysis only | 120 + 60 + 48 evaluation prompts | License/provenance unresolved | Use only after clearance |
| EQ-Bench Creative Writing v3 [^20] | Secondary creative-writing probe | 96 items | License not published in repo | Medium |
| WildBench v2 [^17] writing-relevant subset | Secondary filtered subset | 1,024 test examples / 256 hard examples | CC BY 4.0 dataset / Apache-2.0 repo | Medium |
| WritingPreferenceBench [^8] | Judge-sensitivity reference | 1,800 preference pairs | ODC-BY in README / Apache-2.0 in HF metadata | Medium as a reference, not primary |
| LongGenBench [^9] | Supplementary robustness probe | 4 scenarios | CC BY-ND 4.0 | Medium-low |
| LongJudgeBench [^10] | Judge validation reference | 6 datasets | MIT | Judge validation only |

WritingBench [^3] is a primary benchmark because it gives broad writing prompts, explicit criteria, and a product-level evaluation path.

- **Scale.** WritingBench has 1,000 real-world writing queries across 6 primary domains and 100 subdomains. The first release had 1,239 queries, and the later update reduced or curated the benchmark to 1,000 queries.
- **Task shape.** The domains are Academic & Engineering, Finance & Business, Politics & Law, Literature & Art, Education, and Advertising & Marketing. Average query length is 1,500+ tokens. The generation configuration recommends `max_length` 16,000 or the maximum allowed.
- **Evaluation.** Each query has 5 instance-specific criteria, and the evaluator assigns a 1-10 score and reason per criterion. The code includes Claude and critic-model evaluation paths.
- **Use in this experiment.** Repository LICENSE is Apache-2.0. We expect high fairness because each condition can submit a final response to the same query. If judges do not see internal traces, single-shot and agentic systems face the same product-level condition.
- **Resources.** [Repo](https://github.com/X-PLUG/WritingBench) / [benchmark data](https://github.com/X-PLUG/WritingBench/blob/main/benchmark_query/benchmark_all.jsonl) / [README](https://github.com/X-PLUG/WritingBench#-whats-new) / [evaluation prompt](https://github.com/X-PLUG/WritingBench/blob/main/prompt.py) / [evaluation script](https://github.com/X-PLUG/WritingBench/blob/main/evaluate_benchmark.py) / [license](https://github.com/X-PLUG/WritingBench/blob/main/LICENSE)

HelloBench / HelloEval [^4] is a primary benchmark because it targets long text generation with checklist-wise evaluation.

- **Scale.** HelloBench has 647 testing samples, 5 tasks, and 38 subcategories.
- **Task shape.** The benchmark is dedicated to long text generation. HelloBench selects or wraps open-ended QA, summarization, chat, text completion, and heuristic text generation for long text generation. Length-constrained heuristic generation includes 2k, 4k, 8k, and 16k variants in the README.
- **Evaluation.** HelloEval uses checklist-wise scoring from 0 to 1 and reports an overall LLM eval score from 0-10. The code runs GPT-4o three retries and stores checklist-wise evaluations.
- **Use in this experiment.** Repository LICENSE is Massachusetts Institute of Technology (MIT). We expect high fairness because long-output requirements should expose planner/reviewer effects. The main caveat is that summarization and chat tasks can have long input context, so the experiment should fix context windows and retrieval handling across conditions.
- **Resources.** [Repo](https://github.com/Quehry/HelloBench) / [README](https://github.com/Quehry/HelloBench#repository-contents) / [judge code](https://github.com/Quehry/HelloBench/blob/main/llm_judge.py) / [regression code](https://github.com/Quehry/HelloBench/blob/main/regression.py) / [license](https://github.com/Quehry/HelloBench/blob/main/LICENSE)

LongBench-Write / LongWrite-Ruler / LongWriter [^6] should stay outside the primary benchmark set until the team clears benchmark-file license and provenance.

- **Scale.** The LongWriter repo introduces LongBench-Write and LongWrite-Ruler. Raw evaluation files contain 120 LongBench-Write prompts, 60 English subset prompts, and 48 LongWrite-Ruler prompts. LongWriter-6k Supervised Fine-Tuning (SFT) data ranges 2k-32k words.
- **Evaluation.** Quality scoring uses a GPT-4o judge over Relevance, Accuracy, Coherence, Clarity, Breadth and Depth, and Reading Experience. Each dimension uses 1-5. The script computes the length score separately from requested vs produced length. The quality prompt explicitly excludes length compliance.
- **License gate.** Benchmark-file license/provenance remains unresolved. The repository does not publish a license file in the expected [GitHub LICENSE path](https://github.com/THUDM/LongWriter/blob/main/LICENSE). The HF Apache-2.0 label covers LongWriter-6k SFT data rather than the `evaluation/*.jsonl` benchmark prompt files. That license label applies to the SFT dataset, not automatically to benchmark prompt files.
- **Use in this experiment.** Before use, clear the license for `evaluation/longbench_write*.jsonl` and `longwrite_ruler.jsonl`, the provenance of prompts, redistribution permission, and whether derived benchmark results can be published. After clearance, use LongBench-Write only for supplementary analysis of target output length. Do not count it among the 3 primary benchmarks.
- **Resources.** [Repo](https://github.com/THUDM/LongWriter) / [LongBench-Write data](https://github.com/THUDM/LongWriter/blob/main/evaluation/longbench_write.jsonl) / [LongWrite-Ruler data](https://github.com/THUDM/LongWriter/blob/main/evaluation/longwrite_ruler.jsonl) / [SFT data](https://huggingface.co/datasets/THUDM/LongWriter-6k) / [English evaluation data](https://github.com/THUDM/LongWriter/blob/main/evaluation/longbench_write_en.jsonl) / [quality script](https://github.com/THUDM/LongWriter/blob/main/evaluation/eval_quality.py) / [length script](https://github.com/THUDM/LongWriter/blob/main/evaluation/eval_length.py) / [judge prompt](https://github.com/THUDM/LongWriter/blob/main/evaluation/judge.txt)

EQ-Bench Creative Writing v3 [^20] is a secondary probe for subjective and literary quality, not a primary benchmark. EQ-Bench Creative Writing v3 has 32 prompts across 3 iterations, for 96 items. Genres include historical fiction, epistolary, romance, comedy, and horror. Prompt examples commonly request about 1,000 words. The harness truncates outputs to 4,000 characters for length-bias mitigation according to the README. Evaluation uses a hybrid rubric score plus pairwise Elo/Glicko-2. The README states Sonnet 4.6 for leaderboard parity and lists mitigations for length, position, and verbosity/poetic incoherence. The repository does not publish a license file at the [expected license URL](https://github.com/EQ-bench/creative-writing-bench/blob/main/LICENSE), so confirm the license with the maintainers or repository metadata before using it. We expect medium fit because creative writing is central, but 32 prompts is small and Elo requires historical run files for comparability. [Repo](https://github.com/EQ-bench/creative-writing-bench) / [prompts](https://github.com/EQ-bench/creative-writing-bench/blob/main/data/creative_writing_prompts_v3.json) / [judge prompt](https://github.com/EQ-bench/creative-writing-bench/blob/main/data/creative_writing_judging_prompt.txt) / [script](https://github.com/EQ-bench/creative-writing-bench/blob/main/creative_writing_bench.py)

WildBench v2 [^17] is a secondary filtered-subset option because it is broad assistant evaluation, not a pure long-form writing benchmark. The HF dataset v2 has 1,024 test examples, and V2-hard has 256 examples. Fields include `checklist`, `primary_tag`, `secondary_tags`, and `intent`. The WildBench authors collected real-user tasks, including long and writing-like tasks. V2 uses 5-10 example-specific checklist questions, GPT-4-turbo scoring, pairwise reward, and length-penalized Elo/reward-mix. The HF card says Creative Commons Attribution (CC BY) 4.0 for the dataset, and the repo LICENSE is Apache-2.0. We expect medium fit because real-user diversity is useful, but writing tasks must be filtered by `primary_tag` or `intent`. Otherwise the benchmark measures broad assistant behavior rather than writing quality. [HF data](https://huggingface.co/datasets/allenai/WildBench) / [repo](https://github.com/allenai/WildBench) / [license](https://github.com/allenai/WildBench/blob/main/LICENSE)

DoLoMiTes [^7] is a primary benchmark because it matches structured expert writing better than the other surveyed datasets.

- **Scale.** DoLoMiTes has 519 methodical tasks from 266 experts across 25 fields, plus 1,857 expert post-edited examples. The sources disagree on split size. Paper/archive-derived reporting gives 820 dev / 1,037 test, while the repo README says 830 dev examples and 1,037 test examples. Use 820/1,037 only after recomputing from the released archive in the experiment repository.
- **Task shape.** Reference outputs average 341.42 tokens. Tasks are methodical long-form writing with structured output sections. Generation uses up to 4,096 tokens.
- **Evaluation.** Evaluation includes pairwise language model (LM) preference against GPT-4 and fine-grained 1-5 absolute evaluation. Absolute dimensions are task adherence, factual correctness, depth, completeness, and coherence. Human validation used 200 pairs. Two annotators agreed on 75% of 100 examples. Claude-3 Opus agreement was 67% with ties and 77% without ties.
- **Use in this experiment.** Software is Apache-2.0, and other materials are CC-BY 4.0. We expect high fit for research/report tasks because DoLoMiTes uses structured expert tasks. We expect medium fit for creative writing because the task set is not fiction-centered.
- **Resources.** [Repo](https://github.com/google-deepmind/dolomites) / [released archive](https://dolomites-benchmark.s3.us-west-2.amazonaws.com/dolomites_examples.zip) / [conflicting README](https://github.com/google-deepmind/dolomites/blob/main/README.md)

WritingPreferenceBench [^8] is a judge-sensitivity reference because it contains human-validated preference pairs for subjective writing. WritingPreferenceBench has 1,800 human-validated preference pairs, with 1,200 English pairs and 600 Chinese pairs. The dataset covers 8 creative writing genres and 51 categories. The HF card and repo report mean response lengths around 1,450 words for English chosen and 840 for English rejected. Pair data include `completion_tokens` and `word_len`. Construction uses human-in-the-loop preference construction, 11 expert annotators, 8-hour rubric calibration, a 0-3 creative-writing scale, and retained pairs with >=2/3 agreement and score gap >=1. The LLM-as-judge chooses the preferred response based on creativity, emotional resonance, and stylistic flair. License metadata disagrees. GitHub README says Open Data Commons Attribution License (ODC-BY), while HF metadata says Apache-2.0. Resolve the license before redistribution. Do not use WritingPreferenceBench as a primary generation benchmark because its labels are preference pairs of existing model outputs. [Project](https://WritingPreferenceBench.github.io/) / [HF data](https://huggingface.co/datasets/m-a-p/Writing-Preference-Bench) / [repo](https://github.com/WritingPreferenceBench/Writing-Preference-Bench)

LongGenBench [^9] is a supplementary robustness probe because it stresses long-context instruction following more than writing process quality. LongGenBench evaluates long-form generation in long-context language models and uses four scenarios. Prompt lengths are 16K/32K. Task examples include urban planning, diary entries, and menu-planning-like constrained long outputs. The focus is long-context prompt instruction following, not only output length. HF license is Creative Commons Attribution-NoDerivatives (CC BY-ND) 4.0. The repo has evaluation scripts under `Evalution`. The detailed judge rubric needs further inspection before use. Do not use LongGenBench as a primary benchmark for this experiment. [Repo](https://github.com/mozhu621/LongGenBench) / [HF data](https://huggingface.co/datasets/mozhu/LongGenBench)

LongJudgeBench [^10] is a judge-validation reference, not a generation benchmark. LongJudgeBench should inform judge choice for long outputs rather than replace product-quality benchmarks. LongJudgeBench is a 2026 meta-evaluation benchmark for LLM-as-a-judge on long-form outputs. LongJudgeBench has 6 datasets, pointwise/pairwise/listwise protocols, 4 prompt modes, and 8 judge models. Documents range from avg 3,053 to 28,758 tokens depending on source dataset. Metrics include pairwise accuracy (ACC), Spearman, and Kendall's tau. Prompt modes include vanilla, rubric, reference, and rubric+reference. README reports that rubric/reference can help or hurt depending on task. Repository LICENSE is MIT. [Repo](https://github.com/cjj826/LongJudgeBench) / [reliability script](https://github.com/cjj826/LongJudgeBench/blob/main/src/evaluation/compute_reliability.py) / [license](https://github.com/cjj826/LongJudgeBench/blob/main/LICENSE)

## Essay and argumentative writing datasets with quality annotations

Use essay datasets as prompt sources and human-score references, not as primary generation benchmarks.

| Dataset | role for this paper | access caveat |
|---|---|---|
| ASAP Automated Essay Scoring (ASAP AES) [^21] | Prompt source and historical AES baseline | Kaggle terms |
| PERSUADE 2.0 [^19] | Strong prompt source and human-quality anchor | Review license and consent scope before training use |
| ICLE / ICLE++ [^5] | Held-out essay-trait calibration | ICLE base-text access/license must be cleared before main use |
| ArgRewrite V.2 [^11] | Process-level revision precedent | Not a prompt bank |
| Revision Quality Prediction [^12] | Process trace reference | Some data must be obtained from PETAL Pittsburgh |

ASAP Automated Essay Scoring (ASAP AES) [^21] is a Kaggle competition dataset for human-scored student essays. Use it as a prompt source and historical AES baseline only. Access can require Kaggle terms, so check the current access and license terms on the [Kaggle data page](https://www.kaggle.com/c/asap-aes/data) before relying on it as a reproducibility dependency.

PERSUADE 2.0 [^19] is the strongest prompt-source dataset and human-quality anchor for argumentative writing in this survey. PERSUADE 2.0 has over 25,000 argumentative essays from United States grades 6-12, 15 prompts, and two writing tasks: independent and source-based. The dataset provides holistic essay scores and discourse/argumentative element effectiveness scores. PERSUADE 2.0 gives realistic argumentative prompts and a distribution of student quality. Use a new rubric to judge generated LLM outputs because student-score scales are not directly comparable to LLM long-form quality. [Repo](https://github.com/scrosseye/persuade_corpus_2.0) / [Zenodo record](https://zenodo.org/records/8221504)

ICLE / ICLE++ [^5] is a held-out human-quality anchor outside ASAP and PERSUADE 2.0 for essay-trait calibration. The corpus contains persuasive student essays annotated with holistic and trait-specific scores. ICLE++ tests generalization beyond Automated Student Assessment Prize (ASAP) [^21] and covers multi-trait/cross-prompt AES. Use ICLE++ to calibrate rubrics on persuasive writing traits, not as a main generation benchmark unless ICLE base-text access/license is cleared. [Repo](https://github.com/samlee946/ICLE-PlusPlus)

ArgRewrite V.2 [^11] is a process-level precedent for revision intent, not a prompt bank. ArgRewrite V.2 is an annotated corpus of argumentative revisions. The corpus studies student interactions with a natural language processing (NLP)-based revision assistant and whether feedback forms encourage effective revisions. Use ArgRewrite V.2 to define revision intent categories and to evaluate whether the reviewer/monitor produces useful revision operations. [Repo](https://github.com/omidkashefi/ArgRewrite)

Revision Quality Prediction [^12] predicts whether argumentative revisions are successful, so it is useful for process trace analysis. The work uses annotated elementary essays and a college revision desirability corpus. The code asks users to obtain data from PETAL Pittsburgh. Use Revision Quality Prediction to compare agent reviewer actions against human notions of successful argument revision. Do not use it as a primary product-quality benchmark. [Repo](https://github.com/ZhexiongLiu/Revision-Quality-Prediction) / [PETAL data page](https://petal-cs-pitt.github.io/data.html)

## LLM-as-judge methodology for writing quality

The judge design should pair rubric scoring with balanced pairwise comparisons, then validate the automatic judges against a human validation sample.

### Biases and mitigations

- MT-Bench / Chatbot Arena [^13] paper identifies position bias, verbosity bias, self-enhancement bias, and limited reasoning ability. GPT-4 matched human preferences above 80% agreement in their studied setup. The released setup included 80 MT-Bench questions, 3K expert votes, and 30K arena conversations. [FastChat judge code](https://github.com/lm-sys/FastChat/tree/main/fastchat/llm_judge)
- The judge prompt file in the FastChat repository explicitly instructs the judge to avoid position bias, length influence, and assistant-name bias. The FastChat implementation includes single grading, pairwise-baseline mode, and pairwise-all mode. [Judge prompts](https://github.com/lm-sys/FastChat/blob/main/fastchat/llm_judge/data/judge_prompts.jsonl) / [judgment script](https://github.com/lm-sys/FastChat/blob/main/fastchat/llm_judge/gen_judgment.py)
- G-Eval [^14] uses task definition, criteria, Chain-of-Thought (CoT)-generated evaluation steps, and form-filling scores. G-Eval reports stronger Spearman correlation with human judgments on summarization than prior metrics. G-Eval also warns that LLM evaluators can prefer LLM-generated summaries over human-written summaries. [Repo](https://github.com/nlpyang/geval)
- Prometheus 2 [^15] provides direct assessment and pairwise ranking with user-defined rubrics. The paper and repository emphasize open evaluator transparency and report human/proprietary-judge correlation/agreement. [Eval repo](https://github.com/prometheus-eval/prometheus-eval)
- LongJudgeBench [^10] specifically studies long-form judge reliability. LongJudgeBench reports task-specific length sensitivity, mixed effects from rubric/reference modes, and no universally reliable judge. [Repo](https://github.com/cjj826/LongJudgeBench)

### Recommended judge design for our experiment

1. **Product-quality pointwise score.** For each output, ask two judge families to score independently on Instruction Fulfillment, Organization/Global Coherence, Content Adequacy/Depth, Style/Voice/Audience Fit, and Factuality/Constraint Fidelity. Use a 1-5 anchored rubric with JSON output and a short evidence quote/rationale.
2. **Pairwise preference score.** For every prompt, compare the 6 conditions in a balanced tournament: 15 unordered condition pairs, A/B and B/A orders, and 30 pairwise judgments per prompt per judge. Count ties explicitly. Balanced ordering controls position bias and reduces scale compression.
3. **Blinding and presentation controls.** Hide condition names from judges and human annotators. Use neutral labels such as Output A/B or randomized anonymous identifiers (IDs). The human annotation user interface (UI) should randomize output order per comparison and hide benchmark/source names when feasible.
4. **Judge/generator separation.** Pin the exact run details: judge model versions, prompts, decoding parameters, and seeds. Prefer judge models that are not used as generators. If overlap is unavoidable, run an explicit self-preference test by comparing judge-family outputs against non-overlapping outputs under swapped order.
5. **Length control.** Record word/token length. Report quality both raw and length-stratified. Add length-matched sensitivity analysis where possible. Otherwise include output length as a covariate in regression or Bradley-Terry [^18] analysis, a paired-comparison model that estimates relative strength from wins and losses. Do not include length compliance in the same score as literary/content quality unless the benchmark requires it.
6. **Multi-judge aggregation.** Use one strong proprietary judge and one open evaluator or smaller verifier. If budgets allow, add a third judge specialized in writing. Aggregate pointwise scores by z-scored dimension average, meaning the evaluator standardizes each dimension before averaging. Aggregate pairwise scores by majority vote or Bradley-Terry analysis.
7. **Human validation.** Sample 180-240 pairwise comparisons. Stratify the sample by benchmark, condition pair, prompt length, output length gap, and close-vs-clear automatic decisions. With 6 conditions, the sample gives 12-16 human-checked examples for each of the 15 condition pairs. Use 3 annotators per comparison. Report human-human agreement, judge-human agreement, and disagreement analysis. The scale mirrors the 200-pair DoLoMiTes [^7] validation scale and the MT-Bench [^13] controlled preference protocol without making human annotation the whole experiment.

## Process-level evaluation precedents

Product-only evaluation misses the central claim of a Flower & Hayes [^1]-inspired writing agent. Evaluate the process trace separately from final product quality.

- IteraTeR [^16] is a large-scale, multi-domain, edit-intention annotated corpus of iteratively revised text. IteraTeR models revision depths, granularities, and edit intentions. IteraTeR connects edit intentions to writing quality. [Repo](https://github.com/vipulraheja/IteraTeR) / [dataset README](https://github.com/vipulraheja/IteraTeR/blob/main/dataset/README.md)
- IteraTeR-HUMAN [^16] document-level split includes 481 train, 27 dev, and 51 test documents. Sentence-level split includes 3,254 train, 400 dev, and 364 test examples. Edit actions include add/delete/replace, spans, majority intent, and raw intents from 3 annotators. [IteraTeR dataset README](https://github.com/vipulraheja/IteraTeR/blob/main/dataset/README.md)
- ArgRewrite V.2 [^11] centers on student-driven revision sessions for argumentative writing, including interaction with an NLP-based revision assistant. [Repo](https://github.com/omidkashefi/ArgRewrite)
- Revision Quality Prediction [^12] frames argumentative revision quality as success/failure dependent on argument context and uses chain-of-thought generated argument contexts for prediction. [Repo](https://github.com/ZhexiongLiu/Revision-Quality-Prediction)

**Process fairness policy.** [`docs/experiments/protocol.md`](../experiments/protocol.md) binds all 6 conditions to identical input context, identical tools, identical output budget, and no retrieval. No condition uses web access or retrieval. Condition A3, the STORM [^2]-style condition, follows the protocol's five stages: Perspective discovery, Simulated question answering, Outline, Draft, and Polish. Condition A3 is not the full retrieval-based STORM system. Retrieval, evidence gathering, and citation tracing are not applicable (N/A) by design for every condition.

For the six-condition experiment, the process metrics should follow the protocol-backed trace contracts:

- **Planning trace.** Count goals and rate their specificity. Check whether goals cover audience, purpose, content, organization, and style. Check whether later steps refer back to goals.
- **Translation trace.** Check whether drafts ground claims in plan items, expand sections in a coherent order, and preserve constraints.
- **Review trace.** Count detected issues and issue types. Map revision intent to clarity, fluency, coherence, style, and meaning change. Check whether fixes improve final rubric scores.
- **Monitor trace.** Measure process order entropy, meaning how varied the sequence of planning, translating, and reviewing steps is. Check whether transitions respond to detected problems rather than a fixed sequence.
- **Condition A3 trace.** Record completion of the STORM [^2]-style five protocol stages: Perspective discovery, Simulated question answering, Outline, Draft, and Polish. Retrieval/evidence/citation traces are explicitly N/A under the no-retrieval policy.
- **A5 `cognitive-writing-no-goal-network` trace.** The experiments package skill leaves `goals.md` untouched. Record process switches under the shared trace contract. Record no goal events or goal fields.
- **A6 `cognitive-writing-fixed-order` trace.** The experiments package skill keeps the ordinary goal network. Record process switches and goal events under the shared trace contract. Permit Generate and Evaluate interruptions, then return to the prescribed order.
- **Hypotheses to test.** The no-goal-network condition should show fewer explicit goal references. The fixed-process-order condition should show lower adaptive transitions even if final quality is similar.

## Final recommendation

Use WritingBench [^3], HelloBench [^4], and DoLoMiTes [^7] as the primary benchmark set, with PERSUADE 2.0 [^19] and ICLE++ [^5] as calibration datasets.

### Primary benchmark shortlist

1. WritingBench [^3]
   - **Why.** WritingBench is the closest match to general-purpose writing among the surveyed benchmarks because it has broad domains, explicit criteria, and current leaderboard/evaluation scripts.
   - **Fairness.** All 6 conditions can submit final outputs to the same query set under the equal-context/no-retrieval policy.
   - **Risk.** Some prompts include long materials and domain-specific details; ensure identical input context and output budget.

2. HelloBench [^4]
   - **Why.** HelloBench is the closest match to long text generation among the surveyed benchmarks because it has checklist-wise evaluation plus human annotation/regression tooling.
   - **Fairness.** Use the same wrapped prompt and fixed generation budget for all systems.
   - **Risk.** HelloBench contains multiple task types; report subtask breakdown and avoid overclaiming "writing" from summarization/chat alone.

3. DoLoMiTes [^7]
   - **Why.** DoLoMiTes is the closest match to structured expert writing among the surveyed benchmarks because it uses planning-heavy, methodical tasks.
   - **Fairness.** All 6 conditions get the same task description and input example, with retrieval disabled.
   - **Risk.** Recompute the released archive before final reporting to resolve the split-size conflict.

The experiment team should treat LongBench-Write [^6] as optional supplementary material only after clearing benchmark prompt-file license/provenance. Do not count it as a primary benchmark.

### Prompt-source and human-anchor datasets

1. PERSUADE 2.0 [^19]
   - Use 15 prompts as argumentative writing prompt templates.
   - Use holistic score distribution to calibrate human quality anchors.
   - Do not train on student essays for this paper unless the project team reviews license and consent scope.

2. ICLE++ [^5]
   - Use as external validation of essay-trait rubrics and cross-prompt generalization.
   - ICLE++ fits argumentative/persuasive writing traits better than creative/general writing.

### Judge setup

- Run pointwise rubric with JSON schema on all outputs.
- Run pairwise A/B and B/A on all 15 condition pairs for the primary subset: 30 judgments per prompt per judge.
- Blind condition labels and randomize presentation order for human annotators.
- Use at least two judges, with a strong frontier judge for main numbers and a Prometheus 2 [^15]-style open evaluator for reproducibility/sensitivity.
- Pin model versions, prompts, decoding parameters, and seeds.
- Avoid judge/generator overlap where possible; otherwise run a self-preference diagnostic.
- Automatic evaluation reports should include per-dimension scores, the aggregate score, pairwise win rate, a length-normalized or covariate-adjusted score, and judge agreement.
- Human validation should use 180-240 pairwise comparisons with 3 annotators each. Stratify by benchmark, condition pair, automatic-decision margin, and output-length gap. Report Krippendorff's alpha, Fleiss' kappa, raw agreement, and judge-human agreement.

## Inaccessible and unresolved items

The main unresolved items are benchmark-file licensing, source-count conflicts, and raw-path reliability.

- HelloBench [^4] raw data file paths listed in README are not reliable. Do not rely on raw file path names until the experiment team checks cloning or HF/OpenCompass integration.
- Keep `ASAP++` out of the dataset table until the team verifies a direct official paper/code/data URL.
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
