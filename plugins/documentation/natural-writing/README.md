# natural-writing

Writing and editing rules for prose, messages and the text inside assets.

For plain technical English, runbooks and explanations of mechanisms, the skill
has a technical explanation mode. It keeps conditions, quantities, identifiers and
uncertainty intact, uses consistent terms, and checks protected source text
separately from authored prose. It borrows STE principles without claiming
ASD-STE100 compliance. Ask, for example: "Explain this retry policy in plain
technical English for an engineer who has not worked on this service."

## Install

```bash
# Claude Code
/plugin marketplace add StackOneHQ/powerful-plugins
/plugin install natural-writing@powerful-plugins

# Codex
codex plugin marketplace add StackOneHQ/powerful-plugins
codex plugin add natural-writing@powerful-plugins
```

## Run

| Task | Claude Code command |
|---|---|
| Write or edit copy | `/natural-writing:natural-writing <task>` |
| Review an existing draft | `/natural-writing:review-copy <text or file path>` |

With no argument, the review command uses the latest draft in the conversation.
It returns findings and a proposed rewrite. It edits a file only when requested.
The command follows the review process in
[references/copy-review.md](skills/natural-writing/references/copy-review.md),
including the mechanical check in [scripts/check-copy.sh](scripts/check-copy.sh).
[SKILL.md](skills/natural-writing/SKILL.md) holds the hard rules and links each
reference in the step that needs it.

Plugin commands use a namespace. Use the full command above if another installed
skill has a similar name. Reload plugins or restart Claude Code after updating.

In Codex, use `$natural-writing:natural-writing` to write or edit, and
`$natural-writing:codex-review-copy` to review a draft.

## Mechanical check

```bash
scripts/check-copy.sh [--channel prose|social] [--banned-terms FILE] [--soft-terms FILE] [--allow-house-terms] draft.md
```

Exit 0 is a pass, 1 is a hard failure, 2 is a usage error, an input that is not
a regular file, or a host whose grep cannot run the checks: no `grep -P`, no UTF-8
locale, or a grep error mid-run (on macOS, `brew install grep` provides `ggrep`,
which the script finds on its own).

## Add your house style

Rule 6 in the skill ships empty. To ban terms that are wrong for your team, such
as a competitor's category name or a retired product name, put one pattern per
line in a file and pass it with `--banned-terms`, or set `COPY_BANNED_TERMS`.
Terms that are only wrong as a description of your own product go in a second
file passed with `--soft-terms` (`COPY_SOFT_TERMS`); those are reported, not
failed. The skill has a worked example.
