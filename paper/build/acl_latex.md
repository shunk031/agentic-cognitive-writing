## Revisiting the Cognitive Process Theory of Writing for AI Agents: Process-Level Control for Long-Form Writing

Anonymous ACL submission

## Abstract

AI agents increasingly produce long-form documents as part of multi-step knowledge work, but it remains unclear how the writing process itself should be organized. Existing systems typically advance an outline, a task graph, or a fixed sequence of stages. Drawing on cognitive process theory, we propose Agentic CogWriter, an architecture that maintains an evolving draft and writing state while a `Monitor` repeatedly chooses whether to plan, draft, or review and delegates that activity to a specialist. We evaluate the architecture on deliberately demanding subsets of established long-form writing benchmarks spanning general-purpose writing, long-context generation, and structured expert documents. Independent rubric-based scoring ranks Agentic CogWriter highest on two of the three benchmark types. When a judge directly compares two responses to the same prompt, Agentic CogWriter is preferred to one-shot generation, a fixed planning–drafting–revision workflow, and adaptive task planning. Pre-specified cellwise tests yield no Holm-surviving difference after removing the explicit goal network or fixing process order, while a post-hoc prompt-clustered analysis finds a small preference for adaptive ordering and no significant pooled goal-network effect. Trace analysis further shows that most runs follow a single planning–drafting–reviewing cycle, consistent with adaptive ordering making only a modest contribution. Together, the results support process-organized writing as a promising agent architecture while leaving the main source of its advantage open.

## Introduction

Large language model agents increasingly combine reasoning, tool use, memory, and delegation to carry out multi-step knowledge work (Yao et al., 2023; Shinn et al., 2023; Sumers et al., 2024). Writing is becoming part of that broader workflow: intelligent writing assistants support planning and revision (Gero et al., 2022), while autonomous research systems culminate in reports or scientific manuscripts (Schmidgall et al., 2025; Lu et al., 2024). These settings make long-form writing more than a final decoding step. An agent must decide how to organize a document, turn partial plans into prose, inspect what has been written, and revise when the document no longer serves the task.

Figure 1. Overview of Agentic CogWriter. The input and completed document are distinguished from the agent roles and shared writing state. The `Monitor` reads the persistent state, selects one writing process, delegates it to the corresponding specialist, and observes the updated state before either continuing or terminating after review.

Existing long-form generation systems address this coordination problem by imposing structure on generation (Yao et al., 2019; Yang et al., 2022; Shao et al., 2024; Bai et al., 2025; Xiong et al., 2025; Sun et al., 2026). Some build an outline before drafting, some generate section by section, some recursively decompose a document into tasks, and others interleave structural reasoning with text generation. These approaches have made long-form generation substantially more reliable, but they usually define progress in terms of *content units* such as sections, passages, or task nodes, or in terms of a prescribed sequence of stages. A different architectural question remains comparatively underexplored: *should an agent decide which kind of writing process is needed next?*

The cognitive process theory of writing (Flower and Hayes, 1981; Hayes, 1996; Hayes, 2012) provides a useful abstraction for this question. Flower and Hayes (1981) characterize writing as the coordination of `Planning`, `Translating`, and `Reviewing`, with a `Monitor` deciding which process to invoke as the document develops. The theory therefore suggests an agent architecture in which the unit of control is not the next section or task node, but the next writing process.

Building on Flower and Hayes (1981), we propose Agentic CogWriter, shown in Figure 1. It is a long-form writing architecture implemented on a coding-agent-style harness with persistent state and subagent delegation. A top-level `Monitor` observes the evolving draft, goals, and process history; chooses whether the next activity should be planning, drafting, or reviewing; delegates that activity to a specialized role agent; and then receives the updated state. The resulting writing trajectory is determined online rather than fixed in advance, which is the sense in which the system is *agentic*.

We evaluate Agentic CogWriter on deliberately demanding subsets of complementary long-form writing benchmarks that cover broad instruction-driven writing, sustained long-context generation, and methodical expert-document production (Wu et al., 2026b; Que et al., 2024; Malaviya et al., 2025). The selection prioritizes the longest inputs and, where stated, the longest requested outputs, independently of system outputs, while all systems share the same generator and information policy. Independent scoring and direct same-prompt comparisons show that Agentic CogWriter is competitive across the benchmark types and is preferred to one-shot generation, a fixed writing pipeline, and adaptive task planning. The pre-specified cellwise tests detect no Holm-surviving loss from removing the goal network or fixing process order, while a post-hoc pooled analysis finds a small preference for adaptive ordering and no significant pooled effect of the goal network; together with traces showing that the `Monitor` usually follows a planning–drafting–reviewing cycle, these results bound both components as modest contributors rather than explanations for the much larger baseline gaps.

Our contributions are threefold. First, we formulate long-form writing for general-purpose agents as a process-level architecture problem and introduce Agentic CogWriter, a concrete realization on a coding-agent harness. Second, we compare that architecture with one-shot, fixed-stage, and adaptive task-planning organizations across complementary long-form benchmarks using direct comparisons over three generation runs and pre-specified statistical tests. Third, we use ablations and execution traces to bound the contributions of explicit goal bookkeeping and adaptive process ordering and to characterize how the writing loop behaves, providing empirical constraints for future writing-agent design rather than attributing the result to cognitive theory by analogy.

## Related Work

##### Language agents and document production.

Language-agent research studies architectures that interleave reasoning with actions, tools, memory, and feedback (Yao et al., 2023; Shinn et al., 2023; Sumers et al., 2024), while writing-support systems assist planning, drafting, and revision (Gero et al., 2022). Agentic research systems increasingly connect these capabilities to report or paper generation after literature review and experimentation (Schmidgall et al., 2025; Lu et al., 2024). Our setting focuses on the internal organization of that writing stage when a general-purpose agent is responsible for producing the document.

##### Long-form generation and planning.

Long-form generation becomes harder to control and evaluate as outputs grow in length (Tan et al., 2024; Wu et al., 2026a), motivating explicit planning and decomposition (Yao et al., 2019; Yang et al., 2022; Shao et al., 2024; Bai et al., 2025; Wan et al., 2025; Xiong et al., 2025; Sun et al., 2026). Plan-and-Write (Yao et al., 2019), Re`^3` (Yang et al., 2022), STORM (Shao et al., 2024), and LongWriter (Bai et al., 2025) organize generation around plans, revisions, sections, or manageable content units; CogWriter (Wan et al., 2025), WriteHERE (Xiong et al., 2025), IS-CoT (Sun et al., 2026), and SuperWriter (Wu et al., 2026a) make that structure or refinement increasingly adaptive. The central distinction in our work is the unit selected during execution: these systems primarily advance content, plan, task, or refinement structure, whereas Agentic CogWriter selects among writing processes.

##### Iteration and cognitive models of writing.

Computational work has studied iterative writing through repeated model feedback and through models of human revision (Madaan et al., 2023; Du et al., 2022). Cognitive writing research offers a complementary process decomposition: Flower and Hayes (1981) distinguish `Planning`, `Translating`, and `Reviewing`, and Gero et al. (2022) use these processes to organize writing-support systems; CogWriter (Wan et al., 2025) likewise draws on cognitive writing theory to structure planning, generation, and revision. Agentic CogWriter instead makes the writing process itself the online action selected by the agent and tests that choice through matched alternatives, ablations, and traces. Table 1 summarizes this distinction.

| **Method** | **Persistent state** | **Unit advanced** | **Next-step rule** | **Adaptive** | **Evolving structure** | **Process choice** |
|:---|:---|:---|:---|:---|:---|:---|
| Re`^3` (Yang et al., 2022) | plan, text | passage | fixed workflow | – | – | – |
| STORM (Shao et al., 2024) | outline, evidence | section | fixed workflow | – | – | – |
| CogWriter (Wan et al., 2025) | plan, constraints, text | plan / revision | validate or revise | yes | yes | – |
| WriteHERE (Xiong et al., 2025) | task graph, text | task node | task selection | yes | yes | – |
| **Agentic CogWriter** | **draft, goals, history** | **writing process** | **process selection** | yes | yes | yes |

Table 1. Architectural comparison focused on the decision made during long-form generation. **Adaptive** indicates that the next unit is selected from the current state rather than prescribed by a fixed workflow; **Process choice** indicates that the selectable unit is an explicit writing process such as planning, drafting, or reviewing. The table abstracts each system only along dimensions relevant to our architecture question.

## Agentic CogWriter

We introduce Agentic CogWriter, a long-form writing architecture that turns document production into a stateful loop over explicit writing processes. Figure 1 gives the system overview. To make the information available throughout that loop explicit, we denote the original writing task by

`X=(I,C,O),`

where `I` is the instruction, `C` is any supplied context, and `O` is the requested output contract. The task `X` remains available throughout composition. When the `Monitor` terminates the loop, the current draft is returned as the completed document `D_final`. The architecture has four agent roles: a top-level `Monitor` and three specialists, `Planner`, `Translator`, and `Reviewer`.

### Persistent Writing State

We index the evolving draft by the number of completed process invocations: `D_t` is the current draft after `t` invocations, and `D_0` is the initial draft state before the first invocation. The number of invocations is not fixed in advance. After the `t`-th process invocation, the shared workspace exposes

`S_t=(D_t,G_t,H_t),`

where `D_t` is the current draft, `G_t` is an explicit hierarchy of writing goals, and `H_t` is the observable process history. The `Monitor` decides when to stop after review, subject to the common runtime budget used in our experiments. Keeping these records outside any single agent context allows successive writing processes to inspect and modify the same document-level state.

The goal network is motivated by Flower and Hayes (1981), who describe writers as creating and developing goals during composition. In our implementation, goals can be created, refined, or replaced; we call replacement of an existing goal *goal regeneration*. These records are an engineering representation that makes one theory-derived design choice observable. They are not intended as a claim that the language agent has a human-like cognitive state.

### Process-Level Control

The key architectural choice is what the `Monitor` selects next. Its action space is

`A=(Planning,Translating,Reviewing),`

and its decision after state `S_t` is

`a_t=pi_Monitor(X,D_t,G_t,H_t), a_t in A.`

We use *process-selection policy* as shorthand for this runtime decision; `pi_Monitor` is not a separately trained policy model. We retain Flower and Hayes (1981)’s term `Translating` for the drafting activity. Unlike a section scheduler or task-graph controller, Eq. <a href="#eq:monitor-policy" data-reference-type="eqref" data-reference="eq:monitor-policy">[eq:monitor-policy]</a> selects the *kind of writing work* to perform next.

The process order is therefore not fixed. Drafting can expose a structural problem that motivates renewed planning, and reviewing can trigger either another drafting pass or another planning pass. After a review, the `Monitor` may instead terminate the loop and return the current draft as `D_final`.

### Agent Roles and State Updates

After choosing `a_t`, the `Monitor` delegates the selected process to its corresponding specialist. The `Planner` develops document structure and goals, the `Translator` turns the current plan and goals into prose, and the `Reviewer` evaluates the draft against the task and active goals. Each specialist writes its result back to the shared workspace before returning control to the `Monitor`, yielding the next observable state `S_(t+1)`.

This division separates *coordination* from *execution*. The `Monitor` decides what kind of writing work is needed; the specialist performs that work with role-specific instructions; and the persistent state carries the result into the next decision. A proposed replacement of an existing goal is accepted or rejected by the `Monitor` and recorded in `H_t`. The experiments below test the architecture as a whole and then ablate the explicit goal representation and adaptive process ordering separately.

## Experimental Design

We design the experiments around three questions: (1) does process-level organization improve document quality relative to alternative writing architectures, (2) which components of Agentic CogWriter are necessary for any observed advantage, and (3) how does the resulting writing loop behave in practice? The study contains seven pre-specified systems plus one post-hoc execution check, all compared on the same task inputs and under a common generation contract.

### Systems Compared

##### Alternative writing architectures.

We compare Agentic CogWriter with three ways of organizing long-form generation. The one-shot baseline (`Single-pass`) asks the model to produce the complete document in one call. The fixed-stage baseline (`Staged`) executes `Pre-Write``->``Write``->``Re-Write`, following the common pattern of separating planning, drafting, and revision into a prescribed workflow (Yang et al., 2022; Wan et al., 2025). The adaptive task-planning baseline (`Task-planning`) follows a WriteHERE-style task graph (Xiong et al., 2025): it recursively decomposes the assignment and selects among dependency-satisfied task nodes. Thus, the three alternatives respectively advance the whole document, a fixed writing stage, or an adaptive task node, whereas Agentic CogWriter advances a writing process.

##### Ablations of Agentic CogWriter.

We next modify one architectural choice at a time while leaving the rest of the process loop intact. `No-goals` removes the explicit goal network but retains adaptive process selection and the specialized agents. `Fixed-order` keeps the shared draft, goal network, process history, and specialists but replaces the `Monitor`’s adaptive decision with the repeated `Planning``->``Translating``->``Reviewing` cycle. These ablations test how much explicit goal bookkeeping and adaptive process order contribute to the full system’s performance.

##### Execution variants.

We also probe whether the way writing processes are executed can explain the result. `Single-writer` retains the goal network and process-level loop but performs planning, drafting, and reviewing in one writer context without role-agent delegation; it also limits each `Translating` step to one paragraph before the next process decision. Because those changes are bundled, this condition is diagnostic rather than a clean ablation. After observing the main results, we added `Single-context` as a narrower exploratory check: it preserves the full process loop and shared state but executes each selected process in the `Monitor`’s context rather than in a separate role-agent context. The run also differs in gateway entry point and transport, so we use it only to constrain, rather than establish, a role-context explanation. Table 2 summarizes the systems in a common state–action notation.

| **System** | **State used at step `t`** | **Unit advanced** | **Next-step rule** | **Execution** |
|:---|:---|:---|:---|:---|
| `Single-pass` | `X` | whole document | one generation | one context |
| `Staged` (Yang et al., 2022; Wan et al., 2025) | `X`, prior stage output | fixed stage | Pre-Write`->`Write; `->`Re-Write | one context |
| `Task-planning` (Xiong et al., 2025) | `(D_t,T_t)` | task node `v_t` | `v_t=pi_task(D_t,T_t)` | task graph |
| **Agentic CogWriter** | `(D_t,G_t,H_t)` | **writing process `a_t`** | `a_t=pi_Monitor`; `(X,D_t,G_t,H_t)` | **role subagent** |
| `No-goals` | `(D_t,H_t)` | writing process `a_t` | `a_t=pi_Monitor`; `(X,D_t,H_t)` | role subagent |
| `Fixed-order` | `(D_t,G_t,H_t)` | writing process `a_t` | fixed Planning`->`Translating; `->`Reviewing | role subagent |
| `Single-writer` | `(D_t,G_t,H_t)` | writing process `a_t` | adaptive process selection | one writer |
| `Single-context` | `(D_t,G_t,H_t)` | writing process `a_t` | adaptive process selection | Monitor context |

Table 2. Systems compared under the shared generation contract. `X` is the task input, `D_t` the current draft, `G_t` the goal network, `H_t` the process history, and `T_t` an adaptive task graph. `Single-context` is post-hoc; all other rows were pre-specified. The equations are a common abstraction for comparison rather than the original notation of prior systems.

### Benchmarks and Prompts

To test whether the architecture transfers across distinct forms of long-form writing, we use three complementary benchmarks: (1) WritingBench (Wu et al., 2026b), which covers broad real-world writing requests with task-specific evaluation criteria; (2) HelloBench (Que et al., 2024), which contains long-text tasks including summarization, open-ended generation, and text completion; and (3) DoLoMiTes (Malaviya et al., 2025), which targets methodical expert writing with explicit objectives, procedures, inputs, and constraints. Together, they probe general instruction following, sustained long-context generation, and structured expert-document production rather than a single writing genre.

For each benchmark, we evaluate a deterministic demanding subset selected before scoring and independently of any system output. The selector excludes pilot prompts and prioritizes the longest input contexts and, where a requested output length is stated, the longest requested outputs. The resulting subsets stress different demands across benchmarks: WritingBench combines long inputs with explicit long-output requirements, HelloBench emphasizes very long-input summarization and continuation, and DoLoMiTes emphasizes procedural constraints with more moderate prompt length. This selection concentrates evaluation on cases where sustained generation and context handling leave room for architectural differences to emerge; Appendix A gives the exact rule, sample sizes, composition, and statistical sensitivity.

### Implementation

All systems run in the same Codex-style coding-agent harness. Agentic CogWriter is packaged as a skill: the top-level `Monitor` invokes `Planner`, `Translator`, and `Reviewer` through the harness’s subagent mechanism, while the comparison systems use the same harness and task-level information policy. The implementation follows the platforms’ documented skill and subagent abstractions (Anthropic, 2026a; Anthropic, 2026b; OpenAI, 2026a; OpenAI, 2026e; Google, 2026b; Google, 2026a).

All generations use `gpt-5.6-luna medium`.[^1] Each prompt–system pair is generated in three generation runs that re-generate the same prompt set with the same stack. These are repeated stochastic generations, not independent replications of the underlying claim. The harness records completed outputs and, where applicable, process switches, goal events, delegated invocations, token accounting, and timing. Network access, web search, and external retrieval are disabled for every condition so that architecture cannot change the information available to the writer. Appendix B reports the complete runtime settings.

### Evaluation

##### Pointwise evaluation.

We first score each completed document independently with `gpt-5.6-sol medium`.[^2] For benchmark-native evaluation, WritingBench retains its five query-specific criteria, each scored from 1 to 10, while HelloBench retains its 5–7 item checklist and five-level item scale; the native score is the mean of the corresponding criterion or checklist scores. DoLoMiTes does not provide an analogous native score in our setup. We preserve the benchmark evaluation prompts but substitute `gpt-5.6-sol medium` for the judge models used in the original benchmark reports.[^3]

Because the benchmark-native metrics are not available in the same form for all three datasets, we also score every document with a common five-dimension rubric covering instruction fulfillment, organization and coherence, content adequacy and depth, style and audience fit, and factual or constraint fidelity. This provides a common pointwise view across all three benchmark types, including DoLoMiTes. The judge assigns each dimension a raw score from 1 to 5; to resolve differences within the compressed upper range of that scale, we standardize each dimension within a benchmark across outputs from all seven pre-specified conditions and average the five z-scores. The composite is therefore relative: zero is the across-condition mean for that benchmark, and a negative value means below that reference mean rather than poor absolute writing quality. These pointwise and benchmark-native scores come from the initial generation run and are descriptive. Appendix A reproduces the evaluator prompts and benchmark-specific procedures.

##### Pairwise evaluation.

Pointwise ratings judge each document in isolation and can compress differences among generally strong outputs, so we additionally use direct same-prompt comparisons. We ask `gpt-5.6-sol medium` to compare two responses written for the same prompt and return a winner or tie. LLM judges are known to exhibit position bias (Zheng et al., 2023; Wang et al., 2024); to reduce that bias, every pair is evaluated twice, once as A-versus-B and once with the responses swapped to B-versus-A. We retain a prompt-level winner only when both orders identify the same semantic winner, and record any disagreement, including winner versus tie, as a tie. Reported win rates condition on these decided comparisons; ties and prompts lacking a completed output from either system are excluded from the headline denominator.

The Luna–Sol assignment deliberately gives judging to the higher-capability model, but both models remain in the same GPT-5.6 family. That does not satisfy our separately pre-specified plan to use a different-family judge. Related generator–judge models, including members of the same model family, can introduce systematic preference leakage or self-preference (Li et al., 2026; Panickssery et al., 2024). We therefore disclose the deviation and repeat the selected architecture contrasts with `claude-sonnet-5 medium` as a descriptive cross-family robustness check rather than averaging the two judges.

##### Pre-specified statistical testing.

To avoid choosing favorable contrasts or tests after seeing the results, we fixed the inferential family before scoring. The eight contrasts compare Agentic CogWriter with `Single-pass`, `Staged`, `Task-planning`, `No-goals`, and `Fixed-order`, and compare `Single-writer` with `Single-pass`, Agentic CogWriter, and `No-goals`. Within each benchmark, each contrast is tested separately in each generation run with an exact two-sided sign test over non-tied prompt-level wins and losses (Dixon and Mood, 1946); Holm correction (Holm, 1979) is then applied jointly to the resulting pre-specified cells for that benchmark. We do not pool prompts across generation runs for confirmatory inference. Main-text tables report descriptive means across the three generation runs, while Appendix C reports generation-run-level Wilson intervals (Wilson, 1927) and the multiplicity-adjusted decisions.

As a post-hoc exploratory summary of the ablations, we also use a prompt-clustered analysis pooled over benchmarks and generation runs. For each prompt and run, a win is scored as one, a tie as one half, and a loss as zero; we average those outcomes over the three generation runs, pool the resulting prompt-level values across benchmarks, use a prompt-level bootstrap interval, and apply a sign test over prompts. This analysis was not pre-specified and is reported next to, rather than in place of, the confirmatory cellwise tests.

##### Robustness and behavioral analysis.

Two known properties of automatic judging motivate the sensitivity analyses. LLM evaluators can prefer longer responses (Zheng et al., 2023; Dubois et al., 2024), while related generator–judge models can introduce preference leakage (Li et al., 2026; Panickssery et al., 2024). We therefore check whether the pairwise direction persists within pre-specified output-length bands, under a tight compute match, and under the cross-family judge; because output length and compute are consequences of execution, the first two checks are descriptive rather than causal adjustments.

Aggregate quality scores also cannot show how an adaptive writing agent uses its control loop. We therefore analyze observable traces of process transitions, goal creation and refinement, goal replacement, and delegated invocations. We also compare outcomes from runs that complete one planning–drafting–reviewing cycle with outcomes from runs that take another process path; this trace-defined comparison is observational, not randomized.

## Results

### Pointwise and Benchmark-Native Quality

Table 3 shows that Agentic CogWriter obtains the strongest native and pointwise scores on WritingBench and HelloBench, whereas `Staged` has the strongest DoLoMiTes pointwise score. The table displays the four architecture-level systems, but each pointwise dimension is standardized against outputs from all seven pre-specified conditions before the five z-scores are averaged. The pointwise values are therefore relative: zero is the across-condition mean for that benchmark, and negative entries such as the `Single-pass` WritingBench score indicate below-reference performance rather than negative absolute document quality. Taken together, the independent metrics show that Agentic CogWriter is competitive across all three benchmark types but is not uniformly best.

|  |  |  |  |  |  |  |
|:---|:--:|:--:|:--:|:--:|:--:|:--:|
| **System** | **WritingBench** | **WritingBench** | **HelloBench** | **HelloBench** | **DoLoMiTes** | **DoLoMiTes** |
|  | **Native** | **Pointwise** | **Native** | **Pointwise** | **Native** | **Pointwise** |
| *Alternative writing architectures* | *Alternative writing architectures* | *Alternative writing architectures* | *Alternative writing architectures* | *Alternative writing architectures* | *Alternative writing architectures* | *Alternative writing architectures* |
| `Single-pass` | 7.044 | -0.093 | 0.769 | -0.119 | – | -0.019 |
| `Staged` (Yang et al., 2022; Wan et al., 2025) | 7.084 | -0.054 | 0.78 | -0.007 | – | **0.103** |
| `Task-planning` (Xiong et al., 2025) | 7.258 | -0.062 | 0.781 | 0.04 | – | -0.166 |
| **Agentic CogWriter** | **7.54** | **0.115** | **0.795** | **0.058** | – | 0.005 |

Table 3. Independent document-quality scores on the selected demanding benchmark subsets from the initial generation run. Native scores remain on each benchmark’s own scale. Pointwise scores are z-standardized against outputs from all seven pre-specified conditions within each benchmark, so zero is the corresponding across-condition mean. Best scores in each column are in bold.

### Direct Comparison of Writing Architectures

Table 4 shows a clearer separation among writing architectures when the judge directly compares responses to the same prompt. Its headline rates are mean win rates among *decided* comparisons, meaning that both presentation orders agree on a winner; ties and pairs with a failed output are excluded from that denominator. Under this convention, Agentic CogWriter is preferred to one-shot generation, the fixed-stage workflow, and adaptive task planning, with across-benchmark mean win rates of 80.9%, 67.3%, and 68.5%, respectively. The direction holds in every benchmark–generation-run cell against `Single-pass` and `Task-planning`, and in all but one cell against `Staged`; generation-run-level exact tests with within-benchmark Holm correction support this pattern, with intervals and cell-level decisions in Appendix C. When every attempted prompt is counted instead, so ties and failed pairs remain in the denominator, the corresponding win shares are 63.1%, 46.6%, and 49.7%; assigning every missing pair against Agentic CogWriter still leaves decided-comparison win rates of at least 74.9%, 61.9%, and 66.1%, respectively.

|  |  |  |  |  |
|:---|:--:|:--:|:--:|:--:|
| **Agentic CogWriter win rate (%)** | **Agentic CogWriter win rate (%)** | **Agentic CogWriter win rate (%)** | **Agentic CogWriter win rate (%)** | **Agentic CogWriter win rate (%)** |
| **Comparison** | **Writing** | **Hello** | **DoLo** | **Mean** |
| vs. `Single-pass` | **84.3%** | **85.7%** | **72%** | **80.9%** |
| vs. `Staged` | **80.9%** | **62.8%** | **55.9%** | **67.3%** |
| vs. `Task-planning` | **65.5%** | **63%** | **75.7%** | **68.5%** |

Table 4. Direct same-prompt comparison of writing architectures. Entries are Agentic CogWriter’s mean win rates among decided prompt comparisons across three generation runs. A comparison is decided only when both presentation orders agree on a winner; ties and pairs with a failed output are excluded. Values above 50% favor Agentic CogWriter; winning rates are in bold. “Mean” pools benchmark outcomes within each generation run before averaging across runs. Baseline definitions and citations appear in Section 4.1.

Table 4 establishes an architecture-level difference but does not isolate a mechanism. Agentic CogWriter differs from the three alternatives in several coupled choices, including its persistent state, process-level action space, and repeated return to the `Monitor`. We therefore interpret the direct-comparison result as evidence for the tested organization as a whole rather than for any one of those features.

### Ablations and Execution Diagnostics

Table 5 shows that the pre-specified cellwise tests do not identify a large contribution from either explicit goal bookkeeping or adaptive process order. For both `No-goals` and `Fixed-order`, no benchmark–generation-run cell survives the within-benchmark Holm correction. A post-hoc prompt-clustered analysis gives a more sensitive but exploratory pooled view: after averaging each prompt’s win, tie, and loss outcomes over the three generation runs and pooling benchmarks, Agentic CogWriter is preferred to `Fixed-order` at 53.7% \[51.0%–56.4%\], `p=0.004`, whereas its preference over `No-goals` is 52.3% \[49.6%–55.0%\], `p=0.056`. Because this analysis was not pre-specified, it does not replace the confirmatory cellwise family; together, the estimates indicate a small contribution from adaptive ordering and no significant pooled contribution from the explicit goal network, with both effects bounded near parity and too small to account for the substantially larger advantages over the architecture baselines.

| **Variant** | **WritingBench** | **HelloBench** | **DoLoMiTes** | **Across benchmarks** |
|:---|---:|---:|---:|---:|
| *Ablations* | *Ablations* | *Ablations* | *Ablations* | *Ablations* |
| `No-goals` | 52.1% | 52.4% | 56% | 53.4% |
| `Fixed-order` | 56.8% | 57.4% | 54.7% | 56.3% |
| *Bundled execution diagnostic* | *Bundled execution diagnostic* | *Bundled execution diagnostic* | *Bundled execution diagnostic* | *Bundled execution diagnostic* |
| `Single-writer` | 68.5% | 83.4% | 67.8% | 73.5% |

Table 5. Ablations and execution diagnostic. Entries are Agentic CogWriter’s mean win rates among decided prompt comparisons across three generation runs; ties and pairs with a failed output are excluded. The final column pools benchmarks within each generation run before averaging across runs. `No-goals` and `Fixed-order` each modify one architectural component, whereas `Single-writer` changes several execution properties together.

Table 5 also shows a much larger loss for `Single-writer`, but that comparison changes several execution properties at once. It removes subagent delegation, changes role context, changes how much text can be produced between decisions, and changes output length. Within the tighter and wider pre-specified output-length matching bands, `Single-writer` still wins only 35.1% (`p=0.0141`) and 30.6% (`p=2.32 x 10^-5`), respectively, against Agentic CogWriter, so output length does not explain that gap. The narrower post-hoc `Single-context` check retains the process loop and shows no significant pooled difference from Agentic CogWriter in its exploratory generation run (47.4% win rate for `Single-context`, `p=0.5161`, unadjusted). Because that run also differs in gateway entry point and transport, these results weaken a simple role-context explanation without isolating an alternative mechanism; Appendix E.4 gives the benchmark-level results.

### How Does the Writing Loop Behave in Practice?

Table 6 shows that the supposedly flexible writing loop is behaviorally conservative. The dominant behavior is one `Planning``->``Translating``->``Reviewing` cycle; a new planning step after review is rare, and replacement of an existing goal is also rare. Thus, although Agentic CogWriter can revisit earlier processes, most runs use that freedom very little. This concentration is consistent with the small exploratory advantage over `Fixed-order`: a controller that rarely departs from the default cycle has limited opportunity to benefit from being allowed to deviate.

| **Observed writing-loop behavior**             | **Value** |
|:-----------------------------------------------|----------:|
| One Planning`->`Translating`->`Reviewing cycle |     74.6% |
| Review followed by renewed Planning            |      0.3% |
| Runs accepting replacement of an existing goal |     4/886 |

Table 6. Observed behavior of Agentic CogWriter across completed runs. The first row measures the canonical single-cycle path; the second measures explicit returns from review to planning; the third counts accepted goal regeneration.

Figure 2 shows the same concentration at the sequence and transition levels. The most frequent complete process path is the forward planning–drafting–reviewing progression, and the unrestricted system is visually close to `Fixed-order` because much of its observed behavior follows that path. This result comes from the deliberately demanding benchmark subsets rather than a random collection of routine prompts, but the length-and-demand selector does not guarantee that every task intrinsically requires replanning or repeated revision. The trace evidence therefore shows that adaptive control is rarely exercised on the evaluated subsets rather than that it is unnecessary for all difficult writing tasks.

Figure 2. Observed writing-process behavior. Panel (a) shows the most frequent complete process paths; panels (b) and (c) show transition counts for Agentic CogWriter and `Fixed-order`. P, T, and R denote `Planning`, `Translating` (drafting), and `Reviewing`; E = end.

Table 7 shows no larger advantage for the less common process paths. Runs that complete exactly one planning–drafting–reviewing cycle and runs that take any other path have similar pairwise win rates against `Fixed-order` and `Single-writer`. The split therefore provides no descriptive evidence that departures from the common cycle are where the advantage arises. Because it is defined by observed behavior rather than random assignment, it cannot support a causal claim. Appendix D reports the additional process counts, goal events, and resource-use statistics.

| **Process path**        | **`Fixed-order`** | **`Single-writer`** |
|:------------------------|:-----------------:|:-------------------:|
| Plan`->`draft`->`review |       57.4%       |        72.2%        |
| Other path              |       54.9%       |        75.2%        |
| Fisher `p`              |       0.60        |        0.43         |

Table 7. Descriptive association between Agentic CogWriter’s observed process path and pairwise outcome. The first row contains runs with exactly one planning–drafting–reviewing cycle; entries are Agentic CogWriter win rates among non-tied comparisons against the column system. Two-sided Fisher tests are unadjusted, and the trace-defined split is observational rather than causal.

### Robustness Checks

Table 11 and Table 12 show that the architecture-level direction survives the tested output-length and compute restrictions where eligible pairs exist. The main judge favors longer outputs overall, but Agentic CogWriter remains favored over `Single-pass` within the pre-specified length-matching bands. Under the tightest available compute match, the direction also remains favorable against `Staged` and `Task-planning`; no Agentic CogWriter–`Single-pass` pairs satisfy that compute band. Because output length and realized compute are consequences of execution, these checks are descriptive rather than causal adjustments.

Table 15 shows more judge dependence than the resource-matched checks. The cross-family judge preserves the pooled direction for the checked contrasts but produces many ties and reverses the WritingBench direction for Agentic CogWriter versus `Single-pass`. We therefore interpret it as a partial robustness check rather than as confirmation that the exact win rates are judge-invariant.

## Discussion

The strongest evidence is for the architecture as a whole rather than for a single mechanism. Table 4 shows that Agentic CogWriter is preferred to all three alternative writing organizations in direct same-prompt comparisons, while Table 3 shows a more mixed picture under independent scoring: the proposed system leads on WritingBench and HelloBench but not DoLoMiTes. Read together, these results suggest that process-organized execution is a useful way to structure a general-purpose agent for long-form writing, but not that it dominates every alternative under every quality metric.

The ablations substantially narrow the explanation for that result without reducing either component to a null effect. Table 5 shows that no pre-specified benchmark–generation-run cell for Agentic CogWriter versus `Fixed-order` or `No-goals` survives Holm correction. The post-hoc prompt-clustered analysis, however, estimates a small preference for adaptive ordering at 53.7% \[51.0%–56.4%\], `p=0.004`, while the corresponding goal-network estimate is 52.3% \[49.6%–55.0%\], `p=0.056`. These exploratory intervals keep both contributions close to parity and far smaller than the architecture-level baseline gaps. Table 6 and Figure 2 also show why the ordering effect can be small: even when the `Monitor` may choose freely, it usually follows the planning–drafting–reviewing cycle, leaving relatively few opportunities for a deviation to help.

The simple observed loop is not, by itself, evidence that the benchmark prompts were trivial. The selector prioritizes the longest inputs and, where stated, the longest requested outputs, but those demands differ by benchmark: WritingBench combines long inputs and explicit long-output requests, HelloBench contributes primarily very long-input summarization and continuation tasks, and DoLoMiTes emphasizes methodical expert constraints. The selection criterion therefore rules out an explanation based only on evaluating random short prompts, but it does not measure whether a task intrinsically requires replanning. A plausible alternative is that many benchmark prompts remain solvable with one strong plan–draft–review pass even when they are demanding in length or constraints. Testing prompts whose objectives or evidence change during writing would be a more direct stress test of repeated replanning and goal regeneration.

The execution variants also caution against a simple “more agents is better” interpretation. `Single-writer` performs substantially worse, but it changes delegation, role context, decision granularity, and output length together; the output-length-matched comparisons in Section 5.3 show that length alone does not account for this gap. The narrower `Single-context` comparison preserves the process loop and does not show a significant pooled difference in its exploratory generation run, while still differing in gateway and transport. The remaining candidates are thus properties shared across the successful process-organized variants, such as explicit process decomposition, persistent state between processes, and repeated return to a common `Monitor`. Future experiments should intervene on these shared properties directly rather than infer a mechanism from the bundled comparison.

For agent design, the broader implication is that long-form writing can be treated as an architecture layered on a general-purpose agent harness. Coding-agent-style systems already provide persistent files, tool use, skills, and subagent execution; Agentic CogWriter repurposes those generic capabilities to make writing a stateful process rather than a single generation request. This systems view also connects standalone writing agents to larger workflows in which a document is the final artifact, including research agents that proceed from literature review and experimentation to report or paper generation (Schmidgall et al., 2025; Lu et al., 2024).

Cognitive writing theory plays a narrower role than a claim of cognitive fidelity. Flower and Hayes (1981) provide a vocabulary for separating planning, translating, reviewing, monitoring, and writer-generated goals; our experiments turn several of those ideas into architecture choices that can be removed or constrained. The value of that mapping is falsifiability: the current evidence bounds explicit goal bookkeeping and adaptive ordering as modest contributors under this design rather than establishing them as the source of the larger architecture-level advantage. The traces characterize implemented system behavior, not human cognition, and the results should be read as evidence about writing-agent design rather than validation of a psychological model.

## Conclusion

We study long-form writing as an architecture problem for AI agents. Agentic CogWriter uses a coding-agent-style harness in which a `Monitor` repeatedly inspects persistent writing state and delegates planning, drafting, or reviewing to specialized agents. Across three complementary long-form benchmarks, the system is competitive on independent document-quality measures and is preferred in direct same-prompt comparisons to one-shot generation, a fixed staged workflow, and adaptive task planning.

The ablation and trace results qualify where that advantage comes from. No pre-specified benchmark–generation-run cell shows a Holm-surviving difference after removing the explicit goal network or fixing process order, while the exploratory pooled analysis finds a small preference for adaptive ordering and no significant pooled goal-network effect. The unrestricted `Monitor` also usually follows the same planning–drafting–reviewing cycle on its own, so a controller that rarely departs from that cycle has limited opportunity to benefit from adaptive ordering. We therefore view both theory-derived components as at most modest contributors relative to the larger architecture-level advantage, and the contribution as evidence that process-organized, stateful execution is a promising abstraction for writing agents rather than evidence for any single cognitive mechanism. As general-purpose agents take on workflows that end in reports, documentation, and scientific papers, understanding how to organize the writing loop itself becomes an increasingly important systems question.

## Limitations

Our conclusions concern one generator family, one coding-agent-style harness, and selected demanding subsets of three long-form benchmarks. The selector prioritizes the longest inputs and, where stated, the longest requested outputs rather than an independent semantic measure of difficulty, so the results do not establish transfer to shorter tasks, objectives that evolve during writing, other model families or runtimes, interactive human–AI writing, or end-to-end agents with retrieval. The alternative architectures are our matched implementations under the common generator and harness, not executions of the published systems, and their scores should not be read as leaderboard evaluations of those systems.

The pointwise and benchmark-native scores come from the initial generation run, whereas the direct comparison is repeated across three generation runs that re-generate the same prompts with the same stack. The headline pairwise rates condition on decided comparisons and exclude ties and prompts for which either system lacks a completed output, so they do not by themselves describe every attempted prompt; Section 5.2 reports unconditional and worst-case missing-output views as well. The main judge also shares the generator’s GPT-5.6 family despite a pre-specified plan for a different-family judge; related generator–judge models can introduce preference leakage or self-preference (Li et al., 2026; Panickssery et al., 2024). The cross-family check produces many ties and reverses one WritingBench direction, and we did not collect human judgments; consequently, the relationship between model-judge preference and human preference is unknown. The main judge also favors longer outputs overall, so its choices should not be interpreted as a pure measure of writing quality.

The ablations constrain mechanism claims but do not establish equivalence. No pre-specified benchmark–generation-run cell for removing the goal network or fixing process order survives Holm correction, but the post-hoc prompt-clustered analysis detects a small pooled preference for adaptive ordering at 53.7% \[51.0%–56.4%\], `p=0.004`, while the goal-network estimate is 52.3% \[49.6%–55.0%\], `p=0.056`. Because this pooled analysis was not pre-specified, it is exploratory; its intervals nevertheless bound both components as modest contributors rather than showing that they are irrelevant. `Single-writer` changes delegation, role context, decision granularity, and output length together, while the post-hoc `Single-context` check is narrower but was run for one exploratory generation run and differs in gateway entry point and transport. We therefore cannot attribute the remaining architecture-level difference to role separation, delegation, repeated checkpoints, persistent state, or any other single shared execution feature.

Finally, the length- and compute-matched analyses are descriptive because both variables are consequences of execution. Likewise, the process traces record implemented state transitions and agent actions; they characterize how Agentic CogWriter behaves on these tasks but are not measurements of human cognition and do not validate cognitive process theory as a model of language-agent internals.

## Prompt and experiment configuration

##### Prompt selection and provenance.

The scored study uses the committed `hard100` subset generated from the pinned WritingBench, HelloBench, and DoLoMiTes prompt manifests before generation. The selector first removes pilot prompts, then scores each remaining prompt by its prompt word count plus the largest requested output length found in the prompt text or structured output constraints, when such a length is stated. Candidates above the selector’s fixed maximum prompt-length or requested-length gate are excluded. The remaining candidates are ordered by this score, then prompt word count, requested length, and prompt identifier, all in descending order; the top 100 eligible prompts from each benchmark are retained, yielding 300 scored prompts in total. The committed prompt-set artifact stores the resulting identifiers. Generation reads only these committed manifests and prompt-set identifiers, so output quality does not enter prompt selection.

The selected prompts stress different aspects of long-form writing across the three benchmarks. WritingBench contributes prompts with both long inputs and explicit long-output requirements; HelloBench contributes primarily very long-input summarization and continuation tasks, with explicit output lengths uncommon; and DoLoMiTes contributes methodical expert tasks with more moderate prompt lengths and structured procedural constraints. The `hard100` label therefore denotes the deterministic length-and-demand selector rather than a claim that every selected prompt has the same source of semantic difficulty.

##### Sample size and inferential sensitivity.

The 100-prompt count per benchmark was fixed before scoring rather than selected from the observed results. Under the realized missing and tie rates, a benchmark–contrast–generation-run cell contains about 75 decided comparisons; at the strictest first-step Holm threshold, an exact sign test has 80% power for a true preference of about 73%. Pooling benchmarks only to describe scale yields about 220 decided comparisons and a corresponding detectable preference of about 63%. These calculations characterize the sensitivity of the committed sample and do not make it representative of each full benchmark; the remaining benchmark pools were not judged.

##### Common generation contract.

All pre-specified systems receive the same assignment, supplied context, requested output constraints, generator model, attempt budget, and information policy. The later `Single-context` check uses the same task-level contract. External retrieval is disabled: the coding-agent sandbox denies network access and web search, and systems are instructed not to introduce facts unsupported by the assignment or supplied context. The Codex wrapper invokes the system-specific skill and requires the final response to contain the complete generated document rather than a summary or a link to a workspace artifact.

##### Alternative architecture prompts.

The one-shot condition begins: “Write the final response in one generation pass. Do not make a plan for the reader, describe a review, or expose hidden reasoning.” It then receives the assignment, supplied context, and requested output constraints.

The fixed-stage condition uses three prompts. `Pre-Write` begins: “Prepare a concise working plan for the next writer. Identify the response’s purpose, audience, required content, order, and constraints.” It explicitly says not to write the final response yet. `Write` begins: “Write a complete draft that answers the assignment,” using the complete `Pre-Write` output as working guidance. `Re-Write` begins: “Revise the draft for instruction fulfillment, organization, depth, audience fit, and factual fidelity.” Each stage is restricted to the same assignment and supplied context, and the aggregate output-token budget is fixed across the three stages.

The adaptive task-planning condition uses a persistent directed acyclic task graph containing only `reasoning` and `composition` nodes. The coordinator recursively decomposes or executes the next dependency-satisfied task and may revise active graph structure after observing composed text. The prompt explicitly forbids adapting by selecting named writing processes; adaptation is restricted to task structure.

##### Agentic CogWriter and ablation prompts.

Agentic CogWriter is invoked through the `agentic-cog-writer` skill. The top-level agent acts as the `Monitor`, reads the draft, goal network, and process history, and chooses among `Planning`, `Translating`, and `Reviewing`. The selected process is delegated through the subagent mechanism to the corresponding `Planner`, `Translator`, or `Reviewer`. The skill requires process switches and goal changes to be written to an append-only trace.

The pre-specified ablations modify this contract directly. `No-goals` forbids the explicit goal network while retaining adaptive process choice and the three role agents. `Fixed-order` preserves the goal network and role agents but replaces adaptive selection with the fixed `Planning``->``Translating``->``Reviewing` cycle. The `Single-writer` execution diagnostic retains adaptive process choice and the goal network but forbids delegation to those role agents; it also requires each `Translating` step to append one paragraph before the writer makes the next process decision. Configuration files record the skill or stage prompt used for each system and the SHA-256 hash of fixed stage prompts.

The post-hoc `Single-context` check keeps the same `Monitor`, process instructions, shared draft, goal network, process history, termination rule, and final-output contract as Agentic CogWriter, but executes the selected `Planning`, `Translating`, or `Reviewing` instruction in the `Monitor`’s context instead of delegating to a role agent. It does not impose the one-paragraph `Translating` restriction used by `Single-writer`.

##### Pointwise evaluator prompts.

All reported pointwise judgments use `gpt-5.6-sol medium`. The generic evaluator reads one completed document together with its original assignment and supplied context and assigns an integer score from 1 to 5 for instruction fulfillment, organization and global coherence, content adequacy and depth, style/voice/audience fit, and factuality/constraint fidelity. A ten-prompt pilot showed these raw scores clustering near the upper end of the scale, motivating the standardized presentation used in the paper. For each benchmark, each dimension is z-standardized across outputs from all seven pre-specified conditions and the five z-scores are averaged. Thus, the reported composite is relative to the condition pool for that benchmark rather than an absolute 1-to-5 rating.

Benchmark-native evaluation preserves each dataset’s own evaluation structure and prompt template while replacing the original judge model with `gpt-5.6-sol medium`. WritingBench carries five query-specific criteria for each prompt; the evaluator scores each criterion from 1 to 10 and the native score is their unweighted mean. HelloBench carries 5–7 checklist items per prompt; the evaluator assigns each item one of `(0,0.25,0.5,0.75,1)` and the native score is their mean. We do not report a corresponding native score for DoLoMiTes because the committed prompts do not carry an analogous per-prompt native rubric.

##### Pairwise judge prompt.

The pairwise judge reads the assignment, supplied context, and two complete candidate responses. It is instructed to compare the candidates on instruction fulfillment, organization and global coherence, content adequacy and depth, style/voice/audience fit, factuality, and constraint fidelity and to return `A`, `B`, or `tie`. The prompt explicitly warns against position and length bias. To reduce residual position effects documented for LLM evaluators (Zheng et al., 2023; Wang et al., 2024), every semantic pair is evaluated in both A/B and B/A order; we retain a winner only when both orders agree on the same semantic response, and otherwise record a tie. The judge returns a JSON record containing the winner, short evidence quotes from each response, and a brief rubric-grounded comparison.

## Runtime configuration

Table 8 summarizes the runtime and evaluation settings used for the reported runs. Every condition received the same task input, available information, generator, tool policy, attempt budget, and final-output contract.

| **Setting**                   | **Value**                   |
|:------------------------------|:----------------------------|
| Generator                     | `gpt-5.6-luna medium`       |
| Primary pairwise judge        | `gpt-5.6-sol medium`        |
| Cross-family judge            | `claude-sonnet-5 medium`    |
| Generation runs               | 3 per prompt–condition pair |
| Generator output-token budget | 64,000                      |
| Generator temperature         | unset                       |
| Generator sandbox             | workspace-write             |
| Network access                | denied                      |
| Web search                    | disabled                    |
| Approval policy               | never                       |
| External retrieval            | disabled for all conditions |
| Primary judge seed            | 20260908                    |
| Primary judge retries         | 2                           |
| Pairwise presentation         | both orders                 |
| Presentation disagreement     | counted as tie              |

Table 8. Runtime and evaluation settings used for the reported experiments. Model names include the configured reasoning-effort label where applicable.

## Generation-run-level pairwise outcomes

The following figure shows the prompt-level pairwise estimates for each benchmark and generation run, including the ablation contrasts.

Figure 3. Prompt-level pairwise win rates by benchmark and generation run. Generation-run points show 95% Wilson intervals. Filled or open circles mark cells that do or do not survive the within-benchmark Holm correction; diamonds are descriptive means across generation runs and are not separate inferential tests.

## Additional process and resource statistics

Table 9 reports completion, output size, delegated invocations, goal events, token accounting, and wall-clock time from the first generation run. For Agentic CogWriter, that run uses 13,374 output-plus-reasoning tokens and 46,860 uncached input tokens per attempted run and records 1 accepted goal regeneration. Across the three generation runs, the trace summaries contain mean totals of 1,101.3 goal-creation events and 1,915.3 goal-development events, while the post-`Reviewing` ledger contains 353.7 entries including 3.7 explicit regeneration proposals.

| **Condition** | **Completed** | **Median**; **units** | **Spawns**; **/run** | **Goals created**; **developed/regenerated** | **Output**; **tokens**; **/run** | **Input**; **tokens**; **/run** | **Mean sec.**; **/completed run** |
|:---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| `Single-pass` | 289/300 | 1,654 | 0 | 0/0/0 | 4,874 | 13,263 | 61 |
| `Staged` | 300/300 | 1,510 | 0 | 0/0/0 | 10,728 | 21,822 | 77 |
| `Task-planning` | 292/300 | 1,702 | 8.09 | 0/0/0 | 17,851 | 62,871 | 298 |
| Agentic CogWriter | 293/300 | 1,835 | 3.22 | 1,068/1,864/1 | 13,374 | 46,860 | 426 |
| `No-goals` | 294/300 | 1,762 | 3.04 | 0/0/0 | 9,788 | 39,317 | 345 |
| `Fixed-order` | 282/300 | 1,773 | 3.43 | 267/1,163/3 | 11,402 | 42,888 | 219 |
| `Single-writer` | 280/300 | 1,111 | 0 | 1,621/169/1 | 15,356 | 30,715 | 103 |

Table 9. Process summary from the first generation run across the selected demanding benchmark subsets, which prioritize the longest inputs and, where stated, the longest requested outputs. Completed is the count of completed runs. Spawns are mean delegated invocations per attempted run. Output tokens are Codex-reported output plus reasoning tokens, and input tokens are uncached input tokens; both are means over attempted runs. Wall-clock time is the mean seconds for completed runs.

## Sensitivity analyses

### Record-pooled sensitivity

The record-pooled table reports a sensitivity analysis that treats the two presentation records for each prompt as independent observations; the retained disagreements show how much presentation order can affect the descriptive rates. The retained presentation disagreements were 22.7% on WritingBench, 29.4% on HelloBench, and 21.4% on DoLoMiTes across the three generation runs.

| **Contrast** | **WritingBench** | **HelloBench** | **DoLoMiTes** | **Across benchmarks** |
|:---|:--:|:--:|:--:|:--:|
| Agentic CogWriter vs `Single-pass` | 79.4% (0.8%) | 81.1% (1.2%) | 68.9% (6.2%) | 76.6% (2%) |
| Agentic CogWriter vs `Staged` | 74.6% (1.8%) | 59.9% (2.4%) | 54.7% (5.5%) | 63.6% (2.9%) |
| Agentic CogWriter vs `Task-planning` | 61.9% (4.5%) | 59.5% (4.8%) | 72.5% (6.7%) | 64.7% (1.8%) |
| Agentic CogWriter vs `No-goals` | 51.5% (3.8%) | 50.8% (1.6%) | 53.7% (5.7%) | 51.9% (0.6%) |
| Agentic CogWriter vs `Fixed-order` | 55% (0.6%) | 53.9% (1.3%) | 53.4% (3.1%) | 54.1% (0.9%) |
| `Single-writer` vs `Single-pass` | 66.7% (5.2%) | 41.6% (4.3%) | 53.7% (7.5%) | 54.4% (2.3%) |
| `Single-writer` vs Agentic CogWriter | 35.5% (2.1%) | 20.5% (1.4%) | 35.4% (3.3%) | 30.4% (2%) |
| `Single-writer` vs `No-goals` | 37.2% (3.3%) | 21.5% (4%) | 43% (7.1%) | 33.8% (2.5%) |

Table 10. Record-pooled sensitivity analysis treating the two presentation records for each prompt as independent observations. Benchmark columns report the first-listed condition’s mean record-pooled win rate across replications, with sample SD in parentheses. The final column first pools records across benchmarks within each replication and then reports the mean and sample SD of those replicate-level rates. These are descriptive sensitivity summaries and do not enter the confirmatory inference.

### Output-length sensitivity

The length-control table reports the longer-side preference by output-length ratio; the longer side wins 66.12% of 1647 non-tied comparisons. In the tighter pre-specified matching band, the outcomes from the first generation run are 25/3/7 for Agentic CogWriter versus `Single-pass` (`p=2.74 x 10^-5`), 26/15/7 for Agentic CogWriter versus `Task-planning` (`p=0.1173`), and 18/18/20 for Agentic CogWriter versus `No-goals`. In the wider pre-specified band, the corresponding outcomes are 40/11/17 (`p=5.70 x 10^-5`), 39/18/14 (`p=0.0075`), and 38/30/37 (`p=0.3961`). These matching-band `p`-values are unadjusted descriptive sign-test results. The remaining generation-run-specific rates are reported in Table 11.

| **Output-length ratio** |  **W/L/T**  | **Longer-side**; **win rate** |
|:------------------------|:-----------:|:-----------------------------:|
| 1.00–1.05               | 123/104/91  |            54.19%             |
| 1.05–1.10               |  116/67/92  |            63.39%             |
| 1.10–1.25               | 291/185/177 |            61.13%             |
| 1.25–1.50               | 277/120/141 |            69.77%             |
| 1.50–2.00               |  188/68/66  |            73.44%             |
| 2.00+                   |  94/14/23   |            87.04%             |

Table 11. Pairwise outcomes from the first replication after combining the two presentation orders for each prompt, grouped by output-length ratio. The longer side is the first-listed outcome in each row; ties are excluded from the win-rate denominator. Output units come from the run manifests.

### Compute-stratified sensitivity

| Contrast | Band or bin | W/L/T | Rate | `p` |
|:---|:---|:---|:---|:---|
| Agentic CogWriter vs. `Staged` | within 1.25 | 197/66/98 | 74.9% | `2.55 x 10^-16` |
| Agentic CogWriter vs. `Staged` | within 1.50 | 281/114/168 | 71.1% | `2.21 x 10^-17` |
| Agentic CogWriter vs. `Task-planning` | within 1.25 | 163/63/78 | 72.1% | `2.14 x 10^-11` |
| Agentic CogWriter vs. `Task-planning` | within 1.50 | 276/128/140 | 68.3% | `1.40 x 10^-13` |
| `Single-writer` vs. Agentic CogWriter | within 1.25 | 87/267/83 | 24.6% | `2.13 x 10^-22` |
| `Single-writer` vs. Agentic CogWriter | within 1.50 | 140/404/140 | 25.7% | `1.11 x 10^-30` |
| Agentic CogWriter vs. `Single-pass` | within 1.25 | 0/0/0 |  | `1` |
| Agentic CogWriter vs. `Single-pass` | within 1.50 | 13/6/3 | 68.4% | `0.1671` |
| Agentic CogWriter vs. `Staged` | 0.00–0.50 | 1/0/0 | 100.0% | `1` |
| Agentic CogWriter vs. `Staged` | 0.50–0.67 | 4/4/3 | 50.0% | `1` |
| Agentic CogWriter vs. `Staged` | 0.67–0.80 | 13/12/12 | 52.0% | `1` |
| Agentic CogWriter vs. `Staged` | 0.80–0.91 | 42/10/21 | 80.8% | `9.06 x 10^-6` |
| Agentic CogWriter vs. `Staged` | 0.91–0.95 | 21/7/3 | 75.0% | `0.0125` |
| Agentic CogWriter vs. `Staged` | 0.95–1.05 | 49/20/21 | 71.0% | `6.36 x 10^-4` |
| Agentic CogWriter vs. `Staged` | 1.05–1.10 | 23/6/20 | 79.3% | `0.0023` |
| Agentic CogWriter vs. `Staged` | 1.10–1.25 | 62/23/33 | 72.9% | `2.77 x 10^-5` |
| Agentic CogWriter vs. `Staged` | 1.25–1.50 | 71/36/58 | 66.4% | `9.23 x 10^-4` |
| Agentic CogWriter vs. `Staged` | 1.50–2.00 | 95/57/53 | 62.5% | `0.0026` |
| Agentic CogWriter vs. `Staged` | 2.00+ | 38/29/39 | 56.7% | `0.3284` |
| Agentic CogWriter vs. `Task-planning` | 0.00–0.50 | 44/26/23 | 62.9% | `0.0414` |
| Agentic CogWriter vs. `Task-planning` | 0.50–0.67 | 119/48/55 | 71.3% | `3.83 x 10^-8` |
| Agentic CogWriter vs. `Task-planning` | 0.67–0.80 | 99/58/54 | 63.1% | `0.0013` |
| Agentic CogWriter vs. `Task-planning` | 0.80–0.91 | 69/25/34 | 73.4% | `6.34 x 10^-6` |
| Agentic CogWriter vs. `Task-planning` | 0.91–0.95 | 22/11/11 | 66.7% | `0.0801` |
| Agentic CogWriter vs. `Task-planning` | 0.95–1.05 | 33/16/16 | 67.3% | `0.0213` |
| Agentic CogWriter vs. `Task-planning` | 1.05–1.10 | 13/5/5 | 72.2% | `0.0963` |
| Agentic CogWriter vs. `Task-planning` | 1.10–1.25 | 26/6/12 | 81.2% | `5.35 x 10^-4` |
| Agentic CogWriter vs. `Task-planning` | 1.25–1.50 | 14/7/8 | 66.7% | `0.1892` |
| Agentic CogWriter vs. `Task-planning` | 1.50–2.00 | 7/3/5 | 70.0% | `0.3438` |
| Agentic CogWriter vs. `Task-planning` | 2.00+ | 1/1/2 | 50.0% | `1` |
| `Single-writer` vs. Agentic CogWriter | 0.00–0.50 | 1/5/0 | 16.7% | `0.2188` |
| `Single-writer` vs. Agentic CogWriter | 0.50–0.67 | 9/12/9 | 42.9% | `0.6636` |
| `Single-writer` vs. Agentic CogWriter | 0.67–0.80 | 15/43/20 | 25.9% | `3.07 x 10^-4` |
| `Single-writer` vs. Agentic CogWriter | 0.80–0.91 | 19/62/17 | 23.5% | `1.77 x 10^-6` |
| `Single-writer` vs. Agentic CogWriter | 0.91–0.95 | 12/20/8 | 37.5% | `0.2153` |
| `Single-writer` vs. Agentic CogWriter | 0.95–1.05 | 25/69/22 | 26.6% | `6.34 x 10^-6` |
| `Single-writer` vs. Agentic CogWriter | 1.05–1.10 | 8/39/9 | 17.0% | `5.54 x 10^-6` |
| `Single-writer` vs. Agentic CogWriter | 1.10–1.25 | 23/77/27 | 23.0% | `5.51 x 10^-8` |
| `Single-writer` vs. Agentic CogWriter | 1.25–1.50 | 38/94/37 | 28.8% | `1.19 x 10^-6` |
| `Single-writer` vs. Agentic CogWriter | 1.50–2.00 | 24/68/25 | 26.1% | `4.94 x 10^-6` |
| `Single-writer` vs. Agentic CogWriter | 2.00+ | 7/13/6 | 35.0% | `0.2632` |
| Agentic CogWriter vs. `Single-pass` | 1.25–1.50 | 13/6/3 | 68.4% | `0.1671` |
| Agentic CogWriter vs. `Single-pass` | 1.50–2.00 | 91/15/17 | 85.8% | `1.90 x 10^-14` |
| Agentic CogWriter vs. `Single-pass` | 2.00+ | 464/114/150 | 80.3% | `4.90 x 10^-51` |

Table 12. Compute-stratified pairwise outcomes after combining the two presentation orders for each prompt. The compute ratio is the ratio of output-plus-reasoning tokens per completed run, with retries included; the Agentic CogWriter versus Single-pass contrast has no pairs in the tighter matching band because Agentic CogWriter always uses more compute. The reported sign-test `p`-values are unadjusted descriptive sensitivity statistics and do not enter the confirmatory Holm family.

### Single-context exploratory check

The `Single-context` condition was added after the main results had been observed, to test whether the `Single-writer` loss reflects delegation to separate agents or the absence of process decomposition under a `Monitor`. We registered it as an exploratory condition outside the Holm family before judging and ran one generation run, the same evidence tier as the cross-family check: the question it answers is whether an attribution survives, not whether a new contrast is confirmed. We therefore report the pooled estimate with its interval and the benchmark-level results without adjustment.

| Contrast | Scope | `n` | Dropped | W/L/T | Rate | 95% Wilson / exact `p` |
|:---|:---|---:|---:|---:|---:|:---|
| `Single-context` |  |  |  |  |  |  |
| vs. Agentic CogWriter | WritingBench | 96 | 4 | 35/32/29 | 52.2% | 40.5%–63.7%; `0.8072` |
| `Single-context` |  |  |  |  |  |  |
| vs. Agentic CogWriter | HelloBench | 99 | 1 | 19/35/45 | 35.2% | 23.8%–48.5%; `0.0402` |
| `Single-context` |  |  |  |  |  |  |
| vs. Agentic CogWriter | DoLoMiTes | 98 | 2 | 37/34/27 | 52.1% | 40.7%–63.3%; `0.8126` |
| `Single-context` |  |  |  |  |  |  |
| vs. Agentic CogWriter | Pooled | 293 | 7 | 91/101/101 | 47.4% | 40.5%–54.4%; `0.5161` |
| `Single-context` |  |  |  |  |  |  |
| vs. `Single-pass` | WritingBench | 100 | 0 | 79/8/13 | 90.8% | 82.9%–95.3%; `8.38 x 10^-16` |
| `Single-context` |  |  |  |  |  |  |
| vs. `Single-pass` | HelloBench | 94 | 6 | 42/14/38 | 75.0% | 62.3%–84.5%; `2.34 x 10^-4` |
| `Single-context` |  |  |  |  |  |  |
| vs. `Single-pass` | DoLoMiTes | 95 | 5 | 58/8/29 | 87.9% | 77.9%–93.7%; `1.80 x 10^-10` |
| `Single-context` |  |  |  |  |  |  |
| vs. `Single-pass` | Pooled | 289 | 11 | 179/30/80 | 85.6% | 80.2%–89.8%; `4.96 x 10^-27` |

Table 13. Exploratory single-context results added after the primary results. The outcomes were judged by `gpt-5.6-sol medium` against the matched primary-condition outputs. Wilson intervals are descriptive; exact sign-test `p`-values exclude ties and are unadjusted for multiplicity. The runtime used a different gateway entry point and plain HTTP transport, with the generator model unchanged.

| Metric | `Single-pass` | Agentic CogWriter | `Single-context` |
|:---|---:|---:|---:|
| Completed | 289/300 | 293/300 | 300/300 |
| Output-plus-reasoning tokens per run | 4,874 | 13,374 | 14,497 |
| Wall-clock seconds per completed run | 61 | 426 | 123 |
| Goals created/developed/regenerated | 0/0/0 | 1,068/1,864/1 | 1191/971/0 |
| Ledger entries | 0 | 347 | 321 |
| Ledger entries with proposal | 0 | 3 | 0 |
| Spawns per attempted run | 0 | 3.22 | 0 |

Table 14. Process summaries use the matched primary-condition replication and the exploratory `Single-context` run. Structural auditing found 7 `Single-context` prompts missing `Planning`, 6 missing `Translating`, and 3 missing both, out of 300; the matched Agentic CogWriter audit found 6 prompts missing `Planning` and 7 missing `Translating`, out of 300.

### Cross-family judge robustness

The cross-family table reports pooled outcomes for the three robustness contrasts: 67/44/171 for Agentic CogWriter versus `Single-pass`, 76/25/184 for Agentic CogWriter versus `Task-planning`, and 39/27/221 for Agentic CogWriter versus `No-goals`. The corresponding Wilson intervals are 51.06%–68.97%, 66.01%–82.64%, and 47.05%–70.13%. The judge yields a non-tied combined outcome on 32.6% of 854 eligible pairs, with 182/96/576 overall W/L/T; 395/854 prompt-level outcomes agree with the same-family judge.

| **Contrast** | **Benchmark** | **`n`** | **W/L/T** | **Commit** | **Win rate** | **Agreement** |
|:---|:---|---:|---:|---:|---:|---:|
| Agentic CogWriter vs `Single-pass` | WritingBench | 96 | 19/21/56 | 41.67% | 47.50% | 31/96 |
| Agentic CogWriter vs `Single-pass` | HelloBench | 93 | 15/10/68 | 26.88% | 60.00% | 39/93 |
| Agentic CogWriter vs `Single-pass` | DoLoMiTes | 93 | 33/13/47 | 49.46% | 71.74% | 55/93 |
| Agentic CogWriter vs `Task-planning` | WritingBench | 93 | 28/8/57 | 38.71% | 77.78% | 41/93 |
| Agentic CogWriter vs `Task-planning` | HelloBench | 97 | 6/7/84 | 13.40% | 46.15% | 40/97 |
| Agentic CogWriter vs `Task-planning` | DoLoMiTes | 95 | 42/10/43 | 54.74% | 80.77% | 56/95 |
| Agentic CogWriter vs `No-goals` | WritingBench | 95 | 11/7/77 | 18.95% | 61.11% | 44/95 |
| Agentic CogWriter vs `No-goals` | HelloBench | 96 | 4/5/87 | 9.38% | 44.44% | 43/96 |
| Agentic CogWriter vs `No-goals` | DoLoMiTes | 96 | 24/15/57 | 40.62% | 61.54% | 46/96 |

Table 15. Cross-family judge robustness check using `claude-sonnet-5 medium`. Each row reports the outcome after combining the two presentation orders for each eligible prompt; `n` is the number of eligible pairs. Commit is the fraction of pairs with a non-tied cross-family outcome, and agreement is the fraction of prompts whose combined outcome agrees with the same-family judge. No multiplicity correction is applied.

## Habermas Machine pilot

The Habermas table reports trace totals from the pilot, which tests short consensus writing as a boundary condition rather than as another main benchmark.

| **Condition** | **Created** | **Developed** | **Regenerated** | **Ledger (no/proposal)** | **Pointwise** |
|:---|---:|---:|---:|---:|---:|
| `Single-pass` | 0 | 0 | 0 | 0/0 | 0.1258 |
| `Staged` | 0 | 0 | 0 | 0/0 | 0.1654 |
| `Task-planning` | 0 | 0 | 0 | 0/0 | -0.2169 |
| Agentic CogWriter | 39 | 37 | 0 | 15/0 | -0.0222 |
| `No-goals` | 0 | 0 | 0 | 0/0 | 0.0529 |
| `Fixed-order` | 12 | 27 | 0 | 11/0 | 0.1257 |
| `Exploratory-1` | 0 | 0 | 0 | 0/0 | -0.1605 |
| `Exploratory-2` | 0 | 0 | 0 | 0/0 | -0.1023 |

Table 16. The 80-run Habermas Machine pilot. The pilot completed 78 runs. Completed-run denominators in row order are 10/10, 10/10, 9/10, 10/10, 10/10, 10/10, 10/10, and 9/10. `Task-planning` and `Exploratory-2` each had one failed run; the table retains the trace totals reported in the pilot ledger.

`Exploratory-1` is the exploratory CogWriter-style baseline, with initial planning, immediate plan revision, parallel segment generation, and length review without a goal network; `Exploratory-2` is the exploratory STORM-style baseline, with perspective discovery, simulated question answering, outlining, per-section drafting, and polishing without retrieval. Agentic CogWriter does not lead the pointwise composite in this boundary-condition pilot; in particular, it scores below `Single-pass` and `Staged`. Agentic CogWriter and `Fixed-order` record 0 and 0 regeneration events, respectively; their ledgers contain 15/0 and 11/0 no/proposal outcomes, respectively.

## References

Anthropic. 2026. Agent skills.

<https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview>. Claude Platform Docs. Accessed: 2026-09-03.

Anthropic. 2026. Create custom subagents. <https://code.claude.com/docs/en/sub-agents>. Claude Code Docs. Accessed: 2026-09-03.

Yushi Bai, Jiajie Zhang, Xin Lv, Linzhi Zheng, Siqi Zhu, Lei Hou, Yuxiao Dong, Jie Tang, and Juanzi Li. 2025. Longwriter: Unleashing 10,000+ word generation from long context llms. In *International Conference on Learning Representations*, volume 2025, pages 36528–36546.

W. J. Dixon and A. M. Mood. 1946. [The statistical sign test](https://doi.org/10.1080/01621459.1946.10501898). *Journal of the American Statistical Association*, 41(236):557–566.

Wanyu Du, Vipul Raheja, Dhruv Kumar, Zae Myung Kim, Melissa Lopez, and Dongyeop Kang. 2022. [Understanding iterative revision from human-written text](https://doi.org/10.18653/v1/2022.acl-long.250). In *Proceedings of the 60th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)*, pages 3573–3590. Association for Computational Linguistics.

Yann Dubois, Balázs Galambosi, Percy Liang, and Tatsunori B. Hashimoto. 2024. [Length-controlled AlpacaEval: A simple way to debias automatic evaluators](https://arxiv.org/abs/2404.04475). *arXiv preprint arXiv:2404.04475*. COLM 2024.

Linda Flower and John R Hayes. 1981. A cognitive process theory of writing. *College Composition & Communication*, 32(4):365–387.

Katy Gero, Alex Calderwood, Charlotte Li, and Lydia Chilton. 2022. A design space for writing support tools using a cognitive process model of writing. In *Proceedings of the first workshop on intelligent and interactive writing assistants (In2Writing 2022)*, pages 11–24.

Google. 2026. Asynchronous subagents. <https://antigravity.google/docs/subagents/>. Google Antigravity Docs. Accessed: 2026-09-03.

Google. 2026. Skills. <https://antigravity.google/docs/skills/>. Google Antigravity Docs. Accessed: 2026-09-03.

John R Hayes. 1996. [A new framework for understanding cognition and affect in writing](https://doi.org/10.4324/9780203811122-2). In C. Michael Levy and Sarah Ransdell, editors, *The Science of Writing: Theories, Methods, Individual Differences, and Applications*, pages 1–27. Lawrence Erlbaum Associates, Mahwah, NJ.

John R Hayes. 2012. Modeling and remodeling writing. *Written communication*, 29(3):369–388.

Sture Holm. 1979. [A simple sequentially rejective multiple test procedure](https://www.jstor.org/stable/4615733). *Scandinavian Journal of Statistics*, 6(2):65–70.

Dawei Li, Renliang Sun, Yue Huang, Ming Zhong, Bohan Jiang, Jiawei Han, Xiangliang Zhang, Wei Wang, and Huan Liu. 2026. [Preference leakage: A contamination problem in LLM-as-a-judge](https://openreview.net/forum?id=grIvSXVJ65). In *International Conference on Learning Representations*.

Chris Lu, Cong Lu, Robert Tjarko Lange, Jakob Foerster, Jeff Clune, and David Ha. 2024. [The AI scientist: Towards fully automated open-ended scientific discovery](https://arxiv.org/abs/2408.06292). *arXiv preprint arXiv:2408.06292*.

Aman Madaan, Niket Tandon, Prakhar Gupta, Skyler Hallinan, Luyu Gao, Sarah Wiegreffe, Uri Alon, Nouha Dziri, Shrimai Prabhumoye, Yiming Yang, et al. 2023. Self-refine: Iterative refinement with self-feedback. *Advances in neural information processing systems*, 36:46534–46594.

Chaitanya Malaviya, Priyanka Agrawal, Kuzman Ganchev, Pranesh Srinivasan, Fantine Huot, Jonathan Berant, Mark Yatskar, Dipanjan Das, Mirella Lapata, and Chris Alberti. 2025. Dolomites: Domain-specific long-form methodical tasks. *Transactions of the Association for Computational Linguistics*, 13:1–29.

OpenAI. 2026. Build skills. <https://learn.chatgpt.com/docs/build-skills>. ChatGPT Learn. Accessed: 2026-09-03.

OpenAI. 2026. GPT-5.6: Frontier intelligence that scales with your ambition. <https://openai.com/index/gpt-5-6/>. Accessed 2026-10-05.

OpenAI. 2026. GPT-5.6 Luna model. <https://developers.openai.com/api/docs/models/gpt-5.6-luna>. Accessed 2026-10-05.

OpenAI. 2026. GPT-5.6 Sol model. <https://developers.openai.com/api/docs/models/gpt-5.6-sol>. Accessed 2026-10-05.

OpenAI. 2026. Subagents. <https://learn.chatgpt.com/docs/agent-configuration/subagents>. ChatGPT Learn. Accessed: 2026-09-03.

Arjun Panickssery, Samuel R. Bowman, and Shi Feng. 2024. [LLM evaluators recognize and favor their own generations](https://doi.org/10.52202/079017-2197). In *Advances in Neural Information Processing Systems*.

Haoran Que, Feiyu Duan, Liqun He, Yutao Mou, Wangchunshu Zhou, Jiaheng Liu, Wenge Rong, Zekun Moore Wang, Jian Yang, Ge Zhang, et al. 2024. Hellobench: Evaluating long text generation capabilities of large language models. *arXiv preprint arXiv:2409.16191*.

Samuel Schmidgall, Yusheng Su, Ze Wang, Ximeng Sun, Jialian Wu, Xiaodong Yu, Jiang Liu, Michael Moor, Zicheng Liu, and Emad Barsoum. 2025. [Agent laboratory: Using LLM agents as research assistants](https://doi.org/10.18653/v1/2025.findings-emnlp.320). In *Findings of the Association for Computational Linguistics: EMNLP 2025*, pages 5977–6043. Association for Computational Linguistics.

Yijia Shao, Yucheng Jiang, Theodore Kanell, Peter Xu, Omar Khattab, and Monica Lam. 2024. Assisting in writing wikipedia-like articles from scratch with large language models. In *Proceedings of the 2024 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies (Volume 1: Long Papers)*, pages 6252–6278.

Noah Shinn, Federico Cassano, Ashwin Gopinath, Karthik Narasimhan, and Shunyu Yao. 2023. Reflexion: Language agents with verbal reinforcement learning. *Advances in neural information processing systems*, 36:8634–8652.

Theodore Sumers, Shunyu Yao, Karthik R Narasimhan, and Thomas L. Griffiths. 2024. [Cognitive architectures for language agents](https://openreview.net/forum?id=1i6ZCvflQJ). *Transactions on Machine Learning Research*. Survey Certification, Featured Certification.

Zechen Sun, Yuyang Sun, Zecheng Tang, Juntao Li, Wenpeng Hu, Wenliang Chen, Zhunchen Luo, Guotong Geng, and Min Zhang. 2026. Is-cot: Breaking the long-form generation collapse via interleaved structural thinking. In *Proceedings of the 64th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)*, pages 19874–19887.

Haochen Tan, Zhijiang Guo, Zhan Shi, Lu Xu, Zhili Liu, Yunlong Feng, Xiaoguang Li, Yasheng Wang, Lifeng Shang, Qun Liu, and Linqi Song. 2024. [ProxyQA: An alternative framework for evaluating long-form text generation with large language models](https://doi.org/10.18653/v1/2024.acl-long.368). In *Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)*, pages 6806–6827. Association for Computational Linguistics.

Kaiyang Wan, Honglin Mu, Rui Hao, Haoran Luo, Tianle Gu, and Xiuying Chen. 2025. A cognitive writing perspective for constrained long-form text generation. In *Findings of the Association for Computational Linguistics: ACL 2025*, pages 9832–9844.

Peiyi Wang, Lei Li, Liang Chen, Zefan Cai, Dawei Zhu, Binghuai Lin, Yunbo Cao, Lingpeng Kong, Qi Liu, Tianyu Liu, and Zhifang Sui. 2024. [Large language models are not fair evaluators](https://doi.org/10.18653/v1/2024.acl-long.511). In *Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)*, pages 9440–9450. Association for Computational Linguistics.

Edwin B. Wilson. 1927. [Probable inference, the law of succession, and statistical inference](https://doi.org/10.1080/01621459.1927.10502953). *Journal of the American Statistical Association*, 22(158):209–212.

Yuhao Wu, Yushi Bai, Zhiqiang Hu, Juanzi Li, and Roy Ka-Wei Lee. 2026. [SuperWriter: Reflection-driven long-form generation with large language models](https://aclanthology.org/2026.findings-acl.428/). In *Findings of the Association for Computational Linguistics: ACL 2026*, pages 8790–8812. Association for Computational Linguistics.

Yuning Wu, Jiahao Mei, Ming Yan, Chenliang Li, Shaopeng Lai, Yuran Ren, Zijia Wang, Ji Zhang, Mengyue Wu, Qin Jin, et al. 2026. Writingbench: A comprehensive benchmark for generative writing. *Advances in Neural Information Processing Systems*, 38.

Ruibin Xiong, Yimeng Chen, Dmitrii Khizbullin, Mingchen Zhuge, and Jürgen Schmidhuber. 2025. Beyond outlining: Heterogeneous recursive planning for adaptive long-form writing with language models. In *Proceedings of the 2025 Conference on Empirical Methods in Natural Language Processing*, pages 24689–24725.

Kevin Yang, Yuandong Tian, Nanyun Peng, and Dan Klein. 2022. Re3: Generating longer stories with recursive reprompting and revision. In *Proceedings of the 2022 Conference on Empirical Methods in Natural Language Processing*, pages 4393–4479.

Lili Yao, Nanyun Peng, Ralph Weischedel, Kevin Knight, Dongyan Zhao, and Rui Yan. 2019. [Plan-and-write: Towards better automatic storytelling](https://doi.org/10.1609/aaai.v33i01.33017378). In *Proceedings of the AAAI conference on artificial intelligence*, volume 33, pages 7378–7385. AAAI.

Shunyu Yao, Jeffrey Zhao, Dian Yu, Nan Du, Izhak Shafran, Karthik R Narasimhan, and Yuan Cao. 2023. [React: Synergizing reasoning and acting in language models](https://openreview.net/forum?id=WE_vluYUL-X). In *The Eleventh International Conference on Learning Representations*.

Lianmin Zheng, Wei-Lin Chiang, Ying Sheng, Siyuan Zhuang, Zhanghao Wu, Yonghao Zhuang, Zi Lin, Zhuohan Li, Dacheng Li, Eric P. Xing, Hao Zhang, Joseph E. Gonzalez, and Ion Stoica. 2023. [Judging LLM-as-a-judge with MT-Bench and chatbot arena](https://doi.org/10.52202/075280-2020). In *Advances in Neural Information Processing Systems*, volume 36, pages 46595–46623.

[^1]: We use the model as the generator because the experiment requires high-volume long-form generation across systems and generation runs; OpenAI describes Luna as optimized for cost-sensitive, high-volume workloads and as the fastest, lowest-cost member of the GPT-5.6 family (OpenAI, 2026c; OpenAI, 2026b). Holding the generator fixed across conditions makes the comparison about writing architecture rather than base-model capability.

[^2]: We use the model as the evaluator because Sol is the higher-capability GPT-5.6 model for complex professional work and is reported to outperform Luna across multiple professional and reasoning evaluations (OpenAI, 2026d; OpenAI, 2026b). This places a stronger model in the evaluator role, although the shared model family still motivates the cross-family check described below.

[^3]: The native scores therefore describe our shared-generator implementations under the benchmark rubrics and should not be compared numerically with published leaderboard values.
