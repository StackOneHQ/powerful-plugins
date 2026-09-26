# Several pull requests at once

Read this when the loop covers more than one open PR in the same repository, or when the user has
asked you to merge a set of them one after another.

## Watch each PR on its own

Start one watcher per PR (`pr_review.py wait`), not one loop that waits for every PR's reviewer
check together. A combined loop holds the fastest PR's findings until the slowest reviewer finishes,
and meanwhile the user finds the comments before you do.

## After a sibling merges

A merge into the base leaves every other open PR behind it. Even when the base does not require
up-to-date branches, the remaining PRs were never tested against the merged code, so bring each one
up to date before it merges:

1. `git fetch origin && git merge origin/<base>` in that PR's own checkout. Merge rather than
   rebase, so the push is a plain push and nobody's review history is rewritten.
2. Resolve conflicts **hunk by hunk**. `git checkout --ours <file>` or `--theirs <file>` takes the
   whole file, not the conflicting lines: on a shared manifest or catalog that silently drops the
   entries the other PR just added. Open each conflict, keep both sides' content, and pick the right
   value only on the lines that truly clash.
3. `git add` the resolved files and `git commit --no-edit` to finish the merge. Then
   `git diff origin/<base> -- <file>` for every file that conflicted: only this PR's own changes
   should remain.
4. If the repository versions each change (a plugin, package or chart version that CI checks
   against the base), a version your PR set may now equal or trail the base's. Bump again past the
   base's value.
5. Re-run the generators and the full local checks, then push.

The update is a new head, so it is a new review round: reviewers can and do raise new findings on
it. Wait for them (step 4 of the skill) before calling the PR ready.

Check whether the base requires up-to-date branches:

```bash
gh api "repos/{owner}/{repo}/rules/branches/{base}" \
  --jq 'any(.[]; .type=="required_status_checks" and .parameters.strict_required_status_checks_policy)'
gh api "repos/{owner}/{repo}/branches/{base}/protection" --jq '.required_status_checks.strict'  # 404: none
gh pr view {n} --json mergeStateStatus --jq .mergeStateStatus   # BEHIND means it must be updated
```

A PR that changes a CI rule (a scan's scope, a required check) was tested only against its own diff.
Before it merges, run that rule against the other open PRs' changes too.

## Merge order, when the user asks you to merge

Merging stays the user's decision; do it only when asked. Then:

1. Find which PRs touch the same hand-written files. Generated files overlap everywhere and say
   little:
   ```bash
   gh pr view {n} --json files --jq '.files[].path'   # per PR, then compare the lists
   ```
2. Merge independent PRs first and the one that overlaps most last, so it absorbs everything else
   once instead of being updated after every merge.
3. For each PR in turn: bring it up to date (above), wait for CI and every reviewer on the new head,
   answer what they raise, confirm no open threads if the base requires resolution, then merge with
   the repository's merge method.
4. After the last merge, run the full checks on a fresh clone of the base.
