#!/usr/bin/env python3
"""Train a lightweight public-correction classifier from Qwen-assisted labels.

The target label is the Qwen-assisted annotation from
`llm_annotate_public_correction.py`. It is not human ground truth. The resulting
classifier is an exploratory tool for scaling the pilot labels to the full
comment dataset.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline


COMMUNITY_GROUPS = {
    "skeptical_or_anti_institutional": {
        "antivaxxers",
        "conservative",
        "conspiracy",
        "conspiracy_commons",
        "conspiracytheories",
        "nonewnormal",
        "trueantivaccination",
    },
    "public_health_or_news": {
        "coronavirus",
        "covid19",
        "news",
    },
    "vaccine_experience_or_health": {
        "covidvaccinated",
        "covidvaccine",
        "vaccines",
    },
}

REMOVED_AUTHORS = {"", "[deleted]", "deleted", "automoderator"}


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normalize_token(value: Any) -> str:
    return str(value or "").strip().lower()


def normalize_author(value: Any) -> str | None:
    author = normalize_token(value)
    if author in REMOVED_AUTHORS:
        return None
    return author


def community_group(subreddit: Any) -> str:
    subreddit = normalize_token(subreddit)
    for group, subreddits in COMMUNITY_GROUPS.items():
        if subreddit in subreddits:
            return group
    return "other"


def compact_text(value: Any, limit: int = 5000) -> str:
    text = " ".join(str(value or "").split())
    if len(text) > limit:
        return text[:limit]
    return text


def feature_text(row: dict[str, Any], feature_mode: str) -> str:
    subreddit = normalize_token(row.get("subreddit"))
    candidate = int(boolish(row.get("candidate_correction")))
    group = community_group(subreddit)
    title = compact_text(row.get("submission_title"))
    body = compact_text(row.get("body"))
    if feature_mode == "text_only":
        return f"TITLE={title} COMMENT={body}"
    if feature_mode == "text_candidate":
        return f"CANDIDATE={candidate} TITLE={title} COMMENT={body}"
    return f"SUBREDDIT={subreddit} GROUP={group} CANDIDATE={candidate} TITLE={title} COMMENT={body}"


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def read_annotation_rows(path: Path, feature_mode: str) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for row in rows:
        label = str(row.get("llm_label", "")).strip()
        if label not in {"0", "1"}:
            continue
        row["target"] = int(label)
        row["feature_text"] = feature_text(row, feature_mode)
        out.append(row)
    return out


def build_model(max_features: int, class_weight: str | None) -> Pipeline:
    return Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    max_features=max_features,
                    ngram_range=(1, 2),
                    min_df=1,
                    strip_accents="unicode",
                    sublinear_tf=True,
                    lowercase=True,
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=2000,
                    solver="liblinear",
                    class_weight=class_weight,
                    random_state=0,
                ),
            ),
        ]
    )


def evaluate_holdout(rows: list[dict[str, Any]], args: argparse.Namespace) -> tuple[dict[str, Any], Pipeline]:
    x = [row["feature_text"] for row in rows]
    y = np.array([row["target"] for row in rows])
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=args.test_size,
        stratify=y,
        random_state=args.seed,
    )
    model = build_model(args.max_features, args.class_weight)
    model.fit(x_train, y_train)
    scores = model.predict_proba(x_test)[:, 1]
    preds = (scores >= args.threshold).astype(int)
    report = classification_report(y_test, preds, output_dict=True, zero_division=0)
    matrix = confusion_matrix(y_test, preds, labels=[0, 1]).tolist()
    precision, recall, f1, support = precision_recall_fscore_support(
        y_test, preds, labels=[0, 1], zero_division=0
    )
    metrics = {
        "split": "holdout",
        "train_rows": len(x_train),
        "test_rows": len(x_test),
        "threshold": args.threshold,
        "class_counts_train": dict(Counter(map(int, y_train))),
        "class_counts_test": dict(Counter(map(int, y_test))),
        "confusion_matrix_labels": [0, 1],
        "confusion_matrix": matrix,
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
        "roc_auc": safe_metric(roc_auc_score, y_test, scores),
        "average_precision": safe_metric(average_precision_score, y_test, scores),
    }
    return metrics, model


def evaluate_cross_validation(rows: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    x = np.array([row["feature_text"] for row in rows], dtype=object)
    y = np.array([row["target"] for row in rows])
    skf = StratifiedKFold(n_splits=args.cv_folds, shuffle=True, random_state=args.seed)
    fold_metrics = []
    all_scores = np.zeros(len(y), dtype=float)
    all_preds = np.zeros(len(y), dtype=int)

    for fold, (train_idx, test_idx) in enumerate(skf.split(x, y), 1):
        model = build_model(args.max_features, args.class_weight)
        model.fit(x[train_idx].tolist(), y[train_idx])
        scores = model.predict_proba(x[test_idx].tolist())[:, 1]
        preds = (scores >= args.threshold).astype(int)
        all_scores[test_idx] = scores
        all_preds[test_idx] = preds
        report = classification_report(y[test_idx], preds, output_dict=True, zero_division=0)
        fold_metrics.append(
            {
                "fold": fold,
                "rows": int(len(test_idx)),
                "positive_rate_true": float(y[test_idx].mean()),
                "positive_rate_pred": float(preds.mean()),
                "roc_auc": safe_metric(roc_auc_score, y[test_idx], scores),
                "average_precision": safe_metric(average_precision_score, y[test_idx], scores),
                "f1_positive": float(report["1"]["f1-score"]),
                "precision_positive": float(report["1"]["precision"]),
                "recall_positive": float(report["1"]["recall"]),
            }
        )

    report = classification_report(y, all_preds, output_dict=True, zero_division=0)
    return {
        "split": "stratified_cross_validation",
        "folds": args.cv_folds,
        "threshold": args.threshold,
        "rows": int(len(y)),
        "class_counts": dict(Counter(map(int, y))),
        "confusion_matrix_labels": [0, 1],
        "confusion_matrix": confusion_matrix(y, all_preds, labels=[0, 1]).tolist(),
        "classification_report": report,
        "roc_auc": safe_metric(roc_auc_score, y, all_scores),
        "average_precision": safe_metric(average_precision_score, y, all_scores),
        "fold_metrics": fold_metrics,
    }


def safe_metric(fn: Any, y_true: np.ndarray, y_score: np.ndarray) -> float | None:
    try:
        return float(fn(y_true, y_score))
    except ValueError:
        return None


def load_full_comments(path: Path, feature_mode: str) -> list[dict[str, Any]]:
    rows = []
    for row in iter_jsonl(path):
        row["subreddit"] = normalize_token(row.get("subreddit"))
        row["author_clean"] = normalize_author(row.get("author"))
        row["community_group_proxy"] = community_group(row.get("subreddit"))
        row["feature_text"] = feature_text(row, feature_mode)
        rows.append(row)
    return rows


def apply_model(model: Pipeline, rows: list[dict[str, Any]], threshold: float) -> list[dict[str, Any]]:
    scores = model.predict_proba([row["feature_text"] for row in rows])[:, 1]
    out = []
    for row, score in zip(rows, scores):
        pred = int(score >= threshold)
        out.append(
            {
                "comment_id": row.get("comment_id"),
                "submission_id": row.get("submission_id"),
                "parent_id": row.get("parent_id"),
                "subreddit": row.get("subreddit"),
                "community_group_proxy": row.get("community_group_proxy"),
                "author": row.get("author"),
                "candidate_correction": int(boolish(row.get("candidate_correction"))),
                "public_correction_score": float(score),
                "public_correction_pred": pred,
                "created_utc": row.get("created_utc"),
            }
        )
    return out


def aggregate_threads(predictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    authors_by_thread: dict[str, set[str]] = defaultdict(set)
    correctors_by_thread: dict[str, set[str]] = defaultdict(set)
    for row in predictions:
        submission_id = str(row.get("submission_id") or "")
        if not submission_id:
            continue
        if submission_id not in stats:
            stats[submission_id] = {
                "submission_id": submission_id,
                "subreddit": row.get("subreddit"),
                "community_group_proxy": row.get("community_group_proxy"),
                "comments": 0,
                "predicted_public_corrections": 0,
                "candidate_corrections": 0,
            }
        item = stats[submission_id]
        item["comments"] += 1
        item["predicted_public_corrections"] += int(row["public_correction_pred"])
        item["candidate_corrections"] += int(row["candidate_correction"])
        author = normalize_author(row.get("author"))
        if author:
            authors_by_thread[submission_id].add(author)
            if row["public_correction_pred"]:
                correctors_by_thread[submission_id].add(author)

    out = []
    for submission_id, item in stats.items():
        unique_authors = len(authors_by_thread[submission_id])
        predicted_correctors = len(correctors_by_thread[submission_id])
        item["unique_authors"] = unique_authors
        item["predicted_correctors"] = predicted_correctors
        item["exposed_but_not_predicted_correctors"] = max(unique_authors - predicted_correctors, 0)
        item["predicted_comment_rate"] = div(item["predicted_public_corrections"], item["comments"])
        item["predicted_author_rate"] = div(predicted_correctors, unique_authors)
        item["has_predicted_public_correction"] = int(item["predicted_public_corrections"] > 0)
        out.append(item)
    return sorted(out, key=lambda item: item["predicted_public_corrections"], reverse=True)


def aggregate_groups(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    authors: dict[str, set[str]] = defaultdict(set)
    threads: dict[str, set[str]] = defaultdict(set)
    correctors: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        value = str(row.get(key) or "unknown")
        if value not in grouped:
            grouped[value] = {
                key: value,
                "comments": 0,
                "predicted_public_corrections": 0,
                "candidate_corrections": 0,
            }
        item = grouped[value]
        item["comments"] += 1
        item["predicted_public_corrections"] += int(row.get("public_correction_pred") or 0)
        item["candidate_corrections"] += int(row.get("candidate_correction") or 0)
        submission_id = str(row.get("submission_id") or "")
        if submission_id:
            threads[value].add(submission_id)
        author = normalize_author(row.get("author"))
        if author:
            authors[value].add(author)
            if row.get("public_correction_pred"):
                correctors[value].add(author)

    out = []
    for value, item in grouped.items():
        item["threads"] = len(threads[value])
        item["unique_authors"] = len(authors[value])
        item["predicted_correctors"] = len(correctors[value])
        item["predicted_comment_rate"] = div(item["predicted_public_corrections"], item["comments"])
        item["candidate_comment_rate"] = div(item["candidate_corrections"], item["comments"])
        item["predicted_author_rate"] = div(item["predicted_correctors"], item["unique_authors"])
        out.append(item)
    return sorted(out, key=lambda item: item["predicted_comment_rate"], reverse=True)


def div(num: int | float, den: int | float) -> float:
    return float(num) / float(den) if den else 0.0


def top_features(model: Pipeline, n: int) -> dict[str, list[dict[str, Any]]]:
    vectorizer: TfidfVectorizer = model.named_steps["tfidf"]
    clf: LogisticRegression = model.named_steps["clf"]
    names = vectorizer.get_feature_names_out()
    coefs = clf.coef_[0]
    pos_idx = np.argsort(coefs)[-n:][::-1]
    neg_idx = np.argsort(coefs)[:n]
    return {
        "positive": [{"feature": str(names[i]), "coefficient": float(coefs[i])} for i in pos_idx],
        "negative": [{"feature": str(names[i]), "coefficient": float(coefs[i])} for i in neg_idx],
    }


def run(args: argparse.Namespace) -> None:
    start = time.time()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir = args.output_dir / "metrics"
    tables_dir = args.output_dir / "tables"
    predictions_dir = args.output_dir / "predictions"
    checkpoints_dir = args.output_dir / "checkpoints"
    for directory in [metrics_dir, tables_dir, predictions_dir, checkpoints_dir]:
        directory.mkdir(exist_ok=True)

    annotation_rows = read_annotation_rows(args.annotations, args.feature_mode)
    holdout_metrics, _ = evaluate_holdout(annotation_rows, args)
    cv_metrics = evaluate_cross_validation(annotation_rows, args)

    full_model = build_model(args.max_features, args.class_weight)
    full_model.fit([row["feature_text"] for row in annotation_rows], [row["target"] for row in annotation_rows])
    joblib.dump(full_model, checkpoints_dir / "correction_classifier.joblib")

    full_comments = load_full_comments(args.full_comments, args.feature_mode)
    predictions = apply_model(full_model, full_comments, args.threshold)
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
    write_json(metrics_dir / "holdout_metrics.json", holdout_metrics)
    write_json(metrics_dir / "cross_validation_metrics.json", cv_metrics)
    write_json(metrics_dir / "top_features.json", top_features(full_model, args.top_features))

    summary = {
        "run_status": "exploratory_qwen_assisted_classifier",
        "annotations": str(args.annotations),
        "full_comments": str(args.full_comments),
        "output_dir": str(args.output_dir),
        "annotation_rows": len(annotation_rows),
        "annotation_class_counts": dict(Counter(row["target"] for row in annotation_rows)),
        "full_comment_rows": len(full_comments),
        "threshold": args.threshold,
        "feature_mode": args.feature_mode,
        "max_features": args.max_features,
        "class_weight": args.class_weight,
        "holdout_positive_f1": holdout_metrics["classification_report"]["1"]["f1-score"],
        "cv_positive_f1": cv_metrics["classification_report"]["1"]["f1-score"],
        "cv_roc_auc": cv_metrics["roc_auc"],
        "cv_average_precision": cv_metrics["average_precision"],
        "predicted_public_corrections": sum(row["public_correction_pred"] for row in predictions),
        "candidate_corrections": sum(row["candidate_correction"] for row in predictions),
        "threads_with_predicted_public_correction": sum(
            row["has_predicted_public_correction"] for row in thread_profiles
        ),
        "threads": len(thread_profiles),
        "started_utc": datetime.fromtimestamp(start, timezone.utc).isoformat(),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": time.time() - start,
    }
    write_json(metrics_dir / "run_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train and apply an exploratory correction classifier.")
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--full-comments", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--cv-folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20260625)
    parser.add_argument("--max-features", type=int, default=50000)
    parser.add_argument("--class-weight", choices=["balanced", "none"], default="balanced")
    parser.add_argument(
        "--feature-mode",
        choices=["text_only", "text_candidate", "metadata_full"],
        default="text_candidate",
        help="Feature set for the classifier. metadata_full includes subreddit and community group.",
    )
    parser.add_argument("--top-features", type=int, default=40)
    args = parser.parse_args()
    if args.class_weight == "none":
        args.class_weight = None
    return args


def main() -> None:
    run(build_parser())


if __name__ == "__main__":
    main()
