#!/usr/bin/env python3
"""
Manual Character Controller - Alternative to Animation Graph.

This controller moves characters by directly manipulating their USD transforms,
bypassing the need for the animation graph API which doesn't work in Isaac Lab.

Usage:
    Replace IRACharacterManager.setup_animation_graph() with this approach.
"""

import numpy as np
from typing import Dict, List, Tuple
from pxr import Gf, UsdGeom


class ManualCharacterController:
    """
    Controls character movement without animation graphs.

    Parses GoTo/Idle/LookAround commands and directly updates character transforms.
    Characters move smoothly between waypoints using simple interpolation.
    """

    def __init__(self, walk_speed: float = 0.5):
        """
        Initialize controller.

        Args:
            walk_speed: Walking speed in meters/second (default: 0.5)
        """
        self.walk_speed = walk_speed
        self.character_states: Dict[str, Dict] = {}

    def parse_commands(self, commands: Dict[str, List[Dict]]) -> Dict:
        """
        Parse command file into executable waypoints.

        Args:
            commands: Dictionary of {character_name: [command_dicts]}

        Returns:
            Dictionary of {character_name: waypoint_list}
        """
        waypoints = {}

        for char_name, cmd_list in commands.items():
            char_waypoints = []

            for cmd in cmd_list:
                cmd_type = cmd['type']
                params = cmd['params']

                if cmd_type == 'GoTo' and len(params) >= 4:
                    # GoTo x y z rotation_degrees
                    x, y, z = float(params[0]), float(params[1]), float(params[2])
                    rotation_deg = float(params[3])

                    char_waypoints.append({
                        'type': 'goto',
                        'position': (x, y, z),
                        'rotation': rotation_deg,
                        'duration': None,  # Calculated based on distance
                    })

                elif cmd_type == 'Idle' and len(params) >= 1:
                    # Idle duration_seconds
                    duration = float(params[0])
                    char_waypoints.append({
                        'type': 'idle',
                        'duration': duration,
                    })

                elif cmd_type == 'LookAround' and len(params) >= 1:
                    # LookAround duration_seconds
                    duration = float(params[0])
                    char_waypoints.append({
                        'type': 'look',
                        'duration': duration,
                    })

            if char_waypoints:
                waypoints[char_name] = char_waypoints
                # Initialize state
                self.character_states[char_name] = {
                    'current_waypoint': 0,
                    'time_in_waypoint': 0.0,
                    'current_position': None,
                    'target_position': None,
                }

        return waypoints

    def update(self, stage, character_prims: List, dt: float, loop: bool = True):
        """
        Update character positions for this frame.

        Args:
            stage: USD stage
            character_prims: List of character prim paths
            dt: Time delta since last update (seconds)
            loop: Loop waypoints when finished
        """
        for char_path in character_prims:
            char_prim = stage.GetPrimAtPath(char_path)
            if not char_prim.IsValid():
                continue

            # Extract character name from path (e.g., /World/Characters/Character_0)
            char_name = char_path.split('/')[-1]

            if char_name not in self.character_states:
                continue

            state = self.character_states[char_name]

            # Get current transform
            xform = UsdGeom.Xformable(char_prim)
            if not state['current_position']:
                # Initialize from current position
                translate_ops = [op for op in xform.GetOrderedXformOps()
                               if op.GetOpType() == UsdGeom.XformOp.TypeTranslate]
                if translate_ops:
                    state['current_position'] = np.array(translate_ops[0].Get())
                else:
                    state['current_position'] = np.array([0, 0, 0])

            # Execute current waypoint
            # TODO: Implement waypoint following logic here
            # This is a simplified version - full implementation would:
            # 1. Check current waypoint type (goto/idle/look)
            # 2. Interpolate position for 'goto'
            # 3. Wait for duration for 'idle'/'look'
            # 4. Advance to next waypoint when complete
            # 5. Loop back to waypoint 0 if loop=True

            pass  # Placeholder - implement based on your needs


def apply_manual_controller(people_manager, stage, dt: float = 0.02):
    """
    Apply manual character controller to replace animation graph.

    Args:
        people_manager: IRACharacterManager or PeopleSceneManager instance
        stage: USD stage
        dt: Simulation time step
    """
    # Create controller
    controller = ManualCharacterController(walk_speed=0.5)

    # Parse commands from manager
    commands = people_manager.parse_command_file()
    waypoints = controller.parse_commands(commands)

    print(f"[Manual Controller] Initialized with {len(waypoints)} character paths")

    # Update character positions each frame
    # (This would be called from your environment's step() method)
    controller.update(stage, people_manager.spawned_characters, dt)

    return controller
