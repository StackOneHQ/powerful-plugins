# Decision Artifacts

Create concise, evidence-backed, interactive artifacts that help people understand a model's findings and make a decision.

The plugin separates two choices that are often mixed together:

- **Mode** controls what the reader needs to do: `decide`, `explain`, `act`, `track`, or `explore`.
- **Taste** controls how it feels: `editorial` by default, or `dashboard`, `technical`, or `narrative`.

Users can override either in natural language:

```text
Use decision-artifacts with mode=decide taste=technical.
```

They can also name another installed writing, brand, or design skill. That skill becomes the authority for its concern while the decision structure, evidence, and accessibility rules remain in place.

## Default output

The default is an editorial decision brief built around **simple at rest, exhaustive on demand**:

- conclusion and required action first
- generous use of purposeful charts, diagrams, sequences, timelines, and before/after views
- concise nontechnical overview
- selectable rows, marks, nodes, and steps
- complete evidence, nuance, sources, and technical detail in a side sheet
- no more than two levels of disclosure
- source, confidence rationale, verification state, and last-checked context for consequential claims

## Composition with other skills

The plugin composes with adjacent skills instead of copying their rules.

- `decision-artifacts` owns the decision model, evidence spine, interaction, visual hierarchy, and platform routing.
- `natural-writing` owns sentence-level language.
- `tufte-viz` owns quantitative chart selection and critique.
- `animation-studio` owns motion, when a state change needs it.
- `browser-automation` covers interaction testing of the rendered artifact.
- Any installed response-style skill owns response order, scannability, plain language, and honest uncertainty.
- Any installed diagramming skill owns focused diagrams and visual explanations.
- The project's brand or design-system skill, or its design tokens, owns the visual system. If none exists, the built-in tastes apply and the skill asks before inventing brand values.
- Any installed HTML rendering skill owns its rendering path.
- `vercel-web-design-guidelines` covers implementation review.

Every integration is optional. The skill reads an installed dependency before using it and applies only the responsibilities that dependency currently documents. If a dependency is unavailable, the artifact skill uses a compact fallback without copying the missing skill's rules.

## Installation

```bash
# Claude Code
/plugin marketplace add StackOneHQ/powerful-plugins
/plugin install decision-artifacts@powerful-plugins

# Codex
codex plugin marketplace add StackOneHQ/powerful-plugins
codex plugin add decision-artifacts@powerful-plugins
```

## Example requests

```text
Turn this investigation into a shareable decision artifact.
```

```text
Explain this change to nontechnical readers. Use a technical side panel for proof.
```

```text
Build a track-mode artifact showing what is done, left, blocked, and deliberately excluded.
```

```text
Create an explore-mode site where the reader can change the assumptions. Use our brand skill for the visual style.
```
