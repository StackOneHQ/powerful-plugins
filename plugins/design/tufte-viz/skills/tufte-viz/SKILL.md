---
name: tufte-viz
description: |
  Ideate and critique data visualizations using Edward Tufte's principles from "The Visual Display of Quantitative Information." Use this skill when:
  (1) Designing new data visualizations or charts
  (2) Critiquing or improving existing visualizations
  (3) Reviewing dashboards or reports for graphical integrity
  (4) Deciding between visualization approaches
  (5) Reducing chartjunk or improving data-ink ratio
  (6) Planning small multiples or high-density displays
  Applies principles: data-ink ratio, chartjunk elimination, graphical integrity, lie factor, small multiples, and data density.
---

# Tufte visualization ideation

Apply Edward Tufte's principles to design clear, honest, high-density data visualizations.

## Designing a new visualization

Start from the data story: which comparisons matter, what the key insight is, and who reads it.
Then choose the form:

- High comparison need: small multiples
- Dense data: a data table or sparklines
- Time series: line charts with a minimal grid
- Part-to-whole: a bar chart or table rather than a pie chart

Design with data-ink in mind: start minimal and add only what earns its ink. Default to
grayscale and use colour to encode or emphasise, never to decorate. Before presenting the design,
run it through the Tufte test in `references/tufte-principles.md`.

## Critiquing a visualization

- **Graphical integrity**: compute the lie factor when proportions look off, and check baselines,
  scales and 3D distortion.
- **Chartjunk**: decorative elements, heavy grids, unneeded 3D effects, moire patterns.
- **Data-ink ratio**: what can be erased, and what is redundant.

Give the critique as the few changes that matter most, ordered by impact, each with a specific
before and after. Skip principles the chart already meets rather than listing them as passes.

## Rendered charts: check the render before calling it done

When you produced a file (SVG, HTML card, PNG) rather than a design recommendation, render it and
look at it before reporting it finished. Running the bundled script and writing to its output
folder needs no confirmation:

```bash
node ${CLAUDE_PLUGIN_ROOT}/skills/tufte-viz/scripts/verify-asset-text.mjs \
  --out /tmp/asset-verify path/to/chart.svg
```

It takes `.svg` and `.html` assets, and `--out` must be absolute. It fails on text that
overlaps, is clipped by its container, is hidden behind a later-painted shape, or is invisible.
Then open the screenshots it prints and look at them, because clean geometry does not mean the
chart reads well.

Exit `0` is clean, `1` is a defect, `2` could not check (usually `agent-browser` missing). A `2`
is not a pass: report the asset as unverified.

Hand-placed SVG text has no automatic layout, so a label whose width you guessed wrong renders
over its neighbour or off the edge while the markup looks fine. Fix every reported defect before
calling the chart done; if the user wants it as is, say which defects remain.
`references/render-verification.md` covers the failure modes and how to fix each one.

## References

- `references/tufte-principles.md`: core principles from *The Visual Display of Quantitative
  Information*: lie factor, data-ink, chartjunk, small multiples, integrity.
- `references/analytical-design.md`: extensions from *Envisioning Information*, *Visual
  Explanations* and *Beautiful Evidence*: the six principles of analytical design, sparklines,
  layering and separation, micro/macro, range-frames, causality, confections. Load it for
  dashboards, dense displays, sparklines or explanatory graphics.
- `references/render-verification.md`: the render and screenshot gate for generated assets, plus
  text-width budgeting when placing labels by hand.

## Quick checklist

- [ ] Rendered and verified (no overlapping, clipped, covered or invisible text)
- [ ] Screenshots reviewed by eye, not just by the checker
- [ ] Lie factor close to 1.0 (no visual distortion)
- [ ] Maximum data-ink ratio
- [ ] Zero chartjunk
- [ ] Clear labeling
- [ ] Answers "compared to what?"
- [ ] Shows causality or mechanism where relevant
- [ ] Multivariate (not over-reduced)
- [ ] Words, numbers and images integrated, not segregated
- [ ] Reveals multiple levels of detail (micro and macro)
- [ ] Layering: primary data dominates, secondary recedes
- [ ] Appropriate data density
