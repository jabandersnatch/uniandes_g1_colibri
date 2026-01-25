#!/usr/bin/env python3
"""Simple test to verify cylinder movement over time."""

import argparse
from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
parser.add_argument("--num_envs", type=int, default=1)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()

app_launcher = AppLauncher(args)
simulation_app = app_launcher.app

import gymnasium as gym
import torch
from isaaclab_tasks.utils import parse_env_cfg
from digital_twin_colibri_g1.tasks.manager_based.digital_twin_colibri_g1 import *

def main():
    # Create environment
    env_cfg = parse_env_cfg(
        "Isaac-Colibri-G1-SocialNav-Play-v0",
        device=args.device,
        num_envs=args.num_envs
    )
    env = gym.make("Isaac-Colibri-G1-SocialNav-Play-v0", cfg=env_cfg)

    # Reset
    obs, _ = env.reset()

    print("\n" + "="*80)
    print("CYLINDER MOVEMENT TRACKING")
    print("="*80)

    # Track cylinder 0 position over time
    cyl0 = env.unwrapped.scene['obstacle_0']

    initial_pos = cyl0.data.root_pos_w[0][:2].clone()
    print(f"\nInitial position: {initial_pos}")

    # Write results to file (easier to read)
    with open("/tmp/cylinder_test.txt", "w") as f:
        f.write(f"Initial position: {initial_pos}\n")

        # Run for 100 steps, recording position every 10 steps
        for step in range(100):
            action = torch.zeros(env.action_space.shape, device=env.unwrapped.device)
            env.step(action)

            if step % 10 == 0:
                pos = cyl0.data.root_pos_w[0][:2]
                vel = cyl0.data.root_vel_w[0][:2]
                line = f"Step {step:3d}: pos={pos}, vel={vel}\n"
                f.write(line)
                print(line.strip())

        final_pos = cyl0.data.root_pos_w[0][:2]
        distance_moved = torch.norm(final_pos - initial_pos).item()

        f.write(f"\nFinal position: {final_pos}\n")
        f.write(f"Distance moved: {distance_moved:.4f}m\n")

        if distance_moved > 0.001:
            f.write("\n✅ PHYSICS IS WORKING - Cylinders are moving!\n")
            print(f"\n✅ PHYSICS IS WORKING - Moved {distance_moved:.4f}m")
        else:
            f.write("\n❌ PROBLEM - Cylinders are NOT moving\n")
            print(f"\n❌ PROBLEM - No movement detected")

    print(f"\nResults saved to /tmp/cylinder_test.txt")

    env.close()

if __name__ == "__main__":
    main()
    simulation_app.close()
