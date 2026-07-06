#!/usr/bin/env python3
"""Construct first correction-misallocation tables from predicted labels."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REMOVED_AUTHORS = {"", "[deleted]", "deleted", "automoderator"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def normalize_token(value: Any) -> str:
    return str(value or "").strip().lower()


def normalize_author(value: Any) -> str | None:
    author = normalize_token(value)
    if author in REMOVED_AUTHORS:
        return None
    return author


def to_int(value: Any) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0


def to_float(value: Any) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def div(num: int | float, den: int | float) -> float:
    return float(num) / float(den) if den else 0.0


def entropy(values: Counter[str]) -> float:
    total = sum(values.values())
    if not total:
        return 0.0
    out = 0.0
    for count in values.values():
        p = count / total
        out -= p * math.log(p)
    return out


def build_user_profiles(rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    subreddit_counts: dict[str, Counter[str]] = defaultdict(Counter)
    group_counts: dict[str, Counter[str]] = defaultdict(Counter)
    thread_sets: dict[str, set[str]] = defaultdict(set)

    for row in rows:
        author = normalize_author(row.get("author"))
        if not author:
            continue
        if author not in stats:
            stats[author] = {
                "author": author,
                "comments": 0,
                "predicted_public_corrections": 0,
            }
        stats[author]["comments"] += 1
        pred = to_int(row.get("public_correction_pred"))
        stats[author]["predicted_public_corrections"] += pred
        subreddit_counts[author][normalize_token(row.get("subreddit"))] += 1
        group_counts[author][normalize_token(row.get("community_group_proxy"))] += 1
        submission_id = normalize_token(row.get("submission_id"))
        if submission_id:
            thread_sets[author].add(submission_id)

    for author, item in stats.items():
        item["subreddits_observed"] = len(subreddit_counts[author])
        item["community_groups_observed"] = len(group_counts[author])
        item["subreddit_entropy"] = entropy(subreddit_counts[author])
        item["community_group_entropy"] = entropy(group_counts[author])
        item["threads_observed"] = len(thread_sets[author])
        item["cross_subreddit_observed"] = int(item["subreddits_observed"] > 1)
        item["cross_group_observed"] = int(item["community_groups_observed"] > 1)
        item["correction_rate"] = div(item["predicted_public_corrections"], item["comments"])

    return stats


def build_thread_author_rows(rows: list[dict[str, str]], users: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        author = normalize_author(row.get("author"))
        submission_id = normalize_token(row.get("submission_id"))
        if not author or not submission_id:
            continue
        key = (submission_id, author)
        if key not in grouped:
            user = users[author]
            grouped[key] = {
                "submission_id": submission_id,
                "author": author,
                "subreddit": normalize_token(row.get("subreddit")),
                "community_group_proxy": normalize_token(row.get("community_group_proxy")),
                "comments_in_thread": 0,
                "predicted_public_corrections_in_thread": 0,
                "corrected_in_thread": 0,
                "user_comments": user["comments"],
                "user_subreddits_observed": user["subreddits_observed"],
                "user_community_groups_observed": user["community_groups_observed"],
                "user_cross_subreddit_observed": user["cross_subreddit_observed"],
                "user_cross_group_observed": user["cross_group_observed"],
                "user_subreddit_entropy": user["subreddit_entropy"],
                "user_community_group_entropy": user["community_group_entropy"],
            }
        item = grouped[key]
        item["comments_in_thread"] += 1
        item["predicted_public_corrections_in_thread"] += to_int(row.get("public_correction_pred"))
        item["corrected_in_thread"] = int(item["predicted_public_corrections_in_thread"] > 0)
    return list(grouped.values())


def aggregate_participation(rows: list[dict[str, Any]], key_fields: list[str]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = tuple(row[field] for field in key_fields)
        if key not in grouped:
            grouped[key] = {field: row[field] for field in key_fields}
            grouped[key].update(
                {
                    "thread_author_instances": 0,
                    "correcting_instances": 0,
                    "comments_in_instances": 0,
                }
            )
        item = grouped[key]
        item["thread_author_instances"] += 1
        item["correcting_instances"] += int(row["corrected_in_thread"])
        item["comments_in_instances"] += int(row["comments_in_thread"])

    out = []
    for item in grouped.values():
        item["instance_correction_rate"] = div(item["correcting_instances"], item["thread_author_instances"])
        item["comment_intensity"] = div(item["comments_in_instances"], item["thread_author_instances"])
        out.append(item)
    return sorted(out, key=lambda item: tuple(str(item[field]) for field in key_fields))


def build_thread_profiles(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    authors: dict[str, set[str]] = defaultdict(set)
    correctors: dict[str, set[str]] = defaultdict(set)

    for row in rows:
        submission_id = normalize_token(row.get("submission_id"))
        if not submission_id:
            continue
        if submission_id not in stats:
            stats[submission_id] = {
                "submission_id": submission_id,
                "subreddit": normalize_token(row.get("subreddit")),
                "community_group_proxy": normalize_token(row.get("community_group_proxy")),
                "comments": 0,
                "candidate_corrections": 0,
                "predicted_public_corrections": 0,
                "max_public_correction_score": 0.0,
            }
        item = stats[submission_id]
        item["comments"] += 1
        item["candidate_corrections"] += to_int(row.get("candidate_correction"))
        pred = to_int(row.get("public_correction_pred"))
        item["predicted_public_corrections"] += pred
        item["max_public_correction_score"] = max(item["max_public_correction_score"], to_float(row.get("public_correction_score")))
        author = normalize_author(row.get("author"))
        if author:
            authors[submission_id].add(author)
            if pred:
                correctors[submission_id].add(author)

    out = []
    for submission_id, item in stats.items():
        item["unique_authors"] = len(authors[submission_id])
        item["predicted_correctors"] = len(correctors[submission_id])
        item["exposed_but_not_predicted_correctors"] = max(item["unique_authors"] - item["predicted_correctors"], 0)
        item["predicted_comment_rate"] = div(item["predicted_public_corrections"], item["comments"])
        item["predicted_author_rate"] = div(item["predicted_correctors"], item["unique_authors"])
        item["has_predicted_public_correction"] = int(item["predicted_public_corrections"] > 0)
        item["high_participation_no_predicted_correction"] = int(
            item["unique_authors"] >= 20 and item["predicted_public_corrections"] == 0
        )
        out.append(item)
    return sorted(out, key=lambda item: (item["high_participation_no_predicted_correction"], item["unique_authors"]), reverse=True)


def aggregate_threads_by_group(thread_profiles: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in thread_profiles:
        value = str(row.get(key) or "unknown")
        if value not in grouped:
            grouped[value] = {
                key: value,
                "threads": 0,
                "threads_with_predicted_correction": 0,
                "high_participation_no_predicted_correction_threads": 0,
                "comments": 0,
                "unique_authors_sum": 0,
                "predicted_public_corrections": 0,
                "exposed_but_not_predicted_correctors": 0,
            }
        item = grouped[value]
        item["threads"] += 1
        item["threads_with_predicted_correction"] += int(row["has_predicted_public_correction"])
        item["high_participation_no_predicted_correction_threads"] += int(
            row["high_participation_no_predicted_correction"]
        )
        item["comments"] += int(row["comments"])
        item["unique_authors_sum"] += int(row["unique_authors"])
        item["predicted_public_corrections"] += int(row["predicted_public_corrections"])
        item["exposed_but_not_predicted_correctors"] += int(row["exposed_but_not_predicted_correctors"])

    out = []
    for item in grouped.values():
        item["thread_correction_presence_rate"] = div(item["threads_with_predicted_correction"], item["threads"])
        item["high_participation_no_correction_thread_rate"] = div(
            item["high_participation_no_predicted_correction_threads"], item["threads"]
        )
        item["predicted_corrections_per_thread"] = div(item["predicted_public_corrections"], item["threads"])
        item["exposed_noncorrectors_per_thread"] = div(item["exposed_but_not_predicted_correctors"], item["threads"])
        out.append(item)
    return sorted(out, key=lambda item: item["high_participation_no_correction_thread_rate"], reverse=True)


def run(args: argparse.Namespace) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = args.output_dir / "tables"
    metrics_dir = args.output_dir / "metrics"
    tables_dir.mkdir(exist_ok=True)
    metrics_dir.mkdir(exist_ok=True)

    rows = read_csv(args.predictions)
    users = build_user_profiles(rows)
    thread_author_rows = build_thread_author_rows(rows, users)
    thread_profiles = build_thread_profiles(rows)
    by_cross_group = aggregate_participation(
        thread_author_rows, ["community_group_proxy", "user_cross_group_observed"]
    )
    by_cross_subreddit = aggregate_participation(
        thread_author_rows, ["community_group_proxy", "user_cross_subreddit_observed"]
    )
    thread_group_profiles = aggregate_threads_by_group(thread_profiles, "community_group_proxy")
    thread_subreddit_profiles = aggregate_threads_by_group(thread_profiles, "subreddit")
    high_participation_no_correction = [
        row for row in thread_profiles if row["high_participation_no_predicted_correction"]
    ][:200]

    write_csv(
        tables_dir / "thread_author_by_cross_group.csv",
        by_cross_group,
        [
            "community_group_proxy",
            "user_cross_group_observed",
            "thread_author_instances",
            "correcting_instances",
            "comments_in_instances",
            "instance_correction_rate",
            "comment_intensity",
        ],
    )
    write_csv(
        tables_dir / "thread_author_by_cross_subreddit.csv",
        by_cross_subreddit,
        [
            "community_group_proxy",
            "user_cross_subreddit_observed",
            "thread_author_instances",
            "correcting_instances",
            "comments_in_instances",
            "instance_correction_rate",
            "comment_intensity",
        ],
    )
    write_csv(
        tables_dir / "thread_group_profiles.csv",
        thread_group_profiles,
        [
            "community_group_proxy",
            "threads",
            "threads_with_predicted_correction",
            "high_participation_no_predicted_correction_threads",
            "comments",
            "unique_authors_sum",
            "predicted_public_corrections",
            "exposed_but_not_predicted_correctors",
            "thread_correction_presence_rate",
            "high_participation_no_correction_thread_rate",
            "predicted_corrections_per_thread",
            "exposed_noncorrectors_per_thread",
        ],
    )
    write_csv(
        tables_dir / "thread_subreddit_profiles.csv",
        thread_subreddit_profiles,
        [
            "subreddit",
            "threads",
            "threads_with_predicted_correction",
            "high_participation_no_predicted_correction_threads",
            "comments",
            "unique_authors_sum",
            "predicted_public_corrections",
            "exposed_but_not_predicted_correctors",
            "thread_correction_presence_rate",
            "high_participation_no_correction_thread_rate",
            "predicted_corrections_per_thread",
            "exposed_noncorrectors_per_thread",
        ],
    )
    write_csv(
        tables_dir / "high_participation_no_predicted_correction_threads_top200.csv",
        high_participation_no_correction,
        [
            "submission_id",
            "subreddit",
            "community_group_proxy",
            "comments",
            "unique_authors",
            "candidate_corrections",
            "predicted_public_corrections",
            "predicted_correctors",
            "exposed_but_not_predicted_correctors",
            "max_public_correction_score",
        ],
    )

    summary = {
        "run_status": "exploratory_correction_misallocation_tables",
        "predictions": str(args.predictions),
        "output_dir": str(args.output_dir),
        "comments": len(rows),
        "users": len(users),
        "thread_author_instances": len(thread_author_rows),
        "threads": len(thread_profiles),
        "predicted_public_corrections": sum(to_int(row.get("public_correction_pred")) for row in rows),
        "threads_with_predicted_correction": sum(row["has_predicted_public_correction"] for row in thread_profiles),
        "high_participation_no_predicted_correction_threads": len(
            [row for row in thread_profiles if row["high_participation_no_predicted_correction"]]
        ),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(metrics_dir / "run_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build exploratory correction-misallocation tables.")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
