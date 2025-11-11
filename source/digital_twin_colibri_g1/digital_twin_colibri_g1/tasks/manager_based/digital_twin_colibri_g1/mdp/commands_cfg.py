# Copyright (c) 2022-2025, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Configuration for custom command generators."""

from __future__ import annotations

from dataclasses import MISSING

import isaaclab.sim as sim_utils
from isaaclab.managers.manager_term_cfg import CommandTermCfg
from isaaclab.markers import VisualizationMarkersCfg
from isaaclab.utils import configclass

from .commands import SimpleGoalCommand


@configclass
class SimpleGoalCommandCfg(CommandTermCfg):
    """Configuration for the simple goal position command generator.

    This command generator samples random 2D goal positions at a fixed distance
    from the robot's current position. Goals are resampled periodically.
    """

    class_type: type = SimpleGoalCommand

    asset_name: str = MISSING
    """Name of the robot asset in the scene."""

    resampling_time_range: tuple[float, float] = MISSING
    """Time range for resampling the goal position (min, max) in seconds."""

    @configclass
    class Ranges:
        """Uniform distribution ranges for goal sampling."""

        goal_distance: tuple[float, float] = MISSING
        """Range for goal distance from robot (min, max) in meters."""

    ranges: Ranges = MISSING
    """Range configurations for goal sampling."""

    # Visualization - Large bright green sphere that's easy to see
    goal_visualizer_cfg: VisualizationMarkersCfg = VisualizationMarkersCfg(
        prim_path="/Visuals/Command/goal_position",
        markers={
            "goal_sphere": sim_utils.SphereCfg(
                radius=0.3,  # Large sphere - 30cm radius
                visual_material=sim_utils.PreviewSurfaceCfg(
                    diffuse_color=(0.0, 1.0, 0.0),  # Bright green
                    emissive_color=(0.0, 0.5, 0.0),  # Glowing effect
                    roughness=0.2,
                ),
            ),
        },
    )
    """Configuration for the goal position visualization marker.

    Uses a large bright green glowing sphere for easy visibility in the scene.
    """
