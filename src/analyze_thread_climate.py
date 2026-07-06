#!/usr/bin/env python3
"""Build exploratory thread-climate variables for correction analysis.

This script uses observable textual and conversational proxies. It does not
claim to observe private recognition, perceived sanction, or correction intent.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REMOVED_AUTHORS = {"", "[deleted]", "deleted", "automoderator"}

HOSTILITY_TERMS = [
    "idiot",
    "idiots",
    "moron",
    "morons",
    "stupid",
    "dumb",
    "clown",
    "liar",
    "liars",
    "troll",
    "trolls",
    "shill",
    "shills",
    "paid shill",
    "brainwashed",
    "cult",
    "bullshit",
    "fuck",
    "fucking",
    "shut up",
    "sheep",
    "sheeple",
]

ANTI_INSTITUTIONAL_TERMS = [
    "big pharma",
    "pharma",
    "fauci",
    "cdc",
    "mainstream media",
    "msm",
    "government lies",
    "plandemic",
    "scamdemic",
    "experimental vaccine",
    "gene therapy",
    "fake pandemic",
    "wake up",
    "sheep",
    "sheeple",
    "natural immunity",
    "vaers",
    "ivermectin",
    "hydroxychloroquine",
    "my body my choice",
    "mandate",
    "mandates",
    "tyranny",
    "censorship",
    "nuremberg",
    "depopulation",
    "microchip",
    "5g",
]


def compile_terms(terms: list[str]) -> list[re.Pattern[str]]:
    patterns = []
    for term in terms:
        escaped = re.escape(term.lower())
        if " " in term:
            patterns.append(re.compile(escaped))
        else:
            patterns.append(re.compile(rf"\b{escaped}\b"))
    return patterns


HOSTILITY_PATTERNS = compile_terms(HOSTILITY_TERMS)
ANTI_INSTITUTIONAL_PATTERNS = compile_terms(ANTI_INSTITUTIONAL_TERMS)


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


def normalize_author(value: Any) -> str | None:
    author = normalize_token(value)
    if author in REMOVED_AUTHORS:
        return None
    return author


def compact_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def to_int(value: Any) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0


def to_float(value: Any) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def div(num: int | float, den: int | float) -> float:
    return float(num) / float(den) if den else 0.0


def entropy(values: Counter[str]) -> float:
    total = sum(values.values())
    if not total:
        return 0.0
    out = 0.0
    for count in values.values():
        p = count / total
        out -= p * math.log(p)
    return out


def mean(values: list[float]) -> float:
    return float(sum(values)) / float(len(values)) if values else 0.0


def dominant_value(values: Counter[str]) -> str:
    if not values:
        return "unknown"
    return values.most_common(1)[0][0]


def cue_category(item: dict[str, Any]) -> str:
    if int(item.get("public_correction_pred", 0)) == 1:
        return "correction"
    if int(item.get("anti_institutional_cue", 0)) == 1:
        return "anti_institutional"
    if int(item.get("hostility_cue", 0)) == 1:
        return "hostility"
    return "other"


def author_heterogeneity_metrics(authors: set[str], user_profiles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    profiles = [user_profiles[author] for author in authors if author in user_profiles]
    dominant_group_counts = Counter(str(item.get("dominant_community_group", "unknown")) for item in profiles)
    dominant_subreddit_counts = Counter(str(item.get("dominant_subreddit", "unknown")) for item in profiles)
    cross_group_authors = sum(int(item.get("cross_group_observed", 0)) for item in profiles)
    cross_subreddit_authors = sum(int(item.get("cross_subreddit_observed", 0)) for item in profiles)
    return {
        "audience_profiled_authors": len(profiles),
        "audience_cross_group_authors": cross_group_authors,
        "audience_cross_group_author_share": div(cross_group_authors, len(profiles)),
        "audience_cross_subreddit_authors": cross_subreddit_authors,
        "audience_cross_subreddit_author_share": div(cross_subreddit_authors, len(profiles)),
        "audience_mean_community_group_entropy": mean(
            [float(item.get("community_group_entropy", 0.0)) for item in profiles]
        ),
        "audience_mean_subreddit_entropy": mean([float(item.get("subreddit_entropy", 0.0)) for item in profiles]),
        "audience_dominant_community_group_entropy": entropy(dominant_group_counts),
        "audience_dominant_subreddit_entropy": entropy(dominant_subreddit_counts),
    }


def has_match(text: str, patterns: list[re.Pattern[str]]) -> int:
    lowered = text.lower()
    return int(any(pattern.search(lowered) for pattern in patterns))


def quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(max(math.ceil(q * len(ordered)) - 1, 0), len(ordered) - 1)
    return float(ordered[idx])


def load_predictions(path: Path) -> dict[str, dict[str, Any]]:
    predictions = {}
    for row in read_csv(path):
        comment_id = normalize_token(row.get("comment_id"))
        if not comment_id:
            continue
        predictions[comment_id] = {
            "comment_id": comment_id,
            "submission_id": normalize_token(row.get("submission_id")),
            "parent_id": normalize_token(row.get("parent_id")),
            "subreddit": normalize_token(row.get("subreddit")),
            "community_group_proxy": normalize_token(row.get("community_group_proxy")),
            "author": normalize_author(row.get("author")),
            "candidate_correction": to_int(row.get("candidate_correction")),
            "public_correction_score": to_float(row.get("public_correction_score")),
            "public_correction_pred": to_int(row.get("public_correction_pred")),
            "created_utc": to_float(row.get("created_utc")),
        }
    return predictions


def load_comment_records(comments_path: Path, predictions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for raw in iter_jsonl(comments_path):
        comment_id = normalize_token(raw.get("comment_id"))
        pred = predictions.get(comment_id)
        if not pred:
            continue
        body = compact_text(raw.get("body"))
        title = compact_text(raw.get("submission_title"))
        record = dict(pred)
        record.update(
            {
                "body": body,
                "submission_title": title,
                "text_for_climate": body,
                "level": to_int(raw.get("level")),
                "parent_author": normalize_author(raw.get("parent_author")),
                "submission_author": normalize_author(raw.get("submission_author")),
            }
        )
        record["hostility_cue"] = has_match(record["text_for_climate"], HOSTILITY_PATTERNS)
        record["anti_institutional_cue"] = has_match(record["text_for_climate"], ANTI_INSTITUTIONAL_PATTERNS)
        record["title_hostility_cue"] = has_match(title, HOSTILITY_PATTERNS)
        record["title_anti_institutional_cue"] = has_match(title, ANTI_INSTITUTIONAL_PATTERNS)
        records.append(record)
    return records


def build_user_profiles(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    subreddit_counts: dict[str, Counter[str]] = defaultdict(Counter)
    group_counts: dict[str, Counter[str]] = defaultdict(Counter)
    thread_sets: dict[str, set[str]] = defaultdict(set)

    for row in records:
        author = row.get("author")
        if not author:
            continue
        if author not in profiles:
            profiles[author] = {
                "author": author,
                "comments": 0,
                "predicted_public_corrections": 0,
            }
        profiles[author]["comments"] += 1
        profiles[author]["predicted_public_corrections"] += int(row["public_correction_pred"])
        subreddit_counts[author][str(row["subreddit"])] += 1
        group_counts[author][str(row["community_group_proxy"])] += 1
        thread_sets[author].add(str(row["submission_id"]))

    for author, item in profiles.items():
        item["subreddits_observed"] = len(subreddit_counts[author])
        item["community_groups_observed"] = len(group_counts[author])
        item["subreddit_entropy"] = entropy(subreddit_counts[author])
        item["community_group_entropy"] = entropy(group_counts[author])
        item["dominant_subreddit"] = dominant_value(subreddit_counts[author])
        item["dominant_community_group"] = dominant_value(group_counts[author])
        item["threads_observed"] = len(thread_sets[author])
        item["cross_subreddit_observed"] = int(item["subreddits_observed"] > 1)
        item["cross_group_observed"] = int(item["community_groups_observed"] > 1)
        item["correction_rate"] = div(item["predicted_public_corrections"], item["comments"])
    return profiles


def build_thread_profiles(
    records: list[dict[str, Any]],
    early_n: int,
    high_participation_author_threshold: int,
    user_profiles: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    user_profiles = user_profiles or {}
    by_thread: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        by_thread[str(row["submission_id"])].append(row)

    predicted_correction_ids = {str(row["comment_id"]) for row in records if int(row["public_correction_pred"]) == 1}
    hostile_reply_to_correction: Counter[str] = Counter()
    replies_to_correction: Counter[str] = Counter()
    corrections_with_hostile_reply: dict[str, set[str]] = defaultdict(set)

    for row in records:
        parent_id = str(row.get("parent_id") or "")
        if parent_id in predicted_correction_ids:
            submission_id = str(row["submission_id"])
            replies_to_correction[submission_id] += 1
            if int(row["hostility_cue"]) == 1:
                hostile_reply_to_correction[submission_id] += 1
                corrections_with_hostile_reply[submission_id].add(parent_id)

    profiles = []
    for submission_id, items in by_thread.items():
        items = sorted(items, key=lambda item: float(item["created_utc"]))
        for idx, item in enumerate(items, 1):
            item["thread_comment_rank"] = idx
            item["is_later_than_early_window"] = int(idx > early_n)
        early_items = items[: max(min(early_n, len(items)), 0)]
        later_items = items[max(min(early_n, len(items)), 0) :]
        authors = {str(item["author"]) for item in items if item.get("author")}
        early_authors = {str(item["author"]) for item in early_items if item.get("author")}
        correctors = {
            str(item["author"])
            for item in items
            if item.get("author") and int(item["public_correction_pred"]) == 1
        }
        later_correctors = {
            str(item["author"])
            for item in later_items
            if item.get("author") and int(item["public_correction_pred"]) == 1
        }
        predicted_corrections = sum(int(item["public_correction_pred"]) for item in items)
        later_predicted_corrections = sum(int(item["public_correction_pred"]) for item in later_items)
        thread_correction_ids = {str(item["comment_id"]) for item in items if int(item["public_correction_pred"]) == 1}
        first_public_correction_rank = 0
        for idx, item in enumerate(items, 1):
            if int(item["public_correction_pred"]) == 1:
                first_public_correction_rank = idx
                break
        audience_metrics = author_heterogeneity_metrics(authors, user_profiles)
        early_audience_metrics = {
            f"early_{key}": value for key, value in author_heterogeneity_metrics(early_authors, user_profiles).items()
        }
        discursive_cue_counts = Counter(cue_category(item) for item in items)
        early_discursive_cue_counts = Counter(cue_category(item) for item in early_items)

        item0 = items[0]
        row = {
            "submission_id": submission_id,
            "subreddit": item0["subreddit"],
            "community_group_proxy": item0["community_group_proxy"],
            "comments": len(items),
            "unique_authors": len(authors),
            "candidate_corrections": sum(int(item["candidate_correction"]) for item in items),
            "predicted_public_corrections": predicted_corrections,
            "predicted_correctors": len(correctors),
            "has_predicted_public_correction": int(predicted_corrections > 0),
            "later_comments": len(later_items),
            "later_predicted_public_corrections": later_predicted_corrections,
            "later_predicted_correctors": len(later_correctors),
            "has_later_predicted_public_correction": int(later_predicted_corrections > 0),
            "predicted_comment_rate": div(predicted_corrections, len(items)),
            "predicted_author_rate": div(len(correctors), len(authors)),
            "later_predicted_comment_rate": div(later_predicted_corrections, len(later_items)),
            "exposed_but_not_predicted_correctors": max(len(authors) - len(correctors), 0),
            "high_participation_no_predicted_correction": int(
                len(authors) >= high_participation_author_threshold and predicted_corrections == 0
            ),
            "hostility_comments": sum(int(item["hostility_cue"]) for item in items),
            "anti_institutional_comments": sum(int(item["anti_institutional_cue"]) for item in items),
            "discursive_cue_entropy": entropy(discursive_cue_counts),
            "early_discursive_cue_entropy": entropy(early_discursive_cue_counts),
            "title_hostility_cue": int(item0["title_hostility_cue"]),
            "title_anti_institutional_cue": int(item0["title_anti_institutional_cue"]),
            "hostility_rate": div(sum(int(item["hostility_cue"]) for item in items), len(items)),
            "anti_institutional_rate": div(sum(int(item["anti_institutional_cue"]) for item in items), len(items)),
            "early_comments": len(early_items),
            "early_predicted_public_corrections": sum(int(item["public_correction_pred"]) for item in early_items),
            "early_correction_norm_presence": int(any(int(item["public_correction_pred"]) == 1 for item in early_items)),
            "early_hostility_rate": div(sum(int(item["hostility_cue"]) for item in early_items), len(early_items)),
            "early_anti_institutional_rate": div(
                sum(int(item["anti_institutional_cue"]) for item in early_items), len(early_items)
            ),
            "first_public_correction_rank": first_public_correction_rank,
            "replies_to_predicted_corrections": replies_to_correction[submission_id],
            "hostile_replies_to_predicted_corrections": hostile_reply_to_correction[submission_id],
            "hostile_reply_to_correction_rate": div(
                hostile_reply_to_correction[submission_id], replies_to_correction[submission_id]
            ),
            "predicted_corrections_with_hostile_reply": len(
                corrections_with_hostile_reply[submission_id].intersection(thread_correction_ids)
            ),
            "sanction_to_correction_presence": int(hostile_reply_to_correction[submission_id] > 0),
        }
        row.update(audience_metrics)
        row.update(early_audience_metrics)
        profiles.append(row)
    return profiles


def attach_high_climate_flags(thread_profiles: list[dict[str, Any]], min_comments: int, q: float) -> dict[str, float]:
    eligible = [row for row in thread_profiles if int(row["comments"]) >= min_comments]
    hostility_threshold = quantile([float(row["hostility_rate"]) for row in eligible], q)
    anti_threshold = quantile([float(row["anti_institutional_rate"]) for row in eligible], q)
    early_hostility_threshold = quantile([float(row["early_hostility_rate"]) for row in eligible], q)
    early_anti_threshold = quantile([float(row["early_anti_institutional_rate"]) for row in eligible], q)
    early_audience_structural_threshold = quantile(
        [float(row["early_audience_cross_group_author_share"]) for row in eligible], q
    )
    audience_structural_threshold = quantile([float(row["audience_cross_group_author_share"]) for row in eligible], q)
    early_discursive_threshold = quantile([float(row["early_discursive_cue_entropy"]) for row in eligible], q)
    discursive_threshold = quantile([float(row["discursive_cue_entropy"]) for row in eligible], q)

    thresholds = {
        "high_climate_min_comments": min_comments,
        "climate_quantile": q,
        "hostility_rate_threshold": hostility_threshold,
        "anti_institutional_rate_threshold": anti_threshold,
        "early_hostility_rate_threshold": early_hostility_threshold,
        "early_anti_institutional_rate_threshold": early_anti_threshold,
        "early_audience_cross_group_author_share_threshold": early_audience_structural_threshold,
        "audience_cross_group_author_share_threshold": audience_structural_threshold,
        "early_discursive_cue_entropy_threshold": early_discursive_threshold,
        "discursive_cue_entropy_threshold": discursive_threshold,
    }

    for row in thread_profiles:
        eligible_row = int(row["comments"]) >= min_comments
        row["high_thread_hostility_climate"] = int(
            eligible_row and float(row["hostility_rate"]) >= hostility_threshold and float(row["hostility_rate"]) > 0
        )
        row["high_thread_anti_institutional_climate"] = int(
            eligible_row
            and float(row["anti_institutional_rate"]) >= anti_threshold
            and float(row["anti_institutional_rate"]) > 0
        )
        row["high_early_hostility_climate"] = int(
            eligible_row
            and float(row["early_hostility_rate"]) >= early_hostility_threshold
            and float(row["early_hostility_rate"]) > 0
        )
        row["high_early_anti_institutional_climate"] = int(
            eligible_row
            and float(row["early_anti_institutional_rate"]) >= early_anti_threshold
            and float(row["early_anti_institutional_rate"]) > 0
        )
        row["high_early_audience_structural_heterogeneity"] = int(
            eligible_row
            and float(row["early_audience_cross_group_author_share"]) >= early_audience_structural_threshold
            and float(row["early_audience_cross_group_author_share"]) > 0
        )
        row["high_audience_structural_heterogeneity"] = int(
            eligible_row
            and float(row["audience_cross_group_author_share"]) >= audience_structural_threshold
            and float(row["audience_cross_group_author_share"]) > 0
        )
        row["high_early_discursive_heterogeneity"] = int(
            eligible_row
            and float(row["early_discursive_cue_entropy"]) >= early_discursive_threshold
            and float(row["early_discursive_cue_entropy"]) > 0
        )
        row["high_thread_discursive_heterogeneity"] = int(
            eligible_row
            and float(row["discursive_cue_entropy"]) >= discursive_threshold
            and float(row["discursive_cue_entropy"]) > 0
        )
    return thresholds


def build_thread_author_rows(
    records: list[dict[str, Any]],
    user_profiles: dict[str, dict[str, Any]],
    thread_profiles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    thread_lookup = {str(row["submission_id"]): row for row in thread_profiles}
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in records:
        author = row.get("author")
        submission_id = str(row["submission_id"])
        if not author or submission_id not in thread_lookup:
            continue
        key = (submission_id, str(author))
        if key not in grouped:
            user = user_profiles[str(author)]
            thread = thread_lookup[submission_id]
            grouped[key] = {
                "submission_id": submission_id,
                "author": author,
                "subreddit": row["subreddit"],
                "community_group_proxy": row["community_group_proxy"],
                "comments_in_thread": 0,
                "early_comments_in_thread": 0,
                "later_comments_in_thread": 0,
                "predicted_public_corrections_in_thread": 0,
                "later_predicted_public_corrections_in_thread": 0,
                "corrected_in_thread": 0,
                "later_corrected_in_thread": 0,
                "user_comments": user["comments"],
                "user_subreddits_observed": user["subreddits_observed"],
                "user_community_groups_observed": user["community_groups_observed"],
                "user_cross_subreddit_observed": user["cross_subreddit_observed"],
                "user_cross_group_observed": user["cross_group_observed"],
                "user_subreddit_entropy": user["subreddit_entropy"],
                "user_community_group_entropy": user["community_group_entropy"],
                "thread_comments": thread["comments"],
                "thread_unique_authors": thread["unique_authors"],
                "thread_hostility_rate": thread["hostility_rate"],
                "thread_anti_institutional_rate": thread["anti_institutional_rate"],
                "early_correction_norm_presence": thread["early_correction_norm_presence"],
                "high_thread_hostility_climate": thread["high_thread_hostility_climate"],
                "high_thread_anti_institutional_climate": thread["high_thread_anti_institutional_climate"],
                "high_early_hostility_climate": thread["high_early_hostility_climate"],
                "high_early_anti_institutional_climate": thread["high_early_anti_institutional_climate"],
                "audience_cross_group_author_share": thread["audience_cross_group_author_share"],
                "early_audience_cross_group_author_share": thread["early_audience_cross_group_author_share"],
                "audience_mean_community_group_entropy": thread["audience_mean_community_group_entropy"],
                "early_audience_mean_community_group_entropy": thread[
                    "early_audience_mean_community_group_entropy"
                ],
                "audience_dominant_community_group_entropy": thread["audience_dominant_community_group_entropy"],
                "early_audience_dominant_community_group_entropy": thread[
                    "early_audience_dominant_community_group_entropy"
                ],
                "discursive_cue_entropy": thread["discursive_cue_entropy"],
                "early_discursive_cue_entropy": thread["early_discursive_cue_entropy"],
                "high_early_audience_structural_heterogeneity": thread[
                    "high_early_audience_structural_heterogeneity"
                ],
                "high_audience_structural_heterogeneity": thread["high_audience_structural_heterogeneity"],
                "high_early_discursive_heterogeneity": thread["high_early_discursive_heterogeneity"],
                "high_thread_discursive_heterogeneity": thread["high_thread_discursive_heterogeneity"],
                "sanction_to_correction_presence": thread["sanction_to_correction_presence"],
                "high_participation_no_predicted_correction": thread["high_participation_no_predicted_correction"],
            }
        item = grouped[key]
        item["comments_in_thread"] += 1
        if int(row.get("is_later_than_early_window", 0)) == 1:
            item["later_comments_in_thread"] += 1
        else:
            item["early_comments_in_thread"] += 1
        item["predicted_public_corrections_in_thread"] += int(row["public_correction_pred"])
        item["corrected_in_thread"] = int(item["predicted_public_corrections_in_thread"] > 0)
        if int(row.get("is_later_than_early_window", 0)) == 1:
            item["later_predicted_public_corrections_in_thread"] += int(row["public_correction_pred"])
            item["later_corrected_in_thread"] = int(item["later_predicted_public_corrections_in_thread"] > 0)
    return list(grouped.values())


def aggregate_instances(
    rows: list[dict[str, Any]], key_fields: list[str], outcome_field: str = "corrected_in_thread"
) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = tuple(row[field] for field in key_fields)
        if key not in grouped:
            grouped[key] = {field: row[field] for field in key_fields}
            grouped[key].update(
                {
                    "thread_author_instances": 0,
                    "correcting_instances": 0,
                    "comments_in_instances": 0,
                }
            )
        item = grouped[key]
        item["thread_author_instances"] += 1
        item["correcting_instances"] += int(row[outcome_field])
        item["comments_in_instances"] += int(row["comments_in_thread"])

    out = []
    for item in grouped.values():
        item["instance_correction_rate"] = div(item["correcting_instances"], item["thread_author_instances"])
        item["comment_intensity"] = div(item["comments_in_instances"], item["thread_author_instances"])
        out.append(item)
    return sorted(out, key=lambda item: tuple(str(item[field]) for field in key_fields))


def build_cross_group_contrasts(
    rows: list[dict[str, Any]],
    climate_fields: list[str],
    include_community_groups: bool,
    outcome_field: str = "corrected_in_thread",
) -> list[dict[str, Any]]:
    output = []
    contexts: list[tuple[str, str | None]] = [("all", None)]
    if include_community_groups:
        contexts.extend(
            sorted({(str(row["community_group_proxy"]), str(row["community_group_proxy"])) for row in rows})
        )

    for climate_field in climate_fields:
        for context_label, community_group in contexts:
            values = sorted({int(row[climate_field]) for row in rows})
            for value in values:
                subset = [
                    row
                    for row in rows
                    if int(row[climate_field]) == value
                    and (community_group is None or str(row["community_group_proxy"]) == community_group)
                ]
                non_cross = [row for row in subset if int(row["user_cross_group_observed"]) == 0]
                cross = [row for row in subset if int(row["user_cross_group_observed"]) == 1]
                non_cross_rate = div(sum(int(row[outcome_field]) for row in non_cross), len(non_cross))
                cross_rate = div(sum(int(row[outcome_field]) for row in cross), len(cross))
                output.append(
                    {
                        "climate_variable": climate_field,
                        "outcome_field": outcome_field,
                        "community_group_proxy": context_label,
                        "climate_value": value,
                        "non_cross_instances": len(non_cross),
                        "cross_instances": len(cross),
                        "non_cross_correcting_instances": sum(int(row[outcome_field]) for row in non_cross),
                        "cross_correcting_instances": sum(int(row[outcome_field]) for row in cross),
                        "non_cross_correction_rate": non_cross_rate,
                        "cross_correction_rate": cross_rate,
                        "cross_minus_non_cross_rate": cross_rate - non_cross_rate,
                    }
                )
    return output


def aggregate_thread_climate_by_group(thread_profiles: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in thread_profiles:
        value = str(row.get(key) or "unknown")
        if value not in grouped:
            grouped[value] = {
                key: value,
                "threads": 0,
                "comments": 0,
                "unique_authors_sum": 0,
                "threads_with_predicted_correction": 0,
                "high_participation_no_predicted_correction_threads": 0,
                "high_thread_hostility_climate_threads": 0,
                "high_thread_anti_institutional_climate_threads": 0,
                "early_correction_norm_presence_threads": 0,
                "sanction_to_correction_presence_threads": 0,
                "high_early_audience_structural_heterogeneity_threads": 0,
                "high_thread_discursive_heterogeneity_threads": 0,
                "hostility_comments": 0,
                "anti_institutional_comments": 0,
                "audience_cross_group_author_share_sum": 0.0,
                "early_audience_cross_group_author_share_sum": 0.0,
                "discursive_cue_entropy_sum": 0.0,
                "early_discursive_cue_entropy_sum": 0.0,
            }
        item = grouped[value]
        item["threads"] += 1
        item["comments"] += int(row["comments"])
        item["unique_authors_sum"] += int(row["unique_authors"])
        item["threads_with_predicted_correction"] += int(row["has_predicted_public_correction"])
        item["high_participation_no_predicted_correction_threads"] += int(
            row["high_participation_no_predicted_correction"]
        )
        item["high_thread_hostility_climate_threads"] += int(row["high_thread_hostility_climate"])
        item["high_thread_anti_institutional_climate_threads"] += int(row["high_thread_anti_institutional_climate"])
        item["early_correction_norm_presence_threads"] += int(row["early_correction_norm_presence"])
        item["sanction_to_correction_presence_threads"] += int(row["sanction_to_correction_presence"])
        item["high_early_audience_structural_heterogeneity_threads"] += int(
            row["high_early_audience_structural_heterogeneity"]
        )
        item["high_thread_discursive_heterogeneity_threads"] += int(row["high_thread_discursive_heterogeneity"])
        item["hostility_comments"] += int(row["hostility_comments"])
        item["anti_institutional_comments"] += int(row["anti_institutional_comments"])
        item["audience_cross_group_author_share_sum"] += float(row["audience_cross_group_author_share"])
        item["early_audience_cross_group_author_share_sum"] += float(row["early_audience_cross_group_author_share"])
        item["discursive_cue_entropy_sum"] += float(row["discursive_cue_entropy"])
        item["early_discursive_cue_entropy_sum"] += float(row["early_discursive_cue_entropy"])

    out = []
    for item in grouped.values():
        item["thread_correction_presence_rate"] = div(item["threads_with_predicted_correction"], item["threads"])
        item["high_participation_no_correction_thread_rate"] = div(
            item["high_participation_no_predicted_correction_threads"], item["threads"]
        )
        item["high_thread_hostility_climate_rate"] = div(item["high_thread_hostility_climate_threads"], item["threads"])
        item["high_thread_anti_institutional_climate_rate"] = div(
            item["high_thread_anti_institutional_climate_threads"], item["threads"]
        )
        item["early_correction_norm_presence_rate"] = div(
            item["early_correction_norm_presence_threads"], item["threads"]
        )
        item["sanction_to_correction_presence_rate"] = div(
            item["sanction_to_correction_presence_threads"], item["threads"]
        )
        item["high_early_audience_structural_heterogeneity_rate"] = div(
            item["high_early_audience_structural_heterogeneity_threads"], item["threads"]
        )
        item["high_thread_discursive_heterogeneity_rate"] = div(
            item["high_thread_discursive_heterogeneity_threads"], item["threads"]
        )
        item["hostility_comment_rate"] = div(item["hostility_comments"], item["comments"])
        item["anti_institutional_comment_rate"] = div(item["anti_institutional_comments"], item["comments"])
        item["mean_audience_cross_group_author_share"] = div(
            item["audience_cross_group_author_share_sum"], item["threads"]
        )
        item["mean_early_audience_cross_group_author_share"] = div(
            item["early_audience_cross_group_author_share_sum"], item["threads"]
        )
        item["mean_discursive_cue_entropy"] = div(item["discursive_cue_entropy_sum"], item["threads"])
        item["mean_early_discursive_cue_entropy"] = div(item["early_discursive_cue_entropy_sum"], item["threads"])
        out.append(item)
    return sorted(out, key=lambda item: item["high_participation_no_correction_thread_rate"], reverse=True)


def top_high_participation_no_correction(thread_profiles: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    rows = [row for row in thread_profiles if int(row["high_participation_no_predicted_correction"]) == 1]
    return sorted(rows, key=lambda row: int(row["unique_authors"]), reverse=True)[:limit]


def write_log(path: Path, args: argparse.Namespace, summary: dict[str, Any]) -> None:
    lines = [
        "thread climate analysis run",
        f"generated_utc={summary['generated_utc']}",
        f"command={' '.join(sys.argv)}",
        f"predictions={args.predictions}",
        f"comments={args.comments}",
        f"output_dir={args.output_dir}",
        f"records={summary['comments']}",
        f"threads={summary['threads']}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = args.output_dir / "tables"
    metrics_dir = args.output_dir / "metrics"
    tables_dir.mkdir(exist_ok=True)
    metrics_dir.mkdir(exist_ok=True)

    predictions = load_predictions(args.predictions)
    records = load_comment_records(args.comments, predictions)
    user_profiles = build_user_profiles(records)
    thread_profiles = build_thread_profiles(
        records, args.early_n, args.high_participation_author_threshold, user_profiles
    )
    climate_thresholds = attach_high_climate_flags(thread_profiles, args.min_comments_for_climate, args.climate_quantile)
    thread_author_rows = build_thread_author_rows(records, user_profiles, thread_profiles)

    climate_fields = [
        "high_thread_hostility_climate",
        "high_thread_anti_institutional_climate",
        "early_correction_norm_presence",
        "sanction_to_correction_presence",
        "high_early_audience_structural_heterogeneity",
        "high_thread_discursive_heterogeneity",
    ]

    write_csv(
        tables_dir / "thread_climate_profiles.csv",
        sorted(thread_profiles, key=lambda row: (int(row["unique_authors"]), int(row["comments"])), reverse=True),
        [
            "submission_id",
            "subreddit",
            "community_group_proxy",
            "comments",
            "unique_authors",
            "predicted_public_corrections",
            "predicted_correctors",
            "has_predicted_public_correction",
            "later_comments",
            "later_predicted_public_corrections",
            "later_predicted_correctors",
            "has_later_predicted_public_correction",
            "later_predicted_comment_rate",
            "high_participation_no_predicted_correction",
            "hostility_comments",
            "hostility_rate",
            "anti_institutional_comments",
            "discursive_cue_entropy",
            "early_discursive_cue_entropy",
            "title_hostility_cue",
            "title_anti_institutional_cue",
            "anti_institutional_rate",
            "audience_profiled_authors",
            "audience_cross_group_authors",
            "audience_cross_group_author_share",
            "audience_cross_subreddit_author_share",
            "audience_mean_community_group_entropy",
            "audience_mean_subreddit_entropy",
            "audience_dominant_community_group_entropy",
            "audience_dominant_subreddit_entropy",
            "early_audience_profiled_authors",
            "early_audience_cross_group_authors",
            "early_audience_cross_group_author_share",
            "early_audience_cross_subreddit_author_share",
            "early_audience_mean_community_group_entropy",
            "early_audience_mean_subreddit_entropy",
            "early_audience_dominant_community_group_entropy",
            "early_audience_dominant_subreddit_entropy",
            "early_comments",
            "early_predicted_public_corrections",
            "early_correction_norm_presence",
            "early_hostility_rate",
            "early_anti_institutional_rate",
            "first_public_correction_rank",
            "replies_to_predicted_corrections",
            "hostile_replies_to_predicted_corrections",
            "hostile_reply_to_correction_rate",
            "sanction_to_correction_presence",
            "high_thread_hostility_climate",
            "high_thread_anti_institutional_climate",
            "high_early_hostility_climate",
            "high_early_anti_institutional_climate",
            "high_early_audience_structural_heterogeneity",
            "high_audience_structural_heterogeneity",
            "high_early_discursive_heterogeneity",
            "high_thread_discursive_heterogeneity",
        ],
    )

    aggregate_field_sets = {
        "thread_author_by_cross_group_and_hostility_climate.csv": [
            "high_thread_hostility_climate",
            "user_cross_group_observed",
        ],
        "thread_author_by_cross_group_and_anti_institutional_climate.csv": [
            "high_thread_anti_institutional_climate",
            "user_cross_group_observed",
        ],
        "thread_author_by_cross_group_and_early_correction_norm.csv": [
            "early_correction_norm_presence",
            "user_cross_group_observed",
        ],
        "thread_author_by_cross_group_and_sanction_to_correction.csv": [
            "sanction_to_correction_presence",
            "user_cross_group_observed",
        ],
        "thread_author_by_cross_group_and_early_audience_heterogeneity.csv": [
            "high_early_audience_structural_heterogeneity",
            "user_cross_group_observed",
        ],
        "thread_author_by_cross_group_and_discursive_heterogeneity.csv": [
            "high_thread_discursive_heterogeneity",
            "user_cross_group_observed",
        ],
        "thread_author_by_group_cross_and_hostility_climate.csv": [
            "community_group_proxy",
            "high_thread_hostility_climate",
            "user_cross_group_observed",
        ],
        "thread_author_by_group_cross_and_anti_institutional_climate.csv": [
            "community_group_proxy",
            "high_thread_anti_institutional_climate",
            "user_cross_group_observed",
        ],
    }
    for filename, fields in aggregate_field_sets.items():
        table = aggregate_instances(thread_author_rows, fields)
        write_csv(
            tables_dir / filename,
            table,
            fields
            + [
                "thread_author_instances",
                "correcting_instances",
                "comments_in_instances",
                "instance_correction_rate",
                "comment_intensity",
            ],
        )

    cross_group_contrasts = build_cross_group_contrasts(thread_author_rows, climate_fields, True)
    write_csv(
        tables_dir / "cross_group_correction_contrasts_by_climate.csv",
        cross_group_contrasts,
        [
            "climate_variable",
            "outcome_field",
            "community_group_proxy",
            "climate_value",
            "non_cross_instances",
            "cross_instances",
            "non_cross_correcting_instances",
            "cross_correcting_instances",
            "non_cross_correction_rate",
            "cross_correction_rate",
            "cross_minus_non_cross_rate",
        ],
    )

    later_thread_author_rows = [row for row in thread_author_rows if int(row["later_comments_in_thread"]) > 0]
    later_aggregate_field_sets = {
        "later_thread_author_by_cross_group_and_hostility_climate.csv": [
            "high_thread_hostility_climate",
            "user_cross_group_observed",
        ],
        "later_thread_author_by_cross_group_and_anti_institutional_climate.csv": [
            "high_thread_anti_institutional_climate",
            "user_cross_group_observed",
        ],
        "later_thread_author_by_cross_group_and_early_correction_norm.csv": [
            "early_correction_norm_presence",
            "user_cross_group_observed",
        ],
        "later_thread_author_by_cross_group_and_early_audience_heterogeneity.csv": [
            "high_early_audience_structural_heterogeneity",
            "user_cross_group_observed",
        ],
        "later_thread_author_by_cross_group_and_discursive_heterogeneity.csv": [
            "high_thread_discursive_heterogeneity",
            "user_cross_group_observed",
        ],
    }
    for filename, fields in later_aggregate_field_sets.items():
        table = aggregate_instances(later_thread_author_rows, fields, outcome_field="later_corrected_in_thread")
        write_csv(
            tables_dir / filename,
            table,
            fields
            + [
                "thread_author_instances",
                "correcting_instances",
                "comments_in_instances",
                "instance_correction_rate",
                "comment_intensity",
            ],
        )

    later_cross_group_contrasts = build_cross_group_contrasts(
        later_thread_author_rows, climate_fields, True, outcome_field="later_corrected_in_thread"
    )
    write_csv(
        tables_dir / "later_cross_group_correction_contrasts_by_climate.csv",
        later_cross_group_contrasts,
        [
            "climate_variable",
            "outcome_field",
            "community_group_proxy",
            "climate_value",
            "non_cross_instances",
            "cross_instances",
            "non_cross_correcting_instances",
            "cross_correcting_instances",
            "non_cross_correction_rate",
            "cross_correction_rate",
            "cross_minus_non_cross_rate",
        ],
    )

    community_summary = aggregate_thread_climate_by_group(thread_profiles, "community_group_proxy")
    subreddit_summary = aggregate_thread_climate_by_group(thread_profiles, "subreddit")
    write_csv(
        tables_dir / "community_thread_climate_summary.csv",
        community_summary,
        [
            "community_group_proxy",
            "threads",
            "comments",
            "unique_authors_sum",
            "threads_with_predicted_correction",
            "high_participation_no_predicted_correction_threads",
            "thread_correction_presence_rate",
            "high_participation_no_correction_thread_rate",
            "high_thread_hostility_climate_rate",
            "high_thread_anti_institutional_climate_rate",
            "early_correction_norm_presence_rate",
            "sanction_to_correction_presence_rate",
            "high_early_audience_structural_heterogeneity_rate",
            "high_thread_discursive_heterogeneity_rate",
            "mean_audience_cross_group_author_share",
            "mean_early_audience_cross_group_author_share",
            "mean_discursive_cue_entropy",
            "mean_early_discursive_cue_entropy",
            "hostility_comment_rate",
            "anti_institutional_comment_rate",
        ],
    )
    write_csv(
        tables_dir / "subreddit_thread_climate_summary.csv",
        subreddit_summary,
        [
            "subreddit",
            "threads",
            "comments",
            "unique_authors_sum",
            "threads_with_predicted_correction",
            "high_participation_no_predicted_correction_threads",
            "thread_correction_presence_rate",
            "high_participation_no_correction_thread_rate",
            "high_thread_hostility_climate_rate",
            "high_thread_anti_institutional_climate_rate",
            "early_correction_norm_presence_rate",
            "sanction_to_correction_presence_rate",
            "high_early_audience_structural_heterogeneity_rate",
            "high_thread_discursive_heterogeneity_rate",
            "mean_audience_cross_group_author_share",
            "mean_early_audience_cross_group_author_share",
            "mean_discursive_cue_entropy",
            "mean_early_discursive_cue_entropy",
            "hostility_comment_rate",
            "anti_institutional_comment_rate",
        ],
    )
    write_csv(
        tables_dir / "high_participation_no_correction_threads_with_climate_top200.csv",
        top_high_participation_no_correction(thread_profiles, 200),
        [
            "submission_id",
            "subreddit",
            "community_group_proxy",
            "comments",
            "unique_authors",
            "predicted_public_corrections",
            "predicted_correctors",
            "hostility_rate",
            "anti_institutional_rate",
            "audience_cross_group_author_share",
            "early_audience_cross_group_author_share",
            "discursive_cue_entropy",
            "early_discursive_cue_entropy",
            "early_correction_norm_presence",
            "sanction_to_correction_presence",
            "high_thread_hostility_climate",
            "high_thread_anti_institutional_climate",
            "high_early_audience_structural_heterogeneity",
            "high_thread_discursive_heterogeneity",
        ],
    )

    lexicon_diagnostics = [
        {
            "lexicon": "hostility",
            "terms": len(HOSTILITY_TERMS),
            "comment_matches": sum(int(row["hostility_cue"]) for row in records),
            "comment_match_rate": div(sum(int(row["hostility_cue"]) for row in records), len(records)),
            "title_matches": sum(int(row["title_hostility_cue"]) for row in records),
            "title_match_rate": div(sum(int(row["title_hostility_cue"]) for row in records), len(records)),
        },
        {
            "lexicon": "anti_institutional",
            "terms": len(ANTI_INSTITUTIONAL_TERMS),
            "comment_matches": sum(int(row["anti_institutional_cue"]) for row in records),
            "comment_match_rate": div(sum(int(row["anti_institutional_cue"]) for row in records), len(records)),
            "title_matches": sum(int(row["title_anti_institutional_cue"]) for row in records),
            "title_match_rate": div(sum(int(row["title_anti_institutional_cue"]) for row in records), len(records)),
        },
    ]
    write_csv(
        tables_dir / "lexicon_diagnostics.csv",
        lexicon_diagnostics,
        ["lexicon", "terms", "comment_matches", "comment_match_rate", "title_matches", "title_match_rate"],
    )

    summary = {
        "run_status": "exploratory_thread_climate_tables",
        "predictions": str(args.predictions),
        "comments_path": str(args.comments),
        "output_dir": str(args.output_dir),
        "comments": len(records),
        "threads": len(thread_profiles),
        "users": len(user_profiles),
        "thread_author_instances": len(thread_author_rows),
        "later_thread_author_instances": len(later_thread_author_rows),
        "early_n": args.early_n,
        "high_participation_author_threshold": args.high_participation_author_threshold,
        "climate_thresholds": climate_thresholds,
        "predicted_public_corrections": sum(int(row["public_correction_pred"]) for row in records),
        "later_predicted_public_corrections": sum(
            int(row["public_correction_pred"])
            for row in records
            if int(row.get("is_later_than_early_window", 0)) == 1
        ),
        "threads_with_predicted_correction": sum(
            int(row["has_predicted_public_correction"]) for row in thread_profiles
        ),
        "threads_with_later_predicted_correction": sum(
            int(row["has_later_predicted_public_correction"]) for row in thread_profiles
        ),
        "high_participation_no_predicted_correction_threads": sum(
            int(row["high_participation_no_predicted_correction"]) for row in thread_profiles
        ),
        "threads_with_sanction_to_correction": sum(
            int(row["sanction_to_correction_presence"]) for row in thread_profiles
        ),
        "lexicon_diagnostics": lexicon_diagnostics,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(metrics_dir / "run_summary.json", summary)
    write_log(args.output_dir / "run.log", args, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build exploratory thread-climate tables.")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--comments", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--early-n", type=int, default=10)
    parser.add_argument("--high-participation-author-threshold", type=int, default=20)
    parser.add_argument("--min-comments-for-climate", type=int, default=5)
    parser.add_argument("--climate-quantile", type=float, default=0.75)
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
