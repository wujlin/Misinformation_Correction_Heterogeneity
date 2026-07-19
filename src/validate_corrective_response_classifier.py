#!/usr/bin/env python3
"""Validate the relation-aware corrective-response classifier on human labels."""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import rankdata

from fit_revised_corrective_response_models import build_pair_history, load_comments


SELECTED_SCORE = "base_best_plus_large_title_roberta_mean"
MODEL_SCORES = [
    ("Relation-aware ensemble", SELECTED_SCORE),
    ("Pair + title", "title6232"),
    ("Pair only", "claim6232"),
    ("Large pair + title", "large_title6232"),
    ("NLI pair", "roberta_mnli6232"),
    ("Relation type", "type6232"),
    ("Comment only", "public_correction_score"),
]


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def binary_metrics(target: np.ndarray, score: np.ndarray, threshold: float = 0.5) -> dict[str, float]:
    predicted = (score >= threshold).astype(int)
    true_positive = int(((target == 1) & (predicted == 1)).sum())
    false_positive = int(((target == 0) & (predicted == 1)).sum())
    false_negative = int(((target == 1) & (predicted == 0)).sum())
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    order = np.argsort(score, kind="mergesort")[::-1]
    sorted_target = target[order]
    sorted_score = score[order]
    distinct_score_indices = np.where(np.diff(sorted_score))[0]
    threshold_indices = np.r_[distinct_score_indices, len(target) - 1]
    cumulative_positive = np.cumsum(sorted_target)[threshold_indices]
    cumulative_total = threshold_indices + 1
    precision_curve = cumulative_positive / cumulative_total
    recall_curve = cumulative_positive / target.sum()
    average_precision = float((np.diff(np.r_[0.0, recall_curve]) * precision_curve).sum())

    positives = int(target.sum())
    negatives = int(len(target) - positives)
    ranks = rankdata(score, method="average")
    roc_auc = float((ranks[target == 1].sum() - positives * (positives + 1) / 2) / (positives * negatives))
    return {
        "n": int(len(target)),
        "positives": int(target.sum()),
        "prevalence": float(target.mean()),
        "average_precision": average_precision,
        "roc_auc": roc_auc,
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "brier_score": float(np.mean((score - target) ** 2)),
        "predicted_positives": int(predicted.sum()),
    }


def bootstrap_intervals(
    target: np.ndarray,
    score: np.ndarray,
    iterations: int,
    seed: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    values: dict[str, list[float]] = {
        key: []
        for key in ["average_precision", "roc_auc", "precision", "recall", "f1", "brier_score"]
    }
    n = len(target)
    for _ in range(iterations):
        indices = rng.integers(0, n, n)
        sampled_target = target[indices]
        if np.unique(sampled_target).size < 2:
            continue
        sampled = binary_metrics(sampled_target, score[indices])
        for key in values:
            values[key].append(sampled[key])
    point = binary_metrics(target, score)
    rows = []
    for metric, samples in values.items():
        rows.append(
            {
                "metric": metric,
                "estimate": point[metric],
                "ci_low": float(np.quantile(samples, 0.025)),
                "ci_high": float(np.quantile(samples, 0.975)),
                "bootstrap_iterations": len(samples),
            }
        )
    return pd.DataFrame(rows)


def calibration_summary(target: np.ndarray, score: np.ndarray) -> tuple[dict[str, float], pd.DataFrame]:
    clipped = np.clip(score, 1e-6, 1 - 1e-6)
    logit_score = np.log(clipped / (1.0 - clipped))
    calibration_model = sm.Logit(target, sm.add_constant(logit_score)).fit(disp=False)
    bins = pd.cut(score, bins=np.linspace(0, 1, 11), include_lowest=True, duplicates="drop")
    calibration = pd.DataFrame({"target": target, "score": score, "bin": bins})
    table = (
        calibration.groupby("bin", observed=True)
        .agg(n=("target", "size"), mean_score=("score", "mean"), observed_rate=("target", "mean"))
        .reset_index()
    )
    table["bin"] = table["bin"].astype(str)
    expected_calibration_error = float(
        ((table["n"] / table["n"].sum()) * (table["mean_score"] - table["observed_rate"]).abs()).sum()
    )
    return (
        {
            "brier_score": float(np.mean((score - target) ** 2)),
            "expected_calibration_error_10_bins": expected_calibration_error,
            "calibration_intercept": float(calibration_model.params[0]),
            "calibration_slope": float(calibration_model.params[1]),
        },
        table,
    )


def load_validation_frame(args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, int]]:
    labels = pd.read_csv(args.human_labels, low_memory=False)
    scores = pd.read_csv(args.model_scores, low_memory=False)
    labels["manual_label"] = pd.to_numeric(labels["manual_pair_label"], errors="coerce")
    raw_unclear = int(labels["manual_label"].isna().sum())
    labels["response_words"] = labels["response_body"].fillna("").astype(str).str.split().str.len()
    keep = [
        "pair_id",
        "response_id",
        "response_author",
        "submission_id",
        "subreddit",
        "community_group_proxy",
        "pair_source",
        "response_has_sarcasm",
        "response_words",
        "public_correction_score",
        "manual_label",
    ]
    score_columns = [column for _, column in MODEL_SCORES if column != "public_correction_score"]
    frame = labels[keep].merge(
        scores[["pair_id", *score_columns]],
        on="pair_id",
        how="inner",
        validate="one_to_one",
    )
    unclear = int(frame["manual_label"].isna().sum())
    frame = frame.loc[frame["manual_label"].isin([0, 1])].copy()
    frame["manual_label"] = frame["manual_label"].astype(int)

    training = pd.read_csv(
        args.training_labels,
        usecols=["pair_id", "response_id", "response_author", "submission_id"],
        low_memory=False,
    )
    training_sets = {
        "pair": set(training["pair_id"].astype(str)),
        "response": set(training["response_id"].astype(str)),
        "author": set(training["response_author"].fillna("").astype(str).str.lower()),
        "thread": set(training["submission_id"].astype(str)),
    }
    frame["seen_training_pair"] = frame["pair_id"].astype(str).isin(training_sets["pair"])
    frame["seen_training_response"] = frame["response_id"].astype(str).isin(training_sets["response"])
    frame["seen_training_author"] = (
        frame["response_author"].fillna("").astype(str).str.lower().isin(training_sets["author"])
    )
    frame["seen_training_thread"] = frame["submission_id"].astype(str).isin(training_sets["thread"])
    diagnostics = {
        "raw_validation_pairs": int(len(labels)),
        "unclear_pairs_excluded": raw_unclear,
        "unmatched_model_score_rows": int(len(labels) - len(frame) - raw_unclear),
        "evaluated_pairs": int(len(frame)),
        "pair_overlap": int(frame["seen_training_pair"].sum()),
        "response_overlap": int(frame["seen_training_response"].sum()),
        "author_overlap": int(frame["seen_training_author"].sum()),
        "thread_overlap": int(frame["seen_training_thread"].sum()),
        "unique_validation_threads": int(frame["submission_id"].nunique()),
        "unique_threads_seen_in_training": int(
            frame.loc[frame["seen_training_thread"], "submission_id"].nunique()
        ),
        "unique_validation_authors": int(frame["response_author"].nunique()),
        "unique_authors_seen_in_training": int(
            frame.loc[frame["seen_training_author"], "response_author"].nunique()
        ),
    }
    return frame, diagnostics


def attach_predictor_context(frame: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    comments = load_comments(args)
    history = build_pair_history(comments).rename(columns={"author": "response_author"})
    history["response_author"] = history["response_author"].astype(str).str.lower()
    history["submission_id"] = history["submission_id"].astype(str).str.lower()

    frame = frame.copy()
    frame["response_author"] = frame["response_author"].fillna("").astype(str).str.lower()
    frame["submission_id"] = frame["submission_id"].astype(str).str.lower()
    frame["subreddit"] = frame["subreddit"].astype(str).str.lower()
    frame = frame.merge(
        history[
            [
                "submission_id",
                "response_author",
                "prior_comments",
                "prior_cross_subreddit_participation",
            ]
        ],
        on=["submission_id", "response_author"],
        how="left",
        validate="many_to_one",
    )
    early_context = (
        comments.loc[comments["thread_comment_rank"] <= 10]
        .groupby("submission_id", as_index=False)
        .agg(early_hostile_language_rate=("hostile_language", "mean"))
    )
    frame = frame.merge(early_context, on="submission_id", how="left", validate="many_to_one")
    if frame[["prior_comments", "prior_cross_subreddit_participation", "early_hostile_language_rate"]].isna().any().any():
        raise ValueError("Predictor-context audit could not be attached to every validation pair")
    frame["prior_participation_group"] = "limited prior record"
    eligible = frame["prior_comments"] >= 2
    frame.loc[eligible & frame["prior_cross_subreddit_participation"].eq(0), "prior_participation_group"] = (
        "one prior subreddit"
    )
    frame.loc[eligible & frame["prior_cross_subreddit_participation"].eq(1), "prior_participation_group"] = (
        "multiple prior subreddits"
    )
    frame["early_hostile_language_group"] = np.where(
        frame["early_hostile_language_rate"] > 0,
        "any hostile language",
        "no hostile language",
    )
    return frame


def model_comparison(frame: pd.DataFrame) -> pd.DataFrame:
    target = frame["manual_label"].to_numpy(dtype=int)
    rows = []
    for label, column in MODEL_SCORES:
        score = frame[column].to_numpy(dtype=float)
        rows.append({"model": label, **binary_metrics(target, score)})
    return pd.DataFrame(rows)


def threshold_table(frame: pd.DataFrame) -> pd.DataFrame:
    target = frame["manual_label"].to_numpy(dtype=int)
    score = frame[SELECTED_SCORE].to_numpy(dtype=float)
    rows = []
    for threshold in np.arange(0.3, 0.71, 0.05):
        rows.append({"threshold": round(float(threshold), 2), **binary_metrics(target, score, float(threshold))})
    return pd.DataFrame(rows)


def subgroup_table(frame: pd.DataFrame) -> pd.DataFrame:
    subsets: list[tuple[str, str, pd.DataFrame]] = [
        ("overlap", "all pairs", frame),
        ("overlap", "unseen response", frame.loc[~frame["seen_training_response"]]),
        ("overlap", "unseen author", frame.loc[~frame["seen_training_author"]]),
        ("overlap", "unseen thread", frame.loc[~frame["seen_training_thread"]]),
        (
            "overlap",
            "unseen author and thread",
            frame.loc[~frame["seen_training_author"] & ~frame["seen_training_thread"]],
        ),
    ]
    for value, group in frame.groupby("pair_source"):
        subsets.append(("pair source", str(value), group))
    frame = frame.copy()
    frame["response_length_group"] = pd.qcut(
        frame["response_words"],
        q=4,
        labels=["shortest", "short", "long", "longest"],
        duplicates="drop",
    )
    for value, group in frame.groupby("response_length_group", observed=True):
        subsets.append(("response length", str(value), group))
    for value, group in frame.groupby("community_group_proxy"):
        subsets.append(("community group", str(value), group))
    for value, group in frame.groupby("subreddit"):
        subsets.append(("subreddit", str(value), group))
    for value, group in frame.loc[frame["prior_comments"] >= 2].groupby("prior_participation_group"):
        subsets.append(("prior participation", str(value), group))
    for value, group in frame.groupby("early_hostile_language_group"):
        subsets.append(("early hostile language", str(value), group))

    rows = []
    for dimension, subgroup, group in subsets:
        if len(group) < 30 or group["manual_label"].nunique() < 2:
            continue
        metrics = binary_metrics(
            group["manual_label"].to_numpy(dtype=int),
            group[SELECTED_SCORE].to_numpy(dtype=float),
        )
        rows.append({"dimension": dimension, "subgroup": subgroup, **metrics})
    return pd.DataFrame(rows)


def predictor_subgroup_intervals(frame: pd.DataFrame, iterations: int, seed: int) -> pd.DataFrame:
    groups = [
        (
            "prior participation",
            "one prior subreddit",
            frame.loc[
                (frame["prior_comments"] >= 2)
                & frame["prior_cross_subreddit_participation"].eq(0)
            ],
        ),
        (
            "prior participation",
            "multiple prior subreddits",
            frame.loc[
                (frame["prior_comments"] >= 2)
                & frame["prior_cross_subreddit_participation"].eq(1)
            ],
        ),
        (
            "early hostile language",
            "no hostile language",
            frame.loc[frame["early_hostile_language_rate"].eq(0)],
        ),
        (
            "early hostile language",
            "any hostile language",
            frame.loc[frame["early_hostile_language_rate"].gt(0)],
        ),
    ]
    tables = []
    for index, (dimension, subgroup, group) in enumerate(groups):
        intervals = bootstrap_intervals(
            group["manual_label"].to_numpy(dtype=int),
            group[SELECTED_SCORE].to_numpy(dtype=float),
            iterations,
            seed + index + 1,
        )
        intervals.insert(0, "n", len(group))
        intervals.insert(0, "subgroup", subgroup)
        intervals.insert(0, "dimension", dimension)
        tables.append(intervals)
    return pd.concat(tables, ignore_index=True)


def run(args: argparse.Namespace) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = args.output_dir / "tables"
    metrics_dir = args.output_dir / "metrics"
    tables_dir.mkdir(exist_ok=True)
    metrics_dir.mkdir(exist_ok=True)

    frame, overlap = load_validation_frame(args)
    frame = attach_predictor_context(frame, args)
    target = frame["manual_label"].to_numpy(dtype=int)
    score = frame[SELECTED_SCORE].to_numpy(dtype=float)
    overall = binary_metrics(target, score)
    intervals = bootstrap_intervals(target, score, args.bootstrap_iterations, args.seed)
    calibration, calibration_table = calibration_summary(target, score)
    predicted = (score >= 0.5).astype(int)
    matrix = np.array(
        [
            [int(((target == 0) & (predicted == 0)).sum()), int(((target == 0) & (predicted == 1)).sum())],
            [int(((target == 1) & (predicted == 0)).sum()), int(((target == 1) & (predicted == 1)).sum())],
        ]
    )

    write_csv(tables_dir / "classifier_model_comparison.csv", model_comparison(frame))
    write_csv(tables_dir / "classifier_bootstrap_intervals.csv", intervals)
    write_csv(tables_dir / "classifier_threshold_sensitivity.csv", threshold_table(frame))
    write_csv(tables_dir / "classifier_subgroup_performance.csv", subgroup_table(frame))
    write_csv(
        tables_dir / "classifier_predictor_subgroup_intervals.csv",
        predictor_subgroup_intervals(frame, args.bootstrap_iterations, args.seed),
    )
    write_csv(tables_dir / "classifier_calibration_bins.csv", calibration_table)
    write_csv(
        tables_dir / "classifier_confusion_matrix.csv",
        pd.DataFrame(
            [
                {"actual": 0, "predicted_0": int(matrix[0, 0]), "predicted_1": int(matrix[0, 1])},
                {"actual": 1, "predicted_0": int(matrix[1, 0]), "predicted_1": int(matrix[1, 1])},
            ]
        ),
    )

    summary = {
        "run_status": "corrective_response_classifier_validation_complete",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "command": " ".join(sys.argv),
        "selected_score": SELECTED_SCORE,
        "manual_test_set": str(args.human_labels),
        "training_labels": str(args.training_labels),
        "model_scores": str(args.model_scores),
        "overall": overall,
        "calibration": calibration,
        "overlap_diagnostics": overlap,
        "predictor_context_diagnostics": {
            "eligible_one_prior_subreddit_pairs": int(
                (frame["prior_participation_group"] == "one prior subreddit").sum()
            ),
            "eligible_multiple_prior_subreddit_pairs": int(
                (frame["prior_participation_group"] == "multiple prior subreddits").sum()
            ),
            "pairs_without_early_hostile_language": int(
                (frame["early_hostile_language_group"] == "no hostile language").sum()
            ),
            "pairs_with_early_hostile_language": int(
                (frame["early_hostile_language_group"] == "any hostile language").sum()
            ),
        },
        "validation_scope": (
            "Pair-level human-coded test set; it does not independently validate maximum-score "
            "aggregation across multiple candidate targets in deployment."
        ),
    }
    write_json(metrics_dir / "run_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate the relation-aware corrective-response classifier.")
    parser.add_argument(
        "--human-labels",
        type=Path,
        default=Path(
            "outputs/manual_pair_relation_independent_audit3_combined_800_20260627T162524Z/"
            "manual_pair_annotations.csv"
        ),
    )
    parser.add_argument(
        "--training-labels",
        type=Path,
        default=Path(
            "outputs/manual_pair_relation_combined_6232_next_hard_plus_audit1_20260628T035000Z/"
            "manual_pair_annotations.csv"
        ),
    )
    parser.add_argument(
        "--model-scores",
        type=Path,
        default=Path(
            "outputs/pair_relation_ensemble_raw_models_on_audit3_20260628T020000Z/"
            "predictions/audit3_ensemble_raw_model_scores.csv"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/revised_corrective_response_validation_20260714T000000Z"),
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        default=Path(
            "outputs/full_comment_predictions_latest_pair_ensemble_20260628T142000Z/"
            "predictions/full_comment_predictions.csv"
        ),
    )
    parser.add_argument("--comments", type=Path, default=Path("data/interim/covidvaccine_comments.jsonl"))
    parser.add_argument("--submissions", type=Path, default=Path("data/interim/covidvaccine_submissions.jsonl"))
    parser.add_argument("--bootstrap-iterations", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260714)
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
