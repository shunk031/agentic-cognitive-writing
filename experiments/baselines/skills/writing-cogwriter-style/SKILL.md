---
name: writing-cogwriter-style
description: "Exploratory X-style adaptation of CogWriter. Produce and immediately revise a structured plan, generate document segments in parallel with native subagents, and run a bounded length-review loop without a goal network."
---

# CogWriter-style writing

Run an X-style adaptation of CogWriter, not a reproduction. The fixed top-level order is:

`initial planning -> immediate plan revision -> parallel segment generation -> length review`

The adaptation follows the published behavior of a structured Planning Agent followed by Generation Agents. The initial planning pass creates a structured plan with ordered document segments and requirements. The immediate plan-revision pass checks that plan against the assignment and returns one revised, normalized plan. Native subagents then generate the segments in parallel. Each segment subagent receives the complete revised plan, the assignment, the supplied context, and its local segment plan. Each segment then enters the length-review loop, which expands or compresses it toward the runner's fixed target while preserving meaning and coherence. The coordinator assembles the segments in plan order into the final document.

## Equal-information and no-retrieval policy

The runner gives this condition the same assignment, supplied context, context-window policy, timeout, model family, total output budget, and attempt budget as every comparison condition. The runner fixes the maximum length-review attempts and per-stage budget before the run. Parallelism changes scheduling, not the amount or kind of information available to a subagent.

The coordinator and every subagent may use only `.writing/assignment.md`, the supplied context, the persisted plan, and outputs produced by this run. No actor may browse, search, call a retrieval tool, access the Internet, or use an external source. If the supplied context does not establish a claim, preserve the uncertainty or omit the claim.

This adaptation has no goal network. Leave `.writing/goals.md` untouched, emit no goal events, and do not treat the structured document plan as a replacement goal file. The plan exists only to condition segment generation and is persisted at `.writing/baselines/cogwriter-style/plan.json` for run inspection.

The user owns rhetorical intent, factual authority, final wording, and publication. The coordinator owns the fixed top-level order, subagent dispatch, assembly, and trace recording. Planning and generation subagents own their returned artifacts. A native subagent must not launch a nested `codex exec` process.

## Procedure

1. Read `.writing/assignment.md` and the supplied context. Read the latest shared trace only to avoid clobbering it. Do not read or modify `.writing/goals.md`.
2. Run exactly one initial-planning pass. Require a structured plan with an ordered list of segment IDs, each segment's purpose, required content, target length, dependencies, and whole-document constraints. Persist the returned structure at `.writing/baselines/cogwriter-style/plan-initial.json`.
3. Run exactly one immediate plan-revision pass. Give the revision actor the assignment, supplied context, and complete initial plan. Require a revised structured plan and normalize it without adding a second planning pass. Persist the result at `.writing/baselines/cogwriter-style/plan.json`.
4. Dispatch one native subagent per revised segment in parallel. Every segment subagent receives the complete plan, not only its local item, together with the assignment and supplied context. A subagent may perform one local plan adjustment before writing, as part of its segment-generation call, but it must not change the top-level order or invent a new process.
5. Assemble the returned segment texts in the exact plan order. Persist them under `.writing/baselines/cogwriter-style/segments/`.
6. Run the fixed length-review loop for each segment. The reviewer compares the segment with its target length and the assignment. If the segment is outside the runner's fixed tolerance and budget remains, the reviewer returns one length revision and the coordinator measures again. Stop at the tolerance or the fixed attempt/budget limit. Do not turn length review into a general content review or retrieval pass.
7. Write the assembled, length-reviewed document to `.writing/draft.md`.
8. Append schema-valid `process_switch` events to `.writing/trace/process.jsonl` for the four top-level stages. Use `null -> initial-planning`, `initial-planning -> immediate-plan-revision`, `immediate-plan-revision -> parallel-segment-generation`, and `parallel-segment-generation -> length-review`. Internal segment completions and length attempts are artifacts of the current stage, not new top-level process selections.

Each event includes `timestamp`, `event_type`, `responsible_agent`, `process`, `decision`, `evidence`, `open_uncertainty`, `from_process`, and `to_process`. Use `responsible_agent: "runner"`, cite the stage inputs, and list the relevant plan, segment, or draft files in `artifacts`. Do not append goal events, retrieval events, or private reasoning. If a subagent fallback is needed because native delegation is unavailable, the runner records that observable fallback in the event evidence while keeping the top-level order fixed.

The adaptation does not claim the original models, prompts, dataset, token limits, monitoring implementation, or reported results. The adaptation preserves the published control-flow ideas needed for this comparison and makes the platform, input, budget, and no-retrieval differences explicit.
