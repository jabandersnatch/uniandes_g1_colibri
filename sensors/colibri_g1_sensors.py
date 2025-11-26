# Copyright (c) 2024, Universidad de los Andes
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""
Sensor management for Colibri G1 digital twin.

This module provides sensor initialization and data access for the G1 humanoid robot,
specifically designed for sim2sim ROS2 integration.

Sensors:
- RTX LiDAR: Mounted on torso_link for 360° scanning
- Camera: RGB/Depth camera for visual perception

Based on: isaac-go2-ros2/go2/go2_sensors.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import omni
import omni.replicator.core as rep
from pxr import Gf

if TYPE_CHECKING:
    from omegaconf import DictConfig


class SensorManager:
    """
    Manages sensors for the Colibri G1 humanoid robot.

    This class handles initialization and configuration of sensors attached to the G1 robot,
    providing annotators for data access in the sim2sim ROS2 bridge.

    Attributes:
        num_envs: Number of parallel environments.
        lidar_annotators: List of LiDAR annotators (one per environment).
        cameras: List of camera instances (one per environment).
    """

    def __init__(self, num_envs: int):
        """
        Initialize the sensor manager.

        Args:
            num_envs: Number of parallel environments to manage sensors for.
        """
        self.num_envs = num_envs
        self.lidar_annotators: list = []
        self.cameras: list = []

    def add_rtx_lidar(self, cfg: DictConfig | None = None) -> list:
        """
        Add RTX LiDAR sensor to G1 robot.

        The LiDAR is mounted on torso_link for stable positioning and good visibility.

        Args:
            cfg: Optional configuration object with sensor.lidar settings.
                 Expected structure:
                 ```yaml
                 sensor:
                   lidar:
                     config: "Hesai_XT32_SD10"  # LiDAR model
                     translation: [0.2, 0.0, 0.4]  # Offset from parent link
                     orientation: [1.0, 0.0, 0.0, 0.0]  # Quaternion (w, x, y, z)
                     parent_link: "torso_link"  # Mount point on robot
                 ```

        Returns:
            List of LiDAR annotators (one per environment) for data retrieval.

        Note:
            The G1 robot uses "{ENV_REGEX_NS}/Robot" prim path pattern in Isaac Lab,
            which resolves to "/World/envs/env_{idx}/Robot" at runtime.
        """
        # Extract configuration with defaults
        if cfg is not None and hasattr(cfg, "sensor") and hasattr(cfg.sensor, "lidar"):
            lidar_cfg = cfg.sensor.lidar
            config_name = getattr(lidar_cfg, "config", "Hesai_XT32_SD10")
            translation = getattr(lidar_cfg, "translation", [0.2, 0.0, 0.4])
            orientation = getattr(lidar_cfg, "orientation", [1.0, 0.0, 0.0, 0.0])
            parent_link = getattr(lidar_cfg, "parent_link", "torso_link")
        else:
            # Default configuration for G1 humanoid
            config_name = "Hesai_XT32_SD10"  # 32-channel LiDAR, good for social navigation
            translation = [0.2, 0.0, 0.4]  # Forward and up from torso
            orientation = [1.0, 0.0, 0.0, 0.0]  # Identity rotation (w, x, y, z)
            parent_link = "torso_link"  # Mount on torso for stability

        self.lidar_annotators = []

        for env_idx in range(self.num_envs):
            # Create RTX LiDAR sensor
            # G1 robot prim path: /World/envs/env_{idx}/Robot/{link_name}
            _, sensor = omni.kit.commands.execute(
                "IsaacSensorCreateRtxLidar",
                path="/lidar",
                parent=f"/World/envs/env_{env_idx}/Robot/{parent_link}",
                config=config_name,
                translation=tuple(translation),
                orientation=Gf.Quatd(*orientation),  # Gf.Quatd expects (w, x, y, z)
            )

            # Create annotator for CPU-side data access
            # This annotator extracts point cloud data from the RTX LiDAR
            annotator = rep.AnnotatorRegistry.get_annotator(
                "RtxSensorCpuIsaacCreateRTXLidarScanBuffer"
            )

            # Create render product for the sensor
            # The [1, 1] resolution is a placeholder - actual resolution is determined by LiDAR config
            hydra_texture = rep.create.render_product(
                sensor.GetPath(), [1, 1], name=f"LiDAR_env_{env_idx}"
            )

            # Attach annotator to the render product
            annotator.attach(hydra_texture.path)
            self.lidar_annotators.append(annotator)

        print(f"[Sensors] LiDAR initialized on {parent_link} for {self.num_envs} env(s)")
        return self.lidar_annotators

    def get_lidar_data(self, env_idx: int = 0) -> dict | None:
        """
        Get LiDAR point cloud data for a specific environment.

        Args:
            env_idx: Environment index to retrieve data from.

        Returns:
            Dictionary containing LiDAR data with keys:
            - "data": Raw point cloud data (N x 3 array of XYZ coordinates)
            - "info": Metadata about the scan
            Returns None if no data available or invalid index.

        Example:
            ```python
            sm = SensorManager(num_envs=1)
            sm.add_rtx_lidar()
            # After simulation step...
            data = sm.get_lidar_data(env_idx=0)
            if data is not None:
                points = data["data"]  # Nx3 array
            ```
        """
        if env_idx >= len(self.lidar_annotators):
            return None

        try:
            data = self.lidar_annotators[env_idx].get_data()
            return data
        except Exception:
            return None

    def add_camera(self, cfg: DictConfig | None = None) -> list:
        """
        Add RGB/Depth camera to G1 robot.

        The camera is mounted on torso_link for forward-facing view,
        similar to Go2's front camera setup.

        Args:
            cfg: Configuration object with sensor.camera settings.
                 Expected structure:
                 ```yaml
                 sensor:
                   camera:
                     width: 640
                     height: 480
                     frequency: 30
                     parent_link: "torso_link"
                     translation: [0.3, 0.0, 0.3]
                     frame_id: "front_cam"
                 ```

        Returns:
            List of camera instances (one per environment).
        """
        from isaacsim.sensors.camera import Camera
        import isaacsim.core.utils.numpy.rotations as rot_utils

        # Extract configuration with defaults
        if cfg is not None and hasattr(cfg, "sensor") and hasattr(cfg.sensor, "camera"):
            cam_cfg = cfg.sensor.camera
            width = getattr(cam_cfg, "width", 640)
            height = getattr(cam_cfg, "height", 480)
            freq = getattr(cam_cfg, "frequency", 30)
            parent_link = getattr(cam_cfg, "parent_link", "torso_link")
            translation = getattr(cam_cfg, "translation", [0.3, 0.0, 0.3])
            frame_id = getattr(cam_cfg, "frame_id", "front_cam")
        else:
            # Default configuration
            width = 640
            height = 480
            freq = 30
            parent_link = "torso_link"
            translation = [0.3, 0.0, 0.3]
            frame_id = "front_cam"

        self.cameras = []

        for env_idx in range(self.num_envs):
            # Create camera prim path
            # Camera is attached to the robot's torso_link
            camera_prim_path = f"/World/envs/env_{env_idx}/Robot/{parent_link}/{frame_id}"

            # Create camera with settings similar to Go2
            camera = Camera(
                prim_path=camera_prim_path,
                translation=np.array(translation),
                frequency=freq,
                resolution=(width, height),
                orientation=rot_utils.euler_angles_to_quats(np.array([0, 0, 0]), degrees=True),
            )

            # Initialize the camera
            camera.initialize()

            # Set focal length for reasonable field of view
            camera.set_focal_length(1.5)

            self.cameras.append(camera)

        print(f"[Sensors] Camera initialized on {parent_link} for {self.num_envs} env(s)")
        print(f"[Sensors] Camera resolution: {width}x{height} @ {freq}Hz")
        return self.cameras

    def get_camera_render_product(self, env_idx: int = 0) -> str | None:
        """
        Get the render product path for a camera.

        Args:
            env_idx: Environment index.

        Returns:
            Render product path string, or None if invalid.
        """
        if env_idx >= len(self.cameras):
            return None

        try:
            return self.cameras[env_idx]._render_product_path
        except Exception:
            return None
