# browser-automation

Guidance for driving a browser from an agent: which tool to pick, the `agent-browser` command
reference, ref handling, login and saved state, and the fallbacks.

## Installation

```bash
# Claude Code
/plugin marketplace add StackOneHQ/powerful-plugins
/plugin install browser-automation@powerful-plugins

# Codex
codex plugin marketplace add StackOneHQ/powerful-plugins
codex plugin add browser-automation@powerful-plugins
```

## Why

The browser your coding agent already has is usually the right one: the person can watch it
and take over, and in Chrome it already carries their logins. The other tools each fit a job
it does badly, such as clean headless runs, canvas content or performance traces, so the skill
starts with the agent's own browser and falls back only for those.

## Tool choice

| Tool | When |
|------|------|
| The agent's own browser (Claude in Chrome; in Codex, the Chrome plugin or the in-app Browser plugin) | First choice when the session has one: the task runs in a browser the person can see, and in Chrome with their logins |
| A connected browser MCP server (Playwright MCP, Chrome DevTools MCP) | Next, when there is no built-in browser |
| `agent-browser` | No extension available, or the task needs a clean browser: scraping, repeatable headless checks |
| Playwright | Canvas and `requestAnimationFrame` content that `agent-browser` reports as blank |
| Chrome DevTools MCP | Performance traces and Core Web Vitals |
| `browser-recorder` skill | Recording a video clip |

## Skills

| Skill | Triggers When |
|-------|---------------|
| `browser-automation` | "browse to", "open a website", "fill a form", "click a button", "take a screenshot", "scrape data", "test this web app", any browser task |

## Requirements

For the `agent-browser` path:

```bash
npm install -g agent-browser
agent-browser install   # downloads the browser it drives
```

See [vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser) for details.

## What it covers

- `agent-browser` command reference (navigate, snapshot, click, fill, screenshot)
- Measuring instead of eyeballing: `get box`, `get styles`, `eval`
- Ref lifecycle rules (re-snapshot after every page change)
- Signing in: saved auth state first, then asking you to sign in, then an optional 1Password lookup
- Named sessions for parallel runs
- Fallback steps for the extension, Chrome DevTools MCP and Playwright
