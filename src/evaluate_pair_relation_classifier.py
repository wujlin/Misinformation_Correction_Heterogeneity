#!/usr/bin/env python3
"""Evaluate a trained pair-relation classifier on an external pair audit set."""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    precision_recall_curve,
    precision_recall_fscore_support,
    roc_auc_score,
)
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer, DataCollatorWithPadding

from train_pair_relation_classifier import compact_text, feature_text


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


def load_training_settings(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "feature_mode": data.get("feature_mode"),
        "threshold": data.get("threshold"),
        "model_name": data.get("model_name"),
        "source_training_summary": str(path),
    }


def load_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    out = []
    for row in read_csv(args.annotations):
        label = str(row.get(args.label_field, "")).strip()
        if label not in {"0", "1"}:
            continue
        item = dict(row)
        item["target"] = int(label)
        item["feature_text"] = feature_text(item, args.feature_mode)
        out.append(item)
    return out


def batch_to_device(batch: dict[str, Any], device: torch.device) -> dict[str, Any]:
    return {key: value.to(device) if hasattr(value, "to") else value for key, value in batch.items()}


@torch.no_grad()
def predict_scores(rows: list[dict[str, Any]], args: argparse.Namespace, device: torch.device) -> np.ndarray:
    tokenizer = AutoTokenizer.from_pretrained(args.checkpoint_dir)
    model = AutoModelForSequenceClassification.from_pretrained(args.checkpoint_dir)
    model.to(device)
    model.eval()
    dataset = TextDataset([row["feature_text"] for row in rows], tokenizer, args.max_length)
    collator = DataCollatorWithPadding(tokenizer=tokenizer)
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=False,
        collate_fn=collator,
        num_workers=args.num_workers,
        pin_memory=torch.cuda.is_available(),
    )
    scores: list[float] = []
    for batch in loader:
        batch = batch_to_device(batch, device)
        with torch.amp.autocast("cuda", enabled=args.fp16 and device.type == "cuda"):
            logits = model(**batch).logits
        probs = torch.softmax(logits, dim=-1)[:, 1]
        scores.extend(probs.detach().cpu().numpy().astype(float).tolist())
    return np.array(scores, dtype=float)


def safe_metric(fn: Any, y_true: np.ndarray, scores: np.ndarray) -> float | None:
    try:
        return float(fn(y_true, scores))
    except ValueError:
        return None


def select_threshold(y_true: np.ndarray, scores: np.ndarray) -> dict[str, Any]:
    precision, recall, thresholds = precision_recall_curve(y_true, scores)
    candidates = []
    for i, threshold in enumerate(thresholds):
        p = float(precision[i])
        r = float(recall[i])
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        candidates.append({"threshold": float(threshold), "precision": p, "recall": r, "f1": f1})
    if not candidates:
        return {"threshold": 0.5, "precision": 0.0, "recall": 0.0, "f1": 0.0}
    return max(candidates, key=lambda item: (item["f1"], item["precision"], item["recall"]))


def metrics(y_true: np.ndarray, scores: np.ndarray, threshold: float) -> dict[str, Any]:
    preds = (scores >= threshold).astype(int)
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, preds, labels=[0, 1], zero_division=0
    )
    return {
        "rows": int(len(y_true)),
        "threshold": float(threshold),
        "class_counts": dict(Counter(map(int, y_true))),
        "predicted_positive": int(preds.sum()),
        "predicted_positive_rate": float(preds.mean()) if len(preds) else 0.0,
        "confusion_matrix": confusion_matrix(y_true, preds, labels=[0, 1]).tolist(),
        "classification_report": classification_report(y_true, preds, output_dict=True, zero_division=0),
        "per_class": {
            str(label): {
                "precision": float(precision[i]),
                "recall": float(recall[i]),
                "f1": float(f1[i]),
                "support": int(support[i]),
            }
            for i, label in enumerate([0, 1])
        },
        "roc_auc": safe_metric(roc_auc_score, y_true, scores),
        "average_precision": safe_metric(average_precision_score, y_true, scores),
    }


def subgroup_rows(rows: list[dict[str, Any]], scores: np.ndarray, field: str, threshold: float) -> list[dict[str, Any]]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for idx, row in enumerate(rows):
        grouped[str(row.get(field, ""))].append(idx)
    out = []
    for key, idxs in sorted(grouped.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        y = np.array([int(rows[i]["target"]) for i in idxs], dtype=int)
        s = scores[idxs]
        m = metrics(y, s, threshold)
        out.append(
            {
                field: key,
                "rows": m["rows"],
                "positive": m["class_counts"].get(1, 0),
                "negative": m["class_counts"].get(0, 0),
                "average_precision": m["average_precision"],
                "roc_auc": m["roc_auc"],
                "positive_f1": m["per_class"]["1"]["f1"],
                "positive_precision": m["per_class"]["1"]["precision"],
                "positive_recall": m["per_class"]["1"]["recall"],
                "predicted_positive": m["predicted_positive"],
            }
        )
    return out


def prediction_rows(rows: list[dict[str, Any]], scores: np.ndarray, threshold: float) -> list[dict[str, Any]]:
    out = []
    for row, score in zip(rows, scores):
        out.append(
            {
                "annotation_id": row.get("annotation_id"),
                "pair_id": row.get("pair_id"),
                "claim_id": row.get("claim_id"),
                "response_id": row.get("response_id"),
                "pair_source": row.get("pair_source"),
                "sample_component": row.get("sample_component"),
                "subreddit": row.get("subreddit"),
                "target": int(row.get("target")),
                "pair_relation_score": float(score),
                "pair_relation_pred": int(float(score) >= threshold),
                "manual_pair_relation_type": row.get("manual_pair_relation_type"),
                "manual_pair_target_specificity": row.get("manual_pair_target_specificity"),
                "claim_text": compact_text(row.get("claim_text"), 800),
                "response_body": compact_text(row.get("response_body"), 800),
            }
        )
    return out


def run(args: argparse.Namespace) -> None:
    start = time.time()
    settings = load_training_settings(args.training_summary)
    if args.feature_mode == "auto":
        args.feature_mode = settings.get("feature_mode") or "claim_response"
    if args.threshold is None:
        args.threshold = settings.get("threshold")
    if args.threshold is None:
        raise ValueError("Provide --threshold or --training-summary with a threshold.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir = args.output_dir / "metrics"
    tables_dir = args.output_dir / "tables"
    predictions_dir = args.output_dir / "predictions"
    for path in [metrics_dir, tables_dir, predictions_dir]:
        path.mkdir(parents=True, exist_ok=True)

    rows = load_rows(args)
    y_true = np.array([int(row["target"]) for row in rows], dtype=int)
    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    scores = predict_scores(rows, args, device)
    fixed_metrics = metrics(y_true, scores, float(args.threshold))
    oracle_threshold = select_threshold(y_true, scores)
    oracle_metrics = metrics(y_true, scores, float(oracle_threshold["threshold"]))

    write_json(metrics_dir / "fixed_threshold_metrics.json", fixed_metrics)
    write_json(metrics_dir / "audit_oracle_threshold_metrics.json", oracle_metrics)
    write_json(metrics_dir / "audit_oracle_threshold_selection.json", oracle_threshold)
    write_csv(
        predictions_dir / "pair_audit_predictions.csv",
        prediction_rows(rows, scores, float(args.threshold)),
        [
            "annotation_id",
            "pair_id",
            "claim_id",
            "response_id",
            "pair_source",
            "sample_component",
            "subreddit",
            "target",
            "pair_relation_score",
            "pair_relation_pred",
            "manual_pair_relation_type",
            "manual_pair_target_specificity",
            "claim_text",
            "response_body",
        ],
    )
    for field in ["sample_component", "pair_source", "manual_pair_relation_type", "manual_pair_target_specificity", "subreddit"]:
        rows_out = subgroup_rows(rows, scores, field, float(args.threshold))
        write_csv(
            tables_dir / f"{field}_metrics.csv",
            rows_out,
            [
                field,
                "rows",
                "positive",
                "negative",
                "average_precision",
                "roc_auc",
                "positive_f1",
                "positive_precision",
                "positive_recall",
                "predicted_positive",
            ],
        )

    summary = {
        "run_status": "external_pair_relation_classifier_evaluation",
        "annotations": str(args.annotations),
        "checkpoint_dir": str(args.checkpoint_dir),
        "training_summary": str(args.training_summary) if args.training_summary else "",
        "output_dir": str(args.output_dir),
        "feature_mode": args.feature_mode,
        "label_field": args.label_field,
        "rows": len(rows),
        "class_counts": dict(Counter(map(int, y_true))),
        "fixed_threshold": float(args.threshold),
        "fixed_threshold_average_precision": fixed_metrics["average_precision"],
        "fixed_threshold_roc_auc": fixed_metrics["roc_auc"],
        "fixed_threshold_positive_f1": fixed_metrics["per_class"]["1"]["f1"],
        "fixed_threshold_positive_precision": fixed_metrics["per_class"]["1"]["precision"],
        "fixed_threshold_positive_recall": fixed_metrics["per_class"]["1"]["recall"],
        "fixed_threshold_predicted_positive": fixed_metrics["predicted_positive"],
        "audit_oracle_threshold": oracle_threshold,
        "audit_oracle_positive_f1": oracle_metrics["per_class"]["1"]["f1"],
        "device": str(device),
        "fp16": bool(args.fp16 and device.type == "cuda"),
        "max_length": args.max_length,
        "batch_size": args.batch_size,
        "started_utc": datetime.fromtimestamp(start, timezone.utc).isoformat(),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": time.time() - start,
    }
    write_json(metrics_dir / "run_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate a pair-relation classifier on an external audit set.")
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--training-summary", type=Path)
    parser.add_argument("--feature-mode", default="auto")
    parser.add_argument("--label-field", default="manual_pair_label")
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument("--cpu", action="store_true")
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
