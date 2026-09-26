import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTER = (
    ROOT
    / "plugins"
    / "productivity"
    / "cc-print"
    / "scripts"
    / "export-conversation.js"
)


class CodexRuntimeAdapterTests(unittest.TestCase):
    def test_conversation_exporter_renders_codex_event_messages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            transcript = temporary / "rollout.jsonl"
            output = temporary / "conversation.html"
            entries = [
                {
                    "type": "event_msg",
                    "payload": {"type": "user_message", "message": "Codex user text"},
                },
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "agent_message",
                        "message": "Codex agent **answer**",
                    },
                },
            ]
            transcript.write_text("\n".join(json.dumps(entry) for entry in entries) + "\n")

            completed = subprocess.run(
                [
                    "node",
                    str(EXPORTER),
                    str(transcript),
                    "--format",
                    "html",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            html = output.read_text()
            self.assertIn("Codex user text", html)
            self.assertIn("Codex agent <strong>answer</strong>", html)
            self.assertIn("<title>Claude Conversation</title>", html)


if __name__ == "__main__":
    unittest.main()
