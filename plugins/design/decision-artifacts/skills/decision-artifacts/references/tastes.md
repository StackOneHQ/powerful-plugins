# Tastes

Taste changes visual grammar, not truth or decision structure. Precedence: explicit user instructions, then a user-named design, brand or writing skill for its concern, then the requested taste, then `editorial`. A taste may change type, spacing, colour, density and form. It may not remove evidence, uncertainty, accessible interaction, or the action the page exists for.

## Design floor, every taste

Take colour, type and spacing from the project's brand or design-system skill; with none, the validated palette and ink roles from `dataviz`.

| Area | Floor |
|---|---|
| Type | Nothing under 14 px, chart axes, legends and tooltips included (draw SVG at container width). Body 15 to 16 px; headings weight 400 to 500; tabular figures only in columns and axes. |
| Contrast | Text 4.5:1 against its own surface in both themes; secondary text in the body ink, not light grey. Marks the reader must read 3:1, or their values printed. |
| Colour | One accent per chart, on what the decision is about; the rest context grey. At most 4 coloured series plus Other in a stack, 3 in a scatter. No text in series colours; status colours only for status. Validate each theme's palette against its real surface; dark uses its own steps, never an inverted light palette. |
| Marks | Cards on a neutral page plane; at most five hairline gridlines, no axis lines; rounded bar ends with a 2 px gap between stacked segments; dots ringed in the surface colour. |

Measure it: a script reads every visible text node's size and contrast against its resolved background, and each mark's contrast against its canvas, in both themes at desktop and 320 px. Run the project's render-overlap gate where it has one.

## Editorial, default

For broad audiences, decision briefs and shareable reports. For a Claude artifact, `artifact-design`'s utilitarian treatment for a UI fits better than its editorial one.

- A conclusion-led headline
- A restrained palette with one semantic accent
- Typographic hierarchy, whitespace, rules and direct labels
- One primary figure; add another only when it answers a different question
- Tables and side notes instead of repeated cards
- Transitions of 200 ms or less that explain state or selection, none under reduced motion

## Dashboard

For recurring status, monitoring or operational review.

- A dense but ordered scan path, status and delta before totals
- Compact rows, sparklines, small multiples, aligned numbers
- Filters only when they change the reader's task
- Written context for what changed and what needs attention

Don't force the page into one viewport or turn every metric into a tile.

## Technical

For architecture, implementation, debugging and engineering decisions.

- Mechanism before decoration; diagrams with labelled arrows and ownership boundaries
- Monospace only for identifiers, data and code
- Inspectable evidence and precise states; diffs when the change is the point

Technical taste doesn't mean showing every internal detail on the first screen.

## Narrative

For launches, proposals, change stories and guided explanations.

- One claim per section, in explanation order
- Before, turning point, after and implication when those stages are real

Show ordered steps with scrolling, a stepper or previous/next with a visible outline, not tabs.

## Motion on review pages

When the page exists to compare motion (animations, transitions, video cuts), previews may autoplay, but anything that moves for more than 5 seconds gets a pause control, and reduced motion shows a still frame with a play button. A site's own rules about motion above the fold apply to the site, not to the review page.

## Custom taste

A user may name another installed skill or describe a taste. Apply that source directly rather than mapping it onto a built-in, and keep the mode, evidence and accessibility requirements.
