#!/usr/bin/env python3
"""Build tables and figures for the revised JCMC manuscript."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


TEAL = "#176B73"
ORANGE = "#C46A2D"
BLUE = "#3A6EA5"
CHARCOAL = "#3F454B"
GRAY = "#8B9298"
LIGHT_GRAY = "#D9DDE0"
PALE_GRAY = "#F2F3F4"
WHITE = "#FFFFFF"

FIGURE_MODEL_LABELS = {
    "Relation-aware ensemble": "Relation-aware ensemble",
    "Pair + title": "DeBERTa-v3-base + title",
    "Pair only": "DeBERTa-v3-base pair",
    "Large pair + title": "DeBERTa-v3-large + title",
    "NLI pair": "RoBERTa-MNLI pair",
    "Relation type": "DeBERTa-v3-base relation model",
    "Comment only": "DeBERTa-v3-base response only",
}


def set_style() -> None:
    mpl.rcParams.update(
        {
            "figure.facecolor": WHITE,
            "axes.facecolor": WHITE,
            "savefig.facecolor": WHITE,
            "font.family": "DejaVu Sans",
            "font.size": 8.5,
            "axes.titlesize": 9,
            "axes.labelsize": 8.5,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 7.5,
            "axes.edgecolor": CHARCOAL,
            "axes.linewidth": 0.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def clean_axes(ax: plt.Axes, hide_left: bool = False) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if hide_left:
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)


def panel_label(ax: plt.Axes, label: str, x: float = -0.08) -> None:
    ax.text(x, 1.04, label, transform=ax.transAxes, fontweight="bold", fontsize=10, va="bottom")


def save(fig: plt.Figure, output_dir: Path, name: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_dir / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(output_dir / f"{name}.png", dpi=320, bbox_inches="tight")
    plt.close(fig)


def build_tables(args: argparse.Namespace, tables_dir: Path) -> None:
    tables_dir.mkdir(parents=True, exist_ok=True)
    flow = pd.read_csv(args.model_dir / "tables/sample_flow.csv")
    descriptive = pd.read_csv(args.model_dir / "tables/descriptive_statistics.csv")
    comparison = pd.read_csv(args.validation_dir / "tables/classifier_model_comparison.csv")
    intervals = pd.read_csv(args.validation_dir / "tables/classifier_bootstrap_intervals.csv")
    subgroups = pd.read_csv(args.validation_dir / "tables/classifier_subgroup_performance.csv")
    subgroup_intervals = pd.read_csv(args.validation_dir / "tables/classifier_predictor_subgroup_intervals.csv")
    coefficients = pd.read_csv(args.model_dir / "tables/model_coefficients.csv")
    contrasts = pd.read_csv(args.model_dir / "tables/average_probability_contrasts.csv")
    sensitivity = pd.read_csv(args.model_dir / "tables/sensitivity_models.csv")
    thresholds = pd.read_csv(args.model_dir / "tables/threshold_sensitivity_models.csv")

    flow.to_csv(tables_dir / "table1_sample_flow.csv", index=False)
    descriptive.to_csv(tables_dir / "table1_descriptive_statistics.csv", index=False)
    comparison.to_csv(tables_dir / "table2_classifier_model_comparison.csv", index=False)
    intervals.to_csv(tables_dir / "table2_classifier_bootstrap_intervals.csv", index=False)
    subgroups.to_csv(tables_dir / "table2_classifier_subgroups.csv", index=False)
    subgroup_intervals.to_csv(tables_dir / "table2_classifier_predictor_subgroup_intervals.csv", index=False)

    focal_terms = [
        "prior_cross_subreddit_participation",
        "early_cross_subreddit_participant_share_z",
        "prior_cross_subreddit_participation:early_cross_subreddit_participant_share_z",
        "early_corrective_response_presence",
        "early_hostile_language_rate_z",
        "early_corrective_response_presence:early_hostile_language_rate_z",
        "prior_corrective_response_rate",
        "log_prior_comments",
        "early_prior_history_coverage",
        "early_context_activity",
        "two_candidate_targets",
    ]
    focal_models = [
        "temporally_ordered_first_response",
        "propensity_adjusted_first_response",
        "presence_hostility_interaction",
        "candidate_target_multiplicity_adjusted",
        "early_author_continuation",
    ]
    model_table = coefficients.loc[
        coefficients["model"].isin(focal_models) & coefficients["term"].isin(focal_terms)
    ].copy()
    model_table.to_csv(tables_dir / "table3_focal_model_coefficients.csv", index=False)
    contrasts.to_csv(tables_dir / "table3_average_probability_contrasts.csv", index=False)
    sensitivity.to_csv(tables_dir / "table_s1_window_sensitivity.csv", index=False)
    thresholds.to_csv(tables_dir / "table_s2_threshold_sensitivity.csv", index=False)


def figure_classifier(args: argparse.Namespace, figures_dir: Path) -> None:
    comparison = pd.read_csv(args.validation_dir / "tables/classifier_model_comparison.csv")
    calibration = pd.read_csv(args.validation_dir / "tables/classifier_calibration_bins.csv")
    comparison["model"] = comparison["model"].replace(FIGURE_MODEL_LABELS)
    comparison = comparison.iloc[::-1].reset_index(drop=True)

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.45), gridspec_kw={"width_ratios": [1.45, 1.0]})

    ax = axes[0]
    y = np.arange(len(comparison))
    ax.hlines(y, comparison["average_precision"], comparison["roc_auc"], color=LIGHT_GRAY, linewidth=1.4)
    ax.scatter(
        comparison["average_precision"],
        y,
        s=34,
        color=TEAL,
        edgecolor=WHITE,
        linewidth=0.5,
        label="AP",
        zorder=3,
    )
    ax.scatter(
        comparison["roc_auc"],
        y,
        s=32,
        marker="s",
        facecolor=WHITE,
        edgecolor=ORANGE,
        linewidth=1.2,
        label="ROC-AUC",
        zorder=3,
    )
    ax.set_yticks(y)
    ax.set_yticklabels(comparison["model"])
    ax.set_xlim(0.42, 0.89)
    ax.set_xlabel("Performance on test set")
    ax.legend(
        frameon=False,
        loc="lower right",
        bbox_to_anchor=(1.0, 1.01),
        ncol=2,
        handletextpad=0.4,
        columnspacing=1.0,
        borderaxespad=0,
    )
    clean_axes(ax, hide_left=True)
    panel_label(ax, "A", x=-0.27)

    ax = axes[1]
    ax.plot([0, 1], [0, 1], color=GRAY, linewidth=0.9, linestyle="--")
    ax.plot(
        calibration["mean_score"],
        calibration["observed_rate"],
        color=BLUE,
        linewidth=1.6,
        marker="o",
        markersize=4,
        markerfacecolor=WHITE,
        markeredgewidth=1.1,
    )
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Mean predicted score")
    ax.set_ylabel("Observed corrective proportion")
    ax.set_xticks([0, 0.5, 1])
    ax.set_yticks([0, 0.5, 1])
    ax.text(
        0.04,
        0.94,
        "Brier = .139\nSlope = 0.883",
        transform=ax.transAxes,
        ha="left",
        va="top",
        color=CHARCOAL,
        fontsize=7.5,
    )
    clean_axes(ax)
    panel_label(ax, "B", x=-0.18)

    fig.subplots_adjust(wspace=0.42)
    save(fig, figures_dir, "fig2-detector-validation")


def figure_main_contrasts(args: argparse.Namespace, figures_dir: Path) -> None:
    contrasts = pd.read_csv(args.model_dir / "tables/average_probability_contrasts.csv")
    labels = [
        "Prior participation",
        "Early correction present",
        "Hostile language (+1 SD)",
        "Audience moderation",
    ]
    colors = [TEAL, ORANGE, CHARCOAL, BLUE]
    contrasts = contrasts.copy()
    contrasts["estimate"] = contrasts["estimate_probability_points"] * 100
    contrasts["low"] = contrasts["ci_low"] * 100
    contrasts["high"] = contrasts["ci_high"] * 100

    fig, ax = plt.subplots(figsize=(6.7, 3.25))
    y = np.arange(len(contrasts))[::-1]
    ax.axvline(0, color=GRAY, linewidth=0.9, linestyle="--", zorder=0)
    for index, row in contrasts.iterrows():
        yi = y[index]
        ax.hlines(yi, row["low"], row["high"], color=colors[index], linewidth=1.7)
        ax.scatter(row["estimate"], yi, color=colors[index], s=42, edgecolor=WHITE, linewidth=0.6, zorder=3)
        ax.text(
            row["high"] + 0.22,
            yi,
            f"{row['estimate']:.1f}",
            va="center",
            ha="left",
            color=colors[index],
            fontsize=7.5,
        )
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Average probability difference (percentage points)")
    ax.set_xlim(-2.2, 10.8)
    clean_axes(ax, hide_left=True)
    save(fig, figures_dir, "fig3-observational-mechanism")


def figure_robustness(args: argparse.Namespace, figures_dir: Path) -> None:
    sensitivity = pd.read_csv(args.model_dir / "tables/sensitivity_models.csv")
    thresholds = pd.read_csv(args.model_dir / "tables/threshold_sensitivity_models.csv")
    coefficients = pd.read_csv(args.model_dir / "tables/model_coefficients.csv")
    sensitivity = sensitivity.loc[sensitivity["converged"].astype(bool)].copy()
    terms = [
        ("prior_cross_subreddit_participation", "Prior participation", TEAL),
        ("early_corrective_response_presence", "Early correction", ORANGE),
        ("early_hostile_language_rate_z", "Hostile language", CHARCOAL),
    ]

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.55), gridspec_kw={"width_ratios": [1.05, 1.25]})

    ax = axes[0]
    ax.axvline(1, color=GRAY, linewidth=0.9, linestyle="--", zorder=0)
    rng = np.random.default_rng(20260714)
    for term_index, (term, label, color) in enumerate(terms):
        values = sensitivity.loc[sensitivity["term"] == term, "odds_ratio"].to_numpy()
        y = np.full(len(values), 2 - term_index, dtype=float) + rng.uniform(-0.09, 0.09, len(values))
        ax.scatter(values, y, s=18, color=color, alpha=0.42, edgecolor="none")
        main = coefficients.loc[
            (coefficients["model"] == "propensity_adjusted_first_response")
            & (coefficients["term"] == term)
        ].iloc[0]
        yi = 2 - term_index
        ax.hlines(yi, main["odds_ratio_ci_low"], main["odds_ratio_ci_high"], color=color, linewidth=1.8)
        ax.scatter(main["odds_ratio"], yi, marker="D", s=46, color=color, edgecolor=WHITE, linewidth=0.6, zorder=4)
    ax.set_xscale("log")
    ax.set_xlim(0.75, 4.1)
    ax.set_xticks([0.8, 1.0, 1.5, 2.0, 3.0, 4.0])
    ax.get_xaxis().set_major_formatter(mpl.ticker.ScalarFormatter())
    ax.set_yticks([2, 1, 0])
    ax.set_yticklabels([item[1] for item in terms])
    ax.set_xlabel("Odds ratio")
    clean_axes(ax, hide_left=True)
    panel_label(ax, "A", x=-0.31)

    ax = axes[1]
    ax.axhline(1, color=GRAY, linewidth=0.9, linestyle="--", zorder=0)
    for term, label, color in terms:
        group = thresholds.loc[thresholds["term"] == term].sort_values("classification_threshold")
        ax.plot(
            group["classification_threshold"],
            group["odds_ratio"],
            marker="o",
            markersize=4,
            linewidth=1.5,
            color=color,
            label=label,
        )
    ax.set_yscale("log")
    ax.set_ylim(0.82, 2.75)
    ax.set_yticks([0.9, 1.0, 1.5, 2.0, 2.5])
    ax.get_yaxis().set_major_formatter(mpl.ticker.ScalarFormatter())
    ax.set_xticks([0.3, 0.4, 0.5, 0.6, 0.7])
    ax.set_xlabel("Classification threshold")
    ax.set_ylabel("Odds ratio")
    ax.legend(frameon=False, loc="center right", ncol=1)
    clean_axes(ax)
    panel_label(ax, "B", x=-0.17)

    fig.subplots_adjust(wspace=0.42)
    save(fig, figures_dir, "fig4-robustness")


def run(args: argparse.Namespace) -> None:
    set_style()
    figures_dir = args.output_dir / "figures"
    tables_dir = args.output_dir / "tables"
    build_tables(args, tables_dir)
    figure_classifier(args, figures_dir)
    figure_main_contrasts(args, figures_dir)
    figure_robustness(args, figures_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build revised manuscript tables and figures.")
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path("outputs/revised_corrective_response_models_20260714"),
    )
    parser.add_argument(
        "--validation-dir",
        type=Path,
        default=Path("outputs/revised_corrective_response_validation_20260714"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/revised_manuscript_artifacts_20260714"),
    )
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
