---
name: print
description: Export this conversation to a terminal-styled PNG/SVG/PDF/HTML
argument-hint: "[last N] [from \"topic\"] [until \"topic\"] [light] [png|svg|pdf|html] [full]"
---

Export this conversation to a terminal-styled PNG: $ARGUMENTS

## Automatic Execution

When invoked, immediately:

1. **Find the conversation file**. This session's transcript is named after its id:
   ```bash
   ls ~/.claude/projects/*/"${CLAUDE_SESSION_ID}".jsonl 2>/dev/null | head -1
   ```
   If that finds nothing, fall back to the newest transcript for this folder. Claude Code names the
   folder after the working directory with every character other than a letter or digit turned into `-`:
   ```bash
   ls -t ~/.claude/projects/"$(pwd | sed 's/[^A-Za-z0-9]/-/g')"/*.jsonl 2>/dev/null | head -1
   ```

2. **If no arguments provided**, ask user to choose:
   - Full conversation
   - Last N exchanges (suggest 10, 20, 50)
   - From a specific topic (scan and propose 3-5 key moments)
   - Until a specific topic (exclude messages after)

3. **Find the export script**:
   ```bash
   printf '%s\n' "${CLAUDE_PLUGIN_ROOT}/scripts/export-conversation.js"
   ```

4. **Run the export**:
   ```bash
   node <script-path> <file> [options]
   ```

5. **Report the output location** and offer to open it

## Arguments

Pass these directly after `/cc-print:print`:
- `last 10` - Export last 10 exchanges
- `from "topic"` - Start from message containing "topic"
- `until "topic"` - Stop before message containing "topic"
- `light` - Use light theme
- `png` / `svg` / `pdf` / `html` - Output format (default: png)
- `full` - Export everything (no prompts)

Examples:
- `/cc-print:print` - Interactive mode
- `/cc-print:print last 20` - Last 20 exchanges as PNG
- `/cc-print:print from "auth refactor"` - From specific topic
- `/cc-print:print until "debugging"` - Exclude debugging discussion
- `/cc-print:print full light pdf` - Full conversation, light theme, PDF format
- `/cc-print:print svg` - Export as SVG

## Script Options Reference

```
--output <path>       Output path (default: ~/Desktop/claude-conversation-{timestamp}.png)
--format <type>       Output format: png (default), svg, pdf, html
--width <pixels>      Page width (default: 1200)
--scale <factor>      PNG scale factor for high-DPI (default: 2)
--light-theme         Light background
--include-thinking    Show thinking blocks
--include-tools       Show full tool inputs
--from "<text>"       Start from message containing text
--until "<text>"      Stop before message containing text
--last <n>            Only last n exchanges
--include-self        Include /print invocations in export (excluded by default)
```

## Output Format

Terminal-styled with:
- GitHub dark background (#0d1117) / Light option available
- Green `❯` prompt before each user message, in blue (#58a6ff)
- White assistant responses (#e6edf3), with Markdown lists, tables, links and code blocks
- Muted gray tool uses (#7d8590)
- JetBrains Mono monospace font
- Syntax highlighting for fenced code blocks (highlight.js from a CDN, so plain text when offline)

Only what the user typed and what the assistant wrote is exported: tool results, hook output,
skill bodies and background-task notifications are left out.
