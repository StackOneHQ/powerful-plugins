# Before showing it

Check in a **visible** browser tab. A hidden or background tab pauses `requestAnimationFrame`, so
the drawing freezes and looks broken when it is not. A headless browser is fine when
`document.visibilityState` reports `visible`; confirm that first.

## Capture

Screenshot fixed scroll points on desktop and on a phone: 0, just past each phase boundary (a
boundary plus about 0.005, since scroll positions round to whole pixels and an exact boundary can
land just before it), the middle of each stop, and 1. Do this in the chosen style and, for
Realistic, in its Technical fallback too. Use the same points every time, so
two versions compare frame for frame. Before each screenshot, wait until the render loop has
stopped; a frame taken mid-glide does not count. A `?style=` URL parameter makes every style
reachable from a script.

## Look for

- [ ] The form is the one the user asked for (or the one you picked and named), and every part is
      a part that form really has, in order on its axis.
- [ ] The drawing is accurate: every part has real detail, and nothing reads as a plain cylinder.
- [ ] Technical: no shading, gradients or glow; no line of a far part shows through a nearer one;
      line weights are consistent. Check the hidden lines on 2 to 3 times zoomed crops of every
      part, assembled and apart: at full size a nut drawn over its flange looks fine.
- [ ] Blueprint: every dimension is a real number from the subject or marked illustrative, and its
      text fits between the arrowheads.
- [ ] Patent: every numeral on the drawing has its entry in the legend, and hatching sits on the
      side away from the light.
- [ ] Assembly manual: the arrows point the way the part really moves (measure the cosine between
      each arrow and the part's travel on a real scroll back; it should be close to 1).
- [ ] Graphite: every silhouette has its highlight, and no two neighbouring parts merge.
- [ ] Hologram: the current part reads clearly over the dimmed back lines of the others, and
      its glow passes the smoothness check on a phone.
- [ ] Clay: the ambient occlusion reads as soft clay, with no black blocks in the cavities.
- [ ] Realistic: reflections read as metal and paint, with no white-out, hard square reflections or
      bloomed hot spots.
- [ ] Cutaway or X-ray: only the current component is treated, its insides make sense for its
      job, and the treatment eases in and out with the walkthrough.
- [ ] No part passes through another as the object comes apart.
- [ ] No part is picked out before the walkthrough reaches it, unless it is hovered or clicked;
      picking out eases in and out, with no snap. No part changes colour as the object comes apart.
- [ ] Labels appear on first arrival and stay when scrolling back; one caption at a time;
      everything fits one screen.
- [ ] Leader lines end at their labels and never cross each other or a part.
- [ ] Hover cards don't cover their part.
- [ ] No text below the minimum, including text painted on the object.
- [ ] When scrolling stops, the render loop stops and the current frame stays on screen; scrolling
      is smooth.
- [ ] Every part's card opens from the keyboard, and focus is visible.
- [ ] Reduced motion shows the labelled still frame; the phone layout works.
- [ ] With a housing: it never passes through a part, shows no seam, and is fully gone before the
      parts separate.
- [ ] With a definition panel: it stays visible, with the current component's lines highlighted.
- [ ] With chips: they link where they should.
- [ ] With Flow: beams grow progressively, join before the object and fan out after it, and never
      cross each other.

## Measure, don't eyeball

Expose the state on `window` for the test run, then check:

- Idle: once the glide and the springs have settled and the loop has stopped itself, wrap
  `requestAnimationFrame` with a counter for 3 s. It must read 0.
- Smoothness: first time an empty `requestAnimationFrame` loop to learn the display's frame time,
  then record frame intervals during a scroll glide. The glide's 95th percentile should match the
  empty loop's; a fixed 16.7 ms fails every build on a 30 Hz display.
- Alignment (Three.js): project a few points with `Vector3.project(camera)`, convert the result
  from normalised device coordinates to CSS pixels, and compare with the shared projection; they
  should differ by less than a pixel.
- Draw calls (Three.js): set `renderer.info.autoReset = false`, reset it before the composer
  renders, and read `renderer.info.render.calls`, which then counts every pass.
- Lines: a segment-intersection test of the leader lines against each other, the parts, the chips
  and the labels finds zero, not counting where each line meets its own part and its own label.
  Include each style's own marks in it: Blueprint dimensions, Patent numerals and their leaders,
  Assembly arrows and step bubbles.
- Redraws: draw the same frame several times and compare the pixels; they must match. Read the
  canvas back twice before the first hash: after repeated `getImageData` calls Chrome moves the
  canvas to CPU rendering, which changes the antialiasing, so the first two reads can differ.
- Loading: in the 2D styles and under reduced motion, the network log shows no Three.js request;
  the one exception is a Technical build drawn with Three.js for complex geometry. Clay and
  Realistic request it only once chosen and near the viewport. With no WebGL there is no request at
  all, and a Three.js-drawn Technical build shows its still image. Test no WebGL in a separate
  browser session with WebGL disabled.
- Text: the smallest computed `font-size` on the stage is at least the minimum, and so is any text
  painted on the object, measured as font size times the drawing's scale.
- History: jump straight to the end, then back to the start of the walkthrough; every label is
  still shown.
- Keyboard: Tab reaches each part, Enter and Space each open its card, Escape closes it and returns
  focus.

## After any automated change

Re-run the captures after every automated pass or refactor, not only at the end. Regressions seen
in practice: beams disappearing, labels vanishing after a jump, and the 3D view rendering blank.

## Several variants

Update the shared comparison page, run the same captures for every variant, and carry each piece
of feedback to all of them.
