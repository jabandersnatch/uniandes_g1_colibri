# Copyright (c) 2024, Universidad de los Andes
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Custom event functions for Colibri G1 Digital Twin task."""

import math

import torch
from isaaclab.envs import ManagerBasedEnv


def update_cylinder_obstacles(
    env: ManagerBasedEnv,
    env_ids: torch.Tensor,
    obstacle_cfg_name: str = "obstacles",
):
    """Update cylinder positions using random waypoint navigation.

    Each cylinder moves toward its assigned waypoint at a constant speed.
    When a waypoint is reached, a new random waypoint is sampled within
    the spawn area bounds.

    This function is called as an interval event (via EventTermCfg) to update
    obstacle positions every physics step for ALL environments.

    Args:
        env: Environment instance
        env_ids: Environment indices to update (for interval events, this is ALL active envs)
        obstacle_cfg_name: Name of obstacle config attribute (default: "obstacles")
    """
    # Get obstacle configuration from environment
    cfg = getattr(env.cfg, obstacle_cfg_name)

    # Initialize waypoint buffers if first call
    # These persist across environment resets
    if not hasattr(env, "_obstacle_waypoints"):
        # Waypoints for each cylinder in each environment: (num_envs, num_cylinders, 3)
        env._obstacle_waypoints = torch.zeros(
            (env.num_envs, cfg.num_cylinders, 3),
            device=env.device,
            dtype=torch.float32,
        )

        # Random speeds for each cylinder: (num_envs, num_cylinders)
        # Each cylinder gets a random speed between min and max
        env._obstacle_speeds = (
            torch.rand((env.num_envs, cfg.num_cylinders), device=env.device)
            * (cfg.move_speed_max - cfg.move_speed_min)
            + cfg.move_speed_min
        )

        # Sample initial waypoints for all environments
        _sample_waypoints(env, cfg, torch.arange(env.num_envs, device=env.device))

    # Get timestep for velocity calculation
    dt = env.step_dt

    # Update each cylinder type
    for i in range(cfg.num_cylinders):
        # Get obstacle asset
        obstacle = env.scene[f"obstacle_{i}"]

        # Current positions for specified environments: (num_reset_envs, 3)
        pos = obstacle.data.root_pos_w[env_ids].clone()

        # Distance to waypoint (2D in XY plane)
        dist = torch.norm(
            pos[:, :2] - env._obstacle_waypoints[env_ids, i, :2],
            dim=-1,
        )

        # Check if waypoint reached
        reached_mask = dist < cfg.waypoint_reach_threshold

        # Resample waypoints for cylinders that reached their target
        if reached_mask.any():
            reached_env_ids = env_ids[reached_mask]
            _sample_waypoints(env, cfg, reached_env_ids, cylinder_idx=i)

        # Compute direction to waypoint (normalized)
        direction = env._obstacle_waypoints[env_ids, i, :2] - pos[:, :2]
        direction_norm = torch.norm(direction, dim=-1, keepdim=True).clamp(min=1e-6)
        direction = direction / direction_norm

        # Update position: current_pos + direction * speed * dt
        speed = env._obstacle_speeds[env_ids, i].unsqueeze(1)
        pos[:, :2] += direction * speed * dt
        pos[:, 2] = cfg.spawn_height  # Keep at floor height

        # Compute velocity for physics simulation
        velocity_2d = direction * speed  # (num_envs, 2)
        velocity_3d = torch.zeros((len(env_ids), 3), device=env.device, dtype=torch.float32)
        velocity_3d[:, :2] = velocity_2d  # Set XY velocity, Z velocity = 0

        # Write updated position and velocity to simulation
        root_state = obstacle.data.root_state_w[env_ids].clone()
        root_state[:, :3] = pos  # Update position (xyz)
        # Orientation remains identity quaternion (no rotation)
        obstacle.write_root_pose_to_sim(root_state[:, :7], env_ids=env_ids)

        # Write velocity (linear + angular, 6 DOF)
        velocity_full = torch.zeros((len(env_ids), 6), device=env.device, dtype=torch.float32)
        velocity_full[:, :3] = velocity_3d  # Linear velocity (x, y, z)
        # Angular velocity remains zero (no rotation)
        obstacle.write_root_velocity_to_sim(velocity_full, env_ids=env_ids)

        # Reset internal buffers after writing new state (Isaac Lab pattern)
        # This clears cached data and forces the object to sync with new physics state
        obstacle.reset(env_ids)

        # Force physics synchronization
        obstacle.write_data_to_sim()


def _sample_waypoints(
    env: ManagerBasedEnv,
    cfg,
    env_ids: torch.Tensor,
    cylinder_idx: int = None,
):
    """Sample random waypoints in a radius ring around each environment's origin.

    Waypoints are sampled in polar coordinates (radius, angle) and converted
    to Cartesian (x, y). This ensures cylinders always move within a ring
    around the robot, staying relevant for obstacle avoidance training.

    Args:
        env: Environment instance
        cfg: Obstacle configuration (must have spawn_radius_min/max)
        env_ids: Environment indices to sample waypoints for
        cylinder_idx: Specific cylinder index, or None for all cylinders
    """
    if cylinder_idx is None:
        # Sample for all cylinders in given environments
        for i in range(cfg.num_cylinders):
            _sample_waypoints(env, cfg, env_ids, cylinder_idx=i)
        return

    # Sample waypoint for specific cylinder in specified environments
    num_envs = len(env_ids)

    # Sample radius (distance from env origin) uniformly in [min, max] range
    radius = (
        torch.rand(num_envs, device=env.device)
        * (cfg.spawn_radius_max - cfg.spawn_radius_min)
        + cfg.spawn_radius_min
    )

    # Sample angle uniformly around the full circle [0, 2π]
    angle = torch.rand(num_envs, device=env.device) * 2 * math.pi

    # Convert polar coordinates to Cartesian (relative to env origin at 0,0)
    env._obstacle_waypoints[env_ids, cylinder_idx, 0] = radius * torch.cos(angle)
    env._obstacle_waypoints[env_ids, cylinder_idx, 1] = radius * torch.sin(angle)

    # Z coordinate at floor height
    env._obstacle_waypoints[env_ids, cylinder_idx, 2] = cfg.spawn_height
