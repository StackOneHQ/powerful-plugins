#!/bin/bash
# Notification hook: announce that Claude is blocked and needs user input
# (permission prompts, idle timeouts). Language tracks the configured voice
# when stackvox is available; falls back to English via macOS `say` otherwise.

set -u

if [[ "${SAY_HOOKS_CODEX_HOOK:-}" == "1" && "${SAY_HOOKS_BACKGROUND:-}" != "1" ]]; then
  SAY_HOOKS_BACKGROUND=1 nohup bash "$0" >/dev/null 2>&1 &
  exit 0
fi

# shellcheck source=scripts/lib.sh
source "${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh"

command -v stackvox-say >/dev/null || command -v say >/dev/null || exit 0
# Notifications are user-blocking — always speak, even with focus/rate checks.
# (Set STACKVOX_QUIET_NOTIFICATIONS=1 to apply the same suppression here.)
if [[ "${STACKVOX_QUIET_NOTIFICATIONS:-}" == "1" ]]; then
  should_skip && exit 0
fi

voice=$(read_config_voice)
speed=$(read_config_speed)

if command -v stackvox-say >/dev/null; then
  lang=$(voice_to_lang "$voice")
  kokoro_lang=$(voice_to_kokoro_lang "$voice")
  repo=$(repo_name_raw)
else
  lang="en"
  repo=$(repo_name_expanded)
fi

# shellcheck source=phrases/en.sh
source "${CLAUDE_PLUGIN_ROOT}/phrases/${lang}.sh" 2>/dev/null || \
  source "${CLAUDE_PLUGIN_ROOT}/phrases/en.sh"

template="${TEMPLATES_NOTIFICATION[$RANDOM % ${#TEMPLATES_NOTIFICATION[@]}]}"
# shellcheck disable=SC2059
sentence=$(printf "$template" "$repo")

lock=/tmp/claude-say.lock
if command -v shlock >/dev/null; then
  until shlock -f "$lock" -p $$ 2>/dev/null; do sleep 0.2; done
  trap 'rm -f "$lock"' EXIT
fi

if command -v stackvox-say >/dev/null; then
  stackvox-say --voice "$voice" --lang "$kokoro_lang" --speed "$speed" "$sentence"
else
  say "$sentence"
fi
