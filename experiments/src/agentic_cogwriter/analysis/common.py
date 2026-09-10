from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONTRASTS = (("A4", "A1"), ("A4", "A2"), ("A4", "A3"), ("A4", "A5"), ("A4", "A6"))


@dataclass(frozen=True)
class RunRecord:
    root: Path
    path: Path
    manifest: dict[str, Any]

    @property
    def benchmark(self) -> str:
        return str(self.manifest["inputs"]["benchmark_name"])

    @property
    def condition(self) -> str:
        return str(self.manifest["inputs"]["condition_id"])

    @property
    def prompt(self) -> str:
        return str(self.manifest["inputs"]["prompt_id"])

    @property
    def platform(self) -> str:
        return str(self.manifest["inputs"].get("platform", "codex"))

    @property
    def status(self) -> str:
        return str(self.manifest.get("status", "unknown"))


def _read_manifest(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or not isinstance(value.get("inputs"), dict):
        return None
    inputs = value["inputs"]
    if not all(
        isinstance(inputs.get(field), str)
        for field in ("benchmark_name", "condition_id", "prompt_id")
    ):
        return None
    return value


def select_canonical_runs(roots: list[Path] | tuple[Path, ...]) -> list[RunRecord]:
    candidates: dict[tuple[str, str, str, str], list[RunRecord]] = {}
    for root_value in roots:
        root = root_value.resolve()
        for manifest_path in sorted(root.rglob("run-manifest.json")):
            manifest = _read_manifest(manifest_path)
            if manifest is None:
                continue
            record = RunRecord(root, manifest_path.parent, manifest)
            candidates.setdefault(
                (record.benchmark, record.condition, record.prompt, record.platform), []
            ).append(record)

    selected: list[RunRecord] = []
    for key in sorted(candidates):
        values = candidates[key]
        completed = [value for value in values if value.status == "completed"]
        pool = completed or [value for value in values if value.status != "completed"]
        if pool:
            selected.append(
                max(
                    pool,
                    key=lambda value: (
                        str(value.manifest.get("started_at", "")),
                        str(value.path),
                    ),
                )
            )
    return selected
