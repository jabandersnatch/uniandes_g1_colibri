# Copyright (c) 2022-2025, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Custom command generators for Colibri G1 navigation."""

from __future__ import annotations

import math
import torch
from collections.abc import Sequence
from typing import TYPE_CHECKING

from isaaclab.assets import Articulation
from isaaclab.managers import CommandTerm
from isaaclab.markers import VisualizationMarkers
from isaaclab.utils.math import quat_from_euler_xyz

if TYPE_CHECKING:
    from isaaclab.envs import ManagerBasedEnv

    from .commands_cfg import SimpleGoalCommandCfg


class SimpleGoalCommand(CommandTerm):
    """Simple goal position command generator for navigation.

    This command generator samples random 2D goal positions at a specified distance
    range from the robot's current position. The goal is expressed as a 2D position
    (x, y) in the robot's base frame and resamples at regular intervals.

    This runs alongside the existing velocity command system and provides goal
    positions that can be used for goal-conditioned learning.
    """

    cfg: SimpleGoalCommandCfg
    """Configuration for the command generator."""

    def __init__(self, cfg: SimpleGoalCommandCfg, env: ManagerBasedEnv):
        """Initialize the command generator.

        Args:
            cfg: The configuration for the command generator.
            env: The environment instance.
        """
        # Initialize the base class
        super().__init__(cfg, env)

        # Get the robot asset
        self.robot: Articulation = env.scene[cfg.asset_name]

        # Create buffers to store the goal command
        # -- goal position in world frame (x, y, z)
        self.goal_pos_w = torch.zeros(self.num_envs, 3, device=self.device)
        # -- goal position in base frame (x, y) - this is what gets output
        self.goal_pos_b = torch.zeros(self.num_envs, 2, device=self.device)

        # Metrics
        self.metrics["distance_to_goal"] = torch.zeros(self.num_envs, device=self.device)
        self.metrics["goal_reached"] = torch.zeros(self.num_envs, device=self.device)

    def __str__(self) -> str:
        msg = "SimpleGoalCommand:\n"
        msg += f"\tCommand dimension: {tuple(self.command.shape[1:])}\n"
        msg += f"\tResampling time range: {self.cfg.resampling_time_range}\n"
        msg += f"\tGoal distance range: {self.cfg.ranges.goal_distance}"
        return msg

    """
    Properties
    """

    @property
    def command(self) -> torch.Tensor:
        """The goal position in base frame. Shape is (num_envs, 2) for (x, y)."""
        return self.goal_pos_b

    """
    Implementation specific functions.
    """

    def _update_metrics(self):
        """Update metrics for logging."""
        # Calculate distance to goal (2D, ignoring Z)
        distance = torch.norm(
            self.goal_pos_w[:, :2] - self.robot.data.root_pos_w[:, :2],
            dim=1
        )
        self.metrics["distance_to_goal"] = distance

        # Check if goal is reached (within 0.3m threshold - tighter requirement)
        self.metrics["goal_reached"] = (distance < 0.3).float()

    def _resample_command(self, env_ids: Sequence[int]):
        """Sample new goal positions for the specified environments.

        Args:
            env_ids: Environment indices for which to resample goals.
        """
        n = len(env_ids)

        # Sample random distance within range
        r = torch.empty(n, device=self.device)
        goal_distance = r.uniform_(*self.cfg.ranges.goal_distance)

        # Sample random angle (0 to 2π)
        goal_angle = r.uniform_(0, 2 * math.pi)

        # Convert polar to Cartesian coordinates (relative to robot)
        goal_x = goal_distance * torch.cos(goal_angle)
        goal_y = goal_distance * torch.sin(goal_angle)

        # Set goal position in world frame
        # Start from robot's current position
        self.goal_pos_w[env_ids, 0] = self.robot.data.root_pos_w[env_ids, 0] + goal_x
        self.goal_pos_w[env_ids, 1] = self.robot.data.root_pos_w[env_ids, 1] + goal_y
        # Keep Z at robot's default height
        self.goal_pos_w[env_ids, 2] = self.robot.data.default_root_state[env_ids, 2]

    def _update_command(self):
        """Update the goal position to robot's base frame.

        This is called every step to transform the world-frame goal to the
        robot's current base frame.
        """
        # Calculate relative position in world frame
        goal_vec_w = self.goal_pos_w[:, :2] - self.robot.data.root_pos_w[:, :2]

        # Transform to base frame (simple 2D rotation)
        # Get robot's heading (yaw angle)
        heading = self.robot.data.heading_w
        cos_h = torch.cos(-heading)  # Negative for inverse rotation
        sin_h = torch.sin(-heading)

        # Rotate vector to base frame
        self.goal_pos_b[:, 0] = cos_h * goal_vec_w[:, 0] - sin_h * goal_vec_w[:, 1]
        self.goal_pos_b[:, 1] = sin_h * goal_vec_w[:, 0] + cos_h * goal_vec_w[:, 1]

    def _set_debug_vis_impl(self, debug_vis: bool):
        """Set the debug visualization.

        Args:
            debug_vis: Whether to enable debug visualization.
        """
        if debug_vis:
            # Create markers if they don't exist
            if not hasattr(self, "goal_visualizer"):
                self.goal_visualizer = VisualizationMarkers(self.cfg.goal_visualizer_cfg)
            # Set visibility to true
            self.goal_visualizer.set_visibility(True)
        else:
            if hasattr(self, "goal_visualizer"):
                self.goal_visualizer.set_visibility(False)

    def _debug_vis_callback(self, event):
        """Update the debug visualization.

        Args:
            event: The event that triggered the callback.
        """
        # Safety check: Don't visualize if robot/environment is not initialized
        # This prevents errors during shutdown when scene is destroyed
        if not self.robot.is_initialized:
            return

        # Visualize goal positions as markers
        # Orientation points in the direction of the goal (optional, can be identity)
        zero_rot = torch.zeros(self.num_envs, device=self.device)
        goal_quat = quat_from_euler_xyz(zero_rot, zero_rot, zero_rot)

        self.goal_visualizer.visualize(
            translations=self.goal_pos_w,
            orientations=goal_quat,
        )
