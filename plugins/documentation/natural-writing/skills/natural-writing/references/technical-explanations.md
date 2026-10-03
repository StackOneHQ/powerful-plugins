# Technical explanations

Help the intended reader follow the mechanism or perform the procedure correctly.
Infer the audience from the request. With no other context, write for a technical
colleague who does not know this particular system. Preserve a requested length or
format; a short answer does not need a glossary, introduction, or extra headings.

This mode adopts selected principles from
[ASD-STE100](https://www.asd-ste100.org/STE_faq.html), including short sentences,
consistent terms and explicit instructions. It is STE-inspired, not a compliance
checker. The standard has both writing rules and a controlled dictionary; do not
claim that a model or a sentence-length check establishes conformance.

## Keep the meaning

Before rewriting, identify the facts the reader needs: who acts, on what, under
which condition, in which order, with what outcome and limit. Use these facts as
the comparison after the rewrite. This is working material, not an extra report.

- Keep negation, exceptions, scope, uncertainty and dependencies attached to the
  claim they qualify. "May" must not become "will". "More than" must not become
  "at least". One observed success does not establish a general guarantee.
- Preserve code, identifiers, URLs, mathematical operators, literal messages and
  requested quotations exactly. Do not replace a technical term merely because it
  also appears on a style blacklist. Explain it on first use when the reader needs it.
- Keep quantities and units equivalent. Avoid conversions unless they help the
  requested explanation; check a conversion explicitly. Do not silently round a limit.
- Use one term for one entity. If the source calls two different things "token",
  distinguish them by their actual names or roles. Do not invent a distinction
  the source does not support.
- State an unresolved ambiguity or missing actor briefly. Do not fill it with a
  plausible detail, and do not turn a source question into a confident instruction.

## Make the mechanism readable

Use a named actor and a concrete verb when that actor is known. Split a sentence
when it contains separate decisions or forces the reader to backtrack. Keep a
condition next to the action it controls, usually before it in a procedure.
Separate successive instructions; keep simultaneous actions linked when the
timing matters. Short sentences are a means to understanding, not a word-count target.

Keep the specialist term when a simpler substitute would be less precise. A brief
definition in the sentence is usually enough. Add a glossary only when several
unfamiliar terms recur, and do not explain terms the stated audience already knows.

For a complex mechanism, a small worked example can connect its steps. Label any
invented values as illustrative. Add no new behavior to make the example work.
Offer a diagram only when relationships or timing are hard to follow in prose.

## Check prose and protected text separately

Compare the rewrite with the source facts, including failure cases. A smoother
sentence that changes the condition fails even when every style check passes.

Run the existing `check-copy.sh` gate on authored prose. For mixed documents, save
a temporary prose-only copy that excludes only the exact protected spans identified
above. Check each excluded span against the source before delivery. Do not exclude
authored labels, captions or explanation to make the checker pass. If the checker
cannot run, report that limitation; an unavailable check is not a pass.

The separate comparison lets a literal such as `"queue\u2014paused"` remain unchanged
without allowing punctuation outside that literal. Deliver the finished explanation,
with a short note only for an unresolved ambiguity, requested exception or missing check.

## Example

Source: "In the event that the queue contains more than 40 jobs, the scheduler may
defer admission; running jobs are unaffected, and a retry is permitted only after
the queue has remained below 20 jobs for 5 seconds."

Rewrite: "If the queue contains more than 40 jobs, the scheduler may delay new
jobs. Jobs that are already running continue. Retry only after the queue has stayed
below 20 jobs for 5 seconds."

The rewrite keeps both strict thresholds, the duration, the exception for running
jobs and the scheduler's discretion. It does not promise that the scheduler always
blocks new jobs.
