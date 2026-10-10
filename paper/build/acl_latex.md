## Agentic CogWriter: Revisiting the Cognitive Process Theory of Writing for AI Agents

Anonymous ACL submission

## Abstract

Recent coding agents have made tool-using, stateful execution prominent. The same execution style is increasingly used for knowledge work that ends in long-form documents. Yet long-form writing systems usually advance an outline, task graph, or fixed stage sequence rather than deciding which writing process is needed next. Drawing on cognitive process theory, we propose <span class="smallcaps">Agentic CogWriter</span>, which maintains a shared draft, goals, and process history while a Monitor agent chooses and delegates planning, drafting, or reviewing. We evaluate our system across three long-form writing benchmarks using pointwise rubric scoring and pairwise same-prompt preference judgments. Our system achieves competitive pointwise quality and is preferred to one-shot generation, a fixed planning–drafting–revision workflow, and adaptive task planning in pairwise evaluation. Ablations indicate that neither explicit goals nor adaptive process order alone explains the overall advantage. Process traces show that most runs follow one planning–drafting–reviewing cycle, with departures used selectively rather than continually. Together, the results support process-level control as a promising design for long-form writing agents.

## Introduction

Large language model agents (Yao et al., 2023; Shinn et al., 2023; Sumers et al., 2024; Luo et al., 2025) increasingly combine reasoning, tool use, memory, and delegation to carry out multi-step knowledge work. Recent coding agents have made this interactive, tool-mediated style of execution especially prominent (Yang et al., 2024; Wang et al., 2024b), while similar agentic workflows increasingly produce reports or scientific manuscripts (Schmidgall et al., 2025; Lu et al., 2024). For agents that produce documents, long-form writing requires more than final text generation: the agent must organize the document, turn partial plans into prose, inspect what has been written, and decide when revision is needed.

Figure 1. Overview of <span class="smallcaps">Agentic CogWriter</span>. Inspired by the cognitive process theory of writing, a coding-agent-style control loop turns the task into a document via Planning, Translating, or Reviewing, selected online from the evolving document state.

Existing long-form writing systems impose different forms of structure on generation (Yao et al., 2019; Yang et al., 2022; Shao et al., 2024; Bai et al., 2025; Xiong et al., 2025; Sun et al., 2026). Some build an outline before drafting (Yao et al., 2019; Yang et al., 2022), some generate a document section by section (Shao et al., 2024; Bai et al., 2025), some recursively decompose the document into tasks (Xiong et al., 2025), and some adapt plans or structural reasoning during generation (Wan et al., 2025; Sun et al., 2026). Across these systems, the next step is usually defined by a content unit, task node, or prescribed stage. A complementary design question remains comparatively underexplored: should the writer decide which kind of writing process is needed next?

The cognitive process theory of writing (Flower and Hayes, 1981; Hayes, 1996; Hayes, 2012) provides a useful abstraction for process-level control. Flower and Hayes (1981) characterize writing as coordination among planning, translating, and reviewing, with a monitor deciding which process to invoke as the document develops. This view suggests choosing the next writing process rather than the next section or task node.

Building on Flower and Hayes (1981), we propose <span class="smallcaps">Agentic CogWriter</span>, a long-form writing system that implements this process-level control on top of a coding-agent-style harness with persistent state and subagent delegation (Figure 1). A top-level Monitor agent observes the evolving draft, goals, and process history, chooses whether the next activity should be planning, drafting, or reviewing, and delegates that activity to a corresponding subagent. The resulting process order is chosen during writing rather than fixed in advance.

We evaluate our system on demanding subsets of three complementary long-form writing benchmarks spanning broad instruction-driven writing, long-context generation, and methodical expert-document production (Wu et al., 2026b; Que et al., 2024; Malaviya et al., 2025). We hold the generator and task information constant across the compared conditions so that differences reflect how writing is organized. Pointwise rubric scoring and pairwise same-prompt preference evaluation assess document quality from complementary perspectives. In pairwise evaluation, our system is preferred to one-shot generation, a fixed writing pipeline, and adaptive task planning. The component analyses support a system-level interpretation of this advantage rather than attributing it to explicit goals or adaptive ordering alone under the pre-specified tests. Process traces show that most runs follow a simple planning–drafting–reviewing path, indicating that adaptive ordering is available but used selectively.

Our contributions are threefold. (1) we formulate long-form writing for general-purpose agents as a process-level control problem and introduce a concrete system that chooses among planning, drafting, and reviewing during composition; (2) we compare our system with one-shot, fixed-stage, and adaptive task-planning alternatives across complementary long-form benchmarks; and (3) we use ablations and process analyses to test which proposed components explain the observed advantage and characterize the writing loop in practice.

## Related Work

##### Language agents and document production.

Language-agent research studies systems that interleave reasoning with actions, tools, memory, and feedback (Yao et al., 2023; Shinn et al., 2023; Sumers et al., 2024), while writing-support systems assist planning, drafting, and revision (Gero et al., 2022). Autonomous research systems increasingly connect those capabilities to report or paper generation after literature review and experimentation (Schmidgall et al., 2025; Lu et al., 2024). We focus on how a general-purpose agent organizes that writing stage. Better control of document production can improve not only standalone writing systems but also larger autonomous workflows whose final value depends on the quality of the report or manuscript they produce.

##### Long-form generation and planning.

Long-form generation becomes harder to control and evaluate as outputs grow in length (Tan et al., 2024; Wu et al., 2026a), motivating explicit planning and decomposition (Yao et al., 2019; Yang et al., 2022; Shao et al., 2024; Bai et al., 2025; Wan et al., 2025; Xiong et al., 2025; Sun et al., 2026). Plan-and-Write (Yao et al., 2019), Re`^3` (Yang et al., 2022), STORM (Shao et al., 2024), and LongWriter (Bai et al., 2025) organize generation around plans, revisions, sections, or manageable content units. CogWriter (Wan et al., 2025), WriteHERE (Xiong et al., 2025), IS-CoT (Sun et al., 2026), and SuperWriter (Wu et al., 2026a) make structure or refinement increasingly adaptive. CogWriter conditionally revises plans and generated segments within a planning-and-generation workflow, whereas WriteHERE schedules nodes in an evolving heterogeneous task graph. Our <span class="smallcaps">Agentic CogWriter</span> instead makes planning, drafting, or reviewing the document-level control decision.

##### Iteration and cognitive models of writing.

Iterative generation methods improve text through repeated feedback and revision (Madaan et al., 2023; Du et al., 2022), while cognitive writing research offers a process-level account of how planning, drafting, and reviewing interact (Flower and Hayes, 1981; Hayes, 1996; Hayes, 2012). Gero et al. (2022) use those processes to organize writing-support systems, and CogWriter (Wan et al., 2025) likewise draws on cognitive writing theory to structure planning, generation, and revision. Our <span class="smallcaps">Agentic CogWriter</span> differs by making the writing process itself the online action chosen by a shared document-level controller and by testing that control choice with matched alternatives, ablations, and analyses of observed writing behavior. Table 1 summarizes the distinction alongside other explicit capabilities of representative long-form writing systems.

|  |  |  |  |  |
|:---|:--:|:--:|:--:|:--:|
| **Method** | **Unit of**; **progress** | **Adaptive**; **next step** | **Evolving**; **structure** | **Online process**; **selection** |
| Re`^3` (Yang et al., 2022) | Passage | – | – | – |
| STORM (Shao et al., 2024) | Section | – | – | – |
| CogWriter (Wan et al., 2025) | Plan / segment | yes | Plan | – |
| WriteHERE (Xiong et al., 2025) | Task node | yes | Task graph | – |
| **<span class="smallcaps">Agentic CogWriter</span> (ours)** | **Writing process** | yes | **Goal network** | yes |

Table 1. Comparison of control choices in representative long-form writing systems. The unit of progress is what advances at each step; adaptive next step indicates whether that choice depends on the current state. Evolving structure excludes document text. <span class="smallcaps">Agentic CogWriter</span> is the only compared system with online selection among heterogeneous writing operations: planning, drafting, and reviewing.

## Agentic CogWriter

We introduce <span class="smallcaps">Agentic CogWriter</span>, a long-form writing system that turns document production into a stateful loop over explicit writing processes. Each run begins with a fixed writing task

`X=(I,C,O),`

where `I` is the instruction, `C` is the supplied context, and `O` specifies the requested output requirements. Every writing process can read `X`, but only the document state changes during composition. Figure 1 gives the system overview. One top-level `Monitor` agent coordinates three subagents: `Planner`, `Translator`, and `Reviewer`.

### Persistent Writing State

Composition starts from an initial draft `D_0` and updates a shared document state as writing proceeds. At writing step `t`, the shared workspace contains

`S_t=(D_t,G_t,H_t),`

where `D_t` is the current draft, `G_t` is the current hierarchy of writing goals, and `H_t` is the observable process history. We use `D_0` for the initial draft, which is empty unless the task provides one, and initialize `G_0` from the assignment. Keeping these records outside any single agent context lets successive writing processes inspect and modify the same document-level state.

The goal component `G_t` explicitly records a hierarchy of writing goals, following Flower and Hayes (1981)’s account of writers creating and developing goals during composition. Entries can be created, developed, or replaced as the draft changes; we call replacement of an existing entry *goal regeneration*. This representation makes the theory-derived design choice observable and testable without attributing a human-like cognitive state to the agent.

### Process-Level Control and Execution

The `Monitor` chooses the next writing process from action space `A`:

`A=(Planning,Translating,Reviewing).`

At writing step `t`, it receives the fixed task `X` together with the current draft, goals, and process history, and returns one action

`a_t=Monitor(X,D_t,G_t,H_t), a_t in A.`

We retain Flower and Hayes (1981)’s term `Translating` for the drafting activity. Unlike a section scheduler or task-graph controller, Eq. <a href="#eq:monitor-policy" data-reference-type="eqref" data-reference="eq:monitor-policy">[eq:monitor-policy]</a> selects the kind of writing work to perform next.

If `Planning` is selected, the `Planner` reads the task and current draft, organizes relevant material for the intended audience, and creates or develops writing goals. If `Translating` is selected, the `Translator` reads the current draft and active goals and writes prose within the delegated draft scope. If `Reviewing` is selected, the `Reviewer` checks the draft against the task and active goals, revises within the delegated scope, and reports whether further planning, drafting, or review is needed.

Each subagent writes its changes to the shared workspace before control returns to the `Monitor`, yielding the next state `S_(t+1)`. Review feedback can recommend replacing a goal, but the `Monitor` decides whether to accept that change and records the decision in `H_t`. Because each decision is made from the updated state, the process order is not fixed: drafting can expose a structural problem that sends control back to planning, and reviewing can trigger another drafting or planning pass. After reviewing, the `Monitor` may instead terminate the loop and return the current draft as the completed document `D_final`.

## Experimental Design

We compare the writing systems under the same task inputs and information policy to study three questions: whether process-level organization improves document quality, which components contribute to any advantage, and how the writing loop behaves in practice. We also use one post-hoc execution variant as a diagnostic.

### Systems Compared

We consider seven pre-specified systems under the same generation setup. The systems are numbered below so that the alternatives, ablations, execution variant, and full system can be distinguished throughout the analysis.

##### Alternative writing systems.

We compare three alternatives to <span class="smallcaps">Agentic CogWriter</span>: (1) `Single-pass` produces the complete document in one generation call; (2) `Staged` executes `Pre-Write``->``Write``->``Re-Write`, following the common separation of planning, drafting, and revision (Yang et al., 2022; Wan et al., 2025); and (3) `Task-planning` follows a WriteHERE-style adaptive task graph (Xiong et al., 2025), recursively decomposing the assignment and selecting among dependency-satisfied task nodes. The alternatives therefore advance a whole document, a fixed writing stage, or an adaptive task node, whereas our system advances a writing process.

##### Ablations of Agentic CogWriter.

Two pre-specified ablations change one control mechanism while retaining the rest of the loop. (4) `No-goals` removes the explicit goal representation but keeps adaptive process selection and the three subagents, while (5) `Fixed-order` keeps the shared draft, goals, process history, and subagents but replaces the `Monitor`’s adaptive decision with a repeated `Planning``->``Translating``->``Reviewing` cycle. The comparison tests whether explicit goals or adaptive ordering explain the full-system gain.

##### Execution variant and full system.

\(6\) `Single-writer` retains the goal representation and adaptive process loop but performs planning, drafting, and reviewing in one writer context without subagent delegation; it also limits each `Translating` step to one paragraph, so the condition is diagnostic rather than a clean ablation. (7) <span class="smallcaps">Agentic CogWriter</span> is the full system described in Section 3.2, with adaptive process selection, explicit goals, and role-specific subagents. This is our focal system.

##### Post-hoc execution check.

`Single-context` was added after the main results as a narrower exploratory check and is not one of the seven pre-specified systems. The condition preserves the full process loop and shared state but executes each selected process in the `Monitor`’s context rather than a separate subagent context, serving only as a diagnostic of whether separate role contexts are necessary to explain the observed difference.

|  |  |  |  |  |
|:---|:---|:---|:---|:---|
| **System** | **Information available** | **What advances next?** | **Decision rule** | **Execution** |
| `Single-pass` | `X` | Whole document | One generation | One context |
| `Staged` | `X`, prior stage output | Fixed stage | Pre-Write`->`Write`->`Re-Write | One context |
| `Task-planning` | `X,D_t,T_t` | Task node | Select a ready task node | Task graph |
| **<span class="smallcaps">Agentic CogWriter</span>** | `X,D_t,G_t,H_t` | **Writing process** `a_t` | `a_t=Monitor(X,D_t,G_t,H_t)` | **Subagent** |
| `No-goals` | `X,D_t,H_t` | Writing process `a_t` | `a_t=Monitor(X,D_t,H_t)` | Subagent |
| `Fixed-order` | `X,D_t,G_t,H_t` | Fixed process | Planning`->`Translating`->`Reviewing | Subagent |
| `Single-writer` | `X,D_t,G_t,H_t` | Writing process `a_t` | `a_t=Monitor(X,D_t,G_t,H_t)` | One writer |
| `Single-context` | `X,D_t,G_t,H_t` | Writing process `a_t` | `a_t=Monitor(X,D_t,G_t,H_t)` | Monitor context |

Table 2. Operational comparison of the evaluated writing systems. `Staged` follows fixed planning–drafting–revision stages (Yang et al., 2022; Wan et al., 2025); `Task-planning` follows WriteHERE-style task planning (Xiong et al., 2025). The first four rows expose the central difference in what advances next: document, stage, task node, or writing process. `X` is the task input; `D_t`, `G_t`, and `H_t` are draft, goals, and process history; `T_t` is the task graph. The remaining rows modify <span class="smallcaps">Agentic CogWriter</span>; `Single-context` was added post-hoc.

### Benchmarks and Prompts

We use three benchmarks to test whether process-level organization transfers across different forms of long-form writing: (1) WritingBench (Wu et al., 2026b), which covers broad real-world writing requests with task-specific evaluation criteria; (2) HelloBench (Que et al., 2024), which includes long-text summarization, open-ended generation, and completion; and (3) DoLoMiTes (Malaviya et al., 2025), which targets methodical expert writing with explicit objectives, procedures, inputs, and constraints. The benchmarks cover general instruction following, sustained long-context generation, and structured expert-document production.

We evaluate fixed demanding subsets because short or lightly constrained tasks may not reveal differences in how a system manages a long document. We first reserve any prompts used while developing or debugging the evaluation protocol and never score those prompts. From the remaining benchmark items, we deterministically prioritize cases with longer supplied context and, when the prompt specifies a target length, longer requested output, while applying fixed maximum-length limits. This produces a different demanding subset for each benchmark: WritingBench emphasizes long inputs with explicit long-output requirements, HelloBench emphasizes very long-input summarization and continuation, and DoLoMiTes emphasizes procedurally constrained expert writing.[^1]

### Implementation

All systems run in the same Codex-style coding-agent harness, using `gpt-5.6-luna` as the generator and `gpt-5.6-sol` as the primary evaluator.[^2] Holding the generator fixed across systems isolates writing organization rather than base-model capability. For a cross-family robustness check, we also rescore selected system comparisons with `claude-sonnet-5 medium`. Our system is packaged as an agent skill: the top-level `Monitor` invokes `Planner`, `Translator`, and `Reviewer` through the harness’s subagent mechanism.[^3]

Each prompt–system pair is generated in three runs with the same generator, prompt set, and runtime configuration. Repeating generation lets us measure variation due to stochastic execution while keeping the task set and system definition fixed. Network access, web search, and external retrieval are disabled for every system, and the harness records completed outputs plus available process traces, token accounting, and timing.

### Evaluation

##### Pointwise evaluation.

We score each completed document independently. When a benchmark defines its own rubric, we report that score as the *benchmark-native* score, meaning the benchmark authors’ original criteria rather than our shared rubric. WritingBench uses five prompt-specific criteria, HelloBench uses checklist items, and DoLoMiTes provides no comparable native score.

We also apply a common five-dimension rubric across all three benchmarks: instruction fulfillment, organization and coherence, content adequacy and depth, style and audience fit, and factual or constraint fidelity, each scored from 1 to 5. Because these ratings concentrate near the upper end, each dimension is standardized within each generation run and benchmark across outputs from all seven pre-specified systems before averaging. The composite is relative within a benchmark rather than an absolute quality scale.[^4]

##### Pairwise evaluation.

We directly compare two responses written for the same prompt using the same quality dimensions and record which response is preferred, or a tie. LLM judges can exhibit position bias (Zheng et al., 2023; Wang et al., 2024a), so every pair is evaluated in both presentation orders. We count a preference only when both orders select the same semantic response; any disagreement, including preference versus tie, is recorded as a tie. We report each system contrast as wins/losses/ties (W/L/T) for the first-named system and compute its win rate over non-tied order-consistent comparisons as `W/(W+L)`.

The primary generator and evaluator come from the same model family, which can introduce systematic preference leakage or self-preference (Li et al., 2026; Panickssery et al., 2024). We therefore report the cross-family rescoring described above as a separate descriptive robustness check rather than averaging results from the two evaluators.

##### Pre-specified statistical testing.

We fixed the confirmatory comparisons before scoring to avoid choosing favorable tests after observing results. For each benchmark and generation run, an exact two-sided sign test compares the non-tied prompt-level wins and losses for every pre-specified contrast (Dixon and Mood, 1946). Testing several related contrasts increases the chance of at least one false positive, so we apply Holm’s step-down correction (Holm, 1979) across the pre-specified tests within each benchmark. Generation runs remain separate because they repeat the same prompts rather than provide new independent samples.[^5]

To summarize the two ablation contrasts across generation runs, we compute an exploratory post-hoc prompt-level estimate. For each prompt, win, tie, and loss outcomes are mapped to `1`, `1/2`, and `0`, averaged across the three generation runs, and summarized across benchmarks with a bootstrap interval and sign test.

##### Robustness and behavioral analysis.

Pairwise LLM evaluation can favor longer outputs and can change with judge identity (Zheng et al., 2023; Dubois et al., 2024; Li et al., 2026; Panickssery et al., 2024). We therefore test whether the pairwise direction persists within pre-specified output-length bands, under a tight compute match, and under the cross-family evaluator. Output length and realized compute are consequences of execution, so the first two analyses are descriptive sensitivity checks rather than causal adjustments.

We analyze observable traces of process transitions, goal creation and development, goal replacement, and subagent invocations to characterize how the writing loop is actually used. We also compare runs that complete one planning–drafting–reviewing cycle with runs that take another process path. The trace-defined split is observational rather than randomized, so it describes behavior without identifying a causal mechanism.

## Results

### Pointwise and Benchmark-Native Quality

Table 3 summarizes the pointwise results across the three benchmarks. <span class="smallcaps">Agentic CogWriter</span> obtains the highest mean on every WritingBench and HelloBench measure, and its paired prompt-level differences exclude zero against every alternative on both WritingBench measures and on HelloBench native scores. Its lead over `Staged` and `Task-planning` on HelloBench pointwise scores lies within the paired intervals, as does the higher DoLoMiTes pointwise mean of `Staged` over our system.[^6] WritingBench native scores are rescaled to 0–1 for display, and the common-rubric values are standardized relative to all seven pre-specified systems within each generation run and benchmark, so zero denotes the benchmark-specific comparison mean rather than an absolute quality threshold.

|  |  |  |  |  |  |  |
|:---|---:|---:|---:|---:|---:|---:|
| **System** | **WritingBench** | **WritingBench** | **HelloBench** | **HelloBench** | **DoLoMiTes** | **DoLoMiTes** |
|  | **Native `↑`** | **Pointwise `↑`** | **Native `↑`** | **Pointwise `↑`** | **Native `↑`** | **Pointwise `↑`** |
| *Alternative writing systems* | *Alternative writing systems* | *Alternative writing systems* | *Alternative writing systems* | *Alternative writing systems* | *Alternative writing systems* | *Alternative writing systems* |
| `Single-pass` | 0.697 (0.006) | -0.090 (0.009) | 0.773 (0.005) | -0.112 (0.018) | – | -0.006 (0.018) |
| `Staged` (Yang et al., 2022; Wan et al., 2025) | 0.702 (0.005) | -0.041 (0.012) | 0.781 (0.004) | 0.003 (0.016) | – | <span style="color: tiedgray">**0.064**</span> (0.036) |
| `Task-planning` (Xiong et al., 2025) | 0.722 (0.004) | -0.033 (0.033) | 0.781 (0.003) | -0.016 (0.061) | – | -0.164 (0.015) |
| **<span class="smallcaps">Agentic CogWriter</span>** | **0.747** (0.006) | **0.102** (0.040) | **0.791** (0.005) | <span style="color: tiedgray">**0.013**</span> (0.060) | – | 0.031 (0.035) |

Table 3. Document-quality scores, mean (sample SD in small type) across 3 generation runs. Native uses each benchmark’s criteria; Pointwise uses a common five-dimension rubric, z-scored within each run and benchmark over all seven systems; higher is better, and DoLoMiTes has no native score. Bold marks the highest mean in each column. <span class="smallcaps">Agentic CogWriter</span> scores highest on both measures for WritingBench and HelloBench, separated from every alternative except on HelloBench pointwise scores.

### Direct Comparison of Writing Systems

Table 4 reports a system-level separation in direct same-prompt comparisons. <span class="smallcaps">Agentic CogWriter</span> is preferred to `Single-pass`, `Staged`, and `Task-planning`, with across-benchmark mean win rates of 80.9%, 67.3%, and 68.5%, respectively, among order-consistent comparisons. The direction holds in every benchmark and generation run against `Single-pass` and `Task-planning`, and in all but one benchmark–run test against `Staged`.[^7] The preference also persists under more conservative accounting: counting every attempted prompt yields win shares of 63.1%, 46.6%, and 49.7%, and assigning every missing pair against our system still leaves win rates of at least 74.9%, 61.9%, and 66.1% among order-consistent comparisons.[^8]

|  |  |  |  |  |
|:---|---:|---:|---:|---:|
|  | **<span class="smallcaps">Agentic CogWriter</span> win rate (%)** | **<span class="smallcaps">Agentic CogWriter</span> win rate (%)** | **<span class="smallcaps">Agentic CogWriter</span> win rate (%)** | **<span class="smallcaps">Agentic CogWriter</span> win rate (%)** |
| **Comparison** | **Writing** | **Hello** | **DoLo** | **Mean** |
| vs. `Single-pass` | 84.3% | 85.7% | 72.0% | 80.9% |
| vs. `Staged` | 80.9% | 62.8% | 55.9% | 67.3% |
| vs. `Task-planning` | 65.5% | 63.0% | 75.7% | 68.5% |

Table 4. <span class="smallcaps">Agentic CogWriter</span> same-prompt win rates; above 50% favors our system. Win rates exceed 50% on every benchmark against every alternative, with the largest mean margin over `Single-pass`.

The direct-comparison result supports the tested system as a whole rather than a single mechanism. Our system differs from the alternatives in several coupled design choices, including persistent writing state, a process-level action space, and repeated return to the `Monitor`. The ablations below test whether explicit goals or adaptive process order explain these differences.

### Ablations and Execution Diagnostics

Table 5 places the two pre-specified ablations much closer to <span class="smallcaps">Agentic CogWriter</span> than the alternative writing systems in Table 4. After the within-benchmark Holm correction, all benchmark–run tests comparing our system with `No-goals` or `Fixed-order` remain above the corrected significance threshold. In the exploratory prompt-level summary, our system is preferred to `Fixed-order` at 53.7% \[51.0%–56.4%\], `p=0.004`, while the corresponding preference over `No-goals` is 52.3% \[49.6%–55.0%\], `p=0.056`. The first estimate suggests a small benefit from adaptive ordering; the second does not provide evidence for a comparable effect from the explicit goal representation. Because the summary was defined after the main results, both remain exploratory.

|  |  |  |  |  |
|:---|---:|---:|---:|---:|
|  | **<span class="smallcaps">Agentic CogWriter</span> win rate (%)** | **<span class="smallcaps">Agentic CogWriter</span> win rate (%)** | **<span class="smallcaps">Agentic CogWriter</span> win rate (%)** | **<span class="smallcaps">Agentic CogWriter</span> win rate (%)** |
| **Variant** | **Writing** | **Hello** | **DoLo** | **Mean** |
| *Ablations* | *Ablations* | *Ablations* | *Ablations* | *Ablations* |
| `No-goals` | 52.1% | 52.4% | 56.0% | 53.4% |
| `Fixed-order` | 56.8% | 57.4% | 54.7% | 56.3% |
| *Bundled execution diagnostic* | *Bundled execution diagnostic* | *Bundled execution diagnostic* | *Bundled execution diagnostic* | *Bundled execution diagnostic* |
| `Single-writer` | 68.5% | 83.4% | 67.8% | 73.5% |

Table 5. Three-run <span class="smallcaps">Agentic CogWriter</span> win rates for ablations and a diagnostic; above 50% favors our system. `No-goals` and `Fixed-order` remain near parity, unlike the larger `Single-writer` gap.

Execution changes produce a larger but less easily isolated difference. `Single-writer` removes subagent delegation, changes role context and decision granularity, and alters output length at the same time. Within the tighter and wider pre-specified output-length bands, `Single-writer` still wins only 35.1% (`p=0.0141`) and 30.6% (`p=2.32 x 10^-5`), respectively, against our system, so output length alone does not explain the gap. The narrower post-hoc `Single-context` check shows no significant difference from our system in the exploratory generation run (47.4% win rate for `Single-context`, `p=0.5161`, unadjusted).[^9]

### Observed Writing-Process Behavior

The adaptive writing loop usually follows a simple process path. Table 6 shows that one `Planning``->``Translating``->``Reviewing` cycle dominates the traces; returning to planning after review and replacing an existing goal are both rare. Our system therefore has the ability to revisit earlier processes but uses that flexibility infrequently on the evaluated prompts. This pattern is consistent with the small exploratory advantage over `Fixed-order`: adaptive ordering can help only when the controller departs from the common path.

|                                                |          |
|:-----------------------------------------------|---------:|
| **Observed writing-loop behavior**             | **Rate** |
| One Planning`->`Translating`->`Reviewing cycle |    74.6% |
| Review followed by renewed Planning            |     0.3% |
| Runs with an accepted goal replacement         |     0.5% |

Table 6. One `Planning``->``Translating``->``Reviewing` cycle accounts for 74.6% of runs; replanning and goal replacement are each below 1%. <span class="smallcaps">Agentic CogWriter</span> only rarely revisits earlier processes.

Figure 2 shows the same concentration at the sequence and transition levels. The most frequent complete process path is the forward planning–drafting–reviewing progression, and our system is visually close to `Fixed-order` because much of the observed behavior follows that path. The demanding-subset selection increases input length, requested output length, or procedural burden, but it does not guarantee that every task intrinsically requires replanning. The traces therefore show that adaptive control is rarely exercised on these subsets, not that repeated replanning is unnecessary for difficult writing in general.

Figure 2. Observed writing-process trajectories. Panel (a) shows the most frequent complete paths; panels (b) and (c) show transition counts for <span class="smallcaps">Agentic CogWriter</span> and `Fixed-order`. Our system mostly follows the same forward `Planning``->``Translating``->``Reviewing` progression as `Fixed-order`, with few departures to earlier processes; this concentration is consistent with the small exploratory advantage of adaptive ordering.

Observed departures from the common process path do not show a larger quality advantage. Table 7 compares runs that complete exactly one planning–drafting–reviewing cycle with runs that take any other path and finds similar pairwise win rates against `Fixed-order` and `Single-writer`. Because the split is observational rather than randomized, it cannot establish whether a different path improves or worsens output.[^10]

|  |  |  |
|:---|---:|---:|
|  | **<span class="smallcaps">Agentic CogWriter</span> win rate (%)** | **<span class="smallcaps">Agentic CogWriter</span> win rate (%)** |
| **Process path** | **`Fixed-order`** | **`Single-writer`** |
| Plan`->`draft`->`review | 57.4% | 72.2% |
| Other path | 54.9% | 75.2% |

Table 7. Win rates are similar for planning–drafting–reviewing and other paths against `Fixed-order` and `Single-writer`. The observational split describes association rather than a causal effect.

## Discussion

Tables 3 and 4 show that the clearest advantage of <span class="smallcaps">Agentic CogWriter</span> is not uniform dominance under every pointwise score, but consistent preference in direct same-prompt comparisons. The system ranks first on WritingBench and HelloBench pointwise metrics but not DoLoMiTes, while pairwise evaluation favors it over single-pass generation, fixed writing stages, and adaptive task planning on every benchmark. The pattern supports process-level control as a useful way to organize long-form generation without requiring it to maximize every benchmark-specific metric.

Table 5 suggests that the advantage is better interpreted at the system level than assigned to either explicit goals or adaptive ordering alone. Removing the goal representation or fixing the process order leaves performance near the full system, whereas the larger `Single-writer` gap points to execution structure as another candidate explanation. The post-hoc `Single-context` diagnostic, however, does not reduce that difference to subagent delegation alone. The current evidence therefore supports the coordinated writing loop more strongly than any single tested mechanism.

Figure 2 and Table 6 add a complementary view of adaptivity. <span class="smallcaps">Agentic CogWriter</span> usually follows planning–drafting–reviewing and departs from that path only selectively, so process-level control should not be equated with continual replanning. This perspective complements systems that adapt task decomposition or structural reasoning during generation (Xiong et al., 2025; Wan et al., 2025; Sun et al., 2026): another design axis is not only how dynamically a writer replans, but what kind of writing action its controller selects.

The process findings suggest a more targeted evaluation agenda for writing agents. Long inputs and, where stated, long requested outputs, together with procedural constraints, make document production demanding but do not necessarily create reasons to revisit earlier decisions. Future benchmarks could test process control directly by changing objectives, introducing new evidence, or imposing rhetorical constraints during composition. More broadly, cognitive writing theory provides executable control abstractions rather than claiming that language agents reproduce human cognition: it makes alternative writing processes explicit enough to implement, compare, and falsify.

## Conclusion

<span class="smallcaps">Agentic CogWriter</span> reframes long-form writing for AI agents as a process-level control problem. A top-level `Monitor` chooses whether to plan, draft, or review from persistent writing state and delegates the selected process to a role-specific subagent. Across three long-form writing benchmarks, our system is preferred to single-pass generation, fixed writing stages, and adaptive task planning in direct same-prompt comparisons. Component analyses show that neither explicit goals nor adaptive process ordering alone accounts for the overall advantage, while process traces show that most runs follow a single planning–drafting–reviewing cycle. Together, these results support process-level control as a promising design for long-form writing agents and show how cognitive writing theory can yield executable, falsifiable system hypotheses.

## Limitations

##### Scope and external validity.

Our conclusions concern one generator family, one coding-agent-style harness, and deterministic demanding subsets of three long-form benchmarks. The subset rule emphasizes long inputs and, when specified, long requested outputs rather than an independent semantic measure of difficulty. The results therefore do not establish transfer to shorter tasks, objectives that change during writing, other model families or runtimes, interactive human–AI writing, or end-to-end agents with retrieval. The alternative writing systems are matched implementations under our common generator and harness, not executions of the published systems.

##### Evaluator dependence.

The primary evaluation also leaves uncertainty about judge dependence. Pairwise win rates are computed over order-consistent comparisons, where both presentation orders select the same response; Section 5.2 also reports unconditional and worst-case missing-output views. The primary evaluator belongs to the same model family as the generator, and related generator–judge models can exhibit preference leakage or self-preference (Li et al., 2026; Panickssery et al., 2024). The cross-family check produces many ties and reverses one WritingBench direction, and we did not collect human judgments, so model-judge preference should not be treated as human preference. The primary evaluator also favors longer outputs overall.

##### Component attribution.

The component analyses constrain mechanism claims without establishing equivalence. Removing the explicit goal representation or fixing process order produces no reliable difference in the pre-specified multiple-comparison-corrected tests, while the exploratory prompt-level summary estimates a small preference for adaptive ordering and no comparable goal-representation effect. `Single-writer` changes delegation, role context, decision granularity, and output length together; `Single-context` is narrower but was added post-hoc, uses one exploratory generation run, and differs in execution interface and transport. The current evidence therefore cannot attribute the remaining system-level advantage to any single shared execution feature.

##### Descriptive execution analyses.

The length- and compute-matched analyses are descriptive because both variables are consequences of execution. Process traces likewise record implemented state transitions and agent actions; they characterize how <span class="smallcaps">Agentic CogWriter</span> behaves on these tasks but do not measure human cognition or validate cognitive process theory as a model of language-agent internals.

## Prompt and Experiment Configuration

##### Prompt selection and provenance.

The scored study uses the committed `hard100` subset generated from the pinned WritingBench (Wu et al., 2026b), HelloBench (Que et al., 2024), and DoLoMiTes (Malaviya et al., 2025) manifests before generation. Prompts used while developing the protocol are removed first. Each remaining prompt is ranked by prompt word count plus the largest requested output length stated in the prompt or structured output constraints, subject to fixed maximum-length gates; ties are resolved by prompt word count, requested length, and prompt identifier. The top 100 eligible prompts from each benchmark are retained, yielding 300 scored prompts. Generation reads the committed manifests and identifiers, so system output quality cannot affect selection.

The three selected subsets stress different properties of long-form writing. WritingBench combines long inputs with explicit long-output requirements, HelloBench contributes primarily very long-input summarization and continuation tasks, and DoLoMiTes contributes methodical expert tasks with structured procedural constraints. The `hard100` name identifies the deterministic length-and-demand rule rather than a claim that every prompt has the same source of semantic difficulty.

##### Sample size and inferential sensitivity.

The 100-prompt count per benchmark was fixed before scoring. Under the realized missing and tie rates, a benchmark–contrast–generation-run test contains about 75 decided comparisons; at the strictest first-step Holm threshold, an exact sign test has 80% power for a true preference of about 73%. Combining benchmarks only for a descriptive sensitivity calculation gives about 220 decided comparisons and a detectable preference of about 63%. The calculation describes the sensitivity of the committed sample and does not make the subset representative of each full benchmark.

##### Common generation setup and implementation.

Every pre-specified system receives the same assignment, supplied context, requested output constraints, generator, attempt budget, and information policy. External retrieval is disabled by the coding-agent sandbox and by the experiment prompts. <span class="smallcaps">Agentic CogWriter</span> runs as an agent skill under a top-level `Monitor`; the `Planner`, `Translator`, and `Reviewer` subagents execute the role skills reproduced below. The platform-specific subagent wrappers only dispatch the corresponding role skills and add no separate writing policy. Configuration files pin the skill or stage prompt for every system and record hashes for fixed stage prompts.

All experiment-authored generation and evaluation prompts are reproduced verbatim below. Provider-level defaults that are not authored by the experiment are controlled through the runtime configuration in Appendix B.

### Generation Prompts

#### Baselines

The `Staged` prompts follow the planning–drafting–revision decomposition used by prior long-form writing systems (Yang et al., 2022; Wan et al., 2025), while `Task-planning` follows the adaptive task-planning formulation of WriteHERE (Xiong et al., 2025).

**`Single-pass`**

    ## A1 single-shot

    Write the final response in one generation pass. Do not make a plan for the reader, describe a review, or expose hidden reasoning.

    Use only the assignment and supplied context below. Do not browse, search, call a network service, retrieve a source, or use information that is not supplied here. Follow every requested output constraint. Return only the final response.

    ### Assignment

    {{assignment}}

    ### Supplied context

    {{supplied_context}}

    ### Requested output constraints

    {{output_constraints}}

**`Staged`: Pre-Write**

    ## A2 Pre-Write

    Prepare a concise working plan for the next writer. Identify the response's purpose, audience, required content, order, and constraints. Use only the assignment and supplied context. Do not browse, search, retrieve sources, or add outside facts. Do not write the final response yet.

    ### Assignment

    {{assignment}}

    ### Supplied context

    {{supplied_context}}

    ### Requested output constraints

    {{output_constraints}}

    ### Previous stage output

    {{previous_stage_output}}

**`Staged`: Write**

    ## A2 Write

    Write a complete draft that answers the assignment. Use the Pre-Write output as working guidance, but use only the assignment and supplied context for content. Do not browse, search, retrieve sources, or add outside facts. Follow the requested output constraints. Return only the draft.

    ### Assignment

    {{assignment}}

    ### Supplied context

    {{supplied_context}}

    ### Requested output constraints

    {{output_constraints}}

    ### Pre-Write output

    {{previous_stage_output}}

**`Staged`: Re-Write**

    ## A2 Re-Write

    Revise the draft for instruction fulfillment, organization, depth, audience fit, and factual fidelity. Use only the assignment and supplied context. Do not browse, search, retrieve sources, or add outside facts. Follow the requested output constraints. Return only the revised final response. Do not describe the revision.

    ### Assignment

    {{assignment}}

    ### Supplied context

    {{supplied_context}}

    ### Requested output constraints

    {{output_constraints}}

    ### Draft to revise

    {{previous_stage_output}}

**`Task-planning`**

    ---
    name: writing-adaptive-task-planning
    description: "Confirmatory condition A3 (Adaptive Task Planning). Build and persist a typed reasoning/composition task graph, recursively decompose and execute tasks with subagents, and revise the graph from aggregated text while keeping adaptation on task structure rather than writing-process selection."
    ---

    # Adaptive Task Planning

    Run confirmatory condition A3, Adaptive Task Planning, as an adaptation of WriteHERE[^1]'s heterogeneous recursive planning, not a reproduction. The coordinator dynamically builds a directed acyclic task graph in project files and interleaves recursive decomposition with execution. The root task is a composition task for the complete document. Child tasks may be reasoning tasks for requirements, structure, consistency, or argument development and composition tasks for section or document writing. The coordinator schedules ready tasks by graph state and dependency order, then persists the graph after every change.

    The condition changes task structure only. The coordinator must not adapt by selecting among named writing processes, replacing a task graph with a fixed process pipeline, or using a meta-process chooser. The distinction is the experimental point: Adaptive Task Planning concerns what tasks exist and how they depend on one another, not which writing workflow is selected.

    ## Equal-information and no-retrieval policy

    The runner gives this condition the same assignment, supplied context, context-window policy, timeout, model settings, total output budget, and attempt budget as every comparison condition. The graph may change shape in response to the assignment and task results, but no task may obtain information unavailable to the other conditions.

    Retrieval tasks are disabled under the equal-information policy. The graph may contain only `reasoning` and `composition` task types. Do not create a retrieval node, browse, search, call a retrieval tool, access the Internet, or use an external source. The runner records retrieval, evidence gathering, and citation handling as `N/A` in the run accounting by design. A missing fact remains uncertain or is omitted.

    The final response must contain the complete final text (the runner enforces this; a parallel runner change exists).

    This adaptation uses the task graph as its only planning structure. Do not create or modify `.writing/goals.md` and emit no goal events. The user owns rhetorical intent, factual authority, final wording, and publication. The coordinator owns graph state, ready-task scheduling, subagent dispatch, persistence, and trace recording. Typed task subagents own their returned reasoning or composition results. A native subagent must not launch a nested `codex exec` process.

    ## Persisted graph contract

    Persist the graph at `.writing/baselines/adaptive-task-planning/task-graph.json`. Keep the file valid JSON after every mutation. The top-level object includes `version`, `root_task_id`, `tasks`, and `updated_at`. Each task includes:

    - `id`, a stable project-local identifier
    - `type`, exactly `reasoning` or `composition`
    - `goal`, the task objective
    - `dependencies`, a list of task IDs that must finish first
    - `status`, one of `active`, `suspended`, or `silent`
    - `result`, either `null` or the task's returned result
    - `parent_id`, the containing task ID or `null` for the root
    - `children`, an ordered list of child task IDs

    Store task results under `.writing/baselines/adaptive-task-planning/results/` when they are too large for the graph file. Use project-relative paths in the graph. A suspended task has been decomposed or is waiting for dependencies. An active task is ready for planning or execution. A silent task has completed or failed and will not be scheduled again.

    ## Procedure

    1. Read `.writing/assignment.md` and the supplied context. Initialize a root `composition` task if the graph does not exist. Do not read or modify `.writing/goals.md`.
    2. Select the active task nearest the root by breadth-first depth, breaking ties with the graph's stable task order. Give the subagent the task's parent context, dependency results, relevant graph structure, assignment, and supplied context.
    3. Ask the subagent whether the task is atomic under the two enabled types. If the task is not atomic, ask it for typed child tasks and dependencies. Add the children to the graph, mark the parent `suspended`, and persist the graph before scheduling another task.
    4. If the task is atomic, dispatch its typed executor. A reasoning executor returns a bounded reasoning or planning artifact. A composition executor returns prose for its task. Store the result, mark the task `silent`, update dependent tasks, and persist the graph.
    5. After each composition task completes and its result is stored, re-read the current aggregated text, meaning the composition results produced so far in dependency order. Before scheduling the next task, the coordinator may perform text-conditioned graph revision. Allowed revision operations are:
       - revise the goal text of an active or suspended task
       - add new typed child tasks with dependencies under any non-silent task
       - retire an active or suspended task by marking it `silent` with a result that notes the retirement
       - add or reorder dependencies among non-silent tasks while keeping the graph acyclic

       Each revision appends one schema-valid `process_switch` event with `process: "task-revision"`. The event's `evidence` cites the specific current-text observation that motivated the revision, and its `decision` names the affected task IDs. Revision must not modify or reopen a silent task's result, rewrite already-composed text because composition tasks own prose, introduce task types beyond `reasoning` and `composition`, select or name a writing process, touch `.writing/goals.md`, or emit goal events.
    6. Continue the recursive decompose-or-execute loop until the root composition task is silent. Aggregate composition results in dependency and child order and write the final document to `.writing/draft.md`.
    7. Append one schema-valid `process_switch` event to `.writing/trace/process.jsonl` for each observable graph action that enters a top-level task state. The trace contract has a variable event count with a minimum of one event for a successful run. Every event's `process` value must be exactly one of `task-decomposition`, `task-execution`, or `task-revision`; no other process value is allowed. Explain the task ID, type, dependency evidence, and state change in `decision` and `evidence`. The trace must never claim that a writing-process choice occurred when only the task graph changed.

    Before sending the final response, complete this non-skippable checklist:

    1. The root task is `silent`.
    2. The aggregated document is written to `.writing/draft.md`.
    3. The final response contains the complete final text.

    The run is `INVALID` unless all three checks pass. Returning the complete text without writing `.writing/draft.md` does not satisfy the contract.

    Every trace event includes `timestamp`, `event_type`, `responsible_agent`, `process`, `decision`, `evidence`, `open_uncertainty`, `from_process`, and `to_process`. Use `responsible_agent: "runner"`, add the graph and relevant result files to `artifacts`, and preserve unresolved dependencies or claims in `open_uncertainty`. Retrieval, evidence, and citation fields are `N/A` by design in the runner's derived accounting, not fabricated trace events. Do not append goal events or hidden reasoning. In the JSON object, `timestamp`, `event_type`, `responsible_agent`, `process`, and `decision` are strings; `evidence` and `open_uncertainty` are arrays of strings; `from_process` and `to_process` are strings or `null`; and `artifacts` is an array of project-relative path strings; set `timestamp` to the current wall-clock time obtained from the shell at write time, for example `date -Is`, and never copy example timestamps. For example:

    ```json
    {"timestamp":"2026-01-15T09:00:00+09:00","event_type":"process_switch","responsible_agent":"runner","process":"task-decomposition","decision":"Decompose the root composition task into typed child tasks.","evidence":[".writing/baselines/adaptive-task-planning/task-graph.json"],"open_uncertainty":[],"from_process":null,"to_process":"task-decomposition","artifacts":[".writing/baselines/adaptive-task-planning/task-graph.json"]}
    ```

    The adaptation follows WriteHERE[^1]'s released typed task graph, dependency-aware states, recursive decomposition, and interleaved execution semantics. It does not reproduce the original retrieval agent, prompts, models, frontend, benchmark, or graph implementation. The experiment compares task-structure adaptation under a common no-retrieval information policy.

    [^1]: Ruibin Xiong, Yimeng Chen, Dmitrii Khizbullin, Mingchen Zhuge, and Jürgen Schmidhuber, "Beyond Outlining: Heterogeneous Recursive Planning for Adaptive Long-form Writing with Language Models," *Proceedings of the 2025 Conference on Empirical Methods in Natural Language Processing* (EMNLP 2025), 2025, https://aclanthology.org/2025.emnlp-main.1254/.

#### Agentic CogWriter

**Top-level Agent Skill**

    ---
    name: agentic-cog-writer
    description: Use this skill whenever a user needs help with writing. It runs a `Monitor` loop over the user's rhetorical problem and project state, coordinates the writing processes, and preserves an observable process trace.
    ---

    # Agentic cog writer

    Use this skill in the user's writing project. The project root is the current working directory unless the user names another project.

    The `Monitor` is the main agent running this skill. The `Monitor` chooses the next writing process from the project state and open uncertainty. The `Monitor` does not impose a fixed stage sequence.

    ## `Monitor` responsibilities

    - Keep these under the user's control:
      - rhetorical intent
      - factual authority
      - final wording
      - publication decision
    - Coordinate process switches as the main agent. Record the evidence for each switch and ask the user when a choice materially changes the rhetorical problem or a claim.
    - Delegate the selected process to its role agent. Follow the delegation instructions below.
    - Reconcile each returned report with the active goal and tell the user about proposals that affect intent, factual claims, or a major goal. Let the user override any agent decision.

    ## Start by establishing the writing state

    1. Treat these files as the project's externalized task environment and long-term memory. Create missing files and directories without overwriting existing user content:

       ```text
       .writing/
       ├── assignment.md       # topic, audience, exigency, and writer's goals
       ├── goals.md            # hierarchical goals and creation/development history
       ├── draft.md            # the growing text
       ├── memory/             # topic knowledge, audience knowledge, and writing plans
       └── trace/              # structured process history, one JSON object per line
       ```

    2. Read these before choosing an operation:

       - `.writing/assignment.md`
       - `.writing/goals.md`
       - `.writing/draft.md`
       - relevant files in `.writing/memory/`
       - the latest entries in `.writing/trace/process.jsonl`

       If `.writing/assignment.md` is missing or underspecified, ask the user for:

       - topic
       - audience
       - exigency
       - writer's goals
       - genre
       - constraints

       Do not silently invent a rhetorical problem.

    3. Keep `goals.md` in the notation described in [`references/goals-format.md`](references/goals-format.md). Update it whenever a goal is created, developed, or regenerated. Preserve the history instead of replacing an earlier goal without recording what changed.
    4. Read [`references/trace-jsonl-schema.md`](references/trace-jsonl-schema.md) before writing the first trace entry. Append to `.writing/trace/process.jsonl`; never rewrite or truncate that log.

    ## `Monitor` loop

    At each turn, the `Monitor` should:

    1. Identify the active goal and its parent. If a sub-goal resolves, pop back to the parent goal before choosing the next operation.
    2. Compare the active goal with:

       - the rhetorical problem
       - the current draft
       - retrieved memory
       - open uncertainty

       Use that comparison to select `Planning`, `Translating`, or `Reviewing`. `Planning` may mean:

       - exploring
       - organizing
       - setting a goal

       `Reviewing` may mean:

       - evaluating
       - revising

    3. Before every process switch, append a `process_switch` event naming the responsible process or agent and recording the decision, evidence, and open uncertainty. Record a separate goal event whenever a goal is created, developed, or regenerated. Use the exact fields in the trace reference.
    4. Delegate the selected role using the platform instructions in Delegation briefs.
    5. Re-read the changed state and reconcile the agent's report with the active goal. Treat `Reviewing` verdicts as proposals. Record `goal_developed` only when the Monitor updates that goal and adds its `goals.md` history row; otherwise record an unacted-on `develop` verdict as a disposition without a goal event. For every `regenerate` verdict, either accept it or reject it. On acceptance, update `goals.md` with a history row that keeps the original goal ID marked `superseded` and gives the replacement a new goal ID, and emit `goal_regenerated` with the replacement's `goal_id` and the original goal's `parent_goal_id`; on rejection, write `rejected regeneration of <goal id>: <reason>` in the next `process_switch` decision. The next `process_switch` decision after a `Reviewing` pass must enumerate every received `regenerate` verdict as `regeneration proposals: G2 accepted (<reason>); G4 rejected (<reason>)`, substituting the actual goal IDs and reasons, or `regeneration proposals: none` when no `regenerate` verdict was received. Append that post-`Reviewing` `process_switch` carrying the enumeration before either continuing or completing the run. If the run continues, set its `to_process` to the next process. If the run ends after `Reviewing`, set its `process` and `from_process` to `reviewing` and its `to_process` to `null` before completing the run. After every Translating pass, compare the new draft with every active goal in goals.md, then record a goal_developed or goal_regenerated event for each goal the draft changed, or state in the next process_switch decision that the goal network needed no change and why. Update the appropriate project state:

       - `goals.md`
       - `draft.md`
       - `memory/`

       Keep user-authored text and uncertain claims visible rather than silently normalizing them.

    6. Tell the user:

       - what changed
       - which goal is active
       - what remains uncertain
       - which process the `Monitor` recommends next

       Ask for a decision when the next move depends on the user's intent or factual authority.

    Before sending the final response, complete this non-skippable checklist:

    1. The complete current document is written to `.writing/draft.md`.
    2. The trace holds one goal event (`goal_created`, `goal_developed`, or `goal_regenerated`) for every goal recorded in `goals.md` during this run.
    3. The final response contains the complete final text.

    The run is `INVALID` unless `.writing/draft.md` exists before the final response and the final response contains the complete final text. The final response cannot substitute for the required draft.

    ## Non-linear control rules

    The writing processes form a recursive loop, not a pipeline. A process may call another process to solve a local problem, and that process may call the whole loop again.

    Generate and Evaluate may interrupt any process when new information or a conflict in the growing text demands it. Log the interruption as a process switch, then resume the interrupted parent goal after the sub-goal resolves.

    When new writing changes what the author understands, use Goal-setting to develop or regenerate the goal network. A regenerated goal is not a failure of the earlier plan; it is part of learning through composing. Keep both the prior record and the new rationale in `goals.md` and the trace.

    ## Delegation briefs

    For every delegation, pass:

    - the project root
    - the current goal context: for `Reviewing`, every active goal with its ID plus the parent goal ID; otherwise, the active and parent goal IDs
    - relevant uncertainty
    - the requested output

    Ask each agent to cite the files or draft passages that support its decisions.

    Use the platform path that matches the host:

    - Claude Code: delegate to the bundled role agent. The bundled role agent preloads the matching role skill.
    - Codex: spawn a native Codex subagent and instruct it to use the explicit role skill: `$planning`, `$translating`, or `$reviewing`.

    Do not write a script that spawns `codex exec` children.

    If native delegation is unavailable, perform the role as the `Monitor` and record that fallback in the trace.

    ## Trace contract

    Every process switch and every goal creation, development, or regeneration must append one valid JSON object to `.writing/trace/process.jsonl`. A process-switch object includes `timestamp`, `event_type`, `responsible_agent`, `process`, `decision`, `evidence`, `open_uncertainty`, `from_process`, and `to_process`. A goal event also includes `goal_id` and `parent_goal_id`. Optional `artifacts` lists project-relative files. In the JSON object, `timestamp`, `event_type`, `responsible_agent`, `process`, and `decision` are strings; `evidence` and `open_uncertainty` are arrays of strings; `from_process` and `to_process` are strings or `null`; `goal_id` is a string; `parent_goal_id` is a string or `null`; and `artifacts`, when present, is an array of project-relative path strings; set `timestamp` to the current wall-clock time obtained from the shell at write time, for example `date -Is`, and never copy example timestamps. Keep the code-formatted role names `Planning`, `Translating`, and `Reviewing` in surrounding prose, but write JSON `process`, `from_process`, and `to_process` values with the lowercase contract tokens `planning`, `translating`, and `reviewing`. Do not add experiment-specific fields to the shared trace contract. For example:

    ```json
    {
      "timestamp": "2026-01-15T09:00:00+09:00",
      "event_type": "process_switch",
      "responsible_agent": "monitor",
      "process": "planning",
      "decision": "Choose planning for the active goal and current uncertainty.",
      "evidence": [".writing/assignment.md", ".writing/goals.md"],
      "open_uncertainty": [
        "The audience's highest-priority concern is not yet known."
      ],
      "from_process": null,
      "to_process": "planning",
      "artifacts": [".writing/goals.md"]
    }
    ```

    ## References

    Read these only when the corresponding operation needs them:

    - [`references/trace-jsonl-schema.md`](references/trace-jsonl-schema.md) defines the trace fields and event types.
    - [`references/goals-format.md`](references/goals-format.md) defines hierarchical goal notation and history records.

**`Planner` Subagent Wrapper**

    ---
    name: planner
    description: "`Planning` sub-agent for the agentic-cognitive-writing `Monitor`."
    tools: Read, Write, Edit, Glob, Grep
    skills:
      - planning
    ---

    Follow the preloaded `planning` skill as the complete role prompt. Apply its embedded sub-processes and return the report format it specifies. Treat the `Monitor`'s delegation brief as authoritative for the project root, goal identifiers (IDs), scope, and uncertainty.

**`Planner` Role Skill**

    ---
    name: planning
    description: Internal role skill for the agentic-cognitive-writing `Monitor`. Invoked by delegation from the `Monitor`; do not select this skill directly.
    ---

    # `Planning`

    Turn a delegated writing problem into grounded knowledge, useful organization, and a maintained goal network.

    ## When this skill runs

    You are the `Planning` sub-agent for the agentic-cognitive-writing plugin. The `Monitor` delegates a writing problem to you with a project root, an active goal, and current uncertainty.

    ## Read the state first

    Read these before acting:

    - `.writing/assignment.md`
    - `.writing/goals.md`
    - `.writing/draft.md`
    - relevant files in `.writing/memory/`
    - recent entries in `.writing/trace/process.jsonl`

    Treat the assignment as the rhetorical problem, including:

    - topic
    - audience
    - exigency
    - writer's goals
    - genre
    - constraints

    Do not replace missing user intent with a guess.

    ## Sub-processes

    Your work contains three embedded sub-processes, which you perform inside this prompt rather than delegating to more agents:

    1. Generate: retrieve relevant knowledge from:
       - the project memory
       - user-provided material
       - the current draft

       Separate known material, plausible ideas, and unsupported claims.
    2. Organize: group ideas and identify relationships or missing categories. Propose an order or presentation pattern that serves the audience. The organizing work makes meaning rather than merely rearranging bullets.
    3. Goal-setting: create or develop concrete sub-goals under the active parent goal. Regenerate a higher-level goal only when the exploration or draft provides evidence that the writer's purpose has changed.

    ## Boundaries

    The `Planning` role updates goals, the `Monitor` owns trace evidence, and the user owns intent. Update `.writing/goals.md` when the delegated task creates, develops, or regenerates a goal. Preserve stable goal identifiers (IDs) and add the reason to the history. Return the evidence and uncertainty that the `Monitor` must record. Do not silently change the assignment, factual claims, or the user's top-level intent.

    ## Report format

    Return a concise report with:

    - active parent and child goal IDs;
    - generated knowledge, separated by confidence;
    - the proposed organization and why it fits the audience;
    - goal changes and their evidence;
    - unresolved uncertainty;
    - whether the `Monitor` should continue planning, translate, or review

**`Translator` Subagent Wrapper**

    ---
    name: translator
    description: "`Translating` sub-agent for the agentic-cognitive-writing `Monitor`."
    tools: Read, Write, Edit, Glob, Grep
    skills:
      - translating
    ---

    Follow the preloaded `translating` skill as the complete role prompt. Apply its report format. Treat the `Monitor`'s delegation as authoritative for project root, goal context, scope, and uncertainty.

**`Translator` Role Skill**

    ---
    name: translating
    description: Internal role skill for the agentic-cognitive-writing `Monitor`. Invoked by delegation from the `Monitor`; do not select this skill directly.
    ---

    # `Translating`

    Turn selected meanings and plans into prose within the `Monitor`'s delegated draft scope.

    ## When this skill runs

    You are the `Translating` sub-agent for the agentic-cognitive-writing plugin. The `Monitor` delegates a bounded drafting task with a project root, active goal, parent goal, audience, and requested scope.

    ## Read the state first

    Read these before editing:

    - `.writing/assignment.md`
    - `.writing/goals.md`
    - `.writing/draft.md`
    - relevant files in `.writing/memory/`
    - recent trace entries

    Translate the selected ideas into prose while treating the current wording as provisional. Keep the active goal visible while drafting. Preserve a useful existing sentence when it serves that goal; do not let fluent wording override the rhetorical purpose.

    ## Drafting rules

    Write only the delegated scope in `.writing/draft.md` unless the `Monitor` explicitly asks for an alternative. Preserve useful user text. Flag changes to any of these:

    - claims
    - structure
    - tone
    - audience assumptions

    Do not invent sources, quotations, statistics, or facts. Mark a gap as an open uncertainty for the `Monitor`.

    ## Boundaries

    The `Monitor` owns the process trace and decides whether a new goal is warranted. You may recommend a goal change, but do not create one silently while translating.

    ## Report format

    Return a concise report with:

    - the goal and draft scope addressed;
    - what prose was added or changed;
    - claims that need evidence or user confirmation;
    - how the draft now serves the audience;
    - whether the result exposed a new planning or review need

**`Reviewer` Subagent Wrapper**

    ---
    name: reviewer
    description: "`Reviewing` sub-agent for the agentic-cognitive-writing `Monitor`."
    tools: Read, Write, Edit, Glob, Grep
    skills:
      - reviewing
    ---

    Follow the preloaded `reviewing` skill as the complete role prompt. Apply its embedded sub-processes and return the report format it specifies. Treat the `Monitor`'s delegation brief as authoritative for the project root, goal identifiers (IDs), scope, and uncertainty.

**`Reviewer` Role Skill**

    ---
    name: reviewing
    description: Internal role skill for the agentic-cognitive-writing `Monitor`. Invoked by delegation from the `Monitor`; do not select this skill directly.
    ---

    # `Reviewing`

    Evaluate the draft and plan against the rhetorical problem, then revise only within the `Monitor`'s delegated scope.

    ## When this skill runs

    You are the `Reviewing` sub-agent for the agentic-cognitive-writing plugin. The `Monitor` delegates a review with a project root, active goal, parent goal, draft scope, and uncertainty.

    ## Read the state first

    Read these before reviewing:

    - `.writing/assignment.md`
    - `.writing/goals.md`
    - `.writing/draft.md`
    - relevant files in `.writing/memory/`
    - recent trace entries

    Your work contains two embedded sub-processes, which you perform inside this prompt rather than delegating to more agents.

    ## Sub-processes

    1. Evaluate: test the draft and plan against:

       - the rhetorical problem
       - the audience
       - active goals
       - claim support
       - organization
       - coherence
       - tone
       - local wording

       Distinguish goal and evidence failures from organization and sentence failures.

    2. Revise: make only the requested or clearly authorized changes in the delegated scope. Preserve the writer's intent, call out factual gaps, and state whether the change is local or changes the goal network.

    ## Boundaries

    Evaluation may interrupt any writing process when the draft, a new fact, or a goal conflict demands it. Tell the `Monitor` when that happens.

    If the draft reveals a more useful purpose, recommend goal regeneration with evidence; do not hide the change as copy-editing.

    Do not invent citations or claims.

    ## Report format

    Return a concise report with:

    - findings ordered by effect on the active goal;
    - evidence from the relevant assignment, goal, memory, or draft state;
    - revisions made and their scope;
    - unsupported claims and open uncertainty;
    - when the delegation brief includes a goal network, give one verdict for each active goal, identified by ID, using exactly one of `keep`, `develop`, or `regenerate`. Use one line per goal in the form `- <goal ID> — <keep|develop|regenerate>: <one sentence of evidence from the draft>`. The verdict word must be lowercase: use exactly `keep`, `develop`, or `regenerate`, not `Keep`, `Develop`, `Regenerate`, or another synonym. For `regenerate`, include the proposed replacement purpose in that sentence. Omit this item when the brief has no goal network;
    - whether the `Monitor` should return to the parent goal, plan, translate, or review again

#### Ablations and Execution Variants

**`No-goals`**

    ---
    name: cognitive-writing-no-goal-network
    description: "Experiment-comparison variant of the agentic-cog-writer skill for testing writing without a hierarchical goal network. For internal comparison use only, not the recommended default. Use when a controlled no-goal-network comparison is explicitly requested."
    ---

    # Cognitive writing without a goal network

    Run a comparison that uses the assignment as one implicit objective while preserving the agentic-cog-writer skill's project state, delegation, and trace contracts.

    ## When this skill runs

    Use this skill only when the user explicitly requests a controlled no-goal-network comparison. Do not use it as the default writing workflow.

    ## `Monitor` responsibilities

    - Keep rhetorical intent, factual authority, final wording, and publication decisions under the user's control.
    - Coordinate process switches and record the evidence for each switch.
    - Ask the user when a choice changes the rhetorical problem or a claim.
    - Reconcile each returned role report with the assignment before continuing.
    - Report proposals that affect intent or factual claims. Let the user override an agent decision.

    ## Read the state first

    Create missing files and directories without overwriting existing content. Do not create or modify `.writing/goals.md`. Treat these files as the user's externalized task environment and long-term memory:

    ```text
    .writing/
    ├── assignment.md       # topic, audience, exigency, and writer's goals
    ├── goals.md            # existing file is left untouched, if present
    ├── draft.md            # growing text
    ├── memory/             # topic knowledge, audience knowledge, and writing plans
    └── trace/              # structured process history, one JSON object per line
    ```

    Read these before choosing a process:

    - `.writing/assignment.md`
    - `.writing/draft.md`
    - relevant files in `.writing/memory/`
    - the latest entries in `.writing/trace/process.jsonl`

    Do not create or modify `.writing/goals.md`, whether it exists or not.

    Treat the assignment as the single implicit objective. Do not use a hierarchical goal to fill missing user intent.

    If `assignment.md` is missing or underspecified, ask for:

    - topic
    - audience
    - exigency
    - writer's goals
    - genre
    - constraints

    Do not silently invent a rhetorical problem.

    Read the trace field contract below before writing the first entry. Append to `.writing/trace/process.jsonl`; never rewrite or truncate that log.

    ## `Monitor` loop

    At each turn, the `Monitor` must:

    1. Compare the assignment's implicit objective with the current project state and open uncertainty. Choose `Planning`, `Translating`, or `Reviewing` from that comparison. Do not consult or construct a hierarchical goal network.
    2. Before every process switch, append a `process_switch` event naming the responsible process or agent, its decision, its evidence, and open uncertainty. The no-goal-network variant records no goal-created, goal-developed, or goal-regenerated events.
    3. Delegate the selected role using the Delegation section.
    4. For a `Planning` delegation, request problem representation, Generate, and Organize. Do not request Goal-setting or ask the agent to write `goals.md`. If the agent proposes a hierarchical goal, report it as an observation without changing the file.
    5. Re-read changed state and reconcile the role's work with the assignment. Update `draft.md` or `memory/` as appropriate. Keep user-authored text and uncertain claims visible.
    6. Tell the user:

       - what changed
       - that the assignment remains the implicit objective
       - what remains uncertain
       - which process the `Monitor` recommends next

       Ask for a decision when the next move depends on user intent or factual authority.

    Before sending the final response, write the complete current document to `.writing/draft.md`. The run is `INVALID` unless `.writing/draft.md` exists before the final response and the final response contains the complete final text. The final response cannot substitute for the required draft.

    ## Interruptions

    Generate and Evaluate may interrupt any process when new information or a claim conflict in the growing text demands it. Log each interruption as a `process_switch`, perform the interrupt through the relevant shared role, return to the process that initiated it, and then continue the `Monitor`'s process choice.

    Do not create a goal to track the interrupt. When an interrupt resolves, return to the process that initiated it rather than silently changing the assignment.

    ## Delegation

    For every delegation, pass:

    - the project root
    - the assignment summary
    - relevant uncertainty
    - the requested output

    Ask the delegated agent to cite the files or draft passages that support its decisions. Use the platform path that matches the host:

    - Claude Code: delegate to the planner, translator, or reviewer agent shipped in the `agentic-cognitive-writing` plugin. That agent preloads the matching role skill.
    - Codex: spawn a native Codex subagent and instruct it to use `$planning`, `$translating`, or `$reviewing`.

    Do not write a script that spawns `codex exec` children. If native delegation is unavailable, perform the role as the `Monitor` and record that fallback in the trace.

    ## Trace contract

    Every process switch must append one valid JSON object to `.writing/trace/process.jsonl`. `event_type` is `process_switch`; goal events are not written in this condition. A process-switch object includes `timestamp`, `event_type`, `responsible_agent`, `process`, `decision`, `evidence`, `open_uncertainty`, `from_process`, and `to_process`. Optional `artifacts` lists project-relative files. In the JSON object, `timestamp`, `event_type`, `responsible_agent`, `process`, and `decision` are strings; `evidence` and `open_uncertainty` are arrays of strings; `from_process` and `to_process` are strings or `null`; and `artifacts`, when present, is an array of project-relative path strings; set `timestamp` to the current wall-clock time obtained from the shell at write time, for example `date -Is`, and never copy example timestamps. Keep the code-formatted role names `Planning`, `Translating`, and `Reviewing` in surrounding prose, but write JSON `process`, `from_process`, and `to_process` values with the lowercase contract tokens `planning`, `translating`, and `reviewing`. Do not write goal fields or experiment-specific fields. For example:

    ```json
    {
      "timestamp": "2026-01-15T09:00:00+09:00",
      "event_type": "process_switch",
      "responsible_agent": "monitor",
      "process": "planning",
      "decision": "Choose planning for the assignment's implicit objective.",
      "evidence": [".writing/assignment.md"],
      "open_uncertainty": [],
      "from_process": null,
      "to_process": "planning",
      "artifacts": [".writing/assignment.md"]
    }
    ```

**`Fixed-order`**

    ---
    name: cognitive-writing-fixed-order
    description: "Experiment-comparison variant of the agentic-cog-writer skill for testing a fixed `Planning`, `Translating`, then `Reviewing` order. For internal comparison use only, not the recommended default. Use when a controlled fixed-order comparison is explicitly requested."
    ---

    # Fixed-order cognitive writing

    Run a comparison with a fixed `Planning`, `Translating`, then `Reviewing` order while preserving the agentic-cog-writer skill's project state, goal network, delegation, and trace contracts.

    ## When this skill runs

    Use this skill only when the user explicitly requests a controlled fixed-order comparison. Do not use it as the default writing workflow.

    ## `Monitor` responsibilities

    - Keep rhetorical intent, factual authority, final wording, and publication decisions under the user's control.
    - Coordinate the prescribed order and record the evidence for each process switch.
    - Ask the user when a choice changes the rhetorical problem, a claim, or a major goal.
    - Reconcile each returned role report with the active goal before continuing.
    - Report proposals that affect intent, factual claims, or a major goal. Let the user override any agent decision.

    ## Read the state first

    Create missing files and directories without overwriting existing content. Treat these files as the user's externalized task environment and long-term memory:

    ```text
    .writing/
    ├── assignment.md       # topic, audience, exigency, and writer's goals
    ├── goals.md            # hierarchical goals and creation/development history
    ├── draft.md            # growing text
    ├── memory/             # topic knowledge, audience knowledge, and writing plans
    └── trace/              # structured process history, one JSON object per line
    ```

    Read these before the first process:

    - `.writing/assignment.md`
    - `.writing/goals.md`
    - `.writing/draft.md`
    - relevant files in `.writing/memory/`
    - the latest entries in `.writing/trace/process.jsonl`

    If `assignment.md` is missing or underspecified, ask for:

    - topic
    - audience
    - exigency
    - writer's goals
    - genre
    - constraints

    Do not invent a rhetorical problem.

    Keep `goals.md` in the project's hierarchical notation. Use stable goal identifiers (IDs). Put one goal on each line. Indent child goals beneath their parent. Keep a history section.

    Update the file whenever a goal is created, developed, or regenerated. Preserve earlier history and record the reason for each change.

    Read the trace field contract below before writing the first entry. Append to `.writing/trace/process.jsonl`; never rewrite or truncate that log.

    ## Fixed `Monitor` loop

    At each pass, the `Monitor` must:

    1. Start with `Planning`. After `Planning` resolves, switch to `Translating`. After `Translating` resolves, switch to `Reviewing`. Start the next pass with `Planning`.
    2. Keep the active goal and its parent visible. When a sub-goal resolves, pop back to its parent before continuing the prescribed order.
    3. Compare the active goal with the rhetorical problem, draft, retrieved memory, and open uncertainty. Use that evidence within the current prescribed process. Do not choose a different next process because a local preference suggests it.
    4. Before every process switch, append a `process_switch` event naming the responsible process or agent and recording its decision, evidence, and open uncertainty. Record a separate goal event whenever a goal is created, developed, or regenerated. Use the exact fields in the trace contract below.
    5. Delegate the current role using the Delegation section.
    6. After every `Reviewing` pass, re-read changed state and reconcile the role's report with the active goal. Treat `Reviewing` verdicts as proposals. Record `goal_developed` only when the Monitor updates that goal and adds its `goals.md` history row; otherwise record an unacted-on `develop` verdict as a disposition without a goal event. For every `regenerate` verdict, either accept it or reject it. On acceptance, update `goals.md` with a history row that keeps the original goal ID marked `superseded` and gives the replacement a new goal ID, and emit `goal_regenerated` with the replacement's `goal_id` and the original goal's `parent_goal_id`; on rejection, write `rejected regeneration of <goal id>: <reason>` in the next `process_switch` decision. The next `process_switch` decision after a `Reviewing` pass must enumerate every received `regenerate` verdict as `regeneration proposals: G2 accepted (<reason>); G4 rejected (<reason>)`, substituting the actual goal IDs and reasons, or `regeneration proposals: none` when no `regenerate` verdict was received. Append that post-`Reviewing` `process_switch` carrying the enumeration before either continuing or completing the run. If the run continues, set its `to_process` to the next process. If the run ends after `Reviewing`, set its `process` and `from_process` to `reviewing` and its `to_process` to `null` before completing the run. After a `regenerate` disposition, do not return to `Planning` within the current pass or change the fixed order; complete the `Reviewing` pass, then begin the next pass with `Planning`. After every Translating pass, compare the new draft with every active goal in goals.md, then record a goal_developed or goal_regenerated event for each goal the draft changed, or state in the next process_switch decision that the goal network needed no change and why. Update the appropriate project state:

       - `goals.md`
       - `draft.md`
       - `memory/`

       Keep user-authored text and uncertain claims visible.

    7. Tell the user:

       - what changed
       - which goal is active
       - what remains uncertain
       - which prescribed process comes next

       Ask for a decision when the next move depends on user intent or factual authority.

    Before sending the final response, write the complete current document to `.writing/draft.md`. The run is `INVALID` unless `.writing/draft.md` exists before the final response and the final response contains the complete final text. The final response cannot substitute for the required draft.

    ## Interruptions

    Generate and Evaluate may interrupt any process when new information or a conflict in the growing text demands it. Log each interruption as a `process_switch`, perform the interrupt through the relevant shared role, return to the interrupted process, and then continue with the next process in the prescribed order.

    An interruption must not select a new order. After any sub-goal resolves, return to its parent goal.

    ## Delegation

    For every delegation, pass:

    - the project root
    - the current goal context: for `Reviewing`, every active goal with its ID plus the parent goal ID; otherwise, the active and parent goal IDs
    - relevant uncertainty
    - the requested output

    Ask the delegated agent to cite the files or draft passages that support its decisions. Use the platform path that matches the host:

    - Claude Code: delegate to the planner, translator, or reviewer agent shipped in the `agentic-cognitive-writing` plugin. That agent preloads the matching role skill.
    - Codex: spawn a native Codex subagent and instruct it to use `$planning`, `$translating`, or `$reviewing`.

    Do not write a script that spawns `codex exec` children. If native delegation is unavailable, perform the role as the `Monitor` and record that fallback in the trace.

    ## Trace contract

    Every process switch and every goal creation, development, or regeneration must append one valid JSON object to `.writing/trace/process.jsonl`. `event_type` is one of `process_switch`, `goal_created`, `goal_developed`, or `goal_regenerated`. A process-switch object includes `timestamp`, `event_type`, `responsible_agent`, `process`, `decision`, `evidence`, `open_uncertainty`, `from_process`, and `to_process`. A goal event also includes `goal_id` and `parent_goal_id`. Optional `artifacts` lists project-relative files. In the JSON object, `timestamp`, `event_type`, `responsible_agent`, `process`, and `decision` are strings; `evidence` and `open_uncertainty` are arrays of strings; `from_process` and `to_process` are strings or `null`; `goal_id` is a string; `parent_goal_id` is a string or `null`; and `artifacts`, when present, is an array of project-relative path strings; set `timestamp` to the current wall-clock time obtained from the shell at write time, for example `date -Is`, and never copy example timestamps. Keep the code-formatted role names `Planning`, `Translating`, and `Reviewing` in surrounding prose, but write JSON `process`, `from_process`, and `to_process` values with the lowercase contract tokens `planning`, `translating`, and `reviewing`. Do not add experiment-specific fields to the shared trace contract. For example:

    ```json
    {
      "timestamp": "2026-01-15T09:00:00+09:00",
      "event_type": "process_switch",
      "responsible_agent": "monitor",
      "process": "planning",
      "decision": "Begin the prescribed planning pass for the active goal.",
      "evidence": [".writing/assignment.md", ".writing/goals.md"],
      "open_uncertainty": [
        "The audience's highest-priority concern is not yet known."
      ],
      "from_process": null,
      "to_process": "planning",
      "artifacts": [".writing/goals.md"]
    }
    ```

**`Single-writer`**

    ---
    name: cognitive-writing-single-writer
    description: "Experimental A7 writing skill based on Flower and Hayes's single Writer. Use for controlled comparisons that require one main agent, a live hierarchical goal network, paragraph-scale recursion, and an append-only process trace with Figure 2's sentence example as the theoretical anchor."
    ---

    # Cognitive writing single writer

    Use this skill only for A7. Flower and Hayes's _A Cognitive Process Theory of Writing_[^1] models one Writer with Planning, Translating, and Reviewing under a Monitor. The paper says nothing about software agents. A7 operationalizes that model as one main agent that is both Writer and Monitor, with no subagents.

    ## One Writer and one Monitor

    The main agent is the only Writer. Do not spawn subagents, role agents, delegation tools, or another writing process. The wrapper sets `require_delegation = false`.

    The `Monitor` is the strategist. Choose the next process from the current goal network, the rhetorical problem, and the growing text. Do not impose a stage sequence. Use this default style: plan briefly at the top level, compose one paragraph at a time, and plan locally when needed. A writer may instead explore for a time or move toward polished prose quickly when the active goals support that choice.

    ## Read and preserve the writing state

    Work in the session's current directory. Create missing files without overwriting user content:

    ```text
    .writing/
    ├── assignment.md
    ├── assumptions.md
    ├── goals.md
    ├── draft.md
    ├── memory/
    └── trace/process.jsonl
    ```

    Initialize `.writing/trace/process.jsonl` before writing any goals or process events. Run the trace-initialization command separately from the command that writes initial goals. Create the trace file without truncating existing content. Read `assignment.md`, `goals.md`, `draft.md`, relevant `memory/` files, and the latest trace entries before choosing a process. If the assignment leaves the audience, purpose, scope, genre, or constraints unclear, make a reasonable single-turn assumption and record it in `.writing/assumptions.md`. Do not ask a clarifying question.

    When the initial goal network is missing, write `goals.md` and append one `goal_created` event for every goal in that initial network in the same shell command, before any `Translating` switch. The trace file must already exist before that command. Never write a goal first and defer its event to a later command.

    Use this order for an initial network. First run the initialization command, then run one new shell command that writes `goals.md` and appends one `goal_created` event for every goal line written in the heredoc:

    ```sh
    mkdir -p .writing/trace .writing/memory
    : >> .writing/trace/process.jsonl
    ```

    ```sh
    stamp=$(date -Is)
    cat >> .writing/goals.md <<'EOF'
    G1 | parent: null | State the task's purpose and scope. | kind: content | status: active
    EOF
    printf '%s\n' "{\"timestamp\":\"$stamp\",\"event_type\":\"goal_created\",\"responsible_agent\":\"Writer\",\"process\":\"goal-setting\",\"decision\":\"Create G1 for the task purpose.\",\"evidence\":[\".writing/goals.md\"],\"open_uncertainty\":[],\"goal_id\":\"G1\",\"parent_goal_id\":null}" >> .writing/trace/process.jsonl
    ```

    Follow the repository writing contract for structure, links, claims, and plain English. Apply the `unslop` skill before finishing. Remove filler, AI-pattern phrasing, vague claims, and unnecessary headings without changing the task's meaning.

    ## Keep a working goal network

    The paper's "Writing is a goal-directed process" and "Goals, Topic, and Text" sections describe goals created, developed, and revised during composing. The paper predicts that good and poor writers differ in the quantity and quality of middle-range goals that bridge intention and prose. A7 therefore asks the Writer to make those goals explicit. The prediction belongs to the paper, and the explicit file representation belongs to this experiment.

    Treat `.writing/goals.md` as the current hierarchical network, not a ledger. Each line has a stable goal ID, parent ID, one-line statement, `kind` (`process` or `content`), and `status` (`active`, `resolved`, or `superseded`). Use indentation for parent and child relationships. Keep no history table, verdict list, or proposal list in the file. History lives in the trace.

    When the Writer creates a goal, update the network and append `goal_created`. When the Writer makes an existing goal more specific, update it and append `goal_developed`. When an evaluated passage shows that the active goal is wrong or too abstract, regenerate it immediately: mark the old ID `superseded`, create a new active ID, use the old ID as `parent_goal_id`, and append `goal_regenerated`. There is no proposal-and-acceptance step.

    ## Compose recursively at paragraph scale

    The paper's process model treats processes as optional and allows them to embed at any level. Figure 2 remains the theoretical anchor: planning, translating, and reviewing embed while the Writer works on one sentence. This experiment fixes the smallest observable unit at one paragraph because the writer batches to subsection scale when the unit is left at the sentence. A paragraph is one locally coherent block serving one local goal, not a whole section or subsection.

    For each paragraph, let the `Monitor` choose the next process, translate the paragraph, and use its text to choose what happens next. `generate` and `evaluate` may interrupt any process at any time. When an `evaluate` step finds that the paragraph elaborates or narrows its active goal, update `goals.md`, append the `evaluate` event, and append `goal_developed` in one shell command, following the paper's "State and Develop" pattern. Do not force `goal_developed` when the goal is unchanged. When a local goal resolves, pop back to its immediate parent. When an exploration burst yields useful material, return to the top-level goal and consolidate it into a more specific goal. When a trial paragraph shows that the active goal needs a new purpose or level of abstraction, update `goals.md` and append the `evaluate` and `goal_regenerated` events in one shell command. Do not pop or regenerate mechanically after every paragraph.

    ## Mechanical incremental composition

    The draft is built by appending to `.writing/draft.md`. If the file is missing, create the empty file with `: >> .writing/draft.md`; never truncate it. Never assemble a full draft and write it in one operation. Never use a replacement write, `>`, or a whole-file rewrite. The only exception is a local revision of the most recent passage. Replace only that passage, append a `process_switch` whose `process` is `revise` in the same shell command, and then return to append-only writing. Never rewrite an earlier passage.

    Each `Translating` step appends exactly one paragraph serving one local goal, at most about 120 words. Never append more than 200 words. If a coherent paragraph would exceed about 120 words, split it into two append commands and put an `evaluate` step between them. Each append command must contain one paragraph only, never a subsection or several blank-line-separated paragraphs, and must end with a blank line. In the same shell command, append that paragraph first and then append its `process_switch` plus any goal events to `.writing/trace/process.jsonl`. Do not predeclare future paragraphs or events. Do not write any trace event in a setup-only command before the first draft append. A quoted heredoc may hold the short paragraph and one JSON object per line. The shell command must use `>>` for the draft and trace. Keep evidence factual at append time, such as the existing draft quote, file path, or goal ID, never future-tense evidence.

    Use one shell command with this order for every translating batch:

    ```sh
    fragment=$(cat <<'EOF'
    One paragraph of no more than about 120 words for one local goal.
    EOF
    )
    test "$(printf '%s\n' "$fragment" | wc -w)" -le 120
    printf '%s\n\n' "$fragment" >> .writing/draft.md
    stamp=$(date -Is)
    printf '%s\n' "{\"timestamp\":\"$stamp\",\"event_type\":\"process_switch\",\"responsible_agent\":\"Monitor\",\"process\":\"translating\",\"decision\":\"Append the local passage.\",\"evidence\":[],\"open_uncertainty\":[],\"from_process\":null,\"to_process\":\"translating\"}" >> .writing/trace/process.jsonl
    ```

    Replace process values and evidence with the current state. Keep the word-count check before the draft append in a real command. Append any goal events in that same command, each with its own `date -Is` value. If a paragraph is split, finish the first command, append its `evaluate` event, then run the second command.

    Every `evaluate` event means a `process_switch` whose `process` is `evaluate`. Append it only after the paragraph exists. Its `evidence` array must contain the opening phrase of the paragraph just appended, copied verbatim with punctuation and case unchanged. Read the phrase back from `.writing/draft.md` in the same shell command; never retype or paraphrase it. Check mechanically that the quote is a substring of that paragraph. A `revise` switch must identify the most recent passage it changes.

    For example, read back the last appended paragraph with `tail` and `head`, take its opening eight words, check the substring, and append the evaluate event from `$quote` in that same shell command:

    ```sh
    paragraph=$(tail -n 2 .writing/draft.md | head -n 1)
    quote=$(printf '%s\n' "$paragraph" | awk '{for (i=1; i<=8 && i<=NF; i++) printf "%s%s", $i, (i<8 && i<NF ? OFS : ORS)}')
    case "$paragraph" in *"$quote"*) ;; *) exit 1 ;; esac
    stamp=$(date -Is)
    printf '%s\n' "{\"timestamp\":\"$stamp\",\"event_type\":\"process_switch\",\"responsible_agent\":\"Monitor\",\"process\":\"evaluate\",\"decision\":\"Evaluate the appended paragraph.\",\"evidence\":[\"$quote\"],\"open_uncertainty\":[],\"from_process\":\"translating\",\"to_process\":\"evaluate\"}" >> .writing/trace/process.jsonl
    ```

    ## Processes and trace events

    The exact process tokens are `planning`, `generate`, `organize`, `goal-setting`, `translating`, `reviewing`, `evaluate`, and `revise`. Use only these tokens in JSON. No other process token is allowed, including `evaluating`, `generating`, `organizing`, or `revising`.

    Every event has `timestamp`, `event_type`, `responsible_agent`, `process`, `decision`, `evidence`, and `open_uncertainty`. `event_type` is always exactly one of `process_switch`, `goal_created`, `goal_developed`, or `goal_regenerated`; never put a process token such as `evaluate` or `translating` in `event_type`. The first five fields are strings, and `evidence` and `open_uncertainty` are JSON arrays of strings. A `process_switch` also has `from_process` and `to_process`, each a declared process token or `null`. `evaluate`, `translating`, and every other declared process token may appear only in `process`, `from_process`, or `to_process`. A goal event also has string `goal_id` and string-or-null `parent_goal_id`. Keep the shared trace contract unchanged.

    For `goal_created`, set `parent_goal_id` to the immediate parent. For `goal_developed`, retain the goal's current parent. For `goal_regenerated`, use the replacement ID as `goal_id` and the superseded ID as `parent_goal_id`. Record the reason in `decision` and concrete support in `evidence`. Use an empty `open_uncertainty` array when no uncertainty remains.

    Use these shell forms when there is nothing to cite. Assign `stamp` in the same command before appending the line; never copy a timestamp from an example:

    ```sh
    stamp=$(date -Is)
    printf '%s\n' "{\"timestamp\":\"$stamp\",\"event_type\":\"process_switch\",\"responsible_agent\":\"Monitor\",\"process\":\"evaluate\",\"decision\":\"Evaluate the appended paragraph.\",\"evidence\":[],\"open_uncertainty\":[],\"from_process\":\"translating\",\"to_process\":\"evaluate\"}" >> .writing/trace/process.jsonl
    printf '%s\n' "{\"timestamp\":\"$stamp\",\"event_type\":\"goal_created\",\"responsible_agent\":\"Writer\",\"process\":\"goal-setting\",\"decision\":\"Create the next middle-range goal.\",\"evidence\":[],\"open_uncertainty\":[],\"goal_id\":\"G1\",\"parent_goal_id\":null}" >> .writing/trace/process.jsonl
    ```

    Every shell command that appends one or more trace lines must execute `stamp=$(date -Is)` in that same command before its first trace append and interpolate `$stamp` into every line in that command. The next command must execute `date -Is` again; never type, estimate, copy, or reuse a timestamp across commands. Append to `.writing/trace/process.jsonl`; never rewrite or truncate it. Use one shell command and one quoted heredoc for a related event batch when practical. Each line remains one standalone JSON object. Append one `process_switch` for each process switch, with the first `from_process` set to `null`. Keep process names lowercase in JSON. Do not invent fields or reuse an old timestamp. Read back the appended lines when the command permits and repair malformed JSON before continuing.

    For the sequence of `process_switch` events, the first `from_process` is `null`. Every later `from_process` must equal the immediately preceding `process_switch` event's `to_process`. Goal events do not reset this chain. Before finishing, compare the `from_process` and `to_process` values mechanically in trace order. Do not append a final `reviewing` switch with a stale source.

    The continuity check has this shape:

    ```python
    switches = [e for e in events if e["event_type"] == "process_switch"]
    assert switches[0]["from_process"] is None
    assert all(a["to_process"] == b["from_process"] for a, b in zip(switches, switches[1:]))
    ```

    ## Local checks

    Before each local passage, check the active goal and the text already written. After each append, check the new draft tail and the appended JSON lines. Confirm mechanically that each `evaluate` quote is a substring of the paragraph it evaluates and was read back from the draft. Confirm that each goal update has its required identifiers. Confirm that the current network contains no history table. Confirm that no process switch implies a fixed stage order.

    ## Review and finish

    Review each new passage against its active content goal, process goal, rhetorical problem, audience, purpose, and text already written. Use `generate` or `planning` for a missing idea, `goal-setting` for a more specific path, `reviewing` to read the growing text, and `revise` for a local wording change. Use `goal_developed` when the goal's purpose stays stable but becomes specific. Use `goal_regenerated` when writing changes its purpose or abstraction level. Use the current text as evidence about what comes next, but keep higher-level goals visible. Do not make a section boundary a process boundary or wait for a complete outline before translating.

    Before the final response, read `.writing/draft.md` and return exactly its complete contents, with no summary, link, preamble, or code fence. Keep assumptions in `.writing/assumptions.md`, not in the draft. Check that every current network change has its trace event, every trace line is standalone JSON, every process value is declared above, and no subagent was spawned.

    [^1]: Linda Flower and John R. Hayes. "A Cognitive Process Theory of Writing." College Composition and Communication 32(4), 1981, pp. 365-387. DOI: [10.58680/ccc198115885](https://doi.org/10.58680/ccc198115885) / JSTOR: [https://www.jstor.org/stable/356600](https://www.jstor.org/stable/356600)

**`Single-context`**

    ---
    name: cognitive-writing-single-context
    description: Use this skill for exploratory A8 comparisons. It keeps the Agentic CogWriter Monitor loop, shared writing state, and trace contract, but the host agent performs each selected process in its own context instead of delegating.
    ---

    # Cognitive writing single context

    Use this skill in the user's writing project. The project root is the current working directory unless the user names another project.

    The `Monitor` is the main agent running this skill. The `Monitor` chooses the next writing process from the project state and open uncertainty. The `Monitor` does not impose a fixed stage sequence.

    ## `Monitor` responsibilities

    - Keep these under the user's control:
      - rhetorical intent
      - factual authority
      - final wording
      - publication decision
    - Coordinate process switches as the main agent. Record the evidence for each switch and ask the user when a choice materially changes the rhetorical problem or a claim.
    - Perform the selected process in the host agent's own context. Do not delegate it to a role agent or subagent.
    - Re-read the changed state and reconcile the selected process with the active goal. Tell the user about proposals that affect intent, factual claims, or a major goal. Let the user override any agent decision.

    ## Start by establishing the writing state

    1. Treat these files as the project's externalized task environment and long-term memory. Create missing files and directories without overwriting existing user content:

       ```text
       .writing/
       ├── assignment.md       # topic, audience, exigency, and writer's goals
       ├── goals.md            # hierarchical goals and creation/development history
       ├── draft.md            # the growing text
       ├── memory/             # topic knowledge, audience knowledge, and writing plans
       └── trace/              # structured process history, one JSON object per line
       ```

    2. Read these before choosing an operation:

       - `.writing/assignment.md`
       - `.writing/goals.md`
       - `.writing/draft.md`
       - relevant files in `.writing/memory/`
       - the latest entries in `.writing/trace/process.jsonl`

       If `.writing/assignment.md` is missing or underspecified, ask the user for:

       - topic
       - audience
       - exigency
       - writer's goals
       - genre
       - constraints

       Do not silently invent a rhetorical problem.

    3. Keep `goals.md` in the notation described in [`references/goals-format.md`](references/goals-format.md). Update it whenever a goal is created, developed, or regenerated. Preserve the history instead of replacing an earlier goal without recording what changed.
    4. Read [`references/trace-jsonl-schema.md`](references/trace-jsonl-schema.md) before writing the first trace entry. Append to `.writing/trace/process.jsonl`; never rewrite or truncate that log.

    ## `Monitor` loop

    At each turn, the `Monitor` should:

    1. Identify the active goal and its parent. If a sub-goal resolves, pop back to the parent goal before choosing the next operation.
    2. Compare the active goal with:

       - the rhetorical problem
       - the current draft
       - retrieved memory
       - open uncertainty

       Use that comparison to select `Planning`, `Translating`, or `Reviewing`. `Planning` may mean:

       - exploring
       - organizing
       - setting a goal

       `Reviewing` may mean:

       - evaluating
       - revising

    3. Before every process switch, append a `process_switch` event naming the responsible process or agent and recording the decision, evidence, and open uncertainty. Record a separate goal event whenever a goal is created, developed, or regenerated. Use the exact fields in the trace reference.
    4. Perform the selected process in the host agent's own context, following the role-skill instructions and brief described in In-context process execution. Do not spawn a role agent or subagent.
    5. Re-read the changed state and reconcile the selected process with the active goal. Treat `Reviewing` verdicts as proposals. Record `goal_developed` only when the Monitor updates that goal and adds its `goals.md` history row; otherwise record an unacted-on `develop` verdict as a disposition without a goal event. For every `regenerate` verdict, either accept it or reject it. On acceptance, update `goals.md` with a history row that keeps the original goal ID marked `superseded` and gives the replacement a new goal ID, and emit `goal_regenerated` with the replacement's `goal_id` and the original goal's `parent_goal_id`; on rejection, write `rejected regeneration of <goal id>: <reason>` in the next `process_switch` decision. The next `process_switch` decision after a `Reviewing` pass must enumerate every received `regenerate` verdict as `regeneration proposals: G2 accepted (<reason>); G4 rejected (<reason>)`, substituting the actual goal IDs and reasons, or `regeneration proposals: none` when no `regenerate` verdict was received. Append that post-`Reviewing` `process_switch` carrying the enumeration before either continuing or completing the run. If the run continues, set its `to_process` to the next process. If the run ends after `Reviewing`, set its `process` and `from_process` to `reviewing` and its `to_process` to `null` before completing the run. After every Translating pass, compare the new draft with every active goal in goals.md, then record a goal_developed or goal_regenerated event for each goal the draft changed, or state in the next process_switch decision that the goal network needed no change and why. Update the appropriate project state:

       - `goals.md`
       - `draft.md`
       - `memory/`

       Keep user-authored text and uncertain claims visible rather than silently normalizing them.

    6. Tell the user:

       - what changed
       - which goal is active
       - what remains uncertain
       - which process the `Monitor` recommends next

       Ask for a decision when the next move depends on the user's intent or factual authority.

    Before sending the final response, complete this non-skippable checklist:

    1. The complete current document is written to `.writing/draft.md`.
    2. The trace holds one goal event (`goal_created`, `goal_developed`, or `goal_regenerated`) for every goal recorded in `goals.md` during this run.
    3. The final response contains the complete final text.

    The run is `INVALID` unless `.writing/draft.md` exists before the final response and the final response contains the complete final text. The final response cannot substitute for the required draft.

    ## Non-linear control rules

    The writing processes form a recursive loop, not a pipeline. A process may call another process to solve a local problem, and that process may call the whole loop again.

    Generate and Evaluate may interrupt any process when new information or a conflict in the growing text demands it. Log the interruption as a process switch, then resume the interrupted parent goal after the sub-goal resolves.

    When new writing changes what the author understands, use Goal-setting to develop or regenerate the goal network. A regenerated goal is not a failure of the earlier plan; it is part of learning through composing. Keep both the prior record and the new rationale in `goals.md` and the trace.

    ## In-context process execution

    Perform every selected process in the host agent's own context. Before working, read and apply the selected role's skill instructions from `plugin/skills/planning/SKILL.md`, `plugin/skills/translating/SKILL.md`, or `plugin/skills/reviewing/SKILL.md` exactly as a delegated role agent would. Preserve the project root, active goal context, relevant uncertainty, and requested output while working. Use the same process brief as A4: provide the project root, the current goal context (for `Reviewing`, every active goal with its ID plus the parent goal ID; otherwise the active and parent goal IDs), relevant uncertainty, and requested output. Cite the files or draft passages that support decisions. Do not spawn a role agent, subagent, or child `codex exec` process.

    ## Trace contract

    Every process switch and every goal creation, development, or regeneration must append one valid JSON object to `.writing/trace/process.jsonl`. A process-switch object includes `timestamp`, `event_type`, `responsible_agent`, `process`, `decision`, `evidence`, `open_uncertainty`, `from_process`, and `to_process`. A goal event also includes `goal_id` and `parent_goal_id`. Optional `artifacts` lists project-relative files. In the JSON object, `timestamp`, `event_type`, `responsible_agent`, `process`, and `decision` are strings; `evidence` and `open_uncertainty` are arrays of strings; `from_process` and `to_process` are strings or `null`; `goal_id` is a string; `parent_goal_id` is a string or `null`; and `artifacts`, when present, is an array of project-relative path strings; set `timestamp` to the current wall-clock time obtained from the shell at write time, for example `date -Is`, and never copy example timestamps. Keep the code-formatted role names `Planning`, `Translating`, and `Reviewing` in surrounding prose, but write JSON `process`, `from_process`, and `to_process` values with the lowercase contract tokens `planning`, `translating`, and `reviewing`. Do not add experiment-specific fields to the shared trace contract. For example:

    ```json
    {
      "timestamp": "2026-01-15T09:00:00+09:00",
      "event_type": "process_switch",
      "responsible_agent": "monitor",
      "process": "planning",
      "decision": "Choose planning for the active goal and current uncertainty.",
      "evidence": [".writing/assignment.md", ".writing/goals.md"],
      "open_uncertainty": [
        "The audience's highest-priority concern is not yet known."
      ],
      "from_process": null,
      "to_process": "planning",
      "artifacts": [".writing/goals.md"]
    }
    ```

    ## References

    Read these only when the corresponding operation needs them:

    - [`references/trace-jsonl-schema.md`](references/trace-jsonl-schema.md) defines the trace fields and event types.
    - [`references/goals-format.md`](references/goals-format.md) defines hierarchical goal notation and history records.

### Evaluation Prompts

##### Benchmark-native evaluation.

WritingBench retains five query-specific criteria for each prompt; the evaluator scores each criterion from 1 to 10 and the native score is their unweighted mean. HelloBench retains 5–7 checklist items per prompt; the evaluator scores each item on its five-level scale and the native score is the item mean. DoLoMiTes has no analogous per-prompt native rubric in our committed evaluation, so we report only the common pointwise rubric for that benchmark. Published leaderboard values should not be compared directly with these scores because we use a shared evaluator and our own generated outputs.

**Common Pointwise Rubric**

    <!--
    Agentic CogWriter pointwise judge prompt
    Version: pointwise-v1
    Protocol source: docs/experiments/protocol.md, descriptive pointwise quality
    FastChat source path: fastchat/llm_judge/data/judge_prompts.jsonl
    FastChat source sha256: fd283293406d024f44c174b094ef48031d0687a4682fd3a56b29b138f80281b6
    FastChat adaptation: single-v1 neutral-judge framing only; the five-dimension rubric is protocol-defined.
    -->
    Please act as an impartial judge of one writing response. Judge the response against the assignment and the supplied context. Do not reward outside research or facts that are not supported by the assignment or supplied context. Judge the response itself, not its condition label, length, or any hidden process.

    Return exactly one valid JSON object. Do not use Markdown fences or add explanation outside the JSON object.
    Return the literal `runtime-verified` marker for `judge_family`; the judge engine in `experiments/src/agentic_cogwriter/judges/engine.py` replaces that marker with the serving response's mapped family before the scorer writes the protocol record.

    Use the five dimensions below. Return an integer from 1 to 5 for every dimension. Scores 2 and 4 are allowed when the response falls between the anchors.

    | Dimension | Score 1 | Score 3 | Score 5 |
    | --- | --- | --- | --- |
    | Instruction fulfillment | Misses the central task or constraints. | Completes the main task but misses material requirements. | Meets the task and all material constraints. |
    | Organization and global coherence | Ideas or sections do not form a usable whole. | The response is readable but has visible structural gaps. | The response has a clear structure and sustained global coherence. |
    | Content adequacy and depth | Content is missing, shallow, or unusable for the task. | Content covers the main points with uneven development. | Content is sufficient, developed, and appropriately deep. |
    | Style, voice, and audience fit | Style or voice conflicts with the requested audience or genre. | Style is partly suitable but inconsistent. | Voice, style, and detail fit the audience and genre throughout. |
    | Factuality and constraint fidelity | The response contradicts the supplied context or violates important constraints. | Minor errors or unsupported claims remain. | Claims fit the supplied context, uncertainty is handled honestly, and constraints are obeyed. |

    Copy one short exact evidence quote for each dimension from the response or supplied context. Keep every quote verbatim and no longer than needed to identify the evidence. The final dimension must be judged against the assignment and supplied context. Set judge_level_composite to 0.0 because the scorer computes composites after collecting all outputs. Put any uncertainty in uncertainties, or return an empty array.

    [Prompt ID]
    {prompt_id}

    [Blind condition ID]
    {condition_id}

    [Platform]
    {platform}

    [Assignment]
    {assignment}

    [Supplied context]
    {context}

    [Output]
    {output}

    Return this JSON shape with the metadata values unchanged:
    {{
      "prompt_id": "{prompt_id}",
      "condition_id": "{condition_id}",
      "platform": "{platform}",
      "judge_id": "{judge_id}",
      "judge_family": "{judge_family}",
      "scores": {{
        "instruction_fulfillment": 1,
        "organization_global_coherence": 1,
        "content_adequacy_depth": 1,
        "style_voice_audience_fit": 1,
        "factuality_constraint_fidelity": 1
      }},
      "evidence_quotes": [
        {{"dimension": "instruction_fulfillment", "quote": "<short exact quote>"}},
        {{"dimension": "organization_global_coherence", "quote": "<short exact quote>"}},
        {{"dimension": "content_adequacy_depth", "quote": "<short exact quote>"}},
        {{"dimension": "style_voice_audience_fit", "quote": "<short exact quote>"}},
        {{"dimension": "factuality_constraint_fidelity", "quote": "<short exact quote>"}}
      ],
      "judge_level_composite": 0.0,
      "uncertainties": []
    }}

**Pairwise Comparison**

    <!--
    Agentic CogWriter pairwise judge prompt
    Version: pairwise-v1
    Protocol source: docs/experiments/protocol.md, Balanced pairwise tournament
    FastChat source path: fastchat/llm_judge/data/judge_prompts.jsonl
    FastChat source sha256: fd283293406d024f44c174b094ef48031d0687a4682fd3a56b29b138f80281b6
    FastChat adaptation: pair-v2 position-bias and length-bias controls, adapted to the protocol JSON contract.
    -->
    Please act as an impartial judge comparing two writing responses to the assignment. Choose the response that follows the assignment and answers it better. Consider instruction fulfillment, organization and global coherence, content adequacy and depth, style, voice and audience fit, and factuality and constraint fidelity.

    Compare both responses before deciding. Avoid position bias. The order in which the responses appear must not influence the decision. Do not let response length influence the decision. Do not favor a response because of a name or label. Judge only the assignment and supplied context. Do not reward outside research or facts that are not supported by the assignment or supplied context.

    Return exactly one valid JSON object. Do not use Markdown fences or add explanation outside the JSON object. Choose winner A, B, or tie. Include at least one short exact evidence quote for each response. Each quote must be copied verbatim from the displayed response for that letter or the supplied context. Do not quote the assignment or any other prompt text. Keep every quote no longer than needed to identify the evidence. Write a brief comparison grounded in the rubric.
    Return the literal `runtime-verified` marker for `judge_family`; the judge engine in `experiments/src/agentic_cogwriter/judges/engine.py` replaces that marker with the serving response's mapped family before the scorer writes the protocol record.

    [Prompt ID]
    {prompt_id}

    [Opaque pair ID]
    {pair_id}

    [Derived presentation order]
    {presentation}

    [Assignment]
    {assignment}

    [Supplied context]
    {context}

    [Start of response A]
    {answer_a}
    [End of response A]

    [Start of response B]
    {answer_b}
    [End of response B]

    Return this JSON shape with the metadata values unchanged:
    {{
      "prompt_id": "{prompt_id}",
      "platform": "{platform}",
      "judge_id": "{judge_id}",
      "judge_family": "{judge_family}",
      "pair_id": "{pair_id}",
      "presentation": "{presentation}",
      "winner": "tie",
      "evidence_quotes": {{
        "A": ["<short exact quote from response A or supplied context>"],
        "B": ["<short exact quote from response B or supplied context>"]
      }},
      "reason": "<brief comparison grounded in the rubric>"
    }}

**WritingBench-Native Evaluation**

    <!--
    Agentic CogWriter WritingBench-native pointwise judge prompt
    Version: writingbench-native-v1
    Upstream source path: X-PLUG/WritingBench/benchmark_query/benchmark_all.jsonl
    Upstream source commit: 9c24bb67fd7451a2eacf5810aa7721e3a8b3bdad
    Native checklist blob: e6cd82aabed6fa845f0a28cd2114daad59c012b9
    Upstream critic source: writingbench-prompt.py, sha256:d4d9273bbf037752871056c39e3404a8e900fe8b380c795949b111f67a2e2133
    Upstream user template: user_template.txt, sha256:6eb2f31c4e6e9043eadc68e266b49140282f2150cb689d9c403a7b94c7c91413
    Upstream system line: You are an expert evaluator with extensive experience in evaluating response of given query.
    Cache adaptation: query and response precede the checklist; the reordered text is content-identical to the upstream critic template.
    -->
    Evaluate the Response based on the Query and criteria provided.

    ** Query **
    ```{query}```

    ** Response **
    ```{response}```

    Provide your evaluation based on the criteria:

    Provide reasons for each score, indicating where and why any strengths or deficiencies occur within the Response. Reference specific passages or elements from the text to support your justification.
    Ensure that each reason is concrete, with explicit references to the text that aligns with the criteria requirements.

    ** Criteria **
    ```{criteria}```

    Provide your evaluation based on the criteria:

    ```{criteria}```

    Scoring Range: Assign an integer score between 1 to 10

    ** Output format **
    Return the results in the following JSON format, Only output this JSON format and nothing else:
    ```json
    {{
        "score": an integer score between 1 to 10,
        "reason": "Specific and detailed justification for the score using text elements."
    }}
    ```

**HelloBench-Native Evaluation**

    <!--
    Agentic CogWriter HelloBench-native checklist judge prompt
    Version: hellobench-native-v1
    Upstream repository: Quehry/HelloBench
    Upstream source commit: 92c7d469230b5b6b6ee1bfc1ea2ce49cb9125b57
    Upstream judge script: llm_judge.py
    Upstream judge script sha256: 1434ba32c15ab33f21ea65cb08e0111ac47e2bdb2e6816dacd61f0365e6ff5dd
    Upstream system line: You are a helpful evaluator. Your task is to evaluate the checklists of the responses given by the Large Language Models (LLMs) based on user instructions. These checklists consist of yes or no questions.
    Parse adaptation: structured JSON output replaces upstream's eval() of a Python list; prompt body bytes are unchanged.
    Upstream USER_PROMPT EOF: no final newline
    Request policy: HelloBench uses exactly one judge request per run, so no prompt-cache reordering applies.
    -->

    Your core task is to evaluate the checklists based on the user's instruction and LLM's response, with each checklist item being a yes or no question indicating a specific aspect that the LLM's response should meet. You need to judge the checklist item based on the instruction and response. The evaluation results are scored from 0 to 1, with 5 scores in total, which are:

    0: The response fails to meet the checklist requirements, demonstrating substantial need for improvement across multiple areas.
    0.25: The response partially meets some checklist requirements, but significant elements remain unaddressed.
    0.5: The response meets several checklist requirements, yet the overall evaluation appears ambiguous or unclear.
    0.75: The response aligns with most checklist requirements, though there are still minor areas that could be refined or enhanced.
    1: The response fully satisfies all checklist requirements, with no identifiable issues or areas for improvement. It means this response is already perfect; you can't find any significant flaws in it.

    Here is the instruction:
    {{"instruction": {instruction}}}

    Here is the response given by LLM:
    {{"response": {response}}}

    Since the response may be rather long, I am specifically reminding you here that the response has ended.

    Here are checklists of this instruction:
    {{"checklists": {checklists}}}

    To further remind you, I will repeat my requirements:

    Your core task is to evaluate the checklists based on the user's instruction and LLM's response, with each checklist item being a yes or no question indicating a specific aspect that the LLM's response should meet. You need to judge the checklist item based on the instruction and response. The evaluation results are scored from 0 to 1, with 5 scores in total, which are:

    0: The response fails to meet the checklist requirements, demonstrating substantial need for improvement across multiple areas.
    0.25: The response partially meets some checklist requirements, but significant elements remain unaddressed.
    0.5: The response meets several checklist requirements, yet the overall evaluation appears ambiguous or unclear.
    0.75: The response aligns with most checklist requirements, though there are still minor areas that could be refined or enhanced.
    1: The response fully satisfies all checklist requirements, with no identifiable issues or areas for improvement. It means this response is already perfect; you can't find any significant flaws in it.

    Always provide the reason for your evaluation results. You should be strict but fair in your evaluation. A score of 1 means that the response perfectly meets all the checklist requirements and you think there are really no room for improvements. When giving a score of 1, you need to carefully consider whether this checklist has been perfectly satisfied.

    Evaluate all the checklists and return the evaluation results of the checklists. Output a Python List consisting of the Python Dictionary formatted as follows:
    [{{"checklist_id": "the id of the checklist", "reason": "The reason for your evaluation results", "evaluation_score": "Your evaluation score for this checklist"}},{{"checklist_id": "the id of the checklist", "reason": "The reason for your evaluation results", "evaluation_score": "Your evaluation score for this checklist"}}]

    There are total {num_checklist} checklists that you need to evaluate. The length of the output list is equal to the number of checklists and you should give an evaluation score for each checklist. You should be strict to the evaluation to further compare the responses from different models. Your response must be a valid Python List and should contain nothing else, as it will be directly executed in Python.

## Runtime Configuration

Table 8 reports the runtime controls shared across conditions. We hold the generator, output-token budget, network and retrieval policy, approval policy, task input, and final-output requirements fixed so that the compared conditions differ in how they organize the writing process rather than in model access or external information. Each prompt–condition pair is generated in three runs. Primary pairwise evaluation uses the same judge for every condition, presents each pair in both orders, and records presentation disagreements as ties; the cross-family judge is used only for the separate robustness analysis.

##### Runtime lock and isolation.

The runtime was designed to isolate writing-process organization rather than information access or host configuration. Before a scored run, the runner requires explicit model, decoding, budget, timeout, seed, version, plugin-commit, retry, and statistical settings; unresolved values stop execution before a model process is created. Conditions share the same assignment and supplied context, resource limits, and tool policy, while web search, network access, external retrieval, and unprovided sources are disabled. Per-run provider configuration is also isolated from local guidance, and retries reuse the same prompt and policy rather than adding information or budget. These controls implement the study’s equal-information policy and reduce hidden runtime state as a source of condition differences.

##### Model roles.

The study uses `gpt-5.6-luna` for generation because the experiment requires high-volume long-form generation across many systems, prompts, and replications; the model is positioned for fast, cost-sensitive workloads within the GPT-5.6 family (OpenAI, 2026b; OpenAI, 2026a). `gpt-5.6-sol` is used as the higher-capability primary evaluator, consistent with its positioning for more demanding professional work (OpenAI, 2026c; OpenAI, 2026a). Medium reasoning effort is held fixed rather than tuned within the reported study. For the primary judge, the first main run inherited the documented medium default, and later runs pin medium explicitly to reproduce the same reasoning level.

##### Evaluation controls.

Pairwise outputs are blinded and judged in both presentation orders to reduce known position bias in LLM evaluation (Zheng et al., 2023; Wang et al., 2024a). The two orders are treated as repeated measurements of one prompt-level comparison rather than independent samples: a semantic winner is retained only when both orders agree, and any disagreement becomes a tie. The reported primary judge and generator are both from the GPT-5.6 family, which differs from the planned different-family judge design. We therefore report `claude-sonnet-5 medium` separately as a cross-family robustness check rather than pooling it with the confirmatory judge, given evidence that model-family relationships can affect evaluator preferences (Panickssery et al., 2024).

##### Frozen operational values.

Three independent generation runs define the replication dimension of the pre-specified confirmatory analysis, but the study record gives no additional optimization rationale for choosing exactly three. The 64,000-token generator output budget, primary-judge seed, and two-retry judge policy are likewise frozen operational settings rather than values selected by a documented tuning sweep. Generator temperature is reported as unset because the scored generation interface did not expose that control; unsupported generation controls were monitored rather than varied across conditions. Reporting these values makes the execution reproducible without attributing post-hoc rationales that were not part of the recorded design.

|                               |                             |
|:------------------------------|:----------------------------|
| **Setting**                   | **Value**                   |
| Generator                     | `gpt-5.6-luna medium`       |
| Primary pairwise judge        | `gpt-5.6-sol medium`        |
| Cross-family judge            | `claude-sonnet-5 medium`    |
| Generation runs               | 3 per prompt–condition pair |
| Generator output-token budget | 64,000                      |
| Generator temperature         | unset                       |
| Network access                | denied                      |
| Web search                    | disabled                    |
| Approval policy               | never                       |
| External retrieval            | disabled for all conditions |
| Primary judge seed            | 20260908                    |
| Primary judge retries         | 2                           |
| Pairwise presentation         | both orders                 |
| Presentation disagreement     | counted as tie              |

Table 8. Frozen runtime and evaluation settings used for the reported runs.

## Generation-Run-Level Pairwise Outcomes

The following figure shows the prompt-level pairwise estimates for each benchmark and generation run, including the ablation contrasts. For <span class="smallcaps">Agentic CogWriter</span> versus `Single-pass`, the descriptive mean win rates across generation runs are 72% on DoLoMiTes, 85.7% on HelloBench, and 84.3% on WritingBench.

Figure 3. Run-level pairwise estimates separate the large system comparisons from the ablations. <span class="smallcaps">Agentic CogWriter</span> is consistently favored over `Single-pass` and `Task-planning` and usually over `Staged`, whereas `No-goals` and `Fixed-order` remain near parity and do not survive the within-benchmark Holm correction. Points show 95% Wilson intervals; filled circles survive correction, open circles do not, and diamonds are descriptive means across generation runs.

## Paired Document-Quality Differences

Table 9 reports paired differences behind Table 3 Each prompt’s three generation runs are averaged per system before differencing, so the prompt is the resampling unit, and the intervals come from 10,000 prompt-level bootstrap resamples.

|  |  |  |  |  |  |
|:---|---:|---:|---:|---:|---:|
|  | **WritingBench** | **WritingBench** | **HelloBench** | **HelloBench** | **DoLoMiTes** |
| **vs.** | **Native** | **Pointwise** | **Native** | **Pointwise** | **Pointwise** |
| `Single-pass` | +0.050 \[+0.039, +0.061\] | +0.190 \[+0.114, +0.267\] | +0.018 \[+0.012, +0.024\] | +0.124 \[+0.032, +0.228\] | +0.036 \[-0.022, +0.095\] |
| `Staged` | +0.045 \[+0.034, +0.057\] | +0.141 \[+0.061, +0.223\] | +0.010 \[+0.003, +0.016\] | +0.008 \[-0.094, +0.131\] | -0.033 \[-0.100, +0.035\] |
| `Task-planning` | +0.026 \[+0.019, +0.034\] | +0.127 \[+0.048, +0.209\] | +0.011 \[+0.005, +0.016\] | +0.043 \[-0.057, +0.157\] | +0.206 \[+0.130, +0.281\] |

Table 9. Paired differences in document quality, <span class="smallcaps">Agentic CogWriter</span> minus the compared system, with 95% bootstrap intervals in brackets. Each prompt’s three generation runs are averaged per system before differencing, and prompts are resampled 10,000 times; positive values favor <span class="smallcaps">Agentic CogWriter</span>, and intervals that exclude zero indicate a difference beyond prompt-level sampling variation.

## Additional Process and Resource Statistics

Table 10 reports completion, output size, delegated invocations, goal events, token accounting, and wall-clock time from the first generation run. For <span class="smallcaps">Agentic CogWriter</span>, that run uses 13,374 output-plus-reasoning tokens and 46,860 uncached input tokens per attempted run and records 1 accepted goal regeneration. Across the three generation runs, the trace summaries contain mean totals of 1,101.3 goal-creation events and 1,915.3 goal-development events, while the post-`Reviewing` ledger contains 353.7 entries including 3.7 explicit regeneration proposals.

|  |  |  |  |  |  |  |  |
|:---|---:|---:|---:|---:|---:|---:|---:|
| **Condition** | **Completed** | **Median**; **units** | **Spawns**; **/run** | **Goals created**; **developed/regenerated** | **Output**; **tokens**; **/run** | **Input**; **tokens**; **/run** | **Mean sec.**; **/completed run** |
| `Single-pass` | 289/300 | 1,654 | 0 | 0/0/0 | 4,874 | 13,263 | 61 |
| `Staged` | 300/300 | 1,510 | 0 | 0/0/0 | 10,728 | 21,822 | 77 |
| `Task-planning` | 292/300 | 1,702 | 8.09 | 0/0/0 | 17,851 | 62,871 | 298 |
| <span class="smallcaps">Agentic CogWriter</span> | 293/300 | 1,835 | 3.22 | 1,068/1,864/1 | 13,374 | 46,860 | 426 |
| `No-goals` | 294/300 | 1,762 | 3.04 | 0/0/0 | 9,788 | 39,317 | 345 |
| `Fixed-order` | 282/300 | 1,773 | 3.43 | 267/1,163/3 | 11,402 | 42,888 | 219 |
| `Single-writer` | 280/300 | 1,111 | 0 | 1,621/169/1 | 15,356 | 30,715 | 103 |

Table 10. Realized process and resource use in the first generation run. The systems differ substantially in delegated invocations and token use in addition to their control logic, while accepted goal regeneration is rare. These realized differences motivate the output-length and compute-matched sensitivity analyses rather than treating raw resource use as a controlled mechanism.

## Sensitivity Analyses

### Record-Pooled Sensitivity

Table 11 reports a sensitivity analysis that treats the two presentation records for each prompt as independent observations; the retained disagreements show how much presentation order can affect the descriptive rates. The retained presentation disagreements were 22.7% on WritingBench, 29.4% on HelloBench, and 21.4% on DoLoMiTes across the three generation runs.

|  |  |  |  |  |
|:---|---:|---:|---:|---:|
| **Contrast** | **WritingBench** | **HelloBench** | **DoLoMiTes** | **Across benchmarks** |
| <span class="smallcaps">Agentic CogWriter</span> vs `Single-pass` | 79.4% (0.8%) | 81.1% (1.2%) | 68.9% (6.2%) | 76.6% (2%) |
| <span class="smallcaps">Agentic CogWriter</span> vs `Staged` | 74.6% (1.8%) | 59.9% (2.4%) | 54.7% (5.5%) | 63.6% (2.9%) |
| <span class="smallcaps">Agentic CogWriter</span> vs `Task-planning` | 61.9% (4.5%) | 59.5% (4.8%) | 72.5% (6.7%) | 64.7% (1.8%) |
| <span class="smallcaps">Agentic CogWriter</span> vs `No-goals` | 51.5% (3.8%) | 50.8% (1.6%) | 53.7% (5.7%) | 51.9% (0.6%) |
| <span class="smallcaps">Agentic CogWriter</span> vs `Fixed-order` | 55% (0.6%) | 53.9% (1.3%) | 53.4% (3.1%) | 54.1% (0.9%) |
| `Single-writer` vs `Single-pass` | 66.7% (5.2%) | 41.6% (4.3%) | 53.7% (7.5%) | 54.4% (2.3%) |
| `Single-writer` vs <span class="smallcaps">Agentic CogWriter</span> | 35.5% (2.1%) | 20.5% (1.4%) | 35.4% (3.3%) | 30.4% (2%) |
| `Single-writer` vs `No-goals` | 37.2% (3.3%) | 21.5% (4%) | 43% (7.1%) | 33.8% (2.5%) |

Table 11. Sensitivity analysis that treats the two presentation orders as separate records. The broad preference pattern remains similar, while presentation-order disagreements show why the headline analysis requires both orders to agree before retaining a winner. Values are mean win rates across generation runs with sample SD in parentheses; this analysis is descriptive.

### Output-Length Sensitivity

Table 12 reports pairwise outcomes by output-length ratio. The longer side wins 66.12% of 1647 non-tied comparisons. In the tighter pre-specified matching band, the outcomes from the first generation run for our system are 25/3/7 versus `Single-pass` (`p=2.74 x 10^-5`), 26/15/7 versus `Task-planning` (`p=0.1173`), and 18/18/20 versus `No-goals`. In the wider pre-specified band, the corresponding outcomes are 40/11/17 (`p=5.70 x 10^-5`), 39/18/14 (`p=0.0075`), and 38/30/37 (`p=0.3961`). These matching-band `p`-values are unadjusted descriptive sign-test results.

|                         |             |                               |
|:------------------------|------------:|------------------------------:|
| **Output-length ratio** |   **W/L/T** | **Longer-side**; **win rate** |
| 1.00–1.05               |  123/104/91 |                        54.19% |
| 1.05–1.10               |   116/67/92 |                        63.39% |
| 1.10–1.25               | 291/185/177 |                        61.13% |
| 1.25–1.50               | 277/120/141 |                        69.77% |
| 1.50–2.00               |   188/68/66 |                        73.44% |
| 2.00+                   |    94/14/23 |                        87.04% |

Table 12. Pairwise outcomes from the first generation run grouped by output-length ratio. Longer responses are favored overall, motivating the matched-length checks used to test whether the main system comparisons survive when output lengths are more similar. Here, W/L/T denotes wins/losses/ties for the longer response after applying the two-order consistency rule; ties are excluded from the longer-side win-rate denominator.

### Compute-Stratified Sensitivity

Compute matching asks whether the pairwise direction persists when the compared systems use similar realized output-plus-reasoning token budgets. Table 13 reports outcomes within the pre-specified 1.25`x` and 1.50`x` matching bands and across descriptive ratio bins. Because realized compute is determined by execution, this analysis is a sensitivity check rather than a causal adjustment.

|  |  |  |  |  |
|:---|:---|---:|---:|---:|
| Contrast | Band or bin | W/L/T | Rate | `p` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Staged` | within 1.25 | 197/66/98 | 74.9% | `2.55 x 10^-16` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Staged` | within 1.50 | 281/114/168 | 71.1% | `2.21 x 10^-17` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Task-planning` | within 1.25 | 163/63/78 | 72.1% | `2.14 x 10^-11` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Task-planning` | within 1.50 | 276/128/140 | 68.3% | `1.40 x 10^-13` |
| `Single-writer` vs. <span class="smallcaps">Agentic CogWriter</span> | within 1.25 | 87/267/83 | 24.6% | `2.13 x 10^-22` |
| `Single-writer` vs. <span class="smallcaps">Agentic CogWriter</span> | within 1.50 | 140/404/140 | 25.7% | `1.11 x 10^-30` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Single-pass` | within 1.25 | 0/0/0 |  | `1` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Single-pass` | within 1.50 | 13/6/3 | 68.4% | `0.1671` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Staged` | 0.00–0.50 | 1/0/0 | 100.0% | `1` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Staged` | 0.50–0.67 | 4/4/3 | 50.0% | `1` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Staged` | 0.67–0.80 | 13/12/12 | 52.0% | `1` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Staged` | 0.80–0.91 | 42/10/21 | 80.8% | `9.06 x 10^-6` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Staged` | 0.91–0.95 | 21/7/3 | 75.0% | `0.0125` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Staged` | 0.95–1.05 | 49/20/21 | 71.0% | `6.36 x 10^-4` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Staged` | 1.05–1.10 | 23/6/20 | 79.3% | `0.0023` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Staged` | 1.10–1.25 | 62/23/33 | 72.9% | `2.77 x 10^-5` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Staged` | 1.25–1.50 | 71/36/58 | 66.4% | `9.23 x 10^-4` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Staged` | 1.50–2.00 | 95/57/53 | 62.5% | `0.0026` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Staged` | 2.00+ | 38/29/39 | 56.7% | `0.3284` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Task-planning` | 0.00–0.50 | 44/26/23 | 62.9% | `0.0414` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Task-planning` | 0.50–0.67 | 119/48/55 | 71.3% | `3.83 x 10^-8` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Task-planning` | 0.67–0.80 | 99/58/54 | 63.1% | `0.0013` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Task-planning` | 0.80–0.91 | 69/25/34 | 73.4% | `6.34 x 10^-6` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Task-planning` | 0.91–0.95 | 22/11/11 | 66.7% | `0.0801` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Task-planning` | 0.95–1.05 | 33/16/16 | 67.3% | `0.0213` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Task-planning` | 1.05–1.10 | 13/5/5 | 72.2% | `0.0963` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Task-planning` | 1.10–1.25 | 26/6/12 | 81.2% | `5.35 x 10^-4` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Task-planning` | 1.25–1.50 | 14/7/8 | 66.7% | `0.1892` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Task-planning` | 1.50–2.00 | 7/3/5 | 70.0% | `0.3438` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Task-planning` | 2.00+ | 1/1/2 | 50.0% | `1` |
| `Single-writer` vs. <span class="smallcaps">Agentic CogWriter</span> | 0.00–0.50 | 1/5/0 | 16.7% | `0.2188` |
| `Single-writer` vs. <span class="smallcaps">Agentic CogWriter</span> | 0.50–0.67 | 9/12/9 | 42.9% | `0.6636` |
| `Single-writer` vs. <span class="smallcaps">Agentic CogWriter</span> | 0.67–0.80 | 15/43/20 | 25.9% | `3.07 x 10^-4` |
| `Single-writer` vs. <span class="smallcaps">Agentic CogWriter</span> | 0.80–0.91 | 19/62/17 | 23.5% | `1.77 x 10^-6` |
| `Single-writer` vs. <span class="smallcaps">Agentic CogWriter</span> | 0.91–0.95 | 12/20/8 | 37.5% | `0.2153` |
| `Single-writer` vs. <span class="smallcaps">Agentic CogWriter</span> | 0.95–1.05 | 25/69/22 | 26.6% | `6.34 x 10^-6` |
| `Single-writer` vs. <span class="smallcaps">Agentic CogWriter</span> | 1.05–1.10 | 8/39/9 | 17.0% | `5.54 x 10^-6` |
| `Single-writer` vs. <span class="smallcaps">Agentic CogWriter</span> | 1.10–1.25 | 23/77/27 | 23.0% | `5.51 x 10^-8` |
| `Single-writer` vs. <span class="smallcaps">Agentic CogWriter</span> | 1.25–1.50 | 38/94/37 | 28.8% | `1.19 x 10^-6` |
| `Single-writer` vs. <span class="smallcaps">Agentic CogWriter</span> | 1.50–2.00 | 24/68/25 | 26.1% | `4.94 x 10^-6` |
| `Single-writer` vs. <span class="smallcaps">Agentic CogWriter</span> | 2.00+ | 7/13/6 | 35.0% | `0.2632` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Single-pass` | 1.25–1.50 | 13/6/3 | 68.4% | `0.1671` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Single-pass` | 1.50–2.00 | 91/15/17 | 85.8% | `1.90 x 10^-14` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Single-pass` | 2.00+ | 464/114/150 | 80.3% | `4.90 x 10^-51` |

Table 13. Compute-matched pairwise outcomes. Within the tightest available 1.25`x` band, <span class="smallcaps">Agentic CogWriter</span> remains favored over `Staged` and `Task-planning`; no <span class="smallcaps">Agentic CogWriter</span>–`Single-pass` pairs fall in that band, so the same comparison cannot be made there. The remaining rows show descriptive compute-ratio bins; sign-test `p`-values are unadjusted and do not enter the confirmatory analysis.

### Single-Context Exploratory Check

The `Single-context` condition was added after the main results had been observed, to test whether the `Single-writer` loss reflects delegation to separate agents or the absence of process decomposition under a `Monitor`. We registered it as an exploratory condition outside the Holm family before judging and ran one generation run, the same evidence tier as the cross-family check: the question it answers is whether an attribution survives, not whether a new contrast is confirmed. We therefore report the combined estimate with its interval and the benchmark-level results without adjustment.

|  |  |  |  |  |  |  |
|:---|:---|---:|---:|---:|---:|:---|
| Contrast | Scope | `n` | Dropped | W/L/T | Rate | 95% Wilson / exact `p` |
| `Single-context` |  |  |  |  |  |  |
| vs. <span class="smallcaps">Agentic CogWriter</span> | WritingBench | 96 | 4 | 35/32/29 | 52.2% | 40.5%–63.7%; `0.8072` |
| `Single-context` |  |  |  |  |  |  |
| vs. <span class="smallcaps">Agentic CogWriter</span> | HelloBench | 99 | 1 | 19/35/45 | 35.2% | 23.8%–48.5%; `0.0402` |
| `Single-context` |  |  |  |  |  |  |
| vs. <span class="smallcaps">Agentic CogWriter</span> | DoLoMiTes | 98 | 2 | 37/34/27 | 52.1% | 40.7%–63.3%; `0.8126` |
| `Single-context` |  |  |  |  |  |  |
| vs. <span class="smallcaps">Agentic CogWriter</span> | Pooled | 293 | 7 | 91/101/101 | 47.4% | 40.5%–54.4%; `0.5161` |
| `Single-context` |  |  |  |  |  |  |
| vs. `Single-pass` | WritingBench | 100 | 0 | 79/8/13 | 90.8% | 82.9%–95.3%; `8.38 x 10^-16` |
| `Single-context` |  |  |  |  |  |  |
| vs. `Single-pass` | HelloBench | 94 | 6 | 42/14/38 | 75.0% | 62.3%–84.5%; `2.34 x 10^-4` |
| `Single-context` |  |  |  |  |  |  |
| vs. `Single-pass` | DoLoMiTes | 95 | 5 | 58/8/29 | 87.9% | 77.9%–93.7%; `1.80 x 10^-10` |
| `Single-context` |  |  |  |  |  |  |
| vs. `Single-pass` | Pooled | 289 | 11 | 179/30/80 | 85.6% | 80.2%–89.8%; `4.96 x 10^-27` |

Table 14. Exploratory comparison of `Single-context` with matched primary-condition outputs. In its single generation run, `Single-context` does not show a reliable difference from <span class="smallcaps">Agentic CogWriter</span>, so separate subagent contexts alone are not isolated as the source of the full system’s advantage. Wilson intervals are descriptive and sign-test `p`-values are unadjusted.

|  |  |  |  |
|:---|---:|---:|---:|
| Metric | `Single-pass` | <span class="smallcaps">Agentic CogWriter</span> | `Single-context` |
| Completed | 289/300 | 293/300 | 300/300 |
| Output-plus-reasoning tokens per run | 4,874 | 13,374 | 14,497 |
| Wall-clock seconds per completed run | 61 | 426 | 123 |
| Goals created/developed/regenerated | 0/0/0 | 1,068/1,864/1 | 1191/971/0 |
| Ledger entries | 0 | 347 | 321 |
| Ledger entries with proposal | 0 | 3 | 0 |
| Spawns per attempted run | 0 | 3.22 | 0 |

Table 15. Process and resource profiles for the matched `Single-pass`, <span class="smallcaps">Agentic CogWriter</span>, and `Single-context` runs. `Single-context` preserves the process loop and shared state without separate subagent contexts, making it a narrower execution check than `Single-writer`.

### Cross-Family Judge Robustness

Table 16 reports combined outcomes for three cross-family robustness contrasts involving our system: 67/44/171 versus `Single-pass`, 76/25/184 versus `Task-planning`, and 39/27/221 versus `No-goals`. The corresponding Wilson intervals are 51.06%–68.97%, 66.01%–82.64%, and 47.05%–70.13%. The judge yields a non-tied combined outcome on 32.6% of 854 eligible pairs, with 182/96/576 overall W/L/T; 395/854 prompt-level outcomes agree with the same-family judge.

|  |  |  |  |  |  |  |
|:---|:---|---:|---:|---:|---:|---:|
| **Contrast** | **Benchmark** | **`n`** | **W/L/T** | **Commit** | **Win rate** | **Agreement** |
| <span class="smallcaps">Agentic CogWriter</span> vs `Single-pass` | WritingBench | 96 | 19/21/56 | 41.67% | 47.50% | 31/96 |
| <span class="smallcaps">Agentic CogWriter</span> vs `Single-pass` | HelloBench | 93 | 15/10/68 | 26.88% | 60.00% | 39/93 |
| <span class="smallcaps">Agentic CogWriter</span> vs `Single-pass` | DoLoMiTes | 93 | 33/13/47 | 49.46% | 71.74% | 55/93 |
| <span class="smallcaps">Agentic CogWriter</span> vs `Task-planning` | WritingBench | 93 | 28/8/57 | 38.71% | 77.78% | 41/93 |
| <span class="smallcaps">Agentic CogWriter</span> vs `Task-planning` | HelloBench | 97 | 6/7/84 | 13.40% | 46.15% | 40/97 |
| <span class="smallcaps">Agentic CogWriter</span> vs `Task-planning` | DoLoMiTes | 95 | 42/10/43 | 54.74% | 80.77% | 56/95 |
| <span class="smallcaps">Agentic CogWriter</span> vs `No-goals` | WritingBench | 95 | 11/7/77 | 18.95% | 61.11% | 44/95 |
| <span class="smallcaps">Agentic CogWriter</span> vs `No-goals` | HelloBench | 96 | 4/5/87 | 9.38% | 44.44% | 43/96 |
| <span class="smallcaps">Agentic CogWriter</span> vs `No-goals` | DoLoMiTes | 96 | 24/15/57 | 40.62% | 61.54% | 46/96 |

Table 16. Cross-family judge robustness using `claude-sonnet-5 medium`. Changing judge family preserves the overall direction of the selected comparisons but produces more ties and reverses the WritingBench direction for <span class="smallcaps">Agentic CogWriter</span> versus `Single-pass`, so the exact win rates are judge-sensitive. Commit is the fraction of eligible pairs with a non-tied cross-family outcome; Agreement is the fraction whose combined outcome matches the primary judge.

## Consensus-Writing Evaluation on Habermas Machine Data

We additionally evaluate the writing systems on ten short consensus-writing tasks constructed from the Habermas Machine data (Tessler et al., 2024). Each task provides one deliberation question and the five participants’ original opinions, and asks the system to write a statement the group could endorse. The ten tasks are drawn from the `OOD_TEST` split after requiring complete, distinct participant opinions and disagreement ratings on both sides of the scale midpoint. Across eight conditions, this produces 80 attempted runs; 78 complete successfully. Table 17 summarizes pointwise quality and the available process statistics.

|  |  |  |  |  |  |
|:---|---:|---:|---:|---:|---:|
| **Condition** | **Created** | **Developed** | **Regenerated** | **Ledger (no/proposal)** | **Pointwise** |
| `Single-pass` | 0 | 0 | 0 | 0/0 | 0.1258 |
| `Staged` | 0 | 0 | 0 | 0/0 | 0.1654 |
| `Task-planning` | 0 | 0 | 0 | 0/0 | -0.2169 |
| <span class="smallcaps">Agentic CogWriter</span> | 39 | 37 | 0 | 15/0 | -0.0222 |
| `No-goals` | 0 | 0 | 0 | 0/0 | 0.0529 |
| `Fixed-order` | 12 | 27 | 0 | 11/0 | 0.1257 |
| `Exploratory-1` | 0 | 0 | 0 | 0/0 | -0.1605 |
| `Exploratory-2` | 0 | 0 | 0 | 0/0 | -0.1023 |

Table 17. Additional consensus-writing evaluation on ten tasks derived from Habermas Machine data. Unlike the long-form benchmarks, <span class="smallcaps">Agentic CogWriter</span> does not achieve the highest pointwise score: `Single-pass` and `Staged` are stronger in this short consensus-writing setting. The result shows that the advantage observed on the long-form benchmarks does not automatically transfer to a substantially shorter writing task; 78 of 80 attempted runs completed.

`Exploratory-1` is the exploratory CogWriter-style (Wan et al., 2025) baseline, with initial planning, immediate plan revision, parallel segment generation, and length review without a goal network; `Exploratory-2` is the exploratory STORM-style (Shao et al., 2024) baseline, with perspective discovery, simulated question answering, outlining, per-section drafting, and polishing without retrieval. On these short consensus-writing tasks, <span class="smallcaps">Agentic CogWriter</span> does not achieve the highest pointwise composite; in particular, it scores below `Single-pass` and `Staged`. Our system and `Fixed-order` record 0 and 0 regeneration events, respectively; their ledgers contain 15/0 and 11/0 no/proposal outcomes, respectively.

## References

Yushi Bai, Jiajie Zhang, Xin Lv, Linzhi Zheng, Siqi Zhu, Lei Hou, Yuxiao Dong, Jie Tang, and Juanzi Li. 2025. Longwriter: Unleashing 10,000+ word generation from long context llms. In *International Conference on Learning Representations*, volume 2025, pages 36528–36546.

W. J. Dixon and A. M. Mood. 1946. [The statistical sign test](https://doi.org/10.1080/01621459.1946.10501898). *Journal of the American Statistical Association*, 41(236):557–566.

Wanyu Du, Vipul Raheja, Dhruv Kumar, Zae Myung Kim, Melissa Lopez, and Dongyeop Kang. 2022. [Understanding iterative revision from human-written text](https://doi.org/10.18653/v1/2022.acl-long.250). In *Proceedings of the 60th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)*, pages 3573–3590. Association for Computational Linguistics.

Yann Dubois, Balázs Galambosi, Percy Liang, and Tatsunori B. Hashimoto. 2024. [Length-controlled AlpacaEval: A simple way to debias automatic evaluators](https://arxiv.org/abs/2404.04475). *arXiv preprint arXiv:2404.04475*. COLM 2024.

Linda Flower and John R Hayes. 1981. A cognitive process theory of writing. *College Composition & Communication*, 32(4):365–387.

Katy Gero, Alex Calderwood, Charlotte Li, and Lydia Chilton. 2022. A design space for writing support tools using a cognitive process model of writing. In *Proceedings of the first workshop on intelligent and interactive writing assistants (In2Writing 2022)*, pages 11–24.

John R Hayes. 1996. [A new framework for understanding cognition and affect in writing](https://doi.org/10.4324/9780203811122-2). In C. Michael Levy and Sarah Ransdell, editors, *The Science of Writing: Theories, Methods, Individual Differences, and Applications*, pages 1–27. Lawrence Erlbaum Associates, Mahwah, NJ.

John R Hayes. 2012. Modeling and remodeling writing. *Written communication*, 29(3):369–388.

Sture Holm. 1979. [A simple sequentially rejective multiple test procedure](https://www.jstor.org/stable/4615733). *Scandinavian Journal of Statistics*, 6(2):65–70.

Dawei Li, Renliang Sun, Yue Huang, Ming Zhong, Bohan Jiang, Jiawei Han, Xiangliang Zhang, Wei Wang, and Huan Liu. 2026. [Preference leakage: A contamination problem in LLM-as-a-judge](https://openreview.net/forum?id=grIvSXVJ65). In *International Conference on Learning Representations*.

Chris Lu, Cong Lu, Robert Tjarko Lange, Jakob Foerster, Jeff Clune, and David Ha. 2024. [The AI scientist: Towards fully automated open-ended scientific discovery](https://arxiv.org/abs/2408.06292). *arXiv preprint arXiv:2408.06292*.

Junyu Luo, Weizhi Zhang, Ye Yuan, Yusheng Zhao, Junwei Yang, Yiyang Gu, et al. 2025. [Large language model agent: A survey on methodology, applications and challenges](https://doi.org/10.48550/arXiv.2503.21460). *arXiv preprint arXiv:2503.21460*.

Aman Madaan, Niket Tandon, Prakhar Gupta, Skyler Hallinan, Luyu Gao, Sarah Wiegreffe, Uri Alon, Nouha Dziri, Shrimai Prabhumoye, Yiming Yang, et al. 2023. Self-refine: Iterative refinement with self-feedback. *Advances in neural information processing systems*, 36:46534–46594.

Chaitanya Malaviya, Priyanka Agrawal, Kuzman Ganchev, Pranesh Srinivasan, Fantine Huot, Jonathan Berant, Mark Yatskar, Dipanjan Das, Mirella Lapata, and Chris Alberti. 2025. Dolomites: Domain-specific long-form methodical tasks. *Transactions of the Association for Computational Linguistics*, 13:1–29.

OpenAI. 2026. GPT-5.6: Frontier intelligence that scales with your ambition. <https://openai.com/index/gpt-5-6/>. Accessed 2026-10-05.

OpenAI. 2026. GPT-5.6 Luna model. <https://developers.openai.com/api/docs/models/gpt-5.6-luna>. Accessed 2026-10-05.

OpenAI. 2026. GPT-5.6 Sol model. <https://developers.openai.com/api/docs/models/gpt-5.6-sol>. Accessed 2026-10-05.

Arjun Panickssery, Samuel R. Bowman, and Shi Feng. 2024. [LLM evaluators recognize and favor their own generations](https://doi.org/10.52202/079017-2197). In *Advances in Neural Information Processing Systems*.

Haoran Que, Feiyu Duan, Liqun He, Yutao Mou, Wangchunshu Zhou, Jiaheng Liu, Wenge Rong, Zekun Moore Wang, Jian Yang, Ge Zhang, et al. 2024. Hellobench: Evaluating long text generation capabilities of large language models. *arXiv preprint arXiv:2409.16191*.

Samuel Schmidgall, Yusheng Su, Ze Wang, Ximeng Sun, Jialian Wu, Xiaodong Yu, Jiang Liu, Michael Moor, Zicheng Liu, and Emad Barsoum. 2025. [Agent laboratory: Using LLM agents as research assistants](https://doi.org/10.18653/v1/2025.findings-emnlp.320). In *Findings of the Association for Computational Linguistics: EMNLP 2025*, pages 5977–6043. Association for Computational Linguistics.

Yijia Shao, Yucheng Jiang, Theodore Kanell, Peter Xu, Omar Khattab, and Monica Lam. 2024. Assisting in writing wikipedia-like articles from scratch with large language models. In *Proceedings of the 2024 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies (Volume 1: Long Papers)*, pages 6252–6278.

Noah Shinn, Federico Cassano, Ashwin Gopinath, Karthik Narasimhan, and Shunyu Yao. 2023. Reflexion: Language agents with verbal reinforcement learning. *Advances in neural information processing systems*, 36:8634–8652.

Theodore Sumers, Shunyu Yao, Karthik R Narasimhan, and Thomas L. Griffiths. 2024. [Cognitive architectures for language agents](https://openreview.net/forum?id=1i6ZCvflQJ). *Transactions on Machine Learning Research*. Survey Certification, Featured Certification.

Zechen Sun, Yuyang Sun, Zecheng Tang, Juntao Li, Wenpeng Hu, Wenliang Chen, Zhunchen Luo, Guotong Geng, and Min Zhang. 2026. Is-cot: Breaking the long-form generation collapse via interleaved structural thinking. In *Proceedings of the 64th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)*, pages 19874–19887.

Haochen Tan, Zhijiang Guo, Zhan Shi, Lu Xu, Zhili Liu, Yunlong Feng, Xiaoguang Li, Yasheng Wang, Lifeng Shang, Qun Liu, and Linqi Song. 2024. [ProxyQA: An alternative framework for evaluating long-form text generation with large language models](https://doi.org/10.18653/v1/2024.acl-long.368). In *Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)*, pages 6806–6827. Association for Computational Linguistics.

Michael Henry Tessler, Michiel A. Bakker, Daniel Jarrett, Hannah Sheahan, Martin J. Chadwick, Raphael Koster, Georgina Evans, Lucy Campbell-Gillingham, Tantum Collins, David C. Parkes, Matthew Botvinick, and Christopher Summerfield. 2024. [AI can help humans find common ground in democratic deliberation](https://doi.org/10.1126/science.adq2852). *Science*, 386(6719):eadq2852.

Kaiyang Wan, Honglin Mu, Rui Hao, Haoran Luo, Tianle Gu, and Xiuying Chen. 2025. A cognitive writing perspective for constrained long-form text generation. In *Findings of the Association for Computational Linguistics: ACL 2025*, pages 9832–9844.

Peiyi Wang, Lei Li, Liang Chen, Zefan Cai, Dawei Zhu, Binghuai Lin, Yunbo Cao, Lingpeng Kong, Qi Liu, Tianyu Liu, and Zhifang Sui. 2024. [Large language models are not fair evaluators](https://doi.org/10.18653/v1/2024.acl-long.511). In *Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)*, pages 9440–9450. Association for Computational Linguistics.

Xingyao Wang, Boxuan Li, Yufan Song, Frank F. Xu, Xiangru Tang, Mingchen Zhuge, Jiayi Pan, Yueqi Song, Bowen Li, Jaskirat Singh, et al. 2024. [OpenHands: An open platform for AI software developers as generalist agents](https://arxiv.org/abs/2407.16741). *arXiv preprint arXiv:2407.16741*.

Edwin B. Wilson. 1927. [Probable inference, the law of succession, and statistical inference](https://doi.org/10.1080/01621459.1927.10502953). *Journal of the American Statistical Association*, 22(158):209–212.

Yuhao Wu, Yushi Bai, Zhiqiang Hu, Juanzi Li, and Roy Ka-Wei Lee. 2026. [SuperWriter: Reflection-driven long-form generation with large language models](https://aclanthology.org/2026.findings-acl.428/). In *Findings of the Association for Computational Linguistics: ACL 2026*, pages 8790–8812. Association for Computational Linguistics.

Yuning Wu, Jiahao Mei, Ming Yan, Chenliang Li, Shaopeng Lai, Yuran Ren, Zijia Wang, Ji Zhang, Mengyue Wu, Qin Jin, et al. 2026. Writingbench: A comprehensive benchmark for generative writing. *Advances in Neural Information Processing Systems*, 38.

Ruibin Xiong, Yimeng Chen, Dmitrii Khizbullin, Mingchen Zhuge, and Jürgen Schmidhuber. 2025. Beyond outlining: Heterogeneous recursive planning for adaptive long-form writing with language models. In *Proceedings of the 2025 Conference on Empirical Methods in Natural Language Processing*, pages 24689–24725.

John Yang, Carlos E. Jimenez, Alexander Wettig, Kilian Lieret, Shunyu Yao, Karthik R. Narasimhan, and Ofir Press. 2024. [SWE-agent: Agent-computer interfaces enable automated software engineering](https://arxiv.org/abs/2405.15793). *arXiv preprint arXiv:2405.15793*.

Kevin Yang, Yuandong Tian, Nanyun Peng, and Dan Klein. 2022. Re3: Generating longer stories with recursive reprompting and revision. In *Proceedings of the 2022 Conference on Empirical Methods in Natural Language Processing*, pages 4393–4479.

Lili Yao, Nanyun Peng, Ralph Weischedel, Kevin Knight, Dongyan Zhao, and Rui Yan. 2019. [Plan-and-write: Towards better automatic storytelling](https://doi.org/10.1609/aaai.v33i01.33017378). In *Proceedings of the AAAI conference on artificial intelligence*, volume 33, pages 7378–7385. AAAI.

Shunyu Yao, Jeffrey Zhao, Dian Yu, Nan Du, Izhak Shafran, Karthik R Narasimhan, and Yuan Cao. 2023. [React: Synergizing reasoning and acting in language models](https://openreview.net/forum?id=WE_vluYUL-X). In *The Eleventh International Conference on Learning Representations*.

Lianmin Zheng, Wei-Lin Chiang, Ying Sheng, Siyuan Zhuang, Zhanghao Wu, Yonghao Zhuang, Zi Lin, Zhuohan Li, Dacheng Li, Eric P. Xing, Hao Zhang, Joseph E. Gonzalez, and Ion Stoica. 2023. [Judging LLM-as-a-judge with MT-Bench and chatbot arena](https://doi.org/10.52202/075280-2020). In *Advances in Neural Information Processing Systems*, volume 36, pages 46595–46623.

[^1]: See Appendix A for the exact selection rule, sample sizes, and sensitivity analysis.

[^2]: We choose Luna for high-volume long-form generation because OpenAI positions it for fast, cost-sensitive workloads, and Sol as the primary evaluator because it is the higher-capability tier for complex professional work. Assigning the higher-capability tier to evaluation keeps generation scalable; the shared model family motivates the cross-family check (OpenAI, 2026b; OpenAI, 2026c; OpenAI, 2026a).

[^3]: See Appendix A for the complete prompts and Appendix B for the runtime settings.

[^4]: See Appendix A for the full procedures and evaluator prompts.

[^5]: See Appendix C for the generation-run estimates, Wilson intervals (Wilson, 1927), and corrected test decisions.

[^6]: See Appendix D for the paired differences and intervals.

[^7]: See Appendix C for the run-level intervals and corrected test decisions.

[^8]: See Appendix F for sensitivity analyses: resource-matched comparisons largely preserve the direction, whereas cross-family rescoring is less stable, including a WritingBench reversal against `Single-pass`.

[^9]: See Appendix F for the benchmark-level diagnostic and the remaining execution differences.

[^10]: See Appendix E for process counts, goal events, and resource-use statistics.
