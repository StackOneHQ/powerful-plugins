---
name: browser-recorder
description: Capture a web app as 1920x1080 screenshots and 60fps video clips from a shot list, with a click and scroll event log for video editing (Remotion). Use for product demo footage, feature launch clips, screen recordings of a web flow, or marketing screenshots of an app.
metadata:
  tags: browser, recording, video, screenshots, automation, 1password
---

# Browser Recorder

Use this skill to capture browser sessions as screenshots and video clips, with structured event logging for Remotion post-processing. Always work from a `shot-list.json` file.

This skill covers capture only. Browser choice, safety rules and signing in come from the
`browser-automation` skill in the same marketplace; turning the output into a video is the
`video-creator` agent in `animation-studio`.

## Choose the capture tool

- **Screenshots and mockups**: pick the browser with the order in `browser-automation`: the
  agent's own browser, then a connected browser MCP server, then `agent-browser`, then
  Playwright. Use the first one that can set a 1920x1080 viewport and save a PNG, and sign in
  and capture in that same browser.
- **Video clips**: need a tool that records. The steps below use `agent-browser record`, which
  honours the scene's `fps` up to 60. Without it, fall back to a Playwright script:

  ```js
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },           // without this the page is 1280x720
    recordVideo: { dir: 'video-capture/assets', size: { width: 1920, height: 1080 } },
  });
  // ...load saved state, run the scene's actions...
  await context.close();                               // flushes the video file
  ```

  Rename the saved file to `<scene id>.webm`. Playwright records at about 25fps whatever the
  scene asks for, so set that scene's `fps` in `events.json` to 25 and tell the person when a scene
  wanted more. A GIF recorder in the agent's own browser only suits a quick preview, not footage
  for a composition.

When the clips need a logged-in app, sign in once in the recording browser and save its state,
so every scene starts signed in.

## Shot List Format

`video-capture/shot-list.json` (relative to the working directory) describes every scene to capture. Schema:

```typescript
interface Scene {
  id: string;                        // Unique scene identifier (used as filename stem)
  description: string;               // Human-readable description for logging
  url: string;                       // URL to navigate to
  auth_domain?: string;              // Domain key for 1Password lookup (e.g. "app.example.com")
  capture_mode: "screenshot"         // Single PNG at 1920x1080
               | "video_clip"        // WebM clip with event logging
               | "mockup";           // Full-page screenshot (--full flag)
  actions?: Action[];                // Steps to execute before/during capture
  duration_seconds?: number;         // For video_clip: how long to record (default: 5)
  fps?: number;                      // For video_clip: capture rate, 1-60 (this skill uses 60 when unset)
  caption?: string;                  // Overlay text for the Remotion composition
  zoom_target?: string;              // CSS selector to zoom into (drives a zoom-on-click effect in the composition)
}

interface Action {
  type: "click" | "wait" | "scroll" | "fill" | "hover" | "navigate";
  selector?: string;                 // CSS selector or @ref from snapshot
  value?: string;                    // For fill actions
  deltaY?: number;                   // For scroll actions
  url?: string;                      // For navigate actions
  ms?: number;                       // For wait actions (milliseconds)
}
```

### Example shot-list.json

```json
{
  "scenes": [
    {
      "id": "scene-1",
      "description": "Dashboard overview, the logged-in landing page",
      "url": "https://app.example.com/dashboard",
      "auth_domain": "app.example.com",
      "capture_mode": "screenshot",
      "actions": [
        { "type": "wait", "ms": 800 }
      ],
      "caption": "Everything on one screen."
    },
    {
      "id": "scene-2",
      "description": "Open the first project and scroll through its settings",
      "url": "https://app.example.com/projects",
      "auth_domain": "app.example.com",
      "capture_mode": "video_clip",
      "duration_seconds": 6,
      "fps": 60,
      "actions": [
        { "type": "wait", "ms": 500 },
        { "type": "click", "selector": ".project-card:first-child" },
        { "type": "wait", "ms": 1000 },
        { "type": "scroll", "deltaY": 300 }
      ],
      "caption": "Settings live next to the work.",
      "zoom_target": ".project-card:first-child"
    },
    {
      "id": "scene-3",
      "description": "Full-page API reference",
      "url": "https://docs.example.com/api-reference",
      "capture_mode": "mockup",
      "caption": "The full API reference."
    }
  ]
}
```

## Sign in once per domain

1. Collect the domains that need a login:

   ```bash
   node -e "
   const sl = JSON.parse(require('fs').readFileSync('video-capture/shot-list.json','utf-8'));
   console.log(JSON.stringify([...new Set(sl.scenes.filter(s=>s.auth_domain).map(s=>s.auth_domain))]));
   "
   ```

2. For each domain, reuse saved state if it exists. Otherwise sign in as described in
   `browser-automation` (section 5): the person signs in in a headed window, which covers SSO and
   two-factor prompts, or you fill credentials from their password manager with their go-ahead.
   Use a dedicated demo account where possible, since its data ends up on screen.

   ```bash
   mkdir -p video-capture/.auth
   printf '*\n' > video-capture/.auth/.gitignore   # keep session cookies out of git
   agent-browser open --headed "https://${DOMAIN}/login"
   # ...person signs in, or credentials are filled...
   agent-browser wait --load networkidle
   agent-browser snapshot -i   # confirm a signed-in page (avatar, account menu) before saving
   agent-browser state save "video-capture/.auth/${DOMAIN}.json"
   ```

3. Before each scene on that domain, load the state:

   ```bash
   agent-browser state load "video-capture/.auth/${DOMAIN}.json"
   ```

   If a scene lands on a login page, reload the state and retry once, then stop and ask.

Saved state holds live session cookies. The `.gitignore` above keeps `video-capture/.auth/` out
of version control; delete the folder when the capture is done.

## Screenshot Capture

For each scene with `capture_mode: "screenshot"` or `"mockup"`:

```bash
SCENE_ID="scene-1"
SCENE_URL="https://app.example.com/dashboard"
OUTPUT="video-capture/assets/${SCENE_ID}.png"
mkdir -p video-capture/assets

# Load auth state if needed
agent-browser state load video-capture/.auth/app.example.com.json

agent-browser open "${SCENE_URL}"
agent-browser wait --load networkidle

# Execute any pre-screenshot actions from the shot list
# e.g. agent-browser wait 800

agent-browser set viewport 1920 1080

# For capture_mode "screenshot":
agent-browser screenshot "${OUTPUT}"

# For capture_mode "mockup" (full-page):
agent-browser screenshot --full "${OUTPUT}"
```

Tips:
- Use `agent-browser wait 500` after navigation for animations to settle before capturing
- Use `agent-browser scroll down 300` to bring elements into view before screenshot
- Snapshot first if you need to verify elements are present: `agent-browser snapshot -i`
- Always set viewport to 1920x1080 with `agent-browser set viewport 1920 1080` before capturing

## Video Clip Capture

Recording needs `ffmpeg` on `PATH`. Check before capturing anything, because `record start`
fails without it:

```bash
agent-browser doctor    # reports missing ffmpeg, among other things
```

If `ffmpeg` is missing, install it (`apt install ffmpeg` / `brew install ffmpeg`) or stop and
tell the user. Do not fall back to screenshots and call the scene captured.

For each scene with `capture_mode: "video_clip"`:

```bash
SCENE_ID="scene-2"
SCENE_URL="https://app.example.com/projects"
DURATION=6
FPS=60   # scene.fps, or 60 by default
OUTPUT="video-capture/assets/${SCENE_ID}.webm"
RECORDING_START_MS=$(node -e 'console.log(Date.now())')   # portable; BSD date has no %N

# Load auth state if needed
agent-browser state load video-capture/.auth/app.example.com.json

agent-browser open "${SCENE_URL}"
agent-browser wait --load networkidle
agent-browser set viewport 1920 1080

# Start recording
agent-browser record start "${OUTPUT}" --fps "${FPS}"

# Execute actions with natural timing between steps
agent-browser wait 500
agent-browser click @e1   # snapshot first to get refs if needed
agent-browser wait 1000
agent-browser scroll down 300

# Stop recording after duration
agent-browser wait $((DURATION * 1000))
agent-browser record stop --json   # reports frames and capturedFrames
```

Notes:
- Frames come from Chrome's screencast. `--fps` accepts 1 to 60 and defaults to 30 when
  omitted; capture at 60 unless the scene says otherwise, because product clips are mostly
  scroll, hover, and click motion
- Distinct frames are bounded by how often the page repaints, so a page that renders below
  60fps records below it too. `record stop --json` reports `frames` written and
  `capturedFrames` actually produced. A large gap means the page was static, not that the
  capture failed
- 60fps roughly doubles the bitrate of 30fps. That is fine for 3 to 8 second clips; drop to
  30 for anything longer than about 20 seconds
- Playback duration always matches wall clock, so a slow page holds frames rather than
  speeding the clip up. A gap longer than five seconds is held for five and the rest dropped
- Pass a `.webm` or `.mp4` output path; `ffmpeg` encodes either, so no transcode step
- Keep clips between 3 and 8 seconds for best composition results
- For actions that require fresh refs, run `agent-browser snapshot -i` before the recording starts, then use the refs during recording. Do not snapshot mid-recording as it pauses execution

## Event Logging

Build `events.json` incrementally as you capture each scene. Each scene records the `fps` it was
actually captured at, which can be lower than the shot list asked for. Track clicks, scrolls, and navigation with timestamps relative to recording start.

### events.json schema

```json
{
  "scenes": [
    {
      "scene_id": "scene-2",
      "recording_file": "assets/scene-2.webm",
      "fps": 60,
      "viewport": { "width": 1920, "height": 1080 },
      "events": [
        { "type": "navigate", "url": "https://app.example.com/projects", "timestamp_ms": 0 },
        { "type": "click", "x": 450, "y": 320, "selector": ".project-card:first-child", "timestamp_ms": 1200 },
        { "type": "scroll", "deltaY": 300, "timestamp_ms": 2800 }
      ]
    }
  ]
}
```

### Getting click coordinates

Before recording a video clip, snapshot the page and note element positions:

```bash
agent-browser open "${SCENE_URL}"
agent-browser wait --load networkidle
agent-browser snapshot -i        # find the ref of the element you will click, e.g. @e3
agent-browser get box @e3        # prints x, y, width, height in viewport pixels
```

`snapshot -i` lists refs and roles only, with no coordinates. Use the centre of the box from
`get box` as the click event's `x`/`y`: `x + width / 2` and `y + height / 2`.

### Timestamp tracking

- Timestamps are milliseconds relative to when `agent-browser record start` was called for that scene
- Approximate timestamps from the cumulative wait times between actions
- Example: if you wait 500ms before clicking, the click timestamp is ~500ms

### Write events.json

After all scenes are captured, write `events.json`:

```bash
node -e "
const events = {
  scenes: [
    {
      scene_id: 'scene-2',
      recording_file: 'assets/scene-2.webm',
      fps: 60,
      viewport: { width: 1920, height: 1080 },
      events: [
        { type: 'navigate', url: 'https://app.example.com/projects', timestamp_ms: 0 },
        { type: 'click', x: 450, y: 320, selector: '.project-card:first-child', timestamp_ms: 1200 },
        { type: 'scroll', deltaY: 300, timestamp_ms: 2800 }
      ]
    }
  ]
};
require('fs').writeFileSync('video-capture/events.json', JSON.stringify(events, null, 2));
console.log('events.json written');
"
```

## Output Verification

After capturing all scenes, verify outputs:

```bash
# List assets and check sizes
ls -lh video-capture/assets/

# Validate events.json is valid JSON
node -e "JSON.parse(require('fs').readFileSync('video-capture/events.json','utf-8')); console.log('events.json valid');"

# Check each expected asset exists
node -e "
const sl = JSON.parse(require('fs').readFileSync('video-capture/shot-list.json','utf-8'));
const fs = require('fs');
for (const scene of sl.scenes) {
  const ext = scene.capture_mode === 'video_clip' ? 'webm' : 'png';
  const path = \`video-capture/assets/\${scene.id}.\${ext}\`;
  const exists = fs.existsSync(path);
  const size = exists ? fs.statSync(path).size : 0;
  console.log(\`\${scene.id}.\${ext}: \${exists ? size + ' bytes' : 'MISSING'}\`);
}
"
```

Flag any missing or zero-byte files and recapture before declaring done.

## Troubleshooting

| Problem | Likely cause | Fix |
|---------|-------------|-----|
| `op: command not found` | 1Password CLI not installed | Install `op` CLI, or ask user to provide credentials manually |
| `agent-browser: command not found` | CLI not installed | Run `npm install -g agent-browser` |
| `record start` fails or `--fps` is rejected | `ffmpeg` missing, or `agent-browser` older than 0.37.0 | Install `ffmpeg`; run `agent-browser doctor`, then `npm install -g agent-browser@latest` |
| Login redirects back to login page | Expired state, wrong credentials, or a two-factor prompt | Reload state; check the vault item; ask the person to complete the sign-in |
| Recording file is 0 bytes or empty | `record stop` called too fast | Add more wait time; ensure at least 1s of recording |
| Google SSO shows "access blocked" | Google blocks automated sign-in | Ask the person to sign in in the headed window, then save state |
| Auth state expired mid-session | Session cookie expired | Re-run the login flow for the affected domain and save new state |
| Snapshot refs wrong after navigation | Page changed since last snapshot | Always re-snapshot after any navigation; old refs are invalid |
