# Spark

Ideation and design quality tools for engineering.

Three scopes: `/spark` for what to build next, `/forge` to turn the change in
front of you into its simplest, sturdiest form, `/audit` for what's wrong with the codebase's model.

## Installation

```bash
# Claude Code
/plugin marketplace add StackOneHQ/powerful-plugins
/plugin install spark@powerful-plugins

# Codex
codex plugin marketplace add StackOneHQ/powerful-plugins
codex plugin add spark@powerful-plugins
```

## Skills

This README uses the short names. In Claude Code the full commands are `/spark:spark`,
`/spark:forge` and `/spark:audit`; in Codex they are `$spark:spark`, `$spark:forge` and
`$spark:audit`.

| Skill | Description |
|-------|-------------|
| `/spark` | Find the single smartest, most innovative addition to your current PR/branch or project, then implement it |
| `/forge` | Rewrite a diff, branch or PR into its simplest, sturdiest form and strip agent-written slop, then prove behaviour is unchanged; answer design questions and revise plans |
| `/audit` | Read-only simplification audit of a whole codebase (or several): coverage contract, bounded parallel reviewers, ranked findings published as a visual report |

## Usage

### Spark

Invoke with `/spark` or phrases like "what's the best next move here?"

Spark reads your git context, proposes **one specific, surprising idea**, and offers to build it.

### Forge

Invoke with `/forge` or phrases like:

- "is this the best way to do this?"
- "verify this plan"
- "are we leveraging X effectively?"
- "critique this design"
- "deslop this" / "remove the AI slop from this branch"

Forge is a rewrite, not a review. Pointed at code with an imperative ("forge this", "unslop the PR"), it rewrites the change and runs a loop: measure the slop, read the surrounding code, rewrite, **re-check the lines it wrote itself**, prove the tests behave identically, and repeat until a pass changes nothing. Asked a question ("is this the best way?"), it answers with each finding and the concrete rewrite, and applies nothing. Given a plan, it returns the revised plan.

The rewrite applies seven moves in order: delete, reuse what already exists, collapse single-use abstractions, trust the types, name it, make wrong states unrepresentable, and only then comment. Comments follow a contract: a constraint the code cannot express or a contract the signature hides, two lines by default, every claim checked against the code. Duplicates and slop are fixed in the same pass, never deferred as follow-ups.

`scripts/slop-meter.mjs` measures what a diff adds against the files it lands in: prose comment lines, comment density against the file or its siblings, the longest comment block, type escapes, ticket ids and LLM vocabulary in comments, copied blocks, and calls that repeat a configured call to one of the repo's own functions. Text inside an ordinary string literal is code, not comment; a Python docstring counts as comment. It skips files marked `linguist-generated` in `.gitattributes` and any `--exclude <glob>`, and says which. Forge runs it before and after, and the result must not be worse.

#### Related skills

Forge covers slop in **code**. For the rest:

| Need | Plugin |
|---|---|
| Slop in prose: docs, PR descriptions, commit messages, the wording of a kept comment | [`natural-writing`](../../documentation/natural-writing/) |
| A PR-comment-style review with dedicated simplifier, comment-accuracy, and silent-failure agents | `pr-review-toolkit` (Anthropic's, pinned in this marketplace) |
| Codebase-wide simplification, and a security pass | `/audit` in this plugin, and Claude Code's built-in `/security-review` |

### Audit

Invoke with `/audit` or phrases like:

- "audit this codebase"
- "where should we simplify?"
- "audit our repos for bad state representation"

Audit is a coordination run, not a read-through. It inventories every subsystem
into a coverage contract, dispatches bounded read-only reviewers (max two
findings each, or `skip`), verifies every finding against the tree itself, then
audits its own output for missing coverage, overlap, over-abstraction, schema
gaps, and priority ordering before reporting ranked findings.

Results are published as a **visual report artifact**: coverage strip, top
slices, ranked finding cards with file:line evidence, the full subsystem
inventory including skips, and a dependency graph where findings block each
other. The markdown report stays the record; the page is what gets shared into
a planning meeting.

Three scopes:

| Scope | What it covers |
|-------|----------------|
| Current | The subsystems your branch or working tree touches |
| Whole codebase | Every identifiable subsystem in the repo |
| Multiple codebases | Each repo/package separately, plus a cross-codebase pass for divergent models and contract drift |

**Audit never writes to your repository.** No edits, no test runs, no commits;
the only output is the report. Implementing a finding is a separate follow-up
you opt into afterwards.

#### Forge or Audit?

Use `/forge` for the change in front of you; use `/audit` for the codebase
behind it.

## Requirements

- Claude Code v2.x+ or OpenAI Codex
- Git repository (for context detection)
- `gh` CLI optional (for PR description/comments)
