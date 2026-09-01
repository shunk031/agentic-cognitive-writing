# Cognitive writing process

`cognitive-writing-process` is a cross-platform plugin skeleton for Claude Code and OpenAI Codex. It operationalizes Flower and Hayes' 1981 cognitive process theory as a Monitor skill that coordinates Planning, Translating, and Reviewing. The plugin keeps the writing project's task environment and long-term memory in files owned by the user.

## Install

### Claude Code

For a local marketplace install, run Claude Code from the repository root and add the included marketplace:

```text
/plugin marketplace add .
/plugin install cognitive-writing-process@agentic-cognitive-writing-process
```

For a one-off local session, point Claude Code at the distributable plugin directory:

```bash
claude --plugin-dir /absolute/path/to/agentic-cognitive-writing-process/plugin
```

Claude loads the manifest from `plugin/.claude-plugin/plugin.json`, discovers the component directories at the plugin root, and namespaces the skill as `/cognitive-writing-process:cognitive-writing-process`.

### OpenAI Codex

Codex reads the plugin manifest at `plugin/.codex-plugin/plugin.json`. For a local repo marketplace, copy the distributable directory into the host repository's plugin directory, then add a Codex marketplace file:

```bash
mkdir -p ./plugins
cp -R /absolute/path/to/agentic-cognitive-writing-process/plugin ./plugins/cognitive-writing-process
mkdir -p ./.agents/plugins
```

Create `$REPO_ROOT/.agents/plugins/marketplace.json` with an entry like this:

```json
{
  "name": "local-writing-plugins",
  "interface": { "displayName": "Local writing plugins" },
  "plugins": [
    {
      "name": "cognitive-writing-process",
      "source": { "source": "local", "path": "./plugins/cognitive-writing-process" },
      "policy": { "installation": "AVAILABLE", "authentication": "ON_INSTALL" },
      "category": "Productivity"
    }
  ]
}
```

Register the marketplace, then install the plugin as a separate step. The Codex CLI help confirms the `PLUGIN@MARKETPLACE` selector syntax:

```bash
codex plugin marketplace add .
codex plugin add cognitive-writing-process@local-writing-plugins
```

You can also select the plugin from the Codex or ChatGPT desktop Plugins Directory after registering the marketplace. For a personal install, copy the plugin to `~/.codex/plugins/cognitive-writing-process` and use `~/.agents/plugins/marketplace.json` with `"path": "./.codex/plugins/cognitive-writing-process"`; Codex resolves that path relative to the marketplace root. Restart the desktop app after changing a local marketplace. Codex uses the shared `plugin/skills/` tree; the Claude-only `plugin/agents/*.md` files document the native Claude roles, while the skill asks Codex to delegate those roles to native Codex subagents.

## Theory-to-architecture mapping

The mapping interprets Figure 1 of Flower and Hayes. It is an implementation of the theory, not a claim that the paper specifies plugin files.

| Figure 1 model element | Plugin artifact |
| --- | --- |
| Task environment | User project `.writing/assignment.md` and `.writing/draft.md` |
| Rhetorical problem: topic, audience, exigency | Sections in `.writing/assignment.md` |
| Produced text | User project `.writing/draft.md` |
| Writer's long-term memory: topic and audience knowledge | User project `.writing/memory/` |
| Writer's long-term memory: writing plans | Notes and plans in `.writing/memory/` plus `.writing/goals.md` |
| Planning | Main Monitor skill plus `plugin/agents/planner.md` |
| Generating ideas | Planner's embedded Generate sub-process |
| Organizing ideas and presentation | Planner's embedded Organize sub-process |
| Goal-setting | Planner's embedded Goal-setting sub-process and `.writing/goals.md` |
| Translating | `plugin/agents/translator.md` |
| Reviewing | `plugin/agents/reviewer.md` |
| Evaluating | Reviewer's embedded Evaluate sub-process |
| Revising | Reviewer's embedded Revise sub-process |
| Monitor | `plugin/skills/cognitive-writing-process/SKILL.md`, executed by the main agent |

The Monitor treats these processes as a recursive toolkit. Generate and Evaluate may interrupt any process, and a resolved sub-goal returns control to its parent goal.

## User project state

The plugin creates or maintains this layout in the project where it is used:

```text
.writing/
├── assignment.md       # topic, audience, exigency, writer's goals, constraints
├── goals.md            # hierarchical goal network and history
├── draft.md            # growing text
├── memory/
│   ├── topic.md        # optional topic knowledge
│   ├── audience.md     # optional audience knowledge
│   └── plans.md        # optional reusable writing plans
└── trace/
    └── process.jsonl   # append-only process log
```

The plugin has no runtime dependency on files elsewhere in this repository. It does create and maintain `.writing/` in the user's writing project. That directory belongs to the user and should not be committed unless the user chooses to share the writing process.

See [`skills/cognitive-writing-process/references/goals-format.md`](skills/cognitive-writing-process/references/goals-format.md) for goal notation and [`skills/cognitive-writing-process/references/ablation-variants.md`](skills/cognitive-writing-process/references/ablation-variants.md) for experiment settings.

## Trace JSONL schema

The Monitor appends one valid JSON object per line to `.writing/trace/process.jsonl`. Each line records the responsible actor, process, decision, evidence, and open uncertainty. The required fields are:

| Field | Meaning |
| --- | --- |
| `timestamp` | ISO 8601 timestamp with timezone |
| `event_type` | `process_switch`, `goal_created`, `goal_developed`, or `goal_regenerated` |
| `responsible_agent` | `monitor`, `planner`, `translator`, `reviewer`, or `user` |
| `process` | Process that owns the decision |
| `decision` | Action or rationale in plain language |
| `evidence` | Array of concrete supporting observations or project-relative files |
| `open_uncertainty` | Array of unresolved questions or unsupported claims |

Process switches also include `from_process` and `to_process`. Goal events include `goal_id` and `parent_goal_id`. Optional `artifacts` lists changed files and `ablation` names the active experiment variant.

Example line:

```json
{"timestamp":"2026-01-15T09:00:00+09:00","event_type":"process_switch","responsible_agent":"monitor","process":"planning","from_process":"translating","to_process":"reviewing","decision":"Review the opening after it conflicted with the audience goal.","evidence":[".writing/draft.md: opening uses internal jargon",".writing/goals.md: G1 requires a first-time reader explanation"],"open_uncertainty":["Whether to keep the technical term with a definition"],"goal_id":"G1","parent_goal_id":"G0","artifacts":[".writing/draft.md",".writing/goals.md"]}
```

The field-by-field contract lives in [`skills/cognitive-writing-process/references/trace-jsonl-schema.md`](skills/cognitive-writing-process/references/trace-jsonl-schema.md).

## Evaluation seed

The seed prompts for realistic writing tasks are in [`skills/cognitive-writing-process/evals/evals.json`](skills/cognitive-writing-process/evals/evals.json). They cover initial planning and drafting, review with possible goal regeneration, and the no-goal-network ablation.

## Sources and scope

The plugin follows the shared `SKILL.md` format supported by both hosts. Claude plugin structure and local marketplace behavior are documented in the [Claude Code plugins documentation](https://code.claude.com/docs/en/plugins) and [Claude Code marketplace documentation](https://code.claude.com/docs/en/plugin-marketplaces). Codex plugin packaging and local marketplace behavior are documented in [OpenAI's plugin packaging guide](https://developers.openai.com/plugins/build/plugins) and [Codex skill packaging guide](https://developers.openai.com/plugins/build/skills). The direct implementation patterns consulted were Anthropic's [`feature-dev` plugin manifest](https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/.claude-plugin/plugin.json), its [`code-explorer` agent](https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/agents/code-explorer.md), OpenAI's [`build-web-apps` Codex manifest](https://github.com/openai/plugins/blob/main/plugins/build-web-apps/.codex-plugin/plugin.json), and its [`frontend-app-builder` skill](https://github.com/openai/plugins/blob/main/plugins/build-web-apps/skills/frontend-app-builder/SKILL.md).
