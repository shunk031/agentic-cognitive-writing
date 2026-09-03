# Manual container options

The wrapper in [`README.md`](./README.md) is the normal entry point for both `codex-primary` and `claude-code-replication`. Use a direct Docker command only when another tool needs to own the container lifecycle.

## Quickstart

Before starting, confirm these prerequisites:

- A Docker engine is running.
- The host has `~/.codex/config.toml` with a working provider configuration. The wrapper mounts the file read-only and does not copy or modify it.
- A plugin checkout exists before the run. After the repository's `plugin/` directory is merged, use `/workspace/plugin` as the plugin root shown below. For another checkout, make the checkout available under the repository mount and pass its corresponding `/workspace/...` path.
- Codex command sandboxing requires `--security-opt seccomp=unconfined`. The wrapper adds this option automatically, so keep the default security setting for Codex runs.

Create the gitignored env file from the repository root. The value below is a fake placeholder; replace it locally with the provider credential before running an experiment:

```bash
mkdir -p experiments/docker
printf '%s\n' 'MY_PROVIDER_TOKEN=replace-with-your-provider-token' > experiments/docker/provider.env
```

The helper name `my-provider-auth-helper` and variable name `MY_PROVIDER_TOKEN` below are illustrative values that you must replace. Determine both from your own provider configuration. If the configuration names an auth command, pass that exact command name to `--auth-command` and pass the variable that holds its token to `--auth-env`.

Run one Codex experiment through the wrapper:

```bash
./experiments/docker/run.sh \
  --env-file experiments/docker/provider.env \
  --auth-command my-provider-auth-helper \
  --auth-env MY_PROVIDER_TOKEN \
  -- \
  --manifest experiments/prompts/manifests/writingbench.jsonl \
  --prompt-id writingbench-0001 \
  --condition A4 \
  --platform codex-primary \
  --codex-plugin-root /workspace/plugin \
  --config experiments/config/runtime.json \
  --output-root runs
```

When your codex config authenticates through a helper command, that helper does not exist inside the container, so the wrapper generates a stand-in that returns the token from the environment variable you name. Change only `--platform codex-primary` to `--platform claude-code-replication` for the Claude Code variant. If your provider config does not use an auth helper, omit both auth options.

Codex command sandboxing inside the container requires `--security-opt seccomp=unconfined`; the wrapper adds this option automatically. The `SYS_ADMIN` capability is not required.

A successful run exits with status 0 and prints the runner's final completion message. With `--output-root runs`, the host receives a run directory with these files:

```text
runs/
└── <run-directory>/
    ├── run-manifest.json
    ├── output.raw
    ├── output.normalized.txt
    └── workspace/
        └── .writing/
            └── trace/
                └── process.jsonl
```

Build or reuse the local image:

```bash
docker build \
  --tag agentic-cognitive-writing-experiment:local \
  --file experiments/docker/Dockerfile .
```

Run the runner with the same mounts as the wrapper. The image includes both pinned CLIs, and the runner selects the platform from the experiment arguments:

```bash
docker run --rm --init \
  --security-opt seccomp=unconfined \
  --user "$(id -u):$(id -g)" \
  --workdir /workspace \
  --mount "type=bind,src=$PWD,dst=/workspace" \
  --mount "type=bind,src=$HOME/.codex/config.toml,dst=/home/cog-writer-agent/.codex/config.toml,readonly" \
  --env-file "$PWD/experiments/docker/provider.env" \
  agentic-cognitive-writing-experiment:local \
  uv run --package agentic-cogwriter agentic-cogwriter-runner --help
```

Add `--mount "type=bind,src=/path/to/ca-bundle.pem,dst=/run/user-ca.pem,readonly"` only if your network requires an additional proxy CA. Pass standard proxy variables with Docker's `--env NAME` form only if your network requires proxy forwarding. Provide provider credentials via the gitignored env file and pass them only at run time.
