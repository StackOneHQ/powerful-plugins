# Animation Studio

Create web animations, interactive explanations and short videos with SVG, Canvas, the Web Animations API, Motion (motion.dev), anime.js, Three.js and Remotion. It picks the lightest tools that do the job, follows your project's design tokens, and routes the build to the relevant skill or specialist agent.

## What it does

- **Ideates** animation concepts from rough specs or vague descriptions
- **Decides** which library fits (WAAPI for vanilla scripts, Motion for React, anime.js for SVG and scrubbable timelines, Remotion for video) and what each costs the page in bytes
- **Generates** production-ready animation code that respects `prefers-reduced-motion`, keeps idle motion quiet and never shifts the page layout
- **Explains** systems and mechanisms through Inspect, Follow, Operate and Compare modes: one source-grounded model drives the scene, readouts and captions as the reader changes inputs
- **Builds** scroll-driven "exploded machine" explainers that take a system apart component by component, as a CAD-like line drawing by default (graphite for a dark brand), or a blueprint, patent, assembly-manual, graphite, hologram, clay or reflective 3D look
- **Creates** marketing and product videos with Remotion
- **Teaches** concepts with narrated educational videos, measured audio timing, captions and transcripts

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
| `explain-machine` | Interactive explanations from a URL, repository, docs or short brief. Choose Inspect, Follow, Operate or Compare to answer a specific question; use a sourced worked example and a shared model for motion, readouts and captions. SVG, HTML, Canvas or 3D according to the subject |
| `educational-explainer` | Source-grounded lessons with worked examples, synchronized narration, captions, transcript and a local WAV/timeline checker |
| `exploded-machine` | Existing entry point and detailed Inspect recipe for scroll-driven exploded drawings. Preserves Technical, Blueprint, Patent, Assembly manual, Graphite, Hologram, Clay and Realistic styles, Cutaway and X-ray, and optional housing, definition panel, input/output chips and example flow |

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
/animation-studio:explain-machine <subject, URL or repo path>
/animation-studio:exploded-machine <subject, URL or repo path>
/animation-studio:educational-explainer <concept and source material>
```

In Codex, use `$animation-studio:explain-machine` for an interactive explanation.
`$animation-studio:exploded-machine` continues to produce detailed exploded drawings. The
four agents are available there through the `$animation-studio:animation-studio-specialists` skill.
Use `$animation-studio:educational-explainer` in Codex for a narrated lesson.

Explain Machine chooses the useful modes for the question; it does not require four separate
views. Physical analogies are labeled, illustrative values stay distinguishable from sourced
facts, and controls exercise the same model that produces the visual state. Local artifacts
and checks need no additional approval. Publishing, sending, spending, new dependencies and
external services require authorization. The skill adds no runtime dependency or hosted service.

Educational narration can use an installed local speech engine. Check whether it
needs a model download before promising offline use. The plugin installs no speech
engine automatically.
Hosted speech providers are optional and receive narration only when you authorize
that service. The bundled timeline checker uses Python's standard library and no network.

Or just describe what you want:
- "Make the hero section feel alive"
- "Add floating cards to the integrations grid"
- "Explain our request pipeline as a scroll animation"
- "Let me change an input and see how this mechanism responds"
- "Compare two cache policies with the same request sequence"
- "Create a 15s product demo video"

## Brand and tokens

The plugin carries no brand. It reads colours, fonts and motion curves from your project's design tokens or brand guide, and uses a readable neutral treatment when there are none. The timing and easing values in `docs/BRAND-ANIMATION.md` are defaults you can override.

## Works well with

Optional, all installable from this marketplace:

- `remotion-best-practices`: Remotion rules and patterns (Remotion's own skill, pinned here)
- `decision-artifacts`: mock two to four visual options side by side before building one
- `browser-recorder`: record an animation to compare two versions frame by frame
- `browser-automation`: capture screenshots at each scroll position and viewport

## Libraries

| Library | npm | Use case |
|---------|-----|----------|
| SVG and Canvas | built in | Inspectable mechanisms and model-driven interactive explanations |
| Web Animations API | built in | Fades, staggers and sequenced reveals with zero bytes |
| [Motion](https://motion.dev) | `motion` | React component animations (hover, scroll, layout) |
| [anime.js](https://animejs.com) | `animejs` | Vanilla JS animations (SVG, timelines, stagger) |
| [Three.js](https://threejs.org) | `three` | Explanations where volume or viewpoint matters; exploded-machine Clay and Realistic styles |
| [Remotion](https://remotion.dev) | `remotion` | Programmatic video rendering (MP4/WebM) |
