#!/usr/bin/env python3
"""Fit unified first-response models of corrective responding.

The main analysis uses one temporally ordered first-response cohort. Author
history and early-thread conditions are observed before the focal response.
The early context distinguishes relation-category diversity, ambient hostile
language, and hostile replies directed at an early corrective response.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from patsy import build_design_matrices
from scipy.stats import norm
from statsmodels.stats.sandwich_covariance import cov_cluster_2groups

from analyze_thread_climate import HOSTILITY_PATTERNS, compact_text, has_match


REMOVED_AUTHORS = {"", "[deleted]", "deleted", "automoderator"}
RELATION_TYPES = [
    "direct_rebuttal",
    "evidence_or_source_correction",
    "definition_or_context_correction",
    "questioning_or_source_request",
    "sarcastic_or_quote_edit_correction",
    "noncorrective_factual_statement",
    "misinformation_support_or_elaboration",
    "general_opinion_or_reaction",
]
RELATION_PROBABILITY_COLUMNS = [f"type_prob_{label}" for label in RELATION_TYPES]
NO_IDENTIFIED_RELATION_COLUMN = "type_prob_no_identified_relation"
MAIN_TERMS = [
    "prior_cross_community_participation",
    "early_cross_community_participant_share_z",
    "prior_cross_community_participation:early_cross_community_participant_share_z",
    "early_corrective_response_presence",
    "early_response_relation_diversity_z",
    "early_ambient_hostile_language_rate_z",
    "early_correction_reply_presence",
    "early_correction_directed_hostility_presence",
]


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def normalize_author(value: Any) -> str | None:
    author = str(value or "").strip().lower()
    return None if author in REMOVED_AUTHORS else author


def normalize_comment_id(value: Any) -> str:
    comment_id = str(value or "").strip().lower()
    return comment_id[3:] if comment_id.startswith("t1_") else comment_id


def stable_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def load_submission_starts(path: Path) -> dict[str, float]:
    starts: dict[str, float] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            starts[str(item.get("submission_id") or "").strip().lower()] = float(item["created_utc"])
    return starts


def load_comment_text(path: Path) -> pd.DataFrame:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            body = compact_text(item.get("body"))
            rows.append(
                {
                    "comment_id": normalize_comment_id(item.get("comment_id")),
                    "parent_id": normalize_comment_id(item.get("parent_id")),
                    "body": body,
                    "hostile_language": has_match(body, HOSTILITY_PATTERNS),
                    "body_words": len(body.split()),
                }
            )
    return pd.DataFrame(rows)


def load_relation_type_predictions(path: Path) -> pd.DataFrame:
    """Load type probabilities for the pair selected by the correction pipeline."""
    columns = ["pair_id", "response_id"] + RELATION_PROBABILITY_COLUMNS
    frame = pd.read_csv(path, usecols=columns, low_memory=False)
    frame["pair_id"] = frame["pair_id"].astype(str).str.strip().str.lower()
    frame["response_id"] = frame["response_id"].map(normalize_comment_id)
    for column in RELATION_PROBABILITY_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    return frame.drop_duplicates("pair_id", keep="last")


def load_comments(args: argparse.Namespace) -> pd.DataFrame:
    columns = [
        "comment_id",
        "submission_id",
        "author",
        "subreddit",
        "community_group_proxy",
        "created_utc",
        "public_correction_score",
        "public_correction_pred",
        "pair_relation_candidate_count",
        "pair_relation_best_pair_id",
    ]
    frame = pd.read_csv(args.predictions, usecols=columns, low_memory=False)
    frame["comment_id"] = frame["comment_id"].map(normalize_comment_id)
    frame["submission_id"] = frame["submission_id"].astype(str).str.strip().str.lower()
    frame["pair_relation_best_pair_id"] = (
        frame["pair_relation_best_pair_id"].astype(str).str.strip().str.lower()
    )
    frame["author"] = frame["author"].map(normalize_author)
    frame = frame.loc[frame["author"].notna()].copy()
    frame["subreddit"] = frame["subreddit"].astype(str).str.strip().str.lower()
    frame["community_group_proxy"] = frame["community_group_proxy"].astype(str).str.strip().str.lower()
    for column in [
        "created_utc",
        "public_correction_score",
        "public_correction_pred",
        "pair_relation_candidate_count",
    ]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
    frame["public_correction_pred"] = frame["public_correction_pred"].astype(int)
    frame = frame.merge(load_comment_text(args.comments), on="comment_id", how="left", validate="one_to_one")
    frame["hostile_language"] = pd.to_numeric(frame["hostile_language"], errors="coerce").fillna(0).astype(int)
    frame["body_words"] = pd.to_numeric(frame["body_words"], errors="coerce").fillna(0).astype(int)
    type_predictions = load_relation_type_predictions(args.relation_type_predictions)
    frame = frame.merge(
        type_predictions.drop(columns=["response_id"]),
        left_on="pair_relation_best_pair_id",
        right_on="pair_id",
        how="left",
        validate="many_to_one",
    ).drop(columns=["pair_id"])
    frame["relation_type_available"] = frame[RELATION_PROBABILITY_COLUMNS].notna().all(axis=1).astype(int)
    for column in RELATION_PROBABILITY_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    frame[NO_IDENTIFIED_RELATION_COLUMN] = 1.0 - frame["relation_type_available"].astype(float)
    starts = load_submission_starts(args.submissions)
    frame["thread_start_utc"] = frame["submission_id"].map(starts)
    if frame["thread_start_utc"].isna().any():
        missing = int(frame["thread_start_utc"].isna().sum())
        raise ValueError(f"Missing submission start time for {missing} comments")
    frame = frame.sort_values(["submission_id", "created_utc", "comment_id"]).reset_index(drop=True)
    frame["thread_comment_rank"] = frame.groupby("submission_id").cumcount() + 1
    return frame


def build_author_history(comments: pd.DataFrame) -> dict[str, dict[str, np.ndarray]]:
    history: dict[str, dict[str, np.ndarray]] = {}
    ordered = comments.sort_values(["author", "created_utc", "comment_id"])
    for author, group in ordered.groupby("author", sort=False):
        history[str(author)] = {
            "times": group["created_utc"].to_numpy(dtype=float),
            "subreddits": group["subreddit"].astype(str).to_numpy(),
            "groups": group["community_group_proxy"].astype(str).to_numpy(),
            "corrections": group["public_correction_pred"].to_numpy(dtype=int),
        }
    return history


def build_pair_history(comments: pd.DataFrame) -> pd.DataFrame:
    """Construct pre-submission author histories without repeated set slicing."""
    observation_start = float(comments["created_utc"].min())
    pairs = (
        comments[["submission_id", "author", "thread_start_utc"]]
        .drop_duplicates()
        .sort_values(["author", "thread_start_utc", "submission_id"])
    )

    def cumulative_unique(values: np.ndarray) -> np.ndarray:
        seen: set[str] = set()
        counts = np.empty(len(values), dtype=int)
        for index, value in enumerate(values):
            seen.add(str(value))
            counts[index] = len(seen)
        return counts

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
        prior_subreddit_counts = cumulative_unique(author_comments["subreddit"].astype(str).to_numpy())
        prior_group_counts = cumulative_unique(author_comments["community_group_proxy"].astype(str).to_numpy())
        correction_totals = np.cumsum(author_comments["public_correction_pred"].to_numpy(dtype=int))
        prior_subreddits = np.where(cutoffs > 0, prior_subreddit_counts[np.maximum(cutoffs - 1, 0)], 0)
        prior_groups = np.where(cutoffs > 0, prior_group_counts[np.maximum(cutoffs - 1, 0)], 0)
        prior_corrections = np.where(cutoffs > 0, correction_totals[np.maximum(cutoffs - 1, 0)], 0)
        result = author_pairs.copy()
        result["prior_comments"] = cutoffs.astype(int)
        result["prior_subreddits"] = prior_subreddits.astype(int)
        result["prior_community_groups"] = prior_groups.astype(int)
        result["prior_corrective_responses"] = prior_corrections.astype(int)
        result["prior_corrective_response_rate"] = np.divide(
            prior_corrections,
            cutoffs,
            out=np.zeros_like(prior_corrections, dtype=float),
            where=cutoffs > 0,
        )
        result["prior_cross_subreddit_participation"] = (prior_subreddits > 1).astype(int)
        result["prior_cross_community_participation"] = (prior_groups > 1).astype(int)
        result["prior_history_observed"] = (cutoffs > 0).astype(int)
        result["prior_history_eligible"] = (cutoffs >= 2).astype(int)
        result["history_observation_days"] = np.maximum(
            (result["thread_start_utc"].to_numpy(dtype=float) - observation_start) / 86400.0,
            0.0,
        )
        frames.append(result)
    return pd.concat(frames, ignore_index=True)


def context_split(
    thread: pd.DataFrame,
    window_type: str,
    window_value: float,
    horizon_days: float,
) -> tuple[pd.DataFrame, pd.DataFrame, float] | None:
    start = float(thread["thread_start_utc"].iloc[0])
    horizon = start + horizon_days * 86400.0
    observed = thread.loc[thread["created_utc"] <= horizon].copy()
    if observed.empty:
        return None
    if window_type == "comments":
        count = int(window_value)
        if len(observed) <= count:
            return None
        early = observed.iloc[:count].copy()
        cutoff = float(early["created_utc"].iloc[-1])
        later = observed.loc[observed["created_utc"] > cutoff].copy()
    elif window_type == "hours":
        cutoff = start + float(window_value) * 3600.0
        if cutoff >= horizon:
            return None
        early = observed.loc[observed["created_utc"] <= cutoff].copy()
        later = observed.loc[observed["created_utc"] > cutoff].copy()
        if early.empty or later.empty:
            return None
    else:
        raise ValueError(f"Unsupported window type: {window_type}")
    if later.empty:
        return None
    return early, later, cutoff


def early_context_features(
    early: pd.DataFrame,
    history_lookup: pd.DataFrame,
    cutoff: float,
    window_type: str,
) -> dict[str, Any]:
    submission_id = str(early["submission_id"].iloc[0])
    author_names = list(dict.fromkeys(early["author"].astype(str)))
    cross_values = []
    history_values = []
    for author in author_names:
        key = (submission_id, author)
        if key not in history_lookup.index:
            cross_values.append(0)
            history_values.append(0)
            continue
        item = history_lookup.loc[key]
        cross_values.append(int(item["prior_cross_community_participation"]))
        history_values.append(int(item["prior_history_eligible"]))
    start = float(early["thread_start_utc"].iloc[0])
    duration_hours = max((cutoff - start) / 3600.0, 0.0)
    if window_type == "comments":
        activity_control = math.log1p(duration_hours)
    else:
        activity_control = math.log1p(len(early))
    relation_columns = RELATION_PROBABILITY_COLUMNS + [NO_IDENTIFIED_RELATION_COLUMN]
    mean_relation_probability = early[relation_columns].to_numpy(dtype=float).mean(axis=0)
    nonzero_relation_probability = mean_relation_probability[mean_relation_probability > 0]
    relation_entropy = -float(
        np.sum(nonzero_relation_probability * np.log(nonzero_relation_probability))
    ) / math.log(len(relation_columns))
    early_correction_ids = set(early.loc[early["public_correction_pred"].eq(1), "comment_id"])
    reply_to_early_correction = early["parent_id"].isin(early_correction_ids)
    directed_hostility = reply_to_early_correction & early["hostile_language"].eq(1)
    ambient_hostility = early["hostile_language"].eq(1) & ~reply_to_early_correction
    return {
        "early_comment_count": int(len(early)),
        "early_author_count": int(len(author_names)),
        "early_corrective_response_presence": int(early["public_correction_pred"].max() > 0),
        "early_corrective_response_rate": float(early["public_correction_pred"].mean()),
        "early_response_relation_diversity": relation_entropy,
        "early_relation_type_coverage": float(early["relation_type_available"].mean()),
        "early_ambient_hostile_language_rate": float(ambient_hostility.mean()),
        "early_correction_reply_presence": int(reply_to_early_correction.any()),
        "early_correction_directed_hostility_presence": int(directed_hostility.any()),
        "early_correction_directed_hostility_rate": float(directed_hostility.mean()),
        "early_cross_community_participant_share": float(np.mean(cross_values)),
        "early_prior_history_coverage": float(np.mean(history_values)),
        "early_candidate_response_share": float((early["pair_relation_candidate_count"] > 0).mean()),
        "early_context_activity": activity_control,
        "early_context_duration_hours": duration_hours,
    }


def build_first_response_dataset(
    comments: pd.DataFrame,
    pair_history: pd.DataFrame,
    window_type: str,
    window_value: float,
    horizon_days: float,
    min_prior_comments: int,
    min_history_days: float,
    require_candidate_target: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    history_lookup = pair_history.set_index(["submission_id", "author"])
    rows = []
    flow = defaultdict(int)
    flow["source_threads"] = int(comments["submission_id"].nunique())
    flow["source_comments_with_valid_authors"] = int(len(comments))
    for submission_id, thread in comments.groupby("submission_id", sort=False):
        split = context_split(thread, window_type, window_value, horizon_days)
        if split is None:
            continue
        early, later, cutoff = split
        flow["threads_with_early_and_later_context"] += 1
        early_authors = set(early["author"].astype(str))
        entrants = later.loc[~later["author"].astype(str).isin(early_authors)].copy()
        if entrants.empty:
            continue
        flow["threads_with_later_entrants"] += 1
        first = (
            entrants.sort_values(["author", "created_utc", "comment_id"])
            .groupby("author", as_index=False, sort=False)
            .first()
        )
        features = early_context_features(early, history_lookup, cutoff, window_type)
        for response in first.itertuples(index=False):
            if require_candidate_target and int(response.pair_relation_candidate_count) < 1:
                continue
            key = (str(submission_id), str(response.author))
            if key not in history_lookup.index:
                continue
            author_history = history_lookup.loc[key]
            flow["later_entrant_first_responses"] += 1
            if int(author_history["prior_comments"]) < min_prior_comments:
                continue
            if float(author_history["history_observation_days"]) < min_history_days:
                continue
            flow["main_analysis_responses"] += 1
            row = {
                "submission_id": str(submission_id),
                "author": str(response.author),
                "author_hash": stable_id(str(response.author)),
                "subreddit": str(response.subreddit),
                "community_group_proxy": str(response.community_group_proxy),
                "first_later_corrective_response": int(response.public_correction_pred),
                "first_later_corrective_score": float(response.public_correction_score),
                "first_later_candidate_count": int(response.pair_relation_candidate_count),
                "first_later_body_words": int(response.body_words),
                "response_delay_hours": (float(response.created_utc) - float(response.thread_start_utc)) / 3600.0,
                **features,
                **author_history.to_dict(),
            }
            rows.append(row)
    frame = pd.DataFrame(rows)
    flow_rows = pd.DataFrame([{"stage": key, "count": value} for key, value in flow.items()])
    return frame, flow_rows


def build_continuation_dataset(
    comments: pd.DataFrame,
    pair_history: pd.DataFrame,
    window_type: str,
    window_value: float,
    horizon_days: float,
    min_prior_comments: int,
    min_history_days: float,
) -> pd.DataFrame:
    history_lookup = pair_history.set_index(["submission_id", "author"])
    rows = []
    for submission_id, thread in comments.groupby("submission_id", sort=False):
        split = context_split(thread, window_type, window_value, horizon_days)
        if split is None:
            continue
        early, later, cutoff = split
        early_authors = list(dict.fromkeys(early["author"].astype(str)))
        later_authors = set(later["author"].astype(str))
        cross_status = {
            author: int(history_lookup.loc[(str(submission_id), author), "prior_cross_subreddit_participation"])
            for author in early_authors
            if (str(submission_id), author) in history_lookup.index
        }
        start = float(early["thread_start_utc"].iloc[0])
        activity_control = (
            math.log1p(max((cutoff - start) / 3600.0, 0.0))
            if window_type == "comments"
            else math.log1p(len(early))
        )
        for author in early_authors:
            key = (str(submission_id), author)
            if key not in history_lookup.index:
                continue
            author_history = history_lookup.loc[key]
            if int(author_history["prior_comments"]) < min_prior_comments:
                continue
            if float(author_history["history_observation_days"]) < min_history_days:
                continue
            focal = early.loc[early["author"].astype(str) == author]
            other = early.loc[early["author"].astype(str) != author]
            other_authors = [item for item in early_authors if item != author]
            rows.append(
                {
                    "submission_id": str(submission_id),
                    "author": author,
                    "author_hash": stable_id(author),
                    "subreddit": str(early["subreddit"].iloc[0]),
                    "community_group_proxy": str(early["community_group_proxy"].iloc[0]),
                    "continued_after_early_context": int(author in later_authors),
                    "focal_early_comment_count": int(len(focal)),
                    "focal_early_corrective_response": int(focal["public_correction_pred"].max() > 0),
                    "other_early_corrective_response_presence": int(
                        not other.empty and other["public_correction_pred"].max() > 0
                    ),
                    "other_early_hostile_language_rate": float(other["hostile_language"].mean())
                    if not other.empty
                    else 0.0,
                    "other_early_cross_subreddit_participant_share": float(
                        np.mean([cross_status.get(item, 0) for item in other_authors])
                    )
                    if other_authors
                    else 0.0,
                    "early_context_activity": activity_control,
                    **author_history.to_dict(),
                }
            )
    return pd.DataFrame(rows)


def standardize(frame: pd.DataFrame, columns: list[str]) -> tuple[pd.DataFrame, dict[str, dict[str, float]]]:
    frame = frame.copy()
    moments: dict[str, dict[str, float]] = {}
    for column in columns:
        mean = float(frame[column].mean())
        std = float(frame[column].std(ddof=0))
        if not np.isfinite(std) or std <= 0:
            std = 1.0
        frame[f"{column}_z"] = (frame[column] - mean) / std
        moments[column] = {"mean": mean, "std": std}
    return frame, moments


def prepare_first_response_model(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, dict[str, float]]]:
    frame = frame.copy()
    frame["log_prior_comments"] = np.log1p(frame["prior_comments"].astype(float))
    frame, moments = standardize(
        frame,
        [
            "early_cross_community_participant_share",
            "early_response_relation_diversity",
            "early_ambient_hostile_language_rate",
        ],
    )
    return frame, moments


def prepare_continuation_model(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, dict[str, float]]]:
    frame = frame.copy()
    frame["log_prior_comments"] = np.log1p(frame["prior_comments"].astype(float))
    frame, moments = standardize(
        frame,
        ["other_early_cross_subreddit_participant_share", "other_early_hostile_language_rate"],
    )
    return frame, moments


def fit_two_way_logit(formula: str, frame: pd.DataFrame) -> tuple[Any, np.ndarray]:
    result = smf.logit(formula=formula, data=frame).fit(disp=False, maxiter=300)
    thread_group = pd.factorize(frame["submission_id"])[0]
    author_group = pd.factorize(frame["author_hash"])[0]
    covariance, _, _ = cov_cluster_2groups(result, thread_group, author_group, use_correction=True)
    return result, np.asarray(covariance, dtype=float)


def coefficient_table(result: Any, covariance: np.ndarray, model_name: str) -> pd.DataFrame:
    params = np.asarray(result.params, dtype=float)
    variances = np.diag(covariance)
    standard_errors = np.sqrt(np.where(variances >= 0, variances, np.nan))
    z_values = params / standard_errors
    p_values = 2.0 * norm.sf(np.abs(z_values))
    rows = []
    for index, term in enumerate(result.params.index):
        low = params[index] - 1.96 * standard_errors[index]
        high = params[index] + 1.96 * standard_errors[index]
        rows.append(
            {
                "model": model_name,
                "term": term,
                "coefficient": params[index],
                "std_error_two_way_clustered": standard_errors[index],
                "z": z_values[index],
                "p_value": p_values[index],
                "odds_ratio": math.exp(params[index]),
                "odds_ratio_ci_low": math.exp(low),
                "odds_ratio_ci_high": math.exp(high),
            }
        )
    return pd.DataFrame(rows)


def prediction_and_gradient(result: Any, frame: pd.DataFrame) -> tuple[float, np.ndarray]:
    design_info = result.model.data.design_info
    matrix = np.asarray(build_design_matrices([design_info], frame, return_type="dataframe")[0], dtype=float)
    params = np.asarray(result.params, dtype=float)
    linear = matrix @ params
    probabilities = 1.0 / (1.0 + np.exp(-np.clip(linear, -35, 35)))
    gradient = np.mean(probabilities[:, None] * (1.0 - probabilities[:, None]) * matrix, axis=0)
    return float(probabilities.mean()), gradient


def contrast_from_scenarios(
    result: Any,
    covariance: np.ndarray,
    scenarios: list[tuple[float, pd.DataFrame]],
) -> tuple[float, float, float, float]:
    estimate = 0.0
    gradient = np.zeros(len(result.params), dtype=float)
    for weight, scenario in scenarios:
        value, scenario_gradient = prediction_and_gradient(result, scenario)
        estimate += weight * value
        gradient += weight * scenario_gradient
    variance = float(gradient @ covariance @ gradient)
    standard_error = math.sqrt(max(variance, 0.0))
    return estimate, standard_error, estimate - 1.96 * standard_error, estimate + 1.96 * standard_error


def first_response_contrasts(
    result: Any,
    covariance: np.ndarray,
    frame: pd.DataFrame,
    moments: dict[str, dict[str, float]],
) -> pd.DataFrame:
    rows = []

    def binary_contrast(variable: str, label: str) -> None:
        low = frame.copy()
        high = frame.copy()
        low[variable] = 0
        high[variable] = 1
        estimate, se, ci_low, ci_high = contrast_from_scenarios(result, covariance, [(1.0, high), (-1.0, low)])
        rows.append(
            {
                "contrast": label,
                "estimate_probability_points": estimate,
                "std_error": se,
                "ci_low": ci_low,
                "ci_high": ci_high,
            }
        )

    binary_contrast("prior_cross_community_participation", "Prior cross-community participation: yes vs. no")
    binary_contrast("early_corrective_response_presence", "Early corrective-response presence: present vs. absent")

    low_hostility = frame.copy()
    high_hostility = frame.copy()
    low_hostility["early_ambient_hostile_language_rate_z"] = 0.0
    high_hostility["early_ambient_hostile_language_rate_z"] = 1.0
    estimate, se, ci_low, ci_high = contrast_from_scenarios(
        result, covariance, [(1.0, high_hostility), (-1.0, low_hostility)]
    )
    rows.append(
        {
            "contrast": "Early ambient hostile-language rate: one-SD increase",
            "estimate_probability_points": estimate,
            "std_error": se,
            "ci_low": ci_low,
            "ci_high": ci_high,
        }
    )

    diversity_low = frame.copy()
    diversity_high = frame.copy()
    diversity_low["early_response_relation_diversity_z"] = 0.0
    diversity_high["early_response_relation_diversity_z"] = 1.0
    estimate, se, ci_low, ci_high = contrast_from_scenarios(
        result, covariance, [(1.0, diversity_high), (-1.0, diversity_low)]
    )
    rows.append(
        {
            "contrast": "Early response-relation diversity: one-SD increase",
            "estimate_probability_points": estimate,
            "std_error": se,
            "ci_low": ci_low,
            "ci_high": ci_high,
        }
    )

    share_moment = moments["early_cross_community_participant_share"]
    raw_low = float(frame["early_cross_community_participant_share"].quantile(0.25))
    raw_high = float(frame["early_cross_community_participant_share"].quantile(0.75))
    z_low = (raw_low - share_moment["mean"]) / share_moment["std"]
    z_high = (raw_high - share_moment["mean"]) / share_moment["std"]
    c0_low = frame.copy()
    c1_low = frame.copy()
    c0_high = frame.copy()
    c1_high = frame.copy()
    for scenario, cross, share in [
        (c0_low, 0, z_low),
        (c1_low, 1, z_low),
        (c0_high, 0, z_high),
        (c1_high, 1, z_high),
    ]:
        scenario["prior_cross_community_participation"] = cross
        scenario["early_cross_community_participant_share_z"] = share
    estimate, se, ci_low, ci_high = contrast_from_scenarios(
        result,
        covariance,
        [(1.0, c1_high), (-1.0, c0_high), (-1.0, c1_low), (1.0, c0_low)],
    )
    rows.append(
        {
            "contrast": "Second difference in prior participation gap: Q3 vs. Q1 early cross-community share",
            "estimate_probability_points": estimate,
            "std_error": se,
            "ci_low": ci_low,
            "ci_high": ci_high,
        }
    )
    return pd.DataFrame(rows)


def correction_signal_scenario_table(
    result: Any,
    covariance: np.ndarray,
    frame: pd.DataFrame,
    moments: dict[str, dict[str, float]],
) -> pd.DataFrame:
    rows = []
    scenarios = [
        ("No early corrective response", 0, 0, 0),
        ("Early correction without a direct reply", 1, 0, 0),
        ("Early correction with a nonhostile direct reply", 1, 1, 0),
        ("Early correction with a hostile direct reply", 1, 1, 1),
    ]
    for label, correction, reply, directed_hostility in scenarios:
        scenario = frame.copy()
        scenario["early_corrective_response_presence"] = correction
        scenario["early_correction_reply_presence"] = reply
        scenario["early_correction_directed_hostility_presence"] = directed_hostility
        estimate, gradient = prediction_and_gradient(result, scenario)
        variance = float(gradient @ covariance @ gradient)
        se = math.sqrt(max(variance, 0.0))
        rows.append(
            {
                "early_correction_signal": label,
                "predicted_probability": estimate,
                "ci_low": estimate - 1.96 * se,
                "ci_high": estimate + 1.96 * se,
            }
        )
    return pd.DataFrame(rows)


def descriptive_statistics(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "first_later_corrective_response",
        "prior_cross_community_participation",
        "prior_comments",
        "prior_corrective_response_rate",
        "early_corrective_response_presence",
        "early_cross_community_participant_share",
        "early_response_relation_diversity",
        "early_relation_type_coverage",
        "early_ambient_hostile_language_rate",
        "early_correction_reply_presence",
        "early_correction_directed_hostility_presence",
        "early_prior_history_coverage",
        "early_context_duration_hours",
        "response_delay_hours",
    ]
    rows = []
    for column in columns:
        values = pd.to_numeric(frame[column], errors="coerce").dropna()
        rows.append(
            {
                "variable": column,
                "n": int(len(values)),
                "mean": float(values.mean()),
                "std": float(values.std()),
                "min": float(values.min()),
                "p25": float(values.quantile(0.25)),
                "median": float(values.median()),
                "p75": float(values.quantile(0.75)),
                "max": float(values.max()),
            }
        )
    return pd.DataFrame(rows)


def window_distribution(comments: pd.DataFrame) -> pd.DataFrame:
    rows = []
    grouped = comments.groupby("submission_id", sort=False)
    for submission_id, thread in grouped:
        start = float(thread["thread_start_utc"].iloc[0])
        ordered = thread.sort_values(["created_utc", "comment_id"])
        row = {
            "submission_id": submission_id,
            "comments": int(len(ordered)),
            "thread_duration_days": (float(ordered["created_utc"].max()) - start) / 86400.0,
        }
        for count in [5, 10, 20]:
            row[f"hours_to_comment_{count}"] = (
                (float(ordered["created_utc"].iloc[count - 1]) - start) / 3600.0 if len(ordered) >= count else np.nan
            )
        rows.append(row)
    frame = pd.DataFrame(rows)
    summaries = []
    for column in ["hours_to_comment_5", "hours_to_comment_10", "hours_to_comment_20", "thread_duration_days"]:
        values = frame[column].dropna()
        summaries.append(
            {
                "measure": column,
                "n": int(len(values)),
                "mean": float(values.mean()),
                "median": float(values.median()),
                "p75": float(values.quantile(0.75)),
                "p90": float(values.quantile(0.90)),
                "p95": float(values.quantile(0.95)),
                "p99": float(values.quantile(0.99)),
                "max": float(values.max()),
            }
        )
    return pd.DataFrame(summaries)


def fit_first_response_specification(
    frame: pd.DataFrame,
    model_name: str,
    adjust_prior_corrective_propensity: bool = True,
    adjust_candidate_multiplicity: bool = False,
    fixed_effect: str = "subreddit",
) -> tuple[Any, np.ndarray, pd.DataFrame, dict[str, dict[str, float]]]:
    model_frame, moments = prepare_first_response_model(frame)
    candidate_control = ""
    if adjust_candidate_multiplicity:
        if (model_frame["first_later_candidate_count"] < 1).any():
            raise ValueError("Candidate-multiplicity adjustment requires at least one candidate target")
        model_frame["two_candidate_targets"] = (model_frame["first_later_candidate_count"] >= 2).astype(int)
        candidate_control = "two_candidate_targets + "
    propensity_control = "prior_corrective_response_rate + " if adjust_prior_corrective_propensity else ""
    formula = (
        "first_later_corrective_response ~ "
        "prior_cross_community_participation * early_cross_community_participant_share_z + "
        "early_corrective_response_presence + early_response_relation_diversity_z + "
        "early_ambient_hostile_language_rate_z + early_correction_reply_presence + "
        "early_correction_directed_hostility_presence + "
        f"{propensity_control}{candidate_control}log_prior_comments + early_prior_history_coverage + "
        f"early_relation_type_coverage + early_context_activity + C({fixed_effect})"
    )
    result, covariance = fit_two_way_logit(formula, model_frame)
    table = coefficient_table(result, covariance, model_name)
    return result, covariance, table, moments


def fit_continuation_specification(frame: pd.DataFrame) -> tuple[Any, np.ndarray, pd.DataFrame]:
    model_frame, _ = prepare_continuation_model(frame)
    formula = (
        "continued_after_early_context ~ "
        "prior_cross_subreddit_participation * other_early_cross_subreddit_participant_share_z + "
        "other_early_corrective_response_presence + other_early_hostile_language_rate_z + "
        "focal_early_corrective_response + focal_early_comment_count + "
        "prior_corrective_response_rate + log_prior_comments + early_context_activity + "
        "C(community_group_proxy)"
    )
    result, covariance = fit_two_way_logit(formula, model_frame)
    return result, covariance, coefficient_table(result, covariance, "early_author_continuation")


def sensitivity_runs(
    comments: pd.DataFrame,
    pair_history: pd.DataFrame,
    args: argparse.Namespace,
) -> pd.DataFrame:
    specifications = [
        ("comments", 5, 7, 2, 7, False),
        ("comments", 10, 1, 2, 7, False),
        ("comments", 10, 7, 0, 7, False),
        ("comments", 10, 7, 1, 7, False),
        ("comments", 10, 7, 5, 7, False),
        ("comments", 10, 7, 2, 0, False),
        ("comments", 10, 7, 2, 14, False),
        ("comments", 10, 7, 2, 7, True),
        ("comments", 10, 30, 2, 7, False),
        ("comments", 20, 7, 2, 7, False),
        ("hours", 1, 7, 2, 7, False),
        ("hours", 6, 7, 2, 7, False),
        ("hours", 24, 7, 2, 7, False),
    ]
    rows = []
    for window_type, window_value, horizon_days, min_prior, min_history_days, candidate_only in specifications:
        frame, _ = build_first_response_dataset(
            comments,
            pair_history,
            window_type,
            window_value,
            horizon_days,
            min_prior,
            min_history_days,
            candidate_only,
        )
        if len(frame) < 500 or frame["first_later_corrective_response"].nunique() < 2:
            continue
        try:
            result, covariance, table, _ = fit_first_response_specification(
                frame,
                (
                    f"{window_type}_{window_value}_horizon_{horizon_days}_prior_{min_prior}_"
                    f"history_{min_history_days}_candidate_{int(candidate_only)}"
                ),
                fixed_effect="community_group_proxy",
            )
        except Exception as error:  # pragma: no cover - logged for research runs
            rows.append(
                {
                    "window_type": window_type,
                    "window_value": window_value,
                    "horizon_days": horizon_days,
                    "min_prior_comments": min_prior,
                    "min_history_days": min_history_days,
                    "candidate_target_required": candidate_only,
                    "n": len(frame),
                    "error": str(error),
                }
            )
            continue
        lookup = table.set_index("term")
        for term in MAIN_TERMS:
            if term not in lookup.index:
                continue
            item = lookup.loc[term]
            rows.append(
                {
                    "window_type": window_type,
                    "window_value": window_value,
                    "horizon_days": horizon_days,
                    "min_prior_comments": min_prior,
                    "min_history_days": min_history_days,
                    "candidate_target_required": candidate_only,
                    "n": int(result.nobs),
                    "outcome_mean": float(frame["first_later_corrective_response"].mean()),
                    "term": term,
                    "odds_ratio": float(item["odds_ratio"]),
                    "ci_low": float(item["odds_ratio_ci_low"]),
                    "ci_high": float(item["odds_ratio_ci_high"]),
                    "p_value": float(item["p_value"]),
                    "converged": bool(result.mle_retvals.get("converged", False)),
                    "error": "",
                }
            )
    return pd.DataFrame(rows)


def threshold_sensitivity_runs(comments: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    rows = []
    for threshold in [0.3, 0.4, 0.5, 0.6, 0.7]:
        threshold_comments = comments.copy()
        threshold_comments["public_correction_pred"] = (
            threshold_comments["public_correction_score"] >= threshold
        ).astype(int)
        threshold_history = build_pair_history(threshold_comments)
        frame, _ = build_first_response_dataset(
            threshold_comments,
            threshold_history,
            "comments",
            args.early_comments,
            args.horizon_days,
            args.min_prior_comments,
            args.min_history_days,
        )
        result, covariance, table, _ = fit_first_response_specification(
            frame,
            f"threshold_{threshold:.1f}",
            fixed_effect="community_group_proxy",
        )
        lookup = table.set_index("term")
        for term in MAIN_TERMS:
            if term not in lookup.index:
                continue
            item = lookup.loc[term]
            rows.append(
                {
                    "classification_threshold": threshold,
                    "n": int(result.nobs),
                    "outcome_mean": float(frame["first_later_corrective_response"].mean()),
                    "term": term,
                    "odds_ratio": float(item["odds_ratio"]),
                    "ci_low": float(item["odds_ratio_ci_low"]),
                    "ci_high": float(item["odds_ratio_ci_high"]),
                    "p_value": float(item["p_value"]),
                    "converged": bool(result.mle_retvals.get("converged", False)),
                }
            )
    return pd.DataFrame(rows)


def run(args: argparse.Namespace) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = args.output_dir / "tables"
    metrics_dir = args.output_dir / "metrics"
    tables_dir.mkdir(exist_ok=True)
    metrics_dir.mkdir(exist_ok=True)

    comments = load_comments(args)
    pair_history = build_pair_history(comments)
    main_frame, sample_flow = build_first_response_dataset(
        comments,
        pair_history,
        "comments",
        args.early_comments,
        args.horizon_days,
        args.min_prior_comments,
        args.min_history_days,
    )

    temporal_result, temporal_cov, temporal_table, _ = fit_first_response_specification(
        main_frame,
        "temporally_ordered_first_response",
        adjust_prior_corrective_propensity=False,
    )
    main_result, main_cov, main_table, moments = fit_first_response_specification(
        main_frame,
        "propensity_adjusted_first_response",
    )
    coefficients = pd.concat([temporal_table, main_table], ignore_index=True)
    contrasts = first_response_contrasts(main_result, main_cov, prepare_first_response_model(main_frame)[0], moments)
    correction_signal = correction_signal_scenario_table(
        main_result,
        main_cov,
        prepare_first_response_model(main_frame)[0],
        moments,
    )

    write_csv(tables_dir / "sample_flow.csv", sample_flow)
    write_csv(tables_dir / "descriptive_statistics.csv", descriptive_statistics(main_frame))
    write_csv(tables_dir / "model_coefficients.csv", coefficients)
    write_csv(tables_dir / "average_probability_contrasts.csv", contrasts)
    write_csv(tables_dir / "correction_signal_model_implied_probabilities.csv", correction_signal)
    write_csv(tables_dir / "thread_window_distributions.csv", window_distribution(comments))
    write_csv(tables_dir / "main_analysis_frame.csv", main_frame.drop(columns=["author"], errors="ignore"))

    if not args.skip_sensitivity:
        write_csv(tables_dir / "sensitivity_models.csv", sensitivity_runs(comments, pair_history, args))
        write_csv(tables_dir / "threshold_sensitivity_models.csv", threshold_sensitivity_runs(comments, args))

    summary = {
        "run_status": "revised_corrective_response_models_complete",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "command": " ".join(sys.argv),
        "predictions": str(args.predictions),
        "comments": str(args.comments),
        "submissions": str(args.submissions),
        "output_dir": str(args.output_dir),
        "design": {
            "early_context": f"first {args.early_comments} posted comments",
            "outcome": "first later response by an author absent from the early context",
            "outcome_horizon_days_from_submission": args.horizon_days,
            "minimum_prior_comments": args.min_prior_comments,
            "minimum_history_observation_days": args.min_history_days,
            "author_history_cutoff": "focal submission creation time",
            "covariance": "two-way clustered by submission and author",
        },
        "source_comments_with_valid_authors": int(len(comments)),
        "source_threads": int(comments["submission_id"].nunique()),
        "main_n": int(main_result.nobs),
        "main_outcome_mean": float(main_frame["first_later_corrective_response"].mean()),
        "main_unique_threads": int(main_frame["submission_id"].nunique()),
        "main_unique_authors": int(main_frame["author_hash"].nunique()),
        "main_prior_cross_community_share": float(main_frame["prior_cross_community_participation"].mean()),
        "temporal_model_converged": bool(temporal_result.mle_retvals.get("converged", False)),
        "main_converged": bool(main_result.mle_retvals.get("converged", False)),
        "standardization_moments": moments,
    }
    write_json(metrics_dir / "run_summary.json", summary)
    (metrics_dir / "temporally_ordered_model_summary.txt").write_text(
        temporal_result.summary().as_text(), encoding="utf-8"
    )
    (metrics_dir / "main_model_summary.txt").write_text(main_result.summary().as_text(), encoding="utf-8")
    (args.output_dir / "run.log").write_text(
        "\n".join(
            [
                "revised corrective-response model run",
                f"generated_utc={summary['generated_utc']}",
                f"command={summary['command']}",
                f"main_n={summary['main_n']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fit temporally ordered corrective-response models.")
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
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/revised_corrective_response_models_20260714T000000Z"),
    )
    parser.add_argument("--early-comments", type=int, default=10)
    parser.add_argument("--horizon-days", type=float, default=7.0)
    parser.add_argument("--min-prior-comments", type=int, default=2)
    parser.add_argument("--min-history-days", type=float, default=7.0)
    parser.add_argument("--skip-sensitivity", action="store_true")
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
