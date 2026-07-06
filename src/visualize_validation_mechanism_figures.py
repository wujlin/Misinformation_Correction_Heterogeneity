#!/usr/bin/env python3
"""Create manuscript-style validation and observational mechanism figures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BLUE = "#2F6F8F"
BLUE_DARK = "#1F4E5F"
BLUE_LIGHT = "#C9DDE3"
CLAY = "#A94742"
CLAY_LIGHT = "#E2B8B4"
GRAY = "#4A4A4A"
LIGHT_GRAY = "#E7E7E7"
BG = "#FFFFFF"


def set_style() -> None:
    mpl.rcParams.update(
        {
            "figure.facecolor": BG,
            "axes.facecolor": BG,
            "savefig.facecolor": BG,
            "font.family": "DejaVu Sans",
            "font.size": 8.5,
            "axes.titlesize": 9,
            "axes.labelsize": 8.5,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "axes.edgecolor": "#333333",
            "axes.linewidth": 0.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def save_figure(fig: plt.Figure, output_dir: Path, name: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_dir / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(output_dir / f"{name}.png", dpi=320, bbox_inches="tight")
    plt.close(fig)


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def add_panel_label(ax: plt.Axes, label: str, x: float = -0.08, y: float = 1.04) -> None:
    ax.text(x, y, label, transform=ax.transAxes, ha="left", va="bottom", fontweight="bold", fontsize=10)


def clean_axes(ax: plt.Axes, keep_left: bool = False) -> None:
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    if not keep_left:
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)


def detector_validation_values(summary: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    metrics = summary["audit3_main_metric_reference"]
    metric_rows = [
        ("Average precision", metrics["average_precision"]),
        ("ROC-AUC", metrics["roc_auc"]),
        ("F1 at 0.5", metrics["f1_at_0_5"]),
    ]
    metric_df = pd.DataFrame(metric_rows, columns=["label", "value"])

    all_comments = int(summary["comment_rows"])
    coverage_rows = [
        ("All comments", all_comments, all_comments, "comment"),
        (
            "Comments with pair candidates",
            int(summary["comments_with_pair_candidates"]),
            all_comments,
            "comment",
        ),
        ("Candidate claim-response pairs", int(summary["pair_rows"]), all_comments, "pair"),
        ("Predicted correction comments", int(summary["comment_predicted_positive"]), all_comments, "comment"),
        ("Earlier comment-level corrections", int(summary["legacy_comment_predicted_positive"]), all_comments, "comment"),
    ]
    coverage_df = pd.DataFrame(coverage_rows, columns=["label", "count", "denominator", "unit"])
    coverage_df["share_of_comments"] = coverage_df["count"] / coverage_df["denominator"]
    return metric_df, coverage_df


def figure_detector_validation(summary: dict[str, Any], output_dir: Path, tables_dir: Path) -> None:
    metric_df, coverage_df = detector_validation_values(summary)
    metric_df.to_csv(tables_dir / "detector_validation_metrics.csv", index=False)
    coverage_df.to_csv(tables_dir / "detector_validation_coverage.csv", index=False)

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.35), gridspec_kw={"width_ratios": [1.0, 1.25]})

    ax = axes[0]
    y = np.arange(len(metric_df))[::-1]
    colors = [BLUE if label in {"Average precision", "ROC-AUC"} else "#8A8A8A" for label in metric_df["label"]]
    ax.barh(y, metric_df["value"], color=colors, height=0.58)
    ax.set_yticks(y)
    ax.set_yticklabels(metric_df["label"])
    ax.set_xlim(0, 1.0)
    ax.set_xlabel("Validation metric")
    ax.grid(axis="x", color=LIGHT_GRAY, linewidth=0.6)
    for yi, value in zip(y, metric_df["value"]):
        ax.text(value + 0.018, yi, f"{value:.3f}", va="center", ha="left", color=GRAY, fontsize=7.5)
    clean_axes(ax)
    add_panel_label(ax, "A", x=-0.22)

    ax = axes[1]
    coverage_plot = coverage_df.iloc[::-1].reset_index(drop=True)
    y = np.arange(len(coverage_plot))
    colors = [BLUE_LIGHT if unit == "comment" else CLAY_LIGHT for unit in coverage_plot["unit"]]
    ax.barh(y, coverage_plot["count"], color=colors, height=0.58)
    ax.set_yticks(y)
    ax.set_yticklabels(coverage_plot["label"])
    ax.set_xlabel("Corpus count")
    ax.set_xticks([0, 50_000, 100_000, 150_000])
    ax.set_xticklabels(["0", "50k", "100k", "150k"])
    ax.grid(axis="x", color=LIGHT_GRAY, linewidth=0.6)
    xmax = coverage_plot["count"].max()
    ax.set_xlim(0, xmax * 1.18)
    for yi, row in coverage_plot.iterrows():
        count = int(row["count"])
        if row["unit"] == "comment":
            text = f"{count:,} ({row['share_of_comments'] * 100:.1f}%)"
        else:
            text = f"{count:,} pairs"
        ax.text(count + xmax * 0.018, yi, text, va="center", ha="left", color=GRAY, fontsize=7.3)
    clean_axes(ax)
    add_panel_label(ax, "B", x=-0.24)

    fig.tight_layout(w_pad=2.2)
    save_figure(fig, output_dir, "fig1_detector_validation_and_coverage")


def select_terms(coef: pd.DataFrame) -> pd.DataFrame:
    labels = {
        "user_cross_group_observed": "Cross-group user",
        "high_early_audience_structural_heterogeneity": "High early audience structural heterogeneity",
        "user_cross_group_observed:high_early_audience_structural_heterogeneity": "Cross-group x early audience\nstructural heterogeneity",
        "early_correction_norm_presence": "Early correction norm",
        "high_thread_hostility_climate": "High hostile thread climate",
        "early_correction_norm_presence:high_thread_hostility_climate": "Early correction norm x\nhostile thread climate",
        "high_early_discursive_heterogeneity": "High early discursive heterogeneity",
    }
    rows = []
    for term, label in labels.items():
        match = coef.loc[coef["term"] == term]
        if not match.empty:
            item = match.iloc[0].to_dict()
            item["label"] = label
            rows.append(item)
    return pd.DataFrame(rows)


def plot_scenario_lines(
    ax: plt.Axes,
    scenario: pd.DataFrame,
    value_col: str,
    y_label: str,
    y_lim: tuple[float, float],
    x_label: str | None = "Early audience\nstructural heterogeneity",
) -> None:
    scenario = scenario.copy()
    scenario["x"] = scenario["high_early_audience_structural_heterogeneity"].astype(int)
    scenario["cross_group"] = scenario["user_cross_group_observed"].astype(int)
    labels = {0: "Non-cross-group", 1: "Cross-group"}
    colors = {0: "#8A8A8A", 1: BLUE}
    for cross_group in [0, 1]:
        sub = scenario.loc[scenario["cross_group"] == cross_group].sort_values("x")
        values = sub[value_col].to_numpy() * 100
        ax.plot(
            sub["x"].to_numpy(),
            values,
            color=colors[cross_group],
            marker="o",
            linewidth=1.7,
            markersize=4.5,
            label=labels[cross_group],
        )
        for x, value in zip(sub["x"].to_numpy(), values):
            ax.text(x, value + (y_lim[1] - y_lim[0]) * 0.035, f"{value:.1f}", ha="center", va="bottom", fontsize=7.2)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Low", "High"])
    if x_label:
        ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_ylim(*y_lim)
    ax.grid(axis="y", color=LIGHT_GRAY, linewidth=0.6)
    clean_axes(ax, keep_left=True)


def figure_observational_mechanism(
    logit_coef: pd.DataFrame,
    logit_scenario: pd.DataFrame,
    score_coef: pd.DataFrame,
    score_scenario: pd.DataFrame,
    output_dir: Path,
    tables_dir: Path,
) -> None:
    plot_coef = select_terms(logit_coef)
    plot_coef.to_csv(tables_dir / "observational_logit_focal_coefficients.csv", index=False)
    logit_scenario.to_csv(tables_dir / "observational_logit_scenario_probabilities.csv", index=False)
    score_coef.to_csv(tables_dir / "observational_score_ols_coefficients.csv", index=False)
    score_scenario.to_csv(tables_dir / "observational_score_scenario_values.csv", index=False)

    fig = plt.figure(figsize=(7.2, 5.1))
    grid = fig.add_gridspec(2, 2, width_ratios=[1.35, 1.0], height_ratios=[1.0, 1.0], wspace=0.55, hspace=0.55)
    ax_forest = fig.add_subplot(grid[:, 0])
    ax_logit = fig.add_subplot(grid[0, 1])
    ax_score = fig.add_subplot(grid[1, 1])

    forest = plot_coef.iloc[::-1].reset_index(drop=True)
    y = np.arange(len(forest))
    x = forest["odds_ratio"].to_numpy()
    lo = forest["odds_ratio_ci_low"].to_numpy()
    hi = forest["odds_ratio_ci_high"].to_numpy()
    colors = [BLUE if p < 0.05 else "#8A8A8A" for p in forest["p_value"]]
    ax_forest.hlines(y, lo, hi, color="#8E8E8E", linewidth=1.0)
    ax_forest.scatter(x, y, s=34, color=colors, zorder=3)
    ax_forest.axvline(1.0, color="#222222", linewidth=0.9)
    ax_forest.set_xscale("log")
    ax_forest.set_xticks([0.75, 1.0, 1.25, 1.5, 2.0])
    ax_forest.set_xticklabels(["0.75", "1.0", "1.25", "1.5", "2.0"])
    ax_forest.set_yticks(y)
    ax_forest.set_yticklabels(forest["label"])
    ax_forest.set_xlabel("Odds ratio in main heterogeneity logit")
    ax_forest.set_xlim(0.7, 2.25)
    ax_forest.grid(axis="x", color=LIGHT_GRAY, linewidth=0.6)
    clean_axes(ax_forest)
    add_panel_label(ax_forest, "A", x=-0.32)

    plot_scenario_lines(
        ax_logit,
        logit_scenario,
        "average_predicted_probability",
        "Correction probability (%)",
        (13.5, 21.0),
        x_label=None,
    )
    add_panel_label(ax_logit, "B", x=-0.18, y=1.12)
    ax_logit.legend(frameon=False, loc="upper left", bbox_to_anchor=(0.0, 1.0), borderaxespad=0.0)

    plot_scenario_lines(
        ax_score,
        score_scenario,
        "average_predicted_score_any",
        "Correction score (%)",
        (17.0, 24.8),
    )
    add_panel_label(ax_score, "C", x=-0.18, y=1.12)

    save_figure(fig, output_dir, "fig2_observational_mechanism_results")


def write_run_summary(base_output_dir: Path, args: argparse.Namespace, detector_summary: dict[str, Any]) -> None:
    figure_files = sorted(path.name for path in (base_output_dir / "figures").glob("*.pdf"))
    summary = {
        "run_status": "validation_mechanism_figures_complete",
        "output_dir": str(base_output_dir),
        "detector_summary": str(args.detector_summary),
        "logit_dir": str(args.logit_dir),
        "score_ols_dir": str(args.score_ols_dir),
        "detector_main_ensemble": detector_summary.get("main_ensemble_name"),
        "audit3_main_metric_reference": detector_summary.get("audit3_main_metric_reference"),
        "comment_rows": detector_summary.get("comment_rows"),
        "comments_with_pair_candidates": detector_summary.get("comments_with_pair_candidates"),
        "comment_predicted_positive": detector_summary.get("comment_predicted_positive"),
        "figure_pdf_files": figure_files,
    }
    (base_output_dir / "metrics" / "run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def run(args: argparse.Namespace) -> None:
    set_style()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = args.output_dir / "figures"
    tables_dir = args.output_dir / "tables"
    metrics_dir = args.output_dir / "metrics"
    figures_dir.mkdir(exist_ok=True)
    tables_dir.mkdir(exist_ok=True)
    metrics_dir.mkdir(exist_ok=True)

    detector_summary = read_json(args.detector_summary)
    logit_coef = pd.read_csv(args.logit_dir / "tables" / "heterogeneity_logit_coefficients.csv")
    logit_scenario = pd.read_csv(args.logit_dir / "tables" / "heterogeneity_scenario_predicted_probabilities.csv")
    score_coef = pd.read_csv(args.score_ols_dir / "tables" / "score_ols_coefficients.csv")
    score_scenario = pd.read_csv(args.score_ols_dir / "tables" / "score_heterogeneity_scenario_predicted_values.csv")

    figure_detector_validation(detector_summary, figures_dir, tables_dir)
    figure_observational_mechanism(logit_coef, logit_scenario, score_coef, score_scenario, figures_dir, tables_dir)
    write_run_summary(args.output_dir, args, detector_summary)
    (args.output_dir / "run.log").write_text(
        "\n".join(
            [
                "validation and mechanism manuscript figures",
                f"detector_summary={args.detector_summary}",
                f"logit_dir={args.logit_dir}",
                f"score_ols_dir={args.score_ols_dir}",
                f"output_dir={args.output_dir}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--detector-summary",
        type=Path,
        default=Path("outputs/full_comment_predictions_latest_pair_ensemble_20260628T142000Z/metrics/run_summary.json"),
    )
    parser.add_argument(
        "--logit-dir",
        type=Path,
        default=Path("outputs/thread_climate_logit_no_anti_latest_pair_ensemble_20260701T092000Z"),
    )
    parser.add_argument(
        "--score-ols-dir",
        type=Path,
        default=Path("outputs/thread_climate_score_ols_no_anti_latest_pair_ensemble_20260701T092500Z"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/manuscript_validation_mechanism_figures_20260701T093000Z"),
    )
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
