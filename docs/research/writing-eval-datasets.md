# Dataset and benchmark survey for large language model (LLM) long-form writing quality evaluation

## 0. Summary

Question: which benchmarks and judge setup should the 6-arm long-form writing experiment use?

Answer: use exactly three primary benchmarks.

- WritingBench [^3] covers general-purpose writing. It has 1,000 real-world writing queries across 6 domains and 100 subdomains. Each query has 5 criteria.
  - Repo: https://github.com/X-PLUG/WritingBench
  - Data: https://github.com/X-PLUG/WritingBench/blob/main/benchmark_query/benchmark_all.jsonl
  - Eval prompt: https://github.com/X-PLUG/WritingBench/blob/main/prompt.py
- HelloBench [^4] targets long text generation. It has 647 samples across 5 tasks and 38 subcategories. It selects or wraps these task types for long text generation.
  - Task types:
    - Question answering (QA)
    - Summarization
    - Chat
    - Completion
    - Heuristic generation
  - Repo: https://github.com/Quehry/HelloBench
  - Judge code: https://github.com/Quehry/HelloBench/blob/main/llm_judge.py
- DoLoMiTes [^7] covers structured expert writing. It fits research plans. It also fits reports and design documents better than fiction-heavy benchmarks.
  - Repo: https://github.com/google-deepmind/dolomites
  - Data: https://dolomites-benchmark.s3.us-west-2.amazonaws.com/dolomites_tasks_anon.jsonl
  - Examples: https://dolomites-benchmark.s3.us-west-2.amazonaws.com/dolomites_examples.zip

Run rubric pointwise scoring plus balanced pairwise comparison.

Use PERSUADE 2.0 [^19] and International Corpus of Learner English++ (ICLE++) [^5] as prompt-source and human-anchor datasets, not as primary benchmarks. PERSUADE 2.0 provides argumentative prompts and human score distributions; ICLE++ provides persuasive-essay trait scores outside Automated Student Assessment Prize (ASAP).

- PERSUADE 2.0 [^19]
  - Repo: https://github.com/scrosseye/persuade_corpus_2.0
  - Zenodo record: https://zenodo.org/records/8221504
- ICLE++ [^5]
  - Repo: https://github.com/samlee946/ICLE-PlusPlus

Keep LongBench-Write [^6] outside the primary benchmark set, and use it only as an optional length-control axis after the team clears benchmark prompt-file license and provenance.

The planned comparison has 6 arms, pending final user confirmation.

- Single-shot generation
- Linear Pre-Write/Write/Re-Write
- Synthesis of Topic Outlines through Retrieval and Multi-perspective Question Asking (STORM) [^2]-style linear pipeline without retrieval
- Flower & Hayes [^1]-inspired agent
- Ablation A with no goal network
- Ablation B with fixed process order

All arms receive the same input context and no arm uses web access or retrieval.

Use at least two judge families. Each prompt has 15 arm pairs and 30 A/B plus B/A judgments per judge. Validate the automatic judges with about 180-240 human comparisons and 3 annotators per comparison.

Separate product quality from process analysis. Judges should see final outputs only. Analyze these process signals separately:

- Planning traces
- Revision behavior
- Goal references
- Monitor transitions

## 1. Long-form / creative / general writing benchmarks

| Benchmark | task types / prompt count | output length range | evaluation method | license | agentic system fairness |
|---|---|---|---|---|---|
| WritingBench [^3] | 1,000 real-world writing queries, 6 primary domains, 100 subdomains; first release had 1,239 queries, later update reduced/curated to 1,000. Domains: Academic & Engineering, Finance & Business, Politics & Law, Literature & Art, Education, Advertising & Marketing. Sources:<br>Repo: https://github.com/X-PLUG/WritingBench <br>Data: https://github.com/X-PLUG/WritingBench/blob/main/benchmark_query/benchmark_all.jsonl | Average query length is 1,500+ tokens; generation config recommends max_length 16,000 or max allowed. Source: https://github.com/X-PLUG/WritingBench#-whats-new | Each query has 5 instance-specific criteria; evaluator independently assigns 1-10 score and reason per criterion. Code supports Claude or critic model. Sources:<br>Eval prompt: https://github.com/X-PLUG/WritingBench/blob/main/prompt.py <br>Eval script: https://github.com/X-PLUG/WritingBench/blob/main/evaluate_benchmark.py | Repository LICENSE is Apache-2.0. Source: https://github.com/X-PLUG/WritingBench/blob/main/LICENSE | We infer high fairness. Each arm can submit a final response to the same query. If judges do not see internal traces, single-shot and agentic systems face the same product-level condition. |
| HelloBench / HelloEval [^4] | 647 testing samples, 5 tasks, 38 subcategories. The benchmark is dedicated to long text generation. It selects or wraps open-ended QA, summarization, chat, text completion, and heuristic text generation specifically for long text generation. Sources:<br>Repo: https://github.com/Quehry/HelloBench | HelloBench selects/wraps tasks for long text generation; length-constrained heuristic generation includes 2k/4k/8k/16k variants in README. Source: https://github.com/Quehry/HelloBench#repository-contents | HelloEval uses checklist-wise scoring from 0 to 1 and overall LLM eval score 0-10; code runs GPT-4o three retries and stores checklist-wise evaluations. Sources:<br>Judge code: https://github.com/Quehry/HelloBench/blob/main/llm_judge.py <br>Regression code: https://github.com/Quehry/HelloBench/blob/main/regression.py | Repository LICENSE is Massachusetts Institute of Technology (MIT). Source: https://github.com/Quehry/HelloBench/blob/main/LICENSE | We infer high fairness. Long-output requirements are natural here, so planner/reviewer effects should be measurable. The main caveat is that summarization and chat tasks can have long input context. Fix context windows and retrieval handling across arms. |
| LongBench-Write / LongWrite-Ruler / LongWriter [^6] | LongWriter repo introduces LongBench-Write and LongWrite-Ruler; raw evaluation files contain 120 LongBench-Write prompts, 60 English subset prompts, and 48 LongWrite-Ruler prompts. Sources:<br>Repo: https://github.com/THUDM/LongWriter <br>LongBench-Write data: https://github.com/THUDM/LongWriter/blob/main/evaluation/longbench_write.jsonl <br>LongWrite-Ruler data: https://github.com/THUDM/LongWriter/blob/main/evaluation/longwrite_ruler.jsonl | LongWriter-6k [^6] Supervised Fine-Tuning (SFT) data ranges 2k-32k words, but that license label applies to the SFT dataset, not automatically to benchmark prompt files. Sources:<br>SFT data: https://huggingface.co/datasets/THUDM/LongWriter-6k <br>English evaluation data: https://github.com/THUDM/LongWriter/blob/main/evaluation/longbench_write_en.jsonl | Quality score uses GPT-4o judge over Relevance, Accuracy, Coherence, Clarity, Breadth and Depth, Reading Experience, each 1-5; the script computes the length score separately from requested vs produced length, and the quality prompt explicitly excludes length compliance. Sources:<br>Quality script: https://github.com/THUDM/LongWriter/blob/main/evaluation/eval_quality.py <br>Length script: https://github.com/THUDM/LongWriter/blob/main/evaluation/eval_length.py <br>Judge prompt: https://github.com/THUDM/LongWriter/blob/main/evaluation/judge.txt | Unresolved: we have not resolved benchmark-file license/provenance. The repo LICENSE URL returned 404, and the Hugging Face (HF) Apache-2.0 label covers LongWriter-6k SFT data rather than the `evaluation/*.jsonl` benchmark prompt files. Before use, clear:<br>License for `evaluation/longbench_write*.jsonl` and `longwrite_ruler.jsonl`<br>Provenance of prompts and whether redistribution is allowed<br>Whether derived benchmark results can be published | Use as optional supplementary only after clearance as a length-control axis; do not count it among the 3 primary benchmarks. |
| EQ-Bench Creative Writing v3 | 32 prompts × 3 iterations = 96 items; genres include historical fiction, epistolary, romance, comedy, horror, etc. Sources:<br>Repo: https://github.com/EQ-bench/creative-writing-bench <br>Prompts: https://github.com/EQ-bench/creative-writing-bench/blob/main/data/creative_writing_prompts_v3.json | Prompt examples commonly request about 1,000 words; the harness truncates outputs to 4,000 characters for length-bias mitigation according to README. Sources:<br>Repo: https://github.com/EQ-bench/creative-writing-bench <br>Judge prompt: https://github.com/EQ-bench/creative-writing-bench/blob/main/data/creative_writing_judging_prompt.txt | Hybrid rubric score plus pairwise Elo/Glicko-2; README states Sonnet 4.6 for leaderboard parity and lists mitigations for length, position, verbosity/poetic incoherence. Sources:<br>Repo: https://github.com/EQ-bench/creative-writing-bench <br>Script: https://github.com/EQ-bench/creative-writing-bench/blob/main/creative_writing_bench.py | Unverified: repository license file was 404 during bounded fetch; resolve the license with maintainers or repository metadata before using it. | We infer medium fit. Creative writing is central, but 32 prompts is small and Elo requires historical run files for comparability. This is a good secondary benchmark for subjective/literary quality. |
| WildBench v2 [^17] writing-relevant subset | HF dataset v2 has 1,024 test examples; v2-hard has 256 examples. Fields include checklist, primary_tag, secondary_tags, intent. Sources:<br>HF data: https://huggingface.co/datasets/allenai/WildBench <br>Repo: https://github.com/allenai/WildBench | Not a pure long-form benchmark; it is collected from real-user tasks and includes long/writing-like tasks. Source: https://github.com/allenai/WildBench | V2 uses 5-10 example-specific checklist questions, GPT-4-turbo scoring, pairwise reward, and length-penalized Elo/reward-mix. Sources:<br>Repo: https://github.com/allenai/WildBench <br>HF data: https://huggingface.co/datasets/allenai/WildBench | HF card says Creative Commons Attribution (CC BY) 4.0 for dataset; repo LICENSE is Apache-2.0. Sources:<br>HF data: https://huggingface.co/datasets/allenai/WildBench <br>License: https://github.com/allenai/WildBench/blob/main/LICENSE | We infer medium fit. Real-user diversity is useful, but writing tasks must be filtered by `primary_tag`/`intent`. Otherwise the benchmark measures broad assistant behavior rather than writing quality. |
| DoLoMiTes [^7] | 519 methodical tasks from 266 experts across 25 fields; 1,857 expert post-edited examples. For split size, paper/archive-derived reporting gives 820 dev / 1,037 test, while the repo README says 830 dev examples and 1,037 test examples; record this as a source conflict and use 820/1,037 only after recomputing from the released archive in the experiment repository. Sources:<br>Released archive: https://dolomites-benchmark.s3.us-west-2.amazonaws.com/dolomites_examples.zip <br>Conflicting README: https://github.com/google-deepmind/dolomites/blob/main/README.md | Reference outputs average 341.42 tokens, but tasks are methodical long-form writing with structured output sections; generation uses up to 4,096 tokens. Source: https://github.com/google-deepmind/dolomites | Pairwise language model (LM) preference against GPT-4 and fine-grained 1-5 absolute evaluation over task adherence, factual correctness, depth, completeness, coherence; human validation used 200 pairs, with 75% two-annotator agreement on 100 examples and 67%/77% Claude-3 Opus agreement with/without ties. Source: https://github.com/google-deepmind/dolomites | Software Apache-2.0; other materials CC-BY 4.0. Source: https://github.com/google-deepmind/dolomites/blob/main/README.md | We infer high fit for research/report tasks and medium fit for creative writing. It is especially useful if the paper wants to show agentic planning improves structured expert writing rather than fiction only. |
| WritingPreferenceBench [^8] | 1,800 human-validated preference pairs, 1,200 English and 600 Chinese, across 8 creative writing genres and 51 categories. Sources:<br>Project: https://WritingPreferenceBench.github.io/ <br>HF data: https://huggingface.co/datasets/m-a-p/Writing-Preference-Bench <br>Repo: https://github.com/WritingPreferenceBench/Writing-Preference-Bench | HF/repo report mean response lengths around 1,450 words for English chosen and 840 for English rejected; pair data include completion_tokens and word_len. Sources:<br>HF data: https://huggingface.co/datasets/m-a-p/Writing-Preference-Bench <br>Repo: https://github.com/WritingPreferenceBench/Writing-Preference-Bench | Human-in-the-loop preference construction; 11 expert annotators, 8-hour rubric calibration, 0-3 creative-writing scale, retain pairs with >=2/3 agreement and score gap >=1; LLM-as-judge chooses preferred response based on creativity, emotional resonance, stylistic flair. Sources:<br>HF data: https://huggingface.co/datasets/m-a-p/Writing-Preference-Bench <br>Repo: https://github.com/WritingPreferenceBench/Writing-Preference-Bench | CONFLICT: GitHub README says Open Data Commons Attribution License (ODC-BY); HF metadata says Apache-2.0. Treat as unresolved and reconcile license metadata before use. Sources:<br>Repo: https://github.com/WritingPreferenceBench/Writing-Preference-Bench <br>HF data: https://huggingface.co/datasets/m-a-p/Writing-Preference-Bench | We infer medium fit. It is excellent for validating judge sensitivity to subjective style, but not a clean generation benchmark because labels are preference pairs of existing model outputs. |
| LongGenBench [^9] | Evaluates long-form generation in long-context LMs with four scenarios and prompt lengths 16K/32K; tasks include urban planning, diary entries, menu planning-like constrained long outputs. Sources:<br>Repo: https://github.com/mozhu621/LongGenBench <br>HF data: https://huggingface.co/datasets/mozhu/LongGenBench | Focus is long-context prompt instruction following, not only output length; HF license is Creative Commons Attribution-NoDerivatives (CC BY-ND) 4.0. Sources:<br>Repo: https://github.com/mozhu621/LongGenBench <br>HF data: https://huggingface.co/datasets/mozhu/LongGenBench | Repo has evaluation scripts under `Evalution`; detailed judge rubric was not fully inspected. Sources: https://github.com/mozhu621/LongGenBench | HF card says CC-BY-ND-4.0. Source: https://huggingface.co/datasets/mozhu/LongGenBench | We infer medium-low fit as a primary benchmark. It is useful as a stress test for long instruction adherence, but the paper target is writing process quality, so use only as supplementary robustness. |
| LongJudgeBench [^10] | Not a generation benchmark; it is a 2026 meta-evaluation benchmark for LLM-as-a-judge on long-form outputs, with 6 datasets, pointwise/pairwise/listwise protocols, four prompt modes, and 8 judge models. Sources:<br>Repo: https://github.com/cjj826/LongJudgeBench | Documents range from avg 3,053 to 28,758 tokens depending on source dataset. Source: https://github.com/cjj826/LongJudgeBench | Metrics are pairwise accuracy (ACC), Spearman, Kendall's tau; prompt modes are vanilla/rubric/reference/rubric+reference; README reports rubric/reference can help or hurt depending on task. Sources:<br>Repo: https://github.com/cjj826/LongJudgeBench <br>Reliability script: https://github.com/cjj826/LongJudgeBench/blob/main/src/evaluation/compute_reliability.py | Repository LICENSE is MIT. Source: https://github.com/cjj826/LongJudgeBench/blob/main/LICENSE | We expect this to work for judge validation only. It should not replace product-quality benchmarks, but it directly informs judge choice for long outputs. |

## 2. Essay / argumentative writing datasets with quality annotations

| Dataset | claims and sources | usefulness for this paper |
|---|---|---|
| ASAP Automated Essay Scoring (ASAP AES) | Kaggle competition page exists for "The Hewlett Foundation: Automated Essay Scoring" and describes student-written essay scoring. Source: https://www.kaggle.com/c/asap-aes/data. Unverified: widely used AES setup has 8 prompts and about 13k essays with human scores, but exact count/license were not verified from a direct readable source in this bounded pass. | Prompt source and historical AES baseline only. Access often requires Kaggle terms, so do not make it a primary reproducibility dependency unless the paper can state the access terms clearly. |
| PERSUADE 2.0 [^19] | Over 25,000 argumentative essays from United States grades 6-12; 15 prompts; two writing tasks, independent and source-based; provides holistic essay scores and discourse/argumentative element effectiveness scores. Sources:<br>Repo: https://github.com/scrosseye/persuade_corpus_2.0 <br>Zenodo record: https://zenodo.org/records/8221504 | Strong prompt-source dataset and human-quality anchor. It gives realistic argumentative prompts and a distribution of student quality, but generated LLM outputs should be judged by a new rubric because student-score scales are not directly comparable to LLM long-form quality. |
| ICLE / ICLE++ [^5] | ICLE++ is a corpus of persuasive student essays annotated with holistic and trait-specific scores, designed to test generalization beyond ASAP and support multi-trait/cross-prompt AES. Source: https://github.com/samlee946/ICLE-PlusPlus | Good held-out human-quality anchor outside ASAP/PERSUADE. Use for calibrating rubrics on persuasive writing traits, not as a main generation benchmark unless ICLE base-text access/license is cleared. |
| ArgRewrite V.2 [^11] | Annotated argumentative revisions corpus; studies student interactions with a natural language processing (NLP)-based revision assistant and whether feedback forms encourage effective revisions. Source: https://github.com/omidkashefi/ArgRewrite | Process-level precedent rather than prompt bank. Useful for defining revision intent categories and for evaluating whether our reviewer/monitor produces useful revision operations. |
| Revision Quality Prediction [^12] | Predicts whether argumentative revisions are successful; uses annotated elementary essays and college revision desirability corpus; code asks users to obtain data from PETAL Pittsburgh. Sources:<br>Repo: https://github.com/ZhexiongLiu/Revision-Quality-Prediction <br>PETAL data page: https://petal-cs-pitt.github.io/data.html | Useful for process trace analysis. Compare agent reviewer actions against human notions of successful argument revision. This is not a primary product-quality benchmark. |

## 3. LLM-as-judge methodology for writing quality

### 3.1 Biases and mitigations

- MT-Bench / Chatbot Arena [^13] paper identifies position bias, verbosity bias, self-enhancement bias, and limited reasoning ability; GPT-4 matched human preferences above 80% agreement in their studied setup, with 80 MT-Bench questions, 3K expert votes, and 30K arena conversations released. Sources:
  - Judge code: https://github.com/lm-sys/FastChat/tree/main/fastchat/llm_judge
- FastChat judge prompts explicitly instruct the judge to avoid position bias, length influence, and assistant-name bias; implementation supports single grading, pairwise-baseline, and pairwise-all modes. Sources:
  - Judge prompts: https://github.com/lm-sys/FastChat/blob/main/fastchat/llm_judge/data/judge_prompts.jsonl
  - Judgment script: https://github.com/lm-sys/FastChat/blob/main/fastchat/llm_judge/gen_judgment.py
- G-Eval [^14] uses task definition + criteria + Chain-of-Thought (CoT)-generated evaluation steps + form-filling scores, and reports stronger Spearman correlation with human judgments on summarization than prior metrics. It also warns that LLM evaluators can prefer LLM-generated summaries over human-written summaries. Sources:
  - Repo: https://github.com/nlpyang/geval
- Prometheus 2 [^15] supports both direct assessment and pairwise ranking with user-defined rubrics; the paper/repo emphasize open evaluator transparency and report human/proprietary-judge correlation/agreement. Sources:
  - Repo: https://github.com/prometheus-eval/prometheus-eval
- LongJudgeBench [^10] specifically studies long-form judge reliability; it reports task-specific length sensitivity, that rubric/reference modes help on some datasets and hurt on others, and no single judge is universally reliable. Sources:
  - Repo: https://github.com/cjj826/LongJudgeBench

### 3.2 Recommended judge design for our experiment

Recommended protocol:

1. Product-quality pointwise score. For each output, ask two judge families to score independently on 5 dimensions:
   - Instruction Fulfillment
   - Organization/Global Coherence
   - Content Adequacy/Depth
   - Style/Voice/Audience Fit
   - Factuality/Constraint Fidelity
   Use a 1-5 anchored rubric with JSON output and a short evidence quote/rationale.
2. Pairwise preference score. For every prompt, compare the 6 arms in a balanced tournament: 15 unordered arm pairs, A/B and B/A orders, therefore 30 pairwise judgments per prompt per judge. Count ties explicitly. This controls position bias and reduces scale compression.
3. Blinding and presentation controls. Hide condition names from judges and human annotators. Use neutral labels such as Output A/B or randomized anonymous identifiers (IDs). The human annotation user interface (UI) should randomize output order per comparison and hide benchmark/source names when feasible.
4. Judge/generator separation. Pin these run details:
   - Judge model versions
   - Prompts
   - Decoding parameters
   - Seeds
   Prefer judge models that are not used as generators. If overlap is unavoidable, run an explicit self-preference test by comparing judge-family outputs against non-overlapping outputs under swapped order.
5. Length control. Record word/token length. Report quality both raw and length-stratified. Add length-matched sensitivity analysis where possible. Otherwise include output length as a covariate in regression or Bradley-Terry [^18] analysis. Do not include length compliance in the same score as literary/content quality unless the benchmark requires it.
6. Multi-judge aggregation. Use one strong proprietary judge and one open evaluator or smaller verifier. If budgets allow, add a third judge specialized in writing. Aggregate by z-scored dimension average for pointwise and majority or Bradley-Terry [^18] for pairwise.
7. Human validation. Sample 180-240 pairwise comparisons. Stratify the sample by:
   - Benchmark
   - Arm pair
   - Prompt length
   - Output length gap
   - Close-vs-clear automatic decisions
   With 6 arms, this gives 12-16 human-checked examples for each of the 15 arm pairs. Use 3 annotators per comparison. Report human-human agreement, judge-human agreement, and disagreement analysis. This mirrors the 200-pair DoLoMiTes [^7] validation scale and the MT-Bench [^13] controlled preference protocol without making human annotation the whole experiment.

## 4. Process-level evaluation precedents

Product-only evaluation misses the central claim of a Flower & Hayes [^1]-inspired writing agent. Evaluate the process trace separately from final product quality.

- IteraTeR [^16] is a large-scale, multi-domain, edit-intention annotated corpus of iteratively revised text; it models revision depths, granularities, and edit intentions, and connects edit intentions to writing quality. Sources:
  - Repo: https://github.com/vipulraheja/IteraTeR
  - Dataset README: https://github.com/vipulraheja/IteraTeR/blob/main/dataset/README.md
- IteraTeR-HUMAN [^16] document-level split includes 481 train, 27 dev, 51 test documents; sentence-level split includes 3,254 train, 400 dev, 364 test; edit actions include add/delete/replace, spans, majority intent, raw intents from 3 annotators. Source: https://github.com/vipulraheja/IteraTeR/blob/main/dataset/README.md
- ArgRewrite V.2 [^11] was built around student-driven revision sessions for argumentative writing, including interaction with an NLP-based revision assistant. Sources:
  - Repo: https://github.com/omidkashefi/ArgRewrite
- Revision Quality Prediction [^12] frames argumentative revision quality as success/failure dependent on argument context and uses chain-of-thought generated argument contexts for prediction. Sources:
  - Repo: https://github.com/ZhexiongLiu/Revision-Quality-Prediction

Process fairness policy: all 6 arms receive identical input context, tools, output budget, and no web access. The STORM [^2]-style arm is therefore a linear outline/write/revise pipeline inspired by STORM, not the full retrieval-based STORM system. Retrieval, evidence gathering, and citation trace metrics are not applicable (N/A) by design for every arm.

For the 6-arm experiment, process metrics should be:

- Planning trace. Count goals and rate their specificity. Check whether goals cover audience, purpose, content, organization, and style. Check whether later steps refer back to goals.
- Translation trace. Check whether drafts ground claims in plan items. Check whether sections expand in a coherent order. Check whether the draft preserves constraints.
- Review trace. Count detected issues and issue types. Map revision intent to clarity, fluency, coherence, style, and meaning change. Check whether fixes improve final rubric scores.
- Monitor trace. Measure process order entropy and transitions between planning, translating, and reviewing. Check whether transitions respond to detected problems rather than a fixed sequence.
- STORM [^2]-style arm trace. Record outline structure, simulated question/answer or perspective decomposition if used, section allocation, and linear handoff completeness. Retrieval/evidence/citation traces are explicitly N/A under the no-retrieval policy.
- Ablation-specific checks. The no-goal-network arm should show fewer explicit goal references. The fixed-process-order arm should show lower adaptive transitions even if final quality is similar.

## 5. Final recommendation

### 5.1 Primary benchmark shortlist

1. WritingBench [^3]
   - Why: best match for general-purpose writing, broad domains, explicit criteria, current leaderboard/evaluation scripts
   - Fairness: high; all 6 arms can submit final outputs to the same query set under the equal-context/no-retrieval policy
   - Risk: some prompts include long materials and domain-specific details; ensure identical input context and output budget

2. HelloBench [^4]
   - Why: explicitly targets long text generation and has checklist-wise evaluation plus human annotation/regression tooling
   - Fairness: high; use the same wrapped prompt and fixed generation budget for all systems
   - Risk: contains multiple task types; report subtask breakdown and avoid overclaiming "writing" from summarization/chat alone

3. DoLoMiTes [^7]
   - Why: best match for structured expert writing, planning, and methodical output
   - Fairness: high; all 6 arms get the same task description and input example, with retrieval disabled
   - Risk: recompute the released archive before final reporting to resolve the split-size conflict

Optional supplementary axis: LongBench-Write [^6]

- Use only for length-control analysis after clearing benchmark prompt-file license/provenance.
- Do not count it as a primary benchmark.

### 5.2 Prompt-source / human-anchor datasets

1. PERSUADE 2.0 [^19]
   - Use 15 prompts as argumentative writing prompt templates.
   - Use holistic score distribution to calibrate human quality anchors.
   - Do not train on student essays for this paper unless the project team reviews license and consent scope.

2. ICLE++ [^5]
   - Use as external validation of essay-trait rubrics and cross-prompt generalization
   - Good for argumentative/persuasive writing traits, weaker for creative/general writing

### 5.3 Judge setup

- Run pointwise rubric with JSON schema on all outputs.
- Run pairwise A/B and B/A on all 15 condition pairs for the primary subset: 30 judgments per prompt per judge.
- Blind condition labels and randomize presentation order for human annotators.
- Use at least two judges: a strong frontier judge for main numbers and a Prometheus 2 [^15]-style open evaluator for reproducibility/sensitivity.
- Pin exact:
  - Model versions
  - Prompts
  - Decoding parameters
  - Seeds
- Avoid judge/generator overlap where possible; otherwise run a self-preference diagnostic.
- Report:
  - Per-dimension score
  - Aggregate score
  - Pairwise win rate
  - Length-normalized or covariate-adjusted score
  - Judge agreement
- Human validation:
  - 180-240 pairwise comparisons
  - 3 annotators each
- Stratify human validation by:
  - Benchmark
  - Arm pair
  - Automatic-decision margin
  - Output-length gap
- Report:
  - Krippendorff's alpha/Fleiss' kappa
  - Raw agreement
  - Judge-human agreement

## 6. Inaccessible / unresolved items

- HelloBench [^4] raw data file paths listed in README returned 404. Do not rely on raw file path names until the experiment team checks cloning or HF/OpenCompass integration.
- Keep ASAP++ out of the dataset table until the team verifies a direct official paper/code/data URL.
- DoLoMiTes [^7] split size is a documented conflict: paper/archive-derived reporting gives 820 dev / 1,037 test, while the repo README says 830 dev / 1,037 test. The final experiment should recompute the split from the released archive and cite that reproducible count.
- Keep LongBench-Write [^6] as optional supplementary use because the LongWriter-6k [^6] SFT dataset's Apache-2.0 metadata does not clear `evaluation/*.jsonl` benchmark prompt-file license/provenance.
- Confirm the EQ-Bench Creative Writing license before using prompts in a paper artifact. The listed license URL returned 404: `https://github.com/EQ-bench/creative-writing-bench/blob/main/LICENSE`.
- WritingPreferenceBench [^8] has a license metadata conflict: GitHub README says ODC-BY, while Hugging Face metadata says Apache-2.0. Reconcile before redistribution.

## References

[^1]: Flower, Linda, and John R. Hayes. "A Cognitive Process Theory of Writing." College Composition and Communication, 1981. DOI: 10.2307/356600. https://doi.org/10.2307/356600
[^2]: Shao, Yijia, et al. "Assisting in Writing Wikipedia-like Articles From Scratch with Large Language Models." arXiv, 2024. https://arxiv.org/abs/2402.14207
[^3]: "WritingBench: A Comprehensive Benchmark for Generative Writing." arXiv, 2025. https://arxiv.org/abs/2503.05244
[^4]: "HelloBench: Evaluating Long Text Generation Capabilities of Large Language Models." arXiv, 2024. https://arxiv.org/abs/2409.16191
[^5]: "ICLE++: Modeling Fine-Grained Traits for Holistic Essay Scoring." North American Chapter of the Association for Computational Linguistics (NAACL), 2024. https://aclanthology.org/2024.naacl-long.468/
[^6]: "LongWriter: Unleashing 10,000+ Word Generation from Long Context LLMs." arXiv, 2024. https://arxiv.org/abs/2408.07055
[^7]: "DoLoMiTes: Domain-Specific Long-Form Methodical Tasks." arXiv, 2024. https://arxiv.org/abs/2405.05938
[^8]: "WritingPreferenceBench." arXiv, 2025. https://arxiv.org/abs/2510.14616
[^9]: "LongGenBench." arXiv, 2024. https://arxiv.org/abs/2409.02076
[^10]: "LongJudgeBench." arXiv, 2026. https://arxiv.org/abs/2606.01629
[^11]: Kashefi, Omid, et al. "ArgRewrite V.2." Language Resources and Evaluation, 2021. DOI: 10.1007/s10579-021-09567-z. https://doi.org/10.1007/s10579-021-09567-z
[^12]: "Is This a Good Revision?" Workshop on Innovative Use of Natural Language Processing for Building Educational Applications (BEA), 2023. https://aclanthology.org/2023.bea-1.24/
[^13]: Zheng, Lianmin, et al. "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena." arXiv, 2023. https://arxiv.org/abs/2306.05685
[^14]: Liu, Yang, et al. "G-Eval: Natural Language Generation (NLG) Evaluation using GPT-4 with Better Human Alignment." arXiv, 2023. https://arxiv.org/abs/2303.16634
[^15]: Kim, Seungone, et al. "Prometheus 2: An Open Source Language Model Specialized in Evaluating Other Language Models." arXiv, 2024. https://arxiv.org/abs/2405.01535
[^16]: Raheja, Vipul, et al. "IteraTeR: Improving Text Revision by Learning Where to Edit from Other Revision Tasks." Association for Computational Linguistics (ACL), 2022. https://aclanthology.org/2022.acl-long.250/
[^17]: Lin, Bill Yuchen, et al. "WildBench: Benchmarking LLMs with Challenging Tasks from Real Users in the Wild." arXiv, 2024. https://arxiv.org/abs/2406.04770
[^18]: Bradley, Ralph Allan, and Milton E. Terry. "Rank Analysis of Incomplete Block Designs: I. The Method of Paired Comparisons." Biometrika, 1952. DOI: 10.1093/biomet/39.3-4.324. https://doi.org/10.1093/biomet/39.3-4.324
[^19]: Crossley, S.A., Yu Tian, Perpetual Baffour, Alex Franklin, Meg Benner, and Ulrich Boser. "A large-scale corpus for assessing written argumentation: PERSUADE 2.0." Assessing Writing, 2024. DOI: 10.1016/j.asw.2024.100865. https://doi.org/10.1016/j.asw.2024.100865
