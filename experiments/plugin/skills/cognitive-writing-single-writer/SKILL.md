---
name: cognitive-writing-single-writer
description: "Experimental A7 writing skill based on Flower and Hayes's single Writer. Use for controlled comparisons that require one main agent, a live hierarchical goal network, sentence-level recursion, and an append-only process trace."
---

# Cognitive writing single writer

Use this skill only for A7. Flower and Hayes's _A Cognitive Process Theory of Writing_[^1] models one Writer with Planning, Translating, and Reviewing under a Monitor. The paper says nothing about software agents. A7 operationalizes that model as one main agent that is both Writer and Monitor, with no subagents.

## One Writer and one Monitor

The main agent is the only Writer. Do not spawn subagents, role agents, delegation tools, or another writing process. The wrapper sets `require_delegation = false`.

The `Monitor` is the strategist. Choose the next process from the current goal network, the rhetorical problem, and the growing text. Do not impose a stage sequence. Use this default style: plan briefly at the top level, compose one sentence or a few sentences at a time, and plan locally when needed. A writer may instead explore for a time or move toward polished prose quickly when the active goals support that choice.

## Read and preserve the writing state

Work in the session's current directory. Create missing files without overwriting user content:

```text
.writing/
├── assignment.md
├── assumptions.md
├── goals.md
├── draft.md
├── memory/
└── trace/process.jsonl
```

Read `assignment.md`, `goals.md`, `draft.md`, relevant `memory/` files, and the latest trace entries before choosing a process. If the assignment leaves the audience, purpose, scope, genre, or constraints unclear, make a reasonable single-turn assumption and record it in `.writing/assumptions.md`. Do not ask a clarifying question.

Follow the repository writing contract for structure, links, claims, and plain English. Apply the `unslop` skill before finishing. Remove filler, AI-pattern phrasing, vague claims, and unnecessary headings without changing the task's meaning.

## Keep a working goal network

The paper's "Writing is a goal-directed process" and "Goals, Topic, and Text" sections describe goals created, developed, and revised during composing. The paper predicts that good and poor writers differ in the quantity and quality of middle-range goals that bridge intention and prose. A7 therefore asks the Writer to make those goals explicit. The prediction belongs to the paper, and the explicit file representation belongs to this experiment.

Treat `.writing/goals.md` as the current hierarchical network, not a ledger. Each line has a stable goal ID, parent ID, one-line statement, `kind` (`process` or `content`), and `status` (`active`, `resolved`, or `superseded`). Use indentation for parent and child relationships. Keep no history table, verdict list, or proposal list in the file. History lives in the trace.

When the Writer creates a goal, update the network and append `goal_created`. When the Writer makes an existing goal more specific, update it and append `goal_developed`. When an evaluated passage shows that the active goal is wrong or too abstract, regenerate it immediately: mark the old ID `superseded`, create a new active ID, use the old ID as `parent_goal_id`, and append `goal_regenerated`. There is no proposal-and-acceptance step.

## Compose recursively at sentence level

The paper's process model treats processes as optional and allows them to embed at any level. Figure 2 shows planning, translating, and reviewing embedded while the Writer works on one sentence. A7 operationalizes observable embedding by treating each sentence as the composing unit and fixing the smallest operational batch at a few sentences serving one local goal. That batch size is an experimental choice, not a rule imposed by the paper.

For each local passage, let the `Monitor` choose the next process, translate the passage, and use its text to choose what happens next. `generate` and `evaluate` may interrupt any process at any time. When a local goal resolves, pop back to its immediate parent. When an exploration burst yields useful material, return to the top-level goal and consolidate it into a more specific goal. When a trial passage shows that the active goal needs a new purpose or level of abstraction, use Write and Regenerate immediately. Do not pop or regenerate mechanically after every sentence.

## Mechanical incremental composition

The draft is built by appending to `.writing/draft.md`. Never assemble a full draft and write it in one operation. Never use a replacement write, `>`, or a whole-file rewrite. The only exception is a local revision of the most recent passage. Replace only that passage, append a `process_switch` whose `process` is `revise` in the same shell command, and then return to append-only writing. Never rewrite an earlier passage.

Each `Translating` step appends at most a few sentences, normally one to three, for one local goal. In the same shell command, append that passage first and then append its `process_switch` plus any goal events to `.writing/trace/process.jsonl`. Do not predeclare future passages or events. Do not write any trace event in a setup-only command before the first draft append. A quoted heredoc may hold the short passage and one JSON object per line. The shell command must use `>>` for the draft and trace. Keep evidence factual at append time, such as the existing draft quote, file path, or goal ID, never future-tense evidence.

Use one shell command with this order for every translating batch:

```sh
fragment=$(cat <<'EOF'
One sentence, or a few sentences for one local goal.
EOF
)
printf '%s\n' "$fragment" >> .writing/draft.md
stamp=$(date -Is)
printf '%s\n' "{\"timestamp\":\"$stamp\",\"event_type\":\"process_switch\",\"responsible_agent\":\"Monitor\",\"process\":\"translating\",\"decision\":\"Append the local passage.\",\"evidence\":[],\"open_uncertainty\":[],\"from_process\":\"planning\",\"to_process\":\"translating\"}" >> .writing/trace/process.jsonl
```

Replace process values and evidence with the current state. Append any goal events in that same command, each with its own `date -Is` value.

Every `evaluate` event means a `process_switch` whose `process` is `evaluate`. Append it only after the passage exists. Its `evidence` array must contain the exact first six words of the passage in a quoted string. If one sentence has fewer than six words, evaluate a few-sentence passage so six words are available. A `revise` switch must identify the most recent passage it changes.

## Processes and trace events

The exact process tokens are `planning`, `generate`, `organize`, `goal-setting`, `translating`, `reviewing`, `evaluate`, and `revise`. Use only these tokens in JSON. No other process token is allowed, including `evaluating`, `generating`, `organizing`, or `revising`.

Every event has `timestamp`, `event_type`, `responsible_agent`, `process`, `decision`, `evidence`, and `open_uncertainty`. The first five fields are strings, and `evidence` and `open_uncertainty` are JSON arrays of strings. A `process_switch` also has `from_process` and `to_process`, each a declared process token or `null`. A goal event also has string `goal_id` and string-or-null `parent_goal_id`. Keep the shared trace contract unchanged.

For `goal_created`, set `parent_goal_id` to the immediate parent. For `goal_developed`, retain the goal's current parent. For `goal_regenerated`, use the replacement ID as `goal_id` and the superseded ID as `parent_goal_id`. Record the reason in `decision` and concrete support in `evidence`. Use an empty `open_uncertainty` array when no uncertainty remains.

Use these literal one-line JSON shapes when there is nothing to cite, replacing the illustrative timestamp with `date -Is`:

```json
{"timestamp":"2026-01-01T00:00:00+00:00","event_type":"process_switch","responsible_agent":"Monitor","process":"planning","decision":"Choose planning for the active goal.","evidence":[],"open_uncertainty":[],"from_process":null,"to_process":"planning"}
{"timestamp":"2026-01-01T00:00:00+00:00","event_type":"goal_created","responsible_agent":"Writer","process":"goal-setting","decision":"Create the next middle-range goal.","evidence":[],"open_uncertainty":[],"from_process":null,"to_process":null,"goal_id":"G1","parent_goal_id":null}
```

Get every timestamp from `date -Is` at write time. Append to `.writing/trace/process.jsonl`; never rewrite or truncate it. Use one shell command and one quoted heredoc for a related event batch when practical. Each line remains one standalone JSON object. Append one `process_switch` for each process switch, with the first `from_process` set to `null`. Keep process names lowercase in JSON. Do not invent fields or reuse an old timestamp. Read back the appended lines when the command permits and repair malformed JSON before continuing.

## Local checks

Before each local passage, check the active goal and the text already written. After each append, check the new draft tail and the appended JSON lines. Confirm that each `evaluate` quote has exactly six passage words. Confirm that each goal update has its required identifiers. Confirm that the current network contains no history table. Confirm that no process switch implies a fixed stage order.

## Review and finish

Review each new passage against its active content goal, process goal, rhetorical problem, audience, purpose, and text already written. Use `generate` or `planning` for a missing idea, `goal-setting` for a more specific path, `reviewing` to read the growing text, and `revise` for a local wording change. Use `goal_developed` when the goal's purpose stays stable but becomes specific. Use `goal_regenerated` when writing changes its purpose or abstraction level. Use the current text as evidence about what comes next, but keep higher-level goals visible. Do not make a section boundary a process boundary or wait for a complete outline before translating.

Before the final response, read `.writing/draft.md` and return exactly its complete contents, with no summary, link, preamble, or code fence. Keep assumptions in `.writing/assumptions.md`, not in the draft. Check that every current network change has its trace event, every trace line is standalone JSON, every process value is declared above, and no subagent was spawned.

[^1]: Linda Flower and John R. Hayes. "A Cognitive Process Theory of Writing." College Composition and Communication 32(4), 1981, pp. 365-387. DOI: [10.58680/ccc198115885](https://doi.org/10.58680/ccc198115885) / JSTOR: [https://www.jstor.org/stable/356600](https://www.jstor.org/stable/356600)
