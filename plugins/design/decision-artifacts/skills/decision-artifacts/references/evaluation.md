# Evaluation

Evaluate the result as a decision tool, not as a screenshot.

## Critical checks

An artifact fails if any answer is no:

- Is the main conclusion or current state accurate?
- Are observation, inference, assumption, recommendation, delivery, and verification kept distinct where they matter?
- Can the reader identify the next action without opening a panel?
- Are consequential claims backed by inspectable evidence?
- Can a reader retrieve the complete relevant support for each consequential claim without hunting through nested disclosures?
- Does every control work with pointer and keyboard input?
- Can a reader access material chart information without relying on color or hover?
- Does the artifact remain usable at a narrow mobile width?
- Does the shared or deployed result work from the intended viewer's access level?
- Are live, stored, unavailable, and snapshot data states labelled accurately?

## Quality checks

Score each from 0 to 2: missing, partial, strong.

| Dimension | Strong means |
|---|---|
| Framing | The title states the conclusion or decision, not merely the topic |
| Audience | The primary layer uses the reader's language and expected depth |
| Hierarchy | Load-bearing content is clear; supporting and reference detail are progressively disclosed |
| Completeness | The initial view stays concise while evidence, nuance, exceptions, and sources remain available on demand |
| Evidence | Sources, confidence reasons, scope, and last-checked state appear where consequential |
| Comparison | Options, before/after states, or deltas share a consistent basis |
| Visuals | Appropriate charts, diagrams, sequences, or comparisons carry the material relationships and integrate labels with the data |
| Action | Ownership, next step, and verification are concrete when relevant |
| Restraint | The page avoids repeated cards, decorative charts, duplicated prose, and hidden conclusions |
| Interaction | Rows, marks, nodes, tabs, selection, coordinated views, sheet behavior, copy, links, focus, and Escape work where applicable |
| Responsive | Reading order and controls survive desktop and mobile layouts |

Do not ship with a zero in evidence, completeness, action, interaction, or responsive behavior when that dimension applies.

## Regression prompts

Dry-run the skill against at least two structurally different cases before a major release:

1. A completed technical change that must make sense to nontechnical readers, with technical evidence in a sheet.
2. An audit with findings, proof, confidence, proposed fixes, and before/after outcomes.
3. A living status view showing done, in progress, blocked, left, and deliberately not doing.
4. A sequenced plan where each step explains its effect and what to report back for verification.

For each dry run:

- use real or clearly marked sample data
- inspect the initial screen before interacting
- open every detail path and follow every link
- test copy controls against the exact copied value
- test keyboard order, focus return, Escape, and one narrow viewport
- compare the displayed status with the source after rendering
- test the shared or deployed result from the intended viewer's access level when the platform supports sharing
- run one deletion pass without removing uncertainty, risk, evidence, or requested detail

Record the prompt origin, selected mode and taste, output path or URL, evidence limitations, viewport, interaction results, and failures fixed. Keep the record with the plugin release evidence so a later review can distinguish a completed run from an untested prompt.
