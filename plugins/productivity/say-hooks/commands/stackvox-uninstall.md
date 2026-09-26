---
description: Uninstall stackvox and remove its cached models
---

Uninstall stackvox and clean up its cache. Hooks will fall back to macOS `say` after this.

## Steps

1. **Stop the daemon** (ignore error if not running):
   ```
   stackvox stop 2>/dev/null || true
   ```

2. **Ask the user whether they want to also delete the model cache** (~340MB at `~/.cache/stackvox/`).
   - If yes: `rm -rf "$HOME/.cache/stackvox"`
   - If no: leave the cache so reinstalling later is fast.

3. **Uninstall via pipx:**
   ```
   pipx uninstall stackvox
   ```

4. **Remove the plugin's check-stamp file:**
   ```
   rm -f "$HOME/.cache/say-hooks/last-check"
   ```

5. Confirm uninstall and remind the user the hooks still work via `say` on macOS.
