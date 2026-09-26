from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class ChangedSkillSelectionTests(unittest.TestCase):
    def test_scan_workflow_does_not_duplicate_feature_branch_pr_runs(self) -> None:
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "scan-skills.yml"
        ).read_text()
        self.assertIn("  push:\n    branches: [main]\n", workflow)
        self.assertIn("  pull_request:\n    branches: [main]\n", workflow)

    def test_scan_workflow_grants_code_scanning_permissions(self) -> None:
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "scan-skills.yml"
        ).read_text()
        self.assertIn("  actions: read", workflow)
        self.assertIn("  contents: read", workflow)
        self.assertIn("  security-events: write", workflow)

    def test_scan_workflow_only_uploads_when_code_security_is_enabled(self) -> None:
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "scan-skills.yml"
        ).read_text()
        self.assertIn("name: Check code scanning availability", workflow)
        self.assertIn(
            "steps.code-scanning.outputs.enabled == 'true'",
            workflow,
        )
        self.assertIn(
            ".security_and_analysis.advanced_security.status",
            workflow,
        )

    def test_dispatched_checks_test_the_pull_request_merge_ref(self) -> None:
        workflows = Path(__file__).resolve().parents[1] / ".github" / "workflows"
        sync = (workflows / "codex-sync.yml").read_text()
        for name in ("validate-plugins.yml", "scan-skills.yml"):
            with self.subTest(workflow=name):
                self.assertIn(f"gh workflow run {name} --ref", sync)
                workflow = (workflows / name).read_text()
                self.assertIn("      pr_number:\n", workflow)
                self.assertIn('"+refs/pull/${PR_NUMBER}/merge:', workflow)
                self.assertIn("PR_NUMBER: ${{ inputs.pr_number }}", workflow)
                self.assertIn("HEAD_SHA: ${{ inputs.head_sha }}", workflow)
                self.assertIn(
                    '[ "$(git rev-parse refs/remotes/pull/merge^2)" = "$HEAD_SHA" ]', workflow
                )
        self.assertEqual(sync.count('-f pr_number="${PR_NUMBER}" -f head_sha='), 2)

    def test_hand_authored_openai_policy_rescans_its_skill(self) -> None:
        scanner = Path(__file__).resolve().parents[1] / "scripts" / "scan-skills.sh"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "plugins" / "example" / "skills" / "existing"
            metadata = skill / "agents" / "openai.yaml"
            metadata.parent.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\n"
                "name: existing\n"
                "description: Existing human-authored workflow.\n"
                "---\n"
            )
            metadata.write_text("interface:\n  display_name: Existing\n")
            self._git(root, "init")
            self._git(root, "config", "user.email", "tests@example.com")
            self._git(root, "config", "user.name", "Tests")
            self._git(root, "add", ".")
            self._git(root, "commit", "-m", "initial human-authored policy")
            base = self._git(root, "rev-parse", "HEAD").stdout.strip()
            metadata.write_text("interface:\n  display_name: Custom Existing\n")
            self._git(root, "add", ".")
            self._git(root, "commit", "-m", "change human-authored policy")

            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_scanner = fake_bin / "skillspector"
            fake_scanner.write_text(self.LOGGING_SCANNER)
            fake_scanner.chmod(0o755)
            scan_log = root / "scanned.txt"
            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
            environment["SCAN_LOG"] = str(scan_log)

            completed = subprocess.run(
                ["bash", str(scanner), "changed", base],
                cwd=root,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(
                scan_log.read_text().splitlines(),
                ["plugins/example/skills/existing"],
            )

    def test_deleted_openai_policy_does_not_rescan_its_skill(self) -> None:
        scanner = Path(__file__).resolve().parents[1] / "scripts" / "scan-skills.sh"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "plugins" / "example" / "skills" / "existing"
            metadata = skill / "agents" / "openai.yaml"
            metadata.parent.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\n"
                "name: existing\n"
                "description: Existing human-authored workflow.\n"
                "---\n"
            )
            metadata.write_text(
                "# Generated by scripts/generate_codex_marketplace.py; do not edit.\n"
                "interface:\n"
                "  display_name: Existing\n"
            )
            self._git(root, "init")
            self._git(root, "config", "user.email", "tests@example.com")
            self._git(root, "config", "user.name", "Tests")
            self._git(root, "add", ".")
            self._git(root, "commit", "-m", "initial skill and policy")
            base = self._git(root, "rev-parse", "HEAD").stdout.strip()
            metadata.unlink()
            self._git(root, "add", "-u")
            self._git(root, "commit", "-m", "remove generated policy")

            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_scanner = fake_bin / "skillspector"
            fake_scanner.write_text("#!/usr/bin/env bash\nexit 99\n")
            fake_scanner.chmod(0o755)
            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:{environment['PATH']}"

            completed = subprocess.run(
                ["bash", str(scanner), "changed", base],
                cwd=root,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("No skills to scan", completed.stdout)

    def test_all_mode_scans_human_generated_and_compatibility_skills(self) -> None:
        scanner = Path(__file__).resolve().parents[1] / "scripts" / "scan-skills.sh"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            human = root / "plugins" / "example" / "skills" / "human"
            generated = root / "plugins" / "example" / "skills" / "generated"
            compatibility = (
                root
                / "codex-compat"
                / "external"
                / "skills"
                / "external"
            )
            human.mkdir(parents=True)
            generated.mkdir(parents=True)
            compatibility.mkdir(parents=True)
            (human / "SKILL.md").write_text(
                "---\nname: human\ndescription: Human-authored workflow.\n---\n"
            )
            (generated / "SKILL.md").write_text(
                "---\nname: generated\ndescription: Generated workflow.\n---\n\n"
                "<!-- Generated by scripts/generate_codex_marketplace.py; "
                "do not edit. Source: commands/generated.md -->\n"
            )
            (compatibility / "SKILL.md").write_text(
                "---\nname: external\ndescription: Generated external workflow.\n---\n\n"
                "<!-- Generated by scripts/generate_codex_marketplace.py; "
                "do not edit. Runtime upstream adapter. -->\n"
            )
            self._git(root, "init")
            nested_working_directory = root / "nested"
            nested_working_directory.mkdir()

            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_scanner = fake_bin / "skillspector"
            fake_scanner.write_text(self.LOGGING_SCANNER)
            fake_scanner.chmod(0o755)
            scan_log = root / "scanned.txt"
            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
            environment["SCAN_LOG"] = str(scan_log)

            completed = subprocess.run(
                ["bash", str(scanner), "all"],
                cwd=nested_working_directory,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(
                scan_log.read_text().splitlines(),
                [
                    "codex-compat/external/skills/external",
                    "plugins/example/skills/generated",
                    "plugins/example/skills/human",
                ],
            )

    def test_combines_reports_into_one_run_with_repo_relative_locations(self) -> None:
        scanner = Path(__file__).resolve().parents[1] / "scripts" / "scan-skills.sh"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("first", "second"):
                skill = root / "plugins" / "example" / "skills" / name
                skill.mkdir(parents=True)
                (skill / "SKILL.md").write_text(
                    f"---\nname: {name}\ndescription: A human-authored workflow.\n---\n"
                )
            self._git(root, "init")

            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_scanner = fake_bin / "skillspector"
            fake_scanner.write_text(
                "#!/usr/bin/env bash\n"
                "set -eu\n"
                "output=''\n"
                "previous=''\n"
                "for argument in \"$@\"; do\n"
                "  if [ \"$previous\" = '--output' ]; then output=\"$argument\"; fi\n"
                "  previous=\"$argument\"\n"
                "done\n"
                "printf '%s\\n' '{\"version\":\"2.1.0\",\"runs\":[{\"tool\":{\"driver\":{\"name\":\"skillspector\"}},\"results\":[{\"ruleId\":\"TEST\",\"message\":{\"text\":\"skill finding\"},\"locations\":[{\"physicalLocation\":{\"artifactLocation\":{\"uri\":\"SKILL.md\"}}}]},{\"ruleId\":\"TEST\",\"message\":{\"text\":\"reference finding\"},\"locations\":[{\"physicalLocation\":{\"artifactLocation\":{\"uri\":\"references/details.md\"}}}]}]}]}' > \"$output\"\n"
            )
            fake_scanner.chmod(0o755)
            report_dir = root / "reports"
            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
            environment["REPORT_DIR"] = str(report_dir)

            completed = subprocess.run(
                ["bash", str(scanner), "all"],
                cwd=root,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            combined = json.loads((report_dir / "skillspector.sarif").read_text())
            self.assertEqual(len(combined["runs"]), 1)
            results = combined["runs"][0]["results"]
            self.assertEqual(len(results), 4)
            self.assertEqual(
                {
                    result["locations"][0]["physicalLocation"][
                        "artifactLocation"
                    ]["uri"]
                    for result in results
                },
                {
                    "plugins/example/skills/first/SKILL.md",
                    "plugins/example/skills/first/references/details.md",
                    "plugins/example/skills/second/SKILL.md",
                    "plugins/example/skills/second/references/details.md",
                },
            )

    def test_upload_leaves_out_results_the_allowlist_marks_as_reviewed(self) -> None:
        scanner = Path(__file__).resolve().parents[1] / "scripts" / "scan-skills.sh"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("first", "second"):
                skill = root / "plugins" / "example" / "skills" / name
                skill.mkdir(parents=True)
                (skill / "SKILL.md").write_text(
                    f"---\nname: {name}\ndescription: A human-authored workflow.\n---\n"
                )
            (root / ".skillspector-allowlist.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "reviewed_high_risk": [
                            {
                                "skill": "plugins/example/skills/first",
                                "rules": ["RA2"],
                                "rationale": "The daemon start is the documented purpose.",
                            }
                        ],
                    }
                )
            )
            self._git(root, "init")

            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_scanner = fake_bin / "skillspector"
            fake_scanner.write_text(
                "#!/usr/bin/env bash\n"
                "set -eu\n"
                "output=''\n"
                "previous=''\n"
                "for argument in \"$@\"; do\n"
                "  if [ \"$previous\" = '--output' ]; then output=\"$argument\"; fi\n"
                "  previous=\"$argument\"\n"
                "done\n"
                "printf '%s\\n' '{\"version\":\"2.1.0\",\"runs\":[{\"tool\":{\"driver\":{\"name\":\"skillspector\"}},\"results\":[{\"ruleId\":\"RA2\",\"level\":\"warning\",\"message\":{\"text\":\"reviewed\"},\"locations\":[{\"physicalLocation\":{\"artifactLocation\":{\"uri\":\"SKILL.md\"}}}]},{\"ruleId\":\"EA2\",\"level\":\"warning\",\"message\":{\"text\":\"not reviewed\"},\"locations\":[{\"physicalLocation\":{\"artifactLocation\":{\"uri\":\"SKILL.md\"}}}]}]}]}' > \"$output\"\n"
            )
            fake_scanner.chmod(0o755)
            report_dir = root / "reports"
            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
            environment["REPORT_DIR"] = str(report_dir)

            completed = subprocess.run(
                ["bash", str(scanner), "all"],
                cwd=root,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            combined = json.loads((report_dir / "skillspector.sarif").read_text())
            uploaded = {
                (
                    result["ruleId"],
                    result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"],
                )
                for result in combined["runs"][0]["results"]
            }
            self.assertEqual(
                uploaded,
                {
                    ("EA2", "plugins/example/skills/first/SKILL.md"),
                    ("RA2", "plugins/example/skills/second/SKILL.md"),
                    ("EA2", "plugins/example/skills/second/SKILL.md"),
                },
            )
            per_skill = json.loads(
                (report_dir / "plugins_example_skills_first.sarif").read_text()
            )
            self.assertEqual(len(per_skill["runs"][0]["results"]), 2)

    def test_generated_skill_changes_are_scanned_with_new_adapters(self) -> None:
        scanner = Path(__file__).resolve().parents[1] / "scripts" / "scan-skills.sh"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            existing = root / "plugins" / "example" / "skills" / "existing"
            existing.mkdir(parents=True)
            (existing / "SKILL.md").write_text(
                "---\n"
                "name: existing\n"
                "description: Existing workflow that is unchanged.\n"
                "---\n\n"
                "Keep this workflow unchanged.\n"
            )
            self._git(root, "init")
            self._git(root, "config", "user.email", "tests@example.com")
            self._git(root, "config", "user.name", "Tests")
            self._git(root, "add", ".")
            self._git(root, "commit", "-m", "initial skill")
            base = self._git(root, "rev-parse", "HEAD").stdout.strip()

            metadata = existing / "agents" / "openai.yaml"
            metadata.parent.mkdir()
            metadata.write_text(
                "# Generated by scripts/generate_codex_marketplace.py; do not edit.\n"
                "interface:\n"
                "  display_name: Existing\n"
            )
            adapter = root / "plugins" / "example" / "skills" / "new-adapter"
            adapter.mkdir()
            (adapter / "SKILL.md").write_text(
                "---\n"
                "name: new-adapter\n"
                "description: Newly generated adapter workflow.\n"
                "---\n\n"
                "Run the new workflow.\n"
            )
            generated = (
                root / "plugins" / "example" / "skills" / "generated-adapter"
            )
            generated.mkdir()
            (generated / "SKILL.md").write_text(
                "---\n"
                "name: generated-adapter\n"
                "description: Deterministic copy of existing source instructions.\n"
                "---\n\n"
                "<!-- Generated by scripts/generate_codex_marketplace.py; "
                "do not edit. Source: commands/existing.md -->\n\n"
                "Run the copied workflow.\n"
            )
            self._git(root, "add", ".")
            self._git(root, "commit", "-m", "add Codex metadata")

            fake_bin = root / "bin"
            fake_bin.mkdir()
            real_grep = shutil.which("grep")
            self.assertIsNotNone(real_grep)
            grep_log = root / "grep-calls.txt"
            fake_grep = fake_bin / "grep"
            fake_grep.write_text(
                "#!/usr/bin/env bash\n"
                "printf 'grep\\n' >> \"$GREP_LOG\"\n"
                "exec \"$REAL_GREP\" \"$@\"\n"
            )
            fake_grep.chmod(0o755)
            fake_scanner = fake_bin / "skillspector"
            fake_scanner.write_text(self.LOGGING_SCANNER)
            fake_scanner.chmod(0o755)
            scan_log = root / "scanned.txt"
            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
            environment["SCAN_LOG"] = str(scan_log)
            environment["GREP_LOG"] = str(grep_log)
            environment["REAL_GREP"] = real_grep or ""

            completed = subprocess.run(
                ["bash", str(scanner), "changed", base],
                cwd=root,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            scanned = scan_log.read_text().splitlines()
            self.assertEqual(
                scanned,
                [
                    "plugins/example/skills/generated-adapter",
                    "plugins/example/skills/new-adapter",
                ],
            )

    def test_changed_mode_scans_a_codex_compatibility_skill(self) -> None:
        scanner = Path(__file__).resolve().parents[1] / "scripts" / "scan-skills.sh"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._git(root, "init")
            self._git(root, "config", "user.email", "tests@example.com")
            self._git(root, "config", "user.name", "Tests")
            marker = root / "README.md"
            marker.write_text("initial\n")
            self._git(root, "add", ".")
            self._git(root, "commit", "-m", "initial")
            base = self._git(root, "rev-parse", "HEAD").stdout.strip()

            skill = root / "codex-compat" / "external" / "skills" / "external"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\nname: external\ndescription: Generated external workflow.\n---\n\n"
                "<!-- Generated by scripts/generate_codex_marketplace.py; "
                "do not edit. Runtime upstream adapter. -->\n"
            )
            self._git(root, "add", ".")
            self._git(root, "commit", "-m", "add compatibility skill")

            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_scanner = fake_bin / "skillspector"
            fake_scanner.write_text(self.LOGGING_SCANNER)
            fake_scanner.chmod(0o755)
            scan_log = root / "scanned.txt"
            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
            environment["SCAN_LOG"] = str(scan_log)

            completed = subprocess.run(
                ["bash", str(scanner), "changed", base],
                cwd=root,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(
                scan_log.read_text().splitlines(),
                ["codex-compat/external/skills/external"],
            )

    def test_only_exact_reviewed_skill_rule_pairs_can_waive_high_risk(self) -> None:
        scanner = Path(__file__).resolve().parents[1] / "scripts" / "scan-skills.sh"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill_path = "plugins/example/skills/intentional"
            skill = root / skill_path
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\n"
                "name: intentional\n"
                "description: An intentionally credential-aware internal workflow.\n"
                "---\n"
            )
            self._git(root, "init")

            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_scanner = fake_bin / "skillspector"
            fake_scanner.write_text(
                "#!/usr/bin/env bash\n"
                "set -eu\n"
                "output=''\n"
                "previous=''\n"
                "for argument in \"$@\"; do\n"
                "  if [ \"$previous\" = '--output' ]; then output=\"$argument\"; fi\n"
                "  previous=\"$argument\"\n"
                "done\n"
                "printf '%s\\n' '{\"version\":\"2.1.0\",\"runs\":[{\"tool\":{\"driver\":{\"name\":\"skillspector\"}},\"results\":[{\"ruleId\":\"E1\",\"level\":\"error\",\"message\":{\"text\":\"expected internal transmission\"},\"locations\":[{\"physicalLocation\":{\"artifactLocation\":{\"uri\":\"SKILL.md\"}}}]}]}]}' > \"$output\"\n"
                "exit 1\n"
            )
            fake_scanner.chmod(0o755)
            allowlist = root / ".skillspector-allowlist.json"
            allowlist.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "reviewed_high_risk": [
                            {
                                "skill": skill_path,
                                "rules": ["E1"],
                                "rationale": "This internal workflow intentionally calls a fixed API.",
                            }
                        ],
                    }
                )
            )
            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
            environment["REPORT_DIR"] = str(root / "reports")

            reviewed = subprocess.run(
                ["bash", str(scanner), "all"],
                cwd=root,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(reviewed.returncode, 0, reviewed.stdout + reviewed.stderr)
            self.assertIn("REVIEWED HIGH RISK", reviewed.stdout)

            allowlist.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "reviewed_high_risk": [
                            {
                                "skill": skill_path,
                                "rules": ["PE3"],
                                "rationale": "A different reviewed rule does not waive E1.",
                            }
                        ],
                    }
                )
            )
            unexpected = subprocess.run(
                ["bash", str(scanner), "all"],
                cwd=root,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(unexpected.returncode, 1)
            self.assertIn("HIGH RISK", unexpected.stdout)

    LOGGING_SCANNER = (
        "#!/usr/bin/env bash\n"
        "set -eu\n"
        "printf '%s\\n' \"$2\" >> \"$SCAN_LOG\"\n"
        "output=''\n"
        "previous=''\n"
        "for argument in \"$@\"; do\n"
        "  if [ \"$previous\" = '--output' ]; then output=\"$argument\"; fi\n"
        "  previous=\"$argument\"\n"
        "done\n"
        "printf '{\"version\":\"2.1.0\",\"runs\":[{\"tool\":{\"driver\":{\"name\":\"skillspector\"}},\"results\":[]}]}\\n' > \"$output\"\n"
    )

    def _plugin(self, root: Path) -> Path:
        plugin = root / "plugins" / "engineering" / "example"
        (plugin / ".claude-plugin").mkdir(parents=True)
        (plugin / ".claude-plugin" / "plugin.json").write_text('{"name": "example"}\n')
        (plugin / "skills" / "example").mkdir(parents=True)
        (plugin / "skills" / "example" / "SKILL.md").write_text(
            "---\nname: example\ndescription: Example workflow.\n---\n"
        )
        (plugin / "scripts").mkdir()
        (plugin / "scripts" / "run.py").write_text("print('run')\n")
        (plugin / "src").mkdir()
        (plugin / "src" / "core.py").write_text("VALUE = 1\n")
        return plugin

    # Records the path SkillSpector was handed and every file under it, and reports one
    # finding per file, so a test sees both what was read and how locations are rewritten.
    FILE_LISTING_SCANNER = (
        "#!/usr/bin/env bash\n"
        "set -eu\n"
        "printf '%s\\n' \"$2\" >> \"$SCAN_LOG\"\n"
        "output=''\n"
        "previous=''\n"
        "for argument in \"$@\"; do\n"
        "  if [ \"$previous\" = '--output' ]; then output=\"$argument\"; fi\n"
        "  previous=\"$argument\"\n"
        "done\n"
        "files=\"$(cd \"$2\" && find . -type f | sed 's|^\\./||' | LC_ALL=C sort)\"\n"
        "printf '%s\\n' \"$files\" | sed 's|^|  |' >> \"$SCAN_LOG\"\n"
        "printf '%s\\n' \"$files\" | jq -R '{ruleId: \"TEST\", message: {text: \"seen\"}, "
        "locations: [{physicalLocation: {artifactLocation: {uri: .}}}]}' | "
        "jq -s '{version: \"2.1.0\", runs: [{tool: {driver: {name: \"skillspector\"}}, "
        "results: .}]}' > \"$output\"\n"
    )

    def _scan(
        self,
        root: Path,
        *arguments: str,
        extra_env: dict[str, str] | None = None,
        scanner_script: str | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], list[str]]:
        scanner = Path(__file__).resolve().parents[1] / "scripts" / "scan-skills.sh"
        fake_bin = root / "bin"
        fake_bin.mkdir(exist_ok=True)
        fake_scanner = fake_bin / "skillspector"
        fake_scanner.write_text(scanner_script or self.LOGGING_SCANNER)
        fake_scanner.chmod(0o755)
        scan_log = root / "scanned.txt"
        # The staging folder lands here, so a test can check that it is removed.
        stage_parent = root / "tmp"
        stage_parent.mkdir(exist_ok=True)
        environment = os.environ.copy()
        environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
        environment["SCAN_LOG"] = str(scan_log)
        environment["REPORT_DIR"] = str(root / "reports")
        environment["TMPDIR"] = str(stage_parent)
        environment.update(extra_env or {})
        completed = subprocess.run(
            ["bash", str(scanner), *arguments],
            cwd=root,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        scanned = scan_log.read_text().splitlines() if scan_log.exists() else []
        return completed, scanned

    def test_version_bump_alone_scans_only_the_manifest(self) -> None:
        # Every plugin change bumps plugin.json; that must not rescan the plugin's skills,
        # scripts or source.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = self._plugin(root)
            base = self._commit_all(root, "initial")
            (plugin / ".claude-plugin" / "plugin.json").write_text(
                '{"name": "example", "version": "1.0.1"}\n'
            )
            self._commit_all(root, "bump version")

            completed, scanned = self._scan(
                root, "changed", base, scanner_script=self.FILE_LISTING_SCANNER
            )
            leftover_stage = list((root / "tmp").iterdir())

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(len(scanned), 2, scanned)
        # An absolute staging path, not the plugin folder in the checkout.
        self.assertTrue(scanned[0].endswith("/plugins/engineering/example"), scanned)
        self.assertEqual(scanned[1:], ["  .claude-plugin/plugin.json"])
        self.assertEqual(leftover_stage, [])

    def test_changed_plugin_files_outside_every_folder_are_scanned_alone(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = self._plugin(root)
            base = self._commit_all(root, "initial")
            (plugin / "src" / "core.py").write_text("VALUE = 2\n")
            (plugin / ".mcp.json").write_text('{"mcpServers": {}}\n')
            self._commit_all(root, "change plugin source")

            completed, scanned = self._scan(
                root, "changed", base, scanner_script=self.FILE_LISTING_SCANNER
            )
            report = json.loads(
                (root / "reports" / "plugins_engineering_example.sarif").read_text()
            )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn(">> plugins/engineering/example (changed files", completed.stdout)
        self.assertEqual(scanned[1:], ["  .mcp.json", "  src/core.py"])
        # Finding locations point at the repository files, not the staging copies.
        self.assertEqual(
            sorted(
                result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
                for result in report["runs"][0]["results"]
            ),
            [
                "plugins/engineering/example/.mcp.json",
                "plugins/engineering/example/src/core.py",
            ],
        )

    def test_deleted_plugin_file_outside_every_folder_scans_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = self._plugin(root)
            base = self._commit_all(root, "initial")
            (plugin / "src" / "core.py").unlink()
            self._commit_all(root, "delete source")

            completed, scanned = self._scan(root, "changed", base)

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("No skills to scan", completed.stdout)
        self.assertEqual(scanned, [])

    @unittest.skipIf(os.name == "nt", "symlink creation requires extra Windows privileges")
    def test_changed_symlink_outside_every_folder_scans_the_plugin_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = self._plugin(root)
            base = self._commit_all(root, "initial")
            (plugin / "linked.md").symlink_to("src/core.py")
            (plugin / "src" / "core.py").write_text("VALUE = 2\n")
            (plugin / "skills" / "example" / "SKILL.md").write_text(
                "---\nname: example\ndescription: Changed workflow.\n---\n"
            )
            self._commit_all(root, "link, source and skill")

            completed, scanned = self._scan(root, "changed", base)

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        # Scanned in place, which already covers the changed skill and the staged source.
        self.assertEqual(scanned, ["plugins/engineering/example"])

    def test_single_plugin_root_still_scans_its_component_folders(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._plugin(root)
            self._git(root, "init")

            completed, scanned = self._scan(
                root, "all", extra_env={"SKILL_ROOT": "plugins/engineering/example"}
            )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(
            scanned,
            [
                "plugins/engineering/example/scripts",
                "plugins/engineering/example/skills/example",
            ],
        )

    def test_plugin_and_skill_changes_scan_the_skill_and_the_changed_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = self._plugin(root)
            base = self._commit_all(root, "initial")
            (plugin / "src" / "core.py").write_text("VALUE = 2\n")
            (plugin / "skills" / "example" / "SKILL.md").write_text(
                "---\nname: example\ndescription: Changed workflow.\n---\n"
            )
            self._commit_all(root, "change source and skill")

            completed, scanned = self._scan(
                root, "changed", base, scanner_script=self.FILE_LISTING_SCANNER
            )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        # The staged plugin holds only the changed source, so the skill is scanned on its own.
        self.assertEqual(len(scanned), 4, scanned)
        self.assertTrue(scanned[0].endswith("/plugins/engineering/example"), scanned)
        self.assertEqual(
            scanned[1:],
            ["  src/core.py", "plugins/engineering/example/skills/example", "  SKILL.md"],
        )

    def test_deleted_skill_does_not_scan_the_whole_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = self._plugin(root)
            (plugin / "skills" / "other").mkdir()
            (plugin / "skills" / "other" / "SKILL.md").write_text(
                "---\nname: other\ndescription: Other workflow.\n---\n"
            )
            base = self._commit_all(root, "initial")
            self._git(root, "rm", "-r", "--quiet", "plugins/engineering/example/skills/other")
            self._git(root, "commit", "-m", "delete a skill")

            completed, scanned = self._scan(root, "changed", base)

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(scanned, [])

    def test_checkout_root_can_be_the_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = self._plugin(root)
            for child in list(plugin.iterdir()):
                child.rename(root / child.name)
            shutil.rmtree(root / "plugins")
            base = self._commit_all(root, "initial")
            (root / "src" / "core.py").write_text("VALUE = 2\n")
            self._commit_all(root, "change source")

            completed, scanned = self._scan(
                root,
                "changed",
                base,
                extra_env={"SKILL_ROOT": "."},
                scanner_script=self.FILE_LISTING_SCANNER,
            )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn(">> . (changed files", completed.stdout)
        self.assertEqual(scanned[1:], ["  src/core.py"])

    def _commit_all(self, root: Path, message: str) -> str:
        if not (root / ".git").exists():
            self._git(root, "init")
            self._git(root, "config", "user.email", "tests@example.com")
            self._git(root, "config", "user.name", "Tests")
        self._git(root, "add", "-A")
        self._git(root, "commit", "-m", message)
        return self._git(root, "rev-parse", "HEAD").stdout.strip()

    @staticmethod
    def _git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
