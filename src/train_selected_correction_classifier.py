#!/usr/bin/env python3
"""Train and apply the benchmark-selected public-correction classifier.

Selected model:
    text_only + char n-gram TF-IDF + balanced Logistic Regression.

The label source is Qwen-assisted annotation, not human ground truth. This run
therefore remains an exploratory scaling step.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
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
from sklearn.pipeline import FeatureUnion
from sklearn.pipeline import Pipeline

from train_correction_classifier import (
    aggregate_groups,
    aggregate_threads,
    apply_model,
    load_full_comments,
    read_annotation_rows,
    write_csv,
    write_json,
)


def word_vectorizer(max_word_features: int) -> TfidfVectorizer:
    return TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        max_features=max_word_features,
        min_df=1,
        lowercase=True,
        strip_accents="unicode",
        sublinear_tf=True,
    )


def char_vectorizer(max_char_features: int) -> TfidfVectorizer:
    return TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        max_features=max_char_features,
        min_df=1,
        lowercase=True,
        strip_accents="unicode",
        sublinear_tf=True,
    )


def build_selected_model(args: argparse.Namespace) -> Pipeline:
    if args.model_kind == "char_logreg":
        features = char_vectorizer(args.max_char_features)
    elif args.model_kind == "word_logreg":
        features = word_vectorizer(args.max_word_features)
    else:
        features = FeatureUnion(
            [
                ("word", word_vectorizer(args.max_word_features)),
                ("char", char_vectorizer(args.max_char_features)),
            ]
        )
    return Pipeline(
        steps=[
            ("features", features),
            (
                "clf",
                LogisticRegression(
                    max_iter=3000,
                    solver="liblinear",
                    class_weight=args.class_weight,
                    random_state=args.seed,
                ),
            ),
        ]
    )


def safe_metric(fn: Any, y_true: np.ndarray, y_score: np.ndarray) -> float | None:
    try:
        return float(fn(y_true, y_score))
    except ValueError:
        return None


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
    model = build_selected_model(args)
    model.fit(x_train, y_train)
    scores = model.predict_proba(x_test)[:, 1]
    preds = (scores >= args.threshold).astype(int)
    report = classification_report(y_test, preds, output_dict=True, zero_division=0)
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
        "confusion_matrix": confusion_matrix(y_test, preds, labels=[0, 1]).tolist(),
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
        model = build_selected_model(args)
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


def top_features(model: Pipeline, n: int) -> dict[str, list[dict[str, Any]]]:
    vectorizer = model.named_steps["features"]
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

    full_model = build_selected_model(args)
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
        "run_status": "exploratory_selected_classifier",
        "model": f"{args.feature_mode}_{args.model_kind}_balanced_logistic_regression",
        "annotations": str(args.annotations),
        "full_comments": str(args.full_comments),
        "output_dir": str(args.output_dir),
        "annotation_rows": len(annotation_rows),
        "annotation_class_counts": dict(Counter(row["target"] for row in annotation_rows)),
        "full_comment_rows": len(full_comments),
        "threshold": args.threshold,
        "feature_mode": args.feature_mode,
        "model_kind": args.model_kind,
        "max_char_features": args.max_char_features,
        "max_word_features": args.max_word_features,
        "class_weight": args.class_weight,
        "holdout_positive_f1": holdout_metrics["classification_report"]["1"]["f1-score"],
        "cv_positive_f1": cv_metrics["classification_report"]["1"]["f1-score"],
        "cv_positive_precision": cv_metrics["classification_report"]["1"]["precision"],
        "cv_positive_recall": cv_metrics["classification_report"]["1"]["recall"],
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
    (args.output_dir / "run.log").write_text(
        "\n".join(
            [
                "selected correction classifier full prediction run",
                f"generated_utc={summary['finished_utc']}",
                f"command={' '.join(sys.argv)}",
                f"model={summary['model']}",
                f"threshold={args.threshold}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train and apply the selected correction classifier.")
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--full-comments", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--cv-folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--feature-mode", choices=["text_only", "text_candidate", "metadata_full"], default="text_only")
    parser.add_argument("--model-kind", choices=["char_logreg", "word_logreg", "word_char_logreg"], default="char_logreg")
    parser.add_argument("--max-word-features", type=int, default=50000)
    parser.add_argument("--max-char-features", type=int, default=60000)
    parser.add_argument("--class-weight", choices=["balanced", "none"], default="balanced")
    parser.add_argument("--top-features", type=int, default=60)
    args = parser.parse_args()
    if args.class_weight == "none":
        args.class_weight = None
    return args


def main() -> None:
    run(build_parser())


if __name__ == "__main__":
    main()
