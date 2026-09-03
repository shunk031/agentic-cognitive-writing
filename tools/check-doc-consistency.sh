#!/usr/bin/env python3
"""Check documentation with three string-level rules.

1. Stale identifiers from ``DENY_LIST`` are findings anywhere in a
   documentation file, case-insensitively.
2. Skill tokens must name a skill directory under a plugin root or a package
   name from a plugin manifest.
3. GitHub blob/tree URLs for this repository are findings; use a
   repository-relative link.
"""

from __future__ import annotations

import json
import re
import sys
from argparse import ArgumentParser
from pathlib import Path


REPOSITORY_SLUG = "shunk031/agentic-cognitive-writing"
PLUGIN_RELATIVE_ROOTS = (Path("plugin"), Path("experiments") / "plugin")
PACKAGE_MANIFEST_RELATIVE_PATHS = (
    Path(".claude-plugin") / "plugin.json",
    Path(".codex-plugin") / "plugin.json",
)

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
    r"(?<![A-Za-z0-9_-])(?:"
    r"cognitive-writing-[A-Za-z0-9][A-Za-z0-9_-]*|"
    r"agentic-cog-writer(?:-[A-Za-z0-9][A-Za-z0-9_-]*)?"
    r")",
    re.IGNORECASE,
)
IN_REPOSITORY_URL_PATTERN = re.compile(
    rf"https?://github\.com/{re.escape(REPOSITORY_SLUG)}"
    r"/(?:blob|tree)/[^\s?#]+",
    re.IGNORECASE,
)


def _names_under(directory: Path) -> set[str]:
    if not directory.is_dir():
        return set()
    return {entry.name for entry in directory.iterdir() if entry.is_dir()}


def _plugin_roots(root: Path) -> tuple[list[Path], list[Path]]:
    found: list[Path] = []
    missing: list[Path] = []
    for relative_root in PLUGIN_RELATIVE_ROOTS:
        plugin_root = root / relative_root
        if plugin_root.is_dir():
            found.append(plugin_root)
        else:
            missing.append(relative_root)
    return found, missing


def _package_names(plugin_directory: Path) -> set[str]:
    names: set[str] = set()
    for relative_manifest in PACKAGE_MANIFEST_RELATIVE_PATHS:
        manifest = plugin_directory / relative_manifest
        if not manifest.is_file():
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        name = data.get("name") if isinstance(data, dict) else None
        if isinstance(name, str) and name:
            names.add(name)
    return names


def _known_names(plugin_directories: list[Path]) -> set[str]:
    names: set[str] = set()
    for plugin_directory in plugin_directories:
        names.update(_names_under(plugin_directory / "skills"))
        names.update(_package_names(plugin_directory))
    return names


def _repository_root(cli_root: Path | None) -> Path:
    source_root = Path(__file__).resolve().parents[1]
    return cli_root.expanduser().resolve() if cli_root is not None else source_root


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


def _findings(root: Path, known_names: set[str]) -> list[str]:
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
                if normalized_token in seen_skills:
                    continue
                seen_skills.add(normalized_token)
                if token not in known_names:
                    findings.append(
                        f"{location}: unknown skill name '{token}' "
                        "(not found under plugin/skills/)"
                    )

            for match in IN_REPOSITORY_URL_PATTERN.finditer(line):
                findings.append(
                    f"{location}: in-repository GitHub URL '{match.group(0)}'; "
                    "use a repository-relative link"
                )

    return findings


def main(argv: list[str] | None = None) -> int:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        help="repository root to scan",
    )
    arguments = parser.parse_args(argv)
    root = _repository_root(arguments.repo_root)
    plugin_directories, missing_roots = _plugin_roots(root)
    for missing_root in missing_roots:
        print(f"{missing_root.as_posix()}/: missing; skipping plugin root")
    if not plugin_directories:
        print("no plugin roots found; skipping documentation consistency checks")
        return 0

    findings = _findings(root, _known_names(plugin_directories))
    for finding in findings:
        print(finding)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
