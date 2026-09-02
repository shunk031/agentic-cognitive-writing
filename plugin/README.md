# Agentic cognitive writing

The installed `agentic-cognitive-writing` package lets you invoke the `cognitive-writing` skill in a writing project. The skill plans, drafts, and revises a document while it updates goals and other process state in the project's `.writing/` directory.

The package ships a Claude Code adapter in [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) and [`agents/`](agents/), plus a Codex adapter in [`.codex-plugin/plugin.json`](.codex-plugin/plugin.json) and per-skill metadata under [`skills/`](skills/).

For the theory and architecture behind this plugin, see the [project README](https://github.com/shunk031/agentic-cognitive-writing#readme).

## Install the plugin

Choose a GitHub marketplace for normal use or a local checkout for development. If the repository is private, GitHub installs require access to it.

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

### Development install from a checkout in Claude Code

1. Change to the repository root.
2. Add the local marketplace:

   ```text
   /plugin marketplace add .
   ```

3. Install the plugin:

   ```text
   /plugin install agentic-cognitive-writing@agentic-cognitive-writing-process
   ```

4. To try it without installing, load the plugin directory directly:

   ```bash
   claude --plugin-dir "$PWD/plugin"
   ```

### Development install from a checkout in Codex

1. Change to the repository root. The repository includes [`.agents/plugins/marketplace.json`](../.agents/plugins/marketplace.json) with a local source entry for the [`plugin/`](../plugin/) directory.
2. Add the local marketplace:

   ```bash
   codex plugin marketplace add .
   ```

3. Install the plugin:

   ```bash
   codex plugin add agentic-cognitive-writing@agentic-cognitive-writing-process
   ```

### Personal Codex install

1. Copy the plugin directory to `~/.codex/plugins/agentic-cognitive-writing`.
2. Create `~/.agents/plugins/marketplace.json`:

   ```json
   {
     "name": "agentic-cognitive-writing-process",
     "plugins": [
       {
         "name": "agentic-cognitive-writing",
         "source": {
           "source": "local",
           "path": "../../.codex/plugins/agentic-cognitive-writing"
         }
       }
     ]
   }
   ```

3. Add that marketplace and install the plugin:

   ```bash
   codex plugin marketplace add ~/.agents/plugins
   codex plugin add agentic-cognitive-writing@agentic-cognitive-writing-process
   ```

## Start a writing task

Invoke `/agentic-cognitive-writing:cognitive-writing` in Claude Code or `$cognitive-writing` in Codex. The main skill can also start when your request clearly asks for writing help, without the explicit command.

To bind a delegated role to a custom Codex agent, use the [Codex custom-agent examples](examples/codex-agents/README.md).

## Skills you can use

Use `cognitive-writing` for normal writing tasks. The list below separates that entry from the internal role skills.

### The skill you use

- `cognitive-writing` coordinates planning, drafting, and revision for the current writing project.

### Internal role skills

The Monitor is the part of the skill that decides what to work on next and invokes these roles during delegated work. Do not invoke them directly.

- `planning` handles delegated idea generation and goal setting.
- `translating` handles delegated drafting.
- `reviewing` handles delegated evaluation and revision.

The separate [`cognitive-writing-experiments` package](https://github.com/shunk031/agentic-cognitive-writing) contains `cognitive-writing-fixed-order` and `cognitive-writing-no-goal-network` for controlled comparisons.

Read the [project repository](https://github.com/shunk031/agentic-cognitive-writing) for experiment context.

## Files maintained in your writing project

The plugin creates or maintains this layout in the project where it is used:

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

The Monitor appends every process switch and goal change as one JSON line to `.writing/trace/process.jsonl`. Read the [field-by-field trace schema](skills/cognitive-writing/references/trace-jsonl-schema.md) before inspecting or extending the log.

The main skill also uses [`goals-format.md`](skills/cognitive-writing/references/goals-format.md) for the hierarchical notation in `goals.md`.

The shipped package contains the manifests, skills, and agents it reads at runtime; no other file in this repository is required.

The directory belongs to the user and should not be committed unless the user chooses to share the writing process.
