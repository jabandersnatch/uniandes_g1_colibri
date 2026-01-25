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


def backwards_velocity_penalty(
    env: ManagerBasedRLEnv,
    threshold: float = -0.1,
    asset_cfg: SceneEntityCfg = SceneEntityCfg("robot"),
) -> torch.Tensor:
    """Penalize backwards velocity in robot's body frame.

    This penalty discourages the robot from moving backwards (shuffling) to reach
    goals. It penalizes negative forward velocity (vx) in the robot's body frame.

    The penalty only applies when velocity is below the threshold (default: -0.1 m/s),
    allowing small backwards movements for balance adjustments while penalizing
    deliberate backwards locomotion.

    Args:
        env: The learning environment.
        threshold: Velocity threshold (m/s) below which penalty applies. Negative values
                   mean backwards motion. Default: -0.1 (penalize when moving backwards
                   faster than 10 cm/s).
        asset_cfg: Asset configuration (default: "robot").

    Returns:
        Penalty value (0 when moving forward, positive when moving backward).
        Uses L2 squared kernel for smooth gradients.

    Example:
        # Penalize backwards velocity with weight -0.15
        self.rewards.backwards_penalty = RewTerm(
            func=mdp.backwards_velocity_penalty,
            weight=-0.15,
            params={"threshold": -0.1},
        )
    """
    # Extract the asset
    asset: Articulation = env.scene[asset_cfg.name]

    # Get forward/backward velocity in robot's body frame
    # root_lin_vel_b[:, 0] is the X-axis velocity in body frame:
    #   Positive = moving forward (good)
    #   Negative = moving backward (penalize)
    forward_vel = asset.data.root_lin_vel_b[:, 0]

    # Calculate backwards velocity amount (only when below threshold)
    # If forward_vel = -0.5 and threshold = -0.1:
    #   backwards_vel = clamp(-(-0.5) - (-0.1), min=0) = clamp(0.5 - 0.1, min=0) = 0.4
    # If forward_vel = 0.5 (moving forward):
    #   backwards_vel = clamp(-0.5 - (-0.1), min=0) = clamp(-0.6, min=0) = 0.0
    backwards_vel = torch.clamp(-forward_vel - (-threshold), min=0.0)

    # L2 squared penalty for smooth gradients
    return torch.square(backwards_vel)


def heading_alignment_reward(
    env: ManagerBasedRLEnv,
    command_name: str,
    std: float,
    asset_cfg: SceneEntityCfg = SceneEntityCfg("robot"),
) -> torch.Tensor:
    """Reward robot for facing toward the goal position.

    Encourages the robot to turn and align its heading with the goal direction
    before or while moving. This helps overcome the tendency to walk straight
    forward even when goal is to the side or behind.

    Uses exponential kernel based on heading error (angle difference between
    robot's heading and direction to goal).

    Args:
        env: The learning environment.
        command_name: Name of the goal command (e.g., "goal_position").
        std: Standard deviation for exponential kernel. Smaller values require
             tighter alignment. Typical: 0.3-1.0.
        asset_cfg: Asset configuration (default: "robot").

    Returns:
        Reward value (0 to 1) based on heading alignment.
        1.0 when perfectly facing goal, decays exponentially with angle error.

    Example:
        self.rewards.heading_alignment = RewTerm(
            func=mdp.heading_alignment_reward,
            weight=0.3,
            params={"command_name": "goal_position", "std": 0.5},
        )
    """
    # Extract the asset
    asset: Articulation = env.scene[asset_cfg.name]

    # Get goal position in base frame (2D: x, y)
    goal_pos_b = env.command_manager.get_command(command_name)

    # Calculate angle to goal in base frame
    # atan2(y, x) gives angle from robot's forward direction (X+) to goal
    goal_angle_base = torch.atan2(goal_pos_b[:, 1], goal_pos_b[:, 0])

    # Heading error is just the goal angle (in base frame, robot heading is always 0)
    # Small angle = well aligned, large angle = poorly aligned
    heading_error = torch.abs(goal_angle_base)

    # Exponential reward: exp(-error^2 / std^2)
    # Similar to velocity tracking rewards
    # Perfect alignment (error=0): reward = 1.0
    # 90° off (error=π/2): reward ≈ 0.0 (with std=0.5)
    return torch.exp(-torch.square(heading_error) / (std ** 2))


# ============================================
# Social Navigation Rewards (Phase 3)
# ============================================


def smooth_trajectory_reward(
    env: ManagerBasedRLEnv,
) -> torch.Tensor:
    """
    Reward smooth, non-jerky movements.

    Encourages the robot to move smoothly by penalizing rapid changes
    in actions between timesteps. This creates more comfortable and
    predictable robot behavior for humans nearby.

    Args:
        env: The learning environment.

    Returns:
        Smoothness reward per environment (0 to 1).
        Higher values indicate smoother movement.
    """
    device = env.device

    # Get current and previous actions
    actions = env.action_manager.action
    prev_actions = env.action_manager.prev_action

    # Compute action difference magnitude
    # Lower difference = smoother trajectory
    action_diff = torch.sum(torch.abs(actions - prev_actions), dim=1)

    # Normalize using exponential decay
    # Large differences result in low reward, small differences in high reward
    # The 0.1 scaling factor can be tuned based on typical action magnitudes
    smoothness = torch.exp(-0.1 * action_diff)

    return smoothness


def obstacle_proximity_penalty(
    env: ManagerBasedRLEnv,
    num_cylinders: int = 1,
    threshold: float = 1.5,
    std: float = 0.5,
    cylinder_radius: float = 0.3,
    asset_cfg: SceneEntityCfg = SceneEntityCfg("robot"),
) -> torch.Tensor:
    """Penalize proximity to cylinder obstacles using exponential kernel.

    Computes the minimum distance from robot to any cylinder obstacle and applies
    an exponential penalty. This uses analytical distance computation from known
    cylinder positions (more reliable than RayCaster for dynamic objects).

    Formula: exp(-(distance / std)^2) when distance < threshold, else 0

    Args:
        env: The learning environment.
        num_cylinders: Number of cylinder obstacles in scene.
        threshold: Distance threshold in meters beyond which no penalty applies.
        std: Standard deviation for exponential kernel. Smaller = sharper penalty.
        cylinder_radius: Radius of cylinders for edge distance calculation.
        asset_cfg: Robot asset configuration.

    Returns:
        Penalty value per environment (0 to 1).
        0.0 = no obstacles within threshold, 1.0 = obstacle touching robot.

    Example:
        # Warning penalty (gentle gradient at 1.5m)
        self.rewards.obstacle_proximity_warning = RewTerm(
            func=mdp.obstacle_proximity_penalty,
            weight=-0.5,
            params={"threshold": 1.5, "std": 0.5, "num_cylinders": 3},
        )

        # Critical penalty (sharp gradient at 0.8m)
        self.rewards.obstacle_proximity_critical = RewTerm(
            func=mdp.obstacle_proximity_penalty,
            weight=-2.0,
            params={"threshold": 0.8, "std": 0.3, "num_cylinders": 3},
        )
    """
    # Get robot position
    robot = env.scene[asset_cfg.name]
    robot_pos = robot.data.root_pos_w[:, :2]  # (num_envs, 2) - XY only

    # Compute minimum distance to any cylinder
    min_distance = torch.full(
        (env.num_envs,),
        float("inf"),
        device=env.device,
        dtype=torch.float32,
    )

    obstacles_found = 0
    for i in range(num_cylinders):
        obstacle_name = f"obstacle_{i}"
        # Try both attribute access and dict-style access
        try:
            obstacle = env.scene[obstacle_name]
            obstacle_pos = obstacle.data.root_pos_w[:, :2]
            obstacles_found += 1

            # Distance to cylinder edge (center distance minus radius)
            dist = torch.norm(robot_pos - obstacle_pos, dim=-1) - cylinder_radius
            dist = torch.clamp(dist, min=0.0)

            # Track minimum
            min_distance = torch.minimum(min_distance, dist)
        except (KeyError, AttributeError):
            # Obstacle not found in scene
            pass

    # Replace inf with threshold (no penalty for missing obstacles)
    min_distance = torch.where(
        torch.isinf(min_distance),
        torch.full_like(min_distance, threshold),
        min_distance,
    )

    # Compute exponential penalty
    penalty = torch.exp(-torch.square(min_distance / std))

    # Only apply within threshold
    penalty = torch.where(min_distance < threshold, penalty, torch.zeros_like(penalty))

    return penalty
