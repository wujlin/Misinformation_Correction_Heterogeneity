#!/usr/bin/env python3
"""Combine multiple LLM-assisted annotation CSV files into one training set."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_FIELDS = [
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
    "llm_label",
    "llm_confidence",
    "llm_correction_target",
    "llm_rationale",
    "annotation_source",
]


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


def normalize_label(value: Any) -> str:
    label = str(value or "").strip().upper()
    if label in {"0", "1", "U"}:
        return label
    return ""


def row_key(row: dict[str, Any]) -> str:
    return str(row.get("comment_id") or row.get("annotation_id") or "").strip()


def run(args: argparse.Namespace) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir = args.output_dir / "metrics"
    metrics_dir.mkdir(exist_ok=True)

    combined_by_key: dict[str, dict[str, Any]] = {}
    source_counts: Counter[str] = Counter()
    duplicate_keys: list[str] = []

    for path in args.inputs:
        source = path.parent.name
        rows = read_csv(path)
        for row in rows:
            key = row_key(row)
            label = normalize_label(row.get("llm_label"))
            if not key or label not in {"0", "1", "U"}:
                continue
            clean = {field: row.get(field, "") for field in DEFAULT_FIELDS}
            clean["llm_label"] = label
            clean["annotation_source"] = source
            if key in combined_by_key:
                duplicate_keys.append(key)
                if args.keep == "first":
                    continue
            combined_by_key[key] = clean
            source_counts[source] += 1

    rows = list(combined_by_key.values())
    rows.sort(key=lambda row: (row["annotation_source"], row["annotation_id"], row["comment_id"]))
    for idx, row in enumerate(rows, 1):
        row["combined_annotation_id"] = f"COMB{idx:05d}"

    fieldnames = ["combined_annotation_id"] + DEFAULT_FIELDS
    write_csv(args.output_dir / "llm_annotations.csv", rows, fieldnames)

    label_counts = Counter(row["llm_label"] for row in rows)
    summary = {
        "run_status": "combined_llm_annotations",
        "inputs": [str(path) for path in args.inputs],
        "output_dir": str(args.output_dir),
        "rows": len(rows),
        "label_counts": dict(label_counts),
        "source_counts": dict(source_counts),
        "duplicate_keys": len(duplicate_keys),
        "keep": args.keep,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(metrics_dir / "run_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Combine LLM-assisted annotation CSV files.")
    parser.add_argument("--inputs", type=Path, nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--keep", choices=["first", "last"], default="last")
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
