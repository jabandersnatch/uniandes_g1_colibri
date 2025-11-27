# Copyright (c) 2024, Universidad de los Andes
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""
Play script for G1 with animated people.

This script runs a trained G1 policy in an environment with animated human
characters walking around. The characters serve as dynamic obstacles that
the robot must navigate around.

Usage:
    python scripts/rsl_rl/play_people.py --task=Isaac-Colibri-G1-People-Play-v0
    python scripts/rsl_rl/play_people.py --task=Isaac-Colibri-G1-People-Play-v0 --num_envs 4
    python scripts/rsl_rl/play_people.py --checkpoint /path/to/model.pt

Note:
    This script is based on the standard play.py but adds people spawning
    after environment creation.
"""

"""Launch Isaac Sim Simulator first."""

import argparse
import sys

from isaaclab.app import AppLauncher

# local imports
import cli_args  # isort: skip

# add argparse arguments
parser = argparse.ArgumentParser(description="Play G1 policy with animated people.")
parser.add_argument("--video", action="store_true", default=False, help="Record videos during playback.")
parser.add_argument("--video_length", type=int, default=200, help="Length of the recorded video (in steps).")
parser.add_argument(
    "--disable_fabric", action="store_true", default=False, help="Disable fabric and use USD I/O operations."
)
parser.add_argument("--num_envs", type=int, default=None, help="Number of environments to simulate.")
parser.add_argument(
    "--task", type=str, default="Isaac-Colibri-G1-People-Play-v0", help="Name of the task."
)
parser.add_argument(
    "--agent", type=str, default="rsl_rl_cfg_entry_point", help="Name of the RL agent configuration entry point."
)
parser.add_argument("--seed", type=int, default=None, help="Seed used for the environment")
parser.add_argument(
    "--use_pretrained_checkpoint",
    action="store_true",
    help="Use the pre-trained checkpoint from Nucleus.",
)
parser.add_argument("--real-time", action="store_true", default=False, help="Run in real-time, if possible.")
parser.add_argument(
    "--people_backend",
    type=str,
    default="legacy",
    choices=["legacy", "ira"],
    help="Backend for animated people: 'legacy' (omni.anim.people) or 'ira' (isaacsim.replicator.agent)",
)
parser.add_argument(
    "--ira_config",
    type=str,
    default="cfg/ira_people_config.yaml",
    help="Path to IRA config YAML file (if using IRA backend)",
)
# append RSL-RL cli arguments
cli_args.add_rsl_rl_args(parser)
# append AppLauncher cli args
AppLauncher.add_app_launcher_args(parser)
# parse the arguments
args_cli, hydra_args = parser.parse_known_args()
# always enable cameras to record video
if args_cli.video:
    args_cli.enable_cameras = True

# clear out sys.argv for Hydra
sys.argv = [sys.argv[0]] + hydra_args

# launch omniverse app
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""Rest everything follows."""

import gymnasium as gym
import omni.usd
import omni.kit.app
import os
import time
import torch

from rsl_rl.runners import OnPolicyRunner

from isaaclab.envs import ManagerBasedRLEnvCfg
from isaaclab.utils.assets import retrieve_file_path
from isaaclab.utils.dict import print_dict

from isaaclab_rl.rsl_rl import RslRlBaseRunnerCfg, RslRlVecEnvWrapper

import isaaclab_tasks  # noqa: F401
from isaaclab_tasks.utils import get_checkpoint_path
from isaaclab_tasks.utils.hydra import hydra_task_config

# Import digital twin tasks
import digital_twin_colibri_g1.tasks  # noqa: F401

# Import people modules
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from people import PeopleSceneManager, IRACharacterManager

# Try to import YAML support
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

# ============================================
# ENABLE ANIMATION EXTENSIONS EARLY
# This MUST happen before the gym environment is created
# See: https://forums.developer.nvidia.com/t/isaac-sim-people-simulation-broken-in-4-1-0/301378
# ============================================
def enable_animation_extensions():
    """Enable animation extensions required for omni.anim.people before environment creation."""
    ext_manager = omni.kit.app.get_app().get_extension_manager()

    # Extensions must be enabled in this order for proper schema registration
    extensions = [
        "omni.anim.graph.schema",      # Schema must be first
        "omni.anim.navigation.schema", # Navigation schema
        "omni.anim.graph.core",        # Core animation graph
        "omni.anim.graph.bundle",      # Animation bundle
        "omni.anim.navigation.bundle", # Navigation bundle
        "omni.anim.people",            # People extension
        "omni.kit.scripting",          # Scripting for behavior scripts
    ]

    print("[People] Enabling animation extensions early (before environment creation)...")
    for ext in extensions:
        try:
            ext_manager.set_extension_enabled_immediate(ext, True)
            print(f"[People] Pre-enabled: {ext}")
        except Exception as e:
            print(f"[People] Warning: Could not pre-enable {ext}: {e}")

    # Update app to ensure extensions are fully loaded
    simulation_app.update()
    print("[People] Animation extensions pre-enabled successfully")

# Enable extensions immediately
enable_animation_extensions()


@hydra_task_config(args_cli.task, args_cli.agent)
def main(env_cfg: ManagerBasedRLEnvCfg, agent_cfg: RslRlBaseRunnerCfg):
    """Play with RSL-RL agent and animated people."""
    # grab task name for checkpoint path
    task_name = args_cli.task.split(":")[-1]
    train_task_name = task_name.replace("-Play", "").replace("-People", "")

    # override configurations with non-hydra CLI arguments
    agent_cfg: RslRlBaseRunnerCfg = cli_args.update_rsl_rl_cfg(agent_cfg, args_cli)
    env_cfg.scene.num_envs = args_cli.num_envs if args_cli.num_envs is not None else env_cfg.scene.num_envs

    # set the environment seed
    env_cfg.seed = agent_cfg.seed
    env_cfg.sim.device = args_cli.device if args_cli.device is not None else env_cfg.sim.device

    # specify directory for logging experiments
    log_root_path = os.path.join("logs", "rsl_rl", agent_cfg.experiment_name)
    log_root_path = os.path.abspath(log_root_path)
    print(f"[INFO] Loading experiment from directory: {log_root_path}")

    if args_cli.checkpoint:
        resume_path = retrieve_file_path(args_cli.checkpoint)
    else:
        resume_path = get_checkpoint_path(log_root_path, agent_cfg.load_run, agent_cfg.load_checkpoint)

    log_dir = os.path.dirname(resume_path)
    env_cfg.log_dir = log_dir

    # create isaac environment
    print("[INFO] Creating environment with people configuration...")
    env = gym.make(args_cli.task, cfg=env_cfg, render_mode="rgb_array" if args_cli.video else None)

    # ============================================
    # ADD ANIMATED PEOPLE TO SCENE
    # ============================================
    print("\n[INFO] ========== PEOPLE SCENE INITIALIZATION ==========")
    stage = omni.usd.get_context().get_stage()
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Initialize people based on selected backend
    if args_cli.people_backend == "ira":
        # Use new IRA backend
        print(f"[INFO] Using IRA backend for animated people")
        print(f"[INFO] Loading config from: {args_cli.ira_config}")

        # Load IRA configuration
        ira_config_path = os.path.join(project_root, args_cli.ira_config)
        if os.path.exists(ira_config_path) and YAML_AVAILABLE:
            with open(ira_config_path, 'r') as f:
                ira_config = yaml.safe_load(f)
            print(f"[INFO] ✓ Loaded IRA config from {ira_config_path}")
        else:
            if not YAML_AVAILABLE:
                print(f"[INFO] ⚠ PyYAML not available - using fallback config")
            else:
                print(f"[INFO] ⚠ Config file not found - using fallback config")
            ira_config = None

        # Create IRA manager
        people_manager = IRACharacterManager(
            config=ira_config,
            project_root=project_root,
            verbose=True,
        )
        success = people_manager.initialize()

        if success:
            num_chars = people_manager.get_character_count()
            print(f"[INFO] ✓ IRA initialization successful ({num_chars} characters)")
        else:
            print(f"[INFO] ✗ IRA initialization failed - continuing with empty scene")

    else:
        # Use legacy PeopleSceneManager backend
        print(f"[INFO] Using legacy backend for animated people (omni.anim.people)")

        # Get people configuration - use env_cfg.people if available, otherwise create default
        if hasattr(env_cfg, 'people'):
            people_cfg = env_cfg.people
            print("[INFO] Using people configuration from environment")
        else:
            # Import and create default people configuration
            from digital_twin_colibri_g1.tasks.manager_based.digital_twin_colibri_g1.people_env_cfg import PeopleManagerCfg
            people_cfg = PeopleManagerCfg()
            print("[INFO] Using default people configuration")

        # Create people scene manager and add characters to world
        # Characters are added as GLOBAL assets (not per-environment)
        people_manager = PeopleSceneManager(people_cfg, project_root)
        people_manager.initialize(stage)
        print(f"[INFO] ✓ Legacy initialization complete")

    print("[INFO] ===================================================\n")

    # wrap for video recording
    if args_cli.video:
        video_kwargs = {
            "video_folder": os.path.join(log_dir, "videos", "play_people"),
            "step_trigger": lambda step: step == 0,
            "video_length": args_cli.video_length,
            "disable_logger": True,
        }
        print("[INFO] Recording videos during playback.")
        print_dict(video_kwargs, nesting=4)
        env = gym.wrappers.RecordVideo(env, **video_kwargs)

    # wrap around environment for rsl-rl
    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)

    print(f"[INFO]: Loading model checkpoint from: {resume_path}")
    # load previously trained model
    runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
    runner.load(resume_path)

    # obtain the trained policy for inference
    policy = runner.get_inference_policy(device=env.unwrapped.device)

    dt = env.unwrapped.step_dt

    # reset environment
    obs = env.get_observations()
    timestep = 0

    print("[INFO] Starting simulation with animated people...")
    print("[INFO] Press Ctrl+C or close the window to exit")

    # simulate environment
    while simulation_app.is_running():
        start_time = time.time()
        # run everything in inference mode
        with torch.inference_mode():
            # agent stepping
            actions = policy(obs)
            # env stepping
            obs, _, _, _ = env.step(actions)

        if args_cli.video:
            timestep += 1
            # Exit the play loop after recording one video
            if timestep == args_cli.video_length:
                break

        # time delay for real-time evaluation
        sleep_time = dt - (time.time() - start_time)
        if args_cli.real_time and sleep_time > 0:
            time.sleep(sleep_time)

    # close the simulator
    env.close()


if __name__ == "__main__":
    # run the main function
    main()
    # close sim app
    simulation_app.close()
