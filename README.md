# Agentic CogWriter

[![Checks](https://github.com/shunk031/agentic-cognitive-writing/actions/workflows/checks.yml/badge.svg)](https://github.com/shunk031/agentic-cognitive-writing/actions/workflows/checks.yml)

`Agentic CogWriter` is a writing assistant that plans, drafts, and revises long-form text the way human writers do. The assistant keeps its goals, drafts, notes, and decision log as files in the directory where you write. Instead of generating text in one pass, the assistant revisits and rewrites its own plans and goals as the draft develops.

Agentic CogWriter realizes the writing model in ["A Cognitive Process Theory of Writing"](https://www.jstor.org/stable/356600) (1981)[^1] as an agent system. The theory's `Monitor` runs as the orchestrating agent and decides what to work on next. The `Monitor` delegates `Planning`, `Translating`, and `Reviewing` as roles backed by skills and subagents. The task environment and long-term memory live as files in the writing project, and the goal network evolves as composition proceeds. The three roles work as follows:

- `Planning` generates and organizes ideas and sets goals.
- `Translating` turns selected meanings into words.
- `Reviewing` evaluates and revises the text.

## Installation

Use the GitHub marketplace for the main install path. If the repository is private, GitHub installs require access to it. For development checkouts and personal Codex installs, read [`docs/installation.md`](./docs/installation.md).

### Claude Code

1. Add the repository marketplace:

   ```text
   /plugin marketplace add shunk031/agentic-cognitive-writing
   ```

2. Install the plugin from the marketplace:

   ```text
   /plugin install agentic-cognitive-writing@agentic-cognitive-writing-process
   ```

### Codex

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

The `Monitor` reads this state before each operation. You can inspect or edit it between turns.

For offline package details, read [`plugin/README.md`](plugin/README.md).

## How it works

Read [How the theory maps to Agentic CogWriter](docs/theory-mapping.md) for the Figure 1 diagram and artifact mapping.

## Research and experiment context

Research surveys and the experiment protocol live under [`docs/`](docs/), and the controlled-comparison packages live under [`experiments/`](experiments/).

[^1]: Linda Flower and John R. Hayes. "A Cognitive Process Theory of Writing." College Composition and Communication 32(4), 1981, pp. 365-387.
    DOI: [10.58680/ccc198115885](https://doi.org/10.58680/ccc198115885) / JSTOR: [https://www.jstor.org/stable/356600](https://www.jstor.org/stable/356600)

## License

The repository is licensed under Apache-2.0. Third-party benchmark data and cited external code retain their own licenses.
