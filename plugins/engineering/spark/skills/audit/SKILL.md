---
name: audit
description: "Deprecated alias kept so the old /spark:audit command still works: audit moved to the forge plugin as /forge:audit. Use only when /spark:audit or $spark:audit is invoked by name; for anything else use the forge plugin's audit skill."
invoke: audit
---

# /spark:audit has moved

`audit` left the spark plugin in spark 2.0.0. It now ships in its own plugin, `forge`, as `/forge:audit` (`$forge:audit` in Codex). This alias redirects the old command and will be removed in spark 3.0.0.

1. Tell the user, in one line, that `/spark:audit` is deprecated and that they should use `/forge:audit` from now on.
2. If the `forge:audit` skill is available, invoke it with the arguments this skill received, unchanged, and follow it from there.
3. If it is not available, do not run the audit workflow yourself. Tell the user to install the forge plugin from the same marketplace, then run `/forge:audit`:
   - Claude Code: `/plugin install forge@powerful-plugins`
   - Codex: `codex plugin add forge@powerful-plugins`
