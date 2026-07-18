#!/usr/bin/env python3
"""Run sensitivity checks for the focused access-expression model."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from fit_revised_corrective_response_models import (
    coefficient_table,
    fit_two_way_logit,
    write_csv,
    write_json,
)


OUTCOME = "first_later_corrective_response"
DISCOURSE_TERMS = [
    "early_corrective_response_presence",
    "early_additional_corrections",
    "early_relation_only_diversity_z",
]
FOCAL_TERMS = ["prior_cross_community_participation", *DISCOURSE_TERMS]
NUISANCE_TERMS = (
    "early_cross_community_participant_share_z + "
    "early_ambient_hostile_language_rate_z + "
    "early_correction_reply_presence + "
    "early_correction_directed_hostility_presence + "
    "prior_corrective_response_rate + log_prior_comments + "
    "early_prior_history_coverage + early_relation_type_coverage + "
    "early_context_activity + early_mean_candidate_count_z + C(subreddit)"
)


def formula(
    access_term: str = "prior_cross_community_participation",
    extra_terms: str | None = None,
) -> str:
    focused_terms = " + ".join([access_term, *DISCOURSE_TERMS])
    terms = f"{focused_terms} + {NUISANCE_TERMS}"
    if extra_terms:
        terms = f"{terms} + {extra_terms}"
    return f"{OUTCOME} ~ {terms}"


def fit_specification(
    name: str,
    analysis: str,
    setting: str,
    frame: pd.DataFrame,
    model_formula: str,
    report_terms: list[str] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any], list[dict[str, Any]]]:
    print(f"Fitting {name} (n={len(frame):,})...", flush=True)
    result, covariance = fit_two_way_logit(model_formula, frame)
    coefficients = coefficient_table(result, covariance, name)
    fit_row = {
        "model": name,
        "analysis": analysis,
        "setting": setting,
        "n": int(result.nobs),
        "outcome_rate": float(frame[OUTCOME].mean()),
        "log_likelihood": float(result.llf),
        "aic": float(result.aic),
        "bic": float(result.bic),
        "mcfadden_pseudo_r2": float(result.prsquared),
        "converged": bool(result.mle_retvals.get("converged", False)),
    }
    focal_rows: list[dict[str, Any]] = []
    selected_terms = report_terms or FOCAL_TERMS
    for row in coefficients.loc[coefficients["term"].isin(selected_terms)].itertuples(index=False):
        focal_rows.append(
            {
                "model": name,
                "analysis": analysis,
                "setting": setting,
                "n": int(result.nobs),
                "outcome_rate": float(frame[OUTCOME].mean()),
                "term": row.term,
                "odds_ratio": float(row.odds_ratio),
                "ci_low": float(row.odds_ratio_ci_low),
                "ci_high": float(row.odds_ratio_ci_high),
                "p_value": float(row.p_value),
            }
        )
    return coefficients, fit_row, focal_rows


def run(args: argparse.Namespace) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = args.output_dir / "tables"
    metrics_dir = args.output_dir / "metrics"
    tables_dir.mkdir(exist_ok=True)
    metrics_dir.mkdir(exist_ok=True)

    base = pd.read_csv(args.analysis_frame, low_memory=False)
    coefficient_frames: list[pd.DataFrame] = []
    fit_rows: list[dict[str, Any]] = []
    focal_rows: list[dict[str, Any]] = []

    for threshold in [0.3, 0.4, 0.5, 0.6, 0.7]:
        frame = base.copy()
        frame[OUTCOME] = (frame["first_later_corrective_score"] >= threshold).astype(int)
        name = f"outcome_threshold_{threshold:.1f}"
        coefficients, fit_row, focal = fit_specification(
            name,
            "Outcome threshold",
            f"{threshold:.1f}",
            frame,
            formula(),
        )
        coefficient_frames.append(coefficients)
        fit_rows.append(fit_row)
        focal_rows.extend(focal)

    candidate = base.loc[base["first_later_candidate_count"] >= 1].copy()
    coefficients, fit_row, focal = fit_specification(
        "candidate_target_required",
        "Candidate target",
        "At least one candidate target",
        candidate,
        formula(),
    )
    coefficient_frames.append(coefficients)
    fit_rows.append(fit_row)
    focal_rows.extend(focal)

    candidate["two_candidate_targets"] = (
        candidate["first_later_candidate_count"] >= 2
    ).astype(int)
    coefficients, fit_row, focal = fit_specification(
        "candidate_multiplicity_adjusted",
        "Candidate target",
        "At least one target; adjusts for two targets",
        candidate,
        formula(extra_terms="two_candidate_targets"),
    )
    coefficient_frames.append(coefficients)
    fit_rows.append(fit_row)
    focal_rows.extend(focal)

    access_specs = [
        (
            "access_group_entropy",
            "Community-category entropy",
            "prior_community_group_entropy_z",
        ),
        (
            "access_subreddit_breadth",
            "Generic subreddit breadth",
            "prior_subreddit_breadth_log_z",
        ),
        (
            "access_subreddit_entropy",
            "Generic subreddit entropy",
            "prior_subreddit_entropy_z",
        ),
    ]
    for name, setting, access_term in access_specs:
        coefficients, fit_row, focal = fit_specification(
            name,
            "Access measure",
            setting,
            base,
            formula(access_term=access_term),
            report_terms=[access_term],
        )
        coefficient_frames.append(coefficients)
        fit_rows.append(fit_row)
        focal_rows.extend(focal)

    prior_context = pd.read_csv(args.prior_context_features, low_memory=False)
    context_columns = [
        "submission_id",
        "author_hash",
        "prior_context_correction_rate_z",
        "prior_context_relation_coverage",
    ]
    context_frame = base.merge(
        prior_context[context_columns],
        on=["submission_id", "author_hash"],
        how="left",
        validate="one_to_one",
    )
    if context_frame[context_columns[2:]].isna().any().any():
        raise ValueError("Prior-context features do not cover the complete analysis frame.")
    coefficients, fit_row, focal = fit_specification(
        "access_prior_context_adjusted",
        "Access measure",
        "Adds corrective-response rate in earlier entry contexts",
        context_frame,
        formula(
            extra_terms=(
                "prior_context_correction_rate_z + prior_context_relation_coverage"
            )
        ),
        report_terms=[
            "prior_cross_community_participation",
            "prior_context_correction_rate_z",
        ],
    )
    coefficient_frames.append(coefficients)
    fit_rows.append(fit_row)
    focal_rows.extend(focal)

    coefficients = pd.concat(coefficient_frames, ignore_index=True)
    fits = pd.DataFrame(fit_rows)
    focal = pd.DataFrame(focal_rows)
    write_csv(tables_dir / "sensitivity_model_coefficients.csv", coefficients)
    write_csv(tables_dir / "sensitivity_model_fit.csv", fits)
    write_csv(tables_dir / "sensitivity_focal_estimates.csv", focal)

    summary = {
        "run_status": "focused_supplementary_sensitivity_complete",
        "run_stage": args.run_stage,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "command": " ".join(sys.argv),
        "analysis_frame": str(args.analysis_frame),
        "output_dir": str(args.output_dir),
        "base_n": int(len(base)),
        "candidate_target_n": int(len(candidate)),
        "prior_context_features": str(args.prior_context_features),
        "thresholds": [0.3, 0.4, 0.5, 0.6, 0.7],
        "all_models_converged": bool(fits["converged"].all()),
        "model_count": int(len(fits)),
        "threshold_scope": (
            "The threshold check changes the focal response label. Early-discourse "
            "predictors retain the main-analysis threshold and construction."
        ),
    }
    write_json(metrics_dir / "run_summary.json", summary)
    (args.output_dir / "run.log").write_text(
        "\n".join(
            [
                "focused supplementary sensitivity analysis",
                f"generated_utc={summary['generated_utc']}",
                f"command={summary['command']}",
                f"base_n={summary['base_n']}",
                f"candidate_target_n={summary['candidate_target_n']}",
                f"all_models_converged={summary['all_models_converged']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run sensitivity checks for the focused manuscript model."
    )
    parser.add_argument("--analysis-frame", type=Path, required=True)
    parser.add_argument("--prior-context-features", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--run-stage",
        choices=["exploratory", "manuscript_candidate", "frozen"],
        default="frozen",
    )
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
