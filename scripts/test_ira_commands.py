#!/usr/bin/env python3
"""
TEST 2: IRA Commands - Test command file parsing and execution.

Tests if commands are being parsed correctly and if the behavior script
can execute them (even without animation graph).

Run: python scripts/test_ira_commands.py --duration 10
"""

import sys
import os
import time

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from isaaclab.app import AppLauncher
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--duration", type=int, default=10, help="Test duration in seconds")
parser.add_argument("--headless", action="store_true")
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_known_args()[0]

app_launcher = AppLauncher(args)
simulation_app = app_launcher.app

import omni
import yaml
from people.ira_people_manager import IRACharacterManager
from pxr import UsdGeom

print("\n" + "="*70)
print("TEST 2: IRA COMMAND PARSING & EXECUTION")
print("="*70 + "\n")

# Load config
config_path = os.path.join(project_root, "cfg/ira_people_config.yaml")
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

# Create and initialize manager
manager = IRACharacterManager(config=config, project_root=project_root, verbose=False)
print("[TEST] Initializing IRA manager...")
manager.initialize()

# Parse commands directly
print("\n[TEST] Parsing command file...")
commands = manager.parse_command_file()

if commands:
    print(f"[TEST] ✓ Commands parsed: {len(commands)} characters")
    for char_name, cmd_list in commands.items():
        print(f"[TEST]   - {char_name}: {len(cmd_list)} commands")
        for i, cmd in enumerate(cmd_list[:3]):  # Show first 3
            print(f"[TEST]      {i+1}. {cmd['type']} {' '.join(cmd['params'])}")
        if len(cmd_list) > 3:
            print(f"[TEST]      ... +{len(cmd_list)-3} more")
else:
    print("[TEST] ✗ No commands parsed!")

# Check character positions
print("\n[TEST] Checking character transforms...")
stage = omni.usd.get_context().get_stage()
characters_root = stage.GetPrimAtPath("/World/Characters")

initial_positions = {}
if characters_root.IsValid():
    for char_prim in characters_root.GetChildren():
        char_path = str(char_prim.GetPath())
        char_name = char_path.split('/')[-1]
        
        # Get initial position
        xform = UsdGeom.Xformable(char_prim)
        ops = xform.GetOrderedXformOps()
        for op in ops:
            if op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
                pos = op.Get()
                initial_positions[char_name] = pos
                print(f"[TEST]   - {char_name} initial position: ({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f})")
                break

# Start timeline and monitor for movement
print(f"\n[TEST] Starting timeline for {args.duration} seconds...")
print("[TEST] Monitoring character positions for movement...")

timeline = omni.timeline.get_timeline_interface()
timeline.play()

start_time = time.time()
frame_count = 0
movements_detected = {char: False for char in initial_positions.keys()}

while simulation_app.is_running():
    elapsed = time.time() - start_time
    if elapsed > args.duration:
        break
    
    # Update simulation
    simulation_app.update()
    frame_count += 1
    
    # Check positions every 60 frames (~ 1 second)
    if frame_count % 60 == 0:
        for char_prim in characters_root.GetChildren():
            char_name = str(char_prim.GetPath()).split('/')[-1]
            if char_name not in initial_positions:
                continue
            
            xform = UsdGeom.Xformable(char_prim)
            ops = xform.GetOrderedXformOps()
            for op in ops:
                if op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
                    pos = op.Get()
                    
                    # Check if position changed significantly (> 0.1m)
                    initial = initial_positions[char_name]
                    dist = ((pos[0]-initial[0])**2 + (pos[1]-initial[1])**2 + (pos[2]-initial[2])**2)**0.5
                    
                    if dist > 0.1 and not movements_detected[char_name]:
                        print(f"[TEST] ✓ {char_name} MOVED! Distance: {dist:.2f}m")
                        movements_detected[char_name] = True
                    break

timeline.stop()

# Results
print("\n" + "="*70)
print("TEST 2 RESULTS")
print("="*70)
print(f"\nSimulation ran for {elapsed:.1f}s ({frame_count} frames)")
print("\nMovement detection:")
for char_name, moved in movements_detected.items():
    status = "✓ MOVED" if moved else "✗ NO MOVEMENT"
    print(f"  {char_name}: {status}")

any_movement = any(movements_detected.values())
if any_movement:
    print("\n✅ SUCCESS: Characters are moving!")
    print("   The IRA system is working correctly.")
else:
    print("\n⚠ WARNING: No character movement detected")
    print("   Possible causes:")
    print("   1. Animation graph API not working (expected)")
    print("   2. Behavior script not executing commands")
    print("   3. Commands not reaching character controller")
    print("\n   Next: Run test_ira_animation_workaround.py for manual control")

print()
simulation_app.close()
