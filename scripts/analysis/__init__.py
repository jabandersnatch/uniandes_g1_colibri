# Copyright (c) 2025, Jorge Mendez (Universidad de los Andes)
# SPDX-License-Identifier: BSD-3-Clause

"""Analysis scripts for thesis data extraction and visualization.

This package contains scripts for:
- extract_tensorboard.py: Extract training metrics from TensorBoard logs
- plot_training_curves.py: Generate publication-ready training plots
- evaluate_policy.py: Run policy evaluation and collect behavioral metrics

Usage examples:
    # Extract training data
    python scripts/analysis/extract_tensorboard.py --log_dir <path> --output_dir <path>

    # Generate plots
    python scripts/analysis/plot_training_curves.py --input_dir <path>

    # Evaluate policy (requires Isaac Sim)
    python scripts/analysis/evaluate_policy.py --task <task> --checkpoint <path>
"""
