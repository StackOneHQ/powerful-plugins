---
description: Upgrade stackvox to the latest release on PyPI
---

Upgrade stackvox to the latest release on PyPI. Run the steps in order. If a step fails after the daemon has been stopped, restart it (step 5) so the hooks keep speaking, then report which step failed and stop.

## Steps

1. **Check stackvox is installed.** If `command -v stackvox` fails, stop and point the user to the stackvox-install command.

2. **Stop the running daemon** so the upgrade doesn't replace a binary in use:
   ```
   stackvox stop 2>/dev/null || true
   ```

3. **Upgrade via pipx:**
   ```
   pipx install --force stackvox
   ```

4. **Play the stackvox welcome** to confirm the upgraded binary works:
   ```
   stackvox welcome
   ```

5. **Restart the daemon:**
   ```
   nohup stackvox serve > "$HOME/.cache/stackvox/daemon.log" 2>&1 &
   disown
   ```

6. Report the new version and confirm the daemon is running.
