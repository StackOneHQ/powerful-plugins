# Narration and timing

Prefer an available local speech engine when the user has no provider preference.
The optional [stackvox](https://github.com/StackOneHQ/stackvox) CLI can synthesize
to WAV without a hosted API:

```bash
stackvox speak --file scene.txt --out scene.wav
```

Check the installed CLI's help before using optional arguments. Stackvox downloads
its model on first use; use it offline once its model is cached. Installing it is
optional, not a hook or a prerequisite for other plugin features. If it is absent,
use an available system speech engine or ask which speech option the user wants
when narration is essential. Do not silently return a silent video as narrated.

A user-authorized hosted provider is also acceptable. Read credentials from the
user's existing configuration, never place them in source files, output metadata,
commands shown to the user or logs. Send only the narration needed for synthesis.

Synthesize per scene so a wording change only invalidates that scene's audio.
Measure duration from the WAV or another media probe rather than estimating it
from word count. Use ceiling when converting seconds to frames. A scene must last
through the final sample plus any intended hold. Do not speed up speech merely
to fit a previously guessed duration.

## Timeline checker

`scripts/check_timeline.py` uses Python's standard library. It reads a JSON plan
and PCM WAV files inside the plan's directory. It never plays audio, downloads
software, contacts a service or changes source files.

```json
{
  "fps": 30,
  "total_frames": 180,
  "scenes": [
    {
      "id": "first-attempt",
      "start_frame": 0,
      "end_frame": 180,
      "audio": "scene.wav",
      "transcript": "The first attempt waits one second.",
      "captions": [
        {"start_frame": 0, "end_frame": 150,
         "text": "The first attempt waits one second."}
      ]
    }
  ]
}
```

Scene and caption ranges are half-open and use absolute frames. Scenes must be
contiguous; make an intentional silent gap a scene with `audio: null`, an empty
transcript and no captions. Narrated scenes need captions whose combined text
matches the transcript after whitespace normalization. Caption timing still needs
a listening check: matching words and ranges cannot prove synchronization.

Exit 0 means the declared timeline and WAV durations are consistent; 1 means a
timing or content mismatch; 2 means the input could not be checked. The final
render may differ from the plan: inspect its audio, duration and frames separately.
