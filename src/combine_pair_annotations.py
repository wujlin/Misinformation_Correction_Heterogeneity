#!/usr/bin/env python3
"""Combine pair-level human annotation CSV files."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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


def summarize(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    counts = Counter(str(row.get(field, "")) for row in rows)
    return [{field: key, "rows": value} for key, value in sorted(counts.items())]


def run(args: argparse.Namespace) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir = args.output_dir / "metrics"
    tables_dir = args.output_dir / "tables"
    metrics_dir.mkdir(exist_ok=True)
    tables_dir.mkdir(exist_ok=True)

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    fieldnames: list[str] = []
    input_counts: dict[str, int] = {}
    duplicate_rows = 0

    for path in args.inputs:
        part_rows = read_csv(path)
        input_counts[str(path)] = len(part_rows)
        if part_rows and not fieldnames:
            fieldnames = list(part_rows[0].keys())
        for row in part_rows:
            pair_id = str(row.get("pair_id", "")).strip()
            key = pair_id or str(row.get("annotation_id", "")).strip()
            if key and key in seen:
                duplicate_rows += 1
                continue
            if key:
                seen.add(key)
            rows.append(row)

    if not fieldnames and rows:
        fieldnames = list(rows[0].keys())

    write_csv(args.output_dir / "manual_pair_annotations.csv", rows, fieldnames)
    write_csv(tables_dir / "label_counts.csv", summarize(rows, "manual_pair_label"), ["manual_pair_label", "rows"])
    write_csv(
        tables_dir / "raw_label_counts.csv",
        summarize(rows, "manual_pair_label_initial"),
        ["manual_pair_label_initial", "rows"],
    )
    write_csv(
        tables_dir / "relation_type_counts.csv",
        summarize(rows, "manual_pair_relation_type"),
        ["manual_pair_relation_type", "rows"],
    )
    write_csv(
        tables_dir / "target_specificity_counts.csv",
        summarize(rows, "manual_pair_target_specificity"),
        ["manual_pair_target_specificity", "rows"],
    )
    write_csv(tables_dir / "pair_source_counts.csv", summarize(rows, "pair_source"), ["pair_source", "rows"])
    write_csv(tables_dir / "sample_component_counts.csv", summarize(rows, "sample_component"), ["sample_component", "rows"])
    conflict_rows = [
        row
        for row in rows
        if str(row.get("manual_pair_label", "")).strip() != str(row.get("manual_pair_label_initial", "")).strip()
    ]
    if conflict_rows:
        conflict_fields = [
            "annotation_id",
            "pair_id",
            "sample_component",
            "pair_source",
            "manual_pair_label_initial",
            "manual_pair_label",
            "manual_pair_relation_type",
            "manual_pair_target_specificity",
            "manual_pair_confidence",
            "claim_text",
            "response_body",
            "manual_pair_notes",
        ]
        write_csv(tables_dir / "raw_final_label_conflicts.csv", conflict_rows, conflict_fields)

    summary = {
        "run_status": "combined_pair_relation_annotations",
        "inputs": [str(path) for path in args.inputs],
        "input_counts": input_counts,
        "rows": len(rows),
        "duplicate_rows_skipped": duplicate_rows,
        "raw_final_label_conflicts": len(conflict_rows),
        "output_dir": str(args.output_dir),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(metrics_dir / "run_summary.json", summary)
    (args.output_dir / "run.log").write_text(
        "\n".join(
            [
                "combined pair relation annotations",
                f"generated_utc={summary['generated_utc']}",
                f"rows={len(rows)}",
                f"duplicate_rows_skipped={duplicate_rows}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Combine pair-level human annotation CSVs.")
    parser.add_argument("--inputs", type=Path, nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
