#!/usr/bin/env python3
"""Annotate active samples with a relation-aware correction schema.

This script keeps the binary public-correction label but asks the model to
classify why a comment is or is not a correction. The richer schema is intended
for detector improvement and error analysis, not for multiplying theoretical
claims.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm_annotate_public_correction import (
    annotation_key,
    generate_one,
    load_model,
    normalize_confidence,
    read_csv,
    read_jsonl,
    write_csv,
    write_jsonl,
)


RELATION_TYPES = {
    "direct_parent_correction",
    "thread_claim_correction",
    "evidence_or_source_correction",
    "sarcastic_or_quote_edit_correction",
    "noncorrective_factual_statement",
    "misinformation_support_or_claim",
    "general_opinion_or_reaction",
    "unclear",
}

TARGET_SPECIFICITY = {"parent", "earlier_thread_claim", "general_thread_topic", "none", "unclear"}

SYSTEM_PROMPT = """You are annotating Reddit comments for a misinformation-correction study.

Do not think step by step. Do not include hidden reasoning. Return only the final JSON object.

Task: decide whether the target comment performs public correction, and classify the relation type.

Binary label:
- "1": The comment publicly corrects, challenges, debunks, fact-checks, or provides evidence against a false or misleading claim in the parent comment or earlier thread.
- "0": The comment does not perform public correction.
- "U": The correction function is unclear even after reading the provided context.

Relation type:
- "direct_parent_correction": directly corrects or rejects the parent comment.
- "thread_claim_correction": corrects an earlier claim in the thread, but not necessarily the direct parent.
- "evidence_or_source_correction": provides source, data, study, official information, or factual evidence to correct a claim.
- "sarcastic_or_quote_edit_correction": uses sarcasm, quote edits, strikethrough, or very short wording to correct a claim.
- "noncorrective_factual_statement": factual or explanatory statement, but it does not clearly correct a prior false claim.
- "misinformation_support_or_claim": repeats, supports, or extends a misinformation claim.
- "general_opinion_or_reaction": agreement, insult, joke, personal experience, or opinion without correction.
- "unclear": insufficient context.

Target specificity:
- "parent": the correction target is the parent comment.
- "earlier_thread_claim": the target is another earlier claim in the thread.
- "general_thread_topic": the comment corrects a broad topic without a specific target.
- "none": no correction target.
- "unclear": target cannot be determined.

Return only valid JSON with these fields:
{
  "is_public_correction": "1|0|U",
  "relation_type": "direct_parent_correction|thread_claim_correction|evidence_or_source_correction|sarcastic_or_quote_edit_correction|noncorrective_factual_statement|misinformation_support_or_claim|general_opinion_or_reaction|unclear",
  "target_specificity": "parent|earlier_thread_claim|general_thread_topic|none|unclear",
  "confidence": 0.0,
  "correction_target": "short description or empty string",
  "rationale": "one concise sentence"
}
"""


def build_user_prompt(row: dict[str, str]) -> str:
    parent_body = str(row.get("parent_body", "") or "").strip()
    parent_section = f"\nParent comment being replied to:\n{parent_body}\n" if parent_body else ""
    prior_body = str(row.get("nearest_prior_claim_body", "") or "").strip()
    prior_section = f"\nNearest prior misinformation-like claim in thread:\n{prior_body}\n" if prior_body else ""
    active_reasons = str(row.get("active_reasons", "") or row.get("sample_component", "") or "").strip()
    return f"""Submission title:
{row.get("submission_title", "")}

Subreddit:
{row.get("subreddit", "")}

Active-sampling reason:
{active_reasons}
{parent_section}{prior_section}
Target comment:
{row.get("body", "")}

Does the target comment perform public correction? If yes, what type of correction relation is it?"""


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {
        "is_public_correction": "U",
        "relation_type": "unclear",
        "target_specificity": "unclear",
        "confidence": 0.0,
        "correction_target": "",
        "rationale": "Model output could not be parsed as JSON.",
    }


def normalize_label(value: Any) -> str:
    value = str(value).strip().upper()
    if value in {"1", "TRUE", "YES", "Y"}:
        return "1"
    if value in {"0", "FALSE", "NO", "N"}:
        return "0"
    return "U"


def normalize_relation_type(value: Any) -> str:
    value = str(value or "").strip().lower()
    return value if value in RELATION_TYPES else "unclear"


def normalize_target_specificity(value: Any) -> str:
    value = str(value or "").strip().lower()
    return value if value in TARGET_SPECIFICITY else "unclear"


def run(args: argparse.Namespace) -> None:
    start = time.time()
    all_input_rows = read_csv(args.input)
    input_rows = all_input_rows[: args.limit] if args.limit else list(all_input_rows)

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir = output_dir / "metrics"
    metrics_dir.mkdir(exist_ok=True)

    output_csv = output_dir / "llm_relation_annotations.csv"
    output_raw = output_dir / "llm_relation_raw_outputs.jsonl"

    rows: list[dict[str, Any]] = []
    raw_rows: list[dict[str, Any]] = []
    if args.resume and output_csv.exists():
        rows = read_csv(output_csv)
        raw_rows = read_jsonl(output_raw)
        completed = {annotation_key(row) for row in rows if annotation_key(row)}
        input_rows = [row for row in input_rows if annotation_key(row) not in completed]

    tokenizer, model = load_model(
        args.model,
        args.dtype,
        args.device_map,
        args.trust_remote_code,
        args.attn_implementation,
    )

    csv_fields = list(all_input_rows[0].keys()) + [
        "llm_label",
        "llm_relation_type",
        "llm_target_specificity",
        "llm_confidence",
        "llm_correction_target",
        "llm_rationale",
    ]

    for index, row in enumerate(input_rows, 1):
        raw_output = generate_one(
            tokenizer=tokenizer,
            model=model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=build_user_prompt(row),
            max_new_tokens=args.max_new_tokens,
            temperature=args.temperature,
        )
        parsed = extract_json(raw_output)
        label = normalize_label(parsed.get("is_public_correction"))
        relation_type = normalize_relation_type(parsed.get("relation_type"))
        target_specificity = normalize_target_specificity(parsed.get("target_specificity"))
        confidence = normalize_confidence(parsed.get("confidence"))

        out_row = dict(row)
        out_row.update(
            {
                "llm_label": label,
                "llm_relation_type": relation_type,
                "llm_target_specificity": target_specificity,
                "llm_confidence": confidence,
                "llm_correction_target": str(parsed.get("correction_target", "")),
                "llm_rationale": str(parsed.get("rationale", "")),
            }
        )
        rows.append(out_row)
        raw_rows.append(
            {
                "annotation_id": row.get("annotation_id"),
                "comment_id": row.get("comment_id"),
                "raw_output": raw_output,
                "parsed_output": parsed,
            }
        )
        if index % args.log_every == 0 or index == len(input_rows):
            print(f"Annotated {index}/{len(input_rows)}")
        if args.save_every and index % args.save_every == 0:
            write_csv(output_csv, rows, csv_fields)
            write_jsonl(output_raw, raw_rows)

    write_csv(output_csv, rows, csv_fields)
    write_jsonl(output_raw, raw_rows)

    label_counts: dict[str, int] = {}
    relation_counts: dict[str, int] = {}
    target_counts: dict[str, int] = {}
    for row in rows:
        label_counts[str(row["llm_label"])] = label_counts.get(str(row["llm_label"]), 0) + 1
        relation_counts[str(row["llm_relation_type"])] = relation_counts.get(str(row["llm_relation_type"]), 0) + 1
        target_counts[str(row["llm_target_specificity"])] = target_counts.get(str(row["llm_target_specificity"]), 0) + 1

    summary = {
        "run_status": "exploratory_relation_aware_llm_annotation",
        "input": str(args.input),
        "output_dir": str(output_dir),
        "model": args.model,
        "rows": len(rows),
        "new_rows_this_run": len(input_rows),
        "resume": args.resume,
        "label_counts": label_counts,
        "relation_type_counts": relation_counts,
        "target_specificity_counts": target_counts,
        "temperature": args.temperature,
        "max_new_tokens": args.max_new_tokens,
        "dtype": args.dtype,
        "device_map": args.device_map,
        "trust_remote_code": args.trust_remote_code,
        "attn_implementation": args.attn_implementation,
        "started_utc": datetime.fromtimestamp(start, timezone.utc).isoformat(),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": time.time() - start,
    }
    (metrics_dir / "run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local Qwen annotation with a relation-aware correction schema.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--dtype", choices=["auto", "float16", "bfloat16", "float32"], default="bfloat16")
    parser.add_argument("--device-map", default="auto")
    parser.add_argument("--trust-remote-code", action="store_true")
    parser.add_argument("--attn-implementation", choices=["auto", "sdpa", "flash_attention_2", "eager"], default="auto")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-new-tokens", type=int, default=260)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--log-every", type=int, default=20)
    parser.add_argument("--save-every", type=int, default=50)
    parser.add_argument("--resume", action="store_true")
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
