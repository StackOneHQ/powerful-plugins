"""Timing failures that would clip speech or misstate the delivered captions."""

import copy
import importlib.util
import tempfile
import unittest
import wave
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / (
    "plugins/design/animation-studio/skills/educational-explainer/scripts/check_timeline.py"
)
SPEC = importlib.util.spec_from_file_location("timeline", SCRIPT)
assert SPEC and SPEC.loader
timeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(timeline)


class TimelineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        with wave.open(str(self.root / "audio.wav"), "wb") as audio:
            audio.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
            audio.writeframes(b"\0\0" * 8000)
        self.plan = {"fps": 30, "total_frames": 45, "scenes": [{
            "id": "one", "start_frame": 0, "end_frame": 45, "audio": "audio.wav",
            "transcript": "Wait one second.", "captions": [
                {"start_frame": 0, "end_frame": 30, "text": "Wait one second."}
            ],
        }]}

    def test_valid_timing(self):
        self.assertEqual(timeline.check(self.plan, self.root), [])

    def test_clipped_audio_fails(self):
        self.plan["total_frames"] = 20
        self.plan["scenes"][0]["end_frame"] = 20
        self.assertIn("one: narration exceeds scene duration", timeline.check(self.plan, self.root))

    def test_changed_caption_fails(self):
        self.plan["scenes"][0]["captions"][0]["text"] = "Wait two seconds."
        self.assertIn("one: captions differ from transcript", timeline.check(self.plan, self.root))

    def test_out_of_scene_caption_fails(self):
        self.plan["scenes"][0]["captions"][0]["end_frame"] = 46
        self.assertTrue(any("outside" in e for e in timeline.check(self.plan, self.root)))

    def test_overlap_fails(self):
        next_scene = copy.deepcopy(self.plan["scenes"][0])
        next_scene.update(id="two", start_frame=40, end_frame=85)
        next_scene["captions"][0].update(start_frame=40, end_frame=70)
        self.plan["scenes"].append(next_scene)
        self.plan["total_frames"] = 85
        self.assertTrue(any("contiguous" in e for e in timeline.check(self.plan, self.root)))

    def test_path_escape_rejected(self):
        self.plan["scenes"][0]["audio"] = "../audio.wav"
        with self.assertRaisesRegex(ValueError, "inside"):
            timeline.check(self.plan, self.root)

    def test_missing_file_is_not_a_pass(self):
        self.plan["scenes"][0]["audio"] = "missing.wav"
        with self.assertRaises(OSError):
            timeline.check(self.plan, self.root)

    def test_truncated_wav_rejected(self):
        p = self.root / "audio.wav"
        p.write_bytes(p.read_bytes()[:-2])
        with self.assertRaisesRegex(ValueError, "truncated"):
            timeline.check(self.plan, self.root)

    def test_silent_scene_cannot_claim_narration(self):
        self.plan["scenes"][0]["audio"] = None
        self.assertIn("one: silent scene has narration or captions", timeline.check(self.plan, self.root))

    def test_invalid_fps_rejected(self):
        self.plan["fps"] = True
        with self.assertRaisesRegex(ValueError, "integer"):
            timeline.check(self.plan, self.root)


if __name__ == "__main__":
    unittest.main()
