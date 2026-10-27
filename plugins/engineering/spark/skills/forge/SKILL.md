---
name: forge
description: "Deprecated alias kept so the old /spark:forge command still works: forge moved to the forge plugin as /forge:forge. Use only when /spark:forge or $spark:forge is invoked by name; for anything else use the forge plugin's forge skill."
invoke: forge
---

# /spark:forge has moved

`forge` left the spark plugin in spark 2.0.0. It now ships in its own plugin, `forge`, as `/forge:forge` (`$forge:forge` in Codex). This alias redirects the old command and will be removed in spark 3.0.0.

1. Tell the user, in one line, that `/spark:forge` is deprecated and that they should use `/forge:forge` from now on.
2. If the `forge:forge` skill is available, invoke it with the arguments this skill received, unchanged, and follow it from there.
3. If it is not available, do not run the forge workflow yourself. Tell the user to install the forge plugin from the same marketplace, then run `/forge:forge`:
   - Claude Code: `/plugin install forge@powerful-plugins`
   - Codex: `codex plugin add forge@powerful-plugins`
