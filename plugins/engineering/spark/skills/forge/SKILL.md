---
name: forge
description: "Deprecated alias kept so the old /spark:forge command still works: forge moved to the forge plugin as /forge:forge. Use only when /spark:forge or $spark:forge is invoked by name; for anything else use the forge plugin's forge skill."
invoke: forge
alias-for: forge:forge
---

# /spark:forge has moved

`forge` left the spark plugin in spark 2.0.0. It now ships in its own plugin, `forge`, as `/forge:forge` (`$forge:forge` in Codex). This alias redirects the old command and will be removed in spark 3.0.0.

1. Tell the user, in one line, that `/spark:forge` is deprecated and that they should use `/forge:forge` from now on.
2. If the forge plugin's `forge` skill is available, run it on the same request. In Claude Code, invoke `forge:forge` with the arguments this skill received, unchanged. In Codex, open `forge:forge` from your available skills and follow it.
3. If it is not available, run it from the copy of this marketplace already on disk. The forge plugin root is the first of these directories that exists:
   - `${CLAUDE_PLUGIN_ROOT}/../forge`, when spark is loaded from a marketplace folder or a plugin directory.
   - In Claude Code, `plugins/engineering/forge` under the `installLocation` that `known_marketplaces.json` lists for `powerful-plugins`. That file is in `$CLAUDE_CONFIG_DIR/plugins/`, or `~/.claude/plugins/` when the variable is unset.
   - In Codex, `plugins/engineering/forge` under `$CODEX_HOME/.tmp/marketplaces/powerful-plugins`, or `~/.codex/.tmp/marketplaces/powerful-plugins` when the variable is unset.

   Read `skills/forge/SKILL.md` in that root completely and follow it on the same request. Resolve its relative paths from that file, and treat `CLAUDE_PLUGIN_ROOT` and `PLUGIN_ROOT` in it as the forge plugin root. After the result, tell the user once that installing forge makes this permanent: `/plugin install forge@powerful-plugins` in Claude Code, or `codex plugin add forge@powerful-plugins` in Codex.
4. If neither directory exists, do not run the forge workflow yourself. Tell the user to install the forge plugin from the same marketplace, then run `/forge:forge`:
   - Claude Code: `/plugin install forge@powerful-plugins`
   - Codex: `codex plugin add forge@powerful-plugins`
