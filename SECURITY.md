# Security policy

These plugins run inside coding agents on people's machines, so a flaw in one can reach every user
who installs it. We take reports seriously and would rather hear about a possible issue than miss a
real one.

## Reporting a vulnerability

Report it privately through GitHub's
[private vulnerability reporting](https://github.com/StackOneHQ/powerful-plugins/security/advisories/new)
for this repository. Please don't open a public issue or pull request for a vulnerability.

Useful things to include:

- the plugin, skill, command, agent or script affected, and the version in its `plugin.json`
- what an attacker could do, and what they need first (a malicious page the agent reads, a crafted
  repository, write access to this repo)
- steps or a minimal example that shows it

We aim to acknowledge a report within 3 working days and to agree a fix and disclosure date with
you after that. We credit reporters in the advisory unless you ask us not to.

## What counts

In scope: anything in this repository, including instructions that could lead an agent to run
untrusted code, leak files or credentials, or act without the user's consent; the marketplace
tooling and CI workflows; and the pinned external plugins' entries (report a flaw in the external
plugin itself to its own maintainers too).

Out of scope: vulnerabilities in Claude Code, Codex or other host tools themselves (report those
to their vendors), and the agent model following instructions a user deliberately gave it.

## Supported versions

Only the latest version of each plugin on `main` gets fixes. Updating the marketplace
(`/plugin marketplace update powerful-plugins`, or the Codex equivalent) picks them up.
