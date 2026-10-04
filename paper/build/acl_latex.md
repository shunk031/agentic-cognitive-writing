## What Makes a Writing Agent Work? Revisiting the Cognitive Process Theory of Writing with Language Agents

Anonymous ACL submission

## Abstract

Long-form writing agents often organize generation through plans, sections, subtasks, and revision rounds. We ask a different question: should a writing agent decide which writing process to execute next? We instantiate this idea as Agentic CogWriter, a writing agent built on a coding-agent harness. The host agent implements the `Monitor`, which repeatedly chooses among `Planning`, `Translating`, and `Reviewing` using the current draft, an explicit representation of current writing goals, and a history of previous process choices. The corresponding `Planner`, `Translator`, or `Reviewer` role agent executes the chosen process. Across three complementary long-form writing benchmarks and independent replications, Agentic CogWriter is preferred to single-pass generation, fixed writing stages, and adaptive task planning. The mechanism results are more selective: removing the explicit goal representation or fixing the process order produces no detectable loss under our confirmatory test, and Agentic CogWriter’s `Monitor` usually follows a simple `Planning``->``Translating``->``Reviewing` cycle and rarely replaces existing goals. A diagnostic single-writer ablation performs substantially worse, but it simultaneously removes the three delegated role agents, limits each `Translating` step to one paragraph before the next process decision, and changes output length, so it does not isolate a single mechanism. Compute-matched analyses preserve the advantage over staged and task-planning baselines, while a cross-family judge preserves pooled directions but returns a non-tied judgment on only a minority of pairs. These results show the value of making theory commitments executable and testing them separately: under our design, writing-process decomposition is useful relative to the tested baselines, whereas explicit goal bookkeeping and adaptive process ordering do not explain the observed gain.

## Introduction

Long-form writing requires decisions about both *what* to write and *how* to proceed. Language-model writing systems externalize many of these decisions through plans, outlines, task decomposition, feedback, and revision (Yang et al., 2022; Madaan et al., 2023; Shao et al., 2024; Bai et al., 2025; Xiong et al., 2025). We use *controller* to refer to the part of a writing agent that determines what operation happens next. Existing controllers differ substantially in implementation, but they commonly advance a plan element, passage, section, or task node, or execute a prescribed sequence of operations. In other words, the controller usually selects a content item or task rather than the writing process itself. This leaves a basic design question open: *what should a writing agent be able to choose next?*

The cognitive process theory of writing (Flower and Hayes, 1981) suggests one concrete answer. Flower and Hayes describe `Planning`, `Translating`, and `Reviewing` as recurrent processes coordinated by a `Monitor`, and propose that writer-generated goals can change as composition proceeds. Later accounts revise and extend this model (Hayes, 1996; Hayes, 2012), but the 1981 formulation is especially useful for agent design because it makes several control commitments explicit: the writing processes form the available operations, their order can adapt during composition, and writing is guided by an evolving goal structure. We treat these commitments as experimentally separable hypotheses about agent control, not as a blueprint that should be copied wholesale or as a claim that a language agent reproduces human cognition. The resulting question is therefore not whether cognitive writing theory can be implemented in an agent, but which of its control commitments matter once made executable.

From this perspective, we formulate *process-level control*: the controller chooses which writing process to execute next. We instantiate this formulation as Agentic CogWriter, a writing agent built on a coding-agent harness. Agentic CogWriter maintains three external records while writing: the current draft, an explicit hierarchical representation of current writing goals, and a history of previous process choices and goal changes. We call the goal representation the *goal network*. The host agent implements the `Monitor`, which reads these records and chooses `Planning`, `Translating`, or `Reviewing`; the corresponding `Planner`, `Translator`, or `Reviewer` role agent then executes that process before control returns to the `Monitor`. This operationalization exposes three theory-derived commitments for intervention: explicit goal representation, adaptive process ordering, and separated role contexts.

Figure 1. Two answers to the question of what a writing controller should choose next. Representative structured writing systems use task/content-level control, choosing a section, passage, or task node to work on (left). Agentic CogWriter uses process-level control, choosing among `Planning`, `Translating`, and `Reviewing` from the current draft, goal network, and process history (right). The tested interventions remove the explicit goal representation, adaptive process ordering, or separated role contexts. The single-writer intervention also removes delegation and restricts each `Translating` step to one paragraph before the next process decision, so it does not cleanly isolate separated role contexts.

We ask three research questions. **RQ1** asks whether organizing generation around writing processes improves long-form writing relative to generation with no intermediate choice, a fixed stage sequence, and adaptive choice over task nodes. **RQ2** asks what controlled interventions reveal about the explicit goal representation, adaptive process ordering, and separated role contexts. **RQ3** asks what observable process traces reveal about how the `Monitor` actually uses process-selection flexibility and goal changes during writing.

We evaluate Agentic CogWriter on long-form writing tasks from three complementary benchmarks: WritingBench (Wu et al., 2026), HelloBench (Que et al., 2024), and DoLoMiTes (Malaviya et al., 2025). Within each benchmark, a pre-specified rule selects the longest-output slice, where control choices have more opportunity to affect composition. Using the same generator and coding-agent harness, we compare Agentic CogWriter with single-call generation, a fixed three-stage workflow, and adaptive task planning across three independent replications. Agentic CogWriter is preferred to all three baselines. The mechanism results are more selective: removing the explicit goal representation or replacing adaptive process choice with a fixed `Planning``->``Translating``->``Reviewing` cycle produces no detectable loss. The process traces further show that the unrestricted `Monitor` usually follows that cycle and rarely replaces existing goals. A diagnostic single-writer condition performs substantially worse, but because it changes several execution factors together, it does not isolate separated role contexts. Thus, the experiments support process-organized generation relative to the tested baselines without identifying goal bookkeeping or adaptive process scheduling as the source of the observed advantage.

Our contributions are threefold. First, we frame long-form writing-agent design around what the controller chooses next, distinguishing content or task selection from process-level control. Second, we turn commitments from cognitive writing theory into an executable agent design whose goal representation, process ordering, and role contexts can be observed and intervened on separately. Third, we provide evidence across three benchmarks and replications that process-organized generation outperforms the tested baseline organizations, while two prominent theory-derived commitments, explicit goal bookkeeping and adaptive process ordering, do not explain that advantage under our design. Together, these results show how cognitive theory can serve not only as architectural inspiration, but as a source of falsifiable design hypotheses for language agents.

## Background and Related Work

##### Writing as a controlled process.

Writing research has long treated composition as more than a fixed sequence of stages. Flower and Hayes (Flower and Hayes, 1981) describe writing as recurrent coordination among processes, while later theories emphasize knowledge transformation, knowledge generation, and revised accounts of cognition and affect (Bereiter and Scardamalia, 1987; Galbraith, 1999; Hayes, 1996; Hayes, 2012). This literature exposes separable claims about control: what operations are available, what state guides them, and how their ordering can change during composition. We use the 1981 model selectively because its named processes, coordinating `Monitor`, and mutable goals can become explicit agent actions and records. We therefore treat the theory as a source of testable design commitments, not as a claim of cognitive equivalence.

##### Structured long-form generation.

Long-form language-model systems differ in what advances generation. Plan-and-Write and Re`^3` organize generation around plans and planned passages (Yao et al., 2019; Yang et al., 2022); STORM advances an outline section by section (Shao et al., 2024); and LongWriter’s AgentWrite decomposes a document into subtasks (Bai et al., 2025). WriteHERE makes next-step choice adaptive by recursively expanding a heterogeneous task graph and scheduling dependency-satisfied retrieval, reasoning, and composition nodes (Xiong et al., 2025). Other systems use recurring process-like stages: Self-Refine alternates generation, feedback, and refinement (Madaan et al., 2023), while IS-CoT interleaves Plan–Write–Reflect (Sun et al., 2026). The comparison relevant here is whether the controller advances content or task units, follows a prescribed process sequence, or can choose among writing processes themselves. Appendix A summarizes representative systems using this descriptive vocabulary.

##### Cognitively inspired writing systems.

Cognitive writing models have also informed interactive writing support and analyses of human–AI co-writing (Gero et al., 2022; Wan et al., 2024; Siddiqui et al., 2025; Zhou et al., 2026). CogWriter (Wan et al., 2025) is the closest autonomous long-form system, combining hierarchical planning, parallel generation agents, monitoring, and review under cognitive-writing motivation. Our contribution is therefore not to introduce cognitive theory as inspiration for writing agents. Instead, we make a narrower set of control commitments experimentally separable: writing processes form the `Monitor`’s action space, the goal representation can be removed, process ordering can be fixed, and execution contexts can be altered. This lets us test which executable commitments affect outcomes and how the resulting controller behaves.

## Agentic CogWriter: Process-Level Writing Control

Agentic CogWriter repeats a simple control loop until the `Monitor` decides that no further writing process is needed. At the start of each iteration, the `Monitor` reads the external records maintained by the agent, chooses one writing process, and dispatches the corresponding role agent. When that role agent finishes, its output is written back to the shared records and control returns to the `Monitor`.

### External writing records

Agentic CogWriter maintains three records throughout a run. The *draft* stores the text produced so far. The *goal network* stores the current writing goals in a hierarchical form. The *process history* records previous process choices and changes to those goals.

The goal network is our explicit representation of the writer-generated goals proposed by Flower and Hayes (Flower and Hayes, 1981). Content goals describe what the document should communicate, process goals describe how the writing should proceed, and evaluation goals describe criteria for judging the draft. These goals can change as writing proceeds. A goal may be created, made more specific, or replaced when writing changes its purpose or level of abstraction. We call this last operation *goal regeneration*. Goal creation, development, and regeneration are all recorded in the process history. This representation makes goal changes observable; it does not imply that the language model has a corresponding latent cognitive state.

For compact notation, let `D_t` denote the draft, `G_t` the goal network, and `H_t` the process history immediately before the `Monitor`’s `t`-th decision. We use

`S_t=(D_t,G_t,H_t)`

as shorthand for these three external records. The index `t` counts decisions by the `Monitor`; it advances after the chosen process finishes and the shared records have been updated. The assignment and its constraints remain fixed task context and are not included in `S_t`.

### Process action space

At decision `t`, the `Monitor` chooses one of Agentic CogWriter’s three writing processes:

`a_t in (Planning,Translating,Reviewing).`

We write this choice as

`a_t=pi_monitor(S_t),`

where `pi_monitor` denotes the *process-selection policy*. In our implementation, this policy is the prompted decision made by the host agent; it is not a separately trained model.

The chosen process determines which role agent runs next. The `Planner` develops or reorganizes goals, the `Translator` realizes active goals as prose in the shared draft, and the `Reviewer` evaluates the draft against the active goals and returns verdicts and proposals. These role agents do not choose the next process themselves. Each process executes in its own role-agent context; we refer to this design choice as *separated role contexts*. After a role agent finishes, the `Monitor` reads the updated records, reconciles any proposals, and makes the next process choice.

### Control loop

Agentic CogWriter imposes no fixed order on the three processes. A translating pass can expose a planning problem, and a reviewing pass can lead back to planning or translating. Reviewing can also propose a change to the goal network. The `Monitor` accepts or rejects each such proposal and records the disposition in the process history. A run ends after reviewing when the `Monitor` chooses no further process.

### Testable design commitments

This formulation exposes three commitments that can be examined experimentally. First, Agentic CogWriter maintains an explicit evolving goal representation rather than relying only on the model’s working context. Second, the `Monitor` chooses the process order adaptively rather than following a fixed cycle. Third, `Planning`, `Translating`, and `Reviewing` execute in separated role contexts. The first two commitments admit single-factor interventions in our design. The third is probed diagnostically rather than isolated cleanly because the single-writer condition also changes delegation and how much text is produced between process decisions. Section 4.1 defines these conditions.

## Experimental Design

### Conditions

We answer RQ1 and RQ2 with seven experimental conditions under the same generator and coding-agent harness, and answer RQ3 with the observable traces produced by those runs. RQ1 compares Agentic CogWriter with three baseline organizations that vary what, if anything, is selected next during writing. RQ2 starts from Agentic CogWriter and tests three interventions: removing the explicit goal representation, fixing process order, and replacing delegated role-agent execution with a single writer context. The first two change one target commitment at a time; the third also changes delegation and how much text is produced between process decisions, so it is diagnostic. RQ3 characterizes how the resulting controller actually uses the available process transitions and goal updates.

The first three conditions separate the presence of structure from the object of adaptive choice. `Single-pass` generates the document in one call and therefore makes no intermediate control decision. `Staged` executes a fixed `Pre-Write``->``Write``->``Re-Write` sequence: it introduces process-like stages but does not choose among them. `Task-planning` follows the adaptive task-planning pattern of WriteHERE (Xiong et al., 2025), selecting dependency-satisfied nodes from an evolving task graph. It therefore provides adaptive control, but the choice is over task nodes rather than writing processes. These are controlled re-implementations on our generator and coding-agent harness rather than executions of the published systems.

The fourth condition is Agentic CogWriter as defined in Section 3.2. It keeps the goal network, allows the `Monitor` to choose among `Planning`, `Translating`, and `Reviewing`, and executes the chosen process with the corresponding `Planner`, `Translator`, or `Reviewer` role agent in separated role contexts. We derive three intervention conditions from it. `No-goals` removes the explicit goal representation while retaining adaptive process choice and the three role agents. `Fixed-order` keeps the external records and separated role contexts but replaces adaptive process choice with a fixed `Planning``->``Translating``->``Reviewing` cycle. `Single-writer` retains adaptive process choice and the goal network but executes all three processes in one writer context without subagent delegation. It also constrains each `Translating` step to add one paragraph before the next process decision. It therefore changes role-context separation, delegation, how much text is produced between process decisions, and output length together, and is a diagnostic ablation rather than a clean estimate of any one factor.

Table 1 summarizes what each condition selects next during generation and which commitments it retains.

| **Condition** | **Next decision** | **Goal network** | **Scheduling** | **Execution** |
|:---|:---|:---|:---|:---|
| *Baselines* | *Baselines* | *Baselines* | *Baselines* | *Baselines* |
| `Single-pass` | Nothing (one call) | – | – | One context |
| `Staged` (Yang et al., 2022; Wan et al., 2025) | Stage (fixed) | – | Fixed stages | One context |
| `Task-planning` (Xiong et al., 2025) | Task node | – | Adaptive tasks | Delegated task contexts |
| *Process-level conditions* | *Process-level conditions* | *Process-level conditions* | *Process-level conditions* | *Process-level conditions* |
| Agentic CogWriter | Writing process | yes | Adaptive processes | Separated role contexts |
| `No-goals` | Writing process | – | Adaptive processes | Separated role contexts |
| `Fixed-order` | Writing process (fixed) | yes | Fixed cycle | Separated role contexts |
| *Diagnostic ablation* | *Diagnostic ablation* | *Diagnostic ablation* | *Diagnostic ablation* | *Diagnostic ablation* |
| `Single-writer` | Writing process | yes | Adaptive processes | One writer context; one paragraph per `Translating` step |

Table 1. Experimental conditions. The second column states what, if anything, is selected next during generation. The process-level interventions remove the explicit goal representation or adaptive process ordering while retaining separated role contexts. `Single-writer` retains adaptive process choice and the goal network but removes subagent delegation and restricts each `Translating` step to one paragraph before the next process decision, so it changes several execution factors together.

### Benchmarks and prompts

We use WritingBench (Wu et al., 2026), HelloBench (Que et al., 2024), and DoLoMiTes (Malaviya et al., 2025). WritingBench covers general-purpose writing with task-specific criteria, HelloBench contains long-text generation tasks across several genres, and DoLoMiTes contains structured expert-writing tasks such as plans, reports, and design documents. Their source pools contain 1,000, 647, and 820 prompts, respectively.

We select the 100 prompts per benchmark that request the longest outputs, for 300 prompts total. The ranking combines prompt word count with the largest explicitly requested output length; we exclude pilot identifiers and prompts requesting more than 6,000 words in either component. This longest-output slice is intended to make differences between control strategies easier to observe in long-form settings. The conclusions therefore concern this slice rather than the full benchmark distributions. All conditions receive the same prompt and benchmark information, and external retrieval is disabled.

### Implementation and replications

We hold the generator, task input, available information, tool availability, and final-output contract fixed across conditions. Every prompt–condition pair is generated in three independent replications. The generator is `gpt-5.6-luna medium`; runtime details are reported in Appendix C.

The coding-agent harness uses the host platforms’ documented skills and subagent mechanisms (Anthropic, 2026a; Anthropic, 2026b; OpenAI, 2026a; OpenAI, 2026b; Google, 2026b; Google, 2026a). For Agentic CogWriter, the host agent acts as the `Monitor`, while `Planner`, `Translator`, and `Reviewer` role agents operate over a shared working directory containing the draft, goal network, and process history. The same harness records process switches, goal events, completed outputs, delegated invocations, token accounting, and timing. All conditions return the complete document through the same output channel.

### Evaluation

##### Primary outcome.

Our primary outcome is pairwise preference between two outputs for the same prompt. Each pair is judged in both presentation orders. If both orders select the same winner, that winner is retained; any disagreement becomes a tie. We call this single retained winner or tie the *prompt-collapsed outcome*. Prompts lacking a completed output from either side are excluded.

The locked analysis plan called for a confirmatory judge from a different model family than the generator. The judgments used for the confirmatory contrast family reported here instead come from `gpt-5.6-sol medium`, which shares the generator’s model family. We therefore scope the primary evidence to same-family judging and use `claude-sonnet-5 medium` only as a descriptive cross-family robustness check.

The pre-specified confirmatory family contains eight contrasts: Agentic CogWriter versus `Single-pass`, `Staged`, `Task-planning`, `No-goals`, and `Fixed-order`; and `Single-writer` versus `Single-pass`, Agentic CogWriter, and `No-goals`. Across three benchmarks this yields 24 benchmark-by-contrast cells. We use exact two-sided sign tests on wins and losses and control family-wise error with Holm’s procedure (Dixon and Mood, 1946; Holm, 1979). We report pooled prompt-collapsed win rates across the three replications with 95% Wilson intervals (Wilson, 1927); replicate-specific cells show stability across generation runs.

##### Secondary outcomes and robustness.

Benchmark-native and pointwise scores are secondary diagnostics from the first replication. We test output-length sensitivity using 5% and 10% matching bands. We test inference-compute sensitivity using cumulative output-plus-reasoning tokens and symmetric compute-ratio bands; because realized compute is an outcome of execution, these analyses are descriptive robustness checks rather than causal adjustment. Finally, `claude-sonnet-5 medium` provides a cross-family pairwise check on selected contrasts. Its results are descriptive rather than a second confirmatory family.

##### Process traces.

To answer RQ3, we analyze observable process and goal events rather than latent reasoning. We count process transitions, goal creation, development and regeneration, returns after `Reviewing`, and delegated invocations. Task-graph events from `Task-planning` are kept separate from writing-process events because the two conditions make different kinds of next-step decisions.

## Results

### RQ1: Does organizing generation around writing processes help?

Under same-family judging, RQ1 is positive relative to all three tested baseline organizations: Agentic CogWriter is preferred to `Single-pass`, `Staged`, and `Task-planning`. Table 2 reports the primary pairwise outcomes. Agentic CogWriter’s pooled mean win rate across replications is 80.9% against `Single-pass`, 67.3% against `Staged`, and 68.5% against `Task-planning`. The direction is stable across benchmarks and replications: Agentic CogWriter is favored in every benchmark-by-replication cell against `Single-pass` and `Task-planning`, and in all but one cell against `Staged`. After Holm correction, 8, 3, and 4 of the nine cells survive for the three contrasts, respectively. Replicate-level intervals are shown in Appendix D.

| **Contrast** | **WritingBench** | **HelloBench** | **DoLoMiTes** | **Pooled mean** |
|:---|---:|---:|---:|---:|
| Agentic CogWriter vs `Single-pass` | 84.3% | 85.7% | 72% | 80.9% |
| Agentic CogWriter vs `Staged` | 80.9% | 62.8% | 55.9% | 67.3% |
| Agentic CogWriter vs `Task-planning` | 65.5% | 63% | 75.7% | 68.5% |
| Agentic CogWriter vs `No-goals` | 52.1% | 52.4% | 56% | 53.4% |
| Agentic CogWriter vs `Fixed-order` | 56.8% | 57.4% | 54.7% | 56.3% |
| Agentic CogWriter vs `Single-writer` | 68.5% | 83.4% | 67.8% | 73.5% |

Table 2. Prompt-collapsed pairwise outcomes. Each cell reports Agentic CogWriter’s mean win rate among non-tied comparisons across three replications. Replication variability, Wilson intervals, and Holm-corrected cells are reported in Appendix D.

### RQ2: What do the interventions reveal about the design commitments?

RQ2 yields a selective answer. The confirmatory interventions do not identify either the explicit goal representation or adaptive process ordering as the source of Agentic CogWriter’s advantage, while the diagnostic single-writer comparison shows that the remaining execution differences matter collectively without isolating a single mechanism.

Removing the explicit goal representation leaves the pairwise result close to even: Agentic CogWriter wins 53.4% of non-tied comparisons against `No-goals`, and no benchmark cell survives Holm correction. Replacing adaptive process choice with the fixed process cycle likewise produces no surviving benchmark cell. These contrasts do not establish equivalence; under the confirmatory design, neither intervention produces a detectable loss.

`Single-writer` retains adaptive process choice and the goal network, but executes all three processes in one writer context and limits each `Translating` step to one paragraph before the next process decision. Agentic CogWriter is preferred to this condition in 73.5% of non-tied comparisons. Because this contrast simultaneously removes the three delegated role agents, changes how much text is produced between process decisions, and changes output length, it is diagnostic rather than a single-factor estimate of separated role contexts. An exploratory `Single-context` condition that keeps Agentic CogWriter’s processes and `Monitor` but runs them in one agent context wins 47.4% of non-tied comparisons against Agentic CogWriter (`p=0.5161`) and 85.6% against `Single-pass`, at similar token cost and 3.5 × faster in wall-clock time; Appendix G.4 reports it. Because this condition is post-hoc and has only one replication, it does not resolve the role-context mechanism either.

### RQ3: How does the Monitor use the available control flexibility?

The traces show that Agentic CogWriter uses much less scheduling flexibility than the architecture permits. The `Monitor` follows the `Planning``->``Translating``->``Reviewing` cycle in 74.6% of completed runs, returns from `Reviewing` to `Planning` in only 0.3%, and accepts goal regeneration in only 4 of 886 runs. Thus, although the controller is allowed to choose processes adaptively and replace goals, its observed behavior is usually close to a regular process cycle with a largely stable goal network. These traces do not show that the unused flexibility is unnecessary; they characterize how rarely it is exercised under the tested prompts and implementation. Detailed process counts and sequence distributions appear in Appendix E.

### Robustness

The main RQ1 direction survives the tested output-length and compute restrictions, but judge robustness remains limited. The same-family judge prefers the longer output in 66.12% of non-tied pairs, yet Agentic CogWriter remains favored over `Single-pass` within the tested output-length matching bands. At a compute ratio within 1.25, Agentic CogWriter remains preferred to `Staged` at 74.9% and to `Task-planning` at 72.1%; there are no Agentic CogWriter–`Single-pass` pairs this closely matched in compute. These realized-compute analyses are descriptive rather than causal because compute is itself an outcome of execution.

A cross-family judge preserves the pooled direction for the three checked contrasts, including 60.4% for Agentic CogWriter versus `Single-pass` and 75.2% versus `Task-planning`, but yields a non-tied prompt-collapsed judgment on only 32.6% of eligible pairs and reverses Agentic CogWriter versus `Single-pass` on WritingBench. We therefore treat it as a robustness check rather than replacement confirmatory evidence. Native and pointwise scores are reported in Appendix F; length, compute, and cross-family sensitivity analyses appear in Appendix G.

## Discussion

### What explains the remaining advantage?

The central result is a separation between decomposition and scheduling. Agentic CogWriter is preferred to the three baseline organizations, yet the two single-factor interventions do not identify either the explicit goal representation or adaptive process ordering as the source of that advantage. The process traces point in the same direction: the unrestricted `Monitor` usually follows the simple `Planning``->``Translating``->``Reviewing` cycle and rarely regenerates goals. The remaining candidates are features shared by Agentic CogWriter, `No-goals`, and `Fixed-order`, including decomposition into explicit writing processes, delegated execution, separated role contexts, and the repeated return to the `Monitor` between process executions. The current experiments do not isolate these features from one another.

The diagnostic conditions further restrict what can be claimed. `Single-writer` performs much worse, but it bundles role-context separation, delegation, how much text is produced between process decisions, and output length. The post-hoc `Single-context` result also cautions against attributing the gap specifically to separated role contexts: in one exploratory replication, collapsing the processes into one agent context does not produce a clear loss against Agentic CogWriter. These comparisons make execution structure a target for follow-up experiments, not an identified mechanism.

Two other simple explanations are insufficient on their own. More delegation does not guarantee better writing: `Task-planning` spawns more delegated work than Agentic CogWriter yet loses the pairwise comparison. Greater realized inference expenditure also does not straightforwardly account for the pattern, because the Agentic CogWriter advantage over `Staged` and `Task-planning` persists within the tested compute-matching band. Output length remains a concern, especially for the single-writer comparison, but the length-matched Agentic CogWriter–`Single-pass` analysis shows that length alone does not explain every main contrast. These are constraints on possible explanations, not causal mediation estimates.

### Implications for writing-agent design

The experiments separate two questions that are often coupled in structured generation: how to decompose writing and how to schedule the resulting work. Under the tested design, Agentic CogWriter outperforms the baseline organizations, while explicit goal bookkeeping and adaptive process ordering add no detectable benefit over their corresponding interventions. This makes a simpler hypothesis scientifically plausible: writing agents may benefit from organizing computation around distinct writing processes even when those processes are executed in a largely regular order. Because the intervention results do not establish equivalence and the shared execution features are not isolated, this should be tested directly rather than treated as a general replacement for adaptive control.

### Implications for theory-driven agent design

The cognitive process theory is useful here less as a blueprint to reproduce literally than as a source of executable commitments. Its named processes provide a computational decomposition, while its claims about mutable goals and flexible ordering become design choices that can be intervened on separately. In our experiments, the observed advantage survives interventions on two of those commitments, so the negative results are part of the contribution: they identify theory-derived mechanisms that did not explain the gain under the current design. This is an engineering result about language-agent organization, not evidence that the corresponding cognitive mechanisms are unnecessary for human writing.

## Conclusion

We used the cognitive process theory of writing to pose testable hypotheses about language-agent control rather than as a blueprint to import wholesale. Agentic CogWriter is preferred to single-pass generation, fixed writing stages, and adaptive task planning on the long-form benchmark slices tested here. Yet removing the explicit goal representation or replacing adaptive process ordering with a fixed cycle produces no detectable loss under our confirmatory design, and the unrestricted `Monitor` itself usually follows that cycle. The diagnostic single-writer comparison shows a large gap but cannot assign it to separated role contexts because delegation, decision granularity, and output length change at the same time.

The broader takeaway is that cognitive theory can be most informative for language-agent research when its commitments are made executable and tested separately. Here, explicit goal bookkeeping and adaptive ordering do not explain the observed advantage, while the shared execution structure remains an open mechanistic question. Agentic CogWriter therefore serves not only as an implementation, but as a way to test which commitments of a cognitive account survive contact with current language agents.

## Limitations

Completion differs across replications, and pairwise analyses exclude prompts for which either condition lacks a completed output. Although exclusions are applied symmetrically, the reported preferences therefore describe completed output pairs rather than all attempted runs. Replication-to-replication variation also limits how precisely the pooled rates characterize any single generation run.

The primary judge shares the generator’s model family, despite the locked analysis plan calling for a different-family confirmatory judge. The cross-family judge provides only a partial robustness check and frequently returns ties. We also did not conduct human evaluation, so the relationship between either model judge and human preference is unknown. The same-family judge’s observed preference for longer outputs is an additional reason not to interpret pairwise preference as a mechanism measure.

All generation uses one generator family. The results therefore do not establish that the observed advantage transfers to other generator families. The baselines are controlled re-implementations of the cited designs under our generator and coding-agent harness, not executions of the published systems; the comparisons should not be read as evaluations of those original implementations or their reported results.

The length- and compute-matched analyses are descriptive robustness checks. Realized output length and inference compute are consequences of execution rather than randomized treatments, so matching on them does not identify a causal effect of length or compute. In particular, the available compute-matched comparisons do not cover every primary contrast.

The ablations do not isolate every implementation detail. `Single-writer` changes separated role contexts, delegation, how much text is produced between process decisions, and output length together. The `Single-context` condition is a single post-hoc exploratory replication outside the confirmatory family. It was run once because it serves as a check on the attribution of the `Single-writer` loss rather than as a confirmatory contrast, so the benchmark-level lean toward Agentic CogWriter on HelloBench remains untested by replication. The current evidence therefore cannot attribute the remaining performance difference to separated role contexts, delegation, repeated process checkpoints, or any other single shared execution feature.

Finally, the evaluation uses the longest-output slice from each benchmark, selected by requested output length rather than an independent measure of task difficulty. The claims therefore concern demanding long-form prompts rather than the full benchmark distributions, shorter writing tasks, or other task families. Process traces record implemented agent state, not human goals, monitoring, or discovery; the cognitive theory defines an executable control hypothesis here, not cognitive equivalence.

## Decision comparison

Table 3 summarizes how representative long-form writing systems advance generation under a common descriptive vocabulary.

| **Method** | **Writing structure** | **What advances next?** | **How it is selected** |
|:---|:---|:---|:---|
| Re`^3` (Yang et al., 2022) | Plan-guided drafting and revision | Passage / revision step | Prescribed workflow |
| STORM (Shao et al., 2024) | Outline-driven article drafting | Section / section content | Outline-guided workflow |
| CogWriter (Wan et al., 2025) | Hierarchical planning and parallel generation | Planned generation / revision | Plan execution; monitoring can trigger revision |
| WriteHERE (Xiong et al., 2025) | Recursive heterogeneous task graph | Task node | Adaptive task scheduling |
| IS-CoT (Sun et al., 2026) | Interleaved Plan–Write–Reflect | Process stage | Embedded recurring cycle |
| Agentic CogWriter **(Ours)** | Process-level control | `Planning` / `Translating` / `Reviewing` | Adaptive process selection |

Table 3. Descriptive comparison of how representative long-form writing systems advance generation. The third column identifies the object or stage advanced at a decision point; the fourth describes how that next step is determined. These descriptions provide a common comparison vocabulary rather than reproducing the original authors’ terminology.

## Prompt and experiment configuration

##### Common generation contract.

All seven conditions receive the same assignment, supplied context, requested output constraints, generator model, attempt budget, and information policy. External retrieval is disabled: the coding-agent sandbox denies network access and web search, and conditions are instructed not to introduce facts unsupported by the assignment or supplied context. The Codex wrapper invokes the condition-specific skill and requires the final response to contain the complete generated document rather than a summary or a link to a workspace artifact.

##### Baseline prompts.

The single-pass condition begins: “Write the final response in one generation pass. Do not make a plan for the reader, describe a review, or expose hidden reasoning.” It then receives the assignment, supplied context, and requested output constraints.

The staged condition uses three fixed prompts. `Pre-Write` begins: “Prepare a concise working plan for the next writer. Identify the response’s purpose, audience, required content, order, and constraints.” It explicitly says not to write the final response yet. `Write` begins: “Write a complete draft that answers the assignment,” using the complete `Pre-Write` output as working guidance. `Re-Write` begins: “Revise the draft for instruction fulfillment, organization, depth, audience fit, and factual fidelity.” Each stage is restricted to the same assignment and supplied context, and the aggregate output-token budget is fixed across the three stages.

The adaptive task-planning condition uses a persistent directed acyclic task graph containing only `reasoning` and `composition` nodes. The coordinator recursively decomposes or executes the next dependency-satisfied task and may revise active graph structure after observing composed text. The prompt explicitly forbids adapting by selecting named writing processes; adaptation is restricted to task structure.

##### Agentic CogWriter and intervention prompts.

Agentic CogWriter is invoked through the `agentic-cog-writer` skill. The host agent acts as the `Monitor`, reads the draft, goal network, and process history, and chooses among `Planning`, `Translating`, and `Reviewing`. The selected process is delegated to the corresponding `Planner`, `Translator`, or `Reviewer` role agent. The skill requires process switches and goal changes to be written to an append-only trace.

The three interventions modify this prompt contract directly. `No-goals` forbids the explicit goal network while retaining adaptive process choice and the three role agents. `Fixed-order` preserves the goal network and role agents but replaces adaptive selection with the fixed `Planning``->``Translating``->``Reviewing` cycle. `Single-writer` retains adaptive process choice and the goal network but forbids delegation to those role agents. It also requires each `Translating` step to append one paragraph before the writer makes the next process decision. Condition configuration files record the skill or stage prompt used for each condition and the SHA-256 hash of fixed stage prompts.

##### Pairwise judge prompt.

The primary judge is instructed to act as an impartial judge comparing two responses to the same assignment. Its rubric covers instruction fulfillment, organization and global coherence, content adequacy and depth, style, voice and audience fit, factuality, and constraint fidelity. The prompt explicitly instructs the judge to avoid position bias and length bias, to use only the assignment and supplied context, and to choose `A`, `B`, or `tie`. Each pair is shown in both presentation orders; disagreement across the two orders becomes a tie. The judge returns a JSON record containing the winner, short exact evidence quotes from each response, and a brief rubric-grounded comparison.

## Runtime configuration

Table 4 summarizes the runtime and evaluation settings used for the reported runs. Every condition received the same task input, available information, generator, tool policy, attempt budget, and final-output contract.

| **Setting**                   | **Value**                   |
|:------------------------------|:----------------------------|
| Generator                     | `gpt-5.6-luna medium`       |
| Primary pairwise judge        | `gpt-5.6-sol medium`        |
| Cross-family judge            | `claude-sonnet-5 medium`    |
| Generation replications       | 3 per prompt–condition pair |
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

Table 4. Runtime and evaluation settings used for the reported experiments. Model names include the configured reasoning-effort label where applicable.

## Replicate-level pairwise outcomes

The following figure shows the prompt-collapsed pairwise estimates for each benchmark and replication, including the ablation contrasts.

Figure 2. Prompt-collapsed pairwise win rates by benchmark and replication. Points show 95 percent Wilson intervals; diamonds show the mean across replications, and filled or open circles mark cells that do or do not survive Holm correction.

## Process behavior and resource use

Table 5 reports completion, output size, delegated invocations, goal events, token accounting, and wall-clock time from the first replication. For Agentic CogWriter, the first replication uses 13,374 output-plus-reasoning tokens and 46,860 uncached input tokens per attempted run and records 1 accepted goal regeneration. Across replications, the trace summaries contain mean totals of 1,101.3 goal-creation events and 1,915.3 goal-development events, while the post-`Reviewing` ledger contains 353.7 entries including 3.7 explicit regeneration proposals.

| **Condition** | **Completed** | **Median**; **units** | **Spawns**; **/run** | **Goals created**; **developed/regenerated** | **Output**; **tokens**; **/run** | **Input**; **tokens**; **/run** | **Mean sec.**; **/completed run** |
|:---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| `Single-pass` | 289/300 | 1,654 | 0 | 0/0/0 | 4,874 | 13,263 | 61 |
| `Staged` | 300/300 | 1,510 | 0 | 0/0/0 | 10,728 | 21,822 | 77 |
| `Task-planning` | 292/300 | 1,702 | 8.09 | 0/0/0 | 17,851 | 62,871 | 298 |
| Agentic CogWriter | 293/300 | 1,835 | 3.22 | 1,068/1,864/1 | 13,374 | 46,860 | 426 |
| `No-goals` | 294/300 | 1,762 | 3.04 | 0/0/0 | 9,788 | 39,317 | 345 |
| `Fixed-order` | 282/300 | 1,773 | 3.43 | 267/1,163/3 | 11,402 | 42,888 | 219 |
| `Single-writer` | 280/300 | 1,111 | 0 | 1,621/169/1 | 15,356 | 30,715 | 103 |

Table 5. Process summary from the first replication across the longest-output benchmark slice. All cells are values from the first replication derived from the process-summary JSON source. Completed is the count of completed runs. Spawns are mean delegated invocations per attempted run. Output tokens are Codex-reported output plus reasoning tokens, and input tokens are uncached input tokens; both are means over attempted runs. Wall-clock time is the mean seconds for completed runs.

The following figure shows the process sequences and transition counts used to interpret the fixed-order ablation.

Figure 3. `Monitor` process selection across Agentic CogWriter and `Fixed-order`. Panel (a) shows the most frequent process sequences; panels (b) and (c) show transition counts. P, T, R, and E denote `Planning`, `Translating`, `Reviewing`, and termination.

## Secondary product scores

Native and pointwise scores are secondary diagnostics rather than the confirmatory outcome.

|  |  |  |  |  |  |  |
|:---|:--:|:--:|:--:|:--:|:--:|:--:|
| **Condition** | **WritingBench** | **WritingBench** | **HelloBench** | **HelloBench** | **DoLoMiTes** | **DoLoMiTes** |
|  | **Native** | **Pointwise** | **Native** | **Pointwise** | **Native** | **Pointwise** |
| `Single-pass` | 7.044 | -0.093 | 0.769 | -0.119 | – | -0.019 |
| `Staged` | 7.084 | -0.054 | 0.78 | -0.007 | – | 0.103 |
| `Task-planning` | 7.258 | -0.062 | 0.781 | 0.04 | – | -0.166 |
| Agentic CogWriter | 7.54 | 0.115 | 0.795 | 0.058 | – | 0.005 |

Table 6. Native and pointwise product scores from the first replication for the four primary conditions, as defined in Section 4.4. Completion is reported in Table 5.

## Sensitivity analyses

### Record-pooled sensitivity

The record-pooled table reports a sensitivity analysis that treats the two presentation records for each prompt as independent observations; the retained disagreements show how much presentation order can affect the descriptive rates. The retained presentation disagreements were 22.7% on WritingBench, 29.4% on HelloBench, and 21.4% on DoLoMiTes across the three replications.

| **Contrast** | **WritingBench** | **HelloBench** | **DoLoMiTes** | **Pooled mean (SD);**; **Wilson interval, first replication** |
|:---|:--:|:--:|:--:|:--:|
| Agentic CogWriter vs `Single-pass` | 79.4% (0.8%) | 81.1% (1.2%) | 68.9% (6.2%) | 76.6% (2%); 73.1%–80.2% |
| Agentic CogWriter vs `Staged` | 74.6% (1.8%) | 59.9% (2.4%) | 54.7% (5.5%) | 63.6% (2.9%); 60%–68.1% |
| Agentic CogWriter vs `Task-planning` | 61.9% (4.5%) | 59.5% (4.8%) | 72.5% (6.7%) | 64.7% (1.8%); 62.5%–70.4% |
| Agentic CogWriter vs `No-goals` | 51.5% (3.8%) | 50.8% (1.6%) | 53.7% (5.7%) | 51.9% (0.6%); 47.8%–56.4% |
| Agentic CogWriter vs `Fixed-order` | 55% (0.6%) | 53.9% (1.3%) | 53.4% (3.1%) | 54.1% (0.9%); 50.3%–59% |
| `Single-writer` vs `Single-pass` | 66.7% (5.2%) | 41.6% (4.3%) | 53.7% (7.5%) | 54.4% (2.3%); 51.8%–60.4% |
| `Single-writer` vs Agentic CogWriter | 35.5% (2.1%) | 20.5% (1.4%) | 35.4% (3.3%) | 30.4% (2%); 25.6%–33.3% |
| `Single-writer` vs `No-goals` | 37.2% (3.3%) | 21.5% (4%) | 43% (7.1%) | 33.8% (2.5%); 28.9%–36.9% |

Table 7. Record-pooled sensitivity analysis. The earlier design treated the two presentation records for each prompt as independent observations. Each cell reports the first-listed condition’s record-pooled mean win rate and sample SD across the three replications; the pooled column adds the Wilson interval from the first replication. These values are descriptive sensitivity results, not the confirmatory analysis.

### Output-length sensitivity

The length-control table reports the longer-side preference by output-length ratio; the longer side wins 66.12% of 1647 non-tied comparisons. Within 5 percent, the outcomes from the first replication are 25/3/7 for Agentic CogWriter versus `Single-pass` (`p=2.74 x 10^-5`), 26/15/7 for Agentic CogWriter versus `Task-planning` (`p=0.1173`), and 18/18/20 for Agentic CogWriter versus `No-goals`. Within 10 percent, the corresponding outcomes are 40/11/17 (`p=5.70 x 10^-5`), 39/18/14 (`p=0.0075`), and 38/30/37 (`p=0.3961`). The 5/10-percent rates for Agentic CogWriter versus `Single-pass` are 80.0%/82.7% in the second replication and 82.9%/80.7% in the third replication; the corresponding Agentic CogWriter versus `Task-planning` rates are 57.1%/58.5% and 51.9%/50.9%. The Agentic CogWriter versus `No-goals` replicate rates are 46.7%/45.7% and 59.5%/47.8%.

| **Output-length ratio** |  **W/L/T**  | **Longer-side**; **win rate** |
|:------------------------|:-----------:|:-----------------------------:|
| 1.00–1.05               | 123/104/91  |            54.19%             |
| 1.05–1.10               |  116/67/92  |            63.39%             |
| 1.10–1.25               | 291/185/177 |            61.13%             |
| 1.25–1.50               | 277/120/141 |            69.77%             |
| 1.50–2.00               |  188/68/66  |            73.44%             |
| 2.00+                   |  94/14/23   |            87.04%             |

Table 8. Prompt-collapsed pairwise outcomes from the first replication by output-length ratio. The longer side is the first-listed outcome in each row; ties are excluded from the win-rate denominator. Output units come from the run manifests.

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

Table 9. Compute-stratified prompt-collapsed outcomes. The compute ratio is the ratio of output-plus-reasoning tokens per completed run, with retries included; the Agentic CogWriter versus Single-pass contrast has no pairs within 1.25 because Agentic CogWriter always uses more.

### Single-context ablation

The `Single-context` condition was added after the primary results had been observed, to test whether the `Single-writer` loss reflects delegation to separate agents or the absence of process decomposition under a `Monitor`. We registered it as an exploratory condition outside the Holm family before judging and ran one replication, the same evidence tier as the cross-family check: the question it answers is whether an attribution survives, not whether a new contrast is confirmed. We therefore report the pooled estimate with its interval and the benchmark-level results without adjustment.

| Contrast | Scope | `n` | Dropped | W/L/T | Rate | Wilson 95% / `p` |
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

Table 10. Exploratory single-context results added after the primary results. The one-replication outcomes were judged by `gpt-5.6-sol medium` against replication-1 outputs without multiplicity adjustment. The runtime used a different gateway entry point and plain HTTP transport, with the generator model unchanged.

| Metric | `Single-pass` | Agentic CogWriter | `Single-context` |
|:---|---:|---:|---:|
| Completed | 289/300 | 293/300 | 300/300 |
| Output-plus-reasoning tokens per run | 4,874 | 13,374 | 14,497 |
| Wall-clock seconds per completed run | 61 | 426 | 123 |
| Goals created/developed/regenerated | 0/0/0 | 1,068/1,864/1 | 1191/971/0 |
| Ledger entries | 0 | 347 | 321 |
| Ledger entries with proposal | 0 | 3 | 0 |
| Spawns per attempted run | 0 | 3.22 | 0 |

Table 11. Process summaries are from the first replication for the primary conditions and the single exploratory replication for `Single-context`. Structural auditing found 7 A8 prompts missing `Planning`, 6 missing `Translating`, and 3 missing both, out of 300; the A4 replication-1 audit found 6 prompts missing `Planning` and 7 missing `Translating`, out of 300.

### Cross-family judge robustness

The cross-family table reports pooled outcomes for the three robustness contrasts: 67/44/171 for Agentic CogWriter versus `Single-pass`, 76/25/184 for Agentic CogWriter versus `Task-planning`, and 39/27/221 for Agentic CogWriter versus `No-goals`. The corresponding Wilson intervals are 51.06%–68.97%, 66.01%–82.64%, and 47.05%–70.13%. The judge yields a non-tied prompt-collapsed judgment on 32.6% of 854 pairs, with 182/96/576 overall W/L/T and 395/854 prompt-collapsed agreements.

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

Table 12. Cross-family judge robustness check using `claude-sonnet-5 medium`. Each row reports prompt-collapsed outcomes for the eligible pairs in that benchmark; `n` is the number of eligible pairs. Commit is the fraction of pairs with a non-tied cross-family outcome, and agreement is the fraction of prompts whose collapsed outcomes agree with the same-family judge. No multiplicity correction is applied.

## Habermas Machine pilot

The Habermas table reports trace totals from the 80-run pilot, which tests short consensus writing as a boundary condition rather than a fourth benchmark.

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

Table 13. The 80-run Habermas Machine pilot. The pilot completed 78 runs. Completed-run denominators in row order are 10/10, 10/10, 9/10, 10/10, 10/10, 10/10, 10/10, and 9/10. `Task-planning` and `Exploratory-2` each had one failed run; the table retains the trace totals reported in the pilot ledger.

`Exploratory-1` is the exploratory CogWriter-style baseline, with initial planning, immediate plan revision, parallel segment generation, and length review without a goal network; `Exploratory-2` is the exploratory STORM-style baseline, with perspective discovery, simulated question answering, outlining, per-section drafting, and polishing without retrieval. The Agentic CogWriter condition ranks fifth of eight on the pointwise composite, behind `Single-pass` and `Staged`. Agentic CogWriter and `Fixed-order` record 0 and 0 regeneration events, respectively; their ledgers contain 15/0 and 11/0 no/proposal outcomes, respectively.

## References

Anthropic. 2026. Agent skills.

<https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview>. Claude Platform Docs. Accessed: 2026-09-03.

Anthropic. 2026. Create custom subagents. <https://code.claude.com/docs/en/sub-agents>. Claude Code Docs. Accessed: 2026-09-03.

Yushi Bai, Jiajie Zhang, Xin Lv, Linzhi Zheng, Siqi Zhu, Lei Hou, Yuxiao Dong, Jie Tang, and Juanzi Li. 2025. Longwriter: Unleashing 10,000+ word generation from long context llms. In *International Conference on Learning Representations*, volume 2025, pages 36528–36546.

Carl Bereiter and Marlene Scardamalia. 1987. *The psychology of written composition*. L. Erlbaum Associates Hillsdale, NJ.

W. J. Dixon and A. M. Mood. 1946. [The statistical sign test](https://doi.org/10.1080/01621459.1946.10501898). *Journal of the American Statistical Association*, 41(236):557–566.

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

Yijia Shao, Yucheng Jiang, Theodore Kanell, Peter Xu, Omar Khattab, and Monica Lam. 2024. Assisting in writing wikipedia-like articles from scratch with large language models. In *Proceedings of the 2024 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies (Volume 1: Long Papers)*, pages 6252–6278.

Momin N Siddiqui, Roy D Pea, and Hari Subramonyam. 2025. Script&shift: A layered interface paradigm for integrating content development and rhetorical strategy with llm writing assistants. In *Proceedings of the 2025 CHI Conference on Human Factors in Computing Systems*, pages 1–19.

Zechen Sun, Yuyang Sun, Zecheng Tang, Juntao Li, Wenpeng Hu, Wenliang Chen, Zhunchen Luo, Guotong Geng, and Min Zhang. 2026. Is-cot: Breaking the long-form generation collapse via interleaved structural thinking. In *Proceedings of the 64th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)*, pages 19874–19887.

Kaiyang Wan, Honglin Mu, Rui Hao, Haoran Luo, Tianle Gu, and Xiuying Chen. 2025. A cognitive writing perspective for constrained long-form text generation. In *Findings of the Association for Computational Linguistics: ACL 2025*, pages 9832–9844.

Ruyuan Wan, Simret Araya Gebreegziabher, Toby Jia-Jun Li, and Karla Badillo-Urquiola. 2024. Coco matrix: Taxonomy of cognitive contributions in co-writing with intelligent agents. In *Proceedings of the 16th Conference on Creativity & Cognition*, pages 504–511.

Edwin B. Wilson. 1927. [Probable inference, the law of succession, and statistical inference](https://doi.org/10.1080/01621459.1927.10502953). *Journal of the American Statistical Association*, 22(158):209–212.

Yuning Wu, Jiahao Mei, Ming Yan, Chenliang Li, Shaopeng Lai, Yuran Ren, Zijia Wang, Ji Zhang, Mengyue Wu, Qin Jin, et al. 2026. Writingbench: A comprehensive benchmark for generative writing. *Advances in Neural Information Processing Systems*, 38.

Ruibin Xiong, Yimeng Chen, Dmitrii Khizbullin, Mingchen Zhuge, and Jürgen Schmidhuber. 2025. Beyond outlining: Heterogeneous recursive planning for adaptive long-form writing with language models. In *Proceedings of the 2025 Conference on Empirical Methods in Natural Language Processing*, pages 24689–24725.

Kevin Yang, Yuandong Tian, Nanyun Peng, and Dan Klein. 2022. Re3: Generating longer stories with recursive reprompting and revision. In *Proceedings of the 2022 Conference on Empirical Methods in Natural Language Processing*, pages 4393–4479.

Lili Yao, Nanyun Peng, Ralph Weischedel, Kevin Knight, Dongyan Zhao, and Rui Yan. 2019. [Plan-and-write: Towards better automatic storytelling](https://doi.org/10.1609/aaai.v33i01.33017378). In *Proceedings of the AAAI conference on artificial intelligence*, volume 33, pages 7378–7385. AAAI.

David Zhou, Andrew Chen, John Joon Young Chung, and Sarah Sterman. 2026. Iris: Navigating and reflecting on writing traces using intelligent document histories. *arXiv preprint arXiv:2608.19614*.
