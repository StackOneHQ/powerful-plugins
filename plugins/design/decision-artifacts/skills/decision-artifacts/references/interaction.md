# Interaction

Every control must reduce the reader's work or support a decision; leave out any that doesn't. A selection opens the useful detail directly, never a chain of nested disclosures, and moving content into the sheet is not permission to drop it.

## Answer controls

- One control group per decision, on its row and repeated in its sheet: a segmented choice (or checkboxes for multi-select) plus a note. Each row has a bare `#d-<id>` anchor.
- The recommended option is tagged, never pre-selected unless the reader asked for defaults. "Approve all recommended" fills only unanswered items and stores them as `source: bulk` (a click is `source: pick`). It offers Undo until the next action, and the counter reads "8 of 8 answered · 5 by Approve all". Any row can be cleared; never call `confirm()`.
- Controls stay disabled, with the counter showing that answers are loading, until the stored answers arrive, so Approve all can't overwrite answers it hasn't seen.
- Each row shows Saving…, Saved hh:mm, or Not saved with Retry. If another viewer's write reaches a row the reader is editing, keep the reader's typing and offer Use theirs or Keep mine.
- Above "Copy my answers", a "Your answers" list: each decision with its choice, note and a Change link to its row; unanswered ones say so and link to the question. A decision that depends on another shows "Waiting on …" and is disabled. When an id was answered in an earlier version and its inputs haven't changed, offer "Last time: … Use again"; it counts only once clicked.
- "Copy my answers" copies a prompt-ready list with each choice, note and source, and names the unanswered ones. If the clipboard call fails, show the text selected for a manual copy.
- Write one document per decision, only on a reader action. Coalesce typing into one write per pause; closing the sheet saves a pending note.
- Render viewer-written text with `textContent`. Keep decision ids stable and rebuild every control from the stored answers on load.

## Sheet

- Master-detail: at about 1,100 px and wider, the decision list stays on the left and a persistent panel on the right shows whatever the reader selected last. Selecting a decision row, a chart mark, a finding or a section heading drives the panel; the selected item is marked and the panel has previous and next. Narrower, the same panel opens as a `<dialog>` with `showModal()`, which makes the page inert and closes on Escape; return focus to the trigger on close.
- The panel opens on the overview, not empty, and keeps the answer controls at its top, so choosing never means scrolling back.
- An accessible name and a visible close control. A closed sheet is hidden with `[hidden]`, and the page's CSS keeps `[hidden] { display: none !important; }` so a `display: flex` rule can't leave an invisible sheet catching clicks.

## History, tabs and collapsed sections

- When the reader would compare this run with the last, show the change inline as a "vs <date>" column, not in a tab.
- Tabs suit two to five peer views and older history: tab semantics, arrow keys, and a bare `#anchor` per tab. Never hide an open decision or the conclusion behind one.
- Collapsed history sections open independently, with Expand all. Use an exclusive `<details name>` group only where the reader never compares.

Before/after layout is in [modes.md](modes.md); charts and number pairs in [visuals.md](visuals.md). A mark or node with supporting detail opens the same record as its table row.

## Which component for which job

Sheet, tabs, collapsed sections, segmented choice and checkboxes are above; before/after in [modes.md](modes.md); charts in [visuals.md](visuals.md).

| Job | Component | Minimum |
|---|---|---|
| Confirm an irreversible step | An in-page `<dialog>` (`confirm()` returns false in artifacts) | Says what happens; focus returns |
| A definition or a mark's values | Popover or tooltip | Never the only way to read a value |
| Visual options, or one sentence each | Radio cards with previews | Whole card is the target |
| More than six options | Select or combobox | Type to search |
| A number: timeout, budget cap | Slider or stepper showing the value and its effect ("5 min · saves $20 to $50 a month") | Typed input too |
| One setting applied at once | Toggle | Label says what changes |
| An order of priority | Drag to rank | Move up and down buttons |
| Many rows, one verdict each | Approve or reject per row, plus bulk | Undo for bulk |

Show a headline number as a stat tile or number pair with a signed delta and its basis; magnitudes across rows as a table with inline bars and printed values; an item's state as a badge with icon and word; one decision-changing caveat as a single callout; active filters as removable chips. Every choice keeps its note, and the detail container keeps one name across the page.

## Platform floor

- Lay out for 320 px with no horizontal page scroll. Wide tables scroll in their own container or become stacked labelled rows, using a container query on the table's wrapper so they also stack when the sheet narrows them.
- Choice, note and close controls are at least 24 × 24 px (44 on touch). A sticky answer bar gets matching `scroll-padding` so it never hides the focused control.
- Prefer widely available native features (`<dialog>`, `inert`, `:has()`, container queries, popover); use others only inside `@supports`, as decoration.
- No Print button or plain download link, since neither works inside the artifact frame; for a requested export, use the `downloads` capability's save control on a Claude artifact, and a normal download link on a site or local page. Link live destinations rather than PRs, and repeat critical links in the chat hand-off.
