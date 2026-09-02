#!/usr/bin/env python3
"""Check reader-facing documents against the plugin's current names and paths."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


TRACE_PATH = ".writing/trace/process.jsonl"

DENY_LIST = (
    "cognitive-writing-orchestrator",
    "revision-evaluator",
    "knowledge-transforming-revision",
    "writing-eval-harness",
    "ledger-schema.md",
    "ablation-variants.md",
    ".writing/ablation.md",
)

DENY_PATTERNS = tuple(
    (identifier, re.compile(re.escape(identifier), re.IGNORECASE))
    for identifier in DENY_LIST
)
DENY_PATTERNS += (
    ("6-arm", re.compile(r"\b6-arm\b", re.IGNORECASE)),
    ("six-arm", re.compile(r"\bsix-arm\b", re.IGNORECASE)),
)

SKILL_TOKEN_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_-])cognitive-writing-[A-Za-z0-9][A-Za-z0-9_-]*",
    re.IGNORECASE,
)
GITHUB_BLOB_OR_TREE_PATTERN = re.compile(
    r"https?://github\.com/(?P<owner>[^/\s?#]+)/(?P<repo>[^/\s?#]+)"
    r"/(?:blob|tree)/(?P<revision>[^/\s?#]+)/",
    re.IGNORECASE,
)
HEX_REVISION_PATTERN = re.compile(r"[0-9a-f]{7,40}", re.IGNORECASE)


def _names_under(directory: Path, *, file_stems: bool) -> set[str]:
    if not directory.is_dir():
        return set()

    names: set[str] = set()
    for entry in directory.iterdir():
        if entry.is_dir():
            names.add(entry.name)
        elif file_stems and entry.is_file():
            names.add(entry.stem)
    return names


def _ground_truth(plugin_directory: Path) -> dict[str, object]:
    return {
        "skills": _names_under(plugin_directory / "skills", file_stems=False),
        "agents": _names_under(plugin_directory / "agents", file_stems=True),
        "trace_path": TRACE_PATH,
    }


def _repository_slug(root: Path) -> str | None:
    """Return owner/repository for filtering GitHub links when git metadata exists."""

    try:
        result = subprocess.run(
            ["git", "-C", str(root), "config", "--get", "remote.origin.url"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None

    remote = result.stdout.strip()
    match = re.search(r"github\.com[/:](?P<owner>[^/\s:]+)/(?P<repo>[^/\s]+)$", remote)
    if not match:
        return None
    return f"{match.group('owner')}/{match.group('repo').removesuffix('.git')}".lower()


def _documentation_files(root: Path) -> list[Path]:
    files: set[Path] = set()
    for relative in ("README.md", "AGENTS.md"):
        path = root / relative
        if path.is_file():
            files.add(path)
    for relative_directory in ("docs/research", "docs/experiments"):
        directory = root / relative_directory
        if directory.is_dir():
            files.update(path for path in directory.glob("*.md") if path.is_file())
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def _is_in_repository_url(match: re.Match[str], repository_slug: str | None) -> bool:
    if repository_slug is None:
        return False
    candidate = f"{match.group('owner')}/{match.group('repo').removesuffix('.git')}".lower()
    return candidate == repository_slug


def _findings(
    root: Path, ground_truth: dict[str, object], repository_slug: str | None
) -> list[str]:
    skills = ground_truth["skills"]
    assert isinstance(skills, set)
    known_stale_skills = {
        identifier.lower()
        for identifier in DENY_LIST
        if identifier.lower().startswith("cognitive-writing-")
    }
    findings: list[str] = []

    for path in _documentation_files(root):
        relative_path = path.relative_to(root).as_posix()
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as error:
            findings.append(f"{relative_path}:1: cannot read file: {error}")
            continue

        for line_number, line in enumerate(lines, start=1):
            location = f"{relative_path}:{line_number}"
            for identifier, pattern in DENY_PATTERNS:
                if pattern.search(line):
                    findings.append(f"{location}: stale identifier '{identifier}'")

            seen_skills: set[str] = set()
            for match in SKILL_TOKEN_PATTERN.finditer(line):
                token = match.group(0)
                normalized_token = token.lower()
                if normalized_token in known_stale_skills or normalized_token in seen_skills:
                    continue
                seen_skills.add(normalized_token)
                if token not in skills:
                    findings.append(
                        f"{location}: unknown skill name '{token}' (not found under plugin/skills/)"
                    )

            for match in GITHUB_BLOB_OR_TREE_PATTERN.finditer(line):
                if not _is_in_repository_url(match, repository_slug):
                    continue
                revision = match.group("revision")
                if not HEX_REVISION_PATTERN.fullmatch(revision):
                    findings.append(
                        f"{location}: branch-qualified in-repo GitHub URL uses '{revision}'; "
                        "use a 7-40 character commit SHA"
                    )

    return findings


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    plugin_directory = root / "plugin"
    if not plugin_directory.is_dir():
        print("plugin/: missing; skipping documentation consistency checks")
        return 0

    ground_truth = _ground_truth(plugin_directory)
    repository_slug = _repository_slug(root)
    if repository_slug is None:
        print("in-repo GitHub URL check skipped: repository slug is unknown")
    findings = _findings(root, ground_truth, repository_slug)
    for finding in findings:
        print(finding)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
