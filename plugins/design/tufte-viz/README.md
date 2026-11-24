# Tufte Visualization

Ideate and critique data visualizations using Edward Tufte's principles. Useful for any dashboard, chart, or report where clarity and graphical integrity matter.

## What's Included

- **`tufte-viz` skill**: auto-triggers when designing new charts, critiquing existing visualizations, reviewing dashboards, deciding between approaches, or reducing chartjunk.
- **`skills/tufte-viz/references/tufte-principles.md`**: core principles from *The Visual Display of Quantitative Information*: data-ink ratio, chartjunk, graphical integrity, lie factor, small multiples, data density. Includes the 7-question Tufte test.
- **`skills/tufte-viz/references/analytical-design.md`**: extensions from *Envisioning Information*, *Visual Explanations*, and *Beautiful Evidence*: the 6 principles of analytical design, sparklines, layering & separation, micro/macro design, range-frames, causality. Includes the extended 14-question test.
- **`skills/tufte-viz/references/render-verification.md`** and **`skills/tufte-viz/scripts/verify-asset-text.mjs`**: a render gate for hand-authored SVG and HTML charts. It fails on text that overlaps, is clipped, is covered by a later shape, or is invisible, and saves screenshots to review. Needs the `agent-browser` CLI.

## When It Activates

The skill auto-triggers when:

- Designing new data visualizations or charts
- Critiquing or improving existing visualizations
- Reviewing dashboards or reports for graphical integrity
- Deciding between visualization approaches
- Reducing chartjunk or improving data-ink ratio
- Planning small multiples or high-density displays

## Quick Checklist

- Lie Factor ≈ 1.0 (no visual distortion)
- Maximum data-ink ratio
- Zero chartjunk
- Clear labeling
- Answers "compared to what?"
- Shows causality or mechanism where relevant
- Multivariate (not over-reduced)
- Words, numbers and images integrated, not segregated
- Reveals multiple levels of detail (micro + macro)
- Layering: primary data dominates, secondary recedes
- Appropriate data density

## Installation

```bash
# Claude Code
/plugin marketplace add StackOneHQ/powerful-plugins
/plugin install tufte-viz@powerful-plugins

# Codex
codex plugin marketplace add StackOneHQ/powerful-plugins
codex plugin add tufte-viz@powerful-plugins
```

## Credits

Skill adapted from [aparente's tufte-viz gist](https://gist.github.com/aparente/e48c353755958621b3c0004593105a90), based on Edward Tufte's books.

## License

MIT

## Maintaining

### Checking the checker

```bash
node ${CLAUDE_PLUGIN_ROOT}/skills/tufte-viz/scripts/verify-asset-text.mjs --self-test
```

Runs the fixtures in `scripts/fixtures/` and asserts each defect class is still caught and that
neither clean fixture false-positives. Run it after touching the script.

The fixtures exist because the first version of this gate was validated only against
flat-coordinate SVG, the one construction that hides the transform bug, and so it shipped both a
false pass (an HTML carousel measured as its 40x40 inline logo) and a false fail (20 phantom
defects on a correct chart built from translated groups). A gate that reports PASS on a broken
asset is worse than no gate. If you extend the script, add a fixture that fails without your
change.
