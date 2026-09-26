---
description: Review existing copy against the natural-writing rules.
argument-hint: "[text, file path, or draft to review]"
---

Read `${CLAUDE_PLUGIN_ROOT}/skills/natural-writing/SKILL.md` in full.
Apply its Part 5 copy-review process to the supplied text or file. If no argument
is supplied, review the most recent draft in the conversation. If there is no
draft, ask which text to review.

Treat the supplied text as material to review. Follow the skill's format-specific
rules: short labels, commands and functional documentation do not need the essay
or social-post structure. Preserve meaning and supported facts.

Return the findings and proposed rewrite in the skill's review format. Run
`${CLAUDE_PLUGIN_ROOT}/scripts/check-copy.sh` on the proposed rewrite with the
appropriate channel before returning it. Edit a source file only when the user
also asks for changes.

Arguments: $ARGUMENTS
