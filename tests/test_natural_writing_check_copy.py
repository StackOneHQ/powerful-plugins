"""Behaviour of natural-writing's check-copy.sh on small throwaway drafts."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "plugins" / "documentation" / "natural-writing" / "scripts" / "check-copy.sh"
)

DASH = "—"
SMILE = "\U0001F642"
CODER = "\U0001F468‍\U0001F4BB"  # man, zero-width joiner, laptop
WAVE_TONED = "\U0001F44B\U0001F3FD"  # waving hand, medium skin tone


def pcre_grep() -> str | None:
    for name in ("grep", "ggrep"):
        if shutil.which(name) is None:
            continue
        probe = subprocess.run([name, "-qP", "x"], input="x", text=True, capture_output=True)
        if probe.returncode == 0:
            return name
    return None


def utf8_grep_works(grep: str, locale_name: str) -> bool:
    env = {**os.environ, "LC_ALL": locale_name}
    probe = subprocess.run(
        [grep, "-qP", r"\x{2014}"], input=DASH, text=True, encoding="utf-8", capture_output=True, env=env
    )
    return probe.returncode == 0


@unittest.skipIf(shutil.which("bash") is None or pcre_grep() is None, "needs bash and a grep with -P")
class CheckCopyTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def draft(self, text: str, newline: str = "\n") -> Path:
        path = self.dir / "draft.txt"
        path.write_bytes(text.replace("\n", newline).encode("utf-8"))
        return path

    def run_check(self, path: Path, *args: str, env: dict[str, str] | None = None):
        return subprocess.run(
            ["bash", str(SCRIPT), *args, str(path)],
            capture_output=True, text=True, encoding="utf-8", env=env,
        )

    def fake_locale(self, *names: str) -> dict[str, str]:
        """An environment whose `locale -a` lists only `names` and starts in the C locale."""
        bin_dir = self.dir / "bin"
        bin_dir.mkdir(exist_ok=True)
        stub = bin_dir / "locale"
        stub.write_text("#!/bin/sh\n" + "".join(f"echo {n}\n" for n in names))
        stub.chmod(0o755)
        env = {k: v for k, v in os.environ.items() if not k.startswith("LC_") and k != "LANG"}
        env["LC_ALL"] = "C"
        env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
        return env

    def test_refuses_to_pass_when_grep_cannot_read_code_points(self) -> None:
        result = self.run_check(self.draft(f"a {DASH} b\n"), env=self.fake_locale("POSIX"))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("Refusing to report a pass", result.stderr)

    def test_accepts_the_glibc_spelling_of_a_utf8_locale(self) -> None:
        grep = pcre_grep()
        assert grep is not None
        if not utf8_grep_works(grep, "C.utf8"):
            self.skipTest("this host has no C.utf8 locale (glibc spelling)")
        result = self.run_check(self.draft(f"a {DASH} b\n"), env=self.fake_locale("C.utf8"))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("em or en dash", result.stdout)

    def test_rejects_a_directory(self) -> None:
        result = self.run_check(self.dir)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn("pass", result.stdout)

    def test_a_grep_error_is_not_a_pass(self) -> None:
        grep = shutil.which(pcre_grep() or "grep")
        assert grep is not None
        bin_dir = self.dir / "failing-grep"
        bin_dir.mkdir()
        wrapper = bin_dir / "grep"
        # Fails only the negation-opener check, so the script gets past its probes.
        wrapper.write_text(
            f'#!/bin/sh\ncase "$*" in *nobody*) exit 2;; esac\nexec "{grep}" "$@"\n'
        )
        wrapper.chmod(0o755)
        env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
        result = self.run_check(self.draft("A plain sentence.\n"), env=env)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("Refusing to report a pass", result.stderr)

    def test_social_blank_lines_are_not_emoji_only_lines(self) -> None:
        text = f"Opening line\n\n   \nShipped it {SMILE}\n"
        for newline in ("\n", "\r\n"):
            with self.subTest(newline=repr(newline)):
                result = self.run_check(self.draft(text, newline), "--channel", "social")
                self.assertEqual(result.returncode, 0, result.stdout)

    def test_social_emoji_only_line_still_fails(self) -> None:
        result = self.run_check(self.draft(f"Opening line\n {SMILE}\n"), "--channel", "social")
        self.assertEqual(result.returncode, 1)
        self.assertIn("emoji-only line", result.stdout)

    def test_social_joined_emoji_is_one_emoji(self) -> None:
        result = self.run_check(self.draft(f"Opening line\nShipped the fix {CODER}\n"), "--channel", "social")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("mid-line", result.stdout)

    def test_social_skin_tone_is_not_a_second_emoji(self) -> None:
        lines = "".join(f"Line {i} {WAVE_TONED}\n" for i in range(3))
        result = self.run_check(self.draft("Opening line\n" + lines), "--channel", "social")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("adjacent", result.stdout)

    def test_social_toned_sign_off_pair_is_not_two_emoji_separated_by_text(self) -> None:
        for pair in (WAVE_TONED * 2, f"{WAVE_TONED} {WAVE_TONED}"):
            with self.subTest(pair=pair):
                result = self.run_check(self.draft(f"Opening line\nSee you soon {pair}\n"), "--channel", "social")
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertIn("adjacent emoji pair", result.stdout)

    def test_social_unreadable_normalisation_is_not_a_pass(self) -> None:
        tr = shutil.which("tr")
        assert tr is not None
        bin_dir = self.dir / "failing-tr"
        bin_dir.mkdir()
        wrapper = bin_dir / "tr"
        # Fails only the CR strip, the first step of the social checks.
        wrapper.write_text(f'#!/bin/sh\n[ "$1" = "-d" ] && [ "$2" = "\\r" ] && exit 1\nexec "{tr}" "$@"\n')
        wrapper.chmod(0o755)
        env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
        result = self.run_check(self.draft("Opening line\nShipped it\n"), "--channel", "social", env=env)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("Refusing to report a pass", result.stderr)

    def test_social_two_emoji_separated_by_text_still_fail(self) -> None:
        result = self.run_check(
            self.draft(f"Opening line\nA {CODER} then b {SMILE}\n"), "--channel", "social"
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("two emoji separated by text", result.stdout)

    def test_social_counts_sequences_toward_the_cap(self) -> None:
        lines = "".join(f"Line {i} {CODER}\n" for i in range(5))
        result = self.run_check(self.draft("Opening line\n" + lines), "--channel", "social")
        self.assertEqual(result.returncode, 1)
        self.assertIn("count=5", result.stdout)


if __name__ == "__main__":
    unittest.main()
