# Agentic cognitive writing

After installation, open a writing project, the directory where you are writing, and invoke this writing assistant in Claude Code or Codex. It plans, drafts, and revises recursively, meaning it can revise its own plans and goals as the draft teaches it more. It stores the work in project files so you can inspect and continue it.

For the theory and architecture behind this plugin, see the [project README](https://github.com/shunk031/agentic-cognitive-writing#readme).

## Install

If the repository is private, GitHub installs require access to it.

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

1. Change to the repository root. The repository includes `.agents/plugins/marketplace.json` with a local `./plugin` source entry.
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

## Use the plugin

Invoke `/agentic-cognitive-writing:cognitive-writing` in Claude Code or `$cognitive-writing` in Codex. You can also describe a writing task and let the host invoke the main skill.

## Skills provided

- `cognitive-writing` is the recommended skill. It coordinates the writing process from the current project state.
- `planning` is an internal role skill for delegated planning work. Do not invoke it directly.
- `translating` is an internal role skill for delegated drafting work. Do not invoke it directly.
- `reviewing` is an internal role skill for delegated evaluation and revision. Do not invoke it directly.
- `cognitive-writing-fixed-order` is an experiment-comparison variant that runs the processes in a fixed order. It is not the recommended default.
- `cognitive-writing-no-goal-network` is an experiment-comparison variant that omits hierarchical goals. It is not the recommended default.

## Project state

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

The monitor, the part that decides what to work on next, appends every process switch and goal change as one JSON line to `.writing/trace/process.jsonl`. Read the [field-by-field trace schema](skills/cognitive-writing/references/trace-jsonl-schema.md) before inspecting or extending the log.

The main skill also uses [`goals-format.md`](skills/cognitive-writing/references/goals-format.md) for the hierarchical notation in `goals.md`.

The plugin does not depend on other files in this repository at runtime. It does create and maintain `.writing/` in the user's writing project. That directory belongs to the user and should not be committed unless the user chooses to share the writing process.

For research and experiment context, see the [project repository](https://github.com/shunk031/agentic-cognitive-writing).
