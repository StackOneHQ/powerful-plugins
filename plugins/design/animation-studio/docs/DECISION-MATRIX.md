# Animation Library Decision Matrix

## Quick Decision Tree

```
Is it a video/MP4?
  → Yes: Remotion (see the video-creator agent)
  → No: Continue...

Is it a scroll-driven 3D explainer of a system or pipeline?
  → Yes: the exploded-machine skill (Three.js + 2D canvas overlay)
  → No: Continue...

Is it a simple fade-in on scroll?
  → Yes: CSS (the project's existing reveal utility, or one IntersectionObserver toggling a class)
  → No: Continue...

Is it inside a React component?
  → Yes: Motion (motion.dev)
  → No: Continue...

Does it need SVG path drawing or morphing?
  → Yes: anime.js
  → No: Continue...

Does it need a multi-step timeline you scrub, pause or reverse?
  → Yes: anime.js (timeline API)
  → No: Continue...

Default:
  → Web Animations API (element.animate): zero bytes, handles fades, staggers and sequences
```

## Comparison Table

| Feature | CSS reveal | Web Animations API | Motion | anime.js | Remotion |
|---------|-----------|--------------------|--------|----------|----------|
| Bundle size | 0 KB | 0 KB | see cost table in the `animation-studio` skill | see cost table | N/A (build tool) |
| React required | No | No | Yes (for `motion/react`) | No | Yes (build only) |
| Scroll trigger | IntersectionObserver toggling a class | Manual IntersectionObserver | `whileInView` | Manual IntersectionObserver | N/A |
| Spring physics | No (only a spring-like cubic-bezier) | No (same) | Yes | Yes (spring ease) | Yes |
| SVG animation | Limited | Limited | Limited | Full (path, morph) | Yes |
| Gesture support | Hover only | No | Yes (hover, tap, drag) | No | N/A |
| Timeline | No | Delays per element | `variants` (limited) | Full timeline API | `Sequence` |
| 3D transforms | CSS only | CSS only | CSS only | CSS only | Three.js |
| Server render | N/A | N/A | N/A | N/A | Yes (video output) |
| Where it runs | Any page | Any script or mount hook | React component (or its vanilla `animate` in any script) | Any script or mount hook | Separate project |

## When NOT to Use Each

| Library | Don't use when... |
|---------|------------------|
| CSS reveal | Need interaction (tap, drag), complex sequencing, or SVG drawing |
| Web Animations API | Need a scrubbable timeline, SVG morphing, or gestures |
| Motion | Target isn't a React component, or animation is trivially simple |
| anime.js | Inside a React component (use Motion instead), need gestures, or WAAPI already does it |
| Remotion | Need interactive DOM animation (it renders video files, not live UI) |
