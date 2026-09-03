# Experiment runner

The experiment runner starts one headless top-level skill session for each condition and prompt. The experimenter supplies an immutable benchmark prompt manifest and a complete runtime configuration before a scored run. The runner writes the run manifest, invokes the selected package skill, applies the shared no-retrieval and output-budget policy, and hashes the resulting artifacts.

## Layout

| Directory | Contents |
| --- | --- |
| [`config/`](config/) | Runtime gate and model, judge, decoding, seed, and analysis settings |
| [`prompts/`](prompts/) | One immutable manifest per benchmark |
| [`conditions/`](conditions/) | A1 to A8 wrapper configs, frozen A1 to A3 prompt files, and platform adapters |
| [`runner/`](runner/) | Python package for execution, manifests, budgets, and trace collection |
| [`judge/`](judge/) | Reserved for judge prompts and runners |
| [`human/`](human/) | Reserved for human validation |
| [`analysis/`](analysis/) | Reserved for scoring and statistics |
| [`manifests/`](manifests/) | Run-artifact documentation and generated output |

The judge, human, and analysis directories are stubs in this change. They do not score or inspect experiment outputs.

## Install and test

The repository uses uv for the Python environment. From the repository root, run:

```bash
uv sync
uv run pytest
```

The test suite checks prompt and manifest hashing, runtime placeholder gating, shared output-budget accounting, wrapper metadata, one-session execution, retrieval rejection, and plugin trace collection. The experimenter must resolve any test failure before starting a scored run.

## Prepare a scored run

The experimenter first materializes `writingbench.json`, `hellobench.json`, and `dolomites.json` under [`prompts/`](prompts/) using a permitted benchmark source and a pinned source version. Each row needs `prompt_id`, `benchmark_name`, `source_version`, `prompt_text` or `source_reference`, `requested_output_constraints`, and `hash`. The runner accepts a source reference for provenance but does not fetch it at run time. A scored run therefore needs materialized prompt text.

The experimenter then creates a complete runtime configuration outside the tracked placeholder file. The configuration must replace every `REQUIRED_AT_RUNTIME` value in [`config/runtime.json`](config/runtime.json), including model and judge assignments, decoding, output budget, timeout, retry policy, seeds, CLI versions, plugin commits, and analysis gates. The runner refuses to start a scored run while one value remains open or a required field is missing.

The A1 to A3 wrappers name skills from the sibling `cognitive-writing-baselines` package. This deliverable references that package and does not include its implementation. A4 uses the `agentic-cognitive-writing` package. A5 and A6 use the `cognitive-writing-experiments` package together with the main package. A7 and A8 use the baseline package and are reported as exploratory conditions.

## Run one condition and prompt

The experimenter chooses the platform and condition. Codex uses `codex exec` and Claude Code uses `claude --print`. Each wrapper supplies its package skill invocation, and the runner sends the assignment and supplied context through one top-level session. Retries reuse the same command policy and do not add content or budget.

```bash
uv run python -m experiments.runner \
  --manifest experiments/prompts/writingbench.json \
  --prompt-id writingbench-001 \
  --condition A1 \
  --platform codex-primary \
  --config /path/to/runtime.json \
  --output-root runs
```

The default tracked configuration stops in preflight. A1 to A3 require the sibling baseline package, and A4 to A6 require the branch-relative plugin directories named in their wrapper files. The wrapper metadata names installation commands and skill invocations; plugin behavior stays in the referenced packages.

## Inspect artifacts

Each successful run contains `run-manifest.json`, `output.raw`, `output.normalized.txt`, the plugin-owned `.writing/trace/process.jsonl`, and `checksums.json`. Plugin state files such as `.writing/goals.md` and `.writing/draft.md` are copied when present. The runner preserves raw output bytes and does not rewrite claims or paragraph boundaries during normalization.

The runner fails closed when a headless event reports web search, browser use, retrieval, an MCP tool call, or a network command. The runner gives every condition the same timeout, retry count, supplied-context policy, and output budget. A3 does not generate citations. Its retrieval, evidence, and citation trace policy is `N/A` by design. A7 and A8 remain outside the confirmatory family.
