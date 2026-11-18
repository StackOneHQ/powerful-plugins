#!/bin/sh
# Hook entry point for Turn Vault.
# Claude Code sets CLAUDE_PLUGIN_ROOT and Codex sets PLUGIN_ROOT.
# Hooks run with a minimal PATH, so probe standard Node.js install locations too.
# Always exits 0 so hook execution never blocks or fails an agent session.

if [ "${TURN_VAULT_DISABLED:-0}" = "1" ] || [ "${TURN_VAULT_DISABLED:-}" = "true" ]; then
  exit 0
fi

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-$(CDPATH='' cd -- "$SCRIPT_DIR/.." && pwd)}}"

NODE_BIN=$(command -v node 2>/dev/null || true)
if [ -z "$NODE_BIN" ]; then
  for candidate in \
    "$HOME/.volta/bin/node" \
    "/opt/homebrew/bin/node" \
    "/usr/local/bin/node"
  do
    if [ -x "$candidate" ]; then
      NODE_BIN="$candidate"
      break
    fi
  done
fi

if [ -z "$NODE_BIN" ] && [ -d "$HOME/.nvm/versions/node" ]; then
  for candidate in "$HOME"/.nvm/versions/node/*/bin/node; do
    if [ -x "$candidate" ]; then
      NODE_BIN="$candidate"
    fi
  done
fi

[ -n "$NODE_BIN" ] || exit 0
[ -f "$PLUGIN_ROOT/bin/turn-vault.mjs" ] || exit 0

"$NODE_BIN" "$PLUGIN_ROOT/bin/turn-vault.mjs" "$@" >/dev/null 2>&1 || true
exit 0
