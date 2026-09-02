---
name: cognitive-writing
description: Use this skill whenever a user needs help with writing. It runs a Monitor loop over the user's rhetorical problem and project state, coordinates the writing processes, and preserves an observable process trace.
---

# Cognitive writing

Use this skill in the user's writing project. The project root is the current working directory unless the user names another project.

The Monitor is the main agent running this skill. The Monitor chooses the next writing process from the project state and open uncertainty. The Monitor does not impose a fixed stage sequence.

## Monitor responsibilities

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
   - `assignment.md`
   - `goals.md`
   - `draft.md`
   - relevant files in `memory/`
   - the latest trace entries

   If `assignment.md` is missing or underspecified, ask the user for:
   - topic
   - audience
   - exigency
   - writer's goals
   - genre
   - constraints

   Do not silently invent a rhetorical problem.
3. Keep `goals.md` in the notation described in [`references/goals-format.md`](references/goals-format.md). Update it whenever a goal is created, developed, or regenerated. Preserve the history instead of replacing an earlier goal without recording what changed.
4. Read [`references/trace-jsonl-schema.md`](references/trace-jsonl-schema.md) before writing the first trace entry. Append to `.writing/trace/process.jsonl`; never rewrite or truncate that log.

## Monitor loop

At each turn, the Monitor should:

1. Identify the active goal and its parent. If a sub-goal resolves, pop back to the parent goal before choosing the next operation.
2. Compare the active goal with:
   - the rhetorical problem
   - the current draft
   - retrieved memory
   - open uncertainty

   Use that comparison to select planning, translating, or reviewing. Planning may mean:
   - exploring
   - organizing
   - setting a goal

   Reviewing may mean:
   - evaluating
   - revising
3. Before every process switch, append a `process_switch` event naming the responsible process or agent and recording the decision, evidence, and open uncertainty. Record a separate goal event whenever a goal is created, developed, or regenerated. Use the exact fields in the trace reference.
4. Delegate the selected role using the platform instructions in Delegation briefs.
5. Re-read the changed state and reconcile the agent's work with the active goal. Update the appropriate project state:
   - `goals.md`
   - `draft.md`
   - `memory/`

   Keep user-authored text and uncertain claims visible rather than silently normalizing them.
6. Tell the user:
   - what changed
   - which goal is active
   - what remains uncertain
   - which process the Monitor recommends next

   Ask for a decision when the next move depends on the user's intent or factual authority.

## Non-linear control rules

The writing processes form a recursive loop, not a pipeline. A process may call another process to solve a local problem, and that process may call the whole loop again. Generate and Evaluate may interrupt any process when new information or a conflict in the growing text demands it. Log the interruption as a process switch, then resume the interrupted parent goal after the sub-goal resolves.

When new writing changes what the author understands, use Goal-setting to develop or regenerate the goal network. A regenerated goal is not a failure of the earlier plan; it is part of learning through composing. Keep both the prior record and the new rationale in `goals.md` and the trace.

## Delegation briefs

For every delegation, pass:

- the project root
- the active goal identifier (ID)
- the parent goal ID
- relevant uncertainty
- the requested output

Ask each agent to cite the files or draft passages that support its decisions.

Use the platform path that matches the host:

- Claude Code: delegate to the bundled role agent. The bundled role agent preloads the matching role skill.
- Codex: spawn a native Codex subagent and instruct it to use the explicit role skill: `$planning`, `$translating`, or `$reviewing`.

Do not write a script that spawns `codex exec` children.

If native delegation is unavailable, perform the role as Monitor and record that fallback in the trace.

## References

Read these only when the corresponding operation needs them:

- [`references/trace-jsonl-schema.md`](references/trace-jsonl-schema.md) defines the trace fields and event types.
- [`references/goals-format.md`](references/goals-format.md) defines hierarchical goal notation and history records.
