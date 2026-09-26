# Part 5: Copy review

When invoked, audit text already written. It does not matter who wrote it or how good it already is.

The rules this review walks live in SKILL.md (Part 1, Rules 1 to 6), [sentence-shapes.md](sentence-shapes.md) (S1 to S23), [line-craft.md](line-craft.md) (C1 to C6) and [generative.md](generative.md) (Part 7). `scripts/check-copy.sh` answers step 1 and flags candidates for step 6.

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
