# Evaluation

Evaluate the result as a decision tool, not as a screenshot.

## Critical checks

The artifact fails if any answer is no:

- Is the main conclusion or current state accurate, and is every volatile fact re-checked with its time?
- Does the first screen show what needs the reader, in order, and nothing that Claude could do itself?
- Do recommendations and timelines respect the user's standing rulings and stated scope?
- Can the reader record an answer on every open decision, and can Claude read it back?
- Are observation, inference, assumption, recommendation, delivery and verification kept distinct?
- Are consequential claims backed by evidence reachable in one selection?
- Is every change that can be shown, shown before and after?
- Does every control work with pointer and keyboard, and does Escape return focus?
- Can material chart information be read without colour or hover?
- Does the page work at 390 px with no horizontal scroll?
- Is visible prose within the budget, with no session phrases and no mode or taste labels?
- Are live, stored, unavailable and snapshot data states labelled accurately?

## Reader tasks

Give an unfamiliar reader only the finished artifact. Ask what needs them, which conclusion follows, where its evidence is, and what remains unknown. For a process or scenario, ask them to trace one outcome. These questions belong in review, not on the page.

When changing this skill's behaviour, compare outputs from the released and candidate versions with the same request, inputs, source, audience, model settings and tool budget. Keep source-backed review, model-reader results and real user feedback separate.

## Quality dimensions

A review rubric on top of the critical checks:

| Dimension | Strong means |
|---|---|
| Framing | The `h1` states the conclusion; the `<title>` is a short name |
| Audience | The first layer uses the reader's language and depth |
| Completeness | Evidence, nuance, exceptions and sources stay available on demand |
| Comparison | Options and before/after states share one basis |
| Visuals | Charts, diagrams and comparisons carry the relationships, labelled on the data |
| Restraint | No repeated cards, decorative charts or duplicated prose |

## Release dry run

This section is for maintainers releasing the plugin. It is not part of building an artifact.

Before a major release, run the skill against at least two structurally different cases:

1. A completed technical change that must make sense to nontechnical readers, with technical evidence in a sheet.
2. An audit with findings, proof, confidence, proposed fixes, and before/after outcomes, answered on the page.
3. A living status view showing done, in progress, blocked, left, and deliberately not doing.
4. A sequenced plan where each step explains its effect and what to report back.

For each run: use real or clearly marked sample data; inspect the first screen before interacting; open every detail path and follow every link; record an answer and read it back; test copy controls against the exact copied value; test keyboard order, focus return, Escape and a 390 px viewport; compare displayed status with the source after rendering; and run one deletion pass without removing uncertainty, risk or evidence. Record the prompt, mode and taste, output URL, evidence limits, interaction results and failures fixed.
