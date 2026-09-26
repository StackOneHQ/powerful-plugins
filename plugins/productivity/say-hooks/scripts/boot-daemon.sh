#!/bin/bash
# SessionStart: start the stackvox daemon unless it is missing or already running.
# Without stackvox the other hooks fall back to macOS `say`.

command -v stackvox >/dev/null || exit 0
stackvox status >/dev/null 2>&1 && exit 0

mkdir -p "$HOME/.cache/stackvox"
nohup stackvox serve >"$HOME/.cache/stackvox/daemon.log" 2>&1 &
disown
