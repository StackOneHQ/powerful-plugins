# Choreography, layout and interaction

These rules come from rounds of review on real builds. Each one fixes something a reviewer called
out as abrupt, misaligned, half-visible or inconsistent.

## Coming apart

- The object starts assembled and comes apart along its one axis, every part moving at once, with
  a gap wide enough for each part's own silhouette to read.
- A part never passes through another on the way.

## The walkthrough

- One stop per component, in order. The current component is picked out only when the walkthrough
  reaches it, or when the reader hovers it. Nothing is picked out in advance.
- Picking out eases in and out with a critically damped spring of about 450 ms, and anything that
  follows it (line weight, fill, a small lift off the axis) uses the same spring, so nothing snaps.
- Every other part keeps its own look throughout. Parts never tint or shift colour as the object
  comes apart.
- The change goes on the part's largest visible surface. A part that is mostly exposed mechanism
  (vanes, a fan) barely changes if only its thin end plates take the colour.

## Text

- Each component's label appears the first time the scroll reaches it and stays after, in two
  columns beside the object. Nothing is shown up front.
- The longer explanation is one caption: the current component's caption replaces the previous one.
- Everything fits on one screen: keep the object compact rather than wide so the text never runs
  off screen.
- Text painted on the object (a name on a housing) counts toward the minimum size too, measured as
  its font size times the drawing's scale. When it would land below the minimum, leave it out.
- On a phone the two columns and their leader lines do not fit. Put a small number on each part,
  list the labels in a two-column grid under the object, and keep chips off the parts. Centre the
  object and the grid together in the height the tallest caption leaves, so no band of the screen
  sits empty.

## Lines

- Each leader line ends exactly at its label.
- Lines never cross each other or a part. Elbow lines avoid both: a steep diagonal away from the
  object (start at the part's silhouette, bottom for the left column, top for the right), then
  horizontal to the column. Give the part nearest a column the row nearest the object, so no line
  passes over another's diagonal.
- Pick the anchor on the silhouette whose diagonal leaves the part without crossing any of its own
  pieces. A flared inlet or a big flange often catches a line started at the part's centre; search
  along the part for a clear anchor.
- Stack the rows of a column by the labels' real heights, not a fixed gap, and keep each label
  block clear of every part: a right-hand block sits wholly above its part.

## Interaction

- Hovering or clicking a part or its label picks it out and opens a small card. A hover is a
  pointer that moved onto a part: ignore enter events caused by the page scrolling under a still
  pointer, and close hover cards on scroll, or a resting mouse picks parts out ahead of the
  walkthrough. Cards appear only
  on hover or click, and never cover the part they describe. Try above, below, beside and the four
  diagonals, and take the place that covers the fewest labels, chips and panels.
- Keyboard and screen-reader users get the same: each part has a focusable HTML button placed over
  it (or its label is one), Enter or Space opens its card, Escape closes it and returns focus, and
  focus is visible.

## Optional layers

Add these only when the subject has them or the user asks. None of them is part of the default.

### Housing

For a subject with a real enclosure, or one the user wants revealed. The housing wraps the whole
object, with the subject's logo file on it, and opens first: one half lifts over the object, the
other drops under it, with enough clearance that neither passes through a part. It fades out
progressively as it clears and is fully gone before the parts separate. When closed, draw both
halves as one outline so no seam shows along the split.

### Definition panel

For a subject governed by one config, policy or schema. The panel stays visible the whole time,
with the lines for the current component highlighted. When no single file governs the components,
collect the rules the source states, quote or condense each, and tag it with the components it
governs. On a phone, show only the current component's lines.

### Input and output chips

For real inputs and outputs worth naming: small labelled chips, what comes in on the left and what
goes out on the right, with logos where you can find them. When a middle component calls out to
other services, their chips sit beside that part. Chips link to the pages they represent; when
there are more than fit, a "+N" chip opens a panel with a link to the full list. On a phone,
inputs sit beside the first part and outputs beside or below the last.

### Flow

For a subject where something really travels through (a request, a packet, a signal) and the user
wants it shown. A beam carries one real example through the parts, and a part is picked out when
the beam reaches it rather than at a fixed stop.

- The beam arrives progressively: it grows along its path and never appears end to end at once.
  Beams from several sources join before the object and fan out to several destinations after it.
- When a middle part calls out, its destinations sit beside that part. The beam goes out and comes
  back on the same route, a parallel line beside the outgoing one, then carries on along the axis.
  Pair each outlet with the destination on its side, so the lines never cross.
- A retry or a second round is a beam that loops back to the part it restarts from. Route it
  behind the object: low behind the parts whose leader lines rise, where those parts hide it, and
  climbing only over the middle. When the later round skips a part, the beam hops over it instead
  of lighting it.
- A log of what the example does belongs to the object (on the part the beam is in, or along its
  axis), not in a floating box.
- In the 2D styles the beam is a single accent stroke with a short brighter head (glowing in
  Hologram and Graphite). In Clay and Realistic it is light: a thin bright core in a soft glow, grown with `setDrawRange` on a
  `TubeGeometry` (its index holds `radialSegments × 6` entries per tube segment), with the head a
  short draw range of a slightly wider tube. Axis beams are drawn before the parts, so the parts
  hide them; beams to chips are drawn after.
