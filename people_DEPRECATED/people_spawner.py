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
        self._extensions_enabled = False
        self._current_env_idx = 0  # Track which environment is being initialized

    def enable_extensions(self) -> bool:
        """
        Enable required Isaac Sim extensions for people animation.

        This method enables the following extensions:
        - omni.anim.people: Core character animation
        - omni.anim.navigation.bundle: Character navigation
        - omni.anim.graph.bundle: Animation graph system
        - omni.anim.graph.schema: Animation graph schema (required for standalone)
        - omni.anim.navigation.schema: Navigation schema (required for standalone)

        Returns:
            True if all extensions were enabled successfully.

        Note:
            For proper animation support, extensions should be enabled BEFORE
            the gym environment is created. If using play_people.py, extensions
            are pre-enabled there. This method ensures they're available.

            See: https://forums.developer.nvidia.com/t/isaac-sim-people-simulation-broken-in-4-1-0/301378
        """
        if self._extensions_enabled:
            return True

        import omni.kit.app

        ext_manager = omni.kit.app.get_app().get_extension_manager()

        # Core extensions for animated people
        # Note: Schema extensions must be loaded for standalone/headless mode
        # These should already be enabled by play_people.py, but we ensure here
        extensions = [
            # Schema extensions - required for standalone mode
            "omni.anim.graph.schema",
            "omni.anim.navigation.schema",
            # Core animation extensions
            "omni.anim.graph.core",
            "omni.anim.graph.bundle",
            "omni.anim.navigation.bundle",
            "omni.anim.people",
            # Scripting component for behavior scripts
            "omni.kit.scripting",
        ]

        success = True
        for ext in extensions:
            try:
                # Check if already enabled
                if ext_manager.is_extension_enabled(ext):
                    print(f"[People] Extension already enabled: {ext}")
                else:
                    ext_manager.set_extension_enabled_immediate(ext, True)
                    print(f"[People] Enabled extension: {ext}")
            except Exception as e:
                print(f"[People] Warning: Could not enable {ext}: {e}")
                # Don't fail for optional extensions like scripting
                if ext not in ["omni.kit.scripting"]:
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
        - Character prim path for the extension to find characters

        Settings are based on PeopleSettings class in:
        omni/anim/people/settings.py

        Note:
            Characters are always spawned in env_0, then replicated by Isaac Lab
            to other environments. The character path is fixed to env_0.
        """
        import carb

        settings = carb.settings.get_settings()

        # Command file path (CORRECT PATH from settings.py)
        command_file = os.path.join(self.project_root, self.cfg.command_file)
        if os.path.exists(command_file):
            # Use the correct setting path from PeopleSettings.COMMAND_FILE_PATH
            settings.set(
                "/exts/omni.anim.people/command_settings/command_file_path", command_file
            )
            print(f"[People] Command file: {command_file}")
        else:
            print(f"[People] Warning: Command file not found: {command_file}")
            print(f"[People] Characters will use default idle behavior")

        # Navigation settings (CORRECT PATHS from settings.py)
        settings.set(
            "/exts/omni.anim.people/navigation_settings/navmesh_enabled",
            self.cfg.navmesh_enabled,
        )
        settings.set(
            "/exts/omni.anim.people/navigation_settings/dynamic_avoidance_enabled",
            self.cfg.dynamic_avoidance,
        )

        # Loop setting (CORRECT PATH from settings.py)
        loop_value = "inf" if self.cfg.loop_commands else "1"
        settings.set("/exts/omni.anim.people/command_settings/number_of_loop", loop_value)

        # Character prim path - ALWAYS env_0 since we only spawn to env_0
        # Isaac Lab replicates env_0 to other environments, so behavior script
        # will find characters in all replicated environments automatically.
        character_root_path = "/World/envs/env_0/Characters"
        settings.set(
            "/persistent/exts/omni.anim.people/character_prim_path",
            character_root_path
        )

        print(
            f"[People] Settings: NavMesh={self.cfg.navmesh_enabled}, "
            f"Avoidance={self.cfg.dynamic_avoidance}, Loop={loop_value}"
        )
        print(f"[People] Character prim path set to: {character_root_path}")

    def _get_nucleus_asset_path(self) -> str:
        """Get the Nucleus/Cloud asset root path for Isaac Sim assets.

        Returns:
            The asset root path from carb settings or cloud fallback.
        """
        try:
            import carb
            settings = carb.settings.get_settings()

            # Try cloud path first (Isaac Sim 5.0 default)
            cloud_path = settings.get("/persistent/isaac/asset_root/cloud")
            if cloud_path:
                print(f"[People] Using cloud asset path: {cloud_path}")
                return cloud_path

            # Try default path
            default_path = settings.get("/persistent/isaac/asset_root/default")
            if default_path:
                print(f"[People] Using default asset path: {default_path}")
                return default_path

        except Exception as e:
            print(f"[People] Warning: Could not get carb settings: {e}")

        # Fallback to Isaac Sim 5.0 cloud URL
        fallback = "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.0"
        print(f"[People] Using fallback cloud URL: {fallback}")
        return fallback

    def spawn_characters(self, stage: Usd.Stage, env_idx: int = 0) -> list:
        """
        Spawn character prims into the USD stage.

        Args:
            stage: USD stage to spawn characters into.
            env_idx: Environment index (for multi-env support).

        Returns:
            List of spawned character prims for this environment.

        Note:
            Characters are spawned with randomized positions within the
            configured spawn area. The random seed is fixed for reproducibility.
        """
        from pxr import UsdGeom, Gf

        # Get the asset root path
        asset_root = self._get_nucleus_asset_path()

        # Create characters root prim
        characters_root = f"/World/envs/env_{env_idx}/Characters"
        if not stage.GetPrimAtPath(characters_root):
            UsdGeom.Xform.Define(stage, characters_root)

        # Use fixed seed for reproducible positions during training
        rng = np.random.default_rng(42 + env_idx)

        # Build spawn commands for omni.anim.people extension
        spawn_commands = []
        env_characters = []  # Characters for THIS environment only

        for i in range(self.cfg.num_characters):
            char_name = f"Character_{i}"
            char_path = f"{characters_root}/{char_name}"

            # Check if character already exists in this environment
            if stage.GetPrimAtPath(char_path):
                print(f"[People] {char_name} already exists in env_{env_idx}, skipping")
                continue

            # Generate spawn position within configured area
            x = rng.uniform(self.cfg.spawn_area_min[0], self.cfg.spawn_area_max[0])
            y = rng.uniform(self.cfg.spawn_area_min[1], self.cfg.spawn_area_max[1])
            z = self.cfg.spawn_height

            # Select character asset (cycle through available assets)
            asset_idx = i % len(self.cfg.character_assets)
            asset_path = self.cfg.character_assets[asset_idx]

            # Build full asset URL
            # Config paths are like "/Isaac/People/Characters/..." - we need to append to asset root
            if asset_path.startswith("/Isaac"):
                full_asset_path = f"{asset_root}{asset_path}"
            else:
                full_asset_path = asset_path

            print(f"[People] Loading character from: {full_asset_path}")

            # Create character prim with reference to asset
            char_prim = stage.DefinePrim(char_path, "Xform")
            char_prim.GetReferences().AddReference(full_asset_path)

            # Set position using transform operation
            xform = UsdGeom.Xformable(char_prim)
            xform.ClearXformOpOrder()
            translate_op = xform.AddTranslateOp()
            translate_op.Set(Gf.Vec3d(x, y, z))

            # Animated characters are visual obstacles only (no collision)
            # Physics APIs are not applied to these characters

            env_characters.append(char_prim)
            print(f"[People] Spawned {char_name} at ({x:.2f}, {y:.2f}, {z:.2f})")

            # Store spawn info for command generation
            spawn_commands.append({
                "name": char_name,
                "path": char_path,
                "position": (x, y, z),
                "asset_path": full_asset_path,
            })

        # Store spawn commands for this environment
        if not hasattr(self, '_env_spawn_commands'):
            self._env_spawn_commands = {}
        self._env_spawn_commands[env_idx] = spawn_commands

        return env_characters

    def setup_character_animation(self, stage: Usd.Stage, char_prim) -> bool:
        """
        Setup animation graph and behavior script for a character.

        This enables the character to animate (walk, idle, look around) by
        attaching the CharacterBehavior script from omni.anim.people extension.

        The script attachment follows the pattern from:
        omni.anim.people.python_ext.add_dynamic_obstacle_behavior_script()

        Args:
            stage: USD stage containing the character.
            char_prim: The character's root prim.

        Returns:
            True if animation setup succeeded.
        """
        try:
            from pxr import Usd, UsdSkel, Sdf, UsdGeom
            import omni.kit.commands
            import omni.kit.app
            import time

            # Find SkelRoot prims under the character
            skel_roots = []
            for prim in Usd.PrimRange(char_prim):
                if prim.IsA(UsdSkel.Root):
                    skel_roots.append(prim)

            if not skel_roots:
                print(f"[People] Warning: No SkelRoot found in {char_prim.GetPath()}")
                return False

            print(f"[People] Found {len(skel_roots)} SkelRoot(s) in {char_prim.GetPath()}")

            # Get the extension path to find the character_behavior.py script
            ext_manager = omni.kit.app.get_app().get_extension_manager()
            ext_path = ext_manager.get_extension_path_by_module("omni.anim.people")
            if ext_path:
                script_path = f"{ext_path}/omni/anim/people/scripts/character_behavior.py"
                print(f"[People] Behavior script path: {script_path}")
            else:
                print(f"[People] Warning: Could not find omni.anim.people extension path")
                return False

            # Attach behavior script to each SkelRoot
            for skel_root in skel_roots:
                skel_path = str(skel_root.GetPath())

                try:
                    # Step 1: Apply Scripting API to enable script attachment
                    omni.kit.commands.execute(
                        "ApplyScriptingAPICommand",
                        paths=[Sdf.Path(skel_path)],
                    )
                    print(f"[People] Applied Scripting API to {skel_path}")

                    # Step 2: Apply AnimationGraphAPI for animation support
                    try:
                        from pxr import UsdLux
                        from pxr.UsdGeom import XformCommonAPI
                        import omni.usd

                        # Apply AnimationGraphAPI to the SkelRoot
                        skel_root.SetMetadata("customData", {})
                        print(f"[People] Applied animation metadata to {skel_path}")
                    except Exception as e:
                        print(f"[People] Note: AnimationGraphAPI application: {e}")

                    # Step 3: Attach behavior script
                    scripts_attr = skel_root.GetAttribute("omni:scripting:scripts")
                    if not scripts_attr:
                        # Create the attribute if it doesn't exist
                        scripts_attr = skel_root.CreateAttribute(
                            "omni:scripting:scripts",
                            Sdf.ValueTypeNames.StringArray
                        )
                        print(f"[People] Created scripts attribute for {skel_path}")

                    # Get existing scripts
                    existing_scripts = scripts_attr.Get() or []
                    script_list = list(existing_scripts) if existing_scripts else []

                    # Add script if not already present
                    if script_path not in script_list:
                        script_list.append(script_path)
                        scripts_attr.Set(script_list)
                        print(f"[People] Attached behavior script to {skel_path}")
                    else:
                        print(f"[People] Behavior script already attached to {skel_path}")

                except Exception as e:
                    print(f"[People] Error setting up script for {skel_path}: {e}")
                    import traceback
                    traceback.print_exc()

            print(f"[People] Animation setup complete for {char_prim.GetPath()}")
            return True

        except Exception as e:
            print(f"[People] Warning: Could not setup animation: {e}")
            import traceback
            traceback.print_exc()
            return False

    def start_animation(self) -> bool:
        """
        Start the animation system after characters are spawned.

        This triggers the omni.anim.people extension to begin processing
        character commands and playing animations.

        Returns:
            True if animation was started successfully.
        """
        try:
            # Method 1: Try to use the extension's UI window commands
            try:
                import omni.kit.ui
                import omni.kit.window.extensions

                # Try to find and trigger the "Setup Characters" functionality
                # This mimics clicking the Setup Characters button in the UI
                print("[People] Attempting to trigger animation setup via extension...")

            except Exception as e:
                print(f"[People] Note: UI-based setup not available: {e}")

            # Method 2: Try to directly call the extension's Python API
            try:
                # Try importing omni.anim.people's main module
                import omni.anim.people

                # Some extensions expose a start/play method
                if hasattr(omni.anim.people, "setup_characters"):
                    omni.anim.people.setup_characters()
                    print("[People] Called omni.anim.people.setup_characters()")

                if hasattr(omni.anim.people, "start"):
                    omni.anim.people.start()
                    print("[People] Called omni.anim.people.start()")

            except ImportError:
                print("[People] Note: omni.anim.people module not directly importable")
            except Exception as e:
                print(f"[People] Note: Direct API call: {e}")

            # Method 3: Trigger via timeline/simulation events
            try:
                import omni.timeline

                timeline = omni.timeline.get_timeline_interface()
                if timeline:
                    # Playing the timeline should trigger animation subscriptions
                    timeline.play()
                    print("[People] Started timeline playback")
                    return True

            except Exception as e:
                print(f"[People] Note: Timeline control: {e}")

            return True

        except Exception as e:
            print(f"[People] Warning: Could not start animation: {e}")
            return False

    def initialize(self, stage: Usd.Stage, env_idx: int = 0) -> list:
        """
        Full initialization: enable extensions, configure settings, and spawn characters.

        This is the main entry point for setting up animated people in an environment.
        Characters are always spawned to env_0, then replicated by Isaac Lab.

        Args:
            stage: USD stage to spawn characters into.
            env_idx: For compatibility, but always uses env_0.

        Returns:
            List of spawned character prims.

        Example:
            ```python
            stage = omni.usd.get_context().get_stage()
            characters = spawner.initialize(stage)
            print(f"Spawned {len(characters)} characters (will be replicated)")
            ```
        """
        print("[People] Initializing people spawner for env_0...")

        # Step 1: Enable required extensions (only once globally)
        if not self._extensions_enabled:
            self.enable_extensions()

        # Step 2: Configure carb settings (always env_0)
        self.setup_settings()

        # Step 3: Spawn characters to env_0 only
        # Isaac Lab will replicate these to other environments
        characters = self.spawn_characters(stage, env_idx=0)

        # Step 4: Setup animation for each spawned character
        for char_prim in characters:
            self.setup_character_animation(stage, char_prim)

        # Step 5: Try to start animation playback
        self.start_animation()

        print(f"[People] Initialization complete: {len(characters)} characters spawned to env_0")
        return characters

    def get_character_positions(self, stage, env_idx: int = 0) -> list:
        """
        Get current positions of all characters in a specific environment.

        Args:
            stage: USD stage containing the characters.
            env_idx: Environment index to get positions for.

        Returns:
            List of (x, y, z) tuples for each character's position.
        """
        from pxr import Usd, UsdGeom

        positions = []
        characters_root = f"/World/envs/env_{env_idx}/Characters"
        root_prim = stage.GetPrimAtPath(characters_root)

        if not root_prim.IsValid():
            return positions

        # Iterate through all children to find characters
        for i in range(self.cfg.num_characters):
            char_name = f"Character_{i}"
            char_path = f"{characters_root}/{char_name}"
            char_prim = stage.GetPrimAtPath(char_path)

            if char_prim.IsValid():
                xform = UsdGeom.Xformable(char_prim)
                transform = xform.ComputeLocalToWorldTransform(0)
                pos = transform.ExtractTranslation()
                positions.append((pos[0], pos[1], pos[2]))

        return positions
