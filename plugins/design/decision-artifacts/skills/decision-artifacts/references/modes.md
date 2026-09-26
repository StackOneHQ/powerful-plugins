# Modes

Choose the mode from the reader's job, not from the available data. Combine at most two modes, with one clearly primary.

## Decide

Use when someone must choose, approve, reject, or set direction.

Lead with:

- the recommendation
- the decision required and decision owner, when known
- why now
- confidence and the strongest reason

Show:

- alternatives compared on the criteria that change the decision
- benefits, costs, risks, dependencies, and reversibility
- evidence behind the recommendation
- what would change the recommendation

Good primary views: option comparison, weighted criteria without fake precision, trade-off map, reversible versus irreversible choice.

## Explain

Use when the reader needs a reliable mental model of a change, mechanism, lifecycle, or current state.

Lead with:

- the one-sentence explanation
- why the change or mechanism matters
- the implication for the reader

Show:

- before and after when there is a change
- a labelled mechanism, sequence, or responsibility map
- only the boundaries needed to explain the point
- evidence and technical detail on selection

Good primary views: before/after, annotated flow, sequence, shallow architecture map, responsibility tree.

## Act

Use when the reader must execute work correctly.

Lead with:

- the outcome
- the next step
- current position in the sequence

Show:

- ordered steps with owner, dependency, expected result, and verification gate
- what the reader should report or send back after a step
- safe stopping points and blockers
- copyable commands or messages where useful

Good primary views: stepper, runbook, dependency path, verification checklist.

## Track

Use when the artifact is a living source of truth.

Lead with:

- current state
- meaningful change since the previous version
- blockers and next action
- last verified time

Keep separate:

- proposed, in progress, implemented, shipped
- unverified, tested, observed in production
- blocked, deferred, and deliberately not doing

Good primary views: status table, change timeline, milestone map, findings register. Every row should expose evidence and context on selection.

## Explore

Use when the answer depends on inputs, assumptions, or scenarios.

Lead with:

- the baseline result
- the inputs that most affect it
- the safe interpretation of the model

Show:

- controls with visible values and reset
- baseline and selected scenario together
- assumptions, range limits, and sensitivity
- how the result was calculated or derived

Good primary views: calculator, scenario comparison, sensitivity chart, constrained simulator. Never hide the baseline behind interaction.
