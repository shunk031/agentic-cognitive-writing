---
name: cognitive-writing-loop-only
description: "Use this skill for exploratory loop-only comparisons. It keeps the Agentic CogWriter Monitor loop, shared writing state, and process-switch trace, but removes the goal network, fixes the Planning, Translating, then Reviewing order, and has the host agent perform each process in its own context instead of delegating."
---

> [!NOTE]
> After reading this `SKILL.md`, say: `I read cognitive-writing-loop-only.`

# Loop-only cognitive writing

You are the `Monitor`. Say the acknowledgment line above in your first assistant message, before any tool call; the line never appears in `.writing/draft.md` or in the final response. The project root is the current working directory.

The `Monitor` selects one writing process at a time from the task and the shared writing state, has its role perform it, and repeats until the stop rule holds. Where the assignment is silent, apply genre-appropriate defaults and record them under Assumptions in the restatement.

## Select the next process

Run `Planning`, `Translating`, then `Reviewing`, and repeat this cycle until the stop rule holds. Never change this order, even when a report recommends another process. Before each step, read the writing state and the latest role report, and use them to scope the step: `Planning` addresses the findings of the last `Reviewing` report, `Translating` writes what the plan or those findings require, and `Reviewing` covers the whole draft.

## Stop

End the run only after a `Reviewing` report finds no remaining required change against the task requirements, which the report states as `Verdict: no required change`. Each `Reviewing` report ends one pass. After the fourth pass, stop even when required changes remain. Then follow Finish and return the current draft.

## State

The writing state lives in the project's `.writing/` directory. Create missing files without overwriting existing content. Do not create or modify `.writing/goals.md`, whether it exists or not.

| File                           | Content                                                    | Written by                                                                                  |
| ------------------------------ | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `.writing/assignment.md`       | the task, verbatim, and the `Monitor`'s restatement        | the `Monitor`, before the first process and for each follow-up message                      |
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
Scope: <the sections or passage the agent may change>
Goal-setting: not requested. Do not create or modify .writing/goals.md.
Request: <the work to do: the plan to follow or the findings to address>
```

Write `<Role>` as `Planning`, `Translating`, or `Reviewing`. Never request goal-setting.

## Role reports

Each role's report has fixed fields. Read them as follows:

| Report      | Field      | Use                                               |
| ----------- | ---------- | ------------------------------------------------- |
| `Planning`  | `Plan`     | pass it to the next `Translating` brief's Request |
| every role  | `Findings` | select the next process                           |
| `Reviewing` | `Verdict`  | apply the stop rule                               |

Never copy an acknowledgment line into `.writing/draft.md` or the final response.

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

## Finish

Before the final response:

1. Append the last process switch described in Trace.
2. Read `.writing/draft.md` and return exactly its contents as the final response, with no preamble, summary, acknowledgment line, or code fence.

## Follow-up messages

When a later message changes the task, append it verbatim to `.writing/assignment.md` under `## Change request (verbatim)`, update the restatement, and continue from Select the next process with a new pass count.
