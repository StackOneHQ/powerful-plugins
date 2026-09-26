from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_plugin_versions.py"


class PluginVersionCheckTests(unittest.TestCase):
    def test_plugin_moved_between_categories_with_edits_needs_a_bump(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_plugin(root, "design", "1.0.0", "Original workflow.\n")
            self._git(root, "init", "--quiet")
            self._git(root, "config", "user.email", "tests@example.com")
            self._git(root, "config", "user.name", "Tests")
            self._git(root, "add", ".")
            self._git(root, "commit", "--quiet", "-m", "initial")
            base = self._git(root, "rev-parse", "HEAD").stdout.strip()

            self._git(root, "mv", "plugins/design", "plugins/engineering")
            self._write_plugin(root, "engineering", "1.0.0", "Changed workflow.\n")
            self._git(root, "add", "-A")
            self._git(root, "commit", "--quiet", "-m", "move and edit")
            unbumped = self._check(root, base)

            self._write_plugin(root, "engineering", "1.0.1", "Changed workflow.\n")
            self._git(root, "add", "-A")
            self._git(root, "commit", "--quiet", "-m", "bump")
            bumped = self._check(root, base)

        self.assertEqual(unbumped.returncode, 1, unbumped.stdout + unbumped.stderr)
        self.assertIn("plugins/engineering/example", unbumped.stdout)
        self.assertEqual(bumped.returncode, 0, bumped.stdout + bumped.stderr)

    def test_non_object_manifest_is_skipped_without_a_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_plugin(root, "design", "1.0.0", "Original workflow.\n")
            self._git(root, "init", "--quiet")
            self._git(root, "config", "user.email", "tests@example.com")
            self._git(root, "config", "user.name", "Tests")
            self._git(root, "add", ".")
            self._git(root, "commit", "--quiet", "-m", "initial")
            base = self._git(root, "rev-parse", "HEAD").stdout.strip()
            manifest = root / "plugins" / "design" / "example" / ".claude-plugin" / "plugin.json"
            manifest.write_text("[]\n")
            self._git(root, "commit", "--quiet", "-am", "break the manifest")

            completed = self._check(root, base)

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def _write_plugin(self, root: Path, category: str, version: str, body: str) -> None:
        plugin = root / "plugins" / category / "example"
        (plugin / ".claude-plugin").mkdir(parents=True, exist_ok=True)
        (plugin / "skills" / "example").mkdir(parents=True, exist_ok=True)
        (plugin / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "example", "version": version}) + "\n"
        )
        (plugin / "skills" / "example" / "SKILL.md").write_text(body)
        (root / ".claude-plugin").mkdir(exist_ok=True)
        (root / ".claude-plugin" / "marketplace.json").write_text(
            json.dumps(
                {
                    "name": "example-marketplace",
                    "plugins": [
                        {
                            "name": "example",
                            "source": f"./plugins/{category}/example",
                            "version": version,
                        }
                    ],
                }
            )
            + "\n"
        )

    def _check(self, root: Path, base: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--base", base],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )

    def _git(self, root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *arguments], cwd=root, check=True, capture_output=True, text=True
        )


if __name__ == "__main__":
    unittest.main()
