#!/usr/bin/env python3
"""Check reader-facing documents against the plugin's current names and paths."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from argparse import ArgumentParser
from pathlib import Path


# This token is matched against document text and must remain a string.
TRACE_DOC_TOKEN = ".writing/trace/process.jsonl"
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
    r"(?<![A-Za-z0-9_-])cognitive-writing-[A-Za-z0-9][A-Za-z0-9_-]*",
    re.IGNORECASE,
)
SHA_TOKEN_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])[0-9a-f]{7,40}(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
DOI_TOKEN_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])10\.\d+/[0-9a-f]{7,40}(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
FENCE_PATTERN = re.compile(r"^[ \t]{0,3}(?P<marker>`{3,}|~{3,})")
INLINE_CODE_PATTERN = re.compile(r"`+[^`\n]*`+")
MARKDOWN_LINK_TARGET_PATTERN = re.compile(
    r"\]\(\s*(?:<[^>\n]*>|[^)\n\s]+)"
)
URL_PATTERN = re.compile(r"https?://[^\s<>()\]]+", re.IGNORECASE)
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


def _ground_truth(plugin_directories: list[Path]) -> dict[str, object]:
    skills: set[str] = set()
    agents: set[str] = set()
    packages: set[str] = set()
    trace_doc_tokens: set[str] = set()
    for plugin_directory in plugin_directories:
        skills.update(_names_under(plugin_directory / "skills", file_stems=False))
        agents.update(_names_under(plugin_directory / "agents", file_stems=True))
        packages.update(_package_names(plugin_directory))
        trace_doc_tokens.add(TRACE_DOC_TOKEN)
    return {
        "skills": skills,
        "agents": agents,
        "packages": packages,
        "trace_doc_tokens": trace_doc_tokens,
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


def _git_repository_root(start: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None

    discovered = result.stdout.strip()
    if result.returncode != 0 or not discovered:
        return None
    return Path(discovered).resolve()


def _repository_root(cli_root: Path | None) -> Path:
    source_root = Path(__file__).resolve().parents[1]
    if cli_root is not None:
        return cli_root.expanduser().resolve()
    return _git_repository_root(source_root) or source_root


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


def _mask_excluded_regions(line: str) -> str:
    masked = list(line)
    spans = [
        match.span()
        for pattern in (
            INLINE_CODE_PATTERN,
            MARKDOWN_LINK_TARGET_PATTERN,
            URL_PATTERN,
            DOI_TOKEN_PATTERN,
        )
        for match in pattern.finditer(line)
    ]
    for start, end in spans:
        masked[start:end] = [" "] * (end - start)
    return "".join(masked)


def _findings(
    root: Path, ground_truth: dict[str, object], repository_slug: str | None
) -> list[str]:
    skills = ground_truth["skills"]
    assert isinstance(skills, set)
    packages = ground_truth["packages"]
    assert isinstance(packages, set)
    known_names = skills | packages
    known_stale_skills = {
        identifier.lower()
        for identifier in DENY_LIST
        if identifier.lower().startswith("cognitive-writing-")
    }
    findings: list[str] = []

    for path in _documentation_files(root):
        relative_path = path.relative_to(root).as_posix()
        fence: tuple[str, int] | None = None
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as error:
            findings.append(f"{relative_path}:1: cannot read file: {error}")
            continue

        for line_number, line in enumerate(lines, start=1):
            location = f"{relative_path}:{line_number}"
            fence_match = FENCE_PATTERN.match(line)
            in_fenced_code = fence is not None or fence_match is not None
            if fence is not None:
                if (
                    fence_match is not None
                    and fence_match.group("marker")[0] == fence[0]
                    and len(fence_match.group("marker")) >= fence[1]
                ):
                    fence = None
            elif fence_match is not None:
                marker = fence_match.group("marker")
                fence = (marker[0], len(marker))

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
                if token not in known_names:
                    findings.append(
                        f"{location}: unknown skill name '{token}' (not found under plugin/skills/)"
                    )

            if not in_fenced_code:
                seen_shas: set[str] = set()
                for match in SHA_TOKEN_PATTERN.finditer(_mask_excluded_regions(line)):
                    token = match.group(0)
                    normalized_token = token.lower()
                    if normalized_token in seen_shas:
                        continue
                    seen_shas.add(normalized_token)
                    findings.append(
                        f"{location}: commit SHA '{token}' appears in prose; "
                        "keep SHAs in URLs or code"
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


def main(argv: list[str] | None = None) -> int:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        help="repository root to scan (defaults to git discovery)",
    )
    arguments = parser.parse_args(argv)
    root = _repository_root(arguments.repo_root)
    plugin_directories, missing_roots = _plugin_roots(root)
    for missing_root in missing_roots:
        print(f"{missing_root.as_posix()}/: missing; skipping plugin root")
    if not plugin_directories:
        print("no plugin roots found; skipping documentation consistency checks")
        return 0

    ground_truth = _ground_truth(plugin_directories)
    repository_slug = _repository_slug(root)
    if repository_slug is None:
        print("in-repo GitHub URL check skipped: repository slug is unknown")
    findings = _findings(root, ground_truth, repository_slug)
    for finding in findings:
        print(finding)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
