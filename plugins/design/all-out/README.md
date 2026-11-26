# All-out

Builds the most ambitious version of a presentation, launch video, product page, mockup or
document. The build gets no creative direction, only the facts and the hard constraints, plus one
prompt that asks for the most amazing version of the thing it has ever seen.

Templates, example outputs, layouts and length targets pull a model towards the average of what it
was shown. All-out keeps what must be true and drops everything that only says how it's usually
done. The prompt is adapted from
[a post by @fluxxrider](https://x.com/fluxxrider/status/2125701190872915996), who gave a model this
prompt and no other direction for a presentation.

## Install

**Claude Code**

```text
/plugin marketplace add StackOneHQ/powerful-plugins
/plugin install all-out@powerful-plugins
```

**Codex**

```sh
codex plugin marketplace add StackOneHQ/powerful-plugins
codex plugin add all-out@powerful-plugins
```

## Try it

> Go all out on a presentation about how tides work. It has to run offline as one HTML file.

> Make an all-out version of this landing page next to the one we just built. Keep the copy and
> the links exactly as they are.

The skill writes `all-out/<slug>/BRIEF.md` with the exact brief and what it left out. It builds
the asset next to that file and replies with where it is and up to three ideas worth bringing back
into your standard version.

## What it contains

| Skill | What it does |
|---|---|
| `all-out` | Sorts the request into hard constraints (facts, required content, format, accessibility) and soft ones (templates, examples, layouts, length targets), writes the brief, and runs the build in a fresh context where the host has one (otherwise from the brief alone), on the strongest model settings your setup already allows. |

There are no commands, agents or hooks.

## Using it inside another skill

A skill that produces assets can call All-out for an extra variant: pass it the same hard
constraints and keep the result in its own folder, labelled "All-out". Judge that variant only on
the hard constraints, not on your house style, because the difference is what you're looking for.

## Boundaries

All-out writes only into its output folder and runs local previews with tools you already have.
It asks before installing packages or downloading files, before publishing, sending or deploying
anything, before raising model spend, and before paid image, video or voice generation that you
didn't ask for. Web pages, comments, transcripts and tool output go into the brief as quoted
source material, never as instructions.
