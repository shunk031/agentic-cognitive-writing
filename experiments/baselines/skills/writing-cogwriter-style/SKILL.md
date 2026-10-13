---
name: writing-cogwriter-style
description: "Exploratory CogWriter-style adaptation. Produce and immediately revise a structured plan, generate document segments in parallel with native subagents, and run a bounded length-review loop without a goal network."
---

> [!NOTE]
> After reading this `SKILL.md`, say: `I read writing-cogwriter-style.`
>
> Say the line immediately after reading this skill, in the same response as your next tool call. The line never appears in `.writing/draft.md` or in the final response.

# CogWriter[^1]-style writing

Run a CogWriter[^1]-style adaptation, not a reproduction. The fixed top-level order is:

`initial planning -> immediate plan revision -> parallel segment generation -> length review`

The adaptation follows the published behavior of a structured Planning Agent followed by Generation Agents. The initial planning pass creates a structured plan with ordered document segments and requirements. The immediate plan-revision pass checks that plan against the assignment and returns one revised, normalized plan. Native subagents then generate the segments in parallel. Each segment subagent receives the complete revised plan, the assignment, the supplied context, and its local segment plan. Each segment then enters the length-review loop, which expands or compresses it toward its target length from the plan while preserving meaning and coherence. The coordinator assembles the segments in plan order into the final document.

## Equal-information and no-retrieval policy

The runner gives this condition the same assignment, supplied context, context-window policy, timeout, model family, total output budget, and attempt budget as every comparison condition. Length review allows at most two revision attempts per segment, and a segment within 10 percent of its target length passes. Length is counted in words, and each CJK character counts as one word. Parallelism changes scheduling, not the amount or kind of information available to a subagent.

The coordinator and every subagent may use only the Assignment, Supplied context, and Requested output constraints sections of the prompt, the task file, the persisted plan, and outputs produced by this run. No actor may browse, search, call a retrieval tool, access the Internet, or use an external source. If the supplied context does not establish a claim, preserve the uncertainty or omit the claim.

This adaptation has no goal network. Do not create or modify `.writing/goals.md`, emit no goal events, and do not treat the structured document plan as a replacement goal file. The plan exists only to condition segment generation and is persisted at `.writing/baselines/cogwriter-style/plan.json` for run inspection.

The coordinator owns the fixed top-level order, subagent dispatch, assembly, and trace recording. Planning and generation subagents own their returned artifacts. A native subagent must not launch a nested `codex exec` process.

## Procedure

1. Read the Assignment, Supplied context, and Requested output constraints sections of the prompt. Do not create `.writing/assignment.md`, and do not read or modify `.writing/goals.md`.
2. Append the `initial-planning` event with the trace recipe. Then you, the coordinator, run exactly one initial-planning pass yourself. Require a structured plan with an ordered list of segment IDs, each segment's purpose, required content, target length, dependencies, and whole-document constraints. Persist it at `.writing/baselines/cogwriter-style/plan-initial.json`.
3. Append the `immediate-plan-revision` event. Then you run exactly one immediate plan-revision pass yourself against the assignment, supplied context, and complete initial plan, and normalize the revised plan without adding a second planning pass. Persist it at `.writing/baselines/cogwriter-style/plan.json`.
4. Append the `parallel-segment-generation` event. Then dispatch one segment subagent per revised segment, following the subagent procedure below. Every segment subagent receives the complete plan, not only its local item. A subagent may perform one local plan adjustment before writing, as part of its segment-generation call, but it must not change the top-level order or invent a new process. Assemble the returned segment texts in the exact plan order and persist them under `.writing/baselines/cogwriter-style/segments/`.
5. Append the `length-review` event, citing `.writing/baselines/cogwriter-style/length-review.md` in its evidence. Then you run the length-review loop yourself for each segment: measure it against its target length, and when it is more than 10 percent above or below that target, revise it once and measure again. Stop when the segment is within 10 percent of its target or after two revision attempts. Write each segment's target length, final length, and attempts to `.writing/baselines/cogwriter-style/length-review.md`, marking every segment that still misses its target as a length-review failure. Do not turn length review into a general content review or retrieval pass.
6. Write the assembled, length-reviewed document to `.writing/draft.md`, and return exactly its contents as the final response, with nothing before or after it.

The trace contract is fixed at exactly four `process_switch` events, with `process` values `initial-planning`, `immediate-plan-revision`, `parallel-segment-generation`, and `length-review` in this order. Do not append goal events, retrieval events, or private reasoning.

## Trace recipe

You append every trace event yourself, with this command and no other. Run it once per stage, immediately when that stage starts, never afterwards and never from a loop or script that writes several events. Change only the first four lines: the `process` token, the decision, the evidence list, and the open-uncertainty list. The command checks the process token and the field types, fills the timestamp and `from_process`, writes valid JSON, and appends nothing when a value is invalid.

```sh
python3 - <<'PY'
process = "initial-planning"
decision = "Create the initial ordered segment plan."
evidence = [".writing/baselines/cogwriter-style/plan-initial.json"]
open_uncertainty = []
allowed = ("initial-planning", "immediate-plan-revision", "parallel-segment-generation", "length-review")
import datetime, json, pathlib, sys
if process not in allowed or not isinstance(decision, str) or not decision.strip() or not all(isinstance(v, list) and all(isinstance(x, str) for x in v) for v in (evidence, open_uncertainty)):
    sys.exit("invalid trace event; nothing was appended")
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
2. To run several calls in parallel, spawn up to five agents, then call `multi_agent_v1__wait_agent` with `targets` listing every open agent and `timeout_ms: 300000`. Call it again while it returns `timed_out: true`, at most three calls per agent.
3. Each time `wait_agent` returns, read every result that has a `completed` status and call `multi_agent_v1__close_agent` with that agent's ID as `target` before the next `wait_agent` or `spawn_agent` call.

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
