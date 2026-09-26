import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.smoke_test_codex_marketplace import SmokeError, _catalog, smoke

FAKE_CODEX = """#!{python}
import json, os, sys
with open(os.environ["FAKE_CODEX_LOG"], "a") as log:
    log.write(os.environ.get("CODEX_HOME", "") + "\\n")
arguments = sys.argv[1:]
if arguments[:2] == ["plugin", "list"]:
    print(json.dumps({{"available": [{{"name": "example"}}]}}))
elif arguments[:2] == ["debug", "prompt-input"]:
    # The user message names the plugin, as AGENTS.md or typed input can; only the
    # developer-role skill listing counts as discovery.
    prompt = [
        {{"role": "developer", "content": [{{"type": "input_text", "text": "no plugins"}}]}},
        {{"role": "user", "content": [{{"type": "input_text", "text": "Use $example:codex-run"}}]}},
    ]
    print(json.dumps(prompt))
elif arguments == ["app-server"]:
    listed = os.environ.get("FAKE_CODEX_SKILLS", "")
    for line in sys.stdin:
        request = json.loads(line)
        if "id" not in request:
            continue
        result = {{}}
        if request["method"] == "skills/list":
            skills = [{{"name": name, "enabled": True}} for name in listed.split(",") if name]
            result = {{"data": [{{"skills": skills, "errors": []}}]}}
        print(json.dumps({{"id": request["id"], "result": result}}), flush=True)
else:
    print("{{}}")
"""


class CodexSmokeCatalogTests(unittest.TestCase):
    def test_explicit_skill_comes_from_manifest_codex_only_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / "plugins" / "example"
            skill = plugin / ".codex" / "skills" / "codex-run"
            (root / ".agents" / "plugins").mkdir(parents=True)
            (plugin / ".codex-plugin").mkdir(parents=True)
            skill.mkdir(parents=True)
            (root / ".agents" / "plugins" / "marketplace.json").write_text(
                json.dumps(
                    {
                        "name": "example-marketplace",
                        "plugins": [
                            {
                                "name": "example",
                                "source": {
                                    "source": "local",
                                    "path": "./plugins/example",
                                },
                            }
                        ],
                    }
                )
                + "\n"
            )
            (plugin / ".codex-plugin" / "plugin.json").write_text(
                json.dumps(
                    {
                        "name": "example",
                        "version": "1.0.0",
                        "description": "Run the example workflow.",
                        "skills": "./.codex/skills/",
                    }
                )
                + "\n"
            )
            (skill / "SKILL.md").write_text(
                "---\nname: codex-run\ndescription: Run it.\n---\n"
            )

            marketplace, plugins = _catalog(root)

        self.assertEqual(marketplace, "example-marketplace")
        self.assertEqual(plugins, [("example", "codex-run")])

    def test_explicit_mention_in_the_user_message_does_not_count_as_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._fixture(root)
            codex = root / "codex"
            codex.write_text(FAKE_CODEX.format(python=sys.executable))
            codex.chmod(0o755)
            log = root / "codex-home.log"
            real_home = root / "real-codex-home"

            environment = {
                "FAKE_CODEX_LOG": str(log),
                "CODEX_HOME": str(real_home),
                "FAKE_CODEX_SKILLS": "other:codex-run",
            }
            with patch.dict(os.environ, environment):
                with self.assertRaisesRegex(SmokeError, "was not loaded"):
                    smoke(root, codex, batch_size=8)
            with patch.dict(os.environ, {**environment, "FAKE_CODEX_SKILLS": "example:codex-run"}):
                self.assertEqual(smoke(root, codex, batch_size=8), 1)

            homes = set(log.read_text().splitlines())
        self.assertEqual(len(homes), 2, "each smoke run uses its own temporary CODEX_HOME")
        self.assertNotIn(str(real_home), homes)
        self.assertNotIn("", homes)
        self.assertFalse(any(Path(home).exists() for home in homes))

    def _fixture(self, root: Path) -> None:
        plugin = root / "plugins" / "example"
        skill = plugin / ".codex" / "skills" / "codex-run"
        (root / ".agents" / "plugins").mkdir(parents=True)
        (plugin / ".codex-plugin").mkdir(parents=True)
        skill.mkdir(parents=True)
        (root / ".agents" / "plugins" / "marketplace.json").write_text(
            json.dumps(
                {
                    "name": "example-marketplace",
                    "plugins": [
                        {
                            "name": "example",
                            "source": {"source": "local", "path": "./plugins/example"},
                        }
                    ],
                }
            )
        )
        (plugin / ".codex-plugin" / "plugin.json").write_text(
            json.dumps({"name": "example", "skills": "./.codex/skills/"})
        )
        (skill / "SKILL.md").write_text("---\nname: codex-run\ndescription: Run it.\n---\n")


if __name__ == "__main__":
    unittest.main()
