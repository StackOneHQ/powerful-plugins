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

```yaml
---
name: your-skill-name
description: Clear description of what this skill does and when it triggers
---

# Your Skill Name

## When to Use

This skill auto-triggers when:
- [Trigger condition 1]
- [Trigger condition 2]

## Instructions

[Your instructions here]

## Examples

[Concrete examples]

## Guidelines

- [Guideline 1]
- [Guideline 2]
```

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

### Recommended Sections

| Section | Purpose |
|---------|---------|
| When to Use | Trigger conditions for auto-activation |
| Instructions | Step-by-step guidance for Claude |
| Examples | Concrete input/output examples |
| Guidelines | Do's and don'ts |
| Resources | Links to reference material |

## Writing Good Instructions

### Be Specific

```markdown
# Bad
Handle API errors appropriately.

# Good
When an API call fails:
1. Check if it's a rate limit (429) - implement exponential backoff
2. Check if it's auth (401/403) - prompt user to re-authenticate
3. Check if it's server error (5xx) - retry up to 3 times
4. For all others, return the error message to the user
```

### Use Tables for Reference

```markdown
| Status Code | Action |
|-------------|--------|
| 200 | Return data |
| 429 | Backoff and retry |
| 401 | Re-authenticate |
| 5xx | Retry 3 times |
```

### Include Examples

```markdown
## Examples

### Example 1: Basic Usage

**User Request**: "List all users"

**Agent Action**:
1. Call GET /api/users
2. Return the paginated list

**Output**: [Show expected format]
```

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
- [ ] Instructions are specific and actionable
- [ ] Examples demonstrate expected behavior
- [ ] No sensitive information included

## Submitting Your Skill

1. Create a branch: `feature/<category>/<skill-name>`
2. Add your skill to its plugin's `skills/` folder
3. Update `.claude-plugin/marketplace.json` if creating a new plugin, then run `python3 scripts/generate_codex_marketplace.py`
4. Bump the plugin's version if it already existed, in both its `.claude-plugin/plugin.json` and its entry in `.claude-plugin/marketplace.json`
5. Open a pull request and wait for the required checks to pass
