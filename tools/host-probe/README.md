# Host probe

The host probe checks the host mechanics that the writing plugin depends on: skill discovery, role-skill delegation to a child agent, child context isolation, file hand-off and child lifecycle, and attribution of every action to the parent or the child. The findings are in [`docs/host-probe.md`](../../docs/host-probe.md).

## Files

- [`skills/probe-parent/SKILL.md`](./skills/probe-parent/SKILL.md): writes `parent.txt`, starts one child for the `probe-child` role, then copies `child.txt` into `parent-read.txt`
- [`skills/probe-child/SKILL.md`](./skills/probe-child/SKILL.md): writes `child.txt` and replies with a marker that only this skill contains
- [`claude-agents/probe-child.md`](./claude-agents/probe-child.md): Claude Code subagent that preloads the `probe-child` skill
- [`probe.py`](./probe.py): runs one host in a fresh workspace, then checks the harness records and prints a pass/fail table

## Run

The probe runs the host CLI inside the experiment image `agentic-cognitive-writing-experiment:local`, built from [`experiments/docker/Dockerfile`](../../experiments/docker/Dockerfile). Each run writes into a new directory that holds the workspace, the host's session records, the CLI event stream, and the CLI stderr.

Codex reads the provider settings from a Codex `config.toml`. When that config authenticates through a helper command, pass the command name and an environment variable that holds the token; the probe mounts a stand-in helper that prints the variable:

```bash
MY_TOKEN=... python3 tools/host-probe/probe.py codex /path/to/new-run-dir \
  --codex-config ~/.codex/config.toml --auth-command my-auth-helper --auth-env MY_TOKEN
```

Claude Code reads `~/.claude/.credentials.json`, mounted read-only. `--foreground` sets `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`, so the parent waits for the child inside the `Agent` call:

```bash
python3 tools/host-probe/probe.py claude /path/to/new-run-dir [--foreground]
```

`python3 tools/host-probe/probe.py check /path/to/run-dir` re-checks an existing run. The exit status is 0 only when all five checks pass.
