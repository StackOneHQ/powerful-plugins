# Modes

Choose the mode from the reader's job, not from the available data. Combine at most two, with one clearly primary. Every mode opens with the "Needs you" block from SKILL.md.

## Show the change, in every mode

Wherever a decision or change has a visible effect, show it before and after rather than describing it: a chart with both series, a number pair with the delta, a screenshot of today next to a labelled mockup, a diff, or a rendered option. Do this for every item, not a sample. A mockup is labelled as one, matches the real surface, and is drawn at production quality with the brand or mockup skill, not as a placeholder.

Pick the layout from the question. If the values matter, overlay before and after on one axis; if the change matters, draw it as arrows or signed bars from zero, sorted by size. Rendered surfaces (screens, mockups, copy) sit side by side at the same scale, crop and order, stacked on phones. Use swipe or onion skin only for pixel-aligned images, on a range input with a text value, a Before/After toggle and alt text on both.

## Decide

Use when someone must choose, approve, reject or set direction.

Lead with the recommendation, the decision owner when known, why now, and the strongest reason with its confidence.

Show:

- options compared on the criteria that change the decision, each with its strongest case and its worst consequence; "keep current" is always one of them when it exists
- at most four genuinely distinct options on the main surface, none beaten on every criterion; dropped ones get a line each in the sheet. When the options are visual (a page, an asset, copy in context, a placement), render each one
- what happens if nobody decides, and by when
- costs, dependencies and reversibility; the assumption the recommendation rests on, and the signal that would reopen it
- **Next steps in order**: owner, dependency, what done looks like, and the line to report back
- decisions that need nothing from the reader, listed separately as "No decision needed"

Shape the answers to the question: multi-select and "all of these" where several apply; a question that only applies under another answer says so and hides when that answer isn't chosen. Each action button says what it does ("Move to Trash", not "Delete"), and any total it reports is de-duplicated and matches what the reader will actually get.

When the job is to present or share with a team rather than to decide alone, offer a deck with a decisions slide and the same evidence panels.

Good primary views: option comparison, before/after per option, trade-off map, reversible versus irreversible choice.

## Explain

Use when the reader needs a reliable mental model of a change, mechanism, lifecycle or current state.

Lead with the one-sentence explanation, why it matters, and the implication for the reader. Show before and after, a labelled mechanism, sequence or responsibility map, only the boundaries the point needs, and technical detail on selection.

For a mechanism or a worked example, follow [guided-walkthroughs.md](guided-walkthroughs.md).

Good primary views: before/after, annotated flow, sequence, shallow architecture map.

## Act

Use when the reader must execute work correctly.

Lead with the outcome, the next step and the current position. Show ordered steps with owner, dependency, expected result and verification gate; what to report back after each step; safe stopping points and blockers; copyable commands or messages.

Good primary views: stepper, runbook, dependency path, verification checklist.

## Track

Use when the artifact is a living source of truth.

Lead with the current state, what changed since the last version, blockers and next action, and the "Updated <time> UTC" line. Keep separate:

- proposed, in progress, implemented, shipped
- unverified, checked in source, tested, observed
- blocked, deferred, and deliberately not doing

Keep a dated "Corrections" row whenever a published claim changes. Older runs and past answers can sit in a tab or a collapsed section.

Good primary views: status table, change timeline, findings register. Every row opens its evidence.

## Explore

Use when the answer depends on inputs, assumptions or scenarios.

Lead with the baseline result, the inputs that most affect it, and the safe interpretation. Show controls with visible values and reset, baseline and selected scenario together, assumptions and range limits, and how the result was derived. Never hide the baseline behind interaction.
