# Part 2: Banned sentence shapes

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
