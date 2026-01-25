# Copyright (c) 2024, Universidad de los Andes
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""
G1 Environment with Animated People for Colibri Digital Twin.

This module provides environment configurations that include animated human
characters walking in the environment. The people serve as dynamic obstacles
for training social navigation policies.

Task Variants:
    - Isaac-Colibri-G1-People-v0: Training environment with animated people
    - Isaac-Colibri-G1-People-Play-v0: Visualization environment with people
"""

from __future__ import annotations

from isaaclab.utils import configclass

from .digital_twin_colibri_g1_env_cfg import (
    DigitalTwinColibriG1EnvCfg,
    DigitalTwinColibriG1EnvCfg_PLAY,
)


@configclass
class PeopleManagerCfg:
    """Configuration for animated people in the environment.

    This configuration controls the spawning and behavior of animated
    human characters using Isaac Sim's omni.anim.people extension.

    Attributes:
        num_characters: Number of animated characters to spawn.
        command_file: Path to the command file defining character behaviors.
        character_assets: List of USD paths to character assets.
        spawn_area_min: Minimum X, Y coordinates for spawn area.
        spawn_area_max: Maximum X, Y coordinates for spawn area.
        spawn_height: Height at which to spawn characters (match floor level).
        navmesh_enabled: Whether to use NavMesh for character navigation.
        dynamic_avoidance: Whether characters avoid each other dynamically.
        loop_commands: Whether characters loop through their command sequence.
    """

    # Number of characters to spawn
    num_characters: int = 2

    # Path to command file (relative to project root)
    command_file: str = "cfg/people_commands.txt"

    # Character assets - VERIFIED WORKING URLs (tested with curl HTTP 200)
    # CRITICAL: Cloud asset paths use pattern: /Isaac/4.0/Isaac/People/Characters/[name]/[name].usd
    # Available characters:
    #   - female_adult_police_02 (Police Woman)
    #   - male_adult_police_04 (Police Man)
    character_assets: tuple = (
        "/Isaac/4.0/Isaac/People/Characters/female_adult_police_02/female_adult_police_02.usd",
        "/Isaac/4.0/Isaac/People/Characters/original_male_adult_police_04/male_adult_police_04.usd",
    )

    # Spawn configuration
    # Area within which characters are randomly placed
    # Condensed area to avoid walls and stay near the robot
    # Robot spawns at origin (0, 0), so we spawn people 1-2m away
    spawn_area_min: tuple = (1.0, -1.5)  # In front of robot, to the side
    spawn_area_max: tuple = (2.5, 1.5)   # Condensed 1.5m x 3m area
    spawn_height: float = 1.2  # Colibri Lab floor height

    # Navigation settings
    navmesh_enabled: bool = False  # Disable NavMesh (use fixed waypoints instead)
    dynamic_avoidance: bool = True  # Characters avoid each other

    # Animation settings
    loop_commands: bool = True  # Characters repeat their command sequence


@configclass
class DigitalTwinColibriG1PeopleEnvCfg(DigitalTwinColibriG1EnvCfg):
    """
    G1 environment configuration with animated people for TRAINING.

    This configuration extends the base G1 environment by adding animated
    human characters that serve as dynamic obstacles. The policy must learn
    to navigate while avoiding these moving obstacles.

    Key modifications from base config:
        - Reduced num_envs (64) due to people overhead
        - Increased env_spacing (15m) to accommodate people
        - People configuration for spawning and behavior
    """

    # People configuration
    people: PeopleManagerCfg = PeopleManagerCfg()

    def __post_init__(self):
        # Call parent initialization first
        super().__post_init__()

        # ============================================
        # SCENE: Adjust for people overhead
        # ============================================

        # Reduce environments due to people rendering overhead
        # Each environment will have animated characters
        self.scene.num_envs = 64

        # Increase spacing to accommodate people movement area
        self.scene.env_spacing = 15.0

        # ============================================
        # PEOPLE SETTINGS (can be overridden)
        # ============================================

        # Default: 2 characters for training
        self.people.num_characters = 2

        # ============================================
        # EPISODE: Slightly longer for navigation
        # ============================================

        # Keep episode length from base (20s) - long enough for navigation
        # self.episode_length_s = 20.0  # (inherited)


@configclass
class DigitalTwinColibriG1PeopleEnvCfg_PLAY(DigitalTwinColibriG1EnvCfg_PLAY):
    """
    Play/visualization configuration with animated people.

    This configuration is optimized for visualization and testing of
    policies with animated people. Uses fewer environments and characters
    for better visual feedback.
    """

    # People configuration (optimized for visualization)
    people: PeopleManagerCfg = PeopleManagerCfg()

    def __post_init__(self):
        # Call parent initialization (inherits PLAY settings)
        super().__post_init__()

        # ============================================
        # SCENE: Fewer environments for visualization
        # ============================================

        # Few environments for clear visualization
        self.scene.num_envs = 4

        # Spacing for people movement
        self.scene.env_spacing = 15.0

        # ============================================
        # PEOPLE SETTINGS: Reduced for visualization
        # ============================================

        # Fewer characters for clearer visualization
        self.people.num_characters = 2
