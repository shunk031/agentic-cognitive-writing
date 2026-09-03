#!/usr/bin/env python3
"""Run with: uv run tools/test_check_doc_consistency.py"""

from __future__ import annotations

import io
import os
import runpy
import subprocess
import sys
import tarfile
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


CHECKER = Path(__file__).resolve().with_name("check-doc-consistency.sh")
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_SLUG = "shunk031/agentic-cognitive-writing"
ACTUAL_PLUGIN_COMMIT = "d0d6da7d0607f9d54b35973c2cf4e10d779a15dd"
MAIN_SKILL = "agentic-cog-writer"


def _clean_git_environment() -> dict[str, str]:
    return {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("GIT_")
    }


def _run_git(
    *arguments: str,
    cwd: Path,
    check: bool,
    capture_output: bool = False,
    text: bool = False,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *arguments],
        check=check,
        cwd=cwd,
        env=_clean_git_environment(),
        capture_output=capture_output,
        text=text,
    )


class CheckDocConsistencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = TemporaryDirectory()
        self.root = Path(self._temporary_directory.name)

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    def _create_plugin(
        self,
        relative_root: Path,
        *,
        skills: tuple[str, ...] = (),
        agents: tuple[str, ...] = (),
    ) -> None:
        plugin_root = self.root / relative_root
        skills_root = plugin_root / "skills"
        agents_root = plugin_root / "agents"
        skills_root.mkdir(parents=True)
        agents_root.mkdir()
        for skill in skills:
            (skills_root / skill).mkdir()
        for agent in agents:
            (agents_root / f"{agent}.md").write_text("agent\n", encoding="utf-8")

    def _write_readme(self, text: str) -> None:
        (self.root / "README.md").write_text(text, encoding="utf-8")

    def _add_origin_remote(self) -> None:
        _run_git("init", "--quiet", cwd=self.root, check=True)
        _run_git(
            "config",
            "remote.origin.url",
            f"https://github.com/{REPOSITORY_SLUG}.git",
            cwd=self.root,
            check=True,
        )

    def _initialize_committed_git_fixture(self) -> None:
        _run_git("init", "--quiet", cwd=self.root, check=True)
        _run_git("symbolic-ref", "HEAD", "refs/heads/main", cwd=self.root, check=True)
        _run_git(
            "config",
            "remote.origin.url",
            f"https://github.com/{REPOSITORY_SLUG}.git",
            cwd=self.root,
            check=True,
        )
        _run_git("config", "user.name", "Checker Test", cwd=self.root, check=True)
        _run_git(
            "config",
            "user.email",
            "checker-test@example.invalid",
            cwd=self.root,
            check=True,
        )

    def _commit_fixture(self, message: str) -> str:
        _run_git("add", ".", cwd=self.root, check=True)
        _run_git("commit", "--quiet", "-m", message, cwd=self.root, check=True)
        return _run_git(
            "rev-parse",
            "HEAD",
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def _checkout_new_branch(self, branch: str) -> None:
        _run_git("checkout", "--quiet", "-b", branch, cwd=self.root, check=True)

    def _update_ref(self, ref: str, revision: str) -> None:
        _run_git("update-ref", ref, revision, cwd=self.root, check=True)

    def _run_checker(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CHECKER), "--repo-root", str(self.root)],
            check=False,
            cwd=self.root,
            env=_clean_git_environment(),
            capture_output=True,
            text=True,
        )

    def _materialize_actual_plugin_tree(self) -> None:
        ref = f"{ACTUAL_PLUGIN_COMMIT}^{{commit}}"
        object_check = _run_git(
            "cat-file",
            "-e",
            ref,
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if object_check.returncode != 0:
            fetch = _run_git(
                "fetch",
                "origin",
                "feat/cognitive-writing-plugin",
                cwd=REPOSITORY_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                fetch.returncode,
                0,
                fetch.stdout + fetch.stderr,
            )

        archive = _run_git(
            "archive",
            "--format=tar",
            ACTUAL_PLUGIN_COMMIT,
            "README.md",
            "plugin",
            "experiments/plugin",
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
        )
        self.assertEqual(archive.returncode, 0, archive.stderr.decode())
        with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as archive_file:
            for member in archive_file.getmembers():
                target = self.root / Path(member.name)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    source = archive_file.extractfile(member)
                    self.assertIsNotNone(source)
                    target.write_bytes(source.read())

    def test_both_plugin_roots_union_skills_agents_and_trace_doc_token(self) -> None:
        self._create_plugin(
            Path("plugin"), skills=(MAIN_SKILL,), agents=("planner",)
        )
        self._create_plugin(
            Path("experiments/plugin"),
            skills=("cognitive-writing-fixed-order",),
            agents=("reviewer",),
        )
        self._write_readme(
            f"{MAIN_SKILL} /agentic-cognitive-writing:{MAIN_SKILL} ${MAIN_SKILL} "
            "cognitive-writing-fixed-order "
            ".writing/trace/process.jsonl\n"
        )

        result = self._run_checker()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("missing; skipping plugin root", result.stdout)
        self.assertNotIn("unknown skill name", result.stdout)

        checker_globals = runpy.run_path(str(CHECKER))
        ground_truth = checker_globals["_ground_truth"](
            [self.root / "plugin", self.root / "experiments/plugin"]
        )
        self.assertEqual(ground_truth["agents"], {"planner", "reviewer"})
        self.assertEqual(
            ground_truth["trace_doc_tokens"], {".writing/trace/process.jsonl"}
        )

    def test_actual_plugin_tree_at_d0d6da7_is_clean(self) -> None:
        self._materialize_actual_plugin_tree()

        result = self._run_checker()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("unknown skill name", result.stdout)

        checker_globals = runpy.run_path(str(CHECKER))
        ground_truth = checker_globals["_ground_truth"](
            [self.root / "plugin", self.root / "experiments/plugin"]
        )
        self.assertIn("cognitive-writing-experiments", ground_truth["packages"])

    def test_no_plugin_roots_print_notices_and_exit_zero(self) -> None:
        result = self._run_checker()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("plugin/: missing; skipping plugin root", result.stdout)
        self.assertIn("experiments/plugin/: missing; skipping plugin root", result.stdout)
        self.assertIn("no plugin roots found; skipping", result.stdout)

    def test_one_plugin_root_prints_optional_root_notice_and_continues(self) -> None:
        self._create_plugin(Path("plugin"), skills=(MAIN_SKILL,))

        result = self._run_checker()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("experiments/plugin/: missing; skipping plugin root", result.stdout)
        self.assertNotIn("no plugin roots found", result.stdout)

    def test_experiments_only_variant_is_clean(self) -> None:
        self._create_plugin(
            Path("experiments/plugin"),
            skills=("cognitive-writing-fixed-order",),
        )
        self._write_readme("cognitive-writing-fixed-order\n")

        result = self._run_checker()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("plugin/: missing; skipping plugin root", result.stdout)
        self.assertNotIn("unknown skill name", result.stdout)

    def test_variant_is_flagged_when_neither_plugin_root_contains_it(self) -> None:
        self._create_plugin(Path("plugin"), skills=(MAIN_SKILL,))
        self._write_readme("cognitive-writing-fixed-order\n")

        result = self._run_checker()

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "README.md:1: unknown skill name 'cognitive-writing-fixed-order'",
            result.stdout,
        )

    def test_unknown_agentic_cog_writer_skill_is_flagged(self) -> None:
        self._create_plugin(Path("plugin"), skills=(MAIN_SKILL,))
        self._write_readme("agentic-cog-writer-unavailable\n")

        result = self._run_checker()

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "README.md:1: unknown skill name 'agentic-cog-writer-unavailable'",
            result.stdout,
        )

    def test_in_repo_blob_and_tree_branch_urls_are_findings(self) -> None:
        self._create_plugin(Path("plugin"), skills=(MAIN_SKILL,))
        self._add_origin_remote()
        self._write_readme(
            f"blob: https://github.com/{REPOSITORY_SLUG}/blob/main/README.md\n"
            f"tree: https://github.com/{REPOSITORY_SLUG}/tree/main/plugin\n"
        )

        result = self._run_checker()

        findings = [
            line for line in result.stdout.splitlines() if line.startswith("README.md:")
        ]
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(len(findings), 2, result.stdout)
        self.assertEqual(result.stdout.count("use a relative link"), 2)

    def test_in_repo_commit_pinned_url_on_default_branch_is_clean(self) -> None:
        self._create_plugin(Path("plugin"), skills=(MAIN_SKILL,))
        self._write_readme("baseline\n")
        self._initialize_committed_git_fixture()
        baseline_commit = self._commit_fixture("baseline")
        self._write_readme(
            f"Pinned snapshot: https://github.com/{REPOSITORY_SLUG}/blob/"
            f"{baseline_commit}/README.md\n"
        )

        result = self._run_checker()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("commit-pinned in-repo GitHub URL", result.stdout)

    def test_commit_pin_accepted_when_either_default_branch_ref_reaches_it(self) -> None:
        self._create_plugin(Path("plugin"), skills=(MAIN_SKILL,))
        self._write_readme("base\n")
        self._initialize_committed_git_fixture()
        base_commit = self._commit_fixture("base")
        (self.root / "descendant.txt").write_text("descendant\n", encoding="utf-8")
        descendant_commit = self._commit_fixture("descendant")
        self._update_ref("refs/remotes/origin/main", base_commit)
        self._write_readme(
            f"Pinned snapshot: https://github.com/{REPOSITORY_SLUG}/blob/"
            f"{descendant_commit}/README.md\n"
        )

        result = self._run_checker()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("commit-pinned in-repo GitHub URL", result.stdout)

    def test_in_repo_commit_pinned_url_off_default_branch_is_flagged(self) -> None:
        self._create_plugin(Path("plugin"), skills=(MAIN_SKILL,))
        self._write_readme("baseline\n")
        self._initialize_committed_git_fixture()
        self._commit_fixture("baseline")
        self._checkout_new_branch("feature")
        (self.root / "feature.txt").write_text("feature\n", encoding="utf-8")
        feature_commit = self._commit_fixture("feature")
        self._write_readme(
            f"Pinned snapshot: https://github.com/{REPOSITORY_SLUG}/tree/"
            f"{feature_commit}/plugin\n"
        )

        result = self._run_checker()

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "the pin will break after squash-merge, use a relative link",
            result.stdout,
        )

    def test_unknown_in_repo_commit_pin_is_flagged(self) -> None:
        self._create_plugin(Path("plugin"), skills=(MAIN_SKILL,))
        self._add_origin_remote()
        self._write_readme(
            f"Unknown snapshot: https://github.com/{REPOSITORY_SLUG}/blob/"
            "d0d6da7/README.md\n"
        )

        result = self._run_checker()

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "the pin will break after squash-merge, use a relative link",
            result.stdout,
        )

    def test_no_remote_external_links_are_clean_with_notice(self) -> None:
        self._create_plugin(Path("plugin"), skills=(MAIN_SKILL,))
        self._write_readme(
            "External: https://github.com/example/external-project/blob/main/README.md\n"
        )

        result = self._run_checker()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            "in-repo GitHub URL check skipped: repository slug is unknown",
            result.stdout,
        )
        self.assertNotIn("branch-qualified in-repo GitHub URL", result.stdout)

    def test_unknown_commit_pins_are_findings(self) -> None:
        self._create_plugin(Path("plugin"), skills=(MAIN_SKILL,))
        self._add_origin_remote()
        revisions = ("abcdef0", "a" * 40, "ABCDEF0", "ABCDEF123456")
        self._write_readme(
            "\n".join(
                f"https://github.com/{REPOSITORY_SLUG}/blob/{revision}/README.md"
                for revision in revisions
            )
            + "\n"
        )

        result = self._run_checker()

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count("commit-pinned in-repo GitHub URL"), 4)

    def test_standalone_prose_sha_is_flagged(self) -> None:
        self._create_plugin(Path("plugin"), skills=(MAIN_SKILL,))
        self._write_readme("The snapshot at d0d6da7 uses the shipped plugin.\n")

        result = self._run_checker()

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "README.md:1: commit SHA 'd0d6da7' appears in prose",
            result.stdout,
        )

    def test_doi_suffixes_in_bibliography_are_clean(self) -> None:
        self._create_plugin(Path("plugin"), skills=(MAIN_SKILL,))
        self._write_readme(
            "[^1]: DOI: [10.58680/ccc198115885]("
            "https://doi.org/10.58680/ccc198115885) and 10.58680/ccc198115885.\n"
        )

        result = self._run_checker()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("commit SHA", result.stdout)

    def test_dotted_doi_is_clean(self) -> None:
        self._create_plugin(Path("plugin"), skills=(MAIN_SKILL,))
        self._write_readme(
            "Bibliography DOI: 10.1145/3290605.3300233.\n"
        )

        result = self._run_checker()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("commit SHA", result.stdout)

    def test_bare_doi_suffix_without_prefix_is_flagged(self) -> None:
        self._create_plugin(Path("plugin"), skills=(MAIN_SKILL,))
        self._write_readme("The snapshot at ccc198115885 is documented.\n")

        result = self._run_checker()

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "README.md:1: commit SHA 'ccc198115885' appears in prose",
            result.stdout,
        )

    def test_hyphenated_doi_like_suffix_is_flagged(self) -> None:
        self._create_plugin(Path("plugin"), skills=(MAIN_SKILL,))
        self._write_readme(
            "The snapshot at 10.1234/d0d6da7-not-a-doi is documented.\n"
        )

        result = self._run_checker()

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "README.md:1: commit SHA 'd0d6da7' appears in prose",
            result.stdout,
        )

    def test_sha_inside_pinned_markdown_link_url_is_clean(self) -> None:
        self._create_plugin(Path("plugin"), skills=(MAIN_SKILL,))
        self._write_readme(
            "Pinned [snapshot](https://github.com/example/project/blob/"
            "d0d6da7/README.md) is documented.\n"
        )

        result = self._run_checker()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("commit SHA", result.stdout)

    def test_code_spans_and_fenced_code_are_clean(self) -> None:
        self._create_plugin(Path("plugin"), skills=(MAIN_SKILL,))
        self._write_readme(
            "Use `deadbeef` and `d0d6da7` as fixture values.\n"
            "```text\n"
            "The fenced example uses d0d6da7.\n"
            "```\n"
        )

        result = self._run_checker()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("commit SHA", result.stdout)

    def test_short_hex_fragments_are_ignored(self) -> None:
        self._create_plugin(Path("plugin"), skills=(MAIN_SKILL,))
        self._write_readme("Short fragments abcdef and 123456 are ignored.\n")

        result = self._run_checker()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("commit SHA", result.stdout)


if __name__ == "__main__":
    unittest.main()
