#!/usr/bin/env python3
"""Train lightweight score rerankers for public-correction detection.

The reranker combines existing detector scores with simple relation/context
features. It is evaluated on an independent audit set and is intended as a fast
test of whether prediction quality can be improved without another transformer
fine-tuning run.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier, GradientBoostingClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, confusion_matrix, precision_recall_curve, precision_recall_fscore_support, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


CORRECTION_TERMS = [
    "actually",
    "not true",
    "false",
    "wrong",
    "misleading",
    "debunk",
    "fact check",
    "fact-check",
    "source",
    "evidence",
    "study",
    "data",
    "according to",
    "cdc",
    "who",
    "fda",
    "peer reviewed",
    "peer-reviewed",
    "that's not",
    "that is not",
    "this is not",
]

MISINFO_TERMS = [
    "big pharma",
    "fauci",
    "plandemic",
    "scamdemic",
    "experimental vaccine",
    "gene therapy",
    "fake pandemic",
    "natural immunity",
    "vaers",
    "ivermectin",
    "hydroxychloroquine",
    "microchip",
    "5g",
    "depopulation",
    "nuremberg",
    "my body my choice",
    "mandate",
    "tyranny",
    "censorship",
]

SARCASM_TERMS = ["/s", "yeah right", "sure buddy", "good thing", "lol", "lmao", "ftfy"]


def compile_terms(terms: list[str]) -> list[re.Pattern[str]]:
    patterns = []
    for term in terms:
        escaped = re.escape(term.lower())
        if " " in term or any(ch in term for ch in ["/", "-"]):
            patterns.append(re.compile(escaped))
        else:
            patterns.append(re.compile(rf"\b{escaped}\b"))
    return patterns


CORRECTION_PATTERNS = compile_terms(CORRECTION_TERMS)
MISINFO_PATTERNS = compile_terms(MISINFO_TERMS)
SARCASM_PATTERNS = compile_terms(SARCASM_TERMS)


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


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


def normalize_token(value: Any) -> str:
    return str(value or "").strip().lower()


def compact_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def to_float(value: Any) -> float:
    try:
        out = float(str(value))
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(out):
        return 0.0
    return out


def has_match(text: str, patterns: list[re.Pattern[str]]) -> int:
    lowered = text.lower()
    return int(any(pattern.search(lowered) for pattern in patterns))


def count_matches(text: str, patterns: list[re.Pattern[str]]) -> int:
    lowered = text.lower()
    return sum(1 for pattern in patterns if pattern.search(lowered))


def load_comments(path: Path) -> dict[str, dict[str, Any]]:
    rows = []
    for raw in iter_jsonl(path):
        comment_id = normalize_token(raw.get("comment_id"))
        if not comment_id:
            continue
        rows.append(
            {
                "comment_id": comment_id,
                "submission_id": normalize_token(raw.get("submission_id")),
                "parent_id": normalize_token(raw.get("parent_id")),
                "subreddit": normalize_token(raw.get("subreddit")),
                "submission_title": compact_text(raw.get("submission_title")),
                "body": compact_text(raw.get("body")),
                "created_utc": to_float(raw.get("created_utc")),
                "level": int(to_float(raw.get("level"))),
            }
        )
    by_id = {row["comment_id"]: row for row in rows}
    for row in rows:
        parent = by_id.get(row["parent_id"], {})
        row["parent_body"] = parent.get("body", "")
    return by_id


def load_prediction_scores(paths: list[Path]) -> tuple[dict[str, dict[str, float]], list[str]]:
    scores: dict[str, dict[str, float]] = defaultdict(dict)
    score_names = []
    for idx, path in enumerate(paths, 1):
        name = path.parent.parent.name
        short = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower()
        if not short:
            short = f"model_{idx}"
        while short in score_names:
            short = f"{short}_{idx}"
        score_names.append(short)
        for row in read_csv(path):
            comment_id = normalize_token(row.get("comment_id"))
            if comment_id:
                scores[comment_id][short] = to_float(row.get("public_correction_score"))
    return scores, score_names


def load_labels(paths: list[Path], source_prefix: str) -> pd.DataFrame:
    rows = []
    for path in paths:
        for row in read_csv(path):
            label = str(row.get("llm_label", "")).strip()
            comment_id = normalize_token(row.get("comment_id"))
            if label not in {"0", "1"} or not comment_id:
                continue
            rows.append(
                {
                    "comment_id": comment_id,
                    "label": int(label),
                    "label_source": f"{source_prefix}:{path.parent.name}",
                    "annotation_source": str(row.get("annotation_source") or path.parent.name),
                    "sample_component": str(row.get("sample_component") or ""),
                    "relation_type": str(row.get("llm_relation_type") or ""),
                }
            )
    return pd.DataFrame(rows).drop_duplicates("comment_id", keep="last")


def text_features(comment: dict[str, Any]) -> dict[str, Any]:
    title = comment.get("submission_title", "")
    body = comment.get("body", "")
    parent = comment.get("parent_body", "")
    all_text = f"{title} {parent} {body}"
    return {
        "subreddit": comment.get("subreddit", ""),
        "has_parent": int(bool(parent)),
        "body_len": len(body),
        "parent_len": len(parent),
        "title_len": len(title),
        "is_short": int(len(body) <= 120),
        "has_quote": int(body.strip().startswith(">") or "\n>" in body),
        "has_quote_edit": int("~~" in body or "ftfy" in body.lower()),
        "has_url": int("http://" in body.lower() or "https://" in body.lower()),
        "has_digit": int(any(ch.isdigit() for ch in body)),
        "has_question": int("?" in body),
        "has_exclamation": int("!" in body),
        "correction_term_count": count_matches(all_text, CORRECTION_PATTERNS),
        "body_correction_term_count": count_matches(body, CORRECTION_PATTERNS),
        "parent_misinfo_term_count": count_matches(parent, MISINFO_PATTERNS),
        "body_misinfo_term_count": count_matches(body, MISINFO_PATTERNS),
        "has_sarcasm": has_match(body, SARCASM_PATTERNS),
    }


def build_matrix(
    labels: pd.DataFrame,
    comments: dict[str, dict[str, Any]],
    scores: dict[str, dict[str, float]],
    score_names: list[str],
) -> pd.DataFrame:
    rows = []
    for row in labels.to_dict("records"):
        comment_id = row["comment_id"]
        comment = comments.get(comment_id, {})
        item = dict(row)
        item.update(text_features(comment))
        model_scores = scores.get(comment_id, {})
        values = []
        for name in score_names:
            score = model_scores.get(name, np.nan)
            item[f"score_{name}"] = score
            if not np.isnan(score):
                values.append(float(score))
        item["score_mean"] = float(np.mean(values)) if values else np.nan
        item["score_max"] = float(np.max(values)) if values else np.nan
        item["score_min"] = float(np.min(values)) if values else np.nan
        item["score_std"] = float(np.std(values)) if values else np.nan
        item["score_range"] = float(np.max(values) - np.min(values)) if values else np.nan
        item["score_models_present"] = len(values)
        rows.append(item)
    return pd.DataFrame(rows)


def select_threshold(y_true: np.ndarray, scores: np.ndarray) -> dict[str, float]:
    precision, recall, thresholds = precision_recall_curve(y_true, scores)
    best = {"threshold": 0.5, "precision": 0.0, "recall": 0.0, "f1": 0.0}
    for idx, threshold in enumerate(thresholds):
        p = float(precision[idx])
        r = float(recall[idx])
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        if (f1, p, r) > (best["f1"], best["precision"], best["recall"]):
            best = {"threshold": float(threshold), "precision": p, "recall": r, "f1": f1}
    return best


def metrics(y_true: np.ndarray, scores: np.ndarray, threshold: float) -> dict[str, Any]:
    pred = (scores >= threshold).astype(int)
    precision, recall, f1, support = precision_recall_fscore_support(y_true, pred, labels=[0, 1], zero_division=0)
    return {
        "average_precision": float(average_precision_score(y_true, scores)),
        "roc_auc": float(roc_auc_score(y_true, scores)),
        "threshold": float(threshold),
        "confusion_matrix": confusion_matrix(y_true, pred, labels=[0, 1]).tolist(),
        "positive_precision": float(precision[1]),
        "positive_recall": float(recall[1]),
        "positive_f1": float(f1[1]),
        "predicted_positive": int(pred.sum()),
        "predicted_positive_rate": float(pred.mean()),
    }


def make_preprocessor(df: pd.DataFrame, feature_cols: list[str], categorical_cols: list[str]) -> ColumnTransformer:
    numeric_cols = [col for col in feature_cols if col not in categorical_cols]
    return ColumnTransformer(
        transformers=[
            ("num", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), numeric_cols),
            ("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), categorical_cols),
        ]
    )


def sample_weights(df: pd.DataFrame, mode: str) -> np.ndarray | None:
    if mode == "none":
        return None
    weights = np.ones(len(df), dtype=float)
    active = df["annotation_source"].astype(str).str.contains("relation_schema_active", na=False)
    if mode == "active_025":
        weights[active.to_numpy()] = 0.25
    elif mode == "active_050":
        weights[active.to_numpy()] = 0.5
    elif mode == "active_075":
        weights[active.to_numpy()] = 0.75
    return weights


def model_specs(seed: int) -> dict[str, Any]:
    return {
        "logit_balanced": LogisticRegression(max_iter=2000, class_weight="balanced", solver="liblinear", random_state=seed),
        "logit_none": LogisticRegression(max_iter=2000, class_weight=None, solver="liblinear", random_state=seed),
        "gb": GradientBoostingClassifier(random_state=seed, n_estimators=160, learning_rate=0.035, max_depth=2),
        "histgb": HistGradientBoostingClassifier(random_state=seed, max_iter=180, learning_rate=0.035, l2_regularization=0.05),
        "rf_balanced": RandomForestClassifier(n_estimators=400, min_samples_leaf=8, class_weight="balanced_subsample", random_state=seed, n_jobs=-1),
        "extra_balanced": ExtraTreesClassifier(n_estimators=500, min_samples_leaf=6, class_weight="balanced", random_state=seed, n_jobs=-1),
    }


def run(args: argparse.Namespace) -> None:
    start = time.time()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir = args.output_dir / "metrics"
    tables_dir = args.output_dir / "tables"
    predictions_dir = args.output_dir / "predictions"
    for directory in [metrics_dir, tables_dir, predictions_dir]:
        directory.mkdir(exist_ok=True)

    comments = load_comments(args.comments)
    scores, score_names = load_prediction_scores(args.predictions)
    train_labels = load_labels(args.train_annotations, "train")
    audit_labels = load_labels([args.audit], "audit")
    train_df = build_matrix(train_labels, comments, scores, score_names)
    audit_df = build_matrix(audit_labels, comments, scores, score_names)

    feature_cols = [col for col in train_df.columns if col.startswith("score_")] + [
        "has_parent",
        "body_len",
        "parent_len",
        "title_len",
        "is_short",
        "has_quote",
        "has_quote_edit",
        "has_url",
        "has_digit",
        "has_question",
        "has_exclamation",
        "correction_term_count",
        "body_correction_term_count",
        "parent_misinfo_term_count",
        "body_misinfo_term_count",
        "has_sarcasm",
        "subreddit",
    ]
    categorical_cols = ["subreddit"]
    y = train_df["label"].to_numpy(dtype=int)
    y_audit = audit_df["label"].to_numpy(dtype=int)
    train_idx, val_idx = train_test_split(
        np.arange(len(train_df)),
        test_size=args.val_size,
        random_state=args.seed,
        stratify=y,
    )

    baseline_rows = []
    for name in score_names + ["score_mean", "score_max"]:
        col = f"score_{name}" if name in score_names else name
        if col not in audit_df:
            continue
        audit_scores = audit_df[col].fillna(0).to_numpy(dtype=float)
        val_scores = train_df.iloc[val_idx][col].fillna(0).to_numpy(dtype=float)
        threshold = select_threshold(y[val_idx], val_scores)["threshold"]
        row = {"model": f"baseline:{col}", **metrics(y_audit, audit_scores, threshold)}
        baseline_rows.append(row)

    rows = []
    pred_rows: list[dict[str, Any]] = []
    specs = model_specs(args.seed)
    for weight_mode in args.weight_modes:
        weights = sample_weights(train_df, weight_mode)
        for model_name, estimator in specs.items():
            preprocessor = make_preprocessor(train_df, feature_cols, categorical_cols)
            clf = Pipeline([("pre", preprocessor), ("model", estimator)])
            fit_kwargs = {}
            if weights is not None:
                fit_kwargs["model__sample_weight"] = weights
            clf.fit(train_df[feature_cols], y, **fit_kwargs)
            val_scores = clf.predict_proba(train_df.iloc[val_idx][feature_cols])[:, 1]
            threshold = select_threshold(y[val_idx], val_scores)["threshold"]
            audit_scores = clf.predict_proba(audit_df[feature_cols])[:, 1]
            row = {
                "model": model_name,
                "weight_mode": weight_mode,
                **metrics(y_audit, audit_scores, threshold),
            }
            rows.append(row)
            for comment_id, label, score in zip(audit_df["comment_id"], y_audit, audit_scores):
                pred_rows.append(
                    {
                        "model": model_name,
                        "weight_mode": weight_mode,
                        "comment_id": comment_id,
                        "llm_label": int(label),
                        "score": float(score),
                    }
                )

    all_rows = baseline_rows + rows
    all_rows.sort(key=lambda row: row["average_precision"], reverse=True)
    write_csv(
        tables_dir / "audit_model_comparison.csv",
        all_rows,
        [
            "model",
            "weight_mode",
            "average_precision",
            "roc_auc",
            "threshold",
            "positive_precision",
            "positive_recall",
            "positive_f1",
            "predicted_positive",
            "predicted_positive_rate",
            "confusion_matrix",
        ],
    )
    write_csv(predictions_dir / "audit_reranker_predictions.csv", pred_rows, ["model", "weight_mode", "comment_id", "llm_label", "score"])

    summary = {
        "run_status": "score_reranker_audit_evaluation",
        "train_annotations": [str(path) for path in args.train_annotations],
        "audit": str(args.audit),
        "comments": str(args.comments),
        "predictions": [str(path) for path in args.predictions],
        "output_dir": str(args.output_dir),
        "train_rows": int(len(train_df)),
        "audit_rows": int(len(audit_df)),
        "train_label_counts": train_df["label"].value_counts().sort_index().to_dict(),
        "audit_label_counts": audit_df["label"].value_counts().sort_index().to_dict(),
        "score_names": score_names,
        "feature_cols": feature_cols,
        "best_model": all_rows[0],
        "started_utc": datetime.fromtimestamp(start, timezone.utc).isoformat(),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": time.time() - start,
    }
    write_json(metrics_dir / "run_summary.json", summary)
    (args.output_dir / "run.log").write_text(
        "\n".join(
            [
                "score reranker audit evaluation",
                f"generated_utc={summary['finished_utc']}",
                f"command={' '.join(sys.argv)}",
                f"best_model={summary['best_model']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train lightweight rerankers from detector scores and context features.")
    parser.add_argument("--train-annotations", type=Path, nargs="+", required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--comments", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260627)
    parser.add_argument("--val-size", type=float, default=0.2)
    parser.add_argument("--weight-modes", nargs="+", default=["none", "active_025", "active_050", "active_075"])
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
