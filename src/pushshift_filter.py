#!/usr/bin/env python3
"""Filter local Pushshift/Watchful1 Reddit archive files for the pilot.

The script reads zstandard-compressed ndjson files downloaded from archive
datasets and extracts a small claim-focused sample. It does not contact Reddit.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, TextIO


QUOTE_RE = re.compile(r'"([^"]+)"')


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def open_archive_text(path: Path) -> tuple[TextIO, subprocess.Popen[str] | None]:
    if path.suffix == ".zst":
        process = subprocess.Popen(
            ["zstd", "-dc", str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if process.stdout is None:
            raise RuntimeError(f"Could not open zstd stream for {path}")
        return process.stdout, process
    return path.open("r", encoding="utf-8", errors="replace"), None


def iter_archive_rows(path: Path) -> Iterable[dict[str, Any]]:
    stream, process = open_archive_text(path)
    try:
        for line_number, line in enumerate(stream, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                print(f"WARNING: bad JSON in {path}:{line_number}", file=sys.stderr)
    finally:
        stream.close()
        if process:
            stderr = process.stderr.read() if process.stderr else ""
            return_code = process.wait()
            if return_code != 0:
                raise RuntimeError(f"zstd failed for {path}: {stderr.strip()}")


def normalize_text(value: Any) -> str:
    return str(value or "").lower()


def query_terms(query: str) -> list[str]:
    quoted = [term.lower() for term in QUOTE_RE.findall(query)]
    if quoted:
        return quoted
    return [term.lower() for term in query.split() if term.strip()]


def claim_matches(text: str, claim: dict[str, Any]) -> tuple[bool, str | None]:
    for query in claim.get("queries", []):
        terms = query_terms(str(query))
        if terms and all(term in text for term in terms):
            return True, str(query)
    return False, None


def normalize_submission(raw: dict[str, Any], claim: dict[str, Any], matched_query: str, source_file: Path) -> dict[str, Any]:
    permalink = raw.get("permalink")
    if permalink and str(permalink).startswith("/"):
        permalink = f"https://www.reddit.com{permalink}"
    return {
        "claim_id": claim["claim_id"],
        "claim": claim.get("claim"),
        "matched_query": matched_query,
        "submission_id": raw.get("id"),
        "submission_fullname": raw.get("name") or f"t3_{raw.get('id')}",
        "subreddit": raw.get("subreddit"),
        "author": raw.get("author"),
        "title": raw.get("title"),
        "selftext": raw.get("selftext"),
        "score": raw.get("score"),
        "num_comments": raw.get("num_comments"),
        "created_utc": raw.get("created_utc"),
        "permalink": permalink,
        "url": raw.get("url"),
        "archive_source": str(source_file),
    }


def normalize_comment(raw: dict[str, Any], submission_lookup: dict[str, dict[str, Any]], source_file: Path) -> dict[str, Any]:
    link_id = str(raw.get("link_id") or "")
    submission_id = link_id.replace("t3_", "")
    submission = submission_lookup[submission_id]
    permalink = raw.get("permalink")
    if permalink and str(permalink).startswith("/"):
        permalink = f"https://www.reddit.com{permalink}"
    return {
        "claim_id": submission.get("claim_id"),
        "submission_id": submission_id,
        "comment_id": raw.get("id"),
        "comment_fullname": raw.get("name") or f"t1_{raw.get('id')}",
        "parent_id": raw.get("parent_id"),
        "link_id": link_id,
        "subreddit": raw.get("subreddit") or submission.get("subreddit"),
        "author": raw.get("author"),
        "body": raw.get("body"),
        "score": raw.get("score"),
        "created_utc": raw.get("created_utc"),
        "permalink": permalink,
        "archive_source": str(source_file),
    }


def run_submissions(args: argparse.Namespace) -> None:
    claims = read_json(args.claims)
    per_claim_counts = {claim["claim_id"]: 0 for claim in claims}
    seen: set[tuple[str, str]] = set()
    rows: list[dict[str, Any]] = []

    for input_path in args.inputs:
        print(f"Scanning submissions: {input_path}", file=sys.stderr)
        for raw in iter_archive_rows(input_path):
            text = " ".join([normalize_text(raw.get("title")), normalize_text(raw.get("selftext"))])
            for claim in claims:
                claim_id = claim["claim_id"]
                if args.limit_per_claim and per_claim_counts[claim_id] >= args.limit_per_claim:
                    continue
                matched, matched_query = claim_matches(text, claim)
                if not matched or matched_query is None:
                    continue
                key = (claim_id, str(raw.get("id")))
                if key in seen:
                    continue
                seen.add(key)
                per_claim_counts[claim_id] += 1
                rows.append(normalize_submission(raw, claim, matched_query, input_path))

    count = write_jsonl(args.out, rows)
    print(f"Wrote {count} submissions to {args.out}", file=sys.stderr)
    print(f"Per-claim counts: {per_claim_counts}", file=sys.stderr)


def load_submission_lookup(path: Path) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in iter_jsonl(path):
        submission_id = str(row.get("submission_id") or "")
        if submission_id:
            lookup[submission_id] = row
    return lookup


def run_comments(args: argparse.Namespace) -> None:
    submission_lookup = load_submission_lookup(args.submissions)
    if not submission_lookup:
        raise RuntimeError(f"No submissions found in {args.submissions}")

    rows: list[dict[str, Any]] = []
    target_link_ids = {f"t3_{submission_id}" for submission_id in submission_lookup}

    for input_path in args.inputs:
        print(f"Scanning comments: {input_path}", file=sys.stderr)
        for raw in iter_archive_rows(input_path):
            link_id = str(raw.get("link_id") or "")
            if link_id not in target_link_ids:
                continue
            rows.append(normalize_comment(raw, submission_lookup, input_path))

    count = write_jsonl(args.out, rows)
    print(f"Wrote {count} comments to {args.out}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Filter local Pushshift/Watchful1 Reddit archives.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    submissions = subparsers.add_parser("submissions", help="Filter archive submissions by pilot claims.")
    submissions.add_argument("--claims", type=Path, default=Path("config/pilot_claims.json"))
    submissions.add_argument("--inputs", type=Path, nargs="+", required=True)
    submissions.add_argument("--out", type=Path, default=Path("data/interim/archive_candidate_submissions.jsonl"))
    submissions.add_argument("--limit-per-claim", type=int, default=200)
    submissions.set_defaults(func=run_submissions)

    comments = subparsers.add_parser("comments", help="Collect comments for filtered submissions.")
    comments.add_argument("--submissions", type=Path, default=Path("data/interim/archive_candidate_submissions.jsonl"))
    comments.add_argument("--inputs", type=Path, nargs="+", required=True)
    comments.add_argument("--out", type=Path, default=Path("data/interim/archive_candidate_comments.jsonl"))
    comments.set_defaults(func=run_comments)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
