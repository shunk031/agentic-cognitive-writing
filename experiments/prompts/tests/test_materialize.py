from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from experiments.prompts.materialize import (
    BENCHMARKS,
    EXPECTED_COUNTS,
    MANIFEST_FIELDS,
    canonical_json,
    dolomites_archive_counts,
    hash_manifest_row,
    sha256_file,
    validate_manifest_row,
    write_immutable,
)

ROOT = Path(__file__).parents[3]
MANIFEST_DIR = ROOT / "experiments" / "prompts" / "manifests"


def test_hash_is_canonical_and_excludes_hash_field() -> None:
    left = {"prompt_id": "p1", "prompt_text": "hello", "value": [2, 1]}
    right = {"value": [2, 1], "prompt_text": "hello", "prompt_id": "p1"}

    assert canonical_json(left) == canonical_json(right)
    assert hash_manifest_row(left) == hash_manifest_row(right)
    assert hash_manifest_row({**left, "hash": "ignored"}) == hash_manifest_row(left)


def test_immutable_write_is_idempotent_and_rejects_different_content(
    tmp_path: Path,
) -> None:
    target = tmp_path / "manifest.jsonl"
    write_immutable(target, b"one\n")
    write_immutable(target, b"one\n")

    with pytest.raises(FileExistsError):
        write_immutable(target, b"two\n")


def test_dolomites_archive_counts_are_recomputed_from_member_contents(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "examples.zip"
    payloads = {
        "dolomites_examples/dolomites_examples.dev.public.jsonl": b'{"id": 1}\n{"id": 2}\n',
        "dolomites_examples/dolomites_examples.test.noreference.jsonl": b'{"id": 3}\n',
    }
    with zipfile.ZipFile(archive, "w") as output:
        for name, payload in payloads.items():
            output.writestr(name, payload)

    assert dolomites_archive_counts(archive) == {"dev": 2, "test": 1}


def test_checked_in_manifests_have_schema_hashes_and_expected_counts() -> None:
    for benchmark_name, expected_count in EXPECTED_COUNTS.items():
        path = MANIFEST_DIR / f"{benchmark_name}.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]

        assert len(rows) == expected_count
        assert len({row["prompt_id"] for row in rows}) == expected_count
        for row in rows:
            assert set(row) == set(MANIFEST_FIELDS)
            validate_manifest_row(row)
            assert row["hash"] == hash_manifest_row(row)


def test_checked_in_provenance_records_pins_license_and_split() -> None:
    provenance = json.loads(
        (ROOT / "experiments" / "prompts" / "provenance.json").read_text()
    )

    assert set(provenance["benchmarks"]) == set(BENCHMARKS)
    assert provenance["benchmarks"]["writingbench"]["source_version"].endswith(
        "@9c24bb67fd7451a2eacf5810aa7721e3a8b3bdad"
    )
    assert provenance["benchmarks"]["hellobench"]["source_version"].endswith(
        "@92c7d469230b5b6b6ee1bfc1ea2ce49cb9125b57"
    )
    dolomites = provenance["benchmarks"]["dolomites"]
    assert dolomites["license"] == "CC-BY-4.0"
    assert dolomites["split"]["observed_counts"] == {"dev": 820, "test": 1037}
    assert dolomites["split"]["manifest_subset"] == "dev"

    split = json.loads(
        (ROOT / "experiments" / "prompts" / "dolomites_split.json").read_text()
    )
    assert split["archive_sha256"] == dolomites["archive_sha256"]
    assert split["archive_sha256"] == (
        "62ee47b4cdf67d1efd7a21029384a929e3d66cab49989aab85ea3534b8b86c32"
    )
    assert split["observed_counts"] == dolomites["split"]["observed_counts"]


def test_file_hash_is_streamed_and_stable(tmp_path: Path) -> None:
    target = tmp_path / "source.bin"
    target.write_bytes(b"benchmark bytes")

    assert sha256_file(target) == (
        "ba1370283a334fab7a28bade2cd18a857f319babaacec3ec4346e9eb68eba93b"
    )


def test_dolomites_manifest_does_not_include_reference_outputs() -> None:
    first_row = json.loads(
        (MANIFEST_DIR / "dolomites.jsonl").read_text().splitlines()[0]
    )

    assert "example_output" not in first_row["prompt_text"]
    assert "post_edited_example" not in first_row["prompt_text"]
    assert (
        "Use only the supplied task context and input"
        in first_row["requested_output_constraints"][-1]
    )


def test_archive_count_requires_both_pinned_members(tmp_path: Path) -> None:
    archive = tmp_path / "incomplete.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(
            "dolomites_examples/dolomites_examples.dev.public.jsonl", b"{}\n"
        )

    with pytest.raises(ValueError, match="required member"):
        dolomites_archive_counts(archive)
