"""Isaac Sim ROS2 bridge for Colibri G1 digital twin.

This script launches Isaac Sim with the trained navigation policy and publishes
robot state via ROS2 topics for sim2sim transfer or monitoring.

Usage:
    python sim2sim/isaac_colibri_g1_ros2.py

References:
    - isaac-go2-ros2/isaac_g1_ros2.py - Main entry point pattern
    - isaac-go2-ros2/go2/go2_ctrl.py - Policy loading example
"""

import argparse
import math
import os
import time

import hydra
import rclpy
import torch
from isaaclab.app import AppLauncher

# Add argparse arguments
parser = argparse.ArgumentParser(
    description="Colibri G1 digital twin with ROS2 integration for sim2sim transfer."
)

# Append AppLauncher CLI args
AppLauncher.add_app_launcher_args(parser)

# Parse arguments
args_cli = parser.parse_args()

# Launch Omniverse app
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""Rest everything follows."""

import carb
import omni
import torch

# Import environment configuration
from digital_twin_colibri_g1.tasks.manager_based.digital_twin_colibri_g1 import (
    DigitalTwinColibriG1EnvCfg_PLAY,
)

# Import ROS2 bridge
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from ros2.colibri_g1_ros2_bridge import RobotDataManager

FILE_PATH = os.path.join(os.path.dirname(__file__), "..", "cfg")


@hydra.main(config_path=FILE_PATH, config_name="ros2_sim", version_base=None)
def run_sim2sim(cfg):
    """Run sim2sim with ROS2 bridge.

    Args:
        cfg: Hydra configuration from ros2_sim.yaml
    """
    print("[INFO] Starting Colibri G1 Sim2Sim ROS2 bridge...")

    # Environment setup (reuse PLAY configuration)
    print("[INFO] Setting up environment...")
    env_cfg = DigitalTwinColibriG1EnvCfg_PLAY()

    # Modify for sim2sim
    env_cfg.scene.num_envs = cfg.num_envs  # Single robot
    env_cfg.episode_length_s = float("inf")  # Continuous operation

    # Create environment
    from isaaclab.envs import ManagerBasedRLEnv

    env = ManagerBasedRLEnv(cfg=env_cfg)
    print(f"[INFO] Environment created with {cfg.num_envs} robot(s)")

    # Load trained policy
    print(f"[INFO] Loading policy from {cfg.policy.checkpoint}")
    policy = load_trained_policy(
        checkpoint_path=cfg.policy.checkpoint,
        env=env,
        device=cfg.policy.device,
    )
    print("[INFO] Policy loaded successfully")

    # Initialize ROS2
    print("[INFO] Initializing ROS2...")
    rclpy.init()
    ros2_bridge = RobotDataManager(env, cfg)
    print("[INFO] ROS2 bridge initialized")

    # Reset environment
    obs, _ = env.reset()
    print("[INFO] Environment reset complete")

    # Simulation loop
    print(f"[INFO] Starting simulation at {cfg.freq} Hz")
    sim_step_dt = float(env_cfg.sim.dt * env_cfg.decimation)

    step_count = 0
    while simulation_app.is_running():
        start_time = time.time()

        with torch.inference_mode():
            # Get policy actions
            actions = policy_inference(policy, obs, cfg.policy.deterministic)

            # Step environment
            step_result = env.step(actions)
            obs = step_result[0]

            # Publish ROS2 data
            ros2_bridge.publish_data()
            rclpy.spin_once(ros2_bridge, timeout_sec=0)

            # Maintain loop rate
            elapsed_time = time.time() - start_time
            if elapsed_time < sim_step_dt:
                sleep_duration = sim_step_dt - elapsed_time
                time.sleep(sleep_duration)

        # Print metrics
        actual_loop_time = time.time() - start_time
        rtf = min(1.0, sim_step_dt / elapsed_time)

        if step_count % 50 == 0:  # Print every 1 second
            print(
                f"\r[INFO] Step: {step_count}, Loop time: {actual_loop_time*1000:.2f}ms, RTF: {rtf:.2f}",
                end="",
                flush=True,
            )
        step_count += 1

    # Cleanup
    print("\n[INFO] Shutting down...")
    ros2_bridge.destroy_node()
    rclpy.shutdown()
    simulation_app.close()
    print("[INFO] Shutdown complete")


def load_trained_policy(checkpoint_path: str, env, device: str = "cuda"):
    """Load trained RSL-RL policy for inference.

    Args:
        checkpoint_path: Path to policy checkpoint (.pt file)
        env: Isaac Lab environment
        device: Device for inference (cuda or cpu)

    Returns:
        Callable: Trained policy for inference
    """
    from rsl_rl.runners import OnPolicyRunner
    from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper

    # Import agent configuration
    from digital_twin_colibri_g1.tasks.manager_based.digital_twin_colibri_g1.agents import (
        ColibriG1PPORunnerCfg,
    )

    # Create agent configuration
    agent_cfg = ColibriG1PPORunnerCfg()
    agent_cfg.device = device

    # Wrap environment for RSL-RL
    wrapped_env = RslRlVecEnvWrapper(env)

    # Create runner (used for loading)
    runner = OnPolicyRunner(wrapped_env, agent_cfg.to_dict(), log_dir=None, device=device)

    # Load checkpoint
    print(f"[INFO] Loading checkpoint: {checkpoint_path}")
    runner.load(checkpoint_path)

    # Get inference policy
    policy = runner.get_inference_policy(device=device)

    print("[INFO] Policy loaded and ready for inference")
    return policy


def policy_inference(policy, obs, deterministic=True):
    """Run policy inference.

    Args:
        policy: Trained policy network
        obs: Observations dictionary
        deterministic: If True, use mean action (no exploration noise)

    Returns:
        torch.Tensor: Actions
    """
    # Get policy observations from dictionary
    obs_tensor = obs["policy"]

    # Call policy directly (returns actions)
    # RSL-RL's get_inference_policy() returns a callable that processes observations
    actions = policy(obs_tensor)

    return actions


if __name__ == "__main__":
    run_sim2sim()


# TODO Phase 6.1: Complete ROS2 bridge integration
# TODO Phase 6.2: Implement policy loading from checkpoint
# TODO Phase 6.3: Add navigation metrics logging
# TODO Phase 6.4: Add sensor support (camera, LiDAR)
