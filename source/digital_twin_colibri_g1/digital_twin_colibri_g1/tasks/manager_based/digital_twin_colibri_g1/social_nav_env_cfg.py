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

import math

from isaaclab.assets import RigidObjectCfg
from isaaclab.managers import EventTermCfg
from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.sensors import RayCasterCfg, patterns
from isaaclab.sim.schemas.schemas_cfg import RigidBodyPropertiesCfg
from isaaclab.sim.spawners.shapes import CylinderCfg
from isaaclab.sim.spawners.materials import PreviewSurfaceCfg
from isaaclab.utils import configclass

from .digital_twin_colibri_g1_env_cfg import (
    DigitalTwinColibriG1EnvCfg,
    DigitalTwinColibriG1EnvCfg_PLAY,
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
    # 8 sectors = 45° per sector (simpler, faster)
    num_sectors: int = 8

    # Maximum range for observation normalization
    max_range: float = 10.0

    # Height filtering for relevant obstacles
    min_height: float = 0.2  # Above ground
    max_height: float = 2.0  # Below typical ceiling


@configclass
class ObstacleManagerCfg:
    """Configuration for moving cylinder obstacles.

    These cylinders serve as dynamic obstacles that the robot must avoid
    while navigating to goals. They move autonomously via random waypoint navigation.

    Cylinders spawn and move within a radius ring around the robot, ensuring
    they are always in the robot's path (not too close, not too far).

    Attributes:
        num_cylinders: Number of cylinders per environment (3-5 recommended).
        cylinder_radius: Cylinder radius in meters (human body width).
        cylinder_height: Cylinder height in meters (human height).
        obstacle_color: RGB color for visibility (orange default).
        spawn_radius_min: Minimum distance from robot center (meters).
        spawn_radius_max: Maximum distance from robot center (meters).
        spawn_height: Height at which cylinders spawn (match floor level).
        move_speed_min: Minimum movement speed in m/s.
        move_speed_max: Maximum movement speed in m/s.
        waypoint_reach_threshold: Distance to consider waypoint reached (meters).
    """

    # Cylinder count and appearance
    num_cylinders: int = 3  # Multiple cylinders for realistic training
    cylinder_radius: float = 0.3  # Meters (human body width)
    cylinder_height: float = 1.8  # Meters (human height)
    obstacle_color: tuple = (1.0, 0.5, 0.0)  # Orange for visibility

    # Radius-based spawning (ring around robot)
    spawn_radius_min: float = 2.0  # Minimum distance from robot center (meters)
    spawn_radius_max: float = 5.0  # Maximum distance from robot center (meters)
    spawn_height: float = 1.2  # Colibri floor height

    # Movement parameters
    move_speed_min: float = 0.3  # m/s (slow walk)
    move_speed_max: float = 0.6  # m/s (normal walk)
    waypoint_reach_threshold: float = 0.5  # Distance to consider reached (m)


@configclass
class SocialNavRewardsCfg:
    """Configuration for social navigation specific rewards.

    These rewards encourage the robot to maintain appropriate distances
    from humans while navigating to goals.

    Thresholds are tuned for gradual learning:
    - Warning level starts further out (2.0m) with gentle penalty
    - Critical level at 1.0m with stronger penalty
    - Smoother gradients (larger std) help policy learn avoidance

    Attributes:
        human_proximity_weight: Penalty for being within proximity threshold.
        human_proximity_threshold: Distance at which penalty starts (meters).
        human_proximity_std: Gaussian std for smooth gradient (meters).
        personal_space_weight: Strong penalty for personal space violation.
        personal_space_threshold: Distance defining personal space (meters).
        personal_space_std: Gaussian std for critical penalty (meters).
        smooth_trajectory_weight: Reward for smooth, non-jerky movements.
    """

    # Warning level - penalize being within 2.0m (gentler, earlier warning)
    human_proximity_weight: float = -0.3  # Gentler than before (-0.5)
    human_proximity_threshold: float = 2.0  # Increased from 1.5m
    human_proximity_std: float = 0.6  # Smoother gradient

    # Critical level - stronger penalty at 1.0m
    personal_space_weight: float = -1.5  # Reduced from -2.0
    personal_space_threshold: float = 1.0  # Increased from 0.8m
    personal_space_std: float = 0.3

    # Smooth trajectory - penalize jerky movements
    smooth_trajectory_weight: float = 0.1


@configclass
class DigitalTwinColibriG1SocialNavEnvCfg(DigitalTwinColibriG1EnvCfg):
    """
    G1 Social Navigation Environment: LiDAR perception + Cylinder obstacle avoidance.

    This configuration builds on the base environment by adding:
    - RayCaster LiDAR sensor for 360° obstacle detection
    - Moving cylinder obstacles (human-sized) with random waypoint navigation
    - LiDAR sector observations for the policy
    - Collision avoidance rewards based on LiDAR proximity

    The robot learns to:
    - Navigate to goals using velocity commands
    - Perceive obstacles via LiDAR sectors (16 angular bins)
    - Maintain appropriate distance from moving cylinders
    - Move smoothly without jerky motions

    Observation Space Extension:
        - lidar_sectors: Minimum distance per angular sector (16 dimensions)

    Reward Additions (Phase 4):
        - obstacle_proximity_warning: Penalty for obstacles within 1.5m
        - obstacle_proximity_critical: Strong penalty for obstacles within 0.8m
        - smooth_trajectory: Reward for smooth movements
    """

    # LiDAR observation configuration
    lidar_obs: LidarObservationCfg = LidarObservationCfg()

    # Obstacle management configuration
    obstacles: ObstacleManagerCfg = ObstacleManagerCfg()

    # Social navigation rewards configuration
    social_rewards: SocialNavRewardsCfg = SocialNavRewardsCfg()

    def __post_init__(self):
        # Call parent initialization (gets base config)
        super().__post_init__()

        # ============================================
        # SCENE: Adjust for LiDAR + Cylinders
        # ============================================

        # Match base locomotion task environment spacing for efficiency
        # Cylinders spawn/move within their radius range without overlap
        self.scene.num_envs = 128

        # Same spacing as base task for compact training
        # Cylinders move in spawn_radius_min/max range (2-5m)
        self.scene.env_spacing = 0.2

        # ============================================
        # SENSORS: Add RayCaster LiDAR for STATIC obstacle detection
        # ============================================

        # RayCaster LiDAR sensor mounted on torso
        #
        # IMPORTANT LIMITATION: RayCaster can ONLY detect STATIC meshes listed in
        # mesh_prim_paths. It CANNOT detect dynamic RigidObjects (like cylinders).
        #
        # Our hybrid observation approach:
        #   1. RayCaster LiDAR → detects static environment (ground, walls)
        #   2. Analytical computation → calculates cylinder distances from positions
        #   3. hybrid_sector_distances() → merges both into unified observation
        #
        # The cylinder obstacles are detected via cylinder_sector_distances() which
        # computes distances analytically from known cylinder positions - this is
        # MORE RELIABLE than ray tracing for dynamic objects anyway!
        self.scene.lidar = RayCasterCfg(
            prim_path="{ENV_REGEX_NS}/Robot/torso_link",
            offset=RayCasterCfg.OffsetCfg(pos=(0.0, 0.0, 0.5)),  # 50cm above torso (chest height)

            pattern_cfg=patterns.LidarPatternCfg(
                channels=4,  # Reduced for performance
                vertical_fov_range=(-5.0, 5.0),  # Narrow vertical range
                horizontal_fov_range=(0.0, 360.0),  # Full 360° coverage
                horizontal_res=15.0,  # 15° horizontal = 24 samples/channel = 96 rays total
            ),

            max_distance=10.0,  # 10m detection range
            drift_range=(0.0, 0.0),  # No sensor drift

            # RayCaster only supports static meshes (cannot detect dynamic RigidObjects like cylinders)
            # Each environment has its own isolated lab (ColibriLab), so use ENV_REGEX_NS
            mesh_prim_paths=["/World/ground"],

            # Disable visualization for training
            debug_vis=False,
        )

        # ============================================
        # OBSTACLES: Spawn moving cylinder obstacles
        # ============================================

        # Spawn multiple cylinders per environment as dynamic obstacles
        # Cylinders are evenly distributed around the robot at startup
        # Initial radius is midpoint of [spawn_radius_min, spawn_radius_max]
        initial_radius = (self.obstacles.spawn_radius_min + self.obstacles.spawn_radius_max) / 2

        for i in range(self.obstacles.num_cylinders):
            # Calculate evenly spaced initial angle for this cylinder
            base_angle = (2 * math.pi * i) / self.obstacles.num_cylinders

            # Initial position in polar coordinates converted to Cartesian
            init_x = initial_radius * math.cos(base_angle)
            init_y = initial_radius * math.sin(base_angle)

            cylinder_cfg = RigidObjectCfg(
                prim_path=f"{{ENV_REGEX_NS}}/Obstacle_{i}",

                spawn=CylinderCfg(
                    radius=self.obstacles.cylinder_radius,
                    height=self.obstacles.cylinder_height,

                    # Visual material
                    visual_material=PreviewSurfaceCfg(
                        diffuse_color=self.obstacles.obstacle_color,
                        metallic=0.2,
                        roughness=0.8,
                    ),

                    # CRITICAL: Dynamic rigid body (kinematic_enabled=False)
                    # This fixes visual update bug in Isaac Sim 4.5/5.0 where kinematic
                    # bodies don't update visually (GitHub: IsaacSim#251, IsaacLab#2069)
                    # High damping keeps movement predictable and prevents being pushed
                    rigid_props=RigidBodyPropertiesCfg(
                        rigid_body_enabled=True,
                        kinematic_enabled=False,  # Dynamic body - visuals update correctly
                        disable_gravity=True,      # Keep at floor height
                        linear_damping=15.0,       # High damping for predictable movement
                        angular_damping=15.0,      # Prevent rotation from collisions
                        max_linear_velocity=1.0,   # Cap max speed
                    ),
                ),

                init_state=RigidObjectCfg.InitialStateCfg(
                    pos=(init_x, init_y, self.obstacles.spawn_height),
                    rot=(1.0, 0.0, 0.0, 0.0),  # Identity quaternion (w, x, y, z)
                ),
            )

            # Register in scene with dynamic name (obstacle_0, obstacle_1, etc.)
            setattr(self.scene, f"obstacle_{i}", cylinder_cfg)

        # ============================================
        # EVENTS: Cylinder movement via waypoint navigation
        # ============================================

        # Update obstacle positions every physics step (50 Hz)
        # This makes cylinders move autonomously toward random waypoints
        self.events.update_obstacles = EventTermCfg(
            func=mdp.update_cylinder_obstacles,
            mode="interval",
            interval_range_s=(0.02, 0.02),  # Every physics step (50 Hz)
            params={"obstacle_cfg_name": "obstacles"},
        )

        # ============================================
        # OBSERVATIONS: Add obstacle perception features
        # ============================================

        # Hybrid sector distances: combines LiDAR (static) + cylinders (dynamic)
        # LiDAR detects ground/walls, analytical computes cylinder distances
        # Both are merged to give comprehensive obstacle awareness
        self.observations.policy.obstacle_sectors = ObsTerm(
            func=mdp.hybrid_sector_distances,
            params={
                "num_sectors": self.lidar_obs.num_sectors,  # 8 sectors (45° each)
                "num_cylinders": self.obstacles.num_cylinders,
                "sensor_name": "lidar",
                "max_range": self.lidar_obs.max_range,
                "cylinder_radius": self.obstacles.cylinder_radius,
            },
        )

        # Direct cylinder distances (useful for learning proximity)
        self.observations.policy.cylinder_distances = ObsTerm(
            func=mdp.cylinder_distances,
            params={
                "num_cylinders": self.obstacles.num_cylinders,
                "max_range": self.lidar_obs.max_range,
            },
        )

        # ============================================
        # REWARDS: Collision avoidance (analytical cylinder distances)
        # ============================================

        # Warning-level proximity penalty (2.0m threshold)
        # Gentle gradient to encourage maintaining distance from cylinders
        self.rewards.obstacle_proximity_warning = RewTerm(
            func=mdp.obstacle_proximity_penalty,
            weight=self.social_rewards.human_proximity_weight,  # -0.3
            params={
                "num_cylinders": self.obstacles.num_cylinders,
                "threshold": self.social_rewards.human_proximity_threshold,  # 2.0m
                "std": self.social_rewards.human_proximity_std,  # 0.6
                "cylinder_radius": self.obstacles.cylinder_radius,
            },
        )

        # Critical proximity penalty (1.0m threshold)
        # Stronger gradient to discourage close encounters
        self.rewards.obstacle_proximity_critical = RewTerm(
            func=mdp.obstacle_proximity_penalty,
            weight=self.social_rewards.personal_space_weight,  # -1.5
            params={
                "num_cylinders": self.obstacles.num_cylinders,
                "threshold": self.social_rewards.personal_space_threshold,  # 1.0m
                "std": self.social_rewards.personal_space_std,  # 0.3
                "cylinder_radius": self.obstacles.cylinder_radius,
            },
        )

        # Reward smooth trajectories
        # Encourages comfortable, predictable robot behavior
        self.rewards.smooth_trajectory = RewTerm(
            func=mdp.smooth_trajectory_reward,
            weight=self.social_rewards.smooth_trajectory_weight,
        )


@configclass
class DigitalTwinColibriG1SocialNavEnvCfg_PLAY(DigitalTwinColibriG1EnvCfg_PLAY):
    """
    Play/visualization configuration for Social Navigation with Cylinders.

    Uses the same observation and reward structure as training,
    but with fewer environments for clearer visualization of obstacle avoidance.
    """

    # LiDAR observation configuration (same as training)
    lidar_obs: LidarObservationCfg = LidarObservationCfg()

    # Obstacle management configuration (same as training)
    obstacles: ObstacleManagerCfg = ObstacleManagerCfg()

    # Social navigation rewards configuration (same as training)
    social_rewards: SocialNavRewardsCfg = SocialNavRewardsCfg()

    def __post_init__(self):
        # Call parent initialization (gets base PLAY config)
        super().__post_init__()

        # ============================================
        # SENSORS: Add RayCaster LiDAR (same as training, but with visualization)
        # ============================================

        # RayCaster LiDAR sensor with debug visualization for PLAY mode
        # NOTE: Only detects static meshes (ground). Cylinders detected analytically.
        self.scene.lidar = RayCasterCfg(
            prim_path="{ENV_REGEX_NS}/Robot/torso_link",
            offset=RayCasterCfg.OffsetCfg(pos=(0.0, 0.0, 0.5)),  # 50cm above torso

            pattern_cfg=patterns.LidarPatternCfg(
                channels=4,  # Same as training
                vertical_fov_range=(-5.0, 5.0),  # Same as training
                horizontal_fov_range=(0.0, 360.0),
                horizontal_res=15.0,  # 96 rays total (same as training)
            ),

            max_distance=10.0,
            drift_range=(0.0, 0.0),

            # RayCaster only supports static meshes (cannot detect dynamic RigidObjects like cylinders)
            # Each environment has its own isolated lab (ColibriLab), so use ENV_REGEX_NS
            mesh_prim_paths=["/World/ground"],

            # Disable visualization to avoid callback errors during initialization
            debug_vis=False,
        )

        # ============================================
        # OBSTACLES: Spawn cylinders (same as training)
        # ============================================

        # Spawn cylinders in play mode (dynamic bodies, same as training)
        # Cylinders are evenly distributed around the robot at startup
        initial_radius = (self.obstacles.spawn_radius_min + self.obstacles.spawn_radius_max) / 2

        for i in range(self.obstacles.num_cylinders):
            # Calculate evenly spaced initial angle for this cylinder
            base_angle = (2 * math.pi * i) / self.obstacles.num_cylinders

            # Initial position in polar coordinates converted to Cartesian
            init_x = initial_radius * math.cos(base_angle)
            init_y = initial_radius * math.sin(base_angle)

            cylinder_cfg = RigidObjectCfg(
                prim_path=f"{{ENV_REGEX_NS}}/Obstacle_{i}",

                spawn=CylinderCfg(
                    radius=self.obstacles.cylinder_radius,
                    height=self.obstacles.cylinder_height,
                    visual_material=PreviewSurfaceCfg(
                        diffuse_color=self.obstacles.obstacle_color,
                        metallic=0.2,
                        roughness=0.8,
                    ),
                    # Dynamic rigid body (NOT kinematic) - fixes visual update bug
                    # Isaac Sim 4.5/5.0 bug: kinematic bodies don't update visually
                    rigid_props=RigidBodyPropertiesCfg(
                        rigid_body_enabled=True,
                        kinematic_enabled=False,  # Must be False for visuals to update
                        disable_gravity=True,
                        linear_damping=15.0,
                        angular_damping=15.0,
                        max_linear_velocity=1.0,
                    ),
                ),

                init_state=RigidObjectCfg.InitialStateCfg(
                    pos=(init_x, init_y, self.obstacles.spawn_height),
                    rot=(1.0, 0.0, 0.0, 0.0),
                ),
            )

            setattr(self.scene, f"obstacle_{i}", cylinder_cfg)

        # ============================================
        # EVENTS: Cylinder movement (same as training)
        # ============================================

        # Update obstacles every step for visualization
        self.events.update_obstacles = EventTermCfg(
            func=mdp.update_cylinder_obstacles,
            mode="interval",
            interval_range_s=(0.02, 0.02),
            params={"obstacle_cfg_name": "obstacles"},
        )

        # ============================================
        # GOAL REACHING THRESHOLD for PLAY mode
        # ============================================

        # Increase goal reaching threshold from 0.3m to 0.5m in PLAY mode
        # This prevents robots from getting stuck near goals in visualization
        self.commands.goal_position.goal_reaching_threshold = 0.5

        # ============================================
        # OBSERVATIONS: Same as training for policy compatibility
        # ============================================

        # Hybrid sector distances: combines LiDAR (static) + cylinders (dynamic)
        self.observations.policy.obstacle_sectors = ObsTerm(
            func=mdp.hybrid_sector_distances,
            params={
                "num_sectors": self.lidar_obs.num_sectors,
                "num_cylinders": self.obstacles.num_cylinders,
                "sensor_name": "lidar",
                "max_range": self.lidar_obs.max_range,
                "cylinder_radius": self.obstacles.cylinder_radius,
            },
        )

        # Direct cylinder distances
        self.observations.policy.cylinder_distances = ObsTerm(
            func=mdp.cylinder_distances,
            params={
                "num_cylinders": self.obstacles.num_cylinders,
                "max_range": self.lidar_obs.max_range,
            },
        )
