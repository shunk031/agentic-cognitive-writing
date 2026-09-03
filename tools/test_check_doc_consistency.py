"""Run with: python3 -m pytest tools/test_check_doc_consistency.py -q"""

from __future__ import annotations

import io
import json
import runpy
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

CHECKER = Path(__file__).resolve().with_name("check-doc-consistency.sh")
REPOSITORY_SLUG = "shunk031/agentic-cognitive-writing"
MAIN_SKILL = "agentic-cog-writer"


class CheckDocConsistencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = TemporaryDirectory()
        self.root = Path(self._temporary_directory.name)

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    def _create_plugin(
        self,
        relative_root: Path = Path("plugin"),
        *,
        skills: tuple[str, ...] = (),
        package_name: str | None = None,
    ) -> None:
        plugin_root = self.root / relative_root
        skills_root = plugin_root / "skills"
        skills_root.mkdir(parents=True)
        for skill in skills:
            (skills_root / skill).mkdir()
        if package_name is not None:
            manifest = plugin_root / ".claude-plugin" / "plugin.json"
            manifest.parent.mkdir()
            manifest.write_text(
                json.dumps({"name": package_name}) + "\n", encoding="utf-8"
            )

    def _write_readme(self, text: str) -> None:
        (self.root / "README.md").write_text(text, encoding="utf-8")

    def _run_checker(self) -> tuple[int, str]:
        checker_globals = runpy.run_path(str(CHECKER))
        output = io.StringIO()
        with redirect_stdout(output):
            returncode = checker_globals["main"](
                ["--repo-root", str(self.root)]
            )
        return returncode, output.getvalue()

    def test_stale_identifier_is_case_insensitive(self) -> None:
        self._create_plugin(skills=(MAIN_SKILL,))
        self._write_readme("REVISION-EVALUATOR\n")

        returncode, output = self._run_checker()

        self.assertEqual(returncode, 1, output)
        self.assertIn("stale identifier 'revision-evaluator'", output)

    def test_known_skill_and_package_names_are_clean(self) -> None:
        self._create_plugin(
            skills=(MAIN_SKILL,),
            package_name="cognitive-writing-experiments",
        )
        self._write_readme(
            f"{MAIN_SKILL}\n"
            "cognitive-writing-experiments\n"
        )

        returncode, output = self._run_checker()

        self.assertEqual(returncode, 0, output)
        self.assertNotIn("unknown skill name", output)

    def test_unknown_skill_token_is_flagged(self) -> None:
        self._create_plugin(skills=(MAIN_SKILL,))
        self._write_readme("cognitive-writing-unknown\n")

        returncode, output = self._run_checker()

        self.assertEqual(returncode, 1, output)
        self.assertIn(
            "unknown skill name 'cognitive-writing-unknown'",
            output,
        )

    def test_no_plugin_roots_print_notice_and_exit_zero(self) -> None:
        returncode, output = self._run_checker()

        self.assertEqual(returncode, 0, output)
        self.assertIn("plugin/: missing; skipping plugin root", output)
        self.assertIn("experiments/plugin/: missing; skipping plugin root", output)
        self.assertIn("no plugin roots found; skipping", output)

    def test_in_repository_blob_and_tree_urls_are_findings(self) -> None:
        self._create_plugin(skills=(MAIN_SKILL,))
        self._write_readme(
            f"blob: https://github.com/{REPOSITORY_SLUG}/blob/main/README.md\n"
            f"tree: https://github.com/{REPOSITORY_SLUG}/tree/main/plugin\n"
        )

        returncode, output = self._run_checker()

        self.assertEqual(returncode, 1, output)
        self.assertEqual(output.count("use a repository-relative link"), 2)

    def test_external_pinned_url_is_clean(self) -> None:
        self._create_plugin(skills=(MAIN_SKILL,))
        self._write_readme(
            "https://github.com/stanford-oval/storm/blob/"
            "0123456789abcdef0123456789abcdef01234567/README.md\n"
        )

        returncode, output = self._run_checker()

        self.assertEqual(returncode, 0, output)
        self.assertNotIn("in-repository GitHub URL", output)

    def test_relative_link_is_clean(self) -> None:
        self._create_plugin(skills=(MAIN_SKILL,))
        self._write_readme("See [the plugin](./plugin/) for details.\n")

        returncode, output = self._run_checker()

        self.assertEqual(returncode, 0, output)


if __name__ == "__main__":
    unittest.main()
