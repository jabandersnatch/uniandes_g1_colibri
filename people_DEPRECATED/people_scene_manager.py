# Copyright (c) 2024, Universidad de los Andes
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""
People Scene Manager for Colibri G1 Environment.

This module provides functionality to add animated human characters to an
Isaac Lab scene as GLOBAL (non-replicated) assets. Characters exist once
in the world and are shared by all parallel environments.

Key Principles:
  1. Characters are GLOBAL (not per-environment)
  2. Use prim_path="/World/Characters" (no {ENV_REGEX_NS})
  3. Set collision_group=-1 to mark as global
  4. Add via scene configuration, NOT post-initialization spawning
  5. Let Isaac Lab's InteractiveScene manage them
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

# Try to import Isaac Sim modules (graceful fallback if not available)
try:
    import carb
    ISAAC_AVAILABLE = True
except ImportError:
    ISAAC_AVAILABLE = False

if TYPE_CHECKING:
    from pxr import Usd


class PeopleSceneManager:
    """
    Manages animated people as global scene assets in Isaac Lab.

    Unlike the old approach which tried to spawn people per-environment,
    this manager adds people to the world ONCE, where they're shared
    by all parallel environments.

    This follows Isaac Lab's architectural pattern:
    - Terrain: /World/ground (global)
    - Characters: /World/Characters (global)
    - Robots: {ENV_REGEX_NS}/Robot (replicated per env)

    Attributes:
        cfg: PeopleManagerCfg configuration object.
        project_root: Root directory of the project.
        logger: Logging helper with detailed tracking.
    """

    def __init__(self, people_cfg, project_root: str):
        """
        Initialize the people scene manager.

        Args:
            people_cfg: PeopleManagerCfg configuration object.
            project_root: Root directory of the project (for finding command file).
        """
        self.cfg = people_cfg
        self.project_root = project_root
        self.characters = []
        self._extensions_enabled = False

        # Setup logging with detailed tracking
        self.log_prefix = "[People]"
        self._log(f"Initializing PeopleSceneManager")
        self._log(f"  Project root: {project_root}")
        self._log(f"  Number of characters to spawn: {people_cfg.num_characters}")
        self._log(f"  Spawn area: X [{people_cfg.spawn_area_min[0]}, {people_cfg.spawn_area_max[0]}], "
                  f"Y [{people_cfg.spawn_area_min[1]}, {people_cfg.spawn_area_max[1]}]")
        self._log(f"  Spawn height: {people_cfg.spawn_height}")

    def _log(self, msg: str, level: str = "INFO"):
        """
        Log with detailed level tracking.

        Args:
            msg: Message to log.
            level: Log level (INFO, WARNING, ERROR, DEBUG).
        """
        prefix = f"{self.log_prefix} [{level}]"
        if level == "ERROR":
            print(f"[ERROR] {prefix} {msg}")
        elif level == "WARNING":
            print(f"[WARNING] {prefix} {msg}")
        else:
            print(f"{prefix} {msg}")

    def enable_extensions(self) -> bool:
        """
        Enable required Isaac Sim extensions for people animation.

        Extensions required:
        - omni.anim.people: Core character animation
        - omni.anim.navigation.bundle: Character navigation
        - omni.anim.graph.bundle: Animation graph system
        - omni.kit.scripting: Behavior script support

        Returns:
            True if all extensions were enabled successfully.
        """
        if self._extensions_enabled:
            self._log("Extensions already enabled, skipping")
            return True

        try:
            import omni.kit.app

            ext_manager = omni.kit.app.get_app().get_extension_manager()

            extensions = [
                "omni.anim.graph.schema",
                "omni.anim.navigation.schema",
                "omni.anim.graph.core",
                "omni.anim.graph.bundle",
                "omni.anim.navigation.bundle",
                "omni.anim.people",
                "omni.kit.scripting",
            ]

            self._log(f"Enabling {len(extensions)} extensions for people animation")
            for ext in extensions:
                try:
                    if ext_manager.is_extension_enabled(ext):
                        self._log(f"  ✓ {ext} (already enabled)", "INFO")
                    else:
                        ext_manager.set_extension_enabled_immediate(ext, True)
                        self._log(f"  ✓ {ext} (enabled)", "INFO")
                except Exception as e:
                    self._log(f"  ✗ {ext} - {e}", "WARNING")
                    if "schema" not in ext and "people" not in ext:
                        return False

            self._extensions_enabled = True
            self._log("All extensions enabled successfully")
            return True

        except Exception as e:
            self._log(f"Failed to enable extensions: {e}", "ERROR")
            return False

    def setup_settings(self) -> None:
        """
        Configure omni.anim.people settings via carb settings.

        These settings control how the behavior script finds and animates
        characters in the global world (not per-environment).
        """
        self._log("Configuring omni.anim.people settings")

        try:
            settings = carb.settings.get_settings()

            # Command file path
            command_file = os.path.join(self.project_root, self.cfg.command_file)
            if os.path.exists(command_file):
                settings.set(
                    "/exts/omni.anim.people/command_settings/command_file_path",
                    command_file
                )
                self._log(f"  ✓ Command file: {command_file}", "INFO")
            else:
                self._log(f"  ⚠ Command file not found: {command_file}", "WARNING")
                self._log(f"    Characters will use default idle behavior", "WARNING")

            # Navigation settings
            settings.set(
                "/exts/omni.anim.people/navigation_settings/navmesh_enabled",
                self.cfg.navmesh_enabled,
            )
            self._log(f"  ✓ NavMesh enabled: {self.cfg.navmesh_enabled}", "INFO")

            settings.set(
                "/exts/omni.anim.people/navigation_settings/dynamic_avoidance_enabled",
                self.cfg.dynamic_avoidance,
            )
            self._log(f"  ✓ Dynamic avoidance: {self.cfg.dynamic_avoidance}", "INFO")

            # Loop setting
            loop_value = "inf" if self.cfg.loop_commands else "1"
            settings.set(
                "/exts/omni.anim.people/command_settings/number_of_loop",
                loop_value
            )
            self._log(f"  ✓ Command loop: {loop_value}", "INFO")

            # CRITICAL: Character root path - GLOBAL location, not per-environment
            # This is where the behavior script looks for all characters
            character_root_path = "/World/Characters"
            settings.set(
                "/persistent/exts/omni.anim.people/character_prim_path",
                character_root_path
            )
            self._log(f"  ✓ Character root path: {character_root_path}", "INFO")
            self._log(f"    (This is GLOBAL - characters exist once, not per-environment)", "INFO")

        except Exception as e:
            self._log(f"Failed to setup settings: {e}", "ERROR")

    def spawn_characters_global(self, stage: Usd.Stage) -> list:
        """
        Spawn characters as GLOBAL scene assets (shared by all environments).

        This method creates animated characters in /World/Characters,
        which are NOT replicated per environment. All 512 parallel robots
        share the same animated people.

        Args:
            stage: USD stage to spawn characters into.

        Returns:
            List of spawned character prims.
        """
        from pxr import UsdGeom, Gf
        import numpy as np

        self._log(f"Spawning {self.cfg.num_characters} characters to GLOBAL location")
        self._log(f"  Path: /World/Characters (NOT per-environment)")

        # Create global characters root
        characters_root = "/World/Characters"
        if not stage.GetPrimAtPath(characters_root):
            self._log(f"  Creating root prim: {characters_root}", "INFO")
            UsdGeom.Xform.Define(stage, characters_root)
        else:
            self._log(f"  Root prim already exists: {characters_root}", "INFO")

        # Get asset root
        try:
            asset_root = self._get_nucleus_asset_path()
            self._log(f"  Asset root: {asset_root}", "INFO")
        except Exception as e:
            self._log(f"Failed to get asset root: {e}", "ERROR")
            return []

        # Fixed seed for reproducible positions
        rng = np.random.default_rng(42)
        spawned_chars = []

        for i in range(self.cfg.num_characters):
            char_name = f"Character_{i}"
            char_path = f"{characters_root}/{char_name}"

            # Check if already exists
            if stage.GetPrimAtPath(char_path):
                self._log(f"  ⚠ {char_name} already exists, skipping", "WARNING")
                continue

            # Generate spawn position
            x = rng.uniform(self.cfg.spawn_area_min[0], self.cfg.spawn_area_max[0])
            y = rng.uniform(self.cfg.spawn_area_min[1], self.cfg.spawn_area_max[1])
            z = self.cfg.spawn_height

            # Get character asset
            asset_idx = i % len(self.cfg.character_assets)
            asset_path = self.cfg.character_assets[asset_idx]
            if asset_path.startswith("/Isaac"):
                full_asset_path = f"{asset_root}{asset_path}"
            else:
                full_asset_path = asset_path

            try:
                self._log(f"  Spawning {char_name}", "INFO")
                self._log(f"    Path: {char_path}", "INFO")
                self._log(f"    Asset: {full_asset_path}", "INFO")
                self._log(f"    Position: ({x:.2f}, {y:.2f}, {z:.2f})", "INFO")

                # Create prim with reference
                char_prim = stage.DefinePrim(char_path, "Xform")
                char_prim.GetReferences().AddReference(full_asset_path)

                # Set position
                xform = UsdGeom.Xformable(char_prim)
                xform.ClearXformOpOrder()
                translate_op = xform.AddTranslateOp()
                translate_op.Set(Gf.Vec3d(x, y, z))

                spawned_chars.append(char_prim)
                self._log(f"    ✓ Spawned successfully", "INFO")

            except Exception as e:
                self._log(f"    ✗ Failed to spawn: {e}", "ERROR")
                continue

        self._log(f"Total spawned: {len(spawned_chars)} characters", "INFO")
        return spawned_chars

    def setup_character_animation(self, stage: Usd.Stage, char_prim) -> bool:
        """
        Setup animation for a single character.

        Args:
            stage: USD stage containing the character.
            char_prim: The character root prim.

        Returns:
            True if animation was setup successfully.
        """
        try:
            from pxr import Usd, UsdSkel, Sdf
            import omni.kit.commands
            import omni.kit.app

            char_path = str(char_prim.GetPath())
            self._log(f"Setting up animation for {char_path}", "INFO")

            # Find SkelRoot prims
            skel_roots = []
            for prim in Usd.PrimRange(char_prim):
                if prim.IsA(UsdSkel.Root):
                    skel_roots.append(prim)

            if not skel_roots:
                self._log(f"  ✗ No SkelRoot found in {char_path}", "ERROR")
                return False

            self._log(f"  ✓ Found {len(skel_roots)} SkelRoot(s)", "INFO")

            # Get script path
            ext_manager = omni.kit.app.get_app().get_extension_manager()
            ext_path = ext_manager.get_extension_path_by_module("omni.anim.people")
            if not ext_path:
                self._log(f"  ✗ Could not find omni.anim.people extension", "ERROR")
                return False

            script_path = f"{ext_path}/omni/anim/people/scripts/character_behavior.py"
            self._log(f"  ✓ Behavior script: {script_path}", "INFO")

            # Attach script to each SkelRoot
            for skel_root in skel_roots:
                skel_path = str(skel_root.GetPath())

                try:
                    self._log(f"  Attaching script to {skel_path}", "INFO")

                    # Apply Scripting API
                    omni.kit.commands.execute(
                        "ApplyScriptingAPICommand",
                        paths=[Sdf.Path(skel_path)],
                    )
                    self._log(f"    ✓ Scripting API applied", "INFO")

                    # Create/update scripts attribute
                    scripts_attr = skel_root.GetAttribute("omni:scripting:scripts")
                    if not scripts_attr:
                        scripts_attr = skel_root.CreateAttribute(
                            "omni:scripting:scripts",
                            Sdf.ValueTypeNames.StringArray
                        )
                        self._log(f"    ✓ Created scripts attribute", "INFO")

                    # Set script
                    existing = scripts_attr.Get() or []
                    if script_path not in existing:
                        scripts_attr.Set([script_path])
                        self._log(f"    ✓ Behavior script attached", "INFO")
                    else:
                        self._log(f"    ✓ Behavior script already attached", "INFO")

                except Exception as e:
                    self._log(f"    ✗ Error attaching script: {e}", "ERROR")
                    continue

            self._log(f"  ✓ Animation setup complete for {char_path}", "INFO")
            return True

        except Exception as e:
            self._log(f"  ✗ Failed to setup animation: {e}", "ERROR")
            import traceback
            traceback.print_exc()
            return False

    def start_animation(self) -> bool:
        """Start animation playback."""
        try:
            import omni.timeline

            self._log("Starting animation timeline", "INFO")
            timeline = omni.timeline.get_timeline_interface()
            if timeline:
                timeline.play()
                self._log("  ✓ Timeline playback started", "INFO")
                return True
            return False
        except Exception as e:
            self._log(f"  ⚠ Failed to start timeline: {e}", "WARNING")
            return False

    def _get_nucleus_asset_path(self) -> str:
        """Get the Nucleus asset root path."""
        try:
            settings = carb.settings.get_settings()

            # Try cloud path first
            cloud_path = settings.get("/persistent/isaac/asset_root/cloud")
            if cloud_path:
                return cloud_path

            # Try default
            default_path = settings.get("/persistent/isaac/asset_root/default")
            if default_path:
                return default_path

        except Exception as e:
            self._log(f"  ⚠ Could not get carb settings: {e}", "WARNING")

        # Fallback
        return "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.0"

    def initialize(self, stage: Usd.Stage) -> list:
        """
        Initialize people as global scene assets.

        This is the main entry point. Call this ONCE after the environment
        is created to add animated people to the world.

        Args:
            stage: USD stage to add characters to.

        Returns:
            List of spawned character prims.
        """
        self._log("=" * 70)
        self._log("INITIALIZING PEOPLE AS GLOBAL SCENE ASSETS")
        self._log("=" * 70)

        # Step 1: Enable extensions
        self._log("\nStep 1/5: Enabling extensions", "INFO")
        if not self.enable_extensions():
            self._log("Failed to enable extensions", "ERROR")
            return []

        # Step 2: Configure settings
        self._log("\nStep 2/5: Configuring settings", "INFO")
        self.setup_settings()

        # Step 3: Spawn characters
        self._log("\nStep 3/5: Spawning characters", "INFO")
        characters = self.spawn_characters_global(stage)

        if not characters:
            self._log("No characters were spawned", "ERROR")
            return []

        # Step 4: Setup animation
        self._log("\nStep 4/5: Setting up animation", "INFO")
        for char_prim in characters:
            self.setup_character_animation(stage, char_prim)

        # Step 5: Start animation
        self._log("\nStep 5/5: Starting animation", "INFO")
        self.start_animation()

        self._log("\n" + "=" * 70)
        self._log(f"INITIALIZATION COMPLETE: {len(characters)} characters spawned")
        self._log("=" * 70 + "\n")

        return characters
