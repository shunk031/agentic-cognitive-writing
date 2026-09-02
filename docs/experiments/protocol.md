# Experiment protocol for the cognitive writing process

This protocol defines the paper experiment and future runner. It fixes comparison, data handling, evaluation, process analysis, and reporting rules before any result is collected.

The runner must fill every `REQUIRED_AT_RUNTIME` value before a run. An open value is a pre-run stop condition.

**Source snapshots.** The protocol uses benchmark, evaluation, platform, and plugin evidence from these sources:

- **Survey snapshots.** [Evaluation survey](https://github.com/shunk031/agentic-cognitive-writing/blob/b66284dc47574987932c3be350e21b461e8fb397/docs/research/writing-eval-datasets.md) / [platform survey](https://github.com/shunk031/agentic-cognitive-writing/blob/711cf41142b13f5174ecdfb10dd1ade272c5a118/docs/research/skill-subagent-survey.md)
- **Main plugin snapshots.** [README](https://github.com/shunk031/agentic-cognitive-writing/blob/d0d6da7d0607f9d54b35973c2cf4e10d779a15dd/plugin/README.md) / [core skill](https://github.com/shunk031/agentic-cognitive-writing/blob/d0d6da7d0607f9d54b35973c2cf4e10d779a15dd/plugin/skills/cognitive-writing/SKILL.md) / [trace schema](https://github.com/shunk031/agentic-cognitive-writing/blob/d0d6da7d0607f9d54b35973c2cf4e10d779a15dd/plugin/skills/cognitive-writing/references/trace-jsonl-schema.md)
- **Experiments plugin snapshots.** [Fixed-order skill](https://github.com/shunk031/agentic-cognitive-writing/blob/d0d6da7d0607f9d54b35973c2cf4e10d779a15dd/experiments/plugin/skills/cognitive-writing-fixed-order/SKILL.md) / [no-goal-network skill](https://github.com/shunk031/agentic-cognitive-writing/blob/d0d6da7d0607f9d54b35973c2cf4e10d779a15dd/experiments/plugin/skills/cognitive-writing-no-goal-network/SKILL.md)

## Theory test and research questions

This protocol tests whether the theory-based recursive process improves writing and whether its traces show the predicted goal dynamics.

Flower and Hayes' *A Cognitive Process Theory of Writing* [^1] describes writing as a set of thinking processes that a writer coordinates during composing. The processes are hierarchical and can be embedded in one another. Writing is goal-directed, and writers can create, develop, and regenerate goals as they learn from the act of writing. The Monitor coordinates Planning, Translating, and Reviewing.

The protocol tests that account as an agent process rather than treating the account as a claim about human inner experience.

The experiment has six experimental conditions, identified as A1 through A6. The experiment holds the assignment, supplied context, tool budget, output budget, and no-retrieval rule constant across those conditions. Only the process instructions and the resulting observable process differ. The benchmark and judge choices follow the [evaluation survey](https://github.com/shunk031/agentic-cognitive-writing/blob/b66284dc47574987932c3be350e21b461e8fb397/docs/research/writing-eval-datasets.md).

The research questions (RQ) are:

1. **RQ1.** Does the theory-based recursive Monitor and goal-network architecture produce better writing than a single-shot system and linear-stage pipelines? A goal network is a hierarchy of writing goals that the Monitor coordinates during drafting.
2. **RQ2.** Which components matter? We compare the full plugin with ablation conditions A5 and A6. An ablation condition removes or constrains one component of the full design.
3. **RQ3.** Do agent traces, analyzed as thinking-aloud protocols that record observable writing actions, show the goal creation and regeneration dynamics described by Flower and Hayes [^1]? The RQ3 analysis includes Flower and Hayes' prediction that the quantity and quality of middle-range goals, which connect broad rhetorical aims to local writing actions, relate to writing quality.
4. **RQ4.** Does the mapping replicate across platforms?

The protocol defines the analysis terms used below. An estimand is the quantity that the analysis plans to estimate. Pointwise scoring gives each output an independent rubric score. A Bradley-Terry model [^11] estimates relative condition abilities from pairwise choices. Holm correction [^15] controls the family-wise error rate.

The pointwise two-judge composite is the sole CONFIRMATORY estimand. The composite is the prespecified quantity used for confirmatory tests. Use one correction family per benchmark on the primary Codex pointwise composite. Each family contains the five comparisons of the theory-based condition A4 with the other conditions, for 15 confirmatory tests total.

The pairwise Bradley-Terry [^11] average is a PRIMARY REPORTED estimand but NON-CONFIRMATORY. The pairwise average estimates the relative ability of the conditions from pairwise choices. Report it with intervals and attach no Holm-adjusted claims. All other contrasts remain exploratory.

The protocol also defines process and replication estimands. The primary process estimands are goal events, adaptive process switches, interruptions, and pop-back events. Report rates and distributions for each. The replication estimand is the direction and size of the A4 treatment effect under the secondary platform. Report it separately from the primary platform.

## Six conditions under equal information

The equal-information policy gives all six conditions identical input context. The runner must expose the same local tools, context window policy, timeout, output budget, and number of allowed attempts to every condition. No condition may use a source outside the supplied assignment and context. The no-retrieval policy forbids web search, network retrieval, external browsing, and any unprovided source.

**Single-shot condition A1.** Condition A1 makes one generation pass from the assignment and supplied context. The condition has no explicit planning or review stage. The runner records the externally visible generation event and does not infer hidden goals or stages.

**Linear-stages condition A2.** Condition A2 makes one pass through Pre-Write, Write, and Re-Write. The order is fixed, and each stage hands its output to the next. The runner records the three stage transitions and their outputs. The runner records no unobserved reasoning.

**[STORM](https://github.com/stanford-oval/storm)**[^2]-style condition A3 without retrieval. Condition A3 uses only the supplied assignment and context for perspective discovery, simulated question answering (QA), outline, draft, and polish. Citation generation is omitted under the equal-information policy. The pipeline separates planning from writing and omits retrieval and source gathering.

**A3 trace and evidence handling.** The runner records the five stages. Retrieval, evidence-gathering, and citation traces are not applicable (N/A) by design. The evaluation survey ([evaluation survey snapshot](https://github.com/shunk031/agentic-cognitive-writing/blob/b66284dc47574987932c3be350e21b461e8fb397/docs/research/writing-eval-datasets.md)) and platform survey ([platform survey snapshot](https://github.com/shunk031/agentic-cognitive-writing/blob/711cf41142b13f5174ecdfb10dd1ade272c5a118/docs/research/skill-subagent-survey.md)) describe the no-retrieval adaptation.

**Proposed-plugin condition A4.** Condition A4 uses the documented cognitive-writing plugin. The Monitor selects among the Planning, Translating, and Reviewing processes. The Planner develops a hierarchical goal network. The Translator drafts. The Reviewer evaluates and revises. Generate and Evaluate may interrupt another process. The runner uses the plugin's append-only `.writing/trace/process.jsonl` and goal-network files and records the normal loop under the shared trace contract.

**No-goal-network condition A5.** Condition A5 invokes `cognitive-writing-no-goal-network` from the `cognitive-writing-experiments` plugin. The variant uses the assignment as one implicit objective. The Monitor chooses Planning, Translating, or Reviewing without a hierarchical goal network. The runner leaves any existing `.writing/goals.md` untouched, records process switches under the shared trace contract, and records no goal events or goal fields.

**Fixed-order condition A6.** Condition A6 invokes `cognitive-writing-fixed-order` from the `cognitive-writing-experiments` plugin. The variant runs Planning, Translating, then Reviewing in each pass. Generate and Evaluate may still interrupt when new information or a conflict requires it. After an interruption, the Monitor returns to the prescribed order. The runner keeps the ordinary goal network, records process switches and goal events under the shared trace contract, and adds no variant-specific fields.

All six conditions use the same assignment, starting draft, model settings, and user decisions.

The plugin mapping implements the theory in *A Cognitive Process Theory of Writing* [^1], but that 1981 paper does not specify these files.

The user owns rhetorical intent, factual authority, final wording, and publication.

The Monitor owns process coordination. The Planner, Translator, and Reviewer act within their documented delegated roles. See [`plugin/skills/cognitive-writing/SKILL.md`](https://github.com/shunk031/agentic-cognitive-writing/blob/d0d6da7d0607f9d54b35973c2cf4e10d779a15dd/plugin/skills/cognitive-writing/SKILL.md).

## Primary benchmarks and data gates

The protocol uses three fixed primary benchmarks and gates supplementary data on license and provenance.

### Three primary benchmarks

The primary set contains these benchmarks:

- [WritingBench](https://github.com/X-PLUG/WritingBench) [^3] for broad writing tasks
- [HelloBench](https://github.com/Quehry/HelloBench) [^4] for long-text generation
- [DoLoMiTes](https://github.com/google-deepmind/dolomites) [^5] for structured expert writing

The evaluation survey supports this selection. See [`docs/research/writing-eval-datasets.md`](https://github.com/shunk031/agentic-cognitive-writing/blob/b66284dc47574987932c3be350e21b461e8fb397/docs/research/writing-eval-datasets.md).

**[WritingBench](https://github.com/X-PLUG/WritingBench)**[^3]. Use the pinned curated release. The evaluation survey describes real-world writing queries across varied domains with query-specific criteria. See [`docs/research/writing-eval-datasets.md`](https://github.com/shunk031/agentic-cognitive-writing/blob/b66284dc47574987932c3be350e21b461e8fb397/docs/research/writing-eval-datasets.md). The runner uses the complete pinned query manifest unless a documented data failure blocks an item. The runner keeps blocked items in the run accounting and records the final count and release commit or archive hash.

**[HelloBench](https://github.com/Quehry/HelloBench)**[^4]. Use the pinned testing set. The evaluation survey describes long-text tasks with checklist-based evaluation support across subcategories. See [`docs/research/writing-eval-datasets.md`](https://github.com/shunk031/agentic-cognitive-writing/blob/b66284dc47574987932c3be350e21b461e8fb397/docs/research/writing-eval-datasets.md). The runner uses the complete pinned manifest, keeps blocked items in the run accounting, reports results by task and subcategory as well as in aggregate, and records the final count and release commit or archive hash.

**[DoLoMiTes](https://github.com/google-deepmind/dolomites)**[^5]. Use only the development subset after recomputing the split from the downloaded archive. The evaluation survey reports two source counts. The paper and archive report 820 dev and 1,037 test. The repository README reports 830 dev and 1,037 test. See [`docs/research/writing-eval-datasets.md`](https://github.com/shunk031/agentic-cognitive-writing/blob/b66284dc47574987932c3be350e21b461e8fb397/docs/research/writing-eval-datasets.md). The runner recomputes the split before the first scored run, saves the archive hash, split script version, and observed counts, and does not use the test portion for primary analysis. The expected paper and archive count is 820 dev and 1,037 test, but the archive-derived count is authoritative.

The runner materializes one immutable prompt manifest per benchmark. The manifest is the only prompt input used by a run. Each row contains the stable prompt identifier (ID), benchmark name, source version, prompt text or a permitted source reference, requested output constraints, and hash.

### Prompt sources for human anchors

The prompt sources serve these roles:

- [PERSUADE 2.0](https://github.com/scrosseye/persuade_corpus_2.0) [^6] supplies 15 argumentative prompt templates. Its human scores provide calibration anchors, not target labels for model outputs.
- [ICLE++](https://github.com/samlee946/ICLE-PlusPlus) [^7] supplies an external persuasive-writing anchor for rubric calibration and cross-prompt checks.

The survey recommends both datasets for this role and cautions against treating student essay scores as directly comparable to the new model-quality scores. See [`docs/research/writing-eval-datasets.md`](https://github.com/shunk031/agentic-cognitive-writing/blob/b66284dc47574987932c3be350e21b461e8fb397/docs/research/writing-eval-datasets.md).

The runner must not train on or alter the student essays for this experiment. The runner may use these anchor materials after recording the permitted source reference and license status:

- The 15 [PERSUADE 2.0](https://github.com/scrosseye/persuade_corpus_2.0) [^6] prompt templates as a separate argumentative anchor set
- [ICLE++](https://github.com/samlee946/ICLE-PlusPlus) [^7] as a calibration and generalization check unless its base-text access is cleared

### Optional benchmark with a license gate

[LongBench-Write English](https://github.com/THUDM/LongWriter/blob/main/evaluation/longbench_write_en.jsonl) is optional and supplementary. The benchmark may be added only after the benchmark prompt-file license and provenance are cleared. If included, the benchmark is a length-control and robustness axis, not a fourth primary benchmark.

The survey reports that the [LongWriter-6k](https://huggingface.co/datasets/THUDM/LongWriter-6k) [^8] supervised fine-tuning (SFT) data license does not automatically establish permission for the benchmark prompt files. See [`docs/research/writing-eval-datasets.md`](https://github.com/shunk031/agentic-cognitive-writing/blob/b66284dc47574987932c3be350e21b461e8fb397/docs/research/writing-eval-datasets.md).

This protocol excludes [EQ-Bench Creative Writing](https://github.com/EQ-bench/creative-writing-bench) and [WritingPreferenceBench](https://github.com/WritingPreferenceBench/Writing-Preference-Bench) [^17] because their licensing or metadata remains unresolved. The unresolved resources must not enter a paper result, prompt manifest, or redistributed artifact without a new license review. See [`docs/research/writing-eval-datasets.md`](https://github.com/shunk031/agentic-cognitive-writing/blob/b66284dc47574987932c3be350e21b461e8fb397/docs/research/writing-eval-datasets.md).

## Codex primary and Claude Code replication

The experiment uses separate primary and replication inference with explicit judge-family separation.

The plugin ships a Claude Code adapter through the [Claude Code manifest](https://github.com/shunk031/agentic-cognitive-writing/blob/d0d6da7d0607f9d54b35973c2cf4e10d779a15dd/plugin/.claude-plugin/plugin.json) and [Claude Code agents](https://github.com/shunk031/agentic-cognitive-writing/tree/d0d6da7d0607f9d54b35973c2cf4e10d779a15dd/plugin/agents/), and a Codex adapter through the [Codex manifest](https://github.com/shunk031/agentic-cognitive-writing/blob/d0d6da7d0607f9d54b35973c2cf4e10d779a15dd/plugin/.codex-plugin/plugin.json) and [Codex skill files](https://github.com/shunk031/agentic-cognitive-writing/tree/d0d6da7d0607f9d54b35973c2cf4e10d779a15dd/plugin/skills/).

### Platform assignments

The primary platform is OpenAI Codex headless, invoked with `codex exec`, with all six conditions running as skill or prompt variants over one pinned generator model from the Generative Pre-trained Transformer (GPT) family. The [platform survey](https://github.com/shunk031/agentic-cognitive-writing/blob/711cf41142b13f5174ecdfb10dd1ade272c5a118/docs/research/skill-subagent-survey.md) describes the primary platform's skill and adapter design.

The secondary replication runs the same six condition specifications under Claude Code headless with one pinned Claude-family generator model. A4 to A6 use the plugin, while A1 to A3 use the corresponding prompt variants.

The runner must record the installed Codex and Claude Code CLI versions and validate each exact headless invocation before a run. The [Codex non-interactive mode guide](https://developers.openai.com/codex/non-interactive-mode) and [Claude Code headless mode guide](https://docs.anthropic.com/en/docs/claude-code/headless) provide invocation references.

The runner uses these conceptual interfaces:

- `PRIMARY_GENERATOR`: `codex exec <REQUIRED_AT_RUNTIME flags> <prompt or stdin>`
- `SECONDARY_GENERATOR`: `claude --print <REQUIRED_AT_RUNTIME flags> <prompt or stdin>`

The runner will version the command flags in experiments/conditions/ when the runner lands and record them in every run manifest. The run must not silently fall back to an interactive mode.

Before running A4, A5, or A6, the runner installs the main `agentic-cognitive-writing` plugin. Before running A5 or A6, the runner also installs the `cognitive-writing-experiments` plugin. The main plugin provides the role skills and agents that the experiment plugin uses. The runner records both plugin commits in the run manifest.

The runner starts one top-level session per condition and prompt. In Codex A4 to A6 runs, the plugin may request native Codex subagents as documented. The plugin must not spawn nested `codex exec` children. If native delegation is unavailable and the Monitor performs a delegated role itself, the trace must record that fallback.

### Generator and judge separation

The protocol assigns judges by platform. The Codex run with GPT-family generators uses a Claude-family frontier judge and the shared third-family Prometheus 2 [^9] style open evaluator. The Claude Code run with Claude-family generators uses a GPT-family frontier judge and the same open evaluator.

The open evaluator must belong to a third model family, and the assignment is symmetric across the two platform runs.

The runner must pin each value below. A placeholder blocks the run:

| Value | Required setting |
| --- | --- |
| Codex generator model | `REQUIRED_AT_RUNTIME: exact GPT-family model ID and release` |
| Claude Code generator model | `REQUIRED_AT_RUNTIME: exact Claude-family model ID and release` |
| Codex frontier judge | `REQUIRED_AT_RUNTIME: exact Claude-family frontier model ID and release` |
| Claude Code frontier judge | `REQUIRED_AT_RUNTIME: exact GPT-family frontier model ID and release` |
| Shared open evaluator | `REQUIRED_AT_RUNTIME`: exact third-family Prometheus 2 [^9] style evaluator checkpoint, revision, and serving configuration |
| Generator system and condition prompts | `REQUIRED_AT_RUNTIME: frozen prompt files and hashes` |
| Judge prompts and JSON schemas | `REQUIRED_AT_RUNTIME: frozen prompt files, schema files, and hashes` |
| Temperature | `REQUIRED_AT_RUNTIME`: temperature |
| Top-p or equivalent | `REQUIRED_AT_RUNTIME`: top-p or equivalent |
| Maximum output tokens | `REQUIRED_AT_RUNTIME`: max output tokens |
| Stop rules | `REQUIRED_AT_RUNTIME`: stop rules |
| Timeout | `REQUIRED_AT_RUNTIME`: timeout |
| Generation seed | `REQUIRED_AT_RUNTIME`: generation seed |
| Judge seed | `REQUIRED_AT_RUNTIME`: judge seed |
| Sampling seed | `REQUIRED_AT_RUNTIME`: sampling seed |
| Presentation seed | `REQUIRED_AT_RUNTIME`: presentation seed where the platform allows it |
| Codex version | `REQUIRED_AT_RUNTIME`: Codex version |
| Claude Code version | `REQUIRED_AT_RUNTIME`: Claude Code version |
| Main plugin commit | `REQUIRED_AT_RUNTIME`: main plugin commit |
| Experiments plugin commit | `REQUIRED_AT_RUNTIME`: experiments plugin commit |
| Runner commit | `REQUIRED_AT_RUNTIME`: runner commit |
| Generator and judge family audit | `REQUIRED_AT_RUNTIME: recorded base-model families and runtime verification that each frontier judge differs from the generator family and the open evaluator belongs to a third family` |

The runner records each judge's base-model family and the generator family for every scored output. It fails the run if a frontier judge shares the generator family or if the open evaluator does not belong to a third family. The audit verifies the family labels at runtime rather than trusting configuration names.

The no-retrieval rule applies to generators and judges. Judges receive only the assignment, the permitted supplied context, and the blinded output or output pair. Judges do not receive agent traces, internal role names, or condition labels.

## Product quality and length outcomes

The runner measures output quality and length as separate outcomes. The product unit combines one output, one prompt, one condition, one platform, and one generator seed.

The runner preserves the raw output byte-for-byte and also stores the normalized text used for token and word counts. Normalization may remove only transport wrappers defined in the runner specification. Normalization must not rewrite content, repair claims, or change paragraph boundaries.

### Pointwise quality from two judges

Each assigned judge scores every output independently on five dimensions. Each raw score is an integer from 1 to 5. The judge returns a short evidence quote for each dimension.

For each platform, the runner z-scores each dimension within each benchmark and judge. The runner then averages the five z-scores into that judge's level composite. For platform `p`, judge `j`, benchmark `b`, dimension `d`, and output `i`, the value is `z(i,p,j,b,d) = (raw(i,p,j,b,d) - mean(p,j,b,d)) / sd(p,j,b,d)`. A zero standard deviation uses the frozen zero-variance rule in the runtime gate. Length compliance never enters a quality score.

On the primary Codex platform, every output receives both the Claude-family frontier judge and the open evaluator. The primary pointwise product-quality estimand is the equal-weight mean of the two judge-level composites, `Q_primary(i) = 0.5 * C_Claude(i) + 0.5 * C_open(i)`. Report per-judge raw scores and per-judge composites as sensitivity analyses.

On the Claude Code replication, every output receives the GPT-family frontier judge and the same open evaluator. The replication estimand uses the same equal-weight construction, `Q_replication(i) = 0.5 * C_GPT(i) + 0.5 * C_open(i)`. Keep replication inference separate from primary inference. Do not pool platforms. Report cross-platform agreement descriptively for RQ4.

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
  "condition_id": "<blind condition ID>",
  "platform": "<codex-primary|claude-code-replication>",
  "judge_id": "<judge ID>",
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

The runner rejects a response when it has any of these problems:

- Invalid JSON
- Missing dimensions
- Scores outside 1 to 5
- Evidence quotes that do not occur in the judged output or supplied context

The runner retries an invalid judge response only under the fixed retry count in the run manifest. The runner never gives a failed condition extra content or attempts.

### Balanced pairwise tournament

The six conditions produce 15 unordered condition pairs. For every prompt and assigned judge, run both A/B and B/A presentations. A/B places output A first. B/A places output B first. The two presentations produce 30 judgments per prompt per judge. Apply these controls:

- Blind the condition labels.
- Randomize output order with a recorded seed.
- Record ties as explicit outcomes.

These controls follow the evaluation survey's [judge design](https://github.com/shunk031/agentic-cognitive-writing/blob/b66284dc47574987932c3be350e21b461e8fb397/docs/research/writing-eval-datasets.md) and its position and verbosity bias mitigations.

The pairwise JSON object follows this contract, and every record must include the fields shown below.

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

Group pairwise records on `(platform, judge_id)` before fitting each judge-specific Bradley-Terry [^11] model. Use `judge_family` to verify each group against the runtime judge manifest. Compute the equal-weight average from those per-judge fits within each platform. Do not combine records from different platforms or judges before fitting.

Fit each Bradley-Terry [^11] model with a predeclared tie treatment. For condition `a`, let `theta_Codex(a, Claude)` and `theta_Codex(a, open)` be the judge-specific ability estimates under the same reference-condition constraint. The Codex pairwise average is `theta_primary(a) = 0.5 * theta_Codex(a, Claude) + 0.5 * theta_Codex(a, open)`. For the replication, use `theta_replication(a) = 0.5 * theta_ClaudeCode(a, GPT) + 0.5 * theta_ClaudeCode(a, open)`.

Fit and report the two platform models separately. Report these pairwise outputs:

- Per-judge win rates
- Per-judge Bradley-Terry [^11] ability estimates
- Equal-weight judge averages
- Raw win, loss, and tie counts

If the selected implementation cannot fit ties, count each tie as half a win in the tie-aware win rate.

### Length outcomes and judge sensitivity

The runner records raw word count, model-token count when the pinned tokenizer makes it available, and output-length gap for every pair.

Report every quality result both raw and length-stratified. The length strata and minimum cell size are `REQUIRED_AT_RUNTIME` and must be fixed before scoring.

Length compliance is a standalone outcome for prompts with an explicit requested length. Let `x` be the requested length and `y` the produced length in the same frozen unit. Report these outcomes by condition, benchmark, and platform:

- Relative deviation `D = |y - x| / x`
- Compliance indicator `I(D <= tau)` with the prespecified tolerance `tau = 0.20`
- Compliance rate, computed as the mean of the indicator
- LongWriter [^8] style length score

For `x > 0` and `y > 0`, use the LongWriter [^8] style formula from the [reference length evaluator](https://github.com/THUDM/LongWriter/blob/main/evaluation/eval_length.py). When `y > x`, compute `S = 100 * max(0, 1 - (y / x - 1) / 3)`. When `y <= x`, compute `S = 100 * max(0, 1 - (x / y - 1) / 2)`. If `y = 0`, set `S = 0` and `D = 1`. If a prompt has no explicit length request, report these outcomes as `N/A`. Freeze the length unit, formula, zero-output rule, and `tau` value in the runtime gate.

Length compliance and the length score never enter either quality estimand.

The runner performs a judge and generator family overlap audit. If any judge also generated an output, it runs the self-preference test on a blinded subset with the same A/B and B/A controls. The test estimates whether that judge family changes its choices for its own outputs. If the planned non-overlap assignment holds, the manifest records that the test was not triggered by direct overlap and reports swapped-judge rank agreement as the corresponding sensitivity check. The [evaluation survey](https://github.com/shunk031/agentic-cognitive-writing/blob/b66284dc47574987932c3be350e21b461e8fb397/docs/research/writing-eval-datasets.md) recommends this diagnostic when overlap cannot be avoided.

The covariate sensitivity analysis fits the prespecified quality and pairwise models with benchmark, prompt length, output length, output-length gap, presentation order, judge family, and platform where applicable. The analysis compares the adjusted treatment estimates with the raw and length-stratified estimates. Freeze the model formula, covariate coding, missing-value rule, and interaction terms as `REQUIRED_AT_RUNTIME`. The runner must record those settings in the analysis manifest before inspecting results.

## Human validation of pairwise judgments

Human validation samples 180 to 240 pairwise comparisons from the primary results. The study uses three recruited annotators per comparison. Sampling is stratified by benchmark, condition pair, prompt length, output-length gap, and automatic-decision margin. The human-validation design follows the scale and controls recommended in the [evaluation survey](https://github.com/shunk031/agentic-cognitive-writing/blob/b66284dc47574987932c3be350e21b461e8fb397/docs/research/writing-eval-datasets.md).

The presentation order is randomized per annotator. Annotators see the assignment and two anonymized outputs. They do not see condition names, platform names, judge names, traces, or automatic labels.

The annotation form records `A`, `B`, or `tie`, an optional short reason, annotator ID, comparison ID, presentation seed, and adjudication status.

Annotators must not discuss cases during independent scoring. The study record must state recruitment, compensation, instruction text, consent, data handling, and any review or ethics requirement. Record these details before collection.

Report these agreement measures:

- Krippendorff's alpha [^13]
- Fleiss' kappa [^14]
- Raw agreement
- Agreement between each automatic judge family and the human majority

Report disagreement by benchmark, condition pair, output-length gap, and automatic-decision margin.

Do not discard ties or cases with disagreement.

## Trace-based process analysis

The trace analysis measures observable process behavior and relates it to product quality.

### Trace sources and interpretation

**Trace sources.** For A4, A5, and A6, use the plugin's append-only `.writing/trace/process.jsonl` [trace schema](https://github.com/shunk031/agentic-cognitive-writing/blob/d0d6da7d0607f9d54b35973c2cf4e10d779a15dd/plugin/skills/cognitive-writing/references/trace-jsonl-schema.md) / `.writing/goals.md` for A4 and A6 / the final draft. A5 leaves any existing `goals.md` untouched, so the analysis does not use that file for A5 goal measures.

Each trace line is one JSON object. The documented event types are `process_switch`, `goal_created`, `goal_developed`, and `goal_regenerated`. Process-switch events include `from_process` and `to_process`. Goal events include `goal_id` and `parent_goal_id`. The plugin records responsible actor, decision, evidence, and uncertainty.

For A1, A2, and A3, the runner records only externally observed generation or stage events in the same per-run trace location. An adapter must not invent goals, hidden decisions, or internal reasoning. Plugin-specific fields that cannot be observed are `N/A` in the derived analysis. The baseline stage traces support structural comparisons.

The goal-network estimands apply to A4 and A6. The recursive-monitor estimands apply to A4 to A6, with no goal events or goal fields for A5.

The trace is an operational analogue of a thinking-aloud protocol, not a direct transcript of an agent's private state. The analysis therefore distinguishes logged actions from claims about cognition. An event that lacks enough evidence for a code is marked ambiguous and remains in the denominator for trace completeness.

### Process metrics from traces

The analysis extracts these measures from the traces and uses goal files only for A4 and A6.

**Goal count.** For A4 and A6, count all three goal event types and add the unique active goal IDs in `.writing/goals.md`. For A5, report zero because the variant records no goal events and leaves `.writing/goals.md` untouched. Report a total. When the kind is available, also report content, process, and criterion goals.

**Goal specificity.** Code whether each goal has these properties:

- Defines an operational action
- Names a content target
- Names an audience or purpose target
- States an evaluative criterion

The specificity analysis reports the coding rubric and double-codes a reliability sample. The analysis does not treat goal length alone as specificity.

**Middle-range goal quantity.** Count goals that connect a high-level rhetorical intention to a local prose or process action. Freeze the coding rule and examples before analysis.

**Middle-range goal quality.** Score each middle-range goal on these properties and report the mean and distribution with coder agreement:

- Gives concrete direction
- Covers the rhetorical problem
- Can be checked against the output

**Goal regeneration.** Count `goal_regenerated` events. Verify that the old goal remains in history and that the replacement has a new ID when its meaning materially changes. Record the evidence and stated rationale.

**Process-switch transitions.** Count transitions among the named processes. Include Embedded Generate events, Evaluate events, Organize events, Goal-setting events, and Revise events when the trace records them. Report transition counts and rates per run.

**Process-order entropy.** Compute Shannon entropy [^12] over normalized process sequences and over transition distributions. Report raw entropy, the number of observed states, and the normalization rule.

**Generate and Evaluate interruptions.** Count process switches into Generate or Evaluate while another process is active, using the process fields and explicit decision or evidence markers. Do not infer an interruption from text alone when the event is ambiguous.

**Pop-back events.** Count returns to an immediate parent goal after a child goal resolves. Use the child and parent IDs, status or history, and the next process event. Report unresolved parent links as trace-quality failures.

**Revision intent.** Map each revision to the IteraTeR [^10]-informed categories:

- Clarity changes
- Fluency changes
- Coherence changes
- Style changes
- Meaning changes

Record the edit operation and the evidence in the trace or draft diff. The [evaluation survey](https://github.com/shunk031/agentic-cognitive-writing/blob/b66284dc47574987932c3be350e21b461e8fb397/docs/research/writing-eval-datasets.md) identifies IteraTeR as the process-level revision precedent.

**A3 outline and QA structure.** Count these structures:

- Discovered perspectives
- Simulated questions and answers
- Outline nodes
- Section handoffs
- Polish passes

Retrieval and citation metrics are `N/A` under the common policy.

The analysis correlates process measures with per-prompt product quality. It reports correlations for each judge family. It also reports correlations for the prespecified aggregate. It shows benchmark and output length as covariates. A correlation does not establish that the process caused the quality difference.

## Confirmatory and exploratory analysis

The analysis keeps primary and replication inference separate and reserves confirmatory claims for the primary pointwise two-judge composite. The classification is defined in Theory test and research questions.

The prompt is the paired unit. Each condition receives the same prompt, and platform replications use the same prompt manifest. Invalid or missing outputs remain in the run accounting. The report gives the failure count and reason by condition and benchmark. The report does not silently drop a condition that fails more often.

For pointwise quality, compute the primary equal-weight judge composite for each prompt and condition on each platform. The confirmatory contrasts compare condition A4 with each other condition. Use paired bootstrap intervals or a paired Wilcoxon signed-rank test [^16] across prompts. Report these results:

- Mean and median paired differences
- Confidence intervals
- Test statistic and p-value
- Effect size

Report raw 1 to 5 means, judge-level composites, and per-judge contrasts as sensitivity analyses. Run the same analysis by benchmark. Keep Codex and Claude Code inference separate.

For pairwise quality, report these results on each platform:

- Raw wins, losses, and ties
- Per-judge tie-aware win rates
- Per-judge Bradley-Terry [^11] ability estimates
- Equal-weight judge average

Use prompt-level paired resampling for uncertainty. Report the effect size on the selected Bradley-Terry [^11] scale or the paired difference in tie-aware win rate. Keep Codex and Claude Code inference separate.

For RQ1 and RQ2, run the 15 confirmatory contrasts on the primary Codex pointwise composite. Compare condition A4 with each other condition within each primary benchmark. Report the same five contrasts on the Claude Code replication separately, without pooled or confirmatory inference.

For RQ4, compare platforms descriptively by the following measures and do not pool platforms:

- Direction of the effect
- Rank agreement
- Standardized effect size

Apply Holm correction [^15] within each primary-benchmark family of five confirmatory contrasts on the primary Codex pointwise composite. Do not apply the correction to the pairwise average or to any other contrast. Report the pairwise average with uncertainty intervals and no Holm-adjusted claims. Freeze these settings before outcome inspection:

- Alternative hypotheses
- Missing-value rules
- Bootstrap resample count
- Confidence level
- Effect-size definitions
- Bradley-Terry [^11] tie treatment
- Ability-scale convention

Mark exploratory subgroup results clearly. Do not use them to replace the confirmatory estimates.

## Reproducible runs and artifacts

All runs are scripted under [`experiments/`](../../experiments/). The planned layout is:

```text
experiments/
├── config/       # frozen run, model, judge, and seed configurations
├── prompts/      # materialized prompt manifests and source hashes
├── conditions/   # A1-A6 wrappers and platform-specific adapters
├── runner/       # execution, timeout, retry, and trace collection code
├── judge/        # pointwise and pairwise prompts, schemas, and runners
├── human/        # sampling manifest, annotation form, and agreement code
├── analysis/     # scoring, statistics, plots, and report tables
└── manifests/    # run manifests, checksums, and validation reports
```

The runner writes a manifest before each run. The manifest records these fields:

- **Inputs.** Benchmark release and hash / prompt manifest hash / condition ID / platform / selected skill or prompt variant
- **Models and execution.** CLI versions / main plugin commit / experiments plugin commit / generator and judge model IDs / system / condition / judge prompt hashes / decoding parameters / output budget / tool policy / no-retrieval check
- **Reproducibility and environment.** Random seeds / retry policy / start time / software environment identifiers that are safe to publish

The runner versions or content-hashes outputs, traces, judge responses, human judgments, derived scores, and analysis inputs.

Raw benchmark files are redistributed only when their license allows it. If redistribution is not allowed, version the materialization script, source version, content hash, and clear acquisition instruction instead.

Do not place credentials or private prompt material in the repository.

The runner enforces the equal-tool and no-retrieval policy. It logs network-policy status and fails closed if a generator or judge requests an unpermitted retrieval action. It gives every condition the same timeout and retry budget. A retry cannot change the prompt, tool policy, model, or decoding parameters.

The runner validates these conditions:

- Every trace line is standalone JSON.
- A4 to A6 contain the fields required by their selected plugin skill.
- A5 and A6 manifests record the selected skill from the experiments plugin.
- Blind labels are independent of condition IDs.
- All 15 unordered pairs have both presentation orders.

A validation failure stops publication of the affected result.

## Main threats to validity

The protocol limits claims with checks for construct, comparison, judge, length, platform, benchmark, trace, and licensing risks.

**Construct validity.** A logged agent trace records actions selected by the plugin and runner. The trace does not prove that an agent has human-like thoughts. The RQ3 analysis uses the thinking-aloud analogy only to define observable process measures.

**Comparison validity.** The equal-tool and no-retrieval policy makes the A3 condition a STORM [^2] style pipeline, not the full retrieval-based system. The policy limits claims about source-grounded research performance. The policy also prevents retrieval from becoming an unbalanced advantage for one condition.

**Judge validity.** Pointwise and pairwise judges can show position, verbosity, self-preference, and model-family bias.

The [evaluation survey](https://github.com/shunk031/agentic-cognitive-writing/blob/b66284dc47574987932c3be350e21b461e8fb397/docs/research/writing-eval-datasets.md) documents these risks. The protocol addresses them with:

- Blind labels
- Both presentation orders
- Two judge families
- Evidence quotes
- Length-stratified results
- Overlap audits
- Human validation

The listed controls cannot remove every bias.

**Length confounding.** A longer answer may appear better to a judge even when it adds little value. The [evaluation survey](https://github.com/shunk031/agentic-cognitive-writing/blob/b66284dc47574987932c3be350e21b461e8fb397/docs/research/writing-eval-datasets.md) describes this risk. The protocol records length, reports raw and length-stratified results, and keeps length compliance out of the quality score.

**Platform confounding.** Codex and Claude Code differ in several ways:

- Codex and Claude Code have different CLI behavior.
- Codex and Claude Code have different native delegation.
- Codex and Claude Code use different model families.

The [platform survey](https://github.com/shunk031/agentic-cognitive-writing/blob/711cf41142b13f5174ecdfb10dd1ade272c5a118/docs/research/skill-subagent-survey.md) describes the adapter differences. The replication keeps the task and process mapping fixed while reporting platforms separately. A cross-platform result is a replication of the direction and process signature, not proof that the systems are identical.

**Benchmark coverage.** The primary benchmarks cover different writing settings:

- [WritingBench](https://github.com/X-PLUG/WritingBench) [^3] covers broad writing.
- [HelloBench](https://github.com/Quehry/HelloBench) [^4] covers long-text generation.
- [DoLoMiTes](https://github.com/google-deepmind/dolomites) [^5] covers structured writing.

The primary benchmarks do not represent every genre or language. The argumentative anchors add limited coverage:

- [PERSUADE 2.0](https://github.com/scrosseye/persuade_corpus_2.0) [^6] provides argumentative prompts and human-score anchors, not complete coverage.
- [ICLE++](https://github.com/samlee946/ICLE-PlusPlus) [^7] provides a persuasive-writing anchor, not complete coverage.

The [evaluation survey](https://github.com/shunk031/agentic-cognitive-writing/blob/b66284dc47574987932c3be350e21b461e8fb397/docs/research/writing-eval-datasets.md) supports this scope assessment.

**Trace completeness.** A crash, truncation, or adapter gap can hide a process event. The runner reports trace completeness and treats ambiguous or missing events as data-quality findings. The runner does not impute a goal or process switch.

**Data and licensing.** The protocol has explicit gates for the unresolved items below:

- The [DoLoMiTes](https://github.com/google-deepmind/dolomites) [^5] split conflict
- [LongBench-Write English](https://github.com/THUDM/LongWriter/blob/main/evaluation/longbench_write_en.jsonl) licensing and provenance
- [EQ-Bench Creative Writing](https://github.com/EQ-bench/creative-writing-bench) licensing
- [WritingPreferenceBench](https://github.com/WritingPreferenceBench/Writing-Preference-Bench) [^17] licensing and metadata

The [evaluation survey](https://github.com/shunk031/agentic-cognitive-writing/blob/b66284dc47574987932c3be350e21b461e8fb397/docs/research/writing-eval-datasets.md) provides the evidence for these gates. The analysis cannot use a source merely because a paper or repository mentions it.

## Runtime gates before scoring

The owner must close every gate below before the first scored run. Codex records the decision and the evidence in the run manifest.

1. **DoLoMiTes split.** Download the released [DoLoMiTes](https://github.com/google-deepmind/dolomites) [^5] archive. Recompute dev and test counts. Save the script and archive hash. Cite the resulting count in the paper. The [evaluation survey](https://github.com/shunk031/agentic-cognitive-writing/blob/b66284dc47574987932c3be350e21b461e8fb397/docs/research/writing-eval-datasets.md) reports expected paper/archive counts of 820 dev and 1,037 test. The archive result controls if it differs.
2. **Benchmark materialization.** Pin releases or commits for [WritingBench](https://github.com/X-PLUG/WritingBench) [^3] / [HelloBench](https://github.com/Quehry/HelloBench) [^4] / [DoLoMiTes](https://github.com/google-deepmind/dolomites) [^5]. Materialize prompt manifests and record final item counts.
3. **LongBench-Write license.** Clear the [LongBench-Write English](https://github.com/THUDM/LongWriter/blob/main/evaluation/longbench_write_en.jsonl) benchmark prompt-file license and provenance before any supplementary use. Otherwise keep the benchmark excluded.
4. Record permitted use for **PERSUADE 2.0**[^6] ([15 prompts](https://github.com/scrosseye/persuade_corpus_2.0)) / **ICLE++**[^7] ([calibration material](https://github.com/samlee946/ICLE-PlusPlus)). Do not redistribute material outside its permission.
5. **Generator configuration.** Fill these values:

   - Exact model IDs
   - CLI versions
   - Main plugin commit
   - Experiments plugin commit when A5 or A6 runs
   - Decoding parameters
   - Output budgets
   - Timeout
   - Retry policy
   - Seeds
6. **Judge configuration.** Fill these assignments and checks:

   - Exact Claude-family frontier judge for Codex outputs
   - Exact GPT-family frontier judge for Claude Code outputs
   - The same open evaluator for both platforms
   - Each judge's base-model family
   - Runtime verification that each frontier judge differs from the generator family
   - Runtime verification that the open evaluator belongs to a third family, such as a Mistral-family evaluator
   - Frozen judge prompts, schemas, decoding parameters, and seeds
   - Frozen Bradley-Terry [^11] tie treatment
   - Frozen common ability-scale convention
7. **Length analysis.** Freeze these settings before judging:

   - Tokenizer versions
   - Word-count rules
   - Output-length strata
   - Minimum cell sizes
   - Covariate model
   - Length unit for prompts with an explicit length constraint
   - Relative deviation `D = |y - x| / x`
   - Compliance indicator `I(D <= 0.20)`
   - LongWriter [^8] style score
     - `100 * max(0, 1 - (y / x - 1) / 3)` for `y > x`
     - `100 * max(0, 1 - (x / y - 1) / 2)` for `0 < y <= x`
   - Score `0` when `y = 0`
   - Zero-variance z-score rule
8. **Trace conformance.** Run one smoke test for each condition and platform. Validate these properties:

   - Trace JSON Lines (JSONL)
   - Goal-state handling for each selected skill
   - Correct variant skill invocation
   - Stage events
   - Blind labels
   - Pair balance
   - No-retrieval enforcement
9. **Human study.** Approve these study details:

   - The 180 to 240 comparison sample
   - Three-annotator assignment
   - Recruitment and compensation text
   - Consent
   - Data handling
   - Any required ethics review
10. **Statistical lock.** Freeze these settings:

   - Confirmatory contrast families
   - Paired bootstrap or paired Wilcoxon signed-rank test [^16] settings
   - Holm correction [^15]
   - Confidence level
   - Effect sizes
   - Tie handling
   - Missing-value rules

If a new source check contradicts a settled design item or the plugin's documented behavior, stop the experiment and record the conflict. Do not resolve it by changing a condition after results exist.

[^1]: Linda S. Flower and John R. Hayes, "A Cognitive Process Theory of Writing," *College Composition and Communication* 32, no. 4 (1981): 365-387. [DOI](https://doi.org/10.58680/ccc198115885) / [JSTOR](https://www.jstor.org/stable/356600).
[^2]: Yijia Shao, Yucheng Jiang, Theodore A. Kanell, Peter Xu, Omar Khattab, and Monica S. Lam, "Assisting in Writing Wikipedia-like Articles From Scratch with Large Language Models," arXiv preprint arXiv:2402.14207 (2024). [arXiv](https://arxiv.org/abs/2402.14207).
[^3]: Yuning Wu, Jiahao Mei, Ming Yan, Chenliang Li, Shaopeng Lai, Yuran Ren, Zijia Wang, Ji Zhang, Mengyue Wu, Qin Jin, and Fei Huang, "WritingBench: A Comprehensive Benchmark for Generative Writing," arXiv preprint arXiv:2503.05244 (2025). [arXiv](https://arxiv.org/abs/2503.05244).
[^4]: Haoran Que, Feiyu Duan, Liqun He, Yutao Mou, Wangchunshu Zhou, Jiaheng Liu, Wenge Rong, Zekun Moore Wang, Jian Yang, Ge Zhang, Junran Peng, Zhaoxiang Zhang, Songyang Zhang, and Kai Chen, "HelloBench: Evaluating Long Text Generation Capabilities of Large Language Models," arXiv preprint arXiv:2409.16191 (2024). [arXiv](https://arxiv.org/abs/2409.16191).
[^5]: Chaitanya Malaviya, Priyanka Agrawal, Kuzman Ganchev, Pranesh Srinivasan, Fantine Huot, Jonathan Berant, Mark Yatskar, Dipanjan Das, Mirella Lapata, and Chris Alberti, "DOLOMITES: Domain-Specific Long-Form Methodical Tasks," arXiv preprint arXiv:2405.05938 (2024). [arXiv](https://arxiv.org/abs/2405.05938).
[^6]: S.A. Crossley, Yu Tian, Perpetual Baffour, Alex Franklin, Meg Benner, and Ulrich Boser, "A large-scale corpus for assessing written argumentation: PERSUADE 2.0," *Assessing Writing* 61 (2024): article 100865. [DOI](https://doi.org/10.1016/j.asw.2024.100865).
[^7]: Shengjie Li and Vincent Ng, "ICLE++: Modeling Fine-Grained Traits for Holistic Essay Scoring," *Proceedings of NAACL-HLT* (2024). [ACL Anthology](https://aclanthology.org/2024.naacl-long.468/).
[^8]: Yushi Bai, Jiajie Zhang, Xin Lv, Linzhi Zheng, Siqi Zhu, Lei Hou, Yuxiao Dong, Jie Tang, and Juanzi Li, "LongWriter: Unleashing 10,000+ Word Generation from Long Context LLMs," arXiv preprint arXiv:2408.07055 (2024). [arXiv](https://arxiv.org/abs/2408.07055).
[^9]: Seungone Kim, Juyoung Suk, Shayne Longpre, Bill Yuchen Lin, Jamin Shin, Sean Welleck, Graham Neubig, Moontae Lee, Kyungjae Lee, and Minjoon Seo, "Prometheus 2: An Open Source Language Model Specialized in Evaluating Other Language Models," arXiv preprint arXiv:2405.01535 (2024). [arXiv](https://arxiv.org/abs/2405.01535).
[^10]: Wanyu Du, Vipul Raheja, Dhruv Kumar, Zae Myung Kim, Melissa Lopez, and Dongyeop Kang, "Understanding Iterative Revision from Human-Written Text," *Proceedings of the 60th Annual Meeting of the Association for Computational Linguistics* (Volume 1: Long Papers) (2022): 3573-3590. [ACL Anthology](https://aclanthology.org/2022.acl-long.250/).
[^11]: Ralph Allan Bradley and Milton E. Terry, "Rank Analysis of Incomplete Block Designs: I. The Method of Paired Comparisons," *Biometrika* 39, nos. 3-4 (1952): 324-345. [DOI](https://doi.org/10.1093/biomet/39.3-4.324).
[^12]: Claude E. Shannon, "A Mathematical Theory of Communication," *Bell System Technical Journal* 27, no. 3 (1948): 379-423. [DOI](https://doi.org/10.1002/j.1538-7305.1948.tb01338.x).
[^13]: Klaus Krippendorff, "Bivariate Agreement Coefficients for Reliability of Data," *Sociological Methodology* 2 (1970): 139-150. [JSTOR](https://www.jstor.org/stable/270787).
[^14]: Joseph L. Fleiss, "Measuring Nominal Scale Agreement among Many Raters," *Psychological Bulletin* 76, no. 5 (1971): 378-382. [DOI](https://doi.org/10.1037/h0031619).
[^15]: Sture Holm, "A Simple Sequentially Rejective Multiple Test Procedure," *Scandinavian Journal of Statistics* 6, no. 2 (1979): 65-70. [JSTOR](https://www.jstor.org/stable/4615733).
[^16]: Frank Wilcoxon, "Individual Comparisons by Ranking Methods," *Biometrics Bulletin* 1, no. 6 (1945): 80-83. [JSTOR](https://www.jstor.org/stable/3001968).
[^17]: Shuangshuang Ying, Yunwen Li, Xingwei Qu, Xin Li, Sheng Jin, Minghao Liu, Zhoufutu Wen, Xeron Du, Tianyu Zheng, Yichi Zhang, Letian Ni, Yuyang Cheng, Zhenzhu Yang, Qiguang Chen, Jingzhe Ding, Shengda Long, Wangchunshu Zhou, Jiazhan Feng, Wanjun Zhong, Libo Qin, Ge Zhang, Wenhao Huang, Wanxiang Che, and Chenghua Lin, "Beyond Correctness: Evaluating Subjective Writing Preferences Across Cultures," arXiv preprint arXiv:2510.14616 (2025). [arXiv](https://arxiv.org/abs/2510.14616).
