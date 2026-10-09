#!/usr/bin/env python3
"""Fail CI when manuscript prose changes exceed an explicitly declared feedback scope.

For each feedback batch, paper/feedback-scope.json records the commit immediately
before the batch and the exact before/after replacements authorized for that batch.
Scope declarations must be committed separately from manuscript .tex edits. The
manifest may be extended in later manifest-only commits when the author adds
feedback before the batch is complete; the final manifest still audits the full
prose diff from baseline to HEAD.

Source-only reflow is allowed without a replacement declaration when it changes
only ordinary whitespace inside existing paragraphs. This supports conventions
such as one-sentence-per-line without weakening the guard against prose edits.
New manuscript files remain forbidden unless their exact contents are declared
in ``created_files``.
"""

from __future__ import annotations

import difflib
import json
import re
import subprocess
from pathlib import Path


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).rstrip("\n")


def fail(message: str) -> None:
    raise SystemExit(f"feedback-scope guard: {message}")


def normalize_eof(text: str) -> str:
    """Treat only trailing newline differences as non-substantive."""
    return text.rstrip("\n")


def normalize_paragraph_whitespace(text: str) -> str:
    """Canonicalize whitespace while preserving TeX paragraph boundaries.

    A single physical newline in ordinary TeX prose is whitespace, so inserting
    one between sentences is source formatting only. A blank line is a paragraph
    boundary and is retained here because changing it can change typesetting.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
    paragraphs = re.split(r"\n[ \t]*\n+", normalized)
    return "\n\n".join(re.sub(r"[ \t\n]+", " ", paragraph).strip() for paragraph in paragraphs)


def text_at_commit(commit: str, path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def main() -> None:
    repo = Path(git("rev-parse", "--show-toplevel"))
    manifest_rel = "paper/feedback-scope.json"
    manifest_path = repo / manifest_rel
    if not manifest_path.exists():
        fail("paper/feedback-scope.json is missing")

    scope = json.loads(manifest_path.read_text(encoding="utf-8"))
    baseline = scope.get("baseline_sha", "").strip()
    replacements = scope.get("replacements", [])
    created_files = scope.get("created_files", [])
    if not baseline:
        fail("baseline_sha is required")

    subprocess.run(
        ["git", "cat-file", "-e", f"{baseline}^{{commit}}"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Scope declarations must remain separate from prose edits. The author can
    # add feedback while a batch is in progress, so allow multiple declaration
    # commits, but require every one of them to be manifest-only. The final
    # manifest below still has to reproduce the complete baseline-to-HEAD TeX
    # diff exactly, so additive declarations do not widen the prose allowance
    # implicitly.
    scope_commits = [
        line
        for line in git(
            "log",
            "--format=%H",
            f"{baseline}..HEAD",
            "--",
            manifest_rel,
        ).splitlines()
        if line
    ]
    if not scope_commits:
        fail("feedback-scope.json must be declared after baseline_sha")
    for scope_commit in scope_commits:
        scope_commit_files = {
            path
            for path in git(
                "diff-tree", "--no-commit-id", "--name-only", "-r", scope_commit
            ).splitlines()
            if path
        }
        if scope_commit_files != {manifest_rel}:
            fail(
                "each feedback-scope declaration commit must be manifest-only; "
                f"{scope_commit} changed: " + ", ".join(sorted(scope_commit_files))
            )

    by_path: dict[str, list[dict[str, str]]] = {}
    for index, item in enumerate(replacements, start=1):
        path = item.get("path", "").strip()
        instruction = item.get("instruction", "").strip()
        before = item.get("before", "")
        after = item.get("after", "")
        if not path.startswith("paper/") or not path.endswith(".tex"):
            fail(f"replacement {index} must target a manuscript .tex file under paper/")
        if not instruction:
            fail(f"replacement {index} needs the exact author instruction it implements")
        if not before or before == after:
            fail(f"replacement {index} needs distinct non-empty before/after text")
        by_path.setdefault(path, []).append(item)

    created_by_path: dict[str, dict[str, str]] = {}
    for index, item in enumerate(created_files, start=1):
        path = item.get("path", "").strip()
        instruction = item.get("instruction", "").strip()
        content = item.get("content", "")
        if not path.startswith("paper/") or not path.endswith(".tex"):
            fail(f"created file {index} must be a manuscript .tex file under paper/")
        if not instruction:
            fail(f"created file {index} needs the exact author instruction it implements")
        if not content:
            fail(f"created file {index} needs non-empty exact content")
        if path in created_by_path:
            fail(f"created file declared more than once: {path}")
        created_by_path[path] = item

    changed_tex = {
        path
        for path in git("diff", "--name-only", f"{baseline}..HEAD", "--", "paper").splitlines()
        if path.startswith("paper/") and path.endswith(".tex")
    }

    # Existing files may be reflowed without a declaration only when paragraph
    # boundaries and all non-whitespace characters are identical to baseline.
    unauthorized_files: list[str] = []
    for path in sorted(changed_tex - set(by_path) - set(created_by_path)):
        base_text = text_at_commit(baseline, path)
        current_path = repo / path
        if base_text is None or not current_path.exists():
            unauthorized_files.append(path)
            continue
        current = current_path.read_text(encoding="utf-8")
        if normalize_paragraph_whitespace(base_text) != normalize_paragraph_whitespace(current):
            unauthorized_files.append(path)
    if unauthorized_files:
        fail(
            "manuscript TeX changed outside the declared feedback scope: "
            + ", ".join(unauthorized_files)
        )

    for path, items in by_path.items():
        base_text = text_at_commit(baseline, path)
        if base_text is None:
            fail(f"cannot read {path} at baseline {baseline}")

        expected = base_text
        for item in items:
            before = item["before"]
            count = expected.count(before)
            if count != 1:
                fail(
                    f"declared before-text for {path} must occur exactly once at baseline; "
                    f"found {count}: {item['instruction']}"
                )
            expected = expected.replace(before, item["after"], 1)

        current_path = repo / path
        if not current_path.exists():
            fail(f"declared manuscript file disappeared: {path}")
        current = current_path.read_text(encoding="utf-8")

        # A declaration-only commit may still contain the baseline text. Once
        # prose editing starts, the file must equal exactly the declared result.
        # A final newline is formatting-only and is ignored; all other text
        # remains exact.
        normalized_current = normalize_eof(current)
        normalized_allowed = {
            normalize_eof(base_text),
            normalize_eof(expected),
        }
        if normalized_current not in normalized_allowed:
            diff = "".join(
                difflib.unified_diff(
                    expected.splitlines(keepends=True),
                    current.splitlines(keepends=True),
                    fromfile=f"declared/{path}",
                    tofile=f"actual/{path}",
                )
            )
            fail(
                f"{path} differs from the exact declared replacements. "
                "This usually means neighboring prose was changed without authorization.\n"
                + diff[:8000]
            )

    for path, item in created_by_path.items():
        if text_at_commit(baseline, path) is not None:
            fail(f"declared created file already exists at baseline: {path}")
        current_path = repo / path
        if not current_path.exists():
            # A declaration-only commit may precede creation of the file.
            continue
        current = current_path.read_text(encoding="utf-8")
        if normalize_eof(current) != normalize_eof(item["content"]):
            fail(f"created manuscript file differs from declared exact content: {path}")

    print(
        "Feedback scope guard: passed "
        f"(baseline={baseline}, scope declarations={len(scope_commits)}, "
        f"declared replacements={len(replacements)}, declared created files={len(created_files)})"
    )


if __name__ == "__main__":
    main()
