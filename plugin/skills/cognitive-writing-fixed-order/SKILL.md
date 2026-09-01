---
name: cognitive-writing-fixed-order
description: "Experiment-comparison variant of the cognitive-writing skill for testing a fixed Planning, Translating, then Reviewing order. For internal comparison use only, not the recommended default. Use when a controlled fixed-order comparison is explicitly requested."
---

# Fixed-order cognitive writing

Use this skill only for an explicit comparison with a fixed process order. It keeps the cognitive-writing skill's project state, goal network, delegation, and trace contracts. It changes the Monitor's process choice to Planning, then Translating, then Reviewing on every pass. This is not the recommended default for ordinary writing.

## Responsibility

- The user owns rhetorical intent, factual authority, final wording, and the decision to publish or submit.
- The Monitor is the main agent. It coordinates the fixed order, records process switches, and asks the user when a choice changes the rhetorical problem, a claim, or a major goal.
- The Planner develops the problem representation and goal network. Its embedded processes are Generate, Organize, and Goal-setting.
- The Translator turns selected meanings and plans into draft prose.
- The Reviewer evaluates the draft and plan, then revises within the delegated scope. Its embedded processes are Evaluate and Revise.

Agents may propose changes within their delegated scope. The Monitor reports proposals that affect intent, factual claims, or a major goal. The user may override an agent decision.

## Start with the writing state

1. Treat these files as the user's externalized task environment and long-term memory. Create missing files and directories without overwriting existing content:

   ```text
   .writing/
   ├── assignment.md       # topic, audience, exigency, and writer's goals
   ├── goals.md            # hierarchical goals and creation/development history
   ├── draft.md            # growing text
   ├── memory/             # topic knowledge, audience knowledge, and writing plans
   └── trace/              # structured process history, one JSON object per line
   ```

2. Read `assignment.md`, `goals.md`, `draft.md`, relevant files in `memory/`, and the latest trace entries before the first process. If `assignment.md` is missing or underspecified, ask for the topic, audience, exigency, writer's goals, genre, and constraints. Do not invent a rhetorical problem.
3. Keep `goals.md` in the project's hierarchical notation. Use stable IDs, one goal per line, indentation for parent-child relationships, and a history section. Update it whenever a goal is created, developed, or regenerated. Preserve earlier history and record the reason for each change.
4. Before writing the first trace entry, apply the trace field contract in this skill. Append to `.writing/trace/process.jsonl`; never rewrite or truncate that log.

## Fixed Monitor loop

At each pass, the Monitor must:

1. Start with Planning. After Planning resolves, switch to Translating. After Translating resolves, switch to Reviewing. Start the next pass with Planning.
2. Keep the active goal and its parent visible. When a sub-goal resolves, pop back to its parent before continuing the prescribed order.
3. Compare the active goal with the rhetorical problem, draft, retrieved memory, and open uncertainty. Use that evidence within the current prescribed process. Do not choose a different next process because a local preference suggests it.
4. Before every process switch, append a `process_switch` event naming the responsible process or agent, the decision, its evidence, and open uncertainty. Record a separate goal event whenever a goal is created, developed, or regenerated. Use the exact fields in the trace reference.
5. Delegate the current role. On Claude Code, use the bundled `planner`, `translator`, or `reviewer` agent, which preloads the matching shared role skill. On Codex, request a native Codex subagent and explicitly invoke `$planning`, `$translating`, or `$reviewing` inside that delegation. Do not write a script that spawns `codex exec` children. If native delegation is unavailable, perform the role as Monitor and record that fallback in the trace.
6. Re-read changed state, reconcile the role's work with the active goal, and update `goals.md`, `draft.md`, or `memory/` as appropriate. Keep user-authored text and uncertain claims visible.
7. Tell the user what changed, which goal is active, what remains uncertain, and which prescribed process comes next. Ask for a decision when the next move depends on user intent or factual authority.

## Interruptions and delegation briefs

Generate and Evaluate may interrupt any process when new knowledge, a goal conflict, or the growing text demands it. Log each interruption as a `process_switch`, perform the interrupt through the relevant shared role, return to the interrupted process, and then continue with the next process in the prescribed order. An interruption must not select a new order. After any sub-goal resolves, return to its parent goal.

Pass the project root, active goal ID, parent goal ID, relevant uncertainty, and requested output to each sub-agent. Ask agents to cite the files or draft passages supporting their decisions. The Planner should leave a usable goal network or plan. The Translator should edit only the delegated draft scope and flag unsupported claims. The Reviewer should separate evaluation from revision and state whether a change affects a goal, a claim, organization, or only wording.

Every process switch and every goal creation, development, or regeneration must append one valid JSON object to `.writing/trace/process.jsonl`. A process-switch object includes `timestamp`, `event_type`, `responsible_agent`, `process`, `decision`, `evidence`, `open_uncertainty`, `from_process`, and `to_process`. A goal event also includes `goal_id` and `parent_goal_id`. Optional `artifacts` lists project-relative files. Do not add experiment-specific fields to the shared trace contract.
