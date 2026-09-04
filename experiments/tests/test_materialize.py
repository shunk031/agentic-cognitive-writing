from __future__ import annotations

import hashlib
import importlib
import json
import tomllib
import zipfile
from pathlib import Path
from typing import Any

import pytest

import agentic_cogwriter.prompts.materialize as materialize_module
import agentic_cogwriter.prompts.recompute_dolomites_split as split_module
from agentic_cogwriter.paths import (
    BENCHMARK_CACHE_DIR,
    DOLOMITES_SPLIT_PATH,
    EXPERIMENTS_ROOT,
    MANIFESTS_DIR,
    PROMPT_DATA_ROOT,
    PROVENANCE_PATH,
    REPOSITORY_ROOT,
)
from agentic_cogwriter.prompts.materialize import (
    BENCHMARKS,
    DOLOMITES_DEV_MEMBER,
    DOLOMITES_TEST_MEMBER,
    EXPECTED_COUNTS,
    MANIFEST_FIELDS,
    RemoteFile,
    acquire,
    build_dolomites,
    build_hellobench,
    build_writingbench,
    canonical_json,
    dolomites_archive_counts,
    hash_manifest_row,
    materialize,
    pretty_json,
    provenance,
    sha256_file,
    validate_manifest_row,
    write_immutable,
)

PROMPTS_ROOT = PROMPT_DATA_ROOT
MANIFEST_DIR = MANIFESTS_DIR


def _test_manifest_row(prompt_id: str = "p1") -> dict[str, Any]:
    row: dict[str, Any] = {
        "prompt_id": prompt_id,
        "benchmark_name": "TestBench",
        "source_version": "test@1",
        "prompt_text": "Write a test.",
        "requested_output_constraints": ["Be concise."],
    }
    row["hash"] = hash_manifest_row(row)
    return row


def _write_split_archive(
    path: Path,
    dev_rows: list[dict[str, Any]],
    test_rows: list[dict[str, Any]],
) -> None:
    with zipfile.ZipFile(path, "w") as output:
        output.writestr(
            DOLOMITES_DEV_MEMBER,
            "".join(f"{json.dumps(row)}\n" for row in dev_rows),
        )
        output.writestr(
            DOLOMITES_TEST_MEMBER,
            "".join(f"{json.dumps(row)}\n" for row in test_rows),
        )


def test_materializer_uses_the_src_package_layout() -> None:
    package_path = Path(materialize_module.__file__).resolve()

    assert package_path.parent.name == "prompts"
    assert package_path.parent.parent.name == "agentic_cogwriter"
    assert package_path.parent.parent.parent.name == "src"


def test_agentic_cogwriter_is_a_regular_package() -> None:
    namespace = importlib.import_module("agentic_cogwriter")
    namespace_path = Path(materialize_module.__file__).resolve().parent.parent

    assert namespace.__file__ is not None
    assert namespace.__spec__ is not None
    assert namespace.__spec__.origin == namespace.__file__
    assert (namespace_path / "__init__.py").exists()


def test_paths_are_anchored_at_the_repository_root() -> None:
    root_pyproject = REPOSITORY_ROOT / "pyproject.toml"
    config = tomllib.loads(root_pyproject.read_text())

    assert config["tool"]["uv"]["workspace"]["members"] == ["experiments"]
    assert EXPERIMENTS_ROOT == REPOSITORY_ROOT / "experiments"
    assert PROMPT_DATA_ROOT == EXPERIMENTS_ROOT / "prompts"
    assert MANIFESTS_DIR == PROMPT_DATA_ROOT / "manifests"
    assert PROVENANCE_PATH == PROMPT_DATA_ROOT / "provenance.json"
    assert DOLOMITES_SPLIT_PATH == PROMPT_DATA_ROOT / "dolomites_split.json"
    assert BENCHMARK_CACHE_DIR == REPOSITORY_ROOT / ".cache" / "benchmarks"


def test_hash_is_canonical_and_excludes_hash_field() -> None:
    left = {"prompt_id": "p1", "prompt_text": "hello", "value": [2, 1]}
    right = {"value": [2, 1], "prompt_text": "hello", "prompt_id": "p1"}

    assert canonical_json(left) == canonical_json(right)
    assert hash_manifest_row(left) == hash_manifest_row(right)
    assert hash_manifest_row({**left, "hash": "ignored"}) == hash_manifest_row(left)


def test_plain_json_is_pretty_sorted_and_byte_deterministic(tmp_path: Path) -> None:
    value = {"nested": {"b": 2, "a": 1}, "key": "value"}
    target = tmp_path / "provenance.json"
    expected = '{\n  "key": "value",\n  "nested": {\n    "a": 1,\n    "b": 2\n  }\n}\n'

    materialize_module._write_json(target, value)
    assert target.read_text() == expected
    assert target.read_text() == pretty_json(value) + "\n"

    materialize_module._write_json(target, value)
    assert target.read_text() == expected


def test_validate_manifest_row_rejects_invalid_contract_fields() -> None:
    valid = _test_manifest_row()

    invalid_rows = (
        {**valid, "extra": True},
        {**valid, "prompt_id": ""},
        {**valid, "requested_output_constraints": [""]},
        {**valid, "hash": "short"},
        {**valid, "hash": "0" * 64},
    )

    for row in invalid_rows:
        with pytest.raises(ValueError):
            validate_manifest_row(row)


def test_jsonl_reader_skips_blank_lines_and_rejects_bad_records() -> None:
    rows = list(
        materialize_module._iter_jsonl_lines([b"\n", b'{"id": 1}\n'], "source.jsonl")
    )
    assert rows == [{"id": 1}]

    with pytest.raises(ValueError, match="invalid JSON"):
        list(materialize_module._iter_jsonl_lines([b"not json\n"], "source.jsonl"))
    with pytest.raises(TypeError, match="expected an object"):
        list(materialize_module._iter_jsonl_lines([b"[]\n"], "source.jsonl"))


def test_immutable_write_is_idempotent_and_rejects_different_content(
    tmp_path: Path,
) -> None:
    target = tmp_path / "manifest.jsonl"
    write_immutable(target, b"one\n")
    write_immutable(target, b"one\n")

    with pytest.raises(FileExistsError):
        write_immutable(target, b"two\n")


def test_acquire_downloads_and_reuses_a_verified_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"pinned source"
    source = RemoteFile(
        "source.bin",
        "https://example.test/source.bin",
        hashlib.sha256(payload).hexdigest(),
    )

    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return payload

    monkeypatch.setattr(
        materialize_module.urllib.request,
        "urlopen",
        lambda request, **_kwargs: Response(),
    )
    target = acquire(source, tmp_path)
    assert target.read_bytes() == payload

    def unexpected_urlopen(request: object, **_kwargs: object) -> object:
        raise AssertionError("cache should avoid downloading")

    monkeypatch.setattr(
        materialize_module.urllib.request, "urlopen", unexpected_urlopen
    )
    assert acquire(source, tmp_path) == target


def test_acquire_rejects_cached_and_downloaded_hash_mismatches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cached_source = RemoteFile("cached.bin", "https://example.test/cached", "0" * 64)
    (tmp_path / cached_source.cache_name).write_bytes(b"wrong")
    with pytest.raises(ValueError, match="cached source hash mismatch"):
        acquire(cached_source, tmp_path)

    download_source = RemoteFile(
        "download.bin", "https://example.test/download", "0" * 64
    )

    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b"wrong"

    monkeypatch.setattr(
        materialize_module.urllib.request,
        "urlopen",
        lambda request, **_kwargs: Response(),
    )
    with pytest.raises(ValueError, match="downloaded source hash mismatch"):
        acquire(download_source, tmp_path)


def test_build_writingbench_maps_index_and_query(tmp_path: Path) -> None:
    source = tmp_path / "writingbench.jsonl"
    source.write_text(
        json.dumps(
            {
                "index": 7,
                "query": "Write a memo.",
                "checklist": [
                    {
                        "name": "Structure",
                        "criteria_description": "Use a clear structure.",
                        "1-2": "Missing.",
                        "3-4": "Weak.",
                        "5-6": "Adequate.",
                        "7-8": "Strong.",
                        "9-10": "Excellent.",
                    }
                ],
            }
        )
        + "\n"
    )

    rows = build_writingbench(source)

    assert len(rows) == 1
    assert rows[0]["prompt_id"] == "writingbench-0007"
    assert rows[0]["native_payload"][0]["name"] == "Structure"
    validate_manifest_row(rows[0])

    source.write_text('{"index": "seven", "query": "Write.", "checklist": []}\n')
    with pytest.raises(TypeError, match="index must be an integer"):
        build_writingbench(source)


def test_build_hellobench_uses_requirements_and_fallbacks(tmp_path: Path) -> None:
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    first.write_text(
        '{"id": "one", "instruction": "Draft one.", '
        '"requirements": ["Use headings."]}\n'
    )
    second.write_text(
        '{"id": "two", "instruction": "Draft two.", "requirements": []}\n'
    )

    rows = build_hellobench([first, second])

    assert len(rows) == 2
    assert rows[0]["requested_output_constraints"] == ["Use headings."]
    assert rows[1]["requested_output_constraints"] == [
        "No separate output constraints; follow prompt_text."
    ]

    first.write_text('{"id": 1, "instruction": "Draft."}\n')
    with pytest.raises(TypeError, match="invalid id/instruction"):
        build_hellobench([first])
    first.write_text('{"id": "bad", "instruction": "Draft.", "requirements": [1]}\n')
    with pytest.raises(ValueError, match="requirements are invalid"):
        build_hellobench([first])


def test_build_dolomites_materializes_only_the_dev_split(tmp_path: Path) -> None:
    task = {
        "task_objective": "Explain the objective.",
        "task_procedure": "Follow the procedure.",
        "task_input": "Use this input.",
        "task_output": "Return a report.",
        "task_notes": "Keep the methodical style.",
    }
    dev_rows = [
        {"example_id": f"dev-{index}", "example_input": "input", "task": task}
        for index in range(820)
    ]
    test_rows = [{"example_id": f"test-{index}"} for index in range(1037)]
    archive = tmp_path / "dolomites.zip"
    _write_split_archive(archive, dev_rows, test_rows)

    rows, counts = build_dolomites(archive)

    assert len(rows) == 820
    assert counts == {"dev": 820, "test": 1037}
    assert rows[0]["prompt_id"] == "dolomites-dev-0"
    assert "example_output" not in rows[0]["prompt_text"]
    assert "Return a report." in rows[0]["requested_output_constraints"]


def test_build_dolomites_rejects_an_unexpected_split(tmp_path: Path) -> None:
    archive = tmp_path / "short-dolomites.zip"
    _write_split_archive(archive, [{"id": 1}], [{"id": 2}])

    with pytest.raises(ValueError, match="unexpected DoLoMiTes archive split"):
        build_dolomites(archive)


def test_dolomites_archive_counts_are_recomputed_from_member_contents(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "examples.zip"
    payloads = {
        "dolomites_examples/dolomites_examples.dev.public.jsonl": (
            b'{"id": 1}\n{"id": 2}\n'
        ),
        "dolomites_examples/dolomites_examples.test.noreference.jsonl": b'{"id": 3}\n',
    }
    with zipfile.ZipFile(archive, "w") as output:
        for name, payload in payloads.items():
            output.writestr(name, payload)

    assert dolomites_archive_counts(archive) == {"dev": 2, "test": 1}


def test_manifest_bytes_reject_duplicate_ids_and_write_json(tmp_path: Path) -> None:
    row = _test_manifest_row()
    with pytest.raises(ValueError, match="duplicate prompt ID"):
        materialize_module._manifest_bytes([row, row])

    target = tmp_path / "provenance.json"
    materialize_module._write_json(target, {"key": "value"})
    assert json.loads(target.read_text()) == {"key": "value"}


def test_write_manifest_enforces_the_expected_count(tmp_path: Path) -> None:
    row = _test_manifest_row()
    with pytest.raises(ValueError, match="expected 1000 rows"):
        materialize_module._write_manifest(tmp_path, "writingbench", [row])

    rows = [_test_manifest_row(f"p{index}") for index in range(1000)]
    target = materialize_module._write_manifest(tmp_path, "writingbench", rows)
    assert len(target.read_text().splitlines()) == 1000


def test_checked_in_manifests_have_schema_hashes_and_expected_counts() -> None:
    for benchmark_name, expected_count in EXPECTED_COUNTS.items():
        path = MANIFEST_DIR / f"{benchmark_name}.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]

        assert len(rows) == expected_count
        assert len({row["prompt_id"] for row in rows}) == expected_count
        for row in rows:
            expected_fields = (
                set(MANIFEST_FIELDS) | {"native_payload"}
                if benchmark_name == "writingbench"
                else set(MANIFEST_FIELDS)
            )
            assert set(row) == expected_fields
            validate_manifest_row(row)
            assert row["hash"] == hash_manifest_row(row)


def test_checked_in_manifests_are_byte_deterministic() -> None:
    for benchmark_name in BENCHMARKS:
        path = MANIFEST_DIR / f"{benchmark_name}.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]

        assert materialize_module._manifest_bytes(rows) == path.read_bytes()


def test_checked_in_provenance_records_pins_license_and_split() -> None:
    provenance = json.loads((PROMPTS_ROOT / "provenance.json").read_text())

    assert set(provenance["benchmarks"]) == set(BENCHMARKS)
    writingbench = provenance["benchmarks"]["writingbench"]
    assert "@9c24bb67fd7451a2eacf5810aa7721e3a8b3bdad" in writingbench["source_version"]
    assert writingbench["source_blob_sha1"] == (
        "e6cd82aabed6fa845f0a28cd2114daad59c012b9"
    )
    assert provenance["benchmarks"]["hellobench"]["source_version"].endswith(
        "@92c7d469230b5b6b6ee1bfc1ea2ce49cb9125b57"
    )
    dolomites = provenance["benchmarks"]["dolomites"]
    assert dolomites["license"] == "CC-BY-4.0"
    assert dolomites["split"]["observed_counts"] == {"dev": 820, "test": 1037}
    assert dolomites["split"]["manifest_subset"] == "dev"

    split = json.loads((PROMPTS_ROOT / "dolomites_split.json").read_text())
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


def test_provenance_records_the_archive_derived_split() -> None:
    result = provenance({"dev": 820, "test": 1037})

    assert result["benchmarks"]["dolomites"]["split"]["authoritative_count"] == (
        "archive-derived"
    )


def test_materialize_dispatches_selected_benchmarks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_dir = tmp_path / "manifests"
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(
        materialize_module,
        "acquire",
        lambda source, cache: cache / source.cache_name,
    )
    monkeypatch.setattr(materialize_module, "build_writingbench", lambda source: [])
    monkeypatch.setattr(materialize_module, "build_hellobench", lambda _sources: [])
    monkeypatch.setattr(
        materialize_module,
        "build_dolomites",
        lambda source: ([], {"dev": 820, "test": 1037}),
    )
    monkeypatch.setattr(
        materialize_module,
        "_write_manifest",
        lambda directory, name, rows: directory / f"{name}.jsonl",
    )
    written: list[Path] = []
    monkeypatch.setattr(
        materialize_module,
        "_write_json",
        lambda path, value: written.append(path),
    )

    counts = materialize(BENCHMARKS, output_dir, cache_dir)

    assert counts == {name: 0 for name in BENCHMARKS}
    assert written == [tmp_path / "provenance.json"]


def test_materialize_cli_prints_counts(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        materialize_module,
        "materialize",
        lambda benchmarks, output_dir, cache_dir: {"writingbench": 1000},
    )

    assert materialize_module.main(["--benchmark", "writingbench"]) == 0
    assert capsys.readouterr().out == "writingbench: 1000\n"


def test_recompute_split_cli_writes_observed_counts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "split.zip"
    _write_split_archive(archive, [{"id": 1}], [{"id": 2}])
    archive_hash = sha256_file(archive)
    monkeypatch.setattr(
        split_module,
        "DOLOMITES_ARCHIVE",
        RemoteFile("archive.zip", "https://example.test/archive.zip", archive_hash),
    )
    output = tmp_path / "dolomites_split.json"

    assert split_module.main(["--archive", str(archive), "--output", str(output)]) == 0
    result = json.loads(output.read_text())
    assert output.read_text() == pretty_json(result) + "\n"
    assert result["observed_counts"] == {"dev": 1, "test": 1}
    assert result["manifest_subset"] == "dev"
    assert json.loads(capsys.readouterr().out)["archive_sha256"] == archive_hash

    assert split_module.main(["--archive", str(archive), "--output", str(output)]) == 0
    assert output.read_text() == pretty_json(result) + "\n"


def test_recompute_split_cli_rejects_an_unpinned_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "split.zip"
    _write_split_archive(archive, [{"id": 1}], [{"id": 2}])
    monkeypatch.setattr(
        split_module,
        "DOLOMITES_ARCHIVE",
        RemoteFile("archive.zip", "https://example.test/archive.zip", "0" * 64),
    )

    with pytest.raises(ValueError, match="archive hash mismatch"):
        split_module.main(["--archive", str(archive)])
