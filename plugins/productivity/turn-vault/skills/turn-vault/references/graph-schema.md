# Turn Vault Graph & Backlink Schema

Obsidian Graph View builds edges from two places in Markdown notes:
1. Inline `[[Note Name]]` or `[[Note Name|Display Label]]` wikilinks in the body.
2. Quoted `"[[Note Name]]"` values inside YAML frontmatter properties (Obsidian 1.4+ Properties).

Turn Vault emits both so every node connects cleanly in Graph View **and** in Obsidian's Backlinks pane, while avoiding self-links and duplicate basenames.

## Node types and how they connect

| Node | Default location | Outgoing `[[wikilinks]]` | Purpose in Graph View |
|---|---|---|---|
| **Work Map** | `Work-Map.md` (or custom `--map` / `none`) | Recent days, active tickets, repos, topics | Central anchor node |
| **Daily Log** | `Daily/YYYY-MM-DD.md` | `[[Repo]]`, `[[Ticket]]`, `[[Topic]]`, `[[Deliverable Note]]` | Chronological spine |
| **Ticket** | `Tickets/<TICKET>.md` (or existing vault note) | `[[YYYY-MM-DD]]`, `[[Repo]]`, `[[Topic]]` | Connects a piece of work across repos, days, and domains |
| **Repo** | `Repos/<repo>.md` (or existing vault note) | `[[YYYY-MM-DD]]`, `[[Ticket]]`, `[[Topic]]` | Clusters everything touched in one codebase |
| **Topic** | `Topics/<topic>.md` (or existing vault note) | `[[YYYY-MM-DD]]`, `[[Ticket]]`, `[[Repo]]` | Bridges related work across repos and tickets (services, providers, domains, areas) |
| **Deliverable** | `Notes/<Title>.md` (or user's preferred folder) | `[[Ticket]]`, `[[Repo]]`, `[[Topic]]` | Investigation, plan, review, or decision writeup |

## Existing-note resolution

Before creating any entity note, Turn Vault indexes all non-excluded `.md` files across `vaultDir` by basename (case-insensitive):
- If `PROJ-123.md` or `Payments.md` **already exists** anywhere in the vault (for example under `Projects/PROJ-123.md` or `Areas/Payments.md`), Turn Vault links to and updates that existing note in place instead of creating a duplicate file.
- If a category's folder is set to `none` (`null` in `config.json`), Turn Vault still writes `[[Slug]]` wikilinks in peer notes (creating virtual hubs in Obsidian Graph View) without creating files for that category.

## Deliverable note template (when authoring plans, investigations, or reviews)

When writing a standalone investigation, plan, or review note into the user's vault:

```markdown
---
type: note
created: YYYY-MM-DD
tickets:
  - "[[PROJ-123]]"
repos:
  - "[[web-app]]"
topics:
  - "[[OAuth]]"
---

# Short descriptive title

## Summary

Concise findings or plan, linking meaningfully to [[PROJ-123]], [[web-app]], and [[OAuth]].
```

Link meaningfully: connect real relationships (the ticket, repository, domain and prior notes that informed the work) rather than adding filler links.
