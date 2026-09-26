# Getting Started

How to use the powerful-plugins marketplace with Claude Code or OpenAI Codex.

## Prerequisites

- [Claude Code](https://claude.com/code) or OpenAI Codex installed
- Network access to `github.com`, where the marketplace is published
- Codex runtime-adapted external plugins require Python 3, Git, and HTTPS access
  to `github.com` on first invocation. The verified pinned checkout is cached.
  The catalog has no such plugins today, and Claude Code never uses this path.

## Installation

### Claude Code

```bash
/plugin marketplace add StackOneHQ/powerful-plugins
/plugin install natural-writing@powerful-plugins
```

Run `/plugin` on its own to browse the catalog.

### OpenAI Codex

```bash
codex plugin marketplace add StackOneHQ/powerful-plugins
codex plugin list --marketplace powerful-plugins
codex plugin add natural-writing@powerful-plugins
```

Replace `natural-writing` with any plugin name from the table in the
[README](../README.md#available-plugins).

## Using Skills

### Automatic Activation

Skills activate from context. For example:

- Ask for a chart review and `tufte-viz` applies
- Ask to tighten a draft and `natural-writing` applies
- Ask to automate a browser task and `browser-automation` picks the tool

You can also invoke a skill by name. In Codex, plugin skills are namespaced by plugin, for
example `$tufte-viz:tufte-viz`.

### Standalone Codex Skills

Codex IDE integrations can use the repository's native skills without installing the full
plugin catalog:

```bash
# Install the exporter's pinned YAML dependency once
python3 -m pip install -r requirements.txt

# See which native skills are self-contained
./scripts/export-standalone-skills.sh --list

# Export selected skills to a project
./scripts/export-standalone-skills.sh --dest /path/to/project/.agents/skills skill-one skill-two

# Export selected skills to the current user's shared agent skills directory
./scripts/export-standalone-skills.sh --global skill-one skill-two
```

The exporter copies complete skill directories, including referenced scripts and assets. It
refuses plugin-dependent skills and existing destinations unless `--force` is explicit.
`--all` exports every self-contained native skill, but a large catalog also requires
`--allow-large-catalog`. Command and agent adapters remain available through the Codex plugin
CLI.

## Using Commands

Plugins may include slash commands. In Claude Code the full name includes the plugin:

```bash
/cc-print:print
/natural-writing:review-copy draft.md
```

In Codex, each command is available as a generated `codex-<command>` skill, such as
`$cc-print:codex-print`. A command that shares its name with one of the plugin's skills, such as
`/reflect:reflect`, maps to that skill instead (`$reflect:reflect` in Codex).

## Next Steps

- [Creating Skills](./creating-skills.md)
- [Creating Plugins](./creating-plugins.md)
- [Contributing](../CONTRIBUTING.md)
