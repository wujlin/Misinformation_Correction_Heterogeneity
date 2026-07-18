#!/usr/bin/env python3
"""Empirically calibrated ABM for aggregate public correction.

The simulation uses observed thread-author instances as the agent population.
Agent decision probabilities are calibrated from a no-anti-institutional logit
model, then replayed under counterfactual observable contexts.

This script is intentionally transparent: it does not use LLM agents and it
does not claim to observe private recognition or anticipated accountability.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from fit_thread_climate_models import coefficients_table, prepare_later_dataframe


FORMULA = (
    "later_corrected_in_thread ~ "
    "user_cross_group_observed * high_early_audience_structural_heterogeneity "
    "+ early_correction_norm_presence * high_thread_hostility_climate "
    "+ high_early_discursive_heterogeneity "
    "+ log_thread_comments + log_user_comments "
    "+ C(community_group_proxy)"
)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def write_log(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def prepare_model_dataframe(args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, Any]]:
    df, metadata = prepare_later_dataframe(args)
    needed = [
        "submission_id",
        "later_corrected_in_thread",
        "user_cross_group_observed",
        "high_early_audience_structural_heterogeneity",
        "early_correction_norm_presence",
        "high_thread_hostility_climate",
        "high_early_discursive_heterogeneity",
        "log_thread_comments",
        "log_user_comments",
        "community_group_proxy",
    ]
    missing = [column for column in needed if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    for column in needed:
        if column in {"submission_id", "community_group_proxy"}:
            df[column] = df[column].astype(str)
        else:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)

    df = df.loc[df["later_comments_in_thread"].astype(float) > 0].copy()
    return df, metadata


def fit_calibration_model(df: pd.DataFrame, maxiter: int) -> Any:
    model = smf.logit(formula=FORMULA, data=df)
    return model.fit(
        disp=False,
        maxiter=maxiter,
        cov_type="cluster",
        cov_kwds={"groups": df["submission_id"]},
    )


ScenarioTransform = Callable[[pd.DataFrame], pd.DataFrame]


def scenario_transforms() -> dict[str, ScenarioTransform]:
    def identity(df: pd.DataFrame) -> pd.DataFrame:
        return df.copy()

    def set_column(column: str, value: int) -> ScenarioTransform:
        def transform(df: pd.DataFrame) -> pd.DataFrame:
            out = df.copy()
            out[column] = value
            return out

        return transform

    def supportive_context(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["early_correction_norm_presence"] = 1
        out["high_thread_hostility_climate"] = 0
        return out

    def hostile_no_norm_context(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["early_correction_norm_presence"] = 0
        out["high_thread_hostility_climate"] = 1
        return out

    def no_norm_no_hostility_context(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["early_correction_norm_presence"] = 0
        out["high_thread_hostility_climate"] = 0
        return out

    def norm_with_hostility_context(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["early_correction_norm_presence"] = 1
        out["high_thread_hostility_climate"] = 1
        return out

    return {
        "baseline_observed_context": identity,
        "all_non_cross_group_position": set_column("user_cross_group_observed", 0),
        "all_cross_group_position": set_column("user_cross_group_observed", 1),
        "low_early_audience_structural_heterogeneity": set_column(
            "high_early_audience_structural_heterogeneity", 0
        ),
        "high_early_audience_structural_heterogeneity": set_column(
            "high_early_audience_structural_heterogeneity", 1
        ),
        "no_early_correction_norm": set_column("early_correction_norm_presence", 0),
        "universal_early_correction_norm": set_column("early_correction_norm_presence", 1),
        "remove_hostility": set_column("high_thread_hostility_climate", 0),
        "universal_hostility": set_column("high_thread_hostility_climate", 1),
        "no_norm_no_hostility_context": no_norm_no_hostility_context,
        "supportive_context_norm_without_hostility": supportive_context,
        "norm_with_hostility_context": norm_with_hostility_context,
        "hostile_context_without_early_norm": hostile_no_norm_context,
    }


def simulate_probabilities(
    probabilities: np.ndarray,
    thread_codes: np.ndarray,
    cross_group: np.ndarray,
    audience_heterogeneity: np.ndarray,
    simulations: int,
    rng: np.random.Generator,
) -> pd.DataFrame:
    thread_count = int(thread_codes.max()) + 1 if len(thread_codes) else 0
    rows: list[dict[str, Any]] = []

    for run_id in range(simulations):
        draw = rng.random(len(probabilities)) < probabilities
        total = int(draw.sum())
        by_thread = np.bincount(thread_codes, weights=draw.astype(int), minlength=thread_count)
        active_threads = int((by_thread > 0).sum())
        top10_share = 0.0
        if total:
            top10_share = float(np.sort(by_thread)[-10:].sum() / total)

        rows.append(
            {
                "simulation_id": run_id,
                "correcting_instances": total,
                "correction_rate": float(total / len(probabilities)) if len(probabilities) else 0.0,
                "threads_with_any_correction": active_threads,
                "thread_activation_rate": float(active_threads / thread_count) if thread_count else 0.0,
                "cross_group_share_of_corrections": float(draw[cross_group == 1].sum() / total) if total else 0.0,
                "high_audience_heterogeneity_share_of_corrections": float(
                    draw[audience_heterogeneity == 1].sum() / total
                )
                if total
                else 0.0,
                "top10_thread_correction_share": top10_share,
            }
        )

    return pd.DataFrame(rows)


def summarize_simulation(scenario: str, probabilities: np.ndarray, draws: pd.DataFrame) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "scenario": scenario,
        "mean_probability": float(probabilities.mean()),
        "median_probability": float(np.median(probabilities)),
        "p90_probability": float(np.quantile(probabilities, 0.9)),
    }
    for column in [
        "correcting_instances",
        "correction_rate",
        "threads_with_any_correction",
        "thread_activation_rate",
        "cross_group_share_of_corrections",
        "high_audience_heterogeneity_share_of_corrections",
        "top10_thread_correction_share",
    ]:
        values = draws[column].astype(float)
        summary[f"{column}_mean"] = float(values.mean())
        summary[f"{column}_sd"] = float(values.std(ddof=1)) if len(values) > 1 else 0.0
    return summary


def add_baseline_differences(summary_df: pd.DataFrame) -> pd.DataFrame:
    baseline = summary_df.loc[summary_df["scenario"] == "baseline_observed_context"]
    if baseline.empty:
        return summary_df.copy()
    baseline_row = baseline.iloc[0]
    out = summary_df.copy()
    for column in [
        "mean_probability",
        "correction_rate_mean",
        "threads_with_any_correction_mean",
        "thread_activation_rate_mean",
        "cross_group_share_of_corrections_mean",
        "high_audience_heterogeneity_share_of_corrections_mean",
        "top10_thread_correction_share_mean",
    ]:
        out[f"{column}_minus_baseline"] = out[column] - baseline_row[column]
    return out


def write_scenario_plot(path: Path, summary_with_diff: pd.DataFrame) -> bool:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return False

    labels = {
        "all_non_cross_group_position": "All non-cross-group",
        "all_cross_group_position": "All cross-group",
        "low_early_audience_structural_heterogeneity": "Low early audience structural heterogeneity",
        "high_early_audience_structural_heterogeneity": "High early audience structural heterogeneity",
        "no_early_correction_norm": "No early correction norm",
        "universal_early_correction_norm": "Universal early correction norm",
        "remove_hostility": "No hostile thread climate",
        "universal_hostility": "Universal hostile thread climate",
        "supportive_context_norm_without_hostility": "Early correction norm, low hostile thread climate",
        "hostile_context_without_early_norm": "No early correction norm, high hostile thread climate",
    }
    plot_df = summary_with_diff.loc[
        summary_with_diff["scenario"] != "baseline_observed_context",
        ["scenario", "correction_rate_mean_minus_baseline"],
    ].copy()
    plot_df["label"] = plot_df["scenario"].map(labels).fillna(plot_df["scenario"])
    plot_df["delta_pp"] = plot_df["correction_rate_mean_minus_baseline"] * 100.0
    plot_df = plot_df.sort_values("delta_pp")

    colors = ["#a94442" if value < 0 else "#2f6f8f" for value in plot_df["delta_pp"]]
    fig, ax = plt.subplots(figsize=(8.2, 5.6))
    ax.barh(plot_df["label"], plot_df["delta_pp"], color=colors)
    ax.axvline(0, color="#222222", linewidth=0.8)
    ax.set_xlabel("Change in simulated correction rate relative to baseline (percentage points)")
    ax.set_ylabel("")
    ax.set_title("Empirically calibrated ABM scenario effects")
    ax.grid(axis="x", color="#dddddd", linewidth=0.6)
    ax.tick_params(axis="y", length=0)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    fig.tight_layout()

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=300)
    fig.savefig(path.with_suffix(".pdf"))
    plt.close(fig)
    return True


def run(args: argparse.Namespace) -> None:
    started = datetime.now(timezone.utc)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir = args.output_dir / "metrics"
    tables_dir = args.output_dir / "tables"
    draws_dir = args.output_dir / "draws"
    figures_dir = args.output_dir / "figures"
    metrics_dir.mkdir(exist_ok=True)
    tables_dir.mkdir(exist_ok=True)
    draws_dir.mkdir(exist_ok=True)
    figures_dir.mkdir(exist_ok=True)

    log_lines = [
        f"started_utc={started.isoformat()}",
        f"command={' '.join(sys.argv)}",
        f"formula={FORMULA}",
        "excluded_variable=high_thread_anti_institutional_climate",
    ]

    df, metadata = prepare_model_dataframe(args)
    result = fit_calibration_model(df, args.maxiter)
    coefficients = coefficients_table(result)
    pd.DataFrame(coefficients).to_csv(tables_dir / "calibrated_no_anti_logit_coefficients.csv", index=False)

    thread_codes = pd.Categorical(df["submission_id"]).codes.astype(int)
    cross_group = df["user_cross_group_observed"].astype(int).to_numpy()
    audience_heterogeneity = df["high_early_audience_structural_heterogeneity"].astype(int).to_numpy()
    rng = np.random.default_rng(args.seed)

    scenario_summaries: list[dict[str, Any]] = []
    all_draws: list[pd.DataFrame] = []
    for scenario, transform in scenario_transforms().items():
        scenario_df = transform(df)
        probabilities = np.asarray(result.predict(scenario_df), dtype=float)
        probabilities = np.clip(probabilities, 0.0, 1.0)
        draws = simulate_probabilities(
            probabilities=probabilities,
            thread_codes=thread_codes,
            cross_group=cross_group,
            audience_heterogeneity=audience_heterogeneity,
            simulations=args.simulations,
            rng=rng,
        )
        draws.insert(0, "scenario", scenario)
        if args.write_draws:
            draws.to_csv(draws_dir / f"{scenario}.csv", index=False)
        all_draws.append(draws)
        scenario_summaries.append(summarize_simulation(scenario, probabilities, draws))
        log_lines.append(
            f"scenario={scenario} mean_probability={probabilities.mean():.6f} "
            f"correction_rate_mean={scenario_summaries[-1]['correction_rate_mean']:.6f}"
        )

    summary_df = pd.DataFrame(scenario_summaries)
    summary_with_diff = add_baseline_differences(summary_df)
    summary_df.to_csv(tables_dir / "abm_scenario_summary.csv", index=False)
    summary_with_diff.to_csv(tables_dir / "abm_scenario_differences_from_baseline.csv", index=False)
    pd.concat(all_draws, ignore_index=True).to_csv(tables_dir / "abm_draw_level_summary.csv", index=False)
    plot_written = write_scenario_plot(figures_dir / "abm_scenario_correction_rate_change.png", summary_with_diff)

    run_summary = {
        "run_status": "empirical_population_abm_complete",
        "started_utc": started.isoformat(),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "command": " ".join(sys.argv),
        "formula": FORMULA,
        "excluded_variable": "high_thread_anti_institutional_climate",
        "simulations_per_scenario": args.simulations,
        "seed": args.seed,
        "predictions": str(args.predictions),
        "comments_path": str(args.comments),
        "output_dir": str(args.output_dir),
        "nobs": int(result.nobs),
        "outcome_mean": float(df["later_corrected_in_thread"].mean()),
        "pseudo_r2": float(result.prsquared),
        "aic": float(result.aic),
        "bic": float(result.bic),
        "converged": bool(result.mle_retvals.get("converged", False)),
        "metadata": metadata,
        "scenario_count": len(scenario_summaries),
        "scenario_plot_written": plot_written,
        "baseline": summary_df.loc[summary_df["scenario"] == "baseline_observed_context"].iloc[0].to_dict(),
    }
    write_json(args.output_dir / "run_summary.json", run_summary)
    write_json(metrics_dir / "run_summary.json", run_summary)
    write_json(metrics_dir / "model_fit.json", {k: run_summary[k] for k in ["nobs", "outcome_mean", "pseudo_r2", "aic", "bic", "converged"]})
    write_log(args.output_dir / "run.log", log_lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--predictions",
        type=Path,
        default=Path("outputs/full_comment_predictions_latest_pair_ensemble_20260628T142000Z/predictions/full_comment_predictions.csv"),
    )
    parser.add_argument("--comments", type=Path, default=Path("data/interim/covidvaccine_comments.jsonl"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/abm_empirical_calibrated_no_anti_20260701T000000Z"),
    )
    parser.add_argument("--early-n", type=int, default=10)
    parser.add_argument("--high-participation-author-threshold", type=int, default=10)
    parser.add_argument("--min-comments-for-climate", type=int, default=5)
    parser.add_argument("--climate-quantile", type=float, default=0.75)
    parser.add_argument("--maxiter", type=int, default=200)
    parser.add_argument("--simulations", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20260701)
    parser.add_argument("--write-draws", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
