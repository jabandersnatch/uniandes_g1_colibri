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
        # VELOCITY COMMANDS: Customize for Colibri
        # ============================================

        # Adjust velocity ranges based on your environment constraints
        # Example: Slower speeds for indoor navigation
        # self.commands.base_velocity.ranges.lin_vel_x = (0.0, 1.0)  # m/s forward
        # self.commands.base_velocity.ranges.lin_vel_y = (-0.5, 0.5)  # m/s lateral
        # self.commands.base_velocity.ranges.ang_vel_z = (-1.0, 1.0)  # rad/s rotation

        # ============================================
        # REWARDS: Add custom rewards for Colibri task
        # ============================================

        # Example: You can add custom rewards here
        # Uncomment and modify if you need task-specific rewards

        # self.rewards.custom_colibri_reward = RewTerm(
        #     func=mdp.custom_reward_function,  # Define in mdp/rewards.py
        #     weight=1.0,
        # )

        # Example: Penalize undesired contacts with environment objects
        # self.rewards.obstacle_contact_penalty = RewTerm(
        #     func=mdp.undesired_contacts,
        #     weight=-2.0,
        #     params={
        #         "sensor_cfg": SceneEntityCfg("contact_forces", body_names="torso_link"),
        #         "threshold": 1.0,
        #     }
        # )

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
        # OPTIONAL: Fixed velocity commands for demo
        # ============================================

        # Uncomment to set fixed velocity commands during play
        # self.commands.base_velocity.ranges.lin_vel_x = (1.0, 1.0)  # 1 m/s forward
        # self.commands.base_velocity.ranges.lin_vel_y = (0.0, 0.0)  # No lateral
        # self.commands.base_velocity.ranges.ang_vel_z = (0.0, 0.0)  # No rotation
