#!/usr/bin/env python3
# Copyright (c) 2025, Jorge Mendez (Universidad de los Andes)
# SPDX-License-Identifier: BSD-3-Clause

"""Generate publication-ready training curve plots from CSV data.

This script reads CSV files produced by extract_tensorboard.py and generates
matplotlib figures suitable for thesis publication (PDF and PNG formats).

Usage:
    python scripts/analysis/plot_training_curves.py \
        --input_dir outputs/analysis/training_curves \
        --output_dir outputs/analysis/training_curves
"""

import argparse
import os
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# Publication-ready style settings
PLOT_STYLE = {
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif", "serif"],
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 12,
    "legend.fontsize": 10,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "figure.figsize": (8, 6),
    "figure.dpi": 100,
    "savefig.dpi": 300,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "lines.linewidth": 1.5,
}


def apply_style():
    """Apply publication-ready matplotlib style."""
    plt.rcParams.update(PLOT_STYLE)


def plot_single_metric(
    df: pd.DataFrame,
    title: str,
    ylabel: str,
    output_path: str,
    smooth_window: int = 10,
    show_raw: bool = True,
):
    """Create a single metric plot with optional smoothing.

    Args:
        df: DataFrame with columns [step, wall_time, value].
        title: Plot title.
        ylabel: Y-axis label.
        output_path: Base path for output (without extension).
        smooth_window: Window size for rolling average smoothing.
        show_raw: Whether to show raw data as faint background.
    """
    apply_style()
    fig, ax = plt.subplots()

    steps = df["step"]
    values = df["value"]

    # Plot raw data (faint)
    if show_raw and smooth_window > 1:
        ax.plot(steps, values, alpha=0.2, color="blue", linewidth=0.5, label="_nolegend_")

    # Plot smoothed data
    if smooth_window > 1 and len(values) >= smooth_window:
        smoothed = values.rolling(window=smooth_window, min_periods=1).mean()
        ax.plot(steps, smoothed, color="blue", label=f"Smoothed (window={smooth_window})")
    else:
        ax.plot(steps, values, color="blue", label="Value")

    ax.set_xlabel("Training Iterations")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(loc="best")

    # Tight layout
    plt.tight_layout()

    # Save as PDF (vector) and PNG (raster)
    fig.savefig(f"{output_path}.pdf", format="pdf", bbox_inches="tight")
    fig.savefig(f"{output_path}.png", format="png", bbox_inches="tight")
    print(f"[INFO] Saved: {output_path}.pdf and {output_path}.png")

    plt.close(fig)


def plot_losses(
    policy_loss_df: pd.DataFrame | None,
    value_loss_df: pd.DataFrame | None,
    output_path: str,
    smooth_window: int = 10,
):
    """Create a combined loss plot with policy and value losses.

    Args:
        policy_loss_df: DataFrame for policy loss.
        value_loss_df: DataFrame for value loss.
        output_path: Base path for output (without extension).
        smooth_window: Window size for rolling average smoothing.
    """
    if policy_loss_df is None and value_loss_df is None:
        print("[WARN] No loss data available for combined plot.")
        return

    apply_style()
    fig, ax = plt.subplots()

    colors = {"policy": "blue", "value": "red"}

    if policy_loss_df is not None:
        steps = policy_loss_df["step"]
        values = policy_loss_df["value"]
        if smooth_window > 1 and len(values) >= smooth_window:
            smoothed = values.rolling(window=smooth_window, min_periods=1).mean()
            ax.plot(steps, smoothed, color=colors["policy"], label="Policy Loss")
        else:
            ax.plot(steps, values, color=colors["policy"], label="Policy Loss")

    if value_loss_df is not None:
        steps = value_loss_df["step"]
        values = value_loss_df["value"]
        if smooth_window > 1 and len(values) >= smooth_window:
            smoothed = values.rolling(window=smooth_window, min_periods=1).mean()
            ax.plot(steps, smoothed, color=colors["value"], label="Value Loss")
        else:
            ax.plot(steps, values, color=colors["value"], label="Value Loss")

    ax.set_xlabel("Training Iterations")
    ax.set_ylabel("Loss")
    ax.set_title("Training Losses")
    ax.legend(loc="best")

    plt.tight_layout()

    fig.savefig(f"{output_path}.pdf", format="pdf", bbox_inches="tight")
    fig.savefig(f"{output_path}.png", format="png", bbox_inches="tight")
    print(f"[INFO] Saved: {output_path}.pdf and {output_path}.png")

    plt.close(fig)


def load_csv_files(input_dir: str) -> dict[str, pd.DataFrame]:
    """Load all CSV files from the input directory.

    Args:
        input_dir: Directory containing CSV files.

    Returns:
        Dictionary mapping filenames (without extension) to DataFrames.
    """
    data = {}
    csv_files = list(Path(input_dir).glob("*.csv"))

    for csv_file in csv_files:
        name = csv_file.stem
        df = pd.read_csv(csv_file)
        data[name] = df
        print(f"[INFO] Loaded: {csv_file.name} ({len(df)} rows)")

    return data


def main():
    parser = argparse.ArgumentParser(
        description="Generate publication-ready training curve plots."
    )
    parser.add_argument(
        "--input_dir",
        type=str,
        default="outputs/analysis/training_curves",
        help="Directory containing CSV files from extract_tensorboard.py.",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default=None,
        help="Directory to save plots. Defaults to input_dir.",
    )
    parser.add_argument(
        "--smooth",
        type=int,
        default=10,
        help="Smoothing window size for rolling average.",
    )
    parser.add_argument(
        "--no-raw",
        action="store_true",
        help="Do not show raw data behind smoothed curve.",
    )
    args = parser.parse_args()

    output_dir = args.output_dir or args.input_dir
    os.makedirs(output_dir, exist_ok=True)

    print(f"[INFO] Loading CSV files from: {args.input_dir}")
    data = load_csv_files(args.input_dir)

    if not data:
        print("[ERROR] No CSV files found in input directory.")
        return

    # Plot episode reward (primary figure)
    reward_key = None
    for key in ["train_mean_reward", "mean_reward", "episode_reward"]:
        if key in data:
            reward_key = key
            break

    if reward_key:
        plot_single_metric(
            data[reward_key],
            title="Episode Reward During Training",
            ylabel="Mean Episode Reward",
            output_path=os.path.join(output_dir, "episode_reward"),
            smooth_window=args.smooth,
            show_raw=not args.no_raw,
        )
    else:
        print("[WARN] No reward metric found. Expected 'train_mean_reward' or similar.")

    # Plot losses (combined) - RSL-RL uses "surrogate" for policy loss
    policy_df = data.get("loss_surrogate")
    if policy_df is None:
        policy_df = data.get("loss_policy_loss")
    value_df = data.get("loss_value_function")
    if value_df is None:
        value_df = data.get("loss_value_loss")
    if policy_df is not None or value_df is not None:
        plot_losses(
            policy_df,
            value_df,
            output_path=os.path.join(output_dir, "training_losses"),
            smooth_window=args.smooth,
        )

    # Plot episode length
    length_key = None
    for key in ["train_mean_episode_length", "mean_episode_length"]:
        if key in data:
            length_key = key
            break

    if length_key:
        plot_single_metric(
            data[length_key],
            title="Episode Length During Training",
            ylabel="Mean Episode Length (steps)",
            output_path=os.path.join(output_dir, "episode_length"),
            smooth_window=args.smooth,
            show_raw=not args.no_raw,
        )

    # Plot goal-related metrics if available
    if "metrics_goal_position_distance_to_goal" in data:
        plot_single_metric(
            data["metrics_goal_position_distance_to_goal"],
            title="Distance to Goal During Training",
            ylabel="Mean Distance to Goal (m)",
            output_path=os.path.join(output_dir, "distance_to_goal"),
            smooth_window=args.smooth,
            show_raw=not args.no_raw,
        )

    if "metrics_goal_position_goal_reached" in data:
        plot_single_metric(
            data["metrics_goal_position_goal_reached"],
            title="Goal Reached Rate During Training",
            ylabel="Goal Reached Rate",
            output_path=os.path.join(output_dir, "goal_reached_rate"),
            smooth_window=args.smooth,
            show_raw=not args.no_raw,
        )

    # Plot entropy
    entropy_key = None
    for key in ["loss_entropy", "entropy"]:
        if key in data:
            entropy_key = key
            break

    if entropy_key:
        plot_single_metric(
            data[entropy_key],
            title="Policy Entropy During Training",
            ylabel="Entropy",
            output_path=os.path.join(output_dir, "policy_entropy"),
            smooth_window=args.smooth,
            show_raw=not args.no_raw,
        )

    print(f"\n[SUCCESS] Plots saved to: {output_dir}")


if __name__ == "__main__":
    main()
