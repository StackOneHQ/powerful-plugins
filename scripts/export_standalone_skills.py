#!/usr/bin/env python3
"""Safely export self-contained marketplace skills for standalone Codex use."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from scripts.generate_codex_marketplace import (
    SKILL_DESCRIPTION_LIMIT,
    SKILL_NAME_PATTERN,
    GenerationError,
    _read_text,
    _short_description,
    _text_has_generated_marker,
    split_claude_frontmatter,
)

PLUGIN_DEPENDENCY_PATTERNS = {
    "plugin-root environment variable": re.compile(
        r"(?:CLAUDE|CODEX|PLUGIN)_PLUGIN_ROOT|\$\{?PLUGIN_ROOT"
    ),
    "parent-directory reference": re.compile(r"(?<![\w.])\.\./"),
    "plugin scripts reference": re.compile(r"(?<![\w.])/scripts/"),
    "Claude agent reference": re.compile(r"(?:^|[\s`])/?agents/", re.MULTILINE),
    "external skill loader": re.compile(r"Load skill:", re.IGNORECASE),
}

# In a plugin, a bare scripts/, site/ or src/ path resolves from the plugin root, not the skill.
BARE_RELATIVE_REFERENCE = re.compile(r"(?<![\w./$}~@-])(?:\./)?(scripts|site|src)/")


@dataclass(frozen=True)
class SkillSource:
    name: str
    path: Path
    metadata: dict[str, Any]
    body: str

    @property
    def portable_description(self) -> str:
        return _short_description(self.metadata["description"], SKILL_DESCRIPTION_LIMIT)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skills", nargs="*", help="Exact skill names to export")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--dest", type=Path)
    destination.add_argument(
        "--global", dest="global_destination", action="store_true",
        help="Export into $HOME/.agents/skills",
    )
    parser.add_argument("--all", action="store_true", help="Export every standalone skill")
    parser.add_argument(
        "--allow-large-catalog",
        action="store_true",
        help="Allow --all to exceed Codex's 8,000-character skill-list guidance",
    )
    parser.add_argument("--force", action="store_true", help="Replace existing skill directories")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report without writing")
    parser.add_argument("--list", action="store_true", help="List exportable skill names")
    return parser


def _reject_symlinks(path: Path, stop: Path) -> None:
    current = path
    while current != stop and current.is_relative_to(stop):
        if current.is_symlink():
            raise GenerationError(f"refusing symlinked path: {current}")
        current = current.parent


def discover_skills(root: Path) -> dict[str, SkillSource]:
    root = root.resolve()
    plugins = root / "plugins"
    if not plugins.is_dir():
        raise GenerationError(f"marketplace root has no plugins directory: {root}")
    if plugins.is_symlink():
        raise GenerationError(f"refusing symlinked plugins directory: {plugins}")

    by_name: dict[str, list[SkillSource]] = {}
    for skill_path in sorted(plugins.rglob("SKILL.md")):
        if "skills" not in skill_path.parts or skill_path.is_symlink():
            continue
        text = _read_text(skill_path)
        if _text_has_generated_marker(text):
            continue
        metadata, body = split_claude_frontmatter(text, skill_path)
        name = metadata.get("name")
        description = metadata.get("description")
        if not isinstance(name, str) or not SKILL_NAME_PATTERN.fullmatch(name) or len(name) > 64:
            raise GenerationError(f"{skill_path}: missing or invalid skill name")
        if not isinstance(description, str) or not description.strip():
            raise GenerationError(f"{skill_path}: missing or invalid skill description")
        _reject_symlinks(skill_path.parent, plugins)
        for child in skill_path.parent.rglob("*"):
            if child.is_symlink():
                raise GenerationError(f"{skill_path}: bundled symlink is not standalone: {child}")
        by_name.setdefault(name, []).append(SkillSource(name, skill_path, metadata, body))

    duplicates = {name: sources for name, sources in by_name.items() if len(sources) > 1}
    if duplicates:
        details = "; ".join(
            f"{name}: {', '.join(str(source.path) for source in sources)}"
            for name, sources in sorted(duplicates.items())
        )
        raise GenerationError(f"duplicate skill names are ambiguous: {details}")
    return {name: sources[0] for name, sources in by_name.items()}


def _standalone_problem(source: SkillSource) -> str | None:
    text_suffixes = {
        ".css", ".html", ".js", ".json", ".md", ".mjs", ".py", ".sh",
        ".toml", ".ts", ".txt", ".yaml", ".yml",
    }
    for path in sorted(source.path.parent.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in text_suffixes:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        except OSError as error:
            raise GenerationError(f"unable to inspect {path}: {error}") from error
        for label, pattern in PLUGIN_DEPENDENCY_PATTERNS.items():
            if pattern.search(text):
                return f"{label} in {path.relative_to(source.path.parent)}"
        for match in BARE_RELATIVE_REFERENCE.finditer(text):
            if not (source.path.parent / match.group(1)).is_dir():
                return (
                    f"{match.group(1)}/ reference outside the skill folder in "
                    f"{path.relative_to(source.path.parent)}"
                )
    return None


def _portable_skill_text(source: SkillSource) -> str:
    portable: dict[str, object] = {"name": source.name, "description": source.portable_description}
    for key in ("license", "compatibility", "metadata", "allowed-tools"):
        if key in source.metadata:
            portable[key] = source.metadata[key]
    frontmatter = yaml.safe_dump(portable, allow_unicode=True, sort_keys=False, width=1000)
    return f"---\n{frontmatter}---\n\n{source.body}"


def _safe_destination(destination: Path) -> Path:
    destination = destination.expanduser().absolute()
    # macOS links /tmp and /var into /private; resolve only those before refusing symlinks.
    macos_alias = any(destination.is_relative_to(alias) for alias in ("/tmp", "/var"))
    if sys.platform == "darwin" and macos_alias:
        destination = Path("/private") / destination.relative_to("/")
    for current in (destination, *destination.parents):
        if current.is_symlink():
            raise GenerationError(f"refusing symlinked destination: {current}")
    if destination.exists() and not destination.is_dir():
        raise GenerationError(f"destination must be a regular directory: {destination}")
    return destination


def _stage_skill(source: SkillSource, staging_root: Path) -> Path:
    staged = staging_root / source.name
    shutil.copytree(source.path.parent, staged, symlinks=False)
    (staged / "SKILL.md").write_text(_portable_skill_text(source), encoding="utf-8")
    return staged


def export_skills(
    selected: list[SkillSource], destination: Path, *, force: bool, dry_run: bool
) -> None:
    destination = _safe_destination(destination)
    existing_targets: list[Path] = []
    for source in selected:
        target = destination / source.name
        if target.is_symlink():
            raise GenerationError(f"refusing symlinked skill destination: {target}")
        if target.exists():
            if not target.is_dir():
                raise GenerationError(f"skill destination is not a directory: {target}")
            if not force:
                raise GenerationError(f"skill already exists (use --force): {target}")
            existing_targets.append(target)
    if dry_run:
        return

    destination.mkdir(parents=True, exist_ok=True)
    staging_root = Path(
        tempfile.mkdtemp(prefix=".standalone-skills-stage-", dir=destination.parent)
    )
    backup_root = Path(
        tempfile.mkdtemp(prefix=".standalone-skills-backup-", dir=destination.parent)
    )
    installed: list[Path] = []
    backed_up: list[tuple[Path, Path]] = []
    try:
        staged = {source.name: _stage_skill(source, staging_root) for source in selected}
        for target in existing_targets:
            _safe_destination(destination)
            if target.is_symlink() or not target.is_dir():
                raise GenerationError(f"skill destination changed during export: {target}")
            backup = backup_root / target.name
            os.replace(target, backup)
            backed_up.append((target, backup))
        for source in selected:
            target = destination / source.name
            _safe_destination(destination)
            if target.exists() or target.is_symlink():
                raise GenerationError(f"skill destination changed during export: {target}")
            os.replace(staged[source.name], target)
            installed.append(target)
    except BaseException as error:
        for target in reversed(installed):
            if target.exists() and not target.is_symlink():
                shutil.rmtree(target)
        for target, backup in reversed(backed_up):
            if backup.exists():
                os.replace(backup, target)
        if isinstance(error, GenerationError):
            raise
        raise GenerationError(f"standalone export transaction failed: {error}") from error
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)
        shutil.rmtree(backup_root, ignore_errors=True)


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.all and args.skills:
            raise GenerationError("--all cannot be combined with explicit skill names")
        if not args.all and not args.skills and not args.list:
            raise GenerationError("name one or more skills, or pass --all")
        if len(args.skills) != len(set(args.skills)):
            raise GenerationError("requested skill names must be unique")

        catalog = discover_skills(args.root)
        if args.list:
            for name in sorted(catalog):
                problem = _standalone_problem(catalog[name])
                status = f"not standalone: {problem}" if problem else "standalone"
                print(f"{name}\t{status}")
            return 0

        if args.all:
            selected = [
                source
                for _, source in sorted(catalog.items())
                if _standalone_problem(source) is None
            ]
            metadata_size = sum(
                len(source.name) + len(source.portable_description) for source in selected
            )
            if metadata_size > 8000 and not args.allow_large_catalog:
                raise GenerationError(
                    f"--all would expose about {metadata_size:,} skill-list characters, above "
                    "Codex's 8,000-character guidance; select skills explicitly or pass "
                    "--allow-large-catalog"
                )
        else:
            missing = [name for name in args.skills if name not in catalog]
            if missing:
                raise GenerationError(f"requested skill(s) not found: {', '.join(missing)}")
            selected = [catalog[name] for name in args.skills]
            dependent = [
                f"{source.name} ({problem})"
                for source in selected
                if (problem := _standalone_problem(source)) is not None
            ]
            if dependent:
                raise GenerationError(
                    "these skills depend on their plugin and cannot be exported standalone: "
                    + ", ".join(dependent)
                )

        if args.global_destination:
            user_home = os.environ.get("HOME")
            if not user_home:
                raise GenerationError("--global requires HOME to be set")
            destination = Path(user_home) / ".agents" / "skills"
        else:
            destination = args.dest or args.root / ".agents" / "skills"
        export_skills(selected, destination, force=args.force, dry_run=args.dry_run)
    except GenerationError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    action = "Would export" if args.dry_run else "Exported"
    print(f"{action} {len(selected)} standalone skill(s) to {destination}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
