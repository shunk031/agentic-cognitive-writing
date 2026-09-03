# Install Agentic CogWriter for development or personal use

Use this guide to install `Agentic CogWriter` from a development checkout or as a personal Codex install. Use the GitHub marketplace steps in [`README.md`](../README.md) for the main install path.

## Marketplace and manifest layout

Both clients read the same repository marketplace file, and each client loads its own plugin manifest.

| Platform | Marketplace | Plugin manifest |
| --- | --- | --- |
| Claude Code | [`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json) | [`plugin/.claude-plugin/plugin.json`](../plugin/.claude-plugin/plugin.json) |
| OpenAI Codex | [`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json) | [`plugin/.codex-plugin/plugin.json`](../plugin/.codex-plugin/plugin.json) |

The tested Codex CLI registered and installed the plugin from this shared marketplace file but rejected a root `.codex-plugin/marketplace.json` file.

## Claude Code development install

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

## Codex development install

1. Change to the repository root.
2. Add the local marketplace:

   ```bash
   codex plugin marketplace add .
   ```

3. Install the plugin:

   ```bash
   codex plugin add agentic-cognitive-writing@agentic-cognitive-writing-process
   ```

## Codex personal install

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

For marketplace discovery and portable package details, read the [OpenAI plugin packaging guide](https://developers.openai.com/plugins/build/plugins.md) / [Agent Plugins specification](https://agent-plugins.org/).
