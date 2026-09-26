# Choreography, layout and interaction

These rules come from rounds of review on real builds. Each one fixes something a reviewer called
out as abrupt, misaligned, half-visible or inconsistent.

## Casing

- It wraps the whole machine, with the subject's logo file on it, or its plain name when it has no
  logo.
- It opens by splitting: one half lifts over the machine, the other drops under it, with enough
  clearance that neither passes through a part.
- It fades out progressively as it clears, and is fully gone before the parts separate. Nothing
  half-visible stays behind.

## Highlight

- A part lights up only when the beam reaches its level, or when the reader hovers it. Nothing is
  lit in advance.
- The active part fills with its full accent colour. The change eases in and out with a critically
  damped spring of about 450 ms; shadows and glows follow the same spring, so nothing snaps.
- Every other part keeps its own colour and material throughout. Parts never tint or shift colour
  as the machine expands.
- The fill goes on the part's largest visible surface. A part that is mostly exposed mechanism
  (vanes, a fan) barely changes if only its thin end plates take the colour.

## Text

- Each step's label appears the first time the scroll reaches that step and stays after, in two
  columns beside the machine. Nothing is shown up front.
- The longer explanation is one caption: the current step's caption replaces the previous one.
- Everything fits on one screen: keep the machine compact rather than wide so the text never runs
  off screen.
- No text below the brand's minimum size; labels of 9 or 10 px are too small.
- On a phone the two columns and their leader lines do not fit. Put a small number on each part,
  list the labels in a two-column grid under the machine, and show only the current step's lines of
  the definition panel. Keep chips off the parts: services above the machine, inputs beside its
  first part, outputs below its last.

## Lines

- Each leader line ends exactly at its label.
- Lines never cross each other or a part. Elbow lines avoid both: a steep diagonal away from
  the machine (start at the part's silhouette, bottom for the left column, top for the right), then
  horizontal to the column. Give the part nearest a column the row nearest the machine, so no line
  passes over another's diagonal.

## Interaction

- Hovering or clicking a part or its label highlights the part and opens a small card. Cards appear
  only on hover or click, and never cover the part they describe. Try above, below and beside the
  part, and take the place that covers the fewest labels and chips.
- Keyboard and screen-reader users get the same: each part has a focusable HTML button placed over it (or its label
  is one), Enter or Space opens its card, Escape closes it, and focus is visible.
- Input and output chips link to the pages they represent. When there are more than fit, show a
  "+N" chip that opens a panel with a link to the full list.
- The definition panel stays visible, with the lines for the current step highlighted.

## Flow

- The example travels: out from the entry, through each part in order, fanning out to its
  destinations and back. The beam arrives progressively.
- When a middle part calls out, its destinations sit beside that part. The beam goes out and comes
  back on the same route, a parallel line beside the outgoing one, then carries on along the axis.
  Out and back on different routes cross each other and read as a tangle.
- A retry or a second round is a beam that arcs back over the machine to the step it restarts from.
  When the later round skips a step, the beam hops over that part instead of lighting it.
- A log of what the example does belongs to the machine (along its axis or rail), not in a
  floating box.
