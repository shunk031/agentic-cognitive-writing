# Conditions

The condition registry binds each condition to one package skill, one platform adapter pair, and the shared plugin trace path. The runner sends one top-level headless session for every condition and prompt. The runner does not sequence stages or synthesize trace events.

The A1 to A3 files under `prompts/` remain frozen prompt specifications with content hashes. The corresponding wrapper files invoke `writing-single-shot`, `writing-linear`, and `writing-storm-style` from the `cognitive-writing-baselines` package.

A4 invokes `agentic-cog-writer` from `agentic-cognitive-writing`. A5 and A6 invoke `cognitive-writing-no-goal-network` and `cognitive-writing-fixed-order` from `cognitive-writing-experiments`. B1 and B2 invoke `writing-cogwriter-style` and `writing-writehere-style` from the baseline package. The registry marks B1 and B2 as exploratory.

Every condition uses `.writing/trace/process.jsonl` written by its selected skill. A3 omits citation generation and marks retrieval, evidence, and citation traces as `N/A` in its wrapper policy.
