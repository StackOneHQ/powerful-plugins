# Review loop

Get a pull request through its AI code reviewers without babysitting them. The skill pushes the
branch, works out which reviewers are on the PR, triggers each one the way it expects, waits for a
review of the commit it just pushed, checks every comment against the code, fixes or declines it
with a reply, and goes round again until every reviewer is clean or five rounds have run.

## Install

```bash
# Claude Code
/plugin marketplace add StackOneHQ/powerful-plugins
/plugin install review-loop@powerful-plugins

# Codex
codex plugin marketplace add StackOneHQ/powerful-plugins
codex plugin add review-loop@powerful-plugins
```

Needs the GitHub CLI (`gh`), signed in with access to the repository.

## Use

Ask for it in plain words: "bosh", "address the review comments", "get Cubic and Copilot to
re-review this". In Claude Code the skill is `/review-loop:review-loop`; in Codex,
`$review-loop:review-loop`.

## Reviewers it knows

GitHub Copilot, Cubic, Greptile, CodeRabbit, OpenAI Codex, Cursor Bugbot, Gemini Code Assist, Aikido
and GitHub code scanning. `skills/review-loop/references/reviewers.md` lists each one's login, trigger
and the signal that its review is done. A bot that is not listed is still triaged; it just cannot be
triggered on demand.

## Bundled script

`scripts/pr_review.py` makes the GitHub calls that break on a flaky connection. `threads` lists every
review thread and whether you answered it (a bot resolving its own thread does not count), `reply`
answers a thread exactly once even when a retry follows a dropped connection, and `wait` polls until
every check and named reviewer has finished on the pushed commit. It needs only Python 3 and `gh`.

`skills/review-loop/references/several-prs.md` covers several open PRs at once: one watcher per PR,
bringing a PR up to date after a sibling merges, and the merge order when you ask it to merge.

## What it will and won't do

- It pushes and opens the PR when there is none. It never force-pushes, merges, approves or dismisses
  a review.
- It verifies each claim before fixing or declining it, and replies on every thread.
- It resolves threads only when the base branch requires resolved conversations, or when you ask.
- It stops after five rounds, and says which reviewers never answered instead of calling the PR clean.

Adapted from `bosh`, a Copilot-only loop, to work with any reviewer and with several at once.
