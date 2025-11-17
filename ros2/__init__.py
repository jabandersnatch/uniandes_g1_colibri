"""ROS2 bridge module for Colibri G1 digital twin.

This module provides ROS2 integration for sim2sim transfer and future sim2real deployment.
"""

__version__ = "0.1.0"

from .colibri_g1_ros2_bridge import RobotDataManager
from .colibri_g1_ros2_utils import *

__all__ = ["RobotDataManager"]
