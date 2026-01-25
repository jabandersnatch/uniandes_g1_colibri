"""Utility functions for ROS2 bridge.

This module provides helper functions for message conversions and common operations.
Includes support for both standard ROS2 messages and Unitree G1 message types.

Reference: unitree_ros2/cyclonedds_ws/src/unitree/unitree_hg/msg/
"""

import math

import numpy as np
import torch
from geometry_msgs.msg import Point, Quaternion, Vector3
from rclpy.time import Time as ROSTime

# Unitree G1 message types (requires unitree_hg package)
from unitree_hg.msg import IMUState, MotorCmd, MotorState


# =============================================================================
# Standard ROS2 Message Conversions
# =============================================================================


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


# =============================================================================
# Unitree G1 Message Helpers
# =============================================================================


def create_motor_state(
    pos: float,
    vel: float,
    mode: int = 1,
    accel: float = 0.0,
    tau_est: float = 0.0,
    temperature: list = None,
    voltage: float = 24.0,
) -> MotorState:
    """Create a MotorState message from motor data.

    Args:
        pos: Joint position (radians)
        vel: Joint velocity (rad/s)
        mode: Motor mode (1=enabled, 0=disabled)
        accel: Joint acceleration (rad/s²)
        tau_est: Estimated external torque (Nm)
        temperature: Motor temperatures [motor, driver] (default [25, 25])
        voltage: Motor voltage (default 24.0V)

    Returns:
        MotorState: Unitree motor state message
    """
    msg = MotorState()
    msg.mode = mode
    msg.q = float(pos)
    msg.dq = float(vel)
    msg.ddq = float(accel)
    msg.tau_est = float(tau_est)
    msg.temperature = temperature if temperature else [25, 25]
    msg.vol = float(voltage)
    msg.sensor = [0, 0]
    msg.motorstate = 0
    msg.reserve = [0, 0, 0, 0]
    return msg


def create_motor_cmd(
    pos: float,
    vel: float = 0.0,
    tau: float = 0.0,
    kp: float = 100.0,
    kd: float = 2.0,
    mode: int = 1,
) -> MotorCmd:
    """Create a MotorCmd message for motor control.

    Args:
        pos: Target joint position (radians)
        vel: Target joint velocity (rad/s)
        tau: Target torque (Nm)
        kp: Proportional gain (stiffness)
        kd: Derivative gain (damping)
        mode: Motor mode (1=enable, 0=disable)

    Returns:
        MotorCmd: Unitree motor command message
    """
    msg = MotorCmd()
    msg.mode = mode
    msg.q = float(pos)
    msg.dq = float(vel)
    msg.tau = float(tau)
    msg.kp = float(kp)
    msg.kd = float(kd)
    msg.reserve = 0
    return msg


def create_imu_state(
    quaternion: list,
    gyroscope: list,
    accelerometer: list,
    rpy: list = None,
    temperature: int = 25,
) -> IMUState:
    """Create an IMUState message from sensor data.

    Args:
        quaternion: Orientation [w, x, y, z]
        gyroscope: Angular velocity [wx, wy, wz] (rad/s)
        accelerometer: Linear acceleration [ax, ay, az] (m/s²)
        rpy: Roll-Pitch-Yaw angles [roll, pitch, yaw] (radians)
        temperature: IMU temperature (°C)

    Returns:
        IMUState: Unitree IMU state message
    """
    msg = IMUState()
    msg.quaternion = list(quaternion)
    msg.gyroscope = list(gyroscope)
    msg.accelerometer = list(accelerometer)
    msg.rpy = rpy if rpy else [0.0, 0.0, 0.0]
    msg.temperature = temperature
    return msg


def quaternion_to_rpy(quat: list) -> list:
    """Convert quaternion to roll-pitch-yaw angles.

    Args:
        quat: Quaternion [w, x, y, z]

    Returns:
        list: [roll, pitch, yaw] in radians
    """
    w, x, y, z = quat

    # Roll (x-axis rotation)
    sinr_cosp = 2 * (w * x + y * z)
    cosr_cosp = 1 - 2 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    # Pitch (y-axis rotation)
    sinp = 2 * (w * y - z * x)
    if abs(sinp) >= 1:
        pitch = math.copysign(math.pi / 2, sinp)  # Use 90 degrees if out of range
    else:
        pitch = math.asin(sinp)

    # Yaw (z-axis rotation)
    siny_cosp = 2 * (w * z + x * y)
    cosy_cosp = 1 - 2 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return [roll, pitch, yaw]


def torch_tensor_to_motor_states(
    joint_pos: torch.Tensor,
    joint_vel: torch.Tensor,
    num_motors: int = 35,
    active_dofs: int = 29,
) -> list:
    """Convert Isaac Lab joint tensors to list of MotorState messages.

    Args:
        joint_pos: Joint positions tensor [num_joints]
        joint_vel: Joint velocities tensor [num_joints]
        num_motors: Total motor slots (35 for G1)
        active_dofs: Active degrees of freedom (29 for G1)

    Returns:
        list: List of MotorState messages (length = num_motors)
    """
    motor_states = []

    for i in range(num_motors):
        if i < len(joint_pos) and i < active_dofs:
            motor = create_motor_state(
                pos=float(joint_pos[i].item()),
                vel=float(joint_vel[i].item()),
                mode=1,  # Enabled
            )
        else:
            motor = create_motor_state(pos=0.0, vel=0.0, mode=0)  # Disabled

        motor_states.append(motor)

    return motor_states


def motor_cmds_to_torch_tensors(
    motor_cmds: list,
    device: str = "cuda",
    active_dofs: int = 29,
) -> tuple:
    """Convert list of MotorCmd messages to Isaac Lab tensors.

    Args:
        motor_cmds: List of MotorCmd messages
        device: Torch device
        active_dofs: Number of active DOFs to extract

    Returns:
        tuple: (joint_targets, stiffness, damping) tensors
    """
    joint_targets = torch.zeros(active_dofs, device=device)
    stiffness = torch.zeros(active_dofs, device=device)
    damping = torch.zeros(active_dofs, device=device)

    for i in range(min(active_dofs, len(motor_cmds))):
        joint_targets[i] = motor_cmds[i].q
        stiffness[i] = motor_cmds[i].kp
        damping[i] = motor_cmds[i].kd

    return joint_targets, stiffness, damping


# =============================================================================
# G1 Robot Constants
# =============================================================================

# G1 joint names (29 DOF)
G1_JOINT_NAMES = [
    # Left leg (0-5)
    "left_hip_pitch_joint",
    "left_hip_roll_joint",
    "left_hip_yaw_joint",
    "left_knee_joint",
    "left_ankle_pitch_joint",
    "left_ankle_roll_joint",
    # Right leg (6-11)
    "right_hip_pitch_joint",
    "right_hip_roll_joint",
    "right_hip_yaw_joint",
    "right_knee_joint",
    "right_ankle_pitch_joint",
    "right_ankle_roll_joint",
    # Waist (12)
    "waist_yaw_joint",
    # Left arm (13-19)
    "left_shoulder_pitch_joint",
    "left_shoulder_roll_joint",
    "left_shoulder_yaw_joint",
    "left_elbow_joint",
    "left_wrist_roll_joint",
    "left_wrist_pitch_joint",
    "left_wrist_yaw_joint",
    # Right arm (20-26)
    "right_shoulder_pitch_joint",
    "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint",
    "right_elbow_joint",
    "right_wrist_roll_joint",
    "right_wrist_pitch_joint",
    "right_wrist_yaw_joint",
    # Head (27-28)
    "head_pitch_joint",
    "head_yaw_joint",
]

# Default PD gains for G1 (typical values)
G1_DEFAULT_KP = {
    "hip": 150.0,
    "knee": 150.0,
    "ankle": 40.0,
    "waist": 100.0,
    "shoulder": 40.0,
    "elbow": 40.0,
    "wrist": 20.0,
    "head": 20.0,
}

G1_DEFAULT_KD = {
    "hip": 3.0,
    "knee": 3.0,
    "ankle": 1.0,
    "waist": 2.0,
    "shoulder": 1.0,
    "elbow": 1.0,
    "wrist": 0.5,
    "head": 0.5,
}
