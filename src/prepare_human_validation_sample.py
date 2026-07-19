#!/usr/bin/env python3
"""Prepare a blind human-validation sample for public-correction labels."""

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
    ("near_negative", 0.4, 0.5),
    ("near_positive", 0.5, 0.6),
    ("high_mid", 0.6, 0.8),
    ("very_high", 0.8, 1.0000001),
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


def compact_text(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit] if len(text) > limit else text


def normalize_token(value: Any) -> str:
    return str(value or "").strip().lower()


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


def load_comment_lookup(path: Path, text_limit: int) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in iter_jsonl(path):
        comment_id = normalize_token(row.get("comment_id"))
        if not comment_id:
            continue
        lookup[comment_id] = {
            "submission_title": compact_text(row.get("submission_title"), text_limit),
            "body": compact_text(row.get("body"), text_limit),
            "level": row.get("level", ""),
            "parent_id": normalize_token(row.get("parent_id")),
            "parent_author": row.get("parent_author", ""),
        }
    return lookup


def load_climate_lookup(path: Path | None) -> dict[str, dict[str, str]]:
    if not path or not path.exists():
        return {}
    keep_fields = [
        "comments",
        "unique_authors",
        "predicted_public_corrections",
        "has_predicted_public_correction",
        "later_predicted_public_corrections",
        "hostility_rate",
        "anti_institutional_rate",
        "early_correction_norm_presence",
        "sanction_to_correction_presence",
        "high_thread_hostility_climate",
        "high_thread_anti_institutional_climate",
        "high_early_hostility_climate",
        "high_early_anti_institutional_climate",
    ]
    lookup = {}
    for row in read_csv(path):
        submission_id = normalize_token(row.get("submission_id"))
        if submission_id:
            lookup[submission_id] = {field: row.get(field, "") for field in keep_fields}
    return lookup


def load_manual_lookup(path: Path | None) -> dict[str, dict[str, str]]:
    if not path or not path.exists():
        return {}
    keep_fields = [
        "combined_annotation_id",
        "annotation_id",
        "manual_label",
        "manual_confidence",
        "manual_correction_target",
        "annotation_source",
    ]
    lookup = {}
    for row in read_csv(path):
        comment_id = normalize_token(row.get("comment_id"))
        if comment_id:
            lookup[comment_id] = {field: row.get(field, "") for field in keep_fields}
    return lookup


def build_candidates(args: argparse.Namespace) -> list[dict[str, Any]]:
    comments = load_comment_lookup(args.comments, args.text_limit)
    climate = load_climate_lookup(args.thread_climate)
    manual = load_manual_lookup(args.manual_annotations)

    candidates = []
    for row in read_csv(args.predictions):
        comment_id = normalize_token(row.get("comment_id"))
        if not comment_id or comment_id not in comments:
            continue
        submission_id = normalize_token(row.get("submission_id"))
        parent_id = normalize_token(row.get("parent_id") or comments[comment_id].get("parent_id"))
        score = to_float(row.get("public_correction_score"))
        comment = comments[comment_id]
        parent = comments.get(parent_id, {})
        manual_row = manual.get(comment_id, {})
        climate_row = climate.get(submission_id, {})
        candidates.append(
            {
                "comment_id": comment_id,
                "submission_id": submission_id,
                "parent_id": parent_id,
                "subreddit": normalize_token(row.get("subreddit")),
                "community_group_proxy": normalize_token(row.get("community_group_proxy")) or "unknown",
                "author": row.get("author", ""),
                "candidate_correction": to_int(row.get("candidate_correction")),
                "public_correction_score": score,
                "public_correction_pred": to_int(row.get("public_correction_pred")),
                "score_bin": score_bin(score),
                "uncertainty_distance": abs(score - 0.5),
                "created_utc": row.get("created_utc", ""),
                "level": comment.get("level", ""),
                "submission_title": comment.get("submission_title", ""),
                "parent_body": compact_text(parent.get("body", ""), args.text_limit),
                "body": comment.get("body", ""),
                "in_manual_annotations": 1 if manual_row else 0,
                "manual_label": manual_row.get("manual_label", ""),
                "manual_confidence": manual_row.get("manual_confidence", ""),
                "manual_annotation_id": manual_row.get("combined_annotation_id") or manual_row.get("annotation_id", ""),
                "manual_annotation_source": manual_row.get("annotation_source", ""),
                **climate_row,
            }
        )
    return candidates


def stratified_take(
    rows: list[dict[str, Any]],
    target_rows: int,
    seed: int,
    exclude_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    exclude_ids = exclude_ids or set()
    pool = [row for row in rows if row["comment_id"] not in exclude_ids]
    if not pool or target_rows <= 0:
        return []

    rng = random.Random(seed)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in pool:
        grouped[(row["community_group_proxy"], row["score_bin"])].append(row)

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    keys = sorted(grouped)
    per_stratum = max(1, math.ceil(target_rows * 0.75 / max(len(keys), 1)))

    for key in keys:
        stratum_rows = grouped[key]
        for row in stratum_rows:
            row["_tie"] = rng.random()
        stratum_rows.sort(key=lambda row: (row["uncertainty_distance"], row["_tie"]))
        for row in stratum_rows[:per_stratum]:
            selected.append(row)
            selected_ids.add(row["comment_id"])

    if len(selected) < target_rows:
        remaining = [row for row in pool if row["comment_id"] not in selected_ids]
        for row in remaining:
            row["_tie"] = rng.random()
        remaining.sort(key=lambda row: (row["uncertainty_distance"], row["_tie"]))
        for row in remaining:
            if len(selected) >= target_rows:
                break
            selected.append(row)
            selected_ids.add(row["comment_id"])

    if len(selected) > target_rows:
        selected.sort(key=lambda row: (row["uncertainty_distance"], row["community_group_proxy"], row["score_bin"]))
        selected = selected[:target_rows]

    return selected


def prepare_sample(candidates: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    manual_pool = [row for row in candidates if row.get("in_manual_annotations") == 1]
    manual_target = min(args.min_manual_rows, args.target_rows, len(manual_pool))
    selected = stratified_take(manual_pool, manual_target, args.seed)
    selected_ids = {row["comment_id"] for row in selected}

    remaining_target = args.target_rows - len(selected)
    selected.extend(stratified_take(candidates, remaining_target, args.seed + 1, selected_ids))

    selected.sort(key=lambda row: (row["score_bin"], row["community_group_proxy"], row["uncertainty_distance"]))
    for idx, row in enumerate(selected, 1):
        row["validation_id"] = f"HV{idx:05d}"
        row["human_public_correction"] = ""
        row["human_confidence"] = ""
        row["human_notes"] = ""
    return selected


def summarize(rows: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "candidate_rows": len(candidates),
        "sample_rows": len(rows),
        "sample_by_score_bin": dict(sorted(Counter(row["score_bin"] for row in rows).items())),
        "sample_by_group": dict(sorted(Counter(row["community_group_proxy"] for row in rows).items())),
        "sample_by_model_pred": dict(sorted(Counter(str(row["public_correction_pred"]) for row in rows).items())),
        "sample_by_manual_presence": dict(sorted(Counter(str(row["in_manual_annotations"]) for row in rows).items())),
        "sample_by_manual_label": dict(sorted(Counter(str(row.get("manual_label", "")) for row in rows).items())),
        "sample_by_high_hostility": dict(
            sorted(Counter(str(row.get("high_thread_hostility_climate", "")) for row in rows).items())
        ),
        "sample_by_early_correction_norm": dict(
            sorted(Counter(str(row.get("early_correction_norm_presence", "")) for row in rows).items())
        ),
    }


def run(args: argparse.Namespace) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir = args.output_dir / "metrics"
    tables_dir = args.output_dir / "tables"
    metrics_dir.mkdir(exist_ok=True)
    tables_dir.mkdir(exist_ok=True)

    candidates = build_candidates(args)
    selected = prepare_sample(candidates, args)

    blind_fields = [
        "validation_id",
        "human_public_correction",
        "human_confidence",
        "human_notes",
        "comment_id",
        "submission_id",
        "parent_id",
        "subreddit",
        "community_group_proxy",
        "level",
        "submission_title",
        "parent_body",
        "body",
    ]
    metadata_extra_fields = [
        "author",
        "candidate_correction",
        "public_correction_score",
        "public_correction_pred",
        "score_bin",
        "uncertainty_distance",
        "created_utc",
        "in_manual_annotations",
        "manual_label",
        "manual_confidence",
        "manual_annotation_id",
        "manual_annotation_source",
        "comments",
        "unique_authors",
        "predicted_public_corrections",
        "has_predicted_public_correction",
        "later_predicted_public_corrections",
        "hostility_rate",
        "anti_institutional_rate",
        "early_correction_norm_presence",
        "sanction_to_correction_presence",
        "high_thread_hostility_climate",
        "high_thread_anti_institutional_climate",
        "high_early_hostility_climate",
        "high_early_anti_institutional_climate",
    ]

    write_csv(args.output_dir / "human_validation_sample_blind.csv", selected, blind_fields)
    write_csv(args.output_dir / "human_validation_sample_with_metadata.csv", selected, blind_fields + metadata_extra_fields)

    summary_rows = []
    for key, count in sorted(Counter((row["community_group_proxy"], row["score_bin"]) for row in selected).items()):
        summary_rows.append({"community_group_proxy": key[0], "score_bin": key[1], "rows": count})
    write_csv(tables_dir / "sample_by_group_and_score_bin.csv", summary_rows, ["community_group_proxy", "score_bin", "rows"])

    summary = {
        "run_status": "human_validation_sample_prepared",
        "predictions": str(args.predictions),
        "comments": str(args.comments),
        "thread_climate": str(args.thread_climate) if args.thread_climate else "",
        "manual_annotations": str(args.manual_annotations) if args.manual_annotations else "",
        "output_dir": str(args.output_dir),
        "target_rows": args.target_rows,
        "min_manual_rows": args.min_manual_rows,
        "seed": args.seed,
        "text_limit": args.text_limit,
        "summary": summarize(selected, candidates),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(metrics_dir / "run_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare blind human-validation sample.")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--comments", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--thread-climate", type=Path)
    parser.add_argument("--manual-annotations", type=Path)
    parser.add_argument("--target-rows", type=int, default=400)
    parser.add_argument("--min-manual-rows", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260625)
    parser.add_argument("--text-limit", type=int, default=5000)
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
