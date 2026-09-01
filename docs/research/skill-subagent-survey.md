# Skill/Sub-agent Survey for Agentic Cognitive Writing Process

## 目的と読み方

本レポートは、Flower & Hayes (1981) の Cognitive Process Theory of Writing を、Claude Code plugin と OpenAI Codex から使える skills + sub-agents の実装へ落とすための設計根拠である。各節は、(a) 公式 non-GitHub 資料、(b) GitHub 上の直接ファイル、(c) 差分・含意、の順に整理する。ファイル形式・ディレクトリ構成・プラットフォーム挙動に関する主張は、`VERIFIED` または `HYPOTHESIS` を明示した。

冒頭要約: 問いは「認知的な文章産出プロセスを、Claude Code と Codex の両方で動く skill/sub-agent plugin としてどう設計すべきか」である。方法は、各トピックで公式 non-GitHub ドキュメントを先に読み、その後 GitHub の直接ファイルで実装例を確認し、差分を照合した。結論は、共有可能な中核は `SKILL.md` + `scripts/` + `references/` + `assets/` で、Claude には `.claude-plugin/` と `agents/*.md`、Codex には `.codex-plugin/` と `agents/openai.yaml` を薄い adapter として重ねるのが最小リスクというものだ。帰結として、論文用プロトタイプは「monitor / planner / translator / reviewer」の役割と、各判断を記録する process ledger を中心に置き、最終文面だけでなく認知プロセスの変化を評価できるようにするべきである。

調査制約として、GitHub API は途中から `403` を返したため、既に取得済みの API 結果、raw.githubusercontent.com の直接ファイル、公式 Markdown docs を優先した。API 403 後も raw 直指定で読めたファイルは `VERIFIED` とした。読めなかった推測パスは本文の根拠に使わない。

## 1. Anthropic Skill Format & Skill-Creator

**Sources**

- Official non-GitHub: `VERIFIED` Claude Code Skills docs: https://code.claude.com/docs/en/skills.md
- GitHub code: `VERIFIED` Anthropic skill-creator `SKILL.md`: https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md
- GitHub code: `VERIFIED` validator: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py
- GitHub code: `VERIFIED` schemas: https://github.com/anthropics/skills/blob/main/skills/skill-creator/references/schemas.md
- GitHub code: `VERIFIED` grader/comparator/analyzer agents: https://github.com/anthropics/skills/blob/main/skills/skill-creator/agents/grader.md, https://github.com/anthropics/skills/blob/main/skills/skill-creator/agents/comparator.md, https://github.com/anthropics/skills/blob/main/skills/skill-creator/agents/analyzer.md
- GitHub code: `VERIFIED` packaging/eval scripts: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/package_skill.py, https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/aggregate_benchmark.py, https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/run_eval.py, https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/run_loop.py

**Format and constraints**

- `VERIFIED` Claude Code skills are directories containing `SKILL.md`; `SKILL.md` has YAML frontmatter between `---` markers and Markdown instructions, and Claude can invoke the skill by relevance or by `/skill-name`. Source: https://code.claude.com/docs/en/skills.md
- `VERIFIED` Anthropic skill-creator defines the canonical anatomy as `skill-name/SKILL.md` plus optional `scripts/`, `references/`, and `assets/`. Source: https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md
- `VERIFIED` Anthropic `quick_validate.py` accepts frontmatter keys `name`, `description`, `license`, `allowed-tools`, `metadata`, and `compatibility`; `name` and `description` are required. Source: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py
- `VERIFIED` `name` must be a string, kebab-case with lowercase letters, digits, and hyphens; it must not start/end with `-`, contain `--`, or exceed 64 characters. Source: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py
- `VERIFIED` `description` must be a string, must not contain `<` or `>`, and must not exceed 1024 characters. Source: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py
- `VERIFIED` `compatibility` is optional in the validator and, when present, must be a string no longer than 500 characters. Source: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py
- `VERIFIED` Claude Code docs also show a minimal project skill with only `description` frontmatter; the separate Anthropic skill-creator validator is stricter because it requires `name`. Reconciliation: for portability and package validation, include both `name` and `description`; do not rely on Claude Code's fallback tolerance. Sources: https://code.claude.com/docs/en/skills.md and https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py

**Directory conventions and progressive disclosure**

- `VERIFIED` `scripts/` are for deterministic or repetitive executable code; `references/` are for documentation loaded only when needed; `assets/` are for templates, icons, fonts, and other files used in outputs. Source: https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md
- `VERIFIED` Progressive disclosure has three levels: always-visible metadata (`name` + `description`), `SKILL.md` body when the skill triggers, and optional bundled resources as needed. Anthropic recommends keeping `SKILL.md` under about 500 lines and moving variant-specific details into `references/`. Source: https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md
- `VERIFIED` Claude Code skill locations include enterprise, personal `~/.claude/skills/<skill-name>/SKILL.md`, project `.claude/skills/<skill-name>/SKILL.md`, and plugin `<plugin>/skills/<skill-name>/SKILL.md`; plugin skills are namespaced as `/plugin-name:skill-name`. Source: https://code.claude.com/docs/en/skills.md
- `VERIFIED` Claude Code follows symlinked skill folders in personal/project/enterprise skill locations, but plugin symlink behavior is governed by the plugin reference. Source: https://code.claude.com/docs/en/skills.md

**Skill-creator workflow**

- `VERIFIED` Anthropic skill-creator prescribes: capture intent, interview/research, write `SKILL.md`, create 2-3 realistic test prompts, run with-skill and baseline subagents in the same turn, draft assertions while runs proceed, grade, aggregate benchmark, open an eval viewer, read human feedback, improve, repeat, then optionally optimize description. Source: https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md
- `VERIFIED` `evals/evals.json` schema includes `skill_name`, `evals[].id`, `prompt`, `expected_output`, optional `files`, and `expectations`. Source: https://github.com/anthropics/skills/blob/main/skills/skill-creator/references/schemas.md
- `VERIFIED` `grading.json` expects each assertion under `expectations[]` to use `text`, `passed`, and `evidence`; the viewer depends on these exact field names. Sources: https://github.com/anthropics/skills/blob/main/skills/skill-creator/references/schemas.md and https://github.com/anthropics/skills/blob/main/skills/skill-creator/eval-viewer/generate_review.py
- `VERIFIED` `package_skill.py` creates a `.skill` zip archive after running validation and excludes `__pycache__`, `node_modules`, `.DS_Store`, `*.pyc`, and root-level `evals`. Source: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/package_skill.py

## 2. Claude Code Plugin Format

**Sources**

- Official non-GitHub: `VERIFIED` Create plugins: https://code.claude.com/docs/en/plugins.md
- Official non-GitHub: `VERIFIED` Plugins reference: https://code.claude.com/docs/en/plugins-reference.md
- Official non-GitHub: `VERIFIED` Plugin marketplaces: https://code.claude.com/docs/en/plugin-marketplaces.md
- GitHub code: `VERIFIED` official marketplace: https://github.com/anthropics/claude-plugins-official/blob/main/.claude-plugin/marketplace.json
- GitHub code: `VERIFIED` `skill-creator` plugin manifest: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/skill-creator/.claude-plugin/plugin.json
- GitHub code: `VERIFIED` `feature-dev` plugin manifest and agents: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/.claude-plugin/plugin.json, https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/agents/code-explorer.md, https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/agents/code-architect.md, https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/agents/code-reviewer.md
- GitHub code: `VERIFIED` command-as-skill example: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/code-review/commands/code-review.md
- GitHub code: `VERIFIED` hook example: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/hookify/hooks/hooks.json

**Plugin root and manifest**

- `VERIFIED` A Claude Code plugin is a self-contained directory of components that can include skills, agents, hooks, MCP servers, LSP servers, monitors, `bin/`, and settings. Source: https://code.claude.com/docs/en/plugins-reference.md
- `VERIFIED` The manifest lives at `.claude-plugin/plugin.json` and defines plugin identity such as `name`, `description`, and optional `version`/`author`; Claude Code uses `name` as the skill namespace. Source: https://code.claude.com/docs/en/plugins.md
- `VERIFIED` Component directories are at plugin root, not inside `.claude-plugin/`; `skills/`, `commands/`, `agents/`, `hooks/`, `.mcp.json`, `.lsp.json`, `monitors/`, `bin/`, and `settings.json` are peer paths. Source: https://code.claude.com/docs/en/plugins.md
- `VERIFIED` A plugin with exactly one skill may place `SKILL.md` directly at plugin root; multi-skill plugins should use `skills/<name>/SKILL.md`. Source: https://code.claude.com/docs/en/plugins.md
- `VERIFIED` Plugin skills are always namespaced, e.g. `/my-first-plugin:hello`. Source: https://code.claude.com/docs/en/plugins.md

**Bundled components**

- `VERIFIED` `skills/` contains skill directories; `commands/` contains flat Markdown skill files and is supported, though new plugins should prefer `skills/`. Source: https://code.claude.com/docs/en/plugins-reference.md
- `VERIFIED` `agents/` contains Markdown custom agent definitions; plugin agents are loaded under scoped names such as `my-plugin:code-reviewer`. Source: https://code.claude.com/docs/en/plugins-reference.md
- `VERIFIED` `hooks/hooks.json` or inline `plugin.json` hooks can register event handlers; `hookify` shows `PreToolUse`, `PostToolUse`, `Stop`, and `UserPromptSubmit` hooks calling Python scripts via `${CLAUDE_PLUGIN_ROOT}`. Sources: https://code.claude.com/docs/en/plugins-reference.md and https://github.com/anthropics/claude-plugins-official/blob/main/plugins/hookify/hooks/hooks.json
- `VERIFIED` Plugin default `settings.json` currently supports `agent` and `subagentStatusLine`; setting `agent` can activate a plugin custom agent as the main thread. Source: https://code.claude.com/docs/en/plugins.md

**Marketplace and install flow**

- `VERIFIED` A Claude Code marketplace is `.claude-plugin/marketplace.json` with required `name`, `owner`, and `plugins[]`; each plugin entry requires `name` and `source`. Source: https://code.claude.com/docs/en/plugin-marketplaces.md
- `VERIFIED` Marketplace sources include relative paths, GitHub repo objects, Git URLs, `git-subdir`, `npm`, HTTPS archives, and command sources. Source: https://code.claude.com/docs/en/plugin-marketplaces.md
- `VERIFIED` Users add and install with slash commands such as `/plugin marketplace add ./my-marketplace` and `/plugin install quality-review-plugin@my-plugins`. Source: https://code.claude.com/docs/en/plugin-marketplaces.md
- `VERIFIED` Installed plugins are copied to a cache location except command sources in link mode. Source: https://code.claude.com/docs/en/plugin-marketplaces.md
- `VERIFIED` Anthropic's official marketplace file demonstrates local `source: "./plugins/agent-sdk-dev"` entries and external `git-subdir`/URL entries. Source: https://github.com/anthropics/claude-plugins-official/blob/main/.claude-plugin/marketplace.json

## 3. Claude Code Sub-agent Definitions

**Sources**

- Official non-GitHub: `VERIFIED` Subagents docs: https://code.claude.com/docs/en/sub-agents.md
- Official non-GitHub: `VERIFIED` Plugins reference, agents component: https://code.claude.com/docs/en/plugins-reference.md
- GitHub code: `VERIFIED` `feature-dev` agent files: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/agents/code-explorer.md, https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/agents/code-architect.md, https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/agents/code-reviewer.md
- GitHub code: `VERIFIED` `feature-dev` command invoking agents: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/commands/feature-dev.md
- GitHub code: `VERIFIED` community examples: https://github.com/VoltAgent/awesome-claude-code-subagents/blob/main/categories/09-meta-orchestration/agent-installer.md, https://github.com/contains-studio/agents/blob/main/engineering/ai-engineer.md, https://github.com/0xfurai/claude-code-subagents/blob/main/agents/openai-api-expert.md

**Definition format**

- `VERIFIED` File-based subagents use Markdown files with YAML frontmatter followed by the system prompt body; the body becomes the subagent's system prompt. Source: https://code.claude.com/docs/en/sub-agents.md
- `VERIFIED` Supported frontmatter fields include required `name` and `description`, plus optional `tools`, `disallowedTools`, `model`, `permissionMode`, `maxTurns`, `skills`, `mcpServers`, `hooks`, `memory`, `background`, `effort`, `isolation`, `color`, `initialPrompt`, and `experimental.cacheTtl`. Source: https://code.claude.com/docs/en/sub-agents.md
- `VERIFIED` `name` uses lowercase letters and hyphens; `:` is invalid in the name because plugin-scoped identifiers use colons. Source: https://code.claude.com/docs/en/sub-agents.md
- `VERIFIED` Project subagents live in `.claude/agents/`, user subagents in `~/.claude/agents/`, plugin subagents in a plugin `agents/` directory, and CLI-defined subagents can be passed as JSON via `--agents`. Source: https://code.claude.com/docs/en/sub-agents.md
- `VERIFIED` Plugin subagents support `name`, `description`, `model`, `effort`, `maxTurns`, `tools`, `disallowedTools`, `skills`, `memory`, `background`, and `isolation`; plugin-shipped agents do not support `hooks`, `mcpServers`, or `permissionMode`. Source: https://code.claude.com/docs/en/plugins-reference.md

**Execution and interaction with skills**

- `VERIFIED` A non-fork subagent starts with fresh isolated context, a task message, relevant `CLAUDE.md` hierarchy, git status, and full content of skills named in the subagent `skills` field. Source: https://code.claude.com/docs/en/sub-agents.md
- `VERIFIED` The `skills` field preloads full skill content into the subagent at startup; subagents can still invoke unlisted project, user, and plugin skills through the Skill tool. Source: https://code.claude.com/docs/en/sub-agents.md
- `VERIFIED` Background subagents retain a filtered built-in tool set including `Read`, `Grep`, `Glob`, `Bash`, `Edit`, `Write`, `WebFetch`, `WebSearch`, `TodoWrite`, `Skill`, `ToolSearch`, `EnterWorktree`, `ExitWorktree`, `Monitor`, `TaskStop`, `SendMessage`, and `Artifact`. Source: https://code.claude.com/docs/en/sub-agents.md
- `VERIFIED` `feature-dev/commands/feature-dev.md` uses a command skill to launch multiple `code-explorer`, `code-architect`, and `code-reviewer` agents across discovery, design, and quality review phases. Source: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/commands/feature-dev.md
- `HYPOTHESIS` For our writing-process plugin, Claude Code should represent Flower & Hayes monitor/planner/translator/reviewer as plugin agents, while top-level skills orchestrate phase transitions, because official examples already use commands/skills to route subagents for structured workflows. Evidence: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/commands/feature-dev.md

## 4. OpenAI Codex Skill Format & Skill-Creator

**Sources**

- Official non-GitHub: `VERIFIED` Codex build skills: https://developers.openai.com/codex/build-skills.md
- Official non-GitHub: `VERIFIED` plugin build skills: https://developers.openai.com/plugins/build/skills.md
- Official non-GitHub: `VERIFIED` Codex build plugins: https://developers.openai.com/codex/build-plugins.md
- GitHub code: `VERIFIED` OpenAI system skill-creator: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/SKILL.md
- GitHub code: `VERIFIED` OpenAI validator: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/quick_validate.py
- GitHub code: `VERIFIED` `agents/openai.yaml` reference: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/references/openai_yaml.md
- GitHub code: `VERIFIED` OpenAI skill initializer/generator: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/init_skill.py, https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/generate_openai_yaml.py

**Codex skill anatomy and discovery**

- `VERIFIED` Codex skills are directories with required `SKILL.md` plus optional `scripts/`, `references/`, `assets/`, and `agents/openai.yaml`. Source: https://developers.openai.com/codex/build-skills.md
- `VERIFIED` `SKILL.md` requires `name` and `description`; Codex uses only those frontmatter fields to decide whether to use a skill, then reads the body after the skill triggers. Sources: https://developers.openai.com/codex/build-skills.md and https://github.com/openai/skills/blob/main/skills/.system/skill-creator/SKILL.md
- `VERIFIED` Codex loads local skills from `$CWD/.agents/skills`, parent `.agents/skills` directories up to the repo root, `$HOME/.agents/skills`, `/etc/codex/skills`, and bundled system skills. Source: https://developers.openai.com/codex/build-skills.md
- `VERIFIED` Codex supports explicit invocation with `$skill-name` in CLI/IDE or `/skills`, and implicit invocation by matching the `description`. Source: https://developers.openai.com/codex/build-skills.md
- `VERIFIED` Codex supports symlinked skill folders and follows the symlink target when scanning skill locations. Source: https://developers.openai.com/codex/build-skills.md
- `VERIFIED` Codex can disable a local skill with `[[skills.config]] path = ".../SKILL.md" enabled = false` in `~/.codex/config.toml`; restart is required after changing config. Source: https://developers.openai.com/codex/build-skills.md
- `VERIFIED` Codex's initial skill list includes each skill path and is bounded to at most 2% of the model context window or 8,000 characters when context size is unknown; selected skills still load full `SKILL.md`. Source: https://developers.openai.com/codex/build-skills.md

**OpenAI optional metadata**

- `VERIFIED` `agents/openai.yaml` is optional UI/dependency metadata for ChatGPT and Codex; supported fields include `interface.display_name`, `short_description`, `icon_small`, `icon_large`, `brand_color`, `default_prompt`, and `dependencies.tools[]` for MCP. Source: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/references/openai_yaml.md
- `VERIFIED` `policy.allow_implicit_invocation: false` is documented in OpenAI Codex docs as an optional metadata policy controlling implicit invocation while preserving explicit `$skill` invocation. Source: https://developers.openai.com/codex/build-skills.md
- `VERIFIED` OpenAI `generate_openai_yaml.py` validates interface overrides against `display_name`, `short_description`, `icon_small`, `icon_large`, `brand_color`, and `default_prompt`; it enforces `short_description` length 25-64 characters. Source: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/generate_openai_yaml.py

**Field-by-field diff vs Anthropic**

| Area | Anthropic skill-creator | OpenAI Codex skill-creator | Design consequence |
| --- | --- | --- | --- |
| Required `SKILL.md` fields | `VERIFIED` `name`, `description` required by validator: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py | `VERIFIED` `name`, `description` required by docs and validator: https://developers.openai.com/codex/build-skills.md, https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/quick_validate.py | Use both everywhere. |
| Allowed frontmatter keys | `VERIFIED` `name`, `description`, `license`, `allowed-tools`, `metadata`, `compatibility`: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py | `VERIFIED` `name`, `description`, `license`, `allowed-tools`, `metadata`: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/quick_validate.py | Avoid `compatibility` if the same file must validate under OpenAI's creator. |
| Name rules | `VERIFIED` kebab-case, no leading/trailing/consecutive hyphen, max 64: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py | `VERIFIED` hyphen-case, no leading/trailing/consecutive hyphen, max 64: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/quick_validate.py | Same effective rule. |
| Description rules | `VERIFIED` string, no angle brackets, max 1024: https://github.com/anthropics/skills/blob/main/skills/skill-creator/scripts/quick_validate.py | `VERIFIED` string, no angle brackets, max 1024: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/quick_validate.py | Same effective rule. |
| UI metadata | `VERIFIED` No Anthropic skill UI metadata file is required by the skill-creator anatomy: https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md | `VERIFIED` `agents/openai.yaml` is recommended by OpenAI for UI metadata and dependencies: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/SKILL.md | Add `agents/openai.yaml` as OpenAI-only metadata; Claude should ignore it as an ordinary support file. |
| Creation workflow | `VERIFIED` Emphasizes eval loop, with-skill/baseline subagents, viewer, grader/comparator/analyzer: https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md | `VERIFIED` Emphasizes lean skills, degree-of-freedom choice, `init_skill.py`, `quick_validate.py`, and real usage iteration: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/SKILL.md | Adopt Anthropic's eval workflow and OpenAI's lean/context-budget discipline. |

## 5. Codex Multi-agent / Sub-agent Construction

**Sources**

- Official non-GitHub: `VERIFIED` Codex subagents: https://learn.chatgpt.com/docs/agent-configuration/subagents.md
- Official non-GitHub: `VERIFIED` Codex CLI and `codex exec`: https://developers.openai.com/codex/cli.md and https://learn.chatgpt.com/docs/non-interactive-mode.md
- Official non-GitHub: `VERIFIED` Codex build skills: https://developers.openai.com/codex/build-skills.md
- GitHub code: `VERIFIED` OpenAI plugin example manifest and skills: https://github.com/openai/plugins/blob/main/plugins/build-web-apps/.codex-plugin/plugin.json, https://github.com/openai/plugins/blob/main/plugins/build-web-apps/skills/frontend-app-builder/SKILL.md, https://github.com/openai/plugins/blob/main/plugins/openai-developers/skills/agents-sdk/SKILL.md
- GitHub code: `VERIFIED` Codex GitHub Action security docs as automation pattern: https://github.com/openai/codex-action/blob/main/docs/security.md
- GitHub code: `VERIFIED` STORM implementation pipeline: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/engine.py, https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/outline_generation.py, https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/article_generation.py

**Native Codex capabilities**

- `VERIFIED` ChatGPT Work and Codex can run subagent workflows by spawning specialized agents in parallel and collecting their results into one response. Source: https://learn.chatgpt.com/docs/agent-configuration/subagents.md
- `VERIFIED` Current local Codex releases enable subagent workflows by default, and subagent activity appears in the desktop app, CLI, and IDE extension. Source: https://learn.chatgpt.com/docs/agent-configuration/subagents.md
- `VERIFIED` In Codex CLI, users can ask for subagents explicitly; applicable `AGENTS.md` or skill instructions can also request delegation; `/agent` inspects and switches between agent threads. Source: https://learn.chatgpt.com/docs/agent-configuration/subagents.md
- `VERIFIED` If no subagent model or `model_reasoning_effort` is configured, a Codex subagent inherits the parent model and reasoning effort; users can also configure `[agents]` defaults or custom agent files. Source: https://learn.chatgpt.com/docs/agent-configuration/subagents.md
- `VERIFIED` `codex exec` runs non-interactively, streams progress to stderr, prints final output to stdout, supports `--ephemeral`, JSONL output, output schemas, sandbox selection, and resume. Source: https://learn.chatgpt.com/docs/non-interactive-mode.md
- `HYPOTHESIS` A portable Codex sub-agent construction can be implemented either with native subagent workflows in local Codex clients or by scripts that spawn `codex exec` child sessions and aggregate JSON output. Evidence: native subagents are documented at https://learn.chatgpt.com/docs/agent-configuration/subagents.md and `codex exec` automation is documented at https://learn.chatgpt.com/docs/non-interactive-mode.md

**Concrete ecosystem examples**

- `VERIFIED` Anthropic `feature-dev` plugin shows a skill/command orchestrating separate explorer, architect, and reviewer agents with explicit phase boundaries. Source: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/commands/feature-dev.md
- `VERIFIED` Anthropic `code-review` command uses multiple agents for eligibility, context discovery, PR summary, five parallel review perspectives, and per-issue confidence scoring. Source: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/code-review/commands/code-review.md
- `VERIFIED` VoltAgent's community `agent-installer` agent installs Claude subagents by fetching category lists and raw `.md` files into `~/.claude/agents/` or `.claude/agents/`. Source: https://github.com/VoltAgent/awesome-claude-code-subagents/blob/main/categories/09-meta-orchestration/agent-installer.md
- `VERIFIED` contains-studio's `ai-engineer.md` uses Claude subagent frontmatter with `name`, long `description`, `color`, and `tools`. Source: https://github.com/contains-studio/agents/blob/main/engineering/ai-engineer.md
- `VERIFIED` OpenAI `build-web-apps` plugin uses `.codex-plugin/plugin.json` to package multiple skills and top-level UI metadata, and its `frontend-app-builder` skill coordinates with other installed skills. Sources: https://github.com/openai/plugins/blob/main/plugins/build-web-apps/.codex-plugin/plugin.json and https://github.com/openai/plugins/blob/main/plugins/build-web-apps/skills/frontend-app-builder/SKILL.md
- `VERIFIED` OpenAI `openai-developers` `agents-sdk` skill recommends starting with one `Agent`, then adding tools, handoffs, structured outputs, sandbox execution, and eval harnesses only when needed. Source: https://github.com/openai/plugins/blob/main/plugins/openai-developers/skills/agents-sdk/SKILL.md

## 6. Cross-platform Single-repo Strategies

**Sources**

- Official non-GitHub: `VERIFIED` Claude skills docs: https://code.claude.com/docs/en/skills.md
- Official non-GitHub: `VERIFIED` Claude plugins docs/reference: https://code.claude.com/docs/en/plugins.md and https://code.claude.com/docs/en/plugins-reference.md
- Official non-GitHub: `VERIFIED` OpenAI Codex skills/plugins docs: https://developers.openai.com/codex/build-skills.md and https://developers.openai.com/plugins/build/plugins.md
- GitHub code: `VERIFIED` OpenAI `build-web-apps` plugin: https://github.com/openai/plugins/blob/main/plugins/build-web-apps/.codex-plugin/plugin.json and https://github.com/openai/plugins/blob/main/plugins/build-web-apps/skills/frontend-app-builder/SKILL.md
- GitHub code: `VERIFIED` Anthropic `skill-creator` plugin wrapping an Agent Skill: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/skill-creator/.claude-plugin/plugin.json and https://github.com/anthropics/claude-plugins-official/blob/main/plugins/skill-creator/skills/skill-creator/SKILL.md
- GitHub code: `VERIFIED` Adobe Claude plugin manifest pointing at `skills`: https://github.com/adobe/skills/blob/main/plugins/creative-cloud/adobe-for-creativity/.claude-plugin/plugin.json

**Strategies**

1. **Shared core Agent Skill directory**
   - `VERIFIED` Both Claude Code and Codex accept a directory with `SKILL.md` plus optional `scripts/`, `references/`, and `assets/`. Sources: https://code.claude.com/docs/en/skills.md and https://developers.openai.com/codex/build-skills.md
   - `HYPOTHESIS` Put canonical skills under `skills/<skill-name>/SKILL.md`, avoid Anthropic-only `compatibility`, add OpenAI-only `agents/openai.yaml`, and keep Claude plugin metadata outside the skill directory. This maximizes reuse because the common denominator is `SKILL.md` + support folders.
   - Trade-off: Claude project discovery wants `.claude/skills/`, Codex wants `.agents/skills/`; a bare `skills/` root needs plugin manifests, symlinks, or install scripts.

2. **Dual plugin manifests over one `skills/` tree**
   - `VERIFIED` Claude plugins use `.claude-plugin/plugin.json`; OpenAI plugins use `.codex-plugin/plugin.json`. Sources: https://code.claude.com/docs/en/plugins.md and https://developers.openai.com/plugins/build/plugins.md
   - `VERIFIED` OpenAI plugin manifests can point `skills` at `./skills/`; Claude plugin docs likewise load `skills/` at plugin root. Sources: https://developers.openai.com/plugins/build/skills.md and https://code.claude.com/docs/en/plugins-reference.md
   - `HYPOTHESIS` A single repo can contain both `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json` at plugin root, both pointing to `./skills/`, with platform-specific metadata files in their respective manifest directories.
   - Trade-off: marketplace schemas, install commands, UI metadata, and subagent definitions still diverge.

3. **Symlinked local authoring**
   - `VERIFIED` Claude follows symlinked skill folders in personal/project skill locations; Codex follows symlink targets when scanning skill folders. Sources: https://code.claude.com/docs/en/skills.md and https://developers.openai.com/codex/build-skills.md
   - `HYPOTHESIS` During development, symlink `.claude/skills/<name>` and `.agents/skills/<name>` to the same canonical `skills/<name>` folder.
   - Trade-off: plugin packaging and cache copy semantics can break references outside the plugin directory; avoid `../shared` runtime dependencies in distributed packages. Claude install-cache warning: https://code.claude.com/docs/en/plugin-marketplaces.md

4. **Adapter generation**
   - `VERIFIED` OpenAI provides `init_skill.py` and `generate_openai_yaml.py` for generating `agents/openai.yaml`. Sources: https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/init_skill.py and https://github.com/openai/skills/blob/main/skills/.system/skill-creator/scripts/generate_openai_yaml.py
   - `VERIFIED` Anthropic validates plugins with `claude plugin validate` according to Claude docs. Source: https://code.claude.com/docs/en/plugins.md
   - `HYPOTHESIS` A converter can lint a canonical skill tree, generate `.codex-plugin/plugin.json`, `.claude-plugin/plugin.json`, OpenAI `agents/openai.yaml`, and Claude `agents/*.md` wrappers from a single declarative source.
   - Trade-off: generated files must be checked or regenerated in CI; otherwise the two surfaces drift.

**Recommended single-repo layout**

```text
agentic-cognitive-writing-process/
├── .claude-plugin/
│   └── plugin.json
├── .codex-plugin/
│   └── plugin.json
├── skills/
│   ├── cognitive-writing-orchestrator/
│   │   ├── SKILL.md
│   │   ├── agents/
│   │   │   └── openai.yaml
│   │   ├── references/
│   │   └── scripts/
│   └── revision-evaluator/
│       └── SKILL.md
├── agents/
│   ├── monitor.md
│   ├── planner.md
│   ├── translator.md
│   └── reviewer.md
└── docs/
```

- `HYPOTHESIS` The root `agents/` directory should be Claude subagents, because Claude plugins natively load plugin-root `agents/`; Codex can treat these as reference prompts or convert them into custom agent files if Codex custom agent file schemas stabilize for local clients. Claude plugin agent behavior source: https://code.claude.com/docs/en/plugins-reference.md

## 7. Academic & OSS Prior Art

**Sources**

- Foundational theory: `VERIFIED` Flower & Hayes DOI/Crossref: https://doi.org/10.58680/ccc198115885
- Foundational theory: `VERIFIED` Bereiter & Scardamalia book/reprint DOI/Crossref: https://doi.org/10.4324/9780203812310
- STORM paper: `VERIFIED` NAACL DOI/Crossref and arXiv: https://doi.org/10.18653/v1/2024.naacl-long.347 and https://arxiv.org/abs/2402.14207
- STORM code: `VERIFIED` engine and modules: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/engine.py, https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/knowledge_curation.py, https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/outline_generation.py, https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/article_generation.py, https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/article_polish.py
- CoAuthor dataset: `VERIFIED` ACM DOI/Crossref: https://doi.org/10.1145/3491102.3502030
- PaperDebugger: `VERIFIED` arXiv API result and GitHub code tree files: https://arxiv.org/abs/2512.02589 and https://github.com/PaperDebugger/PaperDebugger/blob/main/internal/api/chat/create_conversation_message_stream.go, https://github.com/PaperDebugger/PaperDebugger/blob/main/.claude/skills/developer/SKILL.md
- PaperQA as research-agent prior art: `VERIFIED` GitHub code files: https://github.com/Future-House/paper-qa/blob/main/src/paperqa/agents/main.py, https://github.com/Future-House/paper-qa/blob/main/src/paperqa/agents/search.py, https://github.com/Future-House/paper-qa/blob/main/tests/test_agents.py

**Writing theory to operationalize**

- `VERIFIED` Flower & Hayes' 1981 article is the canonical source for a cognitive process theory of writing. Source: https://doi.org/10.58680/ccc198115885
- `HYPOTHESIS` The model should map cleanly to agent roles: task environment/context, long-term memory/references, planning, translating/drafting, reviewing, and monitor/control. The mapping is an interpretation of the theory rather than a platform spec; source for the theory identity: https://doi.org/10.58680/ccc198115885
- `VERIFIED` Bereiter & Scardamalia's written-composition work is a canonical source for knowledge-telling vs knowledge-transforming framing. Source: https://doi.org/10.4324/9780203812310
- `HYPOTHESIS` A novelty angle is to make knowledge-transforming explicit as an agentic loop: problem representation -> goal refinement -> content transformation -> rhetorical evaluation, rather than treating "revision" as a final polish step.

**LLM long-form writing systems**

- `VERIFIED` STORM frames long-form Wikipedia-like writing as a pre-writing problem: discover diverse perspectives, simulate perspective-specific question asking against a source-grounded expert, curate information, and create an outline; its paper reports evaluation on FreshWiki and feedback from experienced Wikipedia editors. Sources: https://arxiv.org/abs/2402.14207 and https://doi.org/10.18653/v1/2024.naacl-long.347
- `VERIFIED` STORM code separates pipeline modules for knowledge curation, outline generation, article generation, and article polish. Sources: https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/knowledge_curation.py, https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/outline_generation.py, https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/article_generation.py, https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/modules/article_polish.py
- `HYPOTHESIS` STORM is closest to the planning/research side of Flower & Hayes, but it is less directly a cognitive monitor model because it primarily packages source gathering, outline, generation, and polish as a pipeline.
- `VERIFIED` PaperDebugger is described by its arXiv result as an in-editor, multi-agent, plugin-based academic writing assistant for Overleaf/LaTeX workflows. Source: https://arxiv.org/abs/2512.02589
- `VERIFIED` PaperDebugger's GitHub repo contains a Claude skill at `.claude/skills/developer/SKILL.md`, chat streaming API files, and project/instruction APIs, indicating an implementation that combines editor state, conversation, and agent guidance. Sources: https://github.com/PaperDebugger/PaperDebugger/blob/main/.claude/skills/developer/SKILL.md and https://github.com/PaperDebugger/PaperDebugger/blob/main/internal/api/chat/create_conversation_message_stream.go
- `VERIFIED` PaperQA has an `agents` package with main/search/tools modules and tests, making it useful as a research-agent implementation pattern even though its primary task is question answering over papers rather than writing. Sources: https://github.com/Future-House/paper-qa/blob/main/src/paperqa/agents/main.py and https://github.com/Future-House/paper-qa/blob/main/src/paperqa/agents/search.py

**Human-AI writing evaluation**

- `VERIFIED` CoAuthor is an ACM CHI paper/dataset about human-AI collaborative writing for exploring language model capabilities. Source: https://doi.org/10.1145/3491102.3502030
- `HYPOTHESIS` CoAuthor-style logged interaction data is valuable for evaluating process support because it observes writer prompts, model continuations, acceptance, and revision behavior rather than only final document quality.
- `VERIFIED` STORM uses FreshWiki, outline assessments, generated article comparison, and expert Wikipedia-editor feedback. Source: https://arxiv.org/abs/2402.14207
- `HYPOTHESIS` For our paper, combine final-output metrics with process metrics: number of plan revisions, evidence coverage, goal satisfaction, revision depth, edit locality, self-identified uncertainties, and human acceptance of rhetorical choices.

**Gap and novelty**

- `HYPOTHESIS` Existing systems operationalize pieces of writing cognition: STORM handles research/pre-writing, CoAuthor studies human-AI writing traces, and PaperDebugger embeds multi-agent help into an editor. The open gap is a cross-platform plugin that explicitly maps a classic cognitive writing-process theory to observable skill/subagent roles, state transitions, and experimentable ablations.

## 8. Implications for the Agentic Cognitive Writing Process Plugin

**Sources**

- Official non-GitHub: `VERIFIED` Claude skills/plugins/subagents: https://code.claude.com/docs/en/skills.md, https://code.claude.com/docs/en/plugins.md, https://code.claude.com/docs/en/sub-agents.md
- Official non-GitHub: `VERIFIED` OpenAI skills/plugins/subagents: https://developers.openai.com/codex/build-skills.md, https://developers.openai.com/plugins/build/plugins.md, https://learn.chatgpt.com/docs/agent-configuration/subagents.md
- GitHub code: `VERIFIED` Anthropic `feature-dev` orchestration: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/feature-dev/commands/feature-dev.md
- GitHub code: `VERIFIED` OpenAI `agents-sdk` skill: https://github.com/openai/plugins/blob/main/plugins/openai-developers/skills/agents-sdk/SKILL.md
- Academic/OSS: `VERIFIED` STORM paper/code: https://arxiv.org/abs/2402.14207 and https://github.com/stanford-oval/storm/blob/main/knowledge_storm/storm_wiki/engine.py

**Design options**

1. **Theory-first role decomposition**
   - `HYPOTHESIS` Ship Claude subagents: `monitor`, `planner`, `translator`, `reviewer`, `source-curator`, and `experiment-grader`. Top-level skills orchestrate them as a cognitive loop rather than a fixed waterfall.
   - Reuse: Claude plugin `agents/` format for native role routing, Codex skill instructions for native subagent delegation.
   - Avoid: one giant `SKILL.md`; it will violate progressive disclosure and make process ablations hard.

2. **Shared skills, platform-specific wrappers**
   - `HYPOTHESIS` Keep canonical instructions in `skills/cognitive-writing-orchestrator/SKILL.md`, `skills/knowledge-transforming-revision/SKILL.md`, and `skills/writing-eval-harness/SKILL.md`. Add `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, and OpenAI `agents/openai.yaml`.
   - Reuse: common Agent Skill layout accepted by both platforms.
   - Avoid: Anthropic-only `compatibility` field in shared `SKILL.md`, because OpenAI validator does not allow it.

3. **Stateful process ledger**
   - `HYPOTHESIS` Use a structured writing ledger in `references/ledger-schema.md` or a script-generated JSON file to record rhetorical problem, audience, goals, content plan, source commitments, drafts, revisions, and monitor decisions.
   - Reuse: STORM's separation of research/outline/draft/polish as a pipeline reference, but add Flower & Hayes monitor decisions as first-class data.
   - Avoid: final-output-only grading; it cannot show that cognitive-process scaffolding changed behavior.

4. **Eval harness as a skill, not an afterthought**
   - `HYPOTHESIS` Implement `writing-eval-harness` using the Anthropic skill-creator pattern: with-skill vs baseline, assertions, grader, benchmark aggregation, and human review viewer concepts.
   - Reuse: Anthropic `evals/evals.json`, `grading.json`, benchmark schema, and first-look qualitative review pattern.
   - Avoid: exact-prose assertions. Grade claim grounding, audience-fit, structure, revision quality, and trace evidence.

**Candidate experiment designs**

1. **Full cognitive-loop vs direct drafting**
   - Baselines: direct single-agent prompt; outline-then-draft prompt; STORM-like research-outline-draft pipeline.
   - Treatment: full plugin with monitor/planner/translator/reviewer loop.
   - Metrics: expert ratings for organization, audience fit, argument quality, factual grounding; process metrics from ledger; source precision/recall.
   - Dataset: FreshWiki-like recent topics for expository writing plus domain-specific technical memos.

2. **Ablation of monitor agent**
   - Baselines: full plugin without monitor; monitor replaced by static checklist.
   - Treatment: monitor subagent controls phase switching, goal conflict detection, and revision triggers.
   - Metrics: number of unresolved goal conflicts, revision depth, final coherence, unnecessary token/time overhead.

3. **Knowledge-telling vs knowledge-transforming revision**
   - Baselines: add facts to draft; generic "improve this" revision.
   - Treatment: explicit knowledge-transforming skill that revises the problem representation and audience/rhetorical goals before editing text.
   - Metrics: expert judgments of conceptual transformation, argument novelty, paragraph-level purpose clarity, and trace-coded plan changes.

4. **Human-in-the-loop writing support**
   - Baselines: CoAuthor-style autocomplete/continuation interface; direct chat writing assistant.
   - Treatment: plugin asks targeted monitor/planner questions only when ledger uncertainty is high.
   - Metrics: accepted suggestions, user edits after AI output, time to acceptable draft, NASA-TLX or similar workload survey, qualitative interview coding.

5. **Cross-platform reproducibility**
   - Baselines: Claude-only plugin and Codex-only skill prompts.
   - Treatment: shared skill repo with generated Claude/OpenAI wrappers.
   - Metrics: activation accuracy, output quality parity, platform-specific failure modes, validation pass rate (`claude plugin validate`, OpenAI skill validator), and drift between generated wrappers.

**Immediate implementation recommendation**

- `HYPOTHESIS` Start with a minimal dual-manifest plugin that contains three shared skills and four Claude-native agents. Codex support should initially rely on skills that instruct native Codex subagent delegation; do not invent a custom Codex agent-file format beyond documented `agents/openai.yaml` UI/dependency metadata until official custom-agent file details are stable enough to cite.
- `HYPOTHESIS` The first paper prototype should privilege observability over maximal automation: every phase transition should write a ledger entry with the responsible agent, decision, evidence, and open uncertainty. This makes the Flower & Hayes mapping testable instead of just metaphorical.
