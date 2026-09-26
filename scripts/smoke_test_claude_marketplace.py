#!/usr/bin/env python3
"""Install every marketplace plugin with Claude Code in an isolated configuration."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from generate_codex_marketplace import (  # type: ignore[import-not-found]
    CLAUDE_MARKETPLACE,
    GenerationError,
    _load_json,
    parse_external_source,
)


class SmokeError(RuntimeError):
    """Raised when the real Claude CLI rejects or cannot inspect a plugin."""


MARKETPLACE_NAME = "powerful-plugins"
COMPONENT_COUNT = re.compile(r"^\s*(?:Skills|Agents|Hooks|MCP servers|LSP servers) \((\d+)\)", re.M)


def _run(claude: Path, arguments: list[str], *, cwd: Path, config: Path) -> str:
    environment = {
        **os.environ,
        "CLAUDE_CONFIG_DIR": str(config),
        "NO_COLOR": "1",
        "GIT_CONFIG_COUNT": "2",
        "GIT_CONFIG_KEY_0": "url.https://github.com/.insteadOf",
        "GIT_CONFIG_VALUE_0": "git@github.com:",
        "GIT_CONFIG_KEY_1": "url.https://github.com/.insteadOf",
        "GIT_CONFIG_VALUE_1": "ssh://git@github.com/",
    }
    completed = subprocess.run(
        [str(claude), *arguments],
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=240,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise SmokeError(f"claude {' '.join(arguments)} failed: {detail}")
    return completed.stdout


def _plugin_names(root: Path) -> list[str]:
    try:
        value = _load_json(root / CLAUDE_MARKETPLACE)
    except GenerationError as error:
        raise SmokeError(f"unable to read Claude marketplace: {error}") from error
    if value.get("name") != MARKETPLACE_NAME:
        raise SmokeError(
            f"Claude marketplace identity changed: expected {MARKETPLACE_NAME!r}, "
            f"found {value.get('name')!r}"
        )
    if not isinstance(value.get("plugins"), list):
        raise SmokeError("Claude marketplace has an invalid top-level shape")

    names: list[str] = []
    for entry in value["plugins"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            raise SmokeError("Claude marketplace contains an invalid plugin name")
        name = entry["name"]
        if name in names:
            raise SmokeError(f"Claude marketplace contains duplicate plugin {name!r}")
        source = entry.get("source")
        if isinstance(source, str):
            if not source.startswith("./") or "\\" in source or ".." in Path(source).parts:
                raise SmokeError(f"{name}: invalid local Claude source")
        elif isinstance(source, dict):
            try:
                parse_external_source(source)
            except GenerationError as error:
                raise SmokeError(f"{name}: {error}") from error
        else:
            raise SmokeError(f"{name}: invalid Claude source")
        names.append(name)
    return names


def smoke(root: Path, claude: Path) -> int:
    root = root.resolve()
    plugin_ids = [f"{name}@{MARKETPLACE_NAME}" for name in _plugin_names(root)]
    expected_ids = set(plugin_ids)

    with tempfile.TemporaryDirectory(prefix="claude-marketplace-smoke-") as directory:
        config = Path(directory)
        _run(claude, ["plugin", "marketplace", "add", str(root)], cwd=root, config=config)
        for plugin_id in plugin_ids:
            install = ["plugin", "install", plugin_id, "--scope", "user"]
            _run(claude, install, cwd=root, config=config)

        try:
            listing = json.loads(
                _run(claude, ["plugin", "list", "--json"], cwd=root, config=config)
            )
        except json.JSONDecodeError as error:
            raise SmokeError(f"Claude plugin list returned invalid JSON: {error}") from error
        if not isinstance(listing, list):
            raise SmokeError("Claude plugin list returned an invalid top-level shape")
        actual_ids: set[str] = set()
        for entry in listing:
            if not isinstance(entry, dict) or not entry.get("enabled"):
                continue
            listed_id = entry.get("id")
            if not isinstance(listed_id, str):
                raise SmokeError("Claude plugin list contains an invalid enabled plugin ID")
            actual_ids.add(listed_id)
        if actual_ids != expected_ids:
            missing = sorted(expected_ids - actual_ids)
            unexpected = sorted(actual_ids - expected_ids)
            raise SmokeError(
                f"Claude installed plugin set differs (missing={missing}, unexpected={unexpected})"
            )

        for plugin_id in sorted(expected_ids):
            details = _run(claude, ["plugin", "details", plugin_id], cwd=root, config=config)
            if f"Source: {plugin_id}" not in details:
                raise SmokeError(f"{plugin_id}: Claude details omitted the installed source")
            # An install can succeed and still load nothing, for example when a source
            # resolves to a repository root instead of the plugin's own folder.
            counts = [int(count) for count in COMPONENT_COUNT.findall(details)]
            if not counts:
                raise SmokeError(f"{plugin_id}: Claude details listed no component inventory")
            if sum(counts) == 0:
                raise SmokeError(f"{plugin_id}: installed but exposes no skills, agents or hooks")
    return len(expected_ids)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--claude", type=Path, default=Path("claude"))
    args = parser.parse_args()
    try:
        count = smoke(args.root, args.claude)
    except (SmokeError, OSError, UnicodeError, subprocess.SubprocessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"Claude installed and inspected all {count} marketplace plugins.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
