# Agentic CogWriter experiment variants

The Agentic CogWriter experiment package gives experimenters two skills for comparing writing-process choices: `cognitive-writing-fixed-order` fixes the process order, and `cognitive-writing-no-goal-network` removes the hierarchical goal network.

The variants write to the project's `.writing/` directory and require the main `agentic-cognitive-writing` package. Claude delegates through the main package's bundled agents, while Codex delegates to native subagents that use the shared role skills.

The package ships a Claude Code manifest at [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) and a Codex manifest at [`.codex-plugin/plugin.json`](.codex-plugin/plugin.json); each manifest packages the two skill directories under [`skills/`](skills/).

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

- `cognitive-writing-fixed-order` runs `Planning`, `Translating`, and `Reviewing` in a fixed order on each pass. Generate and Evaluate may interrupt the order, after which the `Monitor` returns to the prescribed sequence.
- `cognitive-writing-no-goal-network` treats the assignment as one implicit objective, leaves `.writing/goals.md` untouched, and traces process switches.

## Invoke a variant

In Claude Code, invoke `/cognitive-writing-experiments:cognitive-writing-fixed-order` or `/cognitive-writing-experiments:cognitive-writing-no-goal-network`. In Codex, invoke `$cognitive-writing-fixed-order` or `$cognitive-writing-no-goal-network`.

Read the [project repository](https://github.com/shunk031/agentic-cognitive-writing) for the main plugin README, shared `.writing/` state layout, trace contract, research protocol, and experiment context.
