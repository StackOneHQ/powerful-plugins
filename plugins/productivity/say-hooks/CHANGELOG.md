# Changelog

All notable changes to `say-hooks` are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions track `.claude-plugin/plugin.json`.

## [1.0.0]

### Added

- Stop, Notification and SessionStart hooks that speak the current repo's status, with stackvox (offline Kokoro-82M) voices and a macOS `say` fallback.
- Codex hooks for SessionStart and Stop.
- `/stackvox-install`, `/stackvox-configure`, `/stackvox-upgrade` and `/stackvox-uninstall` commands.
- Voices in English, French, Hindi, Italian and Brazilian Portuguese, a speed setting, per-repo rate limiting and a skip when the terminal is already in focus.
