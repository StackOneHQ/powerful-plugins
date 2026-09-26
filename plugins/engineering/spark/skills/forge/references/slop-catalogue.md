# Slop catalogue

Patterns agent-written code produces that the team's own code does not. The reference point is always the surrounding codebase: a pattern is slop when the diff does it, the neighbouring code does not, and nothing in the change explains why.

> Does this read like a human on this team wrote it, or like a model that never read the surrounding file? (Karpathy on agent-written code: it is "too defensive", it "overcomplicate[s] code and APIs, bloat[s] abstractions", and it changes things it "doesn't fully understand as a side effect".)


**Convention drift** (the master signal): comment density, error-handling style, naming, import placement, logging, test structure. Compare each hunk against the unchanged parts of the same file and one sibling. Anything the diff does differently without a reason is slop. Never "fix" it by introducing a third convention: match the file, or the codebase majority if the file itself is mixed.

**Comment slop**: comments that restate the line below (`// increment counter`, `// return the result`); narration of in-motion work (`// updated to use new API`, `// now handles null`, `// refactored from old version`); step-numbered comments (`// Step 1: ...`) and section banners (`// ===== Helpers =====`); docstrings on trivial one-liners; JSDoc or docstrings that repeat the type signature and add nothing; markdown formatting inside comments; LLM vocabulary clusters (`robust`, `seamless`, `comprehensive`, `gracefully`, `leverage`, `enhanced`, `ensure`): one is noise, three in a file is a fingerprint; emoji in code, logs, or commit messages. Keep a comment only when it explains a non-obvious invariant, a surprising constraint, or a cross-file coupling, and then keep it short, concrete, and evergreen (the behaviour and the constraint, not the ticket or the incident that prompted it). The test: would a competent engineer reading this for the first time be confused without it? If yes, keep it. If no, delete it. A kept comment's *wording* is then `natural-writing`'s job: its word list and sentence shapes are the authority, not the short list above; forge only decides existence.

**Defensive overkill**: null/undefined/empty checks on values the type system or the caller already guarantees; validating arguments from trusted internal callers; `?.` and `?? default` on non-nullable types; try/catch that swallows, rethrows identically, or logs-and-continues; catch-all handlers that hide the root cause; fallbacks for scenarios that cannot happen; defaults that turn a bug into silently wrong output. Rule: validate at system boundaries (user input, external APIs, deserialisation, environment), trust internal code and framework guarantees, and let errors propagate. A try/catch earns its place only when it (a) handles unsanitised or external input, (b) maps a library error into a domain error, or (c) adds cleanup. Fake resilience is worse than none: a fallback that converts a programming error into silent wrong behaviour is worse than a crash, and is fixed first.

**Scope creep and orthogonal edits**: reformatted lines the change didn't need to touch; renamed variables the request never mentioned; docstrings, comments, or type annotations added to unchanged code; "while I'm here" refactors; comments the model deleted or rewrote because it didn't understand them; ephemeral files left in the tree (`PLAN.md`, `NOTES.md`, `SUMMARY.md`, `*.bak`, scratch scripts); unrequested READMEs or CHANGELOG entries. Test: every changed hunk should trace to the request. Anything that doesn't gets reverted, not reviewed.

**Unrequested compatibility shims**: re-exporting a renamed symbol under its old name; `_unused` or `legacy` renames instead of deletion; deprecated aliases and `// removed` markers; feature flags or `if (useNewPath)` branches for a change that could simply be made; both old and new code paths kept "just in case". For internal code, delete instead of deprecating. One code path.

**Type escape hatches and hallucinated APIs**: `as any`, `as unknown as T`, `@ts-ignore` / `# type: ignore` / `#[allow(...)]` without a reason on the same line; `Any` / `interface{}` where the real shape is one lookup away. Then check the API calls themselves: methods, options, or fields that don't exist in the installed version of the library. Open the package's types under `node_modules/`, the lockfile version, or the generated client, not memory. Guessed field names where an OpenAPI spec or schema is the authority. Fix: derive the real type or the real API; if it can't be determined without research, say so rather than guessing a second time.

**Runtime noise**: entry/exit logging; `console.log` / `print` debugging left behind; `logger.info` on every step of a routine path; `async` functions with no `await`; `.then()` chains inside async code; imports, variables, and parameters the change made unused.

**Naming slop**: `enhanced`, `improved`, `new`, `v2`, `final` in identifiers; `Manager`, `Helper`, `Handler`, `Wrapper`, `Utils`, `Service` suffixes that describe nothing; `data`, `result`, `item`, `temp`, `value2`; `processX` / `handleX` / `doX` where a domain verb exists. Files: `utils.ts` / `helpers.py` / `types.ts` grown into dumping grounds; a barrel `index.ts` that re-exports one module; a new file for a 10-line function that belongs next to its only caller.

**Test slop**: tests that mirror the implementation line by line (change the code, change the test, nothing learned); mocking the unit under test, or mocking so much that only the mocks are exercised; assertions that cannot fail (`toBeDefined()`, `toBeTruthy()`, `not.toThrow()` on pure code, a bare `assert result`); snapshots of output nobody checked; near-identical cases differing by one literal that a table-driven test would collapse; tests added to make CI green rather than to state a behaviour. The mutation check: flip the core condition in the code under test. If no test fails, the test is fixed or replaced.

**Calibration**: slop that changes behaviour, such as a silent fallback, a swallowed error, an `as any` hiding a real mismatch or a test that cannot fail, is fixed first. Clean code is left alone: boundary validation, error mapping and a comment explaining a genuinely surprising constraint are not slop, they are what slop imitates.

## Tools that find slop for you

Use these when relevant; don't force them on trivial changes.
- Run the project's own linter and typechecker on the diff first: anything they report is slop you don't have to argue about
- JS/TS: `knip`, `ts-prune` (dead code, unused exports and deps) · `madge --circular` (cycles) · `jscpd` (copy-paste)
- Python: `vulture` (dead code) · `pyright --strict` / `mypy --strict` (weak types) · `ruff`
- Rust: `cargo-udeps` (unused deps) · `clippy`
- Go: `deadcode` · `staticcheck`

If the project uses one of these stacks and the diff is non-trivial, run the tool when the project already has it installed and cite its output; otherwise recommend it. Don't install a tool, or fetch one with `npx` or `uvx`, just to run it.
