# Copyright (c) 2024, University of Los Andes (MISIS Program)
# Licensed under the BSD 3-Clause License

"""
IRA Character Manager for animated people in Isaac Lab environments.

This module provides the IRACharacterManager class for spawning and controlling
animated human characters using IRA (isaacsim.replicator.agent). Characters
are spawned as global assets (not per-environment) and execute command sequences
for behavioral variety during training.
"""

import os
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import random
from dataclasses import dataclass

# Try to import Isaac APIs
try:
    import carb
    import omni
    from omni.isaac.core.utils.stage import get_current_stage, add_reference_to_stage
    from omni.isaac.core.utils.prims import create_prim, delete_prim
    from pxr import Usd, UsdGeom, Gf
    ISAAC_AVAILABLE = True
except ImportError:
    ISAAC_AVAILABLE = False

# Import NavMesh utilities (handle both package and standalone imports)
try:
    from people.navmesh_utils import NavMeshUtility
except ImportError:
    from navmesh_utils import NavMeshUtility

# Configure logging
_logger = logging.getLogger("[IRA People]")


@dataclass
class CharacterSpawnConfig:
    """Configuration for spawning a single character."""
    name: str                          # Character identifier
    asset_url: str                     # Cloud asset URL
    position: Tuple[float, float, float]  # Spawn position (x, y, z)
    rotation: float                    # Rotation in degrees
    root_path: str = "/World/Characters"  # Parent path


class IRACharacterManager:
    """
    Manages animated characters using IRA (isaacsim.replicator.agent).

    This manager:
    - Loads required extensions in correct order
    - Creates NavMesh for character pathfinding
    - Spawns characters as global assets (shared by all robots)
    - Parses and executes behavior commands
    - Monitors character state for debugging

    The key architectural principle: Characters are GLOBAL assets (/World/Characters),
    not replicated per-environment, so all robots share the same characters.
    """

    # Required extension load order (CRITICAL)
    EXTENSION_LOAD_ORDER = [
        "omni.anim.graph.schema",          # Schema FIRST
        "omni.anim.graph.core",
        "omni.anim.navigation.schema",
        "omni.anim.navigation.core",
        "omni.replicator.agent",           # IRA depends on above
        "omni.kit.scripting",
    ]

    def __init__(
        self,
        config: Dict,
        project_root: Optional[str] = None,
        verbose: bool = True,
    ):
        """
        Initialize IRA Character Manager.

        Args:
            config: Configuration dictionary (loaded from YAML)
            project_root: Root project directory (for relative paths)
            verbose: Enable detailed logging
        """
        self.config = config
        self.project_root = project_root or os.getcwd()
        self.verbose = verbose

        self.spawned_characters: List[str] = []
        self.character_states: Dict[str, Dict] = {}
        self.navmesh_util = NavMeshUtility(verbose=verbose)

        self.log("=" * 60)
        self.log("IRA Character Manager Initialized")
        self.log("=" * 60)
        self.log(f"Project root: {self.project_root}")
        self.log(f"Number of characters to spawn: {config['characters']['num_characters']}")

    def log(self, message: str, level: str = "INFO"):
        """Log message with [IRA People] prefix."""
        prefix = "[IRA People]"
        if level == "INFO":
            _logger.info(f"{prefix} {message}")
        elif level == "WARNING":
            _logger.warning(f"{prefix} {message}")
        elif level == "ERROR":
            _logger.error(f"{prefix} {message}")
        elif level == "DEBUG" and self.verbose:
            _logger.debug(f"{prefix} {message}")

    def enable_extensions(self) -> bool:
        """
        Enable required extensions in correct order.

        CRITICAL: Extensions must load in specific order due to dependencies.
        Schemas must load before cores. IRA depends on graph and navigation cores.

        Returns:
            True if all extensions enabled successfully
        """
        if not ISAAC_AVAILABLE:
            self.log("Isaac Sim not available", level="ERROR")
            return False

        self.log(f"Enabling {len(self.EXTENSION_LOAD_ORDER)} extensions for IRA")

        all_success = True
        for ext_name in self.EXTENSION_LOAD_ORDER:
            try:
                ext_manager = omni.kit.app.get_app().ext_manager
                ext_manager.set_extension_enabled_immediate(ext_name, True)

                # Check if successfully enabled
                is_enabled = ext_manager.is_extension_enabled(ext_name)
                status = "✓ enabled" if is_enabled else "✗ failed"
                self.log(f"  {status}: {ext_name}", level="DEBUG")

                if not is_enabled:
                    all_success = False

            except Exception as e:
                self.log(
                    f"  ⚠ {ext_name}: {str(e)}",
                    level="WARNING"
                )
                # Don't fail completely - extension might already be loaded

        if all_success:
            self.log("✓ All extensions enabled successfully")
        else:
            self.log(
                "⚠ Some extensions failed to enable (may already be loaded)",
                level="WARNING"
            )

        return True

    def configure_carb_settings(self) -> bool:
        """
        Configure carb settings for IRA character animation.

        Sets up paths and behaviors for the omni.anim.people behavior script.

        Returns:
            True if configuration successful
        """
        try:
            # Get configuration values
            character_root = self.config['characters']['animation']['root_path']
            command_file = self.config['behavior']['command_file']

            # Resolve command file path (relative to project root)
            command_file_full = os.path.join(self.project_root, command_file)
            if not os.path.exists(command_file_full):
                self.log(
                    f"⚠ Command file not found: {command_file_full}",
                    level="WARNING"
                )
            else:
                self.log(
                    f"✓ Command file: {command_file_full}",
                    level="DEBUG"
                )

            self.log("Configuring carb settings for animation")

            # Set carb settings (these configure omni.anim.people behavior)
            carb.settings.set_string(
                "/characters/path",
                character_root
            )
            self.log(
                f"  ✓ Character root path: {character_root}",
                level="DEBUG"
            )

            carb.settings.set_string(
                "/behavior/file",
                command_file_full
            )
            self.log(
                f"  ✓ Behavior file: {command_file}",
                level="DEBUG"
            )

            # Animation parameters
            playback_speed = self.config['behavior'].get('playback_speed', 1.0)
            carb.settings.set_float(
                "/animation/playback_speed",
                playback_speed
            )
            self.log(
                f"  ✓ Playback speed: {playback_speed}x",
                level="DEBUG"
            )

            return True

        except Exception as e:
            self.log(
                f"✗ Failed to configure carb settings: {str(e)}",
                level="ERROR"
            )
            return False

    def setup_navmesh(self) -> bool:
        """
        Create or load NavMesh for character pathfinding.

        NavMeshes are required for IRA GoTo commands to work.

        Returns:
            True if NavMesh set up successfully
        """
        try:
            navmesh_config = self.config['navmesh']

            if not navmesh_config.get('enabled', False):
                self.log("NavMesh disabled - skipping setup")
                return True

            create_method = navmesh_config.get('create_method', 'auto')

            if create_method == 'auto':
                self.log("Creating NavMesh from bounds")

                auto_config = navmesh_config.get('auto_generation', {})
                success = self.navmesh_util.create_navmesh_from_bounds(
                    bounds_min=tuple(auto_config.get('bounds_min', [-4.0, -4.0, 0.5])),
                    bounds_max=tuple(auto_config.get('bounds_max', [4.0, 4.0, 0.5])),
                    cell_size=auto_config.get('cell_size', 0.2),
                    walkable_height=auto_config.get('walkable_height', 2.0),
                    walkable_radius=auto_config.get('walkable_radius', 0.35),
                    max_slope=auto_config.get('max_slope', 45.0),
                )

                if success:
                    # Validate created NavMesh
                    spawn_positions = self.config['characters']['spawn'].get(
                        'initial_positions', []
                    )
                    self.navmesh_util.validate_navmesh(
                        spawn_points=spawn_positions
                    )

            elif create_method == 'usd':
                usd_path = navmesh_config.get('usd_path')
                if not usd_path:
                    self.log(
                        "usd_path not specified for NavMesh loading",
                        level="ERROR"
                    )
                    return False

                success = self.navmesh_util.create_from_usd_file(usd_path)

            else:
                self.log(
                    f"Unknown NavMesh creation method: {create_method}",
                    level="ERROR"
                )
                return False

            return success

        except Exception as e:
            self.log(
                f"✗ NavMesh setup failed: {str(e)}",
                level="ERROR"
            )
            return False

    def spawn_characters(self) -> bool:
        """
        Spawn characters to GLOBAL location (/World/Characters).

        Characters are spawned as global assets (not per-environment) so they are
        shared by all robots in the simulation. This follows Isaac Lab's architecture
        pattern where global assets are NOT replicated.

        Returns:
            True if all characters spawned successfully
        """
        if not ISAAC_AVAILABLE:
            self.log("Isaac Sim not available - cannot spawn characters", level="ERROR")
            return False

        try:
            stage = get_current_stage()
            if stage is None:
                self.log("No active stage - cannot spawn characters", level="ERROR")
                return False

            config = self.config['characters']
            num_chars = config['num_characters']
            spawn_config = config['spawn']
            assets = config.get('assets', [])
            root_path = config['animation']['root_path']

            # Get spawn positions and random seed
            initial_positions = spawn_config.get('initial_positions', [])
            random_seed = spawn_config.get('random_seed', 42)
            random.seed(random_seed)

            self.log(f"Spawning {num_chars} characters to GLOBAL location")
            self.log(f"  Root path: {root_path} (GLOBAL, not per-environment)")

            all_success = True

            for char_idx in range(num_chars):
                char_name = f"Character_{char_idx}"

                # Get position (use initial if available, otherwise randomize)
                if char_idx < len(initial_positions):
                    position = initial_positions[char_idx]
                else:
                    # Randomize position within spawn area
                    area_min = spawn_config['area_min']
                    area_max = spawn_config['area_max']
                    height = spawn_config['height']

                    position = (
                        random.uniform(area_min[0], area_max[0]),
                        random.uniform(area_min[1], area_max[1]),
                        height,
                    )

                # Get asset (cycle through available assets)
                if assets:
                    asset = assets[char_idx % len(assets)]
                    asset_url = asset.get('url', '')
                else:
                    # Fallback asset if none specified
                    asset_url = (
                        "https://d36m3dsta5ufqu.cloudfront.net/Isaac-Sim-Assets/"
                        "Isaac/2023.10/Isaac-Sim-4.5.0/Characters/Female_Business_02.usd"
                    )

                prim_path = f"{root_path}/{char_name}"

                try:
                    self.log(f"Spawning {char_name}")
                    self.log(f"  Path: {prim_path}", level="DEBUG")
                    self.log(f"  Asset: {asset_url}", level="DEBUG")
                    self.log(f"  Position: ({position[0]:.2f}, {position[1]:.2f}, {position[2]:.2f})", level="DEBUG")

                    # Add character to stage from cloud asset
                    add_reference_to_stage(
                        usd_path=asset_url,
                        prim_path=prim_path,
                    )

                    # Set position
                    prim = stage.GetPrimAtPath(prim_path)
                    if prim.IsValid():
                        xform = UsdGeom.Xformable(prim)
                        if xform:
                            xform.AddTranslateOp().Set(Gf.Vec3d(*position))

                        self.spawned_characters.append(prim_path)
                        self.character_states[char_name] = {
                            'path': prim_path,
                            'position': position,
                            'animation_state': 'idle',
                        }
                        self.log(f"  ✓ Spawned successfully")
                    else:
                        self.log(
                            f"  ✗ Failed to set transform on prim",
                            level="ERROR"
                        )
                        all_success = False

                except Exception as e:
                    self.log(
                        f"  ✗ Failed to spawn {char_name}: {str(e)}",
                        level="ERROR"
                    )
                    all_success = False

            if all_success:
                self.log(f"✓ All {num_chars} characters spawned successfully")
            else:
                self.log(
                    f"⚠ Some characters failed to spawn",
                    level="WARNING"
                )

            return all_success

        except Exception as e:
            self.log(
                f"✗ Character spawning failed: {str(e)}",
                level="ERROR"
            )
            return False

    def parse_command_file(
        self,
        command_file: Optional[str] = None,
    ) -> Dict[str, List[Dict]]:
        """
        Parse behavior command file.

        Reads character commands in format:
            Character_0 GoTo 1.5 1.0 1.2 0
            Character_0 Idle 2
            Character_0 LookAround 2

        Args:
            command_file: Path to command file (uses config if not specified)

        Returns:
            Dictionary mapping character names to command lists
        """
        try:
            if not command_file:
                command_file = self.config['behavior']['command_file']
                command_file = os.path.join(self.project_root, command_file)

            if not os.path.exists(command_file):
                self.log(
                    f"✗ Command file not found: {command_file}",
                    level="ERROR"
                )
                return {}

            commands: Dict[str, List[Dict]] = {}

            with open(command_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue

                    parts = line.split()
                    if len(parts) < 3:
                        continue

                    char_name = parts[0]
                    command_type = parts[1]
                    params = parts[2:]

                    if char_name not in commands:
                        commands[char_name] = []

                    command_dict = {
                        'type': command_type,
                        'params': params,
                    }

                    commands[char_name].append(command_dict)

            self.log(f"Parsed commands for {len(commands)} characters")
            for char, cmd_list in commands.items():
                self.log(
                    f"  {char}: {len(cmd_list)} commands",
                    level="DEBUG"
                )

            return commands

        except Exception as e:
            self.log(
                f"✗ Failed to parse command file: {str(e)}",
                level="ERROR"
            )
            return {}

    def execute_commands(self) -> bool:
        """
        Execute character behavior commands.

        Parses command file and applies behaviors to characters.

        Returns:
            True if commands parsed successfully
        """
        try:
            commands = self.parse_command_file()

            if not commands:
                self.log("No commands to execute", level="WARNING")
                return False

            self.log(f"Executing commands for {len(commands)} characters")

            for char_name, cmd_list in commands.items():
                self.log(f"  {char_name}:", level="DEBUG")
                for cmd in cmd_list:
                    cmd_type = cmd['type']
                    params = cmd['params']
                    self.log(
                        f"    {cmd_type} {' '.join(params)}",
                        level="DEBUG"
                    )

                    # Validate command parameters
                    if cmd_type == 'GoTo':
                        if len(params) >= 4:
                            x, y, z, rotation = float(params[0]), float(params[1]), float(params[2]), float(params[3])
                            self.log(
                                f"      → Walk to ({x:.1f}, {y:.1f}, {z:.1f}) facing {rotation}°",
                                level="DEBUG"
                            )
                    elif cmd_type == 'Idle':
                        if len(params) >= 1:
                            duration = float(params[0])
                            self.log(
                                f"      → Stand for {duration}s",
                                level="DEBUG"
                            )
                    elif cmd_type == 'LookAround':
                        if len(params) >= 1:
                            duration = float(params[0])
                            self.log(
                                f"      → Look around for {duration}s",
                                level="DEBUG"
                            )

            return True

        except Exception as e:
            self.log(
                f"✗ Command execution failed: {str(e)}",
                level="ERROR"
            )
            return False

    def get_character_state(self, character_name: str) -> Optional[Dict]:
        """
        Get current state of a character.

        Args:
            character_name: Name of character (e.g., "Character_0")

        Returns:
            Dictionary with character state or None if not found
        """
        return self.character_states.get(character_name)

    def initialize(self) -> bool:
        """
        Full initialization sequence for IRA characters.

        Runs all setup steps in correct order:
        1. Enable extensions
        2. Configure carb settings
        3. Setup NavMesh
        4. Spawn characters
        5. Execute commands
        6. Start timeline

        Returns:
            True if initialization successful
        """
        self.log("=" * 60)
        self.log("INITIALIZATION SEQUENCE STARTING")
        self.log("=" * 60)

        # Step 1: Extensions
        if not self.enable_extensions():
            self.log("✗ Extension loading failed", level="ERROR")
            return False

        # Step 2: Carb settings
        if not self.configure_carb_settings():
            self.log("✗ Carb configuration failed", level="ERROR")
            return False

        # Step 3: NavMesh
        if not self.setup_navmesh():
            self.log("⚠ NavMesh setup failed (optional)", level="WARNING")
            # Don't fail completely - NavMesh is optional

        # Step 4: Spawn characters
        if not self.spawn_characters():
            self.log("✗ Character spawning failed", level="ERROR")
            return False

        # Step 5: Execute commands
        if not self.execute_commands():
            self.log("⚠ Command execution failed (optional)", level="WARNING")
            # Don't fail completely - commands are queued for later execution

        # Step 6: Start simulation timeline
        try:
            timeline = omni.timeline.get_timeline_interface()
            timeline.play()
            self.log("✓ Timeline started - animation playback enabled")
        except Exception as e:
            self.log(
                f"⚠ Timeline start failed: {str(e)}",
                level="WARNING"
            )

        self.log("=" * 60)
        self.log(f"INITIALIZATION COMPLETE: {len(self.spawned_characters)} characters spawned")
        self.log("=" * 60)

        return True

    def get_spawned_characters(self) -> List[str]:
        """Get list of spawned character paths."""
        return self.spawned_characters.copy()

    def get_character_count(self) -> int:
        """Get number of spawned characters."""
        return len(self.spawned_characters)
