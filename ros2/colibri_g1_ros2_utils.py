"""Utility functions for ROS2 bridge.

This module provides helper functions for message conversions and common operations.
"""

import torch
import numpy as np
from geometry_msgs.msg import Quaternion, Vector3, Point
from rclpy.time import Time as ROSTime


def torch_to_ros_vector3(tensor: torch.Tensor) -> Vector3:
    """Convert PyTorch tensor to ROS Vector3.

    Args:
        tensor: PyTorch tensor with 3 elements [x, y, z]

    Returns:
        Vector3: ROS geometry_msgs/Vector3
    """
    msg = Vector3()
    msg.x = float(tensor[0])
    msg.y = float(tensor[1])
    msg.z = float(tensor[2])
    return msg


def torch_to_ros_quaternion(tensor: torch.Tensor) -> Quaternion:
    """Convert PyTorch tensor to ROS Quaternion.

    Args:
        tensor: PyTorch tensor with 4 elements [w, x, y, z] (Isaac Lab format)

    Returns:
        Quaternion: ROS geometry_msgs/Quaternion
    """
    msg = Quaternion()
    msg.w = float(tensor[0])
    msg.x = float(tensor[1])
    msg.y = float(tensor[2])
    msg.z = float(tensor[3])
    return msg


def torch_to_ros_point(tensor: torch.Tensor) -> Point:
    """Convert PyTorch tensor to ROS Point.

    Args:
        tensor: PyTorch tensor with 3 elements [x, y, z]

    Returns:
        Point: ROS geometry_msgs/Point
    """
    msg = Point()
    msg.x = float(tensor[0])
    msg.y = float(tensor[1])
    msg.z = float(tensor[2])
    return msg


def sim_time_to_ros_time(sim_time: float) -> ROSTime:
    """Convert simulation time to ROS time.

    Args:
        sim_time: Simulation time (seconds)

    Returns:
        ROSTime: ROS timestamp
    """
    sec = int(sim_time)
    nanosec = int((sim_time - sec) * 1e9)
    return ROSTime(seconds=sec, nanoseconds=nanosec)


def compute_euclidean_distance(pos1: torch.Tensor, pos2: torch.Tensor) -> float:
    """Compute Euclidean distance between two positions.

    Args:
        pos1: First position tensor [x, y, z] or [x, y]
        pos2: Second position tensor [x, y, z] or [x, y]

    Returns:
        float: Euclidean distance
    """
    diff = pos1 - pos2
    return float(torch.norm(diff))


# TODO Phase 6.1: Add more utility functions as needed
# TODO Phase 6.4: Add sensor data conversion utilities
