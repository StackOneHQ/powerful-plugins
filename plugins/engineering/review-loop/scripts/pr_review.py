#!/usr/bin/env python3
"""GitHub calls for the review-loop skill that must survive a flaky network.

  threads <pr> [--unanswered]
      Review threads as JSON, and whether the base requires resolving them. A thread is
      answered when its last comment is yours; a bot resolving it does not count.
  reply <pr> <comment-id> (--body TEXT | --body-file FILE) [--resolve]
      Answer the thread <comment-id> starts. The thread is re-read before every attempt, so a
      retry after a dropped connection never posts twice.
  wait <pr> --head SHA [--check NAME]... [--reviewer LOGIN]...
      Poll until SHA's checks have all finished (with no --reviewer, until there is one), each
      named check exists and each named reviewer has posted a review of SHA, then list
      unanswered threads. --reviewer sees review objects only, not summary comments. A review
      saying the bot could not review (a spent quota) is "did-not-review". Exit 0 done,
      3 timeout, 4 head moved, 5 done but a named reviewer did not review.

Only transient failures (dropped connections, 5xx, secondary rate limits) are retried.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TRANSIENT = re.compile(
    r"dial tcp|network is down|network is unreachable|connection (reset|refused)|i/o timeout"
    r"|TLS handshake|timed out|timeout awaiting|unexpected EOF|no such host"
    r"|HTTP 5\d\d|secondary rate limit|submitted too quickly",
    re.IGNORECASE,
)
NOT_A_REVIEW = re.compile(r"unable to review this pull request|reached (their|your) quota limit", re.I)
ATTEMPTS = 6
MAX_DELAY = 30.0

sleep = time.sleep
monotonic = time.monotonic


class GhError(RuntimeError):
    pass


def _gh_once(args: list[str]) -> tuple[bool, str, str]:
    proc = subprocess.run(["gh", *args], capture_output=True, text=True)
    return proc.returncode == 0, proc.stdout, proc.stderr.strip()


def retry(attempt: Callable[[], tuple[bool, str, str]]) -> str:
    delay, tries = 2.0, 1
    while True:
        ok, out, err = attempt()
        if ok:
            return out
        if tries == ATTEMPTS or not TRANSIENT.search(err):
            raise GhError(err or "gh failed")
        print(f"retrying after: {err.splitlines()[-1]}", file=sys.stderr)
        sleep(delay)
        delay, tries = min(delay * 2, MAX_DELAY), tries + 1


def gh(args: list[str]) -> str:
    """Run gh with retries; only for reads and idempotent writes."""
    return retry(lambda: _gh_once(args))


def gh_json(args: list[str]) -> Any:
    return json.loads(gh(args))


def same_login(a: str, b: str) -> bool:
    return a.lower().removesuffix("[bot]") == b.lower().removesuffix("[bot]")


THREADS_QUERY = """
query($o:String!,$r:String!,$n:Int!,$after:String){repository(owner:$o,name:$r){pullRequest(number:$n){
reviewThreads(first:100,after:$after){pageInfo{hasNextPage endCursor}
nodes{id isResolved isOutdated path line originalLine
head:comments(first:1){nodes{databaseId author{login} body url}}
last:comments(last:1){nodes{author{login}}}}}}}}"""


@dataclass
class Thread:
    id: str
    comment: int
    author: str
    path: str
    line: int | None
    resolved: bool
    outdated: bool
    answered: bool
    url: str
    body: str


def load_threads(repo: str, pr: int, me: str) -> list[Thread]:
    owner, name = repo.split("/", 1)
    threads: list[Thread] = []
    after: str | None = None
    while True:
        args = ["api", "graphql", "-f", f"query={THREADS_QUERY}", "-f", f"o={owner}",
                "-f", f"r={name}", "-F", f"n={pr}"]
        if after:
            args += ["-f", f"after={after}"]
        page = gh_json(args)["data"]["repository"]["pullRequest"]["reviewThreads"]
        for node in page["nodes"]:
            head = node["head"]["nodes"]
            if not head:
                continue
            first = head[0]
            last = node["last"]["nodes"][0]
            body = re.sub(r"<!--.*?-->", "", first["body"] or "", flags=re.S).strip()
            threads.append(Thread(
                id=node["id"], comment=first["databaseId"],
                author=(first["author"] or {}).get("login", ""), path=node["path"],
                line=node["line"] or node["originalLine"], resolved=node["isResolved"],
                outdated=node["isOutdated"],
                answered=same_login((last["author"] or {}).get("login", ""), me),
                url=first["url"], body=body[:400],
            ))
        if not page["pageInfo"]["hasNextPage"]:
            return threads
        after = page["pageInfo"]["endCursor"]


def resolution_required(repo: str, base: str) -> bool:
    rules = gh_json(["api", f"repos/{repo}/rules/branches/{base}"])
    if any(r.get("type") == "pull_request"
           and (r.get("parameters") or {}).get("required_review_thread_resolution")
           for r in rules):
        return True
    try:
        protection = gh_json(["api", f"repos/{repo}/branches/{base}/protection"])
    except GhError as error:
        if "404" in str(error) or "not protected" in str(error).lower():
            return False
        raise
    return bool((protection.get("required_conversation_resolution") or {}).get("enabled"))


def find_thread(repo: str, pr: int, me: str, comment: int) -> Thread:
    for thread in load_threads(repo, pr, me):
        if thread.comment == comment:
            return thread
    raise GhError(f"comment {comment} does not start a review thread on #{pr}")


def cmd_threads(repo: str, args: argparse.Namespace, me: str) -> int:
    base = gh_json(["pr", "view", str(args.pr), "-R", repo, "--json", "baseRefName"])["baseRefName"]
    threads = load_threads(repo, args.pr, me)
    if args.unanswered:
        threads = [t for t in threads if not t.answered]
    print(json.dumps({
        "repo": repo, "pr": args.pr, "me": me, "base": base,
        "resolution_required": resolution_required(repo, base),
        "threads": [t.__dict__ for t in threads],
    }, indent=2))
    return 0


def cmd_reply(repo: str, args: argparse.Namespace, me: str) -> int:
    body = args.body if args.body is not None else Path(args.body_file).read_text(encoding="utf-8")
    if not body.strip():
        raise GhError("empty reply body")

    def post_unless_answered() -> tuple[bool, str, str]:
        if find_thread(repo, args.pr, me, args.comment).answered:
            return True, "already answered", ""
        ok, _, err = _gh_once(["api", "--method", "POST",
                               f"repos/{repo}/pulls/{args.pr}/comments/{args.comment}/replies",
                               "-f", f"body={body}", "--jq", ".id"])
        return ok, "replied", err

    outcome = retry(post_unless_answered)
    thread = find_thread(repo, args.pr, me, args.comment)
    if args.resolve and not thread.resolved:
        gh(["api", "graphql", "-f",
            "query=mutation($t:ID!){resolveReviewThread(input:{threadId:$t}){thread{isResolved}}}",
            "-f", f"t={thread.id}"])
    state = "resolved" if args.resolve or thread.resolved else "left open"
    print(f"comment {args.comment}: {outcome}; {state}")
    return 0


def _one_line(text: str) -> str:
    # A fork's pull request names its own workflow jobs, so a check name with a newline
    # could print a fake status line into the output the agent reads. Applied only when
    # printing: as a key, a cleaned name could merge two distinct checks.
    return "".join(c if c.isprintable() else " " for c in text)


def _check_states(rollup: list[dict[str, Any]]) -> dict[str, str]:
    states: dict[str, str] = {}
    for item in rollup:
        if item.get("__typename") == "StatusContext":
            name, state = item.get("context", ""), item.get("state", "")
            states[name] = "pending" if state in ("PENDING", "EXPECTED") else state.lower()
        else:
            name = item.get("name", "")
            done = item.get("status") == "COMPLETED"
            states[name] = (item.get("conclusion") or "").lower() if done else "pending"
    return states


def _reviewer_states(repo: str, pr: int, head: str, logins: list[str]) -> dict[str, str]:
    out = gh(["api", "--paginate", f"repos/{repo}/pulls/{pr}/reviews",
              "--jq", ".[] | [.user.login, .commit_id, (.body // \"\")] | @json"])
    reviews = [json.loads(line) for line in out.splitlines() if line.strip()]
    states: dict[str, str] = {}
    for login in logins:
        states[login] = "waiting"
        for who, commit, body in reviews:
            if same_login(who, login) and commit == head:
                states[login] = "did-not-review" if NOT_A_REVIEW.search(body) else "reviewed"
    return states


def cmd_wait(repo: str, args: argparse.Namespace, me: str) -> int:
    deadline = monotonic() + args.timeout
    while True:
        view = gh_json(["pr", "view", str(args.pr), "-R", repo,
                        "--json", "headRefOid,statusCheckRollup"])
        head = view["headRefOid"]
        if not head.startswith(args.head):
            print(f"head moved: {head} (expected {args.head})")
            return 4
        checks = _check_states(view.get("statusCheckRollup") or [])
        for wanted in args.check:
            if not any(wanted.lower() in name.lower() for name in checks):
                checks[wanted] = "missing"
        reviewers = _reviewer_states(repo, args.pr, head, args.reviewer)
        waiting = [n for n, s in checks.items() if s in ("pending", "missing")]
        if not checks and not args.reviewer:
            waiting.append("the first check on the head")
        waiting += [n for n, s in reviewers.items() if s == "waiting"]
        if not waiting or monotonic() >= deadline:
            for name, state in sorted(checks.items()):
                print(f"check {_one_line(name)}: {state}")
            for name, state in reviewers.items():
                print(f"reviewer {name}: {state}")
            open_ids = [str(t.comment) for t in load_threads(repo, args.pr, me) if not t.answered]
            print(f"unanswered threads: {len(open_ids)} {' '.join(open_ids)}".rstrip())
            if waiting:
                print(f"timed out waiting for: {', '.join(map(_one_line, waiting))}")
                return 3
            return 5 if "did-not-review" in reviewers.values() else 0
        sleep(min(args.interval, max(deadline - monotonic(), 0)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", help="OWNER/NAME (default: the current repository)")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("threads")
    p.add_argument("pr", type=int)
    p.add_argument("--unanswered", action="store_true")
    p = sub.add_parser("reply")
    p.add_argument("pr", type=int)
    p.add_argument("comment", type=int)
    body = p.add_mutually_exclusive_group(required=True)
    body.add_argument("--body")
    body.add_argument("--body-file")
    p.add_argument("--resolve", action="store_true")
    p = sub.add_parser("wait")
    p.add_argument("pr", type=int)
    p.add_argument("--head", required=True)
    p.add_argument("--check", action="append", default=[])
    p.add_argument("--reviewer", action="append", default=[])
    p.add_argument("--timeout", type=float, default=900)
    p.add_argument("--interval", type=float, default=30)
    args = parser.parse_args(argv)
    try:
        repo = args.repo or gh(["repo", "view", "--json", "nameWithOwner",
                                "--jq", ".nameWithOwner"]).strip()
        me = gh(["api", "user", "--jq", ".login"]).strip()
        command = {"threads": cmd_threads, "reply": cmd_reply, "wait": cmd_wait}[args.command]
        return command(repo, args, me)
    except (GhError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
