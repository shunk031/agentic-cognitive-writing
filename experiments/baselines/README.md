# Cognitive writing baselines

This package gives experimenters five writing conditions that share one assignment, supplied context, model configuration, output budget, and no-retrieval policy. The package is experimental infrastructure. It does not replace Agentic CogWriter, whose package identifier is `agentic-cognitive-writing` and whose skill identifier is `agentic-cog-writer`.

## Conditions

| Condition | Skill | Fixed behavior | Trace expectation |
| --- | --- | --- | --- |
| A1 | `writing-single-shot` | One complete generation pass | One generation event |
| A2 | `writing-linear` | One `Pre-Write`, `Write`, and `Re-Write` pass | Three stage-transition events |
| A3 | `writing-storm-style` | Perspective discovery, simulated question answering, outline, per-section draft, and polish | Five stage events; retrieval, evidence, and citation are `N/A` |
| CogWriter-style adaptation | `writing-cogwriter-style` | Initial plan, immediate plan revision, parallel segment generation, and length review | Top-level stage transitions and observable fallback evidence |
| WriteHERE-style adaptation | `writing-writehere-style` | Persisted typed task graph with recursive decomposition and execution | Graph actions; retrieval is `N/A` |

The runner writes schema-valid JSON Lines to `.writing/trace/process.jsonl`. The baseline events use the shared `process_switch` event shape because the schema defines no separate generation or stage event type. Baseline skills do not emit goal events. The two exploratory adaptations leave `.writing/goals.md` untouched and persist their own plan or task-graph files under `.writing/baselines/`.

## Install and invoke

The package exposes a Claude Code adapter and a Codex adapter through the dual manifests in [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) and [`.codex-plugin/plugin.json`](.codex-plugin/plugin.json).

After the marketplace entry is wired, install `cognitive-writing-baselines` from the repository marketplace. Invoke a condition with `/cognitive-writing-baselines:<skill-name>` in Claude Code or `$<skill-name>` in Codex. For example, use `/cognitive-writing-baselines:writing-linear` or `$writing-linear` for A2.

Use these skills only when the runner or experimenter has selected the matching condition. The runner owns equal budgets, attempt limits, trace paths, and no-retrieval enforcement. A skill must not silently add a tool, a source, a stage, or an extra attempt.

## Shared run policy

Every condition reads `.writing/assignment.md` and the supplied context. No condition may browse, search, retrieve, or use an unprovided source. All conditions receive the same tool policy and context. The final document normally lives at `.writing/draft.md`; condition-specific intermediate artifacts live under `.writing/baselines/` when the skill specifies them.

The experiment protocol treats traces as observable action records, not transcripts of private cognition. The skills therefore record only stage or graph actions that the runner can observe. Missing evidence remains an uncertainty. Retrieval, evidence gathering, and citation traces are explicitly `N/A` for A3 and the WriteHERE-style adaptation because the common policy disables those operations.

## Research basis and fidelity limits

The A3 mapping follows **STORM**[^1]'s released separation of perspective-guided question asking, simulated conversation, outline creation, section-oriented writing, and polishing. The [pinned STORM engine](https://github.com/stanford-oval/storm/blob/e80d9bbea7362141a479940dabb751c1f244e4b6/knowledge_storm/storm_wiki/engine.py) and [pinned outline module](https://github.com/stanford-oval/storm/blob/e80d9bbea7362141a479940dabb751c1f244e4b6/knowledge_storm/storm_wiki/modules/outline_generation.py) show the released module order. The experiment omits STORM's Internet research, references, and citation generation because equal information forbids retrieval. A3 is therefore STORM-style, not the full retrieval system.

The CogWriter adaptation follows **CogWriter**[^2]'s published initial-plan, plan-revision, per-segment generation, and length-revision behavior. The [pinned planning implementation](https://github.com/KaiyangWan/CogWriter/blob/dc3bf084e8733c951172cddd89fa4d7337121fdd/CogWriter_model/Agents/PlanningAgent.py) revises a structured plan immediately, while the [pinned generation implementation](https://github.com/KaiyangWan/CogWriter/blob/dc3bf084e8733c951172cddd89fa4d7337121fdd/CogWriter_model/Agents/GenerationAgent.py) processes segment units concurrently and revises length. The package calls this a CogWriter-style adaptation because it uses native subagents, generic document sections, shared experiment budgets, and no goal network rather than reproducing the released prompts, models, benchmark, or runtime.

The WriteHERE adaptation follows **WriteHERE**[^3]'s typed task graph, dependency-aware states, recursive decomposition, and interleaved planning and execution. The [pinned graph implementation](https://github.com/principia-ai/WriteHERE/blob/0b78fcb9ff47305cb098dcb1eec4982024bb34ab/recursive/graph.py) defines typed nodes, dependencies, statuses, and graph persistence, while the [pinned execution engine](https://github.com/principia-ai/WriteHERE/blob/0b78fcb9ff47305cb098dcb1eec4982024bb34ab/recursive/engine.py) schedules and advances graph tasks. The adaptation disables retrieval and restricts types to reasoning and composition. The adaptation changes task structure only; it never selects a writing-process policy.

## Validation

Run the package-local mechanical validator:

```bash
experiments/baselines/tools/validate-skills.sh
```

The script follows the main package's pinned Anthropic and OpenAI quick validators and validates every skill under `experiments/baselines/skills/`. The `evals/evals.json` files document condition checks for later evaluation. Model-judge execution is outside this package validation command.

## Marketplace wiring

The root marketplace files currently live on the plugin branch rather than this branch's `main` ancestry. After merging the package, add these entries to `.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json` beside the existing package entries.

Claude Code marketplace entry:

```json
{
  "name": "cognitive-writing-baselines",
  "source": "./experiments/baselines"
}
```

Codex marketplace entry:

```json
{
  "name": "cognitive-writing-baselines",
  "source": {
    "source": "local",
    "path": "./experiments/baselines"
  },
  "policy": {
    "installation": "AVAILABLE",
    "authentication": "ON_INSTALL"
  },
  "category": "Productivity"
}
```

[^1]: Yijia Shao, Yucheng Jiang, Theodore A. Kanell, Peter Xu, Omar Khattab, and Monica S. Lam, "Assisting in Writing Wikipedia-like Articles From Scratch with Large Language Models," *Proceedings of NAACL-HLT* (2024), [ACL Anthology](https://aclanthology.org/2024.naacl-long.347/) and [arXiv](https://arxiv.org/abs/2402.14207v2).
[^2]: Kaiyang Wan, Honglin Mu, Rui Hao, Haoran Luo, Tianle Gu, and Xiuying Chen, "A Cognitive Writing Perspective for Constrained Long-Form Text Generation," *Findings of ACL* (2025), [ACL Anthology](https://aclanthology.org/2025.findings-acl.511/) and [arXiv](https://arxiv.org/abs/2502.12568v3).
[^3]: Ruibin Xiong, Yimeng Chen, Dmitrii Khizbullin, Mingchen Zhuge, and Jürgen Schmidhuber, "Beyond Outlining: Heterogeneous Recursive Planning for Adaptive Long-form Writing with Language Models," *Proceedings of EMNLP* (2025), [ACL Anthology](https://aclanthology.org/2025.emnlp-main.1254/) and [arXiv](https://arxiv.org/abs/2503.08275v3).
