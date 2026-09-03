# Docker experiment environment

The Docker environment runs the experiment runner in a disposable container while keeping the repository as the working tree on the host. The image contains Python 3.12.11, Node.js 24.7.0, codex CLI 0.146.0, Claude Code 2.1.236, uv 0.11.32, bubblewrap 0.8.0, git 2.39.5.

## Prerequisites

Start from a fresh checkout of the repository:

```bash
git clone https://github.com/shunk031/agentic-cognitive-writing.git
cd agentic-cognitive-writing
```

Before running an experiment, confirm these prerequisites:

- A Docker engine is running.
- The host has `~/.codex/config.toml` with a working provider configuration. The wrapper mounts the file read-only and does not copy or modify it.
- A plugin checkout exists before the run. The plugin directory ships in this repository at `plugin/` after the plugin change merges; until then, use a checkout of the plugin branch at the host path passed to `--codex-plugin-root`. Keep that host path under this repository so the wrapper mounts it into the container. The example passes the host-relative path `plugin`, which the wrapper exposes as `/workspace/plugin`.
- Codex command sandboxing requires `--security-opt seccomp=unconfined`. The wrapper adds this option automatically, so keep the default security setting for Codex runs.

Create the gitignored env file from the repository root. The value below is a fake placeholder; replace it locally with the provider credential before running an experiment:

```bash
mkdir -p experiments/docker
printf '%s\n' 'MY_PROVIDER_TOKEN=replace-with-your-provider-token' > experiments/docker/provider.env
```

The helper name `my-provider-auth-helper` and variable name `MY_PROVIDER_TOKEN` below are illustrative values that you must replace. Open your host `~/.codex/config.toml`; if it defines an auth helper command for your provider, pass that command's exact name as `--auth-command` and the environment variable it reads as `--auth-env`; if it does not, omit both flags.

`writingbench-0001` and `A4` are valid shipped selections, not placeholders. The prompt ID comes from `experiments/prompts/manifests/writingbench.jsonl`, and the condition comes from the condition registry.

## Run one experiment (wrapper)

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
  --codex-plugin-root plugin \
  --config experiments/config/runtime.json \
  --output-root runs
```

When your Codex config authenticates through a helper command, that helper does not exist inside the container, so the wrapper generates a stand-in that returns the token from the environment variable you name. The wrapper passes credentials only at runtime through `experiments/docker/provider.env`; the file is ignored by Git.

Change only `--platform codex-primary` to `--platform claude-code-replication` to run the Claude Code variant. If your provider config does not use an auth helper, omit both `--auth-command` and `--auth-env`.

The wrapper builds the image on first use. The repository is mounted read-write at `/workspace`, and the host `~/.codex/config.toml` is mounted read-only at `/home/cog-writer-agent/.codex/config.toml`. Use `--dry-run` to inspect the Docker arguments without starting the container.

## What success looks like

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

Codex command sandboxing inside the container requires `--security-opt seccomp=unconfined`; the wrapper adds this option automatically. The `SYS_ADMIN` capability is not required.

## Optional network settings

Only if your network requires proxy forwarding, the wrapper passes common proxy variables from the calling shell. Pass `--ca-file /path/to/ca-bundle.pem` only if your network requires an additional proxy CA. The entrypoint appends the mounted certificate to the image trust bundle for the runner process.

The runner's manifests, runtime configuration, condition definitions, and artifact contract are documented in the [experiment protocol](../../docs/experiments/protocol.md). For manual `docker run` usage and image options, read [manual container options](./manual.md).
