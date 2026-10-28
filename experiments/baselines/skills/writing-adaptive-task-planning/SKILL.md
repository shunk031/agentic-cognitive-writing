---
name: writing-adaptive-task-planning
description: "Confirmatory condition A3 (Adaptive Task Planning). Build and persist a typed reasoning/composition task graph, recursively decompose and execute tasks with subagents, and revise the graph from aggregated text while keeping adaptation on task structure rather than writing-process selection."
---

# Adaptive Task Planning

Run confirmatory condition A3, Adaptive Task Planning, as an adaptation of WriteHERE[^1]'s heterogeneous recursive planning, not a reproduction. The coordinator dynamically builds a directed acyclic task graph in project files and interleaves recursive decomposition with execution. The root task is a composition task for the complete document. Child tasks may be reasoning tasks for requirements, structure, consistency, or argument development and composition tasks for section or document writing. The coordinator schedules ready tasks by graph state and dependency order, then persists the graph after every change.

The condition changes task structure only. The coordinator must not adapt by selecting among named writing processes, replacing a task graph with a fixed process pipeline, or using a meta-process chooser. The distinction is the experimental point: Adaptive Task Planning concerns what tasks exist and how they depend on one another, not which writing workflow is selected.

## Equal-information and no-retrieval policy

The runner gives this condition the same assignment, supplied context, context-window policy, timeout, model settings, total output budget, and attempt budget as every comparison condition. The graph may change shape in response to the assignment and task results, but no task may obtain information unavailable to the other conditions.

Retrieval tasks are disabled under the equal-information policy. The graph may contain only `reasoning` and `composition` task types. Do not create a retrieval node, browse, search, call a retrieval tool, access the Internet, or use an external source. The runner records retrieval, evidence gathering, and citation handling as `N/A` in the run accounting by design. A missing fact remains uncertain or is omitted.

This adaptation uses the task graph as its only planning structure. Do not create or modify `.writing/goals.md` and emit no goal events. The user owns rhetorical intent, factual authority, final wording, and publication. The coordinator owns graph state, ready-task scheduling, subagent dispatch, and persistence. Decomposition agents own their atomicity verdicts and proposed child tasks, and execution agents own their reasoning or composition results. A native subagent must not launch a nested `codex exec` process or spawn an agent.

## Delegation

Delegate each decomposition and each execution to a fresh agent: `spawn_agent` with `fork_context` false and a message that begins with "Read the skill file at plugin/skills/task-decomposition/SKILL.md and follow it." or "Read the skill file at plugin/skills/task-execution/SKILL.md and follow it.", followed by the task's ID, type, and goal, its parent's goal, and the paths of its dependency results. Then `wait` for the agent and `close_agent` it before spawning the next one.

## Persisted graph contract

Persist the graph at `.writing/baselines/adaptive-task-planning/task-graph.json`. Keep the file valid JSON after every mutation. The top-level object includes `version`, `root_task_id`, `tasks`, and `updated_at`. Each task includes:

- `id`, a stable project-local identifier
- `type`, exactly `reasoning` or `composition`
- `goal`, the task objective
- `length`, the target length of a composition task, or `null` for a reasoning task
- `dependencies`, a list of task IDs that must finish first
- `status`, one of `active`, `suspended`, or `silent`
- `result`, either `null` or the task's returned result
- `parent_id`, the containing task ID or `null` for the root
- `children`, an ordered list of child task IDs

Store task results under `.writing/baselines/adaptive-task-planning/results/` when they are too large for the graph file. Use project-relative paths in the graph. A suspended task has been decomposed or is waiting for dependencies. An active task is ready for planning or execution. A silent task has completed or failed and will not be scheduled again.

## Procedure

1. Read the task in `.writing/task.md`. Initialize a root `composition` task if the graph does not exist. Do not read or modify `.writing/goals.md`.
2. Select the active task nearest the root by breadth-first depth, breaking ties with the graph's stable task order. A task is ready when every dependency is `silent`.
3. As in WriteHERE's report mode, a `reasoning` task is atomic, and so is a composition task at depth 3 or deeper, where the root is at depth 0; neither goes to a decomposition agent. Delegate every other newly selected composition task, the root and each child alike, to a decomposition agent, which judges whether the task is atomic. If the task is not atomic, the agent returns typed child tasks and dependencies. Add the children to the graph, with each composition child depending on every composition child before it so that prose is appended in document order, mark the parent `suspended`, and persist the graph before scheduling another task. Such a task executes only after a decomposition agent has judged it atomic.
4. If the task is atomic, delegate it to an execution agent. A reasoning execution writes a bounded reasoning or planning artifact to its result file. A composition execution appends its prose to `.writing/draft.md`. Record the result, mark the task `silent`, and persist the graph. A `suspended` task becomes `silent` when all of its children are `silent`.
5. After each composition task completes, re-read the current aggregated text in `.writing/draft.md`. Before scheduling the next task, the coordinator may perform text-conditioned graph revision. Allowed revision operations are:
   - revise the goal text of an active or suspended task
   - add new typed child tasks with dependencies under any non-silent task
   - retire an active or suspended task by marking it `silent` with a result that notes the retirement
   - add or reorder dependencies among non-silent tasks while keeping the graph acyclic

   Revision must not modify or reopen a silent task's result, rewrite already-composed text because composition tasks own prose, introduce task types beyond `reasoning` and `composition`, select or name a writing process, touch `.writing/goals.md`, or emit goal events.
6. Continue the recursive decompose-or-execute loop until the root task is `silent`. The text in `.writing/draft.md` is then the final document.

The adaptation follows WriteHERE[^1]'s released typed task graph, dependency-aware states, recursive decomposition, and interleaved execution semantics. It does not reproduce the original retrieval agent, prompts, models, frontend, benchmark, or graph implementation. The experiment compares task-structure adaptation under a common no-retrieval information policy.

[^1]: Ruibin Xiong, Yimeng Chen, Dmitrii Khizbullin, Mingchen Zhuge, and Jürgen Schmidhuber, "Beyond Outlining: Heterogeneous Recursive Planning for Adaptive Long-form Writing with Language Models," *Proceedings of the 2025 Conference on Empirical Methods in Natural Language Processing* (EMNLP 2025), 2025, https://aclanthology.org/2025.emnlp-main.1254/.
