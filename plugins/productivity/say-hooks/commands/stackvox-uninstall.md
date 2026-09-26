---
description: Uninstall stackvox and remove its cached models
---

Uninstall stackvox and clean up its cache. Hooks fall back to macOS `say` after this. Running this command is the user's go-ahead to uninstall stackvox; deleting the model cache needs its own yes. Run the steps in order.

## Steps

1. **Stop the daemon** (ignore error if not running):
   ```
   stackvox stop 2>/dev/null || true
   ```

2. **Ask whether to delete the model cache too** (~340MB at `~/.cache/stackvox/`).
   - Only on an explicit yes: `rm -rf "$HOME/.cache/stackvox"`
   - Otherwise leave the cache, so reinstalling later is fast.

3. **Uninstall via pipx:**
   ```
   pipx uninstall stackvox
   ```

4. **Remove the plugin's check-stamp file:**
   ```
   rm -f "$HOME/.cache/say-hooks/last-check"
   ```

5. Tell the user stackvox is gone and that the hooks still speak through `say` on macOS.
