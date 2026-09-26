# Reviewers

How to recognise, trigger and wait for each AI reviewer. Logins are shown as the REST API returns
them; `gh pr view` drops the `[bot]` suffix, so match on the name before it.

| Reviewer | Login | Re-reviews on push | Trigger | Finished when |
|---|---|---|---|---|
| GitHub Copilot | `copilot-pull-request-reviewer[bot]` | When the repository turns on automatic review (it then appears in `reviewRequests`) | Request it as a reviewer (below) | A new review from it, with `commit_id` = the pushed head, that is not a quota notice (below) |
| Cubic | `cubic-dev-ai[bot]` | Yes | Comment `@cubic-dev-ai review this PR`; `@cubic-dev-ai incremental review` covers only changes since its last review | The `cubic · AI code reviewer` check completes on the head. It posts a review only when it has something to say, so do not wait for one |
| Greptile | `greptile-apps[bot]` | When set to review new pushes | Comment `@greptileai` | A new review or summary comment from it; typically 1 to 5 minutes |
| CodeRabbit | `coderabbitai[bot]` | Yes, incrementally | Comment `@coderabbitai review` (incremental) or `@coderabbitai full review` | A new review from it on the head |
| OpenAI Codex | `chatgpt-codex-connector[bot]` | When automatic reviews are on | Comment `@codex review` | It reacts with "eyes", then posts a review; it reports only P0 and P1 issues |
| Cursor Bugbot | `cursor[bot]` | Yes | Comment `cursor review` or `bugbot run` | A new review or check result from it on the head |
| Gemini Code Assist | `gemini-code-assist[bot]` | No | Comment `/gemini review` | A new review from it |
| Aikido Security | `aikido-pr-checks[bot]` | Yes | None known: it runs as a check | The `Aikido Security` check completes on the head |
| Code scanning (e.g. SkillSpector, CodeQL) | `github-advanced-security[bot]` | Yes, through the repository's workflow | None: it re-runs with CI | The scanning workflow finishes on the head; read open alerts through the API (below) |

## GitHub Copilot

Request the review through the REST endpoint; it is the one that reliably works:

```bash
gh api --method POST "repos/{owner}/{repo}/pulls/{n}/requested_reviewers" \
  -f 'reviewers[]=copilot-pull-request-reviewer[bot]'
gh pr view {n} --json reviewRequests   # confirm it attached; the exit code is not enough
```

- `gh pr edit {n} --add-reviewer ...` exits 0 while silently failing on repositories with classic
  Projects enabled.
- The `requestReviews` GraphQL mutation cannot resolve the bot's node id and returns `NOT_FOUND`.
- `copilot-swe-agent` is a different bot that writes code. Do not request it.
- When the account that requests the review has no Copilot review quota left, Copilot posts a
  review on the head that only says "Copilot was unable to review this pull request because the
  user who requested the review has reached their quota limit". It has the head's `commit_id`, so it
  looks like a completion signal. It is not a review: report it once, do not re-request Copilot in
  later rounds, and count its part of the loop as not reviewed. `pr_review.py wait` reports it as
  `did-not-review`.
- Whether Copilot reviews every push is a ruleset setting: a `copilot_code_review` rule in
  `gh api "repos/{owner}/{repo}/rules/branches/{base}"` with `review_on_push`.

If the REST call fails, ask the user to request Copilot once by hand, then continue.

## Cubic

- It reviews every push on its own, and runs as a check named `cubic · AI code reviewer`. Watch that
  check on the new head before posting a trigger.
- Its inline comments carry a severity (P1 to P3) and often a suggested change. Verify the suggestion
  as you would any other claim before applying it.
- A clean round may produce no review at all: the check completes and nothing is posted. When it
  does post, a clean summary says no issues were found, or that all reported issues were addressed.
- The check result is not the verdict. It passes while its threads are open, and threads can appear
  before the check completes, so read the unanswered threads (`pr_review.py threads --unanswered`)
  every round.
- It resolves its own threads when it sees a fix, sometimes before you have replied. A resolved
  thread is not an answered one: reply anyway, for the record.

## Code scanning

Alerts from `github-advanced-security[bot]` often arrive as review threads, and on a branch that
requires resolved conversations they block the merge like any other thread. Not every alert becomes
a thread, so read the open alerts for the PR directly. They are filed under the merge ref, not the
head:

```bash
gh api --paginate "repos/{owner}/{repo}/code-scanning/alerts?ref=refs/pull/{n}/merge&state=open" \
  --jq '.[] | "\(.rule.id) \(.most_recent_instance.location.path):\(.most_recent_instance.location.start_line) #\(.number)"' \
  | sort
```

They are rule matches, not reasoning: an alert on code that does exactly what it should (a helper
that must call `subprocess`, say) is declined with a reply that states why the behaviour is
intended. Fix only a real finding.

A scanner re-raises the same finding on each new commit, under a new alert number, for the same rule
on the same file and line. Key your decisions on rule, file and flagged code, not on the alert
number. Do not triage the repeat again: carry the decision forward, and give its new thread a
one-line reply linking the earlier one, so the thread can be resolved where the base requires it.
The sorted listing above puts repeats next to each other.

## A reviewer that is not listed

Treat any `*[bot]` login that reviews or comments on the PR as a reviewer, and triage its comments.
Do not assume it re-reviews after a push: if no new review or check from it appears during the round,
tell the user it could not be triggered and that its part of the round is unconfirmed.
Add it to this table once its trigger is confirmed in its documentation.
