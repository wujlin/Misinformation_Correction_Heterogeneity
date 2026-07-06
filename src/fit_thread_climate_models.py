#!/usr/bin/env python3
"""Fit exploratory observational models for later public correction.

The model is descriptive. It estimates associations between observable thread
climate, cross-community participation, and later predicted public correction.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
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


def prepare_later_dataframe(args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, Any]]:
    predictions = load_predictions(args.predictions)
    records = load_comment_records(args.comments, predictions)
    user_profiles = build_user_profiles(records)
    thread_profiles = build_thread_profiles(
        records, args.early_n, args.high_participation_author_threshold, user_profiles
    )
    climate_thresholds = attach_high_climate_flags(thread_profiles, args.min_comments_for_climate, args.climate_quantile)
    thread_author_rows = build_thread_author_rows(records, user_profiles, thread_profiles)
    later_rows = [row for row in thread_author_rows if int(row["later_comments_in_thread"]) > 0]
    df = pd.DataFrame(later_rows)

    numeric_columns = [
        "later_corrected_in_thread",
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
    df["community_group_proxy"] = df["community_group_proxy"].astype(str)

    metadata = {
        "comments": len(records),
        "threads": len(thread_profiles),
        "thread_author_instances": len(thread_author_rows),
        "later_thread_author_instances": len(df),
        "climate_thresholds": climate_thresholds,
    }
    return df, metadata


def coefficients_table(result: Any) -> list[dict[str, Any]]:
    conf = result.conf_int()
    rows = []
    for term in result.params.index:
        coef = float(result.params[term])
        se = float(result.bse[term])
        ci_low = float(conf.loc[term, 0])
        ci_high = float(conf.loc[term, 1])
        rows.append(
            {
                "term": term,
                "coef": coef,
                "std_error": se,
                "z": float(result.tvalues[term]),
                "p_value": float(result.pvalues[term]),
                "odds_ratio": float(np.exp(coef)),
                "odds_ratio_ci_low": float(np.exp(ci_low)),
                "odds_ratio_ci_high": float(np.exp(ci_high)),
            }
        )
    return rows


def scenario_predictions(result: Any, df: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for early_norm in [0, 1]:
        for high_hostility in [0, 1]:
            for cross_group in [0, 1]:
                scenario = df.copy()
                scenario["early_correction_norm_presence"] = early_norm
                scenario["high_thread_hostility_climate"] = high_hostility
                scenario["user_cross_group_observed"] = cross_group
                pred = result.predict(scenario)
                rows.append(
                    {
                        "early_correction_norm_presence": early_norm,
                        "high_thread_hostility_climate": high_hostility,
                        "user_cross_group_observed": cross_group,
                        "average_predicted_probability": float(pred.mean()),
                    }
                )
    return rows


def scenario_contrasts(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lookup = {
        (
            int(row["early_correction_norm_presence"]),
            int(row["high_thread_hostility_climate"]),
            int(row["user_cross_group_observed"]),
        ): float(row["average_predicted_probability"])
        for row in scenarios
    }
    rows = []
    for early_norm in [0, 1]:
        for high_hostility in [0, 1]:
            non_cross = lookup[(early_norm, high_hostility, 0)]
            cross = lookup[(early_norm, high_hostility, 1)]
            rows.append(
                {
                    "early_correction_norm_presence": early_norm,
                    "high_thread_hostility_climate": high_hostility,
                    "non_cross_predicted_probability": non_cross,
                    "cross_predicted_probability": cross,
                    "cross_minus_non_cross": cross - non_cross,
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
                    "average_predicted_probability": float(pred.mean()),
                }
            )
    return rows


def heterogeneity_scenario_contrasts(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lookup = {
        (
            int(row["high_early_audience_structural_heterogeneity"]),
            int(row["user_cross_group_observed"]),
        ): float(row["average_predicted_probability"])
        for row in scenarios
    }
    rows = []
    for audience_heterogeneity in [0, 1]:
        non_cross = lookup[(audience_heterogeneity, 0)]
        cross = lookup[(audience_heterogeneity, 1)]
        rows.append(
            {
                "high_early_audience_structural_heterogeneity": audience_heterogeneity,
                "non_cross_predicted_probability": non_cross,
                "cross_predicted_probability": cross,
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
    formula = (
        "later_corrected_in_thread ~ "
        "user_cross_group_observed * high_thread_hostility_climate * early_correction_norm_presence "
        f"{anti_institutional_term}"
        "+ log_thread_comments + log_user_comments "
        "+ C(community_group_proxy)"
    )
    heterogeneity_formula = (
        "later_corrected_in_thread ~ "
        "user_cross_group_observed * high_early_audience_structural_heterogeneity "
        "+ early_correction_norm_presence * high_thread_hostility_climate "
        "+ high_early_discursive_heterogeneity "
        f"{anti_institutional_term}"
        "+ log_thread_comments + log_user_comments "
        "+ C(community_group_proxy)"
    )
    model = smf.logit(formula=formula, data=df)
    result = model.fit(
        disp=False,
        maxiter=args.maxiter,
        cov_type="cluster",
        cov_kwds={"groups": df["submission_id"]},
    )
    heterogeneity_model = smf.logit(formula=heterogeneity_formula, data=df)
    heterogeneity_result = heterogeneity_model.fit(
        disp=False,
        maxiter=args.maxiter,
        cov_type="cluster",
        cov_kwds={"groups": df["submission_id"]},
    )

    coefficient_rows = coefficients_table(result)
    scenarios = scenario_predictions(result, df)
    contrasts = scenario_contrasts(scenarios)
    heterogeneity_coefficient_rows = coefficients_table(heterogeneity_result)
    heterogeneity_scenarios = heterogeneity_scenario_predictions(heterogeneity_result, df)
    heterogeneity_contrasts = heterogeneity_scenario_contrasts(heterogeneity_scenarios)

    write_csv(
        tables_dir / "logit_coefficients.csv",
        coefficient_rows,
        [
            "term",
            "coef",
            "std_error",
            "z",
            "p_value",
            "odds_ratio",
            "odds_ratio_ci_low",
            "odds_ratio_ci_high",
        ],
    )
    write_csv(
        tables_dir / "scenario_predicted_probabilities.csv",
        scenarios,
        [
            "early_correction_norm_presence",
            "high_thread_hostility_climate",
            "user_cross_group_observed",
            "average_predicted_probability",
        ],
    )
    write_csv(
        tables_dir / "scenario_cross_group_contrasts.csv",
        contrasts,
        [
            "early_correction_norm_presence",
            "high_thread_hostility_climate",
            "non_cross_predicted_probability",
            "cross_predicted_probability",
            "cross_minus_non_cross",
        ],
    )
    write_csv(
        tables_dir / "heterogeneity_logit_coefficients.csv",
        heterogeneity_coefficient_rows,
        [
            "term",
            "coef",
            "std_error",
            "z",
            "p_value",
            "odds_ratio",
            "odds_ratio_ci_low",
            "odds_ratio_ci_high",
        ],
    )
    write_csv(
        tables_dir / "heterogeneity_scenario_predicted_probabilities.csv",
        heterogeneity_scenarios,
        [
            "high_early_audience_structural_heterogeneity",
            "user_cross_group_observed",
            "average_predicted_probability",
        ],
    )
    write_csv(
        tables_dir / "heterogeneity_scenario_cross_group_contrasts.csv",
        heterogeneity_contrasts,
        [
            "high_early_audience_structural_heterogeneity",
            "non_cross_predicted_probability",
            "cross_predicted_probability",
            "cross_minus_non_cross",
        ],
    )
    (metrics_dir / "logit_summary.txt").write_text(result.summary().as_text(), encoding="utf-8")
    (metrics_dir / "heterogeneity_logit_summary.txt").write_text(
        heterogeneity_result.summary().as_text(), encoding="utf-8"
    )

    summary = {
        "run_status": "observational_logit_no_anti" if args.exclude_anti_institutional else "exploratory_observational_logit",
        "predictions": str(args.predictions),
        "comments_path": str(args.comments),
        "output_dir": str(args.output_dir),
        "formula": formula,
        "heterogeneity_formula": heterogeneity_formula,
        "anti_institutional_included": not args.exclude_anti_institutional,
        "covariance": "clustered_by_submission_id",
        "maxiter": args.maxiter,
        "nobs": int(result.nobs),
        "outcome_mean": float(df["later_corrected_in_thread"].mean()),
        "pseudo_r2": float(result.prsquared),
        "aic": float(result.aic),
        "bic": float(result.bic),
        "converged": bool(result.mle_retvals.get("converged", False)),
        "heterogeneity_nobs": int(heterogeneity_result.nobs),
        "heterogeneity_pseudo_r2": float(heterogeneity_result.prsquared),
        "heterogeneity_aic": float(heterogeneity_result.aic),
        "heterogeneity_bic": float(heterogeneity_result.bic),
        "heterogeneity_converged": bool(heterogeneity_result.mle_retvals.get("converged", False)),
        "metadata": metadata,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(metrics_dir / "run_summary.json", summary)
    (args.output_dir / "run.log").write_text(
        "\n".join(
            [
                "thread climate later-correction logit run",
                f"generated_utc={summary['generated_utc']}",
                f"command={' '.join(sys.argv)}",
                f"formula={formula}",
                f"heterogeneity_formula={heterogeneity_formula}",
                f"nobs={summary['nobs']}",
                f"converged={summary['converged']}",
                f"heterogeneity_converged={summary['heterogeneity_converged']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fit exploratory later-correction logit models.")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--comments", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--early-n", type=int, default=10)
    parser.add_argument("--high-participation-author-threshold", type=int, default=20)
    parser.add_argument("--min-comments-for-climate", type=int, default=5)
    parser.add_argument("--climate-quantile", type=float, default=0.75)
    parser.add_argument("--maxiter", type=int, default=200)
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
