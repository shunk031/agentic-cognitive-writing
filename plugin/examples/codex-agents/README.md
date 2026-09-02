# Optional Codex custom agents

These files are for a Codex user of the agentic-cognitive-writing plugin who wants stronger per-role binding. Each TOML file points one custom agent at the plugin's matching role skill, tells it to read the `.writing/` state first, and preserves that skill's report format.

The main skill's delegation instructions call native Codex subagents, so the plugin does not require these custom-agent files.

## Copy the files

Copy the three TOML files in this directory to one of these locations:

- `.codex/agents/` in the writing project for project-scoped custom agents.
- `~/.codex/agents/` for personal custom agents.

For example, from the installed plugin directory:

```bash
mkdir -p /path/to/writing-project/.codex/agents
cp examples/codex-agents/*.toml /path/to/writing-project/.codex/agents/
```

Use `~/.codex/agents/` as the destination when you want the agents available across writing projects.

The Codex custom-agent format is upstream and may evolve. Check the [Custom agents documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents.md#custom-agents) before relying on these examples or changing them.
