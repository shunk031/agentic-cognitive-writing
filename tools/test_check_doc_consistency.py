#!/usr/bin/env python3
"""Run with: uv run tools/test_check_doc_consistency.py"""

from __future__ import annotations

import io
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
        subprocess.run(
            ["git", "init", "--quiet", str(self.root)],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "config",
                "remote.origin.url",
                f"https://github.com/{REPOSITORY_SLUG}.git",
            ],
            check=True,
        )

    def _run_checker(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CHECKER), "--repo-root", str(self.root)],
            check=False,
            capture_output=True,
            text=True,
        )

    def _materialize_actual_plugin_tree(self) -> None:
        ref = f"{ACTUAL_PLUGIN_COMMIT}^{{commit}}"
        object_check = subprocess.run(
            ["git", "-C", str(REPOSITORY_ROOT), "cat-file", "-e", ref],
            check=False,
            capture_output=True,
            text=True,
        )
        if object_check.returncode != 0:
            fetch = subprocess.run(
                [
                    "git",
                    "-C",
                    str(REPOSITORY_ROOT),
                    "fetch",
                    "origin",
                    "feat/cognitive-writing-plugin",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                fetch.returncode,
                0,
                fetch.stdout + fetch.stderr,
            )

        archive = subprocess.run(
            [
                "git",
                "-C",
                str(REPOSITORY_ROOT),
                "archive",
                "--format=tar",
                ACTUAL_PLUGIN_COMMIT,
                "README.md",
                "plugin",
                "experiments/plugin",
            ],
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

    def test_both_plugin_roots_union_skills_agents_and_trace_path(self) -> None:
        self._create_plugin(
            Path("plugin"), skills=("cognitive-writing",), agents=("planner",)
        )
        self._create_plugin(
            Path("experiments/plugin"),
            skills=("cognitive-writing-fixed-order",),
            agents=("reviewer",),
        )
        self._write_readme(
            "cognitive-writing cognitive-writing-fixed-order "
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
        self.assertEqual(ground_truth["trace_paths"], {".writing/trace/process.jsonl"})

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
        self._create_plugin(Path("plugin"), skills=("cognitive-writing",))

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
        self._create_plugin(Path("plugin"), skills=("cognitive-writing",))
        self._write_readme("cognitive-writing-fixed-order\n")

        result = self._run_checker()

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "README.md:1: unknown skill name 'cognitive-writing-fixed-order'",
            result.stdout,
        )

    def test_in_repo_blob_and_tree_branch_urls_are_findings(self) -> None:
        self._create_plugin(Path("plugin"), skills=("cognitive-writing",))
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
        self.assertEqual(result.stdout.count("branch-qualified in-repo GitHub URL"), 2)

    def test_no_remote_external_links_are_clean_with_notice(self) -> None:
        self._create_plugin(Path("plugin"), skills=("cognitive-writing",))
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

    def test_seven_to_forty_hex_revisions_are_excluded(self) -> None:
        self._create_plugin(Path("plugin"), skills=("cognitive-writing",))
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

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("branch-qualified in-repo GitHub URL", result.stdout)


if __name__ == "__main__":
    unittest.main()
