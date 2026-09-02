# Skill/sub-agent survey for agentic cognitive writing process

## Purpose and reading guide

This survey documents the platform formats and writing-system prior art behind the agentic-cognitive-writing plugin. It derives the design that the shipped plugin implements: shared skills, small Claude Code and OpenAI Codex adapter files, four writing-process roles, and observable process state. Shipped plugin source: https://github.com/shunk031/agentic-cognitive-writing/blob/b119e32738dae1768d78d8fe25a172c7a851d6c8/plugin/README.md

A shared skill uses files both platforms can read without translation: `SKILL.md`, `scripts/`, `references/`, and `assets/`.

The shipped plugin provides six skills:

- `cognitive-writing`: main monitor skill
- `planning`: internal role skill
- `translating`: internal role skill
- `reviewing`: internal role skill
- `cognitive-writing-fixed-order`: experiment-comparison variant
- `cognitive-writing-no-goal-network`: experiment-comparison variant

The adapter files hold each platform's packaging and agent metadata:

- Claude Code: `.claude-plugin/` and `agents/*.md`
- OpenAI Codex: `.codex-plugin/` and `agents/openai.yaml`

The shipped plugin uses four roles derived from Flower & Hayes' Cognitive Process Theory of Writing [^1]: `monitor`, `planner`, `translator`, and `reviewer`. The monitor is a skill; the other three are Claude-native agent adapters.

The shipped process trace records phase changes, decisions, evidence, and unresolved questions. The design uses that trace to make writing-process changes measurable, not just final text quality.

The sections below support these choices with official platform documentation, direct source links, and published writing-research citations.

## 1. Anthropic skill format and skill-creator

Anthropic's skill format centers on `SKILL.md`, progressive disclosure, and support folders for scripts, references, and assets.

**Sources for Anthropic skill format**

- Official non-GitHub: Claude Code Skills docs: https://code.claude.com/docs/en/skills.md
- GitHub code: Anthropic skill-creator
  - `SKILL.md`: https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md
  - validator: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py
  - schemas: https://github.com/anthropics/skills/blob/main/skills/skill-creator/references/schemas.md
  - grader agent: https://github.com/anthropics/skills/blob/main/skills/skill-creator/agents/grader.md
  - comparator agent: https://github.com/anthropics/skills/blob/main/skills/skill-creator/agents/comparator.md
  - analyzer agent: https://github.com/anthropics/skills/blob/main/skills/skill-creator/agents/analyzer.md
  - package script: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/package_skill.py
  - benchmark aggregation script: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/aggregate_benchmark.py
  - eval script: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/run_eval.py
  - eval loop script: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/run_loop.py

**`SKILL.md` has strict package metadata**

- Claude Code skills are directories containing `SKILL.md`; `SKILL.md` has YAML Ain't Markup Language (YAML) frontmatter between `---` markers and Markdown instructions, and Claude can invoke the skill by relevance or by `/skill-name`. Source: https://code.claude.com/docs/en/skills.md
- Anthropic skill-creator defines the canonical anatomy as `skill-name/SKILL.md` plus optional `scripts/`, `references/`, and `assets/` directories. Source: https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md
- Anthropic `quick_validate.py` accepts `name`, `description`, `license`, `allowed-tools`, `metadata`, and `compatibility`; `name` and `description` are required. Source: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py
- `name` must be a string and kebab-case with lowercase letters, digits, and hyphens. It must not start with `-`, end with `-`, contain `--`, or exceed 64 characters. Source: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py
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
- Progressive disclosure has three levels: always-visible metadata (`name` + `description`), the `SKILL.md` body when the skill triggers, and optional bundled resources as needed. Anthropic recommends keeping `SKILL.md` under about 500 lines and moving variant-specific details into `references/`. Source: https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md
- Claude Code skill locations include enterprise skills, personal skills at `~/.claude/skills/<skill-name>/SKILL.md`, project skills at `.claude/skills/<skill-name>/SKILL.md`, and plugin skills at `<plugin>/skills/<skill-name>/SKILL.md`. Plugin skills are namespaced as `/plugin-name:skill-name`. Source: https://code.claude.com/docs/en/skills.md
- Claude Code follows symlinked skill folders in personal/project/enterprise skill locations, but plugin symlink behavior is governed by the plugin reference. Source: https://code.claude.com/docs/en/skills.md

**Skill-creator workflow is eval-first**

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
- `evals/evals.json` schema includes `skill_name`, `evals[].id`, `prompt`, `expected_output`, optional `files`, and `expectations`. Source: https://github.com/anthropics/skills/blob/main/skills/skill-creator/references/schemas.md
- `grading.json` expects each assertion under `expectations[]` to use `text`, `passed`, and `evidence`. The viewer depends on these exact field names.
  Sources:
  - https://github.com/anthropics/skills/blob/main/skills/skill-creator/references/schemas.md
  - https://github.com/anthropics/skills/blob/main/skills/skill-creator/eval-viewer/generate_review.py
- `package_skill.py` creates a `.skill` zip archive after running validation and excludes `__pycache__`, `node_modules`, `.DS_Store`, `*.pyc`, and root-level `evals`. Source: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/package_skill.py

## 2. Claude Code plugin format

Claude Code plugins package skills, agents, commands, hooks, and settings under one plugin root with `.claude-plugin/plugin.json` as the manifest.

**Sources for Claude Code plugins**

- Official non-GitHub: Create plugins: https://code.claude.com/docs/en/plugins.md
- Official non-GitHub: Plugins reference: https://code.claude.com/docs/en/plugins-reference.md
- Official non-GitHub: Plugin marketplaces: https://code.claude.com/docs/en/plugin-marketplaces.md
- GitHub code: official marketplace: https://github.com/anthropics/claude-plugins-official/blob/main/.claude-plugin/marketplace.json
- GitHub code: `skill-creator` plugin manifest: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/skill-creator/.claude-plugin/plugin.json
- GitHub code: `feature-dev`
  - plugin manifest: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/.claude-plugin/plugin.json
  - code-explorer agent: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/agents/code-explorer.md
  - code-architect agent: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/agents/code-architect.md
  - code-reviewer agent: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/agents/code-reviewer.md
- GitHub code: command-as-skill example: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/code-review/commands/code-review.md
- GitHub code: hook example: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/hookify/hooks/hooks.json

**Plugin manifest lives under `.claude-plugin`**

- A Claude Code plugin is a self-contained directory of components. The reference lists skills, agents, hooks, Model Context Protocol (MCP) servers, Language Server Protocol (LSP) servers, monitors, `bin/`, and settings as supported components. Source: https://code.claude.com/docs/en/plugins-reference.md
- The manifest lives at `.claude-plugin/plugin.json` and defines `name`, `description`, and optional `version`/`author`. Claude Code uses `name` as the skill namespace. Source: https://code.claude.com/docs/en/plugins.md
- Component directories are at plugin root, not inside `.claude-plugin/`. Peer paths include `skills/`, `commands/`, `agents/`, `hooks/`, `.mcp.json`, `.lsp.json`, `monitors/`, `bin/`, and `settings.json`. Source: https://code.claude.com/docs/en/plugins.md
- A plugin with exactly one skill may place `SKILL.md` directly at plugin root; multi-skill plugins should use `skills/<name>/SKILL.md`. Source: https://code.claude.com/docs/en/plugins.md
- Plugin skills are always namespaced, e.g. `/my-first-plugin:hello`. Source: https://code.claude.com/docs/en/plugins.md

**Plugin components stay at root**

- `skills/` contains skill directories; `commands/` contains flat Markdown skill files and is supported, though new plugins should prefer `skills/`. Source: https://code.claude.com/docs/en/plugins-reference.md
- `agents/` contains Markdown custom agent definitions; plugin agents are loaded under scoped names such as `my-plugin:code-reviewer`. Source: https://code.claude.com/docs/en/plugins-reference.md
- `hooks/hooks.json` or inline `plugin.json` hooks can register `PreToolUse`, `PostToolUse`, `Stop`, and `UserPromptSubmit` event handlers. `hookify` shows hooks calling Python scripts via `${CLAUDE_PLUGIN_ROOT}`.
  Sources:
  - https://code.claude.com/docs/en/plugins-reference.md
  - https://github.com/anthropics/claude-plugins-official/blob/main/plugins/hookify/hooks/hooks.json
- Plugin default `settings.json` currently supports `agent` and `subagentStatusLine`; setting `agent` can activate a plugin custom agent as the main thread. Source: https://code.claude.com/docs/en/plugins.md

**Marketplace and install flow**

- A Claude Code marketplace is `.claude-plugin/marketplace.json` with required `name`, `owner`, and `plugins[]` fields. Each plugin entry requires `name` and `source`. Source: https://code.claude.com/docs/en/plugin-marketplaces.md
- Marketplace sources include relative paths, GitHub repo objects, Git URLs, `git-subdir`, `npm`, HTTPS archives, and command sources. Source: https://code.claude.com/docs/en/plugin-marketplaces.md
- Users add and install with slash commands such as `/plugin marketplace add ./my-marketplace` and `/plugin install quality-review-plugin@my-plugins`. Source: https://code.claude.com/docs/en/plugin-marketplaces.md
- Installed plugins are copied to a cache location except command sources in link mode. Source: https://code.claude.com/docs/en/plugin-marketplaces.md
- Anthropic's official marketplace file demonstrates local `source: "./plugins/agent-sdk-dev"` entries and external `git-subdir`/URL entries. Source: https://github.com/anthropics/claude-plugins-official/blob/main/.claude-plugin/marketplace.json

## 3. Claude Code sub-agent definitions

Claude Code subagents are Markdown files with YAML frontmatter, and plugins ship them from a plugin-root `agents/` directory.

**Sources for Claude Code subagents**

- Official non-GitHub: Subagents docs: https://code.claude.com/docs/en/sub-agents.md
- Official non-GitHub: Plugins reference, agents component: https://code.claude.com/docs/en/plugins-reference.md
- GitHub code: `feature-dev`
  - code-explorer agent: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/agents/code-explorer.md
  - code-architect agent: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/agents/code-architect.md
  - code-reviewer agent: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/agents/code-reviewer.md
  - command invoking agents: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/commands/feature-dev.md
- GitHub code: VoltAgent community example: https://github.com/VoltAgent/awesome-claude-code-subagents/blob/main/categories/09-meta-orchestration/agent-installer.md
- GitHub code: contains-studio community example: https://github.com/contains-studio/agents/blob/main/engineering/ai-engineer.md
- GitHub code: 0xfurai community example: https://github.com/0xfurai/claude-code-subagents/blob/main/agents/openai-api-expert.md

**Subagents are Markdown plus frontmatter**

- File-based subagents use Markdown files with YAML frontmatter followed by the system prompt body; the body becomes the subagent's system prompt. Source: https://code.claude.com/docs/en/sub-agents.md
- Supported frontmatter has required `name` and `description` plus optional controls for tools, model, permissions, turns, skills, MCP servers, hooks, memory, background mode, effort, isolation, color, initial prompt, and cache TTL. Source: https://code.claude.com/docs/en/sub-agents.md
- `name` uses lowercase letters and hyphens; `:` is invalid in the name because plugin-scoped identifiers use colons. Source: https://code.claude.com/docs/en/sub-agents.md
- Claude Code supports project subagents in `.claude/agents/`, user subagents in `~/.claude/agents/`, plugin subagents in a plugin `agents/` directory, and CLI-defined subagents passed as JSON via `--agents`. Source: https://code.claude.com/docs/en/sub-agents.md
- Plugin subagents support `name`, `description`, `model`, `effort`, `maxTurns`, `tools`, `disallowedTools`, `skills`, `memory`, `background`, and `isolation`. They do not support `hooks`, `mcpServers`, or `permissionMode`. Source: https://code.claude.com/docs/en/plugins-reference.md

**Execution and interaction with skills**

- A non-fork subagent starts with fresh isolated context, a task message, relevant `CLAUDE.md` hierarchy, git status, and full content of skills named in the subagent `skills` field. Source: https://code.claude.com/docs/en/sub-agents.md
- The `skills` field preloads full skill content into the subagent at startup; subagents can still invoke unlisted project, user, and plugin skills through the Skill tool. Source: https://code.claude.com/docs/en/sub-agents.md
- Background subagents retain a filtered built-in tool set of 17 tools spanning file, search, shell, web, task, skill, worktree, monitor, messaging, and artifact operations. Source: https://code.claude.com/docs/en/sub-agents.md
- `feature-dev/commands/feature-dev.md` uses a command skill to launch `code-explorer`, `code-architect`, and `code-reviewer` across discovery, design, and quality review phases. Source: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/commands/feature-dev.md
- The shipped plugin represents Flower & Hayes' model [^1] as one monitor skill plus three Claude Code plugin agents:
  - `cognitive-writing`: monitor role, executed by the main agent
  - `planner`: Claude-native agent adapter
  - `translator`: Claude-native agent adapter
  - `reviewer`: Claude-native agent adapter
  Top-level skills orchestrate phase transitions, matching the official pattern where commands and skills route subagents for structured workflows. Evidence: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/commands/feature-dev.md

## 4. OpenAI Codex skill format and skill-creator

Codex uses the same basic `SKILL.md` anatomy as Claude skills, but its validator omits Anthropic's `compatibility` key and adds OpenAI-specific UI metadata through `agents/openai.yaml`.

**Sources for Codex skills**

- Official non-GitHub: Codex build skills: https://developers.openai.com/codex/build-skills.md
- Official non-GitHub: plugin build skills: https://developers.openai.com/plugins/build/skills.md
- Official non-GitHub: Codex build plugins: https://developers.openai.com/codex/build-plugins.md
- GitHub code: OpenAI skill-creator
  - system `SKILL.md`: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/SKILL.md
  - validator: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/quick_validate.py
  - `agents/openai.yaml` reference: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/references/openai_yaml.md
  - skill initializer: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/init_skill.py
  - metadata generator: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/generate_openai_yaml.py

**Codex skill anatomy and discovery**

- Codex skills are directories with required `SKILL.md` plus optional `scripts/`, `references/`, `assets/`, and `agents/openai.yaml` support paths. Source: https://developers.openai.com/codex/build-skills.md
- `SKILL.md` requires `name` and `description`; Codex uses only those frontmatter fields to decide whether to use a skill, then reads the body after the skill triggers.
  Sources:
  - https://developers.openai.com/codex/build-skills.md
  - https://github.com/openai/skills/blob/main/skills/.system/skill-creator/SKILL.md
- Codex loads local skills from the current working directory path `$CWD/.agents/skills`, parent `.agents/skills` directories up to the repo root, `$HOME/.agents/skills`, `/etc/codex/skills`, and bundled system skills. Source: https://developers.openai.com/codex/build-skills.md
- Codex supports explicit invocation with `$skill-name` in CLI/integrated development environment (IDE) or `/skills`, and implicit invocation by matching the `description`. Source: https://developers.openai.com/codex/build-skills.md
- Codex supports symlinked skill folders and follows the symlink target when scanning skill locations. Source: https://developers.openai.com/codex/build-skills.md
- Codex can disable a local skill with `[[skills.config]] path = ".../SKILL.md" enabled = false` in `~/.codex/config.toml`; restart is required after changing config. Source: https://developers.openai.com/codex/build-skills.md
- Codex's initial skill list includes each skill path and is bounded to at most 2% of the model context window or 8,000 characters when context size is unknown; selected skills still load full `SKILL.md`. Source: https://developers.openai.com/codex/build-skills.md

**`agents/openai.yaml` carries optional UI metadata**

- `agents/openai.yaml` is optional user interface (UI)/dependency metadata for ChatGPT and Codex. Supported fields include `interface.display_name`, `short_description`, `icon_small`, `icon_large`, `brand_color`, `default_prompt`, and `dependencies.tools[]` for MCP. Source: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/references/openai_yaml.md
- `policy.allow_implicit_invocation: false` is documented in OpenAI Codex docs as an optional metadata policy controlling implicit invocation while preserving explicit `$skill` invocation. Source: https://developers.openai.com/codex/build-skills.md
- OpenAI `generate_openai_yaml.py` validates interface overrides against `display_name`, `short_description`, `icon_small`, `icon_large`, `brand_color`, and `default_prompt`. It enforces `short_description` length 25-64 characters. Source: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/generate_openai_yaml.py

**Field-by-field diff vs Anthropic**

| Area | Anthropic skill-creator | OpenAI Codex skill-creator | Design consequence |
| --- | --- | --- | --- |
| Required `SKILL.md` fields | Required by validator: `name`, `description`<br>https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py | Required by docs and validator: `name`, `description`<br>https://developers.openai.com/codex/build-skills.md <br> https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/quick_validate.py | Use both everywhere. |
| Allowed frontmatter keys | Allowed by validator: `name`, `description`, `license`, `allowed-tools`, `metadata`, `compatibility`<br>https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py | Allowed by validator: `name`, `description`, `license`, `allowed-tools`, `metadata`<br>https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/quick_validate.py | Avoid `compatibility` if the same file must validate under OpenAI's creator. |
| Name rules | Kebab-case; no leading hyphen, trailing hyphen, or consecutive hyphen; max 64 characters<br>https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py | Hyphen-case; no leading hyphen, trailing hyphen, or consecutive hyphen; max 64 characters<br>https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/quick_validate.py | Same effective rule. |
| Description rules | String; no angle brackets; max 1024 characters<br>https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py | String; no angle brackets; max 1024 characters<br>https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/quick_validate.py | Same effective rule. |
| UI metadata | No Anthropic skill UI metadata file is required by the skill-creator anatomy: https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md | `agents/openai.yaml` is recommended by OpenAI for UI metadata and dependencies: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/SKILL.md | Add `agents/openai.yaml` as OpenAI-only metadata; Claude should ignore it as an ordinary support file. |
| Creation workflow | Emphasizes eval loop, with-skill/baseline subagents, viewer, and grader/comparator/analyzer<br>https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md | Emphasizes lean skills, degree-of-freedom choice, `init_skill.py`, `quick_validate.py`, and real usage iteration<br>https://github.com/openai/skills/blob/main/skills/.system/skill-creator/SKILL.md | Adopt Anthropic's eval workflow and OpenAI's lean/context-budget discipline. |

## 5. Codex multi-agent / sub-agent construction

Codex now has native subagent workflows, while `codex exec` remains useful for scripted child sessions and reproducible automation.

**Sources for Codex multi-agent patterns**

- Official non-GitHub: Codex subagents: https://learn.chatgpt.com/docs/agent-configuration/subagents.md
- Official non-GitHub: Codex CLI and `codex exec`:
  - https://developers.openai.com/codex/cli.md
  - https://learn.chatgpt.com/docs/non-interactive-mode.md
- Official non-GitHub: Codex build skills: https://developers.openai.com/codex/build-skills.md
- GitHub code: OpenAI plugin example manifest: https://github.com/openai/plugins/blob/main/plugins/build-web-apps/.codex-plugin/plugin.json
- GitHub code: OpenAI frontend-app-builder skill: https://github.com/openai/plugins/blob/main/plugins/build-web-apps/skills/frontend-app-builder/SKILL.md
- GitHub code: OpenAI agents-sdk skill: https://github.com/openai/plugins/blob/main/plugins/openai-developers/skills/agents-sdk/SKILL.md
- GitHub code: Codex GitHub Action security docs as automation pattern: https://github.com/openai/codex-action/blob/main/docs/security.md
- GitHub code: STORM [^3]
  - engine: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/engine.py
  - outline generation module: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/outline_generation.py
  - article generation module: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/article_generation.py

**Native Codex capabilities**

- ChatGPT Work and Codex can run subagent workflows by spawning specialized agents in parallel and collecting their results into one response. Source: https://learn.chatgpt.com/docs/agent-configuration/subagents.md
- Current local Codex releases enable subagent workflows by default, and subagent activity appears in the desktop app, CLI, and IDE extension. Source: https://learn.chatgpt.com/docs/agent-configuration/subagents.md
- In Codex CLI, users can ask for subagents explicitly; applicable `AGENTS.md` or skill instructions can also request delegation; `/agent` inspects and switches between agent threads. Source: https://learn.chatgpt.com/docs/agent-configuration/subagents.md
- If no subagent model or `model_reasoning_effort` is configured, a Codex subagent inherits the parent model and reasoning effort; users can also configure `[agents]` defaults or custom agent files. Source: https://learn.chatgpt.com/docs/agent-configuration/subagents.md
- `codex exec` runs non-interactively and supports progress on stderr, final output on stdout, `--ephemeral`, JSON Lines (JSONL) output, output schemas, sandbox selection, and resume. Source: https://learn.chatgpt.com/docs/non-interactive-mode.md
- We infer that a portable Codex sub-agent construction can use either native subagent workflows in local Codex clients or scripts that spawn `codex exec` child sessions and aggregate JSON output.
  Evidence:
  - Native subagents are documented at https://learn.chatgpt.com/docs/agent-configuration/subagents.md
  - `codex exec` automation is documented at https://learn.chatgpt.com/docs/non-interactive-mode.md

**Concrete ecosystem examples**

- Anthropic `feature-dev` plugin shows a skill/command orchestrating separate explorer, architect, and reviewer agents with explicit phase boundaries. Source: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/commands/feature-dev.md
- Anthropic `code-review` command uses multiple agents for eligibility, context discovery, pull request (PR) summary, five parallel review perspectives, and per-issue confidence scoring. Source: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/code-review/commands/code-review.md
- VoltAgent's community `agent-installer` agent installs Claude subagents by fetching category lists and raw `.md` files into `~/.claude/agents/` or `.claude/agents/`. Source: https://github.com/VoltAgent/awesome-claude-code-subagents/blob/main/categories/09-meta-orchestration/agent-installer.md
- contains-studio's `ai-engineer.md` uses Claude subagent frontmatter with `name`, long `description`, `color`, and `tools`. Source: https://github.com/contains-studio/agents/blob/main/engineering/ai-engineer.md
- OpenAI `build-web-apps` plugin uses `.codex-plugin/plugin.json` to package multiple skills and top-level UI metadata. Its `frontend-app-builder` skill coordinates with other installed skills.
  Sources:
  - https://github.com/openai/plugins/blob/main/plugins/build-web-apps/.codex-plugin/plugin.json
  - https://github.com/openai/plugins/blob/main/plugins/build-web-apps/skills/frontend-app-builder/SKILL.md
- OpenAI `openai-developers` `agents-sdk` skill recommends starting with one `Agent`, then adding tools, handoffs, structured outputs, sandbox execution, and eval harnesses only when needed. Source: https://github.com/openai/plugins/blob/main/plugins/openai-developers/skills/agents-sdk/SKILL.md

## 6. Cross-platform single-repo strategies

A dual-target repository works best when shared skills stay platform-neutral and each host gets a small manifest or adapter layer.

**Sources for cross-platform packaging**

- Official non-GitHub: Claude skills docs: https://code.claude.com/docs/en/skills.md
- Official non-GitHub: Claude plugins docs/reference:
  - https://code.claude.com/docs/en/plugins.md
  - https://code.claude.com/docs/en/plugins-reference.md
- Official non-GitHub: OpenAI Codex skills/plugins docs:
  - https://developers.openai.com/codex/build-skills.md
  - https://developers.openai.com/plugins/build/plugins.md
- GitHub code: OpenAI `build-web-apps` plugin manifest: https://github.com/openai/plugins/blob/main/plugins/build-web-apps/.codex-plugin/plugin.json
- GitHub code: OpenAI `frontend-app-builder` skill: https://github.com/openai/plugins/blob/main/plugins/build-web-apps/skills/frontend-app-builder/SKILL.md
- GitHub code: Anthropic `skill-creator`
  - plugin manifest: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/skill-creator/.claude-plugin/plugin.json
  - Agent Skill: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/skill-creator/skills/skill-creator/SKILL.md
- GitHub code: Adobe Claude plugin manifest pointing at `skills`: https://github.com/adobe/skills/blob/main/plugins/creative-cloud/adobe-for-creativity/.claude-plugin/plugin.json

**Strategies for one shared skill tree**

1. **Shared core Agent Skill directory**
   - Both Claude Code and Codex accept a directory with `SKILL.md` plus optional `scripts/`, `references/`, and `assets/` support directories.
     Sources:
     - https://code.claude.com/docs/en/skills.md
     - https://developers.openai.com/codex/build-skills.md
   - The plugin uses canonical skills under `skills/<skill-name>/SKILL.md` and keeps the shared layout strict:
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
   - We infer that a single repo can contain `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json` at plugin root. Both can point to `./skills/`, with platform-specific metadata files in their respective manifest directories.
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
   - We infer that a converter can lint a canonical skill tree and generate `.codex-plugin/plugin.json`, `.claude-plugin/plugin.json`, OpenAI `agents/openai.yaml`, and Claude `agents/*.md` wrappers from a single declarative source.
   - Trade-off: generated files must be checked or regenerated in continuous integration (CI); otherwise the two platforms drift.

**Shipped single-repo layout**

```text
agentic-cognitive-writing-process/
|-- plugin/
|   |-- .claude-plugin/
|   |   `-- plugin.json
|   |-- .codex-plugin/
|   |   `-- plugin.json
|   |-- agents/
|   |   |-- planner.md
|   |   |-- reviewer.md
|   |   `-- translator.md
|   |-- skills/
|   |   |-- cognitive-writing/
|   |   |   |-- SKILL.md
|   |   |   |-- evals/
|   |   |   `-- references/
|   |   |-- planning/
|   |   |   |-- SKILL.md
|   |   |   `-- agents/openai.yaml
|   |   |-- translating/
|   |   |   |-- SKILL.md
|   |   |   `-- agents/openai.yaml
|   |   |-- reviewing/
|   |   |   |-- SKILL.md
|   |   |   `-- agents/openai.yaml
|   |   |-- cognitive-writing-fixed-order/
|   |   |   |-- SKILL.md
|   |   |   |-- agents/openai.yaml
|   |   |   `-- evals/
|   |   `-- cognitive-writing-no-goal-network/
|   |       |-- SKILL.md
|   |       |-- agents/openai.yaml
|   |       `-- evals/
|   `-- README.md
`-- docs/research/skill-subagent-survey.md
```

- The plugin-root `agents/` directory contains Claude subagents for `planner`, `translator`, and `reviewer`, because Claude plugins natively load plugin-root `agents/`. Codex can treat these as reference prompts or convert them into custom agent files if Codex custom agent file schemas stabilize for local clients. Claude plugin agent behavior source: https://code.claude.com/docs/en/plugins-reference.md

## 7. Academic and open-source software (OSS) prior art

Prior systems cover planning, revision, tutoring, and long-form research pipelines, but none of the surveyed systems ships this exact Flower-and-Hayes-to-plugin role architecture.

**Sources for prior art**

- STORM [^3] code:
  - engine: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/engine.py
  - knowledge curation module: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/knowledge_curation.py
  - outline generation module: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/outline_generation.py
  - article generation module: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/article_generation.py
  - article polish module: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/article_polish.py
- PaperDebugger [^5]:
  - code: chat streaming API file: https://github.com/PaperDebugger/PaperDebugger/blob/main/internal/api/chat/create_conversation_message_stream.go
  - Claude skill file: https://github.com/PaperDebugger/PaperDebugger/blob/main/.claude/skills/developer/SKILL.md
- PaperQA [^12] as research-agent prior art:
  - main agent code: https://github.com/Future-House/paper-qa/blob/main/src/paperqa/agents/main.py
  - search agent code: https://github.com/Future-House/paper-qa/blob/main/src/paperqa/agents/search.py
  - agent tests: https://github.com/Future-House/paper-qa/blob/main/tests/test_agents.py
- In2Writing venue sweep:
  - Association for Computational Linguistics (ACL) Anthology venue page: https://aclanthology.org/venues/in2writing/
  - 2022 volume page: https://aclanthology.org/volumes/2022.in2writing-1/
  - 2025 volume page: https://aclanthology.org/volumes/2025.in2writing-1/

**Writing theory maps to roles and trace entries**

- Flower & Hayes' Cognitive Process Theory of Writing [^1] is the theory this plugin operationalizes, and it introduces the monitor/planning/translating/reviewing decomposition used throughout this survey.
- The plugin maps Flower & Hayes' model to task environment/context, long-term memory/references, planning, translating/drafting, reviewing, and monitor/control. The mapping is an interpretation of the theory rather than a platform spec.
- Bereiter & Scardamalia [^2] is the canonical source for knowledge-telling vs knowledge-transforming framing.
- A likely novelty angle is to make knowledge-transforming explicit as an agentic loop over problem representation, goal refinement, content transformation, and rhetorical evaluation. This treats revision as more than final polish.
- Gero et al. [^6] build on Flower & Hayes' cognitive process model in "A Design Space for Writing Support Tools Using a Cognitive Process Model of Writing." The paper treats writing as a goal-directed, non-linear process with planning, translating, and reviewing components, then uses that model to define a design space for writing support tools.
- The Gero et al. design space covers which part of the writing process a tool supports and how constrained the supported writing goal is. The paper uses the space to review 30 papers from 2017-2021, identify under-studied highly constrained planning and reviewing, and propose shared evaluation methods and tasks.
- The Gero et al. paper is likely the closest taxonomy for this project, but the mechanism is different. That paper uses Flower and Hayes to classify and compare writing tools. The plugin turns the same model into an executable agent architecture, where monitor, planner, translator, and reviewer roles produce observable state transitions and trace entries.

**In2Writing process-support sweep**

- Schneider et al. [^7] compare natural language generation (NLG) pipeline architecture with research on the human writing process in "Data-to-text systems as writing environment." They derive principles for data-to-text systems as writing environments. The paper argues that process optimization matters because evaluating all generated output is not feasible in mass text production.
- Schneider et al. likely support the plugin's trace design. If output-scale evaluation is weak, the trace can expose planning, configuration, generation, and quality-control decisions.
- Du et al. present Read, Revise, Repeat (R3) [^8]. R3 is a human-in-the-loop iterative text revision system where a model proposes edits, writers accept or reject them, and accepted edits feed the next revision iteration. The evaluation compares human-human revision, system-human revision, and system-only revision using ArXiv, Wikipedia, and Wikinews data.
- R3 is likely useful as an evaluation pattern for our reviewer role because it measures revision depth, edit acceptance, and human control, not only final text quality.
- Liu and August [^9] study writing center tutoring in "From Crafting Text to Crafting Thought." They interview 10 current writing tutors, ground their practices in writing-center literature, and use those strategies to develop an intelligent writing tool prototype.
- Liu and August likely help define user-facing behavior for the monitor and reviewer: ask what the writer wants to work on, prefer higher-order concerns before sentence-level edits, and keep the writer's ownership visible.
- Kim et al. [^10] argue that revision depends on reflection in their voice-interaction paper. They propose a formative study comparing spoken and written interaction with conversational agents.
- The Kim et al. paper gives this project concrete candidate process metrics for a human-in-the-loop experiment:
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
  The STORM paper reports evaluation on FreshWiki and feedback from experienced Wikipedia editors.
- STORM code separates pipeline modules for:
  - Knowledge curation: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/knowledge_curation.py
  - Outline generation: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/outline_generation.py
  - Article generation: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/article_generation.py
  - Article polish: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/article_polish.py
- We infer that STORM is closest to the planning/research side of Flower & Hayes [^1], but it is less directly a cognitive monitor model because it primarily packages source gathering, outline, generation, and polish as a pipeline.
- PaperDebugger [^5] is described by its arXiv result as an in-editor, multi-agent, plugin-based academic writing assistant for Overleaf/LaTeX workflows.
- The PaperDebugger GitHub repo contains:
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
- CoAuthor-style logged interaction data is likely valuable for evaluating process support because it observes writer prompts, model continuations, acceptance, and revision behavior rather than only final document quality.
- STORM [^3] uses FreshWiki, outline assessments, generated article comparison, and expert Wikipedia-editor feedback.
- For a paper evaluation, the survey points to final-output metrics plus these process metrics:
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
  Among the systems surveyed here, a candidate gap appears to be a cross-platform plugin that explicitly maps a classic cognitive writing-process theory to observable skill/subagent roles, state transitions, and component-removal experiments (ablations).

## 8. Implications for the agentic cognitive writing process plugin

The shipped plugin follows the survey's strongest finding: keep the writing process observable, split the work into small roles, and use shared skills plus host-specific adapters.

**Adopted and considered design options**

1. **Theory-first role decomposition**
   - The shipped plugin uses four writing-process roles:
     - `monitor`: main `cognitive-writing` skill, executed by the main agent
     - `planner`: Claude-native agent adapter
     - `translator`: Claude-native agent adapter
     - `reviewer`: Claude-native agent adapter
   - `source-curator` and `experiment-grader` were considered, but they are not part of the shipped plugin.
   - Top-level skills orchestrate the shipped roles as a cognitive loop rather than a fixed waterfall.
   - Reuse: Claude plugin `agents/` format for native role routing, Codex skill instructions for native subagent delegation.
   - Avoid: one giant `SKILL.md`; it will violate progressive disclosure and make process ablations hard.

2. **Shared skills, platform-specific wrappers**
   - The shipped plugin puts canonical instructions in six skills:
     - `skills/cognitive-writing/SKILL.md`: main monitor skill
     - `skills/planning/SKILL.md`: internal role skill
     - `skills/translating/SKILL.md`: internal role skill
     - `skills/reviewing/SKILL.md`: internal role skill
     - `skills/cognitive-writing-fixed-order/SKILL.md`: experiment-comparison variant
     - `skills/cognitive-writing-no-goal-network/SKILL.md`: experiment-comparison variant
   - The adapter layer adds `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, and OpenAI `agents/openai.yaml`.
   - Reuse: common Agent Skill layout accepted by both platforms.
   - Avoid: Anthropic-only `compatibility` field in shared `SKILL.md`, because OpenAI validator does not allow it.

3. **Stateful process trace**
   - The shipped monitor appends JSON Lines (JSONL) entries to `.writing/trace/process.jsonl` in the user's writing project. The schema lives at `plugin/skills/cognitive-writing/references/trace-jsonl-schema.md`: https://github.com/shunk031/agentic-cognitive-writing/blob/b119e32738dae1768d78d8fe25a172c7a851d6c8/plugin/skills/cognitive-writing/references/trace-jsonl-schema.md
   - The trace records rhetorical problem, audience, goals, content plan, source commitments, drafts, revisions, and monitor decisions.
   - Reuse: STORM [^3] as a pipeline reference for research, outline, draft, and polish. Add Flower & Hayes' model [^1] monitor decisions as first-class data.
   - Avoid: final-output-only grading; it cannot show that cognitive-process support changed behavior.

4. **Eval harness as a considered skill**
   - A `writing-eval-harness` skill remains a considered option. It can use the Anthropic skill-creator pattern of with-skill vs baseline runs, assertions, a grader, benchmark aggregation, and human review viewer concepts.
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
     - Process metrics from trace
     - Source precision/recall
   - Dataset: FreshWiki-like recent topics for expository writing plus domain-specific technical memos.

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
   - Treatment: plugin asks targeted monitor/planner questions only when trace uncertainty is high.
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

**Implementation status and remaining options**

- The shipped implementation starts with a minimal dual-manifest plugin that contains six shared skills, one monitor role in the main skill, and three Claude-native agent adapters. Codex support relies on skills that instruct native Codex subagent delegation. A custom Codex agent-file format beyond documented `agents/openai.yaml` UI/dependency metadata remains a considered option until official custom-agent file details are stable enough to cite.
- The paper prototype design privileges observability over maximal automation. Every phase transition writes a trace entry with responsible agent, decision, evidence, and open uncertainty. This makes the Flower & Hayes [^1] mapping testable instead of just metaphorical.

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
