#!/usr/bin/env python3
"""Debug script to find correct mesh paths for RayCaster.

This script lists all prims in the scene to help identify the correct
mesh_prim_paths for RayCaster configuration.
"""

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

from isaaclab.envs import ManagerBasedRLEnvCfg
import isaaclab.sim as sim_utils
from isaaclab_tasks.utils import parse_env_cfg

# Import task to register
import digital_twin_colibri_g1.tasks.manager_based.digital_twin_colibri_g1  # noqa: F401


def main():
    print("\n" + "=" * 60)
    print("DEBUG: Finding Mesh Paths for RayCaster")
    print("=" * 60)

    # Create env using Isaac Lab pattern
    env_cfg: ManagerBasedRLEnvCfg = parse_env_cfg(
        "Isaac-Colibri-G1-v0",
        num_envs=args_cli.num_envs,
        use_fabric=True,
    )

    from isaaclab.envs import ManagerBasedRLEnv
    env = ManagerBasedRLEnv(cfg=env_cfg)
    env.reset()

    # Get USD stage
    import omni.usd
    stage = omni.usd.get_context().get_stage()

    print("\n[1] All prims under /World:")
    print("-" * 40)

    world_prim = stage.GetPrimAtPath("/World")
    if world_prim.IsValid():
        def print_prims(prim, indent=0):
            prim_type = prim.GetTypeName()
            has_collision = False

            # Check for collision API
            if prim.HasAPI("PhysicsCollisionAPI") or "Collision" in str(prim.GetAppliedSchemas()):
                has_collision = True

            # Check if it's a mesh
            is_mesh = prim_type in ["Mesh", "Cube", "Sphere", "Cylinder", "Capsule", "Cone", "Plane"]

            marker = ""
            if is_mesh:
                marker = " [MESH]"
            if has_collision:
                marker += " [COLLISION]"

            print(f"{'  ' * indent}{prim.GetPath()} ({prim_type}){marker}")

            for child in prim.GetChildren():
                print_prims(child, indent + 1)

        print_prims(world_prim)

    print("\n[2] Specifically checking /World/ground:")
    print("-" * 40)

    ground_prim = stage.GetPrimAtPath("/World/ground")
    if ground_prim.IsValid():
        print(f"  Path: {ground_prim.GetPath()}")
        print(f"  Type: {ground_prim.GetTypeName()}")
        print(f"  Schemas: {ground_prim.GetAppliedSchemas()}")

        # List children
        print(f"\n  Children of /World/ground:")
        for child in ground_prim.GetAllChildren():
            child_type = child.GetTypeName()
            print(f"    - {child.GetPath()} ({child_type})")
    else:
        print("  /World/ground NOT FOUND!")

    print("\n[3] Finding all Mesh prims with collision:")
    print("-" * 40)

    mesh_paths = []
    for prim in stage.Traverse():
        prim_type = prim.GetTypeName()
        if prim_type in ["Mesh", "Cube", "Sphere", "Cylinder", "Capsule", "Cone", "Plane"]:
            # Check for collision
            has_collision = prim.HasAPI("PhysicsCollisionAPI")
            path_str = str(prim.GetPath())

            # Skip robot and obstacle meshes
            if "/Robot/" in path_str or "/Obstacle_" in path_str:
                continue

            print(f"  {prim.GetPath()} (collision={has_collision})")
            if has_collision:
                mesh_paths.append(path_str)

    print("\n[4] Recommended mesh_prim_paths for RayCaster:")
    print("-" * 40)
    if mesh_paths:
        for path in mesh_paths[:5]:  # Show top 5
            print(f"  \"{path}\"")
    else:
        print("  No collision meshes found! Try these paths:")
        print("  \"/World/ground\"")
        print("  \"/World/ground/geometry\"")
        print("  \"/World/defaultGroundPlane\"")

    print("\n[5] Checking terrain importer result:")
    print("-" * 40)
    scene = env.scene
    if hasattr(scene, "terrain"):
        terrain = scene.terrain
        print(f"  Terrain type: {type(terrain)}")
        if hasattr(terrain, "cfg"):
            print(f"  Terrain prim_path: {terrain.cfg.prim_path}")
        if hasattr(terrain, "meshes"):
            print(f"  Terrain meshes: {terrain.meshes}")

    print("\n" + "=" * 60)
    print("Use one of the mesh paths above in your RayCasterCfg:")
    print("  mesh_prim_paths=[\"<path_from_above>\"]")
    print("=" * 60)

    # Keep running briefly
    print("\nPress Ctrl+C to exit.\n")
    for _ in range(100):
        action = torch.zeros(env.num_envs, env.action_manager.total_action_dim, device=env.device)
        env.step(action)

    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()
