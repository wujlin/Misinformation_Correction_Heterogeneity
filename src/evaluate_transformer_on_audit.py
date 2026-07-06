#!/usr/bin/env python3
"""Evaluate a transformer correction detector on an external audit set."""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from train_correction_classifier import normalize_token, write_json
from train_transformer_correction_classifier import (
    TransformerPredictionWrapper,
    build_comment_lookup,
    feature_text,
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def prepare_rows(audit: Path, full_comments: Path, feature_mode: str) -> tuple[list[dict[str, Any]], np.ndarray]:
    comments = build_comment_lookup(full_comments)
    rows = []
    labels = []
    for row in read_csv(audit):
        label = str(row.get("llm_label", "")).strip().upper()
        if label not in {"0", "1"}:
            continue
        parent_id = normalize_token(row.get("parent_id"))
        row["parent_body"] = comments.get(parent_id, {}).get("body", "")
        row["feature_text"] = feature_text(row, feature_mode)
        rows.append(row)
        labels.append(int(label))
    return rows, np.array(labels, dtype=int)


def run(args: argparse.Namespace) -> None:
    start = time.time()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir = args.output_dir / "metrics"
    metrics_dir.mkdir(exist_ok=True)

    rows, y_true = prepare_rows(args.audit, args.full_comments, args.feature_mode)
    device = torch.device(args.device if args.device else ("cuda" if torch.cuda.is_available() else "cpu"))
    use_amp = bool(args.fp16 and device.type == "cuda")
    tokenizer = AutoTokenizer.from_pretrained(args.checkpoint_dir)
    model = AutoModelForSequenceClassification.from_pretrained(args.checkpoint_dir)
    model.to(device)

    wrapper = TransformerPredictionWrapper(
        model=model,
        tokenizer=tokenizer,
        device=device,
        max_length=args.max_length,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        use_amp=use_amp,
    )
    scores = wrapper.predict_proba([row["feature_text"] for row in rows])[:, 1]
    preds = (scores >= args.threshold).astype(int)
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, preds, labels=[0, 1], zero_division=0
    )

    summary = {
        "run_status": "external_transformer_audit_evaluation",
        "audit": str(args.audit),
        "full_comments": str(args.full_comments),
        "checkpoint_dir": str(args.checkpoint_dir),
        "output_dir": str(args.output_dir),
        "feature_mode": args.feature_mode,
        "threshold": args.threshold,
        "max_length": args.max_length,
        "batch_size": args.batch_size,
        "device": str(device),
        "fp16": use_amp,
        "rows": int(len(y_true)),
        "class_counts": dict(Counter(map(int, y_true))),
        "positive_rate": float(y_true.mean()) if len(y_true) else 0.0,
        "predicted_positive": int(preds.sum()),
        "predicted_positive_rate": float(preds.mean()) if len(preds) else 0.0,
        "positive_precision": float(precision[1]),
        "positive_recall": float(recall[1]),
        "positive_f1": float(f1[1]),
        "negative_precision": float(precision[0]),
        "negative_recall": float(recall[0]),
        "negative_f1": float(f1[0]),
        "average_precision": float(average_precision_score(y_true, scores)),
        "roc_auc": float(roc_auc_score(y_true, scores)),
        "confusion_matrix": confusion_matrix(y_true, preds, labels=[0, 1]).tolist(),
        "started_utc": datetime.fromtimestamp(start, timezone.utc).isoformat(),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": time.time() - start,
    }
    write_json(metrics_dir / "run_summary.json", summary)

    prediction_rows = []
    for row, score, pred, label in zip(rows, scores, preds, y_true):
        prediction_rows.append(
            {
                "comment_id": row.get("comment_id"),
                "sample_component": row.get("sample_component", ""),
                "llm_label": int(label),
                "score": float(score),
                "pred": int(pred),
                "feature_mode": args.feature_mode,
            }
        )
    with (args.output_dir / "audit_predictions.csv").open("w", encoding="utf-8", newline="") as f:
        fieldnames = ["comment_id", "sample_component", "llm_label", "score", "pred", "feature_mode"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(prediction_rows)

    print(json.dumps(summary, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate a transformer correction detector on an audit CSV.")
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--full-comments", type=Path, required=True)
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--feature-mode",
        choices=["text_only", "text_candidate", "metadata_full", "text_parent", "text_parent_candidate"],
        required=True,
    )
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--batch-size", type=int, default=96)
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--device", default="")
    parser.add_argument("--fp16", action="store_true")
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
