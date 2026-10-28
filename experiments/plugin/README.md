# Agentic CogWriter experiment variants

The `Agentic CogWriter` experiment package gives experimenters five skills for comparing writing-process choices: `cognitive-writing-fixed-order` fixes the process order, `cognitive-writing-fixed-order-skip` adds a rule that skips `Translating` to that order, `cognitive-writing-task-objective` removes the explicit goals, `cognitive-writing-single-context` runs the processes without subagents, and `cognitive-writing-single-writer` also limits each `Translating` step to one paragraph.

The variants write to the project's `.writing/` directory and require the main `agentic-cognitive-writing` package. A6 delegates through the main package's role skills, and A5 through its own copies of them in the `task-objective-planning`, `task-objective-translating`, and `task-objective-reviewing` skill directories; A7 and A8 run the role skills' processes in the main agent's context.

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
- `cognitive-writing-fixed-order-skip` is `cognitive-writing-fixed-order` with two sentences added to its step 2: the `Monitor` skips `Translating` when the latest `Planning` report added no goal that lacks prose, and the pass continues with `Reviewing`.
- `cognitive-writing-task-objective` is the main package's `Monitor` skill without the goals file: the task is the single implicit objective, the Planner reports its organization of the material instead of writing goals, and the `Monitor` appends that organization, as reported, after later `Translating` scopes. The runner stages the A5 role copies under the shared role names and installs the A5 Codex agent definitions from [`task-objective-agents/`](task-objective-agents/) in place of the main package's, whose descriptions are written in goal terms.
- `cognitive-writing-single-writer` is `cognitive-writing-single-context` with one paragraph per `Translating` step: the `Monitor`'s list of the kinds of work and the `Translating` section say one paragraph instead of prose, and the `Monitor` gives every `Translating` step a one-paragraph scope.
- `cognitive-writing-single-context` is the main package's `Monitor` skill followed by the three role skills verbatim: the `Monitor` runs each selected process in its own context instead of spawning an agent.

## Invoke a variant

In Claude Code, invoke `/cognitive-writing-experiments:cognitive-writing-fixed-order`, `/cognitive-writing-experiments:cognitive-writing-fixed-order-skip`, `/cognitive-writing-experiments:cognitive-writing-task-objective`, `/cognitive-writing-experiments:cognitive-writing-single-writer`, or `/cognitive-writing-experiments:cognitive-writing-single-context`. In Codex, invoke `$cognitive-writing-fixed-order`, `$cognitive-writing-fixed-order-skip`, `$cognitive-writing-task-objective`, `$cognitive-writing-single-writer`, or `$cognitive-writing-single-context`.

Read the [project repository](https://github.com/shunk031/agentic-cognitive-writing) for the main plugin README, shared `.writing/` state layout, trace contract, research protocol, and experiment context.
