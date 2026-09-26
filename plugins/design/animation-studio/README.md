# Animation Studio

Create web animations, interactive visuals, scroll-driven 3D explainers and short videos with the Web Animations API, Motion (motion.dev), anime.js, Three.js and Remotion. It picks the lightest library that does the job, follows your project's design tokens, and routes the build to a specialist agent.

## What it does

- **Ideates** animation concepts from rough specs or vague descriptions
- **Decides** which library fits (WAAPI for vanilla scripts, Motion for React, anime.js for SVG and scrubbable timelines, Remotion for video) and what each costs the page in bytes
- **Generates** production-ready animation code that respects `prefers-reduced-motion`, keeps idle motion quiet and never shifts the page layout
- **Builds** scroll-driven "exploded machine" explainers of a system or pipeline, in 3D or a lighter 2D mode
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
| `exploded-machine` | Turn a page, product or architecture into a scroll-driven exploded machine in the style of the animejs.com homepage. Two modes share one scroll state: Cinematic (Three.js, game-quality lighting, desktop default) and Light (a 2D canvas projection, phone default, with a toggle). An anime.js timeline can sequence the poses. Needs only a subject: a URL, a repo path or one sentence |

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
| [Three.js](https://threejs.org) | `three` | WebGL for the exploded-machine explainer |
| [Remotion](https://remotion.dev) | `remotion` | Programmatic video rendering (MP4/WebM) |
