---
name: forge
description: Use when code or a plan should become its simplest, sturdiest form. Triggers on "forge", "unslop", "deslop", "remove the AI slop", "clean this up", "simplify this", "make this elegant", "is this the best way", "critique this design", "verify this plan", and on any diff that reads as agent-written: bloated or inaccurate comments, checks nobody needs, one-caller wrappers, a helper duplicated from elsewhere in the repo, tests that mirror the code.
invoke: forge
---

# Forge

Forge turns working code into the version a senior engineer would be proud to have written: the fewest moving parts that fully do the job, named so they need no explanation, sturdy where the world is unreliable and nowhere else. Future-proof means the next likely change touches one place, not that there are extension points for changes nobody has asked for.

**Forge is a rewrite, not a review.** When the target is code, the deliverable is the improved code. A report without the rewrite is a failed forge.

## Target

| The user... | Forge... |
|---|---|
| points at code, a diff, a branch or a PR with an imperative: "forge this", "unslop", "clean it up" | runs the loop below and rewrites it, then reports in the short shape |
| asks a question about code: "is this the best way?", "does this look AI-written?" | answers with each finding and the concrete rewrite for it, and applies nothing |
| gives a plan with no code | returns the revised plan, each change with its reason |

Default scope is the current branch against its base. Resolve the base; never assume `main`: `git merge-base HEAD <remote>/<default-branch>`, taking the remote whose URL is the canonical repo.

When rewriting, forge edits the working tree and runs the meter, lint, typecheck and tests without asking; for a question or a plan it changes nothing. Committing and pushing stay with the user.

## The loop

Every forge on code runs this loop. The re-check in step 4 is the part that matters most: a rewrite writes new lines and new comments, and slop that forge writes itself is the slop that survives a forge.

1. **Measure.** `node ${CLAUDE_PLUGIN_ROOT}/scripts/slop-meter.mjs --repo . --base <base>`. It reads the working tree, so uncommitted and untracked work counts. It skips, and lists, the files the repo marks `linguist-generated` in `.gitattributes`; pass `--exclude <glob>` for generated output the repo does not mark, and change that output through its generator, never by hand. Keep the numbers: they are the before.
2. **Read.** Every touched file in full, one untouched sibling of each, the helpers and shared types next to them, the dependency manifest, and the repo's own rules: `CLAUDE.md`, `AGENTS.md` and any in-repo skills. You are looking for what already exists, what the team's own code looks like, what the diff duplicates, and what the rules require. Open every copy and reuse candidate the meter lists. Where a specific rule and a general one disagree, the specific one wins.
3. **Rewrite.** Apply the moves below, in order, to the lines this change owns.
4. **Re-check your own lines.** Diff your result against the input. Hold every line you wrote or kept to the same bar as the lines you removed: each comment against the comment contract, each check and branch against "does the type or the caller already guarantee this?". For every comment, name the line that makes each of its claims true; a claim you cannot point to is fixed or deleted. Re-run the meter with the same command.
5. **Prove behaviour.** Run the repo's lint, typecheck and the affected tests. The same tests pass and fail as before your rewrite.
6. **Repeat steps 3 to 5 until a pass changes nothing.** Then report.

Exit only when all hold: a full pass over your own diff found nothing to change; none of the meter's counts (comment lines, longest comment block, type escapes, `try` blocks, optional chains, nullish defaults, risky regexes) is higher than before; every copy it lists is gone or reported as unfinished; the tests match.

## The moves

In this order. Earlier moves remove the need for later ones.

1. **Delete.** Dead code, unreachable branches, unused parameters and imports, compatibility shims, fallbacks for states that cannot happen, leftover logging, scratch files. Deletion is the highest-value edit forge makes. A dependency is unused, or test-only, only when no remaining package lists it as a peer dependency and no config, script or runtime loader names it; your own imports alone never prove it.
2. **Reuse.** Call what already exists in the repo, its shared types or a declared dependency. First list the inputs on which the copy and the original disagree. None: call the original. Some: keep the correct one and fix the other; never add a flag to the original to cover both. Extract a new shared helper only at the third copy.
3. **Collapse.** A shallow wrapper, one whose interface is as complex as its body, becomes inline code; a function that hides real complexity stays, even with one caller. An interface with one implementation goes unless it is exported, a test seam, or the boundary to an external system. Two branches with the same outcome become one. A boolean flag parameter becomes two functions, or none. A regex that needs a comment to be read becomes string methods or named parts, and no regex on untrusted input nests quantifiers.
4. **Trust the types.** Remove a check only when the value's origin is visible and reaches it without `as`, `any` or `JSON.parse`; an exported function's unseen callers guarantee nothing. A result from code you cannot open, a database, a module outside the repo, a network call, has no visible origin: "SQL always returns one row" is reasoning about a contract, and the check stays. Validate only at boundaries: user input, external APIs, deserialisation, environment. A `try`/`catch` stays only if it handles external input, maps a library error to a domain one, or cleans up. A name that belongs to something outside the code, an API field, a model id, an endpoint, is changed only against its source, never from memory; unverifiable, it goes in the report as unfinished.
5. **Name it.** Rename until the code states its own intent. A good name deletes a comment.
6. **Make wrong states unrepresentable.** Prefer a type, a union or a single source of truth over a runtime check that two things agree.
7. **Then comment**, only what the code cannot say.

Fewer concepts, not fewer characters. No nested ternaries, no chain a reader has to unpack; an explaining variable is not bloat.

Stop a move the moment it would change behaviour the change did not set out to change. That covers order and concurrency, timeouts and retries, and the type of anything exported. A defect you find is fixed only as far as the defect itself reaches, and anything past that goes in the report as unfinished.

## The comment contract

A comment in forged code is exactly one of these:

- **A constraint the code cannot express**: why the obvious alternative is wrong, an invariant another file relies on, an outside behaviour this code depends on.
- **A contract that the signature does not reveal**: what a function guarantees that a reader would not assume.

Its shape: one sentence where one will do. Two lines by default, four at most, and four only for a function doc stating a genuinely surprising contract. Present tense and evergreen: no ticket ids, no incident names, no "now", "previously" or "was changed to". Every factual claim in it is true of the code as this pass leaves it, because a wrong comment is worse than none.

Anything else is deleted: a restatement of the next line, narration of the change, a section banner, a step number, a docstring on a self-evident function, a second explanation of something already explained elsewhere in the diff. Explanatory comments stay at or below the file's existing density. A contract comment on a function that hides real complexity is exempt from that ceiling, and still four lines at most. Structural markers the file already uses, such as `// arrange` / `// act` / `// assert`, are structure and stay.

## Nothing is deferred

"Deliberately kept" and "follow-up" are how slop outlives a forge. If a move applies and does not change intended behaviour, it happens in this pass.

| Rationalization | Reality |
|---|---|
| "The duplicate goes away when that module is refactored" | That refactor has no owner. Compare the two, then call the original now. |
| "Only medium confidence" | Read until it is high. If it still is not, ask the user; never keep silently. |
| "It's only a comment" | Comments are the most common slop and the most often wrong. |
| "The tests pass" | Passing is the floor. Forge is about the ceiling. |
| "It can never be empty here" | If the only guarantee you can name lives in code you cannot read, it is a guess. Put the check back. |

Genuinely out of reach, such as a change in another repo, a public API the diff does not own, or a behaviour choice only the user can make, goes in the report as **unfinished**, with the reason. Never as "kept".

## Report

After the loop, and short:

- One line: what the code does now, and why it is better.
- A small table: meter before → after (added comment lines, longest comment block, type escapes, copies) and the test result. Net lines are shown for information, never as a goal.
- The changes, at most seven bullets, each naming its file.
- **Behaviour off the tested path**: each check you removed and the guarantee that makes it dead, so a reviewer can verify what the tests do not cover.
- **Unfinished**, only if anything is, each with its reason.

For a question or a plan, replace the table with the findings and the concrete rewrite for each.

## When to read more

- `references/lenses.md`: simplicity, reuse, resilience, future-proofing, prior art and hygiene, for plans, large diffs, or a design choice in question.
- `references/slop-catalogue.md`: the patterns agent-written code produces, when you are unsure whether something is slop, plus the linters and dead-code tools that find it for you.

## Neighbours

- Prose, such as a README, PR description, commit message, or the wording of a comment forge kept, belongs to `natural-writing`.
- A whole codebase rather than a diff belongs to `audit` in this plugin.
- Posting comments on a PR belongs to a review skill; forge changes the code instead.
