# Decision Artifacts

Build interactive decision pages: what needs the reader comes first, options and changes are shown before and after, the reader's answers are saved on the page so the agent can read them back, and the evidence sits in side panels.

The plugin separates two choices that are often mixed together:

- **Mode** controls what the reader needs to do: `decide`, `explain`, `act`, `track`, or `explore`.
- **Taste** controls how it feels: `editorial` by default, or `dashboard`, `technical`, or `narrative`.

Users can override either in natural language:

```text
Use decision-artifacts with mode=decide taste=technical.
```

They can also name another installed writing, brand, or design skill. That skill becomes the authority for its concern while the decision structure, evidence, and accessibility rules remain in place.

## Default output

The default is an editorial decision page built around **simple at rest, exhaustive on demand**:

- a "Needs you" block first: only what the reader must decide or do, in order
- the conclusion and next action, with the update time and what the page covers
- before/after views wherever a change can be shown: charts, number pairs, screenshots, mockups
- proposed and unverified values drawn differently from measured ones, and likelihood stated apart from confidence
- a working table with the reader's choice and note on every decision, saved on the page, with save state, Undo for Approve all and a "Your answers" review list
- complete evidence, sources, alternatives, and technical detail in a side sheet
- tabs or collapsed sections for history, such as previous runs and past answers
- about 300 words of prose at rest, and no more than two levels of disclosure
- one living page per topic, republished in place
- source, confidence rationale, verification state, and last-checked time for consequential claims

For a guided explanation, the skill can trace one example through a mechanism,
keep a baseline beside an adjustable scenario, and deliver a complete static text
equivalent. The diagram, step labels and result share one model so changing an
input does not leave contradictory views. Ask: "Walk me through this retry policy
with one example. Let me change the delay cap and show why the result changes."

For a spend review, the skill builds an overview with the pace and an owner
table, an explore tab where any bar, row or box filters every view, a tab on
the waste the savings come from, and decisions with saving ranges. Ask: "Where
is our cloud bill going? Let me group it by team or product and pick what to
cut."

## Composition with other skills

The plugin composes with adjacent skills instead of copying their rules.

- `decision-artifacts` owns the decision model, evidence spine, interaction, visual hierarchy, and platform routing.
- `natural-writing` owns sentence-level language.
- `tufte-viz` owns quantitative chart selection and critique.
- `animation-studio` owns motion, when a state change needs it.
- `browser-automation` covers interaction testing of the rendered artifact.
- Any installed response-style skill owns response order, scannability, plain language, and honest uncertainty.
- `diagram-explainer`, or another installed diagramming skill, owns focused diagrams and visual explanations.
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
Give me a decision artifact for these findings so I can pick on each one.
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

```text
Is the decision page up to date? Refresh it with what changed.
```
