import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.validate_external_sources import GenerationError, _external_plugins

SHA = "a" * 40


def _write_catalog(root: Path, source: dict[str, object]) -> None:
    (root / ".claude-plugin").mkdir()
    (root / ".agents" / "plugins").mkdir(parents=True)
    (root / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps({"plugins": [{"name": "external", "source": source}]}) + "\n"
    )
    (root / ".agents" / "plugins" / "source-overrides.json").write_text(
        json.dumps({"version": 2, "plugins": {}}) + "\n"
    )


class ExternalSourceValidatorTests(unittest.TestCase):
    def test_git_subdir_source_supplies_repository_path_and_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_catalog(
                root,
                {
                    "source": "git-subdir",
                    "url": "example/repository",
                    "path": "plugins/external",
                    "sha": SHA,
                },
            )

            plugins = _external_plugins(root)

        self.assertEqual(plugins[0].repo, "example/repository")
        self.assertEqual(plugins[0].sha, SHA)
        self.assertEqual(plugins[0].source_path, "plugins/external")

    def test_github_source_with_path_fails_with_the_fix(self) -> None:
        # Claude Code ignores path on github and installs the repository root instead.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_catalog(
                root,
                {
                    "source": "github",
                    "repo": "example/repository",
                    "path": "plugins/external",
                    "sha": SHA,
                },
            )

            with self.assertRaisesRegex(
                GenerationError, r"^external: .*use git-subdir with url, path and sha"
            ):
                _external_plugins(root)

    def test_unpinned_source_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_catalog(root, {"source": "github", "repo": "example/repository"})

            with self.assertRaisesRegex(GenerationError, "sha"):
                _external_plugins(root)


if __name__ == "__main__":
    unittest.main()
