#!/usr/bin/env python3
"""Prepare an active-learning sample for relation-aware correction annotation.

The sample targets detector boundary cases rather than drawing another broad
random sample. It is designed to improve errors observed in public-correction
detection: context-dependent replies, quote edits, short sarcastic corrections,
high-score factual statements that may not be corrections, and disagreements
between a text-only detector and a context-aware detector.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


CORRECTION_TERMS = [
    "actually",
    "not true",
    "false",
    "wrong",
    "misleading",
    "debunk",
    "fact check",
    "fact-check",
    "source",
    "evidence",
    "study",
    "data",
    "according to",
    "cdc",
    "who",
    "fda",
    "peer reviewed",
    "peer-reviewed",
    "that is not",
    "that's not",
    "this is not",
]

MISINFORMATION_CONTEXT_TERMS = [
    "big pharma",
    "fauci",
    "cdc",
    "plandemic",
    "scamdemic",
    "experimental vaccine",
    "gene therapy",
    "fake pandemic",
    "natural immunity",
    "vaers",
    "ivermectin",
    "hydroxychloroquine",
    "microchip",
    "5g",
    "depopulation",
    "nuremberg",
    "my body my choice",
    "mandate",
    "tyranny",
]

SARCASM_TERMS = [
    "/s",
    "yeah right",
    "sure buddy",
    "good thing",
    "lol",
    "lmao",
    "ftfy",
]


def compile_terms(terms: list[str]) -> list[re.Pattern[str]]:
    patterns = []
    for term in terms:
        escaped = re.escape(term.lower())
        if " " in term or any(ch in term for ch in ["/", "-"]):
            patterns.append(re.compile(escaped))
        else:
            patterns.append(re.compile(rf"\b{escaped}\b"))
    return patterns


CORRECTION_PATTERNS = compile_terms(CORRECTION_TERMS)
MISINFORMATION_CONTEXT_PATTERNS = compile_terms(MISINFORMATION_CONTEXT_TERMS)
SARCASM_PATTERNS = compile_terms(SARCASM_TERMS)


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


def normalize_author(value: Any) -> str:
    return str(value or "").strip()


def compact_text(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit] if len(text) > limit else text


def to_float(value: Any) -> float:
    try:
        out = float(str(value))
    except (TypeError, ValueError):
        return 0.0
    if out != out:
        return 0.0
    return out


def to_int(value: Any) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0


def has_match(text: str, patterns: list[re.Pattern[str]]) -> int:
    lowered = text.lower()
    return int(any(pattern.search(lowered) for pattern in patterns))


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


def load_predictions(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in read_csv(path):
        comment_id = normalize_token(row.get("comment_id"))
        if not comment_id:
            continue
        rows[comment_id] = {
            "comment_id": comment_id,
            "submission_id": normalize_token(row.get("submission_id")),
            "parent_id": normalize_token(row.get("parent_id")),
            "subreddit": normalize_token(row.get("subreddit")),
            "community_group_proxy": normalize_token(row.get("community_group_proxy")),
            "author": normalize_author(row.get("author")),
            "candidate_correction": to_int(row.get("candidate_correction")),
            "score": to_float(row.get("public_correction_score")),
            "pred": to_int(row.get("public_correction_pred")),
            "created_utc": to_float(row.get("created_utc")),
        }
    return rows


def load_thread_climate(path: Path) -> dict[str, dict[str, Any]]:
    keep = [
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
        "high_early_hostility_climate",
        "high_early_anti_institutional_climate",
        "sanction_to_correction_presence",
    ]
    out: dict[str, dict[str, Any]] = {}
    for row in read_csv(path):
        submission_id = normalize_token(row.get("submission_id"))
        if submission_id:
            out[submission_id] = {field: row.get(field, "") for field in keep}
    return out


def load_comments(path: Path, text_limit: int) -> dict[str, dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in iter_jsonl(path):
        comment_id = normalize_token(raw.get("comment_id"))
        if not comment_id:
            continue
        rows.append(
            {
                "comment_id": comment_id,
                "submission_id": normalize_token(raw.get("submission_id")),
                "parent_id": normalize_token(raw.get("parent_id")),
                "author": normalize_author(raw.get("author")),
                "subreddit": normalize_token(raw.get("subreddit")),
                "created_utc": to_float(raw.get("created_utc")),
                "level": to_int(raw.get("level")),
                "submission_title": compact_text(raw.get("submission_title"), text_limit),
                "body": compact_text(raw.get("body"), text_limit),
            }
        )

    by_id = {row["comment_id"]: row for row in rows}
    by_submission: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_submission[row["submission_id"]].append(row)
    for items in by_submission.values():
        items.sort(key=lambda item: (item["created_utc"], item["comment_id"]))
        prior_context = ""
        for rank, item in enumerate(items, 1):
            item["thread_comment_rank"] = rank
            parent = by_id.get(item["parent_id"])
            item["parent_body"] = compact_text(parent["body"], text_limit) if parent else ""
            if prior_context:
                item["nearest_prior_claim_body"] = prior_context
            else:
                item["nearest_prior_claim_body"] = ""
            if has_match(item["body"], MISINFORMATION_CONTEXT_PATTERNS):
                prior_context = item["body"]
    return by_id


def build_candidates(args: argparse.Namespace) -> list[dict[str, Any]]:
    primary = load_predictions(args.primary_predictions)
    secondary = load_predictions(args.secondary_predictions) if args.secondary_predictions else {}
    comments = load_comments(args.comments, args.text_limit)
    threads = load_thread_climate(args.thread_climate)
    existing_ids = load_existing_ids(args.exclude_annotations)

    candidates: list[dict[str, Any]] = []
    for comment_id, pred in primary.items():
        if comment_id in existing_ids:
            continue
        comment = comments.get(comment_id)
        if not comment:
            continue
        submission_id = pred.get("submission_id") or comment["submission_id"]
        thread = threads.get(submission_id, {})
        body = comment["body"]
        parent_body = comment.get("parent_body", "")
        sec = secondary.get(comment_id)
        secondary_score = to_float(sec.get("score")) if sec else ""
        secondary_pred = to_int(sec.get("pred")) if sec else ""
        score_diff = abs(pred["score"] - float(secondary_score)) if sec else ""
        body_len = len(body)
        has_parent = int(bool(parent_body))
        has_quote = int(body.strip().startswith(">") or "\n>" in body)
        has_quote_edit = int("~~" in body or "ftfy" in body.lower())
        has_sarcasm = has_match(body, SARCASM_PATTERNS)
        has_correction_cue = has_match(body, CORRECTION_PATTERNS)
        parent_has_misinfo_cue = has_match(parent_body, MISINFORMATION_CONTEXT_PATTERNS)
        short_contextual = int(has_parent and body_len <= args.short_text_length)
        near_threshold = int(abs(pred["score"] - args.primary_threshold) <= args.near_threshold_width)
        reasons = []
        if sec and (pred["pred"] != secondary_pred or float(score_diff) >= args.disagreement_width):
            reasons.append("model_disagreement")
        if pred["score"] >= args.high_score_cutoff and not has_correction_cue:
            reasons.append("possible_false_positive_high_score_without_cue")
        if pred["score"] <= args.low_score_cutoff and (has_correction_cue or has_quote_edit or short_contextual):
            reasons.append("possible_false_negative_contextual")
        if has_quote_edit or has_quote or has_sarcasm:
            reasons.append("quote_edit_or_sarcasm")
        if short_contextual:
            reasons.append("short_context_dependent")
        if near_threshold:
            reasons.append("near_primary_threshold")
        if has_parent and parent_has_misinfo_cue and pred["score"] <= args.parent_misinfo_low_score_cutoff:
            reasons.append("parent_misinfo_low_score")

        candidates.append(
            {
                "comment_id": comment_id,
                "submission_id": submission_id,
                "parent_id": pred.get("parent_id") or comment.get("parent_id"),
                "subreddit": pred.get("subreddit") or comment.get("subreddit"),
                "community_group_proxy": pred.get("community_group_proxy", ""),
                "author": pred.get("author") or comment.get("author"),
                "candidate_correction": pred.get("candidate_correction", 0),
                "primary_score": pred["score"],
                "primary_pred": pred["pred"],
                "secondary_score": secondary_score,
                "secondary_pred": secondary_pred,
                "score_diff": score_diff,
                "created_utc": pred.get("created_utc") or comment.get("created_utc"),
                "level": comment.get("level", 0),
                "thread_comment_rank": comment.get("thread_comment_rank", 0),
                "has_parent_body": has_parent,
                "body_length": body_len,
                "has_correction_cue": has_correction_cue,
                "has_quote": has_quote,
                "has_quote_edit": has_quote_edit,
                "has_sarcasm": has_sarcasm,
                "parent_has_misinfo_cue": parent_has_misinfo_cue,
                "active_reasons": "|".join(reasons),
                "primary_active_reason": reasons[0] if reasons else "random_calibration",
                "submission_title": comment.get("submission_title", ""),
                "parent_body": parent_body,
                "nearest_prior_claim_body": comment.get("nearest_prior_claim_body", ""),
                "body": body,
                **thread,
            }
        )
    return candidates


def row_priority(row: dict[str, Any], reason: str, rng: random.Random) -> tuple[float, float]:
    score = to_float(row.get("primary_score"))
    diff = to_float(row.get("score_diff"))
    if reason == "model_disagreement":
        return (-diff, rng.random())
    if reason == "possible_false_positive_high_score_without_cue":
        return (-score, rng.random())
    if reason == "possible_false_negative_contextual":
        return (score, rng.random())
    if reason == "quote_edit_or_sarcasm":
        return (score, rng.random())
    if reason == "short_context_dependent":
        return (float(row.get("body_length", 9999)), rng.random())
    if reason == "near_primary_threshold":
        return (abs(score - to_float(row.get("_primary_threshold"))), rng.random())
    if reason == "parent_misinfo_low_score":
        return (score, rng.random())
    return (rng.random(), rng.random())


def select_rows(
    candidates: list[dict[str, Any]],
    target: int,
    quotas: dict[str, int],
    seed: int,
    max_per_submission: int,
    primary_threshold: float,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    submission_counts: Counter[str] = Counter()

    def add(row: dict[str, Any], reason: str) -> bool:
        comment_id = str(row["comment_id"])
        submission_id = str(row["submission_id"])
        if comment_id in selected_ids:
            return False
        if submission_counts[submission_id] >= max_per_submission:
            return False
        out = dict(row)
        out["sample_component"] = reason
        selected.append(out)
        selected_ids.add(comment_id)
        submission_counts[submission_id] += 1
        return True

    for row in candidates:
        row["_primary_threshold"] = primary_threshold

    for reason, quota in quotas.items():
        if quota <= 0:
            continue
        pool = [row for row in candidates if reason in str(row.get("active_reasons", "")).split("|")]
        pool.sort(key=lambda row: row_priority(row, reason, rng))
        count = 0
        for row in pool:
            if count >= quota:
                break
            if add(row, reason):
                count += 1

    remaining = [row for row in candidates if row["comment_id"] not in selected_ids]
    rng.shuffle(remaining)
    for row in remaining:
        if len(selected) >= target:
            break
        add(row, "random_calibration")

    return selected[:target]


def add_annotation_fields(rows: list[dict[str, Any]]) -> None:
    for idx, row in enumerate(rows, 1):
        row["annotation_id"] = f"ARS{idx:05d}"
        row["relation_correction_type"] = ""
        row["is_public_correction"] = ""
        row["target_specificity"] = ""
        row["annotation_confidence"] = ""
        row["annotation_notes"] = ""


def parse_quotas(value: str) -> dict[str, int]:
    quotas: dict[str, int] = {}
    if not value.strip():
        return quotas
    for part in value.split(","):
        if not part.strip():
            continue
        key, raw_val = part.split("=", 1)
        quotas[key.strip()] = int(raw_val)
    return quotas


def summarize_by(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    counts = Counter(str(row.get(field, "")) for row in rows)
    return [{field: key, "rows": value} for key, value in sorted(counts.items())]


def run(args: argparse.Namespace) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir = args.output_dir / "metrics"
    tables_dir = args.output_dir / "tables"
    metrics_dir.mkdir(exist_ok=True)
    tables_dir.mkdir(exist_ok=True)

    candidates = build_candidates(args)
    quotas = parse_quotas(args.quotas)
    selected = select_rows(
        candidates=candidates,
        target=args.target,
        quotas=quotas,
        seed=args.seed,
        max_per_submission=args.max_per_submission,
        primary_threshold=args.primary_threshold,
    )
    add_annotation_fields(selected)

    fieldnames = [
        "annotation_id",
        "sample_component",
        "primary_active_reason",
        "active_reasons",
        "comment_id",
        "submission_id",
        "parent_id",
        "subreddit",
        "community_group_proxy",
        "author",
        "candidate_correction",
        "primary_score",
        "primary_pred",
        "secondary_score",
        "secondary_pred",
        "score_diff",
        "created_utc",
        "level",
        "thread_comment_rank",
        "has_parent_body",
        "body_length",
        "has_correction_cue",
        "has_quote",
        "has_quote_edit",
        "has_sarcasm",
        "parent_has_misinfo_cue",
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
        "high_early_hostility_climate",
        "high_early_anti_institutional_climate",
        "sanction_to_correction_presence",
        "submission_title",
        "parent_body",
        "nearest_prior_claim_body",
        "body",
        "relation_correction_type",
        "is_public_correction",
        "target_specificity",
        "annotation_confidence",
        "annotation_notes",
    ]
    write_csv(args.output_dir / "annotation_sample.csv", selected, fieldnames)
    write_csv(tables_dir / "sample_component_counts.csv", summarize_by(selected, "sample_component"), ["sample_component", "rows"])
    write_csv(
        tables_dir / "primary_active_reason_counts.csv",
        summarize_by(selected, "primary_active_reason"),
        ["primary_active_reason", "rows"],
    )
    write_csv(tables_dir / "subreddit_counts.csv", summarize_by(selected, "subreddit"), ["subreddit", "rows"])

    summary = {
        "run_status": "active_relation_annotation_sample",
        "primary_predictions": str(args.primary_predictions),
        "secondary_predictions": str(args.secondary_predictions) if args.secondary_predictions else "",
        "comments": str(args.comments),
        "thread_climate": str(args.thread_climate),
        "output_dir": str(args.output_dir),
        "target": args.target,
        "selected_rows": len(selected),
        "candidate_rows_after_exclusion": len(candidates),
        "exclude_annotations": [str(path) for path in args.exclude_annotations],
        "quotas": quotas,
        "seed": args.seed,
        "max_per_submission": args.max_per_submission,
        "primary_threshold": args.primary_threshold,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(metrics_dir / "run_summary.json", summary)
    (args.output_dir / "run.log").write_text(
        "\n".join(
            [
                "active relation annotation sample",
                f"generated_utc={summary['generated_utc']}",
                f"primary_predictions={args.primary_predictions}",
                f"secondary_predictions={args.secondary_predictions or ''}",
                f"selected_rows={len(selected)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare active-learning samples for relation-aware correction labels.")
    parser.add_argument("--primary-predictions", type=Path, required=True)
    parser.add_argument("--secondary-predictions", type=Path)
    parser.add_argument("--comments", type=Path, required=True)
    parser.add_argument("--thread-climate", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--exclude-annotations", type=Path, nargs="*", default=[])
    parser.add_argument("--target", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260627)
    parser.add_argument("--text-limit", type=int, default=900)
    parser.add_argument("--short-text-length", type=int, default=120)
    parser.add_argument("--max-per-submission", type=int, default=8)
    parser.add_argument("--primary-threshold", type=float, default=0.861328125)
    parser.add_argument("--near-threshold-width", type=float, default=0.12)
    parser.add_argument("--disagreement-width", type=float, default=0.45)
    parser.add_argument("--high-score-cutoff", type=float, default=0.90)
    parser.add_argument("--low-score-cutoff", type=float, default=0.08)
    parser.add_argument("--parent-misinfo-low-score-cutoff", type=float, default=0.25)
    parser.add_argument(
        "--quotas",
        default=(
            "model_disagreement=220,"
            "possible_false_positive_high_score_without_cue=180,"
            "possible_false_negative_contextual=220,"
            "quote_edit_or_sarcasm=130,"
            "short_context_dependent=120,"
            "near_primary_threshold=90,"
            "parent_misinfo_low_score=90"
        ),
    )
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
