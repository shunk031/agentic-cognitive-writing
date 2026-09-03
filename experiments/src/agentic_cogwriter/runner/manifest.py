"""Prompt manifest schema and immutable hash validation."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..paths import PROVENANCE_PATH
from .errors import ManifestError
from .hashing import sha256_bytes, sha256_json


def _without(mapping: Mapping[str, Any], key: str) -> dict[str, Any]:
    return {name: value for name, value in mapping.items() if name != key}


@dataclass(frozen=True)
class PromptRecord:
    """One immutable benchmark prompt and its requested output constraints."""

    prompt_id: str
    benchmark_name: str
    source_version: str
    prompt_text: str | None
    requested_output_constraints: Any
    row_hash: str
    supplied_context: str = ""
    source_reference: str | None = None
    manifest_hash: str | None = None

    @classmethod
    def from_mapping(
        cls, row: Mapping[str, Any], *, manifest_hash: str | None = None
    ) -> PromptRecord:
        required = (
            "prompt_id",
            "benchmark_name",
            "source_version",
            "requested_output_constraints",
            "hash",
        )
        missing = [field for field in required if field not in row]
        if missing:
            raise ManifestError(f"Prompt row is missing fields: {', '.join(missing)}")
        prompt_text = row.get("prompt_text")
        source_reference = row.get("source_reference")
        if not isinstance(prompt_text, str) and not isinstance(source_reference, str):
            raise ManifestError("Each prompt row needs prompt_text or source_reference")
        if isinstance(prompt_text, str) and not prompt_text.strip():
            raise ManifestError("prompt_text must be a non-empty string")
        if isinstance(source_reference, str) and not source_reference.strip():
            raise ManifestError("source_reference must be a non-empty string")
        if not isinstance(row["prompt_id"], str) or not row["prompt_id"].strip():
            raise ManifestError("prompt_id must be a non-empty string")
        if (
            not isinstance(row["benchmark_name"], str)
            or not row["benchmark_name"].strip()
        ):
            raise ManifestError("benchmark_name must be a non-empty string")
        if (
            not isinstance(row["source_version"], str)
            or not row["source_version"].strip()
        ):
            raise ManifestError("source_version must be a non-empty string")
        expected_hash = sha256_json(_without(row, "hash"))
        if row["hash"] != expected_hash:
            raise ManifestError(
                f"Prompt row {row.get('prompt_id', '<unknown>')} has an invalid "
                "row hash"
            )
        return cls(
            prompt_id=row["prompt_id"],
            benchmark_name=row["benchmark_name"],
            source_version=row["source_version"],
            prompt_text=prompt_text,
            source_reference=source_reference,
            supplied_context=str(row.get("supplied_context", "")),
            requested_output_constraints=row["requested_output_constraints"],
            row_hash=row["hash"],
            manifest_hash=manifest_hash,
        )

    @property
    def input_text(self) -> str:
        """Return prompt text, refusing to fetch a source reference at run time."""

        if self.prompt_text is None:
            raise ManifestError(
                f"Prompt {self.prompt_id} has only source_reference; materialize "
                "prompt text before running"
            )
        return self.prompt_text


@dataclass(frozen=True)
class PromptManifest:
    """A content-addressed collection of prompts for one benchmark."""

    benchmark_name: str
    source_version: str
    prompts: tuple[PromptRecord, ...]
    manifest_hash: str
    path: Path

    def get(self, prompt_id: str) -> PromptRecord:
        """Find one prompt by stable ID."""

        for prompt in self.prompts:
            if prompt.prompt_id == prompt_id:
                return prompt
        raise ManifestError(f"Prompt ID not found: {prompt_id}")


def _validate_prompt_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    benchmark_name: str,
    source_version: str,
    manifest_hash: str,
    path: Path,
) -> PromptManifest:
    """Validate rows shared by JSON and JSON Lines prompt manifests."""

    prompts = tuple(
        PromptRecord.from_mapping(row, manifest_hash=manifest_hash) for row in rows
    )
    for prompt in prompts:
        if prompt.benchmark_name != benchmark_name:
            raise ManifestError(
                f"Prompt {prompt.prompt_id} benchmark_name differs from manifest "
                "benchmark_name"
            )
        if prompt.source_version != source_version:
            raise ManifestError(
                f"Prompt {prompt.prompt_id} source_version differs from manifest "
                "source_version"
            )
    ids = [prompt.prompt_id for prompt in prompts]
    if len(ids) != len(set(ids)):
        raise ManifestError("Prompt IDs must be unique within a manifest")
    return PromptManifest(
        benchmark_name=benchmark_name,
        source_version=source_version,
        prompts=prompts,
        manifest_hash=manifest_hash,
        path=path,
    )


def _parse_jsonl(text: str, path: Path) -> list[Mapping[str, Any]]:
    """Parse the sibling benchmark member's one-object-per-line format."""

    rows: list[Mapping[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ManifestError(
                f"Invalid JSONL in {path}:{line_number}: {exc}"
            ) from exc
        if not isinstance(value, dict):
            raise ManifestError(
                f"Prompt manifest row {path}:{line_number} must be an object"
            )
        rows.append(value)
    if not rows:
        raise ManifestError(f"Prompt manifest {path} has no rows")
    return rows


def _load_document_manifest(
    document: Mapping[str, Any], *, path: Path
) -> PromptManifest:
    """Load an object-form manifest used by isolated runner fixtures."""

    required = (
        "schema_version",
        "benchmark_name",
        "source_version",
        "prompts",
        "manifest_hash",
    )
    missing = [field for field in required if field not in document]
    if missing:
        raise ManifestError(f"Prompt manifest is missing fields: {', '.join(missing)}")
    if document["schema_version"] != 1:
        raise ManifestError("Unsupported prompt manifest schema_version")
    if not isinstance(document["prompts"], list):
        raise ManifestError("Prompt manifest prompts must be a list")
    expected_hash = sha256_json(_without(document, "manifest_hash"))
    if document["manifest_hash"] != expected_hash:
        raise ManifestError("Prompt manifest has an invalid manifest_hash")
    if not isinstance(document["benchmark_name"], str) or not isinstance(
        document["source_version"], str
    ):
        raise ManifestError(
            "Prompt manifest benchmark and source versions must be strings"
        )
    rows = [row for row in document["prompts"] if isinstance(row, dict)]
    if len(rows) != len(document["prompts"]):
        raise ManifestError("Prompt manifest rows must be objects")
    return _validate_prompt_rows(
        rows,
        benchmark_name=document["benchmark_name"],
        source_version=document["source_version"],
        manifest_hash=document["manifest_hash"],
        path=path,
    )


def load_prompt_manifest(path: Path) -> PromptManifest:
    """Load JSONL prompt rows and validate hashes without network access."""

    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise ManifestError(f"Cannot read prompt manifest {path}: {exc}") from exc

    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        document = None
    if isinstance(document, dict) and {
        "schema_version",
        "benchmark_name",
        "source_version",
        "prompts",
        "manifest_hash",
    }.issubset(document):
        return _load_document_manifest(document, path=path)

    rows = _parse_jsonl(text, path)
    first = rows[0]
    benchmark_name = first.get("benchmark_name")
    source_version = first.get("source_version")
    if not isinstance(benchmark_name, str) or not benchmark_name.strip():
        raise ManifestError("JSONL prompt rows need a benchmark_name")
    if not isinstance(source_version, str) or not source_version.strip():
        raise ManifestError("JSONL prompt rows need a source_version")
    return _validate_prompt_rows(
        rows,
        benchmark_name=benchmark_name,
        source_version=source_version,
        manifest_hash=sha256_bytes(raw),
        path=path,
    )


def load_benchmark_provenance(
    benchmark_name: str, *, path: Path = PROVENANCE_PATH
) -> dict[str, Any]:
    """Return the checked-in provenance record for a benchmark without rewriting it."""

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Cannot read benchmark provenance {path}: {exc}") from exc
    benchmarks = document.get("benchmarks") if isinstance(document, dict) else None
    if not isinstance(benchmarks, Mapping):
        raise ManifestError(f"Benchmark provenance {path} has no benchmarks object")
    key = benchmark_name.casefold()
    value = benchmarks.get(key)
    if not isinstance(value, dict):
        for candidate in benchmarks.values():
            if (
                isinstance(candidate, dict)
                and candidate.get("name", "").casefold() == key
            ):
                value = candidate
                break
    if not isinstance(value, dict):
        raise ManifestError(f"Benchmark {benchmark_name!r} has no record in {path}")
    return json.loads(json.dumps(value, ensure_ascii=False))
