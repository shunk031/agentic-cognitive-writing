# Experiment protocol for the cognitive writing process

This document defines the paper experiment and the future experiment runner. It fixes the comparison, data handling, evaluation, process analysis, and reporting rules before any result is collected. The runner must fill every `REQUIRED_AT_RUNTIME` value before a run. An open value is a pre-run stop condition.

The primary evidence base is the independently reviewed and ACCEPTED survey in `docs/research/writing-eval-datasets.md`[^1]. Platform and plugin claims use `docs/research/skill-subagent-survey.md`[^2] and the system snapshot in `plugin/README.md`[^3], `plugin/skills/cognitive-writing/SKILL.md`[^4], `plugin/skills/cognitive-writing/references/ablation-variants.md`[^5], and `plugin/skills/cognitive-writing/references/trace-jsonl-schema.md`[^6].

The cited survey and plugin files are supplied by prerequisite PR #1, PR #2, and PR #3. They land on `main` only after those pull requests merge.[^11] Until then, the footnotes below point to stable accepted commit snapshots.

## Overview and research questions

Flower and Hayes describe writing as a set of thinking processes that a writer coordinates during composing. The processes are hierarchical and can be embedded in one another. Writing is goal-directed, and writers can create, develop, and regenerate goals as they learn from the act of writing.[^7] The Monitor coordinates Planning, Translating, and Reviewing. This protocol tests that account as an agent process rather than treating it as a claim about human inner experience.

The experiment uses the same assignment, supplied context, tool budget, output budget, and no-retrieval rule for every arm. Only the process instructions and the resulting observable process differ. The benchmark and judge choices follow the evaluation survey.[^1]

The questions are:

1. **RQ1.** Does the theory-based recursive Monitor and goal-network architecture produce better writing than a single-shot system and linear-stage pipelines?
2. **RQ2.** Which components matter? We compare the full plugin with the no-goal-network and fixed-process-order ablations.
3. **RQ3.** Do agent traces, analyzed as thinking-aloud protocols, show the goal creation and regeneration dynamics described by Flower and Hayes? This includes their prediction that the quantity and quality of middle-range goals relate to writing quality.
4. **RQ4.** Does the mapping replicate across platforms?

The pointwise two-judge composite is the sole CONFIRMATORY estimand (Holm families: per benchmark, 5 theory-arm-vs-other contrasts; 15 confirmatory tests total). The pairwise Bradley-Terry average is a PRIMARY REPORTED estimand but NON-CONFIRMATORY: reported with intervals, no Holm-adjusted claims attached; all other contrasts remain exploratory. The 15 confirmatory tests apply to the primary Codex pointwise composite. The Claude Code replication remains separate. The primary process estimands are the rates and distributions of goal events, adaptive process switches, interruptions, and pop-back events. The replication estimand is the direction and size of the A4 treatment effect under the secondary platform, reported separately from the primary platform.

## Arms

All six arms receive identical input context. The runner must expose the same local tools, context window policy, timeout, output budget, and number of allowed attempts to every arm. No arm may use web search, network retrieval, external browsing, or an unprovided source. The A3 perspective and question steps use only the supplied assignment and context.

| Arm | Process specification | Required trace behavior |
| --- | --- | --- |
| A1 single-shot | One generation pass from the assignment and supplied context. No explicit planning or review stage. | Record the externally visible generation event. Do not infer hidden goals or stages. |
| A2 linear stages | One pass each through Pre-Write, Write, and Re-Write. The order is fixed and each stage hands its output to the next. | Record the three stage transitions and their outputs. Record no unobserved reasoning. |
| A3 STORM-style linear pipeline without retrieval | Perspective discovery, simulated question and answer, outline, draft, and polish. This is inspired by STORM's separated planning and writing modules, but it omits retrieval, source gathering, and citation generation under the equal-information policy. The surveys describe this no-retrieval adaptation and the related STORM pipeline precedent.[^1][^2] | Record perspective, simulated QA, outline, draft, and polish structure. Retrieval, evidence-gathering, and citation traces are `N/A` by design. |
| A4 proposed plugin | The documented cognitive-writing plugin. The Monitor selects among Planning, Translating, and Reviewing. The Planner develops a hierarchical goal network. The Translator drafts. The Reviewer evaluates and revises. Generate and Evaluate may interrupt another process. | Use the plugin's append-only `.writing/trace/process.jsonl` and goal-network files. Record the normal loop with no ablation marker. |
| A5 no goal network | The plugin's documented `no-goal-network` variant. The assignment acts as one implicit objective. The Monitor does not create, develop, or regenerate hierarchical goal IDs. | Keep an existing `goals.md` unchanged. Continue recording process switches. Set `ablation` to `no-goal-network` in each applicable trace event. |
| A6 fixed process order | The plugin's documented `fixed-linear-order` variant. Repeat `planning -> translating -> reviewing` for each pass. Generate and Evaluate may still interrupt when new knowledge, a serious goal conflict, or the growing text requires it. Return to the prescribed order after the interruption. | Keep the ordinary goal network and trace. Set `ablation` to `fixed-linear-order` in each applicable trace event. |

A5 and A6 are session variants, not forks of the plugin. The runner must apply the exact variant names and behavior in `plugin/skills/cognitive-writing/references/ablation-variants.md`.[^5] All full and ablated runs use the same assignment, starting draft, model settings, and user decisions.

The plugin mapping is an implementation of the theory, not a claim that the 1981 paper specifies these files. The user owns rhetorical intent, factual authority, final wording, and publication. The Monitor owns process coordination. The Planner, Translator, and Reviewer act within their documented delegated roles.[^4]

## Benchmarks and data gates

### Primary benchmarks

The primary set is WritingBench, HelloBench, and the DoLoMiTes development subset. The evaluation survey selected these three because they cover broad writing tasks, long-text generation, and structured expert writing.[^1]

| Benchmark | Planned material | Run rule and gate |
| --- | --- | --- |
| WritingBench | Use the pinned curated release. The survey reports 1,000 real-world writing queries across six domains and 100 subdomains, with query-specific criteria.[^1] | Use the complete pinned query manifest unless a documented data failure blocks an item. Keep blocked items in the run accounting. Record the final count and the release commit or archive hash. |
| HelloBench | Use the pinned testing set. The survey reports 647 samples across five tasks and 38 subcategories, with long-text and checklist-based evaluation support.[^1] | Use the complete pinned manifest. Keep blocked items in the run accounting. Report results by task and subcategory as well as in aggregate. Record the final count and the release commit or archive hash. |
| DoLoMiTes | Use only the development subset after recomputing the split from the downloaded archive. The survey reports a conflict between 820 dev and 1,037 test examples from the paper/archive and 830 dev and 1,037 test examples in the repository README.[^1] | Recompute the split before the first scored run. Save the archive hash, split script version, and observed counts. Do not use the test portion for primary analysis. The expected paper/archive count is 820 dev and 1,037 test, but the archive-derived count is authoritative. |

The runner materializes one immutable prompt manifest per benchmark. Each row contains a stable prompt ID, benchmark name, source version, prompt text or a permitted source reference, requested output constraints, and a hash. The manifest is the only prompt input used by a run.

### Prompt sources and human anchors

PERSUADE 2.0 supplies 15 argumentative prompt templates. Its human scores provide calibration anchors, not target labels for model outputs. ICLE++ supplies an external persuasive-writing anchor for rubric calibration and cross-prompt checks. The survey recommends both datasets for this role and cautions against treating student essay scores as directly comparable to the new model-quality scores.[^1]

The runner must not train on or alter the student essays for this experiment. It may use the 15 PERSUADE 2.0 prompt templates as a separate argumentative anchor set after recording the permitted source reference and license status. ICLE++ remains a calibration and generalization check unless its base-text access is cleared.

### Optional supplementary benchmark

LongBench-Write English is optional and supplementary. It may be added only after the benchmark prompt-file license and provenance are cleared. If used, it is a length-control and robustness axis, not a fourth primary benchmark. The survey reports that the SFT data license does not automatically establish permission for the benchmark prompt files.[^1]

EQ-Bench Creative Writing and WritingPreferenceBench are excluded from this protocol because their licensing or metadata remains unresolved in the evidence base. They must not enter a paper result, prompt manifest, or redistributed artifact without a new license review.[^1]

## Platforms and models

### Platform assignments

The primary platform is OpenAI Codex headless, invoked with `codex exec`. All six arms run as skill or prompt variants over one pinned GPT-family generator model. The secondary replication runs the same six arm specifications under Claude Code headless with one pinned Claude-family generator model. A4 to A6 use the plugin, while A1 to A3 use the corresponding prompt variants. The platform survey describes the shared skill and platform-adapter design.[^2]

`VERIFIED 2026-09-02`: OpenAI documents `codex exec` as its non-interactive mode for scripts and CI, with final output on stdout and progress on stderr. Anthropic documents Claude Code headless execution with `claude -p` or `claude --print`. The runner must follow the installed CLI version's syntax and record that version.[^8][^9]

The runner uses these conceptual interfaces:

```text
PRIMARY_GENERATOR: codex exec <REQUIRED_AT_RUNTIME flags> <prompt or stdin>
SECONDARY_GENERATOR: claude --print <REQUIRED_AT_RUNTIME flags> <prompt or stdin>
```

The exact command flags are versioned in `experiments/arms/` and recorded in every run manifest. The run must not silently fall back to an interactive mode.

The runner starts one top-level session per arm and prompt. In Codex A4 to A6 runs, the plugin may request native Codex subagents as documented. The plugin must not spawn nested `codex exec` children. If native delegation is unavailable and the Monitor performs a delegated role itself, the trace must record that fallback.

### Generator and judge separation

The primary Codex GPT-family generators are judged by a Claude-family frontier judge and the same Prometheus-2-style open evaluator used for replication. The Claude Code Claude-family generators are judged by a GPT-family frontier judge and that same open evaluator. The open evaluator must belong to a third model family. The assignment is symmetric across the two platform runs.

The runner must pin each value below. A placeholder blocks the run:

| Value | Required setting |
| --- | --- |
| Codex generator model | `REQUIRED_AT_RUNTIME: exact GPT-family model ID and release` |
| Claude Code generator model | `REQUIRED_AT_RUNTIME: exact Claude-family model ID and release` |
| Codex frontier judge | `REQUIRED_AT_RUNTIME: exact Claude-family frontier model ID and release` |
| Claude Code frontier judge | `REQUIRED_AT_RUNTIME: exact GPT-family frontier model ID and release` |
| Shared open evaluator | `REQUIRED_AT_RUNTIME: exact third-family Prometheus-2-style evaluator checkpoint, revision, and serving configuration` |
| Generator system and arm prompts | `REQUIRED_AT_RUNTIME: frozen prompt files and hashes` |
| Judge prompts and JSON schemas | `REQUIRED_AT_RUNTIME: frozen prompt files, schema files, and hashes` |
| Decoding parameters | `REQUIRED_AT_RUNTIME: temperature, top-p or equivalent, max output tokens, stop rules, and timeout` |
| Seeds | `REQUIRED_AT_RUNTIME: fixed generation, judge, sampling, and presentation seeds where the platform allows them` |
| CLI and plugin versions | `REQUIRED_AT_RUNTIME: exact Codex version, Claude Code version, plugin commit, and runner commit` |
| Generator and judge family audit | `REQUIRED_AT_RUNTIME: recorded base-model families and runtime verification that each frontier judge differs from the generator family and the open evaluator belongs to a third family` |

The runner assigns judges explicitly. Codex outputs use `{Claude-family frontier judge, shared third-family open evaluator}`. Claude Code outputs use `{GPT-family frontier judge, shared third-family open evaluator}`. The runner records each judge's base-model family and the generator family for every scored output. It fails the run if a frontier judge shares the generator family or if the open evaluator does not belong to a third family. The audit verifies the family labels at runtime rather than trusting configuration names.

The no-retrieval rule applies to generators and judges. Judges receive the assignment, the permitted supplied context, and the blinded output or output pair. They do not receive agent traces, internal role names, or condition labels.

## Product evaluation

The product unit is one output for one prompt, arm, platform, and generator seed. The runner preserves the raw output byte-for-byte and also stores the normalized text used for token and word counts. Normalization may remove only transport wrappers defined in the runner specification. It must not rewrite content, repair claims, or change paragraph boundaries.

### Pointwise quality

Each assigned judge scores every output independently on five dimensions. Each raw score is an integer from 1 to 5. The judge returns a short evidence quote for each dimension. For each platform, the runner z-scores each dimension within each benchmark and judge. It then averages the five z-scores into that judge's level composite. For platform `p`, judge `j`, benchmark `b`, dimension `d`, and output `i`, the value is `z(i,p,j,b,d) = (raw(i,p,j,b,d) - mean(p,j,b,d)) / sd(p,j,b,d)`. A zero standard deviation uses the frozen zero-variance rule in the runtime gate. Length compliance never enters a quality score.

On the primary Codex platform, every output receives both the Claude-family frontier judge and the open evaluator. The primary pointwise product-quality estimand is the equal-weight mean of the two judge-level composites, `Q_primary(i) = 0.5 * C_Claude(i) + 0.5 * C_open(i)`. Per-judge raw scores and per-judge composites are reported as sensitivity analyses. On the Claude Code replication, every output receives the GPT-family frontier judge and the same open evaluator. The replication estimand uses the same equal-weight construction, `Q_replication(i) = 0.5 * C_GPT(i) + 0.5 * C_open(i)`. Replication inference stays separate from the primary inference. The analysis does not pool platforms. Cross-platform agreement is descriptive for RQ4.

| Dimension | Score 1 | Score 3 | Score 5 |
| --- | --- | --- | --- |
| Instruction fulfillment | Misses the central task or constraints. | Completes the main task but misses material requirements. | Meets the task and all material constraints. |
| Organization and global coherence | Ideas or sections do not form a usable whole. | The response is readable but has visible structural gaps. | The response has a clear structure and sustained global coherence. |
| Content adequacy and depth | Content is missing, shallow, or unusable for the task. | Content covers the main points with uneven development. | Content is sufficient, developed, and appropriately deep. |
| Style, voice, and audience fit | Style or voice conflicts with the requested audience or genre. | Style is partly suitable but inconsistent. | Voice, style, and detail fit the audience and genre throughout. |
| Factuality and constraint fidelity | The response contradicts the supplied context or violates important constraints. | Minor errors or unsupported claims remain. | Claims fit the supplied context, uncertainty is handled honestly, and constraints are obeyed. |

The last dimension is judged against the assignment and supplied context. The no-retrieval policy means that a judge must not reward outside fact gathering. A quote must be copied from the output or the supplied context and must be short enough to identify the evidence without reproducing the response.

The pointwise JSON object follows this contract:

```json
{
  "prompt_id": "<prompt ID>",
  "arm_id": "<blind condition ID>",
  "platform": "<codex|claude>",
  "judge_family": "<claude_frontier|gpt_frontier|open_evaluator>",
  "scores": {
    "instruction_fulfillment": 1,
    "organization_global_coherence": 1,
    "content_adequacy_depth": 1,
    "style_voice_audience_fit": 1,
    "factuality_constraint_fidelity": 1
  },
  "evidence_quotes": [
    {"dimension": "instruction_fulfillment", "quote": "<short exact quote>"}
  ],
  "judge_level_composite": 0.0,
  "uncertainties": ["<short uncertainty or empty array>"]
}
```

The runner rejects invalid JSON, missing dimensions, scores outside 1 to 5, or evidence quotes that do not occur in the judged output or supplied context. It retries an invalid judge response only under the fixed retry count in the run manifest. It never gives a failed condition extra content or attempts.

### Balanced pairwise tournament

The six arms produce 15 unordered arm pairs. For every prompt and assigned judge, run both A/B and B/A presentations. This produces 30 judgments per prompt per judge. The condition labels are blind, the output order is randomized by a recorded seed, and ties are explicit outcomes. These controls follow the evaluation survey's judge design and its position and verbosity bias mitigations.[^1]

The pairwise JSON object follows this contract:

Every record must include the fields shown below.

```json
{
  "prompt_id": "<prompt ID>",
  "platform": "<codex-primary|claude-code-replication>",
  "judge_id": "<judge ID>",
  "judge_family": "<claude_frontier|gpt_frontier|open_evaluator>",
  "pair_id": "<unordered pair ID>",
  "presentation": "<A|B or B|A>",
  "winner": "<A|B|tie>",
  "evidence_quotes": {
    "A": ["<short exact quote>"],
    "B": ["<short exact quote>"]
  },
  "reason": "<brief comparison grounded in the rubric>"
}
```

Group pairwise records on `(platform, judge_id)` before fitting each judge-specific Bradley-Terry model. Use `judge_family` to verify each group against the runtime judge manifest. Compute the equal-weight average from those per-judge fits within each platform. Do not combine records from different platforms or judges before fitting.

The pointwise two-judge composite is the sole CONFIRMATORY estimand (Holm families: per benchmark, 5 theory-arm-vs-other contrasts; 15 confirmatory tests total). The pairwise Bradley-Terry average is a PRIMARY REPORTED estimand but NON-CONFIRMATORY: reported with intervals, no Holm-adjusted claims attached; all other contrasts remain exploratory. Fit each Bradley-Terry model with a predeclared tie treatment. For arm `a`, let `theta_Codex(a, Claude)` and `theta_Codex(a, open)` be the judge-specific ability estimates under the same reference-arm constraint. The Codex pairwise average is `theta_primary(a) = 0.5 * theta_Codex(a, Claude) + 0.5 * theta_Codex(a, open)`. For the replication, use `theta_replication(a) = 0.5 * theta_ClaudeCode(a, GPT) + 0.5 * theta_ClaudeCode(a, open)`. Fit and report the two platform models separately. Report per-judge win rates in addition to the equal-weight estimates. If the selected implementation cannot fit ties, report tie-aware win rates with ties counted as half a win and the raw win, loss, and tie counts. Do not pool platforms.

### Length and judge sensitivity

The runner records raw word count and model-token count when the pinned tokenizer makes the latter available. It reports every quality result both raw and length-stratified. It also reports output-length gaps for every pair. The length strata and minimum cell size are `REQUIRED_AT_RUNTIME` and must be fixed before scoring.

Length compliance is a standalone outcome for prompts with an explicit requested length. Let `x` be the requested length and `y` the produced length in the same frozen unit. Report relative deviation `D = |y - x| / x`. Report compliance `I(D <= tau)` for the prespecified tolerance `tau = 0.20`, and report the compliance rate as the mean of this indicator by arm, benchmark, and platform. Also report the LongWriter-style length score. For `x > 0` and `y > 0`, use `S = 100 * max(0, 1 - (y / x - 1) / 3)` when `y > x`, and `S = 100 * max(0, 1 - (x / y - 1) / 2)` when `y <= x`. If `y = 0`, set `S = 0` and `D = 1`. If a prompt has no explicit length request, report these outcomes as `N/A`. The exact unit, formula, zero-output rule, and `tau` value are repeated in the runtime gate. Length compliance and the length score never enter either quality estimand.[^10]

The runner performs a judge and generator family overlap audit. If any judge also generated an output, it runs the self-preference test on a blinded subset with the same A/B and B/A controls. The test estimates whether that judge family changes its choices for its own outputs. If the planned non-overlap assignment holds, the manifest records that the test was not triggered by direct overlap and reports swapped-judge rank agreement as the corresponding sensitivity check. The survey recommends this diagnostic when overlap cannot be avoided.[^1]

The covariate sensitivity analysis fits the prespecified quality and pairwise models with benchmark, prompt length, output length, output-length gap, presentation order, judge family, and platform terms where applicable. It compares the adjusted treatment estimates with the raw and length-stratified estimates. The model formula, covariate coding, missing-value rule, and interaction terms are `REQUIRED_AT_RUNTIME` and must appear in the analysis manifest before results are inspected.

## Human validation

Human validation samples 180 to 240 pairwise comparisons from the primary results. It uses three recruited annotators per comparison. Sampling is stratified by benchmark, arm pair, prompt length, output-length gap, and automatic-decision margin. The presentation order is randomized per annotator. Annotators see the assignment and two anonymized outputs, but not arm names, platform names, judge names, traces, or automatic labels. This design follows the scale and controls recommended in the evaluation survey.[^1]

The annotation form records `A`, `B`, or `tie`, an optional short reason, annotator ID, comparison ID, presentation seed, and adjudication status. Annotators must not discuss cases during independent scoring. The study record must state recruitment, compensation, instruction text, consent, data handling, and any review or ethics requirement before collection.

Report Krippendorff's alpha, Fleiss' kappa, raw agreement, and agreement between each automatic judge family and the human majority. Report disagreement by benchmark, arm pair, output-length gap, and automatic-decision margin. Do not discard ties or cases with disagreement.

## Process analysis

### Trace source and interpretation

For A4, A5, and A6, the authoritative source is the plugin's append-only `.writing/trace/process.jsonl`, together with `.writing/goals.md` and the final draft. Each line is one JSON object. The documented event types are `process_switch`, `goal_created`, `goal_developed`, and `goal_regenerated`. Process switches include `from_process` and `to_process`. Goal events include `goal_id` and `parent_goal_id`. The plugin records the responsible actor, decision, evidence, uncertainty, and applicable ablation.[^6]

For A1, A2, and A3, the runner records only externally observed generation or stage events in the same per-run trace location. An adapter must not invent goals, hidden decisions, or internal reasoning. Plugin-specific fields that cannot be observed are `N/A` in the derived analysis. The baseline stage traces support structural comparisons. The goal-network and recursive-monitor estimands are interpreted primarily on A4 to A6, where the plugin documents those semantics.

The trace is an operational analogue of a thinking-aloud protocol, not a direct transcript of an agent's private state. The analysis therefore distinguishes logged actions from claims about cognition. An event that lacks enough evidence for a code is marked ambiguous and remains in the denominator for trace completeness.

### Metrics

The analysis extracts these measures from the trace and goal files:

| Process measure | Operational definition |
| --- | --- |
| Goal count | Count `goal_created`, `goal_developed`, and `goal_regenerated` events, plus the unique active goal IDs in `goals.md`. Report total, content, process, and criterion goals where the kind is available. |
| Goal specificity | Code each goal for an operational action, content target, audience or purpose target, and evaluative criterion. Report the coding rubric and double-code a reliability sample. Do not treat goal length alone as specificity. |
| Middle-range goal quantity | Count goals that connect a high-level rhetorical intention to a local prose or process action. The coding rule and examples are frozen before analysis. |
| Middle-range goal quality | Score whether each middle-range goal gives concrete direction, covers the rhetorical problem, and can be checked against the output. Report the mean and distribution, with coder agreement. |
| Goal regeneration | Count `goal_regenerated` events and verify that the old goal remains in history and the replacement has a new ID when its meaning materially changes. Record the evidence and stated rationale. |
| Process-switch transitions | Count transitions between Planning, Translating, Reviewing, and embedded Generate, Organize, Goal-setting, Evaluate, or Revise processes when the trace names them. Report transition counts and rates per run. |
| Process-order entropy | Compute Shannon entropy over normalized process sequences and over transition distributions. Report raw entropy, the number of observed states, and the normalization rule. |
| Generate and Evaluate interruptions | Count process switches into Generate or Evaluate while another process is active, using the process fields and explicit decision or evidence markers. Do not infer an interruption from text alone when the event is ambiguous. |
| Pop-back events | Count returns to an immediate parent goal after a child goal resolves. Use the child and parent IDs, status or history, and the next process event. Report unresolved parent links as trace-quality failures. |
| Revision intent | Map each revision to the IteraTeR-informed categories clarity, fluency, coherence, style, and meaning change. Record the edit operation and the evidence in the trace or draft diff. The survey identifies IteraTeR as the process-level revision precedent.[^1] |
| A3 outline and QA structure | Count discovered perspectives, simulated questions and answers, outline nodes, section handoffs, and polish passes. Retrieval and citation metrics are `N/A` under the common policy. |

The analysis correlates process measures with per-prompt product quality. It reports correlations for each judge family and for the prespecified aggregate, with benchmark and output length shown as covariates. A correlation does not establish that the process caused the quality difference.

## Statistical analysis

The prompt is the paired unit. Each arm receives the same prompt, and platform replications use the same prompt manifest. Invalid or missing outputs remain in the run accounting. The report gives the failure count and reason by arm and benchmark. It does not silently drop a condition that fails more often.

For pointwise quality, compute the primary equal-weight judge composite for each prompt and arm on each platform. The confirmatory contrasts compare A4 with A1, A2, A3, A5, and A6. Use paired bootstrap intervals or a paired Wilcoxon signed-rank test across prompts. Report mean and median paired differences, confidence intervals, the test statistic and p-value, and an effect size. Report raw 1 to 5 means, judge-level composites, and per-judge contrasts as sensitivity analyses. Run the same analysis by benchmark, but keep Codex and Claude Code inference separate.

For pairwise quality, report raw wins, losses, ties, per-judge tie-aware win rates, per-judge Bradley-Terry ability estimates, and the equal-weight judge average on each platform. Use prompt-level paired resampling for uncertainty. Report the effect size on the selected Bradley-Terry scale or the paired difference in tie-aware win rate. Keep Codex and Claude Code inference separate.

The pointwise two-judge composite is the sole CONFIRMATORY estimand (Holm families: per benchmark, 5 theory-arm-vs-other contrasts; 15 confirmatory tests total). The pairwise Bradley-Terry average is a PRIMARY REPORTED estimand but NON-CONFIRMATORY: reported with intervals, no Holm-adjusted claims attached; all other contrasts remain exploratory. For RQ1 and RQ2, run the 15 confirmatory contrasts on the primary Codex pointwise composite. The contrasts compare A4 with A1, A2, A3, A5, and A6 within each primary benchmark. Report the same five contrasts on the Claude Code replication separately, without pooled or confirmatory inference. Report the pairwise average with intervals, but attach no Holm-adjusted claims to it. For RQ4, compare platforms descriptively by direction, rank agreement, and standardized effect size. The analysis does not pool platforms.

Apply Holm correction within each primary-benchmark family of five confirmatory contrasts on the primary Codex pointwise composite. Do not apply Holm correction to the pairwise average or to any other contrast. Report the pairwise average with uncertainty intervals and no Holm-adjusted claims. The alternative hypotheses, missing-value rules, bootstrap resample count, confidence level, effect-size definitions, Bradley-Terry tie treatment, and ability-scale convention are `REQUIRED_AT_RUNTIME` and must be frozen before outcome inspection. Exploratory subgroup results use clear labels and do not replace the confirmatory estimates.

## Reproducibility and artifact plan

All runs are scripted under `experiments/`. The planned layout is:

```text
experiments/
├── config/       # frozen run, model, judge, and seed configurations
├── prompts/      # materialized prompt manifests and source hashes
├── arms/         # A1-A6 wrappers and platform-specific adapters
├── runner/       # execution, timeout, retry, and trace collection code
├── judge/        # pointwise and pairwise prompts, schemas, and runners
├── human/        # sampling manifest, annotation form, and agreement code
├── analysis/     # scoring, statistics, plots, and report tables
└── manifests/    # run manifests, checksums, and validation reports
```

The runner writes a manifest before each run. It records the benchmark release and hash, prompt manifest hash, arm ID, platform, CLI versions, plugin commit, model IDs, system and arm prompt hashes, judge prompt hashes, decoding parameters, output budget, tool policy, no-retrieval check, random seeds, retry policy, start time, and software environment identifiers that are safe to publish.

Every output, trace, judge response, human judgment, derived score, and analysis input is versioned or referenced by a content hash. Raw benchmark files are redistributed only when their license allows it. If redistribution is not allowed, version the materialization script, source version, hash, and a clear acquisition instruction instead. Do not place credentials or private prompt material in the repository.

The runner enforces the equal-tool and no-retrieval policy. It logs network-policy status and fails closed if a generator or judge requests an unpermitted retrieval action. It gives every arm the same timeout and retry budget. A retry cannot change the prompt, tool policy, model, or decoding parameters.

The runner validates every trace line as standalone JSON, validates required plugin fields for A4 to A6, checks that A5 and A6 markers match the selected variant, checks that blind labels are independent of arm IDs, and checks that the 15 unordered pairs have both presentation orders. A validation failure stops publication of the affected result.

## Threats to validity

**Construct validity.** A logged agent trace records actions selected by the plugin and runner. It does not prove that an agent has human-like thoughts. The RQ3 analysis uses the thinking-aloud analogy only to define observable process measures.

**Comparison validity.** The equal-tool and no-retrieval policy makes the A3 arm a STORM-style pipeline, not the full retrieval-based STORM system. This limits claims about source-grounded research performance. It also prevents retrieval from becoming an unbalanced advantage for one arm.

**Judge validity.** Pointwise and pairwise judges can show position, verbosity, self-preference, and model-family bias.[^1] Blind labels, both presentation orders, two judge families, evidence quotes, length-stratified results, overlap audits, and human validation address these risks. They cannot remove them.

**Length confounding.** A longer answer may appear better to a judge even when it adds little value. The protocol records length, reports raw and length-stratified results, and keeps length compliance out of the quality score.

**Platform confounding.** Codex and Claude Code differ in CLI behavior, native delegation, and model family. The replication keeps the task and process mapping fixed while reporting platforms separately. A cross-platform result is a replication of the direction and process signature, not proof that the systems are identical.

**Benchmark coverage.** WritingBench, HelloBench, and DoLoMiTes cover broad, long-text, and structured writing, but they do not represent every genre or language.[^1] PERSUADE 2.0 and ICLE++ provide argumentative anchors, not complete coverage.[^1]

**Trace completeness.** A crash, truncation, or adapter gap can hide a process event. The runner reports trace completeness and treats ambiguous or missing events as data-quality findings. It does not impute a goal or process switch.

**Data and licensing.** The DoLoMiTes split conflict and the unresolved LongBench-Write, EQ-Bench, and WritingPreferenceBench licensing require explicit gates.[^1] The analysis cannot use a source merely because a paper or repository mentions it.

## Open TODO gates

The owner must close every gate below before the first scored run. Codex records the decision and the evidence in the run manifest.

1. **DoLoMiTes split.** Download the released archive, recompute dev and test counts, save the script and archive hash, and cite the resulting count in the paper. Expected paper/archive counts are 820 dev and 1,037 test. The archive result controls if it differs.
2. **Benchmark materialization.** Pin WritingBench, HelloBench, and DoLoMiTes releases or commits. Materialize prompt manifests and record final item counts.
3. **LongBench-Write license.** Clear the benchmark prompt-file license and provenance before any supplementary use. Otherwise keep the benchmark excluded.
4. **PERSUADE 2.0 and ICLE++ access.** Record the permitted use of the 15 PERSUADE 2.0 prompts and the ICLE++ calibration material. Do not redistribute material outside its permission.
5. **Generator configuration.** Fill the exact model IDs, CLI versions, plugin commit, decoding parameters, output budgets, timeout, retry policy, and seeds.
6. **Judge configuration.** Fill the exact Claude-family frontier judge for Codex outputs, the exact GPT-family frontier judge for Claude Code outputs, and the same open evaluator for both platforms. Record each base-model family. Verify at runtime that each frontier judge differs from the generator family and that the open evaluator belongs to a third family, such as a Mistral-family evaluator. Freeze judge prompts, schemas, decoding parameters, seeds, the Bradley-Terry tie treatment, and the common ability-scale convention.
7. **Length analysis.** Freeze tokenizer versions, word-count rules, output-length strata, minimum cell sizes, and the covariate model before judging. For prompts with an explicit length constraint, freeze the length unit, `D = |y - x| / x`, compliance indicator `I(D <= 0.20)`, and LongWriter-style score `100 * max(0, 1 - (y / x - 1) / 3)` for `y > x`, or `100 * max(0, 1 - (x / y - 1) / 2)` for `0 < y <= x`, with score `0` when `y = 0`. Freeze the zero-variance z-score rule as well.
8. **Trace conformance.** Run one smoke test for each arm and platform. Validate trace JSONL, goal history, ablation markers, stage events, blind labels, pair balance, and no-retrieval enforcement.
9. **Human study.** Approve the 180 to 240 comparison sample, three-annotator assignment, recruitment and compensation text, consent, data handling, and any required ethics review.
10. **Statistical lock.** Freeze confirmatory contrast families, paired bootstrap or Wilcoxon settings, Holm correction, confidence level, effect sizes, tie handling, and missing-value rules.

If a new source check contradicts a settled design item or the plugin's documented behavior, stop the experiment and record the conflict. Do not resolve it by changing an arm after results exist.

[^1]: [Writing evaluation datasets survey at accepted commit `b66284d`](https://github.com/shunk031/agentic-cognitive-writing/blob/b66284dc47574987932c3be350e21b461e8fb397/docs/research/writing-eval-datasets.md)
[^2]: [Skill and subagent survey at accepted commit `711cf41`](https://github.com/shunk031/agentic-cognitive-writing/blob/711cf41142b13f5174ecdfb10dd1ade272c5a118/docs/research/skill-subagent-survey.md)
[^3]: [Cognitive writing plugin README at commit `1facf95`](https://github.com/shunk031/agentic-cognitive-writing/blob/1facf95b3ce71fac8baa0f6bf75eb25aea48e264/plugin/README.md)
[^4]: [Cognitive writing skill at commit `1facf95`](https://github.com/shunk031/agentic-cognitive-writing/blob/1facf95b3ce71fac8baa0f6bf75eb25aea48e264/plugin/skills/cognitive-writing/SKILL.md)
[^5]: [Plugin ablation variants at commit `1facf95`](https://github.com/shunk031/agentic-cognitive-writing/blob/1facf95b3ce71fac8baa0f6bf75eb25aea48e264/plugin/skills/cognitive-writing/references/ablation-variants.md)
[^6]: [Plugin trace schema at commit `1facf95`](https://github.com/shunk031/agentic-cognitive-writing/blob/1facf95b3ce71fac8baa0f6bf75eb25aea48e264/plugin/skills/cognitive-writing/references/trace-jsonl-schema.md)
[^7]: Linda S. Flower and John R. Hayes, "A Cognitive Process Theory of Writing," *College Composition and Communication* 32, no. 4 (1981): 365-387. [JSTOR](https://www.jstor.org/stable/356600).
[^8]: `VERIFIED 2026-09-02`: [OpenAI Codex non-interactive mode](https://developers.openai.com/codex/non-interactive-mode).
[^9]: `VERIFIED 2026-09-02`: [Anthropic Claude Code headless mode](https://docs.anthropic.com/en/docs/claude-code/headless).
[^10]: `VERIFIED 2026-09-02`: [LongWriter length evaluator](https://github.com/THUDM/LongWriter/blob/main/evaluation/eval_length.py).
[^11]: The survey and plugin files will land on `main` through [PR #1](https://github.com/shunk031/agentic-cognitive-writing/pull/1), [PR #2](https://github.com/shunk031/agentic-cognitive-writing/pull/2), and [PR #3](https://github.com/shunk031/agentic-cognitive-writing/pull/3). These links point to the prerequisite pull requests that must merge before those files are available on `main`.
