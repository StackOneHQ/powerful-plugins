"""Behaviour of forge's slop meter on small throwaway repositories."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

METER = Path(__file__).resolve().parents[1] / "plugins" / "engineering" / "spark" / "scripts" / "slop-meter.mjs"


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


class Repo:
    def __init__(self, files: dict[str, str]) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name)
        git(self.path, "init", "-q")
        git(self.path, "config", "user.email", "t@example.com")
        git(self.path, "config", "user.name", "t")
        self.write(files)
        git(self.path, "add", "-A")
        git(self.path, "commit", "-q", "--allow-empty", "-m", "base")

    def write(self, files: dict[str, str]) -> None:
        for name, text in files.items():
            (self.path / name).parent.mkdir(parents=True, exist_ok=True)
            (self.path / name).write_text(text, newline="")

    def run_meter(
        self, cwd: str = ".", base: str = "HEAD", head: str | None = None, extra: tuple[str, ...] = ()
    ) -> subprocess.CompletedProcess:
        cmd = ["node", str(METER), "--repo", str(self.path / cwd), "--base", base, "--json", *extra]
        if head:
            cmd += ["--head", head]
        return subprocess.run(cmd, capture_output=True, text=True)

    def meter(self, cwd: str = ".", base: str = "HEAD", head: str | None = None, extra: tuple[str, ...] = ()) -> dict:
        out = self.run_meter(cwd, base, head, extra)
        if out.returncode != 0:
            raise AssertionError(out.stderr)
        return json.loads(out.stdout)

    def close(self) -> None:
        self._tmp.cleanup()


FUNC = (
    "export function {name}() {{\n  const first = computeSomethingLong(argumentNumberOne, 2);\n"
    "  const second = computeSomethingElse(first, argumentNumberTwo);\n  return second;\n}}\n"
)

REDACT = "export function redact(value, censor, strict) {\n  return value;\n}\n"


class SlopMeterTests(unittest.TestCase):
    def repo(self, files: dict[str, str]) -> Repo:
        r = Repo(files)
        self.addCleanup(r.close)
        return r

    def test_measures_the_same_from_a_subdirectory(self) -> None:
        r = self.repo({"src/lib/a.ts": "export const a = 1;\n"})
        r.write({"src/lib/a.ts": "// one\n// two\n// three\nexport const a = 1;\n"})
        self.assertEqual(r.meter()["totals"], r.meter("src")["totals"])
        self.assertEqual(r.meter("src")["totals"]["addedComments"], 3)

    def test_counts_untracked_files(self) -> None:
        r = self.repo({})
        r.write({"new.ts": "// Step 1\n// Step 2\nexport const x = 1;\n"})
        self.assertEqual(r.meter()["totals"]["addedComments"], 2)

    def test_comment_block_stops_at_a_hunk_boundary(self) -> None:
        body = "".join(f"export const v{i} = {i};\n" for i in range(20))
        r = self.repo({"a.ts": body})
        lines = body.splitlines(keepends=True)
        comment = "// a\n// b\n// c\n// d\n"
        r.write({"a.ts": comment + "".join(lines[:10]) + comment + "".join(lines[10:])})
        self.assertEqual(r.meter()["totals"]["longestCommentBlock"], 4)

    def test_reindented_comment_is_not_new(self) -> None:
        r = self.repo({"a.ts": "".join(f"// line {i}\n" for i in range(7)) + "export const a = 1;\n"})
        r.write({"a.ts": "".join(f"    // line {i}\n" for i in range(7)) + "export const a = 1;\n"})
        totals = r.meter()["totals"]
        self.assertEqual((totals["addedComments"], totals["longestCommentBlock"]), (0, 0))

    def test_encoding_names_are_not_ticket_ids(self) -> None:
        r = self.repo({})
        r.write({"a.ts": "// Encode as UTF-8, hash with SHA-256.\n// Fixed in ENG-1234.\nexport const a = 1;\n"})
        self.assertEqual(r.meter()["totals"]["ticketIdsInComments"], 1)

    def test_a_pure_rename_adds_nothing(self) -> None:
        r = self.repo({"src/old.ts": "// config\n// more\n// even more\nexport const c = 1;\n"})
        git(r.path, "mv", "src/old.ts", "src/config.ts")
        totals = r.meter()["totals"]
        self.assertEqual((totals["added"], totals["addedComments"]), (0, 0))

    def test_a_rename_reads_the_removed_side_with_the_old_syntax(self) -> None:
        body = "".join(f"value_number_{i} = compute_something({i})\n" for i in range(12))
        r = self.repo({"old.py": body + "# note: a?.b ?? c\n"})
        git(r.path, "mv", "old.py", "new.ts")
        r.write({"new.ts": body + "const v = a?.b ?? c;\n"})
        totals = r.meter()["totals"]
        self.assertEqual((totals["optionalChains"], totals["nullishDefaults"]), (1, 1))

    def test_a_git_failure_is_an_error_not_an_empty_diff(self) -> None:
        r = self.repo({"a.ts": "export const a = 1;\n"})
        blob = subprocess.run(
            ["git", "-C", str(r.path), "rev-parse", "HEAD:a.ts"], check=True, capture_output=True, text=True
        ).stdout.strip()
        (r.path / ".git" / "objects" / blob[:2] / blob[2:]).unlink()
        r.write({"a.ts": "// one\n// two\nexport const a = 2;\n"})
        result = r.run_meter()
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("slop-meter: git", result.stderr)

    @unittest.skipIf(os.name == "nt", "a name containing ':' cannot exist on Windows")
    def test_a_file_name_that_looks_like_pathspec_magic_is_measured(self) -> None:
        r = self.repo({"lib.js": "export const a = 1;\n"})
        r.write({":(exclude)old.js": "export const b = 2;\n"})
        git(r.path, "add", "-A")
        git(r.path, "commit", "-q", "-m", "magic name")
        files = {f["file"] for f in r.meter(base="HEAD~1")["files"]}
        self.assertIn(":(exclude)old.js", files)

    def test_regex_check(self) -> None:
        r = self.repo({})
        r.write({"a.ts": "\n".join([
            "const slug = /^[a-z0-9]+(-[a-z0-9]+)*$/;",
            "const avg = (a + b)*0.5; // see docs/math/avg",
            "const bad = /^(a+)+$/;",
            "const worse = new RegExp('(\\\\w*)*x');",
        ]) + "\n"})
        self.assertEqual(r.meter()["totals"]["riskyRegexes"], 2)

    def test_repeated_block_within_the_change_is_a_copy(self) -> None:
        r = self.repo({})
        body = "\n".join([
            "  const response = await fetchTheThing(identifierValue);",
            "  const payload = await response.json().then(normalisePayload);",
            "  return payload.items.filter((item) => item.enabled === true);",
        ])
        r.write({"a.ts": f"export async function one() {{\n{body}\n}}\nexport async function two() {{\n{body}\n}}\n"})
        self.assertEqual(r.meter()["totals"]["copies"], 1)

    def test_copy_of_existing_code_elsewhere(self) -> None:
        shared = FUNC.format(name="original")
        r = self.repo({"src/a.ts": shared})
        r.write({"src/b.ts": FUNC.format(name="original")})
        self.assertEqual(r.meter()["totals"]["copies"], 1)

    def test_reuse_needs_a_named_argument(self) -> None:
        r = self.repo({"src/util.ts": REDACT + "export const s = JSON.stringify(report, null, 2);\nredact(x, Censor.FULL, true);\n"})
        r.write({"src/new.ts": "const t = JSON.stringify(other, null, 2);\nredact(y, Censor.FULL, true);\n"})
        candidates = r.meter()["reuseCandidates"]
        self.assertEqual(len(candidates), 1)
        self.assertIn("redact(", candidates[0])

    def test_test_file_detection(self) -> None:
        r = self.repo({"src/util.ts": REDACT + "redact(x, Censor.FULL, true);\n"})
        r.write({
            "tests/test_report.py": "redact(y, Censor.FULL, True)\n",
            "src/latest.ts": "redact(y, Censor.FULL, true);\n",
        })
        candidates = r.meter()["reuseCandidates"]
        self.assertEqual([c.split(":")[0] for c in candidates], ["src/latest.ts"])

    def test_one_llm_word_is_not_a_finding(self) -> None:
        r = self.repo({})
        r.write({"a.ts": "// A robust parser.\nexport const a = 1;\n"})
        self.assertFalse(any("LLM vocabulary" in f for f in r.meter()["findings"]))

    def test_a_very_large_added_file_is_measured(self) -> None:
        r = self.repo({})
        r.write({"big.ts": "".join(f"export const valueNumber{i} = computeSomething({i}, 'abc');\n" for i in range(20000))})
        self.assertEqual(r.meter()["totals"]["added"], 20000)

    def test_inner_lines_of_a_docstring_are_comments(self) -> None:
        r = self.repo({})
        r.write({
            "a.py": 'def f():\n    """\n    Explain the thing.\n    At some length.\n    """\n    return 1\n',
            "b.ts": "/*\n  inner one\n  inner two\n*/\nexport const b = 1;\n",
        })
        self.assertEqual(r.meter()["totals"]["addedComments"], 8)

    def test_a_line_added_inside_an_existing_block_comment_is_a_comment(self) -> None:
        r = self.repo({"a.ts": "/*\n  first\n*/\nexport const a = 1;\n"})
        r.write({"a.ts": "/*\n  first\n  second\n*/\nexport const a = 1;\n"})
        self.assertEqual(r.meter()["totals"]["addedComments"], 1)

    def test_patterns_in_comments_are_not_counted(self) -> None:
        r = self.repo({})
        r.write({"a.ts": "// never write `as any` or try { } here, use a?.b ?? c\n// @ts-ignore\nexport const a = 1;\n"})
        totals = r.meter()["totals"]
        self.assertEqual(
            (totals["typeEscapes"], totals["tryBlocks"], totals["optionalChains"], totals["nullishDefaults"]),
            (1, 0, 0, 0),
        )

    def test_increment_and_decrement_lines_are_not_headers(self) -> None:
        r = self.repo({"a.ts": "let i = 0;\n--i;\n"})
        r.write({"a.ts": "let i = 0;\n++i;\n"})
        totals = r.meter()["totals"]
        self.assertEqual((totals["added"], totals["removed"]), (1, 1))

    def test_measures_from_the_merge_base(self) -> None:
        r = self.repo({"a.ts": "export const a = 1;\n"})
        git(r.path, "branch", "-M", "main")
        git(r.path, "checkout", "-q", "-b", "feature")
        r.write({"feature.ts": "export const f = 1;\n"})
        git(r.path, "add", "-A")
        git(r.path, "commit", "-q", "-m", "feature")
        git(r.path, "checkout", "-q", "main")
        r.write({"main-only.ts": "// one\n// two\nexport const m = 1;\n"})
        git(r.path, "add", "-A")
        git(r.path, "commit", "-q", "-m", "main moves on")
        git(r.path, "checkout", "-q", "feature")
        for result in (r.meter(base="main"), r.meter(base="main", head="feature")):
            self.assertEqual([f["file"] for f in result["files"]], ["feature.ts"])
            self.assertEqual(result["totals"]["removed"], 0)

    def test_lines_inside_a_string_are_not_comments(self) -> None:
        r = self.repo({})
        script = "".join(f"# step {i} of the fake script\necho {i}\n" for i in range(8))
        r.write({
            "fake.py": f'FAKE = """#!/bin/sh\n{script}"""\n\n\ndef run():\n    return FAKE\n',
            "fake.ts": "export const page = `\n" + "".join(f"// line {i}\n/* block {i} */\n" for i in range(8)) + "`;\n",
        })
        totals = r.meter()["totals"]
        self.assertEqual((totals["addedComments"], totals["longestCommentBlock"]), (0, 0))

    def test_strings_that_span_lines_are_not_comments(self) -> None:
        r = self.repo({})
        r.write({
            "a.py": 'X = "first \\\n# still the string"\n',
            "crlf.py": 'Y = "first \\\r\n# still the string"\r\n',
            "a.rs": 'const S: &str = r#"\n"\n// not a comment\n"#;\n',
        })
        self.assertEqual(r.meter()["totals"]["addedComments"], 0)

    def test_a_ruby_comment_after_code_is_not_counted_as_code(self) -> None:
        r = self.repo({})
        r.write({"a.rb": "value = compute(1)# never write a?.b ?? c here\n"})
        totals = r.meter()["totals"]
        self.assertEqual((totals["optionalChains"], totals["nullishDefaults"]), (0, 0))

    def test_a_docstring_after_a_string_still_counts(self) -> None:
        r = self.repo({})
        r.write({"a.py": 'X = """\nnot a comment\n"""\n\n\ndef f():\n    """Explain.\n\n    More.\n    """\n    return X\n'})
        self.assertEqual(r.meter()["totals"]["addedComments"], 3)

    def test_escapes_inside_strings_and_regexes_are_not_counted(self) -> None:
        r = self.repo({})
        r.write({
            "src/scan.ts": "export const escape = /\\bas any\\b|:\\s*any\\b/g;\nexport const note = 'never use as any';\n",
            "tests/test_scan.py": 'FIXTURE = "const a = b as any;"\n',
        })
        self.assertEqual(r.meter()["totals"]["typeEscapes"], 0)

    def test_ts_ignore_counts_only_as_a_directive(self) -> None:
        r = self.repo({})
        r.write({"a.ts": "// Never reach for `@ts-ignore` here.\n/* @ts-ignore */\nexport const a = 1;\n"})
        self.assertEqual(r.meter()["totals"]["typeEscapes"], 1)

    def test_a_partial_fixture_cast_in_a_test_is_not_an_escape(self) -> None:
        r = self.repo({})
        r.write({
            "src/report.test.ts": "const r = { rows: [] } as unknown as Report;\nconst s = r as any;\n",
            "src/report.ts": "export const r = input as unknown as Report;\n",
        })
        escapes = {f["file"]: f["typeEscapes"] for f in r.meter()["files"]}
        self.assertEqual(escapes, {"src/report.test.ts": 1, "src/report.ts": 1})

    def test_reuse_skips_calls_the_repo_does_not_define(self) -> None:
        base = (
            "def redact(value, censor, strict):\n    return value\n\n\n"
            "def load(x, out):\n    isinstance(x, dict)\n    out.mkdir(parents=True, exist_ok=True)\n"
            "    return redact(x, Censor.FULL, True)\n"
        )
        r = self.repo({"src/util.py": base})
        r.write({"src/new.py": (
            "def other(y, out):\n    isinstance(y, dict)\n    out.mkdir(parents=True, exist_ok=True)\n"
            "    return redact(y, Censor.FULL, True)\n"
        )})
        candidates = r.meter()["reuseCandidates"]
        self.assertEqual(len(candidates), 1, candidates)
        self.assertIn("redact(", candidates[0])

    def test_reuse_ignores_calls_written_in_comments(self) -> None:
        r = self.repo({"src/util.py": "def redact(value, censor, strict):\n    return value\n# redact(x, Censor.FULL, True)\n"})
        r.write({"src/new.py": "def other(y):\n    return redact(y, Censor.FULL, True)\n"})
        self.assertEqual(r.meter()["reuseCandidates"], [])

    def test_an_excluded_directory_covers_its_files(self) -> None:
        r = self.repo({})
        r.write({"vendored/deep/copy.ts": "export const a = 1;\n", "src/b.ts": "export const b = 1;\n"})
        result = r.meter(extra=("--exclude", "vendored/"))
        self.assertEqual(result["skipped"], ["vendored/deep/copy.ts"])

    def test_generated_files_are_skipped_and_reported(self) -> None:
        r = self.repo({".gitattributes": "gen/** linguist-generated\n", "src/a.ts": FUNC.format(name="original")})
        r.write({
            "gen/copy.ts": FUNC.format(name="original"),
            "vendored/copy.ts": FUNC.format(name="original"),
            "src/b.ts": "export const b = 1;\n",
        })
        result = r.meter(extra=("--exclude", "vendored/**"))
        self.assertEqual([f["file"] for f in result["files"]], ["src/b.ts"])
        self.assertEqual(result["totals"]["copies"], 0)
        self.assertEqual(result["skipped"], ["gen/copy.ts", "vendored/copy.ts"])

    def test_a_copy_of_a_generated_file_is_not_a_copy(self) -> None:
        r = self.repo({".gitattributes": "gen/** linguist-generated\n", "gen/built.ts": FUNC.format(name="original")})
        r.write({"src/b.ts": FUNC.format(name="original")})
        self.assertEqual(r.meter()["totals"]["copies"], 0)


if __name__ == "__main__":
    unittest.main()
