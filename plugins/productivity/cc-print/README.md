# cc-print

Export Claude Code (or Codex) conversations to terminal-styled PNG, SVG, PDF, or HTML.

## What it does

Converts your conversation JSONL into a styled output that looks like terminal output, with proper syntax highlighting, code blocks, and color themes. Useful for sharing a session in a doc, a pull request or a slide.

Self-referencing messages (the print command itself and its responses) are automatically filtered out of exports, so your output stays clean.

## Installation

```bash
# Claude Code
/plugin marketplace add StackOneHQ/powerful-plugins
/plugin install cc-print@powerful-plugins

# Codex
codex plugin marketplace add StackOneHQ/powerful-plugins
codex plugin add cc-print@powerful-plugins
```

Needs Node.js. PNG, SVG and PDF output also need [Puppeteer](https://pptr.dev/). A global
install is enough; the script finds it on its own:

```bash
npm install -g puppeteer
```

HTML output works without any dependencies.

## Usage

In Claude Code the command is `/cc-print:print`. It finds the current session from the
working directory and runs the export script from the installed plugin. In Codex, use `$cc-print:codex-print`, which exports the newest Codex
session started in the current folder.

```
/cc-print:print                         Interactive mode (choose what to export)
/cc-print:print last 20                 Last 20 exchanges as PNG
/cc-print:print from "auth refactor"    Start from a specific topic
/cc-print:print until "debugging"       Stop before a topic
/cc-print:print full light pdf          Full conversation, light theme, PDF
/cc-print:print svg                     Export as SVG
```

You can also run the script directly on any conversation file, from the plugin folder:

```bash
node scripts/export-conversation.js ~/.claude/projects/<encoded-cwd>/<session>.jsonl --last 10 --format pdf
```

`<encoded-cwd>` is the session's working directory with every character other than a letter or digit
replaced by `-`. Run
`node scripts/export-conversation.js` with no arguments for the full option list, which adds
`--output`, `--width`, `--scale`, `--include-thinking`, `--include-tools` and `--include-self`.

## Options

| Option | Description |
|--------|-------------|
| `last N` | Export last N exchanges |
| `from "text"` | Start from message containing text |
| `until "text"` | Stop before message containing text |
| `light` | Use light theme (default: dark) |
| `png` / `svg` / `pdf` / `html` | Output format (default: png) |
| `full` | Export everything without prompts |

## Output

Files are saved to `~/Desktop/claude-conversation-{timestamp}.{format}` by default, or to the current
folder when there is no Desktop. SVG output is the PNG wrapped in an SVG file: it scales, but its text
is not selectable. Code blocks are highlighted with highlight.js, loaded from a CDN, so they stay
plain when you are offline.

The dark theme matches GitHub's color palette. The light theme uses a white background with matching contrast.
