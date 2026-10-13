---
name: cognitive-writing-loop-only
description: "Experiment variant of the agentic-cog-writer skill without the goal network, with a fixed Planning, Translating, then Reviewing order, and with each process performed in the Monitor's own context. Use it only when a controlled comparison requests this variant."
---

> [!NOTE]
> After reading this `SKILL.md`, say: `I read cognitive-writing-loop-only.`

# Loop-only cognitive writing

You are the `Monitor`. Say the acknowledgment line above in an assistant message of its own immediately after reading this skill; the line never appears in `.writing/draft.md` or in the final response. The project root is the current working directory, and `<skill dir>` below is the directory that contains this `SKILL.md`.

The `Monitor` selects one writing process at a time from the task and the shared writing state, has its role perform it, and repeats until the stop rule holds. Where the assignment is silent, apply genre-appropriate defaults and record them under Assumptions in the restatement.

## Select the next process

Follow the fixed `Planning`, `Translating`, then `Reviewing` order: run the three processes in that order and repeat this cycle until the stop rule holds. Never change this order, even when a report recommends another process; a change request starts a new cycle with `Planning`. Before each step, read the writing state and the latest role report, and use them to scope the step: `Planning` addresses the open findings of the last `Reviewing` report, `Translating` writes what the plan or those findings require, and `Reviewing` covers the whole draft.

## Stop

The stop rule holds when any of these is true:

- The latest `Reviewing` report's Open findings list is `- none`, and no change request arrived after it. Decide from the list itself, not from the report's Verdict line.
- Four passes have ended. Each `Reviewing` report ends one pass.
- Twelve role steps have run.

Count passes and role steps from the start of the run or from the latest change request. When the stop rule holds, follow Finish and return the current draft.

## State

The writing state lives in the project's `.writing/` directory. Do not create or modify `.writing/goals.md`, whether it exists or not. Do not consult or construct a hierarchical goal network.

| File                           | Content                                                    | Written by                                                                                  |
| ------------------------------ | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `.writing/assignment.md`       | the task, verbatim, and the `Monitor`'s restatement        | the `Monitor`, at setup and for each follow-up message                                      |
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

## Perform the selected process

Perform every selected process in your own context instead of delegating it. Do not call `multi_agent_v1__spawn_agent`, do not run `codex` in the shell, and do not write a script that starts agents.

The first time a process is selected, read its role skill at `<project root>/.agents/skills/<role>/SKILL.md`, where `<role>` is `planning`, `translating`, or `reviewing`, and say the role skill's acknowledgment line in an assistant message of its own. Each time the process runs:

1. Append the brief below to `.writing/reports.md` under a `## <Role> brief` heading.
2. Perform the role as its role skill and the brief describe, writing only the files that the process writes.
3. Append the role's report, in the role skill's report format but without the acknowledgment line, to `.writing/reports.md` under a `## <Role> report` heading.

The `Monitor` alone writes `.writing/reports.md`. Write briefs and reports only to that file, never as assistant messages, and never put an acknowledgment line in it.

### Brief

Fill every field of this template:

```text
Process: <Role>
Project root: <absolute path of the project root>
Assignment: verbatim in .writing/assignment.md. Read all of it.
Output language: <the restatement's output language>. Write all prose in it.
Length and format: <the restatement's length and format>
Scope: <the sections or passage this step may change>
Goal-setting: not requested. Do not create or modify .writing/goals.md.
Request: <the work to do: the plan to follow or the findings to address>
```

Write `<Role>` as `Planning`, `Translating`, or `Reviewing`. Never request goal-setting.

## Role reports

Each role's report has fixed fields. Read them as follows:

| Report                    | Field           | Use                                                                                      |
| ------------------------- | --------------- | ---------------------------------------------------------------------------------------- |
| `Planning`                | `Plan`          | pass it to the next `Translating` brief's Request                                        |
| `Planning`, `Translating` | `Findings`      | scope the next step in the cycle                                                                  |
| `Reviewing`               | `Open findings` | apply the stop rule and scope the next step in the cycle                                          |

Never copy an acknowledgment line into `.writing/draft.md`, a brief, or the final response.

## Trace

Log every event with this one command, and with no other command. Write one `key: value` line per field, write list items as `- item` lines under their key, and separate events with a `---` line:

```sh
python3 <skill dir>/scripts/writing_state.py log --no-goals <<'EOF'
event_type: process_switch
to_process: translating
decision: Draft the opening section, which has no draft text yet.
evidence:
- .writing/draft.md has no opening section
EOF
```

The script adds the timestamp, the responsible agent, `process`, and `from_process`, writes valid JSON, and appends nothing when an event is invalid. When it prints an error, fix the input and run the command again. A process switch has these keys:

- `event_type`: `process_switch`
- `to_process`: `planning`, `translating`, or `reviewing`, or `null` when the run stops
- `decision`: the decision and its reason in plain language
- `evidence` and `open_uncertainty`: optional lists of `- item` lines

Log a process switch before every role step, including the last one. When the run stops, log one last switch with `to_process: null`.

## Finish

Before the final response:

1. Run `python3 <skill dir>/scripts/writing_state.py check`. The command verifies that the trace parses and prints the logged process path.
2. Log the last process switch described in Trace.
3. Read `.writing/draft.md` and return exactly its contents as the final response, with no preamble, summary, acknowledgment line, or code fence.

## Follow-up messages

When a later message changes the task, append it verbatim to `.writing/assignment.md` under `## Change request (verbatim)` and update the restatement. The change request voids the latest `Reviewing` verdict and restarts the pass and step counts, so the next process is `Planning`.

## References

- [`references/trace-jsonl-schema.md`](references/trace-jsonl-schema.md) describes the trace fields for readers of the trace.
