#!/usr/bin/env python3
"""Test script to verify cylinder obstacles are created and moving."""

import argparse

from isaaclab.app import AppLauncher

# Create argument parser
parser = argparse.ArgumentParser(description="Test cylinder obstacles in Social Nav environment.")
parser.add_argument("--num_envs", type=int, default=2, help="Number of environments to simulate.")
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()

# Launch Isaac Sim
app_launcher = AppLauncher(args)
simulation_app = app_launcher.app

import gymnasium as gym
import torch
from isaaclab_tasks.utils import parse_env_cfg
from digital_twin_colibri_g1.tasks.manager_based.digital_twin_colibri_g1 import *  # noqa: F401, F403

def main():
    # Parse environment configuration
    env_cfg = parse_env_cfg(
        "Isaac-Colibri-G1-SocialNav-v0",
        device=args.device,
        num_envs=args.num_envs
    )

    # Create environment
    env = gym.make("Isaac-Colibri-G1-SocialNav-v0", cfg=env_cfg)

    # Reset environment
    obs, _ = env.reset()

    # Print cylinder information
    print("\n" + "="*80)
    print("CYLINDER OBSTACLE CHECK")
    print("="*80)

    # Check if cylinders exist
    for i in range(3):  # num_cylinders = 3
        cylinder_name = f"obstacle_{i}"
        try:
            cylinder = env.unwrapped.scene[cylinder_name]
            print(f"\n{cylinder_name}: FOUND")
            print(f"  Type: {type(cylinder)}")
            print(f"  Position (env 0): {cylinder.data.root_pos_w[0]}")
            print(f"  Position (env 1): {cylinder.data.root_pos_w[1]}")
        except KeyError:
            print(f"\n{cylinder_name}: NOT FOUND")

    # Check if waypoints exist
    if hasattr(env.unwrapped, "_obstacle_waypoints"):
        print(f"\nWaypoints initialized: YES")
        print(f"  Shape: {env.unwrapped._obstacle_waypoints.shape}")
        print(f"  Env 0 waypoints:")
        for i in range(3):
            print(f"    Cylinder {i}: {env.unwrapped._obstacle_waypoints[0, i]}")
    else:
        print(f"\nWaypoints initialized: NO")

    # Run a few steps and check if positions change
    print("\n" + "="*80)
    print("MOVEMENT TEST (10 steps)")
    print("="*80)

    # Store initial positions
    initial_pos = {}
    for i in range(3):
        cylinder = env.unwrapped.scene[f"obstacle_{i}"]
        initial_pos[i] = cylinder.data.root_pos_w[0].clone()

    # Print detailed state BEFORE stepping
    print("\n[BEFORE STEP] Cylinder 0 (Env 0):")
    cyl0 = env.unwrapped.scene['obstacle_0']
    print(f"  Position: {cyl0.data.root_pos_w[0]}")
    print(f"  Velocity: {cyl0.data.root_vel_w[0][:3]}")
    if hasattr(env.unwrapped, "_obstacle_waypoints"):
        print(f"  Waypoint: {env.unwrapped._obstacle_waypoints[0, 0]}")
        print(f"  Speed: {env.unwrapped._obstacle_speeds[0, 0]:.3f} m/s")

    # Run 10 steps
    for step in range(10):
        action = torch.zeros(env.action_space.shape, device=env.unwrapped.device)
        env.step(action)

    # Print detailed state AFTER stepping
    print("\n[AFTER 10 STEPS] Cylinder 0 (Env 0):")
    print(f"  Position: {cyl0.data.root_pos_w[0]}")
    print(f"  Velocity: {cyl0.data.root_vel_w[0][:3]}")

    # Check final positions
    print("\n" + "="*80)
    print("POSITION CHANGES SUMMARY")
    print("="*80)
    for i in range(3):
        cylinder = env.unwrapped.scene[f"obstacle_{i}"]
        final_pos = cylinder.data.root_pos_w[0]
        delta = final_pos - initial_pos[i]
        distance_moved = torch.norm(delta).item()
        print(f"  Cylinder {i}: moved {distance_moved:.4f}m (delta: {delta})")

    env.close()
    print("\nTest complete!")

if __name__ == "__main__":
    main()
