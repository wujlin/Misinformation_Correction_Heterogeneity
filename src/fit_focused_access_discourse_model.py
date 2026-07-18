#!/usr/bin/env python3
"""Fit the focused access and corrective-discourse model on the unified cohort."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from fit_revised_corrective_response_models import (
    coefficient_table,
    contrast_from_scenarios,
    fit_two_way_logit,
    prediction_and_gradient,
    write_csv,
    write_json,
)


OUTCOME = "first_later_corrective_response"


def fit_row(name: str, result: Any) -> dict[str, Any]:
    return {
        "model": name,
        "n": int(result.nobs),
        "log_likelihood": float(result.llf),
        "aic": float(result.aic),
        "bic": float(result.bic),
        "mcfadden_pseudo_r2": float(result.prsquared),
        "converged": bool(result.mle_retvals.get("converged", False)),
    }


def add_contrast(
    rows: list[dict[str, Any]],
    model_name: str,
    label: str,
    result: Any,
    covariance: np.ndarray,
    scenarios: list[tuple[float, pd.DataFrame]],
) -> None:
    estimate, se, low, high = contrast_from_scenarios(result, covariance, scenarios)
    rows.append(
        {
            "model": model_name,
            "contrast": label,
            "estimate_probability_points": estimate,
            "std_error": se,
            "ci_low": low,
            "ci_high": high,
        }
    )


def prediction_row(
    model_name: str,
    label: str,
    result: Any,
    covariance: np.ndarray,
    scenario: pd.DataFrame,
) -> dict[str, Any]:
    estimate, gradient = prediction_and_gradient(result, scenario)
    variance = float(gradient @ covariance @ gradient)
    se = float(np.sqrt(max(variance, 0.0)))
    return {
        "model": model_name,
        "scenario": label,
        "estimated_probability": estimate,
        "std_error": se,
        "ci_low": estimate - 1.96 * se,
        "ci_high": estimate + 1.96 * se,
    }


def run(args: argparse.Namespace) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = args.output_dir / "tables"
    metrics_dir = args.output_dir / "metrics"
    tables_dir.mkdir(exist_ok=True)
    metrics_dir.mkdir(exist_ok=True)

    frame = pd.read_csv(args.analysis_frame, low_memory=False)
    nuisance = (
        "early_cross_community_participant_share_z + early_ambient_hostile_language_rate_z + "
        "early_correction_reply_presence + early_correction_directed_hostility_presence + "
        "prior_corrective_response_rate + log_prior_comments + early_prior_history_coverage + "
        "early_relation_type_coverage + early_context_activity + "
        "early_mean_candidate_count_z + C(subreddit)"
    )
    temporal_nuisance = nuisance.replace("prior_corrective_response_rate + ", "")
    focused_terms = (
        "prior_cross_community_participation + early_corrective_response_presence + "
        "early_additional_corrections + early_relation_only_diversity_z"
    )
    formulas = {
        "focused_temporally_ordered": (
            f"{OUTCOME} ~ {focused_terms} + {temporal_nuisance}"
        ),
        "focused_main": (
            f"{OUTCOME} ~ {focused_terms} + {nuisance}"
        ),
        "focused_count_categories": (
            f"{OUTCOME} ~ prior_cross_community_participation + "
            "C(early_correction_count_capped) + early_relation_only_diversity_z + "
            f"{nuisance}"
        ),
        "focused_group_entropy": (
            f"{OUTCOME} ~ prior_community_group_entropy_z + "
            "early_corrective_response_presence + early_additional_corrections + "
            f"early_relation_only_diversity_z + {nuisance}"
        ),
    }

    coefficient_frames: list[pd.DataFrame] = []
    fit_rows: list[dict[str, Any]] = []
    fitted: dict[str, tuple[Any, np.ndarray]] = {}
    for model_name, formula in formulas.items():
        print(f"Fitting {model_name}...", flush=True)
        result, covariance = fit_two_way_logit(formula, frame)
        fitted[model_name] = (result, covariance)
        coefficient_frames.append(coefficient_table(result, covariance, model_name))
        fit_rows.append(fit_row(model_name, result))
    coefficients = pd.concat(coefficient_frames, ignore_index=True)

    main_result, main_covariance = fitted["focused_main"]
    contrast_rows: list[dict[str, Any]] = []
    cross_low = frame.copy()
    cross_high = frame.copy()
    cross_low["prior_cross_community_participation"] = 0
    cross_high["prior_cross_community_participation"] = 1
    add_contrast(
        contrast_rows,
        "focused_main",
        "prior cross-community participation: yes versus no",
        main_result,
        main_covariance,
        [(1.0, cross_high), (-1.0, cross_low)],
    )

    count_scenarios: dict[int, pd.DataFrame] = {}
    for correction_count in range(5):
        scenario = frame.copy()
        scenario["early_corrective_response_presence"] = int(correction_count > 0)
        scenario["early_additional_corrections"] = max(correction_count - 1, 0)
        count_scenarios[correction_count] = scenario
    add_contrast(
        contrast_rows,
        "focused_main",
        "one versus zero early corrective responses",
        main_result,
        main_covariance,
        [(1.0, count_scenarios[1]), (-1.0, count_scenarios[0])],
    )
    add_contrast(
        contrast_rows,
        "focused_main",
        "two versus one early corrective responses",
        main_result,
        main_covariance,
        [(1.0, count_scenarios[2]), (-1.0, count_scenarios[1])],
    )
    diversity_mean = frame.copy()
    diversity_high = frame.copy()
    diversity_mean["early_relation_only_diversity_z"] = 0.0
    diversity_high["early_relation_only_diversity_z"] = 1.0
    add_contrast(
        contrast_rows,
        "focused_main",
        "one-SD increase in early relation diversity",
        main_result,
        main_covariance,
        [(1.0, diversity_high), (-1.0, diversity_mean)],
    )

    prediction_rows = [
        prediction_row(
            "focused_main",
            f"{count} early corrective responses",
            main_result,
            main_covariance,
            scenario,
        )
        for count, scenario in count_scenarios.items()
    ]
    category_result, category_covariance = fitted["focused_count_categories"]
    for count in range(5):
        scenario = frame.copy()
        scenario["early_correction_count_capped"] = count
        prediction_rows.append(
            prediction_row(
                "focused_count_categories",
                f"{count if count < 4 else '4 or more'} early corrective responses",
                category_result,
                category_covariance,
                scenario,
            )
        )

    write_csv(tables_dir / "model_coefficients.csv", coefficients)
    write_csv(tables_dir / "model_fit.csv", pd.DataFrame(fit_rows))
    write_csv(tables_dir / "average_probability_contrasts.csv", pd.DataFrame(contrast_rows))
    write_csv(tables_dir / "correction_count_probabilities.csv", pd.DataFrame(prediction_rows))

    focal_terms = [
        "prior_cross_community_participation",
        "early_corrective_response_presence",
        "early_additional_corrections",
        "early_relation_only_diversity_z",
    ]
    focal = coefficients.loc[
        coefficients["model"].eq("focused_main") & coefficients["term"].isin(focal_terms)
    ].copy()
    summary = {
        "run_status": "focused_access_discourse_model_complete",
        "run_stage": "manuscript_candidate",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "command": " ".join(sys.argv),
        "output_dir": str(args.output_dir),
        "analysis_frame": str(args.analysis_frame),
        "n": int(len(frame)),
        "authors": int(frame["author_hash"].nunique()),
        "threads": int(frame["submission_id"].nunique()),
        "outcome_rate": float(frame[OUTCOME].mean()),
        "all_models_converged": bool(pd.DataFrame(fit_rows)["converged"].all()),
        "focused_odds_ratios": {
            row.term: {
                "odds_ratio": float(row.odds_ratio),
                "ci_low": float(row.odds_ratio_ci_low),
                "ci_high": float(row.odds_ratio_ci_high),
                "p_value": float(row.p_value),
            }
            for row in focal.itertuples(index=False)
        },
    }
    write_json(metrics_dir / "run_summary.json", summary)
    (args.output_dir / "run.log").write_text(
        "\n".join(
            [
                "focused access and corrective-discourse model",
                f"generated_utc={summary['generated_utc']}",
                f"command={summary['command']}",
                f"n={summary['n']}",
                f"all_models_converged={summary['all_models_converged']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fit the focused manuscript model.")
    parser.add_argument("--analysis-frame", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
