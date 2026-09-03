# Cognitive writing baselines

This package gives experimenters five baseline and exploratory conditions with the same assignment, supplied context, model settings, output budget, and no-retrieval policy. The `agentic-cognitive-writing` package supplies Agentic CogWriter for the main condition; this package supplies the comparison conditions.

## Install and invoke

Install `cognitive-writing-baselines` from the repository marketplace. Invoke a selected condition with `/cognitive-writing-baselines:<skill-name>` in Claude Code or `$<skill-name>` in Codex. For example, use `/cognitive-writing-baselines:writing-linear` or `$writing-linear` for A2.

## Conditions

| Condition | Skill | Fixed behavior | Trace expectation |
| --- | --- | --- | --- |
| A1 | `writing-single-shot` | One complete generation pass | One generation event |
| A2 | `writing-linear` | One `Pre-Write`, `Write`, and `Re-Write` pass | Three stage-transition events |
| A3 | `writing-storm-style` | Perspective discovery, simulated question answering, outline, per-section draft, and polish | Five stage events; retrieval, evidence, and citation are `N/A` |
| CogWriter-style adaptation | `writing-cogwriter-style` | Initial plan, immediate plan revision, parallel segment generation, and length review | Top-level stage transitions and observable fallback evidence |
| WriteHERE-style adaptation | `writing-writehere-style` | Persisted typed task graph with recursive decomposition and execution | Graph actions; retrieval is `N/A` |

## Shared run policy

Every condition reads `.writing/assignment.md` and the supplied context under the same tool, model, budget, and no-retrieval policy. The runner writes observable events to `.writing/trace/process.jsonl`; the final document normally lives at `.writing/draft.md`. Retrieval, evidence gathering, and citation traces are `N/A` for A3 and the WriteHERE-style adaptation because the shared policy disables those operations.

## Adaptation caveats

`writing-storm-style` is a no-retrieval STORM[^1] adaptation. `writing-cogwriter-style` and `writing-writehere-style` are exploratory adaptations of CogWriter[^2] and WriteHERE[^3], not reproductions. The shared policy keeps inputs and budgets equal and disables retrieval and citation generation; each skill documents its operational stages and trace rules.

## Validation

Run the package-local mechanical validator:

```bash
experiments/baselines/tools/validate-skills.sh
```

The validator checks every skill with the pinned quick validators. Model judging is outside this package command.

[^1]: Yijia Shao, Yucheng Jiang, Theodore A. Kanell, Peter Xu, Omar Khattab, and Monica S. Lam, "Assisting in Writing Wikipedia-like Articles From Scratch with Large Language Models," *Proceedings of NAACL-HLT* (2024), [ACL Anthology](https://aclanthology.org/2024.naacl-long.347/) and [arXiv](https://arxiv.org/abs/2402.14207v2).
[^2]: Kaiyang Wan, Honglin Mu, Rui Hao, Haoran Luo, Tianle Gu, and Xiuying Chen, "A Cognitive Writing Perspective for Constrained Long-Form Text Generation," *Findings of ACL* (2025), [ACL Anthology](https://aclanthology.org/2025.findings-acl.511/) and [arXiv](https://arxiv.org/abs/2502.12568v3).
[^3]: Ruibin Xiong, Yimeng Chen, Dmitrii Khizbullin, Mingchen Zhuge, and Jürgen Schmidhuber, "Beyond Outlining: Heterogeneous Recursive Planning for Adaptive Long-form Writing with Language Models," *Proceedings of EMNLP* (2025), [ACL Anthology](https://aclanthology.org/2025.emnlp-main.1254/) and [arXiv](https://arxiv.org/abs/2503.08275v3).
