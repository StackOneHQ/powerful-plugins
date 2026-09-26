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

# Tufte Visualization Ideation

Apply Edward Tufte's principles to design clear, honest, high-density data visualizations.

## Workflow

### For new visualizations:

1. **Clarify the data story**
   - What comparisons matter?
   - What's the key insight to communicate?
   - Who's the audience?

2. **Select approach** using Tufte principles:
   - High comparison need → Small multiples
   - Dense data → Consider data tables, sparklines
   - Time-series → Line charts with minimal grid
   - Part-to-whole → Avoid pie charts; prefer bar/table

3. **Design with data-ink in mind**
   - Start minimal, add only what's necessary
   - Every element must earn its ink
   - Default to grayscale; use color purposefully

4. **Apply the Tufte test** (see references/tufte-principles.md)

### For critiquing visualizations:

1. **Check graphical integrity**
   - Calculate lie factor if proportions seem off
   - Verify baselines and scales
   - Look for 3D distortion

2. **Identify chartjunk**
   - Decorative elements
   - Heavy grids
   - Unnecessary 3D effects
   - Moiré patterns

3. **Evaluate data-ink ratio**
   - What can be erased?
   - What's redundant?

4. **Suggest improvements** with specific before/after recommendations

### Before reporting any rendered chart as done (mandatory)

If you produced an actual file (SVG, HTML card, PNG) rather than a design
recommendation, you must render it and check it before you call it finished:

```bash
node ${CLAUDE_PLUGIN_ROOT}/skills/tufte-viz/scripts/verify-asset-text.mjs \
  --out /tmp/asset-verify path/to/chart.svg
```

Takes `.svg` and `.html` assets. `--out` must be absolute. The script fails on text that
overlaps, is clipped by its container, is hidden behind a later-painted shape, or is
invisible. Then **open the screenshots it prints and look at them** — clean geometry does
not mean the chart reads well.

Exit `0` = clean, `1` = defect, `2` = could not check (usually `agent-browser` missing).
A `2` is not a pass: report the asset as unverified.

Hand-placed SVG text has no automatic layout, so a label whose width you guessed wrong
silently renders over its neighbour or off the edge while the markup looks fine. Do not
commit or report a chart while the verifier reports a defect. See
`references/render-verification.md` for the failure modes and how to fix each one.

## Key Principles Reference

- `references/tufte-principles.md` — core principles from *Visual Display of Quantitative Information*: lie factor, data-ink, chartjunk, small multiples, integrity.
- `references/analytical-design.md` — extensions from *Envisioning Information*, *Visual Explanations*, and *Beautiful Evidence*: the 6 principles of analytical design, sparklines, layering & separation, micro/macro, range-frames, causality, confections. Load when designing dashboards, dense displays, sparklines, or explanatory graphics.
- `references/render-verification.md` — the render/screenshot gate for generated assets: overlap, clipping, occlusion and visibility checks, plus text-width budgeting when placing labels by hand.

**Quick checklist:**
- [ ] Rendered and verified (no overlapping, clipped, covered or invisible text)
- [ ] Screenshots reviewed by eye, not just by checker
- [ ] Lie Factor ≈ 1.0 (no visual distortion)
- [ ] Maximum data-ink ratio
- [ ] Zero chartjunk
- [ ] Clear labeling
- [ ] Answers "compared to what?"
- [ ] Shows causality or mechanism where relevant
- [ ] Multivariate (not over-reduced)
- [ ] Words, numbers, images integrated — not segregated
- [ ] Reveals multiple levels of detail (micro + macro)
- [ ] Layering: primary data dominates, secondary recedes
- [ ] Appropriate data density
