#!/usr/bin/env python3
"""Prepare the Zensical documentation source tree.

The hand-written files under ``docs/`` remain the source of truth.

Repository-relative links that leave ``docs/`` are valid on GitHub, but their
targets do not belong to Zensical's ``docs_dir``. For the generated site only,
rewrite those links to their corresponding GitHub source URLs.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = REPO_ROOT / "docs"
OUTPUT_ROOT = REPO_ROOT / ".docs-site"

REPOSITORY_URL = "https://github.com/shunk031/agentic-cognitive-writing"
BRANCH = "main"

# Rewrite ordinary Markdown links whose targets walk out of docs/. Links that
# stay inside docs/ are deliberately left untouched so Zensical can validate
# and rewrite them as documentation links.
OUTWARD_LINK = re.compile(
    r"(?P<prefix>\]\()"
    r"(?P<target>(?:\.\./)+[^)\s#]+)"
    r"(?P<fragment>#[^)\s]+)?"
    r"(?P<suffix>\))"
)


def is_within(path: Path, parent: Path) -> bool:
    """Return whether ``path`` is contained by ``parent``."""
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def github_url(target: Path) -> str:
    """Return the GitHub source URL for a repository path."""
    relative = target.relative_to(REPO_ROOT).as_posix()
    kind = "tree" if target.is_dir() else "blob"
    return f"{REPOSITORY_URL}/{kind}/{BRANCH}/{relative}"


def rewrite_links(source: Path, text: str) -> str:
    """Rewrite repository-relative links that leave the docs tree."""

    def replace(match: re.Match[str]) -> str:
        raw_target = match.group("target")
        resolved = (source.parent / raw_target).resolve()

        if is_within(resolved, DOCS_ROOT):
            return match.group(0)

        if not is_within(resolved, REPO_ROOT):
            return match.group(0)

        fragment = match.group("fragment") or ""
        return (
            f"{match.group('prefix')}"
            f"{github_url(resolved)}"
            f"{fragment}"
            f"{match.group('suffix')}"
        )

    return OUTWARD_LINK.sub(replace, text)


def main() -> int:
    """Copy docs into the generated site source tree."""
    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)

    OUTPUT_ROOT.mkdir(parents=True)

    pages = 0
    for source in sorted(DOCS_ROOT.rglob("*")):
        if not source.is_file():
            continue

        destination = OUTPUT_ROOT / source.relative_to(DOCS_ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)

        if source.suffix == ".md":
            text = source.read_text(encoding="utf-8")
            destination.write_text(rewrite_links(source, text), encoding="utf-8")
            pages += 1
        else:
            shutil.copy2(source, destination)

    print(f"prepared {pages} Markdown pages in {OUTPUT_ROOT.relative_to(REPO_ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
