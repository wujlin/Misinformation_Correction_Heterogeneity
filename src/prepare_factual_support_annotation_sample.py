#!/usr/bin/env python3
"""Select factual/support boundary pairs for relation annotation."""

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


FACTUAL_TERMS = [
    "cdc",
    "fda",
    "who",
    "vaers",
    "pfizer",
    "moderna",
    "johnson",
    "study",
    "studies",
    "trial",
    "data",
    "evidence",
    "source",
    "article",
    "report",
    "research",
    "paper",
    "peer reviewed",
    "statistics",
    "rate",
    "risk",
    "case",
    "cases",
    "death",
    "deaths",
    "hospitalization",
    "myocarditis",
    "infection",
    "vaccine",
    "vaccinated",
    "unvaccinated",
    "covid",
    "http",
    "www",
]

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
    "that's true",
    "you are right",
]

CORRECTION_CUE_TERMS = [
    "false",
    "wrong",
    "misinformation",
    "misinfo",
    "not true",
    "debunk",
    "fact check",
    "incorrect",
    "source?",
]


def compile_terms(terms: list[str]) -> list[re.Pattern[str]]:
    patterns = []
    for term in terms:
        escaped = re.escape(term.lower())
        if " " in term or "?" in term:
            patterns.append(re.compile(escaped))
        else:
            patterns.append(re.compile(rf"\b{escaped}\b"))
    return patterns


FACTUAL_PATTERNS = compile_terms(FACTUAL_TERMS)
SUPPORT_PATTERNS = compile_terms(SUPPORT_TERMS)
CORRECTION_CUE_PATTERNS = compile_terms(CORRECTION_CUE_TERMS)
NUMERIC_PATTERN = re.compile(r"(\b\d+(\.\d+)?\s*%|\b\d{2,}\b)")


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


def has_match(text: str, patterns: list[re.Pattern[str]]) -> int:
    lowered = str(text or "").lower()
    return int(any(pattern.search(lowered) for pattern in patterns))


def to_float(value: Any) -> float:
    try:
        out = float(str(value))
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if out != out else out


def parse_quotas(value: str) -> dict[str, int]:
    quotas: dict[str, int] = {}
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        key, raw_val = part.split("=", 1)
        quotas[key.strip()] = int(raw_val)
    return quotas


def enrich(row: dict[str, Any], score_fields: list[str]) -> dict[str, Any]:
    body = str(row.get("response_body", ""))
    row = dict(row)
    scores = [to_float(row.get(field)) for field in score_fields]
    row["_ensemble_score"] = sum(scores) / len(scores) if scores else 0.0
    row["_factual_like"] = has_match(body, FACTUAL_PATTERNS)
    row["_support_like"] = has_match(body, SUPPORT_PATTERNS)
    row["_correction_cue_like"] = has_match(body, CORRECTION_CUE_PATTERNS)
    row["_numeric_like"] = int(bool(NUMERIC_PATTERN.search(body)))
    row["_long_enough"] = int(len(body.strip()) >= 80)
    row["_factual_support_score"] = (
        row["_factual_like"]
        + row["_support_like"]
        + row["_numeric_like"]
        + row["_long_enough"]
    )
    row["selection_ensemble_score"] = row["_ensemble_score"]
    row["selection_factual_like"] = row["_factual_like"]
    row["selection_support_like"] = row["_support_like"]
    row["selection_correction_cue_like"] = row["_correction_cue_like"]
    row["selection_numeric_like"] = row["_numeric_like"]
    row["selection_factual_support_score"] = row["_factual_support_score"]
    return row


def pool_for_component(rows: list[dict[str, Any]], component: str, high: float, low: float) -> list[dict[str, Any]]:
    if component == "factual_high_score":
        return [r for r in rows if r["_ensemble_score"] >= high and r["_factual_like"]]
    if component == "factual_support_high_score":
        return [r for r in rows if r["_ensemble_score"] >= high and r["_factual_like"] and r["_support_like"]]
    if component == "factual_numeric_high_score":
        return [r for r in rows if r["_ensemble_score"] >= high and r["_factual_like"] and r["_numeric_like"]]
    if component == "correction_cue_factual_high_score":
        return [r for r in rows if r["_ensemble_score"] >= high and r["_factual_like"] and r["_correction_cue_like"]]
    if component == "type_support_high_score":
        return [
            r
            for r in rows
            if r["_ensemble_score"] >= high
            and str(r.get("type_pred_relation_type", "")) == "misinformation_support_or_elaboration"
        ]
    if component == "low_score_factual_calibration":
        return [r for r in rows if r["_ensemble_score"] <= low and r["_factual_like"]]
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

    raw_rows = read_csv(args.input)
    score_fields = [field.strip() for field in args.score_fields.split(",") if field.strip()]
    rows = [enrich(row, score_fields) for row in raw_rows]
    quotas = parse_quotas(args.quotas)
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()

    def add(row: dict[str, Any], component: str) -> bool:
        pair_id = str(row.get("pair_id", ""))
        if pair_id in selected_ids:
            return False
        out = dict(row)
        out["factual_sample_component"] = component
        selected.append(out)
        selected_ids.add(pair_id)
        return True

    for component, quota in quotas.items():
        pool = pool_for_component(rows, component, args.high_score_cutoff, args.low_score_cutoff)
        if component in {"low_score_factual_calibration", "random_calibration"}:
            rng.shuffle(pool)
        else:
            pool.sort(key=lambda r: (-r["_factual_support_score"], -r["_ensemble_score"], rng.random()))
        count = 0
        for row in pool:
            if count >= quota:
                break
            if add(row, component):
                count += 1

    remaining = [row for row in rows if str(row.get("pair_id", "")) not in selected_ids]
    remaining.sort(key=lambda r: (-r["_factual_support_score"], -r["_ensemble_score"], rng.random()))
    for row in remaining:
        if len(selected) >= args.target:
            break
        add(row, "fallback_factual_high_score")

    selected = selected[: args.target]
    for idx, row in enumerate(selected, 1):
        row["annotation_id"] = f"FSP{idx:05d}"
        for key in ["is_correction_relation", "relation_type", "target_specificity", "annotation_confidence", "annotation_notes"]:
            row[key] = ""

    drop_fields = {
        "_ensemble_score",
        "_factual_like",
        "_support_like",
        "_correction_cue_like",
        "_numeric_like",
        "_long_enough",
        "_factual_support_score",
    }
    input_fields = [field for field in raw_rows[0].keys() if field not in drop_fields and field != "annotation_id"]
    extra_fields = [
        "annotation_id",
        "factual_sample_component",
        "selection_ensemble_score",
        "selection_factual_like",
        "selection_support_like",
        "selection_correction_cue_like",
        "selection_numeric_like",
        "selection_factual_support_score",
    ]
    annotation_fields = [
        "is_correction_relation",
        "relation_type",
        "target_specificity",
        "annotation_confidence",
        "annotation_notes",
    ]
    fieldnames = extra_fields + input_fields + annotation_fields
    write_csv(args.output_dir / "annotation_pairs.csv", selected, fieldnames)
    write_csv(tables_dir / "factual_sample_component_counts.csv", summarize_by(selected, "factual_sample_component"), ["factual_sample_component", "rows"])
    write_csv(tables_dir / "type_pred_relation_type_counts.csv", summarize_by(selected, "type_pred_relation_type"), ["type_pred_relation_type", "rows"])
    write_csv(tables_dir / "pair_source_counts.csv", summarize_by(selected, "pair_source"), ["pair_source", "rows"])

    summary = {
        "run_status": "factual_support_pair_annotation_sample",
        "input": str(args.input),
        "output_dir": str(args.output_dir),
        "candidate_rows": len(rows),
        "selected_rows": len(selected),
        "target": args.target,
        "score_fields": score_fields,
        "quotas": quotas,
        "high_score_cutoff": args.high_score_cutoff,
        "low_score_cutoff": args.low_score_cutoff,
        "seed": args.seed,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(metrics_dir / "run_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Select factual/support boundary candidates.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--target", type=int, default=700)
    parser.add_argument("--seed", type=int, default=20260701)
    parser.add_argument("--high-score-cutoff", type=float, default=0.45)
    parser.add_argument("--low-score-cutoff", type=float, default=0.25)
    parser.add_argument(
        "--score-fields",
        default="score_binary3000,score_binary_large,score_typebase,score_nli_deberta",
    )
    parser.add_argument(
        "--quotas",
        default=(
            "factual_high_score=180,"
            "factual_support_high_score=170,"
            "factual_numeric_high_score=110,"
            "correction_cue_factual_high_score=90,"
            "type_support_high_score=60,"
            "low_score_factual_calibration=40,"
            "random_calibration=50"
        ),
    )
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
