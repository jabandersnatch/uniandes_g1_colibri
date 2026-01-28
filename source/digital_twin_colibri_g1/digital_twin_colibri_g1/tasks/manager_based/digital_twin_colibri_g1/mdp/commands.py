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
from isaaclab.envs.mdp.commands import UniformVelocityCommand
from isaaclab.managers import CommandTerm
from isaaclab.markers import VisualizationMarkers
from isaaclab.utils.math import quat_from_euler_xyz

if TYPE_CHECKING:
    from isaaclab.envs import ManagerBasedEnv

    from .commands_cfg import (
        GoalBiasedVelocityCommandCfg,
        GoalDirectedVelocityCommandCfg,
        SimpleGoalCommandCfg,
    )


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
        # -- current goal position in world frame (x, y, z) - what robot sees NOW
        self.goal_pos_w = torch.zeros(self.num_envs, 3, device=self.device)
        # -- target goal position in world frame - where we're transitioning TO
        self.target_goal_pos_w = torch.zeros(self.num_envs, 3, device=self.device)
        # -- goal position at start of transition - where we're transitioning FROM
        self.start_goal_pos_w = torch.zeros(self.num_envs, 3, device=self.device)
        # -- goal position in base frame (x, y) - this is what gets output
        self.goal_pos_b = torch.zeros(self.num_envs, 2, device=self.device)

        # Transition tracking
        self.transition_start_time = torch.zeros(self.num_envs, device=self.device)
        self.is_transitioning = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)

        # Track last episode length to detect resets
        self.last_episode_length = torch.zeros(self.num_envs, device=self.device)

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

        # Check if goal is reached (configurable threshold)
        # Default 0.3m for training, can be increased to 0.5m for play mode
        self.metrics["goal_reached"] = (distance < self.cfg.goal_reaching_threshold).float()

    def _resample_command(self, env_ids: Sequence[int], is_goal_reached: bool = False, use_transition: bool = True):
        """Sample new goal positions with optional smooth transition.

        Args:
            env_ids: Environment indices for which to resample goals.
            is_goal_reached: If True, use shorter distance range for small jumps.
            use_transition: If True, smoothly interpolate to new goal. If False, jump immediately.
        """
        n = len(env_ids)

        # --- DISTANCE SAMPLING ---
        # Use shorter distance when goal was just reached (small jump)
        # Use normal distance for initial spawn or after robot reset
        if is_goal_reached and hasattr(self.cfg.ranges, 'goal_reached_distance'):
            goal_distance = torch.empty(n, device=self.device).uniform_(
                *self.cfg.ranges.goal_reached_distance
            )
        else:
            goal_distance = torch.empty(n, device=self.device).uniform_(
                *self.cfg.ranges.goal_distance
            )

        # --- FORWARD-BIASED ANGLE SAMPLING ---
        # Get robot's current heading (yaw angle in world frame)
        robot_heading = self.robot.data.heading_w[env_ids]

        # For initial spawn/reset: Place goals RIGHT IN FRONT (tight angle)
        # For goal reached: Allow wider spread for variety
        if not is_goal_reached:
            # Initial spawn: 80% chance of tight forward cone (±30°)
            # This makes most goals appear directly in front
            is_tight_forward = torch.rand(n, device=self.device) < 0.8

            angle_offset = torch.where(
                is_tight_forward,
                # Tight forward cone: ±30° (π/6 radians)
                torch.rand(n, device=self.device) * (math.pi / 3) - math.pi / 6,
                # Wide spread: anywhere in front hemisphere ±90°
                torch.rand(n, device=self.device) * math.pi - math.pi / 2,
            )
        else:
            # Goal reached: Use forward bias probability for variety
            # 65% in front hemisphere, 35% in back for exploration
            is_front_hemisphere = torch.rand(n, device=self.device) < self.cfg.forward_bias_probability

            angle_offset = torch.where(
                is_front_hemisphere,
                # Front: uniform in [-π/2, +π/2]
                torch.rand(n, device=self.device) * math.pi - math.pi / 2,
                # Back: uniform in [+π/2, +3π/2], then wrap
                torch.rand(n, device=self.device) * math.pi + math.pi / 2,
            )

        # Compute goal angle in world frame and wrap to [-π, π]
        from isaaclab.utils.math import wrap_to_pi
        goal_angle_world = wrap_to_pi(robot_heading + angle_offset)

        # Convert polar to Cartesian coordinates (relative to robot's current position)
        goal_x = goal_distance * torch.cos(goal_angle_world)
        goal_y = goal_distance * torch.sin(goal_angle_world)

        # Calculate new goal position in world frame
        new_goal_x = self.robot.data.root_pos_w[env_ids, 0] + goal_x
        new_goal_y = self.robot.data.root_pos_w[env_ids, 1] + goal_y
        new_goal_z = self.robot.data.default_root_state[env_ids, 2]

        if use_transition:
            # SMOOTH TRANSITION: Store current goal as start, new goal as target
            # Goal will interpolate smoothly over time (used when goal is reached)
            self.start_goal_pos_w[env_ids] = self.goal_pos_w[env_ids].clone()
            self.target_goal_pos_w[env_ids, 0] = new_goal_x
            self.target_goal_pos_w[env_ids, 1] = new_goal_y
            self.target_goal_pos_w[env_ids, 2] = new_goal_z

            # Mark as transitioning and record start time
            self.is_transitioning[env_ids] = True
            self.transition_start_time[env_ids] = self._env.episode_length_buf[env_ids].float() * self._env.step_dt
        else:
            # INSTANT SPAWN: Set goal position immediately (used on reset/initial spawn)
            # No transition, goal appears instantly at new position
            self.goal_pos_w[env_ids, 0] = new_goal_x
            self.goal_pos_w[env_ids, 1] = new_goal_y
            self.goal_pos_w[env_ids, 2] = new_goal_z
            self.target_goal_pos_w[env_ids] = self.goal_pos_w[env_ids].clone()
            self.start_goal_pos_w[env_ids] = self.goal_pos_w[env_ids].clone()

            # Not transitioning - goal is already at final position
            self.is_transitioning[env_ids] = False

    def _update_command(self):
        """Update goal position with reach-based resampling and smooth transitions.

        This is called every step to:
        1. Detect robot resets and regenerate goals (full distance)
        2. Detect goal reached and resample with small jump
        3. Interpolate between old and new goals (if transitioning)
        4. Transform to robot's base frame
        """
        # Calculate current time for each environment
        current_time = self._env.episode_length_buf.float() * self._env.step_dt

        # --- DETECT ROBOT RESETS (falling/terminating) ---
        # Episode length decreased or is zero = robot respawned
        current_episode_length = self._env.episode_length_buf.float()
        reset_ids = (current_episode_length < self.last_episode_length).nonzero(as_tuple=False).flatten()

        if len(reset_ids) > 0:
            # On reset: Resample goal at robot's NEW position
            # Use FULL distance range (2-4m from new spawn location)
            # NO TRANSITION - goal appears instantly at correct location
            self._resample_command(reset_ids, is_goal_reached=False, use_transition=False)

        # Update tracker for next step
        self.last_episode_length[:] = current_episode_length

        # --- DETECT GOAL REACHED (reach-based resampling) ---
        # Check which environments have reached their goal
        # Only resample if NOT currently transitioning (avoids rapid resampling)
        goal_reached_ids = (
            (self.metrics["goal_reached"] > 0.5) &  # Goal is reached
            (~self.is_transitioning)  # Not already transitioning
        ).nonzero(as_tuple=False).flatten()

        if len(goal_reached_ids) > 0:
            # Resample with SMALL jump distance (goal "moves away" slightly)
            # USE SMOOTH TRANSITION - goal interpolates to new position
            self._resample_command(goal_reached_ids, is_goal_reached=True, use_transition=True)

        # --- SMOOTH TRANSITION INTERPOLATION ---
        # For environments that are transitioning, interpolate
        transitioning_ids = self.is_transitioning.nonzero(as_tuple=False).flatten()

        if len(transitioning_ids) > 0:
            # Time since transition started
            elapsed = current_time[transitioning_ids] - self.transition_start_time[transitioning_ids]

            # Interpolation factor (0 to 1 over transition_time)
            t = (elapsed / self.cfg.goal_transition_time).clamp(0.0, 1.0)

            # Linear interpolation: current = start + t * (target - start)
            self.goal_pos_w[transitioning_ids] = (
                self.start_goal_pos_w[transitioning_ids] +
                t.unsqueeze(1) * (self.target_goal_pos_w[transitioning_ids] -
                                 self.start_goal_pos_w[transitioning_ids])
            )

            # Check if transition complete (t >= 1.0)
            completed = t >= 1.0
            if completed.any():
                completed_ids = transitioning_ids[completed]
                self.is_transitioning[completed_ids] = False

        # --- TRANSFORM TO BASE FRAME ---
        # Transform current goal to base frame (for ALL environments)
        goal_vec_w = self.goal_pos_w[:, :2] - self.robot.data.root_pos_w[:, :2]

        # Transform to base frame (simple 2D rotation)
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
        """Update the debug visualization with color change when goal is reached.

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

        # Select marker based on whether goal is reached
        # marker_indices: 0 = "goal_far" (green), 1 = "goal_reached" (blue)
        marker_indices = torch.where(
            self.metrics["goal_reached"] > 0.5,  # goal_reached is 1.0 when within threshold
            1,  # Use "goal_reached" marker (blue)
            0,  # Use "goal_far" marker (green)
        ).int()

        self.goal_visualizer.visualize(
            translations=self.goal_pos_w,
            orientations=goal_quat,
            marker_indices=marker_indices,
        )


class GoalBiasedVelocityCommand(UniformVelocityCommand):
    """Velocity command generator with bias toward goal positions.

    This extends the standard UniformVelocityCommand by biasing the randomly
    sampled velocities toward the current goal position. This creates a gentle
    preference for moving toward goals while maintaining the randomness and
    exploration that helps locomotion learning.

    The final velocity is a weighted blend:
        final_vel = (1 - bias) * random_vel + bias * goal_directed_vel

    This approach keeps all the benefits of the proven velocity tracking system
    while adding goal-awareness.
    """

    cfg: GoalBiasedVelocityCommandCfg
    """Configuration for the command generator."""

    def __init__(self, cfg: GoalBiasedVelocityCommandCfg, env: ManagerBasedEnv):
        """Initialize the goal-biased velocity command generator.

        Args:
            cfg: Configuration for the command generator.
            env: The environment instance.
        """
        # Initialize parent class (UniformVelocityCommand)
        super().__init__(cfg, env)

        # Store reference to goal command name
        self.goal_command_name = cfg.goal_command_name

    def _resample_command(self, env_ids: Sequence[int]):
        """Resample velocity commands with bias toward goal.

        This overrides the parent's _resample_command to blend random velocities
        with goal-directed velocities.

        Args:
            env_ids: Environment indices for which to resample commands.
        """
        # First, sample random velocities using parent's method
        super()._resample_command(env_ids)

        # If no goal bias, just use the random velocities
        if self.cfg.goal_bias <= 0.0:
            return

        # Get goal position from the goal command manager
        # Goal is in base frame: (x, y) where robot is at origin
        try:
            goal_pos_b = self._env.command_manager.get_command(self.goal_command_name)
        except KeyError:
            # If goal command doesn't exist, just use random velocities
            return

        # Calculate goal-directed velocity components
        # Direction to goal (normalized)
        goal_direction = goal_pos_b[env_ids, :2]  # (N, 2) - x, y in base frame
        goal_distance = torch.norm(goal_direction, dim=1, keepdim=True).clamp(min=1e-6)
        goal_unit_vec = goal_direction / goal_distance

        # Scale by desired velocity magnitude (use max velocity from ranges)
        max_forward_vel = self.cfg.ranges.lin_vel_x[1]
        goal_velocity = goal_unit_vec * max_forward_vel * 0.7  # 70% of max speed

        # Store the original random velocities
        random_vel_x = self.vel_command_b[env_ids, 0].clone()
        random_vel_y = self.vel_command_b[env_ids, 1].clone()

        # Blend random and goal-directed velocities
        # final = (1 - bias) * random + bias * goal_directed
        blend_factor = self.cfg.goal_bias

        self.vel_command_b[env_ids, 0] = (
            (1.0 - blend_factor) * random_vel_x + blend_factor * goal_velocity[:, 0]
        )
        self.vel_command_b[env_ids, 1] = (
            (1.0 - blend_factor) * random_vel_y + blend_factor * goal_velocity[:, 1]
        )

        # Angular velocity (yaw) remains mostly random, but can add slight bias
        # to point toward goal if desired - for now keep it random for more natural motion


class GoalDirectedVelocityCommand(UniformVelocityCommand):
    """Velocity command generator that ALWAYS tracks the goal position.

    Unlike GoalBiasedVelocityCommand which blends random and goal-directed velocities,
    this command generator produces velocities that ALWAYS point toward the goal.
    The velocity magnitude is smoothly adjusted based on distance to goal:
    - Far from goal: Full speed (max velocity)
    - Near goal: Reduced speed for smooth approach
    - Very close: Minimum speed (20% of max) to avoid oscillation

    This provides direct goal-directed navigation while maintaining smooth,
    natural robot movement through continuous velocity adjustments.

    Key features:
    - Velocity direction: Always toward goal
    - Velocity magnitude: Distance-dependent with configurable min threshold
    - Smooth transitions: No sudden velocity changes
    - Compatible with existing velocity tracking rewards
    """

    cfg: GoalDirectedVelocityCommandCfg
    """Configuration for the command generator."""

    def __init__(self, cfg: GoalDirectedVelocityCommandCfg, env: ManagerBasedEnv):
        """Initialize the goal-directed velocity command generator.

        Args:
            cfg: Configuration for the command generator.
            env: The environment instance.
        """
        # Initialize parent class (UniformVelocityCommand)
        super().__init__(cfg, env)

        # Store reference to goal command name
        self.goal_command_name = cfg.goal_command_name

        # Cache velocity parameters for efficiency
        self.max_lin_vel = cfg.ranges.lin_vel_x[1]  # Maximum forward velocity
        self.min_vel_ratio = cfg.min_velocity_ratio  # Minimum velocity as ratio of max
        self.distance_scaling = cfg.distance_scaling_factor  # Distance at which to start reducing speed

    def _resample_command(self, env_ids: Sequence[int]):
        """Generate goal-directed velocity commands.

        Instead of random sampling, this computes velocities that point toward
        the goal position with magnitude based on distance.

        Args:
            env_ids: Environment indices for which to resample commands.
        """
        # Get goal position from the goal command manager
        # Goal is in base frame: (x, y) where robot is at origin
        try:
            goal_pos_b = self._env.command_manager.get_command(self.goal_command_name)
        except KeyError:
            # If goal command doesn't exist, fall back to zero velocity
            self.vel_command_b[env_ids, :] = 0.0
            return

        # Calculate goal direction and distance (2D only - ignore Z)
        goal_direction = goal_pos_b[env_ids, :2]  # (N, 2) - x, y in base frame
        goal_distance = torch.norm(goal_direction, dim=1, keepdim=True).clamp(min=1e-6)
        goal_unit_vec = goal_direction / goal_distance

        # --- DISTANCE-BASED VELOCITY SCALING ---
        # Scale velocity based on distance with smooth falloff
        # - Far away (> distance_scaling): 100% max velocity
        # - Close (< distance_scaling): Linearly decrease to min_velocity_ratio

        # Normalized distance (0 to 1+, clamped at 1)
        normalized_distance = (goal_distance.squeeze(-1) / self.distance_scaling).clamp(0.0, 1.0)

        # Distance scaling: min_ratio to 1.0 based on distance
        distance_scale = self.min_vel_ratio + (1.0 - self.min_vel_ratio) * normalized_distance

        # --- HEADING-AWARE VELOCITY SCALING (NEW!) ---
        # Only move fast when robot is FACING the goal direction
        # This prevents backwards shuffling by requiring robot to turn first

        # Calculate goal direction angle in base frame
        # Note: goal_pos_b is already in base frame, so forward = positive X
        goal_angle_base = torch.atan2(goal_direction[:, 1], goal_direction[:, 0])

        # In base frame, robot heading is always 0 (forward is X+)
        # Heading error is just the goal angle in base frame
        heading_error = goal_angle_base

        # Calculate alignment using cosine
        # cos(0°) = 1.0 when goal is directly ahead
        # cos(90°) = 0.0 when goal is to the side
        # cos(180°) = -1.0 when goal is behind
        alignment = torch.cos(heading_error)

        # Map alignment [-1, 1] to [0, 1] range
        # This gives: 0.0 when facing backwards, 1.0 when facing forward
        alignment_factor = (alignment + 1.0) / 2.0

        # Apply heading-aware scaling with minimum 40% speed
        # RELAXED: Allow more movement even when not perfectly aligned (helps turning)
        # When facing goal (alignment_factor=1.0): heading_scale = 0.4 + 0.6 = 1.0
        # When perpendicular (alignment_factor=0.5): heading_scale = 0.4 + 0.3 = 0.7
        # When backwards (alignment_factor=0.0): heading_scale = 0.4 + 0.0 = 0.4
        min_heading_ratio = 0.4  # Increased from 0.2 to allow more movement while turning
        heading_scale = min_heading_ratio + (1.0 - min_heading_ratio) * alignment_factor

        # --- COMBINED VELOCITY MAGNITUDE ---
        # Combine both distance and heading scaling
        # Final speed = max_vel * distance_scale * heading_scale
        combined_scale = distance_scale * heading_scale
        desired_speed = combined_scale * self.max_lin_vel

        # --- SET VELOCITY COMMANDS ---
        # CRITICAL FIX: NEVER command backwards velocity!
        # Problem: If goal is behind and we command backwards velocity,
        #          velocity tracking reward (+3.0) REWARDS walking backwards!
        # Solution: Only command forward/lateral velocities. If goal is behind,
        #          command ZERO forward velocity (turn only) until aligned.

        # Calculate commanded velocity components
        cmd_vx = goal_unit_vec[:, 0] * desired_speed  # Forward/backward component
        cmd_vy = goal_unit_vec[:, 1] * desired_speed  # Lateral component

        # NEVER allow negative (backwards) forward velocity commands!
        # If goal is behind (cmd_vx < 0), clamp to zero → robot must turn first
        # If goal is ahead (cmd_vx > 0), use normal command
        self.vel_command_b[env_ids, 0] = torch.clamp(cmd_vx, min=0.0)

        # Lateral velocity is fine as-is (strafing is okay)
        self.vel_command_b[env_ids, 1] = cmd_vy

        # --- ANGULAR VELOCITY (YAW) ---
        # Calculate angle to goal for smooth turning
        # In base frame, this is just the goal_angle_base we calculated earlier
        angle_to_goal = goal_angle_base

        # Use proportional control for turning
        # Larger heading errors require more angular velocity
        max_ang_vel = self.cfg.ranges.ang_vel_z[1]

        # VERY HIGH turning gain to encourage fast direction changes
        # The robot should prioritize turning to face goal over walking misaligned
        turning_gain = 5.0  # Increased from 3.0 → very aggressive turning

        # Angular velocity proportional to heading error (with saturation at max)
        # When goal is behind (angle ±180°): Maximum turning speed
        # When goal is ahead (angle ~0°): Minimal turning
        # High gain means robot quickly reaches max angular velocity when misaligned
        self.vel_command_b[env_ids, 2] = (angle_to_goal * turning_gain).clamp(
            -max_ang_vel, max_ang_vel
        )

    def _update_command(self):
        """Update velocity commands every step.

        Unlike the parent class which only updates on resampling timer,
        we update EVERY step to continuously track the moving goal.
        """
        # Update for ALL environments every step (goal position changes as robot moves)
        all_env_ids = torch.arange(self.num_envs, device=self.device)
        self._resample_command(all_env_ids)

        # Update metrics
        self._update_metrics()
