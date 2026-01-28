# Copyright (c) 2022-2025, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Configuration for custom command generators."""

from __future__ import annotations

from dataclasses import MISSING

import isaaclab.sim as sim_utils
from isaaclab.envs.mdp.commands import UniformVelocityCommandCfg
from isaaclab.managers.manager_term_cfg import CommandTermCfg
from isaaclab.markers import VisualizationMarkersCfg
from isaaclab.utils import configclass

from .commands import GoalBiasedVelocityCommand, GoalDirectedVelocityCommand, SimpleGoalCommand


@configclass
class SimpleGoalCommandCfg(CommandTermCfg):
    """Configuration for the simple goal position command generator.

    This command generator samples random 2D goal positions at a fixed distance
    from the robot's current position. Goals are resampled periodically.
    """

    class_type: type = SimpleGoalCommand

    asset_name: str = MISSING
    """Name of the robot asset in the scene."""

    resampling_time_range: tuple[float, float] = MISSING
    """Time range for resampling the goal position (min, max) in seconds."""

    goal_transition_time: float = 1.5
    """Time in seconds to smoothly transition from old goal to new goal.

    Instead of instantly jumping to the new goal position (which can disorient
    the robot), we linearly interpolate over this time period. This provides:
    - Smoother visual feedback
    - Less sudden changes in reward gradient
    - Robot gets time to adjust heading
    - More natural learning signal

    Default: 1.5 seconds (feels natural, not too slow)
    """

    forward_bias_probability: float = 0.65
    """Probability that goal spawns in front hemisphere (vs. behind).

    This biases goal sampling toward the robot's forward direction to encourage
    forward locomotion learning. The robot's heading determines "forward".

    - 0.5: No bias, completely random (50% front, 50% back)
    - 0.65: Moderate forward bias (65% front, 35% back) - RECOMMENDED
    - 0.8: Strong forward bias (80% front, 20% back)
    - 1.0: Always in front (no backwards goals)

    Front hemisphere: ±90° from robot's heading
    Back hemisphere: remaining 180° arc

    Default: 0.65 (moderate bias, allows some backward exploration)
    """

    goal_reaching_threshold: float = 0.3
    """Distance threshold (in meters) for detecting goal reached.

    When the robot is closer than this distance to the goal, the goal is considered
    "reached" and a new goal is resampled.

    - 0.3: Tight threshold (training) - requires precise reaching
    - 0.5: Relaxed threshold (play mode) - more forgiving for evaluation

    Default: 0.3 meters (training mode)
    """

    @configclass
    class Ranges:
        """Uniform distribution ranges for goal sampling."""

        goal_distance: tuple[float, float] = MISSING
        """Range for goal distance from robot (min, max) in meters.

        Used for:
        - Initial goal spawn when environment starts
        - Goal resample after robot falls/resets
        """

        goal_reached_distance: tuple[float, float] = (0.5, 1.5)
        """Range for goal distance when goal is reached (small jump).

        When robot reaches the current goal, the goal "moves away" by sampling
        a new position at this shorter distance. This creates a continuous
        navigation task without large jumps.

        Smaller values = goal stays nearby (micro-adjustments)
        Larger values = goal jumps further (re-navigation required)

        Default: (0.5, 1.5) meters - small jump that requires continued movement
        """

    ranges: Ranges = MISSING
    """Range configurations for goal sampling."""

    # Visualization - Dual-color sphere (green when far, blue when reached)
    goal_visualizer_cfg: VisualizationMarkersCfg = VisualizationMarkersCfg(
        prim_path="/Visuals/Command/goal_position",
        markers={
            "goal_far": sim_utils.SphereCfg(
                radius=0.3,  # Large sphere - 30cm radius
                visual_material=sim_utils.PreviewSurfaceCfg(
                    diffuse_color=(0.0, 1.0, 0.0),  # Bright green when far
                    emissive_color=(0.0, 0.5, 0.0),  # Glowing effect
                    roughness=0.2,
                ),
            ),
            "goal_reached": sim_utils.SphereCfg(
                radius=0.3,  # Same size
                visual_material=sim_utils.PreviewSurfaceCfg(
                    diffuse_color=(0.0, 0.5, 1.0),  # Bright cyan/blue when reached
                    emissive_color=(0.0, 0.2, 0.5),  # Blue glow
                    roughness=0.2,
                ),
            ),
        },
    )
    """Configuration for the goal position visualization marker.

    Uses dual-color spheres that change based on proximity:
    - Green (goal_far): When goal is not yet reached (distance > 0.3m)
    - Cyan/Blue (goal_reached): When robot reaches goal (distance < 0.3m)

    This provides clear visual feedback when the goal is successfully reached.
    """


@configclass
class GoalBiasedVelocityCommandCfg(UniformVelocityCommandCfg):
    """Configuration for goal-biased velocity command generator.

    This extends UniformVelocityCommandCfg to add goal-biasing behavior.
    The velocity commands are blended between random exploration and
    goal-directed movement.
    """

    class_type: type = GoalBiasedVelocityCommand

    goal_command_name: str = MISSING
    """Name of the goal command to bias toward (e.g., 'goal_position')."""

    goal_bias: float = 0.2
    """Bias factor for goal-directed velocity (0.0 to 1.0).

    - 0.0: Purely random velocities (same as UniformVelocityCommand)
    - 0.2: 20% goal-directed, 80% random (recommended conservative start)
    - 0.5: 50/50 blend
    - 1.0: Purely goal-directed (not recommended, removes exploration)

    Default: 0.2 (gentle bias that maintains exploration)
    """


@configclass
class GoalDirectedVelocityCommandCfg(UniformVelocityCommandCfg):
    """Configuration for fully goal-directed velocity command generator.

    This command generator produces velocities that ALWAYS point directly
    toward the goal position. Unlike GoalBiasedVelocityCommand, there is
    no random component - the robot will always move toward the goal.

    The velocity magnitude is smoothly adjusted based on distance to goal:
    - Far from goal (> distance_scaling_factor): Full speed
    - Near goal (< distance_scaling_factor): Linearly reduced speed
    - At goal: Minimum speed (min_velocity_ratio * max_vel)

    This approach provides direct goal navigation while maintaining smooth,
    controlled movement through continuous velocity adjustments.
    """

    class_type: type = GoalDirectedVelocityCommand

    goal_command_name: str = MISSING
    """Name of the goal command to track (e.g., 'goal_position')."""

    min_velocity_ratio: float = 0.2
    """Minimum velocity as a ratio of maximum velocity (0.0 to 1.0).

    When very close to the goal, the robot will still move at this minimum
    speed to avoid oscillation and ensure smooth final approach.

    - 0.0: Can slow to complete stop at goal (may cause oscillation)
    - 0.2: Maintains 20% of max speed minimum (recommended)
    - 0.5: Maintains 50% of max speed minimum (conservative)

    Default: 0.2 (maintains smooth movement while allowing slowdown)
    """

    distance_scaling_factor: float = 3.0
    """Distance threshold (in meters) for velocity scaling.

    When distance to goal exceeds this value, robot moves at full speed.
    When distance is less, speed is linearly reduced based on min_velocity_ratio.

    Examples with max_vel=1.5 m/s, min_ratio=0.2:
    - At 3.0m: 1.5 m/s (100% speed)
    - At 1.5m: 0.9 m/s (60% speed)
    - At 0.5m: 0.4 m/s (27% speed)
    - At 0.0m: 0.3 m/s (20% speed, minimum)

    Default: 3.0 meters (starts reducing speed at medium range)
    """
