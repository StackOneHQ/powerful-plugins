#!/bin/bash
# Preview a voice by playing a real hook phrase in the voice's own language.

set -u

voice="${1:?Usage: preview-voice.sh <voice> [<speed>] [<repo_label>]}"

# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

kokoro_lang=$(voice_to_kokoro_lang "$voice")
speed="${2:-$(read_config_speed)}"
load_phrases "$(voice_to_lang "$voice")"
# shellcheck disable=SC2059
sentence=$(printf "${TEMPLATES_RESPONSE[0]}" "${3:-stack vox}")

# Prefer the daemon if it's up (no model reload between previews).
if command -v stackvox-say >/dev/null && stackvox status >/dev/null 2>&1; then
  stackvox-say --voice "$voice" --lang "$kokoro_lang" --speed "$speed" "$sentence"
else
  stackvox speak "$sentence" --voice "$voice" --lang "$kokoro_lang" --speed "$speed"
fi
