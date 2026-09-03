# Agentic CogWriter experiment runner

Agentic CogWriter is the writing system evaluated by this runner. To prepare a scored run, the experimenter uses the committed prompt manifests, supplies a complete runtime configuration, selects a condition and platform, runs the CLI, and inspects the artifacts. The runner starts one headless session per condition and prompt, applies the shared information, timeout, retry, no-retrieval, and output-budget rules, writes the run manifest, and hashes the outputs and traces.

## Layout

| Directory | Contents |
| --- | --- |
| [`config/`](config/) | Runtime gate and model, judge, decoding, seed, and analysis settings |
| [`prompts/`](prompts/) | One immutable manifest per benchmark |
| [`conditions/`](conditions/) | A1 to A6 and B1 to B2 wrapper configs, frozen baseline prompt files, and platform adapters |
| [`src/agentic_cogwriter/runner/`](src/agentic_cogwriter/runner/) | Python subpackage for execution, manifests, budgets, and trace collection |
| [`judge/`](judge/) | Reserved for judge prompts and runners |
| [`human/`](human/) | Reserved for human validation |
| [`analysis/`](analysis/) | Reserved for scoring and statistics |
| [`manifests/`](manifests/) | Run-artifact documentation and generated output |

The judge, human, and analysis directories are reserved and empty. They do not score or inspect experiment outputs.

## Install and test

The repository uses uv for the Python environment. From the repository root, run:

```bash
uv sync
uv run pytest
```

The test suite checks prompt and manifest hashing, runtime placeholder gating, shared output-budget accounting, wrapper metadata, one-session execution, retrieval rejection, and plugin trace collection. The experimenter must resolve any test failure before starting a scored run.

## Prepare a scored run

Use the committed manifests under [`prompts/manifests/`](prompts/manifests/). To regenerate or verify them, follow [`prompts/README.md`](prompts/README.md) and use the `agentic-cogwriter-materialize` entry point. That document defines the manifest schema and the permitted source and hash checks.

The experimenter then creates a complete runtime configuration outside the tracked placeholder file. The configuration must replace every `REQUIRED_AT_RUNTIME` value in [`config/runtime.json`](config/runtime.json), including model and judge assignments, decoding, output budget, timeout, retry policy, seeds, CLI versions, plugin commits, and analysis gates. The runner refuses to start a scored run while one value remains open or a required field is missing.

The A1 to A3 wrappers invoke skills from the `cognitive-writing-baselines` package. The A4 Agentic CogWriter condition uses the `agentic-cognitive-writing` package. A5 and A6 use the `cognitive-writing-experiments` package together with the main package. B1 and B2 use the baseline package and are reported as exploratory conditions.

## Run one condition and prompt

The experimenter chooses the platform and condition. Codex uses `codex exec` and Claude Code uses `claude --print`. Before a Codex session starts, the runner stages the selected skill, its references, and any delegated role skills inside the run workspace; the prompt then tells Codex to read `plugin/skills/<skill>/SKILL.md`. Claude Code wrappers use the platform's plugin invocation. The runner sends the assignment and supplied context through one top-level session. Retries reuse the same command policy and do not add content or budget.

```bash
uv run --package agentic-cogwriter agentic-cogwriter-runner \
  --manifest experiments/prompts/manifests/writingbench.jsonl \
  --prompt-id writingbench-0001 \
  --condition A1 \
  --platform codex-primary \
  --codex-plugin-root /path/to/plugin \
  --config /path/to/runtime.json \
  --output-root runs
```

The default tracked configuration stops in preflight. For Codex, set `--codex-plugin-root` to a directory containing `skills/<skill>/SKILL.md`; the runner copies the required files into the run workspace before invoking Codex. A container run that mounts the plugin at `/plugin` must pass `--codex-plugin-root /plugin`. Codex reads `plugin/skills/<skill>/SKILL.md` from the workspace and does not install a plugin into `CODEX_HOME`. When the option is omitted, the runner selects matching skill files from the wrapper's configured plugin paths. Claude Code uses the plugin directories listed by its selected wrapper.

## Inspect artifacts

Each successful run contains the following files:

- `run-manifest.json` records the prompt, condition, platform, versions, policy status, and run outcome.
- `prompt.txt` preserves the exact composed prompt sent to the top-level session.
- `output.raw` preserves the final output bytes extracted from the headless response.
- `output.normalized.txt` contains the same final output as text for downstream tools.
- `.writing/trace/process.jsonl` contains the selected skill's trace events.
- `checksums.json` contains SHA-256 hashes for the run artifacts when the run reaches artifact finalization.
- `attempt-NNN.events.jsonl`, `attempt-NNN.stdout.raw`, and `attempt-NNN.stderr.raw` preserve each transport stream; failed runs retain them for diagnosis.
- `run-manifest.json` reports `budget_used_tokens` from Codex `turn.completed` usage when available; otherwise the field is `null` and `token_accounting.status` is `monitored-only`. `output_units_used` records the configured post-hoc output-budget measurement.

The run manifest records absolute execution paths and SHA-256 hashes for the staged skill files. The runner also copies `.writing/goals.md` and `.writing/draft.md` when the selected skill creates them. It does not rewrite claims or paragraph boundaries during normalization.

The final response must contain the complete product text. The runner does not substitute `.writing/draft.md`; a response shorter than half of an existing draft fails the run for inspection.

## Policy enforcement

The runner gives every condition the same assignment, supplied context, timeout, retry count, and output budget. It rejects a run when a headless event or accepted output contains web search, browser use, retrieval, an MCP tool call, a URL, a network command, or a bare retrieval token.

Codex first turns use `sandbox_workspace_write.network_access=false`, disable Codex web search, and use the non-interactive `codex exec --json` adapter. Claude Code enables its sandbox, fails if the sandbox is unavailable, prevents unsandboxed commands, uses an empty strict network allowlist, and denies retrieval tools. These platform settings are the primary no-retrieval mechanism; raw-output marker scanning is a secondary tripwire. The manifest records the platform status. A platform that cannot guarantee denial is recorded as `monitored-only` and cannot be represented as enforced.

The adapter passes Claude Code's documented `CLAUDE_CODE_MAX_OUTPUT_TOKENS` setting into each invocation. Codex `exec` has no supported generation-token, temperature, top-p, seed, or stop-rule control, so those Codex controls are `monitored-only`. The runner still applies a post-hoc output-budget check and fails a run that exceeds the configured limit. Claude Code's temperature, top-p, seed, and stop-rule controls are also `monitored-only` because `claude --print` does not document corresponding options. When `output_counting` selects a pinned tokenizer, the runner counts its tokens; otherwise it uses the frozen word rule in the runtime configuration. This is a measurement unit, not a claim that the CLI enforced a word cap.

The judge-side no-retrieval gate belongs to the judge module and is not enforced by this runner. The run manifest records `judge_side: out-of-scope pending judge module`; the judge module must enforce and audit that gate before scoring. A3 does not generate citations. Its retrieval, evidence, and citation trace policy is `N/A` by design. B1 and B2 are outside the confirmatory family.

The adapter behavior was checked against the [Codex non-interactive mode guide](https://developers.openai.com/codex/non-interactive-mode), the [Codex execution adapter](https://github.com/openai/codex/blob/main/sdk/typescript/src/exec.ts), the [Claude Code CLI reference](https://code.claude.com/docs/en/cli-usage), the [Claude Code environment-variable reference](https://code.claude.com/docs/en/env-vars), and the [Claude Code sandbox guide](https://code.claude.com/docs/en/sandboxing). The pinned CLI versions are supplied by `config/runtime.json`; verify them before a scored run.
