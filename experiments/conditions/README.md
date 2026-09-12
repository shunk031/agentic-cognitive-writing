# Conditions

One TOML wrapper per condition binds the condition to one package skill, one platform adapter pair, the shared plugin trace path, and its ordered stage specifications. The runner sends one top-level headless session for every condition and prompt. The runner does not sequence stages or synthesize trace events.

The frozen files under `prompts/` remain prompt specifications with content hashes. The A1 to A3 wrappers invoke `writing-single-shot`, `writing-linear`, and `writing-adaptive-task-planning` from the `cognitive-writing-baselines` package; the existing five-stage prompt specifications are used by B2's `writing-storm-style` wrapper.

A4 invokes `agentic-cog-writer` from `agentic-cognitive-writing`. A5 and A6 invoke `cognitive-writing-no-goal-network` and `cognitive-writing-fixed-order` from `cognitive-writing-experiments`. B1 and B2 invoke `writing-cogwriter-style` and `writing-storm-style` from the baseline package. The B1 and B2 wrappers mark their conditions as exploratory.

Shared prompt paragraphs live in [`contracts/`](contracts/). The runner appends `single_turn.md` to Codex invocations, adds `delegation.md` when `require_delegation = true`, and appends `workspace.md` followed by `single_turn.md` to Claude Code invocations; wrapper files retain only condition-specific invocation text. The runner renders contract names and generic shared-input blocks as `##` headings, frozen stage titles as `##` headings, and frozen stage labels as `###` headings.

Every condition uses `.writing/trace/process.jsonl` written by its selected skill. The no-retrieval A3 and B2 wrappers omit citation generation and mark retrieval, evidence, and citation traces as `N/A` in their wrapper policies.
