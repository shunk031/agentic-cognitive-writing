# Runtime configuration

The experimenter owns the model, judge, decoding, budget, timeout, seed, plugin, and statistical choices. The tracked [`runtime.json`](runtime.json) leaves every scored-run choice as `REQUIRED_AT_RUNTIME`, so the runner stops before creating a model process until the experimenter supplies a complete private configuration with `--config`.

The configuration must not contain credentials or private prompt material. The runner records safe setting values in each run manifest and keeps the same timeout, retry count, tool policy, and output budget across conditions.
