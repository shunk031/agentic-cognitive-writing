---
name: writing-adaptive-task-planning
description: "Confirmatory condition A3 (Adaptive Task Planning). Build and persist a typed reasoning/composition task graph, recursively decompose and execute tasks with subagents, and revise the graph from aggregated text while keeping adaptation on task structure rather than writing-process selection."
---

> [!NOTE]
> After reading this `SKILL.md`, say: `I read writing-adaptive-task-planning.`
>
> Say the line immediately after reading this skill, in the same response as your next tool call. The line never appears in `.writing/draft.md` or in the final response.

# Adaptive Task Planning

Run confirmatory condition A3, Adaptive Task Planning, as an adaptation of WriteHERE[^1]'s heterogeneous recursive planning, not a reproduction. The coordinator dynamically builds a directed acyclic task graph in project files and interleaves recursive decomposition with execution. The root task is a composition task for the complete document. Child tasks may be reasoning tasks for requirements, structure, consistency, or argument development and composition tasks for section or document writing. The coordinator schedules ready tasks by graph state and dependency order, then persists the graph after every change.

The condition changes task structure only. The coordinator must not adapt by selecting among named writing processes, replacing a task graph with a fixed process pipeline, or using a meta-process chooser.

## Equal-information and no-retrieval policy

The runner gives this condition the same assignment, supplied context, context-window policy, timeout, model settings, total output budget, and attempt budget as every comparison condition. The graph may change shape in response to the assignment and task results, but no task may obtain information unavailable to the other conditions.

Retrieval tasks are disabled under the equal-information policy. The graph may contain only `reasoning` and `composition` task types. Do not create a retrieval node, browse, search, call a retrieval tool, access the Internet, or use an external source. The runner records retrieval, evidence gathering, and citation handling as `N/A` in the run accounting by design. A missing fact remains uncertain or is omitted.

This adaptation uses the task graph as its only planning structure. Do not create or modify `.writing/goals.md` and emit no goal events. The coordinator owns graph state, ready-task scheduling, subagent dispatch, persistence, and trace recording. Typed task subagents own their returned reasoning or composition results. A native subagent must not launch a nested `codex exec` process.

## Persisted graph contract

Persist the graph at `.writing/baselines/adaptive-task-planning/task-graph.json`. Keep the file valid JSON after every mutation. The top-level object includes `version`, `root_task_id`, `tasks`, and `updated_at`. Each task includes:

- `id`, a stable project-local identifier
- `type`, exactly `reasoning` or `composition`
- `goal`, the task objective
- `dependencies`, a list of task IDs that must finish first
- `status`, one of `active`, `suspended`, or `silent`
- `result`, either `null` or the task's returned result
- `parent_id`, the containing task ID or `null` for the root
- `children`, an ordered list of child task IDs

Store task results under `.writing/baselines/adaptive-task-planning/results/` when they are too large for the graph file. Use project-relative paths in the graph. A suspended task has been decomposed or is waiting for dependencies. An active task is ready for planning or execution. A silent task has completed or failed and will not be scheduled again.

## Procedure

1. Read the Assignment, Supplied context, and Requested output constraints sections of the prompt. Do not create `.writing/assignment.md`. Initialize a root `composition` task if the graph does not exist. Do not read or modify `.writing/goals.md`.
2. Select the active task nearest the root by breadth-first depth, breaking ties with the graph's stable task order. Give the subagent the task's parent context, dependency results, and relevant graph structure in a brief that follows the subagent procedure below.
3. Ask the subagent whether the task is atomic under the two enabled types. Every task, at every depth, gets this atomicity decision before it is executed. If the task is not atomic, ask it for typed child tasks and dependencies. Decompose at most three levels below the root and keep the graph at no more than 30 tasks; at either cap, treat every remaining task as atomic. Add the children to the graph, mark the parent `suspended`, and persist the graph before scheduling another task.
4. If the task is atomic, dispatch its typed executor. A reasoning executor returns a bounded reasoning or planning artifact. A composition executor returns prose for its task. Store the result, mark the task `silent`, update dependent tasks, and persist the graph.
5. After each composition task completes and its result is stored, re-read the current aggregated text, meaning the composition results produced so far in dependency order. Before scheduling the next task, the coordinator may perform text-conditioned graph revision. Allowed revision operations are:
   - revise the goal text of an active or suspended task
   - add new typed child tasks with dependencies under any non-silent task
   - retire an active or suspended task by marking it `silent` with a result that notes the retirement
   - add or reorder dependencies among non-silent tasks while keeping the graph acyclic

   Each revision appends one schema-valid `process_switch` event with `process: "task-revision"`. The event's `evidence` cites the specific current-text observation that motivated the revision, and its `decision` names the affected task IDs. Revision must not modify or reopen a silent task's result, rewrite already-composed text because composition tasks own prose, introduce task types beyond `reasoning` and `composition`, select or name a writing process, touch `.writing/goals.md`, or emit goal events.
6. Continue the recursive decompose-or-execute loop. A suspended task becomes silent as soon as all of its children are silent, and a task whose subagent call fails its retry becomes silent with a failure note as its result. When the root composition task becomes silent, stop scheduling. Aggregate composition results in dependency and child order and write the final document to `.writing/draft.md`.
7. Append one `process_switch` event to `.writing/trace/process.jsonl` with the trace recipe below for each observable graph action that enters a top-level task state. The trace must never claim that a writing-process choice occurred when only the task graph changed.

Before sending the final response, complete this non-skippable checklist:

1. The root task is `silent`.
2. The aggregated document is written to `.writing/draft.md`.
3. The final response is exactly the contents of `.writing/draft.md`, with nothing before or after it.

The run is `INVALID` unless all three checks pass. Returning the complete text without writing `.writing/draft.md` does not satisfy the contract.

The trace has a variable number of `process_switch` events, at least one for a successful run, one for each observable graph action that enters a top-level task state. Every event's `process` value is exactly one of `task-decomposition`, `task-execution`, or `task-revision`. Name the task ID, type, dependency evidence, and state change in the decision and evidence, and preserve unresolved dependencies or claims in the open-uncertainty list. Do not append goal events or hidden reasoning.

## Trace recipe

You append every trace event yourself, with this command and no other. Run it once per graph action, immediately when that graph action starts, never afterwards and never from a loop or script that writes several events. Change only the first four lines: the `process` token, the decision, the evidence list, and the open-uncertainty list. The command checks the process token and the field types, fills the timestamp and `from_process`, writes valid JSON, and appends nothing when a value is invalid.

```sh
python3 - <<'PY'
process = "task-decomposition"
decision = "Decompose the root composition task into typed child tasks."
evidence = [".writing/baselines/adaptive-task-planning/task-graph.json"]
open_uncertainty = []
allowed = ("task-decomposition", "task-execution", "task-revision")
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

Before the first subagent call, copy the prompt's Assignment, Supplied context, and Requested output constraints sections verbatim into `.writing/baselines/adaptive-task-planning/task.md`. Then run every subagent call this way:

1. Call `multi_agent_v1__spawn_agent` with `fork_context: false` and `message` set to a brief from the template below.
2. To run several calls in parallel, spawn up to five agents, then call `multi_agent_v1__wait_agent` with `targets` listing every open agent and `timeout_ms: 300000`. Call it again while it returns `timed_out: true`, at most three calls per agent.
3. Each time `wait_agent` returns, read every result that has a `completed` status and call `multi_agent_v1__close_agent` with that agent's ID as `target` before the next `wait_agent` or `spawn_agent` call.

Keep at most five agents open at a time. A final status other than `completed` with a non-empty result is a failure: close the agent and spawn the same brief once more, and when the retry also fails, continue without that result and name the gap in the next trace event's evidence. Do not run `codex` in the shell.

```text
You are a <kind> subagent for a writing project. You are not the coordinator. Do not spawn agents, do not run codex, and do not write .writing/trace/process.jsonl.
This is a single-turn task with no interactive user; never ask questions.
Use only the task file and the material in this brief. Do not search the web, fetch URLs, call retrieval tools, or use other external sources.
Task file: .writing/baselines/adaptive-task-planning/task.md holds the assignment, supplied context, and requested output constraints verbatim. Read all of it.
Output language: <the language the assignment requests, or the language of its instructions>. Write all prose in it.
Length: <the target length for this task or segment>
Scope: <the task or segment and its place in the document>
Request: <the work to do, with the plan or dependency results it needs>
Your final message is the result.
```

The adaptation follows WriteHERE[^1]'s released typed task graph, dependency-aware states, recursive decomposition, and interleaved execution semantics. It does not reproduce the original retrieval agent, prompts, models, frontend, benchmark, or graph implementation. The experiment compares task-structure adaptation under a common no-retrieval information policy.

[^1]: Ruibin Xiong, Yimeng Chen, Dmitrii Khizbullin, Mingchen Zhuge, and Jürgen Schmidhuber, "Beyond Outlining: Heterogeneous Recursive Planning for Adaptive Long-form Writing with Language Models," *Proceedings of the 2025 Conference on Empirical Methods in Natural Language Processing* (EMNLP 2025), 2025, https://aclanthology.org/2025.emnlp-main.1254/.
