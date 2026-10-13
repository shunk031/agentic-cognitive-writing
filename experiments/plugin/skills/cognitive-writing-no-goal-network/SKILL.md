---
name: cognitive-writing-no-goal-network
description: "Experiment-comparison variant of the agentic-cog-writer skill for testing writing without a hierarchical goal network. For internal comparison use only, not the recommended default. Use when a controlled no-goal-network comparison is explicitly requested."
---

> [!NOTE]
> After reading this `SKILL.md`, say: `I read cognitive-writing-no-goal-network.`

# Cognitive writing without a goal network

You are the `Monitor`. Say the acknowledgment line above in your first assistant message, before any tool call; the line never appears in `.writing/draft.md` or in the final response. The project root is the current working directory.

The `Monitor` selects one writing process at a time from the task and the shared writing state, has its role perform it, and repeats until the stop rule holds. Where the assignment is silent, apply genre-appropriate defaults and record them under Assumptions in the restatement.

## Select the next process

Before each step, read `.writing/assignment.md`, `.writing/draft.md`, the latest trace entries, and the latest role report. Select exactly one process, using the first row that matches:

| State                                                                                                                                | Next process                                  |
| ------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------- |
| The stop rule holds                                                                                                                  | Stop                                          |
| No `Planning` report exists yet, or the latest report names a structural problem: a missing required section or a wrong organization | `Planning`                                    |
| Part of the latest plan has no draft text yet, or the latest report names a problem localized to a passage                           | `Translating`, scoped to that part or passage |
| The draft changed after the last `Reviewing` report                                                                                  | `Reviewing` of the whole draft                |

A role's recommended next process is evidence for this choice; the `Monitor` alone selects the next process. Do not consult or construct a hierarchical goal network.

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

## Delegate the selected process

Delegate every selected process to its own role agent: `Planning` to a `Planner`, `Translating` to a `Translator`, and `Reviewing` to a `Reviewer`. Never perform a role yourself and never write `.writing/goals.md` or `.writing/draft.md`. When a role agent fails, delegate the same process again.

In Codex, for each step:

1. Call the `spawn_agent` tool with `fork_context: false` and the brief below as the message. Leave `model` and the reasoning settings unset.
2. Call `wait_agent` on that agent with a long timeout, such as 1,200,000 ms, and call it again while it times out.
3. Read the report, which is the agent's final message in the completed status.
4. Call `close_agent` on that agent.

Run one role agent at a time. Do not run `codex` in the shell, and do not write a script that starts agents.

In Claude Code, delegate to the bundled `planner`, `translator`, or `reviewer` agent with the same brief.

### Brief

Fill every field of this template:

```text
$<role> You are the <Role> role agent for a writing project. You are not the Monitor.
Role skill: <project root>/.agents/skills/<role>/SKILL.md. Read it in full first and follow it.
Do not open the Monitor skill or another role's skill, do not spawn agents, do not run codex, and do not write .writing/trace/process.jsonl.
Project root: <absolute path of the project root>
Assignment: verbatim in <project root>/.writing/assignment.md. Read all of it.
Output language: <the restatement's output language>
Length and format: <the restatement's length and format>
Scope: <the sections or passage the agent may change>
Goal-setting: not requested. Do not create or modify .writing/goals.md.
Request: <the work to do: the plan to follow or the findings to address>
Your final message is your report, in the role skill's report format, beginning with the role skill's acknowledgment line.
```

Write `<role>` in lowercase and `<Role>` capitalized: `planning` and `Planning`, `translating` and `Translating`, or `reviewing` and `Reviewing`. When `.agents/skills/<role>/SKILL.md` does not exist under the project root, give the absolute path of `<role>/SKILL.md` in the skills directory that contains this skill. Never request goal-setting.

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
