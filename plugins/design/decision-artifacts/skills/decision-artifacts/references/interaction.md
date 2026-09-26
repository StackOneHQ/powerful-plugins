# Interaction and progressive detail

Interaction must reduce cognitive load or support a decision. If the same result is clearer without a control, omit it.

## Simple at rest, exhaustive on demand

Design two deliberate information layers:

1. **At rest:** conclusion, current state, strongest evidence, primary visual, and next action. This view should be understandable without clicking.
2. **On demand:** the complete supporting record for the selected item, including evidence, sources, confidence rationale, assumptions, exceptions, implementation detail, and verification history when available.

Moving content into the second layer is not permission to drop it. For every consequential claim, confirm that a reader can reach the material support from the claim's row, mark, node, step, or source link. Avoid nested disclosure chains: a selection should open the useful detail directly.

## Page and detail surface

- Keep the conclusion, main visual, and next action visible without interaction.
- Make rows, chart marks, diagram nodes, timeline events, or sequence steps selectable when they have useful detail. Afford selection consistently so the reader can predict where depth is available.
- Use one right-side sheet on wide screens. Use a full-screen sheet or inline expansion on small screens.
- Put technical context, evidence, sources, assumptions, exceptions, verification history, and implementation detail in the sheet.
- Preserve the selected item in the URL when the platform makes deep links practical.
- Restore focus to the triggering element when the sheet closes.

## Tabs

Use tabs for two to five peer views of the same subject. Do not use them for ordered steps, unrelated sections, or to make the first screen look sparse.

- Use tab, tablist, and tabpanel semantics.
- Arrow keys move among tabs; Tab enters the active panel.
- Keep labels short and make the active state unambiguous without color alone.
- Prefer automatic activation only when panels render without delay.

## Sheets and dialogs

- Give the surface an accessible name.
- Move focus inside when opened and keep modal focus contained.
- Escape closes it unless closing would discard unsaved input; warn before loss.
- Provide a visible close control.
- Prevent the obscured page from acting interactive while a modal sheet is open.

## Visual grammar

Use visual forms generously when they compress a real relationship:

| Reader question | Prefer |
|---|---|
| Which option is better, and why? | Aligned comparison, decision matrix, or trade-off map |
| What changed? | Before/after, diff, slope, or delta view |
| What happens in what order? | Sequence, stepper, timeline, or state transition |
| How does the system work? | Flow, responsibility map, dependency graph, or architecture diagram |
| What is changing in the numbers? | Directly labelled chart, small multiples, or distribution |
| Where is the issue concentrated? | Heatmap, map, grouped table, or ranked view |
| What changes under different assumptions? | Scenario controls with baseline and selected state together |

Prefer direct labels and visible takeaways. A visualization should let the reader see the claim before reading the explanation. Use animation only to clarify a transition, relationship, or selection.

Use multiple coordinated views when they answer different material questions. For example, a status table can select an item, a timeline can show when it changed, and a side sheet can expose its evidence. Do not duplicate the same numbers across decorative cards, charts, and prose.

## Charts and diagrams

- State the takeaway next to the visual.
- Label important values and differences directly.
- Provide a text or table equivalent for material information.
- Do not make hover the only way to discover data.
- Use color as reinforcement, not the sole encoding.
- When a mark or node has supporting detail, make it selectable and open the same detail model used by the corresponding table row.
- Preserve selection across coordinated views and make the selected state clear without relying on color alone.

## Copy and action controls

- Copy the promised content, not a placeholder or surrounding label.
- Confirm success without stealing focus.
- For copy-as-prompt actions, include enough context for the next model or person to act, while excluding hidden reasoning and irrelevant transcript history.
- Label external destinations and destructive actions clearly.

## Responsive check

At narrow widths, preserve reading order, keep controls reachable, avoid horizontal page scrolling, and ensure the detail surface does not obscure its own close action. Tables may become stacked labelled rows when horizontal comparison is no longer readable.
