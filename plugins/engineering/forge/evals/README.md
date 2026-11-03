# Forge evals

Two suites. They answer different questions, so run both before changing `skills/forge/SKILL.md`.

## Replay: does forge leave the code clean?

`replay/` replays real pull requests whose agent-written code their authors later cleaned up by hand. Each case in `replay/cases.json` pins the commit forge is handed and that hand cleanup. The file ships empty: add cases from your own repositories (see "Adding a replay case" below). A candidate passes when it has no more comment lines and no longer a comment block than the hand cleanup, is no worse than its input on the other measures the scorer lists, keeps the runtime dependencies the hand cleanup kept, and passes and fails exactly the same tests.

```
node evals/replay/score.mjs --case <case-name> \
  --checkout <path to the case's repository> --worktree <path> [--tests]
```

To produce a candidate, check the case's `input` commit out into a worktree, run forge there with the case's `prompt`, and score that worktree. Nothing has to be committed; `--candidate <ref>` scores a commit instead. `--tests` needs a case that lists tests.

## Synthetic: does forge act on slop and leave sound code alone?

`forge-eval.ts` feeds fourteen snippets, a mix of slop and deliberately clean code, and grades the reply. Sloppy input must come back rewritten. Clean input must come back essentially untouched.

```
cd evals && ANTHROPIC_API_KEY=... npm run eval:fast
```

`FORGE_EVAL_MODEL` and `FORGE_EVAL_JUDGE` override the models.

## Results

Same prompt for every run, only the skill differing. "1.5.0 + critique" is 1.5.0 after the prior-art review below. Replay results came from the author's private repositories and are not reproduced here; the lessons they taught are in the skill.

| Synthetic case | Kind | 1.4.0 | 1.5.0 | 1.5.0 + critique |
|---|---|---|---|---|
| idiomatic-code | clean | left alone | left alone | not rerun |
| good-design | clean | findings, then a menu | left alone, decisions raised | one-line fix, raised the rest |
| boundary-code-not-slop | clean | findings, then a menu | kept the boundary code, fixed an overclaiming comment | same |
| llm-slop-abstraction | slop | not run | interface and wrapper deleted, 41 to 15 lines | not rerun |
| wrong-abstraction | slop | not run | split into four functions, 42 to 32 lines | not rerun |
| duplicate-of-existing-helper | slop | not run | not run | reused the existing helper, named the accented-input difference first |

The 1.4.0 runs found real problems but never acted on "forge this". Tests that already failed before the change are expected to fail after it, which is why the check is "the same set", not "all pass". The good-design fix corrected a model id from memory; that prompted the rule that external identifiers are changed only against their source.

### RefactorBench-JS: is behaviour kept?

Five fixtures from [RefactorBench-JS](https://github.com/Create-Inc/refactor-bench), each with hidden tests the agent never sees. Plain Claude got "refactor this file"; forge got "forge this file".

| Fixture | Lines: before / plain / forge | Comment lines: before / plain / forge | Hidden tests: plain / forge |
|---|---|---|---|
| insurance_reports_api | 244 / 194 / 180 | 10 / 12 / 1 | 18/18 / 17/18, then 18/18 |
| rule_generator | 283 / 230 / 223 | 0 / 3 / 0 | 17/17 / 17/17 |
| game_results_handler | 344 / 287 / 194 | 0 / 7 / 0 | 18/18 / 18/18 |
| wallet_api | 553 / 462 / 424 | 54 / 16 / 5 | 21/21 / 21/21 |
| seo_content_data | 312 / 359 / 358 | 2 / 4 / 0 | 15/15 / 15/15 |

Plain Claude added comments in four of five files. Forge removed them and wrote the smaller file four times out of five. The one failure: forge dropped `?.` and `|| {}` on a database result because "an aggregate query always returns one row". The hidden test mocks an empty result. The rule on removing checks now says a result from code you cannot open has no visible origin, and the rerun kept the guards and passed 18/18.

### CodeTaste: does forge pick the refactor a human picked?

Four [CodeTaste](https://github.com/logic-star-ai/codetaste) tasks, open track: the agent gets only a focus such as "Reorganize test structure". The score is the share of the task's semgrep rules the result satisfies. Untouched code scores 0 and the human refactor scores 1. Tests were not run, since they need the benchmark's containers.

| Task | Score: plain / forge | Lines changed: plain / forge | Comment lines added: plain / forge |
|---|---|---|---|
| BentoML "Refactor legacy APIs" | 0.18 / 0.14 | 1004 / 77 | 19 / 3 |
| shields "Simplify library integration" | 0 / 0 | 126 / 149 | 0 / 3 |
| fabric.js "Refactor environment setup and cleanup" | 0.30 / 0.30 | 140 / 86 | 15 / 1 |
| koa "Reorganize test structure" | 1.0 / 1.0 | 1883 / 1864 | 4 / 4 |

Forge does not change which refactor the agent chooses. Both arms read each vague focus the same way. Forge does make the chosen refactor smaller and quieter: on BentoML the plain run changed 1,004 lines and added 11 copied blocks, where forge changed 77 lines and added no copies. CodeTaste measures choosing the refactor, which forge does not claim to do, so the pilot was not scaled to 20 tasks.

### The final skill, rerun end to end

Every suite above was rerun on the skill as merged, after a code review fixed twelve meter and eval defects.

| Suite | Result |
|---|---|
| RefactorBench-JS, 5 fixtures | 89/89 hidden tests pass |
| Replay, private cases | every scorer check passes; tests unchanged |
| Synthetic, 14 scenarios | 53/55 checks |

The reruns caught two more over-reaches, and each became a rule. On one replay case, forge moved `pino` and `pino-http` to `devDependencies` because only a spec imports them, but both are peer dependencies of `nestjs-pino`. Forge now proves a dependency unused against peer dependencies and config as well as imports, and the scorer fails any candidate that changes runtime dependencies the hand cleanup kept. In the synthetic suite, forge made sequential webhook sends parallel, added a timeout, and narrowed an exported type on code that was already sound. Order, concurrency, timeouts and exported types are now out of scope unless the defect being fixed needs them. The two remaining misses are wording: both replies raise the issue in words the pattern list does not contain.

Synthetic scenarios were run through Claude Code subagents on Opus rather than the API harness, and graded with the harness's own pattern and structural checks.

## Prior art reviewed

An independent review compared forge with the code-cleanup tools that exist, assuming none was optimal.

| Tool | Worth adopting | Wrong or harmful |
|---|---|---|
| Cursor `deslop` | judges against local style; 1-3 sentence summary | hardcodes `main`; "minimal edits" never reaches a duplicate; no tests, no re-check |
| Anthropic `code-simplifier` | clarity over brevity; no nested ternaries | hardcodes Anthropic's house style (`function` over arrows), which is drift in any other repo; only sees modified code, so never the original a diff copies |
| `pr-review-toolkit` comment-analyzer | checks every comment claim against the code | report only; pushes for more comments with no length cap |
| `dabit3/deslop` CLI | deterministic, CI-gateable | rewrites `x !== null && x !== undefined && x !== ''` to `if (x)`, which changes behaviour for `0` and `false`; no baseline, no duplication check |

What changed as a result: a duplicate and reuse check in the meter (cross-file duplication is the most measured defect in AI-written code), reuse only after comparing behaviour, collapse only for shallow wrappers (Ousterhout's deep modules), remove a check only when its guarantee is visible, a clarity counterweight against code golf, a nested-quantifier regex check, and an evidence step for every comment claim.

## Adding a replay case

Each entry in `replay/cases.json` is one pull request you cleaned up by hand after an agent wrote it:

```json
{
  "name": "acme-api-request-serializer",
  "why": "What made the agent-written version sloppy.",
  "repo": "acme/api",
  "base": "<commit the branch started from>",
  "input": "<last commit before the hand cleanup: what forge is given>",
  "gold": "<the hand cleanup commit>",
  "prompt": "the exact words you would use to ask for the cleanup",
  "tests": ["optional/spec/paths.spec.ts"]
}
```

