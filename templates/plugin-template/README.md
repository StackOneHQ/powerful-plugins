# Plugin Name

Brief description of what this plugin does.

## Installation

### Claude Code

```bash
/plugin marketplace add StackOneHQ/powerful-plugins
/plugin install plugin-name@powerful-plugins
```

### OpenAI Codex

```bash
codex plugin marketplace add StackOneHQ/powerful-plugins
codex plugin add plugin-name@powerful-plugins
```

The Codex manifest and skill, command and agent adapters are generated from the
Claude plugin source with `python3 scripts/generate_codex_marketplace.py`.

## Features

### Commands

| Command | Description |
|---------|-------------|
| `/plugin-name:command-name` | What it does |

### Skills

| Skill | Triggers When |
|-------|---------------|
| `skill-name` | Auto-triggers when... |

### Hooks

| Event | Action |
|-------|--------|
| `PreToolUse` | What it validates/modifies |

## Usage

### Basic Usage

```bash
/plugin-name:command-name
```

In Codex, the same command is the `$plugin-name:codex-command-name` skill, or `$plugin-name:command-name`
when the plugin also has a skill with the command's name.

### Advanced Usage

[More detailed examples]

## Requirements

- Claude Code v2.x+ or OpenAI Codex
- [Any other dependencies]

## Contributing

See [CONTRIBUTING.md](https://github.com/StackOneHQ/powerful-plugins/blob/main/CONTRIBUTING.md) for guidelines.
