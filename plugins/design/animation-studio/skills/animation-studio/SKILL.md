---
name: animation-studio
description: Create web animations, interactive visuals and short videos with the Web Animations API, Motion, anime.js and Remotion. Use for animation, motion, transitions, scroll effects, hover and micro-interactions, SVG path drawing, idle motion on graphs, and animated explainers or product videos. Picks the lightest library that does the job and routes to specialist agents.
metadata:
  tags: animation, motion, animejs, remotion, waapi, video, 3d, webgl
  optional_skills:
    - remotion-best-practices
---

## When to use

Use this skill when:
- Adding animations, transitions, or motion effects to any component or page
- Creating marketing videos, product demos, or animated explainers
- Someone says "make it move", "animate this", "add motion", "floating", "parallax"
- Building interactive visual effects (hover states, scroll-triggered, layout animations)
- Working with SVG animations, path drawing, or morphing
- Turning a system, pipeline or architecture into a scroll-driven 3D explainer (route to `exploded-machine`)

> **Design tokens**: use the project's own design tokens or brand guidelines for colour, spacing,
> radius and motion curves. If the project has none, ask before inventing a palette. The values
> in this skill are defaults for timing and easing, not a brand.

## Decision Matrix: which library?

| Signal | Library | Why |
|--------|---------|-----|
| Sequenced reveal in a vanilla `<script>` (fade, stagger, typewriter, spring pop) | **Web Animations API** (`element.animate`) | Zero bytes, same easing curves, runs on the compositor. A Motion-based reveal can usually be rewritten in WAAPI at parity; verify it frame by frame |
| React component + hover/scroll/layout | **Motion** (`motion`) | Declarative React API, spring physics. If the component is a hydrated island, hydrate it on visibility rather than on load |
| SVG path draw, morphing, complex timeline | **anime.js** (`animejs`) | Vanilla JS, no React needed, works in plain `<script>` tags |
| Staggered effects without a React island | **WAAPI first, anime.js if you need a timeline object** | A stagger is a delay per element; WAAPI does that with no library |
| Video output (MP4/WebM), social clips | **Remotion** | Rendered video; hand off to the `video-creator` agent |
| Simple fade-in on scroll, basic stagger | **CSS** | If the project already has a CSS reveal system, use it. Otherwise one IntersectionObserver toggling a class is enough. Zero or near-zero JS |
| React enter/exit animations (conditional render) | **Motion** | `AnimatePresence` handles mount/unmount transitions |
| Canvas/WebGL 3D scenes in video | **Remotion + Three.js** | 3D in rendered video, no cost to a live page |
| Data-driven 3D on a live page (points, graphs, constellations) | **Canvas 2D projection, no library** | A hand-written projection can place a few hundred points in 3D with a script of a few KB gzip |
| Scroll-driven 3D explainer of a system, pipeline or architecture | **`exploded-machine` skill** (a Cinematic Three.js mode and a Light 2D canvas mode, both driven by scroll progress) | The one case where WebGL on a live page earns its weight: it is the centrepiece of the page, loads only there, and ships a Light 2D mode |

**Default choice when unclear:** WAAPI for vanilla scripts, Motion for React components, anime.js only for SVG path work or a timeline you need to scrub.

### What each choice costs the page

Rough orders of magnitude, tree-shaken and gzipped. They move with every library version and bundler, so treat them as a guide to the ranking, not as figures to quote. In most bundlers, a library imported from a component's script ships with every page that renders the component, not once per site.

| Choice | Roughly what it adds to the page |
|--------|---------------------------------|
| Web Animations API | 0 KB |
| anime.js 4 (`animate`, `createTimeline`) | under 10 KB gzip |
| Motion in a vanilla script (`animate`, `inView`) | around 20 to 25 KB gzip |
| Motion for React on a page that ships no React yet | Motion plus React and ReactDOM, tens of KB gzip more |

Check your own build rather than trusting this table: run the production build, then read the chunk sizes it reports (or the files in its output directory) for the page you touched.

## Workflow

1. **Understand the target**: read the component or page code
2. **Pick the library**: use the decision matrix above
3. **Check existing animations**: don't conflict with a CSS reveal system or existing Motion code
4. **Dispatch to the right agent or skill:**
   - Concept/brainstorming → `animation-ideator`
   - Motion component → `motion-creator`
   - anime.js or vanilla animation → `animejs-creator`
   - Video → `video-creator`
   - Scroll-driven 3D system explainer → `exploded-machine` skill
5. **Verify**: check that `prefers-reduced-motion` is respected, on the production build as well as the dev server. Dev servers can differ from production in script loading and hydration timing, so build, then serve the output with a static server or the framework's preview command. When you replace or refactor an existing animation, prove parity frame by frame: capture the old and new versions at the same timestamps and compare them. The `browser-recorder` plugin in the powerful-plugins marketplace can record both runs

## Default Animation Language

These defaults suit a professional product. If the project defines motion tokens, use those instead.

### Timing
- UI elements: 200–600ms
- Page transitions: 300–500ms
- Stagger delay: 80–120ms between children
- Video scene transitions: up to 3s
- Never exceed 1s for interactive UI elements

### Easing
- **Motion**: `type: "spring"` with `visualDuration: 0.4, bounce: 0.15` (default)
- **anime.js**: `ease: cubicBezier(.4, 0, .2, 1)` (Material-inspired), with `cubicBezier` imported from `animejs`. v4 dropped the string form `'cubicBezier(...)'`: it warns and falls back to linear
- Avoid `linear` except for continuous loops (progress bars, spinners)
- Avoid aggressive bounce (> 0.3) unless the brand is deliberately playful

### Enter Patterns
- **Fade up** (default): `opacity: 0→1, translateY: 20px→0`
- **Scale in**: `opacity: 0→1, scale: 0.95→1`
- **Slide in**: `translateX: -20px→0, opacity: 0→1`

### Exit Patterns
- Only animate exit when element actually leaves the DOM
- Reverse of enter (fade down, scale out)
- Keep exit faster than enter (0.6× duration)

### Principles
- Always respect `prefers-reduced-motion` (disable transforms, keep opacity)
- Spring physics preferred over easing curves for React (Motion)
- Stagger children for lists and grids, always
- No animation above the fold on initial page load (it delays the first paint of that content)
- Use CSS for simple cases; don't reach for JS when CSS works

## Motion: Quick Reference

```bash
pnpm add motion
```

```tsx
import { motion, AnimatePresence } from "motion/react"

// Scroll-triggered (the most common case)
<motion.div
  initial={{ opacity: 0, y: 20 }}
  whileInView={{ opacity: 1, y: 0 }}
  viewport={{ once: true, margin: "-50px" }}
  transition={{ type: "spring", visualDuration: 0.4, bounce: 0.15 }}
/>

// Stagger children via variants
const container = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.1 } },
}
const item = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
}

<motion.ul variants={container} initial="hidden" whileInView="visible" viewport={{ once: true }}>
  {items.map(i => <motion.li key={i} variants={item} />)}
</motion.ul>

// Hover + tap
<motion.button whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }} />
```

**Framework integration**: `motion/react` needs React on the page.
- In a React app (Next.js, Vite, Remix and so on), import it straight into the component.
- In a framework that hydrates components selectively, the animated component is an island: hydrate it when it scrolls into view, not on load. In Astro, for example, that is `<AnimatedSection client:visible />` rather than `client:load`.
- Outside React (plain HTML, Vue, Svelte), use the framework-agnostic `animate` and `inView` exports from `motion`, the framework's own transition system, or the Web Animations API.

## anime.js: Quick Reference

```bash
pnpm add animejs
```

```js
import { animate, stagger, createTimeline, svg, cubicBezier } from 'animejs'

// Basic animation
animate('.card', {
  translateY: [20, 0],
  opacity: [0, 1],
  duration: 400,
  ease: cubicBezier(.4, 0, .2, 1),
  delay: stagger(100),
})

// SVG path drawing
animate(svg.createDrawable('path'), {
  draw: ['0 0', '0 1'],
  duration: 1500,
  ease: cubicBezier(.4, 0, .2, 1),
})

// Timeline
const tl = createTimeline({ defaults: { duration: 400, ease: cubicBezier(.4, 0, .2, 1) } })
tl.add('.title', { opacity: [0, 1], translateY: [20, 0] })
  .add('.subtitle', { opacity: [0, 1], translateY: [20, 0] }, '-=200')
  .add('.cards', { opacity: [0, 1], translateY: [20, 0], delay: stagger(100) }, '-=200')
```

**Integration**: anime.js runs anywhere a script can: a module script in plain HTML (with a bundler resolving the import), a component's mount hook (`onMounted` in Vue, `onMount` in Svelte), or a `<script>` in an Astro component. The same pattern in plain HTML:
```html
<section class="hero" data-hero>
  <h1>Title</h1>
</section>

<script type="module">
  import { animate } from 'animejs'

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        animate('[data-hero] h1', {
          translateY: [20, 0],
          opacity: [0, 1],
          duration: 400,
        })
        observer.unobserve(entry.target)
      }
    })
  })

  document.querySelectorAll('[data-hero]').forEach(el => observer.observe(el))
</script>
```

## Remotion: Delegation

For video creation, hand off to the `video-creator` agent:
1. It designs the scenes and the choreography
2. If the `remotion-best-practices` skill is installed, load it for composition structure, spring configs and audio
3. Brand colours, logo and messaging come from the project's brand guidelines; ask if there are none

## Before you build: show two to four options

For any visual decision with no obvious answer (how a meter fills, how a toggle is emphasised,
how a graph reads at rest), mock the options as a **live artifact** and let the person choose,
before implementing one.

Run every option with the same data and content so they compare fairly. Showing options beats
describing them in prose, and both beat building one and defending it. A decision framed this
way usually settles in a single round.

Keep it cheap: one HTML file, the project's real tokens, two to four options, a one-line note on
what each costs to build. The `decision-artifacts` plugin in the powerful-plugins marketplace covers the comparison page
itself.

## Idle motion budget

Ambient motion is near-imperceptible or absent. Still until the visitor interacts is a good
default, and a very slight pulse is the most it should do: nothing ambient may compete with the
content.

- A breathing element moves very little. Treat roughly 10% in size and 15% in opacity as the
  upper end for ambient work, not a target, and give each element its own phase and pace so
  nothing pulses in unison.
- Run one `requestAnimationFrame` loop, gated three ways: only while the element is on screen
  (`IntersectionObserver`), stopped when the tab is hidden (`visibilitychange`), and never
  started under `prefers-reduced-motion`.
- Throttle that loop only when you have measured a reason to. Capping an expensive canvas at
  ~25fps is a real saving, and it is visible on anything that moves quickly, so it suits slow
  ambient motion and not pointer-driven motion. If the cost turns out to be layout or paint
  rather than the canvas, fix that instead of dropping frames.
- Take curves and durations from the project's design system rather than inventing them. If it
  has none, make hover asymmetric: a slightly springy enter and a plainer, calmer exit. Suggested
  starting values: `350ms cubic-bezier(0.34, 1.56, 0.64, 1)` for a hover enter, `300ms ease` for
  the exit, about `80ms` for a press, `120ms ease` for a state change, and
  `cubic-bezier(.4, 0, .2, 1)` for a content reveal. Tune them to the brand.
- Under reduced motion, place the final state immediately. Never just run the animation faster.
  This is the one case that overrides "disable transforms, keep opacity" in Principles above:
  that rule is for a one-shot reveal, where the fade still communicates something. An ambient
  loop has no final state to arrive at, so a pulsing opacity is the same distraction as a
  pulsing size. Stop it entirely.
- `prefers-reduced-motion` is a setting the visitor can change mid-session, so subscribe to it
  (`matchMedia(...).addEventListener('change', ...)`) rather than reading it once at startup.
- Keep a reference to whatever tears the loop down (an `AbortController` works well for the
  observers and listeners). In a component framework, abort it from the unmount hook (`useEffect`
  cleanup, `onUnmounted`, `onDestroy`). Don't rely on a router's navigation events alone: some
  only fire in certain modes. In Astro, for example, `astro:before-swap` and `astro:page-load`
  only fire when View Transitions are enabled.

## Motion must not move the page

Anything that plays, fills or reveals inside a page section must not change that section's
height while it runs. A demo that grows pushes everything below it down, and the defect is
invisible in a screenshot.

Reserve the space (a fixed height or an `aspect-ratio`), scroll the overflow inside a fixed row,
and prove it by sampling the wrapper's height across a full run rather than trusting it.
`contain: size` also stops the growth, but the element then ignores its content when sizing, so
it needs an explicit height or it collapses to zero.

## Anti-Patterns

- **Don't animate everything**: pick 2-3 key elements per section
- **Don't mix Motion and CSS transitions on the same property**: pick one
- **Don't hydrate an animated island on load**: in a partial-hydration framework, hydrate it when it becomes visible (in Astro, `client:visible` rather than `client:load`)
- **Don't fight an existing CSS reveal system**: if CSS handles it, stop
- **Don't use anime.js inside React components**: use Motion for React
- **Don't add Three.js or a WebGL layer to a live page by default**: use Remotion for 3D in videos and a Canvas 2D projection for data on the page. The exception is a scroll-driven system explainer built with the `exploded-machine` skill, which loads WebGL only on its own page and ships a Light 2D mode
- **Don't import Motion or anime.js into a vanilla `<script>` for fades and staggers**: that is a Web Animations API job, and the library ships on every page that renders the component
- **Don't stagger more than 6 items**: after 6 it feels slow, not smooth
