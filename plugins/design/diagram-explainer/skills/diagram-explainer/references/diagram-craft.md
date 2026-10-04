# Diagram craft

Give the main path a consistent reading direction. Put labels near what they
describe and separate secondary paths from the primary explanation. Split a
large graph into a readable overview and a focused detail view when one page
cannot carry both. Preserve shared IDs across the views.

Draw boundaries only when they explain ownership, trust, location or responsibility.
Name what each boundary means. Nesting an object inside another makes a membership
claim, so it needs evidence too. Avoid an ornamental cloud, container or database
symbol that implies an implementation the source does not establish.

For a sequence, distinguish a request from its reply and show loops or conditional
branches where they occur. For a state machine, separate states from actions;
label the event and guard on a transition. For causality, explain what the arrow
asserts and which assumptions support it.

## Editable formats

- Mermaid: use stable simple IDs and put human-readable text in quoted labels.
  Check the target renderer's supported diagram syntax; render before delivery.
  Keep the `.mmd` source beside an SVG or other preview when the user needs a file.
- SVG: keep labels as text and meaningful objects in groups. Use a `viewBox`, a
  title and description, and no scripts, event handlers or external assets. Choose
  dimensions from the actual labels; guessed text widths often cause overlap.
- Excalidraw: deliver its editable JSON as well as a preview. Bind connectors to
  their objects and keep IDs unique. Moving a node should retain its relationships.
  Verify that the available editor opens the file before calling it editable.

Use the available host renderer or installed project tools. A tool or renderer
that is missing is a limitation to report, not a reason to fabricate a preview.

## Source notes

A small table is enough for a static diagram:

| Element | Claim | Evidence | Status |
|---|---|---|---|
| `worker -> store` | The worker persists the result before acknowledging | `flow.md`, persistence section | Observed in supplied document |
| `worker -> queue` | A failed job returns to the queue | Not specified | Unknown; no asserted edge |

Put source notes outside a dense diagram unless selecting the element can reveal
them. A visible source link must point to the material that supports the claim.
Do not hide critical conditions or uncertainty exclusively in a tooltip.
