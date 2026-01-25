"""ROS2 bridge for Colibri G1 digital twin using unified single-node architecture.

This module implements a single ROS2 node for publishing robot state and
subscribing to commands, following the Unitree G1 real robot patterns.

The unified architecture merges publishers and subscribers into one node,
eliminating threading complexity while maintaining all functionality.

Topics Published (Unitree Pattern):
    /lowstate (unitree_hg/LowState): Robot state (motors + IMU) @ 50 Hz
    /utlidar/cloud (sensor_msgs/PointCloud2): LiDAR point cloud @ 15 Hz
    /ground_truth/pose (geometry_msgs/PoseStamped): World pose @ 50 Hz
    /ground_truth/twist (geometry_msgs/TwistStamped): World twist @ 50 Hz
    /clock (rosgraph_msgs/Clock): Simulation time (via OmniGraph)

Topics Published (Custom - Navigation):
    /{namespace}/goal_marker (visualization_msgs/Marker): Goal visualization @ 1 Hz
    /{namespace}/navigation/goal_pose (geometry_msgs/PoseStamped): Goal position
    /{namespace}/navigation/distance_to_goal (std_msgs/Float32): Distance metric
    /{namespace}/navigation/status (std_msgs/String): Navigation status

Topics Subscribed:
    /lowcmd (unitree_hg/LowCmd): Motor-level commands (primary)
    /cmd_vel (geometry_msgs/Twist): Velocity commands (exploration)

Reference: unitree_ros2/cyclonedds_ws/src/unitree/unitree_hg/msg/
Reference: go2_isaac_ros2 (CLeARoboticsLab/go2_isaac_ros2)
"""

import time

import numpy as np
import rclpy
import torch
from rclpy.node import Node
from rclpy.time import Time as ROSTime

# Unitree G1 message types (requires unitree_hg package)
from unitree_hg.msg import IMUState, LowCmd, LowState, MotorCmd, MotorState

# Standard ROS2 message types
from geometry_msgs.msg import PoseStamped, TransformStamped, Twist, TwistStamped
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import PointCloud2, PointField
from sensor_msgs_py import point_cloud2
from std_msgs.msg import Float32, Header, String
from visualization_msgs.msg import Marker

# TF2
import tf2_ros
from tf2_ros.static_transform_broadcaster import StaticTransformBroadcaster

# Isaac Sim / Omniverse
import omni
import omni.graph.core as og

# Enable ROS2 bridge extension (required for ROS2 image writers)
ext_manager = omni.kit.app.get_app().get_extension_manager()
ext_manager.set_extension_enabled_immediate("omni.isaac.ros2_bridge", True)


# G1 Robot Configuration
G1_NUM_MOTORS = 35  # Total motor slots in LowState/LowCmd (real robot)
G1_ACTIVE_DOFS = 29  # Actual DOFs used by G1


class ColibriG1RobotDataManager(Node):
    """Unified ROS2 node for Colibri G1 sim2sim integration.

    Combines publishers and subscribers into a single node, eliminating threading
    complexity while maintaining full functionality.

    Publishes:
        - /lowstate (unitree_hg/LowState): Motor states + IMU @ 50 Hz
        - /utlidar/cloud (sensor_msgs/PointCloud2): LiDAR point cloud @ 15 Hz
        - /ground_truth/pose, /twist: Ground truth pose/twist @ 50 Hz
        - /colibri_g1/goal_marker: Goal visualization @ 1 Hz
        - Navigation metrics and camera images

    Subscribes:
        - /lowcmd (unitree_hg/LowCmd): Motor commands
        - /cmd_vel (geometry_msgs/Twist): Velocity commands

    Args:
        env: Isaac Lab environment
        cfg: Configuration object (from ros2_sim.yaml)
        lidar_annotators: List of LiDAR annotators, or None
        cameras: List of camera instances, or None
    """

    def __init__(self, env, cfg, lidar_annotators=None, cameras=None):
        super().__init__("colibri_g1_node")

        # Store environment and config
        self.env = env
        self.cfg = cfg
        self.robot = env.scene["robot"]
        self.lidar_annotators = lidar_annotators
        self.cameras = cameras
        self.clock_msg = None

        # Namespace for custom topics
        self.nav_namespace = cfg.ros2.namespace if cfg else "colibri_g1"

        # Create OmniGraph for clock publishing (matches isaac-go2-ros2 pattern)
        self._create_ros_time_graph()

        # Initialize publishers
        self._init_publishers()

        # Initialize TF broadcaster
        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)

        # Initialize static transforms (lidar_link, camera)
        self._publish_static_transforms()

        # Initialize subscribers
        self._init_subscribers()

        # Initialize camera publishers if available
        if cameras is not None:
            self._create_camera_publishers()

        # State tracking for publishing
        self.last_goal_marker_time = ROSTime(seconds=0, nanoseconds=0)

        # Rate control (wall time)
        self.lidar_freq = cfg.sensor.lidar.publish_rate if cfg and hasattr(cfg.sensor, "lidar") else 15.0
        self.last_lidar_pub_time = time.time()

        # External control state (from subscribers)
        device = cfg.policy.device if cfg else "cuda"
        self.joint_targets = torch.zeros(G1_ACTIVE_DOFS, device=device)
        self.stiffness = torch.zeros(G1_ACTIVE_DOFS, device=device)
        self.damping = torch.zeros(G1_ACTIVE_DOFS, device=device)
        self.use_external_control = False

        # Velocity command state (from cmd_vel subscriber)
        self.cmd_vel_linear = torch.zeros(3, device=device)
        self.cmd_vel_angular = torch.zeros(3, device=device)
        self.use_cmd_vel = False
        self.last_cmd_vel_time = time.time()

        self.get_logger().info("Colibri G1 ROS2 node initialized (unified single-node architecture)")

    def _create_ros_time_graph(self):
        """Create OmniGraph for publishing /clock topic with simulation time."""
        keys = og.Controller.Keys
        og.Controller.edit(
            {"graph_path": "/ClockActionGraph", "evaluator_name": "execution"},
            {
                keys.CREATE_NODES: [
                    ("ReadSimTime", "isaacsim.core.nodes.IsaacReadSimulationTime"),
                    ("OnPlaybackTick", "omni.graph.action.OnPlaybackTick"),
                    ("PublishClock", "isaacsim.ros2.bridge.ROS2PublishClock"),
                ],
                keys.CONNECT: [
                    ("OnPlaybackTick.outputs:tick", "PublishClock.inputs:execIn"),
                    ("ReadSimTime.outputs:simulationTime", "PublishClock.inputs:timeStamp"),
                ],
                keys.SET_VALUES: [
                    ("PublishClock.inputs:topicName", "/clock"),
                ],
            },
        )
        self.get_logger().info("OmniGraph clock publisher created for /clock")

    def _init_publishers(self):
        """Create ROS2 publishers following Unitree patterns."""
        # Primary: Unitree LowState (motor + IMU)
        self.lowstate_pub = self.create_publisher(LowState, "/lowstate", 10)

        # LiDAR point cloud publisher (Unitree naming convention)
        if self.lidar_annotators is not None:
            self.lidar_pub = self.create_publisher(PointCloud2, "/utlidar/cloud", 10)
            self.get_logger().info("LiDAR publisher created: /utlidar/cloud")

        # Ground truth (simulation only)
        self.ground_truth_pose_pub = self.create_publisher(PoseStamped, "/ground_truth/pose", 10)
        self.ground_truth_twist_pub = self.create_publisher(TwistStamped, "/ground_truth/twist", 10)

        # Custom navigation topics (keep for visualization)
        self.goal_marker_pub = self.create_publisher(Marker, f"/{self.nav_namespace}/goal_marker", 10)
        self.goal_pose_pub = self.create_publisher(PoseStamped, f"/{self.nav_namespace}/navigation/goal_pose", 10)
        self.distance_to_goal_pub = self.create_publisher(
            Float32, f"/{self.nav_namespace}/navigation/distance_to_goal", 10
        )
        self.nav_status_pub = self.create_publisher(String, f"/{self.nav_namespace}/navigation/status", 10)

        self.get_logger().info("Publishers initialized (Unitree pattern + navigation)")

    def _init_subscribers(self):
        """Create ROS2 subscribers for motor and velocity commands."""
        self.lowcmd_sub = self.create_subscription(LowCmd, "/lowcmd", self._lowcmd_callback, 1)
        self.cmd_vel_sub = self.create_subscription(Twist, "/cmd_vel", self._cmd_vel_callback, 10)
        self.get_logger().info("Subscribers initialized (lowcmd, cmd_vel)")

    def _publish_static_transforms(self):
        """Publish static transforms for sensors (lidar_link, camera, etc.)."""
        if self.lidar_annotators is not None and self.cfg:
            lidar_broadcaster = StaticTransformBroadcaster(self)
            lidar_transform = TransformStamped()
            lidar_transform.header.stamp = self.get_clock().now().to_msg()
            lidar_transform.header.frame_id = "base_link"
            lidar_transform.child_frame_id = self.cfg.sensor.lidar.frame_id

            translation = self.cfg.sensor.lidar.translation
            lidar_transform.transform.translation.x = float(translation[0])
            lidar_transform.transform.translation.y = float(translation[1])
            lidar_transform.transform.translation.z = float(translation[2])

            orientation = self.cfg.sensor.lidar.orientation
            lidar_transform.transform.rotation.w = float(orientation[0])
            lidar_transform.transform.rotation.x = float(orientation[1])
            lidar_transform.transform.rotation.y = float(orientation[2])
            lidar_transform.transform.rotation.z = float(orientation[3])

            lidar_broadcaster.sendTransform(lidar_transform)
            self.get_logger().info(f"Static transform: base_link -> {self.cfg.sensor.lidar.frame_id}")

    def publish_data(self):
        """Publish all robot state data (called every simulation step).

        Handles:
            - Unitree /lowstate (motor + IMU)
            - Ground truth pose/twist
            - TF transforms (map -> base_link)
            - LiDAR point clouds (rate-limited)
            - Navigation metrics and markers (rate-limited)
        """
        # Compute simulation time and robot data
        sim_time_sec = float(self.env.unwrapped.common_step_counter * self.env.unwrapped.step_dt)
        robot_data = self.robot.data

        # Call original publish logic with extracted parameters
        self._publish_all(robot_data, sim_time_sec)

    def _publish_all(self, robot_data, sim_time_sec: float):
        """Internal method to publish all robot state data.

        Args:
            robot_data: Robot articulation data from Isaac Lab
            sim_time_sec: Simulation time in seconds
        """
        # Store clock for timestamp consistency
        self._update_clock(sim_time_sec)

        # Publish Unitree LowState (motor + IMU)
        self._publish_lowstate(robot_data)

        # Publish ground truth (simulation-only topics)
        self._publish_ground_truth(robot_data)

        # Publish TF: map -> base_link
        self._publish_transforms(robot_data)

        # Publish LiDAR (rate-limited)
        if self.lidar_annotators is not None and self._should_publish_lidar():
            self._publish_lidar()

        # Publish navigation topics (rate-limited)
        current_time = self._sim_time_to_ros_time(sim_time_sec)
        if self._should_publish_goal_marker(current_time):
            self._publish_goal_marker(robot_data, self.env, current_time)
            self._publish_navigation_metrics(robot_data, self.env, current_time)

    def _update_clock(self, sim_time_sec: float):
        """Update internal clock message for timestamp consistency."""
        msg = Clock()
        msg.clock.sec = int(sim_time_sec)
        msg.clock.nanosec = int((sim_time_sec - int(sim_time_sec)) * 1e9)
        self.clock_msg = msg

    def _publish_lowstate(self, robot_data):
        """Publish /lowstate with motor states and IMU data.

        This matches the real G1 robot's /lowstate topic format.
        """
        msg = LowState()

        # Version and mode
        msg.version = [0, 0]
        msg.mode_pr = 0  # 0 = PR mode (ankle)
        msg.mode_machine = 0
        msg.tick = self.clock_msg.clock.sec * 1000 + self.clock_msg.clock.nanosec // 1000000

        # IMU State
        root_state = robot_data.root_state_w[0]  # [pos(3), quat(4), lin_vel(3), ang_vel(3)]

        # Quaternion (Isaac Lab: w, x, y, z)
        quat = root_state[3:7]
        msg.imu_state.quaternion[0] = float(quat[0].item())  # w
        msg.imu_state.quaternion[1] = float(quat[1].item())  # x
        msg.imu_state.quaternion[2] = float(quat[2].item())  # y
        msg.imu_state.quaternion[3] = float(quat[3].item())  # z

        # Gyroscope (angular velocity in body frame)
        ang_vel = root_state[10:13]
        msg.imu_state.gyroscope[0] = float(ang_vel[0].item())
        msg.imu_state.gyroscope[1] = float(ang_vel[1].item())
        msg.imu_state.gyroscope[2] = float(ang_vel[2].item())

        # Accelerometer (approximate with gravity)
        # TODO: Use actual IMU sensor if available
        msg.imu_state.accelerometer[0] = 0.0
        msg.imu_state.accelerometer[1] = 0.0
        msg.imu_state.accelerometer[2] = 9.81

        # RPY from quaternion
        msg.imu_state.rpy[0] = 0.0  # Roll
        msg.imu_state.rpy[1] = 0.0  # Pitch
        msg.imu_state.rpy[2] = 0.0  # Yaw
        msg.imu_state.temperature = 25

        # Motor States (29 active DOFs, padded to 35)
        joint_pos = robot_data.joint_pos[0]
        joint_vel = robot_data.joint_vel[0]

        for i in range(G1_NUM_MOTORS):
            motor = MotorState()
            if i < len(joint_pos):
                motor.mode = 1  # Enabled
                motor.q = float(joint_pos[i].item())
                motor.dq = float(joint_vel[i].item())
                motor.ddq = 0.0  # Acceleration not available
                motor.tau_est = 0.0  # Torque estimate not available
                motor.temperature = [25, 25]
                motor.vol = 24.0
                motor.sensor = [0, 0]
                motor.motorstate = 0
                motor.reserve = [0, 0, 0, 0]
            else:
                motor.mode = 0  # Disabled (padding)
                motor.q = 0.0
                motor.dq = 0.0
            msg.motor_state[i] = motor

        # CRC (0 for simulation)
        msg.crc = 0

        self.lowstate_pub.publish(msg)

    def _publish_ground_truth(self, robot_data):
        """Publish ground truth pose and twist (simulation only)."""
        root_state = robot_data.root_state_w[0]

        # Pose
        pose_msg = PoseStamped()
        pose_msg.header.frame_id = "world"
        pose_msg.header.stamp.sec = self.clock_msg.clock.sec
        pose_msg.header.stamp.nanosec = self.clock_msg.clock.nanosec

        pose_msg.pose.position.x = float(root_state[0].item())
        pose_msg.pose.position.y = float(root_state[1].item())
        pose_msg.pose.position.z = float(root_state[2].item())
        pose_msg.pose.orientation.w = float(root_state[3].item())
        pose_msg.pose.orientation.x = float(root_state[4].item())
        pose_msg.pose.orientation.y = float(root_state[5].item())
        pose_msg.pose.orientation.z = float(root_state[6].item())

        self.ground_truth_pose_pub.publish(pose_msg)

        # Twist
        twist_msg = TwistStamped()
        twist_msg.header.frame_id = "world"
        twist_msg.header.stamp.sec = self.clock_msg.clock.sec
        twist_msg.header.stamp.nanosec = self.clock_msg.clock.nanosec

        twist_msg.twist.linear.x = float(root_state[7].item())
        twist_msg.twist.linear.y = float(root_state[8].item())
        twist_msg.twist.linear.z = float(root_state[9].item())
        twist_msg.twist.angular.x = float(root_state[10].item())
        twist_msg.twist.angular.y = float(root_state[11].item())
        twist_msg.twist.angular.z = float(root_state[12].item())

        self.ground_truth_twist_pub.publish(twist_msg)

    def _publish_transforms(self, robot_data):
        """Publish TF: map -> base_link."""
        root_state = robot_data.root_state_w[0]

        transform = TransformStamped()
        transform.header.stamp.sec = self.clock_msg.clock.sec
        transform.header.stamp.nanosec = self.clock_msg.clock.nanosec
        transform.header.frame_id = "map"
        transform.child_frame_id = "base_link"

        transform.transform.translation.x = float(root_state[0].item())
        transform.transform.translation.y = float(root_state[1].item())
        transform.transform.translation.z = float(root_state[2].item())
        transform.transform.rotation.w = float(root_state[3].item())
        transform.transform.rotation.x = float(root_state[4].item())
        transform.transform.rotation.y = float(root_state[5].item())
        transform.transform.rotation.z = float(root_state[6].item())

        self.tf_broadcaster.sendTransform(transform)

    def _should_publish_lidar(self):
        """Check if LiDAR should be published (wall time rate control)."""
        dt = time.time() - self.last_lidar_pub_time
        return dt >= (1.0 / self.lidar_freq)

    def _publish_lidar(self):
        """Publish /utlidar/cloud point cloud (Unitree naming convention)."""
        self.last_lidar_pub_time = time.time()

        try:
            lidar_data = self.lidar_annotators[0].get_data()
            if lidar_data is None or "data" not in lidar_data:
                return

            points = lidar_data["data"].reshape(-1, 3)

            # Filter by distance
            min_range = getattr(self.cfg.sensor.lidar, "min_range", 0.3)
            max_range = getattr(self.cfg.sensor.lidar, "max_range", 100.0)
            distances = np.linalg.norm(points, axis=1)
            valid_mask = (distances >= min_range) & (distances <= max_range)
            filtered_points = points[valid_mask]

            if len(filtered_points) == 0:
                return

            # Create PointCloud2 message
            header = Header()
            header.frame_id = self.cfg.sensor.lidar.frame_id
            header.stamp.sec = self.clock_msg.clock.sec
            header.stamp.nanosec = self.clock_msg.clock.nanosec

            fields = [
                PointField(name="x", offset=0, datatype=PointField.FLOAT32, count=1),
                PointField(name="y", offset=4, datatype=PointField.FLOAT32, count=1),
                PointField(name="z", offset=8, datatype=PointField.FLOAT32, count=1),
            ]

            msg = point_cloud2.create_cloud(header, fields, filtered_points)
            self.lidar_pub.publish(msg)

        except Exception as e:
            self.get_logger().warn(f"Failed to publish LiDAR: {e}")

    def _sim_time_to_ros_time(self, sim_time: float) -> ROSTime:
        """Convert simulation time to ROS Time object."""
        sec = int(sim_time)
        nanosec = int((sim_time - sec) * 1e9)
        return ROSTime(seconds=sec, nanoseconds=nanosec)

    def _should_publish_goal_marker(self, current_time: ROSTime) -> bool:
        """Check if goal marker should be published."""
        time_diff = (current_time - self.last_goal_marker_time).nanoseconds
        rate = self.cfg.ros2.goal_marker_rate if self.cfg else 1.0
        publish_interval_ns = int(1.0 / rate * 1e9)
        return time_diff >= publish_interval_ns

    def _publish_goal_marker(self, robot_data, env, current_time: ROSTime):
        """Publish goal marker for visualization."""
        from .colibri_g1_ros2_utils import compute_euclidean_distance, torch_to_ros_point

        goal_cmd_term = env.command_manager._terms["goal_position"]
        goal_pos_w = goal_cmd_term.goal_pos_w[0]

        root_state = robot_data.root_state_w[0]
        robot_pos = root_state[:3]

        distance = compute_euclidean_distance(robot_pos[:2], goal_pos_w[:2])

        marker = Marker()
        marker.header.stamp = current_time.to_msg()
        marker.header.frame_id = "map"
        marker.ns = "navigation"
        marker.id = 0
        marker.type = Marker.SPHERE
        marker.action = Marker.ADD
        marker.pose.position = torch_to_ros_point(goal_pos_w)
        marker.pose.orientation.w = 1.0
        marker.scale.x = 0.3
        marker.scale.y = 0.3
        marker.scale.z = 0.3

        if distance > 0.3:
            marker.color.r, marker.color.g, marker.color.b = 0.0, 1.0, 0.0  # Green
        else:
            marker.color.r, marker.color.g, marker.color.b = 0.0, 0.0, 1.0  # Blue
        marker.color.a = 0.6

        self.goal_marker_pub.publish(marker)

        goal_pose = PoseStamped()
        goal_pose.header.stamp = current_time.to_msg()
        goal_pose.header.frame_id = "map"
        goal_pose.pose.position = torch_to_ros_point(goal_pos_w)
        goal_pose.pose.orientation.w = 1.0
        self.goal_pose_pub.publish(goal_pose)

        self.last_goal_marker_time = current_time

    def _publish_navigation_metrics(self, robot_data, env, current_time: ROSTime):
        """Publish navigation metrics."""
        from .colibri_g1_ros2_utils import compute_euclidean_distance

        goal_cmd_term = env.command_manager._terms["goal_position"]
        goal_pos_w = goal_cmd_term.goal_pos_w[0]

        root_state = robot_data.root_state_w[0]
        robot_pos = root_state[:3]

        distance = compute_euclidean_distance(robot_pos[:2], goal_pos_w[:2])

        distance_msg = Float32()
        distance_msg.data = distance
        self.distance_to_goal_pub.publish(distance_msg)

        status_msg = String()
        status_msg.data = "approaching" if distance > 0.3 else "reached"
        self.nav_status_pub.publish(status_msg)

    # ===========================
    # Subscriber Callbacks
    # ===========================

    def _lowcmd_callback(self, msg: LowCmd):
        """Handle motor-level commands from /lowcmd.

        Extracts joint position targets, stiffness (kp), and damping (kd)
        from the LowCmd message for use in the simulation step.
        """
        for i in range(min(G1_ACTIVE_DOFS, G1_NUM_MOTORS)):
            self.joint_targets[i] = msg.motor_cmd[i].q
            self.stiffness[i] = msg.motor_cmd[i].kp
            self.damping[i] = msg.motor_cmd[i].kd

        self.use_external_control = True
        self.use_cmd_vel = False

    def _cmd_vel_callback(self, msg: Twist):
        """Handle velocity commands from /cmd_vel (exploration mode)."""
        self.cmd_vel_linear[0] = msg.linear.x
        self.cmd_vel_linear[1] = msg.linear.y
        self.cmd_vel_linear[2] = msg.linear.z
        self.cmd_vel_angular[0] = msg.angular.x
        self.cmd_vel_angular[1] = msg.angular.y
        self.cmd_vel_angular[2] = msg.angular.z

        self.use_cmd_vel = True
        self.last_cmd_vel_time = time.time()
        # Note: use_external_control takes priority if both are active

    # ===========================
    # External Control Accessors
    # ===========================

    def get_external_control(self):
        """Get external control state.

        Returns:
            tuple: (joint_targets, stiffness, damping, use_external_control)
        """
        return (
            self.joint_targets.clone(),
            self.stiffness.clone(),
            self.damping.clone(),
            self.use_external_control,
        )

    def get_cmd_vel(self):
        """Get velocity command state.

        Returns:
            tuple: (linear, angular, use_cmd_vel)
        """
        return (self.cmd_vel_linear.clone(), self.cmd_vel_angular.clone(), self.use_cmd_vel)

    # ===========================
    # Camera Publishing
    # ===========================

    def _create_camera_publishers(self):
        """Initialize camera image publishers using OmniGraph."""
        if not hasattr(self.cfg.sensor, "camera"):
            return

        cam_cfg = self.cfg.sensor.camera

        for i, camera in enumerate(self.cameras):
            self._create_camera_graph(
                camera,
                color_enabled=getattr(cam_cfg, "color_image", True),
                depth_enabled=getattr(cam_cfg, "depth_image", True),
            )

    def _create_camera_graph(self, camera, color_enabled=True, depth_enabled=True):
        """Create OmniGraph for camera image publishing."""
        color_topic = "/front_cam/color_image"
        depth_topic = "/front_cam/depth_image"
        frame_id = self.cfg.sensor.camera.frame_id

        keys = og.Controller.Keys

        nodes_to_create = [
            ("OnPlaybackTick", "omni.graph.action.OnPlaybackTick"),
            ("IsaacCreateRenderProduct", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
        ]

        values_to_set = [
            ("IsaacCreateRenderProduct.inputs:cameraPrim", camera.prim_path),
            ("IsaacCreateRenderProduct.inputs:enabled", True),
            ("IsaacCreateRenderProduct.inputs:height", self.cfg.sensor.camera.height),
            ("IsaacCreateRenderProduct.inputs:width", self.cfg.sensor.camera.width),
        ]

        connections = [
            ("OnPlaybackTick.outputs:tick", "IsaacCreateRenderProduct.inputs:execIn"),
        ]

        if color_enabled:
            nodes_to_create.append(("ROS2CameraHelperColor", "isaacsim.ros2.bridge.ROS2CameraHelper"))
            values_to_set.extend(
                [
                    ("ROS2CameraHelperColor.inputs:type", "rgb"),
                    ("ROS2CameraHelperColor.inputs:topicName", color_topic),
                    ("ROS2CameraHelperColor.inputs:frameId", frame_id),
                    ("ROS2CameraHelperColor.inputs:useSystemTime", False),
                ]
            )
            connections.extend(
                [
                    ("IsaacCreateRenderProduct.outputs:execOut", "ROS2CameraHelperColor.inputs:execIn"),
                    ("IsaacCreateRenderProduct.outputs:renderProductPath", "ROS2CameraHelperColor.inputs:renderProductPath"),
                ]
            )

        if depth_enabled:
            nodes_to_create.append(("ROS2CameraHelperDepth", "isaacsim.ros2.bridge.ROS2CameraHelper"))
            values_to_set.extend(
                [
                    ("ROS2CameraHelperDepth.inputs:type", "depth"),
                    ("ROS2CameraHelperDepth.inputs:topicName", depth_topic),
                    ("ROS2CameraHelperDepth.inputs:frameId", frame_id),
                    ("ROS2CameraHelperDepth.inputs:useSystemTime", False),
                ]
            )
            connections.extend(
                [
                    ("IsaacCreateRenderProduct.outputs:execOut", "ROS2CameraHelperDepth.inputs:execIn"),
                    ("IsaacCreateRenderProduct.outputs:renderProductPath", "ROS2CameraHelperDepth.inputs:renderProductPath"),
                ]
            )

        og.Controller.edit(
            {"graph_path": "/ColibriCameraROS2Graph", "evaluator_name": "execution"},
            {
                keys.CREATE_NODES: nodes_to_create,
                keys.SET_VALUES: values_to_set,
                keys.CONNECT: connections,
            },
        )

        if color_enabled:
            self.get_logger().info(f"Color image publisher: {color_topic}")
        if depth_enabled:
            self.get_logger().info(f"Depth image publisher: {depth_topic}")


# Backward compatibility aliases for old code (deprecated)
G1PubNode = ColibriG1RobotDataManager
G1SubNode = ColibriG1RobotDataManager
RobotDataManager = ColibriG1RobotDataManager


# Phase 6.1 - ROS2 bridge with Unitree message patterns
# Phase 6.2 - Policy integration
# Phase 6.3 - Navigation metrics
# Phase 6.4 - LiDAR sensor support
# Phase 6.5 - Camera image publishing
# Phase 7.0 - Unitree G1 real robot compatibility (/lowstate, /lowcmd)
