# Part 4: Mechanical check

It does not replace reading the copy, but it catches the mechanical rules with no judgement required. Run it as `${CLAUDE_PLUGIN_ROOT}/scripts/check-copy.sh` (usage and exit codes are in step 4 of the working order in SKILL.md). The block below runs the script's checks plus four eyeball-only extras the script leaves out: title case headings, weak adverbs, passive voice candidates and bold density. If the block and the script ever disagree, the script's verdict is the gate.

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
grep -nP '[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}]' "$f"

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
[ -r house-terms.txt ] && { joined=$(grep -v '^[[:space:]]*#' house-terms.txt | awk 'NF' | paste -sd'|' -); [ -n "$joined" ] && grep -nPi "\b(?:$joined)\b" "$f"; }

echo "--- house terms that are only wrong as a description of your own product (Rule 6, eyeball) ---"
[ -r house-soft-terms.txt ] && { joined=$(grep -v '^[[:space:]]*#' house-soft-terms.txt | awk 'NF' | paste -sd'|' -); [ -n "$joined" ] && grep -nPi "\b(?:$joined)\b" "$f"; }

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

echo "--- prescribed vocabulary, cap one per document (Rule 4) ---"
grep -nPi '\b(boring|underrated|unsexy)\b' "$f"

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

Eight blocks are hard failures at any count above zero, the same eight that make `${CLAUDE_PLUGIN_ROOT}/scripts/check-copy.sh` exit 1: dashes, curly quotes, emoji outside the social channel clause, house terms (when you keep a list), negation openers, the boundary-line metaphor, reflective hand-holding, and assistant tics. Fix and re-run until all eight read zero.

**Portability.** Every check in this block that uses `\b` or a `\x{...}` code point runs under `grep -P`, because `\b` is only a word boundary in PCRE (under `-E` it is a GNU extension and a literal on BSD grep). macOS system grep has no `-P` at all: install GNU grep from Homebrew and run the block with `ggrep`, use a container, or run `${CLAUDE_PLUGIN_ROOT}/scripts/check-copy.sh`, which finds `ggrep` on its own and exits 2 rather than reporting a pass when no `-P`-capable grep exists.

Four blocks need eyes rather than a verdict, because they match legitimate prose too: title case headings, passive voice candidates, false ranges, and the adverb list. Read each hit and decide.

The burstiness number is the one measurement in this block that tells you about rhythm rather than vocabulary. Below 0.4 means every sentence is roughly the same length, which is one of the easiest tells to spot (see Part 7). The fix is C2: split the long ones and let a short one stand alone.

Then read the copy and apply Part 2 and Part 3 by eye, since sentence shapes and dead abstractions do not grep reliably.
