# Cognitive writing baselines

This package gives experimenters five comparison conditions with the same assignment, supplied context, model settings, output budget, and no-retrieval policy. The `agentic-cognitive-writing` package supplies Agentic CogWriter for the main condition; this package supplies the comparison conditions.

## Install and invoke

Install `cognitive-writing-baselines` from the repository marketplace. Invoke a selected condition with `/cognitive-writing-baselines:<skill-name>` in Claude Code or `$<skill-name>` in Codex. For example, use `/cognitive-writing-baselines:writing-linear` or `$writing-linear` for A2.

The package layout uses [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) for Claude Code and [`.codex-plugin/plugin.json`](.codex-plugin/plugin.json) for Codex.

## Conditions

| Condition | Skill | Fixed behavior | Trace expectation |
| --- | --- | --- | --- |
| A1 Single-pass | `writing-single-shot` | One complete generation pass | One generation event |
| A2 Staged Writing | `writing-linear` | One `Pre-Write`, `Write`, and `Re-Write` pass | Three stage-transition events |
| A3 Adaptive Task Planning | `writing-adaptive-task-planning` | Persisted typed task graph with recursive decomposition, execution, and text-conditioned graph revision | Graph actions and revisions; retrieval is `N/A` |
| B1 CogWriter-style | `writing-cogwriter-style` | Initial plan, immediate plan revision, parallel segment generation, and length review | Top-level stage transitions and observable fallback evidence |
| B2 STORM-style | `writing-storm-style` | Perspective discovery, simulated question answering, outline, per-section draft, and polish | Five stage events; retrieval, evidence, and citation are `N/A` |

## Shared run policy

Every condition reads `.writing/assignment.md` and the supplied context under the same tool, model, budget, and no-retrieval policy. The runner writes observable events to `.writing/trace/process.jsonl`; the final document normally lives at `.writing/draft.md`. Retrieval, evidence gathering, and citation traces are `N/A` for A3 Adaptive Task Planning and B2 STORM-style because the shared policy disables those operations.

## Adaptation caveats

A3 Adaptive Task Planning (`writing-adaptive-task-planning`) is an adaptation of WriteHERE[^3], not a reproduction. Its task-graph behavior follows the [pinned graph implementation](https://github.com/principia-ai/WriteHERE/blob/0b78fcb9ff47305cb098dcb1eec4982024bb34ab/recursive/graph.py) and [pinned execution engine](https://github.com/principia-ai/WriteHERE/blob/0b78fcb9ff47305cb098dcb1eec4982024bb34ab/recursive/engine.py).

B1 CogWriter-style (`writing-cogwriter-style`) remains an exploratory adaptation of CogWriter[^2]. Its behavior follows the [pinned planning implementation](https://github.com/KaiyangWan/CogWriter/blob/dc3bf084e8733c951172cddd89fa4d7337121fdd/CogWriter_model/Agents/PlanningAgent.py) and [pinned generation implementation](https://github.com/KaiyangWan/CogWriter/blob/dc3bf084e8733c951172cddd89fa4d7337121fdd/CogWriter_model/Agents/GenerationAgent.py) for plan revision, parallel segment generation, and length review.

B2 STORM-style (`writing-storm-style`) is a no-retrieval adaptation of STORM[^1]. Its stage mapping follows the [pinned STORM engine](https://github.com/stanford-oval/storm/blob/e80d9bbea7362141a479940dabb751c1f244e4b6/knowledge_storm/storm_wiki/engine.py) and [pinned outline module](https://github.com/stanford-oval/storm/blob/e80d9bbea7362141a479940dabb751c1f244e4b6/knowledge_storm/storm_wiki/modules/outline_generation.py).

## Validation

Run the package-local mechanical validator:

```bash
experiments/baselines/tools/validate-skills.sh
```

The validator checks every skill with the pinned quick validators. Model judging is outside this package command.

[^1]: Yijia Shao, Yucheng Jiang, Theodore A. Kanell, Peter Xu, Omar Khattab, and Monica S. Lam, "Assisting in Writing Wikipedia-like Articles From Scratch with Large Language Models," *Proceedings of NAACL-HLT* (2024), [ACL Anthology](https://aclanthology.org/2024.naacl-long.347/) and [arXiv](https://arxiv.org/abs/2402.14207v2).
[^2]: Kaiyang Wan, Honglin Mu, Rui Hao, Haoran Luo, Tianle Gu, and Xiuying Chen, "A Cognitive Writing Perspective for Constrained Long-Form Text Generation," *Findings of ACL* (2025), [ACL Anthology](https://aclanthology.org/2025.findings-acl.511/) and [arXiv](https://arxiv.org/abs/2502.12568v3).
[^3]: Ruibin Xiong, Yimeng Chen, Dmitrii Khizbullin, Mingchen Zhuge, and Jürgen Schmidhuber, "Beyond Outlining: Heterogeneous Recursive Planning for Adaptive Long-form Writing with Language Models," *Proceedings of EMNLP* (2025), [ACL Anthology](https://aclanthology.org/2025.emnlp-main.1254/) and [arXiv](https://arxiv.org/abs/2503.08275v3).
