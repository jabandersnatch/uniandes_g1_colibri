# Copyright (c) 2024, Universidad de los Andes
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Custom observation functions for Colibri G1 Digital Twin task.

This module provides obstacle-aware observations for social navigation:

**Static Environment (RayCaster LiDAR)**:
- lidar_height_scan: Height scan relative to robot (for terrain awareness)

**Dynamic Obstacles (Analytical)**:
- cylinder_distances: Direct distances to each cylinder
- cylinder_sector_distances: Angular sectors combining LiDAR + cylinders

Note: Isaac Lab's RayCaster only supports static meshes. For dynamic obstacles
(cylinders), we compute distances analytically and merge with LiDAR data.
"""

import torch
from isaaclab.envs import ManagerBasedRLEnv
from isaaclab.managers import SceneEntityCfg
from isaaclab.sensors import RayCaster


def cylinder_distances(
    env: ManagerBasedRLEnv,
    num_cylinders: int = 1,
    max_range: float = 10.0,
    asset_cfg: SceneEntityCfg = SceneEntityCfg("robot"),
) -> torch.Tensor:
    """Compute distances from robot to each cylinder obstacle.

    Returns the 2D (XY plane) distance from the robot base to each cylinder center.
    Distances are normalized to [0, 1] where 0 = at obstacle, 1 = at max_range.

    Args:
        env: Environment instance
        num_cylinders: Number of cylinder obstacles in scene
        max_range: Maximum range for normalization (meters)
        asset_cfg: Robot asset configuration

    Returns:
        Tensor of shape (num_envs, num_cylinders) with normalized distances.
    """
    # Get robot position
    robot = env.scene[asset_cfg.name]
    robot_pos = robot.data.root_pos_w[:, :2]  # (num_envs, 2) - XY only

    # Initialize distances tensor
    distances = torch.zeros(
        (env.num_envs, num_cylinders),
        device=env.device,
        dtype=torch.float32,
    )

    # Compute distance to each cylinder
    for i in range(num_cylinders):
        obstacle_name = f"obstacle_{i}"
        if hasattr(env.scene, obstacle_name):
            obstacle = env.scene[obstacle_name]
            obstacle_pos = obstacle.data.root_pos_w[:, :2]  # (num_envs, 2)
            dist = torch.norm(robot_pos - obstacle_pos, dim=-1)
            distances[:, i] = dist
        else:
            # Obstacle not in scene, return max range
            distances[:, i] = max_range

    # Normalize and clamp to [0, 1]
    return torch.clamp(distances / max_range, 0.0, 1.0)


def cylinder_sector_distances(
    env: ManagerBasedRLEnv,
    num_sectors: int = 8,
    num_cylinders: int = 1,
    max_range: float = 10.0,
    cylinder_radius: float = 0.3,
    asset_cfg: SceneEntityCfg = SceneEntityCfg("robot"),
) -> torch.Tensor:
    """Project cylinder obstacles into angular sectors around the robot.

    Similar to LiDAR sector observations but computed analytically from known
    cylinder positions. Each sector covers 360°/num_sectors degrees.

    For each sector, returns the minimum distance to any cylinder whose center
    falls within that angular range, minus the cylinder radius.

    Args:
        env: Environment instance
        num_sectors: Number of angular sectors (default 8 = 45° each)
        num_cylinders: Number of cylinder obstacles in scene
        max_range: Maximum detection range (meters)
        cylinder_radius: Radius of cylinders for edge distance
        asset_cfg: Robot asset configuration

    Returns:
        Tensor of shape (num_envs, num_sectors) with normalized min distances.
        0.0 = obstacle touching robot, 1.0 = no obstacle within range.
    """
    # Get robot position and orientation
    robot = env.scene[asset_cfg.name]
    robot_pos = robot.data.root_pos_w[:, :2]  # (num_envs, 2)
    robot_quat = robot.data.root_quat_w  # (num_envs, 4) - (w, x, y, z)

    # Extract yaw angle from quaternion (rotation around Z axis)
    # yaw = atan2(2*(w*z + x*y), 1 - 2*(y^2 + z^2))
    w, x, y, z = robot_quat[:, 0], robot_quat[:, 1], robot_quat[:, 2], robot_quat[:, 3]
    robot_yaw = torch.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))

    # Initialize sector distances to max_range
    sector_distances = torch.full(
        (env.num_envs, num_sectors),
        max_range,
        device=env.device,
        dtype=torch.float32,
    )

    sector_size = 2 * torch.pi / num_sectors

    # Process each cylinder
    for i in range(num_cylinders):
        obstacle_name = f"obstacle_{i}"
        if not hasattr(env.scene, obstacle_name):
            continue

        obstacle = env.scene[obstacle_name]
        obstacle_pos = obstacle.data.root_pos_w[:, :2]  # (num_envs, 2)

        # Vector from robot to obstacle
        delta = obstacle_pos - robot_pos  # (num_envs, 2)

        # Distance to cylinder edge (center distance minus radius)
        dist = torch.norm(delta, dim=-1) - cylinder_radius  # (num_envs,)
        dist = torch.clamp(dist, min=0.0)  # Can't be negative

        # Angle to obstacle in world frame
        angle_world = torch.atan2(delta[:, 1], delta[:, 0])  # (num_envs,)

        # Convert to robot body frame (relative to robot heading)
        angle_body = angle_world - robot_yaw

        # Normalize to [0, 2π]
        angle_body = (angle_body + torch.pi) % (2 * torch.pi)

        # Map to sector index
        sector_idx = (angle_body / sector_size).long() % num_sectors

        # Update sector with minimum distance
        for env_idx in range(env.num_envs):
            s = sector_idx[env_idx].item()
            d = dist[env_idx].item()
            if d < sector_distances[env_idx, s]:
                sector_distances[env_idx, s] = d

    # Normalize to [0, 1]
    return torch.clamp(sector_distances / max_range, 0.0, 1.0)


def lidar_scan_distances(
    env: ManagerBasedRLEnv,
    sensor_name: str = "lidar",
    max_range: float = 10.0,
) -> torch.Tensor:
    """Get raw LiDAR distance measurements.

    Returns the distance from the sensor to each ray hit point. This provides
    terrain/static obstacle awareness from the RayCaster sensor.

    Note: RayCaster only detects static meshes (ground, walls), not dynamic
    RigidObjects like cylinders. Use cylinder_distances for dynamic obstacles.

    Args:
        env: Environment instance
        sensor_name: Name of RayCaster sensor in scene
        max_range: Maximum range for normalization

    Returns:
        Tensor of shape (num_envs, num_rays) with normalized distances [0, 1].
    """
    sensor: RayCaster = env.scene.sensors[sensor_name]

    # Get ray hit points in world frame
    ray_hits_w = sensor.data.ray_hits_w  # (num_envs, num_rays, 3)
    sensor_pos_w = sensor.data.pos_w  # (num_envs, 3)

    # Compute distances
    sensor_pos_expanded = sensor_pos_w.unsqueeze(1)  # (num_envs, 1, 3)
    distances = torch.norm(ray_hits_w - sensor_pos_expanded, dim=-1)  # (num_envs, num_rays)

    # Normalize and clamp
    return torch.clamp(distances / max_range, 0.0, 1.0)


def lidar_sector_min_distances(
    env: ManagerBasedRLEnv,
    num_sectors: int = 8,
    sensor_name: str = "lidar",
    max_range: float = 10.0,
) -> torch.Tensor:
    """Process LiDAR rays into angular sectors with minimum distance.

    Bins LiDAR rays into angular sectors and returns the minimum distance
    detected in each sector. This provides a fixed-size observation for
    static environment awareness (ground, walls, static obstacles).

    Note: For dynamic obstacles (cylinders), use cylinder_sector_distances.
    For a combined observation, use hybrid_sector_distances.

    Args:
        env: Environment instance
        num_sectors: Number of angular sectors (default 8 = 45° each)
        sensor_name: Name of RayCaster sensor in scene
        max_range: Maximum range for normalization

    Returns:
        Tensor of shape (num_envs, num_sectors) with normalized min distances.
    """
    sensor: RayCaster = env.scene.sensors[sensor_name]

    # Get sensor data
    ray_hits_w = sensor.data.ray_hits_w  # (num_envs, num_rays, 3)
    sensor_pos_w = sensor.data.pos_w  # (num_envs, 3)
    sensor_quat_w = sensor.data.quat_w  # (num_envs, 4)

    num_envs = ray_hits_w.shape[0]
    num_rays = ray_hits_w.shape[1]

    # Compute ray distances
    sensor_pos_expanded = sensor_pos_w.unsqueeze(1)  # (num_envs, 1, 3)
    distances = torch.norm(ray_hits_w - sensor_pos_expanded, dim=-1)  # (num_envs, num_rays)

    # Transform to sensor body frame
    # Need to expand quaternion for each ray
    from isaaclab.utils.math import quat_apply_inverse

    ray_hits_relative = ray_hits_w - sensor_pos_expanded  # (num_envs, num_rays, 3)

    # Flatten for batch quaternion operation
    ray_hits_flat = ray_hits_relative.reshape(-1, 3)  # (num_envs * num_rays, 3)
    quat_expanded = sensor_quat_w.unsqueeze(1).expand(-1, num_rays, -1)  # (num_envs, num_rays, 4)
    quat_flat = quat_expanded.reshape(-1, 4)  # (num_envs * num_rays, 4)

    # Apply inverse rotation
    ray_hits_b_flat = quat_apply_inverse(quat_flat, ray_hits_flat)  # (num_envs * num_rays, 3)
    ray_hits_b = ray_hits_b_flat.reshape(num_envs, num_rays, 3)  # (num_envs, num_rays, 3)

    # Compute horizontal angles in body frame
    angles = torch.atan2(ray_hits_b[..., 1], ray_hits_b[..., 0])
    angles = (angles + torch.pi) % (2 * torch.pi)  # [0, 2π]

    # Map to sector indices
    sector_size = 2 * torch.pi / num_sectors
    sector_indices = (angles / sector_size).long() % num_sectors

    # Initialize output
    sector_distances = torch.full(
        (num_envs, num_sectors),
        max_range,
        device=env.device,
        dtype=torch.float32,
    )

    # Find min distance per sector
    for s in range(num_sectors):
        mask = sector_indices == s  # (num_envs, num_rays)
        masked_dist = torch.where(mask, distances, torch.full_like(distances, float("inf")))
        sector_distances[:, s] = masked_dist.min(dim=-1).values

    # Replace inf with max_range
    sector_distances = torch.where(
        torch.isinf(sector_distances),
        torch.full_like(sector_distances, max_range),
        sector_distances,
    )

    return torch.clamp(sector_distances / max_range, 0.0, 1.0)


def hybrid_sector_distances(
    env: ManagerBasedRLEnv,
    num_sectors: int = 8,
    num_cylinders: int = 1,
    sensor_name: str = "lidar",
    max_range: float = 10.0,
    cylinder_radius: float = 0.3,
    asset_cfg: SceneEntityCfg = SceneEntityCfg("robot"),
) -> torch.Tensor:
    """Combine LiDAR and analytical cylinder distances into sector representation.

    This function merges two sources of obstacle information:
    1. LiDAR RayCaster: Detects static environment (ground, walls, static objects)
    2. Analytical: Computes distances to dynamic cylinder obstacles

    For each angular sector, returns the minimum distance from either source.
    This provides comprehensive obstacle awareness for navigation.

    Args:
        env: Environment instance
        num_sectors: Number of angular sectors
        num_cylinders: Number of cylinder obstacles
        sensor_name: Name of RayCaster sensor
        max_range: Maximum detection range
        cylinder_radius: Radius of cylinders
        asset_cfg: Robot asset configuration

    Returns:
        Tensor of shape (num_envs, num_sectors) with normalized min distances.
        Combines both LiDAR (static) and cylinder (dynamic) detections.
    """
    # Get LiDAR sector distances (static environment)
    lidar_sectors = lidar_sector_min_distances(
        env, num_sectors=num_sectors, sensor_name=sensor_name, max_range=max_range
    )

    # Get cylinder sector distances (dynamic obstacles)
    cylinder_sectors = cylinder_sector_distances(
        env,
        num_sectors=num_sectors,
        num_cylinders=num_cylinders,
        max_range=max_range,
        cylinder_radius=cylinder_radius,
        asset_cfg=asset_cfg,
    )

    # Take minimum of both (closest obstacle in each sector)
    # Both are already normalized to [0, 1]
    return torch.minimum(lidar_sectors, cylinder_sectors)
