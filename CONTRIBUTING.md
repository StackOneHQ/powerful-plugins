# Contributing to powerful-plugins

Guidelines for contributing plugins, skills and hooks to this marketplace. Pull requests and
issues are welcome from anyone.

## Does It Belong Here?

This marketplace takes plugins that are useful to anyone who runs Claude Code or Codex. A good
fit works without a StackOne account and carries no StackOne branding, internal names or
product assumptions.

- A plugin that needs a StackOne account, API, connector or MCP server belongs in
  [StackOneHQ/agent-plugins](https://github.com/StackOneHQ/agent-plugins).
- A plugin that only makes sense inside one company, such as its brand, customers or internal
  tools, does not belong in a public marketplace.

## How Pull Requests Work

- **StackOne team members** push a branch to this repository and open a pull request. The Sync
  Codex Plugins workflow regenerates the Codex files and commits them to your branch.
- **Everyone else** opens a pull request from a fork. The workflow cannot push to a fork, so run
  `python3 scripts/generate_codex_marketplace.py` yourself and commit the result; the check tells
  you when it is needed. A maintainer approves the workflow runs and starts the AI review.
- [cubic](https://cubic.dev) reviews each pull request using [`cubic.yaml`](cubic.yaml). Its
  repository rules restate the ground rules in [CLAUDE.md](CLAUDE.md). Fix or reply to every
  comment; unresolved threads block the merge.
- The required checks are `validate`, `generator-windows` and `scan-skills`. Merges are squash
  only.

## Quick Reference

### Skill Structure

```
my-skill/
├── SKILL.md              # Required: frontmatter + instructions
└── reference.md          # Optional: additional context
```

### Plugin Structure

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json       # Required: plugin manifest
├── commands/             # Optional: slash commands
├── agents/               # Optional: specialized agents
├── skills/               # Optional: bundled skills
├── hooks/                # Optional: event handlers
├── scripts/              # Optional: scripts the skills, commands or hooks run
├── .mcp.json             # Optional: MCP server config
└── README.md             # Required: documentation
```

## Creating a Skill

### 1. Choose the Right Category

| Category | Use For |
|----------|---------|
| `calculators/` | Cost and usage calculators and forecasts |
| `design/` | Animation, visual design, data visualization |
| `documentation/` | Writing standards, editing, technical prose |
| `engineering/` | Development workflows, browser tooling, agent tooling |
| `productivity/` | Personal workflow tools, exports, reporting |

### 2. Create SKILL.md

```yaml
---
name: my-skill-name
description: Clear description of what this skill does and when the agent should use it
---

# My Skill Name

## When to Use

- Trigger condition 1
- Trigger condition 2

## Instructions

[Detailed instructions for the agent to follow]

## Examples

[Concrete usage examples]

## Guidelines

- Guideline 1
- Guideline 2
```

### 3. Naming Conventions

- **No company or owner prefix**: name the plugin after what it does (`tufte-viz`)
- **Skill names**: lowercase with hyphens (`api-patterns`, not `APIPatterns`)
- **Descriptions**: start with a verb ("Create...", "Review...", "Generate...")
- **No abbreviations** in folder names: `documentation`, not `docs`

## Creating a Plugin

### 1. plugin.json Format

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "What this plugin does",
  "author": {
    "name": "Your Name",
    "url": "https://github.com/your-handle"
  },
  "license": "MIT",
  "keywords": ["keyword1", "keyword2"]
}
```

### 2. Adding Commands

Create `commands/my-command.md`. In Claude Code it runs as `/my-plugin:my-command`:

```markdown
---
description: What the command does
argument-hint: "[optional-args]"
---

# /my-command

[Instructions for the agent when this command is invoked]
```

### 3. Adding Agents

Create `agents/my-agent.md`:

```markdown
---
name: my-agent
description: Specialized agent for specific tasks
model: sonnet  # or opus, haiku
---

# My Agent

[Agent instructions and capabilities]
```

### 4. Adding Hooks

Create `hooks/hooks.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/scripts/validate.sh"
          }
        ]
      }
    ]
  }
}
```

Keep only Codex-supported events in `hooks/hooks.json`. Claude-only events go in
`hooks/claude-hooks.json`, declared in the Claude manifest. See [CLAUDE.md](CLAUDE.md).

### 5. Register and Generate

Add one entry to `.claude-plugin/marketplace.json`, then run:

```bash
python3 scripts/generate_codex_marketplace.py
```

Commit the generated Codex files with your change. Do not edit them by hand.

## Testing Your Contribution

### Local Testing

```bash
# Claude Code, one session, no install
claude --plugin-dir plugins/<category>/my-plugin

# Claude Code, installed from a local checkout
/plugin marketplace add /path/to/powerful-plugins
/plugin install my-plugin@powerful-plugins

# Codex
codex plugin marketplace add /path/to/powerful-plugins
codex plugin add my-plugin@powerful-plugins
```

### Dependencies

`requirements.txt` and `requirements-dev.txt` pin every package, including indirect ones, with
hashes, and CI installs them with `--require-hashes`. Dependabot proposes weekly bumps. cubic
reviews each one and approves it when the review is clean, and it merges once the required checks
pass; a bump with open cubic findings, or one someone else pushed to, waits for a person. To change a pin by hand, edit it and regenerate the hashes:

```bash
uv pip compile requirements.txt --universal --python-version 3.12 --generate-hashes \
  --no-header --no-annotate -o requirements.txt
```

For `requirements-dev.txt`, compile the development tools together with `requirements.txt` and
keep only the packages that are not already in `requirements.txt`, under its `-r` line.

### Automated Checks

```bash
python3 -m pip install -r requirements-dev.txt
ruff check scripts/*.py tests/*.py
mypy scripts/*.py
python3 -m unittest discover -s tests -v
python3 scripts/check_plugin_versions.py --base origin/main
python3 scripts/generate_codex_marketplace.py --check
python3 scripts/validate_codex_plugins.py
python3 scripts/validate_external_sources.py
find scripts plugins -type f -name '*.sh' -print0 | xargs -0 shellcheck --severity=error
claude plugin validate --strict .
scripts/scan-skills.sh changed
```

CI also installs every plugin with real Claude Code and Codex CLIs; the README's
[Validation](README.md#validation) section has those commands.

### Validation Checklist

- [ ] SKILL.md has valid YAML frontmatter, and its `name` matches its folder
- [ ] plugin.json is valid JSON and its `name` matches the catalog entry
- [ ] The plugin version was bumped, in `plugin.json` and its catalog entry, if the plugin already existed
- [ ] All referenced files exist
- [ ] Scripts are executable (`chmod +x`)
- [ ] No hardcoded paths (use `${CLAUDE_PLUGIN_ROOT}`)
- [ ] README.md documents usage
- [ ] Generated Codex files are committed and `--check` passes

## Pull Request Process

### 1. Branch Naming

```
feature/<category>/<plugin-name>
fix/<category>/<issue-description>
```

### 2. Pull Request Title

Pull requests are squash-merged, so the title becomes the commit message on `main`. Say what
changed and in which plugin, for example `natural-writing: flag stacked hedges`.

### 3. PR Description Template

```markdown
## Summary
What this PR adds or changes

## Category
calculators | design | documentation | engineering | productivity

## Type
skill | plugin | hook | template | tooling

## Testing
How you tested this, in Claude Code and in Codex

## Checklist
- [ ] Follows naming conventions
- [ ] Includes README or documentation
- [ ] Version bumped where needed
- [ ] Tested locally
- [ ] No sensitive information
```

### 4. Merging

`main` is protected. A change lands only through a pull request, once the required checks
(`validate`, `generator-windows` and `scan-skills`) pass and every review conversation is
resolved. Pull requests are squash-merged; force pushes to `main` and deleting it are blocked.
On a pull request from a branch of this repository, the Sync Codex Plugins workflow commits any
missing generated Codex files for you. From a fork, run the generator yourself.

## Code Style

### Markdown

- ATX-style headers (`#`, `##`, `###`)
- Code blocks with language identifiers
- Tables for structured data
- No trailing whitespace

### JSON

- 2-space indentation
- No trailing commas
- Double quotes for strings

### Shell Scripts

- `#!/usr/bin/env bash` shebang
- Exit codes: 0 (success), 1 (error), 2 (block the action, for hooks)
- Quote variables: `"$variable"`
- Must pass `shellcheck --severity=error`

### Python

- Must pass `ruff check` and `mypy --strict` (configured in `pyproject.toml`)

## Sensitive Information

Never include:

- API keys or secrets
- Employer, client or customer names and data, including StackOne's
- Private URLs
- Personal identifying information

## Questions?

Check existing plugins for examples, or open an issue on
[GitHub](https://github.com/StackOneHQ/powerful-plugins/issues).
