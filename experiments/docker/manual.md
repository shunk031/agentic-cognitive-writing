# Manual container options

The wrapper in [`README.md`](./README.md) is the normal entry point. Use a direct Docker command only when another tool needs to own the container lifecycle.

Build or reuse the local image:

```bash
docker build \
  --tag agentic-cognitive-writing-experiment:local \
  --file experiments/docker/Dockerfile .
```

Run the runner with the same mounts as the wrapper:

```bash
docker run --rm --init \
  --user "$(id -u):$(id -g)" \
  --workdir /workspace \
  --mount "type=bind,src=$PWD,dst=/workspace" \
  --mount "type=bind,src=$HOME/.codex/config.toml,dst=/home/codex/.codex/config.toml,readonly" \
  --env-file "$PWD/experiments/docker/provider.env" \
  agentic-cognitive-writing-experiment:local \
  uv run --package agentic-cogwriter agentic-cogwriter-runner --help
```

Add `--mount "type=bind,src=/path/to/ca-bundle.pem,dst=/run/user-ca.pem,readonly"` when an additional proxy CA is required. Pass standard proxy variables with Docker's `--env NAME` form when the calling shell provides them. Keep provider values in the ignored env file and pass them only at run time.
