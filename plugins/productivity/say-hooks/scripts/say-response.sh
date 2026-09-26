#!/bin/bash
# Stop hook: announce that the turn finished, labelled with the repo name.

set -u

# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
detach_under_codex "$0"

command -v stackvox-say >/dev/null || command -v say >/dev/null || exit 0
should_skip && exit 0

announce TEMPLATES_RESPONSE
