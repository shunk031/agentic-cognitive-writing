"""Prompt manifest schema and immutable hash validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .errors import ManifestError
from .hashing import sha256_json


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
    def from_mapping(cls, row: Mapping[str, Any], *, manifest_hash: str | None = None) -> "PromptRecord":
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
        if not isinstance(row["prompt_id"], str) or not row["prompt_id"].strip():
            raise ManifestError("prompt_id must be a non-empty string")
        if not isinstance(row["benchmark_name"], str) or not row["benchmark_name"].strip():
            raise ManifestError("benchmark_name must be a non-empty string")
        if not isinstance(row["source_version"], str) or not row["source_version"].strip():
            raise ManifestError("source_version must be a non-empty string")
        expected_hash = sha256_json(_without(row, "hash"))
        if row["hash"] != expected_hash:
            raise ManifestError(
                f"Prompt row {row.get('prompt_id', '<unknown>')} has an invalid row hash"
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
                f"Prompt {self.prompt_id} has only source_reference; materialize prompt text before running"
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


def load_prompt_manifest(path: Path) -> PromptManifest:
    """Load and validate a materialized prompt manifest without network access."""

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Cannot read prompt manifest {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise ManifestError("Prompt manifest must be a JSON object")
    required = ("schema_version", "benchmark_name", "source_version", "prompts", "manifest_hash")
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
    prompts = tuple(
        PromptRecord.from_mapping(row, manifest_hash=document["manifest_hash"])
        for row in document["prompts"]
    )
    for prompt in prompts:
        if prompt.benchmark_name != document["benchmark_name"]:
            raise ManifestError(
                f"Prompt {prompt.prompt_id} benchmark_name differs from manifest benchmark_name"
            )
        if prompt.source_version != document["source_version"]:
            raise ManifestError(
                f"Prompt {prompt.prompt_id} source_version differs from manifest source_version"
            )
    ids = [prompt.prompt_id for prompt in prompts]
    if len(ids) != len(set(ids)):
        raise ManifestError("Prompt IDs must be unique within a manifest")
    return PromptManifest(
        benchmark_name=document["benchmark_name"],
        source_version=document["source_version"],
        prompts=prompts,
        manifest_hash=document["manifest_hash"],
        path=path,
    )
