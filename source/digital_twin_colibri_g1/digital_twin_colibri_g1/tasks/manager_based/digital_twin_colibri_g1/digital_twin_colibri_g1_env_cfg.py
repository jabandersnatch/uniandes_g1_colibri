# Copyright (c) 2022-2025, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""
G1 Humanoid Robot Environment for Digital Twin Colibri Project.

This environment configures the Unitree G1 humanoid robot for velocity tracking
in a custom USD environment (Colibri digital twin).
"""

from __future__ import annotations

import os
from pathlib import Path

from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.terrains import TerrainImporterCfg
from isaaclab.utils import configclass
from isaaclab.utils.assets import ISAAC_NUCLEUS_DIR

# ============================================
# Import base G1 configuration from IsaacLab
# ============================================
from isaaclab_tasks.manager_based.locomotion.velocity.config.g1.flat_env_cfg import (
    G1FlatEnvCfg,
)

# Import custom MDP functions if needed
from . import mdp

##
# Environment Configuration
##


@configclass
class DigitalTwinColibriG1EnvCfg(G1FlatEnvCfg):
    """
    G1 humanoid robot for velocity tracking in Colibri digital twin environment.

    This configuration inherits from the standard G1 flat terrain config
    and customizes it for the Colibri project's specific requirements.
    """

    def __post_init__(self):
        # Call parent initialization first to get all G1 defaults
        super().__post_init__()

        # ============================================
        # TERRAIN: Replace with Custom USD Environment
        # ============================================

        # Path to custom Colibri USD environment
        ASSETS_DIR = (
            Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent
            / "assets"
        )

        # Load custom USD environment for Colibri digital twin
        usd_path = ASSETS_DIR / "colivriLab" / "ColibriBuilding.usd"

        self.scene.terrain = TerrainImporterCfg(
            prim_path="/World/ground",
            terrain_type="usd",
            usd_path=str(usd_path),
            terrain_generator=None,
            collision_group=-1,
        )

        # ============================================
        # SCENE SETTINGS: Adjust for your hardware
        # ============================================

        # Reduce number of parallel environments if needed
        # G1 default is 4096, reduce if your USD is complex or GPU memory limited
        self.scene.num_envs = 512  # Adjust based on your GPU

        # Adjust environment spacing for your specific environment
        self.scene.env_spacing = 0.2

        # Episode length (seconds)
        self.episode_length_s = 20.0

        # ============================================
        # ROBOT SPAWNING: Adjust height for raised floor
        # ============================================

        # Override spawn height to prevent robots getting stuck in raised floor
        # Adjust the Z value based on your floor height in the USD
        # The range (1.0, 1.0) spawns robots at exactly 1.0m above origin
        # Increase if needed based on your floor elevation
        self.events.reset_base.params["pose_range"]["z"] = (1.2, 1.2)

        # ============================================
        # GOAL POSITION: Add goal tracking for navigation
        # ============================================

        # Add goal position command (runs alongside velocity commands)
        # Goals are sampled 2-4m from robot (closer for easier reaching)
        # Resample every 20-30s (longer time to allow robot to reach goal)
        self.commands.goal_position = mdp.SimpleGoalCommandCfg(
            asset_name="robot",
            resampling_time_range=(20.0, 30.0),  # Increased: Give more time to reach goal
            debug_vis=True,  # Enable visualization with color change when reached
            ranges=mdp.SimpleGoalCommandCfg.Ranges(
                goal_distance=(2.0, 4.0),  # Reduced: Closer goals (2-4m instead of 3-6m)
            ),
        )

        # ============================================
        # VELOCITY COMMANDS: Replace with goal-directed velocity
        # ============================================

        # Replace random velocity commands with goal-directed commands
        # Robot will ALWAYS move toward the goal with smooth speed adjustments
        self.commands.base_velocity = mdp.GoalDirectedVelocityCommandCfg(
            asset_name="robot",
            goal_command_name="goal_position",  # Track the goal position command
            resampling_time_range=(100.0, 100.0),  # Not used (updates every step)
            min_velocity_ratio=0.2,  # Maintain at least 20% speed when close
            distance_scaling_factor=3.0,  # Start reducing speed within 3m
            debug_vis=True,  # Show velocity arrow
            ranges=mdp.GoalDirectedVelocityCommandCfg.Ranges(
                # Original G1 velocity ranges (reduced from 1.5 back to 1.0)
                lin_vel_x=(0.0, 1.0),  # Forward: 0-1.0 m/s (original G1 range)
                lin_vel_y=(-0.5, 0.5),  # Lateral: ±0.5 m/s (original G1 range)
                ang_vel_z=(-1.0, 1.0),  # Rotation: ±1.0 rad/s (original G1 range)
                heading=(-3.14, 3.14),  # Full rotation range
            ),
        )

        # ============================================
        # OBSERVATIONS: Add goal position to observation space
        # ============================================

        # Add goal position (2D: x, y in base frame) to policy observations
        self.observations.policy.goal_position = ObsTerm(
            func=mdp.generated_commands,
            params={"command_name": "goal_position"},
        )

        # ============================================
        # REWARDS: Add custom rewards for Colibri task (GOAL-DIRECTED)
        # ============================================

        # GOAL-DIRECTED APPROACH: Direct navigation with smooth movement
        # Velocity commands ALWAYS point toward goal (no randomness)
        # Velocity magnitude smoothly adjusts based on distance
        #
        # Philosophy: Teach the policy to track goal-directed velocities!
        # - Velocity commands always point toward goal (direct navigation)
        # - Speed adjusts smoothly: fast when far, slow when close
        # - Policy learns to execute these goal-directed velocities
        # - Reward for both tracking velocity AND approaching goal
        #
        # Reward Balancing:
        #   Velocity tracking: weight 1.0 + 2.0 = 3.0 (learn to follow commands)
        #   Goal tracking:     weight 0.3 + 0.2 = 0.5 (bonus for proximity)
        #   Ratio:             6:1 (velocity tracking dominant)
        # Since commands point toward goal, tracking them achieves navigation!

        # Coarse goal tracking (wide gradient for exploration)
        self.rewards.goal_tracking = RewTerm(
            func=mdp.goal_distance_exp,
            weight=0.3,  # Was 0.05 - now 6x stronger!
            params={
                "command_name": "goal_position",
                "std": 5.0,  # Gentle gradient across 3-6m range
            },
        )

        # Fine goal tracking (tight gradient for precision near goal)
        self.rewards.goal_tracking_fine = RewTerm(
            func=mdp.goal_distance_exp,
            weight=0.2,  # Additional precision reward
            params={
                "command_name": "goal_position",
                "std": 3.0,  # Tighter gradient for final approach
            },
        )

        # Backwards velocity penalty (discourage backwards shuffling, but not too harsh)
        # Reduced to allow natural turning movements that may involve small backwards steps
        self.rewards.backwards_penalty = RewTerm(
            func=mdp.backwards_velocity_penalty,
            weight=-0.5,  # Moderate penalty (was -2.0, too harsh)
            params={
                "threshold": -0.05,  # Small threshold to allow balance adjustments
            },
        )

        # Heading alignment reward (encourage facing toward goal)
        # Rewards robot for turning to face the goal direction
        self.rewards.heading_alignment = RewTerm(
            func=mdp.heading_alignment_reward,
            weight=0.3,  # Significant reward for good alignment
            params={
                "command_name": "goal_position",
                "std": 0.5,  # Exponential kernel (tight alignment preferred)
            },
        )

        # ============================================
        # OBSERVATIONS: Modify if needed
        # ============================================

        # The G1 config already includes:
        # - base_lin_vel, base_ang_vel
        # - projected_gravity
        # - velocity_commands
        # - joint_pos, joint_vel
        # - actions
        # - height_scan (disabled for flat terrain, but can re-enable for USD)

        # Example: Re-enable height scanning if your USD has terrain variation
        # from isaaclab.sensors import RayCasterCfg, patterns
        # self.scene.height_scanner = RayCasterCfg(
        #     prim_path="{ENV_REGEX_NS}/Robot/torso_link",
        #     offset=RayCasterCfg.OffsetCfg(pos=(0.0, 0.0, 20.0)),
        #     ray_alignment="yaw",
        #     pattern_cfg=patterns.GridPatternCfg(resolution=0.1, size=[1.6, 1.0]),
        #     debug_vis=False,
        #     mesh_prim_paths=["/World/ground"],
        # )

        # ============================================
        # VIEWER SETTINGS: Better camera for visualization
        # ============================================

        # Adjust viewer camera position for better visualization
        self.viewer.eye = (5.0, 5.0, 3.0)  # Camera position
        self.viewer.lookat = (0.0, 0.0, 0.0)  # Camera target


@configclass
class DigitalTwinColibriG1EnvCfg_PLAY(DigitalTwinColibriG1EnvCfg):
    """
    Play/evaluation configuration for visualization and policy testing.

    This config reduces the number of environments and disables randomization
    for better visualization and consistent evaluation.
    """

    def __post_init__(self):
        # Call parent initialization
        super().__post_init__()

        # ============================================
        # SCENE: Fewer environments for visualization
        # ============================================

        self.scene.num_envs = 10  # Small number for visualization
        self.scene.env_spacing = 5

        # Longer episodes for evaluation/demo
        self.episode_length_s = 30.0

        # ============================================
        # DISABLE RANDOMIZATION for consistent eval
        # ============================================

        # Disable observation noise
        self.observations.policy.enable_corruption = False

        # Remove external disturbances
        if hasattr(self.events, "base_external_force_torque"):
            self.events.base_external_force_torque = None
        if hasattr(self.events, "push_robot"):
            self.events.push_robot = None

        # ============================================
        # DISABLE STANDING for clearer visualization
        # ============================================

        # In PLAY mode, disable "standing" environments (where robot stands still)
        # This prevents confusing behavior where:
        # - Green velocity arrow disappears
        # - Robot appears "frozen"
        # Training keeps standing enabled for diversity (2%)
        self.commands.base_velocity.rel_standing_envs = 0.0

        # ============================================
        # OPTIONAL: Fixed velocity commands for demo
        # ============================================

        # Uncomment to set fixed velocity commands during play
        # self.commands.base_velocity.ranges.lin_vel_x = (1.0, 1.0)  # 1 m/s forward
        # self.commands.base_velocity.ranges.lin_vel_y = (0.0, 0.0)  # No lateral
        # self.commands.base_velocity.ranges.ang_vel_z = (0.0, 0.0)  # No rotation
