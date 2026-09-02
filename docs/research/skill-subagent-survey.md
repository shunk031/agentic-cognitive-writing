# Skill/sub-agent survey for agentic cognitive writing process

## Purpose and reading guide

This report provides design evidence for turning Flower & Hayes' Cognitive Process Theory of Writing [^1] into a skills + sub-agents implementation that works as a Claude Code plugin and from OpenAI Codex. Each section follows the same order:

- Official non-GitHub sources
- Direct GitHub files
- Differences and implications

Opening summary. The question is how to design a skill/sub-agent plugin for a cognitive writing process that works in both Claude Code and Codex. The method was:

- Read official non-GitHub documentation first for each topic.
- Check direct GitHub files for implementation examples.
- Reconcile the differences.

The conclusion is that the lowest-risk shared core is:

- `SKILL.md`
- `scripts/`
- `references/`
- `assets/`

Thin adapters sit on top:

- Claude: `.claude-plugin/` and `agents/*.md`
- Codex: `.codex-plugin/` and `agents/openai.yaml`

For the paper prototype, the design should center four roles:

- `monitor`
- `planner`
- `translator`
- `reviewer`

A process ledger should record each decision, so the evaluation can measure changes in the cognitive process as well as the final text.

Evidence rule. Unsupported paths are not evidence for platform behavior.

## 1. Anthropic skill format and skill-creator

**Sources**

- Official non-GitHub: Claude Code Skills docs: https://code.claude.com/docs/en/skills.md
- GitHub code: Anthropic skill-creator `SKILL.md`: https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md
- GitHub code: validator: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py
- GitHub code: schemas: https://github.com/anthropics/skills/blob/main/skills/skill-creator/references/schemas.md
- GitHub code: grader agent: https://github.com/anthropics/skills/blob/main/skills/skill-creator/agents/grader.md
- GitHub code: comparator agent: https://github.com/anthropics/skills/blob/main/skills/skill-creator/agents/comparator.md
- GitHub code: analyzer agent: https://github.com/anthropics/skills/blob/main/skills/skill-creator/agents/analyzer.md
- GitHub code: package script: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/package_skill.py
- GitHub code: benchmark aggregation script: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/aggregate_benchmark.py
- GitHub code: eval script: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/run_eval.py
- GitHub code: eval loop script: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/run_loop.py

**Format and constraints**

- Claude Code skills are directories containing `SKILL.md`; `SKILL.md` has YAML Ain't Markup Language (YAML) frontmatter between `---` markers and Markdown instructions, and Claude can invoke the skill by relevance or by `/skill-name`. Source: https://code.claude.com/docs/en/skills.md
- Anthropic skill-creator defines the canonical anatomy as `skill-name/SKILL.md` plus optional support directories:
  - `scripts/`
  - `references/`
  - `assets/`
  Source: https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md
- Anthropic `quick_validate.py` accepts these frontmatter keys:
  - `name`
  - `description`
  - `license`
  - `allowed-tools`
  - `metadata`
  - `compatibility`
  `name` and `description` are required. Source: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py
- `name` must be a string and kebab-case with lowercase letters, digits, and hyphens. It must not:
  - Start with `-`
  - End with `-`
  - Contain `--`
  - Exceed 64 characters
  Source: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py
- `description` must be a string, must not contain `<` or `>`, and must not exceed 1024 characters. Source: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py
- `compatibility` is optional in the validator and, when present, must be a string no longer than 500 characters. Source: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py
- Claude Code docs also show a minimal project skill with only `description` frontmatter; the separate Anthropic skill-creator validator is stricter because it requires `name`. Reconciliation: for portability and package validation, include both `name` and `description`; do not rely on Claude Code's fallback tolerance.
  Sources:
  - https://code.claude.com/docs/en/skills.md
  - https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py

**Directory conventions and progressive disclosure**

- Anthropic defines the optional skill directories this way:
  - `scripts/` are for deterministic or repetitive executable code.
  - `references/` are for documentation loaded only when needed.
  - `assets/` are for templates, icons, fonts, and other files used in outputs.
  Source: https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md
- Progressive disclosure has three levels:
  - Always-visible metadata (`name` + `description`)
  - The `SKILL.md` body when the skill triggers
  - Optional bundled resources as needed
  Anthropic recommends keeping `SKILL.md` under about 500 lines and moving variant-specific details into `references/`. Source: https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md
- Claude Code skill locations include:
  - Enterprise skills
  - Personal skills at `~/.claude/skills/<skill-name>/SKILL.md`
  - Project skills at `.claude/skills/<skill-name>/SKILL.md`
  - Plugin skills at `<plugin>/skills/<skill-name>/SKILL.md`
  Plugin skills are namespaced as `/plugin-name:skill-name`. Source: https://code.claude.com/docs/en/skills.md
- Claude Code follows symlinked skill folders in personal/project/enterprise skill locations, but plugin symlink behavior is governed by the plugin reference. Source: https://code.claude.com/docs/en/skills.md

**Skill-creator workflow**

- Anthropic skill-creator prescribes this workflow:
  - Capture intent.
  - Interview/research.
  - Write `SKILL.md`.
  - Create 2-3 realistic test prompts.
  - Run with-skill and baseline subagents in the same turn.
  - Draft assertions while runs proceed.
  - Grade.
  - Aggregate benchmark.
  - Open an eval viewer.
  - Read human feedback.
  - Improve.
  - Repeat.
  - Optionally optimize the description.
  Source: https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md
- `evals/evals.json` schema includes:
  - `skill_name`
  - `evals[].id`
  - `prompt`
  - `expected_output`
  - Optional `files`
  - `expectations`
  Source: https://github.com/anthropics/skills/blob/main/skills/skill-creator/references/schemas.md
- `grading.json` expects each assertion under `expectations[]` to use:
  - `text`
  - `passed`
  - `evidence`
  The viewer depends on these exact field names.
  Sources:
  - https://github.com/anthropics/skills/blob/main/skills/skill-creator/references/schemas.md
  - https://github.com/anthropics/skills/blob/main/skills/skill-creator/eval-viewer/generate_review.py
- `package_skill.py` creates a `.skill` zip archive after running validation and excludes:
  - `__pycache__`
  - `node_modules`
  - `.DS_Store`
  - `*.pyc`
  - Root-level `evals`
  Source: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/package_skill.py

## 2. Claude Code plugin format

**Sources**

- Official non-GitHub: Create plugins: https://code.claude.com/docs/en/plugins.md
- Official non-GitHub: Plugins reference: https://code.claude.com/docs/en/plugins-reference.md
- Official non-GitHub: Plugin marketplaces: https://code.claude.com/docs/en/plugin-marketplaces.md
- GitHub code: official marketplace: https://github.com/anthropics/claude-plugins-official/blob/main/.claude-plugin/marketplace.json
- GitHub code: `skill-creator` plugin manifest: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/skill-creator/.claude-plugin/plugin.json
- GitHub code: `feature-dev` plugin manifest: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/.claude-plugin/plugin.json
- GitHub code: `feature-dev` code-explorer agent: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/agents/code-explorer.md
- GitHub code: `feature-dev` code-architect agent: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/agents/code-architect.md
- GitHub code: `feature-dev` code-reviewer agent: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/agents/code-reviewer.md
- GitHub code: command-as-skill example: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/code-review/commands/code-review.md
- GitHub code: hook example: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/hookify/hooks/hooks.json

**Plugin root and manifest**

- A Claude Code plugin is a self-contained directory of components that can include:
  - Skills
  - Agents
  - Hooks
  - Model Context Protocol (MCP) servers
  - Language Server Protocol (LSP) servers
  - Monitors
  - `bin/`
  - Settings
  Source: https://code.claude.com/docs/en/plugins-reference.md
- The manifest lives at `.claude-plugin/plugin.json` and defines plugin identity fields:
  - `name`
  - `description`
  - Optional `version`/`author`
  Claude Code uses `name` as the skill namespace. Source: https://code.claude.com/docs/en/plugins.md
- Component directories are at plugin root, not inside `.claude-plugin/`. These are peer paths:
  - `skills/`
  - `commands/`
  - `agents/`
  - `hooks/`
  - `.mcp.json`
  - `.lsp.json`
  - `monitors/`
  - `bin/`
  - `settings.json`
  Source: https://code.claude.com/docs/en/plugins.md
- A plugin with exactly one skill may place `SKILL.md` directly at plugin root; multi-skill plugins should use `skills/<name>/SKILL.md`. Source: https://code.claude.com/docs/en/plugins.md
- Plugin skills are always namespaced, e.g. `/my-first-plugin:hello`. Source: https://code.claude.com/docs/en/plugins.md

**Bundled components**

- `skills/` contains skill directories; `commands/` contains flat Markdown skill files and is supported, though new plugins should prefer `skills/`. Source: https://code.claude.com/docs/en/plugins-reference.md
- `agents/` contains Markdown custom agent definitions; plugin agents are loaded under scoped names such as `my-plugin:code-reviewer`. Source: https://code.claude.com/docs/en/plugins-reference.md
- `hooks/hooks.json` or inline `plugin.json` hooks can register event handlers. `hookify` shows hooks calling Python scripts via `${CLAUDE_PLUGIN_ROOT}` for:
  - `PreToolUse`
  - `PostToolUse`
  - `Stop`
  - `UserPromptSubmit`
  Sources:
  - https://code.claude.com/docs/en/plugins-reference.md
  - https://github.com/anthropics/claude-plugins-official/blob/main/plugins/hookify/hooks/hooks.json
- Plugin default `settings.json` currently supports `agent` and `subagentStatusLine`; setting `agent` can activate a plugin custom agent as the main thread. Source: https://code.claude.com/docs/en/plugins.md

**Marketplace and install flow**

- A Claude Code marketplace is `.claude-plugin/marketplace.json` with required fields:
  - `name`
  - `owner`
  - `plugins[]`
  Each plugin entry requires `name` and `source`. Source: https://code.claude.com/docs/en/plugin-marketplaces.md
- Marketplace sources include:
  - Relative paths
  - GitHub repo objects
  - Git URLs
  - `git-subdir`
  - `npm`
  - HTTPS archives
  - Command sources
  Source: https://code.claude.com/docs/en/plugin-marketplaces.md
- Users add and install with slash commands such as `/plugin marketplace add ./my-marketplace` and `/plugin install quality-review-plugin@my-plugins`. Source: https://code.claude.com/docs/en/plugin-marketplaces.md
- Installed plugins are copied to a cache location except command sources in link mode. Source: https://code.claude.com/docs/en/plugin-marketplaces.md
- Anthropic's official marketplace file demonstrates local `source: "./plugins/agent-sdk-dev"` entries and external `git-subdir`/URL entries. Source: https://github.com/anthropics/claude-plugins-official/blob/main/.claude-plugin/marketplace.json

## 3. Claude Code sub-agent definitions

**Sources**

- Official non-GitHub: Subagents docs: https://code.claude.com/docs/en/sub-agents.md
- Official non-GitHub: Plugins reference, agents component: https://code.claude.com/docs/en/plugins-reference.md
- GitHub code: `feature-dev` code-explorer agent: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/agents/code-explorer.md
- GitHub code: `feature-dev` code-architect agent: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/agents/code-architect.md
- GitHub code: `feature-dev` code-reviewer agent: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/agents/code-reviewer.md
- GitHub code: `feature-dev` command invoking agents: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/commands/feature-dev.md
- GitHub code: VoltAgent community example: https://github.com/VoltAgent/awesome-claude-code-subagents/blob/main/categories/09-meta-orchestration/agent-installer.md
- GitHub code: contains-studio community example: https://github.com/contains-studio/agents/blob/main/engineering/ai-engineer.md
- GitHub code: 0xfurai community example: https://github.com/0xfurai/claude-code-subagents/blob/main/agents/openai-api-expert.md

**Definition format**

- File-based subagents use Markdown files with YAML frontmatter followed by the system prompt body; the body becomes the subagent's system prompt. Source: https://code.claude.com/docs/en/sub-agents.md
- Supported frontmatter fields include:
  - Required `name`
  - Required `description`
  - Optional `tools`
  - Optional `disallowedTools`
  - Optional `model`
  - Optional `permissionMode`
  - Optional `maxTurns`
  - Optional `skills`
  - Optional `mcpServers`
  - Optional `hooks`
  - Optional `memory`
  - Optional `background`
  - Optional `effort`
  - Optional `isolation`
  - Optional `color`
  - Optional `initialPrompt`
  - Optional `experimental.cacheTtl`
  Source: https://code.claude.com/docs/en/sub-agents.md
- `name` uses lowercase letters and hyphens; `:` is invalid in the name because plugin-scoped identifiers use colons. Source: https://code.claude.com/docs/en/sub-agents.md
- Claude Code supports these subagent locations and definitions:
  - Project subagents in `.claude/agents/`
  - User subagents in `~/.claude/agents/`
  - Plugin subagents in a plugin `agents/` directory
  - CLI-defined subagents passed as JSON via `--agents`
  Source: https://code.claude.com/docs/en/sub-agents.md
- Plugin subagents support:
  - `name`
  - `description`
  - `model`
  - `effort`
  - `maxTurns`
  - `tools`
  - `disallowedTools`
  - `skills`
  - `memory`
  - `background`
  - `isolation`
  Plugin-shipped agents do not support:
  - `hooks`
  - `mcpServers`
  - `permissionMode`
  Source: https://code.claude.com/docs/en/plugins-reference.md

**Execution and interaction with skills**

- A non-fork subagent starts with fresh isolated context, a task message, relevant `CLAUDE.md` hierarchy, git status, and full content of skills named in the subagent `skills` field. Source: https://code.claude.com/docs/en/sub-agents.md
- The `skills` field preloads full skill content into the subagent at startup; subagents can still invoke unlisted project, user, and plugin skills through the Skill tool. Source: https://code.claude.com/docs/en/sub-agents.md
- Background subagents retain a filtered built-in tool set:
  - `Read`
  - `Grep`
  - `Glob`
  - `Bash`
  - `Edit`
  - `Write`
  - `WebFetch`
  - `WebSearch`
  - `TodoWrite`
  - `Skill`
  - `ToolSearch`
  - `EnterWorktree`
  - `ExitWorktree`
  - `Monitor`
  - `TaskStop`
  - `SendMessage`
  - `Artifact`
  Source: https://code.claude.com/docs/en/sub-agents.md
- `feature-dev/commands/feature-dev.md` uses a command skill to launch these agents across discovery, design, and quality review phases:
  - `code-explorer`
  - `code-architect`
  - `code-reviewer`
  Source: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/commands/feature-dev.md
- We infer that our writing-process plugin should represent Flower & Hayes' model [^1] as Claude Code plugin agents:
  - `monitor`
  - `planner`
  - `translator`
  - `reviewer`
  Top-level skills should orchestrate phase transitions, because official examples already use commands/skills to route subagents for structured workflows. Evidence: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/commands/feature-dev.md

## 4. OpenAI Codex skill format and skill-creator

**Sources**

- Official non-GitHub: Codex build skills: https://developers.openai.com/codex/build-skills.md
- Official non-GitHub: plugin build skills: https://developers.openai.com/plugins/build/skills.md
- Official non-GitHub: Codex build plugins: https://developers.openai.com/codex/build-plugins.md
- GitHub code: OpenAI system skill-creator: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/SKILL.md
- GitHub code: OpenAI validator: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/quick_validate.py
- GitHub code: `agents/openai.yaml` reference: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/references/openai_yaml.md
- GitHub code: OpenAI skill initializer: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/init_skill.py
- GitHub code: OpenAI metadata generator: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/generate_openai_yaml.py

**Codex skill anatomy and discovery**

- Codex skills are directories with required `SKILL.md` plus optional support paths:
  - `scripts/`
  - `references/`
  - `assets/`
  - `agents/openai.yaml`
  Source: https://developers.openai.com/codex/build-skills.md
- `SKILL.md` requires `name` and `description`; Codex uses only those frontmatter fields to decide whether to use a skill, then reads the body after the skill triggers.
  Sources:
  - https://developers.openai.com/codex/build-skills.md
  - https://github.com/openai/skills/blob/main/skills/.system/skill-creator/SKILL.md
- Codex loads local skills from:
  - `$CWD/.agents/skills`
  - Parent `.agents/skills` directories up to the repo root
  - `$HOME/.agents/skills`
  - `/etc/codex/skills`
  - Bundled system skills
  Source: https://developers.openai.com/codex/build-skills.md
- Codex supports explicit invocation with `$skill-name` in CLI/integrated development environment (IDE) or `/skills`, and implicit invocation by matching the `description`. Source: https://developers.openai.com/codex/build-skills.md
- Codex supports symlinked skill folders and follows the symlink target when scanning skill locations. Source: https://developers.openai.com/codex/build-skills.md
- Codex can disable a local skill with `[[skills.config]] path = ".../SKILL.md" enabled = false` in `~/.codex/config.toml`; restart is required after changing config. Source: https://developers.openai.com/codex/build-skills.md
- Codex's initial skill list includes each skill path and is bounded to at most 2% of the model context window or 8,000 characters when context size is unknown; selected skills still load full `SKILL.md`. Source: https://developers.openai.com/codex/build-skills.md

**OpenAI optional metadata**

- `agents/openai.yaml` is optional user interface (UI)/dependency metadata for ChatGPT and Codex. Supported fields include:
  - `interface.display_name`
  - `short_description`
  - `icon_small`
  - `icon_large`
  - `brand_color`
  - `default_prompt`
  - `dependencies.tools[]` for MCP
  Source: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/references/openai_yaml.md
- `policy.allow_implicit_invocation: false` is documented in OpenAI Codex docs as an optional metadata policy controlling implicit invocation while preserving explicit `$skill` invocation. Source: https://developers.openai.com/codex/build-skills.md
- OpenAI `generate_openai_yaml.py` validates interface overrides against:
  - `display_name`
  - `short_description`
  - `icon_small`
  - `icon_large`
  - `brand_color`
  - `default_prompt`
  It enforces `short_description` length 25-64 characters. Source: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/generate_openai_yaml.py

**Field-by-field diff vs Anthropic**

| Area | Anthropic skill-creator | OpenAI Codex skill-creator | Design consequence |
| --- | --- | --- | --- |
| Required `SKILL.md` fields | Required by validator:<br>`name`<br>`description`<br>https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py | Required by docs and validator:<br>`name`<br>`description`<br>https://developers.openai.com/codex/build-skills.md <br> https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/quick_validate.py | Use both everywhere. |
| Allowed frontmatter keys | Allowed by validator:<br>`name`<br>`description`<br>`license`<br>`allowed-tools`<br>`metadata`<br>`compatibility`<br>https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py | Allowed by validator:<br>`name`<br>`description`<br>`license`<br>`allowed-tools`<br>`metadata`<br>https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/quick_validate.py | Avoid `compatibility` if the same file must validate under OpenAI's creator. |
| Name rules | Kebab-case:<br>No leading hyphen<br>No trailing hyphen<br>No consecutive hyphen<br>Max 64 characters<br>https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py | Hyphen-case:<br>No leading hyphen<br>No trailing hyphen<br>No consecutive hyphen<br>Max 64 characters<br>https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/quick_validate.py | Same effective rule. |
| Description rules | String:<br>No angle brackets<br>Max 1024 characters<br>https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py | String:<br>No angle brackets<br>Max 1024 characters<br>https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/quick_validate.py | Same effective rule. |
| UI metadata | No Anthropic skill UI metadata file is required by the skill-creator anatomy: https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md | `agents/openai.yaml` is recommended by OpenAI for UI metadata and dependencies: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/SKILL.md | Add `agents/openai.yaml` as OpenAI-only metadata; Claude should ignore it as an ordinary support file. |
| Creation workflow | Emphasizes:<br>Eval loop<br>With-skill/baseline subagents<br>Viewer<br>Grader/comparator/analyzer<br>https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md | Emphasizes:<br>Lean skills<br>Degree-of-freedom choice<br>`init_skill.py`<br>`quick_validate.py`<br>Real usage iteration<br>https://github.com/openai/skills/blob/main/skills/.system/skill-creator/SKILL.md | Adopt Anthropic's eval workflow and OpenAI's lean/context-budget discipline. |

## 5. Codex multi-agent / sub-agent construction

**Sources**

- Official non-GitHub: Codex subagents: https://learn.chatgpt.com/docs/agent-configuration/subagents.md
- Official non-GitHub: Codex CLI and `codex exec`:
  - https://developers.openai.com/codex/cli.md
  - https://learn.chatgpt.com/docs/non-interactive-mode.md
- Official non-GitHub: Codex build skills: https://developers.openai.com/codex/build-skills.md
- GitHub code: OpenAI plugin example manifest: https://github.com/openai/plugins/blob/main/plugins/build-web-apps/.codex-plugin/plugin.json
- GitHub code: OpenAI frontend-app-builder skill: https://github.com/openai/plugins/blob/main/plugins/build-web-apps/skills/frontend-app-builder/SKILL.md
- GitHub code: OpenAI agents-sdk skill: https://github.com/openai/plugins/blob/main/plugins/openai-developers/skills/agents-sdk/SKILL.md
- GitHub code: Codex GitHub Action security docs as automation pattern: https://github.com/openai/codex-action/blob/main/docs/security.md
- GitHub code: STORM [^3] engine: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/engine.py
- GitHub code: STORM [^3] outline generation module: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/outline_generation.py
- GitHub code: STORM [^3] article generation module: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/article_generation.py

**Native Codex capabilities**

- ChatGPT Work and Codex can run subagent workflows by spawning specialized agents in parallel and collecting their results into one response. Source: https://learn.chatgpt.com/docs/agent-configuration/subagents.md
- Current local Codex releases enable subagent workflows by default, and subagent activity appears in the desktop app, CLI, and IDE extension. Source: https://learn.chatgpt.com/docs/agent-configuration/subagents.md
- In Codex CLI, users can ask for subagents explicitly; applicable `AGENTS.md` or skill instructions can also request delegation; `/agent` inspects and switches between agent threads. Source: https://learn.chatgpt.com/docs/agent-configuration/subagents.md
- If no subagent model or `model_reasoning_effort` is configured, a Codex subagent inherits the parent model and reasoning effort; users can also configure `[agents]` defaults or custom agent files. Source: https://learn.chatgpt.com/docs/agent-configuration/subagents.md
- `codex exec` runs non-interactively and supports:
  - Streaming progress to stderr
  - Printing final output to stdout
  - `--ephemeral`
  - JSON Lines (JSONL) output
  - Output schemas
  - Sandbox selection
  - Resume
  Source: https://learn.chatgpt.com/docs/non-interactive-mode.md
- We infer that a portable Codex sub-agent construction can use either native subagent workflows in local Codex clients or scripts that spawn `codex exec` child sessions and aggregate JSON output.
  Evidence:
  - Native subagents are documented at https://learn.chatgpt.com/docs/agent-configuration/subagents.md
  - `codex exec` automation is documented at https://learn.chatgpt.com/docs/non-interactive-mode.md

**Concrete ecosystem examples**

- Anthropic `feature-dev` plugin shows a skill/command orchestrating separate explorer, architect, and reviewer agents with explicit phase boundaries. Source: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/commands/feature-dev.md
- Anthropic `code-review` command uses multiple agents for:
  - Eligibility
  - Context discovery
  - Pull request (PR) summary
  - Five parallel review perspectives
  - Per-issue confidence scoring
  Source: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/code-review/commands/code-review.md
- VoltAgent's community `agent-installer` agent installs Claude subagents by fetching category lists and raw `.md` files into `~/.claude/agents/` or `.claude/agents/`. Source: https://github.com/VoltAgent/awesome-claude-code-subagents/blob/main/categories/09-meta-orchestration/agent-installer.md
- contains-studio's `ai-engineer.md` uses Claude subagent frontmatter with `name`, long `description`, `color`, and `tools`. Source: https://github.com/contains-studio/agents/blob/main/engineering/ai-engineer.md
- OpenAI `build-web-apps` plugin uses `.codex-plugin/plugin.json` to package multiple skills and top-level UI metadata. Its `frontend-app-builder` skill coordinates with other installed skills.
  Sources:
  - https://github.com/openai/plugins/blob/main/plugins/build-web-apps/.codex-plugin/plugin.json
  - https://github.com/openai/plugins/blob/main/plugins/build-web-apps/skills/frontend-app-builder/SKILL.md
- OpenAI `openai-developers` `agents-sdk` skill recommends starting with one `Agent`, then adding these only when needed:
  - Tools
  - Handoffs
  - Structured outputs
  - Sandbox execution
  - eval harnesses
  Source: https://github.com/openai/plugins/blob/main/plugins/openai-developers/skills/agents-sdk/SKILL.md

## 6. Cross-platform single-repo strategies

**Sources**

- Official non-GitHub: Claude skills docs: https://code.claude.com/docs/en/skills.md
- Official non-GitHub: Claude plugins docs/reference:
  - https://code.claude.com/docs/en/plugins.md
  - https://code.claude.com/docs/en/plugins-reference.md
- Official non-GitHub: OpenAI Codex skills/plugins docs:
  - https://developers.openai.com/codex/build-skills.md
  - https://developers.openai.com/plugins/build/plugins.md
- GitHub code: OpenAI `build-web-apps` plugin manifest: https://github.com/openai/plugins/blob/main/plugins/build-web-apps/.codex-plugin/plugin.json
- GitHub code: OpenAI `frontend-app-builder` skill: https://github.com/openai/plugins/blob/main/plugins/build-web-apps/skills/frontend-app-builder/SKILL.md
- GitHub code: Anthropic `skill-creator` plugin manifest: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/skill-creator/.claude-plugin/plugin.json
- GitHub code: Anthropic `skill-creator` Agent Skill: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/skill-creator/skills/skill-creator/SKILL.md
- GitHub code: Adobe Claude plugin manifest pointing at `skills`: https://github.com/adobe/skills/blob/main/plugins/creative-cloud/adobe-for-creativity/.claude-plugin/plugin.json

**Strategies**

1. **Shared core Agent Skill directory**
   - Both Claude Code and Codex accept a directory with `SKILL.md` plus optional support directories:
     - `scripts/`
     - `references/`
     - `assets/`
     Sources:
     - https://code.claude.com/docs/en/skills.md
     - https://developers.openai.com/codex/build-skills.md
   - We infer that canonical skills should live under `skills/<skill-name>/SKILL.md`. Keep the shared layout strict:
     - Avoid Anthropic-only `compatibility`.
     - Add OpenAI-only `agents/openai.yaml`.
     - Keep Claude plugin metadata outside the skill directory.
     This maximizes reuse because the common denominator is `SKILL.md` + support folders.
   - Trade-off: Claude project discovery wants `.claude/skills/`, Codex wants `.agents/skills/`; a bare `skills/` root needs plugin manifests, symlinks, or install scripts.

2. **Dual plugin manifests over one `skills/` tree**
   - Claude plugins use `.claude-plugin/plugin.json`; OpenAI plugins use `.codex-plugin/plugin.json`.
     Sources:
     - https://code.claude.com/docs/en/plugins.md
     - https://developers.openai.com/plugins/build/plugins.md
   - OpenAI plugin manifests can point `skills` at `./skills/`; Claude plugin docs likewise load `skills/` at plugin root.
     Sources:
     - https://developers.openai.com/plugins/build/skills.md
     - https://code.claude.com/docs/en/plugins-reference.md
   - We infer that a single repo can contain both manifests at plugin root:
     - `.claude-plugin/plugin.json`
     - `.codex-plugin/plugin.json`
     Both can point to `./skills/`, with platform-specific metadata files in their respective manifest directories.
   - Trade-off: marketplace schemas, install commands, UI metadata, and subagent definitions still diverge.

3. **Symlinked local authoring**
   - Claude follows symlinked skill folders in personal/project skill locations; Codex follows symlink targets when scanning skill folders.
     Sources:
     - https://code.claude.com/docs/en/skills.md
     - https://developers.openai.com/codex/build-skills.md
   - During development, teams can likely symlink `.claude/skills/<name>` and `.agents/skills/<name>` to the same canonical `skills/<name>` folder.
   - Trade-off: plugin packaging and cache copy semantics can break references outside the plugin directory; avoid `../shared` runtime dependencies in distributed packages. Claude install-cache warning: https://code.claude.com/docs/en/plugin-marketplaces.md

4. **Adapter generation**
   - OpenAI provides `init_skill.py` and `generate_openai_yaml.py` for generating `agents/openai.yaml`.
     Sources:
     - https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/init_skill.py
     - https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/generate_openai_yaml.py
   - Anthropic validates plugins with `claude plugin validate` according to Claude docs. Source: https://code.claude.com/docs/en/plugins.md
   - We infer that a converter can lint a canonical skill tree and generate adapters from a single declarative source:
     - `.codex-plugin/plugin.json`
     - `.claude-plugin/plugin.json`
     - OpenAI `agents/openai.yaml`
     - Claude `agents/*.md` wrappers
   - Trade-off: generated files must be checked or regenerated in CI; otherwise the two platforms drift.

**Recommended single-repo layout**

```text
agentic-cognitive-writing-process/
|-- .claude-plugin/
|   `-- plugin.json
|-- .codex-plugin/
|   `-- plugin.json
|-- skills/
|   |-- cognitive-writing-orchestrator/
|   |   |-- SKILL.md
|   |   |-- agents/
|   |   |   `-- openai.yaml
|   |   |-- references/
|   |   `-- scripts/
|   `-- revision-evaluator/
|       `-- SKILL.md
|-- agents/
|   |-- monitor.md
|   |-- planner.md
|   |-- translator.md
|   `-- reviewer.md
`-- docs/
```

- We infer that the root `agents/` directory should contain Claude subagents, because Claude plugins natively load plugin-root `agents/`; Codex can treat these as reference prompts or convert them into custom agent files if Codex custom agent file schemas stabilize for local clients. Claude plugin agent behavior source: https://code.claude.com/docs/en/plugins-reference.md

## 7. Academic and open-source software (OSS) prior art

**Sources**

- STORM [^3] code: engine: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/engine.py
- STORM [^3] code: knowledge curation module: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/knowledge_curation.py
- STORM [^3] code: outline generation module: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/outline_generation.py
- STORM [^3] code: article generation module: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/article_generation.py
- STORM [^3] code: article polish module: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/article_polish.py
- PaperDebugger [^5] code: chat streaming API file: https://github.com/PaperDebugger/PaperDebugger/blob/main/internal/api/chat/create_conversation_message_stream.go
- PaperDebugger [^5]: Claude skill file: https://github.com/PaperDebugger/PaperDebugger/blob/main/.claude/skills/developer/SKILL.md
- PaperQA [^12] as research-agent prior art: main agent code: https://github.com/Future-House/paper-qa/blob/main/src/paperqa/agents/main.py
- PaperQA [^12] as research-agent prior art: search agent code: https://github.com/Future-House/paper-qa/blob/main/src/paperqa/agents/search.py
- PaperQA [^12] as research-agent prior art: agent tests: https://github.com/Future-House/paper-qa/blob/main/tests/test_agents.py
- In2Writing venue sweep: Association for Computational Linguistics (ACL) Anthology venue page: https://aclanthology.org/venues/in2writing/
- In2Writing venue sweep: 2022 volume page: https://aclanthology.org/volumes/2022.in2writing-1/
- In2Writing venue sweep: 2025 volume page: https://aclanthology.org/volumes/2025.in2writing-1/

**Writing theory to operationalize**

- Flower & Hayes' Cognitive Process Theory of Writing [^1] is the canonical source for a cognitive process theory of writing.
- We infer that Flower & Hayes' model [^1] should map cleanly to agent roles:
  - Task environment/context
  - Long-term memory/references
  - Planning
  - Translating/drafting
  - Reviewing
  - Monitor/control
  The mapping is an interpretation of the theory rather than a platform spec.
- Bereiter & Scardamalia [^2] is the canonical source for knowledge-telling vs knowledge-transforming framing.
- A likely novelty angle is to make knowledge-transforming [^2] explicit as an agentic loop:
  - Problem representation
  - Goal refinement
  - Content transformation
  - Rhetorical evaluation
  This treats revision as more than final polish.
- Gero et al. [^6] build on Flower & Hayes' cognitive process model [^1] in "A Design Space for Writing Support Tools Using a Cognitive Process Model of Writing." The paper treats writing as a goal-directed, non-linear process with these components:
  - Planning
  - Translating
  - Reviewing
  It then uses that model to define a design space for writing support tools.
- The Gero et al. [^6] design space covers which part of the writing process a tool supports and how constrained the supported writing goal is. The paper uses the space to review 30 papers from 2017-2021, identify under-studied highly constrained planning and reviewing, and propose shared evaluation methods and tasks.
- We infer that the Gero et al. [^6] paper gives this project the closest taxonomy, but the mechanism is different. That paper uses Flower and Hayes [^1] to classify and compare writing tools. Our plugin should turn the same model into an executable agent architecture, where monitor, planner, translator, and reviewer roles produce observable state transitions and ledger entries.

**In2Writing process-support sweep**

- ACL Anthology lists In2Writing volumes for 2022 and 2025, with 15 and 11 papers respectively; this sweep screened those 26 ACL entries and selected five total additions, including the required Gero et al. design-space paper [^6]. Source: https://aclanthology.org/venues/in2writing/
- Schneider et al. [^7] compare natural language generation (NLG) pipeline architecture with research on the human writing process in "Data-to-text systems as writing environment." They derive principles for data-to-text systems as writing environments. The paper argues that process optimization matters because evaluating all generated output is not feasible in mass text production.
- We infer that Schneider et al. [^7] support the plugin's ledger design. If output-scale evaluation is weak, the tool should expose the decisions that produce the text:
  - Planning
  - Configuration
  - Generation
  - Quality control
- Du et al. [^8] present R3 [^8] in "Read, Revise, Repeat." R3 is a human-in-the-loop iterative text revision system where a model proposes edits, writers accept or reject them, and accepted edits feed the next revision iteration. The evaluation compares:
  - Human-human revision
  - System-human revision
  - System-only revision
  It uses ArXiv, Wikipedia, and Wikinews data.
- R3 [^8] is likely useful as an evaluation pattern for our reviewer role because it measures revision depth, edit acceptance, and human control, not only final text quality.
- Liu and August [^9] study writing center tutoring in "From Crafting Text to Crafting Thought." They interview 10 current writing tutors, ground their practices in writing-center literature, and use those strategies to develop an intelligent writing tool prototype.
- We infer that Liu and August [^9] help define user-facing behavior for the monitor and reviewer: ask what the writer wants to work on, prefer higher-order concerns before sentence-level edits, and keep the writer's ownership visible.
- Kim et al. [^10] argue that revision depends on reflection in their voice-interaction paper. They propose a formative study comparing spoken and written interaction with conversational agents.
- We infer that the Kim et al. [^10] paper gives this project concrete process metrics for a human-in-the-loop experiment:
  - Reflection depth
  - Higher-order concern frequency
  - Turn structure
  - Cognitive load
  - Revision depth

**Large language model (LLM) long-form writing systems**

- STORM [^3] frames long-form Wikipedia-like writing as a pre-writing problem:
  - Discover diverse perspectives
  - Simulate perspective-specific question asking against a source-grounded expert
  - Curate information
  - Create an outline
  The STORM paper reports evaluation on FreshWiki [^3] and feedback from experienced Wikipedia editors.
- STORM [^3] code separates pipeline modules for:
  - Knowledge curation: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/knowledge_curation.py
  - Outline generation: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/outline_generation.py
  - Article generation: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/article_generation.py
  - Article polish: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/article_polish.py
- We infer that STORM [^3] is closest to the planning/research side of Flower & Hayes [^1], but it is less directly a cognitive monitor model because it primarily packages source gathering, outline, generation, and polish as a pipeline.
- PaperDebugger [^5] is described by its arXiv result as an in-editor, multi-agent, plugin-based academic writing assistant for Overleaf/LaTeX workflows.
- The PaperDebugger [^5] GitHub repo contains:
  - A Claude skill at `.claude/skills/developer/SKILL.md`: https://github.com/PaperDebugger/PaperDebugger/blob/main/.claude/skills/developer/SKILL.md
  - Chat streaming API files: https://github.com/PaperDebugger/PaperDebugger/blob/main/internal/api/chat/create_conversation_message_stream.go
  - Project/instruction APIs
  This indicates an implementation that combines editor state, conversation, and agent guidance.
- PaperQA [^12] has an `agents` package with main/search/tools modules and tests, making it useful as a research-agent implementation pattern even though its primary task is question answering over papers rather than writing.
  Sources:
  - https://github.com/Future-House/paper-qa/blob/main/src/paperqa/agents/main.py
  - https://github.com/Future-House/paper-qa/blob/main/src/paperqa/agents/search.py

**Human and artificial intelligence (AI) writing evaluation**

- CoAuthor [^4] is an Association for Computing Machinery (ACM) Conference on Human Factors in Computing Systems (CHI) paper/dataset about human-AI collaborative writing for exploring language model capabilities.
- CoAuthor-style [^4] logged interaction data is likely valuable for evaluating process support because it observes writer prompts, model continuations, acceptance, and revision behavior rather than only final document quality.
- STORM [^3] uses FreshWiki [^3], outline assessments, generated article comparison, and expert Wikipedia-editor feedback.
- For our paper, we should likely combine final-output metrics with these process metrics:
  - Number of plan revisions
  - Evidence coverage
  - Goal satisfaction
  - Revision depth
  - Edit locality
  - Self-identified uncertainties
  - Human acceptance of rhetorical choices

**Gap and novelty**

- Existing systems likely operationalize pieces of writing cognition:
  - STORM [^3] handles research/pre-writing
  - CoAuthor [^4] studies human-AI writing traces
  - PaperDebugger [^5] embeds multi-agent help into an editor
  The open gap is a cross-platform plugin that explicitly maps a classic cognitive writing-process theory to observable skill/subagent roles, state transitions, and experimentable ablations.

## 8. Implications for the agentic cognitive writing process plugin

**Sources**

- Official non-GitHub: Claude skills: https://code.claude.com/docs/en/skills.md
- Official non-GitHub: Claude plugins: https://code.claude.com/docs/en/plugins.md
- Official non-GitHub: Claude subagents: https://code.claude.com/docs/en/sub-agents.md
- Official non-GitHub: OpenAI skills: https://developers.openai.com/codex/build-skills.md
- Official non-GitHub: OpenAI plugins: https://developers.openai.com/plugins/build/plugins.md
- Official non-GitHub: OpenAI subagents: https://learn.chatgpt.com/docs/agent-configuration/subagents.md
- GitHub code: Anthropic `feature-dev` orchestration: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/commands/feature-dev.md
- GitHub code: OpenAI `agents-sdk` skill: https://github.com/openai/plugins/blob/main/plugins/openai-developers/skills/agents-sdk/SKILL.md
- Academic/open-source software (OSS): STORM [^3] code: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/engine.py

**Design options**

1. **Theory-first role decomposition**
   - We infer that the plugin should ship these Claude subagents:
     - `monitor`
     - `planner`
     - `translator`
     - `reviewer`
     - `source-curator`
     - `experiment-grader`
     Top-level skills orchestrate them as a cognitive loop rather than a fixed waterfall.
   - Reuse: Claude plugin `agents/` format for native role routing, Codex skill instructions for native subagent delegation.
   - Avoid: one giant `SKILL.md`; it will violate progressive disclosure and make process ablations hard.

2. **Shared skills, platform-specific wrappers**
   - We infer that canonical instructions should live in:
     - `skills/cognitive-writing-orchestrator/SKILL.md`
     - `skills/knowledge-transforming-revision/SKILL.md`
     - `skills/writing-eval-harness/SKILL.md`
     Add these wrapper files:
     - `.claude-plugin/plugin.json`
     - `.codex-plugin/plugin.json`
     - OpenAI `agents/openai.yaml`
   - Reuse: common Agent Skill layout accepted by both platforms.
   - Avoid: Anthropic-only `compatibility` field in shared `SKILL.md`, because OpenAI validator does not allow it.

3. **Stateful process ledger**
   - We infer that the plugin should use a structured writing ledger in `references/ledger-schema.md` or a script-generated JSON file to record:
     - Rhetorical problem
     - Audience
     - Goals
     - Content plan
     - Source commitments
     - Drafts
     - Revisions
     - Monitor decisions
   - Reuse: STORM [^3] as a pipeline reference for research, outline, draft, and polish. Add Flower & Hayes' model [^1] monitor decisions as first-class data.
   - Avoid: final-output-only grading; it cannot show that cognitive-process support changed behavior.

4. **Eval harness as a skill, not an afterthought**
   - We infer that `writing-eval-harness` should use the Anthropic skill-creator pattern:
     - With-skill vs baseline
     - Assertions
     - Grader
     - Benchmark aggregation
     - Human review viewer concepts
   - Reuse: Anthropic `evals/evals.json`, `grading.json`, benchmark schema, and first-look qualitative review pattern.
   - Avoid: exact-prose assertions. Grade claim grounding, audience-fit, structure, revision quality, and trace evidence.

**Candidate experiment designs**

1. **Full cognitive-loop vs direct drafting**
   - Baselines:
     - Direct single-agent prompt
     - Outline-then-draft prompt
     - STORM-like [^3] research-outline-draft pipeline
   - Treatment: full plugin with monitor/planner/translator/reviewer loop.
   - Metrics:
     - Expert ratings for organization
     - Expert ratings for audience fit
     - Expert ratings for argument quality
     - Expert ratings for factual grounding
     - Process metrics from ledger
     - Source precision/recall
   - Dataset: FreshWiki-like [^3] recent topics for expository writing plus domain-specific technical memos.

2. **Ablation of monitor agent**
   - Baselines: full plugin without monitor; monitor replaced by static checklist.
   - Treatment: monitor subagent controls phase switching, goal conflict detection, and revision triggers.
   - Metrics:
     - Number of unresolved goal conflicts
     - Revision depth
     - Final coherence
     - Unnecessary token/time overhead

3. **Knowledge-telling vs knowledge-transforming revision**
   - Baselines: add facts to draft; generic "improve this" revision.
   - Treatment: explicit knowledge-transforming skill that revises the problem representation and audience/rhetorical goals before editing text.
   - Metrics:
     - Expert judgments of conceptual transformation
     - Expert judgments of argument novelty
     - Expert judgments of paragraph-level purpose clarity
     - Trace-coded plan changes

4. **Human-in-the-loop writing support**
   - Baselines:
     - CoAuthor-style [^4] autocomplete/continuation interface
     - Direct chat writing assistant
   - Treatment: plugin asks targeted monitor/planner questions only when ledger uncertainty is high.
   - Metrics:
     - Accepted suggestions
     - User edits after AI output
     - Time to acceptable draft
     - NASA Task Load Index (NASA-TLX) [^11] or similar workload survey
     - Qualitative interview coding

5. **Cross-platform reproducibility**
   - Baselines: Claude-only plugin and Codex-only skill prompts.
   - Treatment: shared skill repo with generated Claude/OpenAI wrappers.
   - Metrics:
     - Activation accuracy
     - Output quality parity
     - Platform-specific failure modes
     - Validation pass rate (`claude plugin validate`, OpenAI skill validator)
     - Drift between generated wrappers

**Immediate implementation recommendation**

- We infer that the first implementation should start with a minimal dual-manifest plugin that contains three shared skills and four Claude-native agents. Codex support should initially rely on skills that instruct native Codex subagent delegation; do not invent a custom Codex agent-file format beyond documented `agents/openai.yaml` UI/dependency metadata until official custom-agent file details are stable enough to cite.
- We infer that the first paper prototype should privilege observability over maximal automation. Every phase transition should write a ledger entry with:
  - Responsible agent
  - Decision
  - Evidence
  - Open uncertainty
  This makes the Flower & Hayes [^1] mapping testable instead of just metaphorical.

## Footnotes

[^1]: Linda Flower and John R. Hayes. "A Cognitive Process Theory of Writing." College Composition and Communication, 32(4), 1981. DOI: https://doi.org/10.58680/ccc198115885
[^2]: Carl Bereiter and Marlene Scardamalia. The Psychology of Written Composition. Routledge, 1987. DOI/reprint: https://doi.org/10.4324/9780203812310
[^3]: Yijia Shao, Yucheng Jiang, Theodore Kanell, Peter Xu, Omar Khattab, and Monica Lam. "Assisting in Writing Wikipedia-like Articles From Scratch with Large Language Models." Proceedings of the 2024 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies (NAACL-HLT 2024), 2024. DOI: https://doi.org/10.18653/v1/2024.naacl-long.347. arXiv: https://arxiv.org/abs/2402.14207
[^4]: Mina Lee, Percy Liang, and Qian Yang. "CoAuthor: Designing a Human-AI Collaborative Writing Dataset for Exploring Language Model Capabilities." Proceedings of CHI 2022, 2022. DOI: https://doi.org/10.1145/3491102.3502030
[^5]: Junyi Hou, Andre Lin Huikai, Nuo Chen, Yiwei Gong, and Bingsheng He. "PaperDebugger: A Plugin-Based Multi-Agent System for In-Editor Academic Writing, Review, and Editing." arXiv preprint, 2025, revised 2026. arXiv: https://arxiv.org/abs/2512.02589
[^6]: Katy Gero, Alex Calderwood, Charlotte Li, and Lydia Chilton. "A Design Space for Writing Support Tools Using a Cognitive Process Model of Writing." Proceedings of the First Workshop on Intelligent and Interactive Writing Assistants (In2Writing 2022), 2022. DOI: https://doi.org/10.18653/v1/2022.in2writing-1.2. ACL: https://aclanthology.org/2022.in2writing-1.2/. PDF: https://aclanthology.org/2022.in2writing-1.2.pdf
[^7]: Adela Schneider, Andreas Madsack, Johanna Heininger, Ching-Yi Chen, and Robert Weißgraeber. "Data-to-text systems as writing environment." Proceedings of the First Workshop on Intelligent and Interactive Writing Assistants (In2Writing 2022), 2022. DOI: https://doi.org/10.18653/v1/2022.in2writing-1.1. ACL: https://aclanthology.org/2022.in2writing-1.1/
[^8]: Wanyu Du, Zae Myung Kim, Vipul Raheja, Dhruv Kumar, and Dongyeop Kang. "Read, Revise, Repeat: A System Demonstration for Human-in-the-loop Iterative Text Revision." Proceedings of the First Workshop on Intelligent and Interactive Writing Assistants (In2Writing 2022), 2022. DOI: https://doi.org/10.18653/v1/2022.in2writing-1.14. ACL: https://aclanthology.org/2022.in2writing-1.14/
[^9]: Yijun Liu and Tal August. "From Crafting Text to Crafting Thought: Grounding Intelligent Writing Support to Writing Center Pedagogy." Proceedings of the Fourth Workshop on Intelligent and Interactive Writing Assistants (In2Writing 2025), 2025. DOI: https://doi.org/10.18653/v1/2025.in2writing-1.5. ACL: https://aclanthology.org/2025.in2writing-1.5/
[^10]: Jiho Kim, Philippe Laban, Xiang Chen, and Kenneth C. Arnold. "Voice Interaction With Conversational AI Could Facilitate Thoughtful Reflection and Substantive Revision in Writing." Proceedings of the Fourth Workshop on Intelligent and Interactive Writing Assistants (In2Writing 2025), 2025. DOI: https://doi.org/10.18653/v1/2025.in2writing-1.7. ACL: https://aclanthology.org/2025.in2writing-1.7/
[^11]: Sandra G. Hart and Lowell E. Staveland. "Development of NASA-TLX (Task Load Index): Results of Empirical and Theoretical Research." Advances in Psychology, 52, 1988. DOI: https://doi.org/10.1016/S0166-4115(08)62386-9. ScienceDirect: https://www.sciencedirect.com/science/chapter/bookseries/pii/S0166411508623869
[^12]: Andrew D. White. "PaperQA: Retrieval-Augmented Generative Agent for Scientific Research." arXiv preprint, 2023. arXiv: https://arxiv.org/abs/2312.07559
