#!/bin/bash
# Shared helpers for say-hooks, sourced by the scripts next to it.

SAY_HOOKS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_VOICE="af_heart"
DEFAULT_SPEED="1.0"
CONFIG_FILE="$HOME/.claude/say-hooks.local.md"
RATE_LIMIT_SECONDS=3
CACHE_DIR="$HOME/.cache/say-hooks"
# Shared by every session, so two that finish together take turns instead of talking over each other.
SPEECH_LOCK="$CACHE_DIR/speech.lock"

TERMINAL_NAMES_PATTERN='^(iTerm2|Terminal|Alacritty|kitty|Ghostty|Warp|WezTerm|Hyper|Tabby|Code|Cursor|Electron)$'

# detach_under_codex <script>: Codex hooks cannot be async, so under Codex the
# script re-runs itself in the background and the hook returns at once.
detach_under_codex() {
  [[ "${SAY_HOOKS_CODEX_HOOK:-}" == "1" && "${SAY_HOOKS_BACKGROUND:-}" != "1" ]] || return 0
  SAY_HOOKS_BACKGROUND=1 nohup bash "$1" >/dev/null 2>&1 &
  exit 0
}

# Epoch mtime of a file, or 0 when it is absent. BSD stat on macOS, GNU stat elsewhere.
_file_mtime() {
  [[ -f "$1" ]] || { echo 0; return; }
  if stat --version >/dev/null 2>&1; then
    stat -c %Y "$1"
  else
    stat -f %m "$1"
  fi
}

# Succeeds when the hook should stay silent. STACKVOX_ALWAYS_SPEAK=1 never skips.
should_skip() {
  [[ "${STACKVOX_ALWAYS_SPEAK:-}" == "1" ]] && return 1
  rate_limited || is_hosting_terminal_focused
}

# Succeeds when a hook in this directory spoke under RATE_LIMIT_SECONDS ago, and
# otherwise records now. Per directory, so another repo's session never silences this one.
rate_limited() {
  local stamp now
  mkdir -p "$CACHE_DIR"
  stamp="$CACHE_DIR/$(printf '%s' "$PWD" | shasum -a 1 2>/dev/null | cut -c1-12).last"
  now=$(date +%s)
  (( now - $(_file_mtime "$stamp") < RATE_LIMIT_SECONDS )) && return 0
  echo "$now" > "$stamp"
  return 1
}

# macOS only: walks up from $PPID to the terminal hosting the session and
# succeeds when it is the frontmost application. Anything undetermined is "not focused".
is_hosting_terminal_focused() {
  [[ "$(uname)" == "Darwin" ]] || return 1
  command -v osascript >/dev/null || return 1

  local pid="$PPID" host_pid="" name
  while [[ "$pid" -gt 1 ]]; do
    name=$(ps -o comm= -p "$pid" 2>/dev/null | awk -F/ '{print $NF}')
    if [[ "$name" =~ $TERMINAL_NAMES_PATTERN ]]; then
      host_pid="$pid"
      break
    fi
    pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
    [[ -z "$pid" ]] && return 1
  done
  [[ -z "$host_pid" ]] && return 1

  local front
  front=$(osascript -e 'tell application "System Events" to get unix id of first application process whose frontmost is true' 2>/dev/null)
  [[ "$host_pid" == "$front" ]]
}

# The value of `<field>:` in the config file's YAML frontmatter, without quotes
# or a trailing `# comment`; empty when absent.
_read_config_field() {
  [[ -f "$CONFIG_FILE" ]] || return
  awk -v field="$1" '
    /^---[[:space:]]*$/ { f = !f; next }
    f && $0 ~ "^[[:space:]]*" field ":" {
      sub("^[[:space:]]*" field ":[[:space:]]*", "")
      sub(/[[:space:]]*#.*/, "")
      gsub(/^[[:space:]"'\'']+|[[:space:]"'\'']+$/, "")
      print
      exit
    }
  ' "$CONFIG_FILE"
}

read_config_voice() {
  local v
  v=$(_read_config_field voice)
  echo "${v:-$DEFAULT_VOICE}"
}

read_config_speed() {
  local s
  s=$(_read_config_field speed)
  echo "${s:-$DEFAULT_SPEED}"
}

# The phrases/ file for a voice, by its prefix.
voice_to_lang() {
  case "${1:0:2}" in
    af|am|bf|bm) echo "en" ;;
    ff)          echo "fr" ;;
    hf|hm)       echo "hi" ;;
    if|im)       echo "it" ;;
    pf|pm)       echo "pt" ;;
    *)           echo "en" ;;
  esac
}

# The --lang code stackvox expects for a voice, by its prefix.
voice_to_kokoro_lang() {
  case "${1:0:2}" in
    af|am) echo "en-us" ;;
    bf|bm) echo "en-gb" ;;
    ff)    echo "fr-fr" ;;
    hf|hm) echo "hi" ;;
    if|im) echo "it" ;;
    pf|pm) echo "pt-br" ;;
    *)     echo "en-us" ;;
  esac
}

# Defines TEMPLATES_RESPONSE and TEMPLATES_NOTIFICATION for a language, falling back to English.
load_phrases() {
  # shellcheck source=../phrases/en.sh
  source "$SAY_HOOKS_ROOT/phrases/$1.sh" 2>/dev/null || source "$SAY_HOOKS_ROOT/phrases/en.sh"
}

# repo_label <spelling>...: the directory name split into words on - and _, with
# each word that matches a listed spelling spelt out as capital letters.
repo_label() {
  local word parts=()
  for word in $(basename "$PWD" | tr '_-' '  '); do
    case " $* " in
      *" $word "*) word=$(printf '%s' "$word" | tr '[:lower:]' '[:upper:]' | sed 's/./& /g; s/ $//') ;;
    esac
    parts+=("$word")
  done
  echo "${parts[*]}"
}

# announce <array name>: speak a random phrase from that array, labelled with the
# repo, in the configured voice through stackvox, or in English through macOS `say`.
announce() {
  local voice speed lang=en repo
  if command -v stackvox-say >/dev/null; then
    voice=$(read_config_voice)
    speed=$(read_config_speed)
    lang=$(voice_to_lang "$voice")
    # Kokoro reads most acronyms correctly; `say` needs more of them spelt out.
    repo=$(repo_label cli CLI)
  else
    repo=$(repo_label mcp MCP api API cli CLI hris HRIS ai AI)
  fi

  load_phrases "$lang"
  local ref="$1[@]"
  local templates=("${!ref}")
  local sentence
  # shellcheck disable=SC2059
  sentence=$(printf "${templates[RANDOM % ${#templates[@]}]}" "$repo")

  if command -v shlock >/dev/null; then
    mkdir -p "$CACHE_DIR"
    until shlock -f "$SPEECH_LOCK" -p $$ 2>/dev/null; do sleep 0.2; done
    trap 'rm -f "$SPEECH_LOCK"' EXIT
  fi

  if command -v stackvox-say >/dev/null; then
    stackvox-say --voice "$voice" --lang "$(voice_to_kokoro_lang "$voice")" --speed "$speed" "$sentence"
  else
    say "$sentence"
  fi
}
