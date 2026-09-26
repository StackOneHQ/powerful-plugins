# Verifier fixtures

Run them with:

```bash
node ../verify-asset-text.mjs --self-test
```

Each fixture pins one behaviour of `verify-asset-text.mjs`. The expected defect classes
are declared in the `SELF_TEST` map in that script; the fixtures carry no comments of
their own, because a comment inside a shipped `.svg`/`.html` asset is a hidden-instruction
carrier and the repo's SkillSpector scan flags it.

| Fixture | Expected | Pins |
|---|---|---|
| `clean.svg` | *(none)* | Correct SVG built from translated `<g>` groups must not false-positive. |
| `transformed-groups.svg` | `overlap`, `clipped`, `covered` | Every defect is expressed *through* a group transform. |
| `clean-slide.html` | *(none)* | Correct 1200x1500 slide carrying an inline `<svg>` logo must not false-positive. |
| `overflowing-slide.html` | `clipped`, `covered` | Slide-relative clipping and HTML stacking occlusion. |
| `clean-prose.html` | *(none)* | Inline `<span>`s that **wrap across lines** must not read as collisions. |
| `clean-centred.html` | *(none)* | `text-align:center` and padded blocks — box overlaps that the glyphs never make. |
| `clipped-beside-br.html` | `clipped` | Text that shares its element with a `<br>` is still measured (text nodes, not leaf elements). |
| `clipped-beside-span.html` | `clipped` | Same, for text beside an inline `<span>`. |
| `clean-script-in-body.html` | *(none)* | `<script>` and `<style>` in `<body>` are not content and must not read as invisible text. |
| `inline-svg-covered.html` | `covered` | An inline SVG shape's fill covers a label in HTML mode, not only CSS backgrounds. |
| `clean-circle-corner.svg` | *(none)* | A label in the empty corner of a circle's bounding box is not covered: fill geometry, not boxes. |
| `clean-scaled.svg` | *(none)* | `width="1200"` over a 600-unit `viewBox`: the screenshot must cover the rendered size, or the self-test reports `cropped`. |
| `clean-percent.svg` | *(none)* | `width="50%"` over a 600-unit `viewBox`: the viewport is sized so it draws at 1:1, or the self-test reports `shrunk`. |
| `clean-translucent-group.svg` | *(none)* | A dark rect inside `<g opacity="0.3">` tints a label, it does not cover it: opacity multiplies down the ancestor chain. |
| `clean-translucent-overlay.html` | *(none)* | Same in HTML mode, for an inline SVG group and for a solid `<div>` inside a translucent parent. |
| `wrapped-line-covered.html` | `covered` | A card over the first line of a wrapped paragraph: coverage is hit-tested per line fragment, not at the centre of the union box. |

## Why these exist

The first version of this gate was validated only against flat-coordinate SVG — the one
construction that hides its worst bug — so it shipped wrong in both directions:

- `getBBox()` returns **element-local** coordinates, so a `<text>` inside
  `<g transform="translate(400,80)">` reported `x=0`. A correct chart drew 20 phantom
  defects, and a genuinely broken one was indistinguishable from the noise.
  `transformed-groups.svg` and `clean.svg` are the pair that catches this.
- Asset type was decided with `querySelector('svg')`, so an HTML slide carrying one inline
  `<svg>` logo was verified **as the 40x40 logo** and reported `PASS`.
  `overflowing-slide.html` is that exact shape: it passes under the old code.
- HTML clipped against the document, which cannot see text running past a slide edge —
  the slide is `overflow: hidden`, so the document never grows. Same fixture.
- HTML occlusion was never checked at all. Same fixture: `.card` is a later sibling than
  `.buried`, so it wins the stacking contest and hides it.

`clean-prose.html` was added later, after running the gate over a real 8-slide carousel
rather than only over these fixtures. Every fixture above places text absolutely on a
single line, so none of them exercised **wrapped inline content** — and
`getBoundingClientRect()` on an inline element that wraps returns the *union* of its line
fragments, a box spanning the whole column and several lines. Two `<span>`s in one flowing
`<p>` therefore "overlapped" without a glyph touching. The checks now compare
`getClientRects()` fragment-by-fragment. Fixtures prove the cases you thought of; run the
gate over real content to find the ones you did not.

A gate that reports PASS on a broken asset is worse than no gate. If you extend the
script, add a fixture that fails without your change.

## Editing them

`clean.*` and its broken twin are deliberately near-identical — same construction, same
strings, only the layout differs. Keep them that way: the pair is what distinguishes
"detects the defect" from "flags everything".
