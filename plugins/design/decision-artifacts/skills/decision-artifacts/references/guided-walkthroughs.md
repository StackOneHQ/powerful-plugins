# Guided walkthroughs

Teach a mechanism by following one example from input to outcome. Use this recipe
when the reader needs to understand an order, state transition, calculation or
conditional branch. An ordinary explanation does not need an interactive page.

## Keep one trace consistent

Choose a concrete example from the source, or label invented values as illustrative.
Represent the example as data shared by the diagram, steps, result and text
equivalent. Each step should say what changed, why it changed and which source
supports that rule. Keep conditions, units, boundaries and failure cases intact.

Separate a source fact from an assumed input and a derived result. A toy simulator
must state its assumptions and limits. Do not label it as a live system or a
prediction when it merely illustrates a documented rule.

Use previous/next controls or direct step selection when order matters. Show the
current position and allow the reader to return to the start. Leave the page still
until the reader acts. Motion can explain the transition, but the final state must
also explain it without animation.

## Add controls only when they teach

When an input changes the result in a meaningful way, let the reader change it.
Keep units and valid ranges visible, show the original baseline alongside the
selected scenario, and provide reset. Explain the observed difference in words.

Calculate the trace and result from one function or model. Do not independently
hard-code the diagram, caption and result: they drift when a value changes. If a
change invalidates the current step, move to a valid state and explain why.
Reject invalid values explicitly; do not silently clamp them to make the example
look reasonable. Limit a numeric demonstration before its computation overflows.

## Keep the answer available without interaction

Include a complete static trace of the baseline in ordinary HTML or a companion
text file. It must contain the actual steps, outcome and qualifications, not a
message telling the reader to enable JavaScript. Keep it available for printing,
screen readers and readers who prefer text. Dynamic updates should not force a
screen reader to announce the whole diagram on every keypress.

Use real buttons and labelled inputs. Selection should work by keyboard, preserve
visible focus, and never require hover or color alone. Respect reduced motion by
showing the resulting state directly. On a small screen, keep the reading order
and controls usable without hiding essential labels.

## Test the model and the page

Calculate expected results independently of the UI implementation before using
them as test cases. Exercise the baseline, one meaningful change, a boundary and
an invalid input. Then exercise reset and every step with both keyboard and pointer.
Check that the diagram, labels, result and text explanation agree after each action.

Inspect desktop and narrow layouts, reduced motion, and the static equivalent.
For a disabled or unavailable browser path, state what remains untested. A screenshot
cannot establish that the controls or calculations work.

Ask the reader a concrete question the walkthrough should answer, such as which
condition changes the branch and what the result becomes. Use their answer and
feedback to adjust the explanation's level of detail. Do not add a quiz to the
artifact unless the user wants one; this can be a question during review.
