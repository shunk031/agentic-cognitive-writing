## Revisiting the Cognitive Process Theory of Writing with Language Agents

Shunsuke Kitada  
Graduate School of Informatics and Engineering, The University of Electro-Communication  
`shunsuke.kitada@uec.ac.jp`

## Abstract

Language-model writing systems decide what to do next in terms of sections, subtasks, or plans. The cognitive process theory of writing (Flower and Hayes, 1981) instead has a monitor decide which writing process, planning, translating, or reviewing, runs next, and no autonomous writer has been built that way. We build Agentic CogWriter, a writing system made of skills and subagents that uses a coding agent as its harness: a `Monitor` skill chooses the next writing process and delegates `Planning`, `Translating`, and `Reviewing` to `Planner`, `Translator`, and `Reviewer` subagents over a shared draft and goal network. We compare it with single-pass, staged, and task-planning writers on the most demanding prompts of WritingBench, HelloBench, and DoLoMiTes, and we switch off each of the theory’s three commitments in turn. The delegating writer wins 80.9% of decided comparisons against single-pass writing and is also favored over the staged and task-planning writers. Of the three commitments, only the split into separate agents shows a clear loss when removed; removing the goal network or the dynamic process order shows no detectable loss, and the `Monitor` mostly follows the textbook order on its own. A judge from another model family agrees on direction but decides only a third of the pairs, and all confirmatory judgments come from the generator’s own model family.

## Introduction

> *“Reading maketh a full man; conference a ready man; and writing an exact man.”*
>
> — *Francis Bacon* (Bacon, 1625)

What makes a writer exact has since been studied as a process in which authors coordinate planning, drafting, and revision (Rohman, 1965; Flower and Hayes, 1981; Hayes, 1996; Hayes, 2012). Flower and Hayes (1981) made that coordination a matter of control. The processes recur in no fixed order, and a `Monitor`, guided by goals the writer keeps revising, decides which runs next. That account has guided writing research and the design of tools that support human writers (Gero et al., 2022), yet no writing system has made process selection its controller. Language agents make such a writer possible, and two questions follow: does a writer improve when its control follows the theory, and which part of the theory accounts for the gain?

Figure 1. The control loop in Agentic CogWriter. The `Monitor` selects a process and delegates it to the corresponding agent. The agent updates the shared draft, goal network, and history before control returns; the `Reviewer` can trigger goal regeneration.

Neither question has been answered: language-model writing systems adapt over units of work such as sections, subtasks, and plans (Bai et al., 2025; Xiong et al., 2025), never over the writing processes themselves.

In this paper, we present Agentic CogWriter, a writing agent whose controller chooses the next writing process rather than the next unit of work, and use it to answer both questions. The system is built from skills and subagents on a coding-agent harness: the `Monitor` is a skill, the `Planner`, `Translator`, and `Reviewer` subagents run the three processes, and the theory’s control commitments become ablations that change instructions rather than code. We compare seven writers on the most demanding prompts of the same three benchmarks, with three independent replications. The architecture is favored over the baselines, winning 80.9% of non-tied comparisons against single-pass writing.

The distinction matters because existing systems are not short of structure. They plan before drafting (Yang et al., 2022; Shao et al., 2024), decompose the task or refine a draft in rounds (Bai et al., 2025; Wan et al., 2025; Madaan et al., 2023), and interleave planning with execution (Xiong et al., 2025); what none of them does is make the choice of the next writing process the decision its controller takes. Flower and Hayes (1981) place control exactly there: their `Monitor` chooses among writing processes, the choice depends on the writer’s goals, and evaluating a partial draft can interrupt any process and revise those goals. Cognitively inspired systems borrow parts of this account (Wan et al., 2025), and the systems above share its vocabulary of planning, drafting, and revision (Yang et al., 2022; Madaan et al., 2023; Shao et al., 2024; Bai et al., 2025; Wan et al., 2025), but none adopts its controller.

Agentic CogWriter delegates `Planning`, `Translating`, and `Reviewing` to separate agents over a shared draft, a goal network, and a history, and the `Monitor` takes control back after each process. The same plugin runs unchanged on two host platforms, so the writer described here is one a reader can run.

The theory makes three commitments that an implementation can keep or drop (Flower and Hayes, 1981): the writer maintains a network of goals that it keeps revising, a `Monitor` chooses which process runs next rather than following a fixed order, and the processes are distinct rather than one undifferentiated act of writing. We turn each commitment into an ablation. The goal-network ablation drops the goal network, the fixed-order ablation replaces the `Monitor`’s choice with a fixed cycle, and the single-writer ablation keeps one agent writing paragraph by paragraph with no delegation; a loss after removing a commitment would show that it contributed, whereas no detectable loss does not show that it contributed nothing. We compare the full system and these three ablations with three writers built the way current systems are built, a single call, fixed stages, and adaptive task planning, on WritingBench (Wu et al., 2026), HelloBench (Que et al., 2024), and DoLoMiTes (Malaviya et al., 2025), with the comparisons and their correction for multiple testing fixed in advance (Section 4.5); Section 4.1 states the three research questions.

This paper makes two contributions. First, it turns the cognitive process theory of writing into a running writer: the `Monitor` is a skill on a coding agent, the `Planner`, `Translator`, and `Reviewer` subagents run the three processes, and each of the theory’s commitments can be switched off by changing an instruction. Second, it reports which of those commitments made a measurable difference. Only one did: when the three processes are folded back into one agent, the writer loses clearly, whereas removing the goal network or the dynamic process order shows no detectable loss, and the traces show the `Monitor` mostly following the textbook order on its own. Two caveats apply throughout. The single-agent ablation also changes how finely the writer recurses and how much it writes, so the loss cannot be attributed to delegation alone; and every confirmatory judgment came from a model in the generator’s family, which we check with a judge from another family and with output-length matching.

## Related work

The theory decides over writing processes; existing systems decide over units of work. Table 1 compares their control units, and the rest of this section reviews each line of work in turn.

| **Method** | **Control State** | **Control Unit** | **Decision** | **Evolving Structure** |
|:---|:---|:---|:---|:---|
| Re`^3` ; (Yang et al., 2022) | Plan `P` ; Text `D_t` | Passage | `D_(t+1) = pi_gen (P,D_t) [generation policy]` | Text `D_t` |
| STORM ; (Shao et al., 2024) | Outline `O_t` ; Evidence `E_t` | Section | `D_t = pi_gen (O_t,E_t) [generation policy]` | Text `D_t` |
| CogWriter ; (Wan et al., 2025) | Hierarchical plan `P` ; Constraints `C` ; Text `D_t` | Plan ; output | `pi_check (P,D,C) in (accept,revise) [validation policy]` | Plan `P` ; Text `D_t` |
| WriteHERE ; (Xiong et al., 2025) | Task graph `T_t` ; Written text `D_t` | Task node ; `v_t` | `v_t = pi_task (T_t) [task-selection policy]` | Task graph `T_t` |
| **Ours** | **Text `D_t`** ; **Goal network `G_t`** ; **Process history `H_t`** | **Writing** ; **process `a_t`** | `a_t = pi_monitor (D_t,G_t,H_t) [process-selection policy]` | **Text `D_t`** ; **Goal network `G_t`** ; **Process state** |

Table 1. Architecture-level comparison of long-form writing systems. Here, `pi` denotes a decision policy, with its lowercase word subscript indicating the type of decision made. `t` is a writing step; `P` is a plan, `O_t` an outline, `E_t` evidence, and `C` constraints. `D_t` denotes the text at step `t`, `G_t` the evolving writer-goal network, `H_t` the process history, `T_t` the dynamic task graph, `v_t` the selected task node, and `a_t` the selected writing process. The equations provide a common abstraction of the architectures rather than reproducing their original formulations.

### Cognitive process models of writing

Cognitive writing models treat composition as more than linear text production. Flower and Hayes (1981) describe interacting `Planning`, `Translating`, and `Reviewing` processes coordinated by a `Monitor` and guided by writer-generated goals. Later accounts distinguish knowledge-telling from knowledge-transforming (Bereiter and Scardamalia, 1987), treat text production as knowledge generation (Galbraith, 1999), and revise the 1981 model (Hayes, 1996; Hayes, 2012). We use the 1981 account for its explicit process-control hypotheses, not as a complete theory of cognition.

### Task-oriented control for language-model writing

Long-form generation research organizes what a language model does. Plan-and-Write (Yao et al., 2019) separates planning from realization; Re`^3` (Yang et al., 2022) drafts from a global plan; Self-Refine (Madaan et al., 2023) iterates feedback and revision; STORM (Shao et al., 2024) strengthens pre-writing; and LongWriter’s AgentWrite pipeline (Bai et al., 2025) decomposes long generation into subtasks. These systems control executable work units such as plans, passages, sections, or refinements.

Recent systems make those structures adaptive. WriteHERE (Xiong et al., 2025) interleaves recursive task decomposition with execution, and IS-CoT (Sun et al., 2026) runs a Plan, Write, Reflect cycle in which reflection checks progress and adjusts the next plan. Both decide over units of work; Agentic CogWriter decides which writing process runs next, and our fixed schedule is not a stand-in for IS-CoT.

### Process-oriented control for writing agents

Cognitive writing processes have mainly guided writing-support research. Gero et al. (2022) organize support systems around Planning, Translating, and Reviewing; CoCo Matrix (Wan et al., 2024) characterizes human–AI co-writing; Script&Shift (Siddiqui et al., 2025) supports movement between content development and rhetorical organization; and other systems infer process states or expose writing histories (Zhou et al., 2026). These systems do not make process selection the autonomous controller.

CogWriter (Wan et al., 2025) is closest to ours in autonomous generation. It combines hierarchical planning, generation agents, monitoring, and reviewing, but centers computation on task decomposition and local plans. Of the four systems, none exposes an explicit writer-goal state or a process-level trace (Appendix A). Our `Monitor` instead chooses among `Planning`, `Translating`, and `Reviewing` while maintaining a writer-goal representation. This process-level control also relates to cognitive architectures for language agents (Sumers et al., 2024) and interleaved agent loops (Yao et al., 2023; Shinn et al., 2023).

## Agentic CogWriter

Agentic CogWriter is a language-agent architecture that runs the cognitive process theory of writing (Flower and Hayes, 1981): at each step a `Monitor` chooses which writing process runs next, so the controller decides over writing processes rather than over sections or tasks (Table 1).

We implement the architecture with a `Monitor` and three delegated agents: a `Planner`, a `Translator`, and a `Reviewer`. The `Planner`, `Translator`, and `Reviewer` are subagents that run the `Planning`, `Translating`, and `Reviewing` processes and return control to the `Monitor`. The agents share the document, writer-goal network, and process history. The `Monitor` selects a process, invokes its corresponding agent, and receives the updated state.

### Control state and goal network

The control state at writing step `t` is

`(D_t,G_t,H_t),`

where `D_t` is the text so far, `G_t` is the writer-goal network, and `H_t` records executed processes and goal events. The assignment and its constraints remain static task context.

We model a hierarchy of content, process, and evaluation goals: a sub-goal stays active under its parent, and resolving it returns attention to the parent. Following Flower and Hayes (1981), process goals say how to proceed and content goals say what to say for an audience, and goals arise throughout composing, either as sub-goals of an existing purpose or by regenerating a top-level goal in light of what the draft reveals. The implementation records each goal and every creation, development, and regeneration event as state and trace entries.

### Writing processes

The `Planner` runs `Planning` to generate or refine goals and organize their pursuit. The `Translator` runs `Translating` to realize active goals as prose and primarily updates `D_t`:

`D_t -> D_(t+1).`

Process execution can expose missing information, conflicting goals, or organizational problems. The `Reviewer` runs `Reviewing` to evaluate `D_t` against active goals. Evaluation may lead to further `Planning` or `Translating`, and can culminate in goal revision when the draft reveals a changed purpose. Goal-network change is therefore not assigned to `Reviewing` alone.

### Monitor-based process selection

The `Monitor`’s decision at step `t` is

`a_t=pi_monitor(D_t,G_t,H_t),`

where `a_t` is one of the three writing processes. In the evaluated system, `pi_monitor` is a prompted decision by the host agent over the current state and open uncertainty, not a separate learned classifier or a fixed rule. The selected process updates the state, and the process and goal events enter `H_t`. The loop permits transitions during composition: `Translating` can expose a problem that calls for `Planning`, `Reviewing` can call for `Planning` or `Translating`, and resolving a local goal can return attention to a parent goal. The loop ends when `Reviewing` returns no next process.

## Experiments

### Research questions

We define three research questions that separate product quality, mechanisms, and process behavior:

- **RQ1: Effectiveness.** Does the delegating writer produce better long-form writing than a single call, fixed stages, and adaptive task planning?

- **RQ2: What carries the effect?** Which of the theory’s commitments, the goal network, dynamic process selection, or distinct delegated processes, carries any improvement?

- **RQ3: Process dynamics.** What do the process traces show about how the `Monitor` actually behaved and how that compares with the theory’s account?

### Conditions

We compare seven organizations of long-form writing. Table 2 gives their control states, units, decisions, and evolving structures.

| **Condition** | **State** | **Unit** | **Choice** | **Structure** |
|:---|:---|:---|:---|:---|
| *Baselines* | *Baselines* | *Baselines* | *Baselines* | *Baselines* |
| `Single-pass` | Assignment `X` | Document | `D_t=pi_writer(X)` | None |
| `Staged` (Yang et al., 2022; Wan et al., 2025) | `X`; stages | Stage | `a_t=sigma_stage(t)` | Stages; `D_t` |
| `Task-planning` (Xiong et al., 2025) | `D_t`; graph `T_t` | Task node | `v_t=pi_task(T_t,D_t)` | `D_t`; `T_t` |
| *Agentic CogWriter variants* | *Agentic CogWriter variants* | *Agentic CogWriter variants* | *Agentic CogWriter variants* | *Agentic CogWriter variants* |
| `Full` | `D_t`; `G_t`; `H_t` | Process | `a_t=pi_monitor(D_t,G_t,H_t)` | `D_t`; `G_t`; `H_t` |
| `No-goals` | `D_t`; `H_t` | Process | `a_t=pi_monitor(D_t,H_t)` | `D_t`; `H_t` |
| `Fixed-order` | `D_t`; `G_t`; `H_t` | Process | `a_t=sigma_cycle(t)` | `D_t`; `G_t`; `H_t` |
| `Single-writer` | `D_t`; `G_t` | Paragraph | `pi_writer(D_t,G_t)` | `D_t`; `G_t` |

Table 2. Experimental conditions. Here `X` is the assignment, `t` is a writing step, `D_t` is the current document, `G_t` is the current goal network, `H_t` is the process history, `a_t` is the selected process, and `v_t` is the selected task node. The table records the control state, unit, decision rule, and evolving structure for the four primary conditions and three ablations. `Single-writer` uses one writer context and no delegation.

We re-implement the three baselines of the cited designs on the same generator and harness, so control alone varies across conditions; the published systems’ own implementations were not run, and the Limitations section states what that trade-off leaves open.

##### `Staged`: Staged writing.

`Staged` runs fixed `Pre-Write``->``Write``->``Re-Write` stages.

##### `Task-planning`: Adaptive task planning.

`Task-planning` follows WriteHERE (Xiong et al., 2025) and operates on dependency-satisfied nodes.

##### `Fixed-order`: Fixed process order.

`Fixed-order` repeats the three process roles in a fixed cycle.

##### `Single-writer`: Single-writer recursion.

`Single-writer` uses a paragraph as the control unit, where one writer context chooses the next action without delegation.

### Benchmarks and prompt selection

##### Benchmarks.

We use WritingBench (Wu et al., 2026), HelloBench (Que et al., 2024), and DoLoMiTes (Malaviya et al., 2025). WritingBench asks for general-purpose writing judged against task-specific criteria, HelloBench asks for long-text generation across question answering, summarization, chat, completion, and heuristic generation, and DoLoMiTes asks for structured expert writing such as research plans, reports, and design documents. The source pools contain 1,000 WritingBench, 647 HelloBench, and 820 DoLoMiTes prompts.

##### Prompt selection.

We take the 100 prompts per benchmark that call for the longest documents, 300 in all. We rank prompts by word count plus the largest explicitly requested output length, exclude pilot identifiers and prompts above 6,000 words in either component, and select the longest 100 per benchmark by this key. Length is a proxy for difficulty, not a benchmark-provided difficulty score. All conditions receive the same prompt and benchmark information; external retrieval is disabled.

##### Why the hard slice.

We focus on the hard slice because even the most demanding prompts leave the benchmarks’ own scales little room to separate. On the benchmarks’ own scales and the pairwise preference defined in Section 4.5, WritingBench ranges from 7.044 for `Single-pass` to 7.54 for `Full` and HelloBench from 0.769 to 0.795, while the pairwise preference separates `Full` from `Single-pass`, `Staged`, and `Task-planning` at 80.9%, 67.3%, and 68.5% across the three replications (Tables 3 and 4). The prompts not selected are shorter by the rank key; the study did not evaluate them.

### Implementation

##### Controlled comparison.

We hold the generator, task input, available information, tool availability, and final-output contract constant across conditions, so differences reflect control alone. We replicate every prompt-condition pair three times because generator sampling is not fixed. Runtime settings are listed in Appendix B.

##### Harness.

We use the documented host platforms’ skills and subagent invocation (Anthropic, 2026a; Anthropic, 2026b; OpenAI, 2026a; OpenAI, 2026b; Google, 2026b; Google, 2026a). The host coding agent runs the Agentic CogWriter skill as the `Monitor`, while the `Planner`, `Translator`, and `Reviewer` are subagents over a shared working directory holding the draft, goal network, and history. This mapping makes the ablations instruction changes rather than code changes, and it makes the process invocations and traces recordable. The same plugin runs unchanged on two host platforms.

##### Conditions on the harness.

`Full` delegates `Planning`, `Translating`, and `Reviewing` to the corresponding role subagents under the host agent’s `Monitor`. `Task-planning` uses the same host agent to delegate one node at a time from a task graph, a dependency-linked graph of reasoning and composition tasks. `Single-writer` uses one agent that writes and revises paragraph by paragraph without delegation, so it has no `Planner`, `Translator`, or `Reviewer` subagents.

##### Traces.

An attempted run is every generation launched for a prompt-condition pair, and a completed run is an attempted run with the required final output and process trace; only completed runs enter completion denominators. The run manifests call the word-count unit used for generated text an output unit, and one delegated invocation a spawn. The traces record goal events for goal creation, development, and regeneration, and process events for switches among writing processes.

##### Termination.

`Full` stops when `Reviewing` returns no next process, as defined in Section 3.3, recorded in the trace as `to_process=null`. `Task-planning` stops when its root composition task becomes silent after completion or failure. `Single-writer` ends its paragraph-scale recursion by returning the complete final document. All conditions return the complete final document through the same output channel.

### Evaluation protocol

##### Judges.

We use one judge, `gpt-5.6-sol medium`, for three judgment types: a pairwise preference between two conditions’ outputs for the same prompt, judged for every run, plus a native score on the benchmark’s own scale and a pointwise composite, judged for the first replication. The judge shares the generator’s model family, so confirmatory claims are conditional on same-family judging.

##### Native and pointwise scores.

Native scores use each benchmark’s own scale. WritingBench uses a 1 to 10 scale, HelloBench uses the mean of its yes-or-no checklist on a 0 to 1 scale under its upstream contract, and DoLoMiTes has no native score in this protocol. Pointwise scores use the judge’s z-scored composite across rubric dimensions, comparable across benchmarks but not a benchmark scale.

##### Replication.

We judge pairwise preference for every run because it is the confirmatory estimand and measures between-replication variability. Native and pointwise scores, the process summary, and the output-length bins come from the first replication. We report pooled pairwise rates as the mean and sample standard deviation (SD) across the three replications after collapsing the two presentation-order judgments into one prompt outcome, and we count Holm-surviving cells per replication.

##### Confirmatory design.

We judge each pair in both presentation orders and collapse the two judgments into one prompt outcome. Agreement keeps the shared winner, whereas any disagreement, including a winner-versus-tie result, becomes a tie. We drop a prompt when either condition lacks a completed run, so one collapsed outcome per prompt is the estimand.

The confirmatory family contains eight contrasts: `Full` versus `Single-pass`, `Staged`, `Task-planning`, `No-goals`, and `Fixed-order`; and `Single-writer` versus `Single-pass`, `Full`, and `No-goals`. These contrasts span three benchmarks, yielding 24 cells, and use the exact two-sided sign test on wins and losses after ties are excluded (Dixon and Mood, 1946). Holm’s step-down procedure orders the 24 `p` values and tests each against a threshold that loosens from 0.05/24 upward, stopping at the first failure, so that the family-wise probability of one or more false positives across the family is at most 5 percent (Holm, 1979).

We size this design for its estimand: the 300 pooled prompts leave about 282 eligible pairs and 220 decided comparisons per contrast, enough for the exact sign test to detect a true preference of about 63% with 80 percent power at the first Holm threshold, whereas a 100-prompt benchmark cell, with about 75 decided comparisons, detects only preferences near 73%. We report pooled rates and their 95 percent Wilson intervals (Wilson, 1927) as descriptive summaries.

##### Robustness checks.

We test judge-family robustness with `claude-sonnet-5 medium` through Bedrock, both presentation orders, and prompt-collapsed outcomes for the same 854 eligible pairs. The descriptive check pools each contrast without multiplicity correction, and its per-benchmark counts are descriptive. The check is not a second confirmatory family because each cell contains about 100 prompts and the judge commits on 32.6% of pairs. We report win/loss/tie (W/L/T) counts for the robustness check. We test output-length sensitivity with output units in the run manifests, 5 percent and 10 percent matching bands, and exact two-sided sign tests; the output-length bins come from the first replication.

##### Process-level analysis.

We compare observable traces at each condition’s control unit by analyzing `Task-planning` through `Single-writer` and counting process transitions, goal events, regeneration, returns to higher-level goals, task decomposition, and execution events. We do not combine task and writing-process events because the conditions use different control units.

## Results

### RQ1: Effectiveness

##### Pairwise preference.

Table 3 and Figure 2 report the primary pairwise answer to RQ1. Under same-family pairwise judging on 300 hard prompts, the prompt-collapsed pooled win rates across the three replications for `Full` are 80.9% (SD 2.8%) against `Single-pass`, 67.3% (SD 3.9%) against `Staged`, and 68.5% (SD 1.9%) against `Task-planning`. `Full` is directionally favored in every benchmark cell against `Single-pass` and `Task-planning` across all three replications; `Full` versus `Staged` is directionally favored in every cell except DoLoMiTes in the third replication, where the rate is 49.3%.

Figure 2 plots the same prompt-collapsed rates and intervals by benchmark and replication. Across the nine benchmark-by-replication cells, Holm correction retains 8 for `Full` versus `Single-pass`, 3 for `Full` versus `Staged`, and 4 for `Full` versus `Task-planning`. The directional pattern is broader than the corrected evidence: `Full` remains above `Single-pass` and `Task-planning` in all nine cells, while `Full` versus `Staged` keeps the DoLoMiTes exception in the third replication.

Figure 2. The plot visualizes the same prompt-collapsed rates and intervals per benchmark and replication for the eight confirmatory contrasts. Rows compare `Full` with `Single-pass`, `Staged`, `Task-planning`, `No-goals`, and `Fixed-order`, followed by `Single-writer` contrasts. Points show the three replications with 95 percent Wilson intervals; diamonds show their mean, and filled or open circles mark cells that do or do not survive Holm correction.

| **Contrast** | **WritingBench** | **HelloBench** | **DoLoMiTes** | **Pooled mean (SD)** |
|:---|---:|---:|---:|---:|
| `Full` vs `Single-pass` | 84.3% (2.2%) | 85.7% (2.3%) | 72% (7%) | 80.9% (2.8%) |
| `Full` vs `Staged` | 80.9% (2.9%) | 62.8% (4.9%) | 55.9% (5.9%) | 67.3% (3.9%) |
| `Full` vs `Task-planning` | 65.5% (6.2%) | 63% (6.9%) | 75.7% (6.7%) | 68.5% (1.9%) |
| `No-goals` vs `Full` | 47.9% (5%) | 47.6% (4.5%) | 44% (6.2%) | 46.6% (1.1%) |
| `Fixed-order` vs `Full` | 43.2% (1.4%) | 42.6% (2.9%) | 45.3% (3.2%) | 43.7% (1.3%) |
| `Single-writer` vs `Full` | 31.5% (3.6%) | 16.6% (1.9%) | 32.2% (2.7%) | 26.5% (2.1%) |
| `Single-writer` vs `Single-pass` | 72% (6.4%) | 39.8% (4.9%) | 54.8% (8.1%) | 56.4% (3.7%) |

Table 3. Prompt-collapsed pairwise outcomes for the three primary contrasts and four ablation contrasts. Each cell reports the first-listed condition’s mean win rate (sample SD in percentage points) across the three replications, with prompt-level ties removed within each replication; Holm significance is reported in the text for the per-benchmark confirmatory cells.

##### Native and pointwise scores.

Table 4 shows that the native and pointwise scores separate the four primary conditions far less than the pairwise preference does: `Full` leads both native scales, yet the whole WritingBench range from `Single-pass` to `Full` is 7.044 to 7.54 on a 1 to 10 scale, while the pointwise ordering varies by benchmark and places `Staged` above `Full` on DoLoMiTes.

|  |  |  |  |  |  |  |
|:---|:--:|:--:|:--:|:--:|:--:|:--:|
| **Condition** | **WritingBench** | **WritingBench** | **HelloBench** | **HelloBench** | **DoLoMiTes** | **DoLoMiTes** |
|  | **Native** | **Pointwise** | **Native** | **Pointwise** | **Native** | **Pointwise** |
| `Single-pass` | 7.044 | -0.093 | 0.769 | -0.119 | – | -0.019 |
| `Staged` | 7.084 | -0.054 | 0.78 | -0.007 | – | 0.103 |
| `Task-planning` | 7.258 | -0.062 | 0.781 | 0.04 | – | -0.166 |
| `Full` | 7.54 | 0.115 | 0.795 | 0.058 | – | 0.005 |

Table 4. Native and pointwise product scores from the first replication for the four primary conditions, as defined in Section 4.5. Completion is reported in Table 5.

##### Robustness to output length.

Figure 3 shows the two robustness checks: output-length control in panel (a) and cross-family judging in panel (b). Figure 3(a) reports the longer side’s win rate across output-length ratio bins. The judge preferred the longer side in 66.12% of 1647 non-tied comparisons from the first replication (95 percent Wilson interval 63.80%–68.37%). Matching preserves the `Full` advantage over `Single-pass` in all three replications, supports `Full` over `Task-planning` in only one of the three replications, and leaves `Full` versus `No-goals` as a bounded null. Appendix C reports the record-pooled sensitivity estimates, and Appendix D gives the bin-level W/L/T counts and rates.

Figure 3. Output-length control and cross-family judging. (a) Bars show the longer side’s win rate among non-tied pairs across output-length ratio bins; bar annotations give total pair counts, including ties, and diamonds show `Full` versus `Single-pass` within 5 percent and 10 percent matching bands. (b) Bars compare same-family `gpt-5.6-sol medium` and `claude-sonnet-5 medium` win rates among non-tied pairs for `Full` versus `Single-pass`, `Task-planning`, and `No-goals`; right-side annotations report the `claude-sonnet-5 medium` tie share over all pairs. On WritingBench, the `Full` versus `Single-pass` result reverses direction under `claude-sonnet-5 medium`.

##### Robustness to judge family.

Figure 3(b) reports the cross-family judge’s pooled outcomes. Without multiplicity correction, cross-family judging preserves pooled direction for all three contrasts: 60.4% for `Full` versus `Single-pass` (47.50% on WritingBench), 75.2% for `Full` versus `Task-planning`, and 59.1% for `Full` versus `No-goals` (`p=0.1753`). The judge commits on 32.6% of pairs and has 32 direction conflicts. Appendix E lists the corresponding descriptive per-benchmark counts, commitments, and agreements.

### RQ2: What carries the effect?

Table 3 reports the four ablation rows; RQ2 yields bounded comparisons rather than equality tests. Under same-family judging across three replications, `Full` versus `No-goals` is a bounded null: the pooled win rate is 53.4% (SD 1.1%) for `Full`. `Full` versus `Fixed-order` has no per-benchmark cell surviving Holm correction in any replication. The untested pairs are `No-goals` and `Fixed-order` with `Single-pass`, `Staged`, or `Task-planning`, and `Single-writer` with `Staged`, `Task-planning`, or `Fixed-order`. The intervals do not establish equality or exclude smaller effects.

Table 3 shows the remaining ablation pattern: `Single-writer` versus `Single-pass` is mixed across benchmarks, with `Single-writer` winning on WritingBench, losing on HelloBench, and mixed on DoLoMiTes across all three replications. No HelloBench cell survives Holm correction after collapse. `Single-writer` wins only 26.5% (SD 2.1%) of non-tied comparisons against `Full` and 30.1% (SD 3.5%) against `No-goals` in the pooled summaries. These contrasts are consistent with delegated process roles carrying the effect, but they do not isolate that interpretation because `Single-writer` changes recursion granularity and output length and `Task-planning` changes the delegated unit.

### RQ3: Process dynamics

Table 5 shows what the delegating architecture costs and how much it delegates in the first replication: `Full` uses 13,374 output-plus-reasoning tokens per attempted run and 426 seconds per completed run against 4,874 tokens and 61 seconds for `Single-pass`, and it spawns 3.22 delegated invocations per attempted run against 8.09 for `Task-planning`, which uses more tokens and loses the pairwise contrast. The table also reports completion, median output units, and input tokens for all seven conditions.

The process-trace analysis reports means across the three replications, with sample standard deviations (SD) in parentheses. A ledger entry is the enumeration recorded when `Reviewing` hands control back, listing every regeneration verdict or stating that none was proposed. Across the three replications, the `Full` traces contain 1,101.3 (SD 60.4) goal-creation events and 1,915.3 (SD 46.9) goal-development events per run. Its post-`Reviewing` ledger contains 353.7 (SD 7) entries per run, including 3.7 (SD 1.2) explicit regeneration proposals; accepted regeneration occurs between 1 and 4 times across the three replications. The `Fixed-order` traces contain 288 (SD 26.7) goal-creation events, 1,176.7 (SD 62.6) goal-development events, and 301 (SD 10.8) ledger entries per run, including 4 (SD 3.5) explicit proposals. Under same-family judging, `Task-planning` delegates more often than `Full`, with 8.17 (SD 0.27) versus 3.24 (SD 0.03) mean spawns per attempted run, yet `Full` beats `Task-planning`.

| **Condition** | **Completed** | **Median**; **units** | **Spawns**; **/run** | **Goals created**; **developed/regenerated** | **Output**; **tokens**; **/run** | **Input**; **tokens**; **/run** | **Mean sec.**; **/completed run** |
|:---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| `Single-pass` | 289/300 | 1,654 | 0 | 0/0/0 | 4,874 | 13,263 | 61 |
| `Staged` | 300/300 | 1,510 | 0 | 0/0/0 | 10,728 | 21,822 | 77 |
| `Task-planning` | 292/300 | 1,702 | 8.09 | 0/0/0 | 17,851 | 62,871 | 298 |
| `Full` | 293/300 | 1,835 | 3.22 | 1,068/1,864/1 | 13,374 | 46,860 | 426 |
| `No-goals` | 294/300 | 1,762 | 3.04 | 0/0/0 | 9,788 | 39,317 | 345 |
| `Fixed-order` | 282/300 | 1,773 | 3.43 | 267/1,163/3 | 11,402 | 42,888 | 219 |
| `Single-writer` | 280/300 | 1,111 | 0 | 1,621/169/1 | 15,356 | 30,715 | 103 |

Table 5. Process summary from the first replication across the 300-prompt hard set. All cells are values from the first replication derived from the process-summary JSON source. Completed is the count of completed runs. Spawns are mean delegated invocations per attempted run. Output tokens are Codex-reported output plus reasoning tokens, and input tokens are uncached input tokens; both are means over attempted runs. Wall-clock time is the mean seconds for completed runs.

Figure 4 shows that the traces mostly follow the planned `Planning``->``Translating``->``Reviewing` cycle. The trace source contains 886 completed `Full` runs and 874 completed `Fixed-order` runs across the supplied replications. Exact single-cycle sequences account for 56.4% of `Full` runs and 50.8% of `Fixed-order` runs, while cycle compliance reaches 74.6% and 89.8%, respectively. Among compliant `Full` runs, 99.2% made one pass; among compliant `Fixed-order` runs, 8.5% made two or three passes.

The traces show how the `Monitor` returns from `Reviewing` and how often it regenerates goals. After `Reviewing`, control returned to `Translating` in 14.8% of `Full` runs and to `Planning` in 0.3%. For `Fixed-order`, the corresponding rates were 1.0% and 9.7%; a return to `Planning` starts the next pass by design. Regeneration occurred in 4 `Full` runs and 10 `Fixed-order` runs.

The remaining trace comparisons do not explain why `Full` and `Fixed-order` reach similar product outcomes. Leading-process reconstruction accounted for 23/39 raw non-`Planning` starts in `Full` and 103/103 in `Fixed-order`. Exact-cycle status shows no association with wins under Fisher’s exact test (Fisher, 1922): exact-cycle `Full` runs won 57.4% of comparisons against `Fixed-order` versus 54.9% for other runs (`p=0.60`), and 72.2% versus 75.2% against `Single-writer` (`p=0.43`).

Figure 4. `Monitor` process selection across `Full` and `Fixed-order`. (a) Horizontal bars show the five most frequent observed process sequences per condition; labels join process abbreviations with arrows, and annotations give counts and shares of completed runs across the three replications. The key is P for `Planning`, T for `Translating`, and R for `Reviewing`. (b) and (c) show transition counts for `Full` and `Fixed-order` using the same P, T, R, and E abbreviations on both axes, with E denoting termination. Cycle compliance collapses immediate repeats, requires one or more complete `Planning``->``Translating``->``Reviewing` passes, and ends at `Reviewing`.

## Discussion

##### What the ablations attribute.

The ablations point to the split of the work among agents, not to the theory’s control dynamics. Folding the three processes back into one agent, `Single-writer`, wins only 26.5% of non-tied comparisons against `Full`, whereas removing the goal network or the dynamic process order shows no detectable loss. The traces show how little the control dynamics were exercised: given the freedom the theory demands, the `Monitor` reproduced the `Planning`, `Translating`, `Reviewing` order in 74.6% of runs, returned from `Reviewing` to `Planning` in 0.3% of runs, and accepted a goal regeneration in 4 runs, and its departures from that order showed no detectable association with wins. What the ablations cannot do is isolate the split itself: `Single-writer` also changes how finely the writer recurses and how much it writes, and `Task-planning` changes what is delegated, so the loss may come from any of those together.

##### What the checks bound.

The robustness checks in Figure 3 bound the evidence rather than overturn it. The judge prefers the longer side in 66.12% of non-tied pairs, yet the advantage over `Single-pass` survives the tested output-length matching bands in all three replications; a judge from another model family keeps every pooled direction but compresses that margin to 60.4%, reverses it on WritingBench at 47.50%, and commits on only 32.6% of pairs. The advantage over `Task-planning` shows the opposite pattern: it holds across judge families at 75.2% but survives length matching in only one of the three replications, with the second and third replications directionally above 50% but inconclusive. Same-family judging therefore still conditions the primary claims.

##### For writers who use coding agents.

For anyone who writes with a coding agent, the results translate into a setup and a budget. The setup is the plugin as evaluated: one skill for the `Monitor`, three role skills invoked as subagents, and a working directory holding the draft, the goals, and the history; because the ablations changed skill instructions rather than code, each process is an inspectable, replaceable unit. Across these replications, removing the goal ledger produced a bounded null and fixing the process order produced no Holm-surviving cell; neither result establishes equality, and the ablations do not establish delegation as necessary, so the single-writer ablation is the only one with a confirmed loss, which is consistent with delegated roles carrying the effect without isolating delegation. The budget is real: in the first replication, `Full` used 13,374 output-plus-reasoning tokens per attempted run and 426 seconds per completed run, against 4,874 tokens and 61 seconds for `Single-pass` (Table 5), while delegating less often than `Task-planning` and still winning that contrast. The gain was measured on prompts that demand long, structured documents; the 80-run Habermas pilot, in which `Full` ranks fifth of eight on the pointwise composite behind `Single-pass` and `Staged`, marks a boundary where `Full` did not lead.

##### For the theory.

For the theory, the result compares what the account describes with which of its mechanisms the implementation exercised, without establishing which parts are necessary. The account describes a writer who revises goals as the draft reveals them and who moves between processes as the draft demands; the implementation operationalized goal regeneration and post-`Reviewing` process choice, and it recorded regeneration in 4 of 886 runs and `Reviewing`-to-`Planning` transitions in 0.3% of runs, while the distinction the account draws between process goals and content goals (Flower and Hayes, 1981) motivates our distinction between process-boundary delegation and task-level planning. Transfer therefore remains an inference from the contrasts, not a statement about human writers: the goal events, ledgers, and process switches recorded here are the state of an agent, not evidence of human cognition.

##### Objections that remain.

A skeptical reader will raise four objections, and the evidence answers each only in part. First, the primary judge shares the generator’s model family; the cross-family judge agrees on the direction of every contrast but narrows the `Single-pass` margin and reverses it on WritingBench, so a same-family component remains. Second, the judge prefers longer outputs; the `Single-pass` advantage survives the tested output-length matching bands in all three replications, while the `Task-planning` advantage does so only in the first of the three replications. Third, every baseline is our re-implementation of the cited design under one generator family; the comparison is controlled, but it says nothing about the published systems’ own implementations or about other models. Fourth, the prompts are the 300 that demand the most writing; the design buys sensitivity where an architecture can differ and gives up external validity on routine prompts, and the Habermas pilot shows `Full` not leading on the pointwise composite for short consensus writing. Native scales compress differences, but the z-scored composite has no ceiling, and `Staged` exceeds `Full` on DoLoMiTes on that composite. The evidence therefore supports only bounded directional differences in these tested comparisons, with Holm support varying by contrast and benchmark; it does not establish gains from the goal network or dynamic process selection, or delegation as necessary.

## Conclusion

We made the cognitive process theory of writing executable on a coding agent and tested it. On the most demanding prompts of three benchmarks, the writer that delegates `Planning`, `Translating`, and `Reviewing` to separate agents wins most comparisons against single-pass, staged, and task-planning writers, and its margin over single-pass writing survives output-length matching and a change of judge family. Of the theory’s three commitments, only the split into separate agents made a measurable difference: removing the goal network or the dynamic process order showed no detectable loss, and the `Monitor` mostly followed the textbook order on its own. The ablations cannot separate that split from its side effects on output length and granularity, and the confirmatory judgments come from the generator’s own model family, so the result is a bounded one. For writers who use coding agents, our evidence supports delegating the three processes and shows no detectable gain from goal bookkeeping or from letting the `Monitor` reorder them; for the theory, its control dynamics did not show up in the product.

The plugin, the experiment runner, and the analysis scripts accompany the paper.[^1]

## Limitations

Completion differs across replications. Missing completed runs removed 161, 33, and 36 pairs in the three replications, because validation changes after the first replication raised completion; excluded pairs were dropped symmetrically, and every contrast kept its direction. The largest pooled between-replication SD is 3.9%, and Holm support varies by cell.

The main judge shares the generator’s model family, so same-family judging can favor shared preferences. The cross-family judge provides a partial check, but no human evaluation was performed, so agreement between the judge and human raters is unknown.

All generation used a single generator family, `gpt-5.6-luna`. The results therefore do not establish that the architecture’s advantage transfers to other generator families; a second-generator replication was not run. The baselines are likewise re-implementations of the cited designs under that generator, so the comparison is controlled but says nothing about the published systems’ own implementations or their reported results.

The cross-family judge commits on 32.6% of pairs, with 576 ties, 395/854 agreement, and 32 conflicts. Longer outputs win 66.12% of non-tied pairs. The cross-family judge’s high tie rate and the same-family judge’s length preference limit the checks.

The ablations do not isolate every implementation detail. `Single-writer` changes delegation, recursion granularity, and output length; `Task-planning` changes the control unit and delegated work. The comparisons support a mechanism-level interpretation but identify no necessary code path.

The hard prompt set samples the longest prompts by Section 4.3’s rank key, so length proxies difficulty rather than a benchmark score. Results do not establish performance on routine prompts or other task families. The demanding slice trades external validity for sensitivity.

The 80-run Habermas Machine pilot tests short consensus writing as a boundary condition, not a fourth benchmark; Appendix F reports its trace totals.

Process traces record implemented agent state, not human goals, monitoring, or discovery; the source theory defines an executable control hypothesis, not cognitive equivalence.

## Mechanism comparison

The mechanism-comparison table reports which computational mechanisms are explicit in the evaluated writing systems; it distinguishes modeled capacity from observed regeneration events.

| **Method** | **Recursive**; **Processes** | **Dynamic Process**; **Selection** | **Explicit Writer**; **Goal State** | **Writing-induced**; **Goal Revision** | **Process-level**; **Trace** |
|:---|:--:|:--:|:--:|:--:|:--:|
| Re`^3` (Yang et al., 2022) | Partial | – | – | – | – |
| STORM (Shao et al., 2024) | – | – | – | – | – |
| CogWriter (Wan et al., 2025) | Partial | – | – | Partial | – |
| WriteHERE (Xiong et al., 2025) | Partial | Partial | Partial | Partial | – |
| Agentic CogWriter **(Ours)** | yes | yes | yes | yes | yes |

Table 6. Comparison of computational mechanisms for controlling long-form writing. yes denotes an explicitly modeled mechanism, *Partial* denotes related functionality without an explicit representation of the corresponding writing-process construct, and – indicates that the mechanism is not explicitly modeled. The writing-induced goal revision column records modeled capacity, not an observed run event: across the three replications, `Full` recorded 2.3 (SD 1.5) accepted regenerations per run, and its ledger contained 353.7 (SD 7) entries, including 3.7 (SD 1.2) with proposals (Section 5.3).

## Runtime configuration

Runtime configuration records the execution settings needed to reproduce the runs without changing how the results are interpreted. The generator used `gpt-5.6-luna medium` with a 64,000 output-token budget; temperature was not set. Each run used one Codex CLI session in a container.

The pairwise judge used `gpt-5.6-sol medium` with seed 20260908 and two retries. The cross-family judge used `claude-sonnet-5 medium` through Bedrock with seed 20260908. Every condition received the same task input, available information, model, tool availability, and final-output contract.

## Record-pooled sensitivity analysis

The record-pooled table reports a sensitivity analysis that treats the two presentation records for each prompt as independent observations; the retained disagreements show how much presentation order can affect the descriptive rates. The retained presentation disagreements were 22.7% on WritingBench, 29.4% on HelloBench, and 21.4% on DoLoMiTes across the three replications.

| **Contrast** | **WritingBench** | **HelloBench** | **DoLoMiTes** | **Pooled mean (SD);**; **Wilson interval, first replication** |
|:---|:--:|:--:|:--:|:--:|
| `Full` vs `Single-pass` | 79.4% (0.8%) | 81.1% (1.2%) | 68.9% (6.2%) | 76.6% (2%); 73.1%–80.2% |
| `Full` vs `Staged` | 74.6% (1.8%) | 59.9% (2.4%) | 54.7% (5.5%) | 63.6% (2.9%); 60%–68.1% |
| `Full` vs `Task-planning` | 61.9% (4.5%) | 59.5% (4.8%) | 72.5% (6.7%) | 64.7% (1.8%); 62.5%–70.4% |
| `Full` vs `No-goals` | 51.5% (3.8%) | 50.8% (1.6%) | 53.7% (5.7%) | 51.9% (0.6%); 47.8%–56.4% |
| `Full` vs `Fixed-order` | 55% (0.6%) | 53.9% (1.3%) | 53.4% (3.1%) | 54.1% (0.9%); 50.3%–59% |
| `Single-writer` vs `Single-pass` | 66.7% (5.2%) | 41.6% (4.3%) | 53.7% (7.5%) | 54.4% (2.3%); 51.8%–60.4% |
| `Single-writer` vs `Full` | 35.5% (2.1%) | 20.5% (1.4%) | 35.4% (3.3%) | 30.4% (2%); 25.6%–33.3% |
| `Single-writer` vs `No-goals` | 37.2% (3.3%) | 21.5% (4%) | 43% (7.1%) | 33.8% (2.5%); 28.9%–36.9% |

Table 7. Record-pooled sensitivity analysis. The earlier design treated the two presentation records for each prompt as independent observations. Each cell reports the first-listed condition’s record-pooled mean win rate and sample SD across the three replications; the pooled column adds the Wilson interval from the first replication. These values are descriptive sensitivity results, not the confirmatory analysis.

## Output-length sensitivity

The length-control table reports the longer-side preference by output-length ratio; the longer side wins 66.12% of 1647 non-tied comparisons. Within 5 percent, the outcomes from the first replication are 25/3/7 for `Full` versus `Single-pass` (`p=2.74 x 10^-5`), 26/15/7 for `Full` versus `Task-planning` (`p=0.1173`), and 18/18/20 for `Full` versus `No-goals`. Within 10 percent, the corresponding outcomes are 40/11/17 (`p=5.70 x 10^-5`), 39/18/14 (`p=0.0075`), and 38/30/37 (`p=0.3961`). The 5/10-percent rates for `Full` versus `Single-pass` are 80.0%/82.7% in the second replication and 82.9%/80.7% in the third replication; the corresponding `Full` versus `Task-planning` rates are 57.1%/58.5% and 51.9%/50.9%. The `Full` versus `No-goals` replicate rates are 46.7%/45.7% and 59.5%/47.8%.

| **Output-length ratio** |  **W/L/T**  | **Longer-side**; **win rate** |
|:------------------------|:-----------:|:-----------------------------:|
| 1.00–1.05               | 123/104/91  |            54.19%             |
| 1.05–1.10               |  116/67/92  |            63.39%             |
| 1.10–1.25               | 291/185/177 |            61.13%             |
| 1.25–1.50               | 277/120/141 |            69.77%             |
| 1.50–2.00               |  188/68/66  |            73.44%             |
| 2.00+                   |  94/14/23   |            87.04%             |

Table 8. Prompt-collapsed pairwise outcomes from the first replication by output-length ratio. The longer side is the first-listed outcome in each row; ties are excluded from the win-rate denominator. Output units come from the run manifests.

## Cross-family judge robustness

The cross-family table reports pooled outcomes for the three robustness contrasts: 67/44/171 for `Full` versus `Single-pass`, 76/25/184 for `Full` versus `Task-planning`, and 39/27/221 for `Full` versus `No-goals`. The corresponding Wilson intervals are 51.06%–68.97%, 66.01%–82.64%, and 47.05%–70.13%. The judge commits on 32.6% of 854 pairs, with 182/96/576 overall W/L/T and 395/854 prompt-collapsed agreements.

| **Contrast** | **Benchmark** | **`n`** | **W/L/T** | **Commit** | **Win rate** | **Agreement** |
|:---|:---|---:|---:|---:|---:|---:|
| `Full` vs `Single-pass` | WritingBench | 96 | 19/21/56 | 41.67% | 47.50% | 31/96 |
| `Full` vs `Single-pass` | HelloBench | 93 | 15/10/68 | 26.88% | 60.00% | 39/93 |
| `Full` vs `Single-pass` | DoLoMiTes | 93 | 33/13/47 | 49.46% | 71.74% | 55/93 |
| `Full` vs `Task-planning` | WritingBench | 93 | 28/8/57 | 38.71% | 77.78% | 41/93 |
| `Full` vs `Task-planning` | HelloBench | 97 | 6/7/84 | 13.40% | 46.15% | 40/97 |
| `Full` vs `Task-planning` | DoLoMiTes | 95 | 42/10/43 | 54.74% | 80.77% | 56/95 |
| `Full` vs `No-goals` | WritingBench | 95 | 11/7/77 | 18.95% | 61.11% | 44/95 |
| `Full` vs `No-goals` | HelloBench | 96 | 4/5/87 | 9.38% | 44.44% | 43/96 |
| `Full` vs `No-goals` | DoLoMiTes | 96 | 24/15/57 | 40.62% | 61.54% | 46/96 |

Table 9. Cross-family judge robustness check using `claude-sonnet-5 medium`. Each row reports prompt-collapsed outcomes for the eligible pairs in that benchmark; `n` is the number of eligible pairs. Commit is the fraction of pairs with a non-tied cross-family outcome, and agreement is the fraction of prompts whose collapsed outcomes agree with the same-family judge. No multiplicity correction is applied.

## Habermas Machine pilot

The Habermas table reports trace totals from the 80-run pilot, which tests short consensus writing as a boundary condition rather than a fourth benchmark.

| **Condition** | **Created** | **Developed** | **Regenerated** | **Ledger (no/proposal)** | **Pointwise** |
|:---|---:|---:|---:|---:|---:|
| `Single-pass` | 0 | 0 | 0 | 0/0 | 0.1258 |
| `Staged` | 0 | 0 | 0 | 0/0 | 0.1654 |
| `Task-planning` | 0 | 0 | 0 | 0/0 | -0.2169 |
| `Full` | 39 | 37 | 0 | 15/0 | -0.0222 |
| `No-goals` | 0 | 0 | 0 | 0/0 | 0.0529 |
| `Fixed-order` | 12 | 27 | 0 | 11/0 | 0.1257 |
| `Exploratory-1` | 0 | 0 | 0 | 0/0 | -0.1605 |
| `Exploratory-2` | 0 | 0 | 0 | 0/0 | -0.1023 |

Table 10. The 80-run Habermas Machine pilot. The pilot completed 78 runs. Completed-run denominators in row order are 10/10, 10/10, 9/10, 10/10, 10/10, 10/10, 10/10, and 9/10. `Task-planning` and `Exploratory-2` each had one failed run; the table retains the trace totals reported in the pilot ledger.

`Exploratory-1` is the exploratory CogWriter-style baseline, with initial planning, immediate plan revision, parallel segment generation, and length review without a goal network; `Exploratory-2` is the exploratory STORM-style baseline, with perspective discovery, simulated question answering, outlining, per-section drafting, and polishing without retrieval. The full system ranks fifth of eight on the pointwise composite, behind `Single-pass` and `Staged` writing. `Full` and `Fixed-order` record 0 and 0 regeneration events, respectively; their ledgers contain 15/0 and 11/0 no/proposal outcomes, respectively.

## References

Anthropic. 2026. Agent skills.

<https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview>. Claude Platform Docs. Accessed: 2026-09-03.

Anthropic. 2026. Create custom subagents. <https://code.claude.com/docs/en/sub-agents>. Claude Code Docs. Accessed: 2026-09-03.

Francis Bacon. 1625. [Of studies](https://archive.org/details/essaysedited00bacouoft). In *The Essays or Counsels, Civil and Moral*. Charles Scribner’s Sons, New York. Essay 50. Quoted from the edition of Mary Augusta Scott, New York: Scribner, 1908, p. 234.

Yushi Bai, Jiajie Zhang, Xin Lv, Linzhi Zheng, Siqi Zhu, Lei Hou, Yuxiao Dong, Jie Tang, and Juanzi Li. 2025. Longwriter: Unleashing 10,000+ word generation from long context llms. In *International Conference on Learning Representations*, volume 2025, pages 36528–36546.

Carl Bereiter and Marlene Scardamalia. 1987. *The psychology of written composition*. L. Erlbaum Associates Hillsdale, NJ.

W. J. Dixon and A. M. Mood. 1946. [The statistical sign test](https://doi.org/10.1080/01621459.1946.10501898). *Journal of the American Statistical Association*, 41(236):557–566.

R. A. Fisher. 1922. [On the interpretation of chi-square from contingency tables, and the calculation of p](https://doi.org/10.1111/j.2397-2335.1922.tb00768.x). *Journal of the Royal Statistical Society*, 85(1):87–94.

Linda Flower and John R Hayes. 1981. A cognitive process theory of writing. *College Composition & Communication*, 32(4):365–387.

David Galbraith. 1999. Writing as a knowledge-constituting process. *Knowing what to write: Conceptual processes in text production*, 4:139–164.

Katy Gero, Alex Calderwood, Charlotte Li, and Lydia Chilton. 2022. A design space for writing support tools using a cognitive process model of writing. In *Proceedings of the first workshop on intelligent and interactive writing assistants (In2Writing 2022)*, pages 11–24.

Google. 2026. Asynchronous subagents. <https://antigravity.google/docs/subagents/>. Google Antigravity Docs. Accessed: 2026-09-03.

Google. 2026. Skills. <https://antigravity.google/docs/skills/>. Google Antigravity Docs. Accessed: 2026-09-03.

John R Hayes. 1996. [A new framework for understanding cognition and affect in writing](https://doi.org/10.4324/9780203811122-2). In C. Michael Levy and Sarah Ransdell, editors, *The Science of Writing: Theories, Methods, Individual Differences, and Applications*, pages 1–27. Lawrence Erlbaum Associates, Mahwah, NJ.

John R Hayes. 2012. Modeling and remodeling writing. *Written communication*, 29(3):369–388.

Sture Holm. 1979. [A simple sequentially rejective multiple test procedure](https://www.jstor.org/stable/4615733). *Scandinavian Journal of Statistics*, 6(2):65–70.

Aman Madaan, Niket Tandon, Prakhar Gupta, Skyler Hallinan, Luyu Gao, Sarah Wiegreffe, Uri Alon, Nouha Dziri, Shrimai Prabhumoye, Yiming Yang, et al. 2023. Self-refine: Iterative refinement with self-feedback. *Advances in neural information processing systems*, 36:46534–46594.

Chaitanya Malaviya, Priyanka Agrawal, Kuzman Ganchev, Pranesh Srinivasan, Fantine Huot, Jonathan Berant, Mark Yatskar, Dipanjan Das, Mirella Lapata, and Chris Alberti. 2025. Dolomites: Domain-specific long-form methodical tasks. *Transactions of the Association for Computational Linguistics*, 13:1–29.

OpenAI. 2026. Build skills. <https://learn.chatgpt.com/docs/build-skills>. ChatGPT Learn. Accessed: 2026-09-03.

OpenAI. 2026. Subagents. <https://learn.chatgpt.com/docs/agent-configuration/subagents>. ChatGPT Learn. Accessed: 2026-09-03.

Haoran Que, Feiyu Duan, Liqun He, Yutao Mou, Wangchunshu Zhou, Jiaheng Liu, Wenge Rong, Zekun Moore Wang, Jian Yang, Ge Zhang, et al. 2024. Hellobench: Evaluating long text generation capabilities of large language models. *arXiv preprint arXiv:2409.16191*.

D Gordon Rohman. 1965. Pre-writing: The stage of discovery in the writing process. *College Composition & Communication*, 16(2):106–112.

Yijia Shao, Yucheng Jiang, Theodore Kanell, Peter Xu, Omar Khattab, and Monica Lam. 2024. Assisting in writing wikipedia-like articles from scratch with large language models. In *Proceedings of the 2024 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies (Volume 1: Long Papers)*, pages 6252–6278.

Noah Shinn, Federico Cassano, Ashwin Gopinath, Karthik Narasimhan, and Shunyu Yao. 2023. Reflexion: Language agents with verbal reinforcement learning. *Advances in neural information processing systems*, 36:8634–8652.

Momin N Siddiqui, Roy D Pea, and Hari Subramonyam. 2025. Script&shift: A layered interface paradigm for integrating content development and rhetorical strategy with llm writing assistants. In *Proceedings of the 2025 CHI Conference on Human Factors in Computing Systems*, pages 1–19.

Theodore Sumers, Shunyu Yao, Karthik R Narasimhan, and Thomas L. Griffiths. 2024. [Cognitive architectures for language agents](https://openreview.net/forum?id=1i6ZCvflQJ). *Transactions on Machine Learning Research*. Survey Certification, Featured Certification.

Zechen Sun, Yuyang Sun, Zecheng Tang, Juntao Li, Wenpeng Hu, Wenliang Chen, Zhunchen Luo, Guotong Geng, and Min Zhang. 2026. Is-cot: Breaking the long-form generation collapse via interleaved structural thinking. In *Proceedings of the 64th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)*, pages 19874–19887.

Kaiyang Wan, Honglin Mu, Rui Hao, Haoran Luo, Tianle Gu, and Xiuying Chen. 2025. A cognitive writing perspective for constrained long-form text generation. In *Findings of the Association for Computational Linguistics: ACL 2025*, pages 9832–9844.

Ruyuan Wan, Simret Araya Gebreegziabher, Toby Jia-Jun Li, and Karla Badillo-Urquiola. 2024. Coco matrix: Taxonomy of cognitive contributions in co-writing with intelligent agents. In *Proceedings of the 16th Conference on Creativity & Cognition*, pages 504–511.

Edwin B. Wilson. 1927. [Probable inference, the law of succession, and statistical inference](https://doi.org/10.1080/01621459.1927.10502953). *Journal of the American Statistical Association*, 22(158):209–212.

Yuning Wu, Jiahao Mei, Ming Yan, Chenliang Li, Shaopeng Lai, Yuran Ren, Zijia Wang, Ji Zhang, Mengyue Wu, Qin Jin, et al. 2026. Writingbench: A comprehensive benchmark for generative writing. *Advances in Neural Information Processing Systems*, 38.

Ruibin Xiong, Yimeng Chen, Dmitrii Khizbullin, Mingchen Zhuge, and Jürgen Schmidhuber. 2025. Beyond outlining: Heterogeneous recursive planning for adaptive long-form writing with language models. In *Proceedings of the 2025 Conference on Empirical Methods in Natural Language Processing*, pages 24689–24725.

Kevin Yang, Yuandong Tian, Nanyun Peng, and Dan Klein. 2022. Re3: Generating longer stories with recursive reprompting and revision. In *Proceedings of the 2022 Conference on Empirical Methods in Natural Language Processing*, pages 4393–4479.

Lili Yao, Nanyun Peng, Ralph Weischedel, Kevin Knight, Dongyan Zhao, and Rui Yan. 2019. [Plan-and-write: Towards better automatic storytelling](https://doi.org/10.1609/aaai.v33i01.33017378). In *Proceedings of the AAAI conference on artificial intelligence*, volume 33, pages 7378–7385. AAAI.

Shunyu Yao, Jeffrey Zhao, Dian Yu, Nan Du, Izhak Shafran, Karthik R Narasimhan, and Yuan Cao. 2023. [React: Synergizing reasoning and acting in language models](https://openreview.net/forum?id=WE_vluYUL-X). In *The Eleventh International Conference on Learning Representations*.

David Zhou, Andrew Chen, John Joon Young Chung, and Sarah Sterman. 2026. Iris: Navigating and reflecting on writing traces using intelligent document histories. *arXiv preprint arXiv:2608.19614*.

[^1]: The repository link is withheld for anonymous review.
