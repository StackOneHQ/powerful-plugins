---
name: natural-writing
description: Write like a human, not an LLM. Auto-triggers when writing or editing documentation, copy, marketing content, social posts, emails, READMEs, blog posts, commit messages, or explanatory text. Bans em dashes and curly quotes outright, bans LLM word choices, bans the sentence SHAPES that survive word-level filters, and adds a line-level craft pass for active voice, concreteness and rhythm. Has a slot for your own banned house terms. Ships scripts/check-copy.sh so any workflow can gate on the mechanical rules. Use /natural-writing:review-copy to audit text already written.
invoke: natural-writing
---

# Natural Writing

Write like a human, not an LLM. Word-level bans are the easy half. The patterns that actually give away AI writing are *shapes*: sentence skeletons that stay recognisable no matter which nouns you drop into them. This skill bans both, adds the line-level rewrite pass that has to follow, and gives you a mechanical check you can run.

This applies to editing as much as to drafting. If text passes through you, it gets the pass, including text you did not write.

## Auto-trigger conditions

Activate when:
- Writing documentation, copy, marketing content, social posts, or explanatory text
- Drafting emails, messages, or communications
- Creating README files, blog posts, or announcements
- Writing commit messages, pull request descriptions, or code comments
- Writing any text that goes inside an asset: SVG diagram labels and titles, chart axis and series names, figure captions, hero and banner copy, slide text, video captions, screenshot annotations, UI copy authored for a mockup
- Editing, cleaning up, or reviewing text that already exists, whoever wrote it
- User asks to "write", "draft", "create copy", "explain", "tighten", or "clean up"

Asset text is the easiest place for these tells to survive, because a label is never read the way a paragraph is. A figure can pass more than one design review with em dashes still in its section labels. If words are going into a picture, they get the same pass as prose, and the grep block in Part 4 runs against the asset source file.

## Match the checks to the format

Apply the mechanical rules and relevant clarity checks to every format, including
asset text. The essay and social-post requirements in the Final gate and Part 7
are not a template for labels, buttons, headings, short replies, factual updates
or reference documentation. Mark checks that do not fit the requested format
as not applicable; a concise label does not need a personal opinion, a number,
an aside, varied paragraphs or a reusable framework.

Preserve the requested meaning, length and purpose. Use only supported facts and
the author's supplied perspective. Never invent a metric, named example, personal
experience or opinion to pass a writing check. If the text already does its job,
leave it concise rather than adding material to make it seem more distinctive.

## Working order

1. Draft or read the text.
2. Apply Part 1 (mechanical rules) and Part 2 (sentence shapes) to remove tells.
3. Apply Part 3 (line-level craft) to every sentence that survived.
4. Run Part 4: `${CLAUDE_PLUGIN_ROOT}/scripts/check-copy.sh`, or the grep block it wraps. A non-zero exit blocks delivery.
5. Apply the Part 7 checks that fit the format and available author material.
6. Ask yourself once, plainly: what in this still reads as machine-written? Fix that, then ship.

Steps 2 and 5 both require consideration. Removing tells alone does not make a
substantial article useful; adding essay features does not make a short label better.

---

# PART 1: Hard mechanical rules

These are absolute. No exercise of judgement, no per-document allowance.

## Rule 1: Em dashes are banned. Zero. Always.

The em dash (Unicode U+2014) must never appear in anything you write. Same for the en dash (U+2013) used as punctuation between clauses. This document deliberately never types either character, so that nothing here can be copied as a model: refer to them by code point, and match them with `grep -oP '[\x{2014}\x{2013}]'`. There is no allowance, no "max 2 per document", no exception for asides, no exception for dramatic pauses.

Replace with one of these, in order of preference:

| Em dash was doing | Use instead | Example |
|---|---|---|
| Introducing an explanation or list | colon `:` | `We fixed the cause: the retry loop never backed off.` |
| Setting off an aside | comma pair | `The retry loop, which never backed off, hammered the API.` |
| Dramatic pause before a payoff | full stop, new sentence | `The retry loop never backed off. The API rate-limited us for six hours.` |
| Joining two related clauses | `,` plus a conjunction, or `;` | `The upload worked, but the thumbnail step did not.` |
| Numeric range | `to` | `10 to 20 minutes` |

The best option is often none of the above: rewrite so no dash is wanted. If you reach for a dash, the sentence is usually carrying two ideas and wants to be two sentences.

**Do not trade the dash for a parenthesis.** Swapping every banned dash for a parenthetical trades one tell for another, and a draft with an aside in every paragraph reads exactly like a dash-heavy draft that went through a find and replace. See Rule 5 for the parenthesis budget.

**Hyphens in compound words are fine** (`per-user`, `first-party`, `24-hour`). This rule is only about dashes used as punctuation between clauses.

## Rule 2: Banned words

**Verbs:** delve, embark, harness, unleash, unlock, navigate (figurative), leverage, foster, cultivate, underscore, showcase, highlight, accentuate, illuminate, elucidate, unpack, unravel, spearhead, pioneer, trailblaze, revolutionize, transform, empower, supercharge, turbocharge, skyrocket

**Arrival and movement metaphors.** Never use these for a decision, a conclusion, a number, or an outcome:
land, landed, lands, landing, "landed on", "where X lands", converge, converged on, coalesce around, "arrived at", "settled on", gravitate toward, "found their way to", drop / dropped (for a release or a number), "hit" (for a number)

Plain replacements: picked, chose, used, adopted, published, agreed, released, reached, was.

- BAD: `Three bakeries landed on the same answer this year.`
- BAD: `The three bakeries in town all landed on the same flour mill.`
- GOOD: `The three bakeries in town all picked Hillside Mill as their flour supplier this year.`

These read as a tell because they dress a boring fact (three bakeries chose a supplier) as a journey. Humans just say who chose what.

**Adjectives:** pivotal, crucial, paramount, vital, robust, seamless, holistic, comprehensive, cutting-edge, groundbreaking, game-changing, innovative, transformative, unparalleled, meticulous, intricate, nuanced, multifaceted, vibrant, dynamic, synergistic, scalable, streamlined, production-ready, battle-tested, enterprise-grade, world-class, best-in-class, state-of-the-art

**Nouns:** tapestry, landscape, realm, paradigm, ecosystem, synergy, testament, cornerstone, catalyst, linchpin, bedrock, nexus, crucible, odyssey, journey (figurative)

**Copula-avoidance verbs.** LLMs dress up a plain "is" or "has" as a fancier verb because the training data rewards it: serves as, stands as, functions as, represents, boasts, features, offers, exemplifies, epitomizes. The inflated verb is the tell precisely because the sentence needed nothing but "is" or "has".

- BAD: `The depot serves as the hub between the warehouse and the delivery vans.`
- GOOD: `The depot is the hub between the warehouse and the delivery vans.`
- BAD: `The new pipeline boasts a 40% faster build time.`
- GOOD: `The new pipeline cut build time by 40%.`

**Digestion and erasure metaphors.** A vivid ingestion or destruction verb applied to an abstract noun acting on another abstract noun: swallow(s), consume(s), erase(s), bury/buries/buried, drown(s) out, dissolve(s), evaporate(s), drain(s). Nothing is literally swallowing or drowning anything, the sentence just wants a dramatic verb standing in for "reduces" or "hides", and no engineer talks this way out loud.

- BAD: `Scale swallows the nuance that made the pilot work.`
- GOOD: `The nuance that made the pilot work does not hold at scale.`
- BAD: `Complexity buries the actual benefit.`
- GOOD: `The extra configuration steps hide the actual benefit.`
- BAD: `Growth erases the margin.`
- GOOD: `Margin drops as customer count grows, because support cost per account does not.`

**Abstract metaphor nouns.** Words that read as technical but stand in for a plainer, concrete one: substrate, wedge, vector, locus, vantage, primitive (as a noun), harness (as a metaphor), surface (as in "API surface"), scaffolding (as a metaphor), modality, gold-plating, ratchet (as a metaphor), evacuate (for moving code), endgame, north star, flywheel. Plus nexus, bedrock and paradigm from the noun list above.

| Instead of | Write |
|---|---|
| substrate | base, or the actual layer's name |
| wedge in | add |
| vector | way, method, route |
| primitive | building block, or the actual type name |
| gold-plating | more than the job needs |
| ratchet | the mechanism's real name, or "a limit that only tightens" |
| evacuate the logic | move the logic out |
| endgame | the last phase |
| north star | the target number |
| flywheel | the loop that feeds itself, spelled out |

The test is whether the concrete word loses anything. It almost never does.

**Inflated synonyms.** utilize, leverage, facilitate, numerous, commence, endeavour, ascertain, garner, enhance, "in the event that", "prior to", "subsequent to". Use instead: use, use, help, many, start, try, find out, get, improve, if, before, after. The fancier synonym is almost never the clearer one.

**Puffery and brochure adjectives.** nestled, vibrant, breathtaking, stunning, renowned, iconic, must-visit, bustling, picturesque, "hidden gem", "rich history", "deeply rooted", "enduring legacy", "indelible mark", "evolving landscape", "pivotal moment", "setting the stage for". These reached AI output through listicle and tourism copy, and none of them survives contact with a technical reader. Give a fact where the adjective wanted to go.

- BAD: `Acme's renowned recipe library covers a vibrant world of home baking.`
- GOOD: `Acme has 600 tested recipes, including 40 sourdough breads.`

## Rule 3: Banned phrases

- "It's important to note that" / "It's worth mentioning" / "It's worth noting"
- "In today's fast-paced world" / "In today's landscape" / "gone are the days"
- "At its core" / "At the heart of" / "When it comes to" / "At the end of the day"
- "Let's dive in" / "Without further ado" / "In summary" / "In conclusion"
- "Under the hood" (say what it does) / "Out of the box" (say "pre-built" or "with no config")
- "Here's the thing" / "here's the kicker" / "here's the uncomfortable part" / "the part nobody talks about" / "the part that stuck with me" / "the dirty secret" / "but here's the catch" / "The catch:"
- **Reflective hand-holding:** "the part I keep coming back to", "the part that gets me" / "got me", "what struck me", "what stuck with me", "the interesting thing is", "what I find fascinating", and any sentence that announces a feeling before it delivers the point. Nobody who does the work types these. State the point.
- "X is the wrong question" / "the real question is" / "the question isn't X, it's Y" / "ask yourself"
- "the blast radius" / "the lesson held" / "let that sink in" / "make no mistake"
- "Turns out" as a paragraph opener
- "Which means" / "Which makes me wonder" as a standalone sentence opener
- "Here's why." / "Here's why both approaches don't work:" as a standalone pivot line
- "I'll just say it:" as an opener
- "Enables you to" (say what it does)
- Abstract capability nouns standing in for what the product actually does: "a unified layer", "an end-to-end solution", "a single pane of glass". Name the behaviour instead
- **Fake-authority phrases:** "studies have shown", "research indicates", "research shows", "experts agree", "data suggests", with no citation attached. Name the actual source, or drop the claim of one.
- **Transition-word stacking:** "Moreover", "Furthermore", "Additionally", "Notably", "Ultimately", "Subsequently", "Conversely" as the first word of a paragraph. One is unremarkable. More than half your paragraphs opening on one of these is a mechanical tell, not a style (see Part 4).
- **Assistant tics:** anything that reads as a chat reply rather than a piece of writing. "I hope this helps", "Let me know if you have any questions", "Of course!", "Certainly!", "Great question", "You're absolutely right", "Happy to help", and standalone "Perfect!" or "Found it!" lines. Delete on sight, including in commit messages, pull request descriptions and code comments.
- **Knowledge-limit disclaimers:** "While specific details are limited", "based on available information", "as of my last update", "it is unclear from the sources". Go and find the fact, or drop the claim that needed it. Never publish the apology for not having it.
- **Filler connectives:** "in order to" (use "to"), "due to the fact that" (use "because"), "for the purpose of" (use "to"), "in the process of" (delete), "it should be noted that" (delete), "there is a X that" (name the subject and give it the verb). Each of these survives deletion with no loss of meaning, which is the definition of filler.

## Rule 4: Cap on prescribed vocabulary

Any word a voice guide recommends becomes its own tell once it appears in every piece. Cap at **one per document**. Typical offenders are knowing, understated words such as boring, underrated or unsexy. `${CLAUDE_PLUGIN_ROOT}/scripts/check-copy.sh` counts a short starter list; replace it with your own voice guide's favourites. Never two of them in the same piece. If the last thing you wrote used "boring", this one does not.

## Rule 5: Typography and formatting

Mechanical, greppable, and they leak the source as reliably as vocabulary does.

**Straight quotes only.** Curly quotation marks and curly apostrophes (U+2018, U+2019, U+201C, U+201D) are banned in prose and in code alike. A word processor produces them, a person typing in an editor does not. This document deliberately never types them: match them with `grep -nP '[\x{2018}\x{2019}\x{201C}\x{201D}]'`. Same rule, same reason, as the dash rule.

**Sentence case headings.** "Rate limits and retries", not "Rate Limits And Retries". Title case in body headings is a house style that almost nobody keeps consistently by hand, so perfect title case across twelve headings reads as generated.

**No decorative emoji.** None in headings, none as bullet markers, none as section dividers, none as a checkmark on a status line, and none at all in documentation, blog posts, changelogs, emails, PR bodies or commit messages. That includes an emoji inside quoted chat text: the check cannot tell a quote from your own words and fails it, so describe the reaction in words instead.

**Social posts get one channel clause, not an exemption.** A single emoji at the end of a line in a LinkedIn or X post, doing the job a tone-of-voice cue does in speech, is the author's register and not decoration. The limits are mechanical: never in the first line, one per line (a line carrying two emoji separated by text fails), at most four per post, adjacent pairs only as a deliberate sign-off and at most once, never as a bullet marker. End of line is the norm; the script reports a mid-line emoji for a look rather than failing it, because some authors do put one mid-clause as a tone cue and that is their register. Check the author's own recent posts before deciding: if they carry one to four such emoji and no decorative ones, a draft with none reads flatter than they do, and a draft with a row of them reads like a template. `check-copy.sh --channel social` enforces the clause; every other channel keeps the zero rule.

**Bold has a budget.** Bold the term the reader will search for, once, where it is defined. Do not bold every proper noun, every acronym, or the opening words of every bullet. If more than roughly one line in ten carries bold, the emphasis has stopped meaning anything.

**Colons join a sentence to a list or an example, not two clauses of argument.** Rule 1 sends the dash's work to a colon, and that is right for `We fixed the cause: the retry loop never backed off.` It is not a licence for the comparison-framing colon: `If you are coming from traditional automation: instead of registering handlers, you describe conditions.` That colon carries no load. Drop the framing clause and state the point on its own.

**Parenthesis budget.** At most one parenthetical aside every few paragraphs. Past that, end the sentence instead. An aside in every paragraph is the signature of dash removal rather than of rewriting.

## Rule 6: House terms (add your own)

Most teams have words that are wrong for them in particular: a competitor's category name, a retired product name, a description of the product that the team rejects. This rule is the slot for that list. It ships empty, so nothing is banned under it until you add terms.

Keep two files, one case-insensitive pattern per line, `#` for comments:

- **Hard bans**, wrong in any context. Pass with `check-copy.sh --banned-terms FILE` or set `COPY_BANNED_TERMS`. Any match fails the check.
- **Soft terms**, ordinary words that are only wrong when they describe your own product. Pass with `--soft-terms FILE` or set `COPY_SOFT_TERMS`. The script prints matches for you to judge.

`--allow-house-terms` turns the hard check off for every file in that run, not only inside quotation marks. Use it only for a piece that quotes the title of an already-published page or is about the term itself, and before you do, confirm by eye that every match sits inside quotation marks.

Neutral example, for a team that sells a scheduling API and does not want it filed as a consumer calendar:

```
# house-terms.txt: hard bans
calendar app
booking widget
all-in-one scheduling

# house-soft-terms.txt: flag for review
calendar
```

"Calendar" stays soft because `calendar sync` is a real feature; it is only wrong as the name for the whole product. Next to each list, write what to say instead ("scheduling API", "availability endpoint", "booking flow"). A ban with no replacement sends the writer to the nearest vague synonym. If you keep a longer voice guide with boilerplates and a say-this-not-that table, link it here so it gets read before drafting.

---

# PART 2: Banned sentence shapes

This is the part word filters miss. Each shape below was caught in real generated output. Ban the skeleton, not the wording, because the wording changes every time and the skeleton does not.

## S1: Negation opener followed by a short arrival fragment

Skeleton: `Nobody <verb>ed X.` then `<Number or group> landed on Y.`

Also: "No one built", "Nobody asked for", "Nobody invented", "Nobody owns", "the half nobody owns", "Nobody talks about".

- BAD:
  ```
  Nobody invented a new ticket format for regional trains.

  Three operators landed on the same answer this year.
  ```
- GOOD: `Northline, Coastway and Valley Rail all picked the same barcode ticket format this year. It is the format their shared ticket machines already print, so the station gates only needed a software update.`

Why it fails: the first sentence exists only to create suspense and carries no information. A human leads with the fact. The negation-then-reveal pair is the most recognisable AI opener in circulation.

**Test:** delete your first sentence. If the piece is still complete and now starts on a fact, that sentence was suspense scaffolding. Leave it deleted.

## S2: Correction pair (the reframe in disguise)

Skeletons, all banned:
- `X did not A. It did B.`
- `X never A'd. They A'd B.`
- `A tells you X. It says nothing about Y.`
- `Not A. B.`
- `It's not X, it's Y.`
- `X is not the problem. Y is.`

- BAD: `The train was never late because of the signals. It was late because of the crew change.`
- GOOD: `The train was late because of the crew change, not the signals.`
- BAD: `Your delivery log names the depot. Not a driver. The depot.`
- GOOD: `Your delivery log names the depot rather than the driver, so you cannot tell which of its forty drivers left the parcel.`

Why it fails: it spends two sentences and a rhetorical swerve to deliver one fact. Say the fact once, with the contrast as a subordinate clause.

**Note for reviewers:** an earlier version of this skill banned only the literal string "it's not X, it's Y". Every example above got through that filter. Match the shape, not the words.

## S3: Aphorism used to cap a paragraph

A short, symmetrical, quotable general truth placed at the end of a beat.

Sub-forms: `You can't X what you can't Y.` / `X is where Y lives.` / `That's X in N words.` / `The second N is the harder half.`

- BAD: `You cannot approve what you cannot name.`
- BAD: `That distance is where the incidents live.`
- BAD: `That is the staffing problem in two lines.`
- GOOD: delete the line. The facts above it already made the point.

Why it fails: nobody writes proverbs into a work post. It reads as a fortune cookie glued onto real content. If the preceding facts do not make the point, fix the facts.

## S4: Self-commentary on the text's own structure

Never describe your own paragraph count, halves, parts, or lines.

- BAD: `That is the staffing problem in two lines.` / `The second line is the harder half.` / `This part is housekeeping.` / `More on that below.`
- GOOD: just continue.

## S5: Stat, stat, aphorism

Skeleton: two juxtaposed percentages with no connective, then a short interpretive fragment.

- BAD:
  ```
  80% of our customers say they read the allergen labels. 15% could name the allergens in the loaf they had just bought.

  That distance is where the complaints live.
  ```
- GOOD: `80% of our customers say they read the allergen labels, but only 15% could name the allergens in the loaf they had just bought.`

One sentence. State the contrast with a conjunction and let the numbers do the work. No interpretive fragment after.

## S6: Fragment stacking

Two or more consecutive sentence fragments used for percussive effect.

- BAD: `Not a driver. The depot.` / `The reason is boring.` / `Dead before it does anything useful.`

**Budget: at most one fragment per piece of copy, and never two in a row.** A single fragment can carry a point. Three in a row is a drum solo, and it is the rhythm every LLM defaults to.

If a voice guide says "fragments are fine for punch" or "he stacks short sentences for effect", that guidance is capped by this rule. One. Not a pattern.

## S7: Tricolons and staccato parallels

- BAD: `The oven is old. Deliveries run late. The rota is short.`
- GOOD: `The oven is old and deliveries run late, and the rota is always short.`
- BAD: `The app can plan routes. It can track parcels. It can reschedule deliveries.`
- GOOD: `The app plans routes and tracks parcels well enough to reschedule a missed delivery on its own.`

Three parallel items in a row is a rhetorical figure, not a sentence. Two is fine. Four or more is a list, so format it as one.

## S8: Rhetorical questions as hooks and closers

- BAD (closer): `If you run a delivery fleet, can your records say which driver left each parcel?`
- BAD (closer): `What does your stock sheet actually show when a shop sells its last loaf?`
- BAD (hook): `What if I tell you that your weather app is guessing?`
- BAD (hook): `So what's really eating up your "grocery budget"?`
- BAD (question answered by its own fragment): `Did the finance team just accept the new expense rules? No.`

A closing question is allowed **at most once across a batch of variants**, and only when it is a question the author would genuinely ask a specific person. It must never be the default ending. Do not append a question to every post because a voice guide says questions drive engagement. If two variants both end on a question, a formula wrote both.

A question as the *opening* line is banned outright. Open on the fact the question was hinting at.

Never ask a question and then answer it yourself in the next fragment. That is a two-line way of stating one thing.

Better endings: a concrete next step, a specific claim someone could argue with, or simply the last fact.

## S9: Colon-fragment label

- BAD: `The result: fewer retries.` / `The problem: nobody owns it.` / `The catch: it only works for reads.`
- GOOD: `That cut retries by half.` / `It only works for reads.`

A noun, a colon, a fragment. Reads like a slide deck. (Note: colons inside a normal sentence are encouraged, see Rule 1. This bans the standalone label form.)

## S10: Escalation ladder

Skeleton: three or more clauses of increasing intensity, each shorter than the last, building to a one-word beat.

- BAD: `It slowed down. Then it stalled. Then nothing.`
- GOOD: `It slowed, then stalled, and stopped responding after about four minutes.`

## S11: Hollow contrast and product reveals

- BAD: `It's not just X, it's Y.` / `Enter Acme.` / `Think again.` / `And that changes everything.`
- GOOD: state what the thing does.

## S12: "This is why we built X" pivot

Skeleton: `This [exact] <noun> is why we built <product>, to <generic capability phrase>.`

Three variants of the same skeleton:
- BAD: `This is the exact reason we started Acme, to give teams a single workspace that handles notes and task tracking.`
- BAD: `This exact visibility is why we built Acme to act as a single source of truth for your team.`
- BAD: `This exact balance is why we built Acme. We give your team the single workspace they need.`
- GOOD: `We built Acme so a meeting note becomes a list of assigned tasks in one keystroke.`

Two failures at once. The pivot phrase is a template, and the payload after it is an abstract capability noun ("single source of truth") instead of a thing the product does. Name the specific behaviour. Never reuse the same pivot sentence across variants or across weeks.

## S13: Recycled or unverifiable anecdote opener

Skeleton: `I [recently] spoke with / chatted with a <C-level title> who <did a vivid thing>.`

- BAD: `I chatted with an enterprise CFO who mapped his department's total addressable market by...`
- BAD: `I recently spoke with a CFO at a large retailer who had been actively fighting with his own finance team.`
- BAD: `A CFO I spoke to recently proved this.`

In one batch of drafts, several posts opened this way, and some of them retold the same underlying anecdote in different words. Rules:
- Do not open with "I spoke with a <title>" more than once in any rolling batch.
- Check what you have already published before using an anecdote. A story reused across two posts reads as invented even when it is true.
- If the anecdote is the point, name what actually happened first and attribute it second.

## S14: Bare stat dump

Skeleton: a bulleted run of numbers with no sentence around them.

- BAD:
  ```
  • 500 parcels sorted per hour, up from 200
  • 2 staff per shift, down from 5
  ```
- GOOD: `The new sorting belt handles 500 parcels an hour, up from 200, with two staff per shift instead of five.`

Numbers need a claim attached. A bullet list of figures makes the reader do the interpreting, which is the writer's job.

## S15: Two-sentence twist cold open

Skeleton: a flat factual sentence, full stop, then a very short reversal that supplies the punch.

- BAD:
  ```
  We borrowed another shop's till software last month. It did nothing.
  A courier moved one parcel. Nobody logged it.
  The prototype works. The rollout doesn't.
  OpenAI told a model to solve a security test. It stole the answers instead.
  ```
- GOOD: `We borrowed another shop's till software last month and it never took a payment, because it had no card reader driver, no tax rates and no product list.`

This is the single most common opener in generated copy: in one batch of drafts, it opened close to half of them. One instance reads as voice. Half a batch reads as a template. The fix is to merge the two sentences so the consequence rides on the fact, or to open on the specific detail rather than the setup. It is a close relative of S1 and S3, and the same test applies: if the first sentence exists only to make the second one land, you have written a formula.

## S16: Fixed closing furniture

Skeleton: every piece in a batch ends with the same apparatus. The same four hashtags. The same product pivot. The same shape of question.

In one batch of drafts, every post carried the same hashtag set, most of the pages ended on a "we built X for this" pivot, and every post closed on a question. Individually each is defensible. Repeated across every post they are a signature, and readers who see two of your posts read the signature before they read the content.

- Hashtags: pick from the actual subject matter, rotate them, or ship none.
- Product pivot: at most one per batch, and check the last four weeks before reusing the phrasing.
- Closing question: see S8. Not mandatory, one per batch at most.

## S17: Boundary-line metaphor

Skeleton: `<Abstract noun> is the line between <A> and <B>.` / `That's the line.` / `X walks the line between A and B.` / `where the line sits` / `crossing the line`.

Readers flag "is the line" as a phrase nobody says out loud.

- BAD: `Compliance is the line between shipping fast and shipping recklessly.`
- BAD: `That's the line most teams don't want to admit they've crossed.`
- BAD: `The real skill is knowing where the line sits.`
- GOOD: `Ship fast, but get a security review before anything touches customer data.`
- GOOD: `Most teams skip the security review to hit the deadline, then find out why it mattered.`

Why it fails: "the line" turns a concrete tradeoff or threshold into a vague spatial metaphor that sounds profound and says nothing measurable. State the actual threshold, the actual rule, or the actual consequence instead of gesturing at a line.

## S18: Trailing participial clause that explains the sentence to the reader

Skeleton: a complete factual sentence, comma, then a present participle telling the reader what the fact means.

Tells: `, highlighting the need for...`, `, ensuring that...`, `, reflecting a broader shift toward...`, `, showcasing...`, `, fostering...`, `, underscoring...`, `, demonstrating...`, `, allowing teams to...`, `, making it easier to...`, `, further cementing...`, `, positioning us to...`

- BAD: `The uploader now retries on 429, ensuring reliable delivery for large files.`
- GOOD: `The uploader now retries on 429 with exponential backoff, up to five attempts over two minutes.`
- BAD: `Three of our largest customers moved to annual billing this quarter, reflecting a broader shift.`
- GOOD: `Three of our largest customers moved to annual billing this quarter, in May, June and July, each after a price review.`

Why it fails: the clause is never a fact. It is the model marking its own homework, either asserting an unfalsifiable benefit or restating the sentence in vaguer words. It also arrives at a predictable position in a predictable rhythm, which is why it survives every word-level filter.

**Test:** delete everything after the comma. If nothing verifiable was lost, leave it deleted. If the meaning genuinely needs saying, give it its own sentence with a number in it.

## S19: Label-colon bullet that restates itself

Skeleton: `**<Noun>:** <the same noun, re-verbed>`

- BAD: `**Performance:** Performance improved across the board.`
- BAD: `**Security:** Security is handled at the server.`
- GOOD: `Median response time fell from 1.9s to 340ms.`
- GOOD: `Every request needs a signed session cookie, and a session expires after 30 idle minutes.`

Not every bold lead-in is this pattern. A lead-in that names the item, ends in a full stop, and is followed by genuinely new detail is fine: `**Schema in TypeScript.** Every table lives in one file, and renaming a column fails the build.` The tell is the colon plus the restatement, so the fix is to keep the detail and drop the label.

Where a whole document is label-colon bullets, the fix is prose. Six labels in a row is an outline that nobody wrote up.

## S20: The despite-challenges arc

Skeleton: `Despite <unnamed challenges>, <subject> continues to <thrive / grow / lead>.`

Also: `While challenges remain, ...`, `Not without its hurdles, ...`, `The road ahead is not without obstacles.`

- BAD: `Despite ongoing supply challenges, the bakery continues to grow.`
- GOOD: `The bakery grew last year, and the two complaints regulars made most at the counter were the 8am queue and sourdough selling out by noon.`

Why it fails: the shape has a slot for any subject and no obligation to name a single challenge, so it can be generated with zero knowledge of the topic. Name the actual obstacle and what happened to it, or cut the sentence.

## S21: False range

Skeleton: `from <A> to <B>`, where A and B are not endpoints of any real scale.

- BAD: `from breakfast to dinner to dessert` (three examples, not a spectrum)
- BAD: `everything from sign-up to cancellation` (filler for "account things")
- GOOD: `breakfast, dinner and dessert`
- GOOD: `bread, pastry and cake recipes, 600 in total`

Keep "from X to Y" for real ranges: `from 200ms to 2s`, `from 2019 to 2024`, `from staging to production`. Everywhere else it is a list in costume, and it usually smuggles in a rule of three at the same time (S7).

## S22: Synonym cycling

Three names for one thing inside a paragraph, because repeating a word felt inelegant: the importer, the sync, the loader, the pipeline. Or: the user, the customer, the end user, the practitioner.

- BAD: `The importer reads the file. The sync then maps the columns, and the loader writes the rows.`
- GOOD: `The importer reads the file, maps the columns and writes the rows.`

Pick one term and repeat it. In technical writing repetition is a feature: a reader who meets three words assumes there are three things, and then has to prove to themselves that there are not. Elegant variation is a strong tell because a human author gets bored and shortens rather than reaching for a thesaurus.

## S23: Name-dropping without content

Skeleton: a list of recognisable names used as evidence, with nothing any of them said or did.

- BAD: `Covered by TechCrunch, The Verge and Forbes, the launch drew broad attention.`
- BAD: `Companies like Stripe, Ramp and Figma face this problem.`
- GOOD: `Gadget Weekly's review said the notes app lost edits made offline, which is also the complaint our support team hears most.`

One name plus what it actually said beats five names plus an adjective. "Companies like X, Y and Z" is the same shape and is usually a guess dressed as research: if you have not verified all three, name the one you have.

---

# PART 3: Line-level craft

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

---

# PART 4: Mechanical check

Run this before delivering. It does not replace reading the copy, but it catches the mechanical rules with no judgement required.

The runnable form is `scripts/check-copy.sh` in this plugin: `check-copy.sh [--channel prose|social] [--banned-terms FILE] [--soft-terms FILE] [--allow-house-terms] <file>...`. It exits 1 when a hard check fails (dashes, curly quotes, emoji per the channel policy, house terms when configured, negation openers, the boundary-line metaphor, reflective hand-holding, assistant tics) and exits 2 when the host has no `grep -P` or no UTF-8 locale, when an input is not a regular file, or when grep itself errors, so a missing dependency can never read as a pass. The informational checks print without failing. Workflows and other skills should call the script rather than paste this block; use `${CLAUDE_PLUGIN_ROOT}/scripts/check-copy.sh` when that variable is set, or locate it with `find "$HOME/.claude" "$HOME/.codex" -path '*natural-writing*/scripts/check-copy.sh' 2>/dev/null | head -1`. The block below is what it checks.

```bash
# Save the draft to a file first, then:
f=draft.txt

# grep -P needs a UTF-8 locale to accept \x{2014} style code points. Without
# this line the dash, curly quote and emoji checks error out and print nothing,
# which reads as a pass and is worse than not running them at all.
export LC_ALL=C.UTF-8

echo "--- em/en dashes (must be 0) ---"
grep -oP '[\x{2014}\x{2013}]' "$f" | wc -l
grep -nP '[\x{2014}\x{2013}]' "$f"

echo "--- arrival metaphors ---"
grep -nPi '\b(land(ed|s|ing)?|converg(e|es|ed|ing)|coalesc(e|es|ed|ing)|arriv(e|ed|es) at|settl(e|ed|es) on|gravitat(e|ed|es) toward)\b' "$f"

echo "--- negation openers ---"
grep -nPi '\b(nobody|no one) (asked|invented|built|owns|talks|told)' "$f"

echo "--- correction pairs ---"
grep -nPi "((it'?s|it is) not [^.]*,? (it'?s|it is))|(never [^.]*\. *(they|it|that)\b)|(says nothing about)|(did ?n[o']?t [^.]*\. *it (became|was|is)\b)" "$f"

echo "--- colon-fragment labels ---"
grep -nEi '^(The (result|problem|catch|answer|reason|upshot|fix)):' "$f"

echo "--- banned words (sample) ---"
grep -nPi '\b(leverage|seamless|robust|comprehensive|cutting-edge|delve|harness|unlock|empower|game-chang|revolutioniz|underscore|showcase|holistic|paradigm|ecosystem|testament)\w*' "$f"

echo "--- filler phrases ---"
grep -nEi "(it'?s (important to note|worth (noting|mentioning))|at the end of the day|here'?s the (thing|kicker|catch)|turns out|under the hood|out of the box|in conclusion|let'?s dive)" "$f"

echo "--- copula-avoidance verbs ---"
grep -nPi '\b(serves? as|stands? as|functions? as|represents?|boasts?|exemplif(y|ies)|epitomiz(e|es))\b' "$f"

echo "--- digestion / erasure metaphors ---"
grep -nPi '\b(swallow(s|ed|ing)?|consum(e|es|ed|ing)|eras(e|es|ed|ing)|drown(s|ed|ing)? out|dissolv(e|es|ed|ing)|evaporat(e|es|ed|ing)|drain(s|ed|ing)?|bur(y|ies|ied))\b' "$f"

echo "--- boundary-line metaphor ---"
grep -nEi "(is the line|that'?s the line|walks? the line|where the line (sits|is)|crossing the line)" "$f"

echo "--- fake-authority phrases ---"
grep -nPi '\b(studies (have )?shown|research (indicates|shows)|experts agree|data suggests)\b' "$f"

echo "--- transition-word stacking (paragraph openers, count vs total paragraphs) ---"
grep -cPi '^(Moreover|Furthermore|Additionally|Notably|Ultimately|Subsequently|Conversely)\b' "$f"

echo "--- curly quotes and apostrophes (must be 0) ---"
grep -oP '[\x{2018}\x{2019}\x{201C}\x{201D}]' "$f" | wc -l
grep -nP '[\x{2018}\x{2019}\x{201C}\x{201D}]' "$f"

echo "--- emoji, prose channel (must be 0) ---"
grep -nP '[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}\x{FE0F}]' "$f"

echo "--- emoji, social channel: decorative placements (must be 0) ---"
# at line start, after a bullet marker, in a heading, or on a line that is only emoji.
# tr drops CRs so a CRLF blank line is not read as a whitespace-only line. One emoji
# below is the atomic group: a base plus skin tones, U+FE0F and zero-width-joined parts.
tr -d '\r' < "$f" | grep -nP '^\s*(#+\s*)?[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}]|^\s*[-*\x{2022}]\s*[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}]|^(?=.*[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}])[\s\x{FE0F}\x{200D}\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}]+$'
echo "--- emoji, social channel: two emoji separated by text on one line (must be 0) ---"
tr -d '\r' < "$f" | grep -nP '(?>[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}][\x{1F3FB}-\x{1F3FF}\x{FE0F}]*(?:\x{200D}[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}][\x{1F3FB}-\x{1F3FF}\x{FE0F}]*)*)\s*[^\s\x{FE0F}\x{200D}\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}].*[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}]'
echo "--- emoji, social channel: adjacent pair and mid-line emoji (eyeball, end of line is the norm) ---"
tr -d '\r' < "$f" | grep -nP '(?>[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}][\x{1F3FB}-\x{1F3FF}\x{FE0F}]*(?:\x{200D}[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}][\x{1F3FB}-\x{1F3FF}\x{FE0F}]*)*)\s*[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}]'
tr -d '\r' < "$f" | grep -nP '(?>[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}][\x{1F3FB}-\x{1F3FF}\x{FE0F}]*(?:\x{200D}[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}][\x{1F3FB}-\x{1F3FF}\x{FE0F}]*)*)\s*[^\s\x{FE0F}\x{200D}\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}\x29\x5D.!?,:;"\x27]'
echo "--- emoji, social channel: total (must be 4 or fewer, none on line 1) ---"
grep -oP '(?>[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}][\x{1F3FB}-\x{1F3FF}\x{FE0F}]*(?:\x{200D}[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}][\x{1F3FB}-\x{1F3FF}\x{FE0F}]*)*)' "$f" | wc -l
head -1 "$f" | grep -cP '[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}]'

echo "--- house terms, wrong in any context (Rule 6, must be 0; skip if you keep no list) ---"
# one pattern per line in house-terms.txt; comments and blank lines dropped
[ -r house-terms.txt ] && grep -nPi "\b(?:$(grep -v '^[[:space:]]*#' house-terms.txt | awk 'NF' | paste -sd'|' -))\b" "$f"

echo "--- house terms that are only wrong as a description of your own product (Rule 6, eyeball) ---"
[ -r house-soft-terms.txt ] && grep -nPi "\b(?:$(grep -v '^[[:space:]]*#' house-soft-terms.txt | awk 'NF' | paste -sd'|' -))\b" "$f"

echo "--- reflective hand-holding (Rule 3, must be 0) ---"
grep -nEi "(keep coming back to|the part that (gets|got|stuck with) me|what struck me|what stuck with me|the interesting thing is|what i find fascinating)" "$f"

echo "--- title case headings (eyeball, proper nouns are fine) ---"
grep -nE '^#{1,6} +\S+( +[A-Z][a-z]+){2,}' "$f"

echo "--- trailing participial clauses (S18) ---"
grep -nPi ',[[:space:]]+(highlighting|ensuring|reflecting|showcasing|fostering|underscoring|demonstrating|allowing|enabling|cementing|solidifying|paving|positioning|signalling|signaling|marking|making it (easier|possible)|further)\b' "$f"

echo "--- label-colon bullets (S19) ---"
grep -nE '^[[:space:]]*[-*]?[[:space:]]*\*\*[^*]+:\*\*' "$f"

echo "--- despite-challenges arc (S20) ---"
grep -nEi '(despite [^.]{0,40}(challenge|hurdle|obstacle|headwind)|while challenges remain|not without its|continues to (thrive|grow|evolve|lead|accelerate))' "$f"

echo "--- false ranges (S21) ---"
grep -nPi '(everything |anything )?\bfrom [a-z]+ to [a-z]+\b' "$f"

echo "--- assistant tics ---"
# Single quotes, not double: an exclamation mark inside double quotes triggers
# bash history expansion when this block is pasted into an interactive shell,
# and the line dies with "event not found" instead of running. That also means
# the apostrophe below has to be matched as . rather than written literally.
grep -nEi '(i hope this helps|great question|you.?re absolutely right|happy to help|of course!|certainly!|^perfect!|^found it!)' "$f"

echo "--- knowledge-limit disclaimers ---"
grep -nEi '(specific details are limited|based on available information|as of my last (update|training)|unclear from the (sources|available))' "$f"

echo "--- filler connectives ---"
grep -nPi '\b(in order to|due to the fact that|for the purpose of|in the process of|it should be noted that|prior to|subsequent to)\b' "$f"

echo "--- inflated synonyms ---"
grep -nPi '\b(utiliz(e|es|ed|ing|ation)|facilitat(e|es|ed|ing)|numerous|commenc(e|es|ed|ing)|ascertain|garner(s|ed|ing)?|enhanc(e|es|ed|ing|ement))\b' "$f"

echo "--- abstract metaphor nouns ---"
grep -nPi '\b(substrate|wedge|vector|locus|vantage|primitive|scaffolding|modality|gold-plat|ratchet|endgame|north star|flywheel|api surface)\b' "$f"

echo "--- puffery and brochure adjectives ---"
grep -nPi '\b(nestled|vibrant|breathtaking|stunning|renowned|iconic|must-visit|bustling|picturesque|hidden gem|rich history|deeply rooted|indelible|evolving landscape|pivotal moment|setting the stage)\b' "$f"

echo "--- stacked hedges (C5) ---"
grep -nPi '\b(could|may|might|can) (potentially|possibly|perhaps|arguably|conceivably)\b' "$f"

echo "--- weak adverbs and intensifiers (C4) ---"
grep -noPi '\b(essentially|basically|simply|just|actually|really|quite|fairly|significantly|very|extremely|incredibly|seamlessly|effectively|truly)\b' "$f"

echo "--- passive voice candidates (C3, eyeball these) ---"
grep -noE '\b(is|are|was|were|been|being) [a-z]+(ed|en)\b' "$f"

echo "--- bold density (want under roughly 1 in 10 lines) ---"
echo "bold runs: $(grep -oE '\*\*[^*]+\*\*' "$f" | wc -l), lines: $(wc -l < "$f")"

echo "--- burstiness, sd of sentence length over mean (want above 0.4) ---"
tr '!?' '..' < "$f" | tr '.' '\n' | awk 'NF>2 {n++; s+=NF; q+=NF*NF} END {if (n>1) {m=s/n; sd=sqrt(q/n-m*m); printf "sentences=%d mean=%.1f sd=%.1f burstiness=%.2f\n", n, m, sd, sd/m}}'
```

Eight blocks are hard failures at any count above zero, the same eight that make `check-copy.sh` exit 1: dashes, curly quotes, emoji outside the social channel clause, house terms (when you keep a list), negation openers, the boundary-line metaphor, reflective hand-holding, and assistant tics. Fix and re-run until all eight read zero.

**Portability.** Every check in this block that uses `\b` or a `\x{...}` code point runs under `grep -P`, because `\b` is only a word boundary in PCRE (under `-E` it is a GNU extension and a literal on BSD grep). macOS system grep has no `-P` at all: install GNU grep from Homebrew and run the block with `ggrep`, use a container, or run `${CLAUDE_PLUGIN_ROOT}/scripts/check-copy.sh`, which finds `ggrep` on its own and exits 2 rather than reporting a pass when no `-P`-capable grep exists.

Four blocks need eyes rather than a verdict, because they match legitimate prose too: title case headings, passive voice candidates, false ranges, and the adverb list. Read each hit and decide.

The burstiness number is the one measurement in this block that tells you about rhythm rather than vocabulary. Below 0.4 means every sentence is roughly the same length, which is a top-three tell (see Part 7). The fix is C2: split the long ones and let a short one stand alone.

Then read the copy and apply Part 2 and Part 3 by eye, since sentence shapes and dead abstractions do not grep reliably.

---

# PART 5: Copy review

When invoked, audit text already written. It does not matter who wrote it or how good it already is.

1. **Hard character count.** Dashes, curly quotes, decorative emoji (or, for a social post, emoji outside the Rule 5 channel clause) and Rule 6 house terms, if a list is configured. All must be zero. List every location.
2. **Shape scan.** Walk S1 through S23 in order. For each hit, quote the line and give the rewrite.
3. **Line-level pass.** Walk C1 through C5. The portability test in C1 applies to every sentence: flag any that would work unchanged in a competitor's docs.
4. **Fragment budget.** Count fragments. More than one is a failure.
5. **Ending check.** Does it close on a rhetorical question or a wrap-up?
6. **Word and phrase scan.** Rules 2 and 3.
7. **Typography and formatting.** Rule 5: heading case, bold density, parenthesis count, colon use.
8. **Prescribed-vocabulary count.** More than one Rule 4 word (boring, underrated, unsexy, or your own list) is a failure.
9. **Generative check.** Run the applicable checks in Part 7. For an article or social post, report what supported author material would improve it, not only what needs removing. For short or functional text, do not treat absent essay features as failures.
10. **Self-audit.** Answer in one line: what still reads as machine-written here? Then fix that too.

Output format:

```
## Copy review

### Hard rules
- Em/en dashes: N (must be 0), lines X, Y
- Banned words: [list with lines]
- Banned phrases: [list with lines]

### Sentence shapes
1. S1 negation opener (line X)
   Original: "..."
   Rewrite:  "..."

### Line-level (C1 to C5)
1. C1 portability failure (line X)
   Original: "..."
   Rewrite:  "..."

### Budgets
- Fragments: N (max 1)
- Prescribed vocab: N (max 1)
- Parentheticals: N
- Bold runs: N over M lines
- Burstiness: N.NN (want above 0.40)
- Closing question: yes/no

### Generative gate
- Checkable number, name or date: yes/no
- Stated position with an admitted limit: yes/no
- One unpolished human artefact: yes/no
- Reader as the subject of at least one sentence: yes/no
- Reusable artefact: yes/no

### Still reads as machine-written because
[one line, then fixed in the rewrite below]

### Rewritten version
[full clean text]
```

---

# PART 6: Before and after

### Corporate filler to direct statement

**Before:** "It's important to note that Acme's comprehensive scheduling platform enables organizations to seamlessly coordinate their teams across locations, leveraging robust automation and cutting-edge algorithms."

**After:** "Acme builds shift rotas for teams that work across several sites. It checks availability, holiday rules and overtime limits."

**Changed:** killed five banned words, removed the filler opener, replaced adjectives with specifics.

### Negation opener to fact

**Before:** "Nobody invented a new log format. Three teams landed on the same answer this year."

**After:** "The billing, search and support teams all picked JSON Lines for their event logs this year. It stores one JSON object per line, so a log can be appended to and streamed without parsing the whole file."

**Changed:** deleted the suspense sentence (S1), replaced "landed on" with "picked", moved the definition to where a reader actually wants it.

### Correction pair to one sentence

**Before:** "Customers never left over price. They left over support."

**After:** "Customers left over support, not price."

**Changed:** two sentences and a swerve become one clause plus a contrast (S2).

### Aphorism cut

**Before:** "82% of managers say their team has a written on-call policy. 14% have run a drill in the last year. That distance is where the outages live."

**After:** "82% of managers say their team has a written on-call policy, but only 14% have run a drill in the last year."

**Changed:** joined the stats with a conjunction (S5), deleted the proverb (S3). The gap between the two numbers is the point and does not need narrating.

### Reframe to plain statement

**Before:** "Spreadsheets have the data. What they lack is the story. Acme doesn't just chart your numbers, it explains them."

**After:** "Spreadsheets hold the numbers but don't say what changed. Acme charts them and writes one line under each chart on what moved and why."

**Changed:** removed the "X. What they lack is Y" reframe and the "doesn't just X, it Y" intensifier (S2, S11).

### Wrap-up to actual ending

**Before:** "In conclusion, as we've explored throughout this article, the future of home baking lies in purpose-built tools that handle the complexity so bakers don't have to. The journey toward truly foolproof bread is just beginning, and the possibilities are endless."

**After:** "Most of the flat loaves readers send me were under-proofed rather than badly mixed, and a cheap probe thermometer will fix more of them than another cookbook."

**Changed:** cut "In conclusion", "as we've explored", "journey", "possibilities are endless". Ended on a specific arguable claim. No dash is needed: the clauses are joined with a comma and "and".

---

# Final gate

Check applicability before submitting. A "no" on an applicable check needs a fix;
an inapplicable check does not require extra content. Keep the mechanical channel
rules, and judge sentence/ending/paragraph checks against the requested format.

1. Dash count, curly-quote count and decorative-emoji count are all exactly zero?
2. Does the first sentence carry a fact rather than build suspense?
3. Zero correction pairs, zero aphorism caps, zero self-commentary on structure?
4. Zero trailing participial clauses explaining what a fact means?
5. One fragment at most, with none adjacent?
6. Does every sentence survive the portability test, so none of them would work unchanged in a competitor's docs?
7. Ending is not a rhetorical question or a wrap-up?
8. Asked out loud: what still reads as machine-written here, and fixed it?
9. Would a working engineer send this to a colleague without embarrassment?

---

# PART 7: The generative half, what to ADD

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

---

# Design notes

Why some rules look the way they do, so an edit does not undo them by accident.

**One script, not pasted copies.** The mechanical check lives in `scripts/check-copy.sh` so workflows and other skills call it rather than paste the grep block. Pasted copies drift: a fix lands in one and never reaches the others. A host without `grep -P` gets exit code 2, never a silent pass.

**Ban the category, not the string.** Word-level bans catch what has already been named. Treat every newly flagged phrase as one instance of an unnamed category and ban the category. `serves as` was missing from earlier word lists because nobody had flagged it, not because it was safe; the copula-avoidance rule now covers the whole family.

**The social channel clause.** The base emoji rule is zero, and one channel relaxes it mechanically. A blanket ban on a channel where the author's own posts carry end-of-line emoji leaves the writer unable to match the author, and a rule that makes emoji mandatory is worse. The clause is narrow on purpose.

**Two reconciliations.** Rule 1 once offered parentheses as a dash replacement; the parenthesis is now budgeted, because swapping one for the other is a find and replace rather than a rewrite. And the hedging ban in C5 sits next to the admitted-uncertainty requirement in Part 7 on purpose: stacked vague modals are the tell, and a single hedge that names its own scope is the fix.

**The portability test.** C1's test is the one check that fails a sentence for saying nothing rather than for using a flagged word. Word lists always trail the output. A test that asks whether the sentence could appear unchanged in a competitor's docs does not.

**Asset text is in scope.** Labels, captions and slide text used to rely on each asset skill's author remembering the rule, and a figure can pass design review with em dashes still in its labels. The skill that owns the rule claims the trigger, so a label gets the same pass as a paragraph.

---

# Credits

Parts 1, 2, 6 and 7 grew out of audits of generated copy and direct reader feedback on it. Rule 5, shapes S18 to S23, and Part 3 are adapted from the `unslop` skill in [cursor/plugins](https://github.com/cursor/plugins/blob/main/pstack/skills/unslop/SKILL.md), reorganised into this skill's structure with new examples.
