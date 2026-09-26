#!/bin/bash
# SessionStart, at most once every 7 days: a one-line hint on stderr when stackvox
# is missing or behind PyPI. It never installs or upgrades anything; the user
# runs /stackvox-install or /stackvox-upgrade.

# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
detach_under_codex "$0"

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
for tool in curl pipx python3; do command -v "$tool" >/dev/null || exit 0; done

installed=$(pipx list --short 2>/dev/null | awk '$1 == "stackvox" {print $2; exit}')
[[ -z "$installed" ]] && exit 0

latest=$(curl -fsSL --max-time 5 https://pypi.org/pypi/stackvox/json 2>/dev/null \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["info"]["version"])' 2>/dev/null)
[[ -z "$latest" ]] && exit 0
touch "$stamp"

# Warn only when installed sorts strictly before latest, so a dev build or
# pre-release ahead of PyPI stays silent.
oldest=$(printf '%s\n%s\n' "$installed" "$latest" | sort -V | head -1)
if [[ "$installed" != "$latest" && "$oldest" == "$installed" ]]; then
  echo "[say-hooks] stackvox update available ($installed → $latest). Run /stackvox-upgrade" >&2
fi
