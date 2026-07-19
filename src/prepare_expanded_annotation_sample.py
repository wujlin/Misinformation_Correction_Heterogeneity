#!/usr/bin/env python3
"""Prepare a larger stratified sample for human correction annotation."""

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


def load_existing_comment_ids(paths: list[Path]) -> set[str]:
    ids = set()
    for path in paths:
        if not path.exists():
            continue
        for row in read_csv(path):
            comment_id = normalize_token(row.get("comment_id"))
            if comment_id:
                ids.add(comment_id)
    return ids


def load_comment_lookup(path: Path, body_limit: int) -> dict[str, dict[str, Any]]:
    lookup = {}
    for row in iter_jsonl(path):
        comment_id = normalize_token(row.get("comment_id"))
        if not comment_id:
            continue
        lookup[comment_id] = {
            "submission_title": compact_text(row.get("submission_title"), body_limit),
            "body": compact_text(row.get("body"), body_limit),
            "level": row.get("level", ""),
            "parent_id": row.get("parent_id", ""),
        }
    return lookup


def build_candidates(args: argparse.Namespace) -> list[dict[str, Any]]:
    existing_ids = load_existing_comment_ids(args.existing_annotations)
    comments = load_comment_lookup(args.comments, args.text_limit)
    candidates = []
    for row in read_csv(args.predictions):
        comment_id = normalize_token(row.get("comment_id"))
        if not comment_id or comment_id in existing_ids or comment_id not in comments:
            continue
        score = to_float(row.get("public_correction_score"))
        group = normalize_token(row.get("community_group_proxy")) or "unknown"
        subreddit = normalize_token(row.get("subreddit"))
        item = {
            "comment_id": comment_id,
            "submission_id": normalize_token(row.get("submission_id")),
            "parent_id": normalize_token(row.get("parent_id") or comments[comment_id].get("parent_id")),
            "subreddit": subreddit,
            "community_group_proxy": group,
            "author": row.get("author", ""),
            "candidate_correction": to_int(row.get("candidate_correction")),
            "model_score": score,
            "model_pred": to_int(row.get("public_correction_pred")),
            "score_bin": score_bin(score),
            "uncertainty_distance": abs(score - 0.5),
            "created_utc": row.get("created_utc", ""),
            "level": comments[comment_id].get("level", ""),
            "submission_title": comments[comment_id]["submission_title"],
            "body": comments[comment_id]["body"],
        }
        candidates.append(item)
    return candidates


def stratified_sample(candidates: list[dict[str, Any]], target_rows: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        grouped[(row["community_group_proxy"], row["score_bin"])].append(row)

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    keys = sorted(grouped)
    per_stratum = max(1, math.ceil(target_rows * 0.70 / max(len(keys), 1)))

    for key in keys:
        rows = grouped[key]
        rng.shuffle(rows)
        for row in rows[:per_stratum]:
            selected.append(row)
            selected_ids.add(row["comment_id"])

    if len(selected) < target_rows:
        remaining = [row for row in candidates if row["comment_id"] not in selected_ids]
        # Prefer uncertain rows first, then add diversity through random tie-breaking.
        for row in remaining:
            row["_tie"] = rng.random()
        remaining.sort(key=lambda row: (row["uncertainty_distance"], row["_tie"]))
        for row in remaining:
            if len(selected) >= target_rows:
                break
            selected.append(row)
            selected_ids.add(row["comment_id"])

    if len(selected) > target_rows:
        # Keep the uncertain rows if the stratified stage overshoots.
        selected.sort(key=lambda row: (row["uncertainty_distance"], row["community_group_proxy"], row["score_bin"]))
        selected = selected[:target_rows]

    selected.sort(key=lambda row: (row["community_group_proxy"], row["score_bin"], row["uncertainty_distance"]))
    for idx, row in enumerate(selected, 1):
        row["annotation_id"] = f"EXP{idx:05d}"
        row["gold_label"] = ""
        row["is_public_correction"] = ""
    return selected


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_group = Counter(row["community_group_proxy"] for row in rows)
    by_bin = Counter(row["score_bin"] for row in rows)
    by_group_bin = Counter(f"{row['community_group_proxy']}|{row['score_bin']}" for row in rows)
    return {
        "rows": len(rows),
        "by_community_group": dict(sorted(by_group.items())),
        "by_score_bin": dict(sorted(by_bin.items())),
        "by_community_group_and_score_bin": dict(sorted(by_group_bin.items())),
        "model_pred_counts": dict(Counter(str(row["model_pred"]) for row in rows)),
        "candidate_correction_counts": dict(Counter(str(row["candidate_correction"]) for row in rows)),
    }


def run(args: argparse.Namespace) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir = args.output_dir / "metrics"
    metrics_dir.mkdir(exist_ok=True)
    candidates = build_candidates(args)
    selected = stratified_sample(candidates, args.target_rows, args.seed)

    fieldnames = [
        "annotation_id",
        "gold_label",
        "is_public_correction",
        "candidate_correction",
        "community_group_proxy",
        "subreddit",
        "comment_id",
        "submission_id",
        "parent_id",
        "level",
        "model_score",
        "model_pred",
        "score_bin",
        "created_utc",
        "submission_title",
        "body",
    ]
    write_csv(args.output_dir / "annotation_sample.csv", selected, fieldnames)

    summary = {
        "run_status": "expanded_annotation_sample",
        "predictions": str(args.predictions),
        "comments": str(args.comments),
        "existing_annotations": [str(path) for path in args.existing_annotations],
        "output_dir": str(args.output_dir),
        "candidate_rows": len(candidates),
        "target_rows": args.target_rows,
        "seed": args.seed,
        "text_limit": args.text_limit,
        "sample_summary": summarize(selected),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(metrics_dir / "run_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare expanded human annotation sample.")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--comments", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--existing-annotations", type=Path, nargs="*", default=[])
    parser.add_argument("--target-rows", type=int, default=2400)
    parser.add_argument("--seed", type=int, default=20260625)
    parser.add_argument("--text-limit", type=int, default=5000)
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
