#!/usr/bin/env python3
"""Build an anonymized zip of the committed repository for double-blind review.

Usage:
    python3 tools/make-anonymous-supplement.py [--ref HEAD] [--output dist/anonymous-supplement.zip]
        [--term TEXT ...]

The zip holds the files committed at --ref (no .git, no untracked or ignored
files) minus the development-only paths in EXCLUDED. Identifying strings are
read at run time, so none of them are committed here:

- the GitHub owner from the origin remote URL,
- git user.name and user.email,
- the local login name and home directory,
- every line of .local/anonymize-terms.txt (gitignored) and every --term.

The owner, name, and email are replaced in text files. Afterwards every file,
binary files included, is scanned case-insensitively for every term and for
each word of the author name; any hit aborts without writing the zip.
"""

from __future__ import annotations

import argparse
import getpass
import io
import re
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = (
    ".github/",
    "AGENTS.md",
    "CLAUDE.md",
    "paper/HANDOFF.md",
    "paper/feedback-scope.json",
    "paper/ARR-RESPONSIBLE-NLP-CHECKLIST.md",
    "paper/human-eval/",
)
ANONYMOUS_OWNER = "anonymous"
ANONYMOUS_NAME = "Anonymous Authors"
ANONYMOUS_EMAIL = "anonymous@example.com"
ZIP_DATE = (1980, 1, 1, 0, 0, 0)


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def git_config(key: str) -> str:
    result = subprocess.run(
        ["git", "config", key], cwd=ROOT, capture_output=True, text=True, check=False
    )
    return result.stdout.strip()


def identity() -> tuple[dict[str, str], list[str]]:
    """Return (replacements, scan terms) gathered from the local environment."""
    owner_match = re.search(
        r"github\.com[:/]([^/]+)/", git("remote", "get-url", "origin")
    )
    owner = owner_match.group(1) if owner_match else ""
    name = git_config("user.name")
    email = git_config("user.email")
    replacements = {
        value: anonymous
        for value, anonymous in (
            (email, ANONYMOUS_EMAIL),
            (name, ANONYMOUS_NAME),
            (owner, ANONYMOUS_OWNER),
        )
        if value
    }
    terms = [*replacements, *name.split(), getpass.getuser(), str(Path.home())]
    extra = ROOT / ".local" / "anonymize-terms.txt"
    if extra.exists():
        terms += extra.read_text(encoding="utf-8").splitlines()
    return replacements, sorted(
        {term.strip() for term in terms if len(term.strip()) >= 3}
    )


def included(path: str) -> bool:
    return not any(path == rule or path.startswith(rule) for rule in EXCLUDED)


def anonymize(data: bytes, replacements: dict[str, str]) -> bytes:
    """Replace identity strings in UTF-8 text; leave binary content untouched."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    for value, anonymous in replacements.items():
        text = re.sub(re.escape(value), anonymous, text, flags=re.IGNORECASE)
    return text.encode("utf-8")


def leaks(files: dict[str, bytes], terms: list[str]) -> list[str]:
    hits = []
    for path, data in files.items():
        lowered = data.lower()
        for term in terms:
            needle = term.lower().encode("utf-8")
            if needle in lowered or needle in path.lower().encode("utf-8"):
                line = (
                    lowered[: lowered.find(needle)].count(b"\n") + 1
                    if needle in lowered
                    else 0
                )
                hits.append(f"{path}:{line}: {term!r}")
    return hits


def committed_files(ref: str) -> tuple[dict[str, bytes], dict[str, int]]:
    """Return the committed file contents and modes at ref, minus EXCLUDED paths."""
    archive = subprocess.run(
        ["git", "archive", "--format=tar", ref],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    files, modes = {}, {}
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar.getmembers():
            content = tar.extractfile(member) if member.isfile() else None
            if content is not None and included(member.name):
                files[member.name] = content.read()
                modes[member.name] = member.mode
    return files, modes


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "dist" / "anonymous-supplement.zip"
    )
    parser.add_argument(
        "--term",
        action="append",
        default=[],
        help="extra identifying string to replace-check",
    )
    args = parser.parse_args(argv)

    replacements, terms = identity()
    terms = sorted({*terms, *(term for term in args.term if len(term) >= 3)})
    committed, modes = committed_files(args.ref)
    files = {path: anonymize(data, replacements) for path, data in committed.items()}
    found = leaks(files, terms)
    if found:
        print("\n".join(found), file=sys.stderr)
        sys.exit(f"identifying strings remain in {len(found)} places; no zip written")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(files):
            info = zipfile.ZipInfo(f"supplement/{path}", ZIP_DATE)
            info.external_attr = (modes[path] & 0o777) << 16
            bundle.writestr(info, files[path], zipfile.ZIP_DEFLATED)
    size = args.output.stat().st_size / 1e6
    print(
        f"Wrote {args.output} ({len(files)} files, {size:.1f} MB) from {git('rev-parse', '--short', args.ref)}; "
        f"{len(terms)} identifying terms scanned, none found."
    )


if __name__ == "__main__":
    main()
