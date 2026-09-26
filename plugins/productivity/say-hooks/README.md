# say-hooks

Speaks up when your coding agent finishes a turn or is blocked waiting for you, so you can look away from the terminal.

## What it does

- **Stop**: when a turn ends, says something like "payments service is ready for you".
- **Notification** (Claude Code only): when Claude is blocked on a permission prompt or an idle timeout, says something like "payments service is blocked".
- **SessionStart**: boots the `stackvox` daemon if it's installed, so speech starts instantly, and runs a weekly install and update check.

The label is the current directory's name, split on hyphens and underscores, with acronyms the speech engine gets wrong spelled out (MCP becomes "M C P", API becomes "A P I", CLI becomes "C L I"). A shared lock in `~/.cache/say-hooks/` stops concurrent sessions from talking over each other.

Codex has no `Notification` event, so in Codex you get the Stop and SessionStart hooks only. Codex hooks cannot run in the background, so the weekly install and update check runs detached there and its hints are not shown; run the stackvox-install or stackvox-upgrade command yourself when you want the better voices or a newer version.

## Installation

```bash
# Claude Code
/plugin marketplace add StackOneHQ/powerful-plugins
/plugin install say-hooks@powerful-plugins

# Codex
codex plugin marketplace add StackOneHQ/powerful-plugins
codex plugin add say-hooks@powerful-plugins
```

That gives you the macOS `say` voice straight away. For the better offline voices, run `/stackvox-install` (see below).

## Two speech backends

| Backend | Quality | Platform | Setup |
|---------|---------|----------|-------|
| **stackvox** (Kokoro-82M, offline neural) | High | macOS + Linux | opt-in, one-time install |
| **macOS `say`** | Stock | macOS only | none: works out of the box |

The hooks prefer `stackvox-say` when it's on PATH and fall back to `say` otherwise. On non-macOS systems without stackvox, they exit silently.

## Installing stackvox

Run `/stackvox-install`. It installs [stackvox](https://github.com/StackOneHQ/stackvox) with `pipx` and starts its local daemon. The daemon loads the Kokoro model once, so each hook call plays in about 13ms instead of starting Python every time.

### Manual install (if you don't want to run the slash command)

```bash
pipx install stackvox
nohup stackvox serve > ~/.cache/stackvox/daemon.log 2>&1 &
```

The first synthesis downloads ~340MB of model files to `~/.cache/stackvox/`.

## Changelog

See [`CHANGELOG.md`](./CHANGELOG.md) for version history.

## Commands

- `/stackvox-install`: install stackvox and start the daemon
- `/stackvox-configure`: pick a voice (with previews) and write it to user config
- `/stackvox-upgrade`: pull the latest stackvox release and restart the daemon
- `/stackvox-uninstall`: remove stackvox and (optionally) its model cache

## Voice & language

The hooks speak in whatever language matches the configured voice:

| Voice prefix | Language |
|--------------|----------|
| `af_*`, `am_*` | American English (en-us) |
| `bf_*`, `bm_*` | British English (en-gb) |
| `ff_*` | French (fr-fr) |
| `hf_*`, `hm_*` | Hindi |
| `if_*`, `im_*` | Italian |
| `pf_*`, `pm_*` | Brazilian Portuguese |

Run `/stackvox-configure` to set the voice, or edit `~/.claude/say-hooks.local.md` directly:

```yaml
---
voice: af_heart
speed: 1.0
---
```

Default voice is `af_heart` (American female, warm). Default speed is `1.0`; the useful range is usually `0.8` to `1.3`.

### Fallback to macOS `say`

When stackvox isn't installed, the hooks fall back to `say`. In that path the language is forced to English regardless of what you've configured (`say` doesn't carry the Kokoro voice set and foreign-language text would be mispronounced).

## Quietness

Two guardrails stop the hooks from being chatty during rapid-fire short turns:

- **Rate limit (per project)**: if a Stop hook fired less than 3 seconds ago *in the same repo*, the next one stays silent. Stamps are keyed by `$PWD`, so sessions in different repos get independent budgets.
- **Focus skip** (macOS only): if the terminal hosting Claude Code is currently the frontmost app, the Stop hook stays silent (you're already looking at the screen). The check walks up from the hook's process to find the specific terminal that launched Claude Code, so multi-terminal setups work correctly.

Both apply to the **Stop** hook only. **Notification** hooks always speak by default: they fire when Claude is blocked and waiting on you, which is exactly when you need to hear it. Set `STACKVOX_QUIET_NOTIFICATIONS=1` if you want the same suppression for notifications.

Override the Stop-hook suppression with `STACKVOX_ALWAYS_SPEAK=1`.

## Update checks

SessionStart runs a lightweight weekly check:
- If stackvox isn't installed → prints a one-line hint suggesting `/stackvox-install`
- If the installed version is behind PyPI → prints a hint suggesting `/stackvox-upgrade`
- Check runs at most once per 7 days (stamped at `~/.cache/say-hooks/last-check`)

Never auto-installs or auto-upgrades: all changes to the user's system go through a slash command.

## Requirements

- **Always:** `bash`. macOS `say` if you want the fallback backend.
- **For stackvox:** `pipx` (installable via Homebrew or `pip --user`). `nc` (BSD netcat: default on macOS, available as `netcat-openbsd` on Linux).
- **Optional:** `curl` for the weekly PyPI update check. `shlock` (ships with macOS) for cross-session serialization.

## Customization

Edit `phrases/*.sh` to change the spoken phrase templates (one file per language). Edit `scripts/lib.sh` to change repo-name normalization and the `say`-backend acronym pronunciation list.

### Picking a stackvox voice

List voices with `stackvox voices`. Pass one via `STACKVOX_VOICE` env var (future) or by editing the scripts to call `stackvox-say --voice bf_emma "$sentence"`.

### Picking a macOS `say` voice

The `say` fallback uses the macOS system voice (System Settings → Accessibility → Read & Speak). Change it there, or edit the scripts to call `say -v "Daniel" "$sentence"`.
