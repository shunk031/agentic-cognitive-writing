# Agentic cognitive writing

The plugin supports Claude Code and OpenAI Codex. After installation, open the writing project, the directory where you are writing. Use this assistant to plan, draft, and revise a document while the assistant updates its plans and goals as the draft develops.

For the theory and architecture behind this plugin, see the [project README](https://github.com/shunk031/agentic-cognitive-writing#readme).

## Install the plugin

Choose a GitHub marketplace for normal use or a local checkout for development.

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

## Start a writing task

Invoke `/agentic-cognitive-writing:cognitive-writing` in Claude Code or `$cognitive-writing` in Codex. You can also describe a writing task and let the host invoke the main skill.

## Skills you can use

Use `cognitive-writing` for normal writing tasks. The other entries support delegated roles or controlled comparisons.

### The skill you use

- `cognitive-writing` coordinates planning, drafting, and revision for the current writing project.

### Internal role skills

The monitor, the part that decides what to work on next, invokes these roles during delegated work. Do not invoke them directly.

- `planning` handles delegated idea generation and goal setting.
- `translating` handles delegated drafting.
- `reviewing` handles delegated evaluation and revision.

### Experiment variants

Use these skills only for controlled comparisons. See the [repository README](https://github.com/shunk031/agentic-cognitive-writing#readme) for context.

- `cognitive-writing-fixed-order` runs Planning, Translating, and Reviewing in a fixed order.
- `cognitive-writing-no-goal-network` uses the assignment as one implicit objective and leaves `goals.md` untouched.

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

The monitor, the part that decides what to work on next, appends every process switch and goal change as one JSON line to `.writing/trace/process.jsonl`. Read the [field-by-field trace schema](skills/cognitive-writing/references/trace-jsonl-schema.md) before inspecting or extending the log.

The main skill also uses [`goals-format.md`](skills/cognitive-writing/references/goals-format.md) for the hierarchical notation in `goals.md`.

The plugin does not depend on other files in this repository at runtime. It does create and maintain `.writing/` in the user's writing project. That directory belongs to the user and should not be committed unless the user chooses to share the writing process.

For research and experiment context, see the [project repository](https://github.com/shunk031/agentic-cognitive-writing).
