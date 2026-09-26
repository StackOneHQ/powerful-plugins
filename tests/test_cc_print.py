import html
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins" / "productivity" / "cc-print" / "scripts" / "export-conversation.js"


def _user(text: object, **extra: object) -> dict[str, object]:
    return {"type": "user", "message": {"role": "user", "content": text}, **extra}


def _assistant(*blocks: dict[str, object]) -> dict[str, object]:
    return {"type": "assistant", "message": {"role": "assistant", "content": list(blocks)}}


def _text(text: str) -> dict[str, object]:
    return {"type": "text", "text": text}


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class CcPrintTests(unittest.TestCase):
    def _run(self, entries: list[dict[str, object]], *args: str) -> tuple[subprocess.CompletedProcess[str], str | None]:
        with tempfile.TemporaryDirectory() as tmp:
            transcript = Path(tmp) / "session.jsonl"
            transcript.write_text("\n".join(json.dumps(entry) for entry in entries) + "\n")
            output = Path(tmp) / "out.html"
            result = subprocess.run(
                ["node", str(SCRIPT), str(transcript), "--format", "html", "--output", str(output), *args],
                capture_output=True,
                text=True,
            )
            return result, output.read_text() if output.exists() else None

    def _export(self, entries: list[dict[str, object]], *args: str) -> str:
        result, page = self._run(entries, *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        assert page is not None
        return page

    def _prompts(self, page: str) -> list[str]:
        return [html.unescape(p) for p in re.findall(r'<div class="user-content">(.*?)</div>', page, re.S)]

    def test_claude_transcript_keeps_only_what_the_user_typed(self) -> None:
        page = self._export(
            [
                _user("first question"),
                _assistant({"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}),
                _user([{"type": "tool_result", "tool_use_id": "t1", "content": "a.txt"}]),
                _user("<task-notification>\n<task-id>x</task-id>\n</task-notification>"),
                _user("Base directory for this skill: /tmp/skill", isMeta=True),
                _user("[Request interrupted by user for tool use]"),
                _user("<command-name>/model</command-name>\n<command-message>model</command-message>\n<command-args>opus</command-args>"),
                {"type": "attachment", "attachment": {"type": "queued_command", "prompt": "typed mid-turn", "humanTurn": True}},
                _assistant(_text("done")),
            ]
        )

        self.assertEqual(self._prompts(page), ["first question", "/model opus", "typed mid-turn"])

    def test_last_counts_user_prompts_not_tool_results(self) -> None:
        entries = []
        for n in range(1, 4):
            entries += [
                _user(f"prompt {n}"),
                _assistant({"type": "tool_use", "name": "Read", "input": {}}),
                _user([{"type": "tool_result", "tool_use_id": f"t{n}", "content": "x"}]),
                _assistant(_text(f"answer {n}")),
            ]

        page = self._export(entries, "--last", "2")

        self.assertEqual(self._prompts(page), ["prompt 2", "prompt 3"])
        self.assertIn("answer 2", page)
        self.assertNotIn("answer 1", page)

    def test_print_invocation_and_its_reply_are_left_out(self) -> None:
        page = self._export(
            [
                _user("fix the bug in export-conversation.js"),
                _assistant(_text("real answer")),
                _user("<command-name>/cc-print:print</command-name>\n<command-args>last 5</command-args>"),
                _assistant(_text("exporting now")),
            ]
        )

        self.assertEqual(self._prompts(page), ["fix the bug in export-conversation.js"])
        self.assertNotIn("exporting now", page)

    def test_codex_rollout_reads_response_items_not_message_events(self) -> None:
        def item(payload: dict[str, object]) -> dict[str, object]:
            return {"type": "response_item", "payload": payload}

        page = self._export(
            [
                {"type": "session_meta", "payload": {"originator": "codex-tui"}},
                item({"type": "message", "role": "developer", "content": [{"type": "input_text", "text": "system rules"}]}),
                item({"type": "message", "role": "user", "content": [{"type": "input_text", "text": "<environment_context>cwd</environment_context>"}]}),
                {"type": "event_msg", "payload": {"type": "user_message", "message": "fix the bug"}},
                item({"type": "message", "role": "user", "content": [{"type": "input_text", "text": "fix the bug"}]}),
                item({"type": "message", "role": "user", "content": [{"type": "input_text", "text": "<task>keep this prompt</task>"}]}),
                item({"type": "custom_tool_call", "name": "exec", "input": "ls"}),
                item({"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "fixed"}]}),
            ]
        )

        self.assertEqual(self._prompts(page), ["fix the bug", "<task>keep this prompt</task>"])
        self.assertIn("fixed", page)
        self.assertIn('<span class="tool-name">exec</span>', page)
        self.assertNotIn("system rules", page)

    def test_markdown_leaves_code_and_arithmetic_as_written(self) -> None:
        page = self._export(
            [
                _user("show me"),
                _assistant(_text("1. Install\n2. Run\n\nMath: 2 * 3 and 4 * 5.\n\n```python\nreturn a * b  # **x**\n- item\n```")),
            ]
        )

        self.assertIn('<span class="marker">1.</span>Install', page)
        self.assertIn("Math: 2 * 3 and 4 * 5.", page)
        self.assertIn("return a * b  # **x**\n- item", page)
        self.assertNotIn("<em>", page)
        self.assertNotIn("<strong>", page)

    def test_fence_closes_only_on_a_bare_fence_line(self) -> None:
        page = self._export(
            [_user("show me"), _assistant(_text("````md\n```js\nlet *a* = 1\n```\n````\n\nName | Size\n--- | ---\nlogo | 12\n\nuse a | b here\n---\nafter the rule"))]
        )

        self.assertIn("```js\nlet *a* = 1\n```", page)
        self.assertNotIn("<em>", page)
        self.assertIn("<th>Name</th>", page)
        self.assertIn("<td>logo</td>", page)
        self.assertIn("use a | b here", page)
        self.assertIn("<hr>", page)

    def test_bad_flags_exit_non_zero_without_output(self) -> None:
        entries = [_user("hi"), _assistant(_text("hello"))]
        for args in (["--last", "2abc"], ["--width", "12px"], ["--scale", "1e309"], ["--last", "0"], ["--bogus"]):
            with self.subTest(args=args):
                result, page = self._run(entries, *args)
                self.assertEqual(result.returncode, 1)
                self.assertIsNone(page)
        result, _ = self._run(entries, "--last")
        self.assertIn("--last needs a value", result.stderr)


if __name__ == "__main__":
    unittest.main()
