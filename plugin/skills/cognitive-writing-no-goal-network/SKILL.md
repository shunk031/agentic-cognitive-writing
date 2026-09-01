---
name: cognitive-writing-no-goal-network
description: "Experiment-comparison variant of the cognitive-writing skill for testing writing without a hierarchical goal network. For internal comparison use only, not the recommended default. Use when a controlled no-goal-network comparison is explicitly requested."
---

# Cognitive writing without a goal network

Run a comparison that uses the assignment as one implicit objective while preserving the cognitive-writing skill's project state, delegation, and trace contracts.

## When this skill runs

Use this skill only when the user explicitly requests a controlled no-goal-network comparison. Do not use it as the default writing workflow.

## Monitor responsibilities

- Keep rhetorical intent, factual authority, final wording, and publication decisions under the user's control.
- Coordinate process switches and record the evidence for each switch.
- Ask the user when a choice changes the rhetorical problem or a claim.
- Reconcile each returned role report with the assignment before continuing.
- Report proposals that affect intent or factual claims. Let the user override an agent decision.

## Read the state first

Create missing files and directories without overwriting existing content. This variant never creates or edits `goals.md`. Treat these files as the user's externalized task environment and long-term memory:

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

Leave `goals.md` untouched, whether it exists or not. Treat the assignment as the single implicit objective. Do not use a hierarchical goal to fill missing user intent. If `assignment.md` is missing or underspecified, ask for:

- topic
- audience
- exigency
- writer's goals
- genre
- constraints

Do not silently invent a rhetorical problem. Read the trace field contract below before writing the first entry. Append to `.writing/trace/process.jsonl`; never rewrite or truncate that log.

## Monitor loop

At each turn, the Monitor must:

1. Compare the assignment's implicit objective with the current project state and open uncertainty. Choose Planning, Translating, or Reviewing from that comparison. Do not consult or construct a hierarchical goal network.
2. Before every process switch, append a `process_switch` event naming the responsible process or agent, its decision, its evidence, and open uncertainty. This variant records no goal-created, goal-developed, or goal-regenerated events.
3. Delegate the selected role using the Delegation section.
4. For a Planning delegation, request problem representation, Generate, and Organize. Do not request Goal-setting or ask the agent to write `goals.md`. If the agent proposes a hierarchical goal, report it as an observation without changing the file.
5. Re-read changed state and reconcile the role's work with the assignment. Update `draft.md` or `memory/` as appropriate. Keep user-authored text and uncertain claims visible.
6. Tell the user:
   - what changed
   - that the assignment remains the implicit objective
   - what remains uncertain
   - which process the Monitor recommends next

   Ask for a decision when the next move depends on user intent or factual authority.

## Interruptions

Generate and Evaluate may interrupt any process when new information or a claim conflict in the growing text demands it. Log each interruption as a `process_switch`, perform the interrupt through the relevant shared role, return to the process that initiated it, and then continue the Monitor's process choice. Do not create a goal to track the interrupt. When an interrupt resolves, return to the process that initiated it rather than silently changing the assignment.

## Delegation

For every delegation, pass:

- the project root
- the assignment summary
- relevant uncertainty
- the requested output

Ask the delegated agent to cite the files or draft passages that support its decisions. Use the platform path that matches the host:

- Claude Code: delegate to the bundled planner, translator, or reviewer agent. It preloads the matching role skill.
- Codex: spawn a native Codex subagent and instruct it to use `$planning`, `$translating`, or `$reviewing`.

Do not write a script that spawns `codex exec` children. If native delegation is unavailable, perform the role as Monitor and record that fallback in the trace.

## Trace contract

Every process switch must append one valid JSON object to `.writing/trace/process.jsonl`. A process-switch object includes `timestamp`, `event_type`, `responsible_agent`, `process`, `decision`, `evidence`, `open_uncertainty`, `from_process`, and `to_process`. Optional `artifacts` lists project-relative files. Do not write goal fields or experiment-specific fields.
