#!/usr/bin/env python3
"""Fetch pinned external plugins and verify every referenced capability exists."""

from __future__ import annotations

import argparse
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from generate_codex_marketplace import (  # type: ignore[import-not-found]
    GenerationError,
    _external_source_overrides,
    _marketplace_entries,
    parse_external_source,
)
from materialize_pinned_upstream import _build_checkout  # type: ignore[import-not-found]


@dataclass(frozen=True)
class ExternalPlugin:
    name: str
    repo: str
    sha: str
    source_path: str | None
    # Files a runtime adapter reads from the checkout; empty when Codex loads the plugin natively.
    entrypoints: tuple[str, ...]


def _external_plugins(root: Path) -> list[ExternalPlugin]:
    overrides = _external_source_overrides(root)
    result: list[ExternalPlugin] = []
    for entry in _marketplace_entries(root):
        if not isinstance(entry.get("source"), dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str):
            raise GenerationError(f"malformed external source: {name!r}")
        try:
            source = parse_external_source(entry["source"])
        except GenerationError as error:
            raise GenerationError(f"{name}: {error}") from error
        override = overrides.get(name)
        entrypoints = tuple(override["entrypoints"]) if override else ()
        result.append(ExternalPlugin(name, source.repo, source.sha, source.path, entrypoints))
    if set(overrides) - {plugin.name for plugin in result}:
        raise GenerationError("source overrides name plugins that are not external")
    return result


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
    for plugin in plugins:
        # The catalog path is already a safe relative path, but the upstream can symlink it away.
        source_root = checkout if plugin.source_path is None else checkout / plugin.source_path
        if not source_root.resolve().is_relative_to(checkout.resolve()):
            raise GenerationError(f"external source path escapes checkout: {plugin.source_path}")
        if not source_root.is_dir():
            raise GenerationError(
                f"{plugin.name}: source path does not exist: {plugin.source_path}"
            )
        for entrypoint in plugin.entrypoints:
            candidate = source_root / entrypoint
            if not candidate.is_file() or not candidate.resolve().is_relative_to(
                source_root.resolve()
            ):
                raise GenerationError(f"{plugin.name}: missing pinned entrypoint {entrypoint}")
        if not plugin.entrypoints and not _has_native_codex_capability(source_root):
            raise GenerationError(
                f"{plugin.name}: direct source exposes no native Codex capability"
            )
    return len(plugins)


def _fetch_group(base: Path, repo: str, sha: str, plugins: list[ExternalPlugin]) -> int:
    checkout = _build_checkout(
        parent=base,
        ref=sha,
        remote_url=f"https://github.com/{repo}.git",
        fetch_attempts=3,
        timeout=120,
    )
    return _validate_checkout(checkout, plugins)


def validate(root: Path, jobs: int) -> tuple[int, int]:
    grouped: dict[tuple[str, str], list[ExternalPlugin]] = {}
    for plugin in _external_plugins(root.resolve()):
        grouped.setdefault((plugin.repo, plugin.sha), []).append(plugin)
    if not grouped:
        # ThreadPoolExecutor rejects zero workers.
        return 0, 0
    with tempfile.TemporaryDirectory(prefix="external-plugin-validation-") as directory:
        validated = 0
        with ThreadPoolExecutor(max_workers=min(jobs, len(grouped))) as executor:
            futures = {
                executor.submit(_fetch_group, Path(directory), repo, sha, group): repo
                for (repo, sha), group in grouped.items()
            }
            for future in as_completed(futures):
                try:
                    validated += future.result()
                except Exception as error:
                    for pending in futures:
                        pending.cancel()
                    if isinstance(error, GenerationError):
                        raise
                    raise GenerationError(f"{futures[future]}: {error}") from error
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
    except (GenerationError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"Validated {plugins} external plugins from {repositories} pinned repositories.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
