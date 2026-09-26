import json
import re
import subprocess
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE = "powerful-plugins"
REPOSITORY = "StackOneHQ/powerful-plugins"


def _catalog() -> dict[str, object]:
    value = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    assert isinstance(value, dict)
    return value


def _component_names() -> set[str]:
    """Every plugin name in the catalog, plus the skills, commands and agents local and imported plugins declare."""
    names: set[str] = set()
    for entry in _catalog()["plugins"]:
        names.add(entry["name"])
        if not isinstance(entry["source"], str):
            continue  # an imported plugin: its components are read from source-overrides.json below
        plugin = ROOT / entry["source"]
        names.update(path.parent.name for path in plugin.glob("skills/*/SKILL.md"))
        names.update(path.parent.name for path in plugin.glob(".codex/skills/*/SKILL.md"))
        names.update(path.stem for path in plugin.glob("commands/*.md"))
        names.update(path.stem for path in plugin.glob("agents/*.md"))
    overrides = json.loads((ROOT / ".agents" / "plugins" / "source-overrides.json").read_text())
    for override in overrides["plugins"].values():
        for entrypoint in override.get("entrypoints", []):
            path = Path(entrypoint)
            names.add(path.parent.name if path.name == "SKILL.md" else path.stem)
    return names


class RepositoryGuidanceTests(unittest.TestCase):
    def test_readme_explains_marketplace_lifecycle(self) -> None:
        readme = (ROOT / "README.md").read_text()

        self.assertIn("## How the Marketplace Works", readme)
        self.assertEqual(readme.count("sequenceDiagram"), 2)
        self.assertIn("Installation never runs the repository generator", readme)
        self.assertIn("python3 scripts/generate_codex_marketplace.py", readme)
        self.assertIn("python3 scripts/generate_codex_marketplace.py --check", readme)
        self.assertIn("Sync Codex Plugins commits regenerated files to same-repo PRs", readme)
        self.assertIn("Every pull request targeting `main`", readme)
        self.assertIn("After merge, the `main` push", readme)

    def test_readme_documents_install_for_both_runtimes(self) -> None:
        readme = (ROOT / "README.md").read_text()

        self.assertIn(f"/plugin marketplace add {REPOSITORY}", readme)
        self.assertIn(f"/plugin install <plugin-name>@{MARKETPLACE}", readme)
        self.assertIn(f"codex plugin marketplace add {REPOSITORY}", readme)
        self.assertIn(f"codex plugin add <plugin-name>@{MARKETPLACE}", readme)

    def test_readme_lists_every_catalog_plugin_and_a_live_count_command(self) -> None:
        readme = (ROOT / "README.md").read_text()
        plugins = _catalog()["plugins"]
        assert isinstance(plugins, list)

        for entry in plugins:
            with self.subTest(plugin=entry["name"]):
                self.assertIn(f"| `{entry['name']}` |", readme)
        self.assertNotRegex(readme, r"\b\d+ plugins\b")
        self.assertIn("jq '[.plugins[]", readme)

    def test_catalog_identity_matches_the_public_repository(self) -> None:
        catalog = _catalog()

        self.assertEqual(catalog["name"], MARKETPLACE)
        self.assertEqual(
            catalog["owner"],
            {"name": "StackOne", "url": "https://github.com/StackOneHQ"},
        )
        codex = json.loads((ROOT / ".agents" / "plugins" / "marketplace.json").read_text())
        self.assertEqual(codex["name"], MARKETPLACE)

    def test_catalog_plugin_names_carry_no_owner_or_company_prefix(self) -> None:
        plugins = _catalog()["plugins"]
        assert isinstance(plugins, list)

        for entry in plugins:
            with self.subTest(plugin=entry["name"]):
                self.assertRegex(entry["name"], r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
                self.assertFalse(entry["name"].startswith(("gleb-", "stackone-")))
                if isinstance(entry["source"], str):
                    self.assertTrue(entry["source"].endswith(f"/{entry['name']}"))


    def test_docs_name_only_skills_this_marketplace_ships(self) -> None:
        # Credits and the survey of other tools name outside skills on purpose.
        allowed = {
            ROOT / "plugins/documentation/natural-writing/skills/natural-writing/SKILL.md": {"unslop"},
        }
        names = _component_names()
        reference = re.compile(r"`/?([a-z][a-z0-9]*(?:-[a-z0-9]+)*)`\s+(?:skill|plugin|agent)s?\b")
        unknown = []
        tracked = subprocess.run(["git", "ls-files", "*.md"], cwd=ROOT, capture_output=True, text=True, check=True)
        for path in sorted(ROOT / name for name in tracked.stdout.splitlines()):
            if "templates" in path.parts:
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for match in reference.finditer(line):
                    name = match.group(1)
                    if name not in names and name not in allowed.get(path, set()):
                        unknown.append(f"{path.relative_to(ROOT)}:{number}: {name}")
        self.assertEqual(unknown, [])

    def test_license_names_the_owner(self) -> None:
        license_text = (ROOT / "LICENSE").read_text()

        self.assertTrue(license_text.startswith("MIT License\n"))
        self.assertIn("Copyright (c) 2026 StackOne", license_text)

    def test_external_adapter_guidance_uses_a_compact_compatibility_mapping(self) -> None:
        guidance = "\n".join(
            path.read_text()
            for path in (ROOT / "CLAUDE.md", ROOT / "docs" / "creating-plugins.md")
        )

        self.assertIn("compatibility mapping", guidance)
        self.assertIn('"source": "runtime-adapter"', guidance)
        self.assertIn('"entrypoints": ["SKILL.md"]', guidance)
        self.assertIn('"source": "git-subdir"', guidance)
        self.assertNotIn("source-locks.json", guidance)
        self.assertIn("Claude Code", guidance)
        self.assertNotIn("add its exact repo, ref, and real entrypoints", guidance)

    def test_runtime_adapter_requirements_are_documented_for_users(self) -> None:
        user_guidance = " ".join(
            " ".join(path.read_text().split())
            for path in (ROOT / "README.md", ROOT / "docs" / "getting-started.md")
        )

        self.assertIn("Python 3, Git, and HTTPS access to `github.com`", user_guidance)
        self.assertIn("first invocation", user_guidance)

    def test_agents_md_is_a_relative_symlink_to_claude_md(self) -> None:
        agents_md = ROOT / "AGENTS.md"

        self.assertTrue(agents_md.is_symlink())
        self.assertEqual(agents_md.readlink(), Path("CLAUDE.md"))

    def test_shared_guidance_defines_one_source_registry(self) -> None:
        guidance = " ".join((ROOT / "CLAUDE.md").read_text().split())

        self.assertIn(
            "Edit only `.claude-plugin/marketplace.json` when registering a plugin",
            guidance,
        )
        self.assertIn("python3 scripts/generate_codex_marketplace.py", guidance)
        self.assertIn("`.agents/plugins/marketplace.json`", guidance)
        self.assertIn("Do not hand-edit generated files", guidance)
        self.assertIn("`codex-*` skill adapters", guidance)
        self.assertIn("`.codex/skills/`", guidance)
        self.assertIn("hooks/claude-hooks.json", guidance)
        self.assertIn("full 40-character lowercase hex `sha`; the generator gives Codex the same commit", guidance)
        self.assertIn("`.codex-mcp.json`", guidance)
        self.assertIn("Do not change `.mcp.json` solely for Codex", guidance)

    def test_prose_outside_plugins_avoids_em_dashes(self) -> None:
        paths = [
            ROOT / "README.md",
            ROOT / "CLAUDE.md",
            ROOT / "CONTRIBUTING.md",
            *sorted((ROOT / "docs").glob("*.md")),
        ]
        for path in paths:
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                self.assertIsNone(re.search("—", path.read_text()))

    def test_gitattributes_marks_exactly_the_generated_files(self) -> None:
        tracked = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-z"], check=True, capture_output=True, text=True
        ).stdout.split("\0")
        fields = subprocess.run(
            ["git", "-C", str(ROOT), "check-attr", "-z", "--stdin", "linguist-generated"],
            input="\0".join(tracked), check=True, capture_output=True, text=True,
        ).stdout.split("\0")
        marked = {fields[k] for k in range(0, len(fields) - 2, 3) if fields[k + 2] in ("set", "true")}
        listed = json.loads((ROOT / ".agents" / "plugins" / "generated-files.json").read_text())["files"]
        self.assertEqual(marked, set(listed))

    def test_cubic_skips_exactly_the_generated_file_patterns(self) -> None:
        config = yaml.safe_load((ROOT / "cubic.yaml").read_text())
        self.assertEqual(config["version"], 1)
        generated = {
            line.split()[0]
            for line in (ROOT / ".gitattributes").read_text().splitlines()
            if "linguist-generated" in line and not line.startswith("#")
        }
        self.assertEqual(set(config["reviews"]["ignore"]["files"]), generated)

if __name__ == "__main__":
    unittest.main()
