#!/usr/bin/env python3
"""Prepare random-audit and audience-relation annotation samples.

The random-audit component provides a cleaner external evaluation set. The
audience-relation component targets later comments in high/low early-audience
structural heterogeneity threads, which is the part of the data that can affect
the later-correction outcome model.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCORE_BINS = [
    ("very_low", 0.0, 0.2),
    ("low_mid", 0.2, 0.4),
    ("near_negative", 0.4, 0.5),
    ("near_positive", 0.5, 0.65),
    ("high_mid", 0.65, 0.9),
    ("very_high", 0.9, 1.0000001),
]


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


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


def compact_text(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit] if len(text) > limit else text


def to_float(value: Any) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def to_int(value: Any) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0


def score_bin(score: float) -> str:
    for name, low, high in SCORE_BINS:
        if low <= score < high:
            return name
    return "unknown"


def load_existing_ids(paths: list[Path]) -> set[str]:
    ids: set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        for row in read_csv(path):
            comment_id = normalize_token(row.get("comment_id"))
            if comment_id:
                ids.add(comment_id)
    return ids


def load_comments(path: Path, text_limit: int) -> dict[str, dict[str, Any]]:
    raw_rows = []
    for row in iter_jsonl(path):
        comment_id = normalize_token(row.get("comment_id"))
        if not comment_id:
            continue
        raw_rows.append(
            {
                "comment_id": comment_id,
                "submission_id": normalize_token(row.get("submission_id")),
                "parent_id": normalize_token(row.get("parent_id")),
                "created_utc": to_float(row.get("created_utc")),
                "level": to_int(row.get("level")),
                "submission_title": compact_text(row.get("submission_title"), text_limit),
                "body": compact_text(row.get("body"), text_limit),
            }
        )

    by_submission: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in raw_rows:
        by_submission[row["submission_id"]].append(row)
    for items in by_submission.values():
        items.sort(key=lambda item: (float(item["created_utc"]), str(item["comment_id"])))
        for rank, item in enumerate(items, 1):
            item["thread_comment_rank"] = rank

    return {row["comment_id"]: row for row in raw_rows}


def load_threads(path: Path) -> dict[str, dict[str, str]]:
    keep_fields = [
        "comments",
        "unique_authors",
        "early_comments",
        "early_correction_norm_presence",
        "high_early_audience_structural_heterogeneity",
        "early_audience_cross_group_author_share",
        "high_audience_structural_heterogeneity",
        "audience_cross_group_author_share",
        "high_early_discursive_heterogeneity",
        "early_discursive_cue_entropy",
        "high_thread_hostility_climate",
        "high_thread_anti_institutional_climate",
    ]
    out = {}
    for row in read_csv(path):
        submission_id = normalize_token(row.get("submission_id"))
        if submission_id:
            out[submission_id] = {field: row.get(field, "") for field in keep_fields}
    return out


def build_candidates(args: argparse.Namespace) -> list[dict[str, Any]]:
    existing_ids = load_existing_ids(args.exclude_annotations)
    comments = load_comments(args.comments, args.text_limit)
    threads = load_threads(args.thread_climate)
    candidates = []

    for row in read_csv(args.predictions):
        comment_id = normalize_token(row.get("comment_id"))
        if not comment_id or comment_id in existing_ids or comment_id not in comments:
            continue
        comment = comments[comment_id]
        submission_id = normalize_token(row.get("submission_id") or comment["submission_id"])
        thread = threads.get(submission_id)
        if not thread:
            continue
        score = to_float(row.get("public_correction_score"))
        rank = to_int(comment.get("thread_comment_rank"))
        is_later_comment = int(rank > args.early_n)
        candidates.append(
            {
                "comment_id": comment_id,
                "submission_id": submission_id,
                "parent_id": normalize_token(row.get("parent_id") or comment.get("parent_id")),
                "subreddit": normalize_token(row.get("subreddit")),
                "community_group_proxy": normalize_token(row.get("community_group_proxy")) or "unknown",
                "author": row.get("author", ""),
                "candidate_correction": to_int(row.get("candidate_correction")),
                "public_correction_score": score,
                "public_correction_pred": to_int(row.get("public_correction_pred")),
                "model_score": score,
                "model_pred": to_int(row.get("public_correction_pred")),
                "score_bin": score_bin(score),
                "threshold_distance": abs(score - args.threshold),
                "created_utc": to_float(row.get("created_utc") or comment.get("created_utc")),
                "level": to_int(comment.get("level")),
                "thread_comment_rank": rank,
                "is_later_comment": is_later_comment,
                "submission_title": comment.get("submission_title", ""),
                "body": comment.get("body", ""),
                **thread,
            }
        )
    return candidates


def add_annotation_fields(rows: list[dict[str, Any]]) -> None:
    for idx, row in enumerate(rows, 1):
        row["annotation_id"] = f"ARR{idx:05d}"
        row["is_public_correction"] = ""
        row["annotation_confidence"] = ""
        row["annotation_notes"] = ""


def simple_random_sample(rows: list[dict[str, Any]], target: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    pool = list(rows)
    rng.shuffle(pool)
    return pool[:target]


def relation_balanced_sample(
    rows: list[dict[str, Any]],
    target: int,
    seed: int,
    exclude_ids: set[str],
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    pool = [
        row
        for row in rows
        if row["comment_id"] not in exclude_ids
        and int(row["is_later_comment"]) == 1
        and str(row.get("high_early_audience_structural_heterogeneity")) in {"0", "1"}
    ]
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in pool:
        key = (
            str(row["high_early_audience_structural_heterogeneity"]),
            str(row.get("early_correction_norm_presence", "0")),
            str(row["public_correction_pred"]),
            str(row["score_bin"]),
        )
        grouped[key].append(row)

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()

    def flag_count(flag: str) -> int:
        return sum(1 for row in selected if str(row["high_early_audience_structural_heterogeneity"]) == flag)

    def take_for_flag(flag: str, flag_target: int) -> None:
        keys = sorted(key for key in grouped if key[0] == flag)
        if not keys:
            return
        per_key = max(1, flag_target // len(keys))
        for key in keys:
            stratum = grouped[key]
            for row in stratum:
                row["_tie"] = rng.random()
            stratum.sort(key=lambda row: (float(row["threshold_distance"]), row["_tie"]))
            for row in stratum[:per_key]:
                if flag_count(flag) >= flag_target:
                    break
                if row["comment_id"] not in selected_ids:
                    selected.append(row)
                    selected_ids.add(row["comment_id"])

        if flag_count(flag) < flag_target:
            remaining = [
                row
                for row in pool
                if row["comment_id"] not in selected_ids
                and str(row["high_early_audience_structural_heterogeneity"]) == flag
            ]
            for row in remaining:
                row["_tie"] = rng.random()
            remaining.sort(key=lambda row: (float(row["threshold_distance"]), row["_tie"]))
            for row in remaining:
                if flag_count(flag) >= flag_target:
                    break
                selected.append(row)
                selected_ids.add(row["comment_id"])

    high_target = target // 2
    low_target = target - high_target
    take_for_flag("1", high_target)
    take_for_flag("0", low_target)

    if len(selected) < target:
        remaining = [row for row in pool if row["comment_id"] not in selected_ids]
        for row in remaining:
            row["_tie"] = rng.random()
        remaining.sort(key=lambda row: (float(row["threshold_distance"]), row["_tie"]))
        for row in remaining:
            if len(selected) >= target:
                break
            selected.append(row)
            selected_ids.add(row["comment_id"])

    return selected[:target]


def counts(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(field, "")) for row in rows).items()))


def write_strata(path: Path, rows: list[dict[str, Any]]) -> None:
    counter = Counter(
        (
            row["sample_component"],
            row.get("high_early_audience_structural_heterogeneity", ""),
            row.get("early_correction_norm_presence", ""),
            row.get("public_correction_pred", ""),
            row.get("score_bin", ""),
            row.get("is_later_comment", ""),
        )
        for row in rows
    )
    out_rows = [
        {
            "sample_component": key[0],
            "high_early_audience_structural_heterogeneity": key[1],
            "early_correction_norm_presence": key[2],
            "public_correction_pred": key[3],
            "score_bin": key[4],
            "is_later_comment": key[5],
            "rows": value,
        }
        for key, value in sorted(counter.items())
    ]
    write_csv(
        path,
        out_rows,
        [
            "sample_component",
            "high_early_audience_structural_heterogeneity",
            "early_correction_norm_presence",
            "public_correction_pred",
            "score_bin",
            "is_later_comment",
            "rows",
        ],
    )


def run(args: argparse.Namespace) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir = args.output_dir / "metrics"
    tables_dir = args.output_dir / "tables"
    metrics_dir.mkdir(exist_ok=True)
    tables_dir.mkdir(exist_ok=True)

    candidates = build_candidates(args)

    random_rows = simple_random_sample(candidates, args.random_audit_rows, args.seed)
    for row in random_rows:
        row["sample_component"] = "random_audit"
    random_ids = {row["comment_id"] for row in random_rows}

    relation_rows = relation_balanced_sample(
        candidates,
        args.relation_rows,
        args.seed + 1,
        random_ids,
    )
    for row in relation_rows:
        row["sample_component"] = "audience_relation_later"

    selected = random_rows + relation_rows
    selected.sort(
        key=lambda row: (
            row["sample_component"],
            str(row.get("high_early_audience_structural_heterogeneity", "")),
            str(row.get("early_correction_norm_presence", "")),
            str(row.get("public_correction_pred", "")),
            str(row.get("score_bin", "")),
            float(row.get("threshold_distance", 0.0)),
        )
    )
    add_annotation_fields(selected)

    blind_fields = [
        "annotation_id",
        "is_public_correction",
        "annotation_confidence",
        "annotation_notes",
        "sample_component",
        "comment_id",
        "submission_id",
        "parent_id",
        "subreddit",
        "community_group_proxy",
        "level",
        "thread_comment_rank",
        "submission_title",
        "body",
    ]
    metadata_fields = [
        "author",
        "candidate_correction",
        "public_correction_score",
        "public_correction_pred",
        "model_score",
        "model_pred",
        "score_bin",
        "threshold_distance",
        "is_later_comment",
        "high_early_audience_structural_heterogeneity",
        "early_audience_cross_group_author_share",
        "high_audience_structural_heterogeneity",
        "audience_cross_group_author_share",
        "early_correction_norm_presence",
        "high_early_discursive_heterogeneity",
        "early_discursive_cue_entropy",
        "high_thread_hostility_climate",
        "high_thread_anti_institutional_climate",
        "comments",
        "unique_authors",
    ]
    write_csv(args.output_dir / "annotation_sample_blind.csv", selected, blind_fields)
    write_csv(args.output_dir / "annotation_sample_with_metadata.csv", selected, blind_fields + metadata_fields)
    write_strata(tables_dir / "sample_strata_counts.csv", selected)

    summary = {
        "run_status": "audience_relation_random_annotation_sample_prepared",
        "predictions": str(args.predictions),
        "comments": str(args.comments),
        "thread_climate": str(args.thread_climate),
        "exclude_annotations": [str(path) for path in args.exclude_annotations],
        "output_dir": str(args.output_dir),
        "candidate_rows": len(candidates),
        "sample_rows": len(selected),
        "random_audit_rows": len(random_rows),
        "relation_rows": len(relation_rows),
        "seed": args.seed,
        "threshold": args.threshold,
        "sample_by_component": counts(selected, "sample_component"),
        "sample_by_high_early_audience_structural_heterogeneity": counts(
            selected, "high_early_audience_structural_heterogeneity"
        ),
        "sample_by_model_pred": counts(selected, "public_correction_pred"),
        "sample_by_score_bin": counts(selected, "score_bin"),
        "sample_by_later_comment": counts(selected, "is_later_comment"),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(metrics_dir / "run_summary.json", summary)
    (args.output_dir / "run.log").write_text(
        "\n".join(
            [
                "audience relation random annotation sample run",
                f"generated_utc={summary['generated_utc']}",
                f"command={' '.join(__import__('sys').argv)}",
                f"candidate_rows={summary['candidate_rows']}",
                f"sample_rows={summary['sample_rows']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare random audit and audience-relation annotation sample.")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--comments", type=Path, required=True)
    parser.add_argument("--thread-climate", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--exclude-annotations", type=Path, nargs="*", default=[])
    parser.add_argument("--random-audit-rows", type=int, default=800)
    parser.add_argument("--relation-rows", type=int, default=1200)
    parser.add_argument("--threshold", type=float, default=0.23486328125)
    parser.add_argument("--early-n", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260626)
    parser.add_argument("--text-limit", type=int, default=5000)
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
