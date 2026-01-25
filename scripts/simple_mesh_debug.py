#!/usr/bin/env python3
"""Simple script to find mesh paths in the scene."""

import argparse
from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
args_cli.headless = True  # Force headless

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

# Now imports work
import omni.usd
from pxr import Usd, UsdGeom, UsdPhysics

# Load just the terrain USD without full env
from isaaclab.terrains import TerrainImporter, TerrainImporterCfg
import isaaclab.sim as sim_utils

def main():
    # Create a basic scene
    sim_utils.SimulationContext(sim_utils.SimulationCfg(dt=0.01, device="cuda:0"))

    # Get path to ColibriLab USD
    from pathlib import Path
    assets_dir = Path(__file__).parent.parent / "assets"
    usd_path = assets_dir / "ColibriLab" / "ColibriLab.usd"

    print("\n" + "=" * 60)
    print(f"Loading terrain from: {usd_path}")
    print("=" * 60)

    # Import terrain
    terrain_cfg = TerrainImporterCfg(
        prim_path="/World/ground",
        terrain_type="usd",
        usd_path=str(usd_path),
    )
    terrain = TerrainImporter(terrain_cfg)

    # Step simulation to let things load
    sim = sim_utils.SimulationContext.instance()
    sim.reset()
    for _ in range(10):
        sim.step()

    # Now analyze the stage
    stage = omni.usd.get_context().get_stage()

    print("\n" + "=" * 60)
    print("MESH PRIMS WITH COLLISION (candidates for RayCaster)")
    print("=" * 60)

    collision_meshes = []
    all_meshes = []

    for prim in stage.Traverse():
        prim_type = prim.GetTypeName()
        path = str(prim.GetPath())

        # Skip env-specific paths (would be cloned)
        if "/env_" in path or "/Robot/" in path:
            continue

        if prim_type in ["Mesh", "Cube", "Sphere", "Cylinder", "Capsule", "Cone", "Plane"]:
            all_meshes.append(path)

            # Check for collision API
            has_collision = prim.HasAPI(UsdPhysics.CollisionAPI)
            if has_collision:
                collision_meshes.append(path)
                print(f"  [COLLISION] {path}")

    print(f"\nTotal meshes: {len(all_meshes)}")
    print(f"Meshes with collision: {len(collision_meshes)}")

    print("\n" + "=" * 60)
    print("GROUND/FLOOR PRIMS")
    print("=" * 60)

    for prim in stage.Traverse():
        path = str(prim.GetPath())
        path_lower = path.lower()
        if "/env_" in path or "/Robot/" in path:
            continue
        if "floor" in path_lower or "ground" in path_lower:
            prim_type = prim.GetTypeName()
            has_collision = prim.HasAPI(UsdPhysics.CollisionAPI)
            marker = " [COLLISION]" if has_collision else ""
            print(f"  {path} ({prim_type}){marker}")

    print("\n" + "=" * 60)
    print("RECOMMENDED mesh_prim_paths FOR RAYCASTER:")
    print("=" * 60)

    if collision_meshes:
        # Find common parent
        ground_prim = stage.GetPrimAtPath("/World/ground")
        if ground_prim.IsValid():
            print(f"\n  Option 1 (parent): \"/World/ground\"")

        # Show first few collision meshes
        print(f"\n  Option 2 (specific meshes):")
        for mesh in collision_meshes[:5]:
            print(f"    \"{mesh}\"")
        if len(collision_meshes) > 5:
            print(f"    ... and {len(collision_meshes) - 5} more")
    else:
        print("  No collision meshes found!")
        print("  Try: \"/World/ground\" (may need collision enabled in USD)")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
    simulation_app.close()
