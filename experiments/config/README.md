# Agentic CogWriter runtime configuration

The experimenter owns the model, judge, decoding, budget, timeout, seed, plugin, and statistical choices for Agentic CogWriter and its comparison conditions. The tracked [`runtime.json`](runtime.json) leaves every scored-run choice as `REQUIRED_AT_RUNTIME`, so the runner stops before creating a model process until the experimenter supplies a complete private configuration with `--config`.

The configuration must not contain credentials or private prompt material. The runner records safe setting values in each run manifest and keeps the same timeout, retry count, tool policy, and output budget across conditions.

The runtime gate also freezes the output-counting unit. Set `output_counting.unit` to `tokens` only with a pinned tokenizer and version; otherwise set it to `words` and document the frozen word rule in `output_counting.word_rule`. The post-hoc budget check fails a run that exceeds that unit limit. Platform control status is recorded separately: Claude Code's maximum-output-token setting is enforced by its adapter, while controls without a documented CLI setting are `monitored-only`.

The runner records benchmark release and source/archive hashes directly from [`prompts/provenance.json`](../prompts/provenance.json). The judge scorer in [`src/agentic_cogwriter/judges/`](../src/agentic_cogwriter/judges/) derives the judge family from the serving response and the explicit model-family map, compares that family with generator evidence in each `run-manifest.json`, and records the audit in `scores-manifest.json`. The judge client exposes no retrieval or tool interface.
