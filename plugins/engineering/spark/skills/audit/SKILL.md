---
name: audit
description: Run a read-only simplification audit across a whole codebase (or several) for materially useful improvements to data structures, state representation, control flow, algorithms, and ownership. Use when the user invokes "/audit" or asks to "audit this codebase", "audit the repo", "find simplifications across the project", "what should we simplify", "where is our state representation wrong", or wants a systematic, subsystem-by-subsystem review rather than a critique of one diff. Coordinates bounded parallel reviewers, enforces a coverage contract, audits its own output, and publishes the ranked findings as a visual report artifact.
invoke: audit
---

# Audit — Systematic Simplification Audit of a Codebase

Find **materially useful simplifications** in data structures, state representation, control flow, algorithms, and ownership — across an entire codebase, a set of codebases, or just the subsystems in play right now.

This is a coordination job, not a single read-through. You are the coordinator: establish a coverage contract, dispatch bounded reviewers, verify every finding yourself, then audit the audit before reporting.

## The Read-Only Contract

**This skill does not change the repository.** No edits, no test runs, no installs, no commits, no pushes, no fixes "while I'm in there". Read-only inspection commands only (`git log`, `git diff`, `grep`, `find`, reading files, read-only static-analysis tools that don't write to the tree).

The one artifact you may write is the audit report itself, and it goes to a scratchpad path outside the source tree unless the user asks for it in-repo. State this constraint to the user up front so they know what they're getting; if they want fixes applied, that is a separate follow-up after the audit is delivered (Step 8).

## Forge or Audit?

| | `/forge` | `/audit` |
|---|---|---|
| Scope | One plan, diff, or implementation | Whole subsystems, whole repo, or several repos |
| Question | "Is this change the best it can be?" | "Where is this codebase's model wrong?" |
| Shape | Measure, rewrite, re-check its own lines, prove behaviour | Coverage contract, bounded reviewer lanes, self-audit |
| Output | The rewritten code and a short report | Ranked findings with evidence, scope, risk, validation |

If the user is asking about the change in front of them, run `/forge`. If they're asking about the codebase, run this.

## Step 1: Establish Scope

Detect state, then confirm the mode before spending reviewer budget:

```bash
git rev-parse --show-toplevel 2>/dev/null    # Repo root
git branch --show-current
git status --short
# The base is where this branch left the default branch; never assume main.
default=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD)   # e.g. origin/main
if [ -n "$default" ] && base=$(git merge-base HEAD "$default"); then
  git diff --stat "$base"...HEAD
else
  echo "No base: origin/HEAD is not set or shares no history with HEAD. Ask the user which branch is the base."
fi
ls -la
```

If it printed "No base", ask the user which branch is the base rather than guessing, and set `base=$(git merge-base HEAD <that branch>)` before any step below that uses `$base`. If the canonical repo is another remote (`upstream` in a fork), use that remote's `HEAD` instead of `origin`'s.

Three modes:

### Current-Scope Audit
The subsystems the active branch or working tree touches, plus the subsystems that own the interfaces those files cross. Use when there's live work in progress and the user says "audit this" / "audit what I'm working on".

Derive the inventory from changed paths:
```bash
git diff --name-only "$base"...HEAD
```
Then expand: for each changed file, the module that owns it is one subsystem row. Do not stop at the file list — a change to one caller of a bad model is evidence about the model, not about the caller.

### Whole-Codebase Audit
Every identifiable subsystem in the repository. The default when the user says "audit this codebase" or is on the default branch with no active work.

### Multi-Codebase Audit
Several repositories, or several independently-owned packages of a monorepo. Use when the user names more than one target, points at a workspace root, or asks about "our codebases".

Run the full Step 2–5 flow **per codebase**, keeping inventories separate so ownership boundaries stay honest. Then add one **cross-codebase pass** that only looks for what a single-repo audit structurally cannot see:

- The same domain model defined independently in each codebase, already diverging
- Contract drift between a producer and its consumers (generated clients, event schemas, shared JSON shapes)
- The same algorithm or state machine reimplemented per repo with different bug sets
- State whose true owner is ambiguous *between* codebases — both write, neither is source of truth

Cross-codebase findings get their own section and are ranked with everything else.

When the mode is ambiguous, ask once (with `AskUserQuestion` in Claude Code) (Current work / Whole codebase / Several codebases), then commit. Don't ask twice.

## Step 2: Build the Coverage Contract

Inventory every identifiable subsystem in scope. A subsystem is a unit with a real ownership boundary — not a directory listing, and not one catch-all row per top-level folder.

Each row gets:

| Field | Meaning |
|---|---|
| ID | Stable short ID (`SS-01`) you reference everywhere after this |
| Name | Descriptive, matches how the team talks about it |
| Boundary | Exactly what this row owns — and what it does not |
| Key files | Implementation entry points |
| Interfaces | Public API, exported types, major call sites, tests |
| Status | `queued` / `in review` / `recommend` / `skip` |

Cover, where materially relevant: frontend, backend, shared infrastructure, platform bridges, generated-contract ownership (who owns the schema, who owns the generator, who owns the output), build/CI tooling, and test infrastructure. Test and tooling code is real code with real state models — include it when it's substantial.

Write one canonical report file and keep it current for the whole run. It contains:

1. Subsystem inventory (the contract)
2. Confirmed opportunities
3. Explicit skip decisions, with the reason
4. Cross-cutting patterns
5. Duplicates and superseded findings
6. Final priorities and dependencies
7. Audit log — every dispatch, every harvest, every verification verdict

Default path: the session scratchpad, e.g. `<scratchpad>/audit-<repo>-<date>.md`. In-repo only if the user asks.

**The inventory is a contract, not a suggestion.** A broad catch-all row does not prove coverage of what it swallows. If you can't state a row's boundary in one sentence, it's two rows.

## Step 3: Run Bounded Subsystem Reviews

Dispatch fresh, read-only reviewers — one distinct subsystem each, non-overlapping boundaries. Use the subagent tool where available (`Task`/`Agent`, read-only tool set); where it isn't, run lanes sequentially in this session and keep the same discipline.

**Concurrency**: bound it to the number of lanes you can actually coordinate — typically 4–6. Use one consolidated wait, don't kill slow-but-productive workers, and close each worker after harvesting. Batch until every `queued` row is closed.

**Scale to the codebase.** A 12-file utility repo is one lane and ten minutes, not a fleet. Reserve full fan-out for codebases with genuinely separable subsystems.

**A reviewer starts with no context.** It cannot see this conversation, the inventory, the files you have already read, or what any sibling reviewer found. Whatever the dispatch omits does not exist for it. Every dispatch therefore carries the assignment envelope *and* the brief — the brief alone is a job description with no job attached.

Envelope, filled in per subsystem:

```
repo (absolute path):  <path>
subsystem:             <SS-xx> — <name>
ownership boundary:    <exactly what this row owns>
explicitly NOT yours:  <adjacent rows that would otherwise look in scope>
key files:             <paths>
public interfaces:     <exported API, types, major call sites>
tests:                 <paths, or `none found`>
build/dep manifest:    <path, or `none`>

Return: at most two opportunities in the field order below, or the single word `skip`.
```

Then the brief, verbatim:

> Review the assigned subsystem for **at most two** materially useful simplifications in its data structures, state representation, or organizing model.
>
> Inspect its implementation, public interfaces, major call sites, and existing tests. Stay inside the assigned ownership boundary. You may name cross-subsystem concerns, but do not expand scope to solve them.
>
> Look for:
> - Scattered booleans or nullable fields that permit invalid combinations, and should be a state machine or discriminated union
> - Repeated assumptions about object shape that want a shared typed model
> - Duplicated branching that a small map, registry, reducer, or command model would remove
> - Unclear ownership of state or behavior that a small module boundary would clarify
> - Repeated scans, transformations, or lookups where a better collection or index materially simplifies the behavior (not just the constant factor)
> - Lifecycle, concurrency, or async states whose representation permits stale or contradictory state
>
> Do not force an abstraction. Prefer boring local code when it is already clear.
>
> Do not recommend changes for stylistic consistency, hypothetical extensibility, minor line-count reduction, or moving existing branching behind a new type.
>
> Return at most two opportunities. If nothing clearly clears the bar, return `skip`.
>
> For each recommendation, return:
> 1. **Verdict** — recommend or skip
> 2. **Evidence** — exact file and line references
> 3. **Current complexity or invalid states** — what the present representation permits that it shouldn't
> 4. **Proposed representation** — and why it is simpler, not merely different
> 5. **Smallest credible implementation scope** — affected files and interfaces
> 6. **Regression risks and migration concerns**
> 7. **Validation** — existing tests that cover this, plus what else would be needed
> 8. **Counter-example** — the exact `file:line` a reader can open to see the problem for themselves: the field that permits the invalid combination, the second definition of the duplicated type, the branch that contradicts the other branch. Quote the line. No counter-example, no recommendation — return `skip` instead.
>
> Do not rate your own confidence. The coordinator verdicts every finding against the tree (Step 4); your job is to make that check cheap, by citing lines that can be opened.
>
> Read-only. Do not modify, create, run, or install anything.

## Step 4: Verify and Synthesize

**Every finding is unverified until you check it yourself against the current repository.** Workers hallucinate line numbers, miss the caller that explains the design, and mistake intentional semantics for accidents. Open the cited files.

Give every finding one of two verdicts. There is no middle rating, and no self-assessment survives from the worker:

- **`CONFIRMED`** — you opened the cited `file:line` and it says what the worker claimed. The counter-example is real, and it demonstrates the problem rather than merely sitting near it.
- **`SPECULATIVE`** — everything else. Dropped from the findings, **counted in the coverage strip**, never silently discarded.

A finding is `SPECULATIVE` when it cites code that doesn't exist or doesn't say what the worker claims; duplicates another finding (merge into the one authoritative subsystem); misreads intentional semantics (the "redundant" flag that encodes a real distinction); only relocates complexity behind a new name; or is a style preference wearing an architecture costume. Anything you did not actually open is `SPECULATIVE` by default — an unread citation is not evidence, and a plausible-sounding one is the specific thing this bar exists to catch.

Why this replaces a confidence rating: a worker rating its own finding is grading its own homework, and the rating carries no information a reader can check. "I opened line 214 and it does contain three booleans that permit four impossible states" is verifiable by anyone; "confidence: high" is not.

Record skips as **completed coverage**, not as gaps. Assign each surviving recommendation to exactly one owning subsystem. Keep opening batches until every inventory row is `recommend` or `skip`.

## Step 5: Audit the Audit

Before reporting, run fresh independent passes — each one blind to the others' conclusions — for:

| Pass | Asks |
|---|---|
| Coverage | What subsystem is missing from the inventory entirely? |
| Overlap | Do two rows claim the same code, or two findings the same problem? |
| Materiality | Which findings are over-abstraction, taste, or churn dressed as simplification? |
| Schema | Which findings are missing evidence, scope, risk, or validation fields? |
| Priority | Does the ranking respect real dependencies between findings? |

If the coverage pass finds a real omission, **add an explicit subsystem row and audit it**. Never hide an omission by widening a boundary that's already marked complete — that turns the contract into fiction.

Then rank by concrete impact, implementation effort, blast radius, and prerequisites — every finding being ranked is already `CONFIRMED`, so correctness is not a ranking axis — and name the best first slices — the findings that are high-impact, low-blast-radius, and unblock others.

## Step 6: Report

The markdown report is the record of the audit. Write it first, in full — the visual in Step 7 is rendered *from* it, never instead of it.

```
# Audit — <scope> — <date>

## Coverage
<n> subsystems inventoried · <n> recommend · <n> skip · <n> added by the coverage pass · <n> findings dropped as SPECULATIVE

## Top Slices
1. [SS-xx] <finding> — <why this one first>
2. ...

## Findings (ranked)

### [SS-xx] <Title>  ·  impact <high/med/low> · effort <s/m/l> · blast radius <n files>

**Counter-example**: `path/file.ts:214` — <the line, quoted>
**Evidence**: `path/file.ts:120-148`, `path/other.ts:30`
**Today**: <what the representation permits that it shouldn't>
**Proposed**: <the representation, concretely>
**Scope**: <files and interfaces touched>
**Risks**: <regressions, migration>
**Validation**: <existing coverage + what's needed>
**Depends on**: <finding IDs, or none>

## Skips
| ID | Subsystem | Why it's fine as-is |

## Cross-cutting patterns
<patterns appearing in 3+ subsystems — these are usually the real finding>

## Cross-codebase   (multi-codebase mode only)
<divergent models, contract drift, duplicated state machines, ambiguous ownership>
```

## Step 7: Visualise It

**A full-codebase audit is a deliverable with an audience — publish it as a visual artifact, don't leave it in terminal scrollback.** Findings get triaged in a planning meeting, argued over, and worked through across weeks; a scrollable ranked page with the evidence attached survives that, a wall of terminal output does not. Do this by default for whole-codebase and multi-codebase runs, and for current-scope runs whenever there's more than a handful of findings. Say what you're doing and hand over the link — don't ask permission first.

Publish with the `Artifact` tool where available. Where it isn't, write a single self-contained HTML file to the scratchpad and hand it to the user.

**Publishing an artifact does not violate the read-only contract** — it writes a page, not the repository. The tree stays untouched either way.

What the page has to do, in priority order:

| Element | Why it earns its place |
|---|---|
| **Coverage strip** at the top | `n` subsystems · `n` recommend · `n` skip · `n` added by the coverage pass · `n` dropped as SPECULATIVE. This is the audit's central claim — lead with it, dropped count included |
| **Top slices** | The 2–4 findings to start Monday, called out above everything else |
| **Ranked findings as cards** | Impact / effort / blast-radius as scannable badges; the quoted counter-example, proposed representation, risks, and validation in the body. Only `CONFIRMED` findings become cards |
| **Subsystem inventory table** | Every row with its status chip. Filterable by status if there are more than ~15 rows |
| **Skips, visible** | Same table, not a hidden appendix. Coverage is the claim; the skips are the proof |
| **Dependency graph** | Only when findings actually block each other — a small inline SVG or mermaid graph of the prerequisite edges. Skip it for a flat list |
| **Cross-cutting patterns** | The section that most often holds the real finding — give it visual weight, not a footnote |

In multi-codebase mode, one page with a section per codebase plus the cross-codebase section — not one page each. The comparison is the point.

Rules for the page:

- **Every number and quote comes from the verified report.** The artifact is a rendering, not a second pass. Do not let a chart's need for a tidy shape invent a count, a severity, or a finding.
- **File:line evidence stays visible** on each finding. A finding you can't trace back to code is a finding nobody will action.
- **Self-contained and theme-aware** — inline CSS/JS, no external assets, readable in light and dark.
- **Scannable before it is readable.** A reader should get coverage, the top slices, and the shape of the risk in fifteen seconds, then be able to drill into any finding.

## Step 8: Hand Off

Then offer the follow-up — and it is a follow-up, not part of the audit:

> "Audit's read-only and the tree is untouched. Here's the report: <link>. Want me to implement the top slice?"

If yes, that's a new task: plan it (plan mode where the tool has one), implement, validate. Do not start implementing inside the audit run.

## Completion Bar

The audit is done only when:

- Every identifiable subsystem has been reviewed
- Every subsystem has a recommendation or an explicit skip
- Every reported finding is `CONFIRMED` against an opened counter-example, and carries complete evidence, scope, risk, and validation fields
- Findings dropped as `SPECULATIVE` are counted in the report, not silently discarded
- Duplicates and weak abstractions have been removed
- Priorities and dependencies are internally consistent
- **The repository is unchanged** — verify with `git status --short` and say so in the report

## Principles

- **Coverage is claimed, then proven.** A row you never dispatched is not covered, however plausible its name.
- **Verify every finding against the tree.** An unverified worker report is a rumor.
- **Skip is a first-class result.** A codebase where 70% of subsystems are correctly boring is a healthy one. Manufactured findings destroy the signal of the real ones.
- **Materially useful, or nothing.** The bar is invalid states made unrepresentable, real duplication removed, ownership clarified — not fewer lines.
- **Don't force abstraction.** Boring local code that's already clear is the correct answer more often than a registry.
- **Cite exact lines.** Every claim points at code a reader can open.
- **Rank by what to do Monday.** The list is only useful if the top item is obviously the right first move.
- **Ship it as a page.** An audit nobody can re-read, filter, or share is an audit that gets skimmed once and forgotten. The findings outlive the session — the format should too.
- **The visual renders the audit, it doesn't perform it.** Every figure on the page traces to a verified finding. A chart that needed a rounder number is a chart that gets a worse number.
- **Read-only means read-only.** The value of this skill is that the user can run it on anything without risk. Breaking that once costs it permanently.
