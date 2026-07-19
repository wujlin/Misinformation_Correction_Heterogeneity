#!/usr/bin/env python3
"""Fine-tune a transformer cross-encoder for claim-response correction relations."""

from __future__ import annotations

import argparse
import csv
import json
import random
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    precision_recall_curve,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    get_linear_schedule_with_warmup,
)


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


def compact_text(value: Any, limit: int = 1200) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit] if len(text) > limit else text


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


class TextDataset(Dataset):
    def __init__(self, texts: list[str], labels: list[int] | None, tokenizer: Any, max_length: int) -> None:
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        item = self.tokenizer(self.texts[idx], truncation=True, max_length=self.max_length)
        if self.labels is not None:
            item["labels"] = int(self.labels[idx])
        return item


def feature_text(row: dict[str, Any], feature_mode: str) -> str:
    title = compact_text(row.get("submission_title"))
    claim = compact_text(row.get("claim_text"))
    response = compact_text(row.get("response_body"))
    pair_source = compact_text(row.get("pair_source"), 80)
    subreddit = compact_text(row.get("subreddit"), 80)
    if feature_mode == "claim_response":
        return f"CLAIM={claim} RESPONSE={response}"
    if feature_mode == "title_claim_response":
        return f"TITLE={title} CLAIM={claim} RESPONSE={response}"
    if feature_mode == "metadata_title_claim_response":
        return f"SUBREDDIT={subreddit} PAIR_SOURCE={pair_source} TITLE={title} CLAIM={claim} RESPONSE={response}"
    raise ValueError(f"Unsupported feature_mode: {feature_mode}")


def load_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    rows = []
    for row in read_csv(args.annotations):
        label = str(row.get(args.label_field, "")).strip()
        if label not in {"0", "1"}:
            continue
        out = dict(row)
        out["target"] = int(label)
        out["feature_text"] = feature_text(out, args.feature_mode)
        rows.append(out)
    return rows


def split_random(rows: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, list[dict[str, Any]]]:
    y = [row["target"] for row in rows]
    train_val, test = train_test_split(rows, test_size=args.test_size, stratify=y, random_state=args.seed)
    y_train_val = [row["target"] for row in train_val]
    val_relative = args.val_size / max(1e-9, 1.0 - args.test_size)
    train, val = train_test_split(train_val, test_size=val_relative, stratify=y_train_val, random_state=args.seed)
    return {"train": train, "val": val, "test": test}


def split_group_response(rows: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, list[dict[str, Any]]]:
    groups = np.array([str(row.get("response_id") or row.get("pair_id")) for row in rows])
    indexes = np.arange(len(rows))
    splitter = GroupShuffleSplit(n_splits=1, test_size=args.test_size, random_state=args.seed)
    train_val_idx, test_idx = next(splitter.split(indexes, groups=groups))
    train_val = [rows[i] for i in train_val_idx]
    test = [rows[i] for i in test_idx]

    train_val_groups = np.array([str(row.get("response_id") or row.get("pair_id")) for row in train_val])
    train_val_indexes = np.arange(len(train_val))
    val_relative = args.val_size / max(1e-9, 1.0 - args.test_size)
    splitter = GroupShuffleSplit(n_splits=1, test_size=val_relative, random_state=args.seed + 1)
    train_idx, val_idx = next(splitter.split(train_val_indexes, groups=train_val_groups))
    train = [train_val[i] for i in train_idx]
    val = [train_val[i] for i in val_idx]
    return {"train": train, "val": val, "test": test}


def split_rows(rows: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, list[dict[str, Any]]]:
    if args.split_mode == "random":
        return split_random(rows, args)
    if args.split_mode == "group_response":
        return split_group_response(rows, args)
    raise ValueError(f"Unsupported split_mode: {args.split_mode}")


def rows_to_xy(rows: list[dict[str, Any]]) -> tuple[list[str], list[int]]:
    return [row["feature_text"] for row in rows], [int(row["target"]) for row in rows]


def make_loader(
    texts: list[str],
    labels: list[int] | None,
    tokenizer: Any,
    args: argparse.Namespace,
    shuffle: bool,
) -> DataLoader:
    dataset = TextDataset(texts, labels, tokenizer, args.max_length)
    collator = DataCollatorWithPadding(tokenizer=tokenizer)
    return DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=shuffle,
        collate_fn=collator,
        num_workers=args.num_workers,
        pin_memory=torch.cuda.is_available(),
    )


def batch_to_device(batch: dict[str, Any], device: torch.device) -> dict[str, Any]:
    return {key: value.to(device) if hasattr(value, "to") else value for key, value in batch.items()}


def class_weights(labels: list[int], device: torch.device, mode: str) -> torch.Tensor | None:
    if mode == "none":
        return None
    counts = Counter(labels)
    if min(counts.values(), default=0) == 0:
        return None
    total = sum(counts.values())
    weights = [total / (2.0 * counts.get(0, 1)), total / (2.0 * counts.get(1, 1))]
    return torch.tensor(weights, dtype=torch.float32, device=device)


def amp_autocast(use_amp: bool) -> torch.amp.autocast:
    return torch.amp.autocast("cuda", enabled=use_amp)


def train_one_epoch(
    model: torch.nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    scheduler: Any,
    device: torch.device,
    weight: torch.Tensor | None,
    use_amp: bool,
) -> float:
    model.train()
    total_loss = 0.0
    total_rows = 0
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    for batch in loader:
        batch = batch_to_device(batch, device)
        labels = batch.pop("labels")
        optimizer.zero_grad(set_to_none=True)
        with amp_autocast(use_amp):
            logits = model(**batch).logits
            loss = F.cross_entropy(logits, labels, weight=weight)
        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(optimizer)
        scaler.update()
        scheduler.step()
        rows = int(labels.shape[0])
        total_loss += float(loss.detach().cpu()) * rows
        total_rows += rows
    return total_loss / max(total_rows, 1)


@torch.no_grad()
def evaluate_loader(
    model: torch.nn.Module,
    loader: DataLoader,
    device: torch.device,
    use_amp: bool,
) -> tuple[np.ndarray, np.ndarray, float]:
    model.eval()
    labels_out: list[int] = []
    scores_out: list[float] = []
    total_loss = 0.0
    total_rows = 0
    for batch in loader:
        batch = batch_to_device(batch, device)
        labels = batch.pop("labels")
        with amp_autocast(use_amp):
            logits = model(**batch).logits
            loss = F.cross_entropy(logits, labels)
        probs = torch.softmax(logits, dim=-1)[:, 1]
        labels_out.extend(labels.detach().cpu().numpy().astype(int).tolist())
        scores_out.extend(probs.detach().cpu().numpy().astype(float).tolist())
        rows = int(labels.shape[0])
        total_loss += float(loss.detach().cpu()) * rows
        total_rows += rows
    return np.array(labels_out, dtype=int), np.array(scores_out, dtype=float), total_loss / max(total_rows, 1)


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


def binary_metrics(y_true: np.ndarray, scores: np.ndarray, threshold: float, split: str, loss: float) -> dict[str, Any]:
    preds = (scores >= threshold).astype(int)
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, preds, labels=[0, 1], zero_division=0
    )
    return {
        "split": split,
        "rows": int(len(y_true)),
        "loss": float(loss),
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


def prediction_rows(rows: list[dict[str, Any]], scores: np.ndarray, threshold: float, split: str) -> list[dict[str, Any]]:
    out = []
    for row, score in zip(rows, scores):
        out.append(
            {
                "split": split,
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
                "claim_text": row.get("claim_text"),
                "response_body": row.get("response_body"),
            }
        )
    return out


def run(args: argparse.Namespace) -> None:
    start = time.time()
    set_seed(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir = args.output_dir / "metrics"
    tables_dir = args.output_dir / "tables"
    predictions_dir = args.output_dir / "predictions"
    checkpoint_dir = args.output_dir / "checkpoints" / "best_model"
    for path in [metrics_dir, tables_dir, predictions_dir, checkpoint_dir]:
        path.mkdir(parents=True, exist_ok=True)

    rows = load_rows(args)
    splits = split_rows(rows, args)
    train_texts, train_y = rows_to_xy(splits["train"])
    val_texts, val_y = rows_to_xy(splits["val"])
    test_texts, test_y = rows_to_xy(splits["test"])

    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    use_amp = bool(args.fp16 and device.type == "cuda")
    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model_name,
        num_labels=2,
        ignore_mismatched_sizes=args.ignore_mismatched_sizes,
    )
    model.to(device)

    train_loader = make_loader(train_texts, train_y, tokenizer, args, shuffle=True)
    val_loader = make_loader(val_texts, val_y, tokenizer, args, shuffle=False)
    test_loader = make_loader(test_texts, test_y, tokenizer, args, shuffle=False)

    weight = class_weights(train_y, device, args.class_weight)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    total_steps = max(1, len(train_loader) * args.epochs)
    warmup_steps = int(total_steps * args.warmup_ratio)
    scheduler = get_linear_schedule_with_warmup(optimizer, warmup_steps, total_steps)

    history = []
    best_state: dict[str, Any] | None = None
    best_score = -1.0
    best_epoch = 0
    for epoch in range(1, args.epochs + 1):
        train_loss = train_one_epoch(model, train_loader, optimizer, scheduler, device, weight, use_amp)
        val_true, val_scores, val_loss = evaluate_loader(model, val_loader, device, use_amp)
        val_ap = safe_metric(average_precision_score, val_true, val_scores)
        val_auc = safe_metric(roc_auc_score, val_true, val_scores)
        row = {
            "epoch": epoch,
            "train_loss": train_loss,
            "val_loss": val_loss,
            "val_average_precision": val_ap,
            "val_roc_auc": val_auc,
        }
        history.append(row)
        print(json.dumps(row, ensure_ascii=False, sort_keys=True))
        score = val_ap if val_ap is not None else -1.0
        if score > best_score:
            best_score = score
            best_epoch = epoch
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)
    model.save_pretrained(checkpoint_dir)
    tokenizer.save_pretrained(checkpoint_dir)

    val_true, val_scores, val_loss = evaluate_loader(model, val_loader, device, use_amp)
    threshold_info = select_threshold(val_true, val_scores)
    threshold = float(threshold_info["threshold"])
    test_true, test_scores, test_loss = evaluate_loader(model, test_loader, device, use_amp)

    val_metrics = binary_metrics(val_true, val_scores, threshold, "val", val_loss)
    test_metrics = binary_metrics(test_true, test_scores, threshold, "test", test_loss)
    write_json(metrics_dir / "val_metrics.json", val_metrics)
    write_json(metrics_dir / "test_metrics.json", test_metrics)
    write_json(metrics_dir / "threshold_selection.json", threshold_info)
    write_csv(
        tables_dir / "training_history.csv",
        history,
        ["epoch", "train_loss", "val_loss", "val_average_precision", "val_roc_auc"],
    )

    all_prediction_rows = []
    all_prediction_rows.extend(prediction_rows(splits["val"], val_scores, threshold, "val"))
    all_prediction_rows.extend(prediction_rows(splits["test"], test_scores, threshold, "test"))
    write_csv(
        predictions_dir / "val_test_pair_predictions.csv",
        all_prediction_rows,
        [
            "split",
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

    split_summary = {
        split: {
            "rows": len(split_rows_),
            "class_counts": dict(Counter(int(row["target"]) for row in split_rows_)),
            "unique_response_ids": len({str(row.get("response_id")) for row in split_rows_}),
            "unique_submission_ids": len({str(row.get("submission_id")) for row in split_rows_}),
        }
        for split, split_rows_ in splits.items()
    }
    summary = {
        "run_status": "pair_relation_transformer_classifier",
        "annotations": str(args.annotations),
        "output_dir": str(args.output_dir),
        "model_name": args.model_name,
        "feature_mode": args.feature_mode,
        "label_field": args.label_field,
        "split_mode": args.split_mode,
        "split_summary": split_summary,
        "annotation_rows_binary": len(rows),
        "class_counts": dict(Counter(int(row["target"]) for row in rows)),
        "class_weight": args.class_weight,
        "best_epoch": best_epoch,
        "selection_metric": "val_average_precision",
        "selection_metric_value": best_score,
        "threshold": threshold,
        "threshold_selection": threshold_info,
        "val_average_precision": val_metrics["average_precision"],
        "val_roc_auc": val_metrics["roc_auc"],
        "val_positive_f1": val_metrics["per_class"]["1"]["f1"],
        "test_average_precision": test_metrics["average_precision"],
        "test_roc_auc": test_metrics["roc_auc"],
        "test_positive_f1": test_metrics["per_class"]["1"]["f1"],
        "test_positive_precision": test_metrics["per_class"]["1"]["precision"],
        "test_positive_recall": test_metrics["per_class"]["1"]["recall"],
        "learning_rate": args.learning_rate,
        "weight_decay": args.weight_decay,
        "warmup_ratio": args.warmup_ratio,
        "epochs_requested": args.epochs,
        "max_length": args.max_length,
        "batch_size": args.batch_size,
        "fp16": use_amp,
        "device": str(device),
        "started_utc": datetime.fromtimestamp(start, timezone.utc).isoformat(),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": time.time() - start,
    }
    write_json(metrics_dir / "run_summary.json", summary)
    (args.output_dir / "run.log").write_text(
        "\n".join(
            [
                "pair relation transformer classifier",
                f"started_utc={summary['started_utc']}",
                f"finished_utc={summary['finished_utc']}",
                f"annotations={args.annotations}",
                f"model_name={args.model_name}",
                f"feature_mode={args.feature_mode}",
                f"split_mode={args.split_mode}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train a claim-response relation classifier.")
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-name", default="microsoft/deberta-v3-base")
    parser.add_argument(
        "--feature-mode",
        choices=["claim_response", "title_claim_response", "metadata_title_claim_response"],
        default="title_claim_response",
    )
    parser.add_argument("--label-field", default="manual_pair_label")
    parser.add_argument("--split-mode", choices=["group_response", "random"], default="group_response")
    parser.add_argument("--test-size", type=float, default=0.15)
    parser.add_argument("--val-size", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=20260627)
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--warmup-ratio", type=float, default=0.06)
    parser.add_argument("--class-weight", choices=["balanced", "none"], default="balanced")
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--ignore-mismatched-sizes", action="store_true")
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
