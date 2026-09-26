---
name: reflect
description: Learn from the active session or recurring patterns across this workspace's sessions, git changes, and PR feedback. Use for reflection, introspection, skill evaluation, or improving repository guidance; propose evidence-backed edits through judgment, tooling, and divergent review lenses.
invoke: reflect
---

# Reflect

Find durable learnings in the current conversation or the workspace's history,
then route them into focused skill or repository-guidance edits.

## Choose the evidence scope

- **Session mode (default):** `/reflect:reflect` or a request about the current task uses
  the active transcript or an explicitly labeled digest.
- **History mode:** `/reflect:reflect --history`, `/reflect:introspect`, or a request about
  recurring corrections, previous sessions, git rework, PR feedback, or
  repository guidance uses [references/history-review.md](references/history-review.md).
  Build its bounded evidence packet before the review lenses below. Honor a
  supplied date range or repository scope; do not include other workspaces.

Both modes use the same Accepted / Rejected / Backlog process. History mode
adds source counts, citations, and missing-data limits to that report. It does
not add a second learning workflow or automatically rewrite CLAUDE.md.

## When to invoke

- The user requested reflection, introspection, skill evaluation, or repository-guidance improvements.
- A complex task (5+ tool calls) just landed cleanly and the recipe is worth keeping.
- The agent hit dead ends, found the working path, and the path generalizes.
- The user corrected the agent's approach mid-task.
- A non-trivial workflow emerged that isn't captured anywhere.

Skip when the conversation is trivial, off-topic, or already covered by an existing skill the parent
followed correctly. One-offs are not learnings. A correction or frustration
signal alone is not a reason to interrupt the user's active task or launch a
history scan. Follow an explicit learning request or an agreed wrap-up step.

## Process

### 1. Gather the evidence

For history mode, follow [history-review.md](references/history-review.md) and
use its packet in place of the active transcript in steps 2 to 6. For session mode,
use the available transcript or conversation context. When the request is to
reduce repeated corrections or evaluate the first usable result, also read
[correction-replays.md](references/correction-replays.md) to distinguish known
requirements from later input and prepare the applicable evaluation handoff.
Ordinary reflection and trivial edits do not require replay trials. In Codex, use a known
session path only after its session metadata identifies the current workspace;
otherwise use a digest. The following discovery procedure is for Claude Code.

Claude Code stores each session under `~/.claude/projects/<cwd-slug>/<session-id>.jsonl`. The slug is
the absolute working directory with its separators replaced by `-`, so the leading `/` becomes a
leading `-`; other punctuation in the path (`.`, `_`) may be replaced the same way.
The main transcript may reference separate subagent transcripts; include only
explicitly linked, same-session evidence when needed. Claude Code keeps them in
`<session-id>/subagents/agent-*.jsonl` next to the main file. When reflect itself
runs as a subagent, its own transcript is in that folder too; leave it out.

Derive the directory rather than assuming one encoding: resolve the full slug first, fall back to
separators-only, and confirm the directory exists before listing it:

```bash
dir=~/.claude/projects/$(pwd | sed 's/[^a-zA-Z0-9]/-/g')
[ -d "$dir" ] || dir=~/.claude/projects/$(pwd | sed 's|/|-|g')
ls -t "$dir"/*.jsonl 2>/dev/null | head -5
```

If neither directory exists, list `~/.claude/projects` and pick the entry whose name matches this
workspace's path, never a different workspace's.

Resolve only the current workspace's directory. Do not glob across `~/.claude/projects/*/`: that
crosses workspace boundaries and reads private sessions from unrelated projects.

Prefer an explicit active-session path or ID from the runtime. Otherwise parse
candidate JSONL records: skip metadata/tool-result records, verify recorded
workspace metadata, and compare the first actual user text with the opening
prompt and known session context. The first line need not be a user message.
If several candidates match (for example forks), use the known session ID; do
not treat the newest file alone as proof that it is the active conversation.

Take the uniquely matching path. If no path resolves unambiguously (a sandbox with no transcript on disk, a resumed session
whose file moved), write a tight digest of the session (the task, the dead ends, the corrections,
the commands that worked) and pass that to the reviewers instead of a path.

A long session's transcript is too large to read whole (several megabytes is common). Give the
reviewers a one-line-per-event index next to the path, so they can search it and then open the
full records they cite. Write it outside any repository, since it holds prompts and tool output,
and delete it (`rm -f "$index"`) once synthesis is done:

```bash
transcript="$dir/<session-id>.jsonl"   # the path resolved above
index=$(mktemp -t reflect-index.XXXXXX)
jq -r 'select(.type=="user" or .type=="assistant") | .timestamp as $t
  | (if (.message.content|type)=="array" then .message.content[] else {type:"text",text:.message.content} end)
  | if .type=="tool_use" then "\($t) USE[\(.name)] \(.input|tostring|.[:600])"
    elif .type=="tool_result" then "\($t) RES \(.content|tostring|.[:800])"
    elif .type=="text" then "\($t) TEXT \(.text|.[:2000])" else empty end
  | gsub("\n"; " ")' "$transcript" > "$index"
```

### 2. Spawn three reviewers in parallel

Use the environment's subagent tool for three independent reviewers when
available and permitted. Leave model selection at the session default. Each
reviewer gets the same evidence and its lens template; reviewers may read cited
context but must not change files or external systems. Wait for all results
before synthesis. If delegation is unavailable, apply the three lenses
sequentially and disclose that the review was not independent.

| Lens | Prompt template |
|---|---|
| Judgment | `references/judgment-reviewer.md` |
| Tooling | `references/tooling-reviewer.md` |
| Divergent | `references/divergent-reviewer.md` |

Pass each template verbatim as the agent prompt, substituting the transcript path, session digest, or bounded history packet
where marked. In session mode with a path, use the packet marker for a short evidence manifest: the
transcript path, the index, any linked subagent transcripts, and the time window. Writing each
substituted template to a file and pointing the reviewer at it is equivalent, and saves copying it
into three prompts. The templates forbid file writes; the parent applies every edit itself.

### 3. Synthesize

Use `references/synthesizer.md` with the evidence scope and each reviewer's
full output inlined where marked. The synthesizer may read cited context to
verify findings, but must not mutate it. Use a separate agent when permitted,
otherwise synthesize locally. It returns Accepted / Rejected / Backlog lists.

### 4. Structural enforcement check

Sanity-check the synthesizer's Accepted list. Move to Backlog any item a lint rule, script, hook,
frontmatter flag, or CI check would enforce more reliably than prose. The synthesizer already applies
this criterion; this is the final pass before edits land. Skill prose is for what mechanisms cannot
enforce.

### 5. Apply

Present the full Accepted / Rejected / Backlog output with concrete proposed
edits before applying them. Reuse explicit authorization already given for the
identified changes; otherwise ask which rows to apply. A request to inspect or
reflect alone authorizes analysis, not edits to shared skills or repo guidance.

Backlog items are tracker submissions rather than skill changes, so ask about them separately in
one line offering to file the listed items to the team's tracker (a Jira, Linear, or GitHub Issues
MCP or CLI, where one is connected).
File only what the user approves; otherwise leave them in the summary for someone to pick up. An unrequested
ticket is tracker noise.

For each approved item, follow the Routing field exactly:

- **`repo guidance: <AGENTS.md or CLAUDE.md path + section>`**: add or revise a
  concise convention in the file that owns it. Preserve existing rules and
  includes. Do not add a boilerplate self-improvement section or an automatic
  frustration trigger. This route requires evidence of a repository-wide
  convention; prefer the relevant existing skill for a task-specific workflow.

- **Trivial existing-skill edit** (a one-line bullet, a tightened sentence, a stale fact corrected):
  edit it directly.
- **Substantive existing-skill edit** (a new section, a new pattern table, more than ~10 lines): hand
  it to the `skill-creator` skill and run its draft / test / iterate loop. For
  correction-driven updates, include the separated replay inputs and grading
  evidence described in `references/correction-replays.md`.
- **`tune description: <skill path>`** (the skill exists but didn't trigger when it should have):
  hand it to `skill-creator` and run its description-optimization loop.
- **`new skill: <kebab-name>`**: hand creation to `skill-creator`. Do not invent the shape ad hoc.

`skill-creator` is Anthropic's skill-authoring skill, shipped in this marketplace as
`skill-creator@powerful-plugins`. If it is not installed, tell the user how to install it, then make the change yourself in the Agent Skills format and test it
against the cases that prompted it before and after the edit.

**Edit the source, not the install.** A skill installed from a marketplace lives under
`~/.claude/plugins/` and is overwritten on the next update. Edit a local checkout of the
marketplace repository the plugin came from (the `source` recorded for it in
`~/.claude/plugins/known_marketplaces.json`, or its plugin manifest's `repository`), then ship the
change through that repository's own release process, including any Codex catalog regeneration it
requires. If no checkout is available, give the user the exact edit to propose upstream instead of
patching the install. Project skills under `.claude/skills/`, `.agents/skills/`, or `.codex/skills/`
and personal skills under the runtime's user skill directory are edited at their
actual source location. Codex plugin caches under `~/.codex/plugins/cache/` (or
an explicitly configured Codex home) are also generated installs, not sources.
A checkout may also contain generated skill adapters. Follow their source
references and the repository's ownership metadata to the authoring file;
regenerate adapters using that repository's tooling instead of editing them.

Run any SKILL.md validator the environment ships on every touched skill before declaring done. In a
plugin marketplace repo that is usually `claude plugin validate --strict .` plus whatever catalog or
adapter check the repo documents (for example a `--check` mode of its Codex generator). Skip this
step where no validator exists.

### 6. Summarize for the user

Short list, no preamble:

- Evidence scope: session or history; sources examined and unavailable sources.
- Edits applied: `<skill or repo-guidance path>`. What changed, one line each.
- New skills created: `<skill path>`. One line each (rare).
- Backlog filed: `<issue title>` (`<tracker>`). One line each.
- Dropped: one line per rejected finding + reason from the synthesizer.

## Credit

Ported from the `reflect` skill in [`cursor/plugins`](https://github.com/cursor/plugins/tree/main/pstack/skills/reflect)
(pstack, MIT). The lenses and the triage criteria are upstream's; transcript discovery, subagent
spawning, and the routing targets are rewritten for Claude Code.
