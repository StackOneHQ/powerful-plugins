import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.validate_codex_plugins import GenerationError, _validate_plugin, _validate_skill


class CodexPluginValidatorTests(unittest.TestCase):
    def test_codex_only_skill_root_does_not_validate_claude_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / "plugins" / "example"
            proxy = plugin / ".codex" / "skills" / "portable-workflow"
            source = plugin / "skills" / "legacy-folder"
            (plugin / ".codex-plugin").mkdir(parents=True)
            proxy.mkdir(parents=True)
            source.mkdir(parents=True)
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
            (proxy / "SKILL.md").write_text(
                "---\n"
                "name: portable-workflow\n"
                "description: Run the portable workflow.\n"
                "---\n\n"
                "Read the Claude source.\n"
            )
            (source / "SKILL.md").write_text(
                "---\n"
                "name: portable-workflow\n"
                f"description: {'Detailed Claude trigger. ' * 80}\n"
                "---\n"
            )

            _validate_plugin(plugin, "example")

    def test_non_mapping_policy_is_a_validation_error_not_a_crash(self) -> None:
        for policy in ("", " []", " allow"):
            with self.subTest(policy=policy), tempfile.TemporaryDirectory() as directory:
                skill = Path(directory) / "workflow"
                (skill / "agents").mkdir(parents=True)
                (skill / "SKILL.md").write_text(
                    "---\nname: workflow\ndescription: Run the workflow.\n---\n"
                )
                (skill / "agents" / "openai.yaml").write_text(
                    f"interface:\n  display_name: Workflow\npolicy:{policy}\n"
                )

                with self.assertRaisesRegex(GenerationError, "policy must be a mapping"):
                    _validate_skill(skill / "SKILL.md")


if __name__ == "__main__":
    unittest.main()
