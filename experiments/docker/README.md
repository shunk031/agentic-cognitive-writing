# Docker experiment environment

The Docker environment runs the experiment runner in a disposable container while keeping the repository as the working tree on the host. The image contains Python 3.12.11, Node.js 24.7.0, uv 0.11.32, git 2.39.5, Codex CLI 0.146.0, and Claude Code CLI 2.1.236.

## Main path

Create `experiments/docker/provider.env` in the repository and provide provider credentials via the gitignored env file. From the repository root, run one experiment through the wrapper:

```bash
./experiments/docker/run.sh \
  --env-file experiments/docker/provider.env \
  -- \
  --manifest experiments/prompts/manifests/writingbench.jsonl \
  --prompt-id writingbench-0001 \
  --condition A1 \
  --platform codex-primary \
  --config experiments/config/runtime.json \
  --output-root runs
```

Use `codex-primary` for the Codex platform or `claude-code-replication` for the Claude Code platform. Both variants use the same container and receive provider credentials only from the runtime env file.

The wrapper builds the image on first use. The repository is mounted read-write at `/workspace`, and the host `~/.codex/config.toml` is mounted read-only at `/home/codex/.codex/config.toml`. The wrapper passes common proxy variables from the calling shell when they are set.

Pass `--ca-file /path/to/ca-bundle.pem` only when the container needs an additional proxy CA. The entrypoint appends the mounted certificate to the image trust bundle for the runner process.

The runner's manifests, runtime configuration, condition definitions, and artifact contract are documented in the [experiment protocol](../../docs/experiments/protocol.md). For manual `docker run` usage and image options, read [manual container options](./manual.md).
