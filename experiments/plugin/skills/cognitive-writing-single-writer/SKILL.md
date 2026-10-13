---
name: cognitive-writing-single-writer
description: "Experiment variant of the agentic-cog-writer skill that performs each selected process in the Monitor's own context and writes exactly one paragraph in each Translating step. Use it only when a controlled comparison requests this variant."
---

> [!NOTE]
> After reading this `SKILL.md`, say: `I read cognitive-writing-single-writer.`

# Single-writer cognitive writing

You are the `Monitor`. Say the acknowledgment line above immediately after reading this skill, in the same response as your next tool call; the line never appears in `.writing/draft.md` or in the final response. The project root is the current working directory, and `<skill dir>` below is the directory that contains this `SKILL.md`.

The `Monitor` selects one writing process at a time from the task and the shared writing state, has its role perform it, and repeats until the stop rule holds. Where the assignment is silent, apply genre-appropriate defaults and record them under Assumptions in the restatement.

## Select the next process

Before each step, read `.writing/assignment.md`, `.writing/goals.md`, `.writing/draft.md`, the latest trace entries, and the latest role report. Select exactly one process, using the first row that matches:

| State                                                                                                                                          | Next process                                                                                             |
| ---------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| The stop rule holds                                                                                                                            | Stop                                                                                                     |
| `.writing/goals.md` has no goals, or a change request arrived after the latest role report                                                     | `Planning`                                                                                               |
| The latest report is from `Planning`                                                                                                           | `Translating`, scoped to the goals and sections that report created, developed, replaced, or reorganized |
| The latest report names a structural or goal-level problem: a missing required section, a wrong organization, or a goal that is unmet or wrong | `Planning`                                                                                               |
| An active goal has no draft text yet, or the latest `Reviewing` report names a problem localized to a passage                                  | `Translating`, scoped to those goals or that passage                                                     |
| Any other state                                                                                                                                | `Reviewing` of the whole draft                                                                           |

A `develop` goal verdict and an accepted `regenerate` verdict are goal-level problems; a rejected `regenerate` verdict is not a problem. A passage problem that a `Translating` report names goes to the next `Reviewing` step, so every return to `Translating` passes through a `Reviewing` report. `Planning` runs twice in a row only when its report leaves `.writing/goals.md` without goals or a change request arrives after it; otherwise a `Planning` report leads to `Translating`. A role's recommended next process is evidence for this choice; the `Monitor` alone selects the next process.

## Stop

The stop rule holds when any of these is true:

- The latest `Reviewing` report's Open findings list is `- none`, the `Monitor` accepted none of its `regenerate` verdicts, and no change request arrived after it. Decide from the list itself, not from the report's Verdict line.
- Four passes have ended. Each `Reviewing` report ends one pass.
- Twelve role steps have run.

Count passes and role steps from the start of the run or from the latest change request. When the stop rule holds, follow Finish and return the current draft.

## State

The writing state lives in the project's `.writing/` directory.

| File                           | Content                                                    | Written by                                                                                  |
| ------------------------------ | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `.writing/assignment.md`       | the task, verbatim, and the `Monitor`'s restatement        | the `Monitor`, at setup and for each follow-up message                                      |
| `.writing/goals.md`            | the hierarchical goal network                              | the `Planning` process                                                                      |
| `.writing/draft.md`            | the current draft                                          | the `Translating` process, and the `Reviewing` process for local revisions within its scope |
| `.writing/trace/process.jsonl` | the process history, one JSON object per line, append-only | the `Monitor`, through `<skill dir>/scripts/writing_state.py`                               |
| `.writing/reports.md` | the brief and the report of each role step, one `## Step N: Process` section per role switch | the `Monitor`, through `<skill dir>/scripts/writing_state.py step` |

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

The first time a process is selected, read its role skill at `<project root>/.agents/skills/<role>/SKILL.md`, where `<role>` is `planning`, `translating`, or `reviewing`, and say the role skill's acknowledgment line immediately after reading it, in the same response as your next tool call. The role skill's instructions about its acknowledgment line and its final message address delegated role agents; here, the report goes to `.writing/reports.md`. Each time a process runs:

1. Log its switch and open its section in `.writing/reports.md` with this command, which takes the keys of a process switch except `event_type` and `to_process`:

   ```sh
   python3 <skill dir>/scripts/writing_state.py step <role> <<'EOF'
   decision: Draft the opening section, which has no draft text yet.
   evidence:
   - .writing/draft.md has no opening section
   EOF
   ```

2. Append the brief below to `.writing/reports.md` under that section.
3. Perform the role as its role skill and the brief describe, writing only the files that the process writes.
4. Append the role's report, in the role skill's report format but without the acknowledgment line, under the same section.

The `Monitor` alone writes `.writing/reports.md`. Write briefs and reports only to that file, never as assistant messages, and never put an acknowledgment line in it. Once `.writing/reports.md` exists, the `log` command refuses role switches, and Finish checks that every section has its switch.

### Brief

Fill every field of this template:

```text
Process: <Role>
Project root: <absolute path of the project root>
Assignment: verbatim in .writing/assignment.md. Read all of it.
Output language: <the restatement's output language>. Write all prose in it.
Length and format: <the restatement's length and format>
Scope: <the goal IDs, sections, or passage this step may change>
Active goals: <the IDs of the active goals; their statements are in .writing/goals.md>
Goal-setting: <requested or not requested>
Rejected proposals: <for Reviewing, each regeneration proposal rejected so far, with its reason; otherwise none>
Request: <the work to do: the plan to follow, the findings to address, or the accepted replacement to apply>
```

Write `<Role>` as `Planning`, `Translating`, or `Reviewing`. Request goal-setting in every `Planning` brief.

## Paragraph unit

Each `Translating` step writes exactly one paragraph: one locally coherent block that serves one goal, with no blank line inside it. Every write to `.writing/draft.md` goes through this command; editing `.writing/draft.md` with `apply_patch`, a shell redirect, or any other tool is forbidden. Use `--append` for a new paragraph at the end, `--insert-before N` for a new paragraph before paragraph N, or `--replace N` to rewrite paragraph N, counting paragraphs from 1:

```sh
python3 <skill dir>/scripts/writing_state.py paragraph --append <<'EOF'
<the paragraph>
EOF
```

The command refuses a second paragraph in the same `Translating` step, and a `Reviewing` step may use only `--replace` for its local revisions. After each paragraph, select the next process as usual; when the scope is not fully drafted yet, the next step is another `Translating` step on the same scope. For the twelve-step cap in the stop rule, an unbroken run of `Translating` steps counts as one role step; each of them still gets its own process switch.

## Role reports

Each role's report has fixed fields. Read them as follows:

| Report                    | Field           | Use                                                                                      |
| ------------------------- | --------------- | ---------------------------------------------------------------------------------------- |
| `Planning`                | `Goal changes`  | log one goal event per line                                                              |
| `Planning`                | `Plan`          | pass it to the next `Translating` brief's Request                                        |
| `Planning`, `Translating` | `Findings`      | select the next process                                                                  |
| `Reviewing`               | `Open findings` | apply the stop rule and select the next process                                          |
| `Reviewing`               | `Goal verdicts` | select `Planning` for `develop`; decide each `regenerate` in the post-`Reviewing` ledger |

Never copy an acknowledgment line into `.writing/draft.md`, a brief, or the final response.

## Goals

The `Planning` process keeps `.writing/goals.md` as a hierarchy of goals with stable IDs, in the notation its role skill defines: `G1` for a top-level goal, and the parent's ID plus a number for a child, such as `G1.2`. Entries can be created, developed, or replaced; replacing an existing entry is goal regeneration.

- A `Reviewing` report proposes a replacement as a `regenerate` goal verdict.
- The `Monitor` accepts or rejects each proposal in the post-`Reviewing` ledger, and lists every rejected proposal with its reason in later `Reviewing` briefs.
- After accepting one, the `Monitor` selects `Planning` and names the replacement in the brief's Request. The `Planning` report lists it as a `replaced` line.

## Trace

Log each role switch with the `step` command that Perform the selected process shows, and every other event, such as goal events and the last switch, with this command and no other. Write one `key: value` line per field, write list items as `- item` lines under their key, and separate events with a `---` line:

```sh
python3 <skill dir>/scripts/writing_state.py log <<'EOF'
event_type: goal_created
goal_id: G1.3
parent_goal_id: G1
decision: Planning created G1.3 for the closing section.
EOF
```

The script adds the timestamp, the responsible agent, `process`, and `from_process`, writes valid JSON, and appends nothing when an event is invalid. When it prints an error, fix the input and run the command again. A process switch has these keys:

- `event_type`: `process_switch`
- `to_process`: `planning`, `translating`, or `reviewing`, or `null` when the run stops
- `decision`: the decision and its reason in plain language
- `evidence` and `open_uncertainty`: optional lists of `- item` lines

Log a process switch before every role step, including the last one. When the run stops, log one last switch with `to_process: null`.

### Goal events

After writing the `Planning` report, log one goal event per `Goal changes` line before selecting the next process. A goal event has `event_type`, `goal_id`, `parent_goal_id`, `decision`, and optional `evidence` and `open_uncertainty` keys:

| Report line                           | `event_type`       | `goal_id` | `parent_goal_id` |
| ------------------------------------- | ------------------ | --------- | ---------------- |
| `created G1.3 (parent G1)`            | `goal_created`     | `G1.3`    | `G1`             |
| `developed G1.2 (parent G1)`          | `goal_developed`   | `G1.2`    | `G1`             |
| `replaced G1.2 with G1.4 (parent G1)` | `goal_regenerated` | `G1.4`    | `G1`             |

Use `null` as `parent_goal_id` for a top-level goal. The script credits `goal_created` and `goal_developed` to the `planner` and `goal_regenerated` to the `monitor`.

### Post-`Reviewing` ledger

The first process switch after each `Reviewing` report carries the ledger in a `regeneration_proposals` key: `none` when the report proposed no replacement, or one `<goal ID> accepted (<reason>)` or `<goal ID> rejected (<reason>)` entry per proposal, separated by `; `. The script refuses that switch without the key and writes the ledger at the start of its decision as `regeneration proposals: …`. When the `Reviewing` step failed and returned no report, the ledger is `none`.

## Finish

Before the final response:

1. Run `python3 <skill dir>/scripts/writing_state.py check --reports`. The command verifies that the trace parses and that `.writing/reports.md` has one step section per role switch, prints the logged process path, and prints each goal in `.writing/goals.md` that has no goal event.
2. For each goal without an event, log a `goal_created` event with `responsible_agent: monitor`.
3. Log the last process switch described in Trace.
4. Read `.writing/draft.md` and return exactly its contents as the final response, copied byte for byte with every leading space and blank line kept, and with no preamble, summary, acknowledgment line, or code fence.

## Follow-up messages

When a later message changes the task, append it verbatim to `.writing/assignment.md` under `## Change request (verbatim)` and update the restatement. The change request voids the latest `Reviewing` verdict and restarts the pass and step counts, so the next process is `Planning`.

## References

- [`references/trace-jsonl-schema.md`](references/trace-jsonl-schema.md) describes the trace fields for readers of the trace.
- [`references/goals-format.md`](references/goals-format.md) describes the goal notation for readers of `.writing/goals.md`.
