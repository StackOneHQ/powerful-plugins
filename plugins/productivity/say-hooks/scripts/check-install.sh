#!/bin/bash
# Weekly check: is stackvox installed? Is the installed version behind PyPI?
# Prints a one-line hint to stderr at most once per 7 days. Never installs
# or upgrades automatically — user must run /stackvox-install or /stackvox-upgrade.

if [[ "${SAY_HOOKS_CODEX_HOOK:-}" == "1" && "${SAY_HOOKS_BACKGROUND:-}" != "1" ]]; then
  SAY_HOOKS_BACKGROUND=1 nohup bash "$0" >/dev/null 2>&1 &
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

cache_dir="$HOME/.cache/say-hooks"
stamp="$cache_dir/last-check"
mkdir -p "$cache_dir"

now=$(date +%s)
mtime=$(_file_mtime "$stamp")
(( mtime > 0 && now - mtime < 604800 )) && exit 0

if ! command -v stackvox >/dev/null; then
  echo "[say-hooks] stackvox not installed. Run /stackvox-install for high-quality voices" >&2
  touch "$stamp"
  exit 0
fi

# Missing curl/pipx/python3 or unreachable PyPI: exit without stamping so we retry
# next session instead of swallowing the check for 7 days.
command -v curl >/dev/null || exit 0
command -v pipx >/dev/null || exit 0
command -v python3 >/dev/null || exit 0

installed=$(pipx list --short 2>/dev/null | awk '$1 == "stackvox" {print $2; exit}')
[[ -z "$installed" ]] && exit 0

latest=$(curl -fsSL --max-time 5 https://pypi.org/pypi/stackvox/json 2>/dev/null \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["info"]["version"])' 2>/dev/null)
[[ -z "$latest" ]] && exit 0
touch "$stamp"

# Only warn when the installed version is strictly older than PyPI's latest.
# `sort -V` orders versions naturally; if the smallest version is not `$latest`,
# then `$installed` is ≥ `$latest` (newer or equal) and we stay silent — so dev
# builds and pre-releases don't trip a false "update available" hint.
oldest=$(printf '%s\n%s\n' "$installed" "$latest" | sort -V | head -1)
if [[ "$installed" != "$latest" && "$oldest" == "$installed" ]]; then
  echo "[say-hooks] stackvox update available ($installed → $latest). Run /stackvox-upgrade" >&2
fi
