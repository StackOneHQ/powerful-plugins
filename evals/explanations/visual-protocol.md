# Visual explanation protocol

Use `visual.jsonl` as original synthetic tasks for educational-explainer,
diagram-explainer and guided walkthroughs. Its relationship and comprehension
questions follow the evaluation ideas of AI2D and ScienceQA cited in README.md;
the cases are not examples from those datasets or official benchmark scores.

Run every case through all three formats in each arm: video, diagram and walkthrough.
Report results by case and format; an unavailable format is missing evidence, not
a smaller passing suite. Freeze development and holdout cases as the writing
protocol describes, with at least two fresh sessions per arm and case-format pair.

A video request asks for
a narrated lesson with a transcript and captions; a diagram request asks for an
editable source and rendered preview; a walkthrough request asks for a local
interactive HTML page and a static equivalent. Keep the source, audience and
budget the same across released and candidate skills. For the new diagram skill,
use the host's ordinary diagram capability as the baseline and record that choice.

Before generation, record the model identifier and settings, date, full prompts,
skill commit and content hashes, renderer and speech-engine versions, voice/model,
tool versions, and unavailable capabilities. Fix the audience, requested duration
or page size, tool budget and rendering limits to explicit shared values for both
arms. Keep these conditions in a local run manifest. Record any unavoidable
difference and do not attribute its effect to the skill.

Give generators only `source`, `request`, the chosen artifact format and those
shared audience and budget constraints, together with their skill content. Expected
facts, answers and checks are evaluation data. Give an independent reader only
the finished artifact and questions, then compare their answers with the source
key. A reviewer with the source should separately audit factual support.

Do not use transcripts alone to score a video or textual graph definitions alone
to score a diagram. Inspect the rendered artifact. Record unsupported or unavailable
checks explicitly. Every critical source fact and question must pass, independent
of visual preference.

## Artifact checks

| Format | Observable checks |
|---|---|
| Diagram | Editable file opens; labels and arrowheads are readable; the direction and condition of each edge match the source; unknown edges remain unknown; text equivalent preserves the material relationships |
| Video | File decodes with audio; actual duration contains all narration; captions match and synchronize; each scene shows the mechanism being discussed; the final artifact answers the comprehension questions |
| Walkthrough | Baseline and changed-input results match independently calculated examples; invalid inputs are rejected; reset restores the baseline; previous/next and selection work; keyboard, narrow layout, reduced motion and static equivalent are usable |

For the retry fixture, the independent oracle at cap 16 is `[1, 2, 4, 8, 16, 16]`
for attempts 0 through 5. At cap 4 it is `[1, 2, 4, 4, 4, 4]`. A negative attempt
is invalid. The cap does not specify a stopping count. Keep these values out of
the generator prompt; they are the browser and media review checks.

## Feedback at each increment

- Writing: compare A/B explanations; ask which is easier to follow and whether a
  boundary condition is clear. Ask which phrase needs a definition.
- Video: show the rendered clip; ask which moment moved too quickly, whether the
  diagram follows the narration, and a question about the final mechanism.
- Diagram: show the preview and editable source; ask the reader to trace the
  success and failure paths and identify any ambiguous arrow or missing condition.
- Walkthrough: ask the reader to change one input, explain the resulting difference
  and return to baseline. Ask which interaction helped them understand the mechanism.

Bind feedback to the entire delivered bundle: enumerate every shipped file with
its relative POSIX path, byte length and SHA-256, sorted by path. Include the
rendered preview/video/HTML, editable sources, captions, transcript, static equivalent
and any local assets they load. Reject symlinks and paths outside the bundle; inline
or vendor remote assets so a later remote change cannot evade the manifest.
Serialize the manifest as a UTF-8 JSON array with sorted object keys, compact
separators and no trailing newline, then hash those bytes with SHA-256. Exclude
the manifest itself and feedback records to avoid a recursive hash. Store that
manifest, its hash and the user's actual feedback locally. Any changed, added or
removed delivered file needs a new manifest and feedback.
Feedback on a previous render does not approve a changed narration, diagram or interaction.
Record model-reader checks as model evaluations; they are not user feedback.
