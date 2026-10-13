# Handoff: Agentic CogWriter rebuild

The Agentic CogWriter plugin is being rebuilt from zero on the `cogwriter-zero` branch. The old `plugin/` directory was removed on purpose, and each part of the new plugin is added only after a small verified step.

## Requirement

The writing skill is host-neutral. A `Monitor` delegates `Planning`, `Translating`, and `Reviewing` to fresh role subagents. The core skill text does not hard-code one host's syntax: Codex invokes a skill with `$name`, and Claude Code uses `/name`, the `Skill` tool, or a subagent definition. Per-host adapters supply the concrete calls.

## Verification plan

The rebuild verifies bottom-up, one step at a time:

1. Host mechanics: discovery, role-skill delegation, context isolation, files and lifecycle, attribution; see [`docs/host-probe.md`](docs/host-probe.md)
2. Each role on its own
3. `Monitor` role selection on fixed states
4. End to end, including a follow-up turn
5. End to end on Claude Code

## Verified facts carried over

- Role skills load reliably only when the host discovers them. On Codex, that means `.agents/skills/` plus a `$name` mention.
- `fork_context: false` isolates a Codex child from the parent's instructions and conversation.
- Scoring reads `draft.md`, not a final message in which the model retyped the draft.
- Model-written logs are unreliable. Behaviour checks derive from harness records.

## Working rules

- One PR per step.
- The author reviews each PR before the next step starts.
- No ad hoc additions beyond the step's scope.
- Simple text.
