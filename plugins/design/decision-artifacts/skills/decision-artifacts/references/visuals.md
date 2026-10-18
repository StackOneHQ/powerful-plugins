# Visuals

Read this when the page draws a chart, a number pair or a quantitative before/after. `tufte-viz` or `dataviz` own chart craft (data-ink, small multiples, palettes); this file covers what a decision page adds.

## Proposals look like proposals

Measured values are solid and filled. Proposed, projected or unverified values are dashed or outlined, lighter, and labelled with their verification word. Use that one encoding across the page. Never rely on hue alone, and never red against green: before and after differ in lightness plus a label, marker or line style. Marks the reader needs keep 3:1 contrast in both themes unless their value is printed on them.

## Ranges, not whiskers

Draw an estimate as a point with an interval band, or as dots for discrete outcomes ("14 of 20 runs saved more than 100 h"), not as a bar with error whiskers. With no range known, print "single run, no range" beside the number.

## The deciding number

Draw the quantity a decision turns on as position on one shared axis (dots or bars), never angle, area, a gauge or colour intensity; against a target, use a bullet graph. A number pair reads before → after, with a signed delta in the decision's unit and its basis (a target or a dated baseline), rounded to the precision that could change the decision, in tabular figures.

## Captions carry the finding

Each figure's caption is one sentence with its number, linked to the evidence record behind it. The marks alone must show the same finding: cover the caption to check. Annotate the change where it happens (delta, cause, threshold) rather than in a legend below. The series the open decision turns on takes the accent; the rest are grey and labelled directly. Views with every series, and filters, go in the sheet.

## Markup

A `<figure>` holding an SVG with `role="img"` and a short name, a `<figcaption>`, and the values in a real table (the working table counts if it holds them). Add a one-line "how to read" for anything other than bars or lines. Hover is never the only way to read a value.

## Which view

| Reader question | Prefer |
|---|---|
| Which option, and why? | Aligned comparison on shared criteria, each option rendered |
| What changed? | Overlay or arrows, per [modes.md](modes.md) |
| Against a target or baseline? | Bullet graph or diverging bar |
| How sure, how spread out? | Point with a band, or a dot strip |
| Which is biggest? | Ordered bar or dot |
| What share of the whole? | One stacked bar, or a table |
| In what order? | Sequence, stepper or timeline |
| How does it work? | Flow, responsibility map or dependency graph |
| What if the inputs change? | Scenario controls with the baseline alongside |
