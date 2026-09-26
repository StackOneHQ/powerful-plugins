# Reflection evaluation

`history-scenarios.json` holds six synthetic behavioral cases for history mode:
recurring workflows, simple repo conventions, mixed routing, over-engineering,
tool preferences, and an uneventful history. Grade them on behavior, not keyword
or heading matches.

To evaluate a model, give it `skills/reflect/SKILL.md`,
`references/history-review.md`, the reviewer/synthesizer templates, and one
fixture's `input`. Paths under `references/` are relative to that skill directory.
Keep `expected` and `must_not` out of its prompt. The supplied packet is the full
scope: do not read real sessions, query GitHub, edit files, or file tracker items.
Use the sequential review fallback if independent subagents are unavailable.

Assess the resulting proposals against the fixture's behavioral expectations,
source citations, and routing criteria, not exact headings or keyword matches.
A clear existing rule should yield an execution-failure finding, not duplicated
instructions. Missing sources must remain explicit; a clean history must not
manufacture patterns. Empty Accepted lists are allowed.

These are portable evaluation inputs, not a claim of an automated model pass.

## Repeated corrections and first-result evaluation

`correction-scenarios.json` adds four synthetic cases: unknown historical
activation, an existing requirement versus a later preference, a separated
replay handoff, and a trivial reflection that should stay small. Use the same
procedure above, allowing the model to read `references/correction-replays.md`
when the skill routes there. Keep all fixture `expected` and `must_not` fields
outside the execution agent's accessible workspace, not merely out of its prompt.

Compare the baseline and candidate skill on the same fixture inputs when
assessing this workflow. Grade the actual reflection report and handoff against
the expectations; do not score matching headings. Record whether each criterion
passes, fails, or cannot be assessed and retain the output supporting that grade.
These cases test reflection's decisions. They do not establish that a downstream
writing skill improved, or measure fewer corrective prompts in real work.
