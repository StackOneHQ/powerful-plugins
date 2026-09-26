# Creating Skills

Guide for creating new skills for the powerful-plugins marketplace.

## What is a Skill?

A skill is a SKILL.md file containing instructions that the agent follows automatically when triggered by context. Unlike commands that require explicit invocation, skills activate based on the task at hand.

## Quick Start

### 1. Copy the Template

Skills live inside a plugin:

```bash
cp -r templates/skill-template plugins/your-category/your-plugin/skills/your-skill-name
```

### 2. Edit SKILL.md

Fill in the template's sections: a `description` that says what the skill does and when to use
it, the goal, the inputs, the boundaries (what's safe to do without asking and what needs a yes)
and the output. Keep a numbered workflow only where the order really matters, and move detail
into `references/`.

[CLAUDE.md](../CLAUDE.md#writing-instructions-that-work-on-any-model) explains why: the skills
run on different models, mostly GPT-6 Astra and Claude Opus 5.5, and both do better with a clear
outcome and boundaries than with a step-by-step recipe or emphatic "MUST" rules.

### 3. Test Locally

```bash
# Load the whole plugin for one session
claude --plugin-dir plugins/your-category/your-plugin

# Or copy the skill into a project for a quick trial
cp -r plugins/your-category/your-plugin/skills/your-skill-name .claude/skills/
```

Then check that the skill triggers on the requests it should.

For Codex, install the plugin from a local marketplace checkout, or export the skill with
`scripts/export-standalone-skills.sh`.

## SKILL.md Structure

### Required Frontmatter

```yaml
---
name: lowercase-with-hyphens
description: Description that tells Claude when to use this skill
---
```

### Recommended sections

These match `templates/skill-template/SKILL.md`. Drop any that don't apply.

| Section | Purpose |
|---------|---------|
| Goal | What good output looks like, so the agent can judge its own work |
| Inputs | What the agent works from, which source wins, and what to do when one is missing |
| Boundaries | User instructions win; what's safe to do without asking; what needs a yes; what's out of scope |
| Workflow | Numbered steps, only where the order matters |
| Output | Format and length of the deliverable |
| References | Files in `references/`, each with when to read it |

## Writing good instructions

The rules and the evidence behind them are in
[CLAUDE.md](../CLAUDE.md#writing-instructions-that-work-on-any-model). In practice:

### Be specific about facts, not about steps

Give the agent the facts it can't guess, and let it plan the work.

```markdown
# Vague
Handle API errors appropriately.

# Specific
The API returns 429 when rate limited, with a Retry-After header in seconds. A 401 means the
token expired: tell the user to run `example login`. Retrying a 5xx is safe because every
endpoint is idempotent.
```

### Use tables for reference data

Lookups such as status codes, file types or option names read better as a table than as prose.

### Show the output when the format is easy to get wrong

One short example of the finished deliverable is worth more than a paragraph describing it.
Don't script the agent's actions step by step in the example.

## Choosing a Category

| Category | For Skills About |
|--------|-----------------|
| `design/` | Animation, visual design, data visualization |
| `documentation/` | Writing, editing, formatting |
| `engineering/` | Code patterns, development workflows, browser and agent tooling |
| `productivity/` | Personal workflow tools, exports, reporting |

## Naming Conventions

- **Lowercase with hyphens**: `api-patterns` not `APIPatterns`
- **Descriptive**: `browser-recorder` not `br`
- **No company or owner prefix**: `tufte-viz`, not `acme-tufte-viz`
- **Action-oriented descriptions**: "Create...", "Answer...", "Generate..."

## Testing Checklist

- [ ] YAML frontmatter is valid
- [ ] Name is lowercase with hyphens
- [ ] Description clearly states when to use
- [ ] Instructions state the goal, boundaries and output, with numbered steps only where order matters
- [ ] Examples demonstrate expected behavior
- [ ] No sensitive information included

## Submitting Your Skill

1. Create a branch: `feature/<category>/<skill-name>`
2. Add your skill to its plugin's `skills/` folder
3. Update `.claude-plugin/marketplace.json` if creating a new plugin, then run `python3 scripts/generate_codex_marketplace.py`
4. Bump the plugin's version if it already existed, in both its `.claude-plugin/plugin.json` and its entry in `.claude-plugin/marketplace.json`
5. Open a pull request and wait for the required checks to pass
