# Evidence spine

The evidence spine keeps the polished summary tied to what is actually known. It may remain an internal working structure, but every material record must be inspectable from the artifact.

## Record

For each prominent claim, capture:

| Field | Meaning |
|---|---|
| Claim | The exact statement the artifact makes |
| Kind | Observation, inference, assumption, or recommendation |
| Evidence | The minimum proof that supports it |
| Source | Link, file, query, test, conversation, or named origin |
| Confidence | High, medium, low, or unknown, with a short reason |
| Verification | Verified, unverified, stale, or contradicted |
| Last checked | Date or timestamp when volatility matters |
| Scope | Where the claim applies and known exclusions |
| Decision effect | What changes if the claim is false |

Do not show empty metadata for trivial claims. Do show provenance for facts that drive the recommendation, status, risk, or expected impact.

## Separate state axes

Delivery state and verification state answer different questions.

| Delivery | Verification |
|---|---|
| Proposed | Unverified |
| In progress | Checked in code or source |
| Implemented | Tested in a controlled environment |
| Shipped | Observed in the intended environment |
| Deferred or rejected | Stale or contradicted |

Do not infer one axis from the other. A merged change is not automatically tested. A passing test is not proof of production behavior.

## Confidence

Use words and reasons, not invented probabilities.

- **High:** direct, current evidence covers the claim's scope
- **Medium:** evidence is relevant but incomplete, indirect, or somewhat stale
- **Low:** the claim relies mainly on inference or an unverified source
- **Unknown:** evidence is missing or contradictory

Expose what would raise or lower confidence when that affects the decision.

## Presentation

Keep the headline conclusion concise. Let a selected row, chart mark, or diagram node open the relevant evidence record in the detail surface. Include source links, verification state, and contradictions there. Surface critical uncertainty on the main page rather than hiding it in the panel.
