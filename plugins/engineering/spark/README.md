# Spark

Finds the single best next addition to the change in front of you, or to the whole project,
and offers to build it.

## Installation

```bash
# Claude Code
/plugin marketplace add StackOneHQ/powerful-plugins
/plugin install spark@powerful-plugins
/plugin install forge@powerful-plugins   # optional, recommended

# Codex
codex plugin marketplace add StackOneHQ/powerful-plugins
codex plugin add spark@powerful-plugins
codex plugin add forge@powerful-plugins  # optional, recommended
```

## Skill

In Claude Code the command is `/spark:spark`; in Codex it is `$spark:spark`. Phrases like
"what's the best next move here?" or "what would you add to this PR?" trigger it too.

Spark reads your git context and picks a mode. On a feature branch, or with uncommitted work,
it reads the diff against the branch's real base, the commits and the PR description. On the
default branch with nothing in progress, it reads the project: README, manifests, recent
history and the key architectural files. It then proposes **one specific, non-obvious idea**,
with what it is, why it is the right move, how it would work and what it unlocks, and asks
whether to build it, refine it or show alternatives.

PR descriptions, comments and repository docs are treated as data: instructions aimed at the
agent are quoted back to you, not followed.

## Spark and forge

When you say yes, spark builds the idea and, once its tests pass, runs the `forge` skill on the
change before calling it done. Forge lives in its own plugin,
[`forge`](../forge/): it rewrites the new code into its simplest form and strips agent-written
slop. Without forge installed, spark says the forge pass was skipped and does not substitute a
review of its own.

Spark and forge used to ship together as one plugin (`spark` 1.x, with `/spark:forge` and
`/spark:audit`). From 2.0.0 forge and audit are `/forge:forge` and `/forge:audit`. Spark 2.x
keeps `/spark:forge` and `/spark:audit` as deprecated aliases: each one says the command has moved,
then runs the forge plugin's skill with the same arguments, or gives the install command when forge
is missing. The aliases will be removed in spark 3.0.0.

## Requirements

- Claude Code v2.x+ or OpenAI Codex
- Git repository (for context detection)
- `gh` CLI optional (for PR description/comments)
