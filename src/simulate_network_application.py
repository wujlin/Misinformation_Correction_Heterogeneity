#!/usr/bin/env python3
"""Map the focused corrective-response model onto observed Reddit networks.

The simulation preserves the observed thread membership, reply edges, comment
times, and focal first-response nodes. It varies the three focal predictors and
reports how model-implied response probabilities aggregate into correction
coverage across the observed discussion networks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from patsy import build_design_matrices
from scipy.sparse import csr_matrix
from scipy.special import expit

from fit_revised_corrective_response_models import (
    coefficient_table,
    fit_two_way_logit,
    write_csv,
    write_json,
)


OUTCOME = "first_later_corrective_response"
FORMULA = (
    f"{OUTCOME} ~ prior_cross_community_participation + "
    "early_corrective_response_presence + early_additional_corrections + "
    "early_relation_only_diversity_z + "
    "early_cross_community_participant_share_z + "
    "early_ambient_hostile_language_rate_z + "
    "early_correction_reply_presence + "
    "early_correction_directed_hostility_presence + "
    "prior_corrective_response_rate + log_prior_comments + "
    "early_prior_history_coverage + early_relation_type_coverage + "
    "early_context_activity + early_mean_candidate_count_z + C(subreddit)"
)

SCENARIOS = [
    "baseline",
    "wider_access",
    "one_more_early_correction",
    "broader_early_relations",
    "combined",
]

METRICS = [
    "corrective_response_rate",
    "threads_with_correction",
    "later_comments_after_correction",
    "same_branch_reach",
]


def normalize_id(value: Any) -> str:
    identifier = str(value or "").strip().lower()
    if identifier.startswith(("t1_", "t3_")):
        return identifier[3:]
    return identifier


def stable_id(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def positive_semidefinite(covariance: np.ndarray) -> tuple[np.ndarray, int]:
    symmetric = (covariance + covariance.T) / 2.0
    values, vectors = np.linalg.eigh(symmetric)
    clipped = int(np.sum(values < 0))
    values = np.maximum(values, 0.0)
    return (vectors * values) @ vectors.T, clipped


def design_matrix(result: Any, frame: pd.DataFrame) -> np.ndarray:
    design = build_design_matrices(
        [result.model.data.design_info],
        frame,
        return_type="dataframe",
    )[0]
    return np.asarray(design, dtype=float)


def add_one_early_correction(frame: pd.DataFrame) -> pd.DataFrame:
    scenario = frame.copy()
    count = (
        scenario["early_corrective_response_presence"].astype(int)
        + scenario["early_additional_corrections"].astype(int)
    )
    increased = np.minimum(count + 1, 10)
    scenario["early_corrective_response_presence"] = (increased > 0).astype(int)
    scenario["early_additional_corrections"] = np.maximum(increased - 1, 0)
    return scenario


def broaden_early_relations(frame: pd.DataFrame) -> pd.DataFrame:
    scenario = frame.copy()
    upper = float(frame["early_relation_only_diversity_z"].max())
    scenario["early_relation_only_diversity_z"] = np.minimum(
        scenario["early_relation_only_diversity_z"].astype(float) + 1.0,
        upper,
    )
    return scenario


def build_scenario_designs(result: Any, frame: pd.DataFrame) -> tuple[dict[str, Any], dict[str, Any]]:
    access_share = float(frame["prior_cross_community_participation"].mean())
    target_share = min(access_share * 2.0, 1.0)
    expansion_probability = (target_share - access_share) / max(1.0 - access_share, 1e-12)
    access_eligible = frame["prior_cross_community_participation"].eq(0).to_numpy()

    access_high = frame.copy()
    access_high.loc[access_eligible, "prior_cross_community_participation"] = 1

    correction = add_one_early_correction(frame)
    diversity = broaden_early_relations(frame)
    combined = broaden_early_relations(correction)
    combined_access_high = combined.copy()
    combined_access_high.loc[access_eligible, "prior_cross_community_participation"] = 1

    designs = {
        "baseline": design_matrix(result, frame),
        "access_high": design_matrix(result, access_high),
        "one_more_early_correction": design_matrix(result, correction),
        "broader_early_relations": design_matrix(result, diversity),
        "combined": design_matrix(result, combined),
        "combined_access_high": design_matrix(result, combined_access_high),
    }
    metadata = {
        "observed_access_share": access_share,
        "target_access_share": target_share,
        "access_expansion_probability_among_eligible_records": expansion_probability,
        "diversity_shift_standard_deviations": 1.0,
        "diversity_upper_bound": float(frame["early_relation_only_diversity_z"].max()),
        "added_early_corrective_responses": 1,
    }
    arrays = {
        "designs": designs,
        "access_eligible": access_eligible,
        "access_expansion_probability": expansion_probability,
    }
    return arrays, metadata


def scenario_probabilities(beta: np.ndarray, arrays: dict[str, Any]) -> dict[str, np.ndarray]:
    designs = arrays["designs"]
    access_eligible = arrays["access_eligible"]
    expansion_probability = float(arrays["access_expansion_probability"])

    baseline = expit(designs["baseline"] @ beta)
    access_high = expit(designs["access_high"] @ beta)
    wider_access = baseline.copy()
    wider_access[access_eligible] = (
        (1.0 - expansion_probability) * baseline[access_eligible]
        + expansion_probability * access_high[access_eligible]
    )

    correction = expit(designs["one_more_early_correction"] @ beta)
    diversity = expit(designs["broader_early_relations"] @ beta)
    combined = expit(designs["combined"] @ beta)
    combined_high = expit(designs["combined_access_high"] @ beta)
    combined[access_eligible] = (
        (1.0 - expansion_probability) * combined[access_eligible]
        + expansion_probability * combined_high[access_eligible]
    )
    return {
        "baseline": baseline,
        "wider_access": wider_access,
        "one_more_early_correction": correction,
        "broader_early_relations": diversity,
        "combined": combined,
    }


def load_network(
    analysis: pd.DataFrame,
    predictions_path: Path,
    horizon_days: float,
) -> dict[str, Any]:
    prediction_columns = [
        "comment_id",
        "submission_id",
        "parent_id",
        "author",
        "created_utc",
    ]
    comments = pd.read_csv(predictions_path, usecols=prediction_columns, low_memory=False)
    for column in ["comment_id", "submission_id", "parent_id"]:
        comments[column] = comments[column].map(normalize_id)
    comments["author_hash"] = comments["author"].map(stable_id)
    comments["created_key"] = comments["created_utc"].round().astype("int64")
    if comments["comment_id"].duplicated().any():
        raise ValueError("Comment IDs are not unique in the prediction file")

    focal = analysis[
        [
            "submission_id",
            "author_hash",
            "thread_start_utc",
            "response_delay_hours",
            OUTCOME,
        ]
    ].copy()
    focal["row_id"] = np.arange(len(focal), dtype=int)
    focal["created_key"] = (
        focal["thread_start_utc"] + focal["response_delay_hours"] * 3600.0
    ).round().astype("int64")
    focal = focal.merge(
        comments[["comment_id", "submission_id", "author_hash", "created_key"]],
        on=["submission_id", "author_hash", "created_key"],
        how="left",
        validate="one_to_one",
    )
    if focal["comment_id"].isna().any():
        raise ValueError(f"Could not map {int(focal['comment_id'].isna().sum())} focal responses")
    focal = focal.sort_values("row_id").reset_index(drop=True)

    thread_metadata = (
        analysis.groupby("submission_id", as_index=False)
        .agg(
            thread_start_utc=("thread_start_utc", "first"),
            early_context_duration_hours=("early_context_duration_hours", "first"),
        )
        .sort_values("submission_id")
        .reset_index(drop=True)
    )
    thread_metadata["thread_code"] = np.arange(len(thread_metadata), dtype=int)
    thread_code = dict(zip(thread_metadata["submission_id"], thread_metadata["thread_code"]))

    comments = comments.merge(thread_metadata, on="submission_id", how="inner", validate="many_to_one")
    early_end = (
        comments["thread_start_utc"] + comments["early_context_duration_hours"] * 3600.0
    )
    horizon_end = comments["thread_start_utc"] + horizon_days * 86400.0
    comments = comments.loc[
        comments["created_utc"].gt(early_end) & comments["created_utc"].le(horizon_end)
    ].copy()
    comments = comments.sort_values(["submission_id", "created_utc", "comment_id"]).reset_index(drop=True)
    comments["thread_code"] = comments["submission_id"].map(thread_code).astype(int)

    focal_lookup = dict(zip(focal["comment_id"], focal["row_id"]))
    focal_times = np.full(len(focal), np.nan, dtype=float)
    focal_thread_codes = np.full(len(focal), -1, dtype=int)
    for item in comments.itertuples(index=False):
        row_id = focal_lookup.get(item.comment_id)
        if row_id is not None:
            focal_times[row_id] = float(item.created_utc)
            focal_thread_codes[row_id] = int(item.thread_code)
    if np.isnan(focal_times).any() or (focal_thread_codes < 0).any():
        raise ValueError("At least one focal response is absent from the seven-day network")

    path_lookup: dict[str, tuple[int, ...]] = {}
    sparse_rows: list[int] = []
    sparse_columns: list[int] = []
    for comment_index, item in enumerate(comments.itertuples(index=False)):
        path = path_lookup.get(item.parent_id, ())
        parent_focal = focal_lookup.get(item.parent_id)
        if parent_focal is not None:
            path = path + (parent_focal,)
        path_lookup[item.comment_id] = path
        if path:
            sparse_rows.extend([comment_index] * len(path))
            sparse_columns.extend(path)
    values = np.ones(len(sparse_rows), dtype=np.int8)
    ancestor_matrix = csr_matrix(
        (values, (sparse_rows, sparse_columns)),
        shape=(len(comments), len(focal)),
        dtype=np.int8,
    )

    return {
        "focal_comment_ids": focal["comment_id"].to_numpy(),
        "focal_times": focal_times,
        "focal_thread_codes": focal_thread_codes,
        "observed_outcomes": analysis[OUTCOME].to_numpy(dtype=np.int8),
        "comment_times": comments["created_utc"].to_numpy(dtype=float),
        "comment_thread_codes": comments["thread_code"].to_numpy(dtype=int),
        "ancestor_matrix": ancestor_matrix,
        "thread_count": len(thread_metadata),
        "comment_count": len(comments),
        "reply_edge_count": int(comments["parent_id"].isin(set(comments["comment_id"])).sum()),
        "mapped_focal_count": len(focal),
        "ancestor_link_count": int(ancestor_matrix.nnz),
    }


def network_metrics(states: np.ndarray, network: dict[str, Any]) -> dict[str, float]:
    states = np.asarray(states, dtype=np.int8)
    focal_thread_codes = network["focal_thread_codes"]
    thread_count = int(network["thread_count"])
    correction_count = np.bincount(
        focal_thread_codes,
        weights=states,
        minlength=thread_count,
    )
    first_correction_time = np.full(thread_count, np.inf, dtype=float)
    selected = states.astype(bool)
    if selected.any():
        np.minimum.at(
            first_correction_time,
            focal_thread_codes[selected],
            network["focal_times"][selected],
        )
    correction_available = network["comment_times"] > first_correction_time[
        network["comment_thread_codes"]
    ]
    same_branch = np.asarray(network["ancestor_matrix"] @ states).ravel() > 0
    return {
        "corrective_response_rate": float(states.mean()),
        "threads_with_correction": float((correction_count > 0).mean()),
        "later_comments_after_correction": float(correction_available.mean()),
        "same_branch_reach": float(same_branch.mean()),
    }


def simulate(
    result: Any,
    covariance: np.ndarray,
    arrays: dict[str, Any],
    network: dict[str, Any],
    draws: int,
    seed: int,
) -> tuple[pd.DataFrame, int]:
    covariance_psd, clipped_eigenvalues = positive_semidefinite(covariance)
    rng = np.random.default_rng(seed)
    beta_draws = rng.multivariate_normal(
        np.asarray(result.params, dtype=float),
        covariance_psd,
        size=draws,
        check_valid="ignore",
    )
    rows: list[dict[str, Any]] = []
    observed = np.asarray(network["observed_outcomes"], dtype=np.int8)
    for draw_id, beta in enumerate(beta_draws):
        probabilities = scenario_probabilities(beta, arrays)
        baseline_probability = probabilities["baseline"]
        common_uniform = rng.random(len(network["focal_times"]))
        latent_rank = np.where(
            observed == 1,
            common_uniform * baseline_probability,
            baseline_probability + common_uniform * (1.0 - baseline_probability),
        )
        for scenario in SCENARIOS:
            states = latent_rank < probabilities[scenario]
            rows.append(
                {
                    "draw": draw_id,
                    "scenario": scenario,
                    **network_metrics(states, network),
                }
            )
    return pd.DataFrame(rows), clipped_eigenvalues


def summarize_draws(draws: pd.DataFrame) -> pd.DataFrame:
    baseline = draws.loc[draws["scenario"].eq("baseline")].set_index("draw")
    rows: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        current = draws.loc[draws["scenario"].eq(scenario)].set_index("draw")
        for metric in METRICS:
            values = current[metric].astype(float)
            differences = values - baseline[metric].astype(float)
            rows.append(
                {
                    "scenario": scenario,
                    "metric": metric,
                    "estimate": float(values.mean()),
                    "interval_low": float(values.quantile(0.025)),
                    "interval_high": float(values.quantile(0.975)),
                    "difference_from_baseline": float(differences.mean()),
                    "difference_interval_low": float(differences.quantile(0.025)),
                    "difference_interval_high": float(differences.quantile(0.975)),
                }
            )
    return pd.DataFrame(rows)


def run(args: argparse.Namespace) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = args.output_dir / "tables"
    metrics_dir = args.output_dir / "metrics"
    tables_dir.mkdir(exist_ok=True)
    metrics_dir.mkdir(exist_ok=True)

    analysis = pd.read_csv(args.analysis_frame, low_memory=False)
    result, covariance = fit_two_way_logit(FORMULA, analysis)
    arrays, scenario_metadata = build_scenario_designs(result, analysis)
    network = load_network(analysis, args.predictions, args.horizon_days)
    draw_table, clipped_eigenvalues = simulate(
        result,
        covariance,
        arrays,
        network,
        args.draws,
        args.seed,
    )
    summary_table = summarize_draws(draw_table)
    observed_metrics = network_metrics(network["observed_outcomes"], network)

    coefficients = coefficient_table(result, covariance, "focused_main")
    write_csv(tables_dir / "model_coefficients.csv", coefficients)
    write_csv(tables_dir / "network_simulation_draws.csv", draw_table)
    write_csv(tables_dir / "network_scenario_summary.csv", summary_table)
    write_csv(
        tables_dir / "observed_network_metrics.csv",
        pd.DataFrame([{"metric": key, "estimate": value} for key, value in observed_metrics.items()]),
    )

    model_fit = {
        "n": int(result.nobs),
        "log_likelihood": float(result.llf),
        "aic": float(result.aic),
        "bic": float(result.bic),
        "mcfadden_pseudo_r2": float(result.prsquared),
        "converged": bool(result.mle_retvals.get("converged", False)),
    }
    write_json(metrics_dir / "model_fit.json", model_fit)

    summary = {
        "run_status": "empirical_network_simulation_complete",
        "run_stage": args.run_stage,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "command": " ".join(sys.argv),
        "output_dir": str(args.output_dir),
        "analysis_frame": str(args.analysis_frame),
        "predictions": str(args.predictions),
        "seed": args.seed,
        "simulation_draws": args.draws,
        "horizon_days": args.horizon_days,
        "focal_responses": int(len(analysis)),
        "authors": int(analysis["author_hash"].nunique()),
        "threads": int(network["thread_count"]),
        "later_network_comments": int(network["comment_count"]),
        "mapped_focal_responses": int(network["mapped_focal_count"]),
        "observed_reply_edges_within_period": int(network["reply_edge_count"]),
        "focal_ancestor_links": int(network["ancestor_link_count"]),
        "clipped_negative_covariance_eigenvalues": clipped_eigenvalues,
        "projection_mode": "latent_rank_conditioned_on_observed_baseline",
        "scenario_metadata": scenario_metadata,
        "observed_network_metrics": observed_metrics,
        "model_fit": model_fit,
    }
    write_json(args.output_dir / "run_summary.json", summary)
    write_json(metrics_dir / "run_summary.json", summary)
    (args.output_dir / "run.log").write_text(
        "\n".join(
            [
                "empirical network simulation",
                f"generated_utc={summary['generated_utc']}",
                f"command={summary['command']}",
                f"run_stage={summary['run_stage']}",
                f"focal_responses={summary['focal_responses']}",
                f"mapped_focal_responses={summary['mapped_focal_responses']}",
                f"threads={summary['threads']}",
                f"later_network_comments={summary['later_network_comments']}",
                f"simulation_draws={summary['simulation_draws']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simulate corrective responding on observed reply networks.")
    parser.add_argument(
        "--analysis-frame",
        type=Path,
        default=Path(
            "outputs/_core_story_deep_dive_relative_access_20260717T023845Z/"
            "tables/analysis_frame.csv"
        ),
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        default=Path(
            "outputs/full_comment_predictions_latest_pair_ensemble_20260628T142000Z/"
            "predictions/full_comment_predictions.csv"
        ),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--draws", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260718)
    parser.add_argument("--horizon-days", type=float, default=7.0)
    parser.add_argument(
        "--run-stage",
        choices=["exploratory", "manuscript_candidate", "frozen"],
        default="exploratory",
    )
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
