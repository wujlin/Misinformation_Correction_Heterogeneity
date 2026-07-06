#!/usr/bin/env python3
"""Fine-tune a transformer classifier for public-correction detection."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
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
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    get_linear_schedule_with_warmup,
)

from train_correction_classifier import (
    aggregate_groups,
    aggregate_threads,
    boolish,
    compact_text,
    community_group,
    normalize_author,
    normalize_token,
    write_csv,
    write_json,
)


class TextDataset(Dataset):
    def __init__(
        self,
        texts: list[str],
        labels: list[int] | None,
        tokenizer: Any,
        max_length: int,
    ) -> None:
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        item = self.tokenizer(
            self.texts[idx],
            truncation=True,
            max_length=self.max_length,
        )
        if self.labels is not None:
            item["labels"] = int(self.labels[idx])
        return item


class TransformerPredictionWrapper:
    def __init__(
        self,
        model: torch.nn.Module,
        tokenizer: Any,
        device: torch.device,
        max_length: int,
        batch_size: int,
        num_workers: int,
        use_amp: bool,
    ) -> None:
        self.model = model
        self.tokenizer = tokenizer
        self.device = device
        self.max_length = max_length
        self.batch_size = batch_size
        self.num_workers = num_workers
        self.use_amp = use_amp

    def predict_proba(self, texts: list[str]) -> np.ndarray:
        scores = predict_scores(
            self.model,
            self.tokenizer,
            texts,
            self.device,
            self.max_length,
            self.batch_size,
            self.num_workers,
            self.use_amp,
        )
        return np.column_stack([1.0 - scores, scores])


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def safe_metric(fn: Any, y_true: np.ndarray, y_score: np.ndarray) -> float | None:
    try:
        return float(fn(y_true, y_score))
    except ValueError:
        return None


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def feature_text(row: dict[str, Any], feature_mode: str) -> str:
    subreddit = normalize_token(row.get("subreddit"))
    group = normalize_token(row.get("community_group_proxy")) or community_group(subreddit)
    candidate = int(boolish(row.get("candidate_correction")))
    title = compact_text(row.get("submission_title"))
    parent = compact_text(row.get("parent_body"))
    body = compact_text(row.get("body"))
    if feature_mode == "text_only":
        return f"TITLE={title} COMMENT={body}"
    if feature_mode == "text_candidate":
        return f"CANDIDATE={candidate} TITLE={title} COMMENT={body}"
    if feature_mode == "metadata_full":
        return f"SUBREDDIT={subreddit} GROUP={group} CANDIDATE={candidate} TITLE={title} COMMENT={body}"
    if feature_mode == "text_parent":
        return f"TITLE={title} COMMENT={body} PARENT={parent}"
    if feature_mode == "text_parent_candidate":
        return f"CANDIDATE={candidate} TITLE={title} COMMENT={body} PARENT={parent}"
    raise ValueError(f"Unsupported feature_mode: {feature_mode}")


def build_comment_lookup(path: Path) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in iter_jsonl(path):
        comment_id = normalize_token(row.get("comment_id"))
        if not comment_id:
            continue
        lookup[comment_id] = {
            "body": row.get("body", ""),
            "parent_id": normalize_token(row.get("parent_id")),
            "submission_title": row.get("submission_title", ""),
        }
    return lookup


def read_transformer_annotation_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    comment_lookup = build_comment_lookup(args.full_comments)
    out = []
    for row in read_csv(args.annotations):
        label = str(row.get("llm_label", "")).strip()
        if label not in {"0", "1"}:
            continue
        parent_id = normalize_token(row.get("parent_id"))
        parent_body = comment_lookup.get(parent_id, {}).get("body", "")
        row["target"] = int(label)
        row["parent_body"] = parent_body
        row["feature_text"] = feature_text(row, args.feature_mode)
        out.append(row)
    return out


def load_full_comments_with_context(path: Path, feature_mode: str) -> list[dict[str, Any]]:
    rows = iter_jsonl(path)
    body_lookup = {normalize_token(row.get("comment_id")): row.get("body", "") for row in rows}
    out = []
    for row in rows:
        row["subreddit"] = normalize_token(row.get("subreddit"))
        row["author_clean"] = normalize_author(row.get("author"))
        row["community_group_proxy"] = community_group(row.get("subreddit"))
        row["parent_body"] = body_lookup.get(normalize_token(row.get("parent_id")), "")
        row["feature_text"] = feature_text(row, feature_mode)
        out.append(row)
    return out


def count_rows_with_parent_context(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows if compact_text(row.get("parent_body")))


def split_rows(rows: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, list[dict[str, Any]]]:
    y = [row["target"] for row in rows]
    train_val, test = train_test_split(
        rows,
        test_size=args.test_size,
        stratify=y,
        random_state=args.seed,
    )
    y_train_val = [row["target"] for row in train_val]
    val_relative = args.val_size / max(1e-9, 1.0 - args.test_size)
    train, val = train_test_split(
        train_val,
        test_size=val_relative,
        stratify=y_train_val,
        random_state=args.seed,
    )
    return {"train": train, "val": val, "test": test}


def rows_to_xy(rows: list[dict[str, Any]]) -> tuple[list[str], list[int]]:
    return [row["feature_text"] for row in rows], [int(row["target"]) for row in rows]


def class_weights(labels: list[int], device: torch.device) -> torch.Tensor | None:
    counts = Counter(labels)
    if not counts or min(counts.values()) == 0:
        return None
    total = sum(counts.values())
    weights = [total / (2.0 * counts.get(0, 1)), total / (2.0 * counts.get(1, 1))]
    return torch.tensor(weights, dtype=torch.float32, device=device)


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


@torch.no_grad()
def predict_scores(
    model: torch.nn.Module,
    tokenizer: Any,
    texts: list[str],
    device: torch.device,
    max_length: int,
    batch_size: int,
    num_workers: int,
    use_amp: bool,
) -> np.ndarray:
    model.eval()
    dataset = TextDataset(texts, None, tokenizer, max_length)
    collator = DataCollatorWithPadding(tokenizer=tokenizer)
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        collate_fn=collator,
        num_workers=num_workers,
        pin_memory=torch.cuda.is_available(),
    )
    scores: list[float] = []
    for batch in loader:
        batch = batch_to_device(batch, device)
        with amp_autocast(use_amp):
            logits = model(**batch).logits
        probs = torch.softmax(logits, dim=-1)[:, 1]
        scores.extend(probs.detach().cpu().numpy().astype(float).tolist())
    return np.array(scores, dtype=float)


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


def binary_metrics(y_true: np.ndarray, scores: np.ndarray, threshold: float, split: str) -> dict[str, Any]:
    preds = (scores >= threshold).astype(int)
    report = classification_report(y_true, preds, output_dict=True, zero_division=0)
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, preds, labels=[0, 1], zero_division=0
    )
    return {
        "split": split,
        "rows": int(len(y_true)),
        "threshold": float(threshold),
        "class_counts": dict(Counter(map(int, y_true))),
        "predicted_positive": int(preds.sum()),
        "predicted_positive_rate": float(preds.mean()) if len(preds) else 0.0,
        "confusion_matrix_labels": [0, 1],
        "confusion_matrix": confusion_matrix(y_true, preds, labels=[0, 1]).tolist(),
        "classification_report": report,
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


def write_prediction_outputs(
    output_dir: Path,
    full_comments: list[dict[str, Any]],
    wrapper: TransformerPredictionWrapper,
    threshold: float,
) -> dict[str, Any]:
    tables_dir = output_dir / "tables"
    predictions_dir = output_dir / "predictions"
    scores = wrapper.predict_proba([row["feature_text"] for row in full_comments])[:, 1]
    predictions = []
    for row, score in zip(full_comments, scores):
        predictions.append(
            {
                "comment_id": row.get("comment_id"),
                "submission_id": row.get("submission_id"),
                "parent_id": row.get("parent_id"),
                "subreddit": row.get("subreddit"),
                "community_group_proxy": row.get("community_group_proxy"),
                "author": row.get("author"),
                "candidate_correction": int(row.get("candidate_correction") in {1, True, "1", "true", "True"}),
                "public_correction_score": float(score),
                "public_correction_pred": int(score >= threshold),
                "created_utc": row.get("created_utc"),
            }
        )

    thread_profiles = aggregate_threads(predictions)
    subreddit_profiles = aggregate_groups(predictions, "subreddit")
    community_profiles = aggregate_groups(predictions, "community_group_proxy")

    write_csv(
        predictions_dir / "full_comment_predictions.csv",
        predictions,
        [
            "comment_id",
            "submission_id",
            "parent_id",
            "subreddit",
            "community_group_proxy",
            "author",
            "candidate_correction",
            "public_correction_score",
            "public_correction_pred",
            "created_utc",
        ],
    )
    write_csv(
        tables_dir / "thread_profiles_predicted.csv",
        thread_profiles,
        [
            "submission_id",
            "subreddit",
            "community_group_proxy",
            "comments",
            "unique_authors",
            "candidate_corrections",
            "predicted_public_corrections",
            "predicted_correctors",
            "exposed_but_not_predicted_correctors",
            "predicted_comment_rate",
            "predicted_author_rate",
            "has_predicted_public_correction",
        ],
    )
    write_csv(
        tables_dir / "subreddit_profiles_predicted.csv",
        subreddit_profiles,
        [
            "subreddit",
            "threads",
            "comments",
            "unique_authors",
            "candidate_corrections",
            "predicted_public_corrections",
            "predicted_correctors",
            "candidate_comment_rate",
            "predicted_comment_rate",
            "predicted_author_rate",
        ],
    )
    write_csv(
        tables_dir / "community_group_profiles_predicted.csv",
        community_profiles,
        [
            "community_group_proxy",
            "threads",
            "comments",
            "unique_authors",
            "candidate_corrections",
            "predicted_public_corrections",
            "predicted_correctors",
            "candidate_comment_rate",
            "predicted_comment_rate",
            "predicted_author_rate",
        ],
    )
    return {
        "full_comment_rows": len(full_comments),
        "predicted_public_corrections": int(sum(row["public_correction_pred"] for row in predictions)),
        "candidate_corrections": int(sum(row["candidate_correction"] for row in predictions)),
        "threads_with_predicted_public_correction": int(
            sum(row["has_predicted_public_correction"] for row in thread_profiles)
        ),
        "threads": len(thread_profiles),
    }


def train(args: argparse.Namespace) -> dict[str, Any]:
    set_seed(args.seed)
    start = time.time()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir = args.output_dir / "metrics"
    tables_dir = args.output_dir / "tables"
    predictions_dir = args.output_dir / "predictions"
    checkpoints_dir = args.output_dir / "checkpoints"
    for directory in [metrics_dir, tables_dir, predictions_dir, checkpoints_dir]:
        directory.mkdir(exist_ok=True)

    annotation_rows = read_transformer_annotation_rows(args)
    splits = split_rows(annotation_rows, args)
    train_texts, train_labels = rows_to_xy(splits["train"])
    val_texts, val_labels = rows_to_xy(splits["val"])
    test_texts, test_labels = rows_to_xy(splits["test"])

    device = torch.device(args.device if args.device else ("cuda" if torch.cuda.is_available() else "cpu"))
    use_amp = bool(args.fp16 and device.type == "cuda")
    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    model = AutoModelForSequenceClassification.from_pretrained(args.model_name, num_labels=2)
    model.to(device)

    train_loader = make_loader(train_texts, train_labels, tokenizer, args, shuffle=True)
    val_loader = make_loader(val_texts, val_labels, tokenizer, args, shuffle=False)
    test_loader = make_loader(test_texts, test_labels, tokenizer, args, shuffle=False)

    weight = class_weights(train_labels, device) if args.class_weight == "balanced" else None
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    total_steps = max(1, len(train_loader) * args.epochs)
    warmup_steps = int(total_steps * args.warmup_ratio)
    scheduler = get_linear_schedule_with_warmup(optimizer, warmup_steps, total_steps)

    best_metric = -math.inf
    best_epoch = 0
    stale_epochs = 0
    history = []
    best_dir = checkpoints_dir / "best_model"

    for epoch in range(1, args.epochs + 1):
        train_loss = train_one_epoch(model, train_loader, optimizer, scheduler, device, weight, use_amp)
        y_val, val_scores, val_loss = evaluate_loader(model, val_loader, device, use_amp)
        threshold_info = select_threshold(y_val, val_scores)
        val_metrics = binary_metrics(y_val, val_scores, threshold_info["threshold"], "val")
        epoch_metric = val_metrics[args.selection_metric]
        if epoch_metric is None:
            epoch_metric = -math.inf
        row = {
            "epoch": epoch,
            "train_loss": train_loss,
            "val_loss": val_loss,
            "val_threshold": threshold_info["threshold"],
            "val_positive_f1": val_metrics["classification_report"]["1"]["f1-score"],
            "val_positive_precision": val_metrics["classification_report"]["1"]["precision"],
            "val_positive_recall": val_metrics["classification_report"]["1"]["recall"],
            "val_roc_auc": val_metrics["roc_auc"],
            "val_average_precision": val_metrics["average_precision"],
        }
        history.append(row)

        if float(epoch_metric) > best_metric:
            best_metric = float(epoch_metric)
            best_epoch = epoch
            stale_epochs = 0
            model.save_pretrained(best_dir)
            tokenizer.save_pretrained(best_dir)
        else:
            stale_epochs += 1
        if stale_epochs >= args.early_stop_patience:
            break

    tokenizer = AutoTokenizer.from_pretrained(best_dir)
    model = AutoModelForSequenceClassification.from_pretrained(best_dir)
    model.to(device)
    y_val, val_scores, val_loss = evaluate_loader(model, val_loader, device, use_amp)
    threshold_info = select_threshold(y_val, val_scores)
    final_threshold = threshold_info["threshold"] if args.use_best_val_threshold else args.threshold
    val_metrics = binary_metrics(y_val, val_scores, final_threshold, "val")
    y_test, test_scores, test_loss = evaluate_loader(model, test_loader, device, use_amp)
    test_metrics = binary_metrics(y_test, test_scores, final_threshold, "test")

    full_prediction_summary: dict[str, Any] = {}
    if not args.skip_full_prediction:
        full_comments = load_full_comments_with_context(args.full_comments, args.feature_mode)
        wrapper = TransformerPredictionWrapper(
            model=model,
            tokenizer=tokenizer,
            device=device,
            max_length=args.max_length,
            batch_size=args.predict_batch_size,
            num_workers=args.num_workers,
            use_amp=use_amp,
        )
        full_prediction_summary = write_prediction_outputs(args.output_dir, full_comments, wrapper, final_threshold)

    write_csv(
        tables_dir / "training_history.csv",
        history,
        [
            "epoch",
            "train_loss",
            "val_loss",
            "val_threshold",
            "val_positive_f1",
            "val_positive_precision",
            "val_positive_recall",
            "val_roc_auc",
            "val_average_precision",
        ],
    )
    write_json(metrics_dir / "val_metrics.json", val_metrics)
    write_json(metrics_dir / "test_metrics.json", test_metrics)
    write_json(metrics_dir / "threshold_selection.json", threshold_info)

    summary = {
        "run_status": "transformer_correction_classifier",
        "model_name": args.model_name,
        "annotations": str(args.annotations),
        "full_comments": str(args.full_comments),
        "output_dir": str(args.output_dir),
        "annotation_rows": len(annotation_rows),
        "annotation_class_counts": dict(Counter(row["target"] for row in annotation_rows)),
        "annotation_rows_with_parent_context": count_rows_with_parent_context(annotation_rows),
        "split_rows": {key: len(value) for key, value in splits.items()},
        "feature_mode": args.feature_mode,
        "max_length": args.max_length,
        "batch_size": args.batch_size,
        "predict_batch_size": args.predict_batch_size,
        "epochs_requested": args.epochs,
        "epochs_completed": len(history),
        "best_epoch": best_epoch,
        "selection_metric": args.selection_metric,
        "selection_metric_value": best_metric,
        "threshold": final_threshold,
        "use_best_val_threshold": args.use_best_val_threshold,
        "threshold_selection": threshold_info,
        "class_weight": args.class_weight,
        "learning_rate": args.learning_rate,
        "weight_decay": args.weight_decay,
        "warmup_ratio": args.warmup_ratio,
        "device": str(device),
        "fp16": use_amp,
        "val_loss": val_loss,
        "test_loss": test_loss,
        "val_positive_f1": val_metrics["classification_report"]["1"]["f1-score"],
        "val_positive_precision": val_metrics["classification_report"]["1"]["precision"],
        "val_positive_recall": val_metrics["classification_report"]["1"]["recall"],
        "val_roc_auc": val_metrics["roc_auc"],
        "val_average_precision": val_metrics["average_precision"],
        "test_positive_f1": test_metrics["classification_report"]["1"]["f1-score"],
        "test_positive_precision": test_metrics["classification_report"]["1"]["precision"],
        "test_positive_recall": test_metrics["classification_report"]["1"]["recall"],
        "test_roc_auc": test_metrics["roc_auc"],
        "test_average_precision": test_metrics["average_precision"],
        **full_prediction_summary,
        "started_utc": datetime.fromtimestamp(start, timezone.utc).isoformat(),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": time.time() - start,
    }
    write_json(metrics_dir / "run_summary.json", summary)
    (args.output_dir / "run.log").write_text(
        "\n".join(
            [
                "transformer correction classifier run",
                f"generated_utc={summary['finished_utc']}",
                f"command={' '.join(sys.argv)}",
                f"model_name={args.model_name}",
                f"threshold={summary['threshold']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fine-tune a transformer public-correction classifier.")
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--full-comments", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-name", default="distilroberta-base")
    parser.add_argument(
        "--feature-mode",
        choices=["text_only", "text_candidate", "metadata_full", "text_parent", "text_parent_candidate"],
        default="text_only",
    )
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--use-best-val-threshold", action="store_true")
    parser.add_argument("--test-size", type=float, default=0.15)
    parser.add_argument("--val-size", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=20260625)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--early-stop-patience", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--predict-batch-size", type=int, default=128)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--warmup-ratio", type=float, default=0.06)
    parser.add_argument("--class-weight", choices=["balanced", "none"], default="balanced")
    parser.add_argument("--selection-metric", choices=["average_precision", "roc_auc"], default="average_precision")
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--device", default="")
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument("--skip-full-prediction", action="store_true")
    return parser


def main() -> None:
    train(build_parser().parse_args())


if __name__ == "__main__":
    main()
