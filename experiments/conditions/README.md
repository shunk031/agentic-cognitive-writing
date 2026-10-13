# Conditions

One TOML wrapper per condition binds the condition to one package skill, one platform adapter pair, the shared plugin trace path, and its ordered stage specifications. The runner sends one top-level headless session for every condition and prompt. The runner does not sequence stages or synthesize trace events.

The frozen files under `prompts/` remain prompt specifications with content hashes. The A1 to A3 wrappers invoke `writing-single-shot`, `writing-linear`, and `writing-adaptive-task-planning` from the `cognitive-writing-baselines` package; the existing five-stage prompt specifications are used by B2's `writing-storm-style` wrapper.

A4 invokes `agentic-cog-writer` from `agentic-cognitive-writing`. A5, A6, A7, and A8 invoke `cognitive-writing-no-goal-network`, `cognitive-writing-fixed-order`, `cognitive-writing-single-writer`, and `cognitive-writing-single-context` from `cognitive-writing-experiments`. B1 and B2 invoke `writing-cogwriter-style` and `writing-storm-style` from the baseline package. The current study treats A1 through A7 as confirmatory conditions, B1 and B2 as exploratory baselines used only in the Habermas pilot, and A8 as an exploratory single-context ablation added after the primary results were observed.

Shared prompt paragraphs live in [`contracts/`](contracts/). The runner appends `single_turn.md` to Codex invocations, adds `delegation.md` when `require_delegation = true`, and appends `workspace.md` followed by `single_turn.md` to Claude Code invocations; wrapper files retain only condition-specific invocation text. The runner renders contract names and generic shared-input blocks as `##` headings, frozen stage titles as `##` headings, and frozen stage labels as `###` headings.

Every condition uses `.writing/trace/process.jsonl` written by its selected skill. The no-retrieval A3 and B2 wrappers omit citation generation and mark retrieval, evidence, and citation traces as `N/A` in their wrapper policies.

## A9 staged role instructions

A9 tests whether the role instructions alone, without the `Monitor`, explain A4's advantage over A2. A9 is an exploratory condition added after the primary results were observed and sits outside the confirmatory family.

A9 reuses the A2 harness unchanged: the `writing-linear` skill, the same Codex invocation and contracts, one session, the fixed Pre-Write, Write, and Re-Write order, and A2's three-event `process_switch` trace contract. The only difference is the stage text. Each A9 stage file keeps the corresponding A2 stage paragraph and input blocks verbatim and adds one role section taken from the A4 role skills: Pre-Write receives [`planning`](../../plugin/skills/planning/SKILL.md), Write receives [`translating`](../../plugin/skills/translating/SKILL.md), and Re-Write receives [`reviewing`](../../plugin/skills/reviewing/SKILL.md). A9 has no `Monitor`, no goal network or `.writing/goals.md`, no role trace events, no subagents, and no adaptive process selection.

The role sections keep the writing guidance verbatim, including the rhetorical-problem list, audience and organization guidance, claim-support criteria, no-invention rules, and review criteria. The edits below remove or neutralize only text that refers to the `Monitor`, the goal network, the trace, shared `.writing/` state that A2 does not create, subagent delegation, or the report the role returns to the `Monitor`. A2's stage contract requires the Write and Re-Write stages to return only the draft or final text, so those two roles lose their report formats.

**All three roles.** The frontmatter, the role name heading, and the "When this skill runs" section, which names the role as a sub-agent receiving a delegation from the `Monitor`, are removed. The "Read the state first" list of `.writing/assignment.md`, `.writing/goals.md`, `.writing/draft.md`, `.writing/memory/`, and trace entries is removed because the stage prompt carries the assignment, supplied context, and previous stage output inline.

**Planning, used in Pre-Write.**

- The opening line "Turn a delegated writing problem into grounded knowledge, useful organization, and a maintained goal network." becomes "Turn the writing problem into grounded knowledge and useful organization."
- "rather than delegating to more agents" is removed from the sub-process lead-in.
- "the project memory" is removed from the Generate sources because A2 has no memory directory.
- Goal-setting "create or develop concrete sub-goals under the active parent goal. Regenerate a higher-level goal only when the exploration or draft provides evidence that the writer's purpose has changed." becomes "create concrete sub-goals for the response."
- From the Boundaries section, only "Do not silently change the assignment, factual claims, or the user's top-level intent." is kept; the sentences on goal ownership, trace ownership, user intent ownership, `.writing/goals.md` updates, stable goal identifiers, and evidence returned to the `Monitor` are removed.
- The report format becomes a single sentence asking for a concise plan with generated knowledge separated by confidence, the proposed organization and why it fits the audience, the sub-goals for the response, and unresolved uncertainty. The goal-ID, goal-change, and next-process items are removed.

**Translating, used in Write.**

- The opening line drops "within the `Monitor`'s delegated draft scope".
- "Keep the active goal visible while drafting. Preserve a useful existing sentence when it serves that goal" becomes "Keep the plan's sub-goals visible while drafting. Preserve a useful existing sentence when it serves those sub-goals".
- In the drafting rules, "Write only the delegated scope in `.writing/draft.md` unless the `Monitor` explicitly asks for an alternative.", the instruction to flag changes to claims, structure, tone, and audience assumptions, and "Mark a gap as an open uncertainty for the `Monitor`." are removed. "Preserve useful user text." and "Do not invent sources, quotations, statistics, or facts." are kept.
- The Boundaries section on trace ownership and goal changes and the report format are removed.

**Reviewing, used in Re-Write.**

- The opening line "then revise only within the `Monitor`'s delegated scope" becomes "then revise".
- "rather than delegating to more agents" is removed from the sub-process lead-in.
- In the Evaluate list, "active goals" becomes "the plan's sub-goals".
- Revise drops "in the delegated scope", "call out factual gaps", and "state whether the change is local or changes the goal network". "make only the requested or clearly authorized changes" and "Preserve the writer's intent." are kept.
- The Boundaries sentences on interrupting other processes and telling the `Monitor`, and on recommending goal regeneration, are removed. "Do not invent citations or claims." is kept.
- The report format, including the per-goal verdict line, is removed.

## A10 budget-matched Self-Refine

A10 tests whether spending Agentic CogWriter's generation budget on plain self-feedback explains A4's advantage. A10 follows Self-Refine[^1]: one generator writes a draft, gives feedback on it, and refines it, for a fixed number of rounds. A10 is an exploratory condition added after the primary results were observed and sits outside the confirmatory family.

A10 uses the same harness as A2: one `codex exec` session with the shared single-turn contract, the same generator, reasoning effort, output budget, timeout, and retry policy, a workspace-write sandbox with network access off, and a fixed process order recorded as `process_switch` events. The [`writing-self-refine`](../baselines/skills/writing-self-refine/SKILL.md) skill in the baseline package defines the Draft, Feedback, and Refine handoffs and their trace. A10 has no `Monitor`, no goal network or `.writing/goals.md`, no role skills, no subagents, and no early stopping.

The three frozen stage files are generic Self-Refine prompts written for A10, not adaptations of the A4 role skills. [`a10_draft.md`](prompts/a10_draft.md) asks for a complete draft, [`a10_feedback.md`](prompts/a10_feedback.md) asks for actionable and specific feedback that points to the passage or omission behind each problem and the change that would fix it, and [`a10_refine.md`](prompts/a10_refine.md) asks for a complete revision that addresses that feedback. The wrapper lists the Feedback and Refine files once per round, so the trace contract is one Draft event followed by alternating Feedback and Refine events.

**Round count.** A10 runs k = 2 Feedback and Refine rounds. The round count was fixed before the scored run so that A10's mean output-plus-reasoning tokens per document approximate A4's run-1 mean of 13,374 tokens. Calibration ran k = 1 and k = 2 on the same twelve prompts, the four prompts per benchmark ranked immediately below the hard100 cut by the [prompt-set](../prompts/README.md#pilot-and-hard-prompt-subsets) difficulty key. None of the calibration prompts is a pilot or scored prompt. The rule picks the k whose calibration mean is closest to the A4 target, which selects k = 2.

| Rounds | Completed calibration runs | Mean output-plus-reasoning tokens |
| -----: | -------------------------: | --------------------------------: |
|      1 |                         12 |                            11,397 |
|      2 |                         12 |                            13,689 |

[^1]: Aman Madaan, Niket Tandon, Prakhar Gupta, Skyler Hallinan, Luyu Gao, Sarah Wiegreffe, Uri Alon, Nouha Dziri, Shrimai Prabhumoye, Yiming Yang, Shashank Gupta, Bodhisattwa Prasad Majumder, Katherine Hermann, Sean Welleck, Amir Yazdanbakhsh, and Peter Clark, "Self-Refine: Iterative Refinement with Self-Feedback," *Advances in Neural Information Processing Systems* (2023), [DOI](https://doi.org/10.52202/075280-2019) and [arXiv](https://arxiv.org/abs/2303.17651).

## A11 plain agent

A11 tests whether the Agentic CogWriter skill adds anything beyond what the coding-agent harness already provides. A11 is an exploratory condition added after the primary results were observed and sits outside the confirmatory family.

A11 reuses the A1 harness: the same Codex invocation form and contracts, one session, the same generator, output budget, sandbox, and no-network policy, A1's `product_requires_draft = false` gate, and A1's fixed one-event `process_switch` trace contract with the single process `generate`. A11 has no stage prompt, so the composed prompt carries only the invocation, the single-turn contract, and the assignment, supplied context, and requested output constraints.

The [`writing-plain-agent`](../baselines/skills/writing-plain-agent/SKILL.md) skill file holds the only condition-specific text. The writing instruction is this sentence pair, verbatim:

> Write the requested document. Keep your working draft in a file in the workspace; you may plan, draft, and revise it as you see fit before returning the complete final document.

The instruction names no cognitive process, review criterion, audience or goal guidance, or role-skill content. A11 has no `Monitor`, goal network, role instructions, subagents, or fixed draft path.

The runner's validity gate requires a schema-valid trace, so the skill file also gives the one shell command that appends A1's fixed `generate` event to `.writing/trace/process.jsonl`, framed as a harness record outside the writing task. The trace therefore records only that the session ran and says nothing about the agent's drafting behavior; draft writes and revisions are measured from the Codex event stream instead.

## A12 loop-only

A12 tests whether A4's advantage survives when the three components that A5, A6, and A8 each remove alone are removed together. A12 keeps the `Monitor`, the persistent `.writing/` draft and state, the role skills' writing guidance, the process-switch trace, and the A4 harness and settings. A12 has no goal network, a prompt-fixed `Planning`, `Translating`, then `Reviewing` order, and no subagents: the `Monitor` performs every role in its own context. A12 is an exploratory condition added after the primary results were observed and sits outside the confirmatory family.

A12 is built from the A5, A6, and A8 skill texts that generation run 1 executed, not from the current files, which later lost their interactive-user passages. Every run-1 manifest records the SHA-256 of the staged skill file, and the source texts match those hashes:

| Source | Skill | Executed `SKILL.md` SHA-256 |
| ------ | ----- | --------------------------- |
| A5 | `cognitive-writing-no-goal-network` | `4b0feac833dcdd6440f6ca8ee5fe9a470c88f9ec50b5f83be961479539a76a18` |
| A6 | `cognitive-writing-fixed-order` | `e3f03144ee68ee992eeddb915bffa4793b582db3a71753ccd7d557e256f964eb` |
| A8 | `cognitive-writing-single-context` | `44eecb4b51f840638da621f17f451756aac45db015cab26e3dd402c9ce53a8e7` |

The role skills [`planning`](../../plugin/skills/planning/SKILL.md), [`translating`](../../plugin/skills/translating/SKILL.md), and [`reviewing`](../../plugin/skills/reviewing/SKILL.md) are unchanged since run 1, and the runner stages them for A12 exactly as for A5, A6, and A8. The wrapper [`a12_loop_only.toml`](a12_loop_only.toml) takes A5's trace policy, with goal events forbidden and `.writing/goals.md` protected, and A8's `require_delegation = false`, so the runner appends no delegation contract and fails a Codex run that spawns a subagent. Like A6, A12 enforces the fixed order by prompt only.

The [`cognitive-writing-loop-only`](../plugin/skills/cognitive-writing-loop-only/SKILL.md) skill starts from the executed A5 text and makes these changes.

- **Frontmatter and opening.** The name and description are new, the opening line names all three removals, and "no-goal-network" becomes "loop-only" in the usage line.
- **Responsibilities.** A6's "Coordinate the prescribed order" replaces A5's "Coordinate process switches". A8's in-context bullet is added with "selected" changed to "current". "Reconcile each returned role report" becomes "Reconcile each process's work" because no role returns a report.
- **State.** A5's section is kept verbatim, except that "before choosing a process" becomes A6's "before the first process".
- **Loop.** A6's fixed loop replaces A5's adaptive loop. Step 1, the fixed order, is A6's text verbatim. A6's step that keeps the active goal and its parent visible is removed, and A6's evidence step compares the assignment's implicit objective instead of the active goal and ends with A5's "Do not consult or construct a hierarchical goal network." The trace step is A5's, naming the loop-only variant. A8's in-context step replaces the delegation step. A5's `Planning` step asks the `Monitor` to perform problem representation, Generate, and Organize itself and to record a proposed hierarchical goal only as an observation. A5's reconcile step is kept. A6's post-`Reviewing` goal-verdict handling, including `develop` and `regenerate` dispositions, the regeneration-proposal enumeration, and the end-of-run `reviewing` switch it prescribes, and A6's post-`Translating` goal comparison are removed because no goal network exists. The closing report to the user combines A5's "the assignment remains the implicit objective" with A6's "which prescribed process comes next".
- **Interruptions.** A6's paragraph is kept, with the interrupt performed in the host agent's own context instead of through a shared role, and A6's "return to its parent goal" replaced by A5's "Do not create a goal to track the interrupt."
- **In-context execution.** A8's section replaces A5's and A6's delegation sections, with "selected" changed to "current", an added rule that no process creates or modifies `.writing/goals.md`, and A5's brief, which passes the assignment summary, in place of A8's goal-context brief.
- **Trace contract.** A5's contract is kept verbatim except for the example decision, which uses A6's prescribed-pass wording. A12 ships no `references/` directory because A8's goal notation does not apply and the trace contract is inline, as in A5 and A6.

The interactive-user passages that the executed texts share, asking the user for a missing rhetorical problem and reporting to the user after each pass, are kept so that A12 differs from the run-1 conditions only in the three removals. The runner's single-turn contract forbids clarification questions in every condition.
