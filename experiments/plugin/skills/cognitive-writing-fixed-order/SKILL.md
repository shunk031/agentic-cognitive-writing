---
name: cognitive-writing-fixed-order
description: "Experiment-comparison variant of the agentic-cog-writer skill for testing a fixed `Planning`, `Translating`, then `Reviewing` order. For internal comparison use only, not the recommended default. Use when a controlled fixed-order comparison is explicitly requested."
---

# Fixed-order cognitive writing

Run a comparison with a fixed `Planning`, `Translating`, then `Reviewing` order while preserving the agentic-cog-writer skill's project state, goal network, delegation, and trace contracts.

## When this skill runs

Use this skill only when the user explicitly requests a controlled fixed-order comparison. Do not use it as the default writing workflow.

## `Monitor` responsibilities

- Keep rhetorical intent, factual authority, final wording, and publication decisions under the user's control.
- Coordinate the prescribed order and record the evidence for each process switch.
- Ask the user when a choice changes the rhetorical problem, a claim, or a major goal.
- Reconcile each returned role report with the active goal before continuing.
- Report proposals that affect intent, factual claims, or a major goal. Let the user override any agent decision.

## Read the state first

Create missing files and directories without overwriting existing content. Treat these files as the user's externalized task environment and long-term memory:

```text
.writing/
├── assignment.md       # topic, audience, exigency, and writer's goals
├── goals.md            # hierarchical goals and creation/development history
├── draft.md            # growing text
├── memory/             # topic knowledge, audience knowledge, and writing plans
└── trace/              # structured process history, one JSON object per line
```

Read these before the first process:

- `.writing/assignment.md`
- `.writing/goals.md`
- `.writing/draft.md`
- relevant files in `.writing/memory/`
- the latest entries in `.writing/trace/process.jsonl`

If `assignment.md` is missing or underspecified, ask for:

- topic
- audience
- exigency
- writer's goals
- genre
- constraints

Do not invent a rhetorical problem.

Keep `goals.md` in the project's hierarchical notation. Use stable goal identifiers (IDs). Put one goal on each line. Indent child goals beneath their parent. Keep a history section.

Update the file whenever a goal is created, developed, or regenerated. Preserve earlier history and record the reason for each change.

Read the trace field contract below before writing the first entry. Append to `.writing/trace/process.jsonl`; never rewrite or truncate that log.

## Fixed `Monitor` loop

At each pass, the `Monitor` must:

1. Start with `Planning`. After `Planning` resolves, switch to `Translating`. After `Translating` resolves, switch to `Reviewing`. Start the next pass with `Planning`.
2. Keep the active goal and its parent visible. When a sub-goal resolves, pop back to its parent before continuing the prescribed order.
3. Compare the active goal with the rhetorical problem, draft, retrieved memory, and open uncertainty. Use that evidence within the current prescribed process. Do not choose a different next process because a local preference suggests it.
4. Before every process switch, append a `process_switch` event naming the responsible process or agent and recording its decision, evidence, and open uncertainty. Record a separate goal event whenever a goal is created, developed, or regenerated. Use the exact fields in the trace contract below.
5. Delegate the current role using the Delegation section.
6. Re-read changed state and reconcile the role's work with the active goal. Update the appropriate project state:
   - `goals.md`
   - `draft.md`
   - `memory/`

   Keep user-authored text and uncertain claims visible.
7. Tell the user:
   - what changed
   - which goal is active
   - what remains uncertain
   - which prescribed process comes next

   Ask for a decision when the next move depends on user intent or factual authority.

Before sending the final response, write the complete current document to `.writing/draft.md`. The run is `INVALID` unless `.writing/draft.md` exists before the final response and the final response contains the complete final text. The final response cannot substitute for the required draft.

## Interruptions

Generate and Evaluate may interrupt any process when new information or a conflict in the growing text demands it. Log each interruption as a `process_switch`, perform the interrupt through the relevant shared role, return to the interrupted process, and then continue with the next process in the prescribed order.

An interruption must not select a new order. After any sub-goal resolves, return to its parent goal.

## Delegation

For every delegation, pass:

- the project root
- the active goal ID
- the parent goal ID
- relevant uncertainty
- the requested output

Ask the delegated agent to cite the files or draft passages that support its decisions. Use the platform path that matches the host:

- Claude Code: delegate to the planner, translator, or reviewer agent shipped in the `agentic-cognitive-writing` plugin. That agent preloads the matching role skill.
- Codex: spawn a native Codex subagent and instruct it to use `$planning`, `$translating`, or `$reviewing`.

Do not write a script that spawns `codex exec` children. If native delegation is unavailable, perform the role as the `Monitor` and record that fallback in the trace.

## Trace contract

Every process switch and every goal creation, development, or regeneration must append one valid JSON object to `.writing/trace/process.jsonl`. A process-switch object includes `timestamp`, `event_type`, `responsible_agent`, `process`, `decision`, `evidence`, `open_uncertainty`, `from_process`, and `to_process`. A goal event also includes `goal_id` and `parent_goal_id`. Optional `artifacts` lists project-relative files. In the JSON object, `timestamp`, `event_type`, `responsible_agent`, `process`, and `decision` are strings; `evidence` and `open_uncertainty` are arrays of strings; `from_process` and `to_process` are strings or `null`; `goal_id` is a string; `parent_goal_id` is a string or `null`; and `artifacts`, when present, is an array of project-relative path strings. Keep the code-formatted role names `Planning`, `Translating`, and `Reviewing` in surrounding prose, but write JSON `process`, `from_process`, and `to_process` values with the lowercase contract tokens `planning`, `translating`, and `reviewing`. Do not add experiment-specific fields to the shared trace contract. For example:

```json
{"timestamp":"2026-01-15T09:00:00+09:00","event_type":"process_switch","responsible_agent":"monitor","process":"planning","decision":"Begin the prescribed planning pass for the active goal.","evidence":[".writing/assignment.md",".writing/goals.md"],"open_uncertainty":["The audience's highest-priority concern is not yet known."],"from_process":null,"to_process":"planning","artifacts":[".writing/goals.md"]}
```
