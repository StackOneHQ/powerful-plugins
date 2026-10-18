# Interaction and progressive detail

Interaction must reduce the reader's work or support a decision. If the result is clearer without a control, leave the control out.

## Two layers

1. **At rest:** what needs the reader, the conclusion, the strongest evidence, the primary visual and the next action, understandable without clicking.
2. **On demand:** the complete record for the selected item: evidence, sources, confidence, assumptions, exceptions, implementation detail and verification history.

Moving content to the second layer is not permission to drop it. A selection opens the useful detail directly, never a chain of nested disclosures.

## Answer controls

- One control group per decision, on its row and repeated in its sheet: a segmented choice (or checkboxes for multi-select) plus a note field.
- The recommended option is marked but not pre-selected unless the reader asked for defaults; "Approve all recommended" fills only unanswered items.
- A visible "N of M answered" and a saved state the reader can see ("Saved" or the error and what to do).
- "Copy my answers" copies a prompt-ready list of every decision with its choice and note, and says which are unanswered.
- Write one document at a time per decision, only on a reader action, and coalesce typing into one write per pause.
- Render viewer-written text with `textContent`, never `innerHTML`.
- Keep decision ids stable and rebuild every control from the stored answers on load, so values survive a republish.

## Sheet

- A right-side sheet on wide screens; full-screen on small ones.
- An accessible name, a visible close control, Escape to close, focus moved in on open and returned to the trigger on close. Closing saves any pending note first.
- The obscured page isn't interactive while a modal sheet is open.
- A closed sheet is hidden with `[hidden]` and the page's CSS keeps `[hidden] { display: none !important; }`, so a `display: flex` rule can't leave an invisible sheet catching clicks.

## Tabs and collapsed sections

Tabs suit two to five peer views, and history the reader may want: previous runs, past answers, older versions, archived options. Use tab, tablist and tabpanel semantics; arrow keys move between tabs. Never hide an open decision or the conclusion behind a tab. Collapsed sections (`<details>`) suit the same history when tabs would be heavy.

## Charts, diagrams and visuals

- State the takeaway next to the visual and label key values directly.
- Give material chart information a text or table equivalent; never make hover the only way to read it, or colour the only encoding.
- A mark or node with supporting detail opens the same record as its table row.
- Don't repeat the same numbers across cards, charts and prose.

| Reader question | Prefer |
|---|---|
| Which option, and why? | Aligned comparison or trade-off map, each option rendered |
| What changed? | Before/after, diff, slope or delta |
| In what order? | Sequence, stepper or timeline |
| How does it work? | Flow, responsibility map or dependency graph |
| Where is it concentrated? | Ranked view, grouped table or heatmap |
| What if the inputs change? | Scenario controls with the baseline alongside |

## Copy and links

Copy the promised content, confirm without stealing focus, and label external and destructive actions. When the reader needs per-row links (drafts, docs, dashboards), link the live destination rather than a PR, and repeat critical links in the chat hand-off.

## Narrow screens

Keep reading order and controls reachable, avoid horizontal page scroll, and let tables become stacked labelled rows when columns stop being readable.
