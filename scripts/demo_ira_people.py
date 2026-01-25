#!/usr/bin/env python3

# Copyright (c) 2024, University of Los Andes (MISIS Program)
# Licensed under the BSD 3-Clause License

"""
Demo script: Launch Isaac Sim with animated people using IRA.

This script demonstrates the IRA animated people implementation by:
1. Launching Isaac Sim directly (simpler, more robust)
2. Spawning animated characters using IRA
3. Running simulation so you can see people moving

This is a VISUAL demo - you'll see the characters walk around in real-time!

Usage:
    python scripts/demo_ira_people.py [--duration 30] [--num_chars 2] [--headless]
"""

import argparse
import sys
import os
import time

# Add paths for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
digital_twin_root = os.path.dirname(script_dir)
sys.path.insert(0, os.path.join(digital_twin_root, 'people'))

# Parse arguments
parser = argparse.ArgumentParser(description="Demo IRA animated people")
parser.add_argument("--duration", type=int, default=30, help="Simulation duration in seconds")
parser.add_argument("--num_chars", type=int, default=2, help="Number of characters to spawn")
parser.add_argument("--headless", action="store_true", help="Run without GUI")
args = parser.parse_args()

print("[Demo] Launching Isaac Sim directly...")

# Launch Isaac Sim without AppLauncher (simpler for demos)
import omni
from omni.isaac.kit import SimulationApp

# Create simulation app
print("[Demo] Creating simulation app...")
simulation_app = SimulationApp({"headless": args.headless, "physics_enabled": True})

print("[Demo] ✓ Isaac Sim launched")

# Now we can safely import Isaac modules
import carb
from omni.isaac.core.utils.stage import get_current_stage, create_new_stage
from omni.isaac.core.utils.prims import create_prim
from pxr import Usd, UsdGeom, Gf

# Import custom modules
from ira_people_manager import IRACharacterManager
from navmesh_utils import NavMeshUtility

print("[Demo] ✓ Imports successful")


def create_ground_plane():
    """Create a simple ground plane for the scene."""
    print("[Demo] Creating ground plane...")
    stage = get_current_stage()

    # Create ground prim
    ground_prim = stage.DefinePrim("/World/ground", "Xform")
    ground_mesh = UsdGeom.Mesh.Define(stage, "/World/ground/mesh")

    # Simple plane geometry
    ground_mesh.GetPointsAttr().Set([
        Gf.Vec3f(-5, -5, 0),
        Gf.Vec3f(5, -5, 0),
        Gf.Vec3f(5, 5, 0),
        Gf.Vec3f(-5, 5, 0),
    ])
    ground_mesh.GetFaceVertexCountsAttr().Set([4])
    ground_mesh.GetFaceVertexIndicesAttr().Set([0, 1, 2, 3])

    # Add material to make it visible
    print("[Demo] ✓ Ground plane created")


def create_demo_scene():
    """Create a simple scene for the demo."""
    print("[Demo] Creating demo scene...")
    stage = get_current_stage()

    if stage is None:
        print("[Demo] Creating new stage...")
        from omni.isaac.core.utils.stage import create_new_stage
        create_new_stage()
        stage = get_current_stage()

    # Add lights
    light_prim = stage.DefinePrim("/World/light", "Xform")
    light = UsdGeom.Sphere.Define(stage, "/World/light/sphere")
    light.GetRadiusAttr().Set(0.5)

    print("[Demo] ✓ Scene created")


def main():
    """Run the demo."""
    print("\n" + "=" * 70)
    print("IRA ANIMATED PEOPLE DEMO")
    print("=" * 70 + "\n")

    try:
        # Create scene
        create_demo_scene()
        create_ground_plane()

        # Load configuration
        print("[Demo] Loading IRA configuration...")
        config = {
            'simulation': {'headless': getattr(args, 'headless', False), 'verbose': True},
            'behavior': {'command_file': 'cfg/people_commands.txt', 'playback_speed': 1.0},
            'characters': {
                'num_characters': args.num_chars,
                'assets': [{
                    'name': 'Female_Business_01',
                    'url': 'https://d36m3dsta5ufqu.cloudfront.net/Isaac-Sim-Assets/Isaac/2023.10/Isaac-Sim-4.5.0/Characters/Female_Business_02.usd'
                }],
                'spawn': {
                    'area_min': [-3.0, -3.0],
                    'area_max': [3.0, 3.0],
                    'height': 0.5,
                    'initial_positions': [
                        [1.5, 1.0, 0.5],
                        [2.0, -1.0, 0.5],
                    ][:args.num_chars],
                    'random_seed': 42,
                },
                'animation': {
                    'root_path': '/World/Characters',
                    'enable_physics': False,
                    'capsule_radius': 0.35,
                    'capsule_height': 1.8,
                },
            },
            'navmesh': {
                'enabled': True,
                'create_method': 'auto',
                'auto_generation': {
                    'bounds_min': [-4.0, -4.0, 0.0],
                    'bounds_max': [4.0, 4.0, 0.1],
                    'cell_size': 0.2,
                    'walkable_height': 2.0,
                    'walkable_radius': 0.35,
                    'max_slope': 45.0,
                },
            },
            'extensions': [
                'omni.anim.graph.schema',
                'omni.anim.graph.core',
                'omni.anim.navigation.schema',
                'omni.anim.navigation.core',
                'omni.replicator.agent',
                'omni.kit.scripting',
            ],
            'logging': {'level': 'INFO'},
            'diagnostics': {'enabled': True},
        }

        print("[Demo] ✓ Configuration loaded")

        # Create IRA manager
        print("[Demo] Creating IRA Character Manager...")
        project_root = os.path.dirname(os.path.dirname(script_dir))
        manager = IRACharacterManager(
            config=config,
            project_root=project_root,
            verbose=True,
        )
        print("[Demo] ✓ Manager created")

        # Initialize IRA (spawn characters, setup animations)
        print("[Demo] Initializing IRA (spawning characters)...")
        success = manager.initialize()

        if not success:
            print("[Demo] ✗ IRA initialization failed")
            return False

        print("[Demo] ✓ IRA initialization successful")
        print(f"[Demo] ✓ {manager.get_character_count()} characters spawned")

        # Run simulation
        print(f"\n[Demo] ✓ Running simulation for {args.duration} seconds")
        print("[Demo] ⠿ Watch the viewport - characters should be walking around!")
        print("[Demo] ⠿ Press Ctrl+C or close the window to exit\n")

        # Play timeline
        timeline = omni.timeline.get_timeline_interface()
        timeline.play()

        start_time = time.time()
        frame_count = 0

        # Simulation loop
        while simulation_app.is_running():
            elapsed = time.time() - start_time

            # Update simulation
            simulation_app.update()
            frame_count += 1

            # Print progress every 300 frames
            if frame_count % 300 == 0:
                print(f"[Demo] {elapsed:.1f}s / {args.duration}s - {frame_count} frames")

            # Exit after duration
            if elapsed > args.duration:
                print(f"\n[Demo] ✓ Demo complete! ({frame_count} frames)")
                break

        print("[Demo] ✓ Simulation finished successfully!")
        return True

    except Exception as e:
        print(f"[Demo] ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Close simulator
        simulation_app.close()
        print("[Demo] ✓ Isaac Sim closed")


if __name__ == "__main__":
    print("[Demo] Preparing demo...")

    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n[Demo] ⚠ Demo interrupted by user")
        simulation_app.close()
        sys.exit(0)
    except Exception as e:
        print(f"\n[Demo] ✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
