#!/usr/bin/env python3
"""Validate every generated Codex plugin and both marketplace catalogs."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml
from generate_codex_marketplace import (  # type: ignore[import-not-found]
    CODEX_MARKETPLACE,
    GENERATED_MARKER,
    SKILL_DESCRIPTION_LIMIT,
    SKILL_NAME_PATTERN,
    GenerationError,
    _is_semver,
    _load_json,
    _marketplace_entries,
    _read_text,
    convert_source,
    split_frontmatter,
)

SUPPORTED_HOOK_EVENTS = {
    "PermissionRequest",
    "PostCompact",
    "PostToolUse",
    "PreCompact",
    "PreToolUse",
    "SessionEnd",
    "SessionStart",
    "Stop",
    "SubagentStart",
    "SubagentStop",
    "UserPromptSubmit",
}
FORBIDDEN_GENERATED_TOKENS = (
    "$ARGUMENTS",
    "AskUserQuestion",
    "CODEX_PLUGIN_ROOT",
    "Task tool",
)
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def _contained_file(plugin: Path, reference: object, label: str) -> Path:
    if not isinstance(reference, str) or not reference.startswith("./"):
        raise GenerationError(f"{plugin}: {label} must be a ./-prefixed path")
    candidate = plugin / reference[2:]
    if candidate.is_symlink() or not candidate.is_file():
        raise GenerationError(f"{plugin}: missing regular {label} file: {reference}")
    if not candidate.resolve().is_relative_to(plugin.resolve()):
        raise GenerationError(f"{plugin}: {label} escapes plugin root: {reference}")
    return candidate


def _validate_skill(path: Path) -> None:
    text = _read_text(path)
    metadata, _ = split_frontmatter(text, path)
    name = metadata.get("name")
    description = metadata.get("description")
    if not isinstance(name, str) or not SKILL_NAME_PATTERN.fullmatch(name) or len(name) > 64:
        raise GenerationError(f"{path}: invalid Agent Skills name")
    if path.parent.name != name:
        raise GenerationError(f"{path}: name must match its parent directory")
    if not isinstance(description, str) or not description.strip() or len(description) > SKILL_DESCRIPTION_LIMIT:
        raise GenerationError(f"{path}: description must contain 1-1024 characters")
    if GENERATED_MARKER in text:
        for token in FORBIDDEN_GENERATED_TOKENS:
            if token in text:
                raise GenerationError(f"{path}: generated adapter retains {token!r}")
    policy = path.parent / "agents" / "openai.yaml"
    if policy.is_file():
        try:
            value = yaml.safe_load(policy.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as error:
            raise GenerationError(f"{policy}: invalid policy YAML: {error}") from error
        if not isinstance(value, dict) or not isinstance(value.get("interface"), dict):
            raise GenerationError(f"{policy}: missing interface mapping")
        policy_value = value.get("policy", {})
        if not isinstance(policy_value, dict):
            raise GenerationError(f"{policy}: policy must be a mapping")
        invocation = policy_value.get("allow_implicit_invocation", True)
        if not isinstance(invocation, bool):
            raise GenerationError(f"{policy}: allow_implicit_invocation must be boolean")


def _validate_hooks(plugin: Path, manifest: dict[str, Any]) -> bool:
    reference = manifest.get("hooks")
    if reference is None:
        default = plugin / "hooks" / "hooks.json"
        if not default.is_file():
            return False
        path = default
    elif isinstance(reference, str):
        path = _contained_file(plugin, reference, "hooks")
    else:
        raise GenerationError(f"{plugin}: this validator requires file-backed hooks")
    config = _load_json(path)
    hooks = config.get("hooks")
    if not isinstance(hooks, dict) or not hooks:
        raise GenerationError(f"{path}: hooks must be a non-empty object")
    for event, groups in hooks.items():
        if event not in SUPPORTED_HOOK_EVENTS:
            raise GenerationError(f"{path}: unsupported Codex hook event {event!r}")
        if not isinstance(groups, list) or not groups:
            raise GenerationError(f"{path}: {event} must contain matcher groups")
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                raise GenerationError(f"{path}: malformed {event} matcher group")
            for handler in group["hooks"]:
                if not isinstance(handler, dict) or handler.get("type") != "command":
                    raise GenerationError(f"{path}: only command hook handlers are supported")
                if not isinstance(handler.get("command"), str) or not handler["command"].strip():
                    raise GenerationError(f"{path}: hook command must be non-empty")
                if "async" in handler:
                    raise GenerationError(f"{path}: async command hooks are unsupported by Codex")
                timeout = handler.get("timeout")
                if timeout is not None and (not isinstance(timeout, int) or timeout <= 0):
                    raise GenerationError(f"{path}: timeout must be a positive integer")
                if event == "SessionEnd" and isinstance(timeout, int) and timeout > 3:
                    raise GenerationError(f"{path}: SessionEnd timeout cannot exceed 3 seconds")
                if "CODEX_PLUGIN_ROOT" in handler["command"]:
                    raise GenerationError(f"{path}: Codex exposes PLUGIN_ROOT, not CODEX_PLUGIN_ROOT")
    return True


def _validate_mcp(plugin: Path, manifest: dict[str, Any]) -> bool:
    reference = manifest.get("mcpServers")
    if reference is None:
        return False
    config = _load_json(_contained_file(plugin, reference, "MCP config")) if isinstance(reference, str) else {"mcpServers": reference}
    servers = config.get("mcpServers")
    if not isinstance(servers, dict) or not servers:
        raise GenerationError(f"{plugin}: mcpServers must be a non-empty object")
    for name, server in servers.items():
        if not isinstance(name, str) or not isinstance(server, dict):
            raise GenerationError(f"{plugin}: invalid MCP server entry")
        if server.get("type") == "http":
            url = server.get("url")
            if not isinstance(url, str) or not url.startswith("https://"):
                raise GenerationError(f"{plugin}: remote MCP URL must use HTTPS")
        else:
            command = server.get("command")
            args = server.get("args", [])
            if not isinstance(command, str) or not command or not isinstance(args, list):
                raise GenerationError(f"{plugin}: invalid stdio MCP command")
            if command in {"npm", "npx"}:
                raise GenerationError(f"{plugin}: use pinned pnpm/uvx MCP launchers, not {command}")
            if any(not isinstance(arg, str) or "@latest" in arg for arg in args):
                raise GenerationError(f"{plugin}: MCP arguments must be strings with pinned versions")
    return True


def _validate_plugin(plugin: Path, expected_name: str) -> None:
    manifest_path = plugin / ".codex-plugin" / "plugin.json"
    manifest = _load_json(manifest_path)
    if manifest.get("name") != expected_name:
        raise GenerationError(f"{manifest_path}: manifest name does not match catalog")
    if not isinstance(manifest.get("version"), str) or not _is_semver(manifest["version"]):
        raise GenerationError(f"{manifest_path}: invalid semantic version")
    if not isinstance(manifest.get("description"), str) or not manifest["description"].strip():
        raise GenerationError(f"{manifest_path}: missing description")
    skill_files: list[Path] = []
    skills_reference = manifest.get("skills")
    if skills_reference is not None:
        if skills_reference not in {"./skills/", "./.codex/skills/"}:
            raise GenerationError(
                f"{manifest_path}: skills must use ./skills/ or ./.codex/skills/"
            )
        skills_root = plugin / skills_reference[2:]
        if (
            skills_root.is_symlink()
            or not skills_root.is_dir()
            or not skills_root.resolve().is_relative_to(plugin.resolve())
        ):
            raise GenerationError(f"{manifest_path}: unsafe skills directory")
        skill_files = sorted(skills_root.rglob("SKILL.md"))
        if not skill_files:
            raise GenerationError(f"{manifest_path}: skills path has no SKILL.md")
        if not any((child / "SKILL.md").is_file() for child in skills_root.iterdir() if child.is_dir()):
            raise GenerationError(f"{manifest_path}: no top-level installable skill directory")
        for skill in skill_files:
            if skill.is_symlink() or not skill.resolve().is_relative_to(plugin.resolve()):
                raise GenerationError(f"{skill}: symlinked or escaping skill")
            _validate_skill(skill)
    has_mcp = _validate_mcp(plugin, manifest)
    has_hooks = _validate_hooks(plugin, manifest)
    has_apps = "apps" in manifest
    if has_apps and not _load_json(_contained_file(plugin, manifest["apps"], "app config")):
        raise GenerationError(f"{plugin}: app config must not be empty")
    if not (skill_files or has_mcp or has_hooks or has_apps):
        raise GenerationError(f"{plugin}: plugin exposes no Codex capability")


def validate(root: Path) -> tuple[int, int]:
    root = root.resolve()
    claude_entries = _marketplace_entries(root)
    codex_entries = _load_json(root / CODEX_MARKETPLACE).get("plugins")
    if not isinstance(codex_entries, list):
        raise GenerationError("Codex marketplace must contain a plugins array")
    claude_names = [entry.get("name") for entry in claude_entries]
    codex_names = [entry.get("name") for entry in codex_entries if isinstance(entry, dict)]
    if claude_names != codex_names or len(claude_names) != len(set(claude_names)):
        raise GenerationError("Claude and Codex catalogs must have identical unique names")
    external = 0
    codex_by_name = {
        entry.get("name"): entry for entry in codex_entries if isinstance(entry, dict)
    }
    for entry in claude_entries:
        source = entry.get("source")
        if isinstance(source, dict):
            external += 1
            name = entry.get("name")
            if not isinstance(name, str):
                raise GenerationError("Claude external source must have a name")
            try:
                expected_codex = convert_source(source)
            except GenerationError as error:
                raise GenerationError(f"{name}: {error}") from error
            codex_source = codex_by_name[name].get("source")
            if (
                isinstance(codex_source, dict)
                and codex_source.get("source") != "local"
                and codex_source != expected_codex
            ):
                raise GenerationError(
                    f"{name}: Codex source does not match the pinned Claude source; "
                    "rerun the generator"
                )
    local = 0
    for entry in codex_entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("source"), dict):
            raise GenerationError("Codex catalog entries must contain source objects")
        source = entry["source"]
        if source.get("source") != "local":
            ref = source.get("ref")
            if not SHA_PATTERN.fullmatch(str(ref or "")):
                raise GenerationError(f"{entry.get('name')}: direct Codex source must pin a commit SHA")
            continue
        local += 1
        reference = source.get("path")
        if not isinstance(reference, str) or not reference.startswith("./"):
            raise GenerationError(f"{entry.get('name')}: invalid local plugin source")
        plugin = root / reference[2:]
        if plugin.is_symlink() or not plugin.is_dir() or not plugin.resolve().is_relative_to(root):
            raise GenerationError(f"{entry.get('name')}: unsafe local plugin source")
        _validate_plugin(plugin.resolve(), str(entry.get("name")))
    return local, external


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        local, external = validate(args.root)
    except (GenerationError, OSError, UnicodeError, yaml.YAMLError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"Validated {local} local Codex packages and {external} pinned external entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
