#!/usr/bin/env python3
"""Install every marketplace plugin with Codex in an isolated CODEX_HOME and assert discovery."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any


class SmokeError(RuntimeError):
    """Raised when the real Codex CLI rejects or cannot discover a plugin."""


BAD_DIAGNOSTIC = re.compile(
    r"unsupported hook|unknown hook|failed to (?:load|parse)|invalid plugin|invalid manifest",
    re.IGNORECASE,
)


def _environment(home: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment["CODEX_HOME"] = str(home)
    return environment


def _run(codex: Path, arguments: list[str], *, cwd: Path, home: Path) -> str:
    completed = subprocess.run(
        [str(codex), *arguments],
        cwd=cwd,
        env=_environment(home),
        check=False,
        capture_output=True,
        text=True,
        timeout=240,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise SmokeError(f"codex {' '.join(arguments)} failed: {detail}")
    if BAD_DIAGNOSTIC.search(completed.stderr):
        raise SmokeError(
            f"codex {' '.join(arguments)} emitted an incompatibility diagnostic: "
            f"{completed.stderr.strip()}"
        )
    return completed.stdout


def _catalog(root: Path) -> tuple[str, list[tuple[str, str | None]]]:
    try:
        value = json.loads((root / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SmokeError(f"unable to read Codex marketplace: {error}") from error
    if not isinstance(value, dict) or not isinstance(value.get("name"), str) or not isinstance(value.get("plugins"), list):
        raise SmokeError("Codex marketplace has an invalid top-level shape")
    plugins: list[tuple[str, str | None]] = []
    for entry in value["plugins"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            raise SmokeError("Codex marketplace contains an invalid plugin name")
        explicit_skill: str | None = None
        source = entry.get("source")
        if isinstance(source, dict) and source.get("source") == "local":
            source_path = source.get("path")
            if not isinstance(source_path, str) or not source_path.startswith("./"):
                raise SmokeError(f"{entry['name']}: invalid local source")
            plugin_root = root / source_path[2:]
            manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as error:
                raise SmokeError(
                    f"{entry['name']}: unable to read Codex manifest: {error}"
                ) from error
            skills_reference = manifest.get("skills")
            if skills_reference is not None:
                if (
                    not isinstance(skills_reference, str)
                    or not skills_reference.startswith("./")
                    or "\\" in skills_reference
                    or ".." in Path(skills_reference).parts
                ):
                    raise SmokeError(f"{entry['name']}: invalid skills reference")
                skills = plugin_root / skills_reference[2:]
                if not skills.resolve().is_relative_to(plugin_root.resolve()):
                    raise SmokeError(f"{entry['name']}: escaping skills reference")
                candidates = sorted(
                    child.name
                    for child in skills.iterdir()
                    if child.is_dir() and (child / "SKILL.md").is_file()
                )
                if candidates:
                    explicit_skill = candidates[0]
        plugins.append((entry["name"], explicit_skill))
    return value["name"], plugins


def _all_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [text for item in value for text in _all_strings(item)]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _all_strings(item)]
    return []


def _discovered_text(prompt: Any) -> str:
    """Prompt text without user-role messages, whose project context (AGENTS.md, the working
    directory) can name a plugin Codex never discovered. Skill listings are developer-role.
    """
    items = prompt if isinstance(prompt, list) else [prompt]
    return "\n".join(
        text
        for item in items
        if not (isinstance(item, dict) and item.get("role") == "user")
        for text in _all_strings(item)
    )


def _response(stream: Any, request_id: int) -> dict[str, Any]:
    for line in stream:
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(message, dict) and message.get("id") == request_id:
            return message
    return {}


def _enabled_skills(codex: Path, *, cwd: Path, home: Path, timeout: float = 240) -> set[str]:
    """Skills the Codex app server resolved. An explicit-only skill is absent from the prompt's
    skill list, and `debug prompt-input` does not expand a `$plugin:skill` mention.
    """
    requests: list[dict[str, Any]] = [
        {"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "smoke", "version": "0"}}},
        {"method": "initialized"},
        {"id": 2, "method": "skills/list", "params": {"cwds": [str(cwd)], "forceReload": True}},
    ]
    message: dict[str, Any] = {}
    with tempfile.TemporaryFile("w+") as errors:
        try:
            with subprocess.Popen(
                [str(codex), "app-server"],
                cwd=cwd,
                env=_environment(home),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=errors,
                text=True,
            ) as process:
                timer = threading.Timer(timeout, process.kill)
                timer.start()
                try:
                    if process.stdin is None or process.stdout is None:
                        raise SmokeError("codex app-server did not expose its standard streams")
                    for request in requests:
                        process.stdin.write(json.dumps(request) + "\n")
                        process.stdin.flush()
                        if "id" not in request:
                            continue
                        message = _response(process.stdout, request["id"])
                        if not message:
                            raise SmokeError(
                                f"codex app-server gave no answer to {request['method']}"
                            )
                        if "error" in message:
                            raise SmokeError(
                                f"codex app-server {request['method']} failed: {message['error']}"
                            )
                finally:
                    timer.cancel()
                    process.kill()
        except (SmokeError, OSError) as error:
            errors.seek(0)
            detail = errors.read().strip()[-2000:]
            report = f"{error}\ncodex app-server stderr:\n{detail}" if detail else str(error)
            raise SmokeError(report) from error
    result = message.get("result")
    entries = result.get("data") if isinstance(result, dict) else None
    if not isinstance(entries, list):
        raise SmokeError("codex app-server skills/list returned an invalid shape")
    return {
        skill["name"]
        for entry in entries
        if isinstance(entry, dict)
        for skill in entry.get("skills") or []
        if isinstance(skill, dict) and isinstance(skill.get("name"), str) and skill.get("enabled")
    }


def smoke(root: Path, codex: Path, batch_size: int) -> int:
    root = root.resolve()
    marketplace, plugin_specs = _catalog(root)
    expected_names = [name for name, _ in plugin_specs]
    explicit_skills = dict(plugin_specs)
    with tempfile.TemporaryDirectory(prefix="codex-marketplace-smoke-") as directory:
        home = Path(directory)
        _run(codex, ["plugin", "marketplace", "add", str(root), "--json"], cwd=root, home=home)
        listing = json.loads(
            _run(
                codex,
                ["plugin", "list", "--marketplace", marketplace, "--available", "--json"],
                cwd=root,
                home=home,
            )
        )
        available = listing.get("available") if isinstance(listing, dict) else None
        actual_names = [item.get("name") for item in available or [] if isinstance(item, dict)]
        if actual_names != expected_names:
            raise SmokeError("Codex available-plugin list does not match the generated catalog")

        for offset in range(0, len(expected_names), batch_size):
            batch = expected_names[offset : offset + batch_size]
            for name in batch:
                _run(
                    codex,
                    ["plugin", "add", f"{name}@{marketplace}", "--json"],
                    cwd=root,
                    home=home,
                )
            try:
                prompt = json.loads(_run(codex, ["debug", "prompt-input"], cwd=root, home=home))
            except json.JSONDecodeError as error:
                raise SmokeError(f"Codex prompt discovery returned invalid JSON: {error}") from error
            prompt_text = _discovered_text(prompt)
            missing = [name for name in batch if f"{name}:" not in prompt_text]
            for name in missing:
                if explicit_skills.get(name) is None:
                    raise SmokeError(
                        f"{name}: direct source exposes no model-visible skill namespace"
                    )
            enabled = _enabled_skills(codex, cwd=root, home=home) if missing else set()
            for name in missing:
                skill = explicit_skills[name]
                if f"{name}:{skill}" not in enabled:
                    raise SmokeError(
                        f"{name}: explicit skill ${name}:{skill} was not loaded by Codex"
                    )
            for name in reversed(batch):
                _run(
                    codex,
                    ["plugin", "remove", f"{name}@{marketplace}", "--json"],
                    cwd=root,
                    home=home,
                )
    return len(expected_names)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--codex", type=Path, default=Path("codex"))
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    try:
        count = smoke(args.root, args.codex, args.batch_size)
    except (SmokeError, OSError, UnicodeError, subprocess.SubprocessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"Codex installed and discovered all {count} marketplace plugins.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
