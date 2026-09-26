# Rendering

Both modes read the same state every frame and never keep state of their own. The camera, the
part positions and the label anchors come from one projection, so the HTML and canvas layers line
up with the 3D parts exactly.

## Scroll state

- A tall track holds a sticky stage of `100svh`. The track's height sets the pacing: each phase
  needs enough scroll to read its text. A build with six phases used about `1300vh`.
- Map the track's scroll to a progress from 0 to 1, then ease the displayed progress toward it
  every frame with exponential decay, so a scroll-wheel jump glides instead of snapping.
- Give each phase a window of progress and shape it with `smoothstep`, so one phase finishes as
  the next begins.
- With anime.js: build one timeline with `autoplay: false` and seek it to `progress × duration`
  each frame. Without it, compute each pose from the windows directly. Both give identical frames;
  keep the direct computation as the fallback if the library fails to load.

## Cinematic (Three.js)

**Camera.** Orthographic, at a steep three-quarter angle from above and to one side (one build used
a position of about `(-7, 5.2, 16)`). It may turn slightly with scroll and nothing more; a steady
frame reads as engineered, a moving one as a demo reel. From that position a machine laid along
world x looks almost flat (about 7 degrees); tilt the machine group about 20 degrees around z to get
the rising diagonal. Write the projection once (camera basis, pixels per unit, screen centre) and
set the Three.js frustum from the same numbers (`left = -cx / s`, `right = (width - cx) / s`,
`top = cy / s`, `bottom = -(height - cy) / s`); then Light, the labels and the chips need no Three.js
at all, and the two agree to the pixel.

**Materials and light.**
- `MeshPhysicalMaterial` with clearcoat. Accent colours are metallic paint, not flat plastic;
  saturated flat colours read as tacky.
- ACES filmic tone mapping, with a `RoomEnvironment` (or a dark studio with a few softbox strips)
  for reflections. Start dim: an environment intensity of about 0.2 and an exposure just under 1.
  At 0.55 and 1.05 every metal part read white and the casing silver.
- Ambient occlusion (GTAO) and SMAA anti-aliasing as post-processing.
- Soft shadows (VSM). Beams and glows cast no shadow. On a dark stage with no visible floor, keep
  the parts shadowing each other and leave out a shadow-catcher floor: its shadows float in empty
  space as dark blocks.
- The casing is dark smoked glass: near-black, clear coat, low roughness, reflecting a little. A
  bright environment turns it silver. Paint it as one surface so no seams or strips show.

**Beams.** Light, not particles or strings: a wide soft glow over a thin bright core, with a bloom
pulse travelling along it. Beams from several sources join before they enter the machine and fan
out to several destinations after it. A beam grows along its path as the example travels; it never
appears end to end at once. Grow it with `setDrawRange` on a `TubeGeometry` (its index holds
`radialSegments × 6` entries per tube segment), and make the pulse a short draw range of a
slightly wider tube at the head: no custom shader needed. Set the bloom threshold above the brightest
metal highlight so only beams bloom, and lower the strength on a phone: bloom spreads relative to
the canvas, so a strength that suits 1440 px floods 390 px.

**Performance.** Beauty first, then these, which keep it without cost:
- `InstancedMesh` for repeated pieces (bolts, blades, lights) and `mergeGeometries` for static
  parts.
- `renderer.shadowMap.autoUpdate = false`, then set `renderer.shadowMap.needsUpdate = true` once
  after the scene is built and again whenever a caster, a receiver or a light moves; without the
  first one a static scene renders with no shadows at all.
- Once Cinematic is chosen, load Three.js with an `IntersectionObserver` as the section approaches,
  and render only while the eased progress or a hover is changing: an idle page costs nothing.
- In one build these cut draw calls from 1,250 to 271 and GPU memory from 57 MB to 11 MB with no
  visible change.

**Loading.** From a CDN with an import map in a standalone file, or as a dependency imported from
this one section in an existing codebase. An import map downloads nothing until a dynamic
`import()` asks for it. Until Three.js has loaded, draw Light, then swap. If WebGL is unavailable or
the context is lost, switch to Light.

## Light (2D canvas)

- Project the same parts with the same camera maths onto a 2D canvas: filled shapes with a light
  gradient for volume, the same palette, the same beams drawn as layered strokes with a glow. A
  cylinder is the convex hull of its two projected end rings; draw parts far to near.
- Beams along the axis are drawn before the parts, so the parts hide them as solid parts do in 3D;
  beams to chips are drawn after. While closed, both casing halves are drawn after the parts (the
  lower half sits in front of the parts' lower edge) and as one outline, so no seam shows along the
  split.
- Text laid on a surface (the name on the casing) is drawn with a transform built from three
  projected corners. Check it is not mirrored: an axis pointing the wrong way flips it.
- Same state, same phases, same text. Only the drawing is simpler.
- Default on phones (a viewport of 760 px or less, or a coarse pointer), with a visible toggle to
  switch to Cinematic when WebGL is available (hide it when it is not). Cinematic offers the same
  toggle back to Light. Keep the choice for the visit (`sessionStorage`), and load Three.js only
  once Cinematic is chosen.

## Reduced motion and phones

- `prefers-reduced-motion`: one labelled still frame of the assembled or exploded machine, with the
  step text as a normal list. Draw it with Light, so reduced motion never downloads Three.js: it
  overrides a stored Cinematic choice, and the toggle is hidden. Pick a progress where no beam is
  half-grown, or the still shows a stray stub.
- A still image is also an acceptable phone default when even Light is too heavy; keep the toggle.
