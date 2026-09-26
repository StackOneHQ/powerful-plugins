# Render verification for generated assets

**A generated asset is not finished until you have rendered it and looked at it.**

Hand-authored SVG, HTML cards, and carousel slides have no automatic text layout. You
pick an `x` for a label based on a guess about how wide the string will be. When the
guess is wrong the browser does not wrap, shrink, or warn — it just draws the text
over its neighbour, past the edge of the canvas, or underneath a card that gets painted
later. The markup looks completely reasonable while the render is broken.

A typical failure: a bar chart of on-time arrivals whose two longest value labels
(`61.2% (4,807)`, `58.9% (4,626)`) are cut off by the canvas edge, and a route diagram
whose section heading collides with an annotation while two `delayed at the junction`
labels sit behind an opaque legend card.

## The gate

Run this before you report an asset as done, and again after any edit to it:

```bash
node ${CLAUDE_PLUGIN_ROOT}/skills/tufte-viz/scripts/verify-asset-text.mjs \
  --out /tmp/asset-verify \
  path/to/asset-1.svg path/to/asset-2.html
```

`--out` must be an absolute directory. `agent-browser` resolves relative paths against
its own daemon working directory, not yours, so a relative `--out` writes somewhere you
are not looking.

**Exit codes:** `0` all clean · `1` at least one defect · `2` could not check (bad
invocation, a missing input file, `agent-browser` missing, or the browser could not open or
measure an asset).
Never read a `2` as a pass — see *Requirements*.

The script runs in its own `agent-browser` session and closes only that one, so it is safe
to run while you are driving another browser session.

The script prints a screenshot path per asset and checks these failure modes:

| Defect | What it means |
|---|---|
| `overlap` | Two text bounding boxes intersect. Labels are drawn on top of each other. |
| `clipped` | A text box extends past its container — the `viewBox` for an SVG, or the nearest clipping ancestor for HTML. The label is cut off at the edge. |
| `covered` | Text sits under an opaque shape painted after it. SVG has no `z-index`; document order is paint order. |
| `invisible` | Zero font size, zero opacity, `visibility: hidden`, or a zero-area box. Usually a leftover node. |
| `unmeasured` | An HTML page shows text but no text node could be measured, so nothing was checked. Never a pass. |

**Then open every screenshot it emitted and actually look at it.** Passing geometry
only proves nothing collides. It does not prove the asset reads well, that the bars are
scaled honestly, that the colours carry meaning, or that a label points at the right
thing. The script is a floor, not a substitute for looking.

Do not report an asset as done, and do not commit it, while the script reports a
defect. Fix the geometry and re-run.

## What it measures, and why that matters when reading the output

Coordinates are reported in the space you author in: **viewBox user units** for an SVG
document, **page pixels** for HTML. Geometry is measured after every ancestor transform
is applied, so a label inside `<g transform="translate(400,80)">` is reported at its real
position on the canvas rather than at the group-local `x=0`.

Two consequences worth knowing:

- **SVG vs HTML is decided from the document element**, not from the presence of an
  `<svg>` tag. An HTML slide that embeds an inline `<svg>` logo is verified as HTML — the
  slide is the canvas, and the logo's own text is measured along with everything else.
- **HTML clips against the nearest clipping ancestor.** A carousel slide is a fixed-size
  box with `overflow: hidden`, so text can run past the slide edge without the document
  ever growing. The reported bound names the container it broke out of
  (`<div.slide>`), not the page.
- **Geometry comes from the text, not the element.** An element's box includes padding
  and, for `text-align: center`, all the space its glyphs never occupy — a 148px centred
  label whose text spans 55px would otherwise collide with everything within 93px of it.
  Measurement is a `Range` over each node's contents, so only real glyph runs are compared.
- **Wrapped inline text is compared line by line.** An inline `<span>` that wraps has a
  bounding box spanning the whole column and every line it touches, so two spans in one
  paragraph would read as a collision while no glyph touches. Measurement is per line
  fragment; a `clipped` report on wrapped text says which fragment escaped.
- **Very tall assets print a partial-screenshot note.** The viewport is grown to the asset
  up to 2400x12600. Past that the screenshot covers only part of it and the script says
  so — geometry is still measured across the whole asset, but you cannot eyeball what is
  not in the frame, so split the file and re-run.

### Text that was not rendered

If an ancestor is `display: none` — an inactive `reveal.js` slide, a collapsed panel —
its text has no box at all. Flagging those as `invisible` would bury the real findings,
so the script counts them and prints a `note:` instead. **That text ships unverified.**
If those are slides, render them one at a time, or export each to its own file, and run
the gate over each.

### What it does not catch

Geometry only. It will not tell you that dark text landed on a dark card (legible
positioning, illegible contrast), that a number is wrong, or that the chart answers the
wrong question. Those are what the screenshots are for.

**It also cannot make an asset good.** A clean gate and an underwhelming asset are
entirely compatible — see *Passing the gate is not the same as being any good* below.

## Related gates: do not reimplement these

This gate covers **text geometry in any hand-authored SVG or HTML**. Other checks own
adjacent concerns. Use them where they apply rather than growing a second copy here:

| Gate | Owner | Covers |
|---|---|---|
| Text geometry (`overlap`, `clipped`, `covered`, `invisible`) | this file | any hand-authored `.svg` / `.html` |
| Raster export | the project's image or export pipeline, if it has one | output dimensions, background colour, file size, frame count, legibility of small type after compression |
| Product UI fidelity | real screenshots or the product's own components | real chrome, real tokens, real logos, 2x output |
| Logo and palette correctness | the project's brand guidelines or design tokens | official logo files, clear space, the approved palette |

A raster check and this gate are complementary, not alternatives. A raster check verifies
the exported image after the fact. This gate measures *text boxes* in the source before you
rasterise. On a text-bearing image, run this over the `.html` or `.svg` first: a clipped
label is cheaper to find in the DOM than in a webp.

## Fixing the common defects

- **`clipped` value labels on a bar chart** — the bar axis is too wide for the canvas.
  Reserve room for the longest label: compute `max_bar_width = canvas_width -
  label_column_width - longest_value_label_width - padding`, then rescale every bar
  against that. Do not just shrink the font.
- **`clipped` inside an HTML slide** — the text is wider than its container, usually a
  `white-space: nowrap` headline or a stat card with a longer number than planned. Give
  the element a real `width`/`max-width` so it wraps, or shorten the copy. Removing the
  container's `overflow: hidden` hides the symptom and ships an asset that bleeds into
  its neighbour.
- **`overlap` between a heading and an annotation** — long headings are the usual
  culprit. Move the annotation to a row that is genuinely free, or shorten one of them.
  Nudging by 2px because the checker's tolerance is 0.5px is not a fix.
- **`covered` labels** — either move the text out from under the shape, or move the
  shape earlier in document order so the text paints on top. Prefer moving the text;
  reordering can change the intended layering. In HTML the same rule applies via
  stacking order: a later sibling (or a higher `z-index`) wins.
- **`invisible` nodes** — delete them. A `font-size="0"` spacer is dead weight that
  future edits will trip over.

## Passing the gate is not the same as being any good

This gate is a floor. It proves nothing collides, nothing is cut off, nothing is buried.
An asset can clear it completely and still look amateur — and in practice that is the
usual complaint about generated assets, not overlap.

The recurring cause is **authoring by eye instead of linking a source of truth**. The same
lesson shows up in every asset type:

- A template or canvas is a contract, not a style to reproduce. Off-brand images usually
  come from someone rebuilding its values by eye from a shipped image and landing near,
  but not on, them.
- Hand-authoring product UI from a code diff produces an approximation every time:
  different radii, invented navigation labels, a drawn logo, a greyish palette. Choose the
  highest route you can reach (real screenshot, then real components, then a static kit)
  and never skip down a rung because it is faster.
- Never hand-draw, recreate, or approximate a logo.

So before running this gate, check you are not generating an approximation of something
that already exists:

| If the asset contains | Do not eyeball it. Take it from |
|---|---|
| The project's logo, brand colours, or type | the project's brand guidelines or design tokens. If there are none, ask, and use neutral values clearly marked as placeholders until you have an answer |
| A third-party or partner logo | the vendor's official press or brand kit, or a logo file the project already ships |
| Product UI | a real screenshot or the product's own components |
| A recurring asset type (release hero, social card, slide) | the template or canvas file the project already uses, linked rather than copied |
| A chart or diagram | `references/tufte-principles.md` and `references/analytical-design.md` in this skill |
| Body copy or captions | `natural-writing`, if installed |

A geometrically clean asset built from guessed values is still off-brand. Fix the sourcing
first; this gate only catches what is left.

## Budgeting text width

When placing text by hand, estimate width as `chars x font_size x 0.55` for the
system sans stack, and `chars x font_size x 0.6` for the mono stack. Treat that as a
lower bound and leave ~15% slack: bold text, wide digits, and font fallback all run
wider. The verifier measures the truth, so use the estimate to get close and let the
render settle it.

An example of getting this wrong, from a terminal-style diagram (four separate lines):

```xml
<g font-family="SF Mono, Monaco, Consolas, monospace" font-size="14">
  <text y="204" fill="#6b7280">~/timetables</text>
  <text x="95" y="204" fill="#a6e3a1">$</text>
```

The first `<text>` has no `x`, so it starts at 0; the prompt was budgeted 95px.
`~/timetables` is 12 characters at 14px mono: `12 x 14 x 0.6 = 100.8px`. The prompt was
placed at 95, so the `$` lands on the trailing `s`. The author scaled the offset correctly
for the one-character `~` on the line above (`x="20"`) and then reused a guess for the
twelve-character one. The formula above predicts this exactly, and the gate reports it as
four `overlap` findings.

## Look at the shipped assets before you author a new one

Do not compose from a description of the house style when the real thing is on disk.
Before authoring, search the project for figures of the same kind and read two of them:

| Want | Look for |
|---|---|
| A blog diagram or pipeline figure | existing `.svg` figures next to published posts |
| A dense workflow figure | the most text-heavy existing diagram (count its `<text>` nodes) |
| A release or changelog hero | the last two shipped heroes and the template they came from |
| A carousel or slide | an existing slide file in the same format and size |

Run this gate over whatever you pick. If they pass, they are safe to imitate on geometry
as well as on style. Reading one costs a minute and removes most of the guessing that this
gate can only catch after the fact.

This is the step that makes the difference, not a nicety. In practice, assets that come
out right on the first attempt are the ones where the author supplied the brand source plus
**two previously shipped examples** of the same asset type. This gate only measures the text.

## Requirements

Needs the `agent-browser` CLI on `PATH`. If it is missing the script exits `2` and says
so. Report the assets as **unverified** — an unverified asset is not a done asset, and
`2` is not a pass.

## Checking the checker

```bash
node ${CLAUDE_PLUGIN_ROOT}/skills/tufte-viz/scripts/verify-asset-text.mjs --self-test
```

Runs the fixtures in `scripts/fixtures/` and asserts each defect class is still caught
and that neither clean fixture false-positives. Run it after touching the script.

The fixtures exist because the first version of this gate was validated only against
flat-coordinate SVG — the one construction that hides the transform bug — and so it
shipped both a false pass (an HTML carousel measured as its 40x40 inline logo) and a
false fail (20 phantom defects on a correct chart built from translated groups). A gate
that reports PASS on a broken asset is worse than no gate. If you extend the script, add
a fixture that fails without your change.
