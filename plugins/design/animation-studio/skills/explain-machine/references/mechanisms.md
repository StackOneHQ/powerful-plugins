# Geometry and behavior that teach

Use this reference when movement, geometry or a simulation carries the explanation. It is
not a requirement to turn every topic into a physical machine.

## Draw relationships accurately

Choose a stable view in which the important connections remain visible. An orthographic or
isometric SVG drawing often makes the mechanism easier to follow than a moving camera.
Give solids consistent top, side and front faces; apply one light direction and a restrained
material palette. Use occlusion deliberately: a shaft behind a housing stays behind it, and a
cutaway reveals only the part needed to explain the action. Keep labels and control text in
HTML where practical.

Make moving subassemblies local coordinate groups with explicit pivots. Define shared joints,
axes and connection anchors once and use them for adjoining parts and flow paths. Keep input
and output markers attached to those anchors as the scene changes. Small details should
identify function, scale or assembly; leave out detail that competes with the teaching point.

If a real mechanism has gears, belts, rods, valves or pistons, derive linked positions from
their constraints. Meshing external gears rotate in opposite directions at the ratio set by
their tooth counts; a connecting rod keeps its length through the cycle. Verify the source
mechanism before choosing its linkage. An imaginary linkage should not imply a physical law
the model does not implement.

For software or an abstract process, a token can show a request, a gate can show a documented
condition, and a reservoir can show stored state. State the analogy's limits. The visual should
not accidentally claim physical pressure, continuous flow, conservation or timing that the
subject does not have.

## Separate state, view and time

Keep one authoritative state and derive a view from it. For example:

```js
const nextState = transition(state, action);
const view = describe(nextState, parameters);
renderScene(view);
renderReadouts(view);
renderExplanation(view);
```

This is an illustrative architecture, not a required API. `describe` can calculate a pure
relationship directly; a process with accumulated work needs explicit state and transitions.
Keep source rules in those calculations rather than hiding them in SVG attributes or captions.
If randomness matters, use a repeatable seed for comparisons and tests.

Distinguish simulated time from presentation time. A speed control should not silently change
the physical result or the work completed by one step. For numerical integration, use a fixed
time step or an appropriate bounded solver. Avoid a large catch-up jump after a hidden tab
returns. A discrete state machine should advance by its defined event, not by how often the
browser happens to render. Reset clears accumulated state, queued callbacks and stale labels.

At an endpoint, clamp or transition according to the subject's rules. Do not continue moving a
full, empty or stopped mechanism merely to keep the page animated. A user changing direction
should reverse the cause and the relevant effect together; a process that cannot reverse
should make that constraint explicit instead of pretending that playback rewinds reality.

## Observe the model and the drawing together

Choose checks that can expose a wrong explanation:

- For a linkage, inspect a full cycle, the extrema and reverse motion. Measure the connection
  or ratio that should stay fixed instead of relying on a convincing frame.
- For a process, step the example through the documented transitions. Check that a waiting,
  failed or complete state produces the right output and stops the corresponding action.
- For a comparison, replay identical shared inputs; attribute a changed output to the one
  assumption being compared. Keep the scale and units consistent across views.
- For a numerical model, exercise a boundary and check its units and useful invariant. Mark
  an illustrative calculation as such rather than reporting it as measured performance.
- For animation, pause in mid-operation, change an input, resume, then reset. The mechanism,
  caption and readouts should refer to the same state throughout.

Capture the states that expose joints, intersections and labels on desktop and mobile. Under
reduced motion, use explicit steps to reach the same explanatory states without continuous
travel. When motion stops, verify that the render loop settles instead of redrawing forever.

The interactive-mechanism approach is informed by [Anatomy](https://github.com/wheresryan22/anatomy).
