# Copyright (c) 2024, Universidad de los Andes
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""
People Spawner for Colibri G1 Environment.

This module provides functionality to spawn and configure animated human
characters using Isaac Sim's omni.anim.people extension and IRA
(IsaacSim Replicator Agent).

The characters follow scripted behaviors defined in a command file and
serve as dynamic obstacles for training social navigation policies.

Note:
    The omni.anim.people extension is deprecated but still functional.
    It provides simple animated characters that can walk, idle, and look around.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from pxr import Usd


class PeopleSpawner:
    """
    Spawns and configures animated people using omni.anim.people.

    This class handles the initialization of Isaac Sim extensions for
    character animation and spawns characters into the USD stage with
    randomized positions.

    Attributes:
        cfg: PeopleManagerCfg configuration object.
        project_root: Root directory of the project.
        characters: List of spawned character prims.

    Example:
        ```python
        from people import PeopleSpawner
        from people_env_cfg import PeopleManagerCfg

        cfg = PeopleManagerCfg()
        spawner = PeopleSpawner(cfg, "/path/to/project")

        stage = omni.usd.get_context().get_stage()
        spawner.initialize(stage, env_idx=0)
        ```
    """

    def __init__(self, people_cfg, project_root: str):
        """
        Initialize the people spawner.

        Args:
            people_cfg: PeopleManagerCfg configuration object.
            project_root: Root directory of the project (for finding command file).
        """
        self.cfg = people_cfg
        self.project_root = project_root
        self.characters: list = []
        self._extensions_enabled = False

    def enable_extensions(self) -> bool:
        """
        Enable required Isaac Sim extensions for people animation.

        This method enables the following extensions:
        - omni.anim.people: Core character animation
        - omni.anim.navigation.bundle: Character navigation
        - omni.anim.graph.bundle: Animation graph system

        Returns:
            True if all extensions were enabled successfully.

        Note:
            Some extensions may fail to load on certain Isaac Sim versions.
            The method will print warnings but continue execution.
        """
        if self._extensions_enabled:
            return True

        import omni.kit.app

        ext_manager = omni.kit.app.get_app().get_extension_manager()

        # Core extensions for animated people
        extensions = [
            "omni.anim.people",
            "omni.anim.navigation.bundle",
            "omni.anim.graph.bundle",
        ]

        success = True
        for ext in extensions:
            try:
                ext_manager.set_extension_enabled_immediate(ext, True)
                print(f"[People] Enabled extension: {ext}")
            except Exception as e:
                print(f"[People] Warning: Could not enable {ext}: {e}")
                success = False

        self._extensions_enabled = True
        return success

    def setup_settings(self) -> None:
        """
        Configure omni.anim.people settings via carb settings.

        This method sets up:
        - Command file path for character behaviors
        - NavMesh settings (enabled/disabled)
        - Dynamic avoidance between characters
        - Command looping behavior
        """
        import carb

        settings = carb.settings.get_settings()

        # Set command file path
        command_file = os.path.join(self.project_root, self.cfg.command_file)
        if os.path.exists(command_file):
            settings.set(
                "/persistent/exts/omni.anim.people/command_file", command_file
            )
            print(f"[People] Command file: {command_file}")
        else:
            print(f"[People] Warning: Command file not found: {command_file}")
            print(f"[People] Characters will use default idle behavior")

        # Navigation settings
        settings.set(
            "/persistent/exts/omni.anim.people/navmesh_enabled",
            self.cfg.navmesh_enabled,
        )
        settings.set(
            "/persistent/exts/omni.anim.people/dynamic_avoidance",
            self.cfg.dynamic_avoidance,
        )

        # Loop setting
        loop_value = "inf" if self.cfg.loop_commands else "1"
        settings.set("/persistent/exts/omni.anim.people/number_of_loop", loop_value)

        print(
            f"[People] Settings: NavMesh={self.cfg.navmesh_enabled}, "
            f"Avoidance={self.cfg.dynamic_avoidance}, Loop={loop_value}"
        )

    def spawn_characters(self, stage: Usd.Stage, env_idx: int = 0) -> list:
        """
        Spawn character prims into the USD stage.

        Args:
            stage: USD stage to spawn characters into.
            env_idx: Environment index (for multi-env support).

        Returns:
            List of spawned character prims.

        Note:
            Characters are spawned with randomized positions within the
            configured spawn area. The random seed is fixed for reproducibility.
        """
        from pxr import UsdGeom, Gf

        # Create characters root prim
        characters_root = f"/World/envs/env_{env_idx}/Characters"
        if not stage.GetPrimAtPath(characters_root):
            UsdGeom.Xform.Define(stage, characters_root)

        # Use fixed seed for reproducible positions during training
        rng = np.random.default_rng(42 + env_idx)

        for i in range(self.cfg.num_characters):
            char_path = f"{characters_root}/Character_{i}"

            # Check if character already exists
            if stage.GetPrimAtPath(char_path):
                print(f"[People] Character_{i} already exists, skipping")
                continue

            # Generate spawn position within configured area
            x = rng.uniform(self.cfg.spawn_area_min[0], self.cfg.spawn_area_max[0])
            y = rng.uniform(self.cfg.spawn_area_min[1], self.cfg.spawn_area_max[1])
            z = self.cfg.spawn_height

            # Select character asset (cycle through available assets)
            asset_idx = i % len(self.cfg.character_assets)
            asset_path = self.cfg.character_assets[asset_idx]

            # Create character prim with reference to asset
            char_prim = stage.DefinePrim(char_path, "Xform")
            char_prim.GetReferences().AddReference(asset_path)

            # Set position using transform operation
            xform = UsdGeom.Xformable(char_prim)
            xform.ClearXformOpOrder()
            translate_op = xform.AddTranslateOp()
            translate_op.Set(Gf.Vec3d(x, y, z))

            self.characters.append(char_prim)
            print(f"[People] Spawned Character_{i} at ({x:.2f}, {y:.2f}, {z:.2f})")

        return self.characters

    def initialize(self, stage: Usd.Stage, env_idx: int = 0) -> list:
        """
        Full initialization: enable extensions, configure settings, and spawn characters.

        This is the main entry point for setting up animated people in an environment.

        Args:
            stage: USD stage to spawn characters into.
            env_idx: Environment index (for multi-env support).

        Returns:
            List of spawned character prims.

        Example:
            ```python
            stage = omni.usd.get_context().get_stage()
            characters = spawner.initialize(stage, env_idx=0)
            print(f"Spawned {len(characters)} characters")
            ```
        """
        print(f"[People] Initializing people spawner for env_{env_idx}...")

        # Step 1: Enable required extensions
        self.enable_extensions()

        # Step 2: Configure carb settings
        self.setup_settings()

        # Step 3: Spawn characters into stage
        characters = self.spawn_characters(stage, env_idx)

        print(f"[People] Initialization complete: {len(characters)} characters spawned")
        return characters

    def get_character_positions(self) -> list:
        """
        Get current positions of all spawned characters.

        Returns:
            List of (x, y, z) tuples for each character's position.
        """
        from pxr import UsdGeom

        positions = []
        for char_prim in self.characters:
            if char_prim.IsValid():
                xform = UsdGeom.Xformable(char_prim)
                transform = xform.ComputeLocalToWorldTransform(0)
                pos = transform.ExtractTranslation()
                positions.append((pos[0], pos[1], pos[2]))
        return positions
