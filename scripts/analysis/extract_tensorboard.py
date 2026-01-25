#!/usr/bin/env python3
# Copyright (c) 2025, Jorge Mendez (Universidad de los Andes)
# SPDX-License-Identifier: BSD-3-Clause

"""Extract scalar metrics from TensorBoard event files to CSV format.

This script reads TensorBoard event files and exports scalar metrics
(rewards, losses, entropy) to CSV files for analysis and plotting.

Usage:
    python scripts/analysis/extract_tensorboard.py \
        --log_dir logs/rsl_rl/colibri_g1_social_nav/2025-12-01_00-22-15 \
        --output_dir outputs/analysis/training_curves
"""

import argparse
import os
from pathlib import Path

import pandas as pd
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator


# Default metrics to extract from RSL-RL training logs
DEFAULT_METRICS = [
    "Train/mean_reward",
    "Loss/policy_loss",
    "Loss/value_loss",
    "Loss/entropy",
]


def extract_scalars(log_dir: str, metrics: list[str] | None = None) -> dict[str, pd.DataFrame]:
    """Extract scalar metrics from TensorBoard event files.

    Args:
        log_dir: Path to directory containing TensorBoard event files.
        metrics: List of metric names to extract. If None, extracts all scalars.

    Returns:
        Dictionary mapping metric names to DataFrames with columns [step, wall_time, value].
    """
    # Find event files
    event_files = list(Path(log_dir).glob("events.out.tfevents.*"))
    if not event_files:
        raise FileNotFoundError(f"No TensorBoard event files found in {log_dir}")

    print(f"[INFO] Found {len(event_files)} event file(s) in {log_dir}")

    # Load events
    ea = EventAccumulator(log_dir)
    ea.Reload()

    # Get available scalar tags
    available_tags = ea.Tags().get("scalars", [])
    print(f"[INFO] Available scalar tags: {available_tags}")

    if metrics is None:
        metrics = available_tags
    else:
        # Filter to only available metrics
        missing = set(metrics) - set(available_tags)
        if missing:
            print(f"[WARN] Metrics not found: {missing}")
        metrics = [m for m in metrics if m in available_tags]

    # Extract each metric
    results = {}
    for metric in metrics:
        events = ea.Scalars(metric)
        data = [{"step": e.step, "wall_time": e.wall_time, "value": e.value} for e in events]
        results[metric] = pd.DataFrame(data)
        print(f"[INFO] Extracted {len(data)} points for '{metric}'")

    return results


def save_to_csv(data: dict[str, pd.DataFrame], output_dir: str) -> list[str]:
    """Save extracted metrics to CSV files.

    Args:
        data: Dictionary mapping metric names to DataFrames.
        output_dir: Directory to save CSV files.

    Returns:
        List of saved file paths.
    """
    os.makedirs(output_dir, exist_ok=True)

    saved_files = []
    for metric_name, df in data.items():
        # Create safe filename from metric name
        filename = metric_name.replace("/", "_").replace(" ", "_").lower() + ".csv"
        filepath = os.path.join(output_dir, filename)
        df.to_csv(filepath, index=False)
        saved_files.append(filepath)
        print(f"[INFO] Saved: {filepath}")

    return saved_files


def main():
    parser = argparse.ArgumentParser(
        description="Extract TensorBoard scalars to CSV for thesis analysis."
    )
    parser.add_argument(
        "--log_dir",
        type=str,
        required=True,
        help="Path to TensorBoard log directory containing event files.",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="outputs/analysis/training_curves",
        help="Directory to save CSV files.",
    )
    parser.add_argument(
        "--metrics",
        type=str,
        nargs="+",
        default=None,
        help="Specific metrics to extract. If not specified, extracts default RSL-RL metrics.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Extract all available scalar metrics.",
    )
    args = parser.parse_args()

    # Determine which metrics to extract
    if args.all:
        metrics = None  # Extract all
    elif args.metrics:
        metrics = args.metrics
    else:
        metrics = DEFAULT_METRICS

    print(f"[INFO] Extracting metrics from: {args.log_dir}")
    print(f"[INFO] Output directory: {args.output_dir}")

    # Extract and save
    data = extract_scalars(args.log_dir, metrics)

    if not data:
        print("[ERROR] No metrics extracted. Check log directory and metric names.")
        return

    saved_files = save_to_csv(data, args.output_dir)
    print(f"\n[SUCCESS] Extracted {len(saved_files)} metric(s) to CSV files.")

    # Print summary
    print("\n--- Summary ---")
    for metric, df in data.items():
        print(f"{metric}:")
        print(f"  Steps: {df['step'].min()} to {df['step'].max()}")
        print(f"  Values: min={df['value'].min():.4f}, max={df['value'].max():.4f}, final={df['value'].iloc[-1]:.4f}")


if __name__ == "__main__":
    main()
