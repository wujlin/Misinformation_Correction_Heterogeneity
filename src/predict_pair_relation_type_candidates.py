#!/usr/bin/env python3
"""Score unlabeled claim-response pairs with a trained relation-type classifier."""

from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer, DataCollatorWithPadding

from train_pair_relation_classifier import feature_text
from train_pair_relation_type_classifier import CORRECTIVE_TYPES, RELATION_TYPES


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


class TextDataset(Dataset):
    def __init__(self, texts: list[str], tokenizer: Any, max_length: int) -> None:
        self.texts = texts
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        return self.tokenizer(self.texts[idx], truncation=True, max_length=self.max_length)


def batch_to_device(batch: dict[str, Any], device: torch.device) -> dict[str, Any]:
    return {key: value.to(device) if hasattr(value, "to") else value for key, value in batch.items()}


@torch.no_grad()
def predict_probs(rows: list[dict[str, Any]], args: argparse.Namespace, device: torch.device) -> np.ndarray:
    tokenizer = AutoTokenizer.from_pretrained(args.checkpoint_dir)
    model = AutoModelForSequenceClassification.from_pretrained(args.checkpoint_dir)
    model.to(device)
    model.eval()
    texts = [feature_text(row, args.feature_mode) for row in rows]
    dataset = TextDataset(texts, tokenizer, args.max_length)
    collator = DataCollatorWithPadding(tokenizer=tokenizer)
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=False,
        collate_fn=collator,
        num_workers=args.num_workers,
        pin_memory=torch.cuda.is_available(),
    )
    probs_out: list[list[float]] = []
    for batch in loader:
        batch = batch_to_device(batch, device)
        with torch.amp.autocast("cuda", enabled=args.fp16 and device.type == "cuda"):
            logits = model(**batch).logits
        probs = torch.softmax(logits, dim=-1)
        probs_out.extend(probs.detach().cpu().numpy().astype(float).tolist())
    return np.array(probs_out, dtype=float)


def run(args: argparse.Namespace) -> None:
    start = time.time()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir = args.output_dir / "metrics"
    predictions_dir = args.output_dir / "predictions"
    metrics_dir.mkdir(exist_ok=True)
    predictions_dir.mkdir(exist_ok=True)

    rows = read_csv(args.input)
    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    probs = predict_probs(rows, args, device)
    corrective_ids = [RELATION_TYPES.index(label) for label in CORRECTIVE_TYPES]
    correction_scores = probs[:, corrective_ids].sum(axis=1)
    pred_type_ids = probs.argmax(axis=1)

    out_rows: list[dict[str, Any]] = []
    for row, prob_vec, score, pred_id in zip(rows, probs, correction_scores, pred_type_ids):
        out = dict(row)
        out["type_pair_relation_score"] = float(score)
        out["type_pair_relation_pred"] = int(float(score) >= args.threshold)
        out["type_pred_relation_type"] = RELATION_TYPES[int(pred_id)]
        for label, value in zip(RELATION_TYPES, prob_vec):
            out[f"type_prob_{label}"] = float(value)
        out_rows.append(out)

    fieldnames = list(rows[0].keys()) + [
        "type_pair_relation_score",
        "type_pair_relation_pred",
        "type_pred_relation_type",
    ] + [f"type_prob_{label}" for label in RELATION_TYPES]
    write_csv(predictions_dir / "pair_candidate_type_predictions.csv", out_rows, fieldnames)
    summary = {
        "run_status": "pair_relation_type_candidate_prediction",
        "input": str(args.input),
        "checkpoint_dir": str(args.checkpoint_dir),
        "output_dir": str(args.output_dir),
        "feature_mode": args.feature_mode,
        "rows": len(out_rows),
        "threshold": args.threshold,
        "predicted_positive": int(sum(int(row["type_pair_relation_pred"]) for row in out_rows)),
        "score_mean": float(np.mean(correction_scores)) if len(correction_scores) else 0.0,
        "score_min": float(np.min(correction_scores)) if len(correction_scores) else 0.0,
        "score_max": float(np.max(correction_scores)) if len(correction_scores) else 0.0,
        "device": str(device),
        "fp16": bool(args.fp16 and device.type == "cuda"),
        "started_utc": datetime.fromtimestamp(start, timezone.utc).isoformat(),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": time.time() - start,
    }
    write_json(metrics_dir / "run_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score pair candidates with a relation-type classifier.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--feature-mode", default="claim_response")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument("--cpu", action="store_true")
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
