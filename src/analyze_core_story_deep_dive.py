#!/usr/bin/env python3
"""Run focused construct and mechanism checks for the core correction story."""

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

from fit_revised_corrective_response_models import (
    NO_IDENTIFIED_RELATION_COLUMN,
    RELATION_PROBABILITY_COLUMNS,
    RELATION_TYPES,
    build_first_response_dataset,
    build_pair_history,
    coefficient_table,
    contrast_from_scenarios,
    fit_two_way_logit,
    load_comments,
    standardize,
    write_csv,
    write_json,
)


OUTCOME = "first_later_corrective_response"
CORRECTIVE_TYPES = RELATION_TYPES[:5]
NONCORRECTIVE_TYPES = RELATION_TYPES[5:]


def entropy_from_counts(counts: np.ndarray, category_count: int) -> tuple[np.ndarray, np.ndarray]:
    totals = counts.sum(axis=1, keepdims=True)
    probabilities = np.divide(
        counts,
        totals,
        out=np.zeros_like(counts, dtype=float),
        where=totals > 0,
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        terms = np.where(probabilities > 0, probabilities * np.log(probabilities), 0.0)
    raw = -terms.sum(axis=1)
    normalized = raw / math.log(category_count) if category_count > 1 else np.zeros(len(counts))
    return normalized, np.exp(raw)


def build_history_diversity(comments: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    group_categories = sorted(comments["community_group_proxy"].dropna().astype(str).unique())
    subreddit_categories = sorted(comments["subreddit"].dropna().astype(str).unique())
    group_index = {value: index for index, value in enumerate(group_categories)}
    group_count_columns = {
        value: f"prior_community_group_comments_{index}"
        for index, value in enumerate(group_categories)
    }
    subreddit_index = {value: index for index, value in enumerate(subreddit_categories)}
    pairs = (
        comments[["submission_id", "author", "thread_start_utc"]]
        .drop_duplicates()
        .sort_values(["author", "thread_start_utc", "submission_id"])
    )
    pair_groups = {author: group for author, group in pairs.groupby("author", sort=False)}
    frames: list[pd.DataFrame] = []
    for author, author_comments in comments.groupby("author", sort=False):
        author_pairs = pair_groups.get(author)
        if author_pairs is None:
            continue
        author_comments = author_comments.sort_values(["created_utc", "comment_id"])
        times = author_comments["created_utc"].to_numpy(dtype=float)
        cutoffs = np.searchsorted(
            times,
            author_pairs["thread_start_utc"].to_numpy(dtype=float),
            side="left",
        )
        group_one_hot = np.zeros((len(author_comments), len(group_categories)), dtype=int)
        subreddit_one_hot = np.zeros((len(author_comments), len(subreddit_categories)), dtype=int)
        for row_index, value in enumerate(author_comments["community_group_proxy"].astype(str)):
            group_one_hot[row_index, group_index[value]] = 1
        for row_index, value in enumerate(author_comments["subreddit"].astype(str)):
            subreddit_one_hot[row_index, subreddit_index[value]] = 1
        group_cumulative = np.cumsum(group_one_hot, axis=0)
        subreddit_cumulative = np.cumsum(subreddit_one_hot, axis=0)
        group_counts = np.zeros((len(cutoffs), len(group_categories)), dtype=int)
        subreddit_counts = np.zeros((len(cutoffs), len(subreddit_categories)), dtype=int)
        observed = cutoffs > 0
        group_counts[observed] = group_cumulative[cutoffs[observed] - 1]
        subreddit_counts[observed] = subreddit_cumulative[cutoffs[observed] - 1]
        group_entropy, effective_groups = entropy_from_counts(group_counts, len(group_categories))
        subreddit_entropy, effective_subreddits = entropy_from_counts(
            subreddit_counts, len(subreddit_categories)
        )
        result = author_pairs.copy()
        result["prior_community_group_entropy"] = group_entropy
        result["prior_effective_community_groups"] = effective_groups
        result["prior_subreddit_entropy"] = subreddit_entropy
        result["prior_effective_subreddits"] = effective_subreddits
        for category, column in group_count_columns.items():
            result[column] = group_counts[:, group_index[category]]
        frames.append(result)
    metadata = {
        "community_group_categories": group_categories,
        "community_group_count_columns": group_count_columns,
        "subreddit_categories": subreddit_categories,
    }
    return pd.concat(frames, ignore_index=True), metadata


def normalized_entropy(probabilities: np.ndarray) -> float:
    probabilities = np.asarray(probabilities, dtype=float)
    total = float(probabilities.sum())
    if total <= 0 or len(probabilities) <= 1:
        return 0.0
    probabilities = probabilities / total
    positive = probabilities[probabilities > 0]
    return -float(np.sum(positive * np.log(positive))) / math.log(len(probabilities))


def stored_probability_entropy(probabilities: np.ndarray) -> float:
    """Reproduce the manuscript measure before correcting CSV rounding drift."""
    probabilities = np.asarray(probabilities, dtype=float)
    if len(probabilities) <= 1:
        return 0.0
    positive = probabilities[probabilities > 0]
    return -float(np.sum(positive * np.log(positive))) / math.log(len(probabilities))


def build_early_variants(comments: pd.DataFrame, submission_ids: set[str]) -> pd.DataFrame:
    relation_columns = RELATION_PROBABILITY_COLUMNS + [NO_IDENTIFIED_RELATION_COLUMN]
    rows: list[dict[str, Any]] = []
    subset = comments.loc[comments["submission_id"].isin(submission_ids)].copy()
    for submission_id, thread in subset.groupby("submission_id", sort=False):
        early = thread.sort_values(["created_utc", "comment_id"]).iloc[:10].copy()
        if len(early) < 10:
            continue
        relation_matrix = early[relation_columns].to_numpy(dtype=float)
        mean_relation = relation_matrix.mean(axis=0)
        hard_counts = np.bincount(np.argmax(relation_matrix, axis=1), minlength=len(relation_columns))
        available = early["relation_type_available"].eq(1).to_numpy()
        if available.any():
            available_relation_matrix = early.loc[
                available, RELATION_PROBABILITY_COLUMNS
            ].to_numpy(dtype=float)
            relation_only_mean = available_relation_matrix.mean(axis=0)
            relation_only_richness = int(
                np.unique(np.argmax(available_relation_matrix, axis=1)).size
            )
        else:
            relation_only_mean = np.zeros(len(RELATION_PROBABILITY_COLUMNS), dtype=float)
            relation_only_richness = 0
        correction_predictions = early["public_correction_pred"].to_numpy(dtype=int)
        correction_positions = np.flatnonzero(correction_predictions == 1) + 1
        first_position = int(correction_positions[0]) if len(correction_positions) else 0
        candidate_counts = early["pair_relation_candidate_count"].to_numpy(dtype=float)
        row: dict[str, Any] = {
            "submission_id": str(submission_id),
            "early_soft_relation_diversity_check": stored_probability_entropy(mean_relation),
            "early_soft_relation_diversity_renormalized": normalized_entropy(mean_relation),
            "early_hard_relation_diversity": normalized_entropy(hard_counts),
            "early_relation_only_diversity": normalized_entropy(relation_only_mean),
            "early_hard_relation_richness": int(np.count_nonzero(hard_counts)),
            "early_relation_only_richness": relation_only_richness,
            "early_corrective_type_diversity": normalized_entropy(mean_relation[:5]),
            "early_noncorrective_type_diversity": normalized_entropy(mean_relation[5:8]),
            "early_correction_count": int(correction_predictions.sum()),
            "early_additional_corrections": max(int(correction_predictions.sum()) - 1, 0),
            "early_first_correction_position": first_position,
            "early_correction_earliness": (10.0 - first_position) / 9.0 if first_position else np.nan,
            "early_mean_correction_score": float(early["public_correction_score"].mean()),
            "early_max_correction_score": float(early["public_correction_score"].max()),
            "early_mean_candidate_count": float(candidate_counts.mean()),
        }
        for type_name, column in zip(RELATION_TYPES, RELATION_PROBABILITY_COLUMNS):
            row[f"early_mean_type_{type_name}"] = float(early[column].mean())
        rows.append(row)
    return pd.DataFrame(rows)


def prepare_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, dict[str, float]]]:
    frame = frame.copy()
    frame["log_prior_comments"] = np.log1p(frame["prior_comments"].astype(float))
    frame["prior_subreddit_breadth_log"] = np.log1p(frame["prior_subreddits"].astype(float))
    frame["prior_subreddit_breadth_capped"] = np.minimum(
        frame["prior_subreddits"].astype(int), 3
    )
    frame["prior_outgroup_comments_log"] = np.log1p(frame["prior_outgroup_comments"].astype(float))
    frame["early_correction_count_capped"] = np.minimum(
        frame["early_correction_count"].astype(int), 4
    )
    epistemic_columns = [
        "early_mean_type_evidence_or_source_correction",
        "early_mean_type_definition_or_context_correction",
        "early_mean_type_questioning_or_source_request",
        "early_mean_type_noncorrective_factual_statement",
    ]
    relation_type_columns = [f"early_mean_type_{type_name}" for type_name in RELATION_TYPES]
    relation_type_total = frame[relation_type_columns].sum(axis=1).to_numpy(dtype=float)
    epistemic_total = frame[epistemic_columns].sum(axis=1).to_numpy(dtype=float)
    frame["early_epistemic_relation_share"] = np.divide(
        epistemic_total,
        relation_type_total,
        out=np.zeros(len(frame), dtype=float),
        where=relation_type_total > 0,
    )
    present = frame["early_corrective_response_presence"].eq(1)
    earliness_mean = float(frame.loc[present, "early_correction_earliness"].mean())
    earliness_std = float(frame.loc[present, "early_correction_earliness"].std(ddof=0))
    frame["early_correction_earliness_centered"] = 0.0
    if earliness_std > 0:
        frame.loc[present, "early_correction_earliness_centered"] = (
            frame.loc[present, "early_correction_earliness"] - earliness_mean
        ) / earliness_std
    standard_columns = [
        "early_cross_community_participant_share",
        "early_response_relation_diversity",
        "early_soft_relation_diversity_renormalized",
        "early_ambient_hostile_language_rate",
        "prior_community_group_entropy",
        "prior_subreddit_entropy",
        "prior_subreddit_breadth_log",
        "prior_outgroup_share",
        "prior_outgroup_comments_log",
        "early_hard_relation_diversity",
        "early_relation_only_diversity",
        "early_hard_relation_richness",
        "early_relation_only_richness",
        "early_corrective_type_diversity",
        "early_noncorrective_type_diversity",
        "early_mean_correction_score",
        "early_max_correction_score",
        "early_mean_candidate_count",
        "early_epistemic_relation_share",
    ]
    standard_columns.extend(f"early_mean_type_{type_name}" for type_name in RELATION_TYPES)
    frame, moments = standardize(frame, standard_columns)
    moments["early_correction_earliness"] = {
        "mean_among_threads_with_correction": earliness_mean,
        "std_among_threads_with_correction": earliness_std,
    }
    return frame, moments


def model_fit_row(name: str, result: Any) -> dict[str, Any]:
    return {
        "model": name,
        "n": int(result.nobs),
        "log_likelihood": float(result.llf),
        "aic": float(result.aic),
        "bic": float(result.bic),
        "mcfadden_pseudo_r2": float(result.prsquared),
        "converged": bool(result.mle_retvals.get("converged", False)),
    }


def benjamini_hochberg(values: pd.Series) -> np.ndarray:
    p_values = values.to_numpy(dtype=float)
    order = np.argsort(p_values)
    adjusted = np.empty(len(p_values), dtype=float)
    ranked = p_values[order] * len(p_values) / (np.arange(len(p_values)) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    adjusted[order] = np.minimum(ranked, 1.0)
    return adjusted


def add_probability_contrast(
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


def run(args: argparse.Namespace) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = args.output_dir / "tables"
    metrics_dir = args.output_dir / "metrics"
    tables_dir.mkdir(exist_ok=True)
    metrics_dir.mkdir(exist_ok=True)

    print("Loading comment, correction, and relation-type predictions...", flush=True)
    comments = load_comments(args)
    print("Constructing pre-thread author histories...", flush=True)
    pair_history = build_pair_history(comments)
    history_diversity, category_metadata = build_history_diversity(comments)
    pair_history = pair_history.merge(
        history_diversity,
        on=["submission_id", "author", "thread_start_utc"],
        how="left",
        validate="one_to_one",
    )
    print("Rebuilding the unified first-response cohort...", flush=True)
    frame, sample_flow = build_first_response_dataset(
        comments,
        pair_history,
        "comments",
        args.early_comments,
        args.horizon_days,
        args.min_prior_comments,
        args.min_history_days,
    )
    print("Constructing alternative early-discourse measures...", flush=True)
    early_variants = build_early_variants(comments, set(frame["submission_id"].astype(str)))
    frame = frame.merge(early_variants, on="submission_id", how="left", validate="many_to_one")
    frame["prior_current_group_comments"] = 0
    for category, column in category_metadata["community_group_count_columns"].items():
        matches = frame["community_group_proxy"].eq(category)
        frame.loc[matches, "prior_current_group_comments"] = frame.loc[matches, column]
    frame["prior_outgroup_comments"] = (
        frame["prior_comments"].astype(int) - frame["prior_current_group_comments"].astype(int)
    ).clip(lower=0)
    frame["prior_outgroup_participation"] = frame["prior_outgroup_comments"].gt(0).astype(int)
    frame["prior_outgroup_share"] = np.divide(
        frame["prior_outgroup_comments"].to_numpy(dtype=float),
        frame["prior_comments"].to_numpy(dtype=float),
        out=np.zeros(len(frame), dtype=float),
        where=frame["prior_comments"].to_numpy(dtype=float) > 0,
    )
    frame["prior_access_pattern"] = np.select(
        [
            frame["prior_community_groups"].gt(1),
            frame["prior_outgroup_participation"].eq(1),
        ],
        ["multi_group", "other_group_only"],
        default="same_group_only",
    )
    diversity_discrepancy = float(
        (frame["early_response_relation_diversity"] - frame["early_soft_relation_diversity_check"])
        .abs()
        .max()
    )
    if diversity_discrepancy > 1e-10:
        raise ValueError(f"Recomputed relation diversity differs by {diversity_discrepancy}")
    model_frame, moments = prepare_frame(frame)

    nuisance = (
        "early_cross_community_participant_share_z + early_ambient_hostile_language_rate_z + "
        "early_correction_reply_presence + early_correction_directed_hostility_presence + "
        "prior_corrective_response_rate + log_prior_comments + early_prior_history_coverage + "
        "early_relation_type_coverage + early_context_activity + C(subreddit)"
    )
    measurement_nuisance = f"{nuisance} + early_mean_candidate_count_z"
    formulas = {
        "current_main_replication": (
            f"{OUTCOME} ~ prior_cross_community_participation * "
            "early_cross_community_participant_share_z + early_corrective_response_presence + "
            f"early_response_relation_diversity_z + {nuisance}"
        ),
        "access_group_dose": (
            f"{OUTCOME} ~ C(prior_community_groups) + early_corrective_response_presence + "
            f"early_response_relation_diversity_z + {nuisance}"
        ),
        "access_group_entropy": (
            f"{OUTCOME} ~ prior_community_group_entropy_z + early_corrective_response_presence + "
            f"early_response_relation_diversity_z + {nuisance}"
        ),
        "access_subreddit_entropy": (
            f"{OUTCOME} ~ prior_subreddit_entropy_z + early_corrective_response_presence + "
            f"early_response_relation_diversity_z + {nuisance}"
        ),
        "access_subreddit_breadth": (
            f"{OUTCOME} ~ prior_subreddit_breadth_log_z + early_corrective_response_presence + "
            f"early_response_relation_diversity_z + {nuisance}"
        ),
        "access_subreddit_breadth_categories": (
            f"{OUTCOME} ~ C(prior_subreddit_breadth_capped) + "
            "early_corrective_response_presence + early_response_relation_diversity_z + "
            f"{nuisance}"
        ),
        "access_outgroup_binary": (
            f"{OUTCOME} ~ prior_outgroup_participation + early_corrective_response_presence + "
            f"early_response_relation_diversity_z + {nuisance}"
        ),
        "access_outgroup_share": (
            f"{OUTCOME} ~ prior_outgroup_share_z + early_corrective_response_presence + "
            f"early_response_relation_diversity_z + {nuisance}"
        ),
        "access_relative_pattern": (
            f"{OUTCOME} ~ C(prior_access_pattern, Treatment(reference='same_group_only')) + "
            "early_corrective_response_presence + early_response_relation_diversity_z + "
            f"{nuisance}"
        ),
        "correction_intensity": (
            f"{OUTCOME} ~ prior_cross_community_participation + early_corrective_response_presence + "
            "early_additional_corrections + early_response_relation_diversity_z + "
            f"{nuisance}"
        ),
        "correction_timing": (
            f"{OUTCOME} ~ prior_cross_community_participation + early_corrective_response_presence + "
            "early_correction_earliness_centered + early_response_relation_diversity_z + "
            f"{nuisance}"
        ),
        "correction_mean_score": (
            f"{OUTCOME} ~ prior_cross_community_participation + early_mean_correction_score_z + "
            f"early_response_relation_diversity_z + {measurement_nuisance}"
        ),
        "correction_max_score": (
            f"{OUTCOME} ~ prior_cross_community_participation + early_max_correction_score_z + "
            f"early_response_relation_diversity_z + {measurement_nuisance}"
        ),
        "relation_hard_entropy": (
            f"{OUTCOME} ~ prior_cross_community_participation + early_corrective_response_presence + "
            f"early_hard_relation_diversity_z + {measurement_nuisance}"
        ),
        "relation_soft_entropy_renormalized": (
            f"{OUTCOME} ~ prior_cross_community_participation + early_corrective_response_presence + "
            f"early_soft_relation_diversity_renormalized_z + {measurement_nuisance}"
        ),
        "relation_only_entropy": (
            f"{OUTCOME} ~ prior_cross_community_participation + early_corrective_response_presence + "
            f"early_relation_only_diversity_z + {measurement_nuisance}"
        ),
        "relation_hard_richness": (
            f"{OUTCOME} ~ prior_cross_community_participation + early_corrective_response_presence + "
            f"early_hard_relation_richness_z + {measurement_nuisance}"
        ),
        "relation_only_richness": (
            f"{OUTCOME} ~ prior_cross_community_participation + early_corrective_response_presence + "
            f"early_relation_only_richness_z + {measurement_nuisance}"
        ),
        "relation_only_entropy_with_correction_count": (
            f"{OUTCOME} ~ prior_cross_community_participation + "
            "C(early_correction_count_capped) + early_relation_only_diversity_z + "
            f"{measurement_nuisance}"
        ),
        "epistemic_relation_share_with_correction_count": (
            f"{OUTCOME} ~ prior_cross_community_participation + "
            "C(early_correction_count_capped) + early_epistemic_relation_share_z + "
            f"{measurement_nuisance}"
        ),
        "access_visibility_interactions": (
            f"{OUTCOME} ~ prior_cross_community_participation * early_corrective_response_presence + "
            "prior_cross_community_participation * early_response_relation_diversity_z + "
            f"{nuisance}"
        ),
    }
    for type_name in RELATION_TYPES:
        formulas[f"relation_type_{type_name}"] = (
            f"{OUTCOME} ~ prior_cross_community_participation + early_corrective_response_presence + "
            f"early_mean_type_{type_name}_z + {nuisance}"
        )
    if args.model_set == "smoke":
        formulas = {"current_main_replication": formulas["current_main_replication"]}

    coefficient_frames: list[pd.DataFrame] = []
    fit_rows: list[dict[str, Any]] = []
    fitted: dict[str, tuple[Any, np.ndarray]] = {}
    for model_name, formula in formulas.items():
        print(f"Fitting {model_name}...", flush=True)
        result, covariance = fit_two_way_logit(formula, model_frame)
        fitted[model_name] = (result, covariance)
        coefficient_frames.append(coefficient_table(result, covariance, model_name))
        fit_rows.append(model_fit_row(model_name, result))
    coefficients = pd.concat(coefficient_frames, ignore_index=True)

    type_rows = coefficients.loc[
        coefficients["model"].str.startswith("relation_type_")
        & coefficients["term"].str.startswith("early_mean_type_")
    ].copy()
    if not type_rows.empty:
        type_rows["relation_type"] = (
            type_rows["term"]
            .str.removeprefix("early_mean_type_")
            .str.removesuffix("_z")
        )
        type_rows["p_value_bh"] = benjamini_hochberg(type_rows["p_value"])

    contrast_rows: list[dict[str, Any]] = []
    if "access_group_dose" in fitted:
        dose_result, dose_covariance = fitted["access_group_dose"]
        group_reference = model_frame.copy()
        group_two = model_frame.copy()
        group_reference["prior_community_groups"] = 1
        group_two["prior_community_groups"] = 2
        add_probability_contrast(
            contrast_rows,
            "access_group_dose",
            "two versus one prior community groups",
            dose_result,
            dose_covariance,
            [(1.0, group_two), (-1.0, group_reference)],
        )

    if "access_subreddit_breadth_categories" in fitted:
        breadth_result, breadth_covariance = fitted["access_subreddit_breadth_categories"]
        breadth_one = model_frame.copy()
        breadth_two = model_frame.copy()
        breadth_three_plus = model_frame.copy()
        breadth_one["prior_subreddit_breadth_capped"] = 1
        breadth_two["prior_subreddit_breadth_capped"] = 2
        breadth_three_plus["prior_subreddit_breadth_capped"] = 3
        add_probability_contrast(
            contrast_rows,
            "access_subreddit_breadth_categories",
            "two versus one prior subreddits",
            breadth_result,
            breadth_covariance,
            [(1.0, breadth_two), (-1.0, breadth_one)],
        )
        add_probability_contrast(
            contrast_rows,
            "access_subreddit_breadth_categories",
            "three-or-more versus one prior subreddits",
            breadth_result,
            breadth_covariance,
            [(1.0, breadth_three_plus), (-1.0, breadth_one)],
        )

    if "access_relative_pattern" in fitted:
        pattern_result, pattern_covariance = fitted["access_relative_pattern"]
        pattern_same = model_frame.copy()
        pattern_other = model_frame.copy()
        pattern_multi = model_frame.copy()
        pattern_same["prior_access_pattern"] = "same_group_only"
        pattern_other["prior_access_pattern"] = "other_group_only"
        pattern_multi["prior_access_pattern"] = "multi_group"
        add_probability_contrast(
            contrast_rows,
            "access_relative_pattern",
            "other-group-only versus same-group-only prior participation",
            pattern_result,
            pattern_covariance,
            [(1.0, pattern_other), (-1.0, pattern_same)],
        )
        add_probability_contrast(
            contrast_rows,
            "access_relative_pattern",
            "multi-group versus same-group-only prior participation",
            pattern_result,
            pattern_covariance,
            [(1.0, pattern_multi), (-1.0, pattern_same)],
        )

    if "relation_only_entropy_with_correction_count" in fitted:
        composition_result, composition_covariance = fitted[
            "relation_only_entropy_with_correction_count"
        ]
        diversity_mean = model_frame.copy()
        diversity_high = model_frame.copy()
        diversity_mean["early_relation_only_diversity_z"] = 0.0
        diversity_high["early_relation_only_diversity_z"] = 1.0
        add_probability_contrast(
            contrast_rows,
            "relation_only_entropy_with_correction_count",
            "one-SD increase in relation-only diversity holding correction count fixed",
            composition_result,
            composition_covariance,
            [(1.0, diversity_high), (-1.0, diversity_mean)],
        )

    if "access_visibility_interactions" in fitted:
        interaction_result, interaction_covariance = fitted["access_visibility_interactions"]
        c0e0 = model_frame.copy()
        c1e0 = model_frame.copy()
        c0e1 = model_frame.copy()
        c1e1 = model_frame.copy()
        for scenario, cross, correction in [
            (c0e0, 0, 0),
            (c1e0, 1, 0),
            (c0e1, 0, 1),
            (c1e1, 1, 1),
        ]:
            scenario["prior_cross_community_participation"] = cross
            scenario["early_corrective_response_presence"] = correction
        add_probability_contrast(
            contrast_rows,
            "access_visibility_interactions",
            "second difference in prior participation gap by early correction presence",
            interaction_result,
            interaction_covariance,
            [(1.0, c1e1), (-1.0, c0e1), (-1.0, c1e0), (1.0, c0e0)],
        )
        diversity_low = float(model_frame["early_response_relation_diversity_z"].quantile(0.25))
        diversity_high = float(model_frame["early_response_relation_diversity_z"].quantile(0.75))
        c0d0 = model_frame.copy()
        c1d0 = model_frame.copy()
        c0d1 = model_frame.copy()
        c1d1 = model_frame.copy()
        for scenario, cross, diversity in [
            (c0d0, 0, diversity_low),
            (c1d0, 1, diversity_low),
            (c0d1, 0, diversity_high),
            (c1d1, 1, diversity_high),
        ]:
            scenario["prior_cross_community_participation"] = cross
            scenario["early_response_relation_diversity_z"] = diversity
        add_probability_contrast(
            contrast_rows,
            "access_visibility_interactions",
            "second difference in prior participation gap at Q3 versus Q1 relation diversity",
            interaction_result,
            interaction_covariance,
            [(1.0, c1d1), (-1.0, c0d1), (-1.0, c1d0), (1.0, c0d0)],
        )

    access_distribution = (
        model_frame.groupby("prior_community_groups", dropna=False)
        .agg(
            observations=(OUTCOME, "size"),
            corrective_response_rate=(OUTCOME, "mean"),
            mean_prior_comments=("prior_comments", "mean"),
        )
        .reset_index()
    )
    correction_distribution = (
        model_frame.groupby("early_correction_count", dropna=False)
        .agg(observations=(OUTCOME, "size"), corrective_response_rate=(OUTCOME, "mean"))
        .reset_index()
    )
    access_pattern_distribution = (
        model_frame.groupby("prior_access_pattern", dropna=False)
        .agg(
            observations=(OUTCOME, "size"),
            corrective_response_rate=(OUTCOME, "mean"),
            mean_prior_comments=("prior_comments", "mean"),
            mean_outgroup_share=("prior_outgroup_share", "mean"),
        )
        .reset_index()
    )
    relation_measures = [
        "early_response_relation_diversity",
        "early_soft_relation_diversity_renormalized",
        "early_hard_relation_diversity",
        "early_relation_only_diversity",
        "early_hard_relation_richness",
        "early_relation_only_richness",
        "early_corrective_type_diversity",
        "early_noncorrective_type_diversity",
        "early_corrective_response_presence",
        "early_corrective_response_rate",
        "early_relation_type_coverage",
        "early_mean_candidate_count",
        "early_epistemic_relation_share",
    ]
    relation_correlations = model_frame[relation_measures].corr().reset_index().rename(columns={"index": "measure"})
    descriptive_columns = [
        OUTCOME,
        "prior_community_groups",
        "prior_community_group_entropy",
        "prior_subreddits",
        "prior_subreddit_entropy",
        "prior_outgroup_comments",
        "prior_outgroup_share",
        "early_correction_count",
        "early_first_correction_position",
        *relation_measures,
    ]
    descriptives = model_frame[descriptive_columns].describe().T.reset_index().rename(columns={"index": "variable"})

    write_csv(tables_dir / "sample_flow.csv", sample_flow)
    write_csv(tables_dir / "model_coefficients.csv", coefficients)
    write_csv(tables_dir / "model_fit.csv", pd.DataFrame(fit_rows))
    write_csv(tables_dir / "probability_contrasts.csv", pd.DataFrame(contrast_rows))
    write_csv(tables_dir / "relation_type_associations.csv", type_rows)
    write_csv(tables_dir / "access_dose_distribution.csv", access_distribution)
    write_csv(tables_dir / "early_correction_count_distribution.csv", correction_distribution)
    write_csv(tables_dir / "access_pattern_distribution.csv", access_pattern_distribution)
    write_csv(tables_dir / "relation_measure_correlations.csv", relation_correlations)
    write_csv(tables_dir / "feature_descriptives.csv", descriptives)
    if args.model_set == "full":
        write_csv(
            tables_dir / "analysis_frame.csv",
            model_frame.drop(columns=["author"], errors="ignore"),
        )

    summary = {
        "run_status": "core_story_deep_dive_complete",
        "run_stage": "exploratory",
        "model_set": args.model_set,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "command": " ".join(sys.argv),
        "output_dir": str(args.output_dir),
        "n": int(len(model_frame)),
        "authors": int(model_frame["author_hash"].nunique()),
        "threads": int(model_frame["submission_id"].nunique()),
        "outcome_rate": float(model_frame[OUTCOME].mean()),
        "model_count": len(formulas),
        "all_models_converged": bool(pd.DataFrame(fit_rows)["converged"].all()),
        "relation_diversity_recomputation_max_abs_difference": diversity_discrepancy,
        "category_metadata": category_metadata,
        "standardization_moments": moments,
        "questions": [
            "Does prior cross-community participation show dose and alternative-measure evidence?",
            "Do early correction and relation diversity survive pre-specified alternative constructions?",
            "Do prior participation and corrective-discourse visibility show cross-level complementarity?",
            "Which predicted relation types account for the relation-diversity association?",
        ],
    }
    write_json(metrics_dir / "run_summary.json", summary)
    (args.output_dir / "run.log").write_text(
        "\n".join(
            [
                "core story deep-dive run",
                f"generated_utc={summary['generated_utc']}",
                f"command={summary['command']}",
                f"n={summary['n']}",
                f"models={summary['model_count']}",
                f"all_models_converged={summary['all_models_converged']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deepen the access and discourse-visibility findings.")
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
    parser.add_argument("--submissions", type=Path, default=Path("data/interim/covidvaccine_submissions.jsonl"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--early-comments", type=int, default=10)
    parser.add_argument("--horizon-days", type=float, default=7.0)
    parser.add_argument("--min-prior-comments", type=int, default=2)
    parser.add_argument("--min-history-days", type=float, default=7.0)
    parser.add_argument("--model-set", choices=["smoke", "full"], default="full")
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
