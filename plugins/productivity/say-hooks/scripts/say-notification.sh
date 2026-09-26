#!/bin/bash
# Notification hook: announce that the session is blocked on the user.

set -u

# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
detach_under_codex "$0"

command -v stackvox-say >/dev/null || command -v say >/dev/null || exit 0
# A blocked session speaks past the rate and focus checks unless STACKVOX_QUIET_NOTIFICATIONS=1.
if [[ "${STACKVOX_QUIET_NOTIFICATIONS:-}" == "1" ]]; then
  should_skip && exit 0
fi

announce TEMPLATES_NOTIFICATION
