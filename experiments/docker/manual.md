# Manual container options

The [`run.sh`](./run.sh) script in this directory (usage documented in [README.md](./README.md)) is the normal entry point for both `codex` and `claude-code`. Follow the [run.sh command](./README.md#run-one-experiment-runsh), [prerequisites](./README.md#prerequisites), and [success criteria](./README.md#what-success-looks-like) there. Use a direct Docker command only when another tool needs to own the container lifecycle.

The direct command below assumes that the README prerequisites are complete, the repository root is the current directory, the plugin is available at the documented host path, and the gitignored provider env file exists.

Build or reuse the image built from [`Dockerfile`](./Dockerfile):

```bash
docker build \
  --tag agentic-cognitive-writing-experiment:local \
  --file experiments/docker/Dockerfile .
```

Run `uv run --package agentic-cogwriter agentic-cogwriter-runner` with the same mounts as `run.sh`. The image includes both pinned CLIs, and the runner selects the platform from the experiment arguments:

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
