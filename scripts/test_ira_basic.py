#!/usr/bin/env python3
"""
TEST 1: IRA Basic - Minimal character spawning test.

Tests if IRA can spawn characters without the full Isaac Lab environment.
This isolates the spawning logic from the RL environment complexity.

Run: python scripts/test_ira_basic.py
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from isaaclab.app import AppLauncher
import argparse

parser = argparse.ArgumentParser(description="Test IRA basic character spawning")
parser.add_argument("--headless", action="store_true", help="Run headless")
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_known_args()[0]

app_launcher = AppLauncher(args)
simulation_app = app_launcher.app

import omni
import yaml
from people.ira_people_manager import IRACharacterManager

print("\n" + "="*70)
print("TEST 1: IRA BASIC SPAWNING")
print("="*70 + "\n")

# Load config
config_path = os.path.join(project_root, "cfg/ira_people_config.yaml")
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

print("[TEST] ✓ Config loaded")
print(f"[TEST]   - {config['characters']['num_characters']} characters configured")

# Create IRA manager
manager = IRACharacterManager(
    config=config,
    project_root=project_root,
    verbose=True
)

print("\n[TEST] Starting initialization (this will show IRA logs)...")
print("-" * 70)

# Initialize - THIS IS WHERE THE ANIMATION GRAPH ERROR OCCURS
success = manager.initialize()

print("-" * 70)
print()

if success:
    print("[TEST] ✓ Initialization reported SUCCESS")
else:
    print("[TEST] ✗ Initialization reported FAILURE")

# Check stage
stage = omni.usd.get_context().get_stage()
characters_root = stage.GetPrimAtPath("/World/Characters")

if characters_root.IsValid():
    print("[TEST] ✓ /World/Characters prim exists")
    
    # Count spawned characters
    char_count = len([c for c in characters_root.GetChildren()])
    print(f"[TEST] ✓ Found {char_count} character prim(s)")
    
    # List characters
    for child in characters_root.GetChildren():
        print(f"[TEST]   - {child.GetPath()}")
        
        # Check for SkelRoot
        from pxr import UsdSkel
        has_skel = False
        for prim in child.GetDescendants():
            if prim.IsA(UsdSkel.Root):
                has_skel = True
                print(f"[TEST]     ✓ Has SkelRoot: {prim.GetPath()}")
                break
        
        if not has_skel:
            print(f"[TEST]     ✗ No SkelRoot found (animation won't work)")
else:
    print("[TEST] ✗ /World/Characters prim NOT found!")

print("\n" + "="*70)
print("TEST 1 COMPLETE")
print("="*70)
print("\nKEY FINDINGS:")
print("1. Did characters spawn? (check for /World/Characters above)")
print("2. Do they have SkelRoot prims? (needed for animation)")
print("3. Was there an AnimGraphSchema error? (expected, non-fatal)")
print("\nNext: Run test_ira_commands.py to check command parsing")
print()

# Keep window open for a few seconds
import time
time.sleep(3)

simulation_app.close()
