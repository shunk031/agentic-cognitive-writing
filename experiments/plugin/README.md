# Agentic CogWriter experiment variants

The `Agentic CogWriter` experiment package gives experimenters four skills for comparing writing-process choices: `cognitive-writing-fixed-order` fixes the process order, `cognitive-writing-no-goal-network` removes the explicit goals, `cognitive-writing-single-writer` keeps one Writer with a live goal network, and `cognitive-writing-single-context` runs the processes without subagents.

The variants write to the project's `.writing/` directory and require the main `agentic-cognitive-writing` package. A6 delegates through the main package's role skills, and A5 through its own copies of them in the `no-goal-planning`, `no-goal-translating`, and `no-goal-reviewing` skill directories; A7 keeps the main agent as the sole Writer; A8 runs the role skills' processes in the main agent's context.

The package ships a Claude Code manifest at [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) and a Codex manifest at [`.codex-plugin/plugin.json`](.codex-plugin/plugin.json); each manifest packages the skill directories under [`skills/`](skills/).

## Install the required packages

Install the [`agentic-cognitive-writing` package](https://github.com/shunk031/agentic-cognitive-writing) before installing this package. If the repository is private, GitHub installs require access to it.

### Claude Code

1. Add the repository marketplace:

   ```text
   /plugin marketplace add shunk031/agentic-cognitive-writing
   ```

2. Install the main plugin:

   ```text
   /plugin install agentic-cognitive-writing@agentic-cognitive-writing-process
   ```

3. Install the experiment package:

   ```text
   /plugin install cognitive-writing-experiments@agentic-cognitive-writing-process
   ```

### OpenAI Codex

1. Add the repository marketplace:

   ```bash
   codex plugin marketplace add shunk031/agentic-cognitive-writing
   ```

2. Install the main plugin:

   ```bash
   codex plugin add agentic-cognitive-writing@agentic-cognitive-writing-process
   ```

3. Install the experiment package:

   ```bash
   codex plugin add cognitive-writing-experiments@agentic-cognitive-writing-process
   ```

## Choose a variant

Use these skills only for controlled comparisons. They are not recommended defaults.

The variants' seed prompts live beside the skills in [`skills/`](skills/).

- `cognitive-writing-fixed-order` is the main package's `Monitor` skill with a fixed order: each pass delegates `Planning`, `Translating`, and `Reviewing` in that order, and the `Monitor` stops only after `Reviewing`.
- `cognitive-writing-no-goal-network` is the main package's `Monitor` skill without the goals file: the task is the single implicit objective, the Planner reports its organization of the material instead of writing goals, and the `Monitor` copies that organization into later `Translating` scopes. The runner stages the A5 role copies under the shared role names and installs the A5 Codex agent definitions from [`no-goal-agents/`](no-goal-agents/) in place of the main package's, whose descriptions are written in goal terms.
- `cognitive-writing-single-writer` runs the main agent as one Writer, composes at sentence level, and traces its live goal network.
- `cognitive-writing-single-context` is the main package's `Monitor` skill followed by the three role skills verbatim: the `Monitor` runs each selected process in its own context instead of spawning an agent.

## Invoke a variant

In Claude Code, invoke `/cognitive-writing-experiments:cognitive-writing-fixed-order`, `/cognitive-writing-experiments:cognitive-writing-no-goal-network`, `/cognitive-writing-experiments:cognitive-writing-single-writer`, or `/cognitive-writing-experiments:cognitive-writing-single-context`. In Codex, invoke `$cognitive-writing-fixed-order`, `$cognitive-writing-no-goal-network`, `$cognitive-writing-single-writer`, or `$cognitive-writing-single-context`.

Read the [project repository](https://github.com/shunk031/agentic-cognitive-writing) for the main plugin README, shared `.writing/` state layout, trace contract, research protocol, and experiment context.
