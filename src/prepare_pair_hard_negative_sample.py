#!/usr/bin/env python3
"""Select hard-negative-focused pair candidates for additional annotation."""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SUPPORT_TERMS = [
    "right",
    "exactly",
    "yes",
    "yeah",
    "yep",
    "agree",
    "true",
    "this",
    "also",
    "same",
    "correct",
]

REACTION_TERMS = [
    "lol",
    "lmao",
    "haha",
    "idiot",
    "stupid",
    "moron",
    "crazy",
    "bullshit",
    "bs",
    "clown",
    "sheep",
]

CORRECTION_CUE_TERMS = [
    "false",
    "wrong",
    "misinformation",
    "misinfo",
    "source",
    "evidence",
    "study",
    "data",
    "cdc",
    "fda",
    "who",
    "debunk",
    "fact check",
    "not true",
]


def compile_terms(terms: list[str]) -> list[re.Pattern[str]]:
    patterns = []
    for term in terms:
        escaped = re.escape(term.lower())
        if " " in term:
            patterns.append(re.compile(escaped))
        else:
            patterns.append(re.compile(rf"\b{escaped}\b"))
    return patterns


SUPPORT_PATTERNS = compile_terms(SUPPORT_TERMS)
REACTION_PATTERNS = compile_terms(REACTION_TERMS)
CORRECTION_CUE_PATTERNS = compile_terms(CORRECTION_CUE_TERMS)


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


def to_float(value: Any) -> float:
    try:
        out = float(str(value))
    except (TypeError, ValueError):
        return 0.0
    if out != out:
        return 0.0
    return out


def has_match(text: str, patterns: list[re.Pattern[str]]) -> int:
    lowered = str(text or "").lower()
    return int(any(pattern.search(lowered) for pattern in patterns))


def parse_quotas(value: str) -> dict[str, int]:
    quotas: dict[str, int] = {}
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        key, raw_val = part.split("=", 1)
        quotas[key.strip()] = int(raw_val)
    return quotas


def enrich(row: dict[str, Any]) -> dict[str, Any]:
    body = str(row.get("response_body", ""))
    row = dict(row)
    row["_score"] = to_float(row.get("current_pair_relation_score"))
    row["_support_like"] = has_match(body, SUPPORT_PATTERNS)
    row["_reaction_like"] = has_match(body, REACTION_PATTERNS)
    row["_correction_cue_like"] = has_match(body, CORRECTION_CUE_PATTERNS)
    row["_short_response"] = int(len(body.strip()) <= 120)
    return row


def pool_for_component(rows: list[dict[str, Any]], component: str, high_score_cutoff: float, low_score_cutoff: float) -> list[dict[str, Any]]:
    if component == "support_like_high_score":
        return [r for r in rows if r["_score"] >= high_score_cutoff and r["_support_like"]]
    if component == "reaction_like_high_score":
        return [r for r in rows if r["_score"] >= high_score_cutoff and r["_reaction_like"]]
    if component == "correction_cue_high_score":
        return [r for r in rows if r["_score"] >= high_score_cutoff and r["_correction_cue_like"]]
    if component == "parent_random_high_score":
        return [r for r in rows if r.get("sample_component") == "parent_pair_random_calibration" and r["_score"] >= high_score_cutoff]
    if component == "parent_claim_cue_high_score":
        return [r for r in rows if r.get("sample_component") == "parent_claim_cue_or_short" and r["_score"] >= high_score_cutoff]
    if component == "low_score_correction_cue":
        return [r for r in rows if r["_score"] <= low_score_cutoff and r["_correction_cue_like"]]
    if component == "near_threshold_uncertain":
        return [r for r in rows if abs(r["_score"] - high_score_cutoff) <= 0.10]
    if component == "random_calibration":
        return rows
    raise ValueError(f"Unsupported component: {component}")


def summarize_by(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    counts = Counter(str(row.get(field, "")) for row in rows)
    return [{field: key, "rows": value} for key, value in sorted(counts.items())]


def run(args: argparse.Namespace) -> None:
    rng = random.Random(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir = args.output_dir / "metrics"
    tables_dir = args.output_dir / "tables"
    metrics_dir.mkdir(exist_ok=True)
    tables_dir.mkdir(exist_ok=True)

    rows = [enrich(row) for row in read_csv(args.input)]
    quotas = parse_quotas(args.quotas)
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()

    def add(row: dict[str, Any], component: str) -> bool:
        pair_id = str(row.get("pair_id", ""))
        if pair_id in selected_ids:
            return False
        out = dict(row)
        out["hard_sample_component"] = component
        selected.append(out)
        selected_ids.add(pair_id)
        return True

    for component, quota in quotas.items():
        pool = pool_for_component(rows, component, args.high_score_cutoff, args.low_score_cutoff)
        if component == "random_calibration":
            rng.shuffle(pool)
        elif component == "low_score_correction_cue":
            pool.sort(key=lambda r: (r["_score"], rng.random()))
        elif component == "near_threshold_uncertain":
            pool.sort(key=lambda r: (abs(r["_score"] - args.high_score_cutoff), rng.random()))
        else:
            pool.sort(key=lambda r: (-r["_score"], rng.random()))
        count = 0
        for row in pool:
            if count >= quota:
                break
            if add(row, component):
                count += 1

    remaining = [row for row in rows if str(row.get("pair_id", "")) not in selected_ids]
    remaining.sort(key=lambda r: (-r["_score"], rng.random()))
    for row in remaining:
        if len(selected) >= args.target:
            break
        add(row, "fallback_high_score")

    selected = selected[: args.target]
    for idx, row in enumerate(selected, 1):
        row["annotation_id"] = f"HNP{idx:05d}"
        for key in ["is_correction_relation", "relation_type", "target_specificity", "annotation_confidence", "annotation_notes"]:
            row[key] = ""

    drop_fields = {"_score", "_support_like", "_reaction_like", "_correction_cue_like", "_short_response"}
    base_fields = [field for field in read_csv(args.input)[0].keys() if field not in drop_fields]
    fieldnames = ["annotation_id", "hard_sample_component"] + [field for field in base_fields if field != "annotation_id"] + [
        "is_correction_relation",
        "relation_type",
        "target_specificity",
        "annotation_confidence",
        "annotation_notes",
    ]
    write_csv(args.output_dir / "annotation_pairs.csv", selected, fieldnames)
    write_csv(tables_dir / "hard_sample_component_counts.csv", summarize_by(selected, "hard_sample_component"), ["hard_sample_component", "rows"])
    write_csv(tables_dir / "original_sample_component_counts.csv", summarize_by(selected, "sample_component"), ["sample_component", "rows"])
    write_csv(tables_dir / "pair_source_counts.csv", summarize_by(selected, "pair_source"), ["pair_source", "rows"])

    summary = {
        "run_status": "hard_negative_pair_annotation_sample",
        "input": str(args.input),
        "output_dir": str(args.output_dir),
        "candidate_rows": len(rows),
        "selected_rows": len(selected),
        "target": args.target,
        "quotas": quotas,
        "high_score_cutoff": args.high_score_cutoff,
        "low_score_cutoff": args.low_score_cutoff,
        "seed": args.seed,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(metrics_dir / "run_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Select hard-negative-focused pair candidates.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--target", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--high-score-cutoff", type=float, default=0.50)
    parser.add_argument("--low-score-cutoff", type=float, default=0.25)
    parser.add_argument(
        "--quotas",
        default=(
            "support_like_high_score=180,"
            "reaction_like_high_score=120,"
            "correction_cue_high_score=220,"
            "parent_random_high_score=180,"
            "parent_claim_cue_high_score=140,"
            "low_score_correction_cue=80,"
            "random_calibration=80"
        ),
    )
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
