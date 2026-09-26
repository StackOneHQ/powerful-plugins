# Part 7: The generative half, what to add

Parts 1 to 6 are entirely prohibitive. Copy that passes them is clean and can still be worthless: strip the tells and you often strip the fingerprint with them, leaving prose that offends nobody and interests nobody. Social feeds increasingly rank generic, perspective-free posts lower, so blandness costs reach as well as reader attention.

For substantial authored articles and social posts, use a second gate: does the
piece contain a supported perspective or useful detail specific to this author?
For functional or short text, accuracy, clarity and the requested purpose define
completion; use the format guidance above.

## The four things to add

1. **Concreteness.** Exact numbers, including odd non-round ones. Named people, named companies, named repos, version numbers, exact dates, real URLs. Concreteness of named entities is the most cited discriminator of human text in the 2024 to 2026 detection literature, and it is the cheapest to supply because the facts are already yours. "We cut latency significantly" is slop. "p95 went from 1.9s to 340ms after we stopped loading the full order history on every page view" is not.

2. **A stated position with admitted uncertainty.** A neutral-positive register held from first line to last is itself a tell. Take a side, then say where you are unsure, in the same piece. "I think X is wrong, though I have only seen this in two of our apps" reads human in a way that no amount of vocabulary policing can fake.

3. **Rhythm variance.** Vary sentence length, paragraph length and sentence openers deliberately. Uniform block rhythm is a top-three tell in expert-annotator studies. Rough quantified check: burstiness, the standard deviation of sentence length divided by the mean, should sit above roughly 0.4. Human prose runs bursty, short sentences next to long ones; AI output tends to sit below 0.4, with every sentence close to the same length. Include at least one paragraph noticeably shorter than the rest and one that runs long. Do not open three consecutive paragraphs with the same construction, and do not open more than half your paragraphs with a transition word (moreover, furthermore, additionally, notably, ultimately, subsequently, conversely).

4. **One unpolished human artefact.** Something no template produces: a self-undercutting parenthetical, an aside that admits the analogy is imperfect, a piece of chat shorthand, a blunt one-sentence verdict, a coinage invented for this specific subject. Exactly one is enough. This is the highest-signal item on the list.

## The two additions that decide whether it travels

5. **Audience transfer.** At least one sentence whose grammatical subject is the reader or the reader's category, saying what they should do, stop doing, or expect. Company-centric "we" messaging is the one pronoun pattern with a measured negative effect on engagement. Note the fix is not blanket "you", which tests null to negative in the largest datasets: the fix is that the reader's decision is the subject and your experience is the evidence underneath it.

6. **A reusable artefact.** A number, a threshold, a named failure mode, a checklist, a decision table, or a two-word name for a thing. Practical utility is one of the strongest replicated drivers of sharing (Berger & Milkman 2012, +30% per standard deviation, level with awe). Naming it in two words is what lets it travel without you.

## Three habits that produce the six

The list above says what a draft needs. These are the moves that put it there.

- **React, do not enumerate.** A balanced list of pros and cons is the default output of a model with no stake in the answer. Say which one you think is right and why. "Impressive, and also faintly alarming" carries more than "impressive" because it admits two things at once, and a model averaging its training data does not hold contradictions.
- **Use "I" where the view is yours.** First person is not unprofessional, and hiding a personal judgement behind "organizations should" is the tell. Own the claim or cut it.
- **Let a little mess through.** Perfect structure reads machine-made. A section that runs short because there was nothing more to say, a sentence that starts with "and", a parenthetical that undercuts the paragraph above it: these cost nothing and they are unfakeable in aggregate.

## Two shapes to prefer

- **The negative result.** "What did not work", "X is still hard", "we tried Y and it lost to Z". Factual, unfakeable, costly to publish, and therefore high trust. Rarely published in B2B, which is exactly why it travels.
- **The named technique.** "One pattern I find useful for X is Y." The payload is Y; the first person functions only as the credential that earned it, and the subject moves to the reader within a sentence or two.

## Generative gate, run after the Final gate

1. Could any sentence here have been written by someone who does not do this work? If that is true of every sentence, the draft has no author.
2. Is there at least one exact number, name or date that a reader could go and check?
3. Is there a stated position, and is there an admitted limit on it?
4. Do the paragraphs vary in length, and do they start differently?
5. Is there exactly one unpolished human artefact?
6. Is there one sentence whose subject is the reader, and one reusable artefact they could re-open later?

Repair failures on applicable checks using available source material. Do not add
unsupported facts or a manufactured personality to obtain six yes answers. If
essential author material is missing for the requested piece, identify that gap;
otherwise return the useful text without forcing inapplicable additions.
