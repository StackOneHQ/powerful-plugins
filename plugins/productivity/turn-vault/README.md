# turn-vault

Turns your completed coding tasks, past session transcripts and worked tickets into backlinked
Markdown notes in an **Obsidian** vault, so **Graph View** shows how your work connects across
days, tickets, repositories and topics.

Everything stays on your machine: Turn Vault reads local transcripts and writes Markdown into the
folder you choose. It makes no network calls and sends nothing anywhere.

## How it works

1. **Hook-driven live capture, without per-turn noise**
   Installing the plugin registers lightweight hooks (`Stop`, `PreCompact`, `SessionEnd`). There is no background daemon, cron job or manual `settings.json` edit.
   - Until you run `/turn-vault:init`, the hooks do nothing and exit immediately.
   - Once pointed at a vault folder, `Stop` writes only at real task milestones (`git commit`,
     `gh pr create`, `gh pr merge`, a mutating issue-tracker MCP call, or a deliverable note
     written into the vault), and keeps **one consolidated entry per session** up to date.
   - When a session compacts or ends (`PreCompact` / `SessionEnd`), substantive work from that
     session is written once, so investigations and edits that ended without a commit are still
     captured.

2. **Fits the vault you already have**
   A fresh folder, a subfolder of an existing vault, PARA, Johnny.Decimal, Zettelkasten or the
   Daily Notes core plugin all work:
   - `inspect` reads `.obsidian/daily-notes.json` (daily folder and template), existing folder
     names, and whether your daily notes use `## Work Log` or `## Activity`.
   - Each category (`daily`, `tickets`, `repos`, `topics`, `notes`, `map`) maps to any folder in
     the vault, or to `none` (link-only mode: it writes `[[wikilinks]]` and updates matching notes
     wherever you already keep them, without creating folders).
   - Your own prose and custom frontmatter fields are left untouched.

3. **History and ticket miner**
   `/turn-vault:backfill` scans local Claude Code transcripts in `~/.claude/projects/` (main
   sessions and subagents) and extracts worked tickets, pull requests, repositories and topics,
   then writes backlinked notes so Graph View fills in straight away.
   - Ticket IDs are detected with a generic `PREFIX-123` pattern (plus Linear and Jira issue
     URLs), with a built-in list of false positives such as `UTF-8` or `SHA-256`. Pass
     `--team-prefixes "PROJ,OPS"` to accept only your own trackers' prefixes.
   - Titles, statuses and URLs can optionally be added from whatever read-only tracker tools
     your agent already has (an issue-tracker MCP server, `gh pr view`). Without them, backfill
     simply skips enrichment.

## Installation

```bash
# Claude Code
/plugin marketplace add StackOneHQ/powerful-plugins
/plugin install turn-vault@powerful-plugins

# Codex
codex plugin marketplace add StackOneHQ/powerful-plugins
codex plugin add turn-vault@powerful-plugins
```

The Codex manifest and command adapters are generated from the Claude plugin source with
`python3 scripts/generate_codex_marketplace.py`.

## Quick start

```bash
# 1. Point Turn Vault at an Obsidian vault (or a subfolder inside one)
/turn-vault:init ~/Documents/Obsidian/Work

# 2. Backfill past sessions and worked tickets into Graph View
/turn-vault:backfill --since 2026-10-01

# 3. Record a takeaway after a read-only investigation or review
/turn-vault:log Root-caused OAuth callback retry loop on PROJ-123

# 4. Check backlinks and duplicate note names, and refresh Work-Map
/turn-vault:check
```

In Codex, the same commands are the `$turn-vault:codex-init`, `$turn-vault:codex-backfill`,
`$turn-vault:codex-log` and `$turn-vault:codex-check` skills.

## Customizing for an existing vault

Map Turn Vault onto your existing folders, or set any category to `none` for wikilink-only mode:

```bash
node "<plugin-root>/bin/turn-vault.mjs" configure \
  --daily "Journal/Daily" \
  --daily-section "Activity" \
  --tickets "Projects/Tickets" \
  --repos "none" \
  --topics "Areas" \
  --map "Maps/Work-Map.md" \
  --team-prefixes "PROJ,OPS" \
  --topic-dirs "src/integrations,packages" \
  --exclude "Private,Personal"
```

`--topic-dirs` is optional. It lists directory segments whose immediate child folders become
topic hubs when you edit files under them (with `src/integrations`, an edit to
`src/integrations/payments/client.ts` links the session to `[[payments]]`). Without it, topics
come only from `--topics`, enrichment and MCP calls that name a provider.

Environment overrides:

| Variable | Purpose |
|---|---|
| `TURN_VAULT_DIR` | Override the active vault folder |
| `TURN_VAULT_DISABLED=1` | Turn hook capture off in the current shell |
| `TURN_VAULT_HOME` | Override where `config.json` and the incremental scan `state.json` are stored (default `~/Library/Application Support/turn-vault` on macOS, `$XDG_CONFIG_HOME/turn-vault` or `~/.config/turn-vault` elsewhere) |

## Commands, skills and hooks

| Entry point | What it does |
|---|---|
| `turn-vault` (skill) | Setup, vault layout, backfill with optional enrichment, task checkpoints, graph health |
| `/turn-vault:init` | Inspect your vault layout, create or map folders, and turn on hook capture |
| `/turn-vault:backfill` | Mine past transcripts and tickets into backlinked Markdown notes |
| `/turn-vault:log` | Record an explicit end-of-task summary with ticket, repo and topic backlinks |
| `/turn-vault:check` | Check `[[wikilinks]]`, duplicate basenames and empty notes, and refresh `Work-Map` |

| Hook | What it does |
|---|---|
| `Stop` | Writes or updates the session entry when a new task milestone happened |
| `PreCompact`, `SessionEnd` | Flushes substantive work from the session once |

Hooks always exit 0, never block the session, and stay silent when Node.js is missing.

Live capture and backfill read the Claude Code transcript format. Codex runs the same hooks, but
its transcripts use another format, so they record nothing there; in Codex, record work with
`$turn-vault:codex-log`.

## Privacy

- Transcripts are read locally and never leave your machine.
- Tokens, keys, passwords, `Authorization` headers and credentials in URLs are redacted before
  anything is written to the vault.
- Paths you list with `--exclude` (or an exclusion manifest) are never read, indexed or written,
  and notes written there are never named in other notes. Exclusions apply from the moment you
  add them: entries written earlier stay as they are, so edit those lines by hand if one names a
  note you have since excluded (each Turn Vault line ends with a `^tv-` block ID).
- Config and state live in the plugin's own config folder (see `TURN_VAULT_HOME`) with private (`0600`) permissions.

## Testing

```bash
node --test plugins/productivity/turn-vault/scripts/test-turn-vault.mjs
```

## Requirements

- Node.js 20+
- Claude Code v2.x+ or OpenAI Codex
- Obsidian is optional: the notes are plain Markdown with `[[wikilinks]]`

## Credits

Created by [Cameron Carlin](https://github.com/CameronCarlin).
