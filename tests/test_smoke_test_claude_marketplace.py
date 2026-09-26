import json
import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.smoke_test_claude_marketplace import SmokeError, _plugin_names, _run, smoke


class ClaudeSmokeRunnerTests(unittest.TestCase):
    @patch("scripts.smoke_test_claude_marketplace.subprocess.run")
    def test_runner_forces_public_github_clones_over_https(self, run: Mock) -> None:
        run.return_value = CompletedProcess([], 0, stdout="ok", stderr="")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _run(Path("claude"), ["plugin", "list"], cwd=root, config=root / "config")

        environment = run.call_args.kwargs["env"]
        self.assertEqual(environment["GIT_CONFIG_COUNT"], "2")
        self.assertEqual(environment["GIT_CONFIG_KEY_0"], "url.https://github.com/.insteadOf")
        self.assertEqual(environment["GIT_CONFIG_VALUE_0"], "git@github.com:")
        self.assertEqual(environment["GIT_CONFIG_KEY_1"], "url.https://github.com/.insteadOf")
        self.assertEqual(environment["GIT_CONFIG_VALUE_1"], "ssh://git@github.com/")


class ClaudeSmokeCatalogTests(unittest.TestCase):
    def test_catalog_lists_local_and_external_plugins_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / ".claude-plugin" / "marketplace.json"
            catalog.parent.mkdir(parents=True)
            catalog.write_text(
                json.dumps(
                    {
                        "name": "powerful-plugins",
                        "plugins": [
                            {"name": "local", "source": "./plugins/local"},
                            {
                                "name": "external",
                                "source": {
                                    "source": "github",
                                    "repo": "owner/repository",
                                    "sha": "0123456789abcdef0123456789abcdef01234567",
                                },
                            },
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            names = _plugin_names(root)

        self.assertEqual(names, ["local", "external"])

    def test_catalog_rejects_a_ref_in_place_of_a_sha(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / ".claude-plugin" / "marketplace.json"
            catalog.parent.mkdir(parents=True)
            catalog.write_text(
                json.dumps(
                    {
                        "name": "powerful-plugins",
                        "plugins": [
                            {
                                "name": "external",
                                "source": {
                                    "source": "github",
                                    "repo": "owner/repository",
                                    "ref": "0123456789abcdef0123456789abcdef01234567",
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(SmokeError, "pin a commit with sha, not ref"):
                _plugin_names(root)

    def test_catalog_rejects_a_github_source_with_a_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / ".claude-plugin" / "marketplace.json"
            catalog.parent.mkdir(parents=True)
            catalog.write_text(
                json.dumps(
                    {
                        "name": "powerful-plugins",
                        "plugins": [
                            {
                                "name": "external",
                                "source": {
                                    "source": "github",
                                    "repo": "owner/repository",
                                    "path": "plugins/external",
                                    "sha": "0123456789abcdef0123456789abcdef01234567",
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(SmokeError, "^external: .*use git-subdir"):
                _plugin_names(root)

    def test_catalog_rejects_a_marketplace_identity_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / ".claude-plugin" / "marketplace.json"
            catalog.parent.mkdir(parents=True)
            catalog.write_text(
                json.dumps({"name": "renamed-marketplace", "plugins": []}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(SmokeError, "marketplace identity changed"):
                _plugin_names(root)



class ClaudeSmokeInventoryTests(unittest.TestCase):
    def _smoke_with_details(self, details: str) -> int:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / ".claude-plugin" / "marketplace.json"
            catalog.parent.mkdir(parents=True)
            catalog.write_text(
                json.dumps(
                    {
                        "name": "powerful-plugins",
                        "plugins": [{"name": "local", "source": "./plugins/local"}],
                    }
                ),
                encoding="utf-8",
            )

            def fake_run(_claude: Path, arguments: list[str], **_: object) -> str:
                if arguments[:2] == ["plugin", "list"]:
                    return json.dumps([{"id": "local@powerful-plugins", "enabled": True}])
                if arguments[:2] == ["plugin", "details"]:
                    return details
                return ""

            with patch("scripts.smoke_test_claude_marketplace._run", side_effect=fake_run):
                return smoke(root, Path("claude"))

    def test_an_install_that_loads_nothing_fails(self) -> None:
        empty = (
            "Source: local@powerful-plugins\n\nComponent inventory\n"
            "  Skills (0)\n  Agents (0)\n  Hooks (0)\n  MCP servers (0)\n  LSP servers (0)\n"
        )
        with self.assertRaisesRegex(SmokeError, "exposes no skills, agents or hooks"):
            self._smoke_with_details(empty)

    def test_an_install_with_a_skill_passes(self) -> None:
        installed = self._smoke_with_details(
            "Source: local@powerful-plugins\n\nComponent inventory\n"
            "  Skills (1)  review\n  Agents (0)\n"
        )

        self.assertEqual(installed, 1)


if __name__ == "__main__":
    unittest.main()
