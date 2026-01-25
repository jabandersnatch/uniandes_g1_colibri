#!/usr/bin/env python3
# Copyright (c) 2025, Jorge Mendez (Universidad de los Andes)
# SPDX-License-Identifier: BSD-3-Clause

"""Evaluate trained policy and collect behavioral metrics for thesis analysis.

This script loads a trained RSL-RL checkpoint, runs evaluation episodes,
and collects metrics including:
- Goal reach success rate
- Average episode length
- Average distance to goal at termination
- Backwards motion occurrences
- Time to reach goal

Usage:
    python scripts/analysis/evaluate_policy.py \
        --task Isaac-Colibri-G1-SocialNav-Play-v0 \
        --checkpoint logs/rsl_rl/colibri_g1_social_nav/2025-12-01_00-22-15/model_1999.pt \
        --num_episodes 100 \
        --output_dir outputs/analysis/evaluation_metrics
"""

"""Launch Isaac Sim Simulator first."""

import argparse
import sys

from isaaclab.app import AppLauncher

# add argparse arguments
parser = argparse.ArgumentParser(description="Evaluate trained RL policy and collect metrics.")
parser.add_argument("--task", type=str, required=True, help="Name of the task (Play variant).")
parser.add_argument("--checkpoint", type=str, required=True, help="Path to model checkpoint file.")
parser.add_argument("--num_envs", type=int, default=32, help="Number of parallel environments.")
parser.add_argument("--num_episodes", type=int, default=100, help="Total episodes to evaluate.")
parser.add_argument("--output_dir", type=str, default="outputs/analysis/evaluation_metrics", help="Output directory.")
parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility.")
parser.add_argument(
    "--disable_fabric", action="store_true", default=False, help="Disable fabric and use USD I/O operations."
)
# append AppLauncher cli args
AppLauncher.add_app_launcher_args(parser)
# parse the arguments
args_cli, hydra_args = parser.parse_known_args()
# always run headless for evaluation
args_cli.headless = True

# clear out sys.argv for Hydra
sys.argv = [sys.argv[0]] + hydra_args

# launch omniverse app
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""Rest everything follows."""

import json
import os
import time
from datetime import datetime

import gymnasium as gym
import pandas as pd
import torch
from rsl_rl.runners import OnPolicyRunner

from isaaclab.envs import DirectRLEnvCfg, ManagerBasedRLEnvCfg
from isaaclab.utils.assets import retrieve_file_path

from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper

import isaaclab_tasks  # noqa: F401
from isaaclab_tasks.utils.hydra import hydra_task_config

import digital_twin_colibri_g1.tasks  # noqa: F401


class EpisodeMetricsCollector:
    """Collects per-episode metrics during policy evaluation."""

    def __init__(self, num_envs: int, device: str):
        self.num_envs = num_envs
        self.device = device

        # Per-environment tracking - use regular tensors (not inference tensors)
        self._reset_tracking()

        # Completed episode storage
        self.completed_episodes: list[dict] = []

    def _reset_tracking(self):
        """Initialize or reset all tracking tensors."""
        self.episode_lengths = torch.zeros(self.num_envs, device=self.device)
        self.episode_rewards = torch.zeros(self.num_envs, device=self.device)
        self.backward_steps = torch.zeros(self.num_envs, device=self.device)
        self.goal_reached = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
        self.final_distance = torch.zeros(self.num_envs, device=self.device)

    def step(
        self,
        forward_vel: torch.Tensor,
        distance_to_goal: torch.Tensor,
        goal_reached_flag: torch.Tensor,
        rewards: torch.Tensor,
    ):
        """Update metrics for current step.

        Args:
            forward_vel: Forward velocity for each env (positive = forward).
            distance_to_goal: Current distance to goal for each env.
            goal_reached_flag: Whether goal was reached (1.0 or 0.0).
            rewards: Step rewards.
        """
        # Clone tensors to avoid inference mode issues - use non-inplace operations
        self.episode_lengths = self.episode_lengths + 1
        self.episode_rewards = self.episode_rewards + rewards.squeeze().detach()

        # Track backward motion (forward velocity < -0.1 m/s threshold)
        backward_mask = (forward_vel.detach() < -0.1).float()
        self.backward_steps = self.backward_steps + backward_mask

        # Update goal status
        self.goal_reached = self.goal_reached | (goal_reached_flag.detach() > 0.5)
        self.final_distance = distance_to_goal.detach().clone()

    def on_episode_end(self, env_ids: torch.Tensor, dt: float):
        """Record completed episodes and reset tracking.

        Args:
            env_ids: Indices of environments that terminated.
            dt: Simulation timestep for time calculation.
        """
        # Extract data before resetting
        for idx in env_ids.tolist():
            episode_data = {
                "episode_length": int(self.episode_lengths[idx].item()),
                "episode_reward": float(self.episode_rewards[idx].item()),
                "goal_reached": bool(self.goal_reached[idx].item()),
                "final_distance_m": float(self.final_distance[idx].item()),
                "backward_steps": int(self.backward_steps[idx].item()),
                "time_seconds": float(self.episode_lengths[idx].item() * dt),
            }
            self.completed_episodes.append(episode_data)

        # Reset using mask multiplication (non-inplace)
        # Create mask without inplace operations
        reset_mask = torch.ones(self.num_envs, device=self.device)
        zeros = torch.zeros(len(env_ids), device=self.device)
        reset_mask = reset_mask.scatter(0, env_ids.long(), zeros)
        keep_mask = reset_mask.bool()

        self.episode_lengths = self.episode_lengths * reset_mask
        self.episode_rewards = self.episode_rewards * reset_mask
        self.backward_steps = self.backward_steps * reset_mask
        self.goal_reached = self.goal_reached & keep_mask
        self.final_distance = self.final_distance * reset_mask

    def get_summary(self) -> dict:
        """Compute aggregate statistics from completed episodes."""
        if not self.completed_episodes:
            return {}

        df = pd.DataFrame(self.completed_episodes)

        total_episodes = len(df)
        successful = df["goal_reached"].sum()

        summary = {
            "total_episodes": total_episodes,
            "success_rate_percent": float(successful / total_episodes * 100),
            "avg_episode_length_steps": float(df["episode_length"].mean()),
            "std_episode_length_steps": float(df["episode_length"].std()),
            "avg_episode_reward": float(df["episode_reward"].mean()),
            "std_episode_reward": float(df["episode_reward"].std()),
            "avg_final_distance_m": float(df["final_distance_m"].mean()),
            "std_final_distance_m": float(df["final_distance_m"].std()),
            "avg_time_seconds": float(df["time_seconds"].mean()),
            "backward_motion_rate_percent": float(
                (df["backward_steps"] > 0).sum() / total_episodes * 100
            ),
            "avg_backward_steps_per_episode": float(df["backward_steps"].mean()),
        }

        # Add success-only metrics
        successful_df = df[df["goal_reached"]]
        if len(successful_df) > 0:
            summary["avg_time_to_goal_seconds"] = float(successful_df["time_seconds"].mean())
            summary["avg_steps_to_goal"] = float(successful_df["episode_length"].mean())

        return summary


def run_evaluation(env, policy, num_episodes: int, dt: float, device: str) -> EpisodeMetricsCollector:
    """Run evaluation episodes and collect metrics.

    Args:
        env: Wrapped gym environment.
        policy: Trained policy function.
        num_episodes: Target number of episodes to complete.
        dt: Simulation timestep.
        device: Torch device.

    Returns:
        Metrics collector with completed episode data.
    """
    num_envs = env.unwrapped.num_envs
    collector = EpisodeMetricsCollector(num_envs, device)

    # Get environment internals for metric access
    unwrapped_env = env.unwrapped

    # Access goal command manager
    try:
        goal_cmd = unwrapped_env.command_manager.get_term("goal_position")
    except (AttributeError, KeyError):
        print("[WARN] Could not access goal_position command. Using fallback metrics.")
        goal_cmd = None

    # Access robot for velocity
    try:
        robot = unwrapped_env.scene["robot"]
    except (AttributeError, KeyError):
        print("[WARN] Could not access robot. Using fallback metrics.")
        robot = None

    obs = env.get_observations()
    completed = 0
    step_count = 0

    print(f"[INFO] Running evaluation with {num_envs} parallel environments...")
    print(f"[INFO] Target: {num_episodes} episodes")

    start_time = time.time()

    while completed < num_episodes and simulation_app.is_running():
        with torch.inference_mode():
            actions = policy(obs)
            obs, rewards, dones, infos = env.step(actions)

        # Collect per-step metrics
        if goal_cmd is not None:
            distance_to_goal = goal_cmd.metrics["distance_to_goal"]
            goal_reached_flag = goal_cmd.metrics["goal_reached"]
        else:
            distance_to_goal = torch.zeros(num_envs, device=device)
            goal_reached_flag = torch.zeros(num_envs, device=device)

        if robot is not None:
            forward_vel = robot.data.root_lin_vel_b[:, 0]  # x velocity in body frame
        else:
            forward_vel = torch.zeros(num_envs, device=device)

        collector.step(forward_vel, distance_to_goal, goal_reached_flag, rewards)

        # Handle episode terminations
        done_indices = dones.nonzero(as_tuple=False).flatten()
        if len(done_indices) > 0:
            collector.on_episode_end(done_indices, dt)
            completed = len(collector.completed_episodes)

        step_count += 1

        # Progress update every 1000 steps
        if step_count % 1000 == 0:
            elapsed = time.time() - start_time
            print(f"[INFO] Step {step_count}: {completed}/{num_episodes} episodes completed ({elapsed:.1f}s)")

    elapsed = time.time() - start_time
    print(f"[INFO] Evaluation complete: {completed} episodes in {elapsed:.1f}s")

    return collector


@hydra_task_config(args_cli.task, "rsl_rl_cfg_entry_point")
def main(env_cfg: ManagerBasedRLEnvCfg | DirectRLEnvCfg, agent_cfg):
    """Main evaluation function."""
    # Configure environment
    env_cfg.scene.num_envs = args_cli.num_envs
    env_cfg.seed = args_cli.seed
    env_cfg.sim.device = args_cli.device if args_cli.device is not None else env_cfg.sim.device

    # Create environment
    print(f"[INFO] Creating environment: {args_cli.task}")
    env = gym.make(args_cli.task, cfg=env_cfg)
    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)

    # Load checkpoint
    checkpoint_path = retrieve_file_path(args_cli.checkpoint)
    print(f"[INFO] Loading checkpoint: {checkpoint_path}")

    runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
    runner.load(checkpoint_path)
    policy = runner.get_inference_policy(device=env.unwrapped.device)

    # Get timestep
    dt = env.unwrapped.step_dt

    # Run evaluation
    collector = run_evaluation(
        env,
        policy,
        num_episodes=args_cli.num_episodes,
        dt=dt,
        device=env.unwrapped.device,
    )

    # Save results
    os.makedirs(args_cli.output_dir, exist_ok=True)

    # Summary JSON
    summary = collector.get_summary()
    summary["evaluation_config"] = {
        "task": args_cli.task,
        "checkpoint": args_cli.checkpoint,
        "num_envs": args_cli.num_envs,
        "num_episodes": len(collector.completed_episodes),
        "seed": args_cli.seed,
        "timestamp": datetime.now().isoformat(),
    }

    summary_path = os.path.join(args_cli.output_dir, "results.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[INFO] Saved summary: {summary_path}")

    # Per-episode CSV
    episodes_df = pd.DataFrame(collector.completed_episodes)
    episodes_path = os.path.join(args_cli.output_dir, "episodes.csv")
    episodes_df.to_csv(episodes_path, index=False)
    print(f"[INFO] Saved per-episode data: {episodes_path}")

    # Print summary
    print("\n" + "=" * 50)
    print("EVALUATION RESULTS")
    print("=" * 50)
    print(f"Total episodes: {summary['total_episodes']}")
    print(f"Success rate: {summary['success_rate_percent']:.1f}%")
    print(f"Avg episode length: {summary['avg_episode_length_steps']:.1f} steps")
    print(f"Avg episode reward: {summary['avg_episode_reward']:.2f}")
    print(f"Avg final distance: {summary['avg_final_distance_m']:.3f} m")
    print(f"Backward motion rate: {summary['backward_motion_rate_percent']:.1f}%")
    if "avg_time_to_goal_seconds" in summary:
        print(f"Avg time to goal (successful): {summary['avg_time_to_goal_seconds']:.2f} s")
    print("=" * 50)

    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()
