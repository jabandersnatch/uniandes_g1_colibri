# Copyright (c) 2024, Universidad de los Andes
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""
G1 Social Navigation Environment - LiDAR + People + Social Rewards.

This module provides the complete social navigation environment configuration
that combines:
- LiDAR-based perception (sector distances)
- Animated human characters as dynamic obstacles
- Social navigation rewards (human proximity, personal space, smooth trajectory)

Task Variants:
    - Isaac-Colibri-G1-SocialNav-v0: Training environment
    - Isaac-Colibri-G1-SocialNav-Play-v0: Visualization environment
"""

from __future__ import annotations

from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.utils import configclass

from .people_env_cfg import (
    DigitalTwinColibriG1PeopleEnvCfg,
    DigitalTwinColibriG1PeopleEnvCfg_PLAY,
    PeopleManagerCfg,
)
from . import mdp


@configclass
class LidarObservationCfg:
    """Configuration for LiDAR-based observations.

    The LiDAR point cloud is processed into sector-based distance observations
    suitable for policy learning. This provides a fixed-size observation vector
    regardless of the number of LiDAR points.

    Attributes:
        num_sectors: Number of angular sectors to divide the 360° field of view.
        max_range: Maximum detection range in meters (obstacles beyond are ignored).
        min_height: Minimum height for point filtering (above ground).
        max_height: Maximum height for point filtering (below ceiling).
    """

    # Number of sectors to divide the 360° around the robot
    # 16 sectors = 22.5° per sector
    num_sectors: int = 16

    # Maximum range for observation normalization
    max_range: float = 10.0

    # Height filtering for relevant obstacles
    min_height: float = 0.2  # Above ground
    max_height: float = 2.0  # Below typical ceiling


@configclass
class SocialNavRewardsCfg:
    """Configuration for social navigation specific rewards.

    These rewards encourage the robot to maintain appropriate distances
    from humans while navigating to goals.

    Attributes:
        human_proximity_weight: Penalty for being within proximity threshold.
        human_proximity_threshold: Distance at which penalty starts (meters).
        personal_space_weight: Strong penalty for personal space violation.
        personal_space_threshold: Distance defining personal space (meters).
        smooth_trajectory_weight: Reward for smooth, non-jerky movements.
    """

    # Human proximity - penalize getting too close to people
    human_proximity_weight: float = -0.5
    human_proximity_threshold: float = 1.5  # Social distance (meters)

    # Personal space - stronger penalty for very close encounters
    personal_space_weight: float = -2.0
    personal_space_threshold: float = 0.8  # Personal space (meters)

    # Smooth trajectory - penalize jerky movements
    smooth_trajectory_weight: float = 0.1


@configclass
class DigitalTwinColibriG1SocialNavEnvCfg(DigitalTwinColibriG1PeopleEnvCfg):
    """
    G1 Social Navigation Environment: LiDAR perception + People avoidance.

    This configuration builds on the People environment by adding:
    - LiDAR sector observations for the policy
    - Social navigation rewards for human-aware navigation
    - Larger network configuration for handling additional observations

    The robot learns to:
    - Navigate to goals using velocity commands
    - Perceive obstacles via LiDAR sectors
    - Maintain appropriate distance from humans
    - Move smoothly without jerky motions

    Observation Space Extension:
        - lidar_sectors: Minimum distance per angular sector (num_sectors dimensions)

    Reward Additions:
        - human_proximity: Penalty for approaching humans
        - personal_space: Strong penalty for violating personal space
        - smooth_trajectory: Reward for smooth movements
    """

    # LiDAR observation configuration
    lidar_obs: LidarObservationCfg = LidarObservationCfg()

    # Social navigation rewards configuration
    social_rewards: SocialNavRewardsCfg = SocialNavRewardsCfg()

    def __post_init__(self):
        # Call parent initialization (gets People + base config)
        super().__post_init__()

        # ============================================
        # SCENE: Adjust for LiDAR + People overhead
        # ============================================

        # Reduced environments due to combined overhead
        # LiDAR processing + character animation
        self.scene.num_envs = 256

        # Keep large spacing for people movement
        self.scene.env_spacing = 15.0

        # ============================================
        # OBSERVATIONS: Add LiDAR-derived features
        # ============================================

        # LiDAR sector distances (closest obstacle per angular sector)
        # Provides spatial awareness for obstacle avoidance
        self.observations.policy.lidar_sectors = ObsTerm(
            func=mdp.lidar_sector_distances,
            params={
                "num_sectors": self.lidar_obs.num_sectors,
                "max_range": self.lidar_obs.max_range,
            },
        )

        # ============================================
        # REWARDS: Add social navigation rewards
        # ============================================

        # Penalty for getting close to humans
        # Encourages maintaining social distance (1.5m)
        self.rewards.human_proximity = RewTerm(
            func=mdp.human_proximity_penalty,
            weight=self.social_rewards.human_proximity_weight,
            params={"threshold": self.social_rewards.human_proximity_threshold},
        )

        # Strong penalty for personal space violation
        # Critical for safety (0.8m buffer)
        self.rewards.personal_space = RewTerm(
            func=mdp.personal_space_violation,
            weight=self.social_rewards.personal_space_weight,
            params={"threshold": self.social_rewards.personal_space_threshold},
        )

        # Reward smooth trajectories
        # Encourages comfortable, predictable robot behavior
        self.rewards.smooth_trajectory = RewTerm(
            func=mdp.smooth_trajectory_reward,
            weight=self.social_rewards.smooth_trajectory_weight,
        )


@configclass
class DigitalTwinColibriG1SocialNavEnvCfg_PLAY(DigitalTwinColibriG1PeopleEnvCfg_PLAY):
    """
    Play/visualization configuration for Social Navigation.

    Uses the same observation and reward structure as training,
    but with fewer environments for clearer visualization.
    """

    # LiDAR observation configuration (same as training)
    lidar_obs: LidarObservationCfg = LidarObservationCfg()

    # Social navigation rewards configuration (same as training)
    social_rewards: SocialNavRewardsCfg = SocialNavRewardsCfg()

    def __post_init__(self):
        # Call parent initialization (gets People PLAY + base PLAY config)
        super().__post_init__()

        # ============================================
        # OBSERVATIONS: Add LiDAR features for play
        # ============================================

        # LiDAR sector distances (required for policy inference)
        self.observations.policy.lidar_sectors = ObsTerm(
            func=mdp.lidar_sector_distances,
            params={
                "num_sectors": self.lidar_obs.num_sectors,
                "max_range": self.lidar_obs.max_range,
            },
        )
