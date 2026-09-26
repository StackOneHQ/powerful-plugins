#!/bin/bash
# Idempotent daemon boot. Runs on SessionStart. No-op if stackvox is
# not installed (plugin still works via `say` fallback).

command -v stackvox >/dev/null || exit 0
stackvox status >/dev/null 2>&1 && exit 0

mkdir -p "$HOME/.cache/stackvox"
nohup stackvox serve >"$HOME/.cache/stackvox/daemon.log" 2>&1 &
disown
