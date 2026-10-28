---
name: writing-cogwriter-style
description: "Exploratory CogWriter-style adaptation. Produce and immediately revise a structured plan, generate document segments in parallel with native subagents, and run a per-segment length-review loop without a goal network."
---

# CogWriter[^1]-style writing

Run a CogWriter[^1]-style adaptation, not a reproduction. The fixed top-level order is:

`initial planning -> immediate plan revision -> parallel segment generation -> length review`

The adaptation follows the published behavior of a structured Planning Agent followed by Generation Agents. The initial planning pass creates a structured plan with ordered document segments and requirements. The immediate plan-revision pass checks that plan against the assignment and returns one revised, normalized plan. Native subagents then generate the segments in parallel. Each segment subagent receives the complete revised plan, the assignment, the supplied context, and its local segment plan. Each segment then enters the length-review loop, which expands or compresses it toward its target length while preserving meaning and coherence. The coordinator assembles the segments in plan order into the final document.

## Equal-information and no-retrieval policy

The runner gives this condition the same assignment, supplied context, context-window policy, timeout, model family, total output budget, and attempt budget as every comparison condition. Parallelism changes scheduling, not the amount or kind of information available to a subagent.

The coordinator and every subagent may use only the task in `.writing/task.md`, the persisted plan, and outputs produced by this run. No actor may browse, search, call a retrieval tool, access the Internet, or use an external source. If the supplied context does not establish a claim, preserve the uncertainty or omit the claim.

This adaptation has no goal network. Do not create or modify `.writing/goals.md`, emit no goal events, and do not treat the structured document plan as a replacement goal file. The plan exists only to condition segment generation and is persisted at `.writing/baselines/cogwriter-style/plan.json` for run inspection.

The user owns rhetorical intent, factual authority, final wording, and publication. The coordinator owns the fixed top-level order, subagent dispatch, and assembly. Planning and generation subagents own their artifacts. A native subagent must not launch a nested `codex exec` process or spawn an agent.

## Delegation

Delegate each planning pass and each segment to a fresh agent: `spawn_agent` with `fork_context` false and a message that begins with "Read the skill file at plugin/skills/cogwriter-planning/SKILL.md and follow it." or "Read the skill file at plugin/skills/cogwriter-generation/SKILL.md and follow it.", followed by the pass or the segment ID. Keep at most four agents open at a time, below Codex's limit of six open agents: `wait` for the agents spawned and `close_agent` each one before spawning more.

## Procedure

1. Read `.writing/task.md`. Do not read or modify `.writing/goals.md`.
2. Run exactly one initial-planning pass with a planning agent. It writes a structured plan with an ordered list of segment IDs, each segment's purpose, required content, integer target word count, dependencies, and whole-document constraints to `.writing/baselines/cogwriter-style/plan-initial.json`.
3. Run exactly one immediate plan-revision pass with a fresh planning agent. It checks the complete initial plan against the task and writes one revised, normalized plan to `.writing/baselines/cogwriter-style/plan.json`, without a second planning pass.
4. Run parallel segment generation: one segment agent per revised segment. Every segment agent reads the complete plan, not only its local item, together with the task. A segment agent may perform one local plan adjustment before writing, but it must not change the top-level order or invent a new process. It writes its segment to `.writing/baselines/cogwriter-style/segments/<segment ID>.md`.
5. Each segment agent then runs the length-review loop on its own segment: while the segment's word count, by CogWriter's counting rule, is more than 10% away from its target length, it expands or compresses the segment toward the target while preserving meaning and coherence. Length review is not a general content review or a retrieval pass.
6. Write `.writing/draft.md` by concatenating the segment files in plan order with one shell command, without retyping them. The draft is the final document.

The adaptation does not claim to reproduce CogWriter[^1]'s original models, prompts, dataset, token limits, monitoring implementation, or reported results. The adaptation preserves the published control-flow ideas needed for this comparison and makes the platform, input, budget, and no-retrieval differences explicit.

[^1]: Kaiyang Wan, Honglin Mu, Rui Hao, Haoran Luo, Tianle Gu, and Xiuying Chen, "A Cognitive Writing Perspective for Constrained Long-Form Text Generation," *Findings of the Association for Computational Linguistics: ACL 2025* (Findings of ACL 2025), 2025, https://doi.org/10.18653/v1/2025.findings-acl.511.
