# Animation Studio

Create web animations, interactive visuals, scroll-driven 3D explainers and short videos with the Web Animations API, Motion (motion.dev), anime.js, Three.js and Remotion. It picks the lightest library that does the job, follows your project's design tokens, and routes the build to a specialist agent.

## What it does

- **Ideates** animation concepts from rough specs or vague descriptions
- **Decides** which library fits (WAAPI for vanilla scripts, Motion for React, anime.js for SVG and scrubbable timelines, Remotion for video) and what each costs the page in bytes
- **Generates** production-ready animation code that respects `prefers-reduced-motion`, keeps idle motion quiet and never shifts the page layout
- **Builds** scroll-driven "exploded machine" explainers that take a system apart component by component, as a CAD-like line drawing by default, or a blueprint, patent, assembly-manual, graphite, hologram, clay or reflective 3D look
- **Creates** marketing and product videos with Remotion

## Installation

```bash
# Claude Code
/plugin marketplace add StackOneHQ/powerful-plugins
/plugin install animation-studio@powerful-plugins

# Codex
codex plugin marketplace add StackOneHQ/powerful-plugins
codex plugin add animation-studio@powerful-plugins
```

## Skills

| Skill | Purpose |
|-------|---------|
| `animation-studio` | Entry point: decision matrix, page cost table, default timing and easing, idle-motion and layout rules, routing to the agents |
| `exploded-machine` | Explain a system, product or architecture component by component on scroll, as an accurate exploded drawing in the style of the animejs.com homepage. The subject is drawn as a form you pick (an engine, a pipe run, a tube, a rack, a lens...), with each component a part that form really has. Eight styles share one scroll state: Technical (a CAD-like line drawing on a 2D canvas, the default), Blueprint, Patent, Assembly manual, Graphite, Hologram, Clay and Realistic (reflective Three.js 3D); Cutaway and X-ray show what is inside a component. A housing, a definition panel, input and output chips, or a beam carrying an example through are optional layers. Needs only a subject: a URL, a repo path or one sentence |

## Agents

| Agent | Purpose |
|-------|---------|
| `animation-ideator` | Brainstorms 2-3 animation approaches from a concept |
| `motion-creator` | Builds Motion animation components for React apps and React islands |
| `animejs-creator` | Builds anime.js and Web Animations API animations for plain HTML and non-React components (SVG, timelines) |
| `video-creator` | Orchestrates Remotion video creation |

## Usage

```
/animation-studio:animation-studio <animation brief>
/animation-studio:exploded-machine <subject, URL or repo path>
```

In Codex, use `$animation-studio:animation-studio` and `$animation-studio:exploded-machine`. The
four agents are available there through the `$animation-studio:animation-studio-specialists` skill.

Or just describe what you want:
- "Make the hero section feel alive"
- "Add floating cards to the integrations grid"
- "Explain our request pipeline as a scroll animation"
- "Create a 15s product demo video"

## Brand and tokens

The plugin carries no brand. It reads colours, fonts and motion curves from your project's design tokens or brand guide, and asks when there are none. The timing and easing values in `docs/BRAND-ANIMATION.md` are defaults you can override.

## Works well with

Optional, all installable from this marketplace:

- `remotion-best-practices`: Remotion rules and patterns (Remotion's own skill, pinned here)
- `decision-artifacts`: mock two to four visual options side by side before building one
- `browser-recorder`: record an animation to compare two versions frame by frame
- `browser-automation`: capture screenshots at each scroll position and viewport

## Libraries

| Library | npm | Use case |
|---------|-----|----------|
| Web Animations API | built in | Fades, staggers and sequenced reveals with zero bytes |
| [Motion](https://motion.dev) | `motion` | React component animations (hover, scroll, layout) |
| [anime.js](https://animejs.com) | `animejs` | Vanilla JS animations (SVG, timelines, stagger) |
| [Three.js](https://threejs.org) | `three` | WebGL for the exploded-machine Clay and Realistic styles |
| [Remotion](https://remotion.dev) | `remotion` | Programmatic video rendering (MP4/WebM) |
