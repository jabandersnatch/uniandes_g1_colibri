#!/usr/bin/env python3
"""Diagnose what's actually in the USD stage."""

import argparse
import sys
from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
AppLauncher.add_app_launcher_args(parser)
args, _ = parser.parse_known_args()

app_launcher = AppLauncher(args)
simulation_app = app_launcher.app

import gymnasium as gym
import omni
from pxr import Usd

# Import task registration
import isaaclab_tasks  # noqa: F401
import digital_twin_colibri_g1.tasks  # noqa: F401

# Load environment config
print("[DIAG] Loading environment config...")
from digital_twin_colibri_g1.tasks.manager_based.digital_twin_colibri_g1.people_env_cfg import DigitalTwinColibriG1PeopleEnvCfg_PLAY
env_cfg = DigitalTwinColibriG1PeopleEnvCfg_PLAY()
env_cfg.scene.num_envs = 1

print("[DIAG] Creating environment...")
env = gym.make("Isaac-Colibri-G1-People-Play-v0", cfg=env_cfg)

print("\n[DIAG] Checking stage contents...")
stage = omni.usd.get_context().get_stage()

if stage is None:
    print("[DIAG] ✗ No stage found!")
else:
    print("[DIAG] ✓ Stage exists")

    # List all prims
    print("\n[DIAG] All prims in stage:")
    for prim in stage.Traverse():
        path = prim.GetPath()
        prim_type = prim.GetTypeName()
        print(f"  {path} (type: {prim_type})")

    # Specifically look for characters
    print("\n[DIAG] Looking for character-related prims:")
    world = stage.GetPrimAtPath("/World")
    if world.IsValid():
        print(f"  /World exists")
        for child in world.GetChildren():
            print(f"    - {child.GetPath()}")
            if child.GetPath().pathString.startswith("/World/Characters"):
                for subchild in child.GetChildren():
                    print(f"      - {subchild.GetPath()}")

print("\n[DIAG] Complete!")
simulation_app.close()
