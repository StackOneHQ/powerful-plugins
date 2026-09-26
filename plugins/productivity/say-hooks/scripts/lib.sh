#!/bin/bash
# Shared helpers for say-hooks. Sourced by say-*.sh scripts.

DEFAULT_VOICE="af_heart"
DEFAULT_SPEED="1.0"
CONFIG_FILE="$HOME/.claude/say-hooks.local.md"
RATE_LIMIT_SECONDS=3
# Per-project stamp: hash $PWD so two sessions in different repos get
# independent rate limits, but repeat hooks in the same repo debounce.
RATE_LIMIT_STAMP="/tmp/claude-say.$(printf '%s' "$PWD" | shasum -a 1 2>/dev/null | cut -c1-12).last"

TERMINAL_NAMES_PATTERN='^(iTerm2|Terminal|Alacritty|kitty|Ghostty|Warp|WezTerm|Hyper|Tabby|Code|Cursor|Electron)$'

# _file_mtime — epoch mtime of a file. Handles BSD stat (macOS default) and
# GNU stat (Linux, or macOS with coreutils on PATH). Returns 0 if file is absent.
_file_mtime() {
  [[ -f "$1" ]] || { echo 0; return; }
  if stat --version >/dev/null 2>&1; then
    stat -c %Y "$1"
  else
    stat -f %m "$1"
  fi
}

# should_skip — returns 0 (skip) when the hook should stay silent.
# Honors STACKVOX_ALWAYS_SPEAK=1 to bypass both checks.
should_skip() {
  [[ "${STACKVOX_ALWAYS_SPEAK:-}" == "1" ]] && return 1
  rate_limited && return 0
  is_hosting_terminal_focused && return 0
  return 1
}

# rate_limited — 0 if the previous hook fired within RATE_LIMIT_SECONDS.
# Side effect: on non-skip, touches the stamp file so the next call sees us.
rate_limited() {
  local now age mtime
  now=$(date +%s)
  if [[ -f "$RATE_LIMIT_STAMP" ]]; then
    mtime=$(_file_mtime "$RATE_LIMIT_STAMP")
    age=$(( now - mtime ))
    if (( age < RATE_LIMIT_SECONDS )); then
      return 0
    fi
  fi
  echo "$now" > "$RATE_LIMIT_STAMP"
  return 1
}

# is_hosting_terminal_focused — macOS only. Walks up from $PPID to find the
# terminal process that ultimately hosts Claude Code, then checks whether that
# PID is the frontmost application. Returns 0 if focused, 1 otherwise.
# Returns 1 (not focused) on non-macOS or if we can't determine.
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

# _read_config_field — pulls `<field>: value` from YAML frontmatter.
# Strips surrounding whitespace + quotes and drops trailing `# comment`.
# Empty string if absent.
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

# read_config_voice — returns configured voice or DEFAULT_VOICE.
read_config_voice() {
  local v
  v=$(_read_config_field voice)
  echo "${v:-$DEFAULT_VOICE}"
}

# read_config_speed — returns configured speed (as float string) or DEFAULT_SPEED.
read_config_speed() {
  local s
  s=$(_read_config_field speed)
  echo "${s:-$DEFAULT_SPEED}"
}

# voice_to_lang — maps voice prefix to phrase-file language code (en/fr/hi/it/pt).
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

# voice_to_kokoro_lang — maps voice prefix to the --lang code stackvox expects.
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

# repo_name_raw — basename of PWD, normalized for Kokoro pronunciation.
# Kokoro reads most acronyms correctly, so we only expand the ones it gets wrong.
repo_name_raw() {
  local repo parts=() word
  repo=$(basename "$PWD")
  for word in $(echo "$repo" | tr '_-' '  '); do
    case "$word" in
      cli|CLI)           word="C L I" ;;
    esac
    parts+=("$word")
  done
  echo "${parts[*]}"
}

# repo_name_expanded — English-phonetic form for the macOS `say` backend.
# Letter-splits common acronyms so `say` pronounces them correctly.
repo_name_expanded() {
  local repo parts=() word
  repo=$(basename "$PWD")
  for word in $(echo "$repo" | tr '_-' '  '); do
    case "$word" in
      mcp|MCP)           word="M C P" ;;
      api|API)           word="A P I" ;;
      cli|CLI)           word="C L I" ;;
      hris|HRIS)         word="H R I S" ;;
      ai|AI)             word="A I" ;;
    esac
    parts+=("$word")
  done
  echo "${parts[*]}"
}
