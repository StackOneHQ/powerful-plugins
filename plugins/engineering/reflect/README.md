# Reflect

Turn a finished session or recurring workspace history into skill and repository-guidance improvements. `/reflect:reflect` fans three review lenses out over the active
transcript, synthesizes their findings into an Accepted / Rejected / Backlog list, and, after you
approve it, applies each authorized item to its skill or repository-guidance source.

## Installation

### Claude Code

```bash
/plugin marketplace add StackOneHQ/powerful-plugins
/plugin install reflect@powerful-plugins
```

Or load it from a checkout for one session:

```bash
claude --plugin-dir ./plugins/engineering/reflect
```

### OpenAI Codex

```bash
codex plugin marketplace add StackOneHQ/powerful-plugins
codex plugin add reflect@powerful-plugins
```

## Features

### Skills

| Skill | Triggers when |
|-------|---------------|
| `reflect` | You request session reflection, recurring-pattern analysis, or improvements to skills/repository guidance |

### The three lenses

| Lens | Looks for |
|------|-----------|
| Judgment | The durable principle behind a specific incident: corrections received, decisions and their rationale, friction in skill execution |
| Tooling | The load-bearing command, flag, path, or quirk a future agent would otherwise re-derive, plus every time you hand-fed context an MCP could have fetched |
| Divergent | The second-order effect, the skipped verification, the contrarian framing beneath the obvious learning |

A fourth reviewer synthesizes all three, applying durability, specificity, convergence, and
decision-changing criteria, plus a structural check that routes anything a lint rule or hook could
enforce to the backlog instead of skill prose. When subagents are unavailable
or not permitted, the same lenses run sequentially with that limitation disclosed.

## Usage

```bash
/reflect:reflect
```

Run it right after a substantial task lands: a gnarly debug, a workflow you had to correct
mid-flight, a recipe worth keeping. Skip it on trivial or off-topic sessions; one-offs are not
learnings.

Analysis alone changes nothing. The skill prints concrete proposals and applies
only the changes authorized in the session. Tracker filing requires its own
authorization. Corrections do not trigger a mid-task history scan.

## History mode

Use `/reflect:reflect --history`, `/reflect:introspect`, or ask for recurring patterns across this
workspace's sessions, git changes, and PR reviews. By default the review examines at most 10
matching sessions, 40 commits, and 8 merged PRs, with unavailable sources reported
explicitly. It reads inline PR feedback as well as review summaries and comments,
deduplicates repeated reports, and checks existing guidance before proposing edits.

Codex exposes the same workflows as `$reflect:reflect` and `$reflect:codex-introspect`.
Neither mode adds a frustration-triggered introspection rule to your projects, and installing the
plugin does not rewrite any project files.

Six synthetic history scenarios live in
[evals/history-scenarios.json](evals/history-scenarios.json), with evaluation
instructions in [evals/README.md](evals/README.md).

## Improving the first usable result

Ask reflect to reduce repeated corrections or evaluate a skill's first usable
result. It separates requirements available before delivery from later facts,
preferences, and scope changes, then prepares a focused skill-creator handoff
for substantive improvements. Replay executors receive the original inputs;
corrections and accepted answers remain grader-only evidence.

Historical activation stays unknown unless the available catalog and execution
trace establish it. Similar-prompt counts do not become failure rates, and
evaluation plans do not count as measured improvements. Ordinary reflection and
trivial edits remain lightweight. Four synthetic cases cover these decisions in
[evals/correction-scenarios.json](evals/correction-scenarios.json).

## What it edits

| Skill location | How it's edited |
|----------------|-----------------|
| Project skills (`.claude/skills/`, `.agents/skills/`, `.codex/skills/`) | At their source location |
| `AGENTS.md` / `CLAUDE.md` | Verified repository-wide conventions, with authorization |
| `~/.claude/skills/` (personal) | In place |
| `~/.claude/plugins/` / `~/.codex/plugins/cache/` (marketplace-installed) | Never. Installs are overwritten on update, so edit the marketplace's source repo and release it there |

Substantive edits, description tuning, and new skills are handed to Anthropic's `skill-creator` skill
(installable from this marketplace as `skill-creator@powerful-plugins`) when it is installed. Without it, reflect says so and makes the change itself, testing it against
the cases that prompted it before and after the edit.

## Requirements

- Claude Code v2.x+ or OpenAI Codex
- Session mode: a matching transcript or an explicitly labeled current-session digest.
- History mode: workspace-scoped Claude/Codex session metadata, git history, and
  optional GitHub read access. Missing sources are reported, not replaced with
  invented historical evidence.
- Optional: a tracker MCP or CLI (Jira, Linear, GitHub Issues) for filing backlog items you approve, and `skill-creator` for
  substantive edits

## Credit

Ported from the `reflect` skill in
[`cursor/plugins`](https://github.com/cursor/plugins/tree/main/pstack/skills/reflect) (pstack, MIT,
© Lauren Tan). The lenses and triage criteria are upstream's; transcript discovery, subagent
spawning, and the routing targets are rewritten for Claude Code and Codex.

## Contributing

See the main [CONTRIBUTING.md](../../../CONTRIBUTING.md) for guidelines.
