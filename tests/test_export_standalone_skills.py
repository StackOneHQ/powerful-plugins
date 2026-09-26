import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "export-standalone-skills.sh"


class StandaloneExporterSecurityTests(unittest.TestCase):
    def _run(self, root: Path, destination: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "bash",
                str(SCRIPT),
                "--root",
                str(root),
                "--dest",
                str(destination),
                *arguments,
            ],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHON": sys.executable},
        )

    def _skill(
        self, root: Path, directory: str, name: str, body: str = "Run it.\n"
    ) -> Path:
        path = root / "plugins" / "example" / "skills" / directory / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"---\nname: {name}\ndescription: Export {name}.\ninvoke: {name}\n---\n\n{body}"
        )
        return path

    def test_wrapper_reports_missing_yaml_dependency_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fake_python = Path(directory) / "python-without-yaml"
            fake_python.write_text("#!/usr/bin/env bash\nexit 1\n")
            fake_python.chmod(0o755)

            completed = subprocess.run(
                ["bash", str(SCRIPT), "--list"],
                cwd=SCRIPT.parents[1],
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHON": str(fake_python)},
            )

            self.assertEqual(completed.returncode, 2)
            self.assertIn("pip install -r requirements.txt", completed.stderr)
            self.assertNotIn("Traceback", completed.stderr)

    def test_invalid_skill_name_cannot_escape_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            destination = Path(directory) / "exported"
            self._skill(root, "escaped", "../escaped")
            victim = Path(directory) / "escaped"

            completed = self._run(root, destination, "../escaped")

            self.assertEqual(completed.returncode, 2)
            self.assertFalse(victim.exists())
            self.assertFalse(destination.exists())

    def test_malformed_skill_fails_without_partial_exports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            destination = Path(directory) / "exported"
            self._skill(root, "valid", "valid")
            malformed = root / "plugins" / "example" / "skills" / "malformed" / "SKILL.md"
            malformed.parent.mkdir(parents=True)
            malformed.write_text("---\ndescription: Missing a name.\n---\n")

            completed = self._run(root, destination, "valid")

            self.assertEqual(completed.returncode, 2)
            self.assertFalse(destination.exists())

    def test_duplicate_names_are_rejected_before_missing_name_accounting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            destination = Path(directory) / "exported"
            self._skill(root, "first", "duplicate")
            other = root / "plugins" / "other" / "skills" / "duplicate" / "SKILL.md"
            other.parent.mkdir(parents=True)
            other.write_text(
                "---\nname: duplicate\ndescription: Another duplicate.\n---\n"
            )

            completed = self._run(root, destination, "duplicate", "missing")

            self.assertEqual(completed.returncode, 2)
            self.assertIn("duplicate", completed.stderr)
            self.assertFalse(destination.exists())

    def test_destination_symlink_is_not_followed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            destination = Path(directory) / "exported"
            outside = Path(directory) / "outside"
            outside.mkdir()
            destination.mkdir()
            self._skill(root, "safe", "safe")
            os.symlink(outside, destination / "safe")

            completed = self._run(root, destination, "--force", "safe")

            self.assertEqual(completed.returncode, 2)
            self.assertEqual(list(outside.iterdir()), [])

    def test_force_replaces_directory_without_leaving_stale_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            destination = Path(directory) / "exported"
            self._skill(root, "safe", "safe")
            old = destination / "safe"
            old.mkdir(parents=True)
            (old / "stale.txt").write_text("stale\n")

            completed = self._run(root, destination, "--force", "safe")

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertFalse((old / "stale.txt").exists())
            self.assertTrue((old / "SKILL.md").is_file())

    def test_plugin_dependent_skill_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            destination = Path(directory) / "exported"
            self._skill(root, "dependent", "dependent", "Run ${CLAUDE_PLUGIN_ROOT}/tool.sh.\n")

            completed = self._run(root, destination, "dependent")

            self.assertEqual(completed.returncode, 2)
            self.assertIn("cannot be exported standalone", completed.stderr)
            self.assertFalse(destination.exists())

    def test_bare_plugin_relative_script_reference_is_not_standalone(self) -> None:
        for reference in ("scripts/report.py", "./scripts/report.py", "src/report.py"):
            with self.subTest(reference=reference), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "repo"
                destination = Path(directory) / "exported"
                folder = reference.removeprefix("./").split("/")[0]
                body = f"Run `python3 {reference}`.\n"
                self._skill(root, "dependent", "dependent", body)
                bundled = self._skill(root, "bundled", "bundled", body)
                (bundled.parent / folder).mkdir()
                (bundled.parent / folder / "report.py").write_text("print('ok')\n")

                rejected = self._run(root, destination, "dependent")
                self.assertFalse(destination.exists())
                accepted = self._run(root, destination, "bundled")

                self.assertEqual(rejected.returncode, 2)
                self.assertIn("cannot be exported standalone", rejected.stderr)
                self.assertIn(f"{folder}/ reference", rejected.stderr)
                self.assertEqual(accepted.returncode, 0, accepted.stderr)
                self.assertTrue((destination / "bundled" / folder / "report.py").is_file())

    def test_paths_that_are_not_plugin_relative_are_allowed(self) -> None:
        body = (
            "See https://example.com/scripts/report.py, docs/src/x.py, $HOME/scripts/x,\n"
            "and the `@src/components` package.\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            destination = Path(directory) / "exported"
            self._skill(root, "safe", "safe", body)

            completed = self._run(root, destination, "safe")

            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_only_frontmatter_invoke_key_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            destination = Path(directory) / "exported"
            self._skill(root, "safe", "safe", "Keep this line:\ninvoke: body value\n")

            completed = self._run(root, destination, "safe")
            exported = (destination / "safe" / "SKILL.md").read_text()

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(exported.count("invoke:"), 1)
            self.assertIn("invoke: body value", exported)

    def test_claude_metadata_is_normalized_in_standalone_copy_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            destination = Path(directory) / "exported"
            source = self._skill(root, "legacy-folder", "portable-workflow")
            source.write_text(
                "---\n"
                "name: portable-workflow\n"
                f"description: {'Detailed Claude trigger. ' * 80}\n"
                "invocable: true\n"
                "invocable: true\n"
                "---\n\n"
                "Run it.\n"
            )

            completed = self._run(root, destination, "portable-workflow")
            exported = destination / "portable-workflow" / "SKILL.md"
            frontmatter = exported.read_text().split("---", 2)[1]
            metadata = yaml.safe_load(frontmatter)

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(metadata["name"], "portable-workflow")
            self.assertLessEqual(len(metadata["description"]), 1024)
            self.assertNotIn("invocable", metadata)
            self.assertIn("Run it.", exported.read_text())

    def test_no_selection_requires_explicit_all(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            destination = Path(directory) / "exported"
            self._skill(root, "safe", "safe")

            completed = self._run(root, destination)

            self.assertEqual(completed.returncode, 2)
            self.assertIn("--all", completed.stderr)
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
