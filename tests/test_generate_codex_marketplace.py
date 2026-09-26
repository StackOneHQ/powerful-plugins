import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.generate_codex_marketplace as generator
from scripts.generate_codex_marketplace import (
    GenerationError,
    _display_name,
    _load_json,
    _short_description,
    build_expected_files,
    build_plugin_manifest,
    check_generated_files,
    collect_adapter_skills,
    convert_source,
    normalize_category,
    render_agent_adapter,
    render_command_adapter,
    render_existing_skill_metadata,
    resolve_local_source,
    split_claude_frontmatter,
    split_frontmatter,
    write_generated_files,
)


class CatalogConversionTests(unittest.TestCase):
    def test_convert_github_root_source(self) -> None:
        source = {
            "source": "github",
            "repo": "vercel-labs/agent-browser",
            "sha": "0123456789abcdef0123456789abcdef01234567",
        }

        self.assertEqual(
            convert_source(source),
            {
                "source": "url",
                "url": "https://github.com/vercel-labs/agent-browser.git",
                "ref": "0123456789abcdef0123456789abcdef01234567",
            },
        )

    def test_convert_git_subdir_source(self) -> None:
        source = {
            "source": "git-subdir",
            "url": "vercel-labs/agent-skills",
            "path": "skills/react-best-practices",
            "sha": "0123456789abcdef0123456789abcdef01234567",
        }

        self.assertEqual(
            convert_source(source),
            {
                "source": "git-subdir",
                "url": "https://github.com/vercel-labs/agent-skills.git",
                "path": "./skills/react-best-practices",
                "ref": "0123456789abcdef0123456789abcdef01234567",
            },
        )

    def test_github_source_with_path_is_rejected(self) -> None:
        # Claude Code ignores path on a github source and installs the repository root.
        with self.assertRaisesRegex(GenerationError, "use git-subdir with url, path and sha"):
            convert_source(
                {
                    "source": "github",
                    "repo": "example/plugins",
                    "path": "plugins/checker",
                    "sha": "0123456789abcdef0123456789abcdef01234567",
                }
            )

    def test_external_source_must_pin_a_full_sha(self) -> None:
        unpinned = (
            {"source": "github", "repo": "example/plugins"},
            {"source": "github", "repo": "example/plugins", "sha": "0123456"},
            {"source": "github", "repo": "example/plugins", "sha": "0123456789abcdef0123456789abcdef01234567".upper()},
            {"source": "git-subdir", "url": "example/plugins", "path": "plugins/checker"},
        )

        for source in unpinned:
            with self.subTest(source=source):
                with self.assertRaisesRegex(GenerationError, "sha"):
                    convert_source(source)

    def test_external_source_rejects_a_branch_or_tag_ref(self) -> None:
        for extra in ({"ref": "main"}, {"ref": "v2.1.0", "sha": "0123456789abcdef0123456789abcdef01234567"}):
            with self.subTest(extra=extra):
                with self.assertRaisesRegex(GenerationError, "not ref"):
                    convert_source(
                        {"source": "github", "repo": "example/plugins", **extra}
                    )

    def test_convert_source_rejects_unknown_provider(self) -> None:
        for kind in ("gitlab", ["github"], {"github": True}):
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(GenerationError, "unsupported external source"):
                    convert_source({"source": kind, "repo": "example/plugins", "sha": "0123456789abcdef0123456789abcdef01234567"})

    def test_convert_source_rejects_unsafe_repository_and_subdirectory(self) -> None:
        sha = "0123456789abcdef0123456789abcdef01234567"
        unsafe_sources = (
            {"source": "github", "repo": "owner", "sha": sha},
            {"source": "github", "repo": "owner/repo/extra", "sha": sha},
            {"source": "github", "repo": " owner/repo", "sha": sha},
            {"source": "github", "repo": "owner/.git", "sha": sha},
            {"source": "github", "repo": "owner/repo", "sha": sha, "extra": True},
            {"source": "git-subdir", "url": "owner/repo", "sha": sha},
            {"source": "git-subdir", "url": "owner/repo", "path": "../../outside", "sha": sha},
            {"source": "git-subdir", "url": "owner/repo", "path": "skills\\outside", "sha": sha},
            {"source": "git-subdir", "url": "owner/repo", "path": "/absolute", "sha": sha},
            {"source": "git-subdir", "url": "owner/repo", "path": "skills//nested", "sha": sha},
            {"source": "git-subdir", "url": "owner/repo", "path": "./skills", "sha": sha},
        )

        for source in unsafe_sources:
            with self.subTest(source=source):
                with self.assertRaises(GenerationError):
                    convert_source(source)

    def test_json_loader_rejects_duplicate_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"name": "first", "name": "second"}\n')

            with self.assertRaisesRegex(GenerationError, "duplicate JSON key"):
                _load_json(path)

    def test_categories_are_humanized_for_codex(self) -> None:
        self.assertEqual(normalize_category("customer-success"), "Customer Success")
        self.assertEqual(normalize_category("development"), "Development")

    def test_display_names_preserve_canonical_brands_and_acronyms(self) -> None:
        self.assertEqual(_display_name("cc-print"), "CC Print")
        self.assertEqual(_display_name("md-to-html"), "Markdown to HTML")
        self.assertEqual(_display_name("github-pr-review"), "GitHub PR Review")
        self.assertEqual(_display_name("openai-sdk-ui"), "OpenAI SDK UI")
        self.assertEqual(_display_name("tufte-viz"), "Tufte Viz")

    def test_short_descriptions_truncate_at_a_word_boundary(self) -> None:
        self.assertEqual(_short_description("alpha beta gamma", 13), "alpha beta…")
        self.assertEqual(_short_description("alpha beta gamma", 11), "alpha beta…")

    def test_local_source_must_stay_inside_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(GenerationError, "outside the repository"):
                resolve_local_source(root, "./../other-plugin")

    def test_local_source_must_start_with_dot_slash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(GenerationError, "start with './'"):
                resolve_local_source(root, "plugins/example")


class PluginManifestTests(unittest.TestCase):
    def test_build_manifest_prefers_codex_specific_mcp_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory) / "plugins" / "engineering" / "example"
            plugin_dir.mkdir(parents=True)
            (plugin_dir / ".mcp.json").write_text('{"mcpServers":{"claude":{}}}\n')
            (plugin_dir / ".codex-mcp.json").write_text(
                '{"mcpServers":{"codex":{}}}\n'
            )
            entry = {
                "name": "example",
                "description": "Run an example workflow",
                "category": "engineering",
            }
            claude_manifest = {
                "name": "example",
                "version": "1.2.3",
                "description": "Run an example workflow",
                "author": {"name": "Example Author"},
            }

            manifest = build_plugin_manifest(plugin_dir, entry, claude_manifest)

        self.assertEqual(manifest["mcpServers"], "./.codex-mcp.json")

    def test_build_manifest_includes_available_components(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory) / "plugins" / "engineering" / "example"
            (plugin_dir / "skills" / "example").mkdir(parents=True)
            (plugin_dir / "skills" / "example" / "SKILL.md").write_text(
                "---\nname: example\ndescription: Run an example workflow.\n---\n"
            )
            (plugin_dir / "hooks").mkdir()
            (plugin_dir / "hooks" / "hooks.json").write_text("{}\n")
            (plugin_dir / ".mcp.json").write_text("{}\n")
            entry = {
                "name": "example",
                "description": "Run an example workflow",
                "category": "engineering",
            }
            claude_manifest = {
                "name": "example",
                "version": "1.2.3",
                "description": "Run an example workflow",
                "author": {
                    "name": "Example Author",
                    "email": "author@example.com",
                },
                "license": "MIT",
                "keywords": ["example", "fixture"],
            }

            manifest = build_plugin_manifest(plugin_dir, entry, claude_manifest)

        self.assertEqual(manifest["name"], "example")
        self.assertEqual(manifest["version"], "1.2.3")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertEqual(manifest["mcpServers"], "./.mcp.json")
        self.assertNotIn("hooks", manifest)
        self.assertEqual(manifest["author"]["name"], "Example Author")
        self.assertEqual(manifest["interface"]["displayName"], "Example")
        self.assertEqual(manifest["interface"]["category"], "Engineering")
        self.assertEqual(manifest["interface"]["capabilities"], ["Interactive"])
        self.assertEqual(
            manifest["interface"]["defaultPrompt"],
            ["Use Example to run this workflow."],
        )

    def test_build_manifest_rejects_invalid_semver(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory) / "example"
            plugin_dir.mkdir()
            entry = {
                "name": "example",
                "description": "Run an example workflow",
                "category": "engineering",
            }
            claude_manifest = {
                "name": "example",
                "version": "next",
                "description": "Run an example workflow",
                "author": {"name": "Example Author"},
            }

            with self.assertRaisesRegex(GenerationError, "semantic version"):
                build_plugin_manifest(plugin_dir, entry, claude_manifest)

    def test_build_manifest_rejects_numeric_prerelease_with_leading_zero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory) / "example"
            plugin_dir.mkdir()
            entry = {"name": "example", "category": "engineering"}
            claude_manifest = {
                "name": "example",
                "version": "1.0.0-01",
                "description": "Run an example workflow",
                "author": {"name": "Example Author"},
            }

            with self.assertRaisesRegex(GenerationError, "semantic version"):
                build_plugin_manifest(plugin_dir, entry, claude_manifest)

    def test_build_manifest_includes_app_mapping_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory) / "example"
            plugin_dir.mkdir()
            (plugin_dir / ".app.json").write_text("{}\n")
            entry = {"name": "example", "category": "engineering"}
            claude_manifest = {
                "name": "example",
                "version": "1.0.0",
                "description": "Run an example workflow",
                "author": {"name": "Example Author"},
            }

            manifest = build_plugin_manifest(plugin_dir, entry, claude_manifest)

        self.assertEqual(manifest["apps"], "./.app.json")

    def test_custom_claude_hooks_use_codex_default_without_manifest_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory) / "example"
            (plugin_dir / "hooks").mkdir(parents=True)
            (plugin_dir / "hooks" / "hooks.json").write_text("{}\n")
            (plugin_dir / "hooks" / "claude-hooks.json").write_text("{}\n")
            entry = {"name": "example", "category": "engineering"}
            claude_manifest = {
                "name": "example",
                "version": "1.0.0",
                "description": "Run an example workflow",
                "author": {"name": "Example Author"},
                "hooks": "./hooks/claude-hooks.json",
            }

            manifest = build_plugin_manifest(plugin_dir, entry, claude_manifest)

        self.assertNotIn("hooks", manifest)

    def test_root_level_claude_hooks_without_codex_hooks_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory) / "example"
            plugin_dir.mkdir()
            (plugin_dir / "hooks.json").write_text("{}\n")
            claude_manifest = {
                "name": "example",
                "version": "1.0.0",
                "description": "Run an example workflow",
                "author": {"name": "Example Author"},
                "hooks": "./hooks.json",
            }

            with self.assertRaisesRegex(GenerationError, "hooks/hooks.json for Codex"):
                build_plugin_manifest(
                    plugin_dir, {"name": "example", "category": "engineering"}, claude_manifest
                )

    def test_build_manifest_rejects_non_string_category(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory) / "example"
            plugin_dir.mkdir()
            claude_manifest = {
                "name": "example",
                "version": "1.0.0",
                "description": "Run an example workflow",
                "author": {"name": "Example Author"},
            }

            with self.assertRaisesRegex(GenerationError, "category"):
                build_plugin_manifest(
                    plugin_dir,
                    {"name": "example", "category": None},
                    claude_manifest,
                )

    def test_build_manifest_uses_marketplace_author_as_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory) / "example"
            plugin_dir.mkdir()
            entry = {
                "name": "example",
                "description": "Run an example workflow",
                "category": "engineering",
                "author": {
                    "name": "Example Author",
                    "email": "author@example.com",
                },
                "tags": ["example", "fixture"],
            }
            claude_manifest = {
                "name": "example",
                "version": "1.0.0",
                "description": "Run an example workflow",
            }

            manifest = build_plugin_manifest(plugin_dir, entry, claude_manifest)

        self.assertEqual(manifest["author"]["name"], "Example Author")
        self.assertEqual(manifest["keywords"], ["example", "fixture"])

    def test_build_manifest_defaults_links_to_the_public_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory) / "example"
            plugin_dir.mkdir()
            entry = {"name": "example", "category": "engineering"}
            claude_manifest = {
                "name": "example",
                "version": "1.0.0",
                "description": "Run an example workflow",
                "author": {"name": "Example Author"},
            }

            manifest = build_plugin_manifest(plugin_dir, entry, claude_manifest)

        repository = "https://github.com/StackOneHQ/powerful-plugins"
        self.assertEqual(manifest["author"]["url"], "https://github.com/StackOneHQ")
        self.assertEqual(manifest["homepage"], repository)
        self.assertEqual(manifest["repository"], repository)
        self.assertEqual(manifest["interface"]["websiteURL"], repository)

    def test_build_manifest_website_follows_a_declared_homepage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory) / "example"
            plugin_dir.mkdir()
            entry = {"name": "example", "category": "engineering"}
            claude_manifest = {
                "name": "example",
                "version": "1.0.0",
                "description": "Run an example workflow",
                "author": {"name": "Example Author", "url": "https://example.com"},
                "homepage": "https://example.com/plugin",
            }

            manifest = build_plugin_manifest(plugin_dir, entry, claude_manifest)

        self.assertEqual(manifest["author"]["url"], "https://example.com")
        self.assertEqual(manifest["homepage"], "https://example.com/plugin")
        self.assertEqual(manifest["interface"]["websiteURL"], "https://example.com/plugin")


class AdapterTests(unittest.TestCase):
    def test_split_frontmatter_returns_scalar_metadata_and_body(self) -> None:
        metadata, body = split_frontmatter(
            "---\nname: review-copy\ndescription: Review written copy\n---\n\nDo the work.\n",
            Path("skills/review-copy/SKILL.md"),
        )

        self.assertEqual(metadata["name"], "review-copy")
        self.assertEqual(metadata["description"], "Review written copy")
        self.assertEqual(body, "Do the work.\n")

    def test_split_frontmatter_accepts_valid_yaml_colons_and_comments(self) -> None:
        metadata, _ = split_frontmatter(
            "---\n"
            "name: valid # the skill name\n"
            "description: 'Use this workflow. Skip for: deployment tasks.'\n"
            "---\n",
            Path("skills/valid/SKILL.md"),
        )

        self.assertEqual(metadata["name"], "valid")
        self.assertEqual(
            metadata["description"],
            "Use this workflow. Skip for: deployment tasks.",
        )

    def test_split_frontmatter_rejects_unsafe_yaml_tags(self) -> None:
        with self.assertRaisesRegex(GenerationError, "invalid YAML frontmatter"):
            split_frontmatter(
                "---\nname: unsafe\ndescription: !!python/object/new:tuple []\n---\n",
                Path("skills/unsafe/SKILL.md"),
            )

    def test_claude_source_frontmatter_can_preserve_duplicate_key_compatibility(
        self,
    ) -> None:
        source = Path("skills/legacy/SKILL.md")
        text = (
            "---\n"
            "name: legacy\n"
            "description: Run the legacy workflow.\n"
            "invocable: true\n"
            "invocable: true\n"
            "---\n"
        )

        with self.assertRaisesRegex(GenerationError, "duplicate key"):
            split_frontmatter(text, source)

        metadata, _ = split_frontmatter(
            text, source, reject_duplicate_keys=False
        )
        self.assertIs(metadata["invocable"], True)

    def test_claude_source_frontmatter_accepts_legacy_unquoted_colons(self) -> None:
        source = Path("agents/webhook-implementer.md")
        text = (
            "---\n"
            "name: webhook-implementer\n"
            "description: Run phases with gates: research, build, and validate\n"
            "model: sonnet\n"
            "---\n\n"
            "Implement the workflow.\n"
        )

        with self.assertRaisesRegex(GenerationError, "invalid YAML"):
            split_frontmatter(text, source, reject_duplicate_keys=False)

        metadata, body = split_claude_frontmatter(text, source)
        self.assertEqual(
            metadata["description"],
            "Run phases with gates: research, build, and validate",
        )
        self.assertEqual(body, "Implement the workflow.\n")

    def test_split_frontmatter_preserves_yaml_block_semantics(self) -> None:
        metadata, body = split_frontmatter(
            "---\n"
            "name: valid\n"
            "description: >\n"
            "  First sentence.\n"
            "  Second sentence.\n"
            "example: |\n"
            "  alpha\n"
            "  ---\n"
            "  omega\n"
            "---\n\n"
            "Run it.\n",
            Path("skills/valid/SKILL.md"),
        )

        self.assertEqual(metadata["description"], "First sentence. Second sentence.\n")
        self.assertEqual(metadata["example"], "alpha\n---\nomega\n")
        self.assertEqual(body, "Run it.\n")

    def test_split_frontmatter_reads_block_scalar_description(self) -> None:
        metadata, _ = split_frontmatter(
            "---\n"
            "name: webhook-validate\n"
            "description: |\n"
            "  Validate webhook implementation and configuration.\n"
            "  Run structural checks: syntax and completeness.\n"
            "disable-model-invocation: true\n"
            "---\n\n"
            "Validate the implementation.\n",
            Path("skills/webhook-validate/SKILL.md"),
        )

        self.assertEqual(
            metadata["description"],
            "Validate webhook implementation and configuration.\n"
            "Run structural checks: syntax and completeness.\n",
        )

    def test_command_becomes_explicit_codex_skill(self) -> None:
        source = Path("commands/review-copy.md")
        text = (
            "---\n"
            "description: Review copy for LLM writing patterns.\n"
            'argument-hint: "[file-or-directory]"\n'
            "---\n\n"
            "# Review Copy\n\n"
            "Review $ARGUMENTS and report the findings.\n"
        )

        rendered = render_command_adapter(source, text)

        self.assertEqual(rendered.name, "codex-review-copy")
        self.assertIn("name: codex-review-copy", rendered.skill_md)
        self.assertIn("description: \"Review copy", rendered.skill_md)
        self.assertIn("Arguments: `[file-or-directory]`", rendered.skill_md)
        self.assertNotIn("$ARGUMENTS", rendered.skill_md)
        self.assertIn("invocation input", rendered.skill_md)
        self.assertEqual(rendered.skill_md.count("# Review Copy"), 1)
        self.assertIn("allow_implicit_invocation: false", rendered.openai_yaml)
        self.assertIn("$codex-review-copy", rendered.openai_yaml)
        self.assertNotIn("disable-model-invocation", rendered.skill_md)

    def test_argument_placeholders_are_rewritten_only_outside_code(self) -> None:
        source = Path("commands/run.md")
        text = (
            "---\n"
            "description: Run the workflow.\n"
            "---\n\n"
            "Review $1 and pass $@ along. The plan costs $5.00 or $50 a month.\n"
            "Run `grep $1 notes.txt` first.\n\n"
            "```bash\n"
            "awk '{print $1}' \"$@\"\n"
            "```\n"
        )

        rendered = render_command_adapter(source, text)

        self.assertIn("Review invocation argument 1 and pass the invocation input", rendered.skill_md)
        self.assertIn("costs $5.00 or $50 a month", rendered.skill_md)
        self.assertIn("`grep $1 notes.txt`", rendered.skill_md)
        self.assertIn("awk '{print $1}' \"$@\"", rendered.skill_md)

    def test_long_agent_description_is_truncated_for_agent_skills(self) -> None:
        source = Path("agents/reviewer.md")
        text = (
            "---\n"
            "name: reviewer\n"
            f"description: {'Review the change in detail. ' * 60}\n"
            "---\n\n"
            "Review the change.\n"
        )

        rendered = render_agent_adapter(source, text)

        metadata, _ = split_frontmatter(rendered.skill_md, source)
        self.assertLessEqual(len(metadata["description"]), 1024)

    def test_cc_print_command_keeps_claude_source_but_targets_codex_sessions(self) -> None:
        source = Path("commands/print.md")
        text = (
            "---\n"
            "description: Export this conversation.\n"
            "---\n\n"
            "1. **Find the conversation file**. This session's transcript is named after its id:\n"
            "   ```bash\n"
            "   ls ~/.claude/projects/*/\"${CLAUDE_SESSION_ID}\".jsonl 2>/dev/null | head -1\n"
            "   ```\n"
            "   If that finds nothing, fall back to the newest transcript for this folder. Claude Code names the\n"
            "   folder after the working directory with every character other than a letter or digit turned into `-`:\n"
            "   ```bash\n"
            "   ls -t ~/.claude/projects/\"$(pwd | sed 's/[^A-Za-z0-9]/-/g')\"/*.jsonl 2>/dev/null | head -1\n"
            "   ```\n\n"
            "3. **Find the export script**:\n"
            "   ```bash\n"
            "   printf '%s\\n' \"${CLAUDE_PLUGIN_ROOT}/scripts/export-conversation.js\"\n"
            "   ```\n\n"
            "- `/cc-print:print last 20` - Last 20 exchanges as PNG\n"
        )

        rendered = render_command_adapter(source, text)

        self.assertIn('os.environ.get("CODEX_HOME") or', rendered.skill_md)
        self.assertIn("`$cc-print:codex-print last 20`", rendered.skill_md)
        self.assertNotIn("/cc-print:print", rendered.skill_md)
        self.assertIn('${PLUGIN_ROOT}/scripts/export-conversation.js', rendered.skill_md)
        self.assertNotIn("~/.claude/projects", rendered.skill_md)
        self.assertNotIn("CLAUDE_PLUGIN_ROOT", rendered.skill_md)

    def test_agent_becomes_namespaced_specialist_skill(self) -> None:
        source = Path("agents/security-reviewer.md")
        text = (
            "---\n"
            "name: security-reviewer\n"
            "description: Review changes for exploitable security defects.\n"
            "tools:\n"
            "  - Read\n"
            "---\n\n"
            "Inspect the complete change before reporting.\n"
        )

        rendered = render_agent_adapter(source, text)

        self.assertEqual(rendered.name, "agent-security-reviewer")
        self.assertIn("name: agent-security-reviewer", rendered.skill_md)
        self.assertIn("Inspect the complete change", rendered.skill_md)
        self.assertIn("allow_implicit_invocation: false", rendered.openai_yaml)

    def test_agent_without_description_gets_a_codex_only_fallback(self) -> None:
        source = Path("agents/schema-review/orchestrator.md")
        text = (
            "---\n"
            "name: connector-validate\n"
            "model: sonnet\n"
            "tools:\n"
            "  - Read\n"
            "---\n\n"
            "Run the schema review workflow.\n"
        )

        rendered = render_agent_adapter(source, text)

        self.assertIn(
            'description: "Specialist workflow: Connector Validate specialist workflow."',
            rendered.skill_md,
        )
        self.assertIn("Run the schema review workflow", rendered.skill_md)

    def test_command_name_is_normalized_to_agent_skill_rules(self) -> None:
        rendered = render_command_adapter(
            Path("commands/add_decision_makers.md"),
            "---\ndescription: Add decision makers to a campaign.\n---\n\nAdd them.\n",
        )

        self.assertEqual(rendered.name, "codex-add-decision-makers")

    def test_generated_adapter_strips_trailing_whitespace(self) -> None:
        rendered = render_command_adapter(
            Path("commands/review.md"),
            "---\ndescription: Review the current change.\n---\n\n"
            "Line with spaces.  \nNext line.\n",
        )

        self.assertTrue(
            all(line == line.rstrip() for line in rendered.skill_md.splitlines())
        )

    def test_disabled_existing_skill_gets_explicit_policy_metadata(self) -> None:
        source = Path("skills/review/SKILL.md")
        text = (
            "---\n"
            "name: review\n"
            "description: Review a completed change before it ships.\n"
            "disable-model-invocation: true # Claude compatibility setting\n"
            "---\n\n"
            "Review the change.\n"
        )

        metadata = render_existing_skill_metadata(source, text)

        self.assertIsNotNone(metadata)
        self.assertIn("allow_implicit_invocation: false", metadata or "")
        self.assertIn("$review", metadata or "")

    def test_default_existing_skill_does_not_get_redundant_metadata(self) -> None:
        source = Path("skills/review/SKILL.md")
        text = (
            "---\n"
            "name: review\n"
            "description: Review a completed change before it ships.\n"
            "---\n\n"
            "Review the change.\n"
        )

        self.assertIsNone(render_existing_skill_metadata(source, text))

    def test_native_skill_gets_one_codex_only_proxy_instead_of_command_duplicate(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory)
            skill_dir = plugin_dir / "skills" / "review"
            command_dir = plugin_dir / "commands"
            skill_dir.mkdir(parents=True)
            command_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: review\ndescription: Review the current change.\n---\n"
            )
            (command_dir / "review.md").write_text(
                "---\ndescription: Review the current change.\n---\nRun the review.\n"
            )

            adapters = collect_adapter_skills(plugin_dir)

        self.assertEqual(set(adapters), {"review"})
        self.assertIn("../../../skills/review/SKILL.md", adapters["review"].skill_md)
        self.assertIn("allow_implicit_invocation: true", adapters["review"].openai_yaml)

    def test_command_and_agent_namespaces_do_not_collide(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory)
            command_dir = plugin_dir / "commands"
            agent_dir = plugin_dir / "agents"
            command_dir.mkdir()
            agent_dir.mkdir()
            (command_dir / "agent-reviewer.md").write_text(
                "---\ndescription: Run the reviewer workflow.\n---\nReview.\n"
            )
            (agent_dir / "reviewer.md").write_text(
                "---\nname: reviewer\ndescription: Review the current change.\n---\nReview.\n"
            )

            adapters = collect_adapter_skills(plugin_dir)

        self.assertIn("codex-agent-reviewer", adapters)
        self.assertIn("agent-reviewer", adapters)

    def test_normalized_command_name_collision_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory)
            command_dir = plugin_dir / "commands"
            command_dir.mkdir()
            for filename in ("foo-bar.md", "foo_bar.md"):
                (command_dir / filename).write_text(
                    f"---\ndescription: Run {filename}.\n---\nRun it.\n"
                )

            with self.assertRaisesRegex(GenerationError, "adapter name collision"):
                collect_adapter_skills(plugin_dir)

    def test_nested_agents_are_included_in_specialist_routing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory)
            nested = plugin_dir / "agents" / "research"
            nested.mkdir(parents=True)
            (nested / "provider.md").write_text(
                "---\n"
                "name: provider\n"
                "description: Research the provider API.\n"
                "tools: Read, Grep\n"
                "---\n"
                "Research it.\n"
            )

            adapters = collect_adapter_skills(plugin_dir)

        self.assertIn("agent-provider", adapters)
        self.assertIn("agents/research/provider.md", adapters["agent-provider"].skill_md)

    def test_custom_component_paths_and_root_skill_are_exposed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory)
            (plugin_dir / "workflows").mkdir()
            (plugin_dir / "prompts").mkdir()
            (plugin_dir / "specialists").mkdir()
            (plugin_dir / "workflows" / "custom" / "SKILL.md").parent.mkdir()
            (plugin_dir / "workflows" / "custom" / "SKILL.md").write_text(
                "---\nname: custom\ndescription: Run the custom workflow.\n---\nRun it.\n"
            )
            (plugin_dir / "prompts" / "launch.md").write_text(
                "---\ndescription: Launch the custom workflow.\n---\nLaunch it.\n"
            )
            (plugin_dir / "specialists" / "audit.md").write_text(
                "---\nname: audit\ndescription: Audit the result.\n---\nAudit it.\n"
            )
            manifest = {
                "skills": ["./workflows/custom"],
                "commands": "./prompts",
                "agents": ["./specialists"],
            }

            adapters = collect_adapter_skills(plugin_dir, manifest)

        self.assertIn("custom", adapters)
        self.assertIn("codex-launch", adapters)
        self.assertIn("agent-audit", adapters)
        self.assertIn("workflows/custom/SKILL.md", adapters["custom"].skill_md)

    def test_custom_component_path_must_stay_in_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory) / "plugin"
            plugin_dir.mkdir()
            with self.assertRaisesRegex(GenerationError, "component path"):
                collect_adapter_skills(plugin_dir, {"commands": "./../outside"})

    def test_claude_skill_metadata_is_normalized_only_in_codex_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory)
            skill_dir = plugin_dir / "skills" / "legacy-folder"
            skill_dir.mkdir(parents=True)
            source_description = "Use this detailed Claude workflow. " * 80
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: portable-workflow\n"
                f"description: {source_description}\n"
                "---\n\n"
                "Run the source workflow.\n"
            )

            adapters = collect_adapter_skills(plugin_dir)

        proxy = adapters["portable-workflow"]
        metadata, _ = split_frontmatter(proxy.skill_md, proxy.source)
        self.assertLessEqual(len(metadata["description"]), 1024)
        self.assertIn(
            "../../../skills/legacy-folder/SKILL.md", proxy.skill_md
        )


class GenerationTests(unittest.TestCase):
    def _create_fixture_repository(self, root: Path) -> Path:
        plugin_dir = root / "plugins" / "engineering" / "example"
        (root / ".claude-plugin").mkdir(parents=True)
        (plugin_dir / ".claude-plugin").mkdir(parents=True)
        (plugin_dir / "skills" / "guides" / "review").mkdir(parents=True)
        (plugin_dir / "commands").mkdir()
        (plugin_dir / "agents").mkdir()
        (root / ".agents" / "plugins").mkdir(parents=True)
        (root / ".claude-plugin" / "marketplace.json").write_text(
            json.dumps(
                {
                    "name": "fixture-marketplace",
                    "plugins": [
                        {
                            "name": "example",
                            "source": "./plugins/engineering/example",
                            "description": "Run the fixture workflow",
                            "category": "engineering",
                        },
                        {
                            "name": "external-skill",
                            "source": {
                                "source": "git-subdir",
                                "url": "example/skills",
                                "path": "skills/external",
                                "sha": "a" * 40,
                            },
                            "description": "Use an external skill",
                            "category": "development",
                        },
                    ],
                }
            )
            + "\n"
        )
        (plugin_dir / ".claude-plugin" / "plugin.json").write_text(
            json.dumps(
                {
                    "name": "example",
                    "version": "1.0.0",
                    "description": "Run the fixture workflow",
                    "author": {
                        "name": "Example Author",
                        "email": "author@example.com",
                    },
                    "license": "MIT",
                    "keywords": ["fixture"],
                }
            )
            + "\n"
        )
        (plugin_dir / "skills" / "guides" / "review" / "SKILL.md").write_text(
            "---\n"
            "name: review\n"
            "description: Review the fixture output before completion.\n"
            "disable-model-invocation: true\n"
            "---\n\n"
            "Review the output.\n"
        )
        (plugin_dir / "commands" / "run-example.md").write_text(
            "---\ndescription: Run the complete fixture workflow.\n---\n\nRun it.\n"
        )
        (plugin_dir / "agents" / "checker.md").write_text(
            "---\n"
            "name: checker\n"
            "description: Check the fixture result carefully.\n"
            "---\n\n"
            "Check the result.\n"
        )
        return plugin_dir

    def test_build_expected_files_covers_catalog_manifests_and_adapters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._create_fixture_repository(root)

            expected = build_expected_files(root)

        catalog_path = Path(".agents/plugins/marketplace.json")
        manifest_path = Path(
            "plugins/engineering/example/.codex-plugin/plugin.json"
        )
        self.assertIn(catalog_path, expected)
        self.assertIn(manifest_path, expected)
        catalog = json.loads(expected[catalog_path])
        self.assertEqual(catalog["name"], "fixture-marketplace")
        self.assertEqual(catalog["interface"], {"displayName": "Fixture Marketplace"})
        self.assertIn(
            Path(
                "plugins/engineering/example/.codex/skills/"
                "codex-run-example/SKILL.md"
            ),
            expected,
        )
        self.assertIn(
            Path(
                "plugins/engineering/example/.codex/skills/agent-checker/SKILL.md"
            ),
            expected,
        )
        self.assertNotIn(
            Path("plugins/engineering/example/skills/codex-run-example/SKILL.md"),
            expected,
        )
        native_proxy = Path(
            "plugins/engineering/example/.codex/skills/review/SKILL.md"
        )
        self.assertIn(native_proxy, expected)
        self.assertIn(
            "../../../skills/guides/review/SKILL.md", expected[native_proxy]
        )
        self.assertIn(
            "allow_implicit_invocation: false",
            expected[native_proxy.parent / "agents/openai.yaml"],
        )
        self.assertNotIn(
            Path(
                "plugins/engineering/example/skills/guides/review/agents/openai.yaml"
            ),
            expected,
        )
        self.assertIn(
            Path(
                "plugins/engineering/example/.codex/skills/guides/SKILL.md"
            ),
            expected,
        )
        nested_router = Path(
            "plugins/engineering/example/.codex/skills/guides/SKILL.md"
        )
        self.assertIn(
            "../../../skills/guides/review/SKILL.md", expected[nested_router]
        )
        catalog = json.loads(expected[catalog_path])
        self.assertEqual(len(catalog["plugins"]), 2)
        self.assertEqual(
            catalog["plugins"][0]["source"],
            {"source": "local", "path": "./plugins/engineering/example"},
        )
        self.assertEqual(catalog["plugins"][1]["source"]["source"], "git-subdir")
        self.assertEqual(catalog["plugins"][1]["source"]["ref"], "a" * 40)
        manifest = json.loads(expected[manifest_path])
        self.assertEqual(manifest["skills"], "./.codex/skills/")

    def test_generation_is_deterministic_and_check_detects_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._create_fixture_repository(root)
            first = build_expected_files(root)
            second = build_expected_files(root)
            self.assertEqual(first, second)

            write_generated_files(root, first)
            self.assertEqual(check_generated_files(root, first), [])
            self.assertEqual(build_expected_files(root), first)

            catalog_path = root / ".agents" / "plugins" / "marketplace.json"
            catalog_path.write_text("{}\n")
            drift = check_generated_files(root, first)

        self.assertEqual(drift, [Path(".agents/plugins/marketplace.json")])

    def test_check_reports_stale_generated_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin_dir = self._create_fixture_repository(root)
            expected = build_expected_files(root)
            write_generated_files(root, expected)
            stale = plugin_dir / "skills" / "stale" / "SKILL.md"
            stale.parent.mkdir(parents=True)
            stale.write_text(
                "---\nname: stale\ndescription: Stale generated workflow.\n---\n\n"
                "<!-- Generated by scripts/generate_codex_marketplace.py; do not edit. -->\n"
            )

            drift = check_generated_files(root, expected)

        self.assertIn(
            Path("plugins/engineering/example/skills/stale/SKILL.md"), drift
        )

    def test_large_agent_team_becomes_single_specialist_router(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin_dir = self._create_fixture_repository(root)
            for name in ("security", "quality", "tests"):
                punctuation = "" if name == "security" else "."
                (plugin_dir / "agents" / f"{name}.md").write_text(
                    "---\n"
                    f"name: {name}\n"
                    f"description: Run the {name} specialist review{punctuation}\n"
                    "---\n\n"
                    f"Perform the {name} review.\n"
                )

            expected = build_expected_files(root)

        router_root = Path(
            "plugins/engineering/example/.codex/skills/example-specialists"
        )
        self.assertIn(router_root / "SKILL.md", expected)
        self.assertIn(router_root / "agents/openai.yaml", expected)
        self.assertNotIn(
            Path(
                "plugins/engineering/example/.codex/skills/agent-checker/SKILL.md"
            ),
            expected,
        )
        self.assertIn("../../../agents/checker.md", expected[router_root / "SKILL.md"])
        self.assertIn(
            "Run the security specialist review. Read",
            expected[router_root / "SKILL.md"],
        )
        self.assertIn(
            "allow_implicit_invocation: true",
            expected[router_root / "agents/openai.yaml"],
        )

    def test_single_nested_skill_gets_proxy_without_duplicate_router(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin_dir = self._create_fixture_repository(root)
            leaf = plugin_dir / "skills" / "report-generation" / "report-generation"
            leaf.mkdir(parents=True)
            (leaf / "SKILL.md").write_text(
                "---\n"
                "name: report-generation\n"
                "description: Generate the final report.\n"
                "---\n\n"
                "Generate the report.\n"
            )

            adapters = collect_adapter_skills(plugin_dir)

        self.assertIn("report-generation", adapters)
        self.assertEqual(
            adapters["report-generation"].source,
            Path("skills/report-generation/report-generation/SKILL.md"),
        )
        self.assertNotIn("report-generation-router", adapters)

    def test_human_authored_openai_metadata_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin_dir = self._create_fixture_repository(root)
            skill_file = plugin_dir / "skills" / "guides" / "review" / "SKILL.md"
            skill_file.write_text(
                "---\n"
                "name: review\n"
                "description: Review the fixture output before completion.\n"
                "---\n\n"
                "Review the output.\n"
            )
            metadata = skill_file.parent / "agents" / "openai.yaml"
            metadata.parent.mkdir()
            metadata.write_text('interface:\n  display_name: "Custom Review"\n')

            expected = build_expected_files(root)
            write_generated_files(root, expected)
            preserved = metadata.read_text()

        self.assertEqual(
            preserved, 'interface:\n  display_name: "Custom Review"\n'
        )

    def test_writer_rejects_symlinked_output_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "repo"
            outside = base / "outside"
            (root / "plugins" / "example").mkdir(parents=True)
            outside.mkdir()
            os.symlink(outside, root / "plugins" / "example" / ".codex-plugin")

            with self.assertRaisesRegex(GenerationError, "symlink"):
                write_generated_files(
                    root,
                    {
                        Path("plugins/example/.codex-plugin/plugin.json"): "{}\n",
                    },
                )

            self.assertFalse((outside / "plugin.json").exists())

    def test_writer_does_not_follow_predictable_temporary_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            destination = root / ".agents" / "plugins" / "marketplace.json"
            destination.parent.mkdir(parents=True)
            victim = Path(directory) / "victim.txt"
            victim.write_text("preserve me\n")
            os.symlink(victim, destination.with_name(".marketplace.json.tmp"))

            write_generated_files(
                root,
                {Path(".agents/plugins/marketplace.json"): "{}\n"},
            )

            self.assertEqual(victim.read_text(), "preserve me\n")
            self.assertEqual(destination.read_text(), "{}\n")

    def test_writer_preserves_unmarked_legacy_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin_dir = self._create_fixture_repository(root)
            human_file = plugin_dir / ".codex" / "skills" / "human" / "notes.txt"
            human_file.parent.mkdir(parents=True)
            human_file.write_text("human-authored\n")

            expected = build_expected_files(root)
            write_generated_files(root, expected)

            self.assertEqual(human_file.read_text(), "human-authored\n")

    def test_writer_skips_files_whose_content_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relative = Path(".agents/plugins/marketplace.json")
            write_generated_files(root, {relative: "{}\n"})
            destination = root / relative
            first_mtime = destination.stat().st_mtime_ns
            time.sleep(0.01)

            write_generated_files(root, {relative: "{}\n"})

            self.assertEqual(destination.stat().st_mtime_ns, first_mtime)

    def test_generation_lock_uses_the_cross_platform_lock_abstraction(self) -> None:
        source = Path(generator.__file__).read_text()
        self.assertNotIn("import fcntl", source)
        self.assertIsNotNone(getattr(generator, "portalocker", None))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(generator.portalocker, "lock") as lock,
                patch.object(generator.portalocker, "unlock") as unlock,
                generator._generation_lock(root),
            ):
                pass

            lock_stream = lock.call_args.args[0]
            self.assertTrue(lock_stream.closed)
            lock.assert_called_once()
            unlock.assert_called_once_with(lock_stream)
            self.assertFalse((root / ".agents" / "plugins" / ".generation.lock").is_symlink())

    def test_generation_lock_failure_does_not_unlock_an_unacquired_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(
                    generator.portalocker,
                    "lock",
                    side_effect=generator.portalocker.exceptions.LockException(
                        "simulated lock failure"
                    ),
                ),
                patch.object(generator.portalocker, "unlock") as unlock,
                self.assertRaisesRegex(GenerationError, "unable to acquire"),
            ):
                with generator._generation_lock(root):
                    pass

            unlock.assert_not_called()

    def test_writer_rolls_back_every_file_when_a_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = Path("generated/first.txt")
            second = Path("generated/second.txt")
            write_generated_files(root, {first: "old first\n", second: "old second\n"})
            real_atomic_write = generator._atomic_write
            calls = 0

            def fail_second_write(path: Path, content: str) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("simulated write failure")
                real_atomic_write(path, content)

            with patch.object(generator, "_atomic_write", side_effect=fail_second_write):
                with self.assertRaisesRegex(GenerationError, "transaction failed"):
                    write_generated_files(
                        root, {first: "new first\n", second: "new second\n"}
                    )

            self.assertEqual((root / first).read_text(), "old first\n")
            self.assertEqual((root / second).read_text(), "old second\n")

    def test_atomic_writer_skips_directory_fsync_when_unsupported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "generated.txt"

            with patch.object(generator.os, "O_DIRECTORY", None):
                generator._atomic_write(path, "portable\n")

            self.assertEqual(path.read_text(encoding="utf-8"), "portable\n")

    def test_concurrent_generator_processes_converge_without_tempfile_races(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._create_fixture_repository(root)
            script = Path(generator.__file__).resolve()
            processes = [
                subprocess.Popen(
                    [sys.executable, str(script), "--root", str(root)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                for _ in range(8)
            ]
            completed = [process.communicate(timeout=30) for process in processes]

            for process, (stdout, stderr) in zip(processes, completed, strict=True):
                self.assertEqual(process.returncode, 0, stdout + stderr)
            expected = build_expected_files(root)
            self.assertEqual(check_generated_files(root, expected), [])

    def test_removed_plugin_artifacts_are_reported_from_ownership_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin_dir = self._create_fixture_repository(root)
            first = build_expected_files(root)
            write_generated_files(root, first)
            catalog_path = root / ".claude-plugin" / "marketplace.json"
            catalog = json.loads(catalog_path.read_text())
            catalog["plugins"] = [catalog["plugins"][1]]
            catalog_path.write_text(json.dumps(catalog) + "\n")

            second = build_expected_files(root)
            drift = check_generated_files(root, second)

            self.assertIn(
                plugin_dir.relative_to(root) / ".codex-plugin" / "plugin.json",
                drift,
            )

    def test_removing_final_adapter_converges_in_one_generation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin_dir = self._create_fixture_repository(root)
            shutil.rmtree(plugin_dir / "skills")
            shutil.rmtree(plugin_dir / "agents")
            first = build_expected_files(root)
            write_generated_files(root, first)
            (plugin_dir / "commands" / "run-example.md").unlink()

            second = build_expected_files(root)
            write_generated_files(root, second)

            manifest_path = plugin_dir / ".codex-plugin" / "plugin.json"
            self.assertNotIn("skills", json.loads(manifest_path.read_text()))
            self.assertEqual(check_generated_files(root, second), [])

    def test_runtime_adapter_derives_source_metadata_and_bundles_helper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._create_fixture_repository(root)
            catalog_path = root / ".claude-plugin" / "marketplace.json"
            catalog = json.loads(catalog_path.read_text())
            external = catalog["plugins"][1]
            external["author"] = {"name": "Example"}
            catalog_path.write_text(json.dumps(catalog) + "\n")
            overrides = root / ".agents" / "plugins" / "source-overrides.json"
            overrides.parent.mkdir(parents=True, exist_ok=True)
            overrides.write_text(
                json.dumps(
                    {
                        "version": 2,
                        "plugins": {
                            "external-skill": {
                                "source": "runtime-adapter",
                                "entrypoints": ["SKILL.md"],
                            }
                        },
                    }
                )
                + "\n"
            )
            helper_source = Path(generator.__file__).with_name(
                "materialize_pinned_upstream.py"
            )
            fixture_helper = root / "scripts" / helper_source.name
            fixture_helper.parent.mkdir()
            fixture_helper.write_text(helper_source.read_text())

            expected = build_expected_files(root)
            fixture_helper.write_text(helper_source.read_text() + "# helper changed\n")
            changed_helper = build_expected_files(root)
            external["author"] = {"name": "Another Author"}
            external["description"] = "Run the external workflow in detail. " * 40
            catalog_path.write_text(json.dumps(catalog) + "\n")
            changed_metadata = build_expected_files(root)

        manifest_path = Path("codex-compat/external-skill/.codex-plugin/plugin.json")
        self.assertNotEqual(
            json.loads(changed_helper[manifest_path])["version"],
            json.loads(changed_metadata[manifest_path])["version"],
            "changed manifest metadata must change the cached adapter version",
        )
        long_skill = changed_metadata[
            Path("codex-compat/external-skill/skills/external-skill/SKILL.md")
        ]
        metadata, _ = split_frontmatter(long_skill, Path("SKILL.md"))
        self.assertLessEqual(len(metadata["description"]), 1024)
        self.assertTrue(
            json.loads(expected[manifest_path])["version"].startswith(f"0.1.0+{'a' * 12}.")
        )
        self.assertNotEqual(
            json.loads(expected[manifest_path])["version"],
            json.loads(changed_helper[manifest_path])["version"],
            "a changed bundled helper must change the cached adapter version",
        )
        skill_root = Path(
            "codex-compat/external-skill/skills/external-skill"
        )
        skill = expected[skill_root / "SKILL.md"]
        self.assertIn(
            "compatibility: Requires Python 3, Git, and HTTPS access to github.com on first use.",
            skill,
        )
        self.assertIn("scripts/materialize_pinned_upstream.py", skill)
        self.assertIn("--repo example/skills", skill)
        self.assertIn(f"--ref {'a' * 40}", skill)
        self.assertIn("skills/external/SKILL.md", skill)
        for inline_shell in ("git init", "git fetch", "mktemp", "rm -rf"):
            self.assertNotIn(inline_shell, skill)
        self.assertEqual(
            expected[skill_root / "scripts" / "materialize_pinned_upstream.py"],
            helper_source.read_text(),
        )
        manifest = json.loads(
            expected[
                Path("codex-compat/external-skill/.codex-plugin/plugin.json")
            ]
        )
        self.assertEqual(manifest["repository"], "https://github.com/example/skills")

    def test_runtime_adapter_rejects_duplicated_or_escaping_override_metadata(self) -> None:
        invalid_overrides = (
            (
                {
                    "source": "runtime-adapter",
                    "repo": "example/skills",
                    "entrypoints": ["SKILL.md"],
                },
                "only source and entrypoints",
            ),
            (
                {
                    "source": "runtime-adapter",
                    "entrypoints": ["../outside.md"],
                },
                "invalid adapter entrypoint",
            ),
        )
        for override, message in invalid_overrides:
            with self.subTest(override=override), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self._create_fixture_repository(root)
                catalog_path = root / ".claude-plugin" / "marketplace.json"
                catalog = json.loads(catalog_path.read_text())
                catalog["plugins"][1]["author"] = {"name": "Example"}
                catalog_path.write_text(json.dumps(catalog) + "\n")
                overrides = root / ".agents" / "plugins" / "source-overrides.json"
                overrides.parent.mkdir(parents=True, exist_ok=True)
                overrides.write_text(
                    json.dumps(
                        {
                            "version": 2,
                            "plugins": {"external-skill": override},
                        }
                    )
                    + "\n"
                )

                with self.assertRaisesRegex(GenerationError, message):
                    build_expected_files(root)

    def test_catalog_name_must_be_kebab_case(self) -> None:
        for name in ("Fixture Marketplace", "fixture_marketplace", "", 7):
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    self._create_fixture_repository(root)
                    catalog_path = root / ".claude-plugin" / "marketplace.json"
                    catalog = json.loads(catalog_path.read_text())
                    catalog["name"] = name
                    catalog_path.write_text(json.dumps(catalog) + "\n")

                    with self.assertRaisesRegex(GenerationError, "kebab-case"):
                        build_expected_files(root)

    def test_real_marketplace_has_one_codex_entry_per_claude_entry(self) -> None:
        root = Path(__file__).resolve().parents[1]
        claude_catalog = json.loads(
            (root / ".claude-plugin" / "marketplace.json").read_text()
        )
        local_count = sum(
            isinstance(entry["source"], str) for entry in claude_catalog["plugins"]
        )
        external_count = len(claude_catalog["plugins"]) - local_count

        expected = build_expected_files(root)
        codex_catalog = json.loads(
            expected[Path(".agents/plugins/marketplace.json")]
        )
        source_overrides = json.loads(
            (root / ".agents" / "plugins" / "source-overrides.json").read_text()
        )
        adapter_count = len(source_overrides["plugins"])

        self.assertGreater(local_count, 0)
        self.assertEqual(claude_catalog["name"], "powerful-plugins")
        self.assertEqual(codex_catalog["name"], claude_catalog["name"])
        self.assertEqual(codex_catalog["interface"]["displayName"], "Powerful Plugins")
        self.assertEqual(len(codex_catalog["plugins"]), len(claude_catalog["plugins"]))
        self.assertEqual(
            sum(path.name == "plugin.json" for path in expected),
            local_count + adapter_count,
        )
        generated_metadata = "\n".join(
            content
            for path, content in expected.items()
            if path.name == "openai.yaml"
        )
        self.assertNotIn("agent workflow (| agent workflow)", generated_metadata)
        external_names = {
            entry["name"]
            for entry in claude_catalog["plugins"]
            if isinstance(entry["source"], dict)
        }
        claude_shas = {}
        for entry in claude_catalog["plugins"]:
            if isinstance(entry["source"], dict):
                self.assertNotIn("ref", entry["source"])
                self.assertRegex(entry["source"]["sha"], r"^[0-9a-f]{40}$")
                if entry["source"]["source"] == "github":
                    self.assertNotIn("path", entry["source"])
                claude_shas[entry["name"]] = entry["source"]["sha"]
        external_codex = [
            entry
            for entry in codex_catalog["plugins"]
            if entry["name"] in external_names
        ]
        self.assertEqual(len(external_codex), external_count)
        self.assertEqual(
            sum(entry["source"]["source"] == "local" for entry in external_codex),
            adapter_count,
        )
        for entry in external_codex:
            if entry["source"]["source"] != "local":
                # Codex installs the same commit Claude Code does.
                self.assertEqual(entry["source"]["ref"], claude_shas[entry["name"]])
        for path, content in expected.items():
            if (
                path.parts[:1] == ("plugins",)
                and path.name == "SKILL.md"
                and "Generated by scripts/generate_codex_marketplace.py" in content
            ):
                self.assertEqual(path.parts[3:5], (".codex", "skills"))


class StandaloneExporterTests(unittest.TestCase):
    def test_exporter_copies_complete_skill_directory(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        script = repository_root / "scripts" / "export-standalone-skills.sh"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill_dir = root / "plugins" / "example" / "skills" / "complete-skill"
            destination = root / "exported"
            (skill_dir / "reference").mkdir(parents=True)
            (skill_dir / "assets" / "nested").mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: complete-skill\n"
                "description: Exercise the complete standalone export.\n"
                "invoke: complete\n"
                "---\n\n"
                "Use every bundled file.\n"
            )
            (skill_dir / "reference" / "guide.md").write_text("Guide\n")
            (skill_dir / "assets" / "nested" / "data.txt").write_text("Data\n")
            (skill_dir / "TEMPLATE.html").write_text("<main>Template</main>\n")

            completed = subprocess.run(
                [
                    "bash",
                    str(script),
                    "--root",
                    str(root),
                    "--dest",
                    str(destination),
                    "complete-skill",
                ],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHON": sys.executable},
            )

            exported = destination / "complete-skill"
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((exported / "reference" / "guide.md").is_file())
            self.assertTrue((exported / "assets" / "nested" / "data.txt").is_file())
            self.assertTrue((exported / "TEMPLATE.html").is_file())
            self.assertNotIn("invoke:", (exported / "SKILL.md").read_text())


if __name__ == "__main__":
    unittest.main()
