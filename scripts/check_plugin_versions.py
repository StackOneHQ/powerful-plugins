#!/usr/bin/env python3
"""Fail when a plugin's files changed without its version changing.

The plugin cache is keyed by version: it installs to
``~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/``. A user who already holds
``1.0.0`` keeps the copy they have, so a change merged without a version bump reaches nobody.
A plugin that collects many commits at one version leaves installed copies silently missing
whole scripts and reference files.

Only plugins touched by the current change are checked, so the existing drift across the repo
does not block unrelated work.

    python scripts/check_plugin_versions.py --base origin/main
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

MANIFEST = ".claude-plugin/plugin.json"
# Generated mirrors are rewritten from the sources, so a change confined to them is not a
# change to what the plugin does.
GENERATED = (".codex/", ".codex-plugin/", ".agents/")


def git(*args: str) -> str:
    done = subprocess.run(["git", *args], capture_output=True, text=True)
    if done.returncode:
        sys.exit(f"check-plugin-versions: git {' '.join(args)} failed:\n{done.stderr.strip()}")
    return done.stdout.strip()


def version_at(ref: str, manifest: str) -> str | None:
    done = subprocess.run(["git", "show", f"{ref}:{manifest}"], capture_output=True, text=True)
    if done.returncode:
        return None  # the plugin is new on this branch
    try:
        data = json.loads(done.stdout)
    except json.JSONDecodeError:
        sys.exit(f"check-plugin-versions: {manifest} at {ref} is not valid JSON")
    value = data.get("version") if isinstance(data, dict) else None
    return value if isinstance(value, str) else None


def previous_version(ref: str, plugin: str) -> str | None:
    """Return the plugin's version at ``ref``, following a move between category folders.

    A plugin moved to another category reads as new at its new path, so look it up by name
    in the marketplace catalog at ``ref`` and read the manifest from its old location.
    """
    manifest = f"{plugin}/{MANIFEST}"
    before = version_at(ref, manifest)
    if before is not None:
        return before
    try:
        current = json.loads(Path(manifest).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    name = current.get("name") if isinstance(current, dict) else None
    done = subprocess.run(
        ["git", "show", f"{ref}:.claude-plugin/marketplace.json"], capture_output=True, text=True
    )
    if done.returncode or not isinstance(name, str):
        return None
    try:
        catalog = json.loads(done.stdout)
    except json.JSONDecodeError:
        sys.exit(f"check-plugin-versions: .claude-plugin/marketplace.json at {ref} is not valid JSON")
    for entry in catalog.get("plugins", []) if isinstance(catalog, dict) else []:
        if not isinstance(entry, dict) or entry.get("name") != name:
            continue
        source = entry.get("source")
        if isinstance(source, str) and source.startswith("./"):
            moved = version_at(ref, f"{source[2:].rstrip('/')}/{MANIFEST}")
            if moved is not None:
                return moved
        version = entry.get("version")
        return version if isinstance(version, str) else None
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="origin/main", help="ref to compare against")
    args = ap.parse_args()

    merge_base = git("merge-base", args.base, "HEAD")
    changed = [p for p in git("diff", "--name-only", merge_base, "HEAD").splitlines() if p]

    touched: dict[str, list[str]] = {}
    for path in changed:
        parts = path.split("/")
        if len(parts) < 3 or parts[0] != "plugins":
            continue
        plugin = "/".join(parts[:3])
        rest = path[len(plugin) + 1 :]
        if rest.startswith(GENERATED):
            continue
        touched.setdefault(plugin, []).append(path)

    stale = []
    for plugin, files in sorted(touched.items()):
        manifest = f"{plugin}/{MANIFEST}"
        if not Path(manifest).exists():
            continue  # not a plugin root
        before, after = previous_version(merge_base, plugin), version_at("HEAD", manifest)
        if before is None:
            continue  # new plugin; its first version is whatever it declares
        if before == after:
            stale.append((plugin, after, files))

    if not stale:
        print(f"check-plugin-versions: {len(touched)} plugin(s) touched, all versioned correctly.")
        return 0

    print("check-plugin-versions: these plugins changed but kept their version.\n")
    print("The cache is keyed by version, so a user who already has this one keeps the copy")
    print("they have and never receives the change. Bump the version in each manifest.\n")
    for plugin, version, files in stale:
        print(f"  {plugin}  (still {version})")
        for f in files[:4]:
            print(f"      {f}")
        if len(files) > 4:
            print(f"      ... and {len(files) - 4} more")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
