# Learn from corrective prompting

Use when the user asks to reduce repeated guidance or evaluate whether a skill
produces a usable first result. This supplements reflect's evidence and the
skill-creator handoff; it does not start another history scan or change the apply
authorization. Keep a narrow edit narrow.

The **first result** is the first complete deliverable before user correction.
The agent may research, test, and revise internally. A necessary question about
unavailable information or authorization is not an avoidable correction.

## Establish what was knowable

For each candidate incident, preserve the initial request and available prior
context, the first delivered artifact, the later correction, and the skill
version and invocation evidence when available. A prompt-only history entry can
suggest a case but cannot establish that the first output failed. Deduplicate
exports, forks of the same incident, and agent echoes.

Classify the correction before proposing a fix:

| Observation | Treatment |
|---|---|
| A requirement in the initial request, standing guidance, or accessible source was missed | Score it against that earlier evidence; inspect the owning skill before choosing a change |
| A stable expectation is absent from the owning skill | Record a prospective specification candidate; do not retroactively call an unknowable expectation a failure |
| A preference, fact, scope change, or authorization arrived later | Keep it out of the original-result failure score |
| Necessary context could have been retrieved with the available tools | Consider a retrieval or carry-forward improvement in the existing owner |
| Context or execution evidence is missing | Record the gap and leave attribution unknown |

For example, a later currency preference is not a failure unless that currency
was already specified. Existing clear guidance that was ignored calls for an
execution diagnostic or targeted check, not another copy of the same rule.
Historical skill availability and actual loading require their own evidence;
follow the activation criteria in `history-review.md` and the review lenses.
Prospective candidates still need to meet reflect's existing acceptance and
routing criteria. A source gap without supported invocation is not an accepted
skill-body edit merely because today's catalog contains a plausible owner.

## Handoff for a substantive improvement

Give skill-creator a small set of representative cases, with any historical
reproduction limits labeled. For each case, separate:

- **Execution input:** original request, necessary prior context, raw source
  snapshots, initial workspace state, and permitted tools and side effects.
- **Grader-only evidence:** correction, first historical output, later accepted
  artifact when acceptance is explicit, and criteria citing requirements that
  were available before first delivery. Absence of further messages is not
  proof of acceptance.

Keep grader-only material outside the execution agent's accessible workspace.
Publish only synthetic or appropriately anonymized fixtures; preserve private
source citations in the local evidence packet. A replay does not inherit live
production permissions from the historical conversation.

Use matching inputs, model settings, and tools to compare baseline and candidate
skill versions. Record source revisions, skills actually loaded, output artifacts,
verification evidence, and time/cost when available. When diagnosing discovery,
run normal skill selection and explicitly invoked execution as separate trials;
the latter does not measure whether the description triggers.

Grade the actual deliverable against the predeclared admissible criteria, not
its headings or claims that checks passed. Report case-level wins, regressions,
unknowns, and necessary questions. Use unmeasured/unknown rather than zero for
missing results. Counts of similar prompts are sampling evidence, not skill
failure rates or measured reductions in corrective prompting.

If using held-out cases, split whole conversations and near-duplicate tasks
before tuning. Once a case's corrections or expected result informed an edit,
it is a regression fixture; obtain fresh cases before claiming held-out results.
