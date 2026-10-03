"""The eval cannot pass missing outputs, changed literals or stale reviews."""

import hashlib
import importlib.util
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
        self.assertEqual(set(pairs[0]), {"id", "source", "request", "A", "B"})
        self.assertEqual(set(key["case"].values()), {"baseline", "candidate"})

    def test_incomplete_comparison_rejected(self):
        with self.assertRaisesRegex(ValueError, "every selected case"):
            evaluation.blind_pairs(self.cases, {}, {"case": {"output": "Second text."}}, 407)

    def test_synthetic_fixture_contract(self):
        cases = evaluation.load_cases(ROOT / "evals/explanations/writing.jsonl")
        self.assertEqual({case["split"] for case in cases.values()}, {"dev", "holdout"})
        self.assertTrue(all(case["expected_facts"] and case["questions"] for case in cases.values()))


if __name__ == "__main__":
    unittest.main()
