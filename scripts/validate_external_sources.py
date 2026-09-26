#!/usr/bin/env python3
"""Fetch pinned external plugins and verify every referenced capability exists."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from generate_codex_marketplace import (  # type: ignore[import-not-found]
    GenerationError,
    parse_external_source,
)


class ValidationError(ValueError):
    """Raised when a pinned external source is unavailable or incomplete."""


@dataclass(frozen=True)
class ExternalPlugin:
    name: str
    repo: str
    sha: str
    source_path: str | None
    entrypoints: tuple[str, ...]
    adapted: bool


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"{path}: invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: expected an object")
    return value


def _external_plugins(root: Path) -> list[ExternalPlugin]:
    catalog = _load_object(root / ".claude-plugin" / "marketplace.json")
    override_document = _load_object(
        root / ".agents" / "plugins" / "source-overrides.json"
    )
    overrides = override_document.get("plugins")
    if override_document.get("version") != 2 or not isinstance(overrides, dict):
        raise ValidationError("source-overrides.json must contain a plugins object")
    result: list[ExternalPlugin] = []
    for entry in catalog.get("plugins", []):
        if not isinstance(entry, dict) or not isinstance(entry.get("source"), dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str):
            raise ValidationError(f"malformed external source: {name!r}")
        try:
            source = parse_external_source(entry["source"])
        except GenerationError as error:
            raise ValidationError(f"{name}: {error}") from error
        override = overrides.get(name)
        entrypoints: tuple[str, ...] = ()
        if override is not None:
            if (
                not isinstance(override, dict)
                or set(override) != {"source", "entrypoints"}
                or override.get("source") != "runtime-adapter"
                or not isinstance(override.get("entrypoints"), list)
            ):
                raise ValidationError(f"{name}: malformed compatibility override")
            entrypoints = tuple(str(item) for item in override["entrypoints"])
        result.append(
            ExternalPlugin(
                name,
                source.repo,
                source.sha,
                source.path,
                entrypoints,
                override is not None,
            )
        )
    if set(overrides) != {plugin.name for plugin in result if plugin.adapted}:
        raise ValidationError("source overrides contain missing or non-external plugins")
    return result


def _run(command: list[str], *, cwd: Path, attempts: int = 1) -> str:
    last_error = ""
    for attempt in range(attempts):
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if completed.returncode == 0:
            return completed.stdout.strip()
        last_error = completed.stderr.strip() or completed.stdout.strip()
        if attempt + 1 < attempts:
            time.sleep(1)
    raise ValidationError(f"{' '.join(command)} failed: {last_error}")


def _safe_source_root(checkout: Path, source_path: str | None) -> Path:
    if source_path is None:
        return checkout
    normalized = PurePosixPath(source_path)
    if normalized.is_absolute() or any(part in {"", ".", ".."} for part in normalized.parts):
        raise ValidationError(f"unsafe external source path: {source_path}")
    candidate = checkout.joinpath(*normalized.parts)
    if not candidate.resolve().is_relative_to(checkout.resolve()):
        raise ValidationError(f"external source path escapes checkout: {source_path}")
    return candidate


def _has_native_codex_capability(source_root: Path) -> bool:
    if (source_root / ".codex-plugin" / "plugin.json").is_file():
        return True
    if (source_root / ".mcp.json").is_file() or (source_root / "hooks" / "hooks.json").is_file():
        return True
    skills = source_root / "skills"
    return skills.is_dir() and any(
        child.is_dir() and (child / "SKILL.md").is_file() for child in skills.iterdir()
    )


def _validate_checkout(checkout: Path, plugins: list[ExternalPlugin]) -> int:
    head = _run(["git", "rev-parse", "HEAD"], cwd=checkout)
    if head != plugins[0].sha:
        raise ValidationError(f"{plugins[0].repo}: fetched {head}, expected {plugins[0].sha}")
    validated = 0
    for plugin in plugins:
        source_root = _safe_source_root(checkout, plugin.source_path)
        if not source_root.is_dir():
            raise ValidationError(f"{plugin.name}: source path does not exist: {plugin.source_path}")
        if plugin.adapted:
            for entrypoint in plugin.entrypoints:
                normalized = PurePosixPath(entrypoint)
                if normalized.is_absolute() or any(
                    part in {"", ".", ".."} for part in normalized.parts
                ):
                    raise ValidationError(
                        f"{plugin.name}: unsafe compatibility entrypoint {entrypoint}"
                    )
                candidate = source_root.joinpath(*normalized.parts)
                if not candidate.is_file() or not candidate.resolve().is_relative_to(
                    source_root.resolve()
                ):
                    raise ValidationError(f"{plugin.name}: missing pinned entrypoint {entrypoint}")
        elif not _has_native_codex_capability(source_root):
            raise ValidationError(f"{plugin.name}: direct source exposes no native Codex capability")
        validated += 1
    return validated


def _fetch_group(base: Path, key: tuple[str, str], plugins: list[ExternalPlugin]) -> int:
    repo, sha = key
    # Groups are per repo and commit, so two pins of one repo need two checkouts.
    checkout = base / f"{repo.replace('/', '--')}@{sha}"
    checkout.mkdir()
    _run(["git", "init", "--quiet"], cwd=checkout)
    _run(["git", "remote", "add", "origin", f"https://github.com/{repo}.git"], cwd=checkout)
    _run(["git", "fetch", "--quiet", "--depth=1", "origin", sha], cwd=checkout, attempts=3)
    _run(["git", "checkout", "--quiet", "--detach", "FETCH_HEAD"], cwd=checkout)
    return _validate_checkout(checkout, plugins)


def validate(root: Path, jobs: int) -> tuple[int, int]:
    plugins = _external_plugins(root.resolve())
    grouped: dict[tuple[str, str], list[ExternalPlugin]] = {}
    for plugin in plugins:
        grouped.setdefault((plugin.repo, plugin.sha), []).append(plugin)
    if not grouped:
        # A catalogue of local plugins only has nothing to fetch.
        return 0, 0
    with tempfile.TemporaryDirectory(prefix="external-plugin-validation-") as directory:
        base = Path(directory)
        validated = 0
        with ThreadPoolExecutor(max_workers=min(jobs, len(grouped))) as executor:
            futures = {
                executor.submit(_fetch_group, base, key, group): key
                for key, group in grouped.items()
            }
            for future in as_completed(futures):
                try:
                    validated += future.result()
                except Exception as error:
                    for pending in futures:
                        pending.cancel()
                    if isinstance(error, ValidationError):
                        raise
                    raise ValidationError(f"{futures[future][0]}: {error}") from error
    return validated, len(grouped)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    try:
        plugins, repositories = validate(args.root, args.jobs)
    except (ValidationError, OSError, UnicodeError, subprocess.SubprocessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"Validated {plugins} external plugins from {repositories} pinned repositories.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
