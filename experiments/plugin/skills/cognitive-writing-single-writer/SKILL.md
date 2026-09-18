---
name: cognitive-writing-single-writer
description: "Experimental A7 writing skill based on Flower and Hayes's single Writer. Use for controlled comparisons that require one main agent, a live hierarchical goal network, paragraph-scale recursion, and an append-only process trace with Figure 2's sentence example as the theoretical anchor."
---

# Cognitive writing single writer

Use this skill only for A7. Flower and Hayes's _A Cognitive Process Theory of Writing_[^1] models one Writer with Planning, Translating, and Reviewing under a Monitor. The paper says nothing about software agents. A7 operationalizes that model as one main agent that is both Writer and Monitor, with no subagents.

## One Writer and one Monitor

The main agent is the only Writer. Do not spawn subagents, role agents, delegation tools, or another writing process. The wrapper sets `require_delegation = false`.

The `Monitor` is the strategist. Choose the next process from the current goal network, the rhetorical problem, and the growing text. Do not impose a stage sequence. Use this default style: plan briefly at the top level, compose one paragraph at a time, and plan locally when needed. A writer may instead explore for a time or move toward polished prose quickly when the active goals support that choice.

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

Initialize `.writing/trace/process.jsonl` before writing any goals or process events. Run the trace-initialization command separately from the command that writes initial goals. Create the trace file without truncating existing content. Read `assignment.md`, `goals.md`, `draft.md`, relevant `memory/` files, and the latest trace entries before choosing a process. If the assignment leaves the audience, purpose, scope, genre, or constraints unclear, make a reasonable single-turn assumption and record it in `.writing/assumptions.md`. Do not ask a clarifying question.

When the initial goal network is missing, write `goals.md` and append one `goal_created` event for every goal in that initial network in the same shell command, before any `Translating` switch. The trace file must already exist before that command. Never write a goal first and defer its event to a later command.

Use this order for an initial network. First run the initialization command, then run one new shell command that writes `goals.md` and appends one `goal_created` event for every goal line written in the heredoc:

```sh
mkdir -p .writing/trace .writing/memory
: >> .writing/trace/process.jsonl
```

```sh
stamp=$(date -Is)
cat >> .writing/goals.md <<'EOF'
G1 | parent: null | State the task's purpose and scope. | kind: content | status: active
EOF
printf '%s\n' "{\"timestamp\":\"$stamp\",\"event_type\":\"goal_created\",\"responsible_agent\":\"Writer\",\"process\":\"goal-setting\",\"decision\":\"Create G1 for the task purpose.\",\"evidence\":[\".writing/goals.md\"],\"open_uncertainty\":[],\"goal_id\":\"G1\",\"parent_goal_id\":null}" >> .writing/trace/process.jsonl
```

Follow the repository writing contract for structure, links, claims, and plain English. Apply the `unslop` skill before finishing. Remove filler, AI-pattern phrasing, vague claims, and unnecessary headings without changing the task's meaning.

## Keep a working goal network

The paper's "Writing is a goal-directed process" and "Goals, Topic, and Text" sections describe goals created, developed, and revised during composing. The paper predicts that good and poor writers differ in the quantity and quality of middle-range goals that bridge intention and prose. A7 therefore asks the Writer to make those goals explicit. The prediction belongs to the paper, and the explicit file representation belongs to this experiment.

Treat `.writing/goals.md` as the current hierarchical network, not a ledger. Each line has a stable goal ID, parent ID, one-line statement, `kind` (`process` or `content`), and `status` (`active`, `resolved`, or `superseded`). Use indentation for parent and child relationships. Keep no history table, verdict list, or proposal list in the file. History lives in the trace.

When the Writer creates a goal, update the network and append `goal_created`. When the Writer makes an existing goal more specific, update it and append `goal_developed`. When an evaluated passage shows that the active goal is wrong or too abstract, regenerate it immediately: mark the old ID `superseded`, create a new active ID, use the old ID as `parent_goal_id`, and append `goal_regenerated`. There is no proposal-and-acceptance step.

## Compose recursively at paragraph scale

The paper's process model treats processes as optional and allows them to embed at any level. Figure 2 remains the theoretical anchor: planning, translating, and reviewing embed while the Writer works on one sentence. This experiment fixes the smallest observable unit at one paragraph because the writer batches to subsection scale when the unit is left at the sentence. A paragraph is one locally coherent block serving one local goal, not a whole section or subsection.

For each paragraph, let the `Monitor` choose the next process, translate the paragraph, and use its text to choose what happens next. `generate` and `evaluate` may interrupt any process at any time. When an `evaluate` step finds that the paragraph elaborates or narrows its active goal, update `goals.md`, append the `evaluate` event, and append `goal_developed` in one shell command, following the paper's "State and Develop" pattern. Do not force `goal_developed` when the goal is unchanged. When a local goal resolves, pop back to its immediate parent. When an exploration burst yields useful material, return to the top-level goal and consolidate it into a more specific goal. When a trial paragraph shows that the active goal needs a new purpose or level of abstraction, update `goals.md` and append the `evaluate` and `goal_regenerated` events in one shell command. Do not pop or regenerate mechanically after every paragraph.

## Mechanical incremental composition

The draft is built by appending to `.writing/draft.md`. If the file is missing, create the empty file with `: >> .writing/draft.md`; never truncate it. Never assemble a full draft and write it in one operation. Never use a replacement write, `>`, or a whole-file rewrite. The only exception is a local revision of the most recent passage. Replace only that passage, append a `process_switch` whose `process` is `revise` in the same shell command, and then return to append-only writing. Never rewrite an earlier passage.

Each `Translating` step appends exactly one paragraph serving one local goal, at most about 120 words. Never append more than 200 words. If a coherent paragraph would exceed about 120 words, split it into two append commands and put an `evaluate` step between them. Each append command must contain one paragraph only, never a subsection or several blank-line-separated paragraphs, and must end with a blank line. In the same shell command, append that paragraph first and then append its `process_switch` plus any goal events to `.writing/trace/process.jsonl`. Do not predeclare future paragraphs or events. Do not write any trace event in a setup-only command before the first draft append. A quoted heredoc may hold the short paragraph and one JSON object per line. The shell command must use `>>` for the draft and trace. Keep evidence factual at append time, such as the existing draft quote, file path, or goal ID, never future-tense evidence.

Use one shell command with this order for every translating batch:

```sh
fragment=$(cat <<'EOF'
One paragraph of no more than about 120 words for one local goal.
EOF
)
test "$(printf '%s\n' "$fragment" | wc -w)" -le 120
printf '%s\n\n' "$fragment" >> .writing/draft.md
stamp=$(date -Is)
printf '%s\n' "{\"timestamp\":\"$stamp\",\"event_type\":\"process_switch\",\"responsible_agent\":\"Monitor\",\"process\":\"translating\",\"decision\":\"Append the local passage.\",\"evidence\":[],\"open_uncertainty\":[],\"from_process\":null,\"to_process\":\"translating\"}" >> .writing/trace/process.jsonl
```

Replace process values and evidence with the current state. Keep the word-count check before the draft append in a real command. Append any goal events in that same command, each with its own `date -Is` value. If a paragraph is split, finish the first command, append its `evaluate` event, then run the second command.

Every `evaluate` event means a `process_switch` whose `process` is `evaluate`. Append it only after the paragraph exists. Its `evidence` array must contain the opening phrase of the paragraph just appended, copied verbatim with punctuation and case unchanged. Read the phrase back from `.writing/draft.md` in the same shell command; never retype or paraphrase it. Check mechanically that the quote is a substring of that paragraph. A `revise` switch must identify the most recent passage it changes.

For example, read back the last appended paragraph with `tail` and `head`, take its opening eight words, check the substring, and append the evaluate event from `$quote` in that same shell command:

```sh
paragraph=$(tail -n 2 .writing/draft.md | head -n 1)
quote=$(printf '%s\n' "$paragraph" | awk '{for (i=1; i<=8 && i<=NF; i++) printf "%s%s", $i, (i<8 && i<NF ? OFS : ORS)}')
case "$paragraph" in *"$quote"*) ;; *) exit 1 ;; esac
stamp=$(date -Is)
printf '%s\n' "{\"timestamp\":\"$stamp\",\"event_type\":\"process_switch\",\"responsible_agent\":\"Monitor\",\"process\":\"evaluate\",\"decision\":\"Evaluate the appended paragraph.\",\"evidence\":[\"$quote\"],\"open_uncertainty\":[],\"from_process\":\"translating\",\"to_process\":\"evaluate\"}" >> .writing/trace/process.jsonl
```

## Processes and trace events

The exact process tokens are `planning`, `generate`, `organize`, `goal-setting`, `translating`, `reviewing`, `evaluate`, and `revise`. Use only these tokens in JSON. No other process token is allowed, including `evaluating`, `generating`, `organizing`, or `revising`.

Every event has `timestamp`, `event_type`, `responsible_agent`, `process`, `decision`, `evidence`, and `open_uncertainty`. `event_type` is always exactly one of `process_switch`, `goal_created`, `goal_developed`, or `goal_regenerated`; never put a process token such as `evaluate` or `translating` in `event_type`. The first five fields are strings, and `evidence` and `open_uncertainty` are JSON arrays of strings. A `process_switch` also has `from_process` and `to_process`, each a declared process token or `null`. `evaluate`, `translating`, and every other declared process token may appear only in `process`, `from_process`, or `to_process`. A goal event also has string `goal_id` and string-or-null `parent_goal_id`. Keep the shared trace contract unchanged.

For `goal_created`, set `parent_goal_id` to the immediate parent. For `goal_developed`, retain the goal's current parent. For `goal_regenerated`, use the replacement ID as `goal_id` and the superseded ID as `parent_goal_id`. Record the reason in `decision` and concrete support in `evidence`. Use an empty `open_uncertainty` array when no uncertainty remains.

Use these shell forms when there is nothing to cite. Assign `stamp` in the same command before appending the line; never copy a timestamp from an example:

```sh
stamp=$(date -Is)
printf '%s\n' "{\"timestamp\":\"$stamp\",\"event_type\":\"process_switch\",\"responsible_agent\":\"Monitor\",\"process\":\"evaluate\",\"decision\":\"Evaluate the appended paragraph.\",\"evidence\":[],\"open_uncertainty\":[],\"from_process\":\"translating\",\"to_process\":\"evaluate\"}" >> .writing/trace/process.jsonl
printf '%s\n' "{\"timestamp\":\"$stamp\",\"event_type\":\"goal_created\",\"responsible_agent\":\"Writer\",\"process\":\"goal-setting\",\"decision\":\"Create the next middle-range goal.\",\"evidence\":[],\"open_uncertainty\":[],\"goal_id\":\"G1\",\"parent_goal_id\":null}" >> .writing/trace/process.jsonl
```

Every shell command that appends one or more trace lines must execute `stamp=$(date -Is)` in that same command before its first trace append and interpolate `$stamp` into every line in that command. The next command must execute `date -Is` again; never type, estimate, copy, or reuse a timestamp across commands. Append to `.writing/trace/process.jsonl`; never rewrite or truncate it. Use one shell command and one quoted heredoc for a related event batch when practical. Each line remains one standalone JSON object. Append one `process_switch` for each process switch, with the first `from_process` set to `null`. Keep process names lowercase in JSON. Do not invent fields or reuse an old timestamp. Read back the appended lines when the command permits and repair malformed JSON before continuing.

For the sequence of `process_switch` events, the first `from_process` is `null`. Every later `from_process` must equal the immediately preceding `process_switch` event's `to_process`. Goal events do not reset this chain. Before finishing, compare the `from_process` and `to_process` values mechanically in trace order. Do not append a final `reviewing` switch with a stale source.

The continuity check has this shape:

```python
switches = [e for e in events if e["event_type"] == "process_switch"]
assert switches[0]["from_process"] is None
assert all(a["to_process"] == b["from_process"] for a, b in zip(switches, switches[1:]))
```

## Local checks

Before each local passage, check the active goal and the text already written. After each append, check the new draft tail and the appended JSON lines. Confirm mechanically that each `evaluate` quote is a substring of the paragraph it evaluates and was read back from the draft. Confirm that each goal update has its required identifiers. Confirm that the current network contains no history table. Confirm that no process switch implies a fixed stage order.

## Review and finish

Review each new passage against its active content goal, process goal, rhetorical problem, audience, purpose, and text already written. Use `generate` or `planning` for a missing idea, `goal-setting` for a more specific path, `reviewing` to read the growing text, and `revise` for a local wording change. Use `goal_developed` when the goal's purpose stays stable but becomes specific. Use `goal_regenerated` when writing changes its purpose or abstraction level. Use the current text as evidence about what comes next, but keep higher-level goals visible. Do not make a section boundary a process boundary or wait for a complete outline before translating.

Before the final response, read `.writing/draft.md` and return exactly its complete contents, with no summary, link, preamble, or code fence. Keep assumptions in `.writing/assumptions.md`, not in the draft. Check that every current network change has its trace event, every trace line is standalone JSON, every process value is declared above, and no subagent was spawned.

[^1]: Linda Flower and John R. Hayes. "A Cognitive Process Theory of Writing." College Composition and Communication 32(4), 1981, pp. 365-387. DOI: [10.58680/ccc198115885](https://doi.org/10.58680/ccc198115885) / JSTOR: [https://www.jstor.org/stable/356600](https://www.jstor.org/stable/356600)
