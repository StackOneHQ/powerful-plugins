# Part 3: Line-level craft

Parts 1 and 2 delete. This part rewrites, and it runs on every sentence that survived them. It is where clean copy becomes readable copy, and it is the half that most tell-removal passes skip.

## C1: Say what it does, not how it feels

The most common residue after a tell-removal pass is a sentence that names a feeling instead of a mechanism.

| Names a feeling | Names the mechanism |
|---|---|
| the database stays close at hand | `.toSQL()` returns the exact string sent to the database |
| types that follow your schema | renaming a column fails the build |
| an experience developers love | two commands from clone to first passing test |
| enterprise-ready reliability | 99.95% over the last four quarters, measured per region |

Ask what the sentence tells the reader to do or know, then write that. If it cannot be restated as an instruction, a fact or a number, cut it.

**The portability test.** If the sentence could appear unchanged in a competitor's docs, it says nothing about this thing. Cut it, or make it specific. This one test catches more slop than any word list, because it fails a sentence for what it lacks rather than for which words it used.

## C2: One idea per sentence

If a reader has to backtrack to parse a sentence, split it or drop clauses. Two subordinate clauses is usually one too many.

- BAD: `Because the retry loop, which had no backoff and arrived in the release that also changed the login page, kept firing, the API rate-limited us for six hours.`
- GOOD: `The retry loop had no backoff, so it kept firing until the API rate-limited us for six hours. It arrived with the login page redesign.`

This is rhythm variance (Part 7) approached from the other end. Splitting the long sentences is what produces the short ones.

## C3: Active voice, and name the actor

Catch "is/are/was/were + past participle" and say who did it.

- `queries are validated` becomes `the compiler validates queries`
- `the file is parsed by the loader` becomes `the loader parses the file`
- `it was decided that` becomes `we decided to`, or name who decided

Passive is fine when the actor is genuinely unknown or irrelevant: `the record was created in 2019`. It is not fine when it hides who is accountable, which is most of the occasions it shows up in generated text.

## C4: Cut the adverb, or fix the verb

An adverb propping up a weak verb means the verb is wrong.

- `runs quickly` becomes `is fast`, or better, the number
- `significantly improves` becomes the measured delta
- `very large` becomes the size
- `essentially`, `basically`, `simply`, `just`, `actually`, `really`, `quite`, `fairly`: delete, then reread. The meaning is almost always unchanged and the tone is better.

`simply` and `just` do a specific kind of damage in documentation. They tell a reader who is already stuck that their problem was supposed to be easy.

## C5: Hedge once, and hedge specifically

Stacked modals are a tell: "could potentially possibly be argued that it might". Collapse to one: "may".

This does not contradict the admitted uncertainty in Part 7. What matters is where the hedge attaches. A vague hedge on a whole claim is caution with nothing behind it. A specific hedge that names its own limit is credibility.

- BAD: `This could potentially be a significant factor for some organizations.`
- GOOD: `This cut our p95 by half. I have only tested it on the two services that share a database, so I do not know whether it holds for the ones with their own.`

One hedge, one scope, one sentence, then move on.

## C6: Borrowed idiom test

An idiom or slang term stays only if the author already uses it. One reached for because it sounds punchy ("knife fight", "in a suit", "table stakes") reads as a costume, and the reader can tell the difference between a phrase someone says and a phrase someone selected. If you cannot point at the author using it in their own words, cut it and say the plain thing. A reader asking "what does knife fight even mean here?" is the failure this test prevents.
