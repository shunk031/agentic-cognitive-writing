"""Append-only trace writing, validation, and artifact hashing."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from .hashing import sha256_file


def timestamp() -> str:
    """Return a timezone-aware ISO 8601 timestamp."""

    return datetime.now(UTC).isoformat()


def validate_jsonl(path: Path) -> None:
    """Ensure every non-empty trace line is standalone JSON."""

    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        try:
            json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc


def collect_plugin_trace(source_root: Path, run_root: Path) -> list[str]:
    """Copy plugin-owned trace and state files without synthesizing events."""

    copied: list[str] = []
    for relative in (
        Path(".writing/trace/process.jsonl"),
        Path(".writing/goals.md"),
        Path(".writing/draft.md"),
    ):
        source = source_root / relative
        if source.is_file():
            destination = run_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            copied.append(relative.as_posix())
    return copied


def checksums_for_files(root: Path, relative_paths: list[str]) -> dict[str, str]:
    """Hash named run artifacts with a stable ``sha256:`` prefix."""

    return {
        relative: f"sha256:{sha256_file(root / relative)}"
        for relative in relative_paths
        if (root / relative).is_file()
    }
