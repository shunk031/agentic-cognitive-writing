# Experiment runner package

The `agentic-cogwriter-runner` package provides the console command used to run one
Agentic CogWriter experiment condition against one immutable prompt. The
package lives in the uv workspace so its source, tests, and command entry point
are installed from one member project.

Run the package tests from the repository root:

```bash
uv run --package agentic-cogwriter-runner pytest experiments/runner/tests
```

Run the CLI with a completed private runtime configuration:

```bash
uv run --package agentic-cogwriter-runner agentic-cogwriter-runner \
  --manifest experiments/prompts/manifests/writingbench.jsonl \
  --prompt-id writingbench-0001 \
  --condition A1 \
  --platform codex-primary \
  --config /path/to/runtime.json \
  --output-root runs
```

The tracked runtime configuration remains blocked by `REQUIRED_AT_RUNTIME`
placeholders. The runner refuses to start a scored run until the experimenter
provides every protocol-required value.
