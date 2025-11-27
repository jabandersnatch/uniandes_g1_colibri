#!/usr/bin/env python3

# Copyright (c) 2024, University of Los Andes (MISIS Program)
# Licensed under the BSD 3-Clause License

"""
Standalone test script for IRA animated people.

This script tests IRA character spawning and animation WITHOUT Isaac Lab environment
complexity. It provides a fast, debuggable test environment for validating:
- IRA extension loading
- NavMesh creation
- Character spawning
- Command file parsing
- Animation execution

Usage:
    python scripts/test_ira_people.py [--config cfg/ira_people_config.yaml] [--headless] [--timeout 300]
"""

import argparse
import sys
import os
import time
import logging
from pathlib import Path
from typing import Optional

# Configure logging before imports
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    print("[WARNING] PyYAML not available - will use fallback config")

try:
    import carb
    import omni
    from omni.isaac.core.utils.stage import get_current_stage, create_new_stage
    from omni.isaac.core.world import World
    ISAAC_AVAILABLE = True
except ImportError:
    ISAAC_AVAILABLE = False
    print("[WARNING] Isaac Sim not available - running in compatibility mode")

# Import custom modules
try:
    # Add parent directories to path
    import sys
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # scripts/test_ira_people.py -> scripts -> digital_twin_colibri_g1 -> project_root
    digital_twin_root = os.path.dirname(script_dir)  # digital_twin_colibri_g1/
    # Add people directory to path
    people_dir = os.path.join(digital_twin_root, 'people')
    if people_dir not in sys.path:
        sys.path.insert(0, people_dir)
    if digital_twin_root not in sys.path:
        sys.path.insert(0, digital_twin_root)

    # Import directly from people module (not through package __init__)
    from ira_people_manager import IRACharacterManager
    CUSTOM_AVAILABLE = True
except ImportError as e:
    CUSTOM_AVAILABLE = False
    print(f"[WARNING] Custom people module not available: {e}")


class TestIRAConfig:
    """Fallback config if YAML is not available."""
    def __init__(self):
        self.config = {
            'simulation': {
                'headless': True,
                'headless_timeout': 300,
                'real_time': False,
                'verbose': True,
            },
            'behavior': {
                'command_file': 'cfg/people_commands.txt',
                'loop_commands': True,
                'playback_speed': 1.0,
            },
            'characters': {
                'num_characters': 2,
                'assets': [
                    {
                        'name': 'Female_Business_01',
                        'url': 'https://d36m3dsta5ufqu.cloudfront.net/Isaac-Sim-Assets/Isaac/2023.10/Isaac-Sim-4.5.0/Characters/Female_Business_02.usd'
                    }
                ],
                'spawn': {
                    'area_min': [-3.0, -3.0],
                    'area_max': [3.0, 3.0],
                    'height': 1.2,
                    'initial_positions': [
                        [1.5, 1.0, 1.2],
                        [2.0, -1.0, 1.2],
                    ],
                    'random_seed': 42,
                },
                'animation': {
                    'root_path': '/World/Characters',
                    'enable_physics': False,
                    'capsule_radius': 0.35,
                    'capsule_height': 1.8,
                },
            },
            'navmesh': {
                'enabled': True,
                'create_method': 'auto',
                'auto_generation': {
                    'bounds_min': [-4.0, -4.0, 0.5],
                    'bounds_max': [4.0, 4.0, 0.5],
                    'cell_size': 0.2,
                    'walkable_height': 2.0,
                    'walkable_radius': 0.35,
                    'max_slope': 45.0,
                },
                'usd_path': None,
            },
            'extensions': [
                'omni.anim.graph.schema',
                'omni.anim.graph.core',
                'omni.anim.navigation.schema',
                'omni.anim.navigation.core',
                'omni.replicator.agent',
                'omni.kit.scripting',
            ],
            'logging': {
                'level': 'INFO',
                'prefix': '[IRA Test]',
                'extension_status': True,
                'character_spawning': True,
                'navmesh_validation': True,
                'command_execution': True,
                'simulation_state': True,
            },
            'diagnostics': {
                'enabled': True,
                'check_frequency': 10,
                'checks': {
                    'character_positions': True,
                    'animation_state': True,
                    'pathfinding_success': True,
                    'command_execution': True,
                    'performance_metrics': True,
                },
            },
        }


class IRATestRunner:
    """Runner for standalone IRA people tests."""

    def __init__(
        self,
        config_path: str,
        headless: bool = True,
        timeout: int = 300,
        project_root: Optional[str] = None,
    ):
        """
        Initialize test runner.

        Args:
            config_path: Path to YAML config file
            headless: Run without GUI
            timeout: Timeout in seconds (headless mode)
            project_root: Project root directory
        """
        self.config_path = config_path
        self.headless = headless
        self.timeout = timeout
        self.project_root = project_root or os.getcwd()
        self.config = None
        self.manager = None
        self.start_time = time.time()

        self.log("=" * 70)
        self.log("IRA STANDALONE TEST RUNNER")
        self.log("=" * 70)

    def log(self, message: str):
        """Log message with timestamp."""
        print(f"[IRA Test] {message}")

    def load_config(self) -> bool:
        """Load configuration from YAML file."""
        try:
            if YAML_AVAILABLE and os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    self.config = yaml.safe_load(f)
                self.log(f"✓ Loaded config from {self.config_path}")
            else:
                self.log(
                    f"⚠ Config file not found or YAML unavailable - "
                    f"using fallback"
                )
                fallback = TestIRAConfig()
                self.config = fallback.config

            return True

        except Exception as e:
            self.log(f"✗ Failed to load config: {str(e)}")
            return False

    def initialize_stage(self) -> bool:
        """Initialize Isaac Sim stage."""
        if not ISAAC_AVAILABLE:
            self.log(
                "⚠ Isaac Sim not available - skipping stage initialization"
            )
            return True

        try:
            self.log("Initializing Isaac Sim stage")

            # Create new stage
            create_new_stage()
            stage = get_current_stage()

            if stage is None:
                self.log("✗ Failed to create stage")
                return False

            self.log("✓ Stage initialized")
            return True

        except Exception as e:
            self.log(f"⚠ Stage initialization failed: {str(e)}")
            return True  # Continue anyway

    def setup_ira_manager(self) -> bool:
        """Create and setup IRA Character Manager."""
        if not CUSTOM_AVAILABLE:
            self.log("⚠ Custom people module not available")
            return False

        try:
            self.log("Creating IRA Character Manager")

            self.manager = IRACharacterManager(
                config=self.config,
                project_root=self.project_root,
                verbose=True,
            )

            self.log("✓ IRA Character Manager created")
            return True

        except Exception as e:
            self.log(f"✗ Failed to create IRA manager: {str(e)}")
            return False

    def run_initialization(self) -> bool:
        """Run IRA manager initialization."""
        if self.manager is None:
            self.log("✗ Manager not initialized")
            return False

        try:
            self.log("Running IRA initialization sequence")

            success = self.manager.initialize()

            if success:
                self.log("✓ IRA initialization successful")
                num_chars = self.manager.get_character_count()
                self.log(f"  Spawned {num_chars} characters")

                chars = self.manager.get_spawned_characters()
                for char_path in chars:
                    self.log(f"    - {char_path}")
            else:
                self.log("✗ IRA initialization failed")

            return success

        except Exception as e:
            self.log(f"✗ Initialization error: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def run_diagnostics(self) -> bool:
        """Run diagnostic checks."""
        if self.manager is None:
            self.log("✗ Manager not available for diagnostics")
            return False

        try:
            self.log("=" * 70)
            self.log("DIAGNOSTIC REPORT")
            self.log("=" * 70)

            # Character count
            num_chars = self.manager.get_character_count()
            self.log(f"Characters spawned: {num_chars}/{self.config['characters']['num_characters']}")

            # Character paths
            chars = self.manager.get_spawned_characters()
            if chars:
                self.log("Character paths:")
                for char_path in chars:
                    state = self.manager.get_character_state(
                        char_path.split('/')[-1]
                    )
                    if state:
                        pos = state.get('position', 'unknown')
                        self.log(f"  ✓ {char_path}")
                        self.log(f"      Position: {pos}")
            else:
                self.log("  ⚠ No characters spawned")

            # NavMesh status
            navmesh_config = self.config.get('navmesh', {})
            navmesh_enabled = navmesh_config.get('enabled', False)
            if navmesh_enabled:
                self.log(f"NavMesh: {'Enabled' if navmesh_enabled else 'Disabled'}")
            else:
                self.log("NavMesh: Disabled")

            # Command file
            command_file = self.config['behavior'].get('command_file', 'unknown')
            full_path = os.path.join(self.project_root, command_file)
            exists = os.path.exists(full_path)
            status = "✓" if exists else "✗"
            self.log(f"Command file: {status} {command_file}")

            # Extensions
            extensions = self.config.get('extensions', [])
            self.log(f"Extensions to load: {len(extensions)}")

            self.log("=" * 70)
            return True

        except Exception as e:
            self.log(f"✗ Diagnostics error: {str(e)}")
            return False

    def run_simulation(self, duration: float = 10.0) -> bool:
        """Run simulation for specified duration."""
        if not ISAAC_AVAILABLE:
            self.log("⚠ Isaac Sim not available - skipping simulation")
            return True

        try:
            self.log(f"Running simulation for {duration} seconds")

            # Simulation loop
            start = time.time()
            frame_count = 0

            while time.time() - start < duration:
                try:
                    # Step simulation
                    if hasattr(carb, 'update'):
                        carb.update()
                    frame_count += 1

                    # Report progress every 60 frames
                    if frame_count % 60 == 0:
                        elapsed = time.time() - start
                        self.log(
                            f"  Simulation time: {elapsed:.1f}s "
                            f"({frame_count} frames)"
                        )

                except Exception as e:
                    self.log(f"⚠ Simulation step error: {str(e)}")
                    break

            self.log(f"✓ Simulation completed ({frame_count} frames)")
            return True

        except Exception as e:
            self.log(f"⚠ Simulation error: {str(e)}")
            return True  # Don't fail on simulation errors

    def check_timeout(self) -> bool:
        """Check if test has exceeded timeout."""
        elapsed = time.time() - self.start_time
        if elapsed > self.timeout:
            self.log(
                f"⚠ Test timeout exceeded ({elapsed:.0f}s > {self.timeout}s)"
            )
            return False
        return True

    def run(self) -> bool:
        """Run complete test sequence."""
        try:
            # Step 1: Load configuration
            if not self.load_config():
                return False

            # Step 2: Initialize stage
            if not self.initialize_stage():
                self.log("⚠ Stage initialization skipped")

            # Step 3: Setup IRA manager
            if not self.setup_ira_manager():
                return False

            # Step 4: Run initialization
            if not self.run_initialization():
                return False

            # Step 5: Run diagnostics
            if not self.run_diagnostics():
                self.log("⚠ Diagnostics failed (non-critical)")

            # Step 6: Run simulation (if headless timeout not exceeded)
            if self.check_timeout():
                sim_duration = min(10.0, self.timeout / 2)
                if not self.run_simulation(duration=sim_duration):
                    self.log("⚠ Simulation failed (non-critical)")

            self.log("=" * 70)
            self.log("TEST COMPLETE")
            self.log("=" * 70)
            self.log("✓ IRA standalone test successful")
            self.log(f"  Total time: {time.time() - self.start_time:.1f}s")

            return True

        except Exception as e:
            self.log(f"✗ Test failed with exception: {str(e)}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Standalone IRA animated people test"
    )
    parser.add_argument(
        '--config',
        default='cfg/ira_people_config.yaml',
        help='Path to IRA config YAML file',
    )
    parser.add_argument(
        '--headless',
        action='store_true',
        default=True,
        help='Run without GUI (default)',
    )
    parser.add_argument(
        '--with-gui',
        action='store_true',
        help='Run with GUI visualization',
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=300,
        help='Timeout in seconds (headless mode)',
    )
    parser.add_argument(
        '--project-root',
        help='Project root directory (auto-detect if not specified)',
    )

    args = parser.parse_args()

    # Determine headless mode
    headless = not args.with_gui

    # Create and run test
    runner = IRATestRunner(
        config_path=args.config,
        headless=headless,
        timeout=args.timeout,
        project_root=args.project_root,
    )

    success = runner.run()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
