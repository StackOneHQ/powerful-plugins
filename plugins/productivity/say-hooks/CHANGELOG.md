# Changelog

All notable changes to `say-hooks` are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions track `.claude-plugin/plugin.json`.

## [1.1.0]

### Changed

- `/stackvox-install` asks before installing pipx, which is a separate package; running the command covers stackvox only.
- `/stackvox-uninstall` deletes the ~340MB model cache only on an explicit yes.
- `/stackvox-upgrade` restarts the daemon when a step fails after stopping it, so the hooks keep speaking.
- `/stackvox-configure` previews a voice the user already named without showing the full list, and keeps the existing speed on a voice-only change.
- Command wording now reads the same in Claude Code and Codex.

## [1.0.0]

### Added

- Stop, Notification and SessionStart hooks that speak the current repo's status, with stackvox (offline Kokoro-82M) voices and a macOS `say` fallback.
- Codex hooks for SessionStart and Stop.
- `/stackvox-install`, `/stackvox-configure`, `/stackvox-upgrade` and `/stackvox-uninstall` commands.
- Voices in English, French, Hindi, Italian and Brazilian Portuguese, a speed setting, per-repo rate limiting and a skip when the terminal is already in focus.
