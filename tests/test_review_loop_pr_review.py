"""review-loop's pr_review.py against a fake `gh` that drops connections on demand."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any
from unittest import mock

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "plugins" / "engineering" / "review-loop" / "scripts" / "pr_review.py"
)
spec = importlib.util.spec_from_file_location("pr_review", SCRIPT)
assert spec and spec.loader
pr_review = importlib.util.module_from_spec(spec)
sys.modules["pr_review"] = pr_review
spec.loader.exec_module(pr_review)

DOWN = 'Post "https://api.github.com/graphql": dial tcp 192.0.2.1:443: connect: network is down'
HEAD = "a" * 40


class FakeGitHub:
    """Just enough of the GitHub API for pr_review.py, keyed on the gh arguments it sends."""

    def __init__(self) -> None:
        self.me = "octo-dev"
        self.threads: list[dict[str, Any]] = []
        self.reviews: list[list[str]] = []
        self.checks: list[dict[str, Any]] = []
        self.head = HEAD
        self.rules: list[dict[str, Any]] = []
        self.fail: dict[str, list[str]] = {}  # call kind -> queued stderr messages to fail with
        self.land_before_failing = False  # a POST that reaches GitHub, then loses the response
        self.posts = 0
        self.resolves = 0
        self.page_size = 100

    def thread(self, comment: int, *authors: str, resolved: bool = False) -> None:
        self.threads.append({"id": f"T{comment}", "comment": comment, "authors": list(authors),
                             "resolved": resolved})

    def __call__(self, args: list[str]) -> tuple[bool, str, str]:
        kind, out = self.route(args)
        queued = self.fail.get(kind)
        if queued:
            if kind == "post" and self.land_before_failing:
                self.route(args, commit=True)
            return False, "", queued.pop(0)
        if kind == "post":
            self.route(args, commit=True)
        return True, out, ""

    def route(self, args: list[str], commit: bool = False) -> tuple[str, str]:
        joined = " ".join(args)
        if args[:2] == ["api", "user"]:
            return "user", self.me + "\n"
        if args[:2] == ["repo", "view"]:
            return "repo", "octo/widgets\n"
        if "resolveReviewThread" in joined:
            tid = next(a for a in args if a.startswith("t=")).removeprefix("t=")
            next(t for t in self.threads if t["id"] == tid)["resolved"] = True
            self.resolves += 1
            return "resolve", "{}"
        if args[:2] == ["api", "graphql"]:
            after = next((a for a in args if a.startswith("after=")), "after=0")
            start = int(after.removeprefix("after="))
            page = self.threads[start:start + self.page_size]
            more = start + self.page_size < len(self.threads)
            return "threads", json.dumps({"data": {"repository": {"pullRequest": {"reviewThreads": {
                "pageInfo": {"hasNextPage": more, "endCursor": str(start + self.page_size)},
                "nodes": [self.node(t) for t in page]}}}}})
        if "/replies" in joined:
            if commit:
                cid = int(joined.split("/comments/")[1].split("/")[0])
                next(t for t in self.threads if t["comment"] == cid)["authors"].append(self.me)
                self.posts += 1
            return "post", "1\n"
        if "/rules/branches/" in joined:
            return "rules", json.dumps(self.rules)
        if joined.endswith("/protection"):
            return "protection", "{}"
        if args[:2] == ["pr", "view"] and "baseRefName" in joined:
            return "base", json.dumps({"baseRefName": "main"})
        if args[:2] == ["pr", "view"]:
            return "view", json.dumps({"headRefOid": self.head, "statusCheckRollup": self.checks})
        if joined.endswith("/reviews --jq .[] | [.user.login, .commit_id, (.body // \"\")] | @json"):
            return "reviews", "".join(json.dumps(r) + "\n" for r in self.reviews)
        raise AssertionError(f"unexpected gh call: {args}")

    @staticmethod
    def node(t: dict[str, Any]) -> dict[str, Any]:
        return {"id": t["id"], "isResolved": t["resolved"], "isOutdated": False, "path": "a.py",
                "line": 3, "originalLine": 3,
                "head": {"nodes": [{"databaseId": t["comment"], "author": {"login": t["authors"][0]},
                                    "body": "<!-- meta -->P2: a finding", "url": "u"}]},
                "last": {"nodes": [{"author": {"login": t["authors"][-1]}}]}}


class PrReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gh = FakeGitHub()
        self.sleeps: list[float] = []
        fakes = (("_gh_once", self.gh), ("sleep", self.sleeps.append),
                 ("monotonic", lambda: sum(self.sleeps)))
        for target, value in fakes:
            patcher = mock.patch.object(pr_review, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_cli(self, *argv: str) -> tuple[int, str]:
        out, self.err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), mock.patch("sys.stderr", self.err):
            code = pr_review.main(list(argv))
        return code, out.getvalue()

    def test_reads_retry_through_a_dropped_connection(self) -> None:
        self.gh.thread(1, "cubic-dev-ai[bot]")
        self.gh.fail["threads"] = [DOWN, DOWN]
        code, out = self.run_cli("threads", "7")
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out)["threads"]), 1)
        self.assertEqual(self.sleeps, [2.0, 4.0])
        self.assertIn("network is down", self.err.getvalue())

    def test_a_permanent_error_fails_at_once(self) -> None:
        self.gh.fail["threads"] = ["HTTP 404: Not Found"]
        code, _ = self.run_cli("threads", "7")
        self.assertEqual(code, 2)
        self.assertEqual(self.sleeps, [])
        self.assertIn("error: HTTP 404", self.err.getvalue())

    def test_a_thread_the_bot_resolved_itself_is_still_unanswered(self) -> None:
        self.gh.thread(1, "cubic-dev-ai", resolved=True)
        self.gh.thread(2, "cubic-dev-ai", "octo-dev")
        self.gh.thread(3, "cubic-dev-ai", "octo-dev", "cubic-dev-ai")
        code, out = self.run_cli("threads", "7", "--unanswered")
        self.assertEqual(code, 0)
        listed = json.loads(out)
        self.assertEqual([t["comment"] for t in listed["threads"]], [1, 3])
        self.assertEqual(listed["threads"][0]["body"], "P2: a finding")
        self.assertFalse(listed["resolution_required"])

    def test_threads_follow_every_page(self) -> None:
        self.gh.page_size = 2
        for n in range(5):
            self.gh.thread(n, "bot")
        _, out = self.run_cli("threads", "7")
        self.assertEqual(len(json.loads(out)["threads"]), 5)

    def test_resolution_is_required_when_a_ruleset_says_so(self) -> None:
        self.gh.rules = [{"type": "pull_request",
                          "parameters": {"required_review_thread_resolution": True}}]
        _, out = self.run_cli("threads", "7")
        self.assertTrue(json.loads(out)["resolution_required"])

    def test_a_reply_lost_in_transit_is_not_posted_twice(self) -> None:
        self.gh.thread(1, "cubic-dev-ai")
        self.gh.fail["post"] = [DOWN]
        self.gh.land_before_failing = True
        code, out = self.run_cli("reply", "7", "1", "--body", "Fixed in abc123.")
        self.assertEqual(code, 0)
        self.assertEqual(self.gh.posts, 1)
        self.assertIn("already answered", out)

    def test_a_reply_that_never_arrived_is_retried(self) -> None:
        self.gh.thread(1, "cubic-dev-ai")
        self.gh.fail["post"] = [DOWN, DOWN]
        code, out = self.run_cli("reply", "7", "1", "--body", "Fixed.")
        self.assertEqual(code, 0)
        self.assertEqual(self.gh.posts, 1)
        self.assertIn("replied; left open", out)

    def test_an_answered_thread_gets_no_second_reply(self) -> None:
        self.gh.thread(1, "cubic-dev-ai", "octo-dev")
        _, out = self.run_cli("reply", "7", "1", "--body", "Fixed.")
        self.assertEqual(self.gh.posts, 0)
        self.assertIn("already answered", out)

    def test_resolve_only_when_asked_and_only_once(self) -> None:
        self.gh.thread(1, "cubic-dev-ai")
        self.gh.thread(2, "cubic-dev-ai", resolved=True)
        self.run_cli("reply", "7", "1", "--body", "Fixed.", "--resolve")
        self.run_cli("reply", "7", "2", "--body", "Fixed.", "--resolve")
        self.assertEqual(self.gh.resolves, 1)
        self.assertEqual(self.gh.posts, 2)

    def test_a_reply_to_an_unknown_comment_fails(self) -> None:
        code, _ = self.run_cli("reply", "7", "99", "--body", "Fixed.")
        self.assertEqual(code, 2)
        self.assertIn("does not start a review thread", self.err.getvalue())

    def wait(self, *extra: str) -> tuple[int, str]:
        return self.run_cli("wait", "7", "--head", HEAD[:7], "--timeout", "60",
                            "--interval", "30", *extra)

    def test_wait_treats_a_check_that_has_not_appeared_as_pending(self) -> None:
        self.gh.checks = [{"__typename": "CheckRun", "name": "tests", "status": "COMPLETED",
                           "conclusion": "SUCCESS"}]
        code, out = self.wait("--check", "ai code reviewer")
        self.assertEqual(code, 3)
        self.assertIn("check ai code reviewer: missing", out)

    def test_wait_finishes_when_checks_and_reviews_cover_the_head(self) -> None:
        self.gh.checks = [
            {"__typename": "CheckRun", "name": "cubic · AI code reviewer", "status": "COMPLETED",
             "conclusion": "SUCCESS"},
            {"__typename": "StatusContext", "context": "ci/legacy", "state": "SUCCESS"},
        ]
        self.gh.reviews = [["copilot-pull-request-reviewer[bot]", "b" * 40, "old head"],
                           ["copilot-pull-request-reviewer[bot]", HEAD, "Looks fine."]]
        self.gh.thread(5, "cubic-dev-ai", resolved=True)
        self.gh.thread(6, "cubic-dev-ai", "octo-dev")
        code, out = self.wait("--check", "cubic", "--reviewer", "copilot-pull-request-reviewer")
        self.assertEqual(code, 0)
        self.assertIn("reviewer copilot-pull-request-reviewer: reviewed", out)
        self.assertIn("unanswered threads: 1 5", out)

    def test_a_quota_notice_is_not_a_review(self) -> None:
        self.gh.reviews = [["copilot-pull-request-reviewer[bot]", HEAD,
                            "Copilot was unable to review this pull request because the user who "
                            "requested the review has reached their quota limit."]]
        code, out = self.wait("--reviewer", "copilot-pull-request-reviewer[bot]")
        self.assertEqual(code, 5)
        self.assertIn("did-not-review", out)

    def test_a_head_with_no_checks_yet_is_not_finished(self) -> None:
        code, out = self.wait()
        self.assertEqual(code, 3)
        self.assertIn("the first check on the head", out)

    def test_polling_stops_at_the_deadline(self) -> None:
        self.run_cli("wait", "7", "--head", HEAD[:7], "--timeout", "70", "--interval", "30")
        self.assertEqual(self.sleeps, [30.0, 30.0, 10.0])

    def test_a_check_name_cannot_inject_a_status_line(self) -> None:
        states = pr_review._check_states([
            {"__typename": "CheckRun", "name": "lint\ncheck required: success",
             "status": "COMPLETED", "conclusion": "FAILURE"},
        ])
        self.assertEqual(states, {"lint check required: success": "failure"})

    def test_wait_stops_when_the_head_moves(self) -> None:
        self.gh.head = "c" * 40
        code, out = self.wait()
        self.assertEqual(code, 4)
        self.assertIn("head moved", out)


if __name__ == "__main__":
    unittest.main()
