#!/usr/bin/env python3
"""Prepare targeted annotation rows for the heterogeneity-extension model.

This sample is designed to reduce public-correction label noise around the
high_early_audience_structural_heterogeneity effect. It should be used as a
targeted measurement check, not as a p-value tuning device.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCORE_BINS = [
    ("very_low", 0.0, 0.2),
    ("low_mid", 0.2, 0.4),
    ("near_negative", 0.4, 0.65),
    ("near_positive", 0.65, 0.9),
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


def load_comment_lookup(path: Path, text_limit: int) -> dict[str, dict[str, Any]]:
    rows = []
    for row in iter_jsonl(path):
        comment_id = normalize_token(row.get("comment_id"))
        if not comment_id:
            continue
        rows.append(
            {
                "comment_id": comment_id,
                "submission_id": normalize_token(row.get("submission_id")),
                "parent_id": normalize_token(row.get("parent_id")),
                "created_utc": to_float(row.get("created_utc")),
                "level": row.get("level", ""),
                "submission_title": compact_text(row.get("submission_title"), text_limit),
                "body": compact_text(row.get("body"), text_limit),
            }
        )

    rows_by_submission: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        rows_by_submission[row["submission_id"]].append(row)
    for items in rows_by_submission.values():
        items.sort(key=lambda item: (float(item["created_utc"]), str(item["comment_id"])))
        for rank, item in enumerate(items, 1):
            item["thread_comment_rank"] = rank

    lookup = {}
    for row in rows:
        lookup[row["comment_id"]] = {
            "submission_id": normalize_token(row.get("submission_id")),
            "parent_id": normalize_token(row.get("parent_id")),
            "created_utc": to_float(row.get("created_utc")),
            "level": row.get("level", ""),
            "thread_comment_rank": row.get("thread_comment_rank", 0),
            "submission_title": compact_text(row.get("submission_title"), text_limit),
            "body": compact_text(row.get("body"), text_limit),
        }
    return lookup


def load_thread_lookup(path: Path) -> dict[str, dict[str, str]]:
    keep_fields = [
        "comments",
        "unique_authors",
        "early_comments",
        "early_correction_norm_presence",
        "high_thread_hostility_climate",
        "high_thread_anti_institutional_climate",
        "high_early_audience_structural_heterogeneity",
        "high_audience_structural_heterogeneity",
        "high_early_discursive_heterogeneity",
        "high_thread_discursive_heterogeneity",
        "early_audience_cross_group_author_share",
        "audience_cross_group_author_share",
        "early_discursive_cue_entropy",
        "discursive_cue_entropy",
        "hostility_rate",
        "anti_institutional_rate",
    ]
    lookup = {}
    for row in read_csv(path):
        submission_id = normalize_token(row.get("submission_id"))
        if submission_id:
            lookup[submission_id] = {field: row.get(field, "") for field in keep_fields}
    return lookup


def load_qwen_lookup(path: Path | None) -> dict[str, dict[str, str]]:
    if not path or not path.exists():
        return {}
    keep_fields = [
        "combined_annotation_id",
        "annotation_id",
        "llm_label",
        "llm_confidence",
        "llm_correction_target",
        "annotation_source",
    ]
    lookup = {}
    for row in read_csv(path):
        comment_id = normalize_token(row.get("comment_id"))
        if comment_id:
            lookup[comment_id] = {field: row.get(field, "") for field in keep_fields}
    return lookup


def build_candidates(args: argparse.Namespace) -> list[dict[str, Any]]:
    existing_ids = load_existing_ids(args.exclude_annotations)
    comments = load_comment_lookup(args.comments, args.text_limit)
    threads = load_thread_lookup(args.thread_climate)
    qwen = load_qwen_lookup(args.qwen_annotations)

    candidates = []
    for row in read_csv(args.predictions):
        comment_id = normalize_token(row.get("comment_id"))
        if not comment_id or comment_id in existing_ids or comment_id not in comments:
            continue
        comment = comments[comment_id]
        submission_id = normalize_token(row.get("submission_id") or comment.get("submission_id"))
        thread = threads.get(submission_id)
        if not thread:
            continue
        created_utc = to_float(row.get("created_utc") or comment.get("created_utc"))
        score = to_float(row.get("public_correction_score"))
        early_comments = max(to_int(thread.get("early_comments")), args.early_n)
        level = to_int(comment.get("level"))
        thread_comment_rank = to_int(comment.get("thread_comment_rank"))
        later_focus = int(thread_comment_rank > args.early_n)
        item = {
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
            "created_utc": created_utc,
            "level": level,
            "thread_comment_rank": thread_comment_rank,
            "targeted_sampling_focus": "later_or_reply_comment" if later_focus else "early_top_level_comment",
            "submission_title": comment["submission_title"],
            "body": comment["body"],
            "in_qwen_annotations": 1 if comment_id in qwen else 0,
            "qwen_label": qwen.get(comment_id, {}).get("llm_label", ""),
            "qwen_confidence": qwen.get(comment_id, {}).get("llm_confidence", ""),
            **thread,
        }
        candidates.append(item)
    return candidates


def stratified_sample(candidates: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    rng = random.Random(args.seed)
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        key = (
            str(row["high_early_audience_structural_heterogeneity"]),
            str(row["early_correction_norm_presence"]),
            str(row["public_correction_pred"]),
            str(row["score_bin"]),
        )
        grouped[key].append(row)

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    target_high = math.ceil(args.target_rows * args.high_heterogeneity_share)
    target_low = args.target_rows - target_high

    def flag_count(flag: str) -> int:
        return sum(1 for row in selected if str(row["high_early_audience_structural_heterogeneity"]) == flag)

    def take_for_flag(flag: str, target: int) -> None:
        keys = sorted(key for key in grouped if key[0] == flag)
        per_key = max(1, math.ceil(target * 0.75 / max(len(keys), 1)))
        for key in keys:
            rows = grouped[key]
            for row in rows:
                row["_tie"] = rng.random()
            rows.sort(key=lambda row: (row["threshold_distance"], row["_tie"]))
            for row in rows[:per_key]:
                if flag_count(flag) >= target:
                    break
                if row["comment_id"] not in selected_ids:
                    selected.append(row)
                    selected_ids.add(row["comment_id"])
        if flag_count(flag) < target:
            remaining_same_flag = [
                row
                for row in candidates
                if str(row["high_early_audience_structural_heterogeneity"]) == flag
                and row["comment_id"] not in selected_ids
            ]
            for row in remaining_same_flag:
                row["_tie"] = rng.random()
            remaining_same_flag.sort(key=lambda row: (row["threshold_distance"], row["_tie"]))
            for row in remaining_same_flag:
                if flag_count(flag) >= target:
                    break
                selected.append(row)
                selected_ids.add(row["comment_id"])

    take_for_flag("1", target_high)
    take_for_flag("0", target_low)

    if len(selected) < args.target_rows:
        remaining = [row for row in candidates if row["comment_id"] not in selected_ids]
        for row in remaining:
            row["_tie"] = rng.random()
        remaining.sort(key=lambda row: (row["threshold_distance"], row["_tie"]))
        for row in remaining:
            if len(selected) >= args.target_rows:
                break
            selected.append(row)
            selected_ids.add(row["comment_id"])

    selected = selected[: args.target_rows]
    selected.sort(
        key=lambda row: (
            str(row["high_early_audience_structural_heterogeneity"]),
            str(row["early_correction_norm_presence"]),
            str(row["public_correction_pred"]),
            str(row["score_bin"]),
            float(row["threshold_distance"]),
        )
    )
    for idx, row in enumerate(selected, 1):
        row["annotation_id"] = f"HET{idx:05d}"
        row["is_public_correction"] = ""
        row["annotation_confidence"] = ""
        row["annotation_notes"] = ""
    return selected


def summarize(rows: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    def counts(field: str, pool: list[dict[str, Any]] = rows) -> dict[str, int]:
        return dict(sorted(Counter(str(row.get(field, "")) for row in pool).items()))

    return {
        "candidate_rows": len(candidates),
        "sample_rows": len(rows),
        "sample_by_high_early_audience_structural_heterogeneity": counts(
            "high_early_audience_structural_heterogeneity"
        ),
        "sample_by_early_correction_norm": counts("early_correction_norm_presence"),
        "sample_by_model_pred": counts("public_correction_pred"),
        "sample_by_score_bin": counts("score_bin"),
        "sample_by_community_group": counts("community_group_proxy"),
        "sample_by_qwen_presence": counts("in_qwen_annotations"),
        "candidate_by_high_early_audience_structural_heterogeneity": counts(
            "high_early_audience_structural_heterogeneity", candidates
        ),
    }


def run(args: argparse.Namespace) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir = args.output_dir / "metrics"
    tables_dir = args.output_dir / "tables"
    metrics_dir.mkdir(exist_ok=True)
    tables_dir.mkdir(exist_ok=True)

    candidates = build_candidates(args)
    selected = stratified_sample(candidates, args)

    blind_fields = [
        "annotation_id",
        "is_public_correction",
        "annotation_confidence",
        "annotation_notes",
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
        "candidate_correction",
        "public_correction_score",
        "public_correction_pred",
        "model_score",
        "model_pred",
        "score_bin",
        "threshold_distance",
        "targeted_sampling_focus",
        "high_early_audience_structural_heterogeneity",
        "early_audience_cross_group_author_share",
        "high_audience_structural_heterogeneity",
        "audience_cross_group_author_share",
        "early_correction_norm_presence",
        "high_thread_hostility_climate",
        "high_thread_anti_institutional_climate",
        "high_early_discursive_heterogeneity",
        "high_thread_discursive_heterogeneity",
        "early_discursive_cue_entropy",
        "discursive_cue_entropy",
        "comments",
        "unique_authors",
        "in_qwen_annotations",
        "qwen_label",
        "qwen_confidence",
    ]
    write_csv(args.output_dir / "annotation_sample_blind.csv", selected, blind_fields)
    write_csv(args.output_dir / "annotation_sample_with_metadata.csv", selected, blind_fields + metadata_fields)

    summary_rows = []
    for key, count in sorted(
        Counter(
            (
                row["high_early_audience_structural_heterogeneity"],
                row["early_correction_norm_presence"],
                row["public_correction_pred"],
                row["score_bin"],
            )
            for row in selected
        ).items()
    ):
        summary_rows.append(
            {
                "high_early_audience_structural_heterogeneity": key[0],
                "early_correction_norm_presence": key[1],
                "public_correction_pred": key[2],
                "score_bin": key[3],
                "rows": count,
            }
        )
    write_csv(
        tables_dir / "sample_strata_counts.csv",
        summary_rows,
        [
            "high_early_audience_structural_heterogeneity",
            "early_correction_norm_presence",
            "public_correction_pred",
            "score_bin",
            "rows",
        ],
    )

    summary = {
        "run_status": "heterogeneity_targeted_annotation_sample_prepared",
        "predictions": str(args.predictions),
        "comments": str(args.comments),
        "thread_climate": str(args.thread_climate),
        "qwen_annotations": str(args.qwen_annotations) if args.qwen_annotations else "",
        "exclude_annotations": [str(path) for path in args.exclude_annotations],
        "output_dir": str(args.output_dir),
        "target_rows": args.target_rows,
        "high_heterogeneity_share": args.high_heterogeneity_share,
        "threshold": args.threshold,
        "seed": args.seed,
        "text_limit": args.text_limit,
        "summary": summarize(selected, candidates),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(metrics_dir / "run_summary.json", summary)
    (args.output_dir / "run.log").write_text(
        "\n".join(
            [
                "heterogeneity targeted annotation sample run",
                f"generated_utc={summary['generated_utc']}",
                f"command={' '.join(__import__('sys').argv)}",
                f"candidate_rows={summary['summary']['candidate_rows']}",
                f"sample_rows={summary['summary']['sample_rows']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare heterogeneity-targeted public-correction annotation sample.")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--comments", type=Path, required=True)
    parser.add_argument("--thread-climate", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--qwen-annotations", type=Path)
    parser.add_argument("--exclude-annotations", type=Path, nargs="*", default=[])
    parser.add_argument("--target-rows", type=int, default=1200)
    parser.add_argument("--high-heterogeneity-share", type=float, default=0.60)
    parser.add_argument("--threshold", type=float, default=0.81201171875)
    parser.add_argument("--early-n", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260626)
    parser.add_argument("--text-limit", type=int, default=5000)
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
