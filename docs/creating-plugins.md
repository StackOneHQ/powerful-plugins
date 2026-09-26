# Creating Plugins

Guide for creating full-featured plugins with commands, agents, and hooks.

## When to Create a Plugin vs Skill

| Need | Use |
|------|-----|
| Simple instructions/guidelines | Skill |
| Slash commands (`/command`) | Plugin |
| Custom agents | Plugin |
| Event hooks (PreToolUse, etc.) | Plugin |
| MCP server integration | Plugin |
| Bundle of related skills | Plugin |

## Quick Start

### 1. Copy the Template

```bash
cp -r templates/plugin-template plugins/your-category/your-plugin-name
```

Name the plugin after what it does, in lowercase with hyphens, with no company or owner
prefix.

### 2. Edit plugin.json

```json
{
  "name": "your-plugin-name",
  "version": "1.0.0",
  "description": "What your plugin does",
  "author": {
    "name": "Your Name",
    "url": "https://github.com/your-handle"
  },
  "license": "MIT",
  "keywords": ["keyword1", "keyword2"]
}
```

### 3. Add Components

Add any of these optional components:
- `commands/` - Slash commands
- `agents/` - Specialized agents
- `skills/` - Bundled skills
- `hooks/` - Event handlers

### 4. Test Locally

Load the plugin straight from its folder for one session:

```bash
claude --plugin-dir plugins/your-category/your-plugin-name
```

Or install it through a local checkout of the marketplace, after you register it (see
[Adding to Marketplace](#adding-to-marketplace)):

```bash
/plugin marketplace add /path/to/powerful-plugins
/plugin install your-plugin-name@powerful-plugins
```

## Plugin Structure

```
your-plugin-name/
├── .claude-plugin/
│   └── plugin.json           # Required: metadata
├── commands/                 # Optional: slash commands
│   └── your-command.md
├── agents/                   # Optional: specialized agents
│   └── your-agent.md
├── skills/                   # Optional: bundled skills
│   └── your-skill/
│       └── SKILL.md
├── hooks/                    # Optional: event handlers
│   └── hooks.json
├── scripts/                  # Optional: hook scripts
│   └── validate.sh
├── .mcp.json                 # Optional: Claude MCP server config
├── .codex-mcp.json           # Optional: Codex-only MCP override
└── README.md                 # Required: documentation
```

Keep existing Claude MCP behavior in `.mcp.json`. Add `.codex-mcp.json` only
when Codex requires different commands or arguments; generation makes the Codex
manifest prefer that override without changing what Claude Code installs.

## Creating Commands

### commands/your-command.md

The file name is the command name. In Claude Code it runs as `/your-plugin-name:your-command`.

```yaml
---
description: What this command does
argument-hint: "[optional-args]"
---

# /your-command

[Instructions for Claude when this command is invoked. `$ARGUMENTS` holds what the user typed
after the command.]

## Usage

\`\`\`
/your-plugin-name:your-command [optional-args]
\`\`\`

## Workflow

1. Step 1
2. Step 2

## Examples

[Show example usage and output]
```

## Creating Agents

### agents/your-agent.md

```yaml
---
name: your-agent
description: Specialized agent for specific tasks
model: sonnet  # or opus, haiku
---

# Your Agent

[Detailed instructions for this specialized agent]

## Capabilities

- Capability 1
- Capability 2

## Limitations

- What this agent doesn't do
```

## Creating Hooks

### hooks/hooks.json

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

Keep only Codex-supported events in `hooks/hooks.json`. If Claude Code needs an event Codex
does not support, such as `Notification`, put only those Claude-only events in
`hooks/claude-hooks.json` and declare `"hooks": "./hooks/claude-hooks.json"` in
`.claude-plugin/plugin.json`. Claude Code loads both files, so a hook listed in both fires twice.

### scripts/validate.sh

```bash
#!/usr/bin/env bash

# The hook receives the event as JSON on stdin; tool arguments are under .tool_input
FILE_PATH=$(jq -r '.tool_input.file_path // empty')

# Exit codes:
# 0 = allow
# 2 = block the operation (stderr is shown to Claude)
# anything else = non-blocking error; the operation still runs

if [[ "$FILE_PATH" == *.env* ]]; then
  echo "Cannot edit .env files" >&2
  exit 2
fi

exit 0
```

Make scripts executable:
```bash
chmod +x scripts/validate.sh
```

## Using Dynamic Paths

Always use `${CLAUDE_PLUGIN_ROOT}` for paths within your plugin:

```json
{
  "command": "${CLAUDE_PLUGIN_ROOT}/scripts/my-script.sh"
}
```

This ensures the plugin works after installation to the cache.

## Adding to Marketplace

Update `.claude-plugin/marketplace.json`, which is the hand-authored source registry:

```json
{
  "plugins": [
    // ... existing plugins ...
    {
      "name": "your-plugin-name",
      "description": "What it does",
      "version": "1.0.0",
      "author": {
        "name": "Your Name",
        "url": "https://github.com/your-handle"
      },
      "source": "./plugins/your-domain/your-plugin-name",
      "category": "engineering",
      "tags": ["tag1", "tag2"]
    }
  ]
}
```

Then generate the Codex marketplace and plugin adapters:

```bash
python3 -m pip install -r requirements-dev.txt
python3 scripts/generate_codex_marketplace.py
claude plugin validate --strict .
python3 scripts/generate_codex_marketplace.py --check
python3 -m unittest discover -s tests -v
python3 scripts/validate_codex_plugins.py
```

Commit the generated `.agents/plugins/marketplace.json`, local
`.codex-plugin/plugin.json` files, `.codex/skills/` adapters, and policy files
with the source change. Do not edit those outputs by hand. On a pull request from
a branch of this repository, the Sync Codex Plugins workflow regenerates anything
you missed and commits it to your branch. A pull request from a fork gets a
failing check with the command to run instead.

### External Plugins

An external plugin's entry in `.claude-plugin/marketplace.json` pins one upstream commit with a
full 40-character lowercase hex `sha`. The generator derives the Codex source from it, so both
tools use the same pinned commit and there is no second place to update. Claude Code installs that
commit directly; for an upstream without Codex packaging, Codex installs a generated adapter that
fetches it on first use. Pick the source type by where the plugin
lives upstream:

```json
{ "source": "github", "repo": "owner/repo", "sha": "<40-character commit>" }
{ "source": "git-subdir", "url": "owner/repo", "path": "plugins/name", "sha": "<40-character commit>" }
```

Use `github` only for a plugin at the repository root. Claude Code ignores `path` on a `github`
source and installs the whole repository, which loads either nothing or every plugin in it, so
the validators reject that shape. Do not use `ref`: it names a branch or tag, which can move. To
update a pin, change the `sha`, regenerate, and reinstall the plugin to check what loads.

Sources with native Codex packaging need no compatibility override. For a Claude-only layout,
add a compact mapping in `.agents/plugins/source-overrides.json`:

```json
{
  "source": "runtime-adapter",
  "entrypoints": ["SKILL.md"]
}
```

Entrypoints are relative to the source `path`. Do not repeat the
repository, path, or commit in the compatibility mapping. Regenerate and run
`python3 scripts/validate_external_sources.py` after any external change.

## Testing Checklist

- [ ] plugin.json is valid JSON with required fields
- [ ] An existing plugin's version is bumped in `plugin.json` and its catalog entry (`python3 scripts/check_plugin_versions.py --base origin/main`)
- [ ] All referenced files exist
- [ ] Scripts are executable
- [ ] No hardcoded absolute paths
- [ ] README.md documents usage
- [ ] Codex generator has been run and `--check` passes
- [ ] Generated Codex files are committed
- [ ] Native skill names match their parent directories and descriptions are at most 1024 characters
- [ ] Codex-specific hooks use only supported events and synchronous command handlers
- [ ] Commands work when invoked
- [ ] Hooks fire on expected events
- [ ] No sensitive information exposed

## Submitting Your Plugin

1. Create branch: `feature/<category>/<plugin-name>`
2. Add the plugin to the matching category folder
3. Update `.claude-plugin/marketplace.json`
4. Run and commit the Codex generator output
5. Open a pull request against `main`
6. Wait for the required checks (`validate`, `generator-windows`, `scan-skills`) to pass and
   resolve every review conversation; the pull request is then squash-merged
