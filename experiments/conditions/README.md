# Conditions

The condition registry binds each condition to one package skill, one platform adapter pair, and the shared plugin trace path. The runner sends one top-level headless session for every condition and prompt. The runner does not sequence stages or synthesize trace events.

The frozen files under `prompts/` remain prompt specifications with content hashes. The A1 to A3 wrappers invoke `writing-single-shot`, `writing-linear`, and `writing-adaptive-task-planning` from the `cognitive-writing-baselines` package; the existing five-stage prompt specifications are used by B2's `writing-storm-style` wrapper.

A4 invokes `agentic-cog-writer` from `agentic-cognitive-writing`. A5 and A6 invoke `cognitive-writing-no-goal-network` and `cognitive-writing-fixed-order` from `cognitive-writing-experiments`. B1 and B2 invoke `writing-cogwriter-style` and `writing-storm-style` from the baseline package. The registry marks B1 and B2 as exploratory.

Every condition uses `.writing/trace/process.jsonl` written by its selected skill. The no-retrieval A3 and B2 wrappers omit citation generation and mark retrieval, evidence, and citation traces as `N/A` in their wrapper policies.
