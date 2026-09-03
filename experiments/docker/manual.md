# Manual container options

The wrapper in [`README.md`](./README.md) is the normal entry point for both `codex-primary` and `claude-code-replication`. If your provider config resolves credentials through an auth helper command, pass its name and the credential variable to the wrapper with `--auth-command NAME --auth-env VAR`. The wrapper generates the temporary helper and mounts it read-only. Use a direct Docker command only when another tool needs to own the container lifecycle.

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
  --mount "type=bind,src=$HOME/.codex/config.toml,dst=/home/codex/.codex/config.toml,readonly" \
  --env-file "$PWD/experiments/docker/provider.env" \
  agentic-cognitive-writing-experiment:local \
  uv run --package agentic-cogwriter agentic-cogwriter-runner --help
```

Add `--mount "type=bind,src=/path/to/ca-bundle.pem,dst=/run/user-ca.pem,readonly"` only if your network requires an additional proxy CA. Pass standard proxy variables with Docker's `--env NAME` form only if your network requires proxy forwarding. Provide provider credentials via the gitignored env file and pass them only at run time.
