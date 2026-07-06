#!/usr/bin/env python3
"""Optional Reddit collector for correction misallocation research.

The live Reddit API route is not assumed by the current project because the
Reddit for Researchers request was not approved. This script is retained only
for users who have their own valid Reddit API access.

The script intentionally keeps collection small:

- search Reddit submissions for predefined misinformation queries;
- fetch comment trees for candidate submissions;
- write JSONL outputs for downstream annotation and network construction.

It uses Reddit OAuth when REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET are set.
When credentials are absent, the script stops unless the user explicitly opts
into public JSON endpoints. Browser login cookies are not supported as a
default access route.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable


DEFAULT_USER_AGENT = "misinformation-correction-pilot/0.1"


def load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE pairs without adding a dependency."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


class RedditClient:
    def __init__(self, user_agent: str, sleep_seconds: float = 1.0, allow_public_json: bool = False) -> None:
        self.user_agent = user_agent
        self.sleep_seconds = sleep_seconds
        self.allow_public_json = allow_public_json
        self.access_token = self._get_access_token()
        if not self.access_token and not self.allow_public_json:
            raise RuntimeError(
                "No Reddit OAuth credentials found. Set REDDIT_CLIENT_ID and "
                "REDDIT_CLIENT_SECRET, or pass --allow-public-json after "
                "confirming that this access route is appropriate for your use case."
            )

    @property
    def using_oauth(self) -> bool:
        return bool(self.access_token)

    def _get_access_token(self) -> str | None:
        client_id = os.environ.get("REDDIT_CLIENT_ID", "").strip()
        client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "").strip()
        if not client_id or not client_secret:
            return None

        credentials = f"{client_id}:{client_secret}".encode("utf-8")
        auth = base64.b64encode(credentials).decode("ascii")
        body = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode("utf-8")
        request = urllib.request.Request(
            "https://www.reddit.com/api/v1/access_token",
            data=body,
            headers={
                "Authorization": f"Basic {auth}",
                "User-Agent": self.user_agent,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        data = self._open_json(request)
        return data.get("access_token")

    def _open_json(self, request: urllib.request.Request) -> Any:
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            if len(message) > 1_000:
                message = message[:1_000] + "... [truncated]"
            raise RuntimeError(f"HTTP {exc.code} for {request.full_url}: {message}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Request failed for {request.full_url}: {exc}") from exc
        time.sleep(self.sleep_seconds)
        return json.loads(raw)

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        if params:
            query = urllib.parse.urlencode(params)
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{query}"

        headers = {"User-Agent": self.user_agent}
        if self.access_token:
            headers["Authorization"] = f"bearer {self.access_token}"

        request = urllib.request.Request(url, headers=headers)
        return self._open_json(request)

    def search_submissions(self, query: str, limit: int, sort: str) -> list[dict[str, Any]]:
        params = {
            "q": query,
            "limit": min(limit, 100),
            "sort": sort,
            "type": "link",
            "raw_json": 1,
        }
        if self.using_oauth:
            url = "https://oauth.reddit.com/search"
        else:
            url = "https://www.reddit.com/search.json"
        data = self.get_json(url, params)
        children = data.get("data", {}).get("children", [])
        return [child.get("data", {}) for child in children if child.get("kind") == "t3"]

    def fetch_comments(self, submission_id: str, limit: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        params = {
            "limit": min(limit, 500),
            "depth": 10,
            "raw_json": 1,
        }
        if self.using_oauth:
            url = f"https://oauth.reddit.com/comments/{submission_id}"
        else:
            url = f"https://www.reddit.com/comments/{submission_id}.json"
        data = self.get_json(url, params)
        if not isinstance(data, list) or len(data) < 2:
            raise RuntimeError(f"Unexpected comments payload for {submission_id}")
        submission = data[0].get("data", {}).get("children", [{}])[0].get("data", {})
        comments = list(flatten_comments(data[1].get("data", {}).get("children", [])))
        return submission, comments


def flatten_comments(children: list[dict[str, Any]], depth: int = 0) -> Iterable[dict[str, Any]]:
    for child in children:
        if child.get("kind") != "t1":
            continue
        data = child.get("data", {})
        data["_depth"] = depth
        yield data
        replies = data.get("replies")
        if isinstance(replies, dict):
            reply_children = replies.get("data", {}).get("children", [])
            yield from flatten_comments(reply_children, depth + 1)


def normalize_submission(raw: dict[str, Any], claim: dict[str, Any], query: str) -> dict[str, Any]:
    return {
        "claim_id": claim["claim_id"],
        "claim": claim.get("claim"),
        "query": query,
        "submission_id": raw.get("id"),
        "submission_fullname": raw.get("name"),
        "subreddit": raw.get("subreddit"),
        "author": raw.get("author"),
        "title": raw.get("title"),
        "selftext": raw.get("selftext"),
        "score": raw.get("score"),
        "upvote_ratio": raw.get("upvote_ratio"),
        "num_comments": raw.get("num_comments"),
        "created_utc": raw.get("created_utc"),
        "permalink": absolute_permalink(raw.get("permalink")),
        "url": raw.get("url"),
        "over_18": raw.get("over_18"),
    }


def normalize_comment(raw: dict[str, Any], claim_id: str, submission_id: str, submission_subreddit: str) -> dict[str, Any]:
    return {
        "claim_id": claim_id,
        "submission_id": submission_id,
        "comment_id": raw.get("id"),
        "comment_fullname": raw.get("name"),
        "parent_id": raw.get("parent_id"),
        "link_id": raw.get("link_id"),
        "subreddit": raw.get("subreddit") or submission_subreddit,
        "author": raw.get("author"),
        "body": raw.get("body"),
        "score": raw.get("score"),
        "created_utc": raw.get("created_utc"),
        "depth": raw.get("_depth"),
        "permalink": absolute_permalink(raw.get("permalink")),
        "is_submitter": raw.get("is_submitter"),
        "distinguished": raw.get("distinguished"),
    }


def absolute_permalink(permalink: str | None) -> str | None:
    if not permalink:
        return None
    if permalink.startswith("http"):
        return permalink
    return f"https://www.reddit.com{permalink}"


def dedupe_submissions(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    out = []
    for row in rows:
        key = (str(row.get("claim_id")), str(row.get("submission_id")))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def run_search(args: argparse.Namespace) -> None:
    claims = read_json(args.claims)
    client = None if args.dry_run else RedditClient(args.user_agent, args.sleep, allow_public_json=args.allow_public_json)
    access_mode = "dry-run" if client is None else ("oauth" if client.using_oauth else "public-json")
    print(f"Access mode: {access_mode}", file=sys.stderr)

    rows = []
    for claim in claims:
        for query in claim.get("queries", []):
            print(f"Searching {claim['claim_id']}: {query}", file=sys.stderr)
            if args.dry_run:
                continue
            assert client is not None
            submissions = client.search_submissions(query, args.limit_per_query, args.sort)
            rows.extend(normalize_submission(item, claim, query) for item in submissions)

    if args.dry_run:
        print("Dry run complete; no output file written.", file=sys.stderr)
        return

    rows = dedupe_submissions(rows)
    count = write_jsonl(args.out, rows)
    print(f"Wrote {count} submissions to {args.out}", file=sys.stderr)


def run_comments(args: argparse.Namespace) -> None:
    client = None if args.dry_run else RedditClient(args.user_agent, args.sleep, allow_public_json=args.allow_public_json)
    access_mode = "dry-run" if client is None else ("oauth" if client.using_oauth else "public-json")
    print(f"Access mode: {access_mode}", file=sys.stderr)

    submissions = list(iter_jsonl(args.submissions))
    if args.limit_submissions:
        submissions = submissions[: args.limit_submissions]

    rows = []
    for i, submission in enumerate(submissions, 1):
        submission_id = submission.get("submission_id")
        if not submission_id:
            continue
        print(f"[{i}/{len(submissions)}] Fetching comments for {submission_id}", file=sys.stderr)
        if args.dry_run:
            continue
        assert client is not None
        try:
            fetched_submission, comments = client.fetch_comments(submission_id, args.comment_limit)
        except RuntimeError as exc:
            print(f"WARNING: {exc}", file=sys.stderr)
            continue
        subreddit = fetched_submission.get("subreddit") or submission.get("subreddit")
        for comment in comments:
            rows.append(
                normalize_comment(
                    comment,
                    claim_id=str(submission.get("claim_id")),
                    submission_id=str(submission_id),
                    submission_subreddit=str(subreddit),
                )
            )

    if args.dry_run:
        print("Dry run complete; no output file written.", file=sys.stderr)
        return

    count = write_jsonl(args.out, rows)
    print(f"Wrote {count} comments to {args.out}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect pilot Reddit data.")
    parser.add_argument("--env", type=Path, default=Path(".env"), help="Path to optional .env file.")
    parser.add_argument(
        "--user-agent",
        default=os.environ.get("REDDIT_USER_AGENT", DEFAULT_USER_AGENT),
        help="Reddit API user agent.",
    )
    parser.add_argument("--sleep", type=float, default=1.0, help="Seconds to sleep between requests.")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without requesting data.")
    parser.add_argument(
        "--allow-public-json",
        action="store_true",
        help="Explicitly allow unauthenticated public JSON endpoints when OAuth credentials are absent.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="Search submissions for pilot claims.")
    search.add_argument("--claims", type=Path, default=Path("config/pilot_claims.json"))
    search.add_argument("--out", type=Path, default=Path("data/raw/reddit_submissions.jsonl"))
    search.add_argument("--limit-per-query", type=int, default=25)
    search.add_argument("--sort", choices=["relevance", "hot", "top", "new", "comments"], default="relevance")
    search.set_defaults(func=run_search)

    comments = subparsers.add_parser("comments", help="Fetch comments for collected submissions.")
    comments.add_argument("--submissions", type=Path, default=Path("data/raw/reddit_submissions.jsonl"))
    comments.add_argument("--out", type=Path, default=Path("data/raw/reddit_comments.jsonl"))
    comments.add_argument("--limit-submissions", type=int, default=50)
    comments.add_argument("--comment-limit", type=int, default=500)
    comments.set_defaults(func=run_comments)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    load_dotenv(args.env)
    if args.user_agent == DEFAULT_USER_AGENT and os.environ.get("REDDIT_USER_AGENT"):
        args.user_agent = str(os.environ["REDDIT_USER_AGENT"])
    args.func(args)


if __name__ == "__main__":
    main()
