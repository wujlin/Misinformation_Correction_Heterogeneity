#!/usr/bin/env python3
"""Fine-tune a multi-class relation-type classifier for claim-response pairs."""

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
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    precision_recall_curve,
    precision_recall_fscore_support,
    roc_auc_score,
)
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer, DataCollatorWithPadding
from transformers import get_linear_schedule_with_warmup

from train_pair_relation_classifier import feature_text, split_rows


RELATION_TYPES = [
    "direct_rebuttal",
    "evidence_or_source_correction",
    "definition_or_context_correction",
    "questioning_or_source_request",
    "sarcastic_or_quote_edit_correction",
    "noncorrective_factual_statement",
    "misinformation_support_or_elaboration",
    "general_opinion_or_reaction",
]

CORRECTIVE_TYPES = {
    "direct_rebuttal",
    "evidence_or_source_correction",
    "definition_or_context_correction",
    "questioning_or_source_request",
    "sarcastic_or_quote_edit_correction",
}


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


def batch_to_device(batch: dict[str, Any], device: torch.device) -> dict[str, Any]:
    return {key: value.to(device) if hasattr(value, "to") else value for key, value in batch.items()}


def relation_type_from_row(row: dict[str, Any], relation_type_field: str) -> str:
    relation_type = str(row.get(relation_type_field, "")).strip().lower()
    return relation_type


def load_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    label_to_id = {label: idx for idx, label in enumerate(RELATION_TYPES)}
    rows = []
    for row in read_csv(args.annotations):
        relation_type = relation_type_from_row(row, args.relation_type_field)
        if relation_type not in label_to_id:
            continue
        out = dict(row)
        out["relation_type_target"] = label_to_id[relation_type]
        out["target"] = label_to_id[relation_type]
        out["binary_target"] = int(relation_type in CORRECTIVE_TYPES)
        out["feature_text"] = feature_text(out, args.feature_mode)
        rows.append(out)
    return rows


def rows_to_xy(rows: list[dict[str, Any]]) -> tuple[list[str], list[int]]:
    return [row["feature_text"] for row in rows], [int(row["relation_type_target"]) for row in rows]


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


def class_weights(labels: list[int], device: torch.device, mode: str) -> torch.Tensor | None:
    if mode == "none":
        return None
    counts = Counter(labels)
    total = sum(counts.values())
    weights = [total / (len(RELATION_TYPES) * max(1, counts.get(i, 0))) for i in range(len(RELATION_TYPES))]
    return torch.tensor(weights, dtype=torch.float32, device=device)


def correction_scores_from_type_probs(probs: np.ndarray) -> np.ndarray:
    corrective_ids = [RELATION_TYPES.index(label) for label in CORRECTIVE_TYPES]
    return probs[:, corrective_ids].sum(axis=1)


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


def binary_metrics(y_true: np.ndarray, scores: np.ndarray, threshold: float) -> dict[str, Any]:
    pred = (scores >= threshold).astype(int)
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, pred, labels=[0, 1], zero_division=0
    )
    return {
        "rows": int(len(y_true)),
        "class_counts": dict(Counter(map(int, y_true))),
        "predicted_positive": int(pred.sum()),
        "roc_auc": float(roc_auc_score(y_true, scores)) if len(set(y_true.tolist())) > 1 else None,
        "average_precision": float(average_precision_score(y_true, scores)) if len(set(y_true.tolist())) > 1 else None,
        "confusion_matrix": confusion_matrix(y_true, pred, labels=[0, 1]).tolist(),
        "per_class": {
            str(label): {
                "precision": float(precision[i]),
                "recall": float(recall[i]),
                "f1": float(f1[i]),
                "support": int(support[i]),
            }
            for i, label in enumerate([0, 1])
        },
    }


def type_metrics(y_true: np.ndarray, pred: np.ndarray) -> dict[str, Any]:
    return {
        "accuracy": float(accuracy_score(y_true, pred)),
        "class_counts": {RELATION_TYPES[int(k)]: int(v) for k, v in Counter(map(int, y_true)).items()},
        "predicted_counts": {RELATION_TYPES[int(k)]: int(v) for k, v in Counter(map(int, pred)).items()},
    }


@torch.no_grad()
def predict_probs(model: torch.nn.Module, loader: DataLoader, device: torch.device, use_amp: bool) -> tuple[np.ndarray, np.ndarray, float]:
    model.eval()
    labels_out: list[int] = []
    probs_out: list[list[float]] = []
    total_loss = 0.0
    total_rows = 0
    for batch in loader:
        batch = batch_to_device(batch, device)
        labels = batch.pop("labels")
        with torch.amp.autocast("cuda", enabled=use_amp):
            logits = model(**batch).logits
            loss = F.cross_entropy(logits, labels)
        probs = torch.softmax(logits, dim=-1)
        labels_out.extend(labels.detach().cpu().numpy().astype(int).tolist())
        probs_out.extend(probs.detach().cpu().numpy().astype(float).tolist())
        rows = int(labels.shape[0])
        total_loss += float(loss.detach().cpu()) * rows
        total_rows += rows
    return np.array(labels_out, dtype=int), np.array(probs_out, dtype=float), total_loss / max(total_rows, 1)


def train_epoch(
    model: torch.nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    scheduler: Any,
    device: torch.device,
    weight: torch.Tensor | None,
    use_amp: bool,
) -> float:
    model.train()
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    total_loss = 0.0
    total_rows = 0
    for batch in loader:
        batch = batch_to_device(batch, device)
        labels = batch.pop("labels")
        optimizer.zero_grad(set_to_none=True)
        with torch.amp.autocast("cuda", enabled=use_amp):
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


def prediction_rows(rows: list[dict[str, Any]], probs: np.ndarray, threshold: float, split: str) -> list[dict[str, Any]]:
    scores = correction_scores_from_type_probs(probs)
    pred_types = probs.argmax(axis=1)
    out = []
    for row, score, pred_type_id, prob_vec in zip(rows, scores, pred_types, probs):
        out_row = {
            "split": split,
            "annotation_id": row.get("annotation_id"),
            "pair_id": row.get("pair_id"),
            "claim_id": row.get("claim_id"),
            "response_id": row.get("response_id"),
            "pair_source": row.get("pair_source"),
            "sample_component": row.get("sample_component"),
            "subreddit": row.get("subreddit"),
            "binary_target": int(row.get("binary_target")),
            "relation_type_target": RELATION_TYPES[int(row.get("relation_type_target"))],
            "pred_relation_type": RELATION_TYPES[int(pred_type_id)],
            "pair_relation_score": float(score),
            "pair_relation_pred": int(float(score) >= threshold),
        }
        for label, value in zip(RELATION_TYPES, prob_vec):
            out_row[f"prob_{label}"] = float(value)
        out.append(out_row)
    return out


def evaluate_external(args: argparse.Namespace, model: torch.nn.Module, tokenizer: Any, threshold: float, device: torch.device, use_amp: bool) -> dict[str, Any] | None:
    if not args.external_annotations:
        return None
    label_to_id = {label: idx for idx, label in enumerate(RELATION_TYPES)}
    rows = []
    for row in read_csv(args.external_annotations):
        relation_type = relation_type_from_row(row, args.relation_type_field)
        if relation_type not in label_to_id:
            continue
        out = dict(row)
        out["relation_type_target"] = label_to_id[relation_type]
        out["binary_target"] = int(relation_type in CORRECTIVE_TYPES)
        out["feature_text"] = feature_text(out, args.feature_mode)
        rows.append(out)
    texts = [row["feature_text"] for row in rows]
    labels = [int(row["relation_type_target"]) for row in rows]
    loader = make_loader(texts, labels, tokenizer, args, shuffle=False)
    y_type, probs, loss = predict_probs(model, loader, device, use_amp)
    y_binary = np.array([int(row["binary_target"]) for row in rows], dtype=int)
    scores = correction_scores_from_type_probs(probs)
    type_pred = probs.argmax(axis=1)
    metrics = {
        "rows": len(rows),
        "loss": loss,
        "binary": binary_metrics(y_binary, scores, threshold),
        "type": type_metrics(y_type, type_pred),
        "threshold": threshold,
    }
    write_json(args.output_dir / "metrics" / "external_metrics.json", metrics)
    fields = [
        "split",
        "annotation_id",
        "pair_id",
        "claim_id",
        "response_id",
        "pair_source",
        "sample_component",
        "subreddit",
        "binary_target",
        "relation_type_target",
        "pred_relation_type",
        "pair_relation_score",
        "pair_relation_pred",
    ] + [f"prob_{label}" for label in RELATION_TYPES]
    write_csv(args.output_dir / "predictions" / "external_pair_type_predictions.csv", prediction_rows(rows, probs, threshold, "external"), fields)
    return metrics


def run(args: argparse.Namespace) -> None:
    start = time.time()
    set_seed(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for subdir in ["metrics", "tables", "predictions", "checkpoints/best_model"]:
        (args.output_dir / subdir).mkdir(parents=True, exist_ok=True)

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
        num_labels=len(RELATION_TYPES),
        ignore_mismatched_sizes=args.ignore_mismatched_sizes,
    )
    model.to(device)

    train_loader = make_loader(train_texts, train_y, tokenizer, args, shuffle=True)
    val_loader = make_loader(val_texts, val_y, tokenizer, args, shuffle=False)
    test_loader = make_loader(test_texts, test_y, tokenizer, args, shuffle=False)
    weight = class_weights(train_y, device, args.class_weight)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    total_steps = max(1, len(train_loader) * args.epochs)
    scheduler = get_linear_schedule_with_warmup(optimizer, int(total_steps * args.warmup_ratio), total_steps)

    best_state: dict[str, Any] | None = None
    best_epoch = 0
    best_score = -1.0
    history = []
    for epoch in range(1, args.epochs + 1):
        train_loss = train_epoch(model, train_loader, optimizer, scheduler, device, weight, use_amp)
        val_type_true, val_probs, val_loss = predict_probs(model, val_loader, device, use_amp)
        val_binary_true = np.array([int(row["binary_target"]) for row in splits["val"]], dtype=int)
        val_scores = correction_scores_from_type_probs(val_probs)
        val_ap = float(average_precision_score(val_binary_true, val_scores))
        val_auc = float(roc_auc_score(val_binary_true, val_scores))
        val_type_acc = float(accuracy_score(val_type_true, val_probs.argmax(axis=1)))
        row = {
            "epoch": epoch,
            "train_loss": train_loss,
            "val_loss": val_loss,
            "val_binary_average_precision": val_ap,
            "val_binary_roc_auc": val_auc,
            "val_type_accuracy": val_type_acc,
        }
        history.append(row)
        print(json.dumps(row, ensure_ascii=False, sort_keys=True))
        if val_ap > best_score:
            best_score = val_ap
            best_epoch = epoch
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)
    checkpoint_dir = args.output_dir / "checkpoints" / "best_model"
    model.save_pretrained(checkpoint_dir)
    tokenizer.save_pretrained(checkpoint_dir)

    val_type_true, val_probs, val_loss = predict_probs(model, val_loader, device, use_amp)
    val_binary_true = np.array([int(row["binary_target"]) for row in splits["val"]], dtype=int)
    val_scores = correction_scores_from_type_probs(val_probs)
    threshold_info = select_threshold(val_binary_true, val_scores)
    threshold = float(threshold_info["threshold"])

    test_type_true, test_probs, test_loss = predict_probs(model, test_loader, device, use_amp)
    test_binary_true = np.array([int(row["binary_target"]) for row in splits["test"]], dtype=int)
    test_scores = correction_scores_from_type_probs(test_probs)

    val_metrics = {
        "loss": val_loss,
        "binary": binary_metrics(val_binary_true, val_scores, threshold),
        "type": type_metrics(val_type_true, val_probs.argmax(axis=1)),
    }
    test_metrics = {
        "loss": test_loss,
        "binary": binary_metrics(test_binary_true, test_scores, threshold),
        "type": type_metrics(test_type_true, test_probs.argmax(axis=1)),
    }
    write_json(args.output_dir / "metrics" / "val_metrics.json", val_metrics)
    write_json(args.output_dir / "metrics" / "test_metrics.json", test_metrics)
    write_json(args.output_dir / "metrics" / "threshold_selection.json", threshold_info)
    write_csv(
        args.output_dir / "tables" / "training_history.csv",
        history,
        ["epoch", "train_loss", "val_loss", "val_binary_average_precision", "val_binary_roc_auc", "val_type_accuracy"],
    )

    pred_fields = [
        "split",
        "annotation_id",
        "pair_id",
        "claim_id",
        "response_id",
        "pair_source",
        "sample_component",
        "subreddit",
        "binary_target",
        "relation_type_target",
        "pred_relation_type",
        "pair_relation_score",
        "pair_relation_pred",
    ] + [f"prob_{label}" for label in RELATION_TYPES]
    pred_rows = prediction_rows(splits["val"], val_probs, threshold, "val")
    pred_rows.extend(prediction_rows(splits["test"], test_probs, threshold, "test"))
    write_csv(args.output_dir / "predictions" / "val_test_pair_type_predictions.csv", pred_rows, pred_fields)

    external_metrics = evaluate_external(args, model, tokenizer, threshold, device, use_amp)

    summary = {
        "run_status": "pair_relation_type_transformer_classifier",
        "annotations": str(args.annotations),
        "external_annotations": str(args.external_annotations) if args.external_annotations else None,
        "output_dir": str(args.output_dir),
        "model_name": args.model_name,
        "feature_mode": args.feature_mode,
        "relation_types": RELATION_TYPES,
        "corrective_types": sorted(CORRECTIVE_TYPES),
        "annotation_rows": len(rows),
        "relation_type_counts": {RELATION_TYPES[int(k)]: int(v) for k, v in Counter(row["relation_type_target"] for row in rows).items()},
        "binary_class_counts": dict(Counter(row["binary_target"] for row in rows)),
        "class_weight": args.class_weight,
        "best_epoch": best_epoch,
        "selection_metric": "val_binary_average_precision",
        "selection_metric_value": best_score,
        "threshold": threshold,
        "threshold_selection": threshold_info,
        "val_binary_average_precision": val_metrics["binary"]["average_precision"],
        "val_binary_roc_auc": val_metrics["binary"]["roc_auc"],
        "val_type_accuracy": val_metrics["type"]["accuracy"],
        "test_binary_average_precision": test_metrics["binary"]["average_precision"],
        "test_binary_roc_auc": test_metrics["binary"]["roc_auc"],
        "test_type_accuracy": test_metrics["type"]["accuracy"],
        "external_binary_average_precision": external_metrics["binary"]["average_precision"] if external_metrics else None,
        "external_binary_roc_auc": external_metrics["binary"]["roc_auc"] if external_metrics else None,
        "external_type_accuracy": external_metrics["type"]["accuracy"] if external_metrics else None,
        "epochs_requested": args.epochs,
        "batch_size": args.batch_size,
        "max_length": args.max_length,
        "learning_rate": args.learning_rate,
        "weight_decay": args.weight_decay,
        "warmup_ratio": args.warmup_ratio,
        "fp16": use_amp,
        "device": str(device),
        "started_utc": datetime.fromtimestamp(start, timezone.utc).isoformat(),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": time.time() - start,
    }
    write_json(args.output_dir / "metrics" / "run_summary.json", summary)
    (args.output_dir / "run.log").write_text(
        "\n".join(
            [
                "pair relation type transformer classifier",
                f"started_utc={summary['started_utc']}",
                f"finished_utc={summary['finished_utc']}",
                f"annotations={args.annotations}",
                f"external_annotations={args.external_annotations}",
                f"model_name={args.model_name}",
                f"feature_mode={args.feature_mode}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train a relation-type classifier for pair-level correction detection.")
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--external-annotations", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-name", default="microsoft/deberta-v3-base")
    parser.add_argument(
        "--feature-mode",
        choices=["claim_response", "title_claim_response", "metadata_title_claim_response"],
        default="claim_response",
    )
    parser.add_argument("--relation-type-field", default="manual_pair_relation_type")
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
    parser.add_argument("--class-weight", choices=["balanced", "none"], default="none")
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--ignore-mismatched-sizes", action="store_true")
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
