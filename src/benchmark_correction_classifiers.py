#!/usr/bin/env python3
"""Benchmark lightweight public-correction classifiers on assisted labels.

The benchmark evaluates models against the current Qwen-assisted labels. It is
therefore an exploratory model-selection step, not a final validation against
human ground truth.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.feature_selection import SelectKBest, chi2
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_recall_fscore_support,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC


def compact_text(value: Any, limit: int = 5000) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit] if len(text) > limit else text


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def feature_text(row: dict[str, Any], feature_mode: str) -> str:
    title = compact_text(row.get("submission_title"))
    body = compact_text(row.get("body"))
    candidate = int(boolish(row.get("candidate_correction")))
    if feature_mode == "text_candidate":
        return f"CANDIDATE={candidate} TITLE={title} COMMENT={body}"
    return f"TITLE={title} COMMENT={body}"


def read_rows(path: Path, feature_mode: str) -> list[dict[str, Any]]:
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


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def safe_metric(fn: Any, y_true: np.ndarray, y_score: np.ndarray) -> float | None:
    try:
        return float(fn(y_true, y_score))
    except ValueError:
        return None


def word_vectorizer(max_features: int) -> TfidfVectorizer:
    return TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        max_features=max_features,
        min_df=1,
        lowercase=True,
        strip_accents="unicode",
        sublinear_tf=True,
    )


def char_vectorizer(max_features: int) -> TfidfVectorizer:
    return TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        max_features=max_features,
        min_df=1,
        lowercase=True,
        strip_accents="unicode",
        sublinear_tf=True,
    )


def build_models(args: argparse.Namespace) -> dict[str, Pipeline]:
    word = word_vectorizer(args.max_word_features)
    char = char_vectorizer(args.max_char_features)
    word_char = FeatureUnion(
        [
            ("word", word_vectorizer(args.max_word_features)),
            ("char", char_vectorizer(args.max_char_features)),
        ]
    )

    return {
        "word_logreg_balanced": Pipeline(
            [
                ("features", word),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=3000,
                        solver="liblinear",
                        class_weight="balanced",
                        random_state=args.seed,
                    ),
                ),
            ]
        ),
        "word_logreg_unweighted": Pipeline(
            [
                ("features", word_vectorizer(args.max_word_features)),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=3000,
                        solver="liblinear",
                        class_weight=None,
                        random_state=args.seed,
                    ),
                ),
            ]
        ),
        "char_logreg_balanced": Pipeline(
            [
                ("features", char),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=3000,
                        solver="liblinear",
                        class_weight="balanced",
                        random_state=args.seed,
                    ),
                ),
            ]
        ),
        "word_char_logreg_balanced": Pipeline(
            [
                ("features", word_char),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=3000,
                        solver="liblinear",
                        class_weight="balanced",
                        random_state=args.seed,
                    ),
                ),
            ]
        ),
        "word_linear_svm_balanced": Pipeline(
            [
                ("features", word_vectorizer(args.max_word_features)),
                ("clf", LinearSVC(class_weight="balanced", random_state=args.seed, max_iter=5000)),
            ]
        ),
        "char_linear_svm_balanced": Pipeline(
            [
                ("features", char_vectorizer(args.max_char_features)),
                ("clf", LinearSVC(class_weight="balanced", random_state=args.seed, max_iter=5000)),
            ]
        ),
        "word_complement_nb": Pipeline(
            [
                ("features", word_vectorizer(args.max_word_features)),
                ("clf", ComplementNB(alpha=0.5)),
            ]
        ),
        "word_chi2_logreg_balanced": Pipeline(
            [
                ("features", word_vectorizer(args.max_word_features)),
                ("select", SelectKBest(chi2, k=args.chi2_k)),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=3000,
                        solver="liblinear",
                        class_weight="balanced",
                        random_state=args.seed,
                    ),
                ),
            ]
        ),
    }


def model_scores(model: Pipeline, x: list[str]) -> tuple[np.ndarray, str]:
    if hasattr(model, "predict_proba"):
        return model.predict_proba(x)[:, 1], "probability"
    return model.decision_function(x), "decision_function"


def default_predictions(scores: np.ndarray, score_type: str) -> np.ndarray:
    threshold = 0.5 if score_type == "probability" else 0.0
    return (scores >= threshold).astype(int)


def threshold_summary(y: np.ndarray, scores: np.ndarray) -> list[dict[str, Any]]:
    precision, recall, thresholds = precision_recall_curve(y, scores)
    rows: list[dict[str, Any]] = []

    # precision_recall_curve returns one extra precision/recall point without a threshold.
    for p, r, t in zip(precision[:-1], recall[:-1], thresholds):
        f1 = (2 * p * r / (p + r)) if (p + r) else 0.0
        predicted_positive = int((scores >= t).sum())
        rows.append(
            {
                "threshold": float(t),
                "precision_positive": float(p),
                "recall_positive": float(r),
                "f1_positive": float(f1),
                "predicted_positive": predicted_positive,
            }
        )
    return rows


def best_threshold_rows(y: np.ndarray, scores: np.ndarray) -> list[dict[str, Any]]:
    rows = threshold_summary(y, scores)
    if not rows:
        return []
    best_f1 = max(rows, key=lambda row: (row["f1_positive"], row["precision_positive"], row["recall_positive"]))
    out = [{**best_f1, "selection_rule": "max_f1"}]
    for target_precision in [0.70, 0.75, 0.80, 0.85]:
        candidates = [row for row in rows if row["precision_positive"] >= target_precision]
        if candidates:
            best = max(candidates, key=lambda row: (row["recall_positive"], row["f1_positive"]))
            out.append({**best, "selection_rule": f"precision_at_least_{target_precision:.2f}"})
    return out


def evaluate_model(
    model_name: str,
    model: Pipeline,
    rows: list[dict[str, Any]],
    feature_mode: str,
    args: argparse.Namespace,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    x = np.array([row["feature_text"] for row in rows], dtype=object)
    y = np.array([row["target"] for row in rows], dtype=int)
    skf = StratifiedKFold(n_splits=args.cv_folds, shuffle=True, random_state=args.seed)
    oof_scores = np.zeros(len(y), dtype=float)
    oof_preds = np.zeros(len(y), dtype=int)
    fold_rows: list[dict[str, Any]] = []
    score_type = "unknown"

    for fold, (train_idx, test_idx) in enumerate(skf.split(x, y), 1):
        fitted = model
        fitted.fit(x[train_idx].tolist(), y[train_idx])
        scores, score_type = model_scores(fitted, x[test_idx].tolist())
        preds = default_predictions(scores, score_type)
        oof_scores[test_idx] = scores
        oof_preds[test_idx] = preds
        precision, recall, f1, support = precision_recall_fscore_support(
            y[test_idx], preds, labels=[0, 1], zero_division=0
        )
        fold_rows.append(
            {
                "feature_mode": feature_mode,
                "model": model_name,
                "fold": fold,
                "score_type": score_type,
                "test_rows": int(len(test_idx)),
                "true_positive_rate": float(y[test_idx].mean()),
                "predicted_positive_rate": float(preds.mean()),
                "precision_positive": float(precision[1]),
                "recall_positive": float(recall[1]),
                "f1_positive": float(f1[1]),
                "support_positive": int(support[1]),
                "roc_auc": safe_metric(roc_auc_score, y[test_idx], scores),
                "average_precision": safe_metric(average_precision_score, y[test_idx], scores),
            }
        )

    precision, recall, f1, support = precision_recall_fscore_support(
        y, oof_preds, labels=[0, 1], zero_division=0
    )
    matrix = confusion_matrix(y, oof_preds, labels=[0, 1])
    threshold_rows = [
        {
            "feature_mode": feature_mode,
            "model": model_name,
            **row,
        }
        for row in best_threshold_rows(y, oof_scores)
    ]
    best_f1 = next((row for row in threshold_rows if row["selection_rule"] == "max_f1"), None)
    metric = {
        "feature_mode": feature_mode,
        "model": model_name,
        "rows": int(len(y)),
        "positive_rows": int(y.sum()),
        "positive_rate_true": float(y.mean()),
        "score_type": score_type,
        "default_threshold": 0.5 if score_type == "probability" else 0.0,
        "default_predicted_positive": int(oof_preds.sum()),
        "default_predicted_positive_rate": float(oof_preds.mean()),
        "default_precision_positive": float(precision[1]),
        "default_recall_positive": float(recall[1]),
        "default_f1_positive": float(f1[1]),
        "default_precision_negative": float(precision[0]),
        "default_recall_negative": float(recall[0]),
        "default_f1_negative": float(f1[0]),
        "support_positive": int(support[1]),
        "roc_auc": safe_metric(roc_auc_score, y, oof_scores),
        "average_precision": safe_metric(average_precision_score, y, oof_scores),
        "confusion_matrix_tn_fp_fn_tp": [
            int(matrix[0, 0]),
            int(matrix[0, 1]),
            int(matrix[1, 0]),
            int(matrix[1, 1]),
        ],
    }
    if best_f1:
        metric.update(
            {
                "best_f1_threshold": best_f1["threshold"],
                "best_f1_positive": best_f1["f1_positive"],
                "best_f1_precision_positive": best_f1["precision_positive"],
                "best_f1_recall_positive": best_f1["recall_positive"],
                "best_f1_predicted_positive": best_f1["predicted_positive"],
            }
        )
    return metric, fold_rows, threshold_rows


def rank_metrics(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        metrics,
        key=lambda row: (
            row.get("best_f1_positive") or 0,
            row.get("average_precision") or 0,
            row.get("roc_auc") or 0,
            row.get("default_f1_positive") or 0,
        ),
        reverse=True,
    )
    out = []
    for rank, row in enumerate(ranked, 1):
        out.append({**row, "rank_by_best_f1": rank})
    return out


def run(args: argparse.Namespace) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = args.output_dir / "tables"
    metrics_dir = args.output_dir / "metrics"
    tables_dir.mkdir(exist_ok=True)
    metrics_dir.mkdir(exist_ok=True)

    all_metrics: list[dict[str, Any]] = []
    all_folds: list[dict[str, Any]] = []
    all_thresholds: list[dict[str, Any]] = []

    for feature_mode in args.feature_modes:
        rows = read_rows(args.annotations, feature_mode)
        models = build_models(args)
        for model_name, model in models.items():
            metric, fold_rows, threshold_rows = evaluate_model(model_name, model, rows, feature_mode, args)
            all_metrics.append(metric)
            all_folds.extend(fold_rows)
            all_thresholds.extend(threshold_rows)

    ranked = rank_metrics(all_metrics)

    metric_fields = [
        "rank_by_best_f1",
        "feature_mode",
        "model",
        "rows",
        "positive_rows",
        "positive_rate_true",
        "score_type",
        "default_threshold",
        "default_predicted_positive",
        "default_predicted_positive_rate",
        "default_precision_positive",
        "default_recall_positive",
        "default_f1_positive",
        "roc_auc",
        "average_precision",
        "best_f1_threshold",
        "best_f1_positive",
        "best_f1_precision_positive",
        "best_f1_recall_positive",
        "best_f1_predicted_positive",
        "confusion_matrix_tn_fp_fn_tp",
    ]
    write_csv(tables_dir / "model_benchmark_summary.csv", ranked, metric_fields)
    write_csv(
        tables_dir / "fold_metrics.csv",
        all_folds,
        [
            "feature_mode",
            "model",
            "fold",
            "score_type",
            "test_rows",
            "true_positive_rate",
            "predicted_positive_rate",
            "precision_positive",
            "recall_positive",
            "f1_positive",
            "support_positive",
            "roc_auc",
            "average_precision",
        ],
    )
    write_csv(
        tables_dir / "threshold_selection.csv",
        all_thresholds,
        [
            "feature_mode",
            "model",
            "selection_rule",
            "threshold",
            "precision_positive",
            "recall_positive",
            "f1_positive",
            "predicted_positive",
        ],
    )
    write_json(metrics_dir / "model_benchmark_summary.json", {"models": ranked})

    summary = {
        "run_status": "exploratory_classifier_benchmark_qwen_labels",
        "annotations": str(args.annotations),
        "output_dir": str(args.output_dir),
        "feature_modes": args.feature_modes,
        "models_tested": len(all_metrics),
        "cv_folds": args.cv_folds,
        "seed": args.seed,
        "class_counts": dict(Counter(row["target"] for row in read_rows(args.annotations, args.feature_modes[0]))),
        "ranking_rule": "best_f1_positive, then average_precision, then roc_auc",
        "best_model": ranked[0] if ranked else None,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(metrics_dir / "run_summary.json", summary)
    (args.output_dir / "run.log").write_text(
        "\n".join(
            [
                "correction classifier benchmark run",
                f"generated_utc={summary['generated_utc']}",
                f"command={' '.join(sys.argv)}",
                f"annotations={args.annotations}",
                f"feature_modes={','.join(args.feature_modes)}",
                f"models_tested={summary['models_tested']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark public-correction classifiers.")
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--feature-modes", nargs="+", default=["text_only", "text_candidate"])
    parser.add_argument("--cv-folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-word-features", type=int, default=20000)
    parser.add_argument("--max-char-features", type=int, default=30000)
    parser.add_argument("--chi2-k", type=int, default=2000)
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
