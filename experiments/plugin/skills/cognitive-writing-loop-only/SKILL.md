---
name: cognitive-writing-loop-only
description: "Use this skill for exploratory A12 comparisons. It keeps the Agentic CogWriter Monitor loop, shared writing state, and process-switch trace, but removes the goal network, fixes the Planning, Translating, then Reviewing order, and has the host agent perform each process in its own context instead of delegating."
---

# Loop-only cognitive writing

Run a comparison that uses the assignment as one implicit objective, runs `Planning`, `Translating`, then `Reviewing` in a fixed order, and performs every process in the `Monitor`'s own context, while preserving the agentic-cog-writer skill's project state and process-switch trace contracts.

## When this skill runs

Use this skill only when the user explicitly requests a controlled loop-only comparison. Do not use it as the default writing workflow.

## `Monitor` responsibilities

- Keep rhetorical intent, factual authority, final wording, and publication decisions under the user's control.
- Coordinate the prescribed order and record the evidence for each process switch.
- Perform the current process in the host agent's own context. Do not delegate it to a role agent or subagent.
- Ask the user when a choice changes the rhetorical problem or a claim.
- Reconcile each process's work with the assignment before continuing.
- Report proposals that affect intent or factual claims. Let the user override an agent decision.

## Read the state first

Create missing files and directories without overwriting existing content. Do not create or modify `.writing/goals.md`. Treat these files as the user's externalized task environment and long-term memory:

```text
.writing/
├── assignment.md       # topic, audience, exigency, and writer's goals
├── goals.md            # existing file is left untouched, if present
├── draft.md            # growing text
├── memory/             # topic knowledge, audience knowledge, and writing plans
└── trace/              # structured process history, one JSON object per line
```

Read these before the first process:

- `.writing/assignment.md`
- `.writing/draft.md`
- relevant files in `.writing/memory/`
- the latest entries in `.writing/trace/process.jsonl`

Do not create or modify `.writing/goals.md`, whether it exists or not.

Treat the assignment as the single implicit objective. Do not use a hierarchical goal to fill missing user intent.

If `assignment.md` is missing or underspecified, ask for:

- topic
- audience
- exigency
- writer's goals
- genre
- constraints

Do not silently invent a rhetorical problem.

Read the trace field contract below before writing the first entry. Append to `.writing/trace/process.jsonl`; never rewrite or truncate that log.

## Fixed `Monitor` loop

At each pass, the `Monitor` must:

1. Start with `Planning`. After `Planning` resolves, switch to `Translating`. After `Translating` resolves, switch to `Reviewing`. Start the next pass with `Planning`.
2. Compare the assignment's implicit objective with the rhetorical problem, draft, retrieved memory, and open uncertainty. Use that evidence within the current prescribed process. Do not choose a different next process because a local preference suggests it. Do not consult or construct a hierarchical goal network.
3. Before every process switch, append a `process_switch` event naming the responsible process or agent, its decision, its evidence, and open uncertainty. The loop-only variant records no goal-created, goal-developed, or goal-regenerated events.
4. Perform the current process in the host agent's own context, following In-context process execution. Do not spawn a role agent or subagent.
5. For a `Planning` pass, perform problem representation, Generate, and Organize. Do not perform Goal-setting or write `goals.md`. If the planning work suggests a hierarchical goal, record it as an observation without changing the file.
6. Re-read changed state and reconcile the process's work with the assignment. Update `draft.md` or `memory/` as appropriate. Keep user-authored text and uncertain claims visible.
7. Tell the user:

   - what changed
   - that the assignment remains the implicit objective
   - what remains uncertain
   - which prescribed process comes next

   Ask for a decision when the next move depends on user intent or factual authority.

Before sending the final response, write the complete current document to `.writing/draft.md`. The run is `INVALID` unless `.writing/draft.md` exists before the final response and the final response contains the complete final text. The final response cannot substitute for the required draft.

## Interruptions

Generate and Evaluate may interrupt any process when new information or a conflict in the growing text demands it. Log each interruption as a `process_switch`, perform the interrupt in the host agent's own context following the relevant role's instructions, return to the interrupted process, and then continue with the next process in the prescribed order.

An interruption must not select a new order. Do not create a goal to track the interrupt.

## In-context process execution

Perform every process in the host agent's own context. Before working, read and apply the current role's skill instructions from `plugin/skills/planning/SKILL.md`, `plugin/skills/translating/SKILL.md`, or `plugin/skills/reviewing/SKILL.md` exactly as a delegated role agent would, except that no process creates or modifies `.writing/goals.md`. Preserve the project root, the assignment summary, relevant uncertainty, and requested output while working. Use the same process brief as A5: provide the project root, the assignment summary, relevant uncertainty, and the requested output. Cite the files or draft passages that support decisions. Do not spawn a role agent, subagent, or child `codex exec` process.

## Trace contract

Every process switch must append one valid JSON object to `.writing/trace/process.jsonl`. `event_type` is `process_switch`; goal events are not written in this condition. A process-switch object includes `timestamp`, `event_type`, `responsible_agent`, `process`, `decision`, `evidence`, `open_uncertainty`, `from_process`, and `to_process`. Optional `artifacts` lists project-relative files. In the JSON object, `timestamp`, `event_type`, `responsible_agent`, `process`, and `decision` are strings; `evidence` and `open_uncertainty` are arrays of strings; `from_process` and `to_process` are strings or `null`; and `artifacts`, when present, is an array of project-relative path strings; set `timestamp` to the current wall-clock time obtained from the shell at write time, for example `date -Is`, and never copy example timestamps. Keep the code-formatted role names `Planning`, `Translating`, and `Reviewing` in surrounding prose, but write JSON `process`, `from_process`, and `to_process` values with the lowercase contract tokens `planning`, `translating`, and `reviewing`. Do not write goal fields or experiment-specific fields. For example:

```json
{
  "timestamp": "2026-01-15T09:00:00+09:00",
  "event_type": "process_switch",
  "responsible_agent": "monitor",
  "process": "planning",
  "decision": "Begin the prescribed planning pass for the assignment's implicit objective.",
  "evidence": [".writing/assignment.md"],
  "open_uncertainty": [],
  "from_process": null,
  "to_process": "planning",
  "artifacts": [".writing/assignment.md"]
}
```
