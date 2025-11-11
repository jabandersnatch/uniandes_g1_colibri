# Copyright (c) 2022-2025, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Custom reward functions for Colibri G1 navigation task."""

from __future__ import annotations

import torch
from typing import TYPE_CHECKING

from isaaclab.assets import Articulation
from isaaclab.managers import SceneEntityCfg
from isaaclab.utils.math import wrap_to_pi

if TYPE_CHECKING:
    from isaaclab.envs import ManagerBasedRLEnv


def joint_pos_target_l2(env: ManagerBasedRLEnv, target: float, asset_cfg: SceneEntityCfg) -> torch.Tensor:
    """Penalize joint position deviation from a target value."""
    # extract the used quantities (to enable type-hinting)
    asset: Articulation = env.scene[asset_cfg.name]
    # wrap the joint positions to (-pi, pi)
    joint_pos = wrap_to_pi(asset.data.joint_pos[:, asset_cfg.joint_ids])
    # compute the reward
    return torch.sum(torch.square(joint_pos - target), dim=1)


# ============================================
# Navigation Rewards
# ============================================


def goal_distance_exp(env: ManagerBasedRLEnv, command_name: str, std: float) -> torch.Tensor:
    """Exponential reward for approaching the goal position.

    Uses the same exponential kernel as velocity tracking rewards to maintain
    compatibility with the existing G1 locomotion reward structure.

    Formula: exp(-distance_squared / std^2)
    - Returns 1.0 when at goal (distance = 0)
    - Decays exponentially as distance increases
    - std parameter controls the decay rate

    Recommended usage for conservative goal-conditioned learning:
    - std = 5.0: Gentle gradient across 3-6m goal distance range
    - weight = 0.05: Small bonus that doesn't overpower velocity tracking

    Expected reward values (with std=5.0):
    - At 3m: 0.549 (weighted: 0.027)
    - At 4m: 0.449 (weighted: 0.022)
    - At 5m: 0.368 (weighted: 0.018)
    - At 6m: 0.301 (weighted: 0.015)

    This provides 2-4x the magnitude of current velocity tracking rewards (~0.01),
    enough to provide guidance but not enough to break locomotion learning.

    Args:
        env: The learning environment.
        command_name: Name of the goal command (e.g., "goal_position").
        std: Standard deviation for the exponential kernel. Larger values provide
             gentler gradients across longer distances.

    Returns:
        Exponential reward (0 to 1) based on squared distance to goal.
    """
    # Get the goal position command (2D: x, y in base frame)
    goal_pos_b = env.command_manager.get_command(command_name)

    # Calculate squared error (matching velocity tracking reward formula)
    # sum((goal_x - 0)^2 + (goal_y - 0)^2) since goal is in base frame
    distance_squared = torch.sum(torch.square(goal_pos_b[:, :2]), dim=1)

    # Exponential reward: exp(-distance^2 / std^2)
    # Same formula as track_lin_vel_xy_exp and track_ang_vel_z_exp
    return torch.exp(-distance_squared / (std ** 2))
