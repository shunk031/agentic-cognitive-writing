# Conditions

One TOML wrapper per condition binds the condition to one package skill, one platform adapter pair, the shared plugin trace path, and its ordered stage specifications. The runner sends one top-level headless session for every condition and prompt. The runner does not sequence stages or synthesize trace events.

The frozen files under `prompts/` remain prompt specifications with content hashes. The A1 to A3 wrappers invoke `writing-single-shot`, `writing-linear`, and `writing-adaptive-task-planning` from the `cognitive-writing-baselines` package; the existing five-stage prompt specifications are used by B2's `writing-storm-style` wrapper.

A4 invokes `agentic-cog-writer` from `agentic-cognitive-writing`. A5, A6, A7, and A8 invoke `cognitive-writing-no-goal-network`, `cognitive-writing-fixed-order`, `cognitive-writing-single-writer`, and `cognitive-writing-single-context` from `cognitive-writing-experiments`. B1 and B2 invoke `writing-cogwriter-style` and `writing-storm-style` from the baseline package. The current study treats A1 through A7 as confirmatory conditions, B1 and B2 as exploratory baselines used only in the Habermas pilot, and A8 as an exploratory single-context ablation added after the primary results were observed.

Shared prompt paragraphs live in [`contracts/`](contracts/). The runner appends `single_turn.md` and `information.md` to every invocation, adds `delegation.md` to Codex invocations when `require_delegation = true`, and puts `workspace.md` first in Claude Code invocations; wrapper files retain only condition-specific invocation text. `information.md` states the output-language rule and the no-retrieval rule, so every condition receives both in the same words. The runner renders contract names and generic shared-input blocks as `##` headings, frozen stage titles as `##` headings, and frozen stage labels as `###` headings.

Every condition uses `.writing/trace/process.jsonl` written by its selected skill. The no-retrieval A3 and B2 wrappers omit citation generation and mark retrieval, evidence, and citation traces as `N/A` in their wrapper policies.

## Agentic CogWriter and its ablations

A4 runs the [`agentic-cog-writer`](../../plugin/skills/agentic-cog-writer/SKILL.md) skill. [`generate_variant_skills.py`](../../tools/generate_variant_skills.py) writes the A5, A6, A7, A8, and A12 skills from A4's text, replacing, dropping, or adding only the sections that carry the mechanism each condition removes, and copies A4's trace script and references into each skill. [`test_generate_variant_skills.py`](../../tools/test_generate_variant_skills.py) fails when a committed file differs from the generator output, and [`test_skill_texts.py`](../tests/test_skill_texts.py) fails when an undeclared section differs from A4.

| Condition          | Sections that differ from A4                                                                                                             |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| A5 no goal network | selection, state, brief, role reports, finish, and references without goals; no goals, goal-event, or ledger sections                    |
| A6 fixed order     | selection replaced by the repeated `Planning`, `Translating`, then `Reviewing` cycle, with role reports and goals reworded to that cycle |
| A7 single writer   | A8's changes plus a paragraph-unit section that limits each `Translating` step to one paragraph of at most 120 words                     |
| A8 single context  | delegation replaced by in-context execution, with a brief that has no role-agent lines                                                   |
| A12 loop only      | A5's goal removals, A6's selection and role reports, and A8's in-context execution together                                              |

The rewrite removed A7's instructions to follow the repository writing guidance and to remove filler and AI-pattern phrasing, which the other conditions did not have.

**Role skills and delegation.** For Codex runs of A4 to A8 and A12, the runner stages the invoked skill under `plugin/skills/` and the [`planning`](../../plugin/skills/planning/SKILL.md), [`translating`](../../plugin/skills/translating/SKILL.md), and [`reviewing`](../../plugin/skills/reviewing/SKILL.md) role skills under `.agents/skills/`. Codex discovers the role skills there, and their `allow_implicit_invocation: false` policy keeps them out of the `Monitor`'s skill list while a `$planning` mention in a brief still loads the skill. The `Monitor` skill stays outside the discovery roots, and role agents are told not to open it. The generated Codex configuration pins `[agents] max_depth = 1` and `max_threads = 6`, the defaults of the pinned Codex version.

The `Monitor` spawns each role agent with `fork_context: false` and a brief that begins with `$<role>`, states that the agent is not the `Monitor`, and repeats the single-turn, language, and no-retrieval rules that role agents do not otherwise see. A delegating run fails when a role has fewer completed `spawn_agent` calls naming it than `process_switch` events entering it; the manifest records both counts under `role_delegation`. The skills contain no performed-by-the-`Monitor` alternative, so a trace decision that mentions a fallback indicates a deviation from the skill.

**Trace script.** Each Monitor skill ships `scripts/writing_state.py`. Its `log` command reads `key: value` lines, fills the timestamp, `process`, `from_process`, and the responsible agent, encodes every event with a JSON encoder, and appends nothing when an event is invalid. Its `check` command verifies that the trace parses and lists goals without a goal event, and its `words` command implements A7's paragraph limit with CJK characters counted as words.

**Acknowledgment lines.** Every skill the runner stages opens with a note asking the reader to say `I read <skill name>.` immediately after reading it. The top-level agent says its skill's line in an assistant message, a role agent begins its report with its role skill's line, and an in-context `Monitor` says a role skill's line when it first reads that skill. The manifest's `skill_acknowledgments` counts the lines per skill in the top-level event stream and per spawned role agent in the collected rollouts; missing lines are reported, not enforced. The single-turn contract tells every condition never to include an acknowledgment line in the final response, and a final response that contains one fails the run, because the line would otherwise enter the scored document.

## A9 staged role instructions

A9 tests whether the role instructions alone, without the `Monitor`, explain A4's advantage over A2. A9 is an exploratory condition added after the primary results were observed and sits outside the confirmatory family.

A9 reuses the A2 harness unchanged: the `writing-linear` skill, the same Codex invocation and contracts, one session, the fixed Pre-Write, Write, and Re-Write order, and A2's three-event `process_switch` trace contract. The only difference is the stage text. Each A9 stage file keeps the corresponding A2 stage paragraph and input blocks verbatim and adds one role section taken from the A4 role skills: Pre-Write receives [`planning`](../../plugin/skills/planning/SKILL.md), Write receives [`translating`](../../plugin/skills/translating/SKILL.md), and Re-Write receives [`reviewing`](../../plugin/skills/reviewing/SKILL.md). A9 has no `Monitor`, no goal network or `.writing/goals.md`, no role trace events, no subagents, and no adaptive process selection.

[`generate_variant_skills.py`](../../tools/generate_variant_skills.py) writes each role section from the current role skill by these rules, which remove only text that refers to the `Monitor`, the goal network, the trace, shared `.writing/` state that A2 does not create, delegation, local-only revision, or the report the role returns to the `Monitor`. The A9 runs of generation run 1 used role sections taken from the role skills before the rewrite.

- **All three roles.** The frontmatter, the acknowledgment note, the role heading, the "When this skill runs" section, the list of files to read, the Boundaries section, and the report format are removed.
- **Planning, used in Pre-Write.** The opening line becomes "Turn the writing problem into grounded knowledge and useful organization." The rhetorical-problem list and the Generate and Organize sub-processes are kept verbatim. Goal-setting becomes "create concrete sub-goals for the response", with the per-section length targets kept, and the goal notation is removed. The no-invention rule is kept, and the report becomes one sentence asking for the organization, the length targets, the generated knowledge by confidence, the sub-goals, and unresolved uncertainty.
- **Translating, used in Write.** The opening line becomes "Turn selected meanings and plans into prose." The drafting paragraph is kept, with "the scope's goals" becoming "the plan's sub-goals". The drafting rules keep the length-target, supplied-text, and no-invention rules and drop the rules on the brief's language and scope, the files the role must not write, and marking gaps in the report.
- **Reviewing, used in Re-Write.** The opening line becomes "Evaluate the draft against the rhetorical problem, then revise it." The Evaluate list is kept, with "the active goals" becoming "the plan's sub-goals". Revise becomes "revise the draft to fix the problems that Evaluate finds", because the Re-Write stage returns the final text and has no later process to take findings. "Do not invent citations or claims." is kept.

## A10 budget-matched Self-Refine

A10 tests whether spending Agentic CogWriter's generation budget on plain self-feedback explains A4's advantage. A10 follows Self-Refine[^1]: one generator writes a draft, gives feedback on it, and refines it, for a fixed number of rounds. A10 is an exploratory condition added after the primary results were observed and sits outside the confirmatory family.

A10 uses the same harness as A2: one `codex exec` session with the shared single-turn contract, the same generator, reasoning effort, output budget, timeout, and retry policy, a workspace-write sandbox with network access off, and a fixed process order recorded as `process_switch` events. The [`writing-self-refine`](../baselines/skills/writing-self-refine/SKILL.md) skill in the baseline package defines the Draft, Feedback, and Refine handoffs and their trace. A10 has no `Monitor`, no goal network or `.writing/goals.md`, no role skills, no subagents, and no early stopping.

The three frozen stage files are generic Self-Refine prompts written for A10, not adaptations of the A4 role skills. [`a10_draft.md`](prompts/a10_draft.md) asks for a complete draft, [`a10_feedback.md`](prompts/a10_feedback.md) asks for actionable and specific feedback that points to the passage or omission behind each problem and the change that would fix it, and [`a10_refine.md`](prompts/a10_refine.md) asks for a complete revision that addresses that feedback. The wrapper lists the Feedback and Refine files once per round, so the trace contract is one Draft event followed by alternating Feedback and Refine events.

**Round count.** A10 runs k = 2 Feedback and Refine rounds. The round count was fixed before the scored run so that A10's mean output-plus-reasoning tokens per document approximate A4's run-1 mean of 13,374 tokens. Calibration ran k = 1 and k = 2 on the same twelve prompts, the four prompts per benchmark ranked immediately below the hard100 cut by the [prompt-set](../prompts/README.md#pilot-and-hard-prompt-subsets) difficulty key. None of the calibration prompts is a pilot or scored prompt. The rule picks the k whose calibration mean is closest to the A4 target, which selects k = 2.

| Rounds | Completed calibration runs | Mean output-plus-reasoning tokens |
| -----: | -------------------------: | --------------------------------: |
|      1 |                         12 |                            11,397 |
|      2 |                         12 |                            13,689 |

[^1]: Aman Madaan, Niket Tandon, Prakhar Gupta, Skyler Hallinan, Luyu Gao, Sarah Wiegreffe, Uri Alon, Nouha Dziri, Shrimai Prabhumoye, Yiming Yang, Shashank Gupta, Bodhisattwa Prasad Majumder, Katherine Hermann, Sean Welleck, Amir Yazdanbakhsh, and Peter Clark, "Self-Refine: Iterative Refinement with Self-Feedback," _Advances in Neural Information Processing Systems_ (2023), [DOI](https://doi.org/10.52202/075280-2019) and [arXiv](https://arxiv.org/abs/2303.17651).

## A11 plain agent

A11 tests whether the Agentic CogWriter skill adds anything beyond what the coding-agent harness already provides. A11 is an exploratory condition added after the primary results were observed and sits outside the confirmatory family.

A11 reuses the A1 harness: the same Codex invocation form and contracts, one session, the same generator, output budget, sandbox, and no-network policy, A1's `product_requires_draft = false` gate, and A1's fixed one-event `process_switch` trace contract with the single process `generate`. A11 has no stage prompt, so the composed prompt carries only the invocation, the single-turn contract, and the assignment, supplied context, and requested output constraints.

The [`writing-plain-agent`](../baselines/skills/writing-plain-agent/SKILL.md) skill file holds the only condition-specific text. The writing instruction is this sentence pair, verbatim:

> Write the requested document. Keep your working draft in a file in the workspace; you may plan, draft, and revise it as you see fit before returning the complete final document.

The instruction names no cognitive process, review criterion, audience or goal guidance, or role-skill content. A11 has no `Monitor`, goal network, role instructions, subagents, or fixed draft path.

The runner's validity gate requires a schema-valid trace, so the skill file also gives the one shell command that appends A1's fixed `generate` event to `.writing/trace/process.jsonl`, framed as a harness record outside the writing task. The trace therefore records only that the session ran and says nothing about the agent's drafting behavior; draft writes and revisions are measured from the Codex event stream instead.

## A12 loop-only

A12 tests whether A4's advantage survives when the three components that A5, A6, and A8 each remove alone are removed together. A12 keeps the `Monitor`, the persistent `.writing/` draft and state, the role skills' writing guidance, the process-switch trace, and the A4 harness and settings. A12 has no goal network, a prompt-fixed `Planning`, `Translating`, then `Reviewing` order, and no subagents: the `Monitor` performs every role in its own context. A12 is an exploratory condition added after the primary results were observed and sits outside the confirmatory family.

The [`cognitive-writing-loop-only`](../plugin/skills/cognitive-writing-loop-only/SKILL.md) skill combines A5's goal removals, A6's selection section, and A8's in-context execution on A4's text, as the table under Agentic CogWriter and its ablations lists. The wrapper [`a12_loop_only.toml`](a12_loop_only.toml) takes A5's trace policy, with goal events forbidden and `.writing/goals.md` protected, and A8's `require_delegation = false`, so the runner appends no delegation contract and fails a Codex run that spawns a subagent. Like A6, A12 enforces the fixed order by prompt only.

The A12 runs reported for generation run 1 used an earlier text built from the A5, A6, and A8 skill texts that run 1 executed, with their interactive-user passages kept. The rewrite that added the stop rule, the delegation brief, and the shared language contract replaced that text, so a new A12 run is needed for the current skill.
