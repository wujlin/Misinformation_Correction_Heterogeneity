#!/usr/bin/env python3
"""Create concise main-text figures for the unified first-response analysis."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


INK = "#31373C"
GRAY = "#8B9298"
LIGHT_GRAY = "#D8DDE0"
WHITE = "#FFFFFF"
TEAL = "#176B73"
BLUE = "#3A6EA5"
CLAY = "#B8663C"


def set_style() -> None:
    mpl.rcParams.update(
        {
            "figure.facecolor": WHITE,
            "axes.facecolor": WHITE,
            "savefig.facecolor": WHITE,
            "font.family": "DejaVu Sans",
            "font.size": 8.5,
            "axes.labelsize": 8.5,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "axes.edgecolor": INK,
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
    ax.text(
        x,
        1.04,
        label,
        transform=ax.transAxes,
        fontsize=10,
        fontweight="bold",
        va="bottom",
        ha="left",
    )


def save(fig: plt.Figure, output_dir: Path, stem: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_dir / f"{stem}.pdf", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(output_dir / f"{stem}.png", dpi=320, bbox_inches="tight", pad_inches=0.02)
    fig.savefig(output_dir / f"{stem}.jpg", dpi=120, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def figure_main_contrasts(contrasts_path: Path, output_dir: Path) -> None:
    contrast = pd.read_csv(contrasts_path).set_index("contrast")
    specs = [
        (
            "prior cross-community participation: yes versus no",
            "Prior cross-community\nparticipation",
            TEAL,
        ),
        ("one versus zero early corrective responses", "First early corrective\nresponse", BLUE),
        ("two versus one early corrective responses", "Second early corrective\nresponse", BLUE),
        ("one-SD increase in early relation diversity", "Diversity of early\nresponse relations", CLAY),
    ]
    rows = []
    for key, label, color in specs:
        item = contrast.loc[key]
        rows.append(
            {
                "label": label,
                "estimate": float(item["estimate_probability_points"]) * 100,
                "low": float(item["ci_low"]) * 100,
                "high": float(item["ci_high"]) * 100,
                "color": color,
            }
        )
    frame = pd.DataFrame(rows)

    fig, ax = plt.subplots(figsize=(3.35, 2.75))
    y = np.arange(len(frame))[::-1]
    ax.axvline(0, color=LIGHT_GRAY, linewidth=1.0, zorder=0)
    for yi, (_, row) in zip(y, frame.iterrows()):
        ax.hlines(yi, row["low"], row["high"], color=row["color"], linewidth=1.7, zorder=2)
        ax.scatter(row["estimate"], yi, s=38, color=row["color"], edgecolor=WHITE, linewidth=0.7, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels(frame["label"])
    ax.set_xlabel("Probability difference\n(percentage points)")
    ax.set_xlim(-0.25, 4.65)
    ax.set_xticks([0, 1, 2, 3, 4])
    clean_axes(ax, hide_left=True)
    ax.tick_params(axis="y", pad=3)
    fig.subplots_adjust(left=0.51, right=0.97, bottom=0.25, top=0.97)
    save(fig, output_dir, "fig3-observational-mechanism")


def figure_correction_dose(probabilities_path: Path, output_dir: Path) -> None:
    probabilities = pd.read_csv(probabilities_path)
    probabilities = probabilities.loc[
        probabilities["model"].eq("focused_count_categories")
    ].reset_index(drop=True)
    x = np.arange(len(probabilities))
    values = probabilities["estimated_probability"].to_numpy(dtype=float) * 100
    low = probabilities["ci_low"].to_numpy(dtype=float) * 100
    high = probabilities["ci_high"].to_numpy(dtype=float) * 100

    fig, ax = plt.subplots(figsize=(3.35, 2.55))
    ax.plot(x, values, color=BLUE, linewidth=1.6, zorder=1)
    for xi, value, lower, upper in zip(x, values, low, high):
        ax.vlines(xi, lower, upper, color=BLUE, linewidth=1.7, zorder=2)
        ax.scatter(xi, value, s=42, color=BLUE, edgecolor=WHITE, linewidth=0.7, zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels(["0", "1", "2", "3", "4+"])
    ax.set_xlabel("Number of early corrective responses")
    ax.set_ylabel("Estimated probability (%)")
    ax.set_ylim(8.0, 29.0)
    ax.set_yticks([10, 15, 20, 25])
    ax.set_xlim(-0.28, 4.28)
    clean_axes(ax)
    fig.subplots_adjust(left=0.21, right=0.97, bottom=0.22, top=0.97)
    save(fig, output_dir, "fig4-correction-dose")


def figure_network_application(summary_path: Path, output_dir: Path) -> None:
    summary = pd.read_csv(summary_path)
    scenario_specs = [
        ("wider_access", "Wider\naccess"),
        ("one_more_early_correction", "Additional\ncorrection"),
        ("broader_early_relations", "Broader\nrelations"),
        ("combined", "Combined"),
    ]
    change_specs = [
        (
            "threads_with_correction",
            "Threads",
            TEAL,
        ),
        (
            "later_comments_after_correction",
            "Later comments",
            BLUE,
        ),
    ]

    fig, (ax_change, ax_profile) = plt.subplots(
        1,
        2,
        figsize=(7.05, 2.85),
        gridspec_kw={"width_ratios": [1.08, 1.0]},
    )

    x = np.arange(len(scenario_specs), dtype=float)
    bar_width = 0.34
    offsets = [-bar_width / 2, bar_width / 2]
    for offset, (metric, label, color) in zip(offsets, change_specs):
        panel = summary.loc[summary["metric"].eq(metric)].set_index("scenario")
        values = np.array(
            [float(panel.loc[scenario, "difference_from_baseline"]) * 100 for scenario, _ in scenario_specs]
        )
        low = np.array(
            [float(panel.loc[scenario, "difference_interval_low"]) * 100 for scenario, _ in scenario_specs]
        )
        high = np.array(
            [float(panel.loc[scenario, "difference_interval_high"]) * 100 for scenario, _ in scenario_specs]
        )
        ax_change.bar(
            x + offset,
            values,
            width=bar_width,
            color=color,
            edgecolor=WHITE,
            linewidth=0.6,
            label=label,
            zorder=2,
        )
        ax_change.errorbar(
            x + offset,
            values,
            yerr=np.vstack([values - low, high - values]),
            fmt="none",
            ecolor=color,
            elinewidth=1.1,
            capsize=2.0,
            capthick=1.1,
            zorder=3,
        )

    ax_change.axhline(0, color=INK, linewidth=0.8, zorder=1)
    ax_change.set_xticks(x)
    ax_change.set_xticklabels([label for _, label in scenario_specs])
    ax_change.set_ylabel("Change from baseline\n(percentage points)")
    ax_change.set_ylim(0, 11.6)
    ax_change.set_yticks([0, 2, 4, 6, 8, 10])
    panel_label(ax_change, "A")
    ax_change.legend(
        frameon=False,
        loc="upper left",
        bbox_to_anchor=(0.0, 1.04),
        ncol=2,
        handlelength=1.2,
        columnspacing=1.0,
        borderaxespad=0,
    )
    clean_axes(ax_change)

    profile_specs = [
        ("corrective_response_rate", "Corrective responses"),
        ("threads_with_correction", "Threads"),
        ("later_comments_after_correction", "Later comments"),
        ("same_branch_reach", "Same-branch reach"),
    ]
    baseline = summary.loc[summary["scenario"].eq("baseline")].set_index("metric")
    combined = summary.loc[summary["scenario"].eq("combined")].set_index("metric")
    y = np.arange(len(profile_specs))[::-1]
    baseline_values = np.array(
        [float(baseline.loc[metric, "estimate"]) * 100 for metric, _ in profile_specs]
    )
    combined_values = np.array(
        [float(combined.loc[metric, "estimate"]) * 100 for metric, _ in profile_specs]
    )
    gains = combined_values - baseline_values
    ax_profile.barh(
        y,
        baseline_values,
        height=0.54,
        color=LIGHT_GRAY,
        edgecolor=WHITE,
        linewidth=0.6,
        label="Observed baseline",
        zorder=2,
    )
    ax_profile.barh(
        y,
        gains,
        left=baseline_values,
        height=0.54,
        color=CLAY,
        edgecolor=WHITE,
        linewidth=0.6,
        label="Combined increase",
        zorder=3,
    )
    for yi, observed, projected in zip(y, baseline_values, combined_values):
        ax_profile.text(
            min(projected + 1.3, 72.0),
            yi,
            f"{observed:.1f} to {projected:.1f}",
            va="center",
            ha="left",
            fontsize=7.2,
            color=INK,
        )
    ax_profile.set_yticks(y)
    ax_profile.set_yticklabels([label for _, label in profile_specs])
    ax_profile.set_xlabel("Share (%)")
    ax_profile.set_xlim(0, 78)
    ax_profile.set_xticks([0, 20, 40, 60])
    panel_label(ax_profile, "B", x=-0.06)
    ax_profile.set_ylim(-0.6, 4.35)
    ax_profile.legend(
        frameon=False,
        loc="upper left",
        bbox_to_anchor=(0.0, 0.99),
        ncol=2,
        handlelength=1.2,
        columnspacing=0.9,
        fontsize=7.3,
    )
    clean_axes(ax_profile, hide_left=True)
    ax_profile.tick_params(axis="y", labelleft=True, pad=3)

    fig.subplots_adjust(left=0.10, right=0.985, bottom=0.24, top=0.84, wspace=0.48)
    save(fig, output_dir, "fig5-network-application")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build unified first-response figures.")
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path("outputs/focused_access_discourse_model_20260717T025108Z"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("manuscript/overleaf_upload/figures"),
    )
    parser.add_argument(
        "--network-dir",
        type=Path,
        default=Path("outputs/network_application_observed_reply_network_20260718T091417Z"),
    )
    args = parser.parse_args()
    set_style()
    tables = args.model_dir / "tables"
    figure_main_contrasts(tables / "average_probability_contrasts.csv", args.output_dir)
    figure_correction_dose(tables / "correction_count_probabilities.csv", args.output_dir)
    figure_network_application(
        args.network_dir / "tables" / "network_scenario_summary.csv",
        args.output_dir,
    )


if __name__ == "__main__":
    main()
