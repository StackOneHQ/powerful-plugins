# Evidence spine

The evidence spine ties the summary to what is actually known. It can stay an internal working structure, but every material record must be reachable from the artifact.

## Record

For each prominent claim:

| Field | Meaning |
|---|---|
| Claim | The exact statement the artifact makes |
| Kind | Observation, inference, assumption or recommendation |
| Evidence | The minimum proof that supports it |
| Source | A named link, file, query, test, meeting or document, a user ruling with its date, or a stored answer by id; never "the conversation" |
| Confidence | High, medium, low or unknown, with a short reason |
| Verification | One value from the verification column below |
| Last checked | UTC time, taken from tool output, when the claim can change |
| Scope | Where the claim applies and known exclusions |
| Decision effect | What changes if the claim is false |

Skip metadata for trivial claims. Show provenance for anything that drives the recommendation, status, risk or impact.

## Delivery and verification are separate

| Delivery | Verification |
|---|---|
| Proposed | Unverified |
| In progress | Checked in source |
| Implemented | Tested |
| Shipped | Observed |
| Deferred or rejected | Stale or contradicted |

Use exactly these verification values on the page; a badge never says anything the record doesn't. Don't infer one axis from the other: a merged change is not tested, and a passing test is not production behaviour. "Tested" in a local preview is not "Observed" in the live viewer.

## Claims that need extra care

- **Absence.** A claim that something is unused, gone or has no consumers states its census: "checked 14 of 14 monitors, 0 errors". A partial, throttled or failed read is shown as such, never rounded to zero.
- **Volatile state.** Infrastructure, PR and CI status, prices, model lineups and anything else that moves is re-checked before each republish, with its time.
- **People and plans.** Never fill an owner, plan tier or account by inference. Write "owner: ?" and ask.
- **Named sources.** When the user named sources (a scanner, a dashboard, a document), cover each one or say why not.
- **Single-source product claims.** A claim from one positioning or planning document is "Checked in source", not settled. Cross-check the live product or docs before removing a capability from copy.

## Confidence

Words and reasons, not invented percentages.

- **High:** direct, current evidence covers the claim's scope
- **Medium:** relevant but incomplete, indirect or somewhat stale
- **Low:** mainly inference or an unverified source
- **Unknown:** missing or contradictory

Say what would raise or lower confidence when it affects the decision.

## Corrections

When a published claim turns out wrong, fix it on the page and add a dated line to a visible "Corrections" row: what it said, what is true, and how that was found. Don't leave the correction only in chat.

## Presentation

Keep the headline short. A selected row, mark or node opens its record in the sheet, with sources, verification state and contradictions. Critical uncertainty stays on the main page.
