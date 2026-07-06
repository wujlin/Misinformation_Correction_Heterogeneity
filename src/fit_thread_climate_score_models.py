#!/usr/bin/env python3
"""Fit threshold-free thread-climate models using correction scores.

The original thread-climate model uses a binary predicted correction label.
This companion model keeps the same observable predictors but replaces the
outcome with a continuous score-based probability of at least one later
correction by the same author in the same thread.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from analyze_thread_climate import (
    attach_high_climate_flags,
    build_thread_author_rows,
    build_thread_profiles,
    build_user_profiles,
    load_comment_records,
    load_predictions,
)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def clipped_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    if np.isnan(score):
        return 0.0
    return min(max(score, 0.0), 1.0)


def build_score_outcomes(records: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, float]]:
    grouped: dict[tuple[str, str], dict[str, float]] = defaultdict(
        lambda: {
            "all_score_sum": 0.0,
            "all_score_max": 0.0,
            "all_non_correction_product": 1.0,
            "later_score_sum": 0.0,
            "later_score_max": 0.0,
            "later_non_correction_product": 1.0,
        }
    )
    for row in records:
        author = str(row.get("author") or "")
        submission_id = str(row.get("submission_id") or "")
        if not author or not submission_id:
            continue
        score = clipped_score(row.get("public_correction_score"))
        item = grouped[(submission_id, author)]
        item["all_score_sum"] += score
        item["all_score_max"] = max(item["all_score_max"], score)
        item["all_non_correction_product"] *= 1.0 - score
        if int(row.get("is_later_than_early_window", 0)) == 1:
            item["later_score_sum"] += score
            item["later_score_max"] = max(item["later_score_max"], score)
            item["later_non_correction_product"] *= 1.0 - score

    for item in grouped.values():
        item["all_score_any"] = 1.0 - item["all_non_correction_product"]
        item["later_score_any"] = 1.0 - item["later_non_correction_product"]
    return grouped


def prepare_later_dataframe(args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, Any]]:
    predictions = load_predictions(args.predictions)
    records = load_comment_records(args.comments, predictions)
    user_profiles = build_user_profiles(records)
    thread_profiles = build_thread_profiles(
        records, args.early_n, args.high_participation_author_threshold, user_profiles
    )
    climate_thresholds = attach_high_climate_flags(thread_profiles, args.min_comments_for_climate, args.climate_quantile)
    thread_author_rows = build_thread_author_rows(records, user_profiles, thread_profiles)
    score_outcomes = build_score_outcomes(records)

    for row in thread_author_rows:
        key = (str(row["submission_id"]), str(row["author"]))
        scores = score_outcomes.get(key, {})
        row["later_public_correction_score_sum"] = scores.get("later_score_sum", 0.0)
        row["later_public_correction_score_max"] = scores.get("later_score_max", 0.0)
        row["later_public_correction_score_any"] = scores.get("later_score_any", 0.0)
        row["all_public_correction_score_any"] = scores.get("all_score_any", 0.0)

    later_rows = [row for row in thread_author_rows if int(row["later_comments_in_thread"]) > 0]
    df = pd.DataFrame(later_rows)

    numeric_columns = [
        "later_corrected_in_thread",
        "later_public_correction_score_sum",
        "later_public_correction_score_max",
        "later_public_correction_score_any",
        "all_public_correction_score_any",
        "user_cross_group_observed",
        "high_thread_hostility_climate",
        "early_correction_norm_presence",
        "high_thread_anti_institutional_climate",
        "thread_comments",
        "thread_unique_authors",
        "user_comments",
        "user_subreddits_observed",
        "user_community_groups_observed",
        "user_subreddit_entropy",
        "user_community_group_entropy",
        "comments_in_thread",
        "later_comments_in_thread",
        "early_audience_cross_group_author_share",
        "early_audience_mean_community_group_entropy",
        "early_audience_dominant_community_group_entropy",
        "early_discursive_cue_entropy",
        "high_early_audience_structural_heterogeneity",
        "high_early_discursive_heterogeneity",
        "high_audience_structural_heterogeneity",
        "high_thread_discursive_heterogeneity",
    ]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)

    df["log_thread_comments"] = np.log1p(df["thread_comments"])
    df["log_user_comments"] = np.log1p(df["user_comments"])
    df["log_later_comments"] = np.log1p(df["later_comments_in_thread"])
    df["community_group_proxy"] = df["community_group_proxy"].astype(str)

    metadata = {
        "comments": len(records),
        "threads": len(thread_profiles),
        "thread_author_instances": len(thread_author_rows),
        "later_thread_author_instances": len(df),
        "binary_outcome_mean": float(df["later_corrected_in_thread"].mean()),
        "score_any_mean": float(df["later_public_correction_score_any"].mean()),
        "score_sum_mean": float(df["later_public_correction_score_sum"].mean()),
        "score_max_mean": float(df["later_public_correction_score_max"].mean()),
        "climate_thresholds": climate_thresholds,
    }
    return df, metadata


def coefficients_table(result: Any) -> list[dict[str, Any]]:
    conf = result.conf_int()
    rows = []
    for term in result.params.index:
        coef = float(result.params[term])
        ci_low = float(conf.loc[term, 0])
        ci_high = float(conf.loc[term, 1])
        rows.append(
            {
                "term": term,
                "coef": coef,
                "std_error": float(result.bse[term]),
                "t": float(result.tvalues[term]),
                "p_value": float(result.pvalues[term]),
                "ci_low": ci_low,
                "ci_high": ci_high,
            }
        )
    return rows


def heterogeneity_scenario_predictions(result: Any, df: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for audience_heterogeneity in [0, 1]:
        for cross_group in [0, 1]:
            scenario = df.copy()
            scenario["high_early_audience_structural_heterogeneity"] = audience_heterogeneity
            scenario["user_cross_group_observed"] = cross_group
            pred = result.predict(scenario)
            rows.append(
                {
                    "high_early_audience_structural_heterogeneity": audience_heterogeneity,
                    "user_cross_group_observed": cross_group,
                    "average_predicted_score_any": float(pred.mean()),
                }
            )
    return rows


def heterogeneity_scenario_contrasts(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lookup = {
        (
            int(row["high_early_audience_structural_heterogeneity"]),
            int(row["user_cross_group_observed"]),
        ): float(row["average_predicted_score_any"])
        for row in scenarios
    }
    rows = []
    for audience_heterogeneity in [0, 1]:
        non_cross = lookup[(audience_heterogeneity, 0)]
        cross = lookup[(audience_heterogeneity, 1)]
        rows.append(
            {
                "high_early_audience_structural_heterogeneity": audience_heterogeneity,
                "non_cross_predicted_score_any": non_cross,
                "cross_predicted_score_any": cross,
                "cross_minus_non_cross": cross - non_cross,
            }
        )
    return rows


def run(args: argparse.Namespace) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir = args.output_dir / "metrics"
    tables_dir = args.output_dir / "tables"
    metrics_dir.mkdir(exist_ok=True)
    tables_dir.mkdir(exist_ok=True)

    df, metadata = prepare_later_dataframe(args)
    anti_institutional_term = (
        "+ high_thread_anti_institutional_climate "
        if not args.exclude_anti_institutional
        else ""
    )
    heterogeneity_formula = (
        "later_public_correction_score_any ~ "
        "user_cross_group_observed * high_early_audience_structural_heterogeneity "
        "+ early_correction_norm_presence * high_thread_hostility_climate "
        "+ high_early_discursive_heterogeneity "
        f"{anti_institutional_term}"
        "+ log_thread_comments + log_user_comments + log_later_comments "
        "+ C(community_group_proxy)"
    )

    model = smf.ols(formula=heterogeneity_formula, data=df)
    result = model.fit(cov_type="cluster", cov_kwds={"groups": df["submission_id"]})

    coefficient_rows = coefficients_table(result)
    scenarios = heterogeneity_scenario_predictions(result, df)
    contrasts = heterogeneity_scenario_contrasts(scenarios)

    write_csv(
        tables_dir / "score_ols_coefficients.csv",
        coefficient_rows,
        ["term", "coef", "std_error", "t", "p_value", "ci_low", "ci_high"],
    )
    write_csv(
        tables_dir / "score_heterogeneity_scenario_predicted_values.csv",
        scenarios,
        [
            "high_early_audience_structural_heterogeneity",
            "user_cross_group_observed",
            "average_predicted_score_any",
        ],
    )
    write_csv(
        tables_dir / "score_heterogeneity_scenario_cross_group_contrasts.csv",
        contrasts,
        [
            "high_early_audience_structural_heterogeneity",
            "non_cross_predicted_score_any",
            "cross_predicted_score_any",
            "cross_minus_non_cross",
        ],
    )
    (metrics_dir / "score_ols_summary.txt").write_text(result.summary().as_text(), encoding="utf-8")

    summary = {
        "run_status": "score_based_ols_no_anti" if args.exclude_anti_institutional else "exploratory_score_based_ols",
        "predictions": str(args.predictions),
        "comments_path": str(args.comments),
        "output_dir": str(args.output_dir),
        "formula": heterogeneity_formula,
        "anti_institutional_included": not args.exclude_anti_institutional,
        "covariance": "clustered_by_submission_id",
        "nobs": int(result.nobs),
        "r2": float(result.rsquared),
        "adj_r2": float(result.rsquared_adj),
        "aic": float(result.aic),
        "bic": float(result.bic),
        "metadata": metadata,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(metrics_dir / "run_summary.json", summary)
    (args.output_dir / "run.log").write_text(
        "\n".join(
            [
                "thread climate score-based OLS run",
                f"generated_utc={summary['generated_utc']}",
                f"command={' '.join(sys.argv)}",
                f"formula={heterogeneity_formula}",
                f"nobs={summary['nobs']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fit threshold-free score-based thread-climate models.")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--comments", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--early-n", type=int, default=10)
    parser.add_argument("--high-participation-author-threshold", type=int, default=20)
    parser.add_argument("--min-comments-for-climate", type=int, default=5)
    parser.add_argument("--climate-quantile", type=float, default=0.75)
    parser.add_argument(
        "--exclude-anti-institutional",
        action="store_true",
        help="Exclude high_thread_anti_institutional_climate from model formulas.",
    )
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
