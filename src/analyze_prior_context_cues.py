#!/usr/bin/env python3
"""Test prior corrective-cue availability within the unified first-response cohort."""

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
import statsmodels.formula.api as smf
from scipy.stats import norm
from statsmodels.stats.sandwich_covariance import cov_cluster_2groups

from analyze_core_story_deep_dive import stored_probability_entropy
from fit_revised_corrective_response_models import (
    NO_IDENTIFIED_RELATION_COLUMN,
    RELATION_PROBABILITY_COLUMNS,
    coefficient_table,
    contrast_from_scenarios,
    fit_two_way_logit,
    load_comments,
    stable_id,
    standardize,
    write_csv,
    write_json,
)


OUTCOME = "first_later_corrective_response"


def build_entry_context_events(
    comments: pd.DataFrame,
    focal_author_hashes: set[str],
    opening_window: int,
) -> pd.DataFrame:
    """Describe the opening context available before each author's first thread entry."""
    relation_columns = RELATION_PROBABILITY_COLUMNS + [NO_IDENTIFIED_RELATION_COLUMN]
    rows: list[dict[str, Any]] = []
    for submission_id, thread in comments.groupby("submission_id", sort=False):
        ordered = thread.sort_values(["created_utc", "comment_id"]).reset_index(drop=True)
        first_positions = np.flatnonzero(~ordered["author"].duplicated().to_numpy())
        for position in first_positions:
            entry = ordered.iloc[position]
            author_hash = stable_id(str(entry["author"]))
            if author_hash not in focal_author_hashes:
                continue
            context_end = min(int(position), opening_window)
            context = ordered.iloc[:context_end]
            context_size = int(len(context))
            if context_size:
                correction_count = int(context["public_correction_pred"].sum())
                mean_relation = context[relation_columns].to_numpy(dtype=float).mean(axis=0)
                relation_diversity = stored_probability_entropy(mean_relation)
                relation_coverage = float(context["relation_type_available"].mean())
            else:
                correction_count = 0
                relation_diversity = 0.0
                relation_coverage = 0.0
            rows.append(
                {
                    "author_hash": author_hash,
                    "entry_submission_id": str(submission_id),
                    "entry_time": float(entry["created_utc"]),
                    "entry_context_size": context_size,
                    "entry_context_eligible": int(context_size > 0),
                    "entry_opening_window_complete": int(context_size == opening_window),
                    "entry_context_correction_count": correction_count,
                    "entry_context_correction_presence": int(correction_count > 0),
                    "entry_context_relation_diversity": relation_diversity,
                    "entry_context_relation_coverage": relation_coverage,
                }
            )
    return pd.DataFrame(rows)


def cumulative_before(values: np.ndarray, cutoffs: np.ndarray) -> np.ndarray:
    cumulative = np.cumsum(values, dtype=float)
    result = np.zeros(len(cutoffs), dtype=float)
    observed = cutoffs > 0
    result[observed] = cumulative[cutoffs[observed] - 1]
    return result


def aggregate_prior_contexts(
    focal_frame: pd.DataFrame,
    events: pd.DataFrame,
) -> pd.DataFrame:
    event_groups = {
        author_hash: group.sort_values(["entry_time", "entry_submission_id"])
        for author_hash, group in events.groupby("author_hash", sort=False)
    }
    rows: list[pd.DataFrame] = []
    for author_hash, focal in focal_frame.groupby("author_hash", sort=False):
        focal = focal.sort_values(["thread_start_utc", "submission_id"]).copy()
        author_events = event_groups.get(author_hash)
        if author_events is None or author_events.empty:
            cutoffs = np.zeros(len(focal), dtype=int)
            author_events = pd.DataFrame(
                {
                    "entry_time": [],
                    "entry_context_eligible": [],
                    "entry_opening_window_complete": [],
                    "entry_context_size": [],
                    "entry_context_correction_count": [],
                    "entry_context_correction_presence": [],
                    "entry_context_relation_diversity": [],
                    "entry_context_relation_coverage": [],
                }
            )
        else:
            cutoffs = np.searchsorted(
                author_events["entry_time"].to_numpy(dtype=float),
                focal["thread_start_utc"].to_numpy(dtype=float),
                side="left",
            )
        eligible = cumulative_before(
            author_events["entry_context_eligible"].to_numpy(dtype=float), cutoffs
        )
        complete = cumulative_before(
            author_events["entry_opening_window_complete"].to_numpy(dtype=float), cutoffs
        )
        context_comments = cumulative_before(
            author_events["entry_context_size"].to_numpy(dtype=float), cutoffs
        )
        corrections = cumulative_before(
            author_events["entry_context_correction_count"].to_numpy(dtype=float), cutoffs
        )
        correction_contexts = cumulative_before(
            author_events["entry_context_correction_presence"].to_numpy(dtype=float), cutoffs
        )
        diversity_total = cumulative_before(
            (
                author_events["entry_context_relation_diversity"]
                * author_events["entry_context_eligible"]
            ).to_numpy(dtype=float),
            cutoffs,
        )
        relation_coverage_total = cumulative_before(
            (
                author_events["entry_context_relation_coverage"]
                * author_events["entry_context_eligible"]
            ).to_numpy(dtype=float),
            cutoffs,
        )
        focal["prior_entry_contexts"] = cutoffs
        focal["prior_eligible_entry_contexts"] = eligible
        focal["prior_entry_context_coverage"] = np.divide(
            eligible,
            cutoffs,
            out=np.zeros(len(focal), dtype=float),
            where=cutoffs > 0,
        )
        focal["prior_complete_opening_context_share"] = np.divide(
            complete,
            eligible,
            out=np.zeros(len(focal), dtype=float),
            where=eligible > 0,
        )
        focal["prior_context_comment_count"] = context_comments
        focal["prior_context_available_corrections"] = corrections
        focal["prior_context_correction_presence_share"] = np.divide(
            correction_contexts,
            eligible,
            out=np.zeros(len(focal), dtype=float),
            where=eligible > 0,
        )
        focal["prior_context_correction_rate"] = np.divide(
            corrections,
            context_comments,
            out=np.zeros(len(focal), dtype=float),
            where=context_comments > 0,
        )
        focal["prior_context_relation_diversity"] = np.divide(
            diversity_total,
            eligible,
            out=np.zeros(len(focal), dtype=float),
            where=eligible > 0,
        )
        focal["prior_context_relation_coverage"] = np.divide(
            relation_coverage_total,
            eligible,
            out=np.zeros(len(focal), dtype=float),
            where=eligible > 0,
        )
        rows.append(focal)
    return pd.concat(rows, ignore_index=True)


def fit_two_way_ols(formula: str, frame: pd.DataFrame) -> tuple[Any, np.ndarray]:
    result = smf.ols(formula=formula, data=frame).fit()
    thread_group = pd.factorize(frame["submission_id"])[0]
    author_group = pd.factorize(frame["author_hash"])[0]
    covariance, _, _ = cov_cluster_2groups(result, thread_group, author_group, use_correction=True)
    return result, np.asarray(covariance, dtype=float)


def linear_coefficient_table(result: Any, covariance: np.ndarray, model_name: str) -> pd.DataFrame:
    params = np.asarray(result.params, dtype=float)
    standard_errors = np.sqrt(np.maximum(np.diag(covariance), 0.0))
    z_values = params / standard_errors
    p_values = 2.0 * norm.sf(np.abs(z_values))
    return pd.DataFrame(
        {
            "model": model_name,
            "term": result.params.index,
            "coefficient": params,
            "std_error_two_way_clustered": standard_errors,
            "z": z_values,
            "p_value": p_values,
            "ci_low": params - 1.96 * standard_errors,
            "ci_high": params + 1.96 * standard_errors,
        }
    )


def logit_fit_row(name: str, result: Any) -> dict[str, Any]:
    return {
        "model": name,
        "n": int(result.nobs),
        "log_likelihood": float(result.llf),
        "aic": float(result.aic),
        "bic": float(result.bic),
        "mcfadden_pseudo_r2": float(result.prsquared),
        "converged": bool(result.mle_retvals.get("converged", False)),
    }


def run(args: argparse.Namespace) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = args.output_dir / "tables"
    metrics_dir = args.output_dir / "metrics"
    tables_dir.mkdir(exist_ok=True)
    metrics_dir.mkdir(exist_ok=True)

    print("Loading the unified analysis frame...", flush=True)
    base = pd.read_csv(args.analysis_frame, low_memory=False)
    focal_keys = base[["submission_id", "author_hash", "thread_start_utc"]].copy()
    print("Loading comment and relation predictions...", flush=True)
    comments = load_comments(args)
    print("Constructing author entry contexts...", flush=True)
    events = build_entry_context_events(
        comments,
        set(base["author_hash"].astype(str)),
        args.opening_window,
    )
    print("Aggregating contexts observed before each focal thread...", flush=True)
    features = aggregate_prior_contexts(focal_keys, events)
    feature_columns = [
        column
        for column in features.columns
        if column not in {"thread_start_utc"}
    ]
    frame = base.merge(
        features[feature_columns],
        on=["submission_id", "author_hash"],
        how="left",
        validate="one_to_one",
    )
    if frame["prior_entry_contexts"].isna().any():
        raise ValueError("Prior-context aggregation did not cover every focal observation")
    frame["prior_entry_contexts_log"] = np.log1p(frame["prior_entry_contexts"])
    frame["prior_context_available_corrections_log"] = np.log1p(
        frame["prior_context_available_corrections"]
    )
    standard_columns = [
        "prior_entry_contexts_log",
        "prior_context_available_corrections_log",
        "prior_context_correction_presence_share",
        "prior_context_correction_rate",
        "prior_context_relation_diversity",
    ]
    frame, moments = standardize(frame, standard_columns)

    nuisance = (
        "early_cross_community_participant_share_z + early_ambient_hostile_language_rate_z + "
        "early_correction_reply_presence + early_correction_directed_hostility_presence + "
        "prior_corrective_response_rate + log_prior_comments + early_prior_history_coverage + "
        "early_relation_type_coverage + early_context_activity + C(subreddit)"
    )
    core = (
        "prior_cross_community_participation * early_cross_community_participant_share_z + "
        "early_corrective_response_presence + early_response_relation_diversity_z"
    )
    formulas = {
        "baseline_replication": f"{OUTCOME} ~ {core} + {nuisance}",
        "prior_context_presence": (
            f"{OUTCOME} ~ {core} + prior_context_correction_presence_share_z + "
            "prior_entry_context_coverage + prior_context_relation_coverage + "
            f"prior_entry_contexts_log_z + {nuisance}"
        ),
        "prior_context_rate": (
            f"{OUTCOME} ~ {core} + prior_context_correction_rate_z + "
            "prior_entry_context_coverage + prior_context_relation_coverage + "
            f"prior_entry_contexts_log_z + {nuisance}"
        ),
        "prior_context_count": (
            f"{OUTCOME} ~ {core} + prior_context_available_corrections_log_z + "
            "prior_entry_context_coverage + prior_context_relation_coverage + "
            f"prior_entry_contexts_log_z + {nuisance}"
        ),
        "prior_context_joint": (
            f"{OUTCOME} ~ {core} + prior_context_correction_presence_share_z + "
            "prior_context_relation_diversity_z + prior_entry_context_coverage + "
            f"prior_context_relation_coverage + prior_entry_contexts_log_z + {nuisance}"
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
        fit_rows.append(logit_fit_row(model_name, result))
    coefficients = pd.concat(coefficient_frames, ignore_index=True)

    pathway_formulas = {
        "cross_group_to_prior_correction_context": (
            "prior_context_correction_presence_share_z ~ "
            "prior_cross_community_participation + log_prior_comments + "
            "prior_entry_context_coverage + prior_entry_contexts_log_z + C(subreddit)"
        ),
        "cross_group_to_prior_relation_diversity": (
            "prior_context_relation_diversity_z ~ prior_cross_community_participation + "
            "log_prior_comments + prior_entry_context_coverage + "
            "prior_entry_contexts_log_z + C(subreddit)"
        ),
    }
    pathway_frames: list[pd.DataFrame] = []
    for model_name, formula in pathway_formulas.items():
        print(f"Fitting {model_name}...", flush=True)
        result, covariance = fit_two_way_ols(formula, frame)
        pathway_frames.append(linear_coefficient_table(result, covariance, model_name))
    pathway_coefficients = pd.concat(pathway_frames, ignore_index=True)

    contrast_rows: list[dict[str, Any]] = []
    joint_result, joint_covariance = fitted["prior_context_joint"]
    for variable, label in [
        (
            "prior_context_correction_presence_share_z",
            "one-SD increase in prior correction-context presence share",
        ),
        (
            "prior_context_relation_diversity_z",
            "one-SD increase in prior entry-context relation diversity",
        ),
    ]:
        mean = frame.copy()
        high = frame.copy()
        mean[variable] = 0.0
        high[variable] = 1.0
        estimate, se, low, high_ci = contrast_from_scenarios(
            joint_result,
            joint_covariance,
            [(1.0, high), (-1.0, mean)],
        )
        contrast_rows.append(
            {
                "model": "prior_context_joint",
                "contrast": label,
                "estimate_probability_points": estimate,
                "std_error": se,
                "ci_low": low,
                "ci_high": high_ci,
            }
        )

    context_descriptives = (
        frame.groupby("prior_cross_community_participation")
        .agg(
            observations=(OUTCOME, "size"),
            outcome_rate=(OUTCOME, "mean"),
            mean_prior_entry_contexts=("prior_entry_contexts", "mean"),
            mean_entry_context_coverage=("prior_entry_context_coverage", "mean"),
            mean_prior_correction_context_share=(
                "prior_context_correction_presence_share",
                "mean",
            ),
            mean_prior_context_correction_rate=("prior_context_correction_rate", "mean"),
            mean_prior_context_relation_diversity=(
                "prior_context_relation_diversity",
                "mean",
            ),
        )
        .reset_index()
    )
    feature_output_columns = [
        "submission_id",
        "author_hash",
        *[
            column
            for column in frame.columns
            if column.startswith("prior_entry_") or column.startswith("prior_context_")
        ],
    ]
    feature_output_columns = list(dict.fromkeys(feature_output_columns))
    write_csv(tables_dir / "model_coefficients.csv", coefficients)
    write_csv(tables_dir / "model_fit.csv", pd.DataFrame(fit_rows))
    write_csv(tables_dir / "pathway_coefficients.csv", pathway_coefficients)
    write_csv(tables_dir / "probability_contrasts.csv", pd.DataFrame(contrast_rows))
    write_csv(tables_dir / "context_descriptives_by_access.csv", context_descriptives)
    write_csv(tables_dir / "focal_prior_context_features.csv", frame[feature_output_columns])
    write_csv(tables_dir / "entry_context_events.csv", events)

    summary = {
        "run_status": "prior_context_cue_analysis_complete",
        "run_stage": "exploratory",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "command": " ".join(sys.argv),
        "output_dir": str(args.output_dir),
        "analysis_frame": str(args.analysis_frame),
        "opening_window": args.opening_window,
        "n": int(len(frame)),
        "authors": int(frame["author_hash"].nunique()),
        "threads": int(frame["submission_id"].nunique()),
        "entry_context_events": int(len(events)),
        "all_logit_models_converged": bool(pd.DataFrame(fit_rows)["converged"].all()),
        "standardization_moments": moments,
    }
    write_json(metrics_dir / "run_summary.json", summary)
    (args.output_dir / "run.log").write_text(
        "\n".join(
            [
                "prior context cue analysis",
                f"generated_utc={summary['generated_utc']}",
                f"command={summary['command']}",
                f"n={summary['n']}",
                f"entry_context_events={summary['entry_context_events']}",
                f"all_logit_models_converged={summary['all_logit_models_converged']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze prior corrective-cue availability.")
    parser.add_argument("--analysis-frame", type=Path, required=True)
    parser.add_argument(
        "--predictions",
        type=Path,
        default=Path(
            "outputs/full_comment_predictions_latest_pair_ensemble_20260628T142000Z/"
            "predictions/full_comment_predictions.csv"
        ),
    )
    parser.add_argument(
        "--relation-type-predictions",
        type=Path,
        default=Path(
            "outputs/pair_relation_full_candidate_scores_latest22_20260628T125500Z/"
            "type6232/predictions/pair_candidate_type_predictions.csv"
        ),
    )
    parser.add_argument("--comments", type=Path, default=Path("data/interim/covidvaccine_comments.jsonl"))
    parser.add_argument(
        "--submissions",
        type=Path,
        default=Path("data/interim/covidvaccine_submissions.jsonl"),
    )
    parser.add_argument("--opening-window", type=int, default=10)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
