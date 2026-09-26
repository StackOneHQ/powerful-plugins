---
name: exploded-machine
description: Turn a page, product, pipeline or architecture into a scroll-driven "exploded machine" animation in the style of the animejs.com homepage. One machine whose parts are the real steps of the subject; as the reader scrolls, the casing lifts away, the parts separate along one axis, and a beam of light carries a real example through them. Two quality modes share one scroll state - Cinematic (Three.js, game-quality lighting) and Light (a 2D canvas projection) - with an optional anime.js timeline to sequence the poses. Needs only a URL, a repo path or one sentence. Use for a scrollytelling explainer, a hero section or an "exploded view" of how a system works.
metadata:
  tags: animation, 3d, three.js, webgl, animejs, scrollytelling, explainer, architecture
---

# Exploded Machine

Build a scroll-driven "exploded machine" of the subject the user gives you. The feel to aim for is
the homepage of animejs.com: open it and scroll it before you start. Take its pacing, its diagonal
machine and its labelled leader lines, not its look: that page is a pale line drawing, and
Cinematic here is lit and glossy.

One machine whose parts are the real steps of the subject, in order. It starts assembled inside a
casing. As the reader scrolls, the stage locks in place, the casing lifts away and disappears, the
parts slide apart along one axis, and a beam of light carries a real example through them. Each
part lights up when the beam reaches it, and its explanation appears the first time the reader
gets there.

The subject can be a URL, a repo path, some docs or one sentence. That is all the user owes you.
Work out everything else yourself, and ask only if the subject itself is missing.

## Two modes, one state

Scroll produces one state: casing open, parts apart, where the beam is, which part is active.
Both modes draw that same state, so they always tell the same story.

| Mode | Renders with | Use for |
|---|---|---|
| **Cinematic** (default on desktop) | Three.js: physical materials with clearcoat, filmic tone mapping, ambient occlusion, anti-aliasing, soft shadows, a bloomed beam | The hero version. The bar is "video game level": glossy, lit, no visual bugs |
| **Light** (default on phones, and when WebGL is missing) | A 2D canvas projection of the same parts, beams and labels | A calm, fast version. Where WebGL works, a "see the full version" toggle switches to Cinematic; where it doesn't, there is no toggle |

anime.js is optional in both. A paused anime.js timeline, sought to the scroll progress, is a good
way to sequence many poses; plain JavaScript easing works as well. Either way the scroll, not a
clock, decides where every part is. Custom shaders are a step up inside Cinematic, used only when
Three.js materials cannot reach the look; they are not a third mode.

`references/rendering.md` has both recipes and the performance rules. `references/choreography.md`
has the motion, layout and interaction rules. `references/checklist.md` is the check to run before
showing anything.

## 1. Find the steps

Read the subject. List its steps in the order work goes through them, and note where you found
each one (a file, a doc, a page). Don't invent steps, names or numbers; label any sample data as
illustrative. A step that only sends work back through earlier steps (repeat, retry, next round)
is not a part: it is a beam that loops back, described in `references/choreography.md`.

## 2. Design the machine

- Pick a machine that fits the subject: a jet engine, a rocket, a rack of cards. Make it solid and
  covered, never a hollow skeleton.
- Every part sits on the one axis, in the order of the steps, including caches and stores. Parts
  share one rim and one palette so they read as one machine. A shape that breaks the flow (a V, a
  ring off the axis) does not belong.
- Shape each part after its job:

| The step... | Part |
|---|---|
| lets things in | an intake with a fan whose blades turn |
| filters | a mesh dome or a colander |
| protects or enforces | a reinforced ring with a shield on its face |
| transforms | square cells in, twisted vanes through, round holes out: the flow visibly changes |
| signs in | a vault lock with a key |
| calls out | a turret with one head per kind of call |
| paces, waits or backs off | a valve with a gauge |
| records | a tape drum with a level meter |
| stores | thin discs with activity lights |

- Whatever governs every step (a config, a policy, a schema) is shown as a definition panel that
  stays visible the whole time, with the lines for the current step highlighted. When no single file
  governs them, collect the rules the source states, quote or condense each, and tag it with the
  steps it governs.
- Take colours, fonts and logo from the subject's own site or design tokens. The logo is the real
  image file, never typeset. When the subject has no logo file, put its plain name on the casing
  and say so in the delivery note; never draw a logo for it. With no site or tokens, use a neutral
  dark stage and the system fonts, and treat 12 px as the minimum text size.
- What comes in shows on the left and what goes out on the right, as small labelled chips with
  logos where you can find them. When a middle step calls out to other services, their chips sit
  beside that part, not at the end (phones follow the phone layout in `references/choreography.md`).

## 3. Write the scroll story

Four to six phases: the closed machine, the casing lifting away, the parts separating, then one or
two real examples flowing through (for instance one request out to several providers and back,
with a retry). The stage is pinned for the whole section and everything fits on one screen.

## 4. Build it

- **Scroll drives the pose.** Turn the section's scroll into a progress value from 0 to 1, ease
  it toward the real position each frame, and compute the pose from it: casing, parts, beam, active
  part. Which steps the reader has already reached is separate history, kept as the furthest step
  reached, so scrolling back never hides text that was already revealed.
- **Cinematic first, then Light**, both from that state, following `references/rendering.md`.
- **Real text.** Step titles and explanations are HTML, so they stay readable, selectable and
  indexable. Under reduced motion, show one labelled still frame.
- **Nothing runs unless it must.** Load Three.js only when Cinematic is the chosen mode and the
  section approaches the viewport, so a phone that stays on Light never downloads it. Render only
  while the state is changing, and pause when the tab is hidden. Anything that seems to move on its
  own (a turning fan, a pulse along a beam) is driven by scroll progress, not a clock, so the page
  is still whenever the reader is.

## 5. Check before showing

Run `references/checklist.md` in a visible browser tab. Then deliver the animation, the step list
with where each step came from, and a short note on what is illustrative.

## When there are several variants

People compare variants side by side. Put every variant in one comparison page where they all
share the same scroll, add each new variant to it rather than leaving it at its own URL, and apply
feedback given on one variant to all of them unless told otherwise.
