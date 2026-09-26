#!/usr/bin/env python3
"""Fail when a plugin's files changed without its version changing.

Installs are cached per version, so a change merged without a bump never reaches a user who
already has that version. Only plugins the current change touches are checked.
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


def json_at(ref: str, path: str) -> object:
    """The parsed file at ``ref``, or None when ``ref`` has no such file."""
    done = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, text=True)
    if done.returncode:
        return None
    try:
        return json.loads(done.stdout)
    except json.JSONDecodeError:
        sys.exit(f"check-plugin-versions: {path} at {ref} is not valid JSON")


def version_at(ref: str, manifest: str) -> str | None:
    data = json_at(ref, manifest)
    value = data.get("version") if isinstance(data, dict) else None
    return value if isinstance(value, str) else None


def previous_version(ref: str, plugin: str) -> str | None:
    """The plugin's version at ``ref``. A plugin moved to another category folder is found
    by name in the catalog at ``ref``, since its new path does not exist there.
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
    if not isinstance(name, str):
        return None
    catalog = json_at(ref, ".claude-plugin/marketplace.json")
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
            continue
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
