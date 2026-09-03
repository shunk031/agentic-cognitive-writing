# Agentic CogWriter experiment runner

Agentic CogWriter is the writing system evaluated by the experiment runner in [`src/agentic_cogwriter/runner/`](src/agentic_cogwriter/runner/). To prepare a scored run, the experimenter uses the committed prompt manifests, supplies a complete runtime configuration, selects a condition and platform, runs the CLI, and inspects the artifacts. The runner starts one headless session per condition and prompt, applies the shared information, timeout, retry, no-retrieval, and output-budget rules, writes the run manifest, and hashes the outputs and traces.

## Layout

| Directory | Contents |
| --- | --- |
| [`config/`](config/) | Runtime gate and model, judge, decoding, seed, and analysis settings |
| [`prompts/`](prompts/) | One immutable manifest per benchmark |
| [`conditions/`](conditions/) | A1 to A6 and B1 to B2 wrapper configs, frozen baseline prompt files, and platform adapters |
| [`src/agentic_cogwriter/runner/`](src/agentic_cogwriter/runner/) | Python subpackage for execution, manifests, budgets, and trace collection |
| [`src/agentic_cogwriter/judges/`](src/agentic_cogwriter/judges/) | API judge client, fail-closed validators, artifact scorer, and CLI |
| [`human/`](human/) | Reserved for human validation |
| [`analysis/`](analysis/) | Reserved for scoring and statistics |
| [`manifests/`](manifests/) | Run-artifact documentation and generated output |

The human and analysis directories remain reserved. The judge package scores completed run artifacts with one OpenAI-compatible API call per judgment.

## Install and test

The repository uses uv for the Python environment. From the repository root, run:

```bash
uv sync
uv run pytest
```

The test suite checks prompt and manifest hashing, runtime placeholder gating, shared output-budget accounting, wrapper metadata, one-session execution, retrieval rejection, plugin trace collection, judge usage counters, complete pairwise presentations, and runtime judge-family evidence. The experimenter must resolve any test failure before starting a scored run.

## Prepare a scored run

Use the committed manifests under [`prompts/manifests/`](prompts/manifests/). To regenerate or verify them, follow [`prompts/README.md`](prompts/README.md) and use the `agentic-cogwriter-materialize` entry point. That document defines the manifest schema and the permitted source and hash checks.

The experimenter then creates a complete runtime configuration outside the tracked placeholder file. The configuration must replace every `REQUIRED_AT_RUNTIME` value in [`config/runtime.json`](config/runtime.json), including model and judge assignments, decoding, output budget, timeout, retry policy, seeds, CLI versions, plugin commits, and analysis gates. The `generator_and_judge_family_audit.generator_families` object must name the generator family for `codex` and `claude-code`; the runner records the selected value in `run-manifest.json`. The runner refuses to start a scored run while one value remains open or a required field is missing.

The A1 to A3 wrappers invoke skills from the `cognitive-writing-baselines` package. The A4 Agentic CogWriter condition uses the `agentic-cognitive-writing` package. A5 and A6 use the `cognitive-writing-experiments` package together with the main package. B1 and B2 use the baseline package and are reported as exploratory conditions.

## Run one condition and prompt

The experimenter chooses the platform and condition. Codex uses `codex exec` and Claude Code uses `claude --print`. Before a Codex session starts, the runner stages the selected skill, its references, and any delegated role skills inside the run workspace; the prompt then tells Codex to read `plugin/skills/<skill>/SKILL.md`. Claude Code wrappers use the platform's plugin invocation. The runner sends the assignment and supplied context through one top-level session. Retries reuse the same command policy and do not add content or budget.

The `--platform` values accepted by `experiments/src/agentic_cogwriter/runner/cli.py` are `codex` for Codex runs and `claude-code` for Claude Code runs. Use the platform value that matches the headless command you intend to execute.

```bash
uv run --package agentic-cogwriter agentic-cogwriter-runner \
  --manifest experiments/prompts/manifests/writingbench.jsonl \
  --prompt-id writingbench-0001 \
  --condition A1 \
  --platform codex \
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
- `run-manifest.json` reports `budget_used_tokens` as the sum of Codex `turn.completed` output and reasoning tokens across the run. A missing or malformed usage record marks the run `unscored` and excludes it from scoring. `output_units_used` records the configured post-hoc output-budget measurement.

The run manifest records absolute execution paths and SHA-256 hashes for the staged skill files. The runner also copies `.writing/goals.md` and `.writing/draft.md` when the selected skill creates them. It does not rewrite claims or paragraph boundaries during normalization.

The final response must contain the complete product text. For A2 to A6, `.writing/draft.md` must exist and the final response must contain at least half of its characters. B1 and B2 use the same draft gate. A1 is the only no-draft baseline and uses a non-empty completeness floor, measured in the configured output unit, with a 10-unit minimum or half of an explicitly requested length when that length is larger. The runner never substitutes `.writing/draft.md` for the response.

The wrapper TOMLs are the source of truth for trace contracts. Each declares the allowed event types, goal-event policy, event-count bounds, process values, and any exact process-transition order. The runner rejects events outside those declarations; `process_switch` events always require `from_process` and `to_process`, and forbidden-goal conditions also require `.writing/goals.md` to remain untouched.

## Score a completed run

The scorer in [`src/agentic_cogwriter/judges/`](src/agentic_cogwriter/judges/) reads a completed run's `run-manifest.json`, `prompt.txt`, and `output.normalized.txt`, then writes `scores.jsonl` and `scores-manifest.json` beside the run artifacts. The manifest records the versioned template hash, source-run hashes, API usage counters, response hash, attempt count, score-record hash, and the runtime judge-family evidence chain. A successful command prints the `scores.jsonl` path. Pairwise scoring writes both presentation records only after both judgments pass validation.

The private judge configuration supplies the requested model, judge identifier, names of the endpoint and credential environment variables, the template path, the API seed, the pairwise presentation seed, decoding settings, timeout, retry count, and an explicit model-family mapping table. Use a configuration outside the repository. Replace every angle-bracket value in the following example with a value you supply at runtime; the template path must point to [`pointwise-v1.txt`](prompts/judges/pointwise-v1.txt) or [`pairwise-v1.txt`](prompts/judges/pairwise-v1.txt).

```json
{
  "task": "pointwise",
  "model": "<judge-model-id>",
  "judge_id": "<judge-id>",
  "model_family_map": {
    "<claude-frontier-model-id>": {"family": "claude", "role": "frontier"},
    "<gpt-frontier-model-id>": {"family": "gpt", "role": "frontier"},
    "<open-evaluator-model-id>": {"family": "prometheus", "role": "open_evaluator"}
  },
  "base_url_env": "<base-url-environment-variable>",
  "credential_env": "<credential-environment-variable>",
  "template_path": "/path/to/repository/experiments/prompts/judges/pointwise-v1.txt",
  "seed": 12345,
  "presentation_seed": 67890,
  "temperature": 0,
  "top_p_or_equivalent": 1,
  "maximum_output_tokens": 512,
  "stop_rules": [],
  "timeout": 120,
  "retry_policy": {"max_retries": 2}
}
```

The base URL and credential environment variables named in the private configuration must be set before the command runs. The scorer resolves both values at call time and never copies either value into a score artifact. The endpoint response must report a model identifier present in `model_family_map`; the scorer derives the judge family from that mapping instead of trusting a configured family label. The judge engine in [`src/agentic_cogwriter/judges/engine.py`](src/agentic_cogwriter/judges/engine.py) replaces the prompt's `runtime-verified` marker with that runtime-derived protocol value before the score record is written. The completed run's `run-manifest.json` must contain `models_and_execution.generator_model_id` and `models_and_execution.generator_model_family`. The scorer rejects generator-family overlap and an open evaluator that is not distinct from both frontier families.

Run one pointwise judgment with the `agentic-cogwriter-score` entry point:

Tests use a fake transport and never contact the serving endpoint. After the user sets the environment variables named in the private configuration, the following command is the real-call verification step:

```bash
uv run --project experiments agentic-cogwriter-score \
  --run-dir /path/to/completed-run \
  --config /path/to/private-judge-config.json
```

The pointwise record follows the five-dimension contract in [`protocol.md`](../docs/experiments/protocol.md). Invalid JSON, missing dimensions, scores outside 1 to 5, and evidence quotes absent from the output or supplied context are rejected. The configured retry count bounds every additional API call, and every attempt keeps the same prompt and decoding payload.

The pairwise command runs both presentations for one unordered pair. The scorer derives the invocation order from `presentation_seed`, records that seed and the derived order mapping in `scores-manifest.json`, and writes two JSON Lines records only after both presentations validate:

```bash
uv run --project experiments agentic-cogwriter-score \
  --run-dir /path/to/run-a \
  --compare-run-dir /path/to/run-b \
  --config /path/to/private-pairwise-config.json
```

The pairwise records follow the balanced tournament contract in [`protocol.md`](../docs/experiments/protocol.md), including both `A|B` and `B|A` presentations, a winner of `A`, `B`, or `tie`, and verbatim evidence for both outputs. If either presentation fails after the configured retries, the scorer writes no aggregate score artifact. WritingBench criteria and HelloBench checklists are outside this judge stage; a benchmark-native judge can be added as a follow-up after the generic contracts are validated.

## Policy enforcement

The runner gives every condition the same assignment, supplied context, timeout, retry count, and output budget. It rejects a run when the parsed event stream records a web search, browser or retrieval tool invocation, or a network command in an executed-command event. Draft artifacts receive a separate explicit network-command scan. URLs and retrieval words in assistant text, configuration echoes, and generic error events do not trigger the transport tripwire.

Codex first turns use `sandbox_workspace_write.network_access=false`, disable Codex web search, and use the non-interactive `codex exec --json` adapter. Claude Code enables its sandbox, fails if the sandbox is unavailable, prevents unsandboxed commands, uses an empty strict network allowlist, and denies retrieval tools. These platform settings are the primary no-retrieval mechanism; raw-output marker scanning is a secondary tripwire. The manifest records the platform status. A platform that cannot guarantee denial is recorded as `monitored-only` and cannot be represented as enforced.

The adapter passes Claude Code's documented `CLAUDE_CODE_MAX_OUTPUT_TOKENS` setting into each invocation. Codex `exec` has no supported generation-token, temperature, top-p, seed, or stop-rule control, so those Codex controls are `monitored-only`; its reported output and reasoning usage is still checked against the shared cap. Claude Code's temperature, top-p, seed, and stop-rule controls are also `monitored-only` because `claude --print` does not document corresponding options. When `output_counting` selects a pinned tokenizer, the runner counts its tokens; otherwise it uses the frozen word rule in the runtime configuration. The measurement unit does not claim that the CLI enforced a word cap.

The judge client has no retrieval or tool interface and receives only the assignment, permitted supplied context, and blinded output or output pair. The score manifest records the runtime family audit before a score becomes aggregatable. A3 does not generate citations. Its retrieval, evidence, and citation trace policy is `N/A` by design. B1 and B2 are outside the confirmatory family.

The adapter behavior was checked against the [Codex non-interactive mode guide](https://developers.openai.com/codex/non-interactive-mode), the [Codex execution adapter](https://github.com/openai/codex/blob/main/sdk/typescript/src/exec.ts), the [Claude Code CLI reference](https://code.claude.com/docs/en/cli-usage), the [Claude Code environment-variable reference](https://code.claude.com/docs/en/env-vars), and the [Claude Code sandbox guide](https://code.claude.com/docs/en/sandboxing). The pinned CLI versions are supplied by `config/runtime.json`; verify them before a scored run.
