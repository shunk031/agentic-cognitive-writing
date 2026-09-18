---
name: cognitive-writing-single-writer
description: "Experimental A7 writing skill based on Flower and Hayes's single Writer. Use for controlled comparisons that require one main agent, a live hierarchical goal network, sentence-level recursion, and an append-only process trace."
---

# Cognitive writing single writer

Use this skill only for the A7 experimental condition. The skill models the single Writer described in "A Cognitive Process Model" and "The Monitor" in Flower and Hayes's _A Cognitive Process Theory of Writing_.

## One Writer and one Monitor

The main agent is the sole Writer and Monitor. Do not spawn subagents, role agents, delegation tools, or another writing process. The Writer owns planning, generating, translating, evaluating, revising, and goal-setting.

The Monitor is a strategist. Choose the next process from the active goal network, the rhetorical problem, and the growing text. Do not impose a fixed stage order. Use one default style: plan briefly at the top level, compose sentence by sentence, and plan locally when the current sentence or goal needs it. A writer may instead explore for a time or move toward polished prose quickly when the active goals support that choice.

## Read and preserve the writing state

Work in the session's current directory. Create missing files without overwriting existing user content:

```text
.writing/
├── assignment.md
├── assumptions.md
├── goals.md
├── draft.md
├── memory/
└── trace/process.jsonl
```

Read `assignment.md`, `goals.md`, `draft.md`, relevant `memory/` files, and the latest trace entries before choosing a process. If the assignment leaves the audience, purpose, scope, genre, or constraints unclear, apply a reasonable single-turn assumption and record it in `.writing/assumptions.md`. Do not ask a clarifying question in this condition.

Follow the repository writing contract for structure, links, claims, and plain English. Apply the `unslop` skill before finishing: remove filler, AI-pattern phrasing, vague claims, and unnecessary headings without changing the assignment's meaning.

## Keep a working goal network

The `Planning` process creates goals while composing. Treat goals as the working network described in "Writing is a goal-directed process" and "Goals, Topic, and Text", not as a ledger or checklist. Middle-range goals are the main planning output: they connect an abstract intention to a sentence-level choice.

Keep `.writing/goals.md` to the current network only. Each goal has one line with a stable ID, its parent ID, a one-line statement, `kind` (`process` or `content`), and `status` (`active`, `resolved`, or `superseded`). Use indentation to show parent and child relationships. Do not add a history table, per-goal verdict list, or proposal list. Goal history belongs in the trace.

When the Writer creates a goal, update the network and append `goal_created`. When the Writer makes an existing goal more specific, update it and append `goal_developed`. When a trial sentence shows that the active goal is wrong or too abstract, regenerate it immediately: mark the old ID `superseded`, create a new active ID, make the old ID its `parent_goal_id`, and append `goal_regenerated`. Do not use a proposal-and-acceptance step.

## Compose recursively at sentence level

Follow the recursive behavior described in "A Cognitive Process Model" and Figure 2's embedding example:

1. Let the Monitor select an active goal and the next process.
2. Before switching, append one `process_switch` event.
3. Translate one sentence or a few sentences serving one local goal. Never translate a whole section at once.
4. Evaluate the new sentence against the active goal, the rhetorical problem, and the text so far. Revise locally, plan locally, continue, or pop back to the parent goal according to that evaluation.
5. If the sentence changes what the Writer understands, develop or regenerate the goal immediately, then continue composing under the new network.

`generate` and `evaluate` may interrupt any process at any time. An interruption may call a local planning, translating, or reviewing pass and then return to the interrupted parent goal. Use "Explore and Consolidate" after an exploration burst by returning to the top-level goal and making the next goal more specific. Use "Write and Regenerate" when a failed trial sentence teaches the Writer that the current goal needs replacement. These are composing behaviors, not separate stages.

The growing text is part of the task environment. Use each new sentence as evidence about what can come next. Do not let the immediately preceding sentence replace the active higher-level goal. Pop back to the parent when a local sentence is complete. Do not let an early outline prevent a later goal change. Let the text, topic knowledge, and current goals constrain one another.

Planning may retrieve or generate ideas. Planning may organize ideas into a more useful representation. Planning may set a process goal such as exploring, returning later, or opening with a question. Translating turns the current local representation into prose. Reviewing may read the growing text as a springboard for further translating. Evaluating may judge the text or an unwritten plan. Revising may change a sentence or the goal that produced it. Goal-setting may create a middle-range bridge between intention and prose.

The Monitor chooses among these actions from the current state. The Monitor may remain in one process for several local sentences. The Monitor may switch processes when a sentence reveals a conflict. The Monitor may return to a higher-level goal after a local goal resolves. The Monitor may finish only after the draft, goal network, and trace agree.

## Processes and trace events

Use only these process values in trace events: `planning`, `generate`, `organize`, `goal-setting`, `translating`, `reviewing`, `evaluate`, and `revise`. These tokens are exact, not inflected English: write `evaluate`, never `evaluating`; `generate`, never `generating`; `organize`, never `organizing`; and `revise`, never `revising`.

Every `process_switch` event includes `timestamp`, `event_type`, `responsible_agent`, `process`, `decision`, `evidence`, `open_uncertainty`, `from_process`, and `to_process`. Every goal event includes those base fields plus `goal_id` and `parent_goal_id`. Keep the shared trace contract unchanged. Use `goal_id` for the affected goal. For `goal_created`, set `parent_goal_id` to the goal's immediate parent. For `goal_developed`, retain the goal's current parent. For `goal_regenerated`, use the replacement ID as `goal_id` and the superseded old ID as `parent_goal_id`. Record the reason for each change in `decision` and its concrete support in `evidence`. Use an empty `open_uncertainty` array when no uncertainty remains.

Keep `evidence` and `open_uncertainty` as JSON arrays of strings on every event, even when an array has one item. Never emit either field as a bare string.

Get every timestamp from `date -Is` at write time. Append to `.writing/trace/process.jsonl`; never rewrite or truncate it. Because sentence-level recursion creates many events, append a batch with one shell command and one heredoc when practical. Each line in the heredoc must remain one standalone JSON object. Do not write a JSON array, invent experiment-specific fields, or reuse an old timestamp. Before each switch, identify `from_process` and `to_process` explicitly. Set the first `from_process` to `null`. Use `null` for `to_process` only when the writing run ends. Keep process names lowercase in JSON. Use one event per line even when several events share a shell command. The shell supplies the timestamp for each event at the time of the append.

## Review decisions

Review the sentence against the active content goal. Review the sentence against the active process goal. Review the sentence against the rhetorical problem. Review the sentence against the text already written. If the sentence is adequate, mark the local goal resolved when its work is done. If the sentence needs wording changes, use `revise` and keep the same goal. If the sentence needs a missing idea, use `generate` or `planning` locally. If the sentence exposes a more specific path, use `goal-setting` and append `goal_developed`. If the sentence invalidates the active goal, regenerate it without waiting for approval. If a local goal resolves, pop to its immediate parent before selecting the next process. If an exploration burst produces useful material, consolidate it under the top-level goal. If a trial sentence fails, keep the failure as evidence for the next goal decision. Do not hide failed trials by rewriting the trace. Do not turn an evaluation into a per-goal verdict list in `goals.md`. Keep the current network readable enough for the next Writer step.

## Event batching

Use one shell command for a group of related events. Use a quoted heredoc so the shell does not alter JSON text. Put one JSON object on each line of the heredoc. Include the full base field set on every object. Include `from_process` and `to_process` on every `process_switch` object. Include `goal_id` and `parent_goal_id` on every goal object. Run `date -Is` in the same append command that writes the event. Do not use a timestamp copied from this file or an earlier session. Append the batch to `.writing/trace/process.jsonl`. Read back the appended lines after a batch when the shell command permits. Repair a malformed line before continuing the writing loop. Never replace the entire trace with a newly generated log.

The trace records the Writer's decisions, not hidden internal reasoning. Use concise evidence such as a file path, goal ID, or draft sentence. State unresolved factual or rhetorical questions in `open_uncertainty`. Keep `responsible_agent` as the main Writer or Monitor actor. Do not name a subagent because A7 has no subagents.

## Writer's operating rules

Keep the rhetorical problem visible while working on local sentences. Keep the audience and purpose visible when evaluating a sentence. Treat the draft as both an output and a source of new information. Treat a failed sentence as evidence, not as a reason to stop. Use content goals for what the draft should say or do for its audience. Use process goals for how the Writer will continue composing. Prefer middle-range goals over repeated abstract intentions. Resolve a local goal only when its sentence-level work is complete. Pop to a parent goal when the local goal no longer controls the next move. Create a child goal when the current goal needs a concrete next action. Develop a goal when its purpose stays stable but its wording becomes specific. Regenerate a goal when writing changes the purpose or the level of abstraction. Keep superseded goals visible in the current network until the trace records the change. Do not copy trace history into `goals.md`. Do not use a section boundary as a process boundary. Do not wait for a complete outline before translating. Do not stop reviewing because a sentence is grammatically correct. Check whether the sentence advances its active goal. Check whether the sentence fits the text that precedes it. Check whether the sentence changes what the Writer now understands. Let the Monitor choose the next process after each meaningful evaluation. Use the user's assignment as the authority for intent and constraints. Keep unsupported claims visible in `open_uncertainty`. Preserve user-authored wording unless the active goal requires revision.

## Line-level checks

Check the assignment before planning. Check the active goal before translating. Check the sentence before continuing. Check the trace after appending.

Check the draft before completing the response.

Check that the current network contains no history table.

Check that every goal event has both goal identifiers.

Check that the old goal is superseded when a new goal replaces it.

Check that no process switch implies a fixed stage order.

Check that the Monitor remains the decision-maker for each process switch.

Check that the main agent remains the only Writer throughout the run.

## Finish the single-turn task

Before the final response, write the complete draft to `.writing/draft.md`. The final response must contain the complete draft text, not a summary or a link to the file. Keep assumptions in `.writing/assumptions.md` and do not add an assumptions preamble to the draft. Check that every current network change has its corresponding trace event, every trace line is standalone JSON, and every process value is declared above.
