# History review

Use for `/reflect:reflect --history`, `/reflect:introspect`, or a request to learn from recurring
workspace history. This is the evidence-gathering mode of reflect, not a separate
apply workflow. Continue with the three lenses and synthesis in `SKILL.md`.

## Bound the review

Resolve the current workspace's canonical path and git repository. Honor the
user's selected repo, date range, and source limits. Otherwise inspect at most
10 recent matching sessions, 40 recent commits, and 8 recently merged PRs in this
repository. Record the limits and actual counts. Include other worktrees or
repositories only when the requested scope includes them.

Missing access is a reportable limitation, not permission to widen the search.
If the user supplies an evidence packet, review it as supplied without collecting
extra history unless needed to verify a specific finding.

## Session evidence

For Claude Code, use the workspace-specific directory discovery in `SKILL.md`.
Use `sessions-index.json` when present, sorting by the recorded modification time
before selecting the newest matching sessions. Resolve each indexed `fullPath`
and verify that it stays inside that workspace's transcript directory before
reading it. Check recorded workspace metadata when present. If the index is
missing, list JSONL files in that directory, confirm their workspace, and order
by recorded timestamps (filesystem mtime only as a labeled fallback).

For Codex, prefer a session-discovery tool that can filter by workspace. Otherwise
locate the configured Codex session store and inspect only the initial
`session_meta` record of candidates to compare `payload.cwd` with the canonical
workspace path. Read conversation payloads only after an exact match. Do not
print or collect other projects' prompts while locating matching metadata. If
metadata cannot establish scope, skip that candidate and report the gap.

Parse JSONL records, handling text strings and arrays of text blocks. Use Claude
`type: user` messages and Codex user-message events/response items; exclude tool
results, duplicated event/response representations, and subagent echoes from
recurrence counts. Ignore malformed records with an explicit skipped-record
count rather than treating a parse failure as an empty history. Retain relevant
assistant invocation/read records separately, with source citations, to verify
which skills were actually loaded. Do not count those records as user corrections
or infer skill use from a generic command that matches a skill's documentation.

Look for corrections, repeated setup, misunderstood scope, missing context, and
workflows the user had to explain again. Search terms such as “again”, “wrong
file”, or “use X” are candidates, not proof: read surrounding turns before
classifying a correction. Capture a short relevant excerpt, timestamp, session
identifier, and line/turn reference. Redact credentials and unrelated personal
or customer details from the packet.

## Git evidence

Inspect recent commit subjects to find possible fixes, reverts, repeated edits,
and follow-up corrections. For example, `git log -40 --format='%h %as %s'` is a
starting point when no date range was requested. Read the relevant diff and its
context before treating a “fix” subject as rework. Ordinary maintenance, feature
work, and one isolated revert do not establish a recurring agent mistake.
Record commit SHAs and source paths as citations, not proposed permanent rules.

## PR feedback

Discover the repository owner/name from its git remote or `gh repo view`, then
list recent merged PRs within the selected bounds. Read conversation comments,
review summaries, and inline review comments; the last group is not included in
`gh pr view --json comments,reviews`.

With `gh`, the relevant read endpoints are:

```text
gh api --paginate repos/OWNER/REPO/issues/NUMBER/comments
gh api --paginate repos/OWNER/REPO/pulls/NUMBER/reviews
gh api --paginate repos/OWNER/REPO/pulls/NUMBER/comments
```

Use the discovered identifiers, or equivalent read-only connector tools. Preserve
comment IDs/URLs and the reviewed commit. Verify claims against the diff and
follow-up discussion. A bot repeating the same comment across reviews is one
finding, not independent evidence that the problem recurs. Posting replies,
reactions, issues, or review requests is outside this evidence-gathering step.

## Existing guidance and routing

Read the applicable `AGENTS.md` and `CLAUDE.md`, including their referenced
instructions, and only the skills relevant to the candidate patterns. Do not
read every installed skill. Compare each proposal with the existing wording:

| Evidence | Candidate route |
|---|---|
| Task-specific behavior recurs and its skill has a gap | Existing skill body/section |
| Historical catalog proves visibility and a sufficiently complete trace proves missed loading on an in-scope task | `tune description: <skill path>` |
| Historical visibility or invocation evidence is missing | Mark activation unknown; do not diagnose a trigger failure |
| Stable repo convention has no task-specific owner | `repo guidance: <AGENTS.md or CLAUDE.md path + section>` |
| Recurring multi-step workflow has no existing home | `new skill: <name>` |
| Existing clear guidance already covers it | Reject as execution failure/already-covered |
| A script, lint rule, hook, or CI check would enforce it | Backlog with the proposed mechanism |

Count independent incidents, not repeated wording. Keep contradictory evidence
and one-off preferences visible. No corrections in the accessible sources is a
valid result; missing sources are not evidence of a clean history.

## Evidence packet for the lenses

Provide the same compact packet to all three reviewers:

1. Scope: canonical workspace, date range/source limits, and history mode.
2. Coverage: sessions/commits/PRs examined, unavailable sources, skipped records.
3. Candidate incidents: source ID, date, excerpt or diff reference, surrounding
   context, and any corroborating or contradictory source. For a correction
   replay, include which requirements were available before the first delivered
   result and which were introduced later, following `correction-replays.md`.
4. Current guidance: relevant file paths and excerpts, plus observed skill/tool
   usage. If no transcript proves invocation, say so; a PR comment cannot prove
   a skill was used.

For history mode, reviewer evidence may cite a session, git diff, or PR comment.
The active-session “skill was used” rule still applies to skill-body edits: show
actual invocation evidence. Verified repo-wide conventions may route to the
existing AGENTS.md/CLAUDE.md owner without pretending a skill was invoked.
Preserve exact citations and distinguish one incident seen in several sources
from several independent incidents.

Prepend the coverage summary to the standard Accepted / Rejected / Backlog
report. Every accepted proposal needs its supporting citations and the concrete
edit or placement. Apply only changes authorized by the user via `SKILL.md`'s
apply step. Do not automatically insert self-improvement rules, create a tracker
issue, or interrupt unrelated work.
