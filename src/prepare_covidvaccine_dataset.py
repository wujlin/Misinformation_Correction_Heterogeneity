#!/usr/bin/env python3
"""Prepare the external Reddit COVID vaccine dataset for the pilot.

This script standardizes the downloaded GitHub dataset and creates a first-pass
candidate correction flag. The flag is deliberately conservative in naming: it
is a retrieval aid for annotation, not a validated correction label.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


CORRECTION_RE = re.compile(
    r"\b("
    r"false|misinformation|misleading|debunk|fact[- ]?check|"
    r"not true|isn't true|incorrect|wrong|no evidence|source\?|"
    r"cdc|who\.int|snopes|reuters"
    r")\b",
    flags=re.IGNORECASE,
)


def read_csv_rows(path: Path) -> Iterable[dict[str, str]]:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        yield from csv.DictReader(f)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def to_float(value: str) -> float | None:
    value = str(value or "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def to_int(value: str) -> int | None:
    number = to_float(value)
    if number is None:
        return None
    return int(number)


def standardize_submission(row: dict[str, str]) -> dict[str, Any]:
    return {
        "submission_id": row.get("Submission"),
        "subreddit": normalize_subreddit(row.get("Subreddit")),
        "author": row.get("Submission_Author"),
        "title": row.get("Submission_Title"),
        "url": row.get("URL"),
        "created_utc": to_float(row.get("Created_utc", "")),
        "original_submission": empty_to_none(row.get("Original_Submission")),
        "original_subreddit": normalize_subreddit(row.get("Original_Subreddit")),
        "source_dataset": "christinegu27/reddit_covidvaccine_data",
    }


def standardize_comment(row: dict[str, str]) -> dict[str, Any]:
    body = row.get("Body") or ""
    return {
        "comment_id": row.get("ID"),
        "created_utc": to_float(row.get("Date_utc", "")),
        "author": row.get("Author"),
        "body": body,
        "submission_id": row.get("Submission"),
        "parent_id": row.get("Parent_ID"),
        "parent_author": row.get("Parent_Author"),
        "level": to_int(row.get("Level", "")),
        "subreddit": normalize_subreddit(row.get("Subreddit")),
        "submission_author": row.get("Submission_Author"),
        "submission_title": row.get("Submission_Title"),
        "candidate_correction": bool(CORRECTION_RE.search(body)),
        "source_dataset": "christinegu27/reddit_covidvaccine_data",
    }


def empty_to_none(value: str | None) -> str | None:
    value = str(value or "").strip()
    if not value or value.lower() == "nan":
        return None
    return value


def normalize_subreddit(value: str | None) -> str | None:
    value = empty_to_none(value)
    return value.lower() if value else None


def build_thread_profiles(comments: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    authors_by_thread: dict[str, set[str]] = defaultdict(set)
    correction_authors_by_thread: dict[str, set[str]] = defaultdict(set)

    for comment in comments:
        submission_id = str(comment.get("submission_id") or "")
        if not submission_id:
            continue
        if submission_id not in stats:
            stats[submission_id] = {
                "submission_id": submission_id,
                "subreddit": comment.get("subreddit"),
                "submission_title": comment.get("submission_title"),
                "comments": 0,
                "candidate_corrections": 0,
            }
        stats[submission_id]["comments"] += 1
        author = str(comment.get("author") or "")
        if author:
            authors_by_thread[submission_id].add(author)
            if comment.get("candidate_correction"):
                correction_authors_by_thread[submission_id].add(author)
                stats[submission_id]["candidate_corrections"] += 1

    profiles = []
    for submission_id, row in stats.items():
        unique_authors = len(authors_by_thread[submission_id])
        candidate_correctors = len(correction_authors_by_thread[submission_id])
        row["unique_authors"] = unique_authors
        row["candidate_correctors"] = candidate_correctors
        row["exposed_but_not_candidate_correctors"] = max(unique_authors - candidate_correctors, 0)
        row["candidate_correction_rate"] = (
            row["candidate_corrections"] / row["comments"] if row["comments"] else 0
        )
        profiles.append(row)
    return sorted(profiles, key=lambda item: item["candidate_corrections"], reverse=True)


def run(args: argparse.Namespace) -> None:
    input_dir = args.input_dir
    submissions = [standardize_submission(row) for row in read_csv_rows(input_dir / "submissions.csv")]
    comments = [standardize_comment(row) for row in read_csv_rows(input_dir / "reddit_data.csv")]
    thread_profiles = build_thread_profiles(comments)

    submission_count = write_jsonl(args.out_submissions, submissions)
    comment_count = write_jsonl(args.out_comments, comments)
    profile_count = write_csv(
        args.out_threads,
        thread_profiles,
        [
            "submission_id",
            "subreddit",
            "comments",
            "unique_authors",
            "candidate_corrections",
            "candidate_correctors",
            "exposed_but_not_candidate_correctors",
            "candidate_correction_rate",
            "submission_title",
        ],
    )

    print(f"Wrote {submission_count} submissions to {args.out_submissions}")
    print(f"Wrote {comment_count} comments to {args.out_comments}")
    print(f"Wrote {profile_count} thread profiles to {args.out_threads}")
    print(
        "Candidate correction comments:",
        sum(1 for comment in comments if comment["candidate_correction"]),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare external Reddit COVID vaccine data.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/raw/external/reddit_covidvaccine_data"),
    )
    parser.add_argument(
        "--out-submissions",
        type=Path,
        default=Path("data/interim/covidvaccine_submissions.jsonl"),
    )
    parser.add_argument(
        "--out-comments",
        type=Path,
        default=Path("data/interim/covidvaccine_comments.jsonl"),
    )
    parser.add_argument(
        "--out-threads",
        type=Path,
        default=Path("data/interim/covidvaccine_thread_profiles.csv"),
    )
    return parser


def main() -> None:
    parser = build_parser()
    run(parser.parse_args())


if __name__ == "__main__":
    main()
