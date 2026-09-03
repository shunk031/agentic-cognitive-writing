# Docker experiment environment

The Docker environment runs the experiment runner in a disposable container while keeping the repository as the working tree on the host. The image contains Python 3.12.11, Node.js 24.7.0, codex CLI 0.146.0, Claude Code 2.1.236, uv 0.11.32, bubblewrap 0.8.0, git 2.39.5.

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

When your codex config authenticates through a helper command, that helper does not exist inside the container, so the wrapper generates a stand-in that returns the token from the environment variable you name. The wrapper passes credentials only at runtime through `experiments/docker/provider.env`; the file is ignored by Git.

Change only `--platform codex-primary` to `--platform claude-code-replication` to run the Claude Code variant. If your provider config does not use an auth helper, omit both `--auth-command` and `--auth-env`.

Codex command sandboxing inside the container requires `--security-opt seccomp=unconfined`; the wrapper adds this option automatically. The `SYS_ADMIN` capability is not required.

The wrapper builds the image on first use. The repository is mounted read-write at `/workspace`, and the host `~/.codex/config.toml` is mounted read-only at `/home/cog-writer-agent/.codex/config.toml`. Use `--dry-run` to inspect the Docker arguments without starting the container.

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

Only if your network requires proxy forwarding, the wrapper passes common proxy variables from the calling shell. Pass `--ca-file /path/to/ca-bundle.pem` only if your network requires an additional proxy CA. The entrypoint appends the mounted certificate to the image trust bundle for the runner process.

The runner's manifests, runtime configuration, condition definitions, and artifact contract are documented in the [experiment protocol](../../docs/experiments/protocol.md). For manual `docker run` usage and image options, read [manual container options](./manual.md).
