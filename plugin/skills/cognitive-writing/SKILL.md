---
name: cognitive-writing
description: Use this skill whenever a user wants to plan, draft, translate, review, or revise writing. It runs Flower and Hayes' Monitor loop over the rhetorical problem, hierarchical goals, growing text, and writing memory, and coordinates planning, translating, and reviewing while preserving an observable process trace.
---

# Cognitive writing

Use this skill in the user's writing project. The project root is the current working directory unless the user names another project. The Monitor is the main agent running this skill. It chooses the next writing process from the current goal network, draft, rhetorical problem, and uncertainty. It does not impose a fixed stage sequence.

## Roles and responsibility

- The user owns the rhetorical intent, factual authority, final wording, and decision to publish or submit.
- The Monitor, which is the main agent, owns process coordination. It proposes process switches, records their evidence, and asks the user when a choice materially changes the rhetorical problem or claim.
- The Planner develops the problem representation and goal network. Its embedded sub-processes are Generate, Organize, and Goal-setting.
- The Translator turns selected meanings and plans into draft prose.
- The Reviewer checks the draft and plan against the rhetorical problem. Its embedded sub-processes are Evaluate and Revise.

Agents may propose changes within their delegated scope. The Monitor reports those proposals to the user when they affect intent, factual claims, or a major goal. The user may override any agent decision.

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

2. Read `assignment.md`, `goals.md`, `draft.md`, relevant files in `memory/`, and the latest trace entries before choosing an operation. If `assignment.md` is missing or underspecified, ask the user for the topic, audience, exigency, writer's goals, genre, and constraints. Do not silently invent a rhetorical problem.
3. Keep `goals.md` in the notation described in `references/goals-format.md`. Update it whenever a goal is created, developed, or regenerated. Preserve the history instead of replacing an earlier goal without recording what changed.
4. Read `references/trace-jsonl-schema.md` before writing the first trace entry. Append to `.writing/trace/process.jsonl`; never rewrite or truncate that log.

## Monitor loop

At each turn, the Monitor should:

1. Identify the active goal and its parent. If a sub-goal resolves, pop back to the parent goal before choosing the next operation.
2. Compare the active goal with the rhetorical problem, the current draft, retrieved memory, and open uncertainty. Use that comparison to select planning, translating, or reviewing. Planning may mean exploring, organizing, or setting a goal. Reviewing may mean evaluating or revising.
3. Before every process switch, append a `process_switch` event naming the responsible process or agent, the decision, the evidence, and open uncertainty. Record a separate goal event whenever a goal is created, developed, or regenerated. Use the exact fields in the trace reference.
4. Delegate the selected role. On Claude Code, use the bundled `planner`, `translator`, or `reviewer` agent; each agent preloads the matching shared role skill. On Codex, request a native Codex subagent and explicitly invoke the matching role skill, `$planning`, `$translating`, or `$reviewing`, inside that delegation. Do not write a script that spawns `codex exec` children. If native delegation is unavailable, the Monitor may perform the role itself and must record that fallback in the trace.
5. Re-read the changed state, reconcile the agent's work with the active goal, and update `goals.md`, `draft.md`, or `memory/` as appropriate. Keep user-authored text and uncertain claims visible rather than silently normalizing them.
6. Tell the user what changed, which goal is active, what remains uncertain, and which process the Monitor recommends next. Ask for a decision when the next move depends on the user's intent or factual authority.

## Non-linear control rules

Writing processes are a recursive toolkit, not a pipeline. A process may call another process to solve a local problem, and that process may call the whole loop again. Generate and Evaluate may interrupt any process at any time when new knowledge, a goal conflict, or the growing text demands it. Log the interruption as a process switch, then resume the interrupted parent goal after the sub-goal resolves.

When new writing changes what the author understands, use Goal-setting to develop or regenerate the goal network. A regenerated goal is not a failure of the earlier plan; it is part of learning through composing. Keep both the prior record and the new rationale in `goals.md` and the trace.

## Delegation briefs

Pass the project root, active goal ID, parent goal ID, relevant uncertainty, and the requested output to each sub-agent. Ask agents to cite the files or draft passages that support their decisions. The Planner should use `$planning` on Codex, or its preloaded Claude skill, and leave a usable goal network or plan. The Translator should use `$translating` on Codex, or its preloaded Claude skill, edit only the delegated draft scope, and flag unsupported claims. The Reviewer should use `$reviewing` on Codex, or its preloaded Claude skill, separate evaluation from revision, and state whether the revision changes a goal, a claim, the organization, or only wording.

## References

Read these only when the corresponding operation needs them:

- `references/trace-jsonl-schema.md` defines the trace fields and event types.
- `references/goals-format.md` defines hierarchical goal notation and history records.
- `references/ablation-variants.md` defines fixed-linear-order and no-goal-network runs without forking this skill.
