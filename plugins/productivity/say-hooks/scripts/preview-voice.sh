#!/bin/bash
# Preview a voice by playing a real hook phrase in the voice's own language.
# Usage: preview-voice.sh <voice> [<speed>] [<repo_label>]
# Speed defaults to the configured speed (or 1.0). repo_label defaults to "stack vox".

set -u

voice="${1:?Usage: preview-voice.sh <voice> [<speed>] [<repo_label>]}"
speed_override="${2:-}"
repo_label="${3:-stack vox}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"

# shellcheck source=lib.sh
source "$PLUGIN_ROOT/scripts/lib.sh"

lang=$(voice_to_lang "$voice")
kokoro_lang=$(voice_to_kokoro_lang "$voice")
speed="${speed_override:-$(read_config_speed)}"

# shellcheck source=../phrases/en.sh
source "$PLUGIN_ROOT/phrases/${lang}.sh" 2>/dev/null || \
  source "$PLUGIN_ROOT/phrases/en.sh"

template="${TEMPLATES_RESPONSE[0]}"
# shellcheck disable=SC2059
sentence=$(printf "$template" "$repo_label")

# Prefer the daemon if it's up (no model reload between previews).
if command -v stackvox-say >/dev/null && stackvox status >/dev/null 2>&1; then
  stackvox-say --voice "$voice" --lang "$kokoro_lang" --speed "$speed" "$sentence"
else
  stackvox speak "$sentence" --voice "$voice" --lang "$kokoro_lang" --speed "$speed"
fi
