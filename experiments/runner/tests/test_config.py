import json

import pytest
from agentic_cogwriter.runner.config import REQUIRED_RUNTIME_FIELDS, RuntimeConfig
from agentic_cogwriter.runner.errors import ConfigurationError


def test_runtime_placeholders_block_scored_runs(tmp_path):
    path = tmp_path / "runtime.json"
    path.write_text(json.dumps({"codex_generator_model": "REQUIRED_AT_RUNTIME"}))

    config = RuntimeConfig.load(path)

    assert "codex_generator_model" in config.unresolved_fields()
    with pytest.raises(ConfigurationError, match="codex_generator_model"):
        config.require_scored_run()


def test_runtime_config_accepts_filled_values(tmp_path):
    values = {field: "filled" for field in REQUIRED_RUNTIME_FIELDS}
    values.update(
        maximum_output_tokens=100,
        timeout=60,
        retry_policy=0,
    )
    config = RuntimeConfig.from_dict(values)

    config.require_scored_run()
