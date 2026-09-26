# Before showing it

Check in a **visible** browser tab. A hidden or background tab pauses `requestAnimationFrame`, so
the scene freezes and looks broken when it is not. A headless browser is fine when
`document.visibilityState` reports `visible`; confirm that first.

## Capture

Screenshot fixed scroll points (0, each phase boundary, 1) on desktop and on a phone, in both
Cinematic and Light (Cinematic only where the device has WebGL). Use the same points every time, so
two versions compare frame for frame. Before each screenshot, wait until the render loop has
stopped; a frame taken mid-glide does not count. A `?mode=light|cinematic` URL parameter makes both modes
reachable from a script.

## Look for

- [ ] Every part is on the axis, in step order, and looks like its job.
- [ ] The casing never passes through a part and is fully gone before the parts separate.
- [ ] No seams, strips or stray bars on the glass.
- [ ] The logo is the image file (or, when the subject has none, its plain name), the right way up.
- [ ] No part is lit before the beam reaches it, unless it is hovered or clicked; highlights ease
      in and out, with no snap.
- [ ] No part changes colour as the machine expands.
- [ ] Beams are soft light that travels, joins before the machine and fans out after it; no
      dots, no strings, no shadows.
- [ ] Step labels appear on first arrival and stay when scrolling back; one caption at a time;
      everything fits one screen.
- [ ] The definition panel is visible throughout, with the current step's lines highlighted.
- [ ] Leader lines end at their labels and never cross.
- [ ] Hover cards don't cover their part; chips link where they should.
- [ ] No text below the brand's minimum size.
- [ ] When scrolling stops, the render loop stops and the current frame stays on screen;
      scrolling is smooth.
- [ ] Every part's card opens from the keyboard, and focus is visible.
- [ ] Reduced motion shows the still frame; the phone default and its toggle work.

## Measure, don't eyeball

Expose the state on `window` for the test run, then check:

- Idle: once the glide and the highlight springs have settled and the loop has stopped itself, wrap
  `requestAnimationFrame` with a counter for 3 s. It must read 0.
- Smoothness: record frame timestamps during a scroll glide; the 95th percentile should be one
  frame (16.7 ms at 60 Hz).
- Alignment: project a few part points with `Vector3.project(camera)`, convert the result from
  normalised device coordinates to CSS pixels, and compare with the shared projection; they should
  differ by less than a pixel.
- Draw calls: set `renderer.info.autoReset = false`, reset it before the composer renders, and read
  `renderer.info.render.calls`, which then counts every pass.
- Lines: a segment-intersection test of the leader lines against each other, the parts, the chips
  and the labels finds zero, not counting where each line meets its own part and its own label.
- Loading: in Light, under reduced motion and with no WebGL, the network log shows no Three.js
  request. Test no WebGL in a separate browser launched with WebGL disabled.
- Text: the smallest computed `font-size` on the stage is at least the minimum.
- History: scroll to the end, then back to the start of the flow; every label is still shown.
- Keyboard: Tab reaches each part, Enter and Space each open its card, Escape closes it and returns
  focus.

## After any automated change

Re-run the captures after every automated pass or refactor, not only at the end. Regressions seen
in practice: beams disappearing, and the 3D view rendering blank.

## Several variants

Update the shared comparison page, run the same captures for every variant, and carry each piece
of feedback to all of them.
