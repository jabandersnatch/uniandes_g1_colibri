#!/usr/bin/env python3
"""Test LiDAR with simple plane terrain to verify it works."""

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

# Create a minimal test config with plane terrain
from isaaclab.envs import ManagerBasedRLEnvCfg, ManagerBasedRLEnv
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.terrains import TerrainImporterCfg
from isaaclab.sensors import RayCasterCfg, patterns
from isaaclab.assets import AssetBaseCfg
from isaaclab.utils import configclass
import isaaclab.sim as sim_utils

from isaaclab_assets import G1_MINIMAL_CFG


@configclass
class TestSceneCfg(InteractiveSceneCfg):
    """Minimal scene with G1 robot and LiDAR."""

    num_envs = 1
    env_spacing = 5.0

    # Simple plane terrain
    terrain = TerrainImporterCfg(
        prim_path="/World/ground",
        terrain_type="plane",
        collision_group=-1,
        physics_material=sim_utils.RigidBodyMaterialCfg(
            static_friction=1.0,
            dynamic_friction=1.0,
        ),
    )

    # G1 Robot
    robot = G1_MINIMAL_CFG.replace(prim_path="{ENV_REGEX_NS}/Robot")

    # LiDAR sensor with debug visualization
    lidar = RayCasterCfg(
        prim_path="{ENV_REGEX_NS}/Robot/torso_link",
        offset=RayCasterCfg.OffsetCfg(pos=(0.0, 0.0, 0.5)),
        pattern_cfg=patterns.LidarPatternCfg(
            channels=8,
            vertical_fov_range=(-10.0, 10.0),
            horizontal_fov_range=(0.0, 360.0),
            horizontal_res=10.0,  # 36 rays per channel = 288 total
        ),
        max_distance=10.0,
        mesh_prim_paths=["/World/ground"],
        debug_vis=True,  # ENABLED - should see rays!
    )

    # Light
    light = AssetBaseCfg(
        prim_path="/World/light",
        spawn=sim_utils.DistantLightCfg(intensity=3000.0),
    )


def main():
    from isaaclab.scene import InteractiveScene

    print("\n" + "=" * 60)
    print("LiDAR Test with Simple Plane Terrain")
    print("=" * 60)
    print("\nYou should see RAYS emanating from the robot's torso.")
    print("Green/colored lines = ray hits")
    print("Red lines = ray missed (max distance)")
    print("\nPress Ctrl+C to exit.\n")

    # Create scene
    scene_cfg = TestSceneCfg()
    scene = InteractiveScene(scene_cfg)

    # Reset scene
    scene.reset()

    # Get lidar sensor
    lidar = scene.sensors["lidar"]
    print(f"LiDAR sensor: {lidar}")
    print(f"Number of rays: {lidar.num_rays}")
    print(f"Debug vis enabled: {lidar.cfg.debug_vis}")

    # Run simulation
    step = 0
    while simulation_app.is_running():
        # Update scene
        scene.write_data_to_sim()
        sim_utils.SimulationContext.instance().step()
        scene.update(dt=1/60)

        if step % 100 == 0:
            # Print LiDAR data
            hits = lidar.data.ray_hits_w
            pos = lidar.data.pos_w
            distances = torch.norm(hits - pos.unsqueeze(1), dim=-1)
            print(f"Step {step}: min_dist={distances.min():.2f}m, max_dist={distances.max():.2f}m")

        step += 1

    scene.close()


if __name__ == "__main__":
    main()
    simulation_app.close()
