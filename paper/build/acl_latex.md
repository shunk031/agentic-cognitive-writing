## Agentic CogWriter: Revisiting the Cognitive Process Theory of Writing for AI Agents

Anonymous ACL submission

## Abstract

Recent coding agents have made tool-using, stateful execution prominent. The same execution style is increasingly used for knowledge work that ends in long-form documents. Yet long-form writing systems usually advance an outline, task graph, or fixed stage sequence rather than deciding which writing process is needed next. Drawing on cognitive process theory, we propose <span class="smallcaps">Agentic CogWriter</span>, which maintains a shared draft, goals, and process history while a Monitor agent chooses and delegates planning, drafting, or reviewing. We evaluate our system across three long-form writing benchmarks using pointwise rubric scoring and pairwise same-prompt preference judgments. Our system achieves competitive pointwise quality and is preferred to one-shot generation, a fixed planning–drafting–revision workflow, and adaptive task planning in pairwise evaluation. Ablations that drop explicit goals or fix the process order keep most of this advantage on WritingBench and HelloBench, so neither component alone is required to keep it on these tasks. Process traces show that most runs follow a planning–drafting–reviewing path, with departures used selectively rather than continually.

## Introduction

Large language model agents (Yao et al., 2023; Shinn et al., 2023; Sumers et al., 2024; Luo et al., 2025) increasingly combine reasoning, tool use, memory, and delegation to carry out multi-step knowledge work. Recent coding agents have made this interactive, tool-mediated style of execution especially prominent (Yang et al., 2024; Wang et al., 2025), while similar agentic workflows increasingly produce reports or scientific manuscripts (Schmidgall et al., 2025; Lu et al., 2024). For agents that produce documents, long-form writing requires more than final text generation: the agent must organize the document, turn partial plans into prose, inspect what has been written, and decide when revision is needed.

Figure 1. Overview of <span class="smallcaps">Agentic CogWriter</span>. Inspired by the cognitive process theory of writing, a coding-agent-style control loop turns the task into a document via Planning, Translating, or Reviewing, selected online from the evolving document state.

Existing long-form writing systems impose different forms of structure on generation (Yao et al., 2019; Yang et al., 2022; Shao et al., 2024; Bai et al., 2025; Xiong et al., 2025; Sun et al., 2026). Some build an outline before drafting (Yao et al., 2019; Yang et al., 2022), some generate a document section by section (Shao et al., 2024; Bai et al., 2025; Huot et al., 2025), some recursively decompose the document into tasks (Xiong et al., 2025), and some adapt plans or structural reasoning during generation (Wan et al., 2025; Sun et al., 2026). Across these systems, the next step is usually defined by a content unit, task node, or prescribed stage. A complementary design question remains comparatively underexplored: should the writer decide which kind of writing process is needed next?

The cognitive process theory of writing (Flower and Hayes, 1981; Hayes, 1996; Hayes, 2012) provides a useful abstraction for process-level control. Flower and Hayes (1981) characterize writing as coordination among planning, translating, and reviewing, with a monitor deciding which process to invoke as the document develops. This view suggests choosing the next writing process rather than the next section or task node.

Building on Flower and Hayes (1981), we propose <span class="smallcaps">Agentic CogWriter</span>, a long-form writing system that implements this process-level control on top of a coding-agent-style harness with persistent state and subagent delegation (Figure 1). A top-level Monitor agent observes the evolving draft, goals, and process history, chooses whether the next activity should be planning, drafting, or reviewing, and delegates that activity to a corresponding subagent. The resulting process order is chosen during writing rather than fixed in advance. We call the system *agentic* for this combination: online selection of the next writing process, a persistent state shared across steps, and delegation of each selected process to a subagent.

We evaluate our system on three complementary long-form writing benchmarks spanning broad instruction-driven writing, long-context generation, and methodical expert-document production (Wu et al., 2025; Que et al., 2024; Malaviya et al., 2025). We hold the generator and task information constant across conditions. Pointwise rubric scoring and pairwise same-prompt preference evaluation assess document quality from complementary perspectives. In pairwise evaluation, our system is preferred to one-shot generation, a fixed writing pipeline, and adaptive task planning. The component analyses support a system-level interpretation: on these tasks, neither explicit goals nor adaptive ordering alone is required to keep most of this advantage. Process traces show that most runs follow a planning–drafting–reviewing path, indicating that adaptive ordering is available but used selectively.

Our contributions are threefold. (1) We formulate long-form writing for general-purpose agents as a process-level control problem and introduce a concrete system that chooses among planning, drafting, and reviewing during composition; (2) we compare our system with one-shot, fixed-stage, and adaptive task-planning alternatives across complementary long-form benchmarks; and (3) we use ablations and process analyses to test which components the advantage requires and characterize how the loop is used in practice.

## Related Work

##### Language agents and document production.

Language-agent research studies systems that interleave reasoning with actions, tools, memory, and feedback (Yao et al., 2023; Shinn et al., 2023; Sumers et al., 2024), while writing-support systems assist planning, drafting, and revision (Gero et al., 2022). Multi-agent frameworks divide work among role-specialized agents that converse (Wu et al., 2024), follow standardized operating procedures (Hong et al., 2024), or are directed by an orchestrator that selects the next specialized agent (Fourney et al., 2024). Autonomous research systems increasingly connect those capabilities to report or paper generation after literature review and experimentation (Schmidgall et al., 2025; Lu et al., 2024). We focus on how a general-purpose agent organizes that writing stage.

##### Long-form generation and planning.

Long-form generation becomes harder to control and evaluate as outputs grow in length (Tan et al., 2024; Wu et al., 2026), motivating explicit planning and decomposition. Plan-and-Write (Yao et al., 2019), Re`^3` (Yang et al., 2022), DOC (Yang et al., 2023), STORM (Shao et al., 2024), RecurrentGPT (Zhou et al., 2023), and LongWriter (Bai et al., 2025) organize generation around plans, revisions, outlines, sections, or paragraph-level content units. CogWriter (Wan et al., 2025), WriteHERE (Xiong et al., 2025), IS-CoT (Sun et al., 2026), and SuperWriter (Wu et al., 2026) make structure or refinement increasingly adaptive. CogWriter conditionally revises plans and generated segments within a planning-and-generation workflow, whereas WriteHERE schedules nodes in an evolving heterogeneous task graph. Agents’ Room (Huot et al., 2025) defines an orchestrator that chooses the next planning or writing agent from a shared scratchpad, but its agents specialize in story elements, it has no reviewing agent, and its experiments fix the agent order. Our <span class="smallcaps">Agentic CogWriter</span> instead has process-defined subagents and a Monitor that chooses among planning, drafting, and reviewing.

##### Iteration and cognitive models of writing.

Iterative generation methods improve text through repeated feedback and revision (Madaan et al., 2023; Du et al., 2022), and PEER (Schick et al., 2023) trains a model to imitate the writing process by proposing and explaining edits, while cognitive writing research offers a process-level account of how planning, drafting, and reviewing interact (Flower and Hayes, 1981; Hayes, 1996; Hayes, 2012). Gero et al. (2022) use those processes to organize writing-support systems, and CogWriter (Wan et al., 2025) likewise draws on cognitive writing theory to structure planning, generation, and revision. Our <span class="smallcaps">Agentic CogWriter</span> tests this process-level account directly with matched alternatives, ablations, and analyses of observed writing behavior. Table 1 summarizes the distinction alongside other explicit capabilities of representative long-form writing systems.

|  |  |  |  |  |
|:---|:--:|:--:|:--:|:--:|
| **Method** | **Unit of**; **progress** | **Adaptive**; **next step** | **Evolving**; **structure** | **Online process**; **selection** |
| Re`^3` (Yang et al., 2022) | Passage | – | – | – |
| STORM (Shao et al., 2024) | Section | – | – | – |
| Agents’ Room (Huot et al., 2025) | Story element | yes | – | Partial |
| CogWriter (Wan et al., 2025) | Plan / segment | yes | Plan | – |
| WriteHERE (Xiong et al., 2025) | Task node | yes | Task graph | – |
| **<span class="smallcaps">Agentic CogWriter</span> (ours)** | **Writing process** | yes | **Goal network** | yes |

Table 1. Comparison of control choices in representative long-form writing systems, by method design. The unit of progress is what advances at each step; adaptive next step indicates whether that choice depends on the current state. Evolving structure excludes document text. Partial marks selection among planning and writing agents only; <span class="smallcaps">Agentic CogWriter</span> is the only system with online selection among planning, drafting, and reviewing.

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

Each subagent writes its changes to the shared workspace before control returns to the `Monitor`, yielding the next state `S_(t+1)`. Review feedback can recommend replacing a goal, but the `Monitor` decides whether to accept that change and records the decision in `H_t`. Because each decision is made from the updated state, the process order is not fixed: drafting can expose a structural problem that sends control back to planning, and reviewing can trigger another drafting or planning pass. For example, if `Reviewing` finds that the draft omits a section the task requires, the `Monitor` can select `Planning` to add a goal for that section before further `Translating`. The `Monitor` may stop after any process and return the current draft as the final document `D_final`; the runner’s output-token budget or per-command timeout can also end a run before a `Reviewing` pass.

## Experimental Design

We compare the writing systems under the same task inputs and information policy to study three questions: whether process-level organization improves document quality, which components contribute to any advantage, and how the writing loop behaves in practice. We also use one post-hoc execution variant as a diagnostic. Because agent execution is stochastic, every prompt–system pair is generated in three runs, so differences between systems can be judged against run-to-run variation.

### Systems Compared

We consider seven pre-specified systems under the same generation setup. Their numbers below are used throughout the analysis.

##### Alternative writing systems.

We compare three alternatives to <span class="smallcaps">Agentic CogWriter</span>: (1) `Single-pass` produces the complete document in one generation call; (2) `Staged` executes the `Pre-Write``->``Write``->``Re-Write` stage model (Rohman, 1965), which Flower and Hayes (1981) argued against and long-form systems instantiate as planning, drafting, and revision (Yang et al., 2022; Wan et al., 2025); and (3) `Task-planning` follows a WriteHERE-style adaptive task graph (Xiong et al., 2025), recursively decomposing the assignment and selecting among dependency-satisfied task nodes. The alternatives therefore advance a whole document, a fixed writing stage, or an adaptive task node, whereas our system advances a writing process.

##### Ablations of Agentic CogWriter.

Two pre-specified ablations change one control mechanism while retaining the rest of the loop. (4) `No-goals` removes the explicit goal representation but keeps adaptive process selection and the three subagents, while (5) `Fixed-order` keeps the shared draft, goals, process history, and subagents but replaces the `Monitor`’s adaptive decision with a repeated `Planning`–`Translating`–`Reviewing` cycle. The comparison tests whether explicit goals or adaptive ordering explain the full-system gain.

##### Execution variant and full system.

\(6\) `Single-writer` retains the goal representation and adaptive process loop but performs `Planning`, `Translating`, and `Reviewing` in one writer context without subagent delegation; it also limits each `Translating` step to one paragraph, so the condition is diagnostic rather than a clean ablation. Its prompt also asks the writer to follow the repository’s writing guidance and remove filler and AI-pattern phrasing, an instruction the other systems’ prompts do not contain. (7) <span class="smallcaps">Agentic CogWriter</span> is the full system of Section 3.2, with adaptive process selection, explicit goals, and role-specific subagents.

##### Post-hoc execution check.

`Single-context` was added after the main results as a narrower exploratory check and is not one of the seven pre-specified systems. The condition preserves the full process loop and shared state but executes each selected process in the `Monitor`’s context rather than a separate subagent context, serving only as a diagnostic of whether separate role contexts are necessary to explain the observed difference.

|  |  |  |  |  |
|:---|:---|:---|:---|:---|
| **System** | **Information available** | **What advances next?** | **Decision rule** | **Execution** |
| `Single-pass` | `X` | Whole document | One generation | One context |
| `Staged` | `X`, prior stage output | Fixed stage | Pre-Write`->`Write`->`Re-Write | One context |
| `Task-planning` | `X,D_t,T_t` | Task node | Select a ready task node | Task subagents |
| **<span class="smallcaps">Agentic CogWriter</span>** | `X,D_t,G_t,H_t` | **Writing process** `a_t` | `a_t=Monitor(X,D_t,G_t,H_t)` | **Subagent** |
| `No-goals` | `X,D_t,H_t` | Writing process `a_t` | `a_t=Monitor(X,D_t,H_t)` | Subagent |
| `Fixed-order` | `X,D_t,G_t,H_t` | Fixed process | `Planning``->``Translating``->``Reviewing` | Subagent |
| `Single-writer` | `X,D_t,G_t,H_t` | Writing process `a_t` | `a_t=Monitor(X,D_t,G_t,H_t)` | One writer |
| `Single-context` | `X,D_t,G_t,H_t` | Writing process `a_t` | `a_t=Monitor(X,D_t,G_t,H_t)` | `Monitor` context |

Table 2. Operational comparison of the evaluated writing systems. `Staged` follows fixed planning–drafting–revision stages (Yang et al., 2022; Wan et al., 2025); `Task-planning` follows WriteHERE-style task planning (Xiong et al., 2025). The first four rows expose the central difference in what advances next: document, stage, task node, or writing process. `X` is the task input; `D_t`, `G_t`, and `H_t` are draft, goals, and process history; `T_t` is the task graph. The remaining rows modify <span class="smallcaps">Agentic CogWriter</span>; `Single-context` was added post-hoc.

### Benchmarks and Prompts

We use three benchmarks to test whether process-level organization transfers across different forms of long-form writing: (1) WritingBench (Wu et al., 2025), which covers broad real-world writing requests with task-specific evaluation criteria; (2) HelloBench (Que et al., 2024), which includes long-text summarization, open-ended generation, and completion; and (3) DoLoMiTes (Malaviya et al., 2025), which targets methodical expert writing with explicit objectives, procedures, inputs, and constraints. The benchmarks cover general instruction following, sustained long-context generation, and structured expert-document production.

We evaluate fixed demanding subsets because short or lightly constrained tasks may not reveal differences in how a system manages a long document. We first reserve any prompts used while developing or debugging the evaluation protocol and never score those prompts. From the remaining benchmark items, we deterministically prioritize cases with longer supplied context and, when the prompt specifies a target length, longer requested output, while applying fixed maximum-length limits. This produces a different demanding subset for each benchmark: WritingBench emphasizes long inputs with explicit long-output requirements, HelloBench emphasizes very long-input summarization and continuation, and DoLoMiTes emphasizes procedurally constrained expert writing.[^1]

### Implementation

All systems run in Codex CLI as the coding-agent harness with `gpt-5.6-luna` as the generator; API-based scoring uses `gpt-5.6-sol` as the primary evaluator.[^2] The comparison holds the generator, harness, workspace tools, output budget, and task information constant across systems. Each system’s control design and prompts differ together: the alternatives use prompts reimplemented from published designs, and only our system and its ablations and execution variants receive the `Planner`, `Translator`, and `Reviewer` role instructions. Our system is an agent skill: its `Monitor` invokes the three roles as subagents.[^3]

Every generation run uses the same generator, prompt set, and runtime configuration; main-result tables summarize the three runs unless noted otherwise. Network access, web search, and external retrieval are disabled for every system, and the harness records completed outputs plus available process traces, token accounting, and timing.

### Evaluation

We evaluate documents with LLM-as-a-judge (Zheng et al., 2023), in which an evaluator model reads the prompt and the generated documents and returns rubric scores or a preference. We use two protocols: pointwise evaluation scores each document alone, and pairwise evaluation compares two systems’ documents per prompt.

##### Pointwise evaluation.

When a benchmark defines its own rubric, we report that score as the *benchmark-native* score, meaning the benchmark authors’ original criteria rather than our shared rubric. WritingBench uses five prompt-specific criteria scored from 1 to 10, which we rescale to 0–1, HelloBench uses checklist items, and DoLoMiTes provides no comparable native score.

We also apply a common five-dimension rubric across all three benchmarks: instruction fulfillment, organization and coherence, content adequacy and depth, style and audience fit, and factual or constraint fidelity, each scored from 1 to 5.[^4] Because these ratings concentrate near the upper end, each dimension is standardized within each generation run and benchmark across outputs from all seven pre-specified systems before averaging. The composite is relative within a benchmark rather than an absolute quality scale.

##### Pairwise evaluation.

The judge uses the same quality dimensions and records a preference or a tie. LLM judges can exhibit position bias (Zheng et al., 2023; Wang et al., 2024), so every pair is evaluated in both presentation orders. We count a preference only when both orders select the same semantic response; any disagreement, including preference versus tie, is recorded as a tie. For a contrast written as “A vs. B”, we report wins/losses/ties (W/L/T) for A and compute its win rate over non-tied order-consistent comparisons as `W/(W+L)`.

The primary generator and evaluator come from the same model family, which can introduce systematic preference leakage or self-preference (Li et al., 2026; Panickssery et al., 2024). We therefore rescore selected system comparisons with `claude-sonnet-5 medium` as a separate descriptive robustness check rather than averaging results from the two evaluators.

##### Pre-specified statistical testing.

We fixed the confirmatory comparisons before scoring to avoid choosing favorable tests after observing results. For each benchmark and generation run, an exact two-sided sign test compares the non-tied prompt-level wins and losses for every pre-specified contrast (Dixon and Mood, 1946). Testing several related contrasts increases the chance of at least one false positive, so we apply Holm’s step-down correction (Holm, 1979) across the pre-specified tests within each benchmark. Generation runs remain separate because they repeat the same prompts rather than provide new independent samples.[^5]

To summarize the two ablation contrasts across generation runs, we compute an exploratory post-hoc prompt-level estimate. For each prompt, win, tie, and loss outcomes are mapped to `1`, `1/2`, and `0`, averaged across the three generation runs, and summarized across benchmarks with a bootstrap interval (Efron, 1979) and sign test.

##### Robustness and behavioral analysis.

Pairwise LLM evaluation can favor longer outputs and can change with judge identity (Zheng et al., 2023; Dubois et al., 2024; Li et al., 2026; Panickssery et al., 2024). We therefore test whether the pairwise direction persists within pre-specified output-length bands, under a tight compute match, and under the cross-family evaluator. Output length and realized compute are consequences of execution, so the first two analyses are descriptive sensitivity checks rather than causal adjustments.

We analyze observable traces of process transitions, goal creation and development, goal replacement, and subagent invocations to characterize how the writing loop is actually used. We also compare runs that complete one `Planning`–`Translating`–`Reviewing` cycle with runs that take another process path. The trace-defined split is observational rather than randomized, so it describes behavior without identifying a causal mechanism.

## Results

### Pointwise and Benchmark-Native Quality

Table 3 reports document-quality scores for benchmark-native and common-rubric evaluation across the three benchmarks. <span class="smallcaps">Agentic CogWriter</span> exceeds every alternative’s mean on every WritingBench and HelloBench measure, and its paired prompt-level differences exclude zero against each on both WritingBench measures and HelloBench native scores. Its lead over `Staged` and `Task-planning` on HelloBench pointwise scores lies within the paired intervals, as does the higher DoLoMiTes pointwise mean of `Staged`.[^6]

|  |  |  |  |  |  |  |
|:---|---:|---:|---:|---:|---:|---:|
| **System** | **WritingBench** | **WritingBench** | **HelloBench** | **HelloBench** | **DoLoMiTes** | **DoLoMiTes** |
|  | **Native `↑`** | **Pointwise `↑`** | **Native `↑`** | **Pointwise `↑`** | **Native `↑`** | **Pointwise `↑`** |
| `Single-pass` | 0.697 `±` 0.006 | -0.090 `±` 0.009 | 0.773 `±` 0.005 | -0.112 `±` 0.018 | <span style="color: nagray">N/A</span> | -0.006 `±` 0.018 |
| `Staged` (Yang et al., 2022; Wan et al., 2025) | 0.702 `±` 0.005 | -0.041 `±` 0.012 | 0.781 `±` 0.004 | 0.003 `±` 0.016 | <span style="color: nagray">N/A</span> | <span style="color: tiedgray">**0.064** `±` 0.036</span> |
| `Task-planning` (Xiong et al., 2025) | 0.722 `±` 0.004 | -0.033 `±` 0.033 | 0.781 `±` 0.003 | -0.016 `±` 0.061 | <span style="color: nagray">N/A</span> | -0.164 `±` 0.015 |
| **<span class="smallcaps">Agentic CogWriter</span>** | **0.747** `±` 0.006 | **0.102** `±` 0.040 | **0.791** `±` 0.005 | <span style="color: tiedgray">**0.013** `±` 0.060</span> | <span style="color: nagray">N/A</span> | 0.031 `±` 0.035 |

Table 3. Document quality (mean `±` sample SD across runs; higher is better). *Native* uses each benchmark’s criteria; *Pointwise* uses a common five-dimension rubric, z-scored within each run and benchmark over all seven systems; Section 5.3 and Appendix D compare the ablations. Bold marks the highest mean in each column. <span class="smallcaps">Agentic CogWriter</span> exceeds every alternative on WritingBench and HelloBench.

### Direct Comparison of Writing Systems

Table 4 reports a system-level separation in direct same-prompt comparisons. <span class="smallcaps">Agentic CogWriter</span> is preferred to `Single-pass`, `Staged`, and `Task-planning`, with across-benchmark mean win rates of 80.9%, 67.3%, and 68.5%, respectively, among order-consistent comparisons. The direction holds in every benchmark and generation run against `Single-pass` and `Task-planning`, and in all but one benchmark–run test against `Staged`.

Under the pre-specified within-benchmark Holm correction, 8, 4, and 3 of the nine benchmark–run tests separate our system from `Single-pass`, `Task-planning`, and `Staged`, respectively.[^7] The preference also persists under more conservative accounting: counting every attempted prompt yields win shares of 63.1%, 46.6%, and 49.7%, and assigning every missing pair against our system still leaves win rates of at least 74.9%, 61.9%, and 66.1% among order-consistent comparisons.[^8]

|  |  |  |  |  |
|:---|---:|---:|---:|---:|
|  | **<span class="smallcaps">Agentic CogWriter</span> win rate (%)** | **<span class="smallcaps">Agentic CogWriter</span> win rate (%)** | **<span class="smallcaps">Agentic CogWriter</span> win rate (%)** | **<span class="smallcaps">Agentic CogWriter</span> win rate (%)** |
| **Comparison** | **Writing** | **Hello** | **DoLo** | **Across** |
| vs. `Single-pass` | 84.3% | 85.7% | 72.0% | 80.9% |
| vs. `Staged` | 80.9% | 62.8% | 55.9% | 67.3% |
| vs. `Task-planning` | 65.5% | 63.0% | 75.7% | 68.5% |

Table 4. Run-averaged same-prompt win rates; above 50% favors our system. Across averages run-level win rates computed after summing wins and losses across benchmarks; benchmark rates exceed 50%, with the largest mean margin over `Single-pass`.

### Ablations and Execution Diagnostics

Table 5 places the two pre-specified ablations much closer to <span class="smallcaps">Agentic CogWriter</span> than the alternative writing systems in Table 4. No benchmark–run test comparing our system with `No-goals` or `Fixed-order` is significant after the within-benchmark Holm correction. An exploratory prompt-level summary defined after the main results places our system slightly ahead of both ablations, at 53.7% \[51.0%–56.4%\], `p=0.004`, against `Fixed-order` and 52.3% \[49.6%–55.0%\], `p=0.056`, against `No-goals`; the two intervals overlap, so the summary does not rank the components. The ablations nonetheless keep the full system’s advantage over the alternatives: of 12 paired native and pointwise contrasts with them on WritingBench and HelloBench, intervals exclude zero for 11 with `No-goals` and 7 with `Fixed-order`, against 10 with the full system.[^9]

|  |  |  |  |  |
|:---|---:|---:|---:|---:|
|  | **<span class="smallcaps">Agentic CogWriter</span> win rate (%)** | **<span class="smallcaps">Agentic CogWriter</span> win rate (%)** | **<span class="smallcaps">Agentic CogWriter</span> win rate (%)** | **<span class="smallcaps">Agentic CogWriter</span> win rate (%)** |
| **System** | **Writing** | **Hello** | **DoLo** | **Across** |
| `No-goals` | 52.1% | 52.4% | 56.0% | 53.4% |
| `Fixed-order` | 56.8% | 57.4% | 54.7% | 56.3% |
| `Single-writer` | 68.5% | 83.4% | 67.8% | 73.5% |

Table 5. Run-averaged <span class="smallcaps">Agentic CogWriter</span> win rates; above 50% favors our system. Across sums wins and losses over benchmarks, then averages runs. The ablations stay near parity; the diagnostic execution variant `Single-writer` shows a larger gap.

Execution changes produce a larger but less easily isolated difference. `Single-writer` removes subagent delegation, changes role context and decision granularity, and alters output length at the same time. Within the tighter and wider pre-specified output-length bands, `Single-writer` still wins only 35.1% (`p=0.0479`) and 30.6% (`p=5.24 x 10^-4`), respectively, against our system, so output length alone does not explain the gap. The narrower post-hoc `Single-context` check shows no significant difference from our system in the exploratory generation run (47.4% win rate for `Single-context`, `p=0.5161`, unadjusted).[^10]

### Observed Writing-Process Behavior

Table 6 shows a mostly simple writing loop after repeat collapsing and leading-`Planning` reconstruction: 74.6% of complete paths conform to the `Planning`–`Translating`–`Reviewing` cycle structure, while 16.5% of runs return from `Reviewing` to `Translating`. Full replanning (4.1%) and goal replacement (0.5%) are rare, so adaptivity is used mainly for targeted redrafting.

|  |  |
|:---|---:|
| **Observed writing-loop behavior** | **Rate** |
| *Complete path (one per run)* | *Complete path (one per run)* |
| Cycle-compliant path | 74.6% |
| Any other complete path | 25.4% |
| *Runs with each event (can overlap)* | *Runs with each event (can overlap)* |
| `Reviewing` followed by renewed `Translating` | 16.5% |
| `Reviewing` followed by renewed `Planning` | 4.1% |
| Runs with an accepted goal replacement | 0.5% |
| <span style="color: residualgray">Runs with none of these events</span> | <span style="color: residualgray">79.8%</span> |

Table 6. Writing-loop behavior of <span class="smallcaps">Agentic CogWriter</span> after repeat collapsing and leading-`Planning` reconstruction; most paths are cycle-compliant.

Figure 2 shows the same concentration: the forward `Planning`–`Translating`–`Reviewing` progression is most frequent, so our system looks close to `Fixed-order`. Because the demanding subsets increase input or requested output length or procedural burden without guaranteeing a need to replan, the traces show that adaptive control is rarely exercised on these subsets, not that repeated replanning is unnecessary for difficult writing.

Figure 2. Process trajectories: (a) frequent complete paths; (b,c) transition counts per system (E: run end). Our system mostly follows the same forward `Planning`–`Translating`–`Reviewing` progression as `Fixed-order`.

Table 7 shows similar pairwise win rates against `Fixed-order` and `Single-writer` for runs with one `Planning`–`Translating`–`Reviewing` cycle and runs with other paths, so observed departures do not yield a larger quality advantage. Because the split is observational, it cannot show whether path choice affects quality.[^11]

|  |  |  |
|:---|---:|---:|
|  | **<span class="smallcaps">Agentic CogWriter</span> win rate (%)** | **<span class="smallcaps">Agentic CogWriter</span> win rate (%)** |
| **Process path** | **`Fixed-order`** | **`Single-writer`** |
| `Planning``->``Translating``->``Reviewing` | 57.5% | 72.6% |
| Other path | 54.7% | 74.7% |

Table 7. <span class="smallcaps">Agentic CogWriter</span> win rates against `Fixed-order` and `Single-writer` are similar for one-cycle `Planning`–`Translating`–`Reviewing` runs and other-path runs. Rates sum wins and losses over benchmarks and runs; the split is observational, not causal.

## Discussion

Tables 3 and 4 show that <span class="smallcaps">Agentic CogWriter</span> is distinguished by consistent same-prompt preference over the three alternatives rather than uniform pointwise dominance. Because the ablations keep most of that advantage, neither explicit goals nor adaptive ordering alone is required for it on these tasks, where the traces show little replanning.

Figure 2 and Table 6 show that <span class="smallcaps">Agentic CogWriter</span> usually follows planning–drafting–reviewing and departs selectively, so process-level control is not the same as continual replanning. This complements systems that adapt task decomposition or structural reasoning during generation (Xiong et al., 2025; Wan et al., 2025; Sun et al., 2026): a second axis is which process a controller selects, not only how dynamically it replans. More broadly, cognitive writing theory provides executable control abstractions rather than claims that language agents reproduce human cognition, making alternative writing processes explicit enough to implement, compare, and falsify.

## Conclusion

<span class="smallcaps">Agentic CogWriter</span> reframes long-form writing for AI agents as process-level control: a top-level `Monitor` selects planning, drafting, or reviewing from persistent state and delegates to role-specific subagents. Across three long-form writing benchmarks, our system is preferred to single-pass generation, fixed writing stages, and adaptive task planning in same-prompt comparisons; ablations without explicit goals or with a fixed process order keep most of the advantage, and most traces follow a simple planning–drafting–reviewing path.

## Limitations

##### Scope and external validity.

Our conclusions concern one generator family, one coding-agent-style harness, and deterministic subsets of three long-form benchmarks. The subset rule emphasizes long inputs and, when specified, long requested outputs rather than an independent measure of difficulty or of the need to revise. The results therefore do not establish transfer to shorter tasks, other model families or runtimes, interactive human–AI writing, or end-to-end agents with retrieval. A direct next step is a task set that changes objectives, introduces new evidence, or adds rhetorical constraints during writing, so that process selection is required rather than only available.

##### Comparison design.

The alternative writing systems are reimplementations under the shared setup of Section 4.3, not executions of the published systems. `Task-planning` also delegates its task nodes to subagents, so delegation is present on both sides of that comparison. CogWriter-style and STORM-style adaptations (`Exploratory-1`, `Exploratory-2`) run only on ten consensus-writing tasks, and running them on the three benchmarks is the next comparison.[^12] The compute-matched analysis selects pairs with similar realized token use after generation; a Self-Refine baseline (Madaan et al., 2023) given our system’s token budget before generation would test budget-matched iterative revision directly.

##### Evaluator dependence.

Section 5.2 complements the order-consistent win rates with unconditional and worst-case missing-output views. The primary evaluator belongs to the same model family as the generator, and related generator–judge models can exhibit preference leakage or self-preference (Li et al., 2026; Panickssery et al., 2024). The cross-family judge rescored one generation run for the contrasts with `Single-pass`, `Task-planning`, and `No-goals`; summing W/L/T counts over the three benchmarks leaves all three favoring our system, but the judge produces many ties and reverses 3 of 9 benchmark-level comparisons. Extending the check to `Staged` and `Fixed-order` and to all three generation runs would cover every contrast between our system and an alternative or ablation. Model-judge preference is not human preference; a blinded human comparison of same-prompt outputs, stratified by benchmark, contrast, and prompt length, would measure how closely the judges agree with human readers.

##### Component attribution.

The ablations constrain explicit goals and adaptive ordering to modest contributions without establishing equivalence. Neither ablation differs from the full system in any benchmark–run test after Holm correction, each such test reaches 80% power (Card et al., 2020) at a true preference of about 73%, and the exploratory prompt-level summary does not rank the two components.[^13] `Fixed-order` enforces its cycle through the `Monitor`’s instructions so that it shares our system’s agent runtime and differs only in the selection rule, and 89.8% of its paths are cycle-compliant.[^14] Next steps are a runner-enforced cycle and a combined ablation that removes goals and fixes the order together, which would test whether the two mechanisms substitute for each other.

##### Execution variants.

`Single-writer` changes delegation, role context, decision granularity, and output length together; `Single-context` is narrower but was added post-hoc, uses one exploratory generation run, and differs in execution interface and transport. The current evidence therefore does not attribute the remaining system-level advantage to any single shared execution feature.

##### Descriptive execution analyses.

The primary evaluator favors longer outputs overall, and the length- and compute-matched analyses are descriptive because both variables result from execution. Process traces likewise record state transitions and agent actions; they characterize how <span class="smallcaps">Agentic CogWriter</span> behaves on these tasks but do not measure human cognition or validate cognitive process theory as a model of language-agent internals.

## Ethical Considerations

Agentic long-form writing can support the organization and revision of complex documents, but the same capability can also scale persuasive or misleading text and amplify unsupported claims or biases inherited from the underlying model. Process decomposition and reviewing do not provide factuality or safety guarantees, and the system should not be treated as an autonomous authority for high-stakes writing. Our experiments disable external retrieval and study benchmark tasks rather than deployment; downstream use should retain human verification and domain-appropriate safeguards. Multi-step agent execution also makes additional model calls and can increase computational cost relative to one-pass generation, so we report token and runtime statistics to make this tradeoff visible. We recruited no human annotators or participants and collected no new personal data; the study reuses published benchmark artifacts under their released terms (Appendix A).

## Prompt and Experiment Configuration

##### Prompt selection and provenance.

The scored study uses the committed `hard100` subset generated from the pinned WritingBench (Wu et al., 2025), HelloBench (Que et al., 2024), and DoLoMiTes (Malaviya et al., 2025) manifests before generation. Prompts used while developing the protocol are removed first. Each remaining prompt is ranked by prompt word count plus the largest requested output length stated in the prompt or structured output constraints, subject to fixed maximum-length gates; ties are resolved by prompt word count, requested length, and prompt identifier. The top 100 eligible prompts from each benchmark are retained, yielding 300 scored prompts. Of these, 32 WritingBench prompts are written mainly in Chinese and the rest are in English; systems and evaluators receive each prompt in its original language. Generation reads the committed manifests and identifiers, so system output quality cannot affect selection.

##### Artifact provenance and terms.

We use pinned snapshots of WritingBench (Apache-2.0), HelloBench (MIT), and DoLoMiTes (CC BY 4.0 for the benchmark materials); the exploratory Habermas Machine analysis likewise uses CC BY 4.0 materials. The corresponding source commits or archives, content hashes, and transformation notes are recorded in the experiment provenance manifest. We use these artifacts only for research evaluation under their released terms and redistribute only the derived prompt manifests described by that provenance record rather than hidden reference outputs or additional source data. For the Habermas Machine tasks, the materialized prompts omit source participant identifiers. We did not conduct an independent audit of the source benchmarks for offensive content or latent personal information beyond the transformations used to construct the evaluation prompts.

The three selected subsets stress different properties of long-form writing. WritingBench combines long inputs with explicit long-output requirements, HelloBench contributes primarily very long-input summarization and continuation tasks, and DoLoMiTes contributes methodical expert tasks with structured procedural constraints. The `hard100` name identifies the deterministic length-and-demand rule rather than a claim that every prompt has the same source of semantic difficulty.

##### Sample size and inferential sensitivity.

The 100-prompt count per benchmark was fixed before scoring. Under the realized missing and tie rates, a benchmark–contrast–generation-run test contains about 75 decided comparisons; at the strictest first-step Holm threshold, an exact sign test has 80% power for a true preference of about 73%. Combining benchmarks only for a descriptive sensitivity calculation gives about 220 decided comparisons and a detectable preference of about 63%. The calculation describes the sensitivity of the committed sample and does not make the subset representative of each full benchmark.

##### Common generation setup and implementation.

Every pre-specified system receives the same assignment, supplied context, requested output constraints, generator, attempt budget, and information policy. External retrieval is disabled by the coding-agent sandbox and by the experiment prompts. <span class="smallcaps">Agentic CogWriter</span> runs as an agent skill under a top-level `Monitor`; the `Planner`, `Translator`, and `Reviewer` subagents execute the role skills reproduced below. The platform-specific subagent wrappers only dispatch the corresponding role skills and add no separate writing policy. Configuration files pin the skill or stage prompt for every system and record hashes for fixed stage prompts.

The experiment-authored generation and evaluation prompt configurations are listed below. Generation is non-interactive: the runner supplies the assignment, context, and output constraints before each run, so the skill prompts omit interactive user-handoff instructions. Prompt headers use the internal condition codes A1 `Single-pass`, A2 `Staged`, A3 `Task-planning`, A4 <span class="smallcaps">Agentic CogWriter</span>, A5 `No-goals`, A6 `Fixed-order`, A7 `Single-writer`, and A8 `Single-context`. Provider-level defaults not authored by the experiment are set by the runtime configuration in Appendix B.

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

    The final response must contain the complete final text.

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
    - Coordinate process switches as the main agent. Record the evidence for each switch.
    - Delegate the selected process to its role agent. Follow the delegation instructions below.
    - Reconcile each returned report with the active goal before continuing.

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

       Treat `.writing/assignment.md` as the fixed rhetorical problem and constraints for the run.

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

       Keep supplied text and uncertain claims visible rather than silently normalizing them.

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

**Goal Notation Reference**

    # Goal network format

    The goal network in `.writing/goals.md` is the working representation of the writer's purpose. It connects abstract rhetorical aims to concrete content and process goals. It is hierarchical, can be expanded while composing, and can be regenerated when writing changes the author's understanding.

    ## Network notation

    Use stable goal identifiers, one goal per line, and indentation for parent-child relationships:

    ```markdown
    # Goal network

    ## Active network

    - [G0] Explain the policy change to new team members (kind: content, status: active, parent: none)
      - [G1] Establish why the change matters to their first week (kind: content, status: active, parent: G0)
        - [G2] Open with a concrete first-day scenario (kind: process, status: resolved, parent: G1)
      - [G3] Give one example of the new workflow (kind: content, status: pending, parent: G0)

    ## Goal history

    | Timestamp | Event | Goal | Parent | Rationale | Evidence |
    | --- | --- | --- | --- | --- | --- |
    | 2026-01-15T09:04:00+09:00 | created | G1 | G0 | Make the audience impact explicit. | assignment.md |
    | 2026-01-15T09:18:00+09:00 | regenerated | G0 | none | The opening revealed that the real purpose is adoption, not explanation. | draft.md, reviewer note |
    ```

    Set the history table's timestamp column to the current wall-clock time obtained from the shell at write time, for example `date -Is`; never copy timestamps from examples.

    `kind` may be `content`, `process`, or `criterion`. Use `status` values `pending`, `active`, `blocked`, `resolved`, or `superseded`. Keep a regenerated goal's original ID in history and give the replacement a new ID when its meaning materially changes. A small wording refinement can stay under the same ID, but record it as `developed` in the history.

    ## Update rules

    - Add a history row whenever a goal is created, developed, or regenerated.
    - Keep the immediate parent ID on every goal so the Monitor can pop back after a sub-goal resolves.
    - Put evaluation criteria such as audience fit, claim support, or tone in `criterion` goals when they guide a writing choice.
    - Mark a goal `superseded` rather than deleting it when a new goal replaces it.
    - If a goal depends on an unresolved fact or user decision, mark it `blocked` and name the uncertainty in the trace.

**Trace Schema Reference**

    # Trace JSON Lines schema

    The Monitor writes one JSON object per line to `.writing/trace/process.jsonl`. A line must be valid JSON on its own. The log is append-only so a later reader can reconstruct process switches, goal changes, evidence, and uncertainty without relying on a chat transcript.

    ## Fields

    Every event has these fields:

    | Field | Type | Meaning |
    | --- | --- | --- |
    | `timestamp` | string | ISO 8601 timestamp with a timezone offset, set to the current wall-clock time obtained from the shell at write time, for example `date -Is`. Never copy example timestamps. |
    | `event_type` | string | One of `process_switch`, `goal_created`, `goal_developed`, or `goal_regenerated`. |
    | `responsible_agent` | string | Actor responsible for the decision, such as `monitor`, `planner`, `translator`, `reviewer`, or `user`. |
    | `process` | string | Process that made or owns the decision, such as `planning`, `generate`, `organize`, `goal-setting`, `translating`, `reviewing`, `evaluate`, or `revise`. |
    | `decision` | string | Plain-language decision or action. State what changed or why the process moved. |
    | `evidence` | array | Facts, file paths, draft excerpts, goal identifiers, or observations supporting the decision. Keep entries concrete. |
    | `open_uncertainty` | array | Questions, unsupported claims, unresolved conflicts, or missing information left open after the decision. Use an empty array when none remains. |

    Use these conditional fields when they apply:

    | Field | Type | Meaning |
    | --- | --- | --- |
    | `from_process` | string or null | Process being left for a `process_switch`. Use `null` when starting the loop. |
    | `to_process` | string or null | Process being entered for a `process_switch`. |
    | `goal_id` | string | Goal affected by the event. |
    | `parent_goal_id` | string or null | Immediate parent in the goal network. |
    | `artifacts` | array | Project-relative files read or changed because of the event. |

    `process_switch` entries must include `from_process` and `to_process`. Goal events must include `goal_id` and `parent_goal_id`. Every process switch and every goal creation, development, or regeneration must include `responsible_agent`, `decision`, `evidence`, and `open_uncertainty`.

    ## Example

    ```json
    {"timestamp":"2026-01-15T09:00:00+09:00","event_type":"process_switch","responsible_agent":"monitor","process":"planning","from_process":null,"to_process":"planning","decision":"Explore the audience's likely objection before drafting the opening.","evidence":[".writing/assignment.md: audience is first-year students",".writing/goals.md: G0 has no audience-specific sub-goal"],"open_uncertainty":["Which objection matters most to this audience?"],"goal_id":"G0","parent_goal_id":null,"artifacts":[".writing/assignment.md",".writing/goals.md"]}
    {"timestamp":"2026-01-15T09:04:00+09:00","event_type":"goal_developed","responsible_agent":"planner","process":"goal-setting","decision":"Add a sub-goal to answer the audience's objection with one concrete example.","evidence":["Planner grouped three notes in .writing/memory/audience.md"],"open_uncertainty":["The example still needs a source."],"goal_id":"G1","parent_goal_id":"G0","artifacts":[".writing/goals.md",".writing/memory/audience.md"]}
    ```

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

    Use this skill only for the A5 no-goal-network comparison. Do not use it as the default writing workflow.

    ## `Monitor` responsibilities

    - Keep rhetorical intent, factual authority, final wording, and publication decisions under the user's control.
    - Coordinate process switches and record the evidence for each switch.
    - Reconcile each returned role report with the assignment before continuing.

    ## Read the state first

    Create missing files and directories without overwriting existing content. Do not create or modify `.writing/goals.md`. Treat these files as the externalized task environment and long-term memory:

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

    Treat the assignment as the single implicit objective. Do not use a hierarchical goal to fill missing intent.

    Treat `assignment.md` as the fixed task specification for the run.

    Read the trace field contract below before writing the first entry. Append to `.writing/trace/process.jsonl`; never rewrite or truncate that log.

    ## `Monitor` loop

    At each turn, the `Monitor` must:

    1. Compare the assignment's implicit objective with the current project state and open uncertainty. Choose `Planning`, `Translating`, or `Reviewing` from that comparison. Do not consult or construct a hierarchical goal network.
    2. Before every process switch, append a `process_switch` event naming the responsible process or agent, its decision, its evidence, and open uncertainty. The no-goal-network variant records no goal-created, goal-developed, or goal-regenerated events.
    3. Delegate the selected role using the Delegation section.
    4. For a `Planning` delegation, request problem representation, Generate, and Organize. Do not request Goal-setting or ask the agent to write `goals.md`. If the agent proposes a hierarchical goal, report it as an observation without changing the file.
    5. Re-read changed state and reconcile the role's work with the assignment. Update `draft.md` or `memory/` as appropriate. Keep supplied text and uncertain claims visible.

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

    Use this skill only for the A6 fixed-order comparison. Do not use it as the default writing workflow.

    ## `Monitor` responsibilities

    - Keep rhetorical intent, factual authority, final wording, and publication decisions under the user's control.
    - Coordinate the prescribed order and record the evidence for each process switch.
    - Reconcile each returned role report with the active goal before continuing.

    ## Read the state first

    Create missing files and directories without overwriting existing content. Treat these files as the externalized task environment and long-term memory:

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

    Treat `assignment.md` as the fixed rhetorical problem and constraints for the run.

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

       Keep supplied text and uncertain claims visible.

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

    Follow the repository writing contract for structure, links, claims, and plain English. Before finishing, remove filler, AI-pattern phrasing, vague claims, and unnecessary headings without changing the task's meaning.

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

    Use this skill for the A8 single-context comparison. Work in the session's current project root.

    The `Monitor` is the main agent running this skill. The `Monitor` chooses the next writing process from the project state and open uncertainty. The `Monitor` does not impose a fixed stage sequence.

    ## `Monitor` responsibilities

    - Keep these under the user's control:
      - rhetorical intent
      - factual authority
      - final wording
      - publication decision
    - Coordinate process switches as the main agent. Record the evidence for each switch.
    - Perform the selected process in the host agent's own context. Do not delegate it to a role agent or subagent.
    - Re-read the changed state and reconcile the selected process with the active goal before continuing.

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

       Treat `.writing/assignment.md` as the fixed rhetorical problem and constraints for the run.

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

       Keep supplied text and uncertain claims visible rather than silently normalizing them.

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

    Perform every selected process in the host agent's own context. Before working, read and apply the selected role's skill instructions exactly as a delegated role agent would. Preserve the project root, active goal context, relevant uncertainty, and requested output while working. Use the same process brief as A4: provide the project root, the current goal context (for `Reviewing`, every active goal with its ID plus the parent goal ID; otherwise the active and parent goal IDs), relevant uncertainty, and requested output. Cite the files or draft passages that support decisions. Do not spawn a role agent, subagent, or child `codex exec` process.

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

WritingBench retains five query-specific criteria for each prompt; the evaluator scores each criterion from 1 to 10 and the native score is their unweighted mean. HelloBench retains 5–7 checklist items per prompt; the evaluator scores each item on its five-level scale and the native score is the item mean. DoLoMiTes has no analogous per-prompt native rubric in our committed evaluation, so we report only the common pointwise rubric for that benchmark. Published leaderboard values are not comparable with these scores because we use a shared evaluator and our own outputs.

**Common Pointwise Rubric**

    <!--
    Agentic CogWriter pointwise judge prompt
    Version: pointwise-v1
    FastChat source path: fastchat/llm_judge/data/judge_prompts.jsonl
    FastChat source sha256: fd283293406d024f44c174b094ef48031d0687a4682fd3a56b29b138f80281b6
    FastChat adaptation: single-v1 neutral-judge framing only; the five-dimension rubric is protocol-defined.
    -->
    Please act as an impartial judge of one writing response. Judge the response against the assignment and the supplied context. Do not reward outside research or facts that are not supported by the assignment or supplied context. Judge the response itself, not its condition label, length, or any hidden process.

    Return exactly one valid JSON object. Do not use Markdown fences or add explanation outside the JSON object.
    Return the literal `runtime-verified` marker for `judge_family`; the judge engine replaces that marker with the serving response's mapped family before the scorer writes the protocol record.

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
    FastChat source path: fastchat/llm_judge/data/judge_prompts.jsonl
    FastChat source sha256: fd283293406d024f44c174b094ef48031d0687a4682fd3a56b29b138f80281b6
    FastChat adaptation: pair-v2 position-bias and length-bias controls, adapted to the protocol JSON contract.
    -->
    Please act as an impartial judge comparing two writing responses to the assignment. Choose the response that follows the assignment and answers it better. Consider instruction fulfillment, organization and global coherence, content adequacy and depth, style, voice and audience fit, and factuality and constraint fidelity.

    Compare both responses before deciding. Avoid position bias. The order in which the responses appear must not influence the decision. Do not let response length influence the decision. Do not favor a response because of a name or label. Judge only the assignment and supplied context. Do not reward outside research or facts that are not supported by the assignment or supplied context.

    Return exactly one valid JSON object. Do not use Markdown fences or add explanation outside the JSON object. Choose winner A, B, or tie. Include at least one short exact evidence quote for each response. Each quote must be copied verbatim from the displayed response for that letter or the supplied context. Do not quote the assignment or any other prompt text. Keep every quote no longer than needed to identify the evidence. Write a brief comparison grounded in the rubric.
    Return the literal `runtime-verified` marker for `judge_family`; the judge engine replaces that marker with the serving response's mapped family before the scorer writes the protocol record.

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

Table 8 reports the runtime controls shared across conditions. We hold the generator, output-token budget, network and retrieval policy, approval policy, task input, and final-output requirements fixed across conditions. Each prompt–condition pair is generated in three runs. Primary pairwise evaluation uses the same judge for every condition, presents each pair in both orders, and records presentation disagreements as ties; the cross-family judge is used only for the separate robustness analysis.

##### Runtime lock and isolation.

The runtime was designed to hold information access and host configuration fixed across conditions. Before a scored run, the runner requires explicit model, decoding, budget, timeout, seed, version, plugin-commit, retry, and statistical settings; unresolved values stop execution before a model process is created. Conditions share the same assignment and supplied context, resource limits, and tool policy, while web search, network access, external retrieval, and unprovided sources are disabled. Per-run provider configuration is also isolated from local guidance, and retries reuse the same prompt and policy rather than adding information or budget. These controls implement the study’s equal-information policy and reduce hidden runtime state as a source of condition differences. The runner also supports Claude Code as the harness, but every reported generation run uses Codex CLI.

##### Model roles.

The study uses `gpt-5.6-luna` for generation because the experiment requires high-volume long-form generation across many systems, prompts, and replications; the model is positioned for fast, cost-sensitive workloads within the GPT-5.6 family (OpenAI, 2026b; OpenAI, 2026a). `gpt-5.6-sol` is used as the higher-capability primary evaluator, consistent with its positioning for more demanding professional work (OpenAI, 2026c; OpenAI, 2026a). Medium reasoning effort is held fixed rather than tuned within the reported study. For the primary judge, the first main run inherited the documented medium default, and later runs pin medium explicitly to reproduce the same reasoning level.

##### Compute reporting.

The generator and both judges are hosted closed models whose parameter counts and provider-side accelerator configurations are not disclosed to us, so we cannot report model parameter counts or GPU-hours. Instead, we report the model identifiers and roles, reasoning effort, output-token budget, retry policy, available token accounting, and wall-clock statistics recorded by the harness; these quantify observable consumption rather than provider-side compute. No model weights are trained or fine-tuned in this study.

##### Evaluation controls.

Pairwise outputs are blinded and judged in both presentation orders to reduce known position bias in LLM evaluation (Zheng et al., 2023; Wang et al., 2024). The two orders are treated as repeated measurements of one prompt-level comparison rather than independent samples: a semantic winner is retained only when both orders agree, and any disagreement becomes a tie. The reported primary judge and generator are both from the GPT-5.6 family, which differs from the planned different-family judge design. We therefore report `claude-sonnet-5 medium` separately as a cross-family robustness check rather than pooling it with the confirmatory judge, given evidence that model-family relationships can affect evaluator preferences (Panickssery et al., 2024).

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

The following figure shows the prompt-level pairwise estimates for each benchmark and generation run, including the ablation contrasts. The Holm family of each benchmark contains 24 tests: eight pre-specified contrasts in each of the three generation runs. The contrasts compare <span class="smallcaps">Agentic CogWriter</span> with `Single-pass`, `Staged`, `Task-planning`, `No-goals`, and `Fixed-order`, and `Single-writer` with `Single-pass`, <span class="smallcaps">Agentic CogWriter</span>, and `No-goals`. For <span class="smallcaps">Agentic CogWriter</span> versus `Single-pass`, the descriptive mean win rates across generation runs are 72% on DoLoMiTes, 85.7% on HelloBench, and 84.3% on WritingBench.

Figure 3. Run-level pairwise estimates separate the large system comparisons from the ablations. <span class="smallcaps">Agentic CogWriter</span> is consistently favored over `Single-pass` and `Task-planning` and usually over `Staged`, whereas `No-goals` and `Fixed-order` remain near parity and do not survive the within-benchmark Holm correction. Points show 95% Wilson intervals; filled circles survive correction, open circles do not, and diamonds are descriptive means across generation runs.

## Paired Document-Quality Differences

Table 9 reports paired differences behind Table 3. Each prompt’s three generation runs are averaged per system before differencing, so the prompt is the resampling unit, and the intervals come from 10,000 prompt-level bootstrap resamples.

|  |  |  |  |  |  |
|:---|---:|---:|---:|---:|---:|
|  | **WritingBench** | **WritingBench** | **HelloBench** | **HelloBench** | **DoLoMiTes** |
| **vs.** | **Native** | **Pointwise** | **Native** | **Pointwise** | **Pointwise** |
| `Single-pass` | +0.050 \[+0.039, +0.061\] | +0.190 \[+0.114, +0.267\] | +0.018 \[+0.012, +0.024\] | +0.124 \[+0.032, +0.228\] | +0.036 \[-0.022, +0.095\] |
| `Staged` | +0.045 \[+0.034, +0.057\] | +0.141 \[+0.061, +0.223\] | +0.010 \[+0.003, +0.016\] | +0.008 \[-0.094, +0.131\] | -0.033 \[-0.100, +0.035\] |
| `Task-planning` | +0.026 \[+0.019, +0.034\] | +0.127 \[+0.048, +0.209\] | +0.011 \[+0.005, +0.016\] | +0.043 \[-0.057, +0.157\] | +0.206 \[+0.130, +0.281\] |

Table 9. Paired differences in document quality, <span class="smallcaps">Agentic CogWriter</span> minus the compared system, with 95% bootstrap intervals in brackets. Each prompt’s three generation runs are averaged per system before differencing, and prompts are resampled 10,000 times; positive values favor <span class="smallcaps">Agentic CogWriter</span>, and intervals that exclude zero indicate a difference beyond prompt-level sampling variation.

Table 10 applies the same paired comparison to the two ablations against the external alternatives. Across the 12 WritingBench and HelloBench native and pointwise contrasts with the three alternatives, the interval excludes zero for 10 with <span class="smallcaps">Agentic CogWriter</span>, 11 with `No-goals`, and 7 with `Fixed-order`. Removing explicit goals therefore leaves the full system’s advantage intact, and fixing the process order keeps it on every WritingBench native comparison and on most HelloBench native comparisons; on DoLoMiTes, all three systems separate only from `Task-planning`.

|  |  |  |  |  |  |
|:---|---:|---:|---:|---:|---:|
|  | **WritingBench** | **WritingBench** | **HelloBench** | **HelloBench** | **DoLoMiTes** |
| **vs.** | **Native** | **Pointwise** | **Native** | **Pointwise** | **Pointwise** |
| *`No-goals` minus* | *`No-goals` minus* | *`No-goals` minus* | *`No-goals` minus* | *`No-goals` minus* | *`No-goals` minus* |
| `Single-pass` | +0.043 \[+0.033, +0.054\] | +0.147 \[+0.072, +0.227\] | +0.016 \[+0.010, +0.021\] | +0.211 \[+0.122, +0.312\] | +0.007 \[-0.051, +0.068\] |
| `Staged` | +0.039 \[+0.028, +0.050\] | +0.098 \[+0.011, +0.189\] | +0.007 \[+0.001, +0.014\] | +0.095 \[+0.001, +0.209\] | -0.062 \[-0.127, +0.005\] |
| `Task-planning` | +0.019 \[+0.011, +0.028\] | +0.084 \[+0.000, +0.168\] | +0.008 \[+0.003, +0.014\] | +0.129 \[+0.034, +0.240\] | +0.177 \[+0.103, +0.253\] |
| *`Fixed-order` minus* | *`Fixed-order` minus* | *`Fixed-order` minus* | *`Fixed-order` minus* | *`Fixed-order` minus* | *`Fixed-order` minus* |
| `Single-pass` | +0.049 \[+0.039, +0.059\] | +0.129 \[+0.063, +0.197\] | +0.014 \[+0.008, +0.020\] | +0.171 \[+0.070, +0.283\] | +0.054 \[-0.006, +0.113\] |
| `Staged` | +0.044 \[+0.033, +0.056\] | +0.080 \[-0.004, +0.171\] | +0.006 \[-0.000, +0.013\] | +0.055 \[-0.050, +0.180\] | -0.029 \[-0.091, +0.031\] |
| `Task-planning` | +0.025 \[+0.016, +0.034\] | +0.066 \[-0.014, +0.151\] | +0.007 \[+0.001, +0.012\] | +0.089 \[-0.013, +0.198\] | +0.218 \[+0.139, +0.295\] |

Table 10. Paired differences in document quality, ablation minus external alternative, with 95% bootstrap intervals in brackets, computed as in Table 9. Both ablations keep most of the full system’s advantage over the alternatives on WritingBench and HelloBench.

## Additional Process and Resource Statistics

Table 11 reports output size, delegated invocations, goal events, token accounting, and wall-clock time, each averaged across the three generation runs. For <span class="smallcaps">Agentic CogWriter</span>, a generation run averages 1,101.3 goal-creation events and 1,915.3 goal-development events, while its post-`Reviewing` ledger contains 353.7 entries including 3.7 explicit regeneration proposals.

|  |  |  |  |  |  |  |
|:---|---:|---:|---:|---:|---:|---:|
| **Condition** | **Median**; **words** | **Spawns**; **/run** | **Goals created/**; **developed/regenerated**; **/generation run** | **Output**; **tokens**; **/run** | **Input**; **tokens**; **/run** | **Mean sec.**; **/completed run** |
| `Single-pass` | 1,625 | 0 | 0/0/0 | 4,931 | 13,303 | 53 |
| `Staged` | 1,477 | 0 | 0/0/0 | 10,734 | 21,943 | 88 |
| `Task-planning` | 1,642 | 8.17 | 0/0/0 | 18,313 | 63,812 | 327 |
| <span class="smallcaps">Agentic CogWriter</span> | 1,863 | 3.24 | 1,101.3/1,915.3/2.3 | 13,252 | 47,961 | 331 |
| `No-goals` | 1,847 | 3.01 | 0/0/0 | 9,736 | 40,148 | 276 |
| `Fixed-order` | 1,815 | 3.38 | 288/1,176.7/3.7 | 11,420 | 43,665 | 243 |
| `Single-writer` | 1,159 | 0 | 1,679.3/171.7/0.3 | 15,377 | 31,008 | 120 |

Table 11. Realized process and resource use, averaged across the three generation runs. Goal counts are totals per generation run; spawns, tokens, and seconds are means per run (one system on one prompt); words are medians per generation run, counting each CJK character as one word. The systems differ substantially in delegated invocations and token use, while accepted goal regeneration is rare. These realized differences motivate the output-length and compute-matched sensitivity analyses.

##### Trace processing.

Process paths are read from the `Monitor`’s `process_switch` events in trace order: each event’s destination process is one step, and a run ends once, after its last step (E in Figure 2). Figure 2(a) counts these paths as logged, and Figure 2(b,c) counts step-to-step transitions. For Table 6, immediate repeats of a process are merged (*repeat collapsing*), and when the first delegated role is `Planning` but the first logged switch names a later process, a leading `Planning` step is restored (*leading-`Planning` reconstruction*; 23/39 such runs for <span class="smallcaps">Agentic CogWriter</span>). A path is *cycle-compliant* when the result consists of one or more complete `Planning`–`Translating`–`Reviewing` passes, and returns after `Reviewing` are counted from this observed order. `Fixed-order` enforces its order through its prompt only, and 89.8% of its paths are cycle-compliant; the rest skip or repeat a process, for example `Translating`–`Reviewing` without `Planning`.

## Sensitivity Analyses

### Record-Pooled Sensitivity

Table 12 reports a sensitivity analysis that treats the two presentation records for each prompt as independent observations; the retained disagreements show how much presentation order can affect the descriptive rates. The retained presentation disagreements were 22.7% on WritingBench, 29.4% on HelloBench, and 21.4% on DoLoMiTes across the three generation runs.

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

Table 12. Sensitivity analysis that treats the two presentation orders as separate records. The broad preference pattern remains similar, while presentation-order disagreements show why the headline analysis requires both orders to agree before retaining a winner. Values are mean win rates across generation runs with sample SD in parentheses; this analysis is descriptive.

### Output-Length Sensitivity

Table 13 reports matched-length win rates for our system separately in each of the three generation runs. Within the tighter pre-specified matching band, our system is favored over `Single-pass` in every run, stays above parity in every run against `Staged` and `Fixed-order`, remains above parity against `Task-planning` while narrowing toward parity, and changes direction across runs against `No-goals`. The wider pre-specified band shows the same qualitative pattern. These matching-band results are descriptive sensitivity checks; ties are excluded from the win-rate denominator, and generation runs are reported separately because they reuse the same prompts. The `Single-writer` length-band tests in Section 5.3 instead combine the three runs, so their sign tests take the prompt as the unit: a prompt counts as a win or a loss when its outcomes in the band, averaged across runs, favor one system.

|                 |          |               |                |               |
|:----------------|:---------|--------------:|---------------:|--------------:|
| **Comparison**  | **Band** | **First run** | **Second run** | **Third run** |
| `Single-pass`   | Tighter  |    89.3% (28) |     80.0% (25) |    82.9% (35) |
| `Staged`        | Tighter  |    56.0% (25) |     78.8% (33) |    52.8% (36) |
| `Task-planning` | Tighter  |    63.4% (41) |     57.1% (35) |    51.9% (27) |
| `No-goals`      | Tighter  |    50.0% (36) |     46.7% (45) |    59.5% (42) |
| `Fixed-order`   | Tighter  |    55.9% (34) |     61.5% (39) |    57.1% (42) |
| `Single-pass`   | Wider    |    78.4% (51) |     82.7% (52) |    80.7% (57) |
| `Staged`        | Wider    |    64.0% (50) |     68.8% (64) |    56.1% (57) |
| `Task-planning` | Wider    |    68.4% (57) |     58.5% (65) |    50.9% (55) |
| `No-goals`      | Wider    |    55.9% (68) |     45.7% (70) |    47.8% (69) |
| `Fixed-order`   | Wider    |    63.1% (65) |     59.4% (69) |    53.4% (73) |

Table 13. Matched-length win rates for our system in each of the three generation runs, with non-tied comparisons (the denominator) in parentheses. The tighter and wider pre-specified bands keep pairs whose longer output is at most 5% and 10% longer than the shorter one. A rate above parity favors our system. Reporting runs separately preserves the repeated-run design because the same prompts are reused across runs.

### Compute-Stratified Sensitivity

Compute matching asks whether the pairwise direction persists when the compared systems use similar realized output-plus-reasoning token budgets. Table 14 reports outcomes within the pre-specified 1.25`x` and 1.50`x` matching bands and across descriptive ratio bins. Because realized compute is determined by execution, this analysis is a sensitivity check rather than a causal adjustment. Each row combines the three generation runs, so the sign tests take the prompt as the unit, as in the `Single-writer` length-band tests.

|  |  |  |  |  |
|:---|:---|---:|---:|---:|
| Contrast | Band or bin | W/L/T | Rate | `p` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Staged` | within 1.25 | 197/66/98 | 74.9% | `6.78 x 10^-10` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Staged` | within 1.50 | 281/114/168 | 71.1% | `3.23 x 10^-10` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Task-planning` | within 1.25 | 163/63/78 | 72.1% | `1.93 x 10^-8` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Task-planning` | within 1.50 | 276/128/140 | 68.3% | `4.62 x 10^-9` |
| `Single-writer` vs. <span class="smallcaps">Agentic CogWriter</span> | within 1.25 | 87/267/83 | 24.6% | `1.97 x 10^-18` |
| `Single-writer` vs. <span class="smallcaps">Agentic CogWriter</span> | within 1.50 | 140/404/140 | 25.7% | `6.67 x 10^-19` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Single-pass` | within 1.25 | 0/0/0 | <span style="color: nagray">N/A</span> | <span style="color: nagray">N/A</span> |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Single-pass` | within 1.50 | 13/6/3 | 68.4% | `0.2101` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Staged` | 0.00–0.50 | 1/0/0 | 100.0% | `1` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Staged` | 0.50–0.67 | 4/4/3 | 50.0% | `1` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Staged` | 0.67–0.80 | 13/12/12 | 52.0% | `0.8388` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Staged` | 0.80–0.91 | 42/10/21 | 80.8% | `3.85 x 10^-5` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Staged` | 0.91–0.95 | 21/7/3 | 75.0% | `0.0059` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Staged` | 0.95–1.05 | 49/20/21 | 71.0% | `0.0019` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Staged` | 1.05–1.10 | 23/6/20 | 79.3% | `0.0037` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Staged` | 1.10–1.25 | 62/23/33 | 72.9% | `1.94 x 10^-4` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Staged` | 1.25–1.50 | 71/36/58 | 66.4% | `5.24 x 10^-4` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Staged` | 1.50–2.00 | 95/57/53 | 62.5% | `6.41 x 10^-4` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Staged` | 2.00+ | 38/29/39 | 56.7% | `0.4011` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Task-planning` | 0.00–0.50 | 44/26/23 | 62.9% | `0.0365` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Task-planning` | 0.50–0.67 | 119/48/55 | 71.3% | `8.46 x 10^-8` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Task-planning` | 0.67–0.80 | 99/58/54 | 63.1% | `0.0045` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Task-planning` | 0.80–0.91 | 69/25/34 | 73.4% | `8.22 x 10^-5` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Task-planning` | 0.91–0.95 | 22/11/11 | 66.7% | `0.0801` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Task-planning` | 0.95–1.05 | 33/16/16 | 67.3% | `0.0226` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Task-planning` | 1.05–1.10 | 13/5/5 | 72.2% | `0.1185` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Task-planning` | 1.10–1.25 | 26/6/12 | 81.2% | `9.12 x 10^-4` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Task-planning` | 1.25–1.50 | 14/7/8 | 66.7% | `0.1892` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Task-planning` | 1.50–2.00 | 7/3/5 | 70.0% | `0.3438` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Task-planning` | 2.00+ | 1/1/2 | 50.0% | `1` |
| `Single-writer` vs. <span class="smallcaps">Agentic CogWriter</span> | 0.00–0.50 | 1/5/0 | 16.7% | `0.2188` |
| `Single-writer` vs. <span class="smallcaps">Agentic CogWriter</span> | 0.50–0.67 | 9/12/9 | 42.9% | `0.5034` |
| `Single-writer` vs. <span class="smallcaps">Agentic CogWriter</span> | 0.67–0.80 | 15/43/20 | 25.9% | `0.001` |
| `Single-writer` vs. <span class="smallcaps">Agentic CogWriter</span> | 0.80–0.91 | 19/62/17 | 23.5% | `9.10 x 10^-6` |
| `Single-writer` vs. <span class="smallcaps">Agentic CogWriter</span> | 0.91–0.95 | 12/20/8 | 37.5% | `0.2005` |
| `Single-writer` vs. <span class="smallcaps">Agentic CogWriter</span> | 0.95–1.05 | 25/69/22 | 26.6% | `4.77 x 10^-5` |
| `Single-writer` vs. <span class="smallcaps">Agentic CogWriter</span> | 1.05–1.10 | 8/39/9 | 17.0% | `8.96 x 10^-6` |
| `Single-writer` vs. <span class="smallcaps">Agentic CogWriter</span> | 1.10–1.25 | 23/77/27 | 23.0% | `1.62 x 10^-7` |
| `Single-writer` vs. <span class="smallcaps">Agentic CogWriter</span> | 1.25–1.50 | 38/94/37 | 28.8% | `2.02 x 10^-6` |
| `Single-writer` vs. <span class="smallcaps">Agentic CogWriter</span> | 1.50–2.00 | 24/68/25 | 26.1% | `6.49 x 10^-5` |
| `Single-writer` vs. <span class="smallcaps">Agentic CogWriter</span> | 2.00+ | 7/13/6 | 35.0% | `0.3593` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Single-pass` | 1.25–1.50 | 13/6/3 | 68.4% | `0.2101` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Single-pass` | 1.50–2.00 | 91/15/17 | 85.8% | `4.47 x 10^-9` |
| <span class="smallcaps">Agentic CogWriter</span> vs. `Single-pass` | 2.00+ | 464/114/150 | 80.3% | `1.82 x 10^-32` |

Table 14. Compute-matched pairwise outcomes. Ratios divide the first-named system’s output-plus-reasoning tokens by the second’s; the 1.25 and 1.50 bands keep pairs whose larger-to-smaller ratio is at most that value. Within the 1.25 band, <span class="smallcaps">Agentic CogWriter</span> remains favored over `Staged` and `Task-planning`; no pairs with `Single-pass` fall there (N/A). W/L/T counts pairs across the three runs; unadjusted sign-test `p`-values count prompts and are not confirmatory.

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

Table 15. Exploratory comparison of `Single-context` with matched primary-condition outputs. In its single generation run, `Single-context` does not show a reliable difference from <span class="smallcaps">Agentic CogWriter</span>, so separate subagent contexts alone are not isolated as the source of the full system’s advantage. Wilson intervals are descriptive and sign-test `p`-values are unadjusted.

|  |  |  |  |
|:---|---:|---:|---:|
| Metric | `Single-pass` | <span class="smallcaps">Agentic CogWriter</span> | `Single-context` |
| Completed | 289/300 | 293/300 | 300/300 |
| Output-plus-reasoning tokens per run | 4,874 | 13,374 | 14,497 |
| Wall-clock seconds per completed run | 61 | 426 | 123 |
| Goals created/developed/regenerated | 0/0/0 | 1,068/1,864/1 | 1,191/971/0 |
| Ledger entries | 0 | 347 | 321 |
| Ledger entries with proposal | 0 | 3 | 0 |
| Spawns per attempted run | 0 | 3.22 | 0 |

Table 16. Process and resource profiles for the matched `Single-pass`, <span class="smallcaps">Agentic CogWriter</span>, and `Single-context` runs. `Single-context` preserves the process loop and shared state without separate subagent contexts, making it a narrower execution check than `Single-writer`.

### Cross-Family Judge Robustness

Table 17 reports benchmark-level results for three cross-family robustness contrasts involving our system. Within each contrast, summing W/L/T counts over the three benchmarks gives 67/44/171 versus `Single-pass`, 76/25/184 versus `Task-planning`, and 39/27/221 versus `No-goals`. The corresponding Wilson intervals are 51.06%–68.97%, 66.01%–82.64%, and 47.05%–70.13%. Across all three selected contrasts and benchmarks, the judge yields a non-tied order-consistent outcome on 32.6% of 854 eligible pairs, with 182/96/576 W/L/T; 395/854 prompt-level outcomes agree with the same-family judge.

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

Table 17. Cross-family judge robustness using `claude-sonnet-5 medium`. Within each selected contrast, wins, losses, and ties are summed over benchmarks before computing the win rate; all three contrasts favor our system, but 3 of 9 benchmark-level comparisons reverse relative to the primary judge and many outcomes are ties. Commit is the fraction of eligible pairs with a non-tied cross-family outcome; Agreement is the fraction whose order-consistent outcome matches the primary judge.

## Consensus-Writing Evaluation on Habermas Machine Data

We additionally evaluate the writing systems on ten short consensus-writing tasks constructed from the Habermas Machine data (Tessler et al., 2024). Each task provides one deliberation question and the five participants’ original opinions, and asks the system to write a statement the group could endorse. The ten tasks are drawn from the `OOD_TEST` split after requiring complete, distinct participant opinions and disagreement ratings on both sides of the scale midpoint. Across eight conditions, this produces 80 attempted runs; 78 complete successfully. Table 18 summarizes pointwise quality and the available process statistics.

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

Table 18. Additional consensus-writing evaluation on ten tasks derived from Habermas Machine data. Unlike the long-form benchmarks, <span class="smallcaps">Agentic CogWriter</span> does not achieve the highest pointwise score: `Single-pass` and `Staged` are stronger in this short consensus-writing setting. The result shows that the advantage observed on the long-form benchmarks does not automatically transfer to a substantially shorter writing task; 78 of 80 attempted runs completed.

`Exploratory-1` is the exploratory CogWriter-style (Wan et al., 2025) baseline, with initial planning, immediate plan revision, parallel segment generation, and length review without a goal network; `Exploratory-2` is the exploratory STORM-style (Shao et al., 2024) baseline, with perspective discovery, simulated question answering, outlining, per-section drafting, and polishing without retrieval. On these short consensus-writing tasks, <span class="smallcaps">Agentic CogWriter</span> does not achieve the highest pointwise composite; in particular, it scores below `Single-pass` and `Staged`. Our system and `Fixed-order` record 0 and 0 regeneration events, respectively; their ledgers contain 15/0 and 11/0 no/proposal outcomes, respectively.

## References

Yushi Bai, Jiajie Zhang, Xin Lv, Linzhi Zheng, Siqi Zhu, Lei Hou, Yuxiao Dong, Jie Tang, and Juanzi Li. 2025. LongWriter: Unleashing 10,000+ word generation from long context LLMs. In *International Conference on Learning Representations*, volume 2025, pages 36528–36546.

Dallas Card, Peter Henderson, Urvashi Khandelwal, Robin Jia, Kyle Mahowald, and Dan Jurafsky. 2020. [With little power comes great responsibility](https://doi.org/10.18653/v1/2020.emnlp-main.745). In *Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing (EMNLP)*, pages 9263–9274. Association for Computational Linguistics.

W. J. Dixon and A. M. Mood. 1946. [The statistical sign test](https://doi.org/10.1080/01621459.1946.10501898). *Journal of the American Statistical Association*, 41(236):557–566.

Wanyu Du, Vipul Raheja, Dhruv Kumar, Zae Myung Kim, Melissa Lopez, and Dongyeop Kang. 2022. [Understanding iterative revision from human-written text](https://doi.org/10.18653/v1/2022.acl-long.250). In *Proceedings of the 60th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)*, pages 3573–3590. Association for Computational Linguistics.

Yann Dubois, Percy Liang, and Tatsunori Hashimoto. 2024. [Length-controlled AlpacaEval: A simple debiasing of automatic evaluators](https://openreview.net/forum?id=CybBmzWBX0). In *First Conference on Language Modeling*.

Bradley Efron. 1979. [Bootstrap methods: Another look at the jackknife](https://doi.org/10.1214/aos/1176344552). *The Annals of Statistics*, 7(1):1–26.

Linda Flower and John R Hayes. 1981. [A cognitive process theory of writing](https://doi.org/10.58680/ccc198115885). *College Composition & Communication*, 32(4):365–387.

Adam Fourney, Gagan Bansal, Hussein Mozannar, Cheng Tan, Eduardo Salinas, Erkang Zhu, Friederike Niedtner, Grace Proebsting, Griffin Bassman, Jack Gerrits, Jacob Alber, Peter Chang, Ricky Loynd, Robert West, Victor Dibia, Ahmed Awadallah, Ece Kamar, Rafah Hosn, and Saleema Amershi. 2024. [Magentic-One: A generalist multi-agent system for solving complex tasks](https://arxiv.org/abs/2411.04468). *arXiv preprint arXiv:2411.04468*.

Katy Gero, Alex Calderwood, Charlotte Li, and Lydia Chilton. 2022. [A design space for writing support tools using a cognitive process model of writing](https://doi.org/10.18653/v1/2022.in2writing-1.2). In *Proceedings of the First Workshop on Intelligent and Interactive Writing Assistants (In2Writing 2022)*, pages 11–24. Association for Computational Linguistics.

John R Hayes. 1996. A new framework for understanding cognition and affect in writing. In C. Michael Levy and Sarah Ransdell, editors, *The Science of Writing: Theories, Methods, Individual Differences, and Applications*, pages 1–27. Lawrence Erlbaum Associates, Mahwah, NJ.

John R Hayes. 2012. [Modeling and remodeling writing](https://doi.org/10.1177/0741088312451260). *Written Communication*, 29(3):369–388.

Sture Holm. 1979. [A simple sequentially rejective multiple test procedure](https://www.jstor.org/stable/4615733). *Scandinavian Journal of Statistics*, 6(2):65–70.

Sirui Hong, Mingchen Zhuge, Jonathan Chen, Xiawu Zheng, Yuheng Cheng, Ceyao Zhang, Jinlin Wang, Zili Wang, Steven Ka Shing Yau, Zijuan Lin, Liyang Zhou, Chenyu Ran, Lingfeng Xiao, Chenglin Wu, and Jürgen Schmidhuber. 2024. [MetaGPT: Meta programming for a multi-agent collaborative framework](https://openreview.net/forum?id=VtmBAGCN7o). In *The Twelfth International Conference on Learning Representations*.

Fantine Huot, Reinald Kim Amplayo, Jennimaria Palomaki, Alice Shoshana Jakobovits, Elizabeth Clark, and Mirella Lapata. 2025. [Agents’ Room: Narrative generation through multi-step collaboration](https://openreview.net/forum?id=HfWcFs7XLR). In *The Thirteenth International Conference on Learning Representations*.

Dawei Li, Renliang Sun, Yue Huang, Ming Zhong, Bohan Jiang, Jiawei Han, Xiangliang Zhang, Wei Wang, and Huan Liu. 2026. [Preference leakage: A contamination problem in LLM-as-a-judge](https://openreview.net/forum?id=grIvSXVJ65). In *International Conference on Learning Representations*, volume 2026, pages 60486–60511.

Chris Lu, Cong Lu, Robert Tjarko Lange, Jakob Foerster, Jeff Clune, and David Ha. 2024. [The AI Scientist: Towards fully automated open-ended scientific discovery](https://doi.org/10.48550/arXiv.2408.06292). *arXiv preprint arXiv:2408.06292*.

Junyu Luo, Weizhi Zhang, Ye Yuan, Yusheng Zhao, Junwei Yang, Yiyang Gu, et al. 2025. [Large language model agent: A survey on methodology, applications and challenges](https://doi.org/10.48550/arXiv.2503.21460). *arXiv preprint arXiv:2503.21460*.

Aman Madaan, Niket Tandon, Prakhar Gupta, Skyler Hallinan, Luyu Gao, Sarah Wiegreffe, Uri Alon, Nouha Dziri, Shrimai Prabhumoye, Yiming Yang, et al. 2023. [Self-Refine: Iterative refinement with self-feedback](https://doi.org/10.52202/075280-2019). In *Advances in Neural Information Processing Systems*, volume 36, pages 46534–46594.

Chaitanya Malaviya, Priyanka Agrawal, Kuzman Ganchev, Pranesh Srinivasan, Fantine Huot, Jonathan Berant, Mark Yatskar, Dipanjan Das, Mirella Lapata, and Chris Alberti. 2025. [Dolomites: Domain-specific long-form methodical tasks](https://doi.org/10.1162/tacl_a_00727). *Transactions of the Association for Computational Linguistics*, 13:1–29.

OpenAI. 2026. GPT-5.6: Frontier intelligence that scales with your ambition. <https://openai.com/index/gpt-5-6/>. Accessed 2026-10-05.

OpenAI. 2026. GPT-5.6 Luna model. <https://developers.openai.com/api/docs/models/gpt-5.6-luna>. Accessed 2026-10-05.

OpenAI. 2026. GPT-5.6 Sol model. <https://developers.openai.com/api/docs/models/gpt-5.6-sol>. Accessed 2026-10-05.

Arjun Panickssery, Samuel R. Bowman, and Shi Feng. 2024. [LLM evaluators recognize and favor their own generations](https://doi.org/10.52202/079017-2197). In *Advances in Neural Information Processing Systems*, volume 37, pages 68772–68802.

Haoran Que, Feiyu Duan, Liqun He, Yutao Mou, Wangchunshu Zhou, Jiaheng Liu, Wenge Rong, Zekun Moore Wang, Jian Yang, Ge Zhang, et al. 2024. [HelloBench: Evaluating long text generation capabilities of large language models](https://doi.org/10.48550/arXiv.2409.16191). *arXiv preprint arXiv:2409.16191*.

D Gordon Rohman. 1965. [Pre-writing: The stage of discovery in the writing process](https://doi.org/10.2307/354885). *College Composition and Communication*, 16(2):106–112.

Timo Schick, Jane Dwivedi-Yu, Zhengbao Jiang, Fabio Petroni, Patrick Lewis, Gautier Izacard, Qingfei You, Christoforos Nalmpantis, Edouard Grave, and Sebastian Riedel. 2023. [PEER: A collaborative language model](https://openreview.net/forum?id=KbYevcLjnc). In *The Eleventh International Conference on Learning Representations*.

Samuel Schmidgall, Yusheng Su, Ze Wang, Ximeng Sun, Jialian Wu, Xiaodong Yu, Jiang Liu, Michael Moor, Zicheng Liu, and Emad Barsoum. 2025. [Agent Laboratory: Using LLM agents as research assistants](https://doi.org/10.18653/v1/2025.findings-emnlp.320). In *Findings of the Association for Computational Linguistics: EMNLP 2025*, pages 5977–6043. Association for Computational Linguistics.

Yijia Shao, Yucheng Jiang, Theodore Kanell, Peter Xu, Omar Khattab, and Monica Lam. 2024. [Assisting in writing Wikipedia-like articles from scratch with large language models](https://doi.org/10.18653/v1/2024.naacl-long.347). In *Proceedings of the 2024 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies (Volume 1: Long Papers)*, pages 6252–6278. Association for Computational Linguistics.

Noah Shinn, Federico Cassano, Ashwin Gopinath, Karthik Narasimhan, and Shunyu Yao. 2023. [Reflexion: Language agents with verbal reinforcement learning](https://doi.org/10.52202/075280-0377). In *Advances in Neural Information Processing Systems*, volume 36, pages 8634–8652.

Theodore Sumers, Shunyu Yao, Karthik R Narasimhan, and Thomas L. Griffiths. 2024. [Cognitive architectures for language agents](https://openreview.net/forum?id=1i6ZCvflQJ). *Transactions on Machine Learning Research*. Survey Certification, Featured Certification.

Zechen Sun, Yuyang Sun, Zecheng Tang, Juntao Li, Wenpeng Hu, Wenliang Chen, Zhunchen Luo, Guotong Geng, and Min Zhang. 2026. [IS-CoT: Breaking the long-form generation collapse via interleaved structural thinking](https://doi.org/10.18653/v1/2026.acl-long.911). In *Proceedings of the 64th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)*, pages 19874–19887. Association for Computational Linguistics.

Haochen Tan, Zhijiang Guo, Zhan Shi, Lu Xu, Zhili Liu, Yunlong Feng, Xiaoguang Li, Yasheng Wang, Lifeng Shang, Qun Liu, and Linqi Song. 2024. [ProxyQA: An alternative framework for evaluating long-form text generation with large language models](https://doi.org/10.18653/v1/2024.acl-long.368). In *Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)*, pages 6806–6827. Association for Computational Linguistics.

Michael Henry Tessler, Michiel A. Bakker, Daniel Jarrett, Hannah Sheahan, Martin J. Chadwick, Raphael Koster, Georgina Evans, Lucy Campbell-Gillingham, Tantum Collins, David C. Parkes, Matthew Botvinick, and Christopher Summerfield. 2024. [AI can help humans find common ground in democratic deliberation](https://doi.org/10.1126/science.adq2852). *Science*, 386(6719):eadq2852.

Kaiyang Wan, Honglin Mu, Rui Hao, Haoran Luo, Tianle Gu, and Xiuying Chen. 2025. [A cognitive writing perspective for constrained long-form text generation](https://doi.org/10.18653/v1/2025.findings-acl.511). In *Findings of the Association for Computational Linguistics: ACL 2025*, pages 9832–9844. Association for Computational Linguistics.

Peiyi Wang, Lei Li, Liang Chen, Zefan Cai, Dawei Zhu, Binghuai Lin, Yunbo Cao, Lingpeng Kong, Qi Liu, Tianyu Liu, and Zhifang Sui. 2024. [Large language models are not fair evaluators](https://doi.org/10.18653/v1/2024.acl-long.511). In *Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)*, pages 9440–9450. Association for Computational Linguistics.

Xingyao Wang, Boxuan Li, Yufan Song, Frank F. Xu, Xiangru Tang, Mingchen Zhuge, Jiayi Pan, Yueqi Song, Bowen Li, Jaskirat Singh, et al. 2025. [OpenHands: An open platform for AI software developers as generalist agents](https://openreview.net/forum?id=OJd3ayDDoF). In *International Conference on Learning Representations*, volume 2025, pages 65882–65919.

Edwin B. Wilson. 1927. [Probable inference, the law of succession, and statistical inference](https://doi.org/10.1080/01621459.1927.10502953). *Journal of the American Statistical Association*, 22(158):209–212.

Qingyun Wu, Gagan Bansal, Jieyu Zhang, Yiran Wu, Beibin Li, Erkang Zhu, Li Jiang, Xiaoyun Zhang, Shaokun Zhang, Jiale Liu, Ahmed Hassan Awadallah, Ryen W. White, Doug Burger, and Chi Wang. 2024. [AutoGen: Enabling next-gen LLM applications via multi-agent conversations](https://openreview.net/forum?id=BAakY1hNKS). In *First Conference on Language Modeling*.

Yuhao Wu, Yushi Bai, Zhiqiang Hu, Juanzi Li, and Roy Ka-Wei Lee. 2026. [SuperWriter: Reflection-driven long-form generation with large language models](https://doi.org/10.18653/v1/2026.findings-acl.428). In *Findings of the Association for Computational Linguistics: ACL 2026*, pages 8790–8812. Association for Computational Linguistics.

Yuning Wu, Jiahao Mei, Ming Yan, Chenliang Li, Shaopeng Lai, Yuran Ren, Zijia Wang, Ji Zhang, Mengyue Wu, Qin Jin, et al. 2025. [WritingBench: A comprehensive benchmark for generative writing](https://doi.org/10.52202/085713-1737). In *Advances in Neural Information Processing Systems*, volume 38, pages 58018–58051.

Ruibin Xiong, Yimeng Chen, Dmitrii Khizbullin, Mingchen Zhuge, and Jürgen Schmidhuber. 2025. [Beyond outlining: Heterogeneous recursive planning for adaptive long-form writing with language models](https://doi.org/10.18653/v1/2025.emnlp-main.1254). In *Proceedings of the 2025 Conference on Empirical Methods in Natural Language Processing*, pages 24689–24725. Association for Computational Linguistics.

John Yang, Carlos E. Jimenez, Alexander Wettig, Kilian Lieret, Shunyu Yao, Karthik R. Narasimhan, and Ofir Press. 2024. [SWE-agent: Agent-computer interfaces enable automated software engineering](https://doi.org/10.52202/079017-1601). In *Advances in Neural Information Processing Systems*, volume 37, pages 50528–50652.

Kevin Yang, Dan Klein, Nanyun Peng, and Yuandong Tian. 2023. [DOC: Improving long story coherence with detailed outline control](https://doi.org/10.18653/v1/2023.acl-long.190). In *Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)*, pages 3378–3465. Association for Computational Linguistics.

Kevin Yang, Yuandong Tian, Nanyun Peng, and Dan Klein. 2022. [Re3: Generating longer stories with recursive reprompting and revision](https://doi.org/10.18653/v1/2022.emnlp-main.296). In *Proceedings of the 2022 Conference on Empirical Methods in Natural Language Processing*, pages 4393–4479. Association for Computational Linguistics.

Lili Yao, Nanyun Peng, Ralph Weischedel, Kevin Knight, Dongyan Zhao, and Rui Yan. 2019. [Plan-and-write: Towards better automatic storytelling](https://doi.org/10.1609/aaai.v33i01.33017378). In *Proceedings of the AAAI Conference on Artificial Intelligence*, volume 33, pages 7378–7385. AAAI.

Shunyu Yao, Jeffrey Zhao, Dian Yu, Nan Du, Izhak Shafran, Karthik R Narasimhan, and Yuan Cao. 2023. [ReAct: Synergizing reasoning and acting in language models](https://openreview.net/forum?id=WE_vluYUL-X). In *The Eleventh International Conference on Learning Representations*.

Lianmin Zheng, Wei-Lin Chiang, Ying Sheng, Siyuan Zhuang, Zhanghao Wu, Yonghao Zhuang, Zi Lin, Zhuohan Li, Dacheng Li, Eric P. Xing, Hao Zhang, Joseph E. Gonzalez, and Ion Stoica. 2023. [Judging LLM-as-a-judge with MT-Bench and Chatbot Arena](https://doi.org/10.52202/075280-2020). In *Advances in Neural Information Processing Systems*, volume 36, pages 46595–46623.

Wangchunshu Zhou, Yuchen Eleanor Jiang, Peng Cui, Tiannan Wang, Zhenxin Xiao, Yifan Hou, Ryan Cotterell, and Mrinmaya Sachan. 2023. [RecurrentGPT: Interactive generation of (arbitrarily) long text](https://doi.org/10.48550/arXiv.2305.13304). *arXiv preprint arXiv:2305.13304*.

[^1]: See Appendix A for the exact selection rule, sample sizes, and sensitivity analysis.

[^2]: We use Luna, which OpenAI positions for fast, cost-sensitive workloads, for high-volume long-form generation and the higher-capability tier, Sol, for evaluation; the shared model family motivates the cross-family check (OpenAI, 2026b; OpenAI, 2026c; OpenAI, 2026a).

[^3]: See Appendix A for the complete prompts and Appendix B for the runtime settings.

[^4]: See Appendix A for evaluation procedures and prompts.

[^5]: See Appendix C for the generation-run estimates, Wilson intervals (Wilson, 1927), and corrected test decisions.

[^6]: See Appendix D for the paired differences and intervals.

[^7]: See Appendix C for run-level intervals and corrected results.

[^8]: Appendix F reports the resource-matched and cross-family sensitivity analyses: the former largely preserve the direction, whereas cross-family rescoring is less stable, including a WritingBench reversal against `Single-pass`.

[^9]: See Appendix D for these paired differences.

[^10]: See Appendix F for the benchmark-level diagnostic and the remaining execution differences.

[^11]: See Appendix E for process, goal, and resource statistics.

[^12]: See Appendix G for the consensus-writing results.

[^13]: See Appendix A for the power calculation.

[^14]: See Appendix E for the trace classification.
