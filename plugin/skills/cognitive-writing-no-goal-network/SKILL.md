---
name: cognitive-writing-no-goal-network
description: "Experiment-comparison variant of the cognitive-writing skill for testing writing without a hierarchical goal network. For internal comparison use only, not the recommended default. Use when a controlled no-goal-network comparison is explicitly requested."
---

# Cognitive writing without a goal network

Use this skill only for an explicit comparison that removes hierarchical goals. It keeps the cognitive-writing skill's project state, process delegation, and trace contracts. The assignment is the single implicit objective, and the Monitor chooses processes from the assignment, draft, memory, and uncertainty. This is not the recommended default for ordinary writing.

## Responsibility

- The user owns rhetorical intent, factual authority, final wording, and the decision to publish or submit.
- The Monitor is the main agent. It coordinates the writing processes, records process switches, and asks the user when a choice changes the rhetorical problem or a claim.
- The Planner represents the rhetorical problem and performs Generate and Organize. Do not use its Goal-setting sub-process to create or change a hierarchical goal network in this variant.
- The Translator turns selected meanings and plans into draft prose.
- The Reviewer evaluates the draft and plan, then revises within the delegated scope. Its embedded processes are Evaluate and Revise.

Agents may propose changes within their delegated scope. The Monitor reports proposals that affect intent or factual claims. The user may override an agent decision.

## Start with the writing state

1. Treat these files as the user's externalized task environment and long-term memory. Create missing files and directories without overwriting existing content, except that this variant never creates or edits `goals.md`:

   ```text
   .writing/
   ├── assignment.md       # topic, audience, exigency, and writer's goals
   ├── goals.md            # existing file is left untouched, if present
   ├── draft.md            # growing text
   ├── memory/             # topic knowledge, audience knowledge, and writing plans
   └── trace/              # structured process history, one JSON object per line
   ```

2. Read `assignment.md`, `draft.md`, relevant files in `memory/`, and the latest trace entries before choosing a process. Leave `goals.md` untouched, whether it exists or not. Treat the assignment as the single implicit objective; do not use a hierarchical goal to fill missing user intent.
3. If `assignment.md` is missing or underspecified, ask for the topic, audience, exigency, writer's goals, genre, and constraints. Do not silently invent a rhetorical problem.
4. Before writing the first trace entry, apply the trace field contract in this skill. Append to `.writing/trace/process.jsonl`; never rewrite or truncate that log.

## Monitor loop

At each turn, the Monitor must:

1. Compare the assignment's implicit objective with the current draft, retrieved memory, and open uncertainty. Choose Planning, Translating, or Reviewing from that comparison. Do not consult or construct a hierarchical goal network.
2. Before every process switch, append a `process_switch` event naming the responsible process or agent, the decision, its evidence, and open uncertainty. This variant records no goal-created, goal-developed, or goal-regenerated events.
3. Delegate the selected role. On Claude Code, use the bundled `planner`, `translator`, or `reviewer` agent, which preloads the matching shared role skill. On Codex, request a native Codex subagent and explicitly invoke `$planning`, `$translating`, or `$reviewing` inside that delegation. Do not write a script that spawns `codex exec` children. If native delegation is unavailable, perform the role as Monitor and record that fallback in the trace.
4. For a planning delegation, request only problem representation, Generate, and Organize. Do not ask the Planner to run Goal-setting or write `goals.md`. If the Planner proposes a hierarchical goal, report it as an observation without changing the file.
5. Re-read changed state, reconcile the role's work with the assignment, and update `draft.md` or `memory/` as appropriate. Keep user-authored text and uncertain claims visible.
6. Tell the user what changed, that the assignment remains the implicit objective, what remains uncertain, and which process the Monitor recommends next. Ask for a decision when the next move depends on user intent or factual authority.

## Interruptions and delegation briefs

Generate and Evaluate may interrupt any process when new knowledge, a claim conflict, or the growing text demands it. Log each interruption as a `process_switch`, perform the interrupt through the relevant shared role, return to the interrupted process, and then continue the Monitor's process choice. Do not create a goal to track the interrupt. When an interrupt resolves, return to the process that initiated it rather than silently changing the assignment.

Pass the project root, assignment summary, relevant uncertainty, and requested output to each sub-agent. Ask agents to cite the files or draft passages supporting their decisions. The Planner should leave a problem representation or plan without hierarchical goal IDs. The Translator should edit only the delegated draft scope and flag unsupported claims. The Reviewer should separate evaluation from revision and state whether a change affects a claim, organization, or only wording.

Every process switch must append one valid JSON object to `.writing/trace/process.jsonl`. A process-switch object includes `timestamp`, `event_type`, `responsible_agent`, `process`, `decision`, `evidence`, `open_uncertainty`, `from_process`, and `to_process`. Optional `artifacts` lists project-relative files. Do not write goal fields or experiment-specific fields.
