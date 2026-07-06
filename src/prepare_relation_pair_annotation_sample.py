#!/usr/bin/env python3
"""Prepare claim-response pairs for relation-level correction annotation.

The output unit is not a single Reddit comment. The output unit is a candidate
relation between a prior claim and a later response. This makes the measurement
task closer to the theoretical object: whether exposure to a questionable claim
is converted into a public correction relation.
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
    "no evidence",
    "citation",
    "link?",
]

CLAIM_TERMS = [
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
    "side effects",
    "blood clots",
    "myocarditis",
    "vaccine death",
    "vaccine deaths",
    "forced vaccination",
    "not a vaccine",
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
        if " " in term or any(ch in term for ch in ["/", "-", "?"]):
            patterns.append(re.compile(escaped))
        else:
            patterns.append(re.compile(rf"\b{escaped}\b"))
    return patterns


CORRECTION_PATTERNS = compile_terms(CORRECTION_TERMS)
CLAIM_PATTERNS = compile_terms(CLAIM_TERMS)
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
    lowered = str(text or "").lower()
    return int(any(pattern.search(lowered) for pattern in patterns))


def load_predictions(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in read_csv(path):
        comment_id = normalize_token(row.get("comment_id"))
        if not comment_id:
            continue
        out[comment_id] = {
            "comment_id": comment_id,
            "submission_id": normalize_token(row.get("submission_id")),
            "parent_id": normalize_token(row.get("parent_id")),
            "subreddit": normalize_token(row.get("subreddit")),
            "community_group_proxy": normalize_token(row.get("community_group_proxy")),
            "author": normalize_author(row.get("author")),
            "candidate_correction": to_int(row.get("candidate_correction")),
            "public_correction_score": to_float(row.get("public_correction_score")),
            "public_correction_pred": to_int(row.get("public_correction_pred")),
            "created_utc": to_float(row.get("created_utc")),
        }
    return out


def load_existing_pair_ids(paths: list[Path]) -> set[str]:
    out: set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        for row in read_csv(path):
            pair_id = str(row.get("pair_id", "")).strip()
            if pair_id:
                out.add(pair_id)
    return out


def load_comments(path: Path, text_limit: int) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    rows: list[dict[str, Any]] = []
    for raw in iter_jsonl(path):
        comment_id = normalize_token(raw.get("comment_id"))
        submission_id = normalize_token(raw.get("submission_id"))
        if not comment_id or not submission_id:
            continue
        rows.append(
            {
                "comment_id": comment_id,
                "submission_id": submission_id,
                "parent_id": normalize_token(raw.get("parent_id")),
                "author": normalize_author(raw.get("author")),
                "subreddit": normalize_token(raw.get("subreddit")),
                "created_utc": to_float(raw.get("created_utc")),
                "level": to_int(raw.get("level")),
                "submission_title": compact_text(raw.get("submission_title"), text_limit),
                "body": compact_text(raw.get("body"), text_limit),
                "candidate_correction": int(bool(raw.get("candidate_correction"))),
            }
        )

    by_id = {row["comment_id"]: row for row in rows}
    by_submission: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_submission[row["submission_id"]].append(row)
    for items in by_submission.values():
        items.sort(key=lambda row: (row["created_utc"], row["comment_id"]))
        nearest_prior_claim: dict[str, Any] | None = None
        for rank, row in enumerate(items, 1):
            row["thread_comment_rank"] = rank
            row["nearest_prior_claim_id"] = nearest_prior_claim["comment_id"] if nearest_prior_claim else ""
            if has_match(row.get("body", ""), CLAIM_PATTERNS):
                nearest_prior_claim = row
    return by_id, by_submission


def title_claim_id(submission_id: str) -> str:
    return f"submission:{submission_id}"


def make_pair_id(claim_id: str, response_id: str, pair_source: str) -> str:
    return f"{pair_source}:{claim_id}->{response_id}"


def pair_base(
    *,
    response: dict[str, Any],
    prediction: dict[str, Any],
    claim_id: str,
    claim_role: str,
    claim_author: str,
    claim_created_utc: float,
    claim_text: str,
    pair_source: str,
    sample_component: str,
    text_limit: int,
) -> dict[str, Any]:
    response_body = compact_text(response.get("body"), text_limit)
    claim_text = compact_text(claim_text, text_limit)
    time_gap = response["created_utc"] - claim_created_utc if claim_created_utc else ""
    same_author = int(bool(claim_author) and claim_author == response.get("author"))
    return {
        "pair_id": make_pair_id(claim_id, response["comment_id"], pair_source),
        "sample_component": sample_component,
        "pair_source": pair_source,
        "claim_id": claim_id,
        "claim_role": claim_role,
        "claim_author": claim_author,
        "claim_created_utc": claim_created_utc,
        "claim_text": claim_text,
        "claim_has_misinfo_cue": has_match(claim_text, CLAIM_PATTERNS),
        "response_id": response["comment_id"],
        "response_parent_id": response.get("parent_id", ""),
        "response_author": response.get("author", ""),
        "response_created_utc": response.get("created_utc", 0.0),
        "response_body": response_body,
        "response_level": response.get("level", 0),
        "response_thread_comment_rank": response.get("thread_comment_rank", 0),
        "response_has_correction_cue": has_match(response_body, CORRECTION_PATTERNS),
        "response_has_quote": int(response_body.strip().startswith(">") or "\n>" in response_body),
        "response_has_quote_edit": int("~~" in response_body or "ftfy" in response_body.lower()),
        "response_has_sarcasm": has_match(response_body, SARCASM_PATTERNS),
        "same_author": same_author,
        "time_gap_seconds": time_gap,
        "submission_id": response.get("submission_id", ""),
        "submission_title": response.get("submission_title", ""),
        "subreddit": response.get("subreddit", ""),
        "community_group_proxy": prediction.get("community_group_proxy", ""),
        "candidate_correction": prediction.get("candidate_correction", response.get("candidate_correction", 0)),
        "public_correction_score": prediction.get("public_correction_score", 0.0),
        "public_correction_pred": prediction.get("public_correction_pred", 0),
        "is_correction_relation": "",
        "relation_type": "",
        "target_specificity": "",
        "annotation_confidence": "",
        "annotation_notes": "",
    }


def build_pairs(args: argparse.Namespace) -> list[dict[str, Any]]:
    predictions = load_predictions(args.primary_predictions)
    by_id, by_submission = load_comments(args.comments, args.text_limit)
    excluded = load_existing_pair_ids(args.exclude_pairs)

    pairs: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(row: dict[str, Any]) -> None:
        pair_id = str(row["pair_id"])
        if pair_id in seen or pair_id in excluded:
            return
        seen.add(pair_id)
        pairs.append(row)

    for response_id, response in by_id.items():
        pred = predictions.get(response_id, {})
        score = to_float(pred.get("public_correction_score", response.get("candidate_correction", 0)))
        is_high_score = score >= args.high_score_cutoff
        is_near_threshold = abs(score - args.primary_threshold) <= args.near_threshold_width
        response_has_cue = has_match(response.get("body", ""), CORRECTION_PATTERNS)
        response_short = len(str(response.get("body", ""))) <= args.short_text_length

        parent = by_id.get(response.get("parent_id", ""))
        if parent:
            parent_has_claim = has_match(parent.get("body", ""), CLAIM_PATTERNS)
            if is_high_score:
                component = "parent_pair_high_score"
            elif is_near_threshold:
                component = "parent_pair_near_threshold"
            elif parent_has_claim and (response_has_cue or response_short):
                component = "parent_claim_cue_or_short"
            else:
                component = "parent_pair_random_calibration"
            add(
                pair_base(
                    response=response,
                    prediction=pred,
                    claim_id=parent["comment_id"],
                    claim_role="parent_comment",
                    claim_author=parent.get("author", ""),
                    claim_created_utc=parent.get("created_utc", 0.0),
                    claim_text=parent.get("body", ""),
                    pair_source="parent_comment",
                    sample_component=component,
                    text_limit=args.text_limit,
                )
            )
        elif response.get("parent_id") == response.get("submission_id") or response.get("level") == 1:
            title_has_claim = has_match(response.get("submission_title", ""), CLAIM_PATTERNS)
            if is_high_score or response_has_cue or title_has_claim:
                add(
                    pair_base(
                        response=response,
                        prediction=pred,
                        claim_id=title_claim_id(response["submission_id"]),
                        claim_role="submission_title",
                        claim_author="",
                        claim_created_utc=0.0,
                        claim_text=response.get("submission_title", ""),
                        pair_source="submission_title",
                        sample_component="submission_title_pair",
                        text_limit=args.text_limit,
                    )
                )

        prior_claim = by_id.get(str(response.get("nearest_prior_claim_id", "")))
        if prior_claim and prior_claim["comment_id"] != response.get("parent_id"):
            if is_high_score or response_has_cue or is_near_threshold:
                add(
                    pair_base(
                        response=response,
                        prediction=pred,
                        claim_id=prior_claim["comment_id"],
                        claim_role="earlier_thread_claim",
                        claim_author=prior_claim.get("author", ""),
                        claim_created_utc=prior_claim.get("created_utc", 0.0),
                        claim_text=prior_claim.get("body", ""),
                        pair_source="earlier_thread_claim",
                        sample_component="earlier_claim_pair",
                        text_limit=args.text_limit,
                    )
                )

    return pairs


def pair_priority(row: dict[str, Any], rng: random.Random) -> tuple[Any, ...]:
    score = to_float(row.get("public_correction_score"))
    has_claim = to_int(row.get("claim_has_misinfo_cue"))
    has_cue = to_int(row.get("response_has_correction_cue"))
    source_rank = {
        "parent_comment": 0,
        "earlier_thread_claim": 1,
        "submission_title": 2,
    }.get(str(row.get("pair_source")), 3)
    return (-has_claim, -has_cue, -score, source_rank, rng.random())


def select_pairs(args: argparse.Namespace, pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rng = random.Random(args.seed)
    quotas = parse_quotas(args.quotas)
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    response_counts: Counter[str] = Counter()
    submission_counts: Counter[str] = Counter()

    def add(row: dict[str, Any]) -> bool:
        pair_id = str(row["pair_id"])
        response_id = str(row["response_id"])
        submission_id = str(row["submission_id"])
        if pair_id in selected_ids:
            return False
        if response_counts[response_id] >= args.max_pairs_per_response:
            return False
        if submission_counts[submission_id] >= args.max_pairs_per_submission:
            return False
        out = dict(row)
        out["annotation_id"] = f"RPS{len(selected) + 1:05d}"
        selected.append(out)
        selected_ids.add(pair_id)
        response_counts[response_id] += 1
        submission_counts[submission_id] += 1
        return True

    for component, quota in quotas.items():
        pool = [row for row in pairs if row.get("sample_component") == component]
        pool.sort(key=lambda row: pair_priority(row, rng))
        count = 0
        for row in pool:
            if count >= quota:
                break
            if add(row):
                count += 1

    remaining = [row for row in pairs if row["pair_id"] not in selected_ids]
    remaining.sort(key=lambda row: pair_priority(row, rng))
    for row in remaining:
        if len(selected) >= args.target:
            break
        add(row)

    return selected[: args.target]


def parse_quotas(value: str) -> dict[str, int]:
    quotas: dict[str, int] = {}
    for part in value.split(","):
        part = part.strip()
        if not part:
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

    pairs = build_pairs(args)
    selected = select_pairs(args, pairs)

    fieldnames = [
        "annotation_id",
        "pair_id",
        "sample_component",
        "pair_source",
        "claim_id",
        "claim_role",
        "claim_author",
        "claim_created_utc",
        "claim_text",
        "claim_has_misinfo_cue",
        "response_id",
        "response_parent_id",
        "response_author",
        "response_created_utc",
        "response_body",
        "response_level",
        "response_thread_comment_rank",
        "response_has_correction_cue",
        "response_has_quote",
        "response_has_quote_edit",
        "response_has_sarcasm",
        "same_author",
        "time_gap_seconds",
        "submission_id",
        "submission_title",
        "subreddit",
        "community_group_proxy",
        "candidate_correction",
        "public_correction_score",
        "public_correction_pred",
        "is_correction_relation",
        "relation_type",
        "target_specificity",
        "annotation_confidence",
        "annotation_notes",
    ]
    write_csv(args.output_dir / "annotation_pairs.csv", selected, fieldnames)
    write_csv(tables_dir / "sample_component_counts.csv", summarize_by(selected, "sample_component"), ["sample_component", "rows"])
    write_csv(tables_dir / "pair_source_counts.csv", summarize_by(selected, "pair_source"), ["pair_source", "rows"])
    write_csv(tables_dir / "subreddit_counts.csv", summarize_by(selected, "subreddit"), ["subreddit", "rows"])

    summary = {
        "run_status": "relation_pair_annotation_sample",
        "primary_predictions": str(args.primary_predictions),
        "comments": str(args.comments),
        "output_dir": str(args.output_dir),
        "candidate_pairs": len(pairs),
        "selected_pairs": len(selected),
        "target": args.target,
        "quotas": parse_quotas(args.quotas),
        "seed": args.seed,
        "max_pairs_per_response": args.max_pairs_per_response,
        "max_pairs_per_submission": args.max_pairs_per_submission,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(metrics_dir / "run_summary.json", summary)
    (args.output_dir / "run.log").write_text(
        "\n".join(
            [
                "relation pair annotation sample",
                f"generated_utc={summary['generated_utc']}",
                f"candidate_pairs={len(pairs)}",
                f"selected_pairs={len(selected)}",
                f"primary_predictions={args.primary_predictions}",
                f"comments={args.comments}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare claim-response pairs for relation-level correction annotation.")
    parser.add_argument("--primary-predictions", type=Path, required=True)
    parser.add_argument("--comments", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--exclude-pairs", type=Path, nargs="*", default=[])
    parser.add_argument("--target", type=int, default=1200)
    parser.add_argument("--seed", type=int, default=20260627)
    parser.add_argument("--text-limit", type=int, default=900)
    parser.add_argument("--short-text-length", type=int, default=120)
    parser.add_argument("--max-prior-comments", type=int, default=40)
    parser.add_argument("--max-pairs-per-response", type=int, default=2)
    parser.add_argument("--max-pairs-per-submission", type=int, default=10)
    parser.add_argument("--primary-threshold", type=float, default=0.861328125)
    parser.add_argument("--near-threshold-width", type=float, default=0.12)
    parser.add_argument("--high-score-cutoff", type=float, default=0.90)
    parser.add_argument(
        "--quotas",
        default=(
            "parent_pair_high_score=250,"
            "parent_pair_near_threshold=180,"
            "parent_claim_cue_or_short=200,"
            "earlier_claim_pair=250,"
            "submission_title_pair=120,"
            "parent_pair_random_calibration=200"
        ),
    )
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
