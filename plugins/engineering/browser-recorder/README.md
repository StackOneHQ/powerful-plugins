# browser-recorder

Records browser interactions with authentication support. Produces raw screenshots, video clips, and a structured mouse event log for video post-processing.

## Installation

```bash
# Claude Code
/plugin marketplace add StackOneHQ/powerful-plugins
/plugin install browser-recorder@powerful-plugins

# Codex
codex plugin marketplace add StackOneHQ/powerful-plugins
codex plugin add browser-recorder@powerful-plugins
```

## What It Does

This plugin handles the **capture phase** of a video production pipeline. It reads a `shot-list.json` file, signs in once to each domain that needs it, captures screenshots and video clips, and writes a structured `events.json` alongside all assets.

The output is built for a Remotion composition, where `events.json` drives an animated cursor and zoom-on-click effects. The [`animation-studio`](../../design/animation-studio/README.md) plugin's `video-creator` agent handles that step.

## Skills

| Skill | Triggers When |
|-------|---------------|
| `browser-recorder` | "record a browser session", "capture screenshots of", "record video of website", "capture product demo" |

## Output Structure

```
video-capture/
  shot-list.json        # Input: scenes to capture
  events.json           # Output: structured mouse event log per scene
  assets/
    scene-1.png         # Screenshot (capture_mode: screenshot)
    scene-2.webm        # Video clip (capture_mode: video_clip)
    scene-3.png         # Mockup screenshot (capture_mode: mockup)
```

## Features

- **Shot list driven**: define scenes with URLs, actions, captions, and zoom targets in one JSON file
- **Sign-in once per domain**: reuses saved state, or you sign in yourself in a headed window (which covers SSO and two-factor prompts), or it fills credentials from your password manager with your go-ahead. The signed-in state is saved under `video-capture/.auth/` so every scene starts signed in; keep that folder out of version control. Sign-in rules come from the `browser-automation` skill
- **Screenshot capture**: 1920x1080, PNG, full-page support
- **Video clip capture**: WebM or MP4 from Chrome's screencast, 3 to 8 second clips at 60fps unless a scene sets `fps` (1 to 60); needs `ffmpeg`
- **Event logging**: per-scene click/scroll/navigate events with relative timestamps for Remotion post-processing
- **Output verification**: file size checks and events.json validation after capture

## Pairing with a Remotion composition

```
shot-list.json
    │
    ▼
browser-recorder         →  assets/ + events.json
    │
    ▼
Remotion composition     →  final video (MP4)
```

`events.json` carries click coordinates and timestamps. A composition reads them to move an animated cursor and to zoom in on each click. `animation-studio` (`video-creator` agent) can build that composition.

## Requirements

| Tool | Required | Notes |
|------|----------|-------|
| `agent-browser` | Recommended | The default recorder for video clips; screenshots can use the agent's own browser, and Playwright is the fallback |
| `ffmpeg` | Yes | Video encoding and clip assembly |
| `op` (1Password CLI) | Optional | To fill credentials from a vault, with your go-ahead |

Install `agent-browser`:
```bash
npm install -g agent-browser
agent-browser install
```

For general browser driving, see the [`browser-automation`](../browser-automation/README.md) plugin.

## Contributing

See [CONTRIBUTING.md](../../../CONTRIBUTING.md).
