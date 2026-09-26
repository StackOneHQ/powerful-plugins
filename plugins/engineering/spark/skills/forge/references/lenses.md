# Design lenses

Read these when the target is a plan, the diff is large, or a design choice is in question. Each lens ends in a concrete change, never a verdict alone.

## 1: Simplicity
> Could this be simpler without losing capability? (Rich Hickey: "simple" means not intertwined, not "easy to write")

- Are there abstractions that don't earn their complexity? Can you delete an abstraction layer and hard-code the single use case with no loss?
- Is there indirection that a reader would have to trace through without gaining understanding?
- Could two concepts be collapsed into one?
- Is there a simpler mental model that covers the same cases?

**Structural AI slop** (catch these specifically — line-level slop is the slop catalogue):
- Interface with only one implementation — the interface adds indirection with zero benefit
- Wrapper class that just delegates to an inner library without adding auth, retry, or error mapping
- Config objects for values that never change — "configuration theater"
- Custom error taxonomy (4 error classes caught in one place with identical handling)
- Event bus / plugin system / factory pattern for a single use case
- 1000 lines where 100 would do: a builder, a strategy, a registry, and a base class for a function that is called once

## 2: Composability, DRY & Codebase Awareness
> Are the primitives right? Can they be recombined? Has the codebase (or a dep we already have) solved this?

**Before proposing anything new, check what exists.** Grep for similar function names, types, or patterns. Read the shared types module. Scan the dependency manifest. If the repo already has a utility or a dep that covers 80% of the problem, the right move is to use it, not to build a parallel one.

- Is anything implemented twice (or will be soon)?
- Are there duplicate/near-duplicate **type definitions** that should be consolidated into a shared module? (Two versions of `User` that diverge subtly = future bug.)
- Are the boundaries between modules at the right seams?
- Is there a single primitive hiding behind two or three special cases?
- **Circular dependencies** between modules? If `madge --circular` (or equivalent) reports cycles, they signal boundaries in the wrong place, not a trivial ordering issue.

**The Wrong Abstraction test** (Sandi Metz): Is there a shared function that takes behavioral flags (`{ rateLimit?: boolean, audit?: boolean, skipNotification?: boolean }`)? This is a routing switchboard pretending to be a reusable function. The fix is separate focused functions that share small primitives, not one function with an options bag. Duplication of 3 lines of glue code is cheaper than the wrong abstraction.

**AHA rule** (Avoid Hasty Abstractions): Don't abstract until you have 3+ real instances and can see the actual shared shape. Two functions with identical code that change for different reasons are not duplicates.

## 3: Resilience & Reliability
> What breaks at 3am? What breaks at 100x scale? (Michael Nygard: "Integration points are the #1 killer of systems")

- What happens on partial failure? Timeout? Retry?
- Are there implicit ordering assumptions that will eventually be violated?
- Is state management clear? Who owns what? What's the source of truth?
- Are error paths tested or just optimistic happy paths?
- Does `Promise.all` mean one failure kills everything? Should it be `Promise.allSettled`?
- Are there external calls without timeouts? A slow dependency is worse than a failing one.
- Are catch blocks swallowing errors silently, or logging then continuing with corrupt state? Silent error swallowing is fixed first.

**Calibration**: a pure function returning a default for unknown input is a reasonable choice on a non-critical path. On a path that affects money, security or data, surface it as a decision for the user.

*(This challenge is about resilience that is **missing**. Resilience that is **fake** — defensive checks and try/catch that exist for no reason — is the slop catalogue.)*

## 4: Future-Proofing
> Will we need workarounds within 6 months? (But YAGNI beats OCP for internal code)

- Does this paint us into a corner on a likely future requirement?
- Are naming/types specific enough to be clear but general enough to evolve?
- Is there a migration path if assumptions change?
- Would adding the next obvious feature require refactoring this?

**YAGNI check**: Is there speculative flexibility (plugin systems, middleware chains, serialization layers) for a single use case? Extension points cost complexity now for benefits that may never arrive. For internal code, it's cheaper to refactor when the real requirement shows up than to guess.

## 5: Prior Art
> Has this been solved well before? Are we reinventing the wheel?

**Skip this challenge** for trivial helpers or glue code. Run it when the implementation involves: state machines, caching strategies, retry/backoff logic, data structures, scheduling, pub/sub, or any pattern that has a name.

When running:
- Use web search to find how popular, well-maintained projects solve this
- Check if there's a canonical library (popular, actively maintained, well-documented, small dependency footprint)
- Verify the approach matches community best practices for the stack in use
- Name the specific library/pattern, link the docs, explain fit

## 6: Code Hygiene
> Is the code actually clean, or just passing tests? (This is the "would a senior reviewer delete half of this?" pass.)

Run this whenever the diff is non-trivial. Skip for one-line fixes.

**Weak types**: Any `any`, `unknown` (when narrower works), Go `interface{}`, Python `Any`, TypeScript `as` casts hiding real shapes. For each, the fix isn't "pick any stronger type" — it's: read the actual callers and the upstream library types, derive the real shape, propose *that* specific type. Flag anything where the correct type can't be determined without more research.

**Dead code**: Unused exports, functions, files, deps. If `knip`/`ts-prune`/`vulture` finds them, verify they're truly unreferenced (check dynamic imports, string-based lookups, reflection) before recommending deletion.

**Legacy, fallback, and alternate code paths**: Deprecated functions still exported. `if (oldFormat) { ... } else { ... }` branches where the old format no longer ships. Feature-flag fallbacks for flags that are 100% rolled out. `// TODO: remove after v2` comments from v7. Collapse to one path — **all code paths clean, concise, and as singular as possible**.

*(Comments, defensive noise, and compat shims **introduced by this change** are the slop catalogue. Hygiene is about what was already there and what the change leaves behind.)*
