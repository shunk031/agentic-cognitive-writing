---
name: writing-cogwriter-style
description: "Exploratory CogWriter-style adaptation. Produce and immediately revise a structured plan, generate document segments in parallel with native subagents, and run a bounded length-review loop without a goal network."
---

> [!NOTE]
> After reading this `SKILL.md`, say: `I read writing-cogwriter-style.`
>
> Say the line in an assistant message of its own immediately after reading this skill. The line never appears in `.writing/draft.md` or in the final response.

# CogWriter[^1]-style writing

Run a CogWriter[^1]-style adaptation, not a reproduction. The fixed top-level order is:

`initial planning -> immediate plan revision -> parallel segment generation -> length review`

The adaptation follows the published behavior of a structured Planning Agent followed by Generation Agents. The initial planning pass creates a structured plan with ordered document segments and requirements. The immediate plan-revision pass checks that plan against the assignment and returns one revised, normalized plan. Native subagents then generate the segments in parallel. Each segment subagent receives the complete revised plan, the assignment, the supplied context, and its local segment plan. Each segment then enters the length-review loop, which expands or compresses it toward its target length from the plan while preserving meaning and coherence. The coordinator assembles the segments in plan order into the final document.

## Equal-information and no-retrieval policy

The runner gives this condition the same assignment, supplied context, context-window policy, timeout, model family, total output budget, and attempt budget as every comparison condition. Length review allows at most two revision attempts per segment, and a segment within 10 percent of its target length passes. Parallelism changes scheduling, not the amount or kind of information available to a subagent.

The coordinator and every subagent may use only the Assignment, Supplied context, and Requested output constraints sections of the prompt, the task file, the persisted plan, and outputs produced by this run. No actor may browse, search, call a retrieval tool, access the Internet, or use an external source. If the supplied context does not establish a claim, preserve the uncertainty or omit the claim.

This adaptation has no goal network. Do not create or modify `.writing/goals.md`, emit no goal events, and do not treat the structured document plan as a replacement goal file. The plan exists only to condition segment generation and is persisted at `.writing/baselines/cogwriter-style/plan.json` for run inspection.

The coordinator owns the fixed top-level order, subagent dispatch, assembly, and trace recording. Planning and generation subagents own their returned artifacts. A native subagent must not launch a nested `codex exec` process.

## Procedure

1. Read the Assignment, Supplied context, and Requested output constraints sections of the prompt. Do not create `.writing/assignment.md`, and do not read or modify `.writing/goals.md`.
2. Run exactly one initial-planning pass. Require a structured plan with an ordered list of segment IDs, each segment's purpose, required content, target length, dependencies, and whole-document constraints. Persist the returned structure at `.writing/baselines/cogwriter-style/plan-initial.json`.
3. Run exactly one immediate plan-revision pass. Give the revision actor the assignment, supplied context, and complete initial plan. Require a revised structured plan and normalize it without adding a second planning pass. Persist the result at `.writing/baselines/cogwriter-style/plan.json`.
4. Dispatch one native subagent per revised segment in parallel, following the subagent procedure below. Every segment subagent receives the complete plan, not only its local item, together with the assignment and supplied context. A subagent may perform one local plan adjustment before writing, as part of its segment-generation call, but it must not change the top-level order or invent a new process.
5. Assemble the returned segment texts in the exact plan order. Persist them under `.writing/baselines/cogwriter-style/segments/`.
6. Run the fixed length-review loop for each segment. The reviewer compares the segment with its target length and the assignment. If the segment is more than 10 percent above or below its target length, the reviewer returns one length revision and the coordinator measures again. Stop when the segment is within 10 percent of its target or after two revision attempts. Do not turn length review into a general content review or retrieval pass.
7. Write the assembled, length-reviewed document to `.writing/draft.md`.
8. Append schema-valid `process_switch` events to `.writing/trace/process.jsonl` for the four top-level stages. Use `null -> initial-planning`, `initial-planning -> immediate-plan-revision`, `immediate-plan-revision -> parallel-segment-generation`, and `parallel-segment-generation -> length-review`. Internal segment completions and length attempts are artifacts of the current stage, not new top-level process selections.

The trace contract is fixed at exactly four `process_switch` events, with `process` values `initial-planning`, `immediate-plan-revision`, `parallel-segment-generation`, and `length-review` in this order. Do not append goal events, retrieval events, or private reasoning.

## Trace recipe

You append every trace event yourself, with this command and no other. Change only the first four lines: the stage's `process` token, the decision, the evidence list, and the open-uncertainty list. The command fills the timestamp and `from_process`, writes valid JSON, and appends nothing when a value is malformed.

```sh
python3 - <<'PY'
process = "initial-planning"
decision = "Create the initial ordered segment plan."
evidence = [".writing/baselines/cogwriter-style/plan-initial.json"]
open_uncertainty = []
import datetime, json, pathlib
trace = pathlib.Path(".writing/trace/process.jsonl")
trace.parent.mkdir(parents=True, exist_ok=True)
lines = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines() if line.strip()] if trace.exists() else []
event = {"timestamp": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "event_type": "process_switch", "responsible_agent": "runner", "process": process, "from_process": lines[-1]["to_process"] if lines else None, "to_process": process, "decision": decision, "evidence": evidence, "open_uncertainty": open_uncertainty}
with trace.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(event, ensure_ascii=False) + "\n")
PY
```

## Subagent procedure

Before the first subagent call, copy the prompt's Assignment, Supplied context, and Requested output constraints sections verbatim into `.writing/baselines/cogwriter-style/task.md`. Then run every subagent call this way:

1. Call `multi_agent_v1__spawn_agent` with `fork_context: false` and `message` set to a brief from the template below.
2. Call `multi_agent_v1__wait_agent` with `targets` listing the agents to collect and `timeout_ms: 300000`. Call it again while it returns `timed_out: true`, at most three calls per agent.
3. Read each result from its `completed` status, and call `multi_agent_v1__close_agent` with that agent's ID as `target` at once.

Keep at most five agents open at a time. A final status other than `completed` with a non-empty result is a failure: close the agent and spawn the same brief once more, and when the retry also fails, continue without that result and name the gap in the next trace event's evidence. Do not run `codex` in the shell.

```text
You are a <kind> subagent for a writing project. You are not the coordinator. Do not spawn agents, do not run codex, and do not write .writing/trace/process.jsonl.
This is a single-turn task with no interactive user; never ask questions.
Use only the task file and the material in this brief. Do not search the web, fetch URLs, call retrieval tools, or use other external sources.
Task file: .writing/baselines/cogwriter-style/task.md holds the assignment, supplied context, and requested output constraints verbatim. Read all of it.
Output language: <the language the assignment requests, or the language of its instructions>. Write all prose in it.
Length: <the target length for this task or segment>
Scope: <the task or segment and its place in the document>
Request: <the work to do, with the plan or dependency results it needs>
Your final message is the result.
```

The adaptation does not claim to reproduce CogWriter[^1]'s original models, prompts, dataset, token limits, monitoring implementation, or reported results. The adaptation preserves the published control-flow ideas needed for this comparison and makes the platform, input, budget, and no-retrieval differences explicit.

[^1]: Kaiyang Wan, Honglin Mu, Rui Hao, Haoran Luo, Tianle Gu, and Xiuying Chen, "A Cognitive Writing Perspective for Constrained Long-Form Text Generation," *Findings of the Association for Computational Linguistics: ACL 2025* (Findings of ACL 2025), 2025, https://doi.org/10.18653/v1/2025.findings-acl.511.
