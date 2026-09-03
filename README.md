# Agentic CogWriter

Agentic CogWriter is a writing assistant that plans, drafts, and revises long-form text the way human writers do. The assistant keeps its goals, drafts, notes, and decision log as files in the directory where you write. Instead of generating text in one pass, the assistant revisits and rewrites its own plans and goals as the draft develops.

Agentic CogWriter realizes the writing model in ["A Cognitive Process Theory of Writing"](https://www.jstor.org/stable/356600)[^1] by Linda Flower and John R. Hayes (1981) as an agent system. The theory's Monitor runs as the orchestrating agent and decides what to work on next. The Monitor delegates Planning, Translating, and Reviewing as roles backed by skills and subagents. The task environment and long-term memory live as files in the writing project, and the goal network evolves as composition proceeds. The three roles work as follows:

- Planning generates and organizes ideas and sets goals.
- Translating turns selected meanings into words.
- Reviewing evaluates and revises the text.

## Install from GitHub

Use the GitHub marketplace for the main install path. If the repository is private, GitHub installs require access to it. For development checkouts and personal Codex installs, read [`docs/installation.md`](./docs/installation.md).

### GitHub install for Claude Code

1. Add the repository marketplace:

   ```text
   /plugin marketplace add shunk031/agentic-cognitive-writing
   ```

2. Install the plugin from the marketplace:

   ```text
   /plugin install agentic-cognitive-writing@agentic-cognitive-writing-process
   ```

### GitHub install for Codex

1. From the writing project, add the repository marketplace:

   ```bash
   codex plugin marketplace add shunk031/agentic-cognitive-writing
   ```

2. Install the plugin from the marketplace:

   ```bash
   codex plugin add agentic-cognitive-writing@agentic-cognitive-writing-process
   ```

## Try it in a writing project

Agentic CogWriter turns your task into a file-backed writing session that you can inspect between turns.

1. Start in the project where the writing should live.
2. Invoke `/agentic-cognitive-writing:agentic-cog-writer` in Claude Code or `$agentic-cog-writer` in Codex. Describe the topic, audience, reason for writing, and desired result. The main skill asks for the rhetorical problem when needed, then coordinates the writing work through the project files.
3. Review the files the skill creates or updates:

   - `.writing/assignment.md` records the rhetorical problem and constraints.
   - `.writing/goals.md` records the hierarchical goal network and its history.
   - `.writing/draft.md` holds the growing text.
   - `.writing/memory/` holds topic knowledge, audience knowledge, and writing plans.
   - `.writing/trace/process.jsonl` records every process switch and goal change as one JSON line. See the [trace schema](plugin/skills/agentic-cog-writer/references/trace-jsonl-schema.md).

The monitor reads this state before each operation. You can inspect or edit it between turns.

## How it works

Read [How the theory maps to Agentic CogWriter](docs/theory-mapping.md) for the Figure 1 diagram, artifact mapping, and adapter details. Researchers can compare controlled variants in the [experiment package README](experiments/plugin/README.md).

## Find code, research, and experiment material

The repository keeps the main plugin, experiment package, research, and protocol in separate directories.

- [`plugin/`](plugin/) contains the installable main plugin, including shared skills and adapter files.
- [`experiments/plugin/`](experiments/plugin/) contains the installable controlled-comparison variants.
- [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json) and [`.agents/plugins/marketplace.json`](.agents/plugins/marketplace.json) define the local marketplace sources.
- The [`docs/research/skill-subagent-survey.md`](./docs/research/skill-subagent-survey.md) documents the research basis.
- The [`docs/experiments/protocol.md`](./docs/experiments/protocol.md) defines the comparison procedure.
- [`tools/validate-skills.sh`](tools/validate-skills.sh) runs the reproducible skill validators.
- [`plugin/skills/agentic-cog-writer/evals/evals.json`](plugin/skills/agentic-cog-writer/evals/evals.json) and the experiment skill eval files under [`experiments/plugin/skills/`](experiments/plugin/skills/) seed skill evaluations.

For offline use after installation, read [`plugin/README.md`](plugin/README.md); for research and experiment context, browse the linked documents above.

[^1]: Linda Flower and John R. Hayes. "A Cognitive Process Theory of Writing." College Composition and Communication 32(4), 1981, pp. 365-387.
    DOI: [10.58680/ccc198115885](https://doi.org/10.58680/ccc198115885) / JSTOR: [https://www.jstor.org/stable/356600](https://www.jstor.org/stable/356600)
