# Design notes

Why some rules look the way they do, so an edit does not undo them by accident.

**One script, not pasted copies.** The mechanical check lives in `scripts/check-copy.sh` so workflows and other skills call it rather than paste the grep block. Pasted copies drift: a fix lands in one and never reaches the others. A host without `grep -P` gets exit code 2, never a silent pass.

**Ban the category, not the string.** Word-level bans catch what has already been named. Treat every newly flagged phrase as one instance of an unnamed category and ban the category. `serves as` was missing from earlier word lists because nobody had flagged it, not because it was safe; the copula-avoidance rule now covers the whole family.

**The social channel clause.** The base emoji rule is zero, and one channel relaxes it mechanically. A blanket ban on a channel where the author's own posts carry end-of-line emoji leaves the writer unable to match the author, and a rule that makes emoji mandatory is worse. The clause is narrow on purpose.

**Two reconciliations.** Rule 1 once offered parentheses as a dash replacement; the parenthesis is now budgeted, because swapping one for the other is a find and replace rather than a rewrite. And the hedging ban in C5 sits next to the admitted-uncertainty requirement in Part 7 on purpose: stacked vague modals are the tell, and a single hedge that names its own scope is the fix.

**The portability test.** C1's test is the one check that fails a sentence for saying nothing rather than for using a flagged word. Word lists always trail the output. A test that asks whether the sentence could appear unchanged in a competitor's docs does not.

**Asset text is in scope.** Labels, captions and slide text used to rely on each asset skill's author remembering the rule, and a figure can pass design review with em dashes still in its labels. The skill that owns the rule claims the trigger, so a label gets the same pass as a paragraph.
