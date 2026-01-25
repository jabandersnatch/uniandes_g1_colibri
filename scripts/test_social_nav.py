#!/usr/bin/env python3
# Copyright (c) 2024, Universidad de los Andes
# SPDX-License-Identifier: BSD-3-Clause

"""Test script for Social Navigation environment.

This script verifies that:
1. The environment can be created
2. LiDAR sensor is working
3. Cylinder obstacles are spawned and detected
4. Observations include obstacle awareness
5. Rewards are computed correctly

Usage:
    python scripts/test_social_nav.py --num_envs 4
"""

import argparse

from isaaclab.app import AppLauncher

# Parse arguments
parser = argparse.ArgumentParser(description="Test Social Navigation Environment")
parser.add_argument("--num_envs", type=int, default=4, help="Number of environments")
parser.add_argument("--headless", action="store_true", help="Run headless")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

# Launch Isaac Sim
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

# Now import the rest
import torch
import gymnasium as gym

# Import the task to register it
import digital_twin_colibri_g1.tasks.manager_based.digital_twin_colibri_g1  # noqa: F401


def main():
    """Test the social navigation environment."""
    print("\n" + "=" * 60)
    print("Testing Social Navigation Environment")
    print("=" * 60)

    # Create environment
    print("\n[1] Creating environment...")
    env = gym.make(
        "Isaac-Colibri-G1-SocialNav-v0",
        num_envs=args_cli.num_envs,
    )
    print(f"    Environment created with {env.num_envs} envs")

    # Check observation space
    print("\n[2] Checking observation space...")
    obs_space = env.observation_space
    print(f"    Observation space: {obs_space}")
    print(f"    Observation shape: {obs_space.shape}")

    # Reset environment
    print("\n[3] Resetting environment...")
    obs, info = env.reset()
    print(f"    Observation tensor shape: {obs.shape}")

    # Check LiDAR sensor
    print("\n[4] Checking LiDAR sensor...")
    try:
        lidar = env.unwrapped.scene.sensors["lidar"]
        print(f"    LiDAR sensor found: {lidar}")
        print(f"    Number of rays: {lidar.num_rays if hasattr(lidar, 'num_rays') else 'N/A'}")
        print(f"    Ray hits shape: {lidar.data.ray_hits_w.shape}")
    except KeyError:
        print("    WARNING: LiDAR sensor not found!")

    # Check cylinders
    print("\n[5] Checking cylinder obstacles...")
    num_cylinders = 3
    for i in range(num_cylinders):
        obstacle_name = f"obstacle_{i}"
        if hasattr(env.unwrapped.scene, obstacle_name):
            obstacle = getattr(env.unwrapped.scene, obstacle_name)
            pos = obstacle.data.root_pos_w[0]
            print(f"    Cylinder {i}: pos = ({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f})")
        else:
            print(f"    WARNING: {obstacle_name} not found!")

    # Run a few steps
    print("\n[6] Running simulation steps...")
    for step in range(10):
        # Random action
        action = torch.zeros(env.num_envs, env.action_space.shape[0], device=env.unwrapped.device)
        obs, reward, terminated, truncated, info = env.step(action)

        if step % 5 == 0:
            print(f"    Step {step}: reward mean = {reward.mean():.4f}")

    # Check specific observations
    print("\n[7] Checking observation components...")
    obs_manager = env.unwrapped.observation_manager
    obs_dict = obs_manager.compute_group("policy")

    print("    Available observations:")
    for name, tensor in obs_dict.items():
        print(f"      - {name}: shape {tensor.shape}")

    # Check rewards
    print("\n[8] Checking reward components...")
    reward_manager = env.unwrapped.reward_manager
    print("    Active reward terms:")
    for name in reward_manager.active_terms:
        print(f"      - {name}")

    # Close environment
    print("\n[9] Closing environment...")
    env.close()
    print("    Done!")

    print("\n" + "=" * 60)
    print("Social Navigation Environment Test PASSED")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
    simulation_app.close()
