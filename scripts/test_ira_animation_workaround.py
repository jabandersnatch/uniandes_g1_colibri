#!/usr/bin/env python3
"""
TEST 3: IRA Animation Workaround - Manual character movement.

This test bypasses the animation graph entirely and moves characters
manually by parsing commands and updating USD transforms directly.

If this works, we can integrate it into the IRA manager.

Run: python scripts/test_ira_animation_workaround.py --duration 20
"""

import sys
import os
import time
import numpy as np

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from isaaclab.app import AppLauncher
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--duration", type=int, default=20, help="Test duration in seconds")
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_known_args()[0]

app_launcher = AppLauncher(args)
simulation_app = app_launcher.app

import omni
import yaml
from people.ira_people_manager import IRACharacterManager
from pxr import UsdGeom, Gf

print("\n" + "="*70)
print("TEST 3: IRA ANIMATION WORKAROUND (Manual Movement)")
print("="*70 + "\n")

# Load config and initialize IRA
config_path = os.path.join(project_root, "cfg/ira_people_config.yaml")
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

manager = IRACharacterManager(config=config, project_root=project_root, verbose=False)
print("[TEST] Initializing IRA...")
manager.initialize()

# Parse commands
commands = manager.parse_command_file()
print(f"[TEST] ✓ Parsed commands for {len(commands)} characters\n")

# Build waypoint lists
class SimpleWaypointController:
    """Simple waypoint follower for GoTo commands."""
    
    def __init__(self, walk_speed=0.5):
        self.walk_speed = walk_speed
        self.character_data = {}
    
    def add_character(self, char_name, commands):
        """Add a character with its command sequence."""
        waypoints = []
        for cmd in commands:
            if cmd['type'] == 'GoTo' and len(cmd['params']) >= 4:
                x, y, z = float(cmd['params'][0]), float(cmd['params'][1]), float(cmd['params'][2])
                waypoints.append(np.array([x, y, z]))
            # Idle and LookAround just wait in place (simplified)
        
        if waypoints:
            self.character_data[char_name] = {
                'waypoints': waypoints,
                'current_wp': 0,
                'position': waypoints[0].copy(),  # Start at first waypoint
            }
    
    def update(self, dt):
        """Update all character positions."""
        for char_name, data in self.character_data.items():
            waypoints = data['waypoints']
            current_wp = data['current_wp']
            
            if len(waypoints) == 0:
                continue
            
            # Get target waypoint
            target = waypoints[current_wp]
            current_pos = data['position']
            
            # Move toward target
            direction = target - current_pos
            distance = np.linalg.norm(direction)
            
            if distance < 0.1:  # Reached waypoint
                # Move to next waypoint (loop)
                data['current_wp'] = (current_wp + 1) % len(waypoints)
            else:
                # Move toward waypoint
                direction_norm = direction / distance
                step = direction_norm * self.walk_speed * dt
                
                # Don't overshoot
                if np.linalg.norm(step) > distance:
                    data['position'] = target.copy()
                else:
                    data['position'] += step
        
        return self.character_data

# Create controller
controller = SimpleWaypointController(walk_speed=0.5)

# Add characters
for char_name, cmd_list in commands.items():
    controller.add_character(char_name, cmd_list)
    print(f"[TEST] Added {char_name} with {len(cmd_list)} commands")

# Get stage and character prims
stage = omni.usd.get_context().get_stage()
characters_root = stage.GetPrimAtPath("/World/Characters")

character_prims = {}
if characters_root.IsValid():
    for char_prim in characters_root.GetChildren():
        char_name = str(char_prim.GetPath()).split('/')[-1]
        character_prims[char_name] = char_prim

print(f"\n[TEST] Found {len(character_prims)} character prims to control")

# Start simulation
print(f"\n[TEST] Starting manual control for {args.duration} seconds...")
print("[TEST] Characters should now move between waypoints!\n")

timeline = omni.timeline.get_timeline_interface()
timeline.play()

start_time = time.time()
last_update = start_time
frame_count = 0

while simulation_app.is_running():
    current_time = time.time()
    elapsed = current_time - start_time
    
    if elapsed > args.duration:
        break
    
    # Calculate dt
    dt = current_time - last_update
    last_update = current_time
    
    # Update controller
    char_states = controller.update(dt)
    
    # Apply positions to USD prims
    for char_name, state in char_states.items():
        if char_name not in character_prims:
            continue
        
        char_prim = character_prims[char_name]
        new_pos = state['position']
        
        # Update transform
        xform = UsdGeom.Xformable(char_prim)
        ops = xform.GetOrderedXformOps()
        
        for op in ops:
            if op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
                op.Set(Gf.Vec3d(float(new_pos[0]), float(new_pos[1]), float(new_pos[2])))
                break
    
    # Update simulation
    simulation_app.update()
    frame_count += 1
    
    # Progress update every 300 frames
    if frame_count % 300 == 0:
        print(f"[TEST] {elapsed:.1f}s / {args.duration}s - {frame_count} frames")
        for char_name, state in char_states.items():
            pos = state['position']
            wp_idx = state['current_wp']
            print(f"[TEST]   {char_name}: pos=({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}), waypoint={wp_idx}")

timeline.stop()

# Results
print("\n" + "="*70)
print("TEST 3 COMPLETE")
print("="*70)
print(f"\nSimulation ran for {elapsed:.1f}s ({frame_count} frames)")
print("\n✅ If you saw characters moving in the viewport, manual control works!")
print("   This confirms the issue is the animation graph, not the character setup.")
print("\n   Next step: Integrate this manual controller into IRACharacterManager")
print("   by replacing the setup_animation_graph() call with this approach.\n")

simulation_app.close()
