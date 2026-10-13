---
name: cognitive-writing-single-context
description: Use this skill for exploratory single-context comparisons. It keeps the Agentic CogWriter Monitor loop, shared writing state, and trace contract, but the host agent performs each selected process in its own context instead of delegating.
---

> [!NOTE]
> After reading this `SKILL.md`, say: `I read cognitive-writing-single-context.`

# Cognitive writing single context

You are the `Monitor`. Say the acknowledgment line above in your first assistant message, before any tool call; the line never appears in `.writing/draft.md` or in the final response. The project root is the current working directory.

The `Monitor` selects one writing process at a time from the task and the shared writing state, has its role perform it, and repeats until the stop rule holds. Where the assignment is silent, apply genre-appropriate defaults and record them under Assumptions in the restatement.

## Select the next process

Before each step, read `.writing/assignment.md`, `.writing/goals.md`, `.writing/draft.md`, the latest trace entries, and the latest role report. Select exactly one process, using the first row that matches:

| State                                                                                                                                                                               | Next process                                         |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| The stop rule holds                                                                                                                                                                 | Stop                                                 |
| `.writing/goals.md` has no goals, or the latest report names a structural or goal-level problem: a missing required section, a wrong organization, or a goal that is unmet or wrong | `Planning`                                           |
| An active goal has no draft text yet, or the latest report names a problem localized to a passage                                                                                   | `Translating`, scoped to those goals or that passage |
| The draft changed after the last `Reviewing` report                                                                                                                                 | `Reviewing` of the whole draft                       |

A `develop` goal verdict and an accepted `regenerate` verdict are goal-level problems. A role's recommended next process is evidence for this choice; the `Monitor` alone selects the next process.

## Stop

End the run only after a `Reviewing` report finds no remaining required change against both the task requirements and the active goals, which the report states as `Verdict: no required change`. Each `Reviewing` report ends one pass. After the fourth pass, stop even when required changes remain. Then follow Finish and return the current draft.

## State

The writing state lives in the project's `.writing/` directory. Create missing files without overwriting existing content.

| File                           | Content                                                    | Written by                                                                                  |
| ------------------------------ | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `.writing/assignment.md`       | the task, verbatim, and the `Monitor`'s restatement        | the `Monitor`, before the first process and for each follow-up message                      |
| `.writing/goals.md`            | the hierarchical goal network                              | the `Planning` process                                                                      |
| `.writing/draft.md`            | the current draft, empty unless the task supplies one      | the `Translating` process, and the `Reviewing` process for local revisions within its scope |
| `.writing/trace/process.jsonl` | the process history, one JSON object per line, append-only | the `Monitor`                                                                               |

Before the first process, write `.writing/assignment.md` in this form, copying the three task sections from the prompt exactly:

```markdown
# Assignment

## Assignment (verbatim)

## Supplied context (verbatim)

## Requested output constraints (verbatim)

## Restatement

- Topic:
- Audience:
- Exigency:
- Writer's goals:
- Genre:
- Output language: the language the assignment requests, or, when it requests none, the language of the assignment's instructions
- Length:
- Format:
- Assumptions:
```

## Perform the selected process

Perform every selected process in your own context instead of delegating it. Do not call `spawn_agent`, do not run `codex` in the shell, and do not write a script that starts agents.

The first time a process is selected, read its role skill at `<project root>/.agents/skills/<role>/SKILL.md`, where `<role>` is `planning`, `translating`, or `reviewing`, and say the role skill's acknowledgment line in an assistant message. When that file does not exist, read `<role>/SKILL.md` in the skills directory that contains this skill. Each time the process runs:

1. Write the brief below in an assistant message.
2. Perform the role as its role skill and the brief describe, writing only the files that the process writes.
3. Write the role's report in an assistant message, in the role skill's report format without the acknowledgment line.

### Brief

Fill every field of this template:

```text
Process: <Role>
Project root: <absolute path of the project root>
Assignment: verbatim in <project root>/.writing/assignment.md. Read all of it.
Output language: <the restatement's output language>
Length and format: <the restatement's length and format>
Scope: <the goal IDs, sections, or passage the agent may change>
Active goals: <each active goal's ID, parent ID, and statement>
Goal-setting: <requested or not requested>
Request: <the work to do: the plan to follow, the findings to address, or the accepted replacement to apply>
```

Write `<Role>` as `Planning`, `Translating`, or `Reviewing`. Request goal-setting in every `Planning` brief.

## Role reports

Each role's report has fixed fields. Read them as follows:

| Report      | Field           | Use                                                                                      |
| ----------- | --------------- | ---------------------------------------------------------------------------------------- |
| `Planning`  | `Goal changes`  | log one goal event per line                                                              |
| `Planning`  | `Plan`          | pass it to the next `Translating` brief's Request                                        |
| every role  | `Findings`      | select the next process                                                                  |
| `Reviewing` | `Verdict`       | apply the stop rule                                                                      |
| `Reviewing` | `Goal verdicts` | select `Planning` for `develop`; decide each `regenerate` in the post-`Reviewing` ledger |

Never copy an acknowledgment line into `.writing/draft.md` or the final response.

## Goals

The `Planning` process keeps `.writing/goals.md` as a hierarchy of goals with stable IDs, in the notation its role skill defines. Entries can be created, developed, or replaced; replacing an existing entry is goal regeneration.

- A `Reviewing` report proposes a replacement as a `regenerate` goal verdict.
- The `Monitor` accepts or rejects each proposal in the post-`Reviewing` ledger.
- After accepting one, the `Monitor` selects `Planning` and names the replacement in the brief's Request. The `Planning` report lists it as a `replaced` line.

## Trace

Append events to `.writing/trace/process.jsonl` with one shell command per step, the same command for every kind of event. The command replaces `@NOW@` with the current time:

```sh
sed "s/@NOW@/$(date -Is)/" >> .writing/trace/process.jsonl <<'EOF'
{"timestamp":"@NOW@","event_type":"process_switch","responsible_agent":"monitor","process":"translating","from_process":"planning","to_process":"translating","decision":"Draft the opening section, which has no draft text yet.","evidence":[".writing/draft.md has no opening section"],"open_uncertainty":[]}
EOF
```

Each event is one JSON object on one line. A process switch has these fields:

- `timestamp`: `"@NOW@"`
- `event_type`: `process_switch`
- `responsible_agent`: `monitor`
- `process`: the `to_process` value, or `reviewing` when the run stops
- `from_process`: the previous switch's `to_process`, or `null` for the first switch
- `to_process`: `planning`, `translating`, or `reviewing`, or `null` when the run stops
- `decision`: the decision and its reason in plain language
- `evidence` and `open_uncertainty`: arrays of strings, `[]` when empty

Append a process switch before every role step, including the last one. When the run stops, append one last switch with `from_process` `reviewing` and `to_process` `null`.

### Goal events

After a `Planning` report, append one goal event per `Goal changes` line in the same command as the next process switch. A goal event has the fields of a process switch except `from_process` and `to_process`, with `process` `planning`, plus `goal_id` and `parent_goal_id`:

| Report line                       | `event_type`       | `responsible_agent` | `goal_id` | `parent_goal_id` |
| --------------------------------- | ------------------ | ------------------- | --------- | ---------------- |
| `created G3 (parent G1)`          | `goal_created`     | `planner`           | `G3`      | `G1`             |
| `developed G2 (parent G0)`        | `goal_developed`   | `planner`           | `G2`      | `G0`             |
| `replaced G2 with G7 (parent G0)` | `goal_regenerated` | `monitor`           | `G7`      | `G0`             |

Use `null` as `parent_goal_id` for a top-level goal.

### Post-`Reviewing` ledger

The decision of the first process switch after each `Reviewing` report begins with the ledger: `regeneration proposals: G2 accepted (<reason>); G4 rejected (<reason>)`, with the actual goal IDs and reasons, or `regeneration proposals: none` when the report proposed no replacement.

## Finish

Before the final response:

1. Append the last process switch described in Trace.
2. Check that every goal in `.writing/goals.md` has a goal event. This command prints each goal ID that has none:

   ```sh
   for g in $(grep -oE '\[G[0-9]+\]' .writing/goals.md | tr -d '[]' | sort -u); do grep -qE "\"goal_id\": *\"$g\"" .writing/trace/process.jsonl || echo "$g"; done
   ```

   Append a `goal_created` event for each printed ID.

3. Read `.writing/draft.md` and return exactly its contents as the final response, with no preamble, summary, acknowledgment line, or code fence.

## Follow-up messages

When a later message changes the task, append it verbatim to `.writing/assignment.md` under `## Change request (verbatim)`, update the restatement, and continue from Select the next process with a new pass count.

## References

- [`references/trace-jsonl-schema.md`](references/trace-jsonl-schema.md) describes the trace fields for readers of the trace.
- [`references/goals-format.md`](references/goals-format.md) describes the goal notation for readers of `.writing/goals.md`.
