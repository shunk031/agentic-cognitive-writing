import hashlib
import json

import pytest

from experiments.runner.errors import ManifestError
from experiments.runner.manifest import load_prompt_manifest


def _digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _write_manifest(path):
    row = {
        "prompt_id": "wb-001",
        "benchmark_name": "WritingBench",
        "source_version": "release-2026-01",
        "prompt_text": "Write a concise memo.",
        "requested_output_constraints": {"max_words": 100},
    }
    row["hash"] = _digest(row)
    document = {
        "schema_version": 1,
        "benchmark_name": "WritingBench",
        "source_version": "release-2026-01",
        "prompts": [row],
    }
    document["manifest_hash"] = _digest(document)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")


def test_prompt_manifest_validates_row_and_document_hashes(tmp_path):
    path = tmp_path / "writingbench.json"
    _write_manifest(path)

    manifest = load_prompt_manifest(path)

    assert manifest.benchmark_name == "WritingBench"
    assert manifest.manifest_hash == json.loads(path.read_text())["manifest_hash"]
    assert manifest.prompts[0].prompt_id == "wb-001"


def test_prompt_manifest_rejects_tampering(tmp_path):
    path = tmp_path / "writingbench.json"
    _write_manifest(path)
    document = json.loads(path.read_text())
    document["prompts"][0]["prompt_text"] = "Tampered."
    path.write_text(json.dumps(document))

    with pytest.raises(ManifestError, match="manifest_hash|row hash"):
        load_prompt_manifest(path)
