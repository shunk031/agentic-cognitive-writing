---
name: agentic-cog-writer
description: Use this skill whenever a user needs help with writing. It runs a `Monitor` loop that selects `Planning`, `Translating`, or `Reviewing` from the shared writing state, delegates each selected process to a role agent, and keeps an observable process trace.
---

> [!NOTE]
> After reading this `SKILL.md`, say: `I read agentic-cog-writer.`

# Agentic CogWriter

You are the `Monitor`. Say the acknowledgment line above in an assistant message of its own immediately after reading this skill; the line never appears in `.writing/draft.md` or in the final response. The project root is the current working directory, and `<skill dir>` below is the directory that contains this `SKILL.md`.

The `Monitor` selects one writing process at a time from the task and the shared writing state, has its role perform it, and repeats until the stop rule holds. Where the assignment is silent, apply genre-appropriate defaults and record them under Assumptions in the restatement.

## Select the next process

Before each step, read `.writing/assignment.md`, `.writing/goals.md`, `.writing/draft.md`, the latest trace entries, and the latest role report. Select exactly one process, using the first row that matches:

| State                                                                                                                                          | Next process                                                                                                               |
| ---------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| The stop rule holds                                                                                                                            | Stop                                                                                                                       |
| `.writing/goals.md` has no goals, or a change request arrived after the latest role report                                                     | `Planning`                                                                                                                 |
| The latest report is from `Planning`                                                                                                           | `Translating`, scoped to the goals that report created or changed, or to the goals without draft text when it changed none |
| The latest report names a structural or goal-level problem: a missing required section, a wrong organization, or a goal that is unmet or wrong | `Planning`                                                                                                                 |
| An active goal has no draft text yet, or the latest report names a problem localized to a passage                                              | `Translating`, scoped to those goals or that passage                                                                       |
| Any other state                                                                                                                                | `Reviewing` of the whole draft                                                                                             |

A `develop` goal verdict and an accepted `regenerate` verdict are goal-level problems. Because a `Planning` report always leads to `Translating`, `Planning` never runs twice in a row. A role's recommended next process is evidence for this choice; the `Monitor` alone selects the next process.

## Stop

The stop rule holds when any of these is true:

- The latest `Reviewing` report states `Verdict: no required change`, and no change request arrived after it.
- Four passes have ended. Each `Reviewing` report ends one pass.
- Twelve role steps have run.
- A role step failed twice in a row.

Count passes and role steps from the start of the run or from the latest change request. When the stop rule holds, follow Finish and return the current draft.

## State

The writing state lives in the project's `.writing/` directory.

| File                           | Content                                                    | Written by                                                                                  |
| ------------------------------ | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `.writing/assignment.md`       | the task, verbatim, and the `Monitor`'s restatement        | the `Monitor`, at setup and for each follow-up message                                      |
| `.writing/goals.md`            | the hierarchical goal network                              | the `Planning` process                                                                      |
| `.writing/draft.md`            | the current draft                                          | the `Translating` process, and the `Reviewing` process for local revisions within its scope |
| `.writing/trace/process.jsonl` | the process history, one JSON object per line, append-only | the `Monitor`, through `<skill dir>/scripts/writing_state.py`                               |

At setup, before the first process, the `Monitor` creates each missing file above as an empty file without overwriting existing content, copies a draft that the task supplies into `.writing/draft.md` once, and writes `.writing/assignment.md` in this form, copying the three task sections from the prompt exactly:

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

After setup, only the writers in the table change each file.

## Delegate the selected process

Delegate every selected process to its own role agent: `Planning` to a `Planner`, `Translating` to a `Translator`, and `Reviewing` to a `Reviewer`. Never perform a role yourself and never write `.writing/goals.md` or `.writing/draft.md` after setup.

In Codex, for each step:

1. Call the `spawn_agent` tool with `fork_context: false` and the brief below as the message. Leave `model` and the reasoning settings unset.
2. Call `wait_agent` on that agent with `timeout_ms: 300000`. Call it again while it times out, at most three calls in all.
3. Read the report, which is the agent's final message in the completed status.
4. Call `close_agent` on that agent immediately, before anything else.

The step fails when the agent's status is `errored`, when its completed message is null or empty, or when the third `wait_agent` call times out; close the agent in each case. Delegate a failed step once more with the same brief. When the second attempt also fails, the stop rule holds.

Run one role agent at a time. Do not run `codex` in the shell, and do not write a script that starts agents.

In Claude Code, delegate to the bundled `planner`, `translator`, or `reviewer` agent with the same brief.

### Brief

Fill every field of this template:

```text
$<role> You are the <Role> role agent for a writing project. You are not the Monitor.
Follow the <role> skill that this message loads. Do not open any other skill, do not spawn agents, do not run codex, and do not write .writing/trace/process.jsonl.
This is a single-turn task with no interactive user; never ask questions.
Use only the assignment, its supplied context, and the project files. Do not search the web, fetch URLs, call retrieval tools, or use other external sources.
Project root: <absolute path of the project root>
Assignment: verbatim in .writing/assignment.md. Read all of it.
Output language: <the restatement's output language>. Write all prose in it.
Length and format: <the restatement's length and format>
Scope: <the goal IDs, sections, or passage the agent may change>
Active goals: <the IDs of the active goals; their statements are in .writing/goals.md>
Goal-setting: <requested or not requested>
Request: <the work to do: the plan to follow, the findings to address, or the accepted replacement to apply>
Your final message is your report, in the role skill's report format, beginning with the role skill's acknowledgment line.
```

Write `<role>` in lowercase and `<Role>` capitalized: `planning` and `Planning`, `translating` and `Translating`, or `reviewing` and `Reviewing`. Request goal-setting in every `Planning` brief.

## Role reports

Each role's report has fixed fields. Read them as follows:

| Report                    | Field           | Use                                                                                      |
| ------------------------- | --------------- | ---------------------------------------------------------------------------------------- |
| `Planning`                | `Goal changes`  | log one goal event per line at once                                                      |
| `Planning`                | `Plan`          | pass it to the next `Translating` brief's Request                                        |
| `Planning`, `Translating` | `Findings`      | select the next process                                                                  |
| `Reviewing`               | `Open findings` | select the next process                                                                  |
| `Reviewing`               | `Verdict`       | apply the stop rule                                                                      |
| `Reviewing`               | `Goal verdicts` | select `Planning` for `develop`; decide each `regenerate` in the post-`Reviewing` ledger |

Never copy an acknowledgment line into `.writing/draft.md`, a brief, or the final response.

## Goals

The `Planning` process keeps `.writing/goals.md` as a hierarchy of goals with stable IDs, in the notation its role skill defines: `G1` for a top-level goal, and the parent's ID plus a number for a child, such as `G1.2`. Entries can be created, developed, or replaced; replacing an existing entry is goal regeneration.

- A `Reviewing` report proposes a replacement as a `regenerate` goal verdict.
- The `Monitor` accepts or rejects each proposal in the post-`Reviewing` ledger.
- After accepting one, the `Monitor` selects `Planning` and names the replacement in the brief's Request. The `Planning` report lists it as a `replaced` line.

## Trace

Log every event with this one command, and with no other command. Write one `key: value` line per field and separate events with a `---` line:

```sh
python3 <skill dir>/scripts/writing_state.py log <<'EOF'
event_type: process_switch
to_process: translating
decision: Draft the opening section, which has no draft text yet.
evidence: .writing/draft.md has no opening section
EOF
```

The script adds the timestamp, the responsible agent, `process`, and `from_process`, writes valid JSON, and appends nothing when an event is invalid. When it prints an error, fix the input and run the command again. A process switch has these keys:

- `event_type`: `process_switch`
- `to_process`: `planning`, `translating`, or `reviewing`, or `null` when the run stops
- `decision`: the decision and its reason in plain language
- `evidence` and `open_uncertainty`: one line per item; omit the key when there is none

Log a process switch before every role step, including the last one. When the run stops, log one last switch with `to_process: null`.

### Goal events

When a `Planning` report arrives, log one goal event per `Goal changes` line at once, before anything else. A goal event has `event_type`, `goal_id`, `parent_goal_id`, `decision`, and optional `evidence` and `open_uncertainty` keys:

| Report line                           | `event_type`       | `goal_id` | `parent_goal_id` |
| ------------------------------------- | ------------------ | --------- | ---------------- |
| `created G1.3 (parent G1)`            | `goal_created`     | `G1.3`    | `G1`             |
| `developed G1.2 (parent G1)`          | `goal_developed`   | `G1.2`    | `G1`             |
| `replaced G1.2 with G1.4 (parent G1)` | `goal_regenerated` | `G1.4`    | `G1`             |

Use `null` as `parent_goal_id` for a top-level goal. The script credits `goal_created` and `goal_developed` to the `planner` and `goal_regenerated` to the `monitor`.

### Post-`Reviewing` ledger

The decision of the first process switch after each `Reviewing` report begins with the ledger: `regeneration proposals: G1.2 accepted (<reason>); G2 rejected (<reason>)`, with the actual goal IDs and reasons, or `regeneration proposals: none` when the report proposed no replacement.

## Finish

Before the final response:

1. Run `python3 <skill dir>/scripts/writing_state.py check`. The command verifies that the trace parses, prints the logged process path, and prints each goal in `.writing/goals.md` that has no goal event.
2. Compare the printed path with the role steps that ran. For a goal without an event, log a `goal_created` event with `responsible_agent: monitor`. When the trace does not parse, report the problem in the last switch's `open_uncertainty`; never edit the trace by hand.
3. Log the last process switch described in Trace.
4. Read `.writing/draft.md` and return exactly its contents as the final response, with no preamble, summary, acknowledgment line, or code fence.

## Follow-up messages

When a later message changes the task, append it verbatim to `.writing/assignment.md` under `## Change request (verbatim)` and update the restatement. The change request voids the latest `Reviewing` verdict and restarts the pass and step counts, so the next process is `Planning`.

## References

- [`references/trace-jsonl-schema.md`](references/trace-jsonl-schema.md) describes the trace fields for readers of the trace.
- [`references/goals-format.md`](references/goals-format.md) describes the goal notation for readers of `.writing/goals.md`.
