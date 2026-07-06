#!/usr/bin/env python3
"""Annotate claim-response pairs with a correction-relation schema."""

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
    generate_one,
    load_model,
    normalize_confidence,
    read_csv,
    read_jsonl,
    write_csv,
    write_jsonl,
)


RELATION_TYPES = {
    "direct_rebuttal",
    "evidence_or_source_correction",
    "definition_or_context_correction",
    "questioning_or_source_request",
    "sarcastic_or_quote_edit_correction",
    "noncorrective_factual_statement",
    "misinformation_support_or_elaboration",
    "general_opinion_or_reaction",
    "unclear",
}

TARGET_SPECIFICITY = {"given_claim", "broader_thread_claim", "general_topic", "none", "unclear"}
NONCORRECTIVE_RELATION_TYPES = {
    "noncorrective_factual_statement",
    "misinformation_support_or_elaboration",
    "general_opinion_or_reaction",
}


SYSTEM_PROMPT = """You are annotating Reddit claim-response pairs for a misinformation-correction study.

Do not think step by step. Do not include hidden reasoning. Return only the final JSON object.

Task: decide whether the response publicly corrects the given claim.

Binary relation label:
- "1": The response corrects, challenges, debunks, fact-checks, or provides evidence against the given claim.
- "0": The response does not correct the given claim.
- "U": The relation is unclear even after reading the provided context.

Important rules:
- Judge the relation between the given claim and the response, not whether the response sounds generally factual.
- Mark "1" only when the response targets the given claim or clearly corrects the same false or misleading idea.
- Mark "0" when the response is only a general opinion, joke, insult, personal experience, unrelated fact, or support for the claim.
- A source request can be a weak correction only when it challenges the credibility of the given claim.
- If the response agrees with the given claim, reinforces it, adds examples for it, or says the claim is right, mark "0" even if the response contains words such as misinformation, false, evidence, CDC, FDA, study, or source.
- If the given claim itself accuses another side of misinformation and the response agrees with that accusation, mark "0" because the response is not correcting the given claim.
- Do not infer a correction target outside the shown claim unless the response clearly rejects the shown claim.

Examples:
- Given claim: "The CDC admits vaccine deaths are real." Response: "Right, they keep hiding those deaths." Label "0" because the response supports the claim.
- Given claim: "Vaccinated people won't die from COVID." Response: "That is incorrect; vaccinated people have died from COVID." Label "1" because the response corrects the claim.
- Given claim: "Ivermectin works." Response: "Source?" Label "1" only if the source request challenges the credibility of that claim; otherwise label "U" or "0".

Relation type:
- "direct_rebuttal": directly rejects or corrects the given claim.
- "evidence_or_source_correction": uses evidence, official data, scientific information, or a fact-checking source against the claim.
- "definition_or_context_correction": corrects framing, definition, causal interpretation, or missing context.
- "questioning_or_source_request": challenges the claim by asking for source or evidence.
- "sarcastic_or_quote_edit_correction": uses sarcasm, quote edit, or short corrective phrasing.
- "noncorrective_factual_statement": factual statement but no clear correction relation to the given claim.
- "misinformation_support_or_elaboration": supports, repeats, or extends the claim.
- "general_opinion_or_reaction": reaction without a correction relation.
- "unclear": insufficient context.

Target specificity:
- "given_claim": response corrects the claim shown in the prompt.
- "broader_thread_claim": response corrects a related claim in the thread, but not the given claim.
- "general_topic": response comments on the broad topic without a specific correction target.
- "none": no correction target.
- "unclear": target cannot be determined.

Return only valid JSON with these fields:
{
  "is_correction_relation": "1|0|U",
  "relation_type": "direct_rebuttal|evidence_or_source_correction|definition_or_context_correction|questioning_or_source_request|sarcastic_or_quote_edit_correction|noncorrective_factual_statement|misinformation_support_or_elaboration|general_opinion_or_reaction|unclear",
  "target_specificity": "given_claim|broader_thread_claim|general_topic|none|unclear",
  "confidence": 0.0,
  "corrected_claim_summary": "short description or empty string",
  "rationale": "one concise sentence"
}
"""


def annotation_key(row: dict[str, Any]) -> str:
    return str(row.get("pair_id") or row.get("annotation_id") or "").strip()


def build_user_prompt(row: dict[str, str]) -> str:
    return f"""Submission title:
{row.get("submission_title", "")}

Subreddit:
{row.get("subreddit", "")}

Pair source:
{row.get("pair_source", "")}

Given claim:
{row.get("claim_text", "")}

Response:
{row.get("response_body", "")}

Does the response publicly correct the given claim?"""


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
        "is_correction_relation": "U",
        "relation_type": "unclear",
        "target_specificity": "unclear",
        "confidence": 0.0,
        "corrected_claim_summary": "",
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


def enforce_label_consistency(label: str, relation_type: str, target_specificity: str) -> str:
    if relation_type in NONCORRECTIVE_RELATION_TYPES:
        return "0"
    if target_specificity in {"none", "general_topic", "broader_thread_claim"}:
        return "0"
    if relation_type == "unclear" or target_specificity == "unclear":
        return "U" if label == "1" else label
    return label


def run(args: argparse.Namespace) -> None:
    start = time.time()
    all_input_rows = read_csv(args.input)
    input_rows = all_input_rows[: args.limit] if args.limit else list(all_input_rows)

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir = output_dir / "metrics"
    metrics_dir.mkdir(exist_ok=True)

    output_csv = output_dir / "llm_pair_annotations.csv"
    output_raw = output_dir / "llm_pair_raw_outputs.jsonl"

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
        "llm_pair_label_raw",
        "llm_pair_label",
        "llm_pair_relation_type",
        "llm_pair_target_specificity",
        "llm_pair_confidence",
        "llm_corrected_claim_summary",
        "llm_pair_rationale",
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
        raw_label = normalize_label(parsed.get("is_correction_relation"))
        relation_type = normalize_relation_type(parsed.get("relation_type"))
        target_specificity = normalize_target_specificity(parsed.get("target_specificity"))
        label = enforce_label_consistency(raw_label, relation_type, target_specificity)
        confidence = normalize_confidence(parsed.get("confidence"))

        out_row = dict(row)
        out_row.update(
            {
                "llm_pair_label_raw": raw_label,
                "llm_pair_label": label,
                "llm_pair_relation_type": relation_type,
                "llm_pair_target_specificity": target_specificity,
                "llm_pair_confidence": confidence,
                "llm_corrected_claim_summary": str(parsed.get("corrected_claim_summary", "")),
                "llm_pair_rationale": str(parsed.get("rationale", "")),
            }
        )
        rows.append(out_row)
        raw_rows.append(
            {
                "annotation_id": row.get("annotation_id"),
                "pair_id": row.get("pair_id"),
                "response_id": row.get("response_id"),
                "claim_id": row.get("claim_id"),
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
        label_counts[str(row["llm_pair_label"])] = label_counts.get(str(row["llm_pair_label"]), 0) + 1
        relation_counts[str(row["llm_pair_relation_type"])] = relation_counts.get(str(row["llm_pair_relation_type"]), 0) + 1
        target_counts[str(row["llm_pair_target_specificity"])] = target_counts.get(str(row["llm_pair_target_specificity"]), 0) + 1

    summary = {
        "run_status": "exploratory_pair_relation_llm_annotation",
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
    parser = argparse.ArgumentParser(description="Run local Qwen annotation on claim-response pairs.")
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
