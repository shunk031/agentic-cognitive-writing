# Agentic CogWriter

The installed `agentic-cognitive-writing` package lets you invoke Agentic CogWriter in a writing project. Agentic CogWriter realizes the writing model as an agent system. Its `Monitor` chooses the next process. Delegated `Planning`, `Translating`, and `Reviewing` roles update the project's goals, drafts, notes, decision log, and other process state under `.writing/`.

The package ships a Claude Code adapter in [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) and [`agents/`](agents/), plus a Codex adapter in [`.codex-plugin/plugin.json`](.codex-plugin/plugin.json) and per-skill metadata under [`skills/`](skills/).

For the theory and architecture behind this plugin, see the [project README](https://github.com/shunk031/agentic-cognitive-writing#readme).

## Installation

Use the GitHub marketplace for the main install path. If the repository is private, GitHub installs require access to it. For development checkouts and personal Codex installs, read the `docs/installation.md` guide in the [project repository](https://github.com/shunk031/agentic-cognitive-writing).

### GitHub install for Claude Code

1. Add the repository marketplace:

   ```text
   /plugin marketplace add shunk031/agentic-cognitive-writing
   ```

2. Install the plugin:

   ```text
   /plugin install agentic-cognitive-writing@agentic-cognitive-writing-process
   ```

### GitHub install for Codex

1. From the writing project, add the repository marketplace:

   ```bash
   codex plugin marketplace add shunk031/agentic-cognitive-writing
   ```

2. Install the plugin:

   ```bash
   codex plugin add agentic-cognitive-writing@agentic-cognitive-writing-process
   ```

## Start a writing task

Invoke `/agentic-cognitive-writing:agentic-cog-writer` in Claude Code or `$agentic-cog-writer` in Codex. Agentic CogWriter can also start when your request clearly asks for writing help, without the explicit command.

To bind a delegated role to a custom Codex agent, use the [Codex custom-agent examples](examples/codex-agents/README.md).

## Skills you can use

Use Agentic CogWriter for normal writing tasks. The list below separates the main skill entry from the internal role skills.

### The skill you use

- `agentic-cog-writer` coordinates planning, drafting, and revision for the current writing project.

### Internal role skills

The `Monitor` is the part of the skill that decides what to work on next and invokes these roles during delegated work. Do not invoke them directly.

- `planning` handles delegated idea generation and goal setting.
- `translating` handles delegated drafting.
- `reviewing` handles delegated evaluation and revision.

The separate [`cognitive-writing-experiments` package](https://github.com/shunk031/agentic-cognitive-writing) contains `cognitive-writing-fixed-order` and `cognitive-writing-no-goal-network` for controlled comparisons.

## Files maintained in your writing project

Agentic CogWriter creates or maintains this layout in the project where it is used:

```text
.writing/
├── assignment.md       # topic, audience, exigency (reason for writing), writer's goals, constraints
├── goals.md            # hierarchical goal network and history
├── draft.md            # growing text
├── memory/
│   ├── topic.md        # optional topic knowledge
│   ├── audience.md     # optional audience knowledge
│   └── plans.md        # optional reusable writing plans
└── trace/
    └── process.jsonl   # append-only process log
```

The `Monitor` appends every process switch and goal change as one JSON line to `.writing/trace/process.jsonl`. Read the [field-by-field trace schema](skills/agentic-cog-writer/references/trace-jsonl-schema.md) before inspecting or extending the log.

The main skill also uses [`goals-format.md`](skills/agentic-cog-writer/references/goals-format.md) for the hierarchical notation in `goals.md`.

The shipped package contains the manifests, skills, and agents it reads at runtime; no other file in this repository is required.

The directory belongs to the user and should not be committed unless the user chooses to share the writing process.
