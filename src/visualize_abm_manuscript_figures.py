#!/usr/bin/env python3
"""Create manuscript-style figures for the calibrated ABM results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


BLUE = "#2F6F8F"
BLUE_DARK = "#1F4E5F"
BLUE_LIGHT = "#C9DDE3"
CLAY = "#A94742"
CLAY_LIGHT = "#E2B8B4"
GRAY = "#4A4A4A"
LIGHT_GRAY = "#E7E7E7"
BG = "#FFFFFF"


SCENARIO_LABELS = {
    "baseline_observed_context": "Observed baseline",
    "all_non_cross_group_position": "All non-cross-group",
    "all_cross_group_position": "All cross-group",
    "low_early_audience_structural_heterogeneity": "Low early audience\nstructural heterogeneity",
    "high_early_audience_structural_heterogeneity": "High early audience\nstructural heterogeneity",
    "no_early_correction_norm": "No early correction norm",
    "universal_early_correction_norm": "Universal early correction norm",
    "remove_hostility": "No hostile thread\nclimate",
    "universal_hostility": "Universal hostile\nthread climate",
    "no_norm_no_hostility_context": "No early correction norm,\nlow hostile thread climate",
    "supportive_context_norm_without_hostility": "Early correction norm,\nlow hostile thread climate",
    "norm_with_hostility_context": "Early correction norm,\nhigh hostile thread climate",
    "hostile_context_without_early_norm": "No early correction norm,\nhigh hostile thread climate",
}


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


def read_inputs(abm_dir: Path) -> dict[str, Any]:
    with (abm_dir / "run_summary.json").open("r", encoding="utf-8") as f:
        run_summary = json.load(f)
    scenario = pd.read_csv(abm_dir / "tables" / "abm_scenario_differences_from_baseline.csv")
    draws = pd.read_csv(abm_dir / "tables" / "abm_draw_level_summary.csv")
    coef = pd.read_csv(abm_dir / "tables" / "calibrated_no_anti_logit_coefficients.csv")
    return {"run_summary": run_summary, "scenario": scenario, "draws": draws, "coef": coef}


def add_panel_label(ax: plt.Axes, label: str, x: float = -0.08, y: float = 1.05) -> None:
    ax.text(x, y, label, transform=ax.transAxes, ha="left", va="bottom", fontweight="bold", fontsize=10)


def draw_box(ax: plt.Axes, x: float, y: float, w: float, h: float, title: str, subtitle: str, face: str) -> None:
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        linewidth=0.9,
        edgecolor="#333333",
        facecolor=face,
    )
    ax.add_patch(patch)
    ax.text(
        x + w / 2,
        y + h * 0.64,
        title,
        ha="center",
        va="center",
        fontweight="bold",
        color="#222222",
        fontsize=7.6,
        linespacing=1.15,
    )
    ax.text(
        x + w / 2,
        y + h * 0.27,
        subtitle,
        ha="center",
        va="center",
        color=GRAY,
        fontsize=6.7,
        linespacing=1.15,
    )


def draw_arrow(ax: plt.Axes, x1: float, y1: float, x2: float, y2: float) -> None:
    arrow = FancyArrowPatch(
        (x1, y1),
        (x2, y2),
        arrowstyle="-|>",
        mutation_scale=10,
        linewidth=0.9,
        color="#444444",
    )
    ax.add_patch(arrow)


def figure_abm_architecture(run_summary: dict[str, Any], output_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    comments = run_summary["metadata"]["comments"]
    agents = run_summary["nobs"]
    sims = run_summary["simulations_per_scenario"]
    scenario_count = run_summary["scenario_count"]

    boxes = [
        (0.04, 0.56, 0.17, 0.27, "Observed Reddit\ndiscussions", f"{comments:,} comments"),
        (0.29, 0.56, 0.17, 0.27, "Relation-aware\ncorrection detector", "pair-level correction"),
        (0.54, 0.56, 0.17, 0.27, "Empirical agent\npopulation", f"{agents:,} thread-authors"),
        (0.79, 0.56, 0.17, 0.27, "Calibrated ABM\nscenarios", f"{scenario_count} contexts x {sims} draws"),
    ]
    for i, (x, y, w, h, title, subtitle) in enumerate(boxes):
        draw_box(ax, x, y, w, h, title, subtitle, BLUE_LIGHT if i < 3 else "#EDEDED")
        if i < len(boxes) - 1:
            draw_arrow(ax, x + w + 0.012, y + h / 2, boxes[i + 1][0] - 0.012, y + h / 2)

    draw_box(
        ax,
        0.32,
        0.16,
        0.38,
        0.23,
        "Observable conditions",
        "cross-group position | audience structure\ncorrection norm | hostile thread climate",
        "#F2F4F4",
    )
    draw_box(ax, 0.78, 0.16, 0.18, 0.23, "Macro correction\nsupply", "correction rate\nactivated threads", "#F2F4F4")
    draw_arrow(ax, 0.625, 0.56, 0.51, 0.39)
    draw_arrow(ax, 0.70, 0.275, 0.78, 0.275)

    ax.text(0.04, 0.92, "Empirical-population ABM", ha="left", va="center", fontsize=10.5, fontweight="bold")
    ax.text(
        0.04,
        0.08,
        "The model fixes the observed Reddit population and changes observable discussion conditions.",
        ha="left",
        va="center",
        color=GRAY,
        fontsize=8,
    )
    save_figure(fig, output_dir, "fig1_abm_empirical_population_architecture")


def figure_calibration_forest(coef: pd.DataFrame, output_dir: Path) -> None:
    terms = [
        ("user_cross_group_observed", "Cross-group user"),
        ("high_early_audience_structural_heterogeneity", "High early audience structural heterogeneity"),
        ("user_cross_group_observed:high_early_audience_structural_heterogeneity", "Cross-group x early audience\nstructural heterogeneity"),
        ("early_correction_norm_presence", "Early correction norm"),
        ("high_thread_hostility_climate", "High hostile thread climate"),
        ("early_correction_norm_presence:high_thread_hostility_climate", "Early correction norm x\nhostile thread climate"),
        ("high_early_discursive_heterogeneity", "High early discursive heterogeneity"),
        ("log_thread_comments", "Thread activity"),
        ("log_user_comments", "User activity"),
    ]
    rows = []
    for term, label in terms:
        match = coef.loc[coef["term"] == term]
        if not match.empty:
            row = match.iloc[0].to_dict()
            row["label"] = label
            rows.append(row)
    plot_df = pd.DataFrame(rows).iloc[::-1].reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    y = np.arange(len(plot_df))
    x = plot_df["odds_ratio"].to_numpy()
    lo = plot_df["odds_ratio_ci_low"].to_numpy()
    hi = plot_df["odds_ratio_ci_high"].to_numpy()
    colors = [BLUE if p < 0.05 else "#8A8A8A" for p in plot_df["p_value"]]

    ax.hlines(y, lo, hi, color="#8E8E8E", linewidth=1.0)
    ax.scatter(x, y, s=34, color=colors, zorder=3)
    ax.axvline(1.0, color="#222222", linewidth=0.9)
    ax.set_xscale("log")
    ax.set_xticks([0.8, 1.0, 1.25, 1.5, 2.0])
    ax.set_xticklabels(["0.8", "1.0", "1.25", "1.5", "2.0"])
    ax.set_yticks(y)
    ax.set_yticklabels(plot_df["label"])
    ax.set_xlabel("Odds ratio in calibrated heterogeneity logit")
    ax.set_xlim(0.75, 2.25)
    ax.grid(axis="x", color=LIGHT_GRAY, linewidth=0.6)
    ax.tick_params(axis="y", length=0)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    ax.text(
        0.0,
        1.02,
        "Values above 1 indicate higher correction probability",
        color=GRAY,
        fontsize=7.5,
        transform=ax.transAxes,
        ha="left",
    )
    save_figure(fig, output_dir, "fig2_abm_calibration_forest")


def figure_condition_map(scenario: pd.DataFrame, output_dir: Path) -> None:
    mapping = {
        (0, 0): "no_norm_no_hostility_context",
        (1, 0): "supportive_context_norm_without_hostility",
        (0, 1): "hostile_context_without_early_norm",
        (1, 1): "norm_with_hostility_context",
    }
    rate = np.zeros((2, 2))
    threads = np.zeros((2, 2))
    delta_threads = np.zeros((2, 2))
    for norm in [0, 1]:
        for hostility in [0, 1]:
            row = scenario.loc[scenario["scenario"] == mapping[(norm, hostility)]].iloc[0]
            rate[hostility, norm] = row["correction_rate_mean"] * 100
            threads[hostility, norm] = row["threads_with_any_correction_mean"]
            delta_threads[hostility, norm] = row["threads_with_any_correction_mean_minus_baseline"]

    cmap = LinearSegmentedColormap.from_list("correction_rate", ["#F4F1EC", "#A9C8CF", BLUE_DARK])
    fig, ax = plt.subplots(figsize=(4.6, 3.6))
    im = ax.imshow(rate, cmap=cmap, vmin=rate.min(), vmax=rate.max())

    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Absent", "Present"])
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["Low", "High"])
    ax.set_xlabel("Early correction norm")
    ax.set_ylabel("Hostile thread climate")
    ax.tick_params(length=0)

    for hostility in [0, 1]:
        for norm in [0, 1]:
            color = "#111111" if rate[hostility, norm] < rate.mean() else "#FFFFFF"
            ax.text(
                norm,
                hostility,
                f"{rate[hostility, norm]:.1f}%\n{threads[hostility, norm]:,.0f}\n{delta_threads[hostility, norm]:+.0f}",
                ha="center",
                va="center",
                color=color,
                fontsize=8,
                fontweight="bold",
            )

    cbar = fig.colorbar(im, ax=ax, fraction=0.048, pad=0.04)
    cbar.set_label("Simulated correction rate (%)")
    for spine in ax.spines.values():
        spine.set_visible(False)
    save_figure(fig, output_dir, "fig3_abm_correction_activation_condition_map")


def figure_counterfactual_shift(scenario: pd.DataFrame, output_dir: Path) -> None:
    order = [
        "supportive_context_norm_without_hostility",
        "universal_early_correction_norm",
        "all_cross_group_position",
        "remove_hostility",
        "high_early_audience_structural_heterogeneity",
        "all_non_cross_group_position",
        "low_early_audience_structural_heterogeneity",
        "universal_hostility",
        "no_early_correction_norm",
        "hostile_context_without_early_norm",
    ]
    df = scenario.loc[scenario["scenario"].isin(order)].copy()
    df["label"] = df["scenario"].map(SCENARIO_LABELS)
    df["rate_pp"] = df["correction_rate_mean_minus_baseline"] * 100
    df["thread_delta"] = df["threads_with_any_correction_mean_minus_baseline"]
    df["order"] = df["scenario"].map({name: i for i, name in enumerate(order)})
    df = df.sort_values("order", ascending=False)

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 4.6), gridspec_kw={"width_ratios": [1.0, 1.0]})
    y = np.arange(len(df))
    labels = df["label"].to_list()

    for ax, value_col, xlabel, scale in [
        (axes[0], "rate_pp", "Correction-rate change (percentage points)", 1.0),
        (axes[1], "thread_delta", "Activated-thread change", 1.0),
    ]:
        values = df[value_col].to_numpy() * scale
        colors = [BLUE if value >= 0 else CLAY for value in values]
        ax.barh(y, values, color=colors, height=0.58)
        ax.axvline(0, color="#222222", linewidth=0.8)
        ax.grid(axis="x", color=LIGHT_GRAY, linewidth=0.6)
        ax.set_xlabel(xlabel)
        ax.tick_params(axis="y", length=0)
        for spine in ["top", "right", "left"]:
            ax.spines[spine].set_visible(False)
        xmax = max(abs(values.min()), abs(values.max()))
        ax.set_xlim(-xmax * 1.18, xmax * 1.18)
        for yi, value in zip(y, values):
            text = f"{value:+.1f}" if value_col == "rate_pp" else f"{value:+.0f}"
            if value < 0 and abs(value) > xmax * 0.18:
                ax.text(-xmax * 0.05, yi, text, va="center", ha="right", fontsize=7.3, color="#FFFFFF")
            else:
                ha = "left" if value >= 0 else "right"
                offset = xmax * 0.035 if value >= 0 else -xmax * 0.035
                ax.text(value + offset, yi, text, va="center", ha=ha, fontsize=7.3, color=GRAY)

    axes[0].set_yticks(y)
    axes[0].set_yticklabels(labels)
    axes[1].set_yticks(y)
    axes[1].set_yticklabels([])
    add_panel_label(axes[0], "A", x=-0.32)
    add_panel_label(axes[1], "B", x=-0.12)
    fig.tight_layout(w_pad=1.8)
    save_figure(fig, output_dir, "fig4_abm_counterfactual_activation_shift")


def figure_uncertainty_distributions(draws: pd.DataFrame, output_dir: Path) -> None:
    order = [
        "supportive_context_norm_without_hostility",
        "all_cross_group_position",
        "baseline_observed_context",
        "universal_hostility",
        "no_early_correction_norm",
        "hostile_context_without_early_norm",
    ]
    labels = [SCENARIO_LABELS[item] for item in order]
    data = [draws.loc[draws["scenario"] == item, "correction_rate"].to_numpy() * 100 for item in order]

    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    positions = np.arange(len(order))
    parts = ax.violinplot(data, positions=positions, vert=False, widths=0.68, showmeans=False, showextrema=False)
    for i, body in enumerate(parts["bodies"]):
        body.set_facecolor(BLUE if i < 3 else CLAY)
        body.set_edgecolor("none")
        body.set_alpha(0.62)
    medians = [np.median(values) for values in data]
    ax.scatter(medians, positions, color="#222222", s=14, zorder=3)
    ax.set_yticks(positions)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Simulated correction rate across 500 Monte Carlo draws (%)")
    ax.grid(axis="x", color=LIGHT_GRAY, linewidth=0.6)
    ax.tick_params(axis="y", length=0)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    save_figure(fig, output_dir, "figS1_abm_monte_carlo_uncertainty")


def audit_existing_figures(project_root: Path, output_dir: Path) -> pd.DataFrame:
    output_abs = output_dir.resolve()
    image_paths = sorted(
        [
            path
            for path in (project_root / "outputs").rglob("*")
            if path.suffix.lower() in {".png", ".pdf", ".svg"}
            and output_abs not in path.resolve().parents
        ]
    )
    rows = []
    for path in image_paths:
        rows.append(
            {
                "path": str(path.relative_to(project_root)),
                "suffix": path.suffix.lower(),
                "size_bytes": path.stat().st_size,
                "stage": path.parts[path.parts.index("outputs") + 1] if "outputs" in path.parts else "",
            }
        )
    df = pd.DataFrame(rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_dir / "existing_figure_audit.csv", index=False)
    return df


def write_run_summary(output_dir: Path, args: argparse.Namespace, audit: pd.DataFrame, inputs: dict[str, Any]) -> None:
    figures = sorted(path.name for path in (output_dir / "figures").glob("*.pdf"))
    summary = {
        "run_status": "abm_manuscript_figures_complete",
        "abm_dir": str(args.abm_dir),
        "output_dir": str(output_dir),
        "existing_figure_files_before_this_run": int(len(audit)),
        "figure_pdf_files": figures,
        "scenario_count": int(inputs["run_summary"]["scenario_count"]),
        "abm_nobs": int(inputs["run_summary"]["nobs"]),
        "abm_simulations_per_scenario": int(inputs["run_summary"]["simulations_per_scenario"]),
    }
    (output_dir / "run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def run(args: argparse.Namespace) -> None:
    set_style()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = args.output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    inputs = read_inputs(args.abm_dir)
    audit = audit_existing_figures(args.project_root, args.output_dir)

    figure_abm_architecture(inputs["run_summary"], figures_dir)
    figure_calibration_forest(inputs["coef"], figures_dir)
    figure_condition_map(inputs["scenario"], figures_dir)
    figure_counterfactual_shift(inputs["scenario"], figures_dir)
    figure_uncertainty_distributions(inputs["draws"], figures_dir)
    write_run_summary(args.output_dir, args, audit, inputs)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument(
        "--abm-dir",
        type=Path,
        default=Path("outputs/abm_empirical_calibrated_no_anti_20260701T075000Z"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/manuscript_abm_figures_20260701T083000Z"),
    )
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
