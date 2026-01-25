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

# Import NavMesh utilities (handle both package and standalone imports)
try:
    from people.navmesh_utils import NavMeshUtility
except ImportError:
    from navmesh_utils import NavMeshUtility

# Configure logging
_logger = logging.getLogger("[IRA People]")


def _lazy_import_isaac():
    """
    Lazily import Isaac Sim/Lab modules when needed.

    This allows the module to be imported in environments where Isaac Sim
    might not be available at import time, but IS available when we actually
    need to spawn characters.

    Uses direct omni APIs that are always available in Isaac Lab/Sim.

    Returns:
        tuple: (carb, omni, Usd, UsdGeom, Gf) or None
    """
    try:
        import carb
        _logger.debug("[_lazy_import_isaac] Successfully imported carb")
    except ImportError as e:
        _logger.error(f"[_lazy_import_isaac] Failed to import carb: {e}")
        return None

    try:
        import omni
        _logger.debug("[_lazy_import_isaac] Successfully imported omni")
    except ImportError as e:
        _logger.error(f"[_lazy_import_isaac] Failed to import omni: {e}")
        return None

    try:
        from pxr import Usd, UsdGeom, Gf
        _logger.debug("[_lazy_import_isaac] Successfully imported pxr modules")
    except ImportError as e:
        _logger.error(f"[_lazy_import_isaac] Failed to import pxr modules: {e}")
        return None

    return (carb, omni, Usd, UsdGeom, Gf)


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
    # See: https://docs.isaacsim.omniverse.nvidia.com/4.5.0/replicator_tutorials/tutorial_replicator_agent.html
    EXTENSION_LOAD_ORDER = [
        # Animation extensions (required for character control)
        "omni.anim.graph.schema",          # Schema FIRST
        "omni.anim.graph.core",
        "omni.anim.navigation.schema",
        "omni.anim.navigation.core",

        # IRA extensions (official names from Isaac Sim 4.5)
        "isaacsim.replicator.agent.core",  # Core IRA extension (CORRECT NAME)
        # NOTE: Removed isaacsim.replicator.agent.ui - SDG window interferes with animation

        # Scripting support
        "omni.kit.scripting",
        "omni.anim.people",                # People extension for character animation
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
        # Lazy import - Isaac Sim should be available when this is called
        isaac_imports = _lazy_import_isaac()
        if isaac_imports is None:
            self.log("Isaac Sim not available", level="ERROR")
            return False

        carb, omni, Usd, UsdGeom, Gf = isaac_imports

        self.log(f"Enabling {len(self.EXTENSION_LOAD_ORDER)} extensions for IRA")

        all_success = True
        for ext_name in self.EXTENSION_LOAD_ORDER:
            try:
                # Get extension manager using correct API
                app = omni.kit.app.get_app()
                ext_manager = app.get_extension_manager()
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
            # Lazy import carb
            isaac_imports = _lazy_import_isaac()
            if isaac_imports is None:
                self.log("Isaac Sim not available - skipping carb configuration", level="WARNING")
                return True  # Not critical

            carb, omni, Usd, UsdGeom, Gf = isaac_imports

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

            # Try to set carb settings (CRITICAL for behavior script to find characters)
            try:
                settings = carb.settings.get_settings()

                # Set CORRECT carb setting paths for omni.anim.people behavior script
                # Command file path
                settings.set(
                    "/exts/omni.anim.people/command_settings/command_file_path",
                    command_file_full
                )
                self.log(f"  ✓ Command file: {command_file_full}", level="DEBUG")

                # Character prim path (CRITICAL - this is where behavior script looks for characters)
                settings.set(
                    "/persistent/exts/omni.anim.people/character_prim_path",
                    character_root
                )
                self.log(f"  ✓ Character prim path: {character_root}", level="DEBUG")

                # Navigation settings
                settings.set(
                    "/exts/omni.anim.people/navigation_settings/navmesh_enabled",
                    self.config['navmesh'].get('enabled', False)
                )
                settings.set(
                    "/exts/omni.anim.people/navigation_settings/dynamic_avoidance_enabled",
                    True
                )

                # Command looping
                loop_value = "inf" if self.config['behavior'].get('loop_commands', True) else "1"
                settings.set(
                    "/exts/omni.anim.people/command_settings/number_of_loop",
                    loop_value
                )

                self.log(f"  ✓ Carb settings configured correctly", level="DEBUG")
            except Exception as e:
                self.log(
                    f"  ⚠ Carb settings failed (non-critical): {str(e)}",
                    level="DEBUG"
                )

            # Always return True - carb configuration is optional
            return True

        except Exception as e:
            self.log(
                f"⚠ Carb configuration error (non-critical): {str(e)}",
                level="DEBUG"
            )
            return True  # Still return True - carb is optional

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
        # Lazy import
        isaac_imports = _lazy_import_isaac()
        if isaac_imports is None:
            self.log("Isaac Sim not available - cannot spawn characters", level="ERROR")
            return False

        carb, omni, Usd, UsdGeom, Gf = isaac_imports

        try:
            # Get stage using omni API (same as diagnose_stage.py uses)
            stage = omni.usd.get_context().get_stage()
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

            # Get asset root from carb settings (same approach as people_spawner.py)
            # This ensures Isaac Sim resolves paths correctly
            asset_root = None
            try:
                settings = carb.settings.get_settings()
                # Try cloud path first (Isaac Sim 5.0 default)
                asset_root = settings.get("/persistent/isaac/asset_root/cloud")
                if not asset_root:
                    # Try default path
                    asset_root = settings.get("/persistent/isaac/asset_root/default")
                if asset_root:
                    self.log(f"Using asset root: {asset_root}", level="DEBUG")
            except Exception as e:
                self.log(f"Could not get carb asset settings: {str(e)}", level="DEBUG")

            self.log(f"Spawning {num_chars} characters to GLOBAL location")
            self.log(f"  Root path: {root_path} (GLOBAL, not per-environment)")

            # CRITICAL: Create parent prim directory if it doesn't exist
            try:
                root_prim = stage.GetPrimAtPath(root_path)
                if not root_prim.IsValid():
                    self.log(f"Creating parent prim: {root_path}")
                    # Create parent prim using USD API
                    root_prim = stage.DefinePrim(root_path, "Xform")
                    self.log(f"✓ Parent prim created: {root_path}")
            except Exception as e:
                self.log(f"⚠ Failed to create parent prim: {str(e)}", level="WARNING")
                # Continue anyway - maybe it exists

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
                    asset_path = asset.get('url', '')
                else:
                    # Fallback asset if none specified
                    asset_path = "/Isaac/People/Characters/female_adult_police_02/female_adult_police_02.usd"

                # Build full asset URL
                if asset_root:
                    # Append relative path to asset root
                    # asset_root looks like: https://.../Assets/Isaac/5.0
                    # asset_path is like: Isaac/People/Characters/[name]/[name].usd
                    asset_url = f"{asset_root}/{asset_path}"
                else:
                    # No asset root available - use cloud fallback
                    asset_url = f"https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/4.0/{asset_path}"

                prim_path = f"{root_path}/{char_name}"

                try:
                    self.log(f"Spawning {char_name}")
                    self.log(f"  Path: {prim_path}", level="DEBUG")
                    self.log(f"  Asset: {asset_url}", level="DEBUG")
                    self.log(f"  Position: ({position[0]:.2f}, {position[1]:.2f}, {position[2]:.2f})", level="DEBUG")

                    # Create prim and add asset reference
                    char_prim = stage.DefinePrim(prim_path, "Xform")
                    char_prim.GetReferences().AddReference(asset_url)

                    # Set position using transform operation
                    xform = UsdGeom.Xformable(char_prim)
                    xform.ClearXformOpOrder()
                    xform.AddTranslateOp().Set(Gf.Vec3d(*position))

                    # Track spawned character
                    self.spawned_characters.append(prim_path)
                    self.character_states[char_name] = {
                        'path': prim_path,
                        'position': position,
                        'animation_state': 'idle',
                    }
                    self.log(f"  ✓ Spawned successfully")

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

    def setup_character_animation(self, stage, char_prim) -> bool:
        """
        Setup animation for a character by attaching the behavior script.

        This enables the character to execute commands from the command file
        (GoTo, Idle, LookAround, etc).

        Note: This is called AFTER setup_animation_graph(), so the animation
        graph is already applied. This step just attaches the behavior script.
        """
        try:
            from pxr import Usd, UsdSkel, Sdf
            import omni.kit.commands
            import omni.kit.app

            # Lazy import Isaac modules
            isaac_imports = _lazy_import_isaac()
            if isaac_imports is None:
                self.log("Isaac Sim not available - cannot setup character animation", level="WARNING")
                return False

            carb, omni_module, Usd_module, UsdGeom, Gf = isaac_imports

            char_path = str(char_prim.GetPath())
            self.log(f"Setting up animation behavior for {char_path}", level="DEBUG")

            # Find SkelRoot prims (skeleton root for the character)
            skel_roots = []
            for prim in Usd.PrimRange(char_prim):
                if prim.IsA(UsdSkel.Root):
                    skel_roots.append(prim)

            if not skel_roots:
                self.log(f"  ⚠ No SkelRoot found in {char_path}", level="WARNING")
                return False

            self.log(f"  ✓ Found {len(skel_roots)} SkelRoot(s)", level="DEBUG")

            # Get behavior script path from omni.anim.people extension
            try:
                ext_manager = omni.kit.app.get_app().get_extension_manager()
                ext_path = ext_manager.get_extension_path_by_module("omni.anim.people")
                if ext_path:
                    script_path = f"{ext_path}/omni/anim/people/scripts/character_behavior.py"
                    self.log(f"  ✓ Behavior script: {script_path}", level="DEBUG")
                else:
                    self.log(f"  ⚠ Could not find omni.anim.people extension", level="WARNING")
                    # Non-critical - continue anyway
            except Exception as e:
                self.log(f"  ⚠ Error getting script path: {str(e)}", level="WARNING")
                # Non-critical - continue anyway
                script_path = None

            # Attach behavior script to each SkelRoot
            success_count = 0
            for skel_root in skel_roots:
                skel_path = str(skel_root.GetPath())
                try:
                    self.log(f"    Processing {skel_path}", level="DEBUG")

                    # Try to apply Scripting API (if available)
                    try:
                        omni.kit.commands.execute(
                            "ApplyScriptingAPICommand",
                            paths=[Sdf.Path(skel_path)],
                        )
                        self.log(f"    ✓ Scripting API applied", level="DEBUG")
                    except Exception as api_err:
                        self.log(f"    ⚠ Scripting API apply failed (non-critical): {str(api_err)}", level="DEBUG")

                    # Attach behavior script if we have the path
                    if script_path:
                        try:
                            scripts_attr = skel_root.GetAttribute("omni:scripting:scripts")
                            if not scripts_attr:
                                scripts_attr = skel_root.CreateAttribute(
                                    "omni:scripting:scripts",
                                    Sdf.ValueTypeNames.StringArray
                                )

                            existing = scripts_attr.Get() or []
                            if script_path not in existing:
                                scripts_attr.Set([script_path])
                                self.log(f"    ✓ Behavior script attached", level="DEBUG")
                            else:
                                self.log(f"    ✓ Behavior script already attached", level="DEBUG")

                            success_count += 1
                        except Exception as script_err:
                            self.log(f"    ⚠ Error attaching script: {str(script_err)}", level="DEBUG")
                    else:
                        self.log(f"    ⚠ Script path not available, skipping attachment", level="DEBUG")

                except Exception as e:
                    self.log(f"    ⚠ Error processing {skel_path}: {str(e)}", level="DEBUG")

            if success_count > 0:
                self.log(f"  ✓ Animation setup complete for {char_path} ({success_count} skelroots)", level="DEBUG")
                return True
            else:
                self.log(f"  ⚠ No skelroots successfully configured", level="WARNING")
                return False

        except Exception as e:
            self.log(f"  ⚠ Failed to setup animation: {str(e)}", level="WARNING")
            return False

    def setup_animation_graph(self) -> bool:
        """
        Setup animation graph for spawned characters.

        This is the CRITICAL step that enables character animation by applying
        the animation graph (state machine) to character skelroots.

        Without this step:
        - ag.get_character() returns None in behavior script
        - Characters remain in T-pose
        - Commands are parsed but not executed

        Must be called AFTER spawning but BEFORE behavior script attachment.

        Returns:
            True if animation graph setup succeeded.
        """
        try:
            # CRITICAL: Import omni and other modules needed in this method
            isaac_imports = _lazy_import_isaac()
            if isaac_imports is None:
                self.log("Isaac Sim not available - cannot setup animation graph", level="ERROR")
                return False

            carb, omni, Usd, UsdGeom, Gf = isaac_imports

            from isaacsim.replicator.agent.core.stage_util import CharacterUtil
            from omni.anim.people.scripts.custom_command.populate_anim_graph import populate_anim_graph
            from pxr import UsdSkel

            self.log("Setting up animation graph for characters", level="INFO")

            # Step 1: Load default biped template with animation graph
            biped_prim = CharacterUtil.load_default_biped_to_stage()
            self.log("  ✓ Loaded biped template", level="DEBUG")

            # Step 2: Populate animation graph state machine (Idle, GoTo, Custom commands)
            populate_anim_graph()
            self.log("  ✓ Populated animation graph state machine", level="DEBUG")

            # Step 3: Get animation graph from biped
            anim_graph = CharacterUtil.get_anim_graph_from_character(biped_prim)
            if not anim_graph:
                self.log("  ✗ Could not get animation graph from biped", level="ERROR")
                return False

            # Step 4: Find skelroots INSIDE the spawned character prims
            # The skelroots are NOT at the top level - they're inside each loaded character asset
            character_skelroots = []
            stage = omni.usd.get_context().get_stage()

            for char_path in self.spawned_characters:
                char_prim = stage.GetPrimAtPath(char_path)
                if char_prim.IsValid():
                    # Look for SkelRoot prims inside this character
                    # They typically have names like "ManRoot" or similar
                    self._find_skelroots_recursive(char_prim, character_skelroots)

            if not character_skelroots:
                self.log("  ✗ No character skelroots found in spawned characters", level="ERROR")
                return False

            self.log(f"  ✓ Found {len(character_skelroots)} skelroot(s)", level="DEBUG")

            # Step 5: Apply animation graph to each character skelroot
            # THIS IS CRITICAL - without this, animation system doesn't work
            CharacterUtil.setup_animation_graph_to_character(
                character_skelroots,
                anim_graph
            )
            self.log("  ✓ Applied animation graph to all character skelroots", level="DEBUG")

            self.log("✓ Animation graph setup complete", level="INFO")
            return True

        except ImportError as e:
            self.log(f"⚠ IRA utilities not available (non-critical): {str(e)}", level="WARNING")
            return False
        except Exception as e:
            self.log(f"⚠ Animation graph setup failed: {str(e)}", level="WARNING")
            import traceback
            traceback.print_exc()
            return False

    def _find_skelroots_recursive(self, prim, skelroots_list: List) -> None:
        """
        Recursively search for SkelRoot prims within a character prim hierarchy.

        SkelRoot prims define the skeleton structure for animation and are typically
        found inside character USD assets (e.g., /World/Characters/Character_0/ManRoot).

        Args:
            prim: The prim to search (typically a character prim)
            skelroots_list: List to accumulate found SkelRoot prim paths (modified in-place)
        """
        try:
            # Import Sdf for type checking
            isaac_imports = _lazy_import_isaac()
            if isaac_imports is None:
                return

            carb, omni, Usd, UsdGeom, Gf = isaac_imports
            from pxr import Sdf

            # Check if this prim is a SkelRoot
            if prim.GetTypeName() == "SkelRoot":
                skelroot_path = Sdf.Path(prim.GetPath())
                skelroots_list.append(skelroot_path)
                self.log(f"    Found SkelRoot: {prim.GetPath()}", level="DEBUG")

            # Recurse into children
            for child in prim.GetChildren():
                self._find_skelroots_recursive(child, skelroots_list)

        except Exception as e:
            self.log(f"    ⚠ Error in skelroot search: {str(e)}", level="DEBUG")
            # Continue anyway - don't let search errors block initialization

    def initialize(self) -> bool:
        """
        Full initialization sequence for IRA characters.

        Runs all setup steps in correct order:
        1. Enable extensions
        2. Configure carb settings
        3. Setup NavMesh
        4. Spawn characters
        5. Setup animation graph (CRITICAL - applies animation state machine)
        6. Attach behavior scripts
        7. Execute commands
        8. Start timeline

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

        # Step 5: Setup animation graph (CRITICAL - applies animation state machine)
        if not self.setup_animation_graph():
            self.log("⚠ Animation graph setup failed (continuing anyway)", level="WARNING")
            # Don't fail completely - characters may still work with behavior scripts only

        # Step 6: Setup character animation (CRITICAL - attaches behavior script)
        # Get stage for animation setup
        isaac_imports = _lazy_import_isaac()
        if isaac_imports is not None:
            carb, omni, Usd, UsdGeom, Gf = isaac_imports
            stage = omni.usd.get_context().get_stage()
            if stage is not None:
                for char_path in self.spawned_characters:
                    char_prim = stage.GetPrimAtPath(char_path)
                    if char_prim.IsValid():
                        self.setup_character_animation(stage, char_prim)
                        self.log(f"  ✓ Animation setup for {char_path}", level="DEBUG")

        # Step 7: Execute commands
        if not self.execute_commands():
            self.log("⚠ Command execution failed (optional)", level="WARNING")
            # Don't fail completely - commands are queued for later execution

        # Step 8: Start simulation timeline
        try:
            isaac_imports = _lazy_import_isaac()
            if isaac_imports is not None:
                carb, omni, Usd, UsdGeom, Gf = isaac_imports
                timeline = omni.timeline.get_timeline_interface()
                timeline.play()
                self.log("✓ Timeline started - animation playback enabled")
            else:
                self.log("⚠ Cannot start timeline - Isaac Sim not available", level="WARNING")
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
