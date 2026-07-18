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


def average_precision_binary(y_true: np.ndarray, scores: np.ndarray) -> float:
    order = np.argsort(-scores, kind="mergesort")
    sorted_scores = scores[order]
    sorted_true = y_true[order]
    positive_count = int(sorted_true.sum())
    if positive_count == 0:
        return float("nan")
    distinct_indices = np.where(np.diff(sorted_scores))[0]
    threshold_indices = np.r_[distinct_indices, len(sorted_true) - 1]
    true_positives = np.cumsum(sorted_true)[threshold_indices]
    false_positives = 1 + threshold_indices - true_positives
    precision = true_positives / (true_positives + false_positives)
    recall = true_positives / positive_count
    return float(np.sum(np.diff(np.r_[0, recall]) * precision))


def roc_auc_binary(y_true: np.ndarray, scores: np.ndarray) -> float:
    positive_count = int(y_true.sum())
    negative_count = int(len(y_true) - positive_count)
    if positive_count == 0 or negative_count == 0:
        return float("nan")
    ranks = pd.Series(scores).rank(method="average").to_numpy()
    positive_rank_sum = float(ranks[y_true == 1].sum())
    auc = (positive_rank_sum - positive_count * (positive_count + 1) / 2) / (positive_count * negative_count)
    return float(auc)


def threshold_metrics(y_true: np.ndarray, scores: np.ndarray, threshold: float = 0.5) -> dict[str, float | int]:
    y_pred = (scores >= threshold).astype(int)
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision_at_0_5": float(precision),
        "recall_at_0_5": float(recall),
        "f1_at_0_5": float(f1),
        "predicted_positive_at_0_5": int(y_pred.sum()),
    }


def detector_validation_values(summary: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    metrics = summary["audit3_main_metric_reference"]
    metric_rows = [
        ("AP", metrics["average_precision"]),
        ("ROC-AUC", metrics["roc_auc"]),
        ("F1@0.5", metrics["f1_at_0_5"]),
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


def comment_only_audit3_metrics(annotations_path: Path) -> dict[str, Any]:
    annotations = pd.read_csv(annotations_path)
    labels = pd.to_numeric(annotations["llm_pair_label"], errors="coerce")
    scores = pd.to_numeric(annotations["public_correction_score"], errors="coerce")
    valid = labels.isin([0, 1]) & scores.notna()
    y_true = labels.loc[valid].astype(int).to_numpy()
    score_values = scores.loc[valid].astype(float).to_numpy()
    values = {
        "score_name": "public_correction_score",
        "average_precision": average_precision_binary(y_true, score_values),
        "roc_auc": roc_auc_binary(y_true, score_values),
    }
    values.update(threshold_metrics(y_true, score_values))
    return values


def detector_model_comparison_values(ranking_path: Path, annotations_path: Path) -> pd.DataFrame:
    """Comparable detector families evaluated on the same held-out test set."""
    ranking = pd.read_csv(ranking_path).set_index("score_name")
    comparison_specs = [
        (
            "Relation-aware",
            "base_best_plus_large_title_roberta_mean",
            True,
            "selected relation-aware ensemble",
        ),
        (
            "Pair + title",
            "title6232",
            False,
            "binary pair-relation DeBERTa-v3-base with thread title",
        ),
        (
            "Pair only",
            "claim6232",
            False,
            "binary pair-relation DeBERTa-v3-base",
        ),
        (
            "Large pair + title",
            "large_title6232",
            False,
            "binary pair-relation DeBERTa-v3-large with thread title",
        ),
        (
            "NLI pair",
            "roberta_mnli6232",
            False,
            "NLI-style pair model",
        ),
        (
            "Relation type",
            "type6232",
            False,
            "multi-class relation-type DeBERTa-v3-base",
        ),
    ]
    rows = []
    for label, score_name, selected, model_family in comparison_specs:
        values = ranking.loc[score_name].to_dict()
        values.update(
            {
                "label": label,
                "score_name": score_name,
                "selected": selected,
                "model_family": model_family,
            }
        )
        rows.append(values)

    comment_values = comment_only_audit3_metrics(annotations_path)
    comment_values.update(
        {
            "label": "Comment only",
            "selected": False,
            "model_family": "comment-level DeBERTa-v3-base projected to test pairs",
        }
    )
    rows.append(comment_values)
    columns = [
        "label",
        "score_name",
        "model_family",
        "average_precision",
        "roc_auc",
        "precision_at_0_5",
        "recall_at_0_5",
        "f1_at_0_5",
        "predicted_positive_at_0_5",
        "selected",
    ]
    comparison = pd.DataFrame(rows, columns=columns)
    comparison["predicted_positive_at_0_5"] = comparison["predicted_positive_at_0_5"].astype(int)
    comparison["selected"] = comparison["selected"].astype(bool)
    return comparison


def detector_full_model_ranking(ranking_path: Path, annotations_path: Path) -> pd.DataFrame:
    ranking = pd.read_csv(ranking_path)
    comment_values = comment_only_audit3_metrics(annotations_path)
    comment_values["label"] = "Comment-only DeBERTa-base"
    full = pd.concat([ranking, pd.DataFrame([comment_values])], ignore_index=True, sort=False)
    return full.sort_values("average_precision", ascending=False)


def figure_detector_validation(summary: dict[str, Any], args: argparse.Namespace, output_dir: Path, tables_dir: Path) -> None:
    metric_df, coverage_df = detector_validation_values(summary)
    comparison_df = detector_model_comparison_values(args.audit3_model_ranking, args.audit3_annotations)
    full_comparison_df = detector_full_model_ranking(args.audit3_model_ranking, args.audit3_annotations)
    metric_df.to_csv(tables_dir / "detector_validation_metrics.csv", index=False)
    coverage_df.to_csv(tables_dir / "detector_validation_coverage.csv", index=False)
    comparison_df.to_csv(tables_dir / "detector_model_comparison_audit3.csv", index=False)
    full_comparison_df.to_csv(tables_dir / "detector_model_comparison_audit3_full.csv", index=False)

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.8), gridspec_kw={"width_ratios": [0.9, 1.55]})

    ax = axes[0]
    y = np.arange(len(metric_df))[::-1]
    colors = [BLUE if label in {"AP", "ROC-AUC"} else "#8A8A8A" for label in metric_df["label"]]
    ax.barh(y, metric_df["value"], color=colors, height=0.58)
    ax.set_yticks(y)
    ax.set_yticklabels(metric_df["label"])
    ax.set_xlim(0, 1.0)
    ax.set_xlabel("Score")
    ax.set_xticks([0.0, 0.5, 1.0])
    for yi, value in zip(y, metric_df["value"]):
        ax.text(value + 0.018, yi, f"{value:.3f}", va="center", ha="left", color=GRAY, fontsize=7.5)
    clean_axes(ax)
    add_panel_label(ax, "A", x=-0.22)

    ax = axes[1]
    comparison_plot = comparison_df.iloc[::-1].reset_index(drop=True)
    y = np.arange(len(comparison_plot))
    bar_colors = [BLUE_DARK if row["selected"] else BLUE_LIGHT for _, row in comparison_plot.iterrows()]
    ax.barh(y, comparison_plot["average_precision"], color=bar_colors, height=0.58, zorder=1)
    for yi, row in comparison_plot.iterrows():
        ax.scatter(row["f1_at_0_5"], yi, s=30, facecolor=BG, edgecolor=CLAY, linewidth=1.2, zorder=3, label="F1@0.5" if yi == 0 else None)
        if row["f1_at_0_5"] > row["average_precision"] and row["f1_at_0_5"] - row["average_precision"] < 0.12:
            label_x = row["average_precision"] - 0.014
            ha = "right"
        else:
            label_x = row["average_precision"] + 0.014
            ha = "left"
        ax.text(label_x, yi, f"{row['average_precision']:.3f}", va="center", ha=ha, color=GRAY, fontsize=7.1)
    ax.set_yticks(y)
    ax.set_yticklabels(comparison_plot["label"])
    ax.set_xlabel("Score")
    ax.set_xlim(0.0, 0.86)
    ax.set_xticks([0.0, 0.2, 0.4, 0.6, 0.8])
    ax.set_ylim(-0.35, len(comparison_plot) - 0.65)
    ap_handle = mpl.patches.Patch(color=BLUE_LIGHT, label="AP")
    f1_handle = mpl.lines.Line2D([], [], marker="o", markersize=5, markerfacecolor=BG, markeredgecolor=CLAY, linestyle="None", label="F1@0.5")
    ax.legend(handles=[ap_handle, f1_handle], frameon=False, loc="upper right", bbox_to_anchor=(1.0, 1.12), ncol=2, handletextpad=0.4, columnspacing=1.0)
    clean_axes(ax)
    add_panel_label(ax, "B", x=-0.24)

    fig.tight_layout(w_pad=2.2)
    save_figure(fig, output_dir, "fig1_detector_validation_and_coverage")


def select_terms(coef: pd.DataFrame) -> pd.DataFrame:
    labels = {
        "user_cross_group_observed": "Cross-group structural position",
        "high_early_audience_structural_heterogeneity": "High early audience\nstructural heterogeneity",
        "user_cross_group_observed:high_early_audience_structural_heterogeneity": "Cross-group structural position $\\times$\nhigh early audience structural\nheterogeneity",
        "early_correction_norm_presence": "Early correction norm",
        "high_thread_hostility_climate": "High hostile thread climate",
        "early_correction_norm_presence:high_thread_hostility_climate": "Early correction norm $\\times$\nhigh hostile thread climate",
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
    scale: float = 100.0,
    value_fmt: str = "{:.1f}",
) -> None:
    scenario = scenario.copy()
    scenario["x"] = scenario["high_early_audience_structural_heterogeneity"].astype(int)
    scenario["cross_group"] = scenario["user_cross_group_observed"].astype(int)
    labels = {0: "No cross-group", 1: "Cross-group"}
    colors = {0: "#8A8A8A", 1: BLUE}
    line_styles = {0: (0, (3, 2)), 1: "-"}
    marker_faces = {0: BG, 1: BLUE}
    for cross_group in [0, 1]:
        sub = scenario.loc[scenario["cross_group"] == cross_group].sort_values("x")
        values = sub[value_col].to_numpy() * scale
        ax.plot(
            sub["x"].to_numpy(),
            values,
            color=colors[cross_group],
            linestyle=line_styles[cross_group],
            marker="o",
            markerfacecolor=marker_faces[cross_group],
            markeredgecolor=colors[cross_group],
            markeredgewidth=1.0,
            linewidth=1.7,
            markersize=4.5,
            label=labels[cross_group],
            zorder=3,
        )
        for x, value in zip(sub["x"].to_numpy(), values):
            ax.text(
                x,
                value + (y_lim[1] - y_lim[0]) * 0.035,
                value_fmt.format(value),
                ha="center",
                va="bottom",
                color=BLUE_DARK if cross_group else GRAY,
                fontsize=7.2,
            )
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Low", "High"])
    if x_label:
        ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_ylim(*y_lim)
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
    significant = forest["p_value"].to_numpy() < 0.05
    facecolors = [BLUE if is_significant else BG for is_significant in significant]
    edgecolors = [BLUE if is_significant else "#7A7A7A" for is_significant in significant]
    ax_forest.hlines(y, lo, hi, color="#8E8E8E", linewidth=1.0)
    ax_forest.scatter(x, y, s=34, facecolor=facecolors, edgecolor=edgecolors, linewidth=1.0, zorder=3)
    ax_forest.axvline(1.0, color="#222222", linewidth=0.9, zorder=1)
    ax_forest.set_xscale("log")
    ax_forest.set_xticks([0.75, 1.0, 1.25, 1.5, 2.0])
    ax_forest.set_xticklabels(["0.75", "1.0", "1.25", "1.5", "2.0"])
    ax_forest.set_yticks(y)
    ax_forest.set_yticklabels(forest["label"])
    ax_forest.set_xlabel("Odds ratio for later public correction")
    ax_forest.set_xlim(0.7, 2.25)
    ax_forest.minorticks_off()
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
        "Correction score",
        (0.17, 0.248),
        scale=1.0,
        value_fmt="{:.3f}",
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
        "audit3_model_ranking": str(args.audit3_model_ranking),
        "audit3_annotations": str(args.audit3_annotations),
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

    figure_detector_validation(detector_summary, args, figures_dir, tables_dir)
    figure_observational_mechanism(logit_coef, logit_scenario, score_coef, score_scenario, figures_dir, tables_dir)
    write_run_summary(args.output_dir, args, detector_summary)
    (args.output_dir / "run.log").write_text(
        "\n".join(
            [
                "validation and mechanism manuscript figures",
                f"detector_summary={args.detector_summary}",
                f"logit_dir={args.logit_dir}",
                f"score_ols_dir={args.score_ols_dir}",
                f"audit3_model_ranking={args.audit3_model_ranking}",
                f"audit3_annotations={args.audit3_annotations}",
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
        "--audit3-model-ranking",
        type=Path,
        default=Path("outputs/pair_relation_ensemble_raw_models_on_audit3_20260628T020000Z/metrics/score_ranking.csv"),
    )
    parser.add_argument(
        "--audit3-annotations",
        type=Path,
        default=Path("outputs/llm_qwen_pair_relation_independent_audit3_combined_800_20260627T162524Z/llm_pair_annotations.csv"),
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
