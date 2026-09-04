import hashlib
import json

import pytest

from agentic_cogwriter.runner.errors import ManifestError
from agentic_cogwriter.runner.manifest import load_prompt_manifest


def _digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _jsonl_row():
    row = {
        "prompt_id": "p1",
        "benchmark_name": "TestBench",
        "source_version": "test@1",
        "prompt_text": "Write a test.",
        "requested_output_constraints": ["Be concise."],
    }
    row["hash"] = _digest(row)
    return row


def _write_jsonl_manifest(path):
    path.write_bytes(
        (
            json.dumps(
                _jsonl_row(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            + "\n"
        ).encode()
    )


def test_prompt_manifest_validates_row_and_file_hashes(tmp_path):
    path = tmp_path / "testbench.jsonl"
    _write_jsonl_manifest(path)

    manifest = load_prompt_manifest(path)

    assert manifest.benchmark_name == "TestBench"
    assert manifest.manifest_hash == hashlib.sha256(path.read_bytes()).hexdigest()
    assert manifest.prompts[0].prompt_id == "p1"


def test_prompt_manifest_rejects_tampering(tmp_path):
    path = tmp_path / "testbench.jsonl"
    row = _jsonl_row()
    row["prompt_text"] = "Tampered."
    path.write_text(json.dumps(row) + "\n")

    with pytest.raises(ManifestError, match="row hash"):
        load_prompt_manifest(path)


def test_prompt_manifest_rejects_object_form(tmp_path):
    path = tmp_path / "testbench.json"
    document = {
        "schema_version": 1,
        "benchmark_name": "TestBench",
        "source_version": "test@1",
        "prompts": [_jsonl_row()],
    }
    document["manifest_hash"] = _digest(document)
    path.write_text(json.dumps(document, indent=2) + "\n")

    with pytest.raises(ManifestError):
        load_prompt_manifest(path)


def test_prompt_manifest_loads_materialized_jsonl_and_hashes_file(tmp_path):
    path = tmp_path / "writingbench.jsonl"
    row = _jsonl_row()
    path.write_bytes(
        (
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode()
    )

    manifest = load_prompt_manifest(path)

    assert manifest.benchmark_name == "TestBench"
    assert manifest.manifest_hash == hashlib.sha256(path.read_bytes()).hexdigest()
    assert manifest.prompts[0].prompt_id == "p1"
