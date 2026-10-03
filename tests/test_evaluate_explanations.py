"""The eval cannot pass missing outputs, changed literals or stale reviews."""

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("explanation_eval", ROOT / "scripts/evaluate_explanations.py")
assert SPEC and SPEC.loader
evaluation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluation)


class ExplanationEvalTests(unittest.TestCase):
    def setUp(self):
        self.cases = {"case": {
            "id": "case", "source": "Keep 40 and `delay_ms`.", "request": "Explain it.",
            "provenance": "synthetic", "split": "dev", "protected": ["40", "delay_ms"],
            "expected_facts": ["SECRET ANSWER"],
            "questions": [{"question": "What must remain?", "answer": "SECRET ANSWER"}],
        }}

    def test_missing_output_fails(self):
        report = evaluation.score(self.cases, {})
        self.assertEqual(report["status"], "mechanical_failed")

    def test_partial_number_is_not_preserved(self):
        report = evaluation.score(self.cases, {"case": {"output": "Keep 140 and delay_ms."}})
        self.assertEqual(report["cases"][0]["missing_protected"], ["40"])

    def test_clean_literals_still_need_review(self):
        report = evaluation.score(self.cases, {"case": {"output": "40 delay_ms"}})
        self.assertEqual(report["status"], "awaiting_reviews")

    def test_numeric_literals_require_the_complete_number(self):
        for changed in ("140", "40.0", "40,000", "1.40", "1,40", "-40", "+40", "40e2"):
            with self.subTest(changed=changed):
                self.assertFalse(evaluation.contains_literal(changed, "40"))
        for unchanged in ("40", "Use 40.", "(40), then continue", "40 ms"):
            with self.subTest(unchanged=unchanged):
                self.assertTrue(evaluation.contains_literal(unchanged, "40"))

    def test_review_acceptance_thresholds(self):
        text = "40 delay_ms"
        valid = {"meaning": 5, "simplicity": 4, "fluency": 4, "critical_error": False,
                 "rationale": "Facts and questions are preserved.",
                 "output_sha256": hashlib.sha256(text.encode()).hexdigest()}
        for changes, expected in (({}, "reviewed"), ({"critical_error": True}, "review_failed"),
                                  ({"simplicity": 3}, "review_failed"),
                                  ({"fluency": 3}, "review_failed")):
            with self.subTest(changes=changes):
                report = evaluation.score(self.cases, {"case": {"output": text}},
                                          {"case": valid | changes})
                self.assertEqual(report["status"], expected)

    def test_meaning_error_fails_despite_clean_literals(self):
        text = "40 delay_ms"
        review = {"meaning": 4, "simplicity": 5, "fluency": 5, "critical_error": False,
                  "rationale": "A condition was omitted.",
                  "output_sha256": hashlib.sha256(text.encode()).hexdigest()}
        report = evaluation.score(self.cases, {"case": {"output": text}}, {"case": review})
        self.assertEqual(report["status"], "review_failed")

    def test_stale_review_rejected(self):
        review = {"meaning": 5, "simplicity": 5, "fluency": 5, "critical_error": False,
                  "rationale": "Looks correct.", "output_sha256": "old hash"}
        with self.assertRaisesRegex(ValueError, "does not match"):
            evaluation.score(self.cases, {"case": {"output": "40 delay_ms"}}, {"case": review})

    def test_unknown_output_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown output"):
            evaluation.score(self.cases, {"wrong": {"output": "40 delay_ms"}})

    def test_prompt_has_no_answer_key_and_safe_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            evaluation.prepare(self.cases, Path(directory), "dev")
            prompts = list(Path(directory).glob("*.txt"))
            self.assertEqual(len(prompts), 1)
            self.assertIn(self.cases["case"]["source"], prompts[0].read_text())
            self.assertNotIn("SECRET ANSWER", prompts[0].read_text())
            with self.assertRaises(FileExistsError):
                evaluation.prepare(self.cases, Path(directory), "dev")

    def test_blind_pairs_separate_the_key(self):
        baseline = {"case": {"output": "First text."}}
        candidate = {"case": {"output": "Second text."}}
        pairs, key = evaluation.blind_pairs(self.cases, baseline, candidate, 407)
        self.assertEqual(set(pairs[0]), {"id", "source", "request", "questions", "A", "B"})
        self.assertEqual(set(key["case"].values()), {"baseline", "candidate"})
        for label in ("A", "B"):
            arm = {"baseline": baseline, "candidate": candidate}[key["case"][label]]
            self.assertEqual(pairs[0][label], arm["case"]["output"])
        self.assertEqual(pairs[0]["questions"], ["What must remain?"])
        self.assertNotIn("SECRET ANSWER", str(pairs))

    def test_incomplete_comparison_rejected(self):
        with self.assertRaisesRegex(ValueError, "every selected case"):
            evaluation.blind_pairs(self.cases, {}, {"case": {"output": "Second text."}}, 407)

    def test_stale_key_does_not_publish_new_pairs(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "comparison"
            output.mkdir()
            key = output / "private-key.json"
            key.write_text("stale key")
            with self.assertRaises(FileExistsError):
                evaluation.write_comparison(output, [{"A": "new"}], {"A": "candidate"})
            self.assertFalse((output / "pairs.json").exists())
            self.assertEqual(key.read_text(), "stale key")

    def test_comparison_publishes_both_files(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "comparison"
            evaluation.write_comparison(output, [{"A": "new"}], {"A": "candidate"})
            self.assertEqual(json.loads((output / "pairs.json").read_text()), [{"A": "new"}])
            self.assertEqual(json.loads((output / "private-key.json").read_text()), {"A": "candidate"})

    def test_cli_unreviewed_output_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases, outputs, report = (root / name for name in ("cases.jsonl", "outputs.jsonl", "report.json"))
            cases.write_text(json.dumps(self.cases["case"]) + "\n")
            outputs.write_text(json.dumps({"id": "case", "output": "40 delay_ms"}) + "\n")
            result = subprocess.run([sys.executable, str(ROOT / "scripts/evaluate_explanations.py"),
                                     "score", "--cases", str(cases), "--outputs", str(outputs),
                                     "--out", str(report)], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(report.read_text())["status"], "awaiting_reviews")

    def test_synthetic_fixture_contract(self):
        cases = evaluation.load_cases(ROOT / "evals/explanations/writing.jsonl")
        self.assertEqual({case["split"] for case in cases.values()}, {"dev", "holdout"})
        self.assertTrue(all(case["expected_facts"] and case["questions"] for case in cases.values()))


if __name__ == "__main__":
    unittest.main()
