#!/usr/bin/env python3
"""Debug script to check LiDAR sensor attachment."""

import argparse
from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
parser.add_argument("--num_envs", type=int, default=1)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
args_cli.headless = False

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import torch
import gymnasium as gym

# Import task to register
import digital_twin_colibri_g1.tasks.manager_based.digital_twin_colibri_g1  # noqa: F401


def main():
    print("\n" + "=" * 60)
    print("DEBUG: LiDAR Sensor Check")
    print("=" * 60)

    # Create env
    env = gym.make("Isaac-Colibri-G1-SocialNav-v0", num_envs=args_cli.num_envs)
    env.reset()

    # Check scene structure
    print("\n[1] Scene entities:")
    scene = env.unwrapped.scene
    for name in dir(scene):
        if not name.startswith("_"):
            obj = getattr(scene, name, None)
            if obj is not None and hasattr(obj, "cfg"):
                print(f"    - {name}: {type(obj).__name__}")

    # Check sensors specifically
    print("\n[2] Sensors in scene:")
    if hasattr(scene, "sensors"):
        for name, sensor in scene.sensors.items():
            print(f"    - {name}: {type(sensor).__name__}")
            if hasattr(sensor, "cfg"):
                print(f"      prim_path: {sensor.cfg.prim_path}")
                print(f"      debug_vis: {sensor.cfg.debug_vis}")
    else:
        print("    No sensors dict found!")

    # Check if lidar exists
    print("\n[3] LiDAR sensor check:")
    if hasattr(scene, "lidar"):
        lidar = scene.lidar
        print(f"    Found: {lidar}")
        print(f"    Type: {type(lidar)}")
        if hasattr(lidar, "data"):
            print(f"    ray_hits_w shape: {lidar.data.ray_hits_w.shape}")
    else:
        print("    ERROR: scene.lidar not found!")

    # Check robot structure
    print("\n[4] Robot body names:")
    robot = scene["robot"]
    if hasattr(robot, "body_names"):
        print(f"    Body names: {robot.body_names[:10]}...")  # First 10
    if hasattr(robot, "data"):
        print(f"    Root pos shape: {robot.data.root_pos_w.shape}")

    # Check USD stage for sensor prim
    print("\n[5] Checking USD stage for sensor prim:")
    import omni.usd
    stage = omni.usd.get_context().get_stage()

    # Check if torso_link exists
    torso_prim = stage.GetPrimAtPath("/World/envs/env_0/Robot/torso_link")
    if torso_prim.IsValid():
        print(f"    /World/envs/env_0/Robot/torso_link EXISTS")
    else:
        print(f"    /World/envs/env_0/Robot/torso_link NOT FOUND")
        # List children of Robot
        robot_prim = stage.GetPrimAtPath("/World/envs/env_0/Robot")
        if robot_prim.IsValid():
            print("    Robot children:")
            for child in robot_prim.GetChildren()[:10]:
                print(f"      - {child.GetName()}")

    # Run a few steps
    print("\n[6] Running 10 steps...")
    for i in range(10):
        action = torch.zeros(env.num_envs, env.action_space.shape[0], device=env.unwrapped.device)
        env.step(action)

    print("\nDone! Check Isaac Sim window for visualization.")
    print("Press Ctrl+C to exit.\n")

    # Keep running
    while simulation_app.is_running():
        env.step(action)

    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()
