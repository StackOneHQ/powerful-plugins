# Rendering

Every style reads the same state every frame and keeps no state of its own. The camera, the part
positions and the label anchors come from one projection, so the HTML layer lines up with the
drawing exactly, whichever style drew it.

## Scroll state

- A tall track holds a sticky stage of `100svh`. The track's height sets the pacing: each stop
  needs enough scroll to read its text. A build with six phases used about `1300vh`.
- Map the track's scroll to a progress from 0 to 1, then ease the displayed progress toward it
  every frame with exponential decay, so a scroll-wheel jump glides instead of snapping.
- Give each phase a window of progress and shape it with `smoothstep`, so one phase finishes as
  the next begins.
- With anime.js: build one timeline with `autoplay: false` and seek it to `progress × duration`
  each frame. Without it, compute each pose from the windows directly. Both give identical frames;
  keep the direct computation as the fallback if the library fails to load.

## Projection

- Orthographic, at a steep three-quarter angle from above and to one side (one build used a camera
  direction of about `(-7, 5.2, 16)`). It may turn slightly with scroll and nothing more; a steady
  frame reads as engineered, a moving one as a demo reel.
- From that position an object laid along world x looks almost flat (about 7 degrees). Tilt it
  about 20 degrees around z for the rising diagonal. On a phone, flatten the tilt to a few degrees
  so the object spans the width and leaves room above and below it for text.
- Fit the scale so the object's rise plus both label stacks fit the viewport height; the stacks sit
  below the low end and above the high end, so they eat the height the object would use. When the
  object ends up under about 55% of the width, lower the tilt toward 15 degrees.
- Write the projection once: camera basis, pixels per unit, screen centre. Labels, hit areas and
  every style use it. For Three.js, set the frustum from the same numbers (`left = -cx / s`,
  `right = (width - cx) / s`, `top = cy / s`, `bottom = -(height - cy) / s`), and the two agree to
  the pixel.
- This camera sees the faces that point back along the axis and the sides, never the faces that
  point forward along it. Put anything that must be seen (an outlet, a readout, "round holes out")
  on a side or on a stepped rim, not on a forward-facing end.

## Technical (default)

A CAD or patent drawing. The page and every fill are the paper colour; the object exists only as
lines.

- **Build from primitives**: frustums, discs, boxes, rings and extruded profiles, each placed in
  the part's own coordinates. A frustum's outline is the convex hull of its two projected end rings;
  its visible end is an ellipse drawn after the hull.
- **Hidden lines by painting order.** Fill each piece with the paper colour, then stroke it; a
  nearer piece painted later hides the lines behind it, with no geometry maths. The order matters,
  and depth of centre alone gets it wrong for anything mounted on a part:
  - Draw whole parts in order along the axis, the farthest first. Parts are separated by planes
    across the axis and the camera looks back along it, so this order is exact.
  - Within a part, a piece that lies wholly upstream of another (nearer the camera along the axis)
    is drawn after it.
  - An attachment that overlaps its host along the axis (a nut on a flange, a gauge on a pipe, a
    tube in a tube sheet) is drawn after the host when it faces the camera, before it when it faces
    away.
  - Use depth of centre only to order attachments against each other.
- **Line weights.** Silhouettes about 1.25 px in the key ink; creases and detail (ring edges,
  seams, bolt circles, knurling) about 0.75 to 1 px in a lighter ink, about halfway to the paper.
  These weights suit a rim about 100 px across: scale them, and any hatch spacing, with the drawing
  (clamped to roughly 0.6 to 1.1 times), or small parts on a phone fill in solid. Round caps and
  joins. Draw at the device pixel ratio so hairlines stay crisp.
- **Light** comes from the upper left in every style. Technical draws no shading, but Patent's
  hatching, Graphite's highlights and the 3D styles' key light all take their side from it.
- **No shading at all**: no gradients, shadows or glows. Volume comes from the ellipses and the
  detail. Knurling is short parallel ticks around a rim, drawn only on its visible half.
- **Colours.** animejs.com uses a paper of `#dad5d0`, detail ink `#888581` and key ink `#302e2d`;
  take the subject's own neutrals when it has them. A dark brand gets Graphite rather than an
  inverted Technical.
- **The current component** takes the accent on its lines and a slightly heavier silhouette, and
  its fill mixes about a tenth of the accent into the paper. It may ease a short way off the axis
  toward the reader and back. Every other part keeps its lines.
- **Too complex to paint in order?** When parts interpenetrate or need curved detail that no
  single depth order can draw, use Three.js for this style instead: unlit paper-coloured fills with
  `polygonOffset`, plus `LineSegments` from `EdgesGeometry` (a threshold near 25 degrees) in the ink
  colours. It gives exact hidden lines at little cost.

## Blueprint

Technical in drafting colours. Everything in the Technical recipe applies; only these change.

- Paper is Prussian blue (about `#1d477f`), key lines near-white, detail lines a pale blue. Fills
  stay the paper colour, so hidden lines are still removed.
- A faint grid (a line every 14 px or so, about 8% white) sits on the paper, behind the object.
- The current component gets dimension lines: extension lines off two of its edges, a line between
  them with arrowheads, and the measurement written along it. Use a real number from the subject
  (a limit, a size, a latency) or mark it illustrative. Its lines take a pale yellow accent.

## Patent

Black ink on white, the look of a patent drawing's figures.

- White paper, black ink, no colour. Fills stay white, so hidden lines are removed.
- Shade with hatching, not tone: parallel lines at about 45 degrees on the side away from the light,
  clipped to each shape, spaced about 3 px at the drawing's reference scale.
- Reference numerals (10, 12, 14...) sit on thin curved leaders drawn by hand on the drawing, in
  place of text labels. The HTML labels become the legend, each one pairing a numeral with its
  name, so the text stays readable and indexable.
- The current component takes a heavier outline; the accent, if any, goes only on its numeral.

## Assembly manual

The wordless look of furniture instructions.

- White paper and bold, even outlines of about 2 px at the reference scale, with almost no detail
  lines. No shading.
- Arrows show the current component moving into place along the axis. Draw them from the
  component's real motion in the pose, so an arrow never points the wrong way.
- A numbered step bubble matches the walkthrough stop. Every other part drops to about 40% ink, so
  the part that moves stands out.

## Graphite

The animejs.com hero: solid shapes on a dark ground, lit from one side.

- Fills are near-black, a step lighter on faces toward the camera. No outlines.
- One warm highlight, about 1.5 px, runs along each silhouette edge that faces the light: stroke the
  edges of each outline whose outward normal points toward the upper left.
- The current component's highlight takes the accent and its fill lifts one step. Every silhouette
  needs its highlight, or neighbouring parts merge into one dark mass.

## Hologram

A glowing wireframe on near-black. It is the one style that shows hidden lines on purpose.

- No fills. Draw every edge, front and back: both end rings of each frustum, and lines along its
  length every 30 degrees or so.
- Lines are thin (about 0.8 px) in a cyan or the accent, with a small glow (a canvas shadow blur
  of about 6 px). Keep the blur small and redraw only on change: blur is the costly part.
- Showing every line tangles quickly, so the current component is drawn at full brightness and
  every other part at about 35%. Faint scanlines are optional.

## Clay

Soft matte 3D in Three.js: friendlier and cheaper than Realistic.

- `MeshStandardMaterial` with a roughness near 0.9 and no metalness. Colours are the brand palette
  mixed about 60% toward white; the current component takes the accent at full strength.
- A hemisphere light plus one soft key from the upper left. No environment reflections, no bloom.
- Strong ambient occlusion (GTAO) does most of the work: it is what makes clay read as clay.
- A light background with a soft contact shadow under the object. Unlike Realistic on a dark stage,
  a floor shadow suits Clay.
- Loading, fallback and performance follow Realistic below.

## Realistic

Physically based 3D in Three.js, for when the user asks for a lit, reflective render.

- **Materials.** `MeshPhysicalMaterial` with clear coat. Accent colours are metallic paint, not
  flat plastic; saturated flat colours read as tacky. Metals reflect an environment map
  (`RoomEnvironment`, or a studio of a few soft strips).
- **Light.** ACES filmic tone mapping. Start dim: an environment intensity of about 0.2 and an
  exposure just under 1; at 0.55 and 1.05 every metal part read white. Use one key light plus a
  hemisphere light. A coloured rim light on clear coat makes bloomed hot spots.
- **Glossy surfaces.** Very low roughness mirrors the environment's light panels as hard squares.
  A housing of dark smoked glass looked right at a roughness near 0.22 and a clear-coat roughness
  near 0.16.
- **Post-processing.** Ambient occlusion (GTAO) and SMAA. Keep glows and beams out of the AO
  pass, or they cast black blocks into the cavities around them. Bloom is optional: keep its
  threshold above the brightest metal highlight so only emissive pieces bloom, and lower its
  strength on a phone, where it spreads over more of the picture.
- **Shadows.** Soft shadows (VSM), parts shadowing each other. On a dark stage with no visible
  floor, leave out a shadow-catcher floor: its shadows float in empty space as dark blocks.
- **Backdrop.** Paint any background on a canvas and use it as `scene.background`, so it sits
  behind the post-processing instead of fighting it.
- **Performance.** `InstancedMesh` for repeated pieces (bolts, blades, lights) and
  `mergeGeometries` for static parts. Set `renderer.shadowMap.autoUpdate = false`, then
  `renderer.shadowMap.needsUpdate = true` once after the scene is built and again whenever a caster
  or a light moves; without the first one a static scene has no shadows. In one build these cut
  draw calls from 1,250 to 271 and GPU memory from 57 MB to 11 MB with no visible change.
- **Loading.** From a CDN with an import map in a standalone file, or as a dependency imported
  from this one section in an existing codebase. An import map downloads nothing until a dynamic
  `import()` asks for it; trigger it with an `IntersectionObserver` as the section approaches.
  Until Three.js has loaded, draw Technical, then swap. If WebGL is unavailable or the context is
  lost, switch to Technical.

## Treatments

Both work on the current component only, and ease in and out with the walkthrough's spring.

- **Cutaway.** Remove a wedge of about 100 degrees from the component's shell, centred on the side
  facing the camera. Draw the component's insides within the wedge, then fill the two cut planes
  and hatch them at 45 degrees. In a 2D style, clip to the wedge's projected outline to draw the
  insides, and fill and hatch the cut planes as flat polygons. In Three.js, put two clipping planes
  on the shell's material (`material.clippingPlanes`, with `renderer.localClippingEnabled`) and add
  flat caps on the cut planes.
- **X-ray.** The shell turns translucent (about 30% fill) and keeps its outline; the insides are
  drawn solid inside it, with their far edges dashed. It reads best in Clay and Realistic, where the
  shell can use `transmission`; in the line styles it is lower in contrast than Cutaway.
- Hidden lines are part of the point here, so the "no line shows through" check skips the treated
  component.

## Phones, reduced motion and no WebGL

- The 2D styles run everywhere. Clay and Realistic default to Technical on phones (a viewport of
  760 px or less, or a coarse pointer) and offer a visible toggle to the full version when WebGL is
  available; the full version offers the toggle back. Keep the choice for the visit
  (`sessionStorage`), and hide the toggle where WebGL is missing.
- `prefers-reduced-motion`: one labelled still frame of the object apart, with every label shown
  and the component text as a normal list. It never downloads Three.js: it overrides a stored
  choice, and the toggle is hidden. The still reuses the normal desktop or phone layout; leave
  panels it hides out of the fitting, since a hidden element measures as zero and collapses the
  fit.
