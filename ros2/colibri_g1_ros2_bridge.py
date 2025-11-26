"""ROS2 bridge for Colibri G1 digital twin.

This module implements the main ROS2 node for publishing robot state and
subscribing to commands.

Reference: isaac-go2-ros2/ros2/g1_ros2_bridge.py
"""

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.time import Time as ROSTime
import torch

# ROS2 message types
from geometry_msgs.msg import PoseStamped, Twist, TransformStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import JointState, PointCloud2, PointField
from sensor_msgs_py import point_cloud2
from std_msgs.msg import Float32, String
from visualization_msgs.msg import Marker
# Note: Clock msg not needed - /clock published via OmniGraph

# TF2
import tf2_ros
from tf2_ros.static_transform_broadcaster import StaticTransformBroadcaster
from geometry_msgs.msg import TransformStamped

# Camera/Image publishing
import omni
import omni.graph.core as og
import omni.replicator.core as rep
import omni.syntheticdata._syntheticdata as sd

# Enable ROS2 bridge extension (required for ROS2 image writers)
ext_manager = omni.kit.app.get_app().get_extension_manager()
ext_manager.set_extension_enabled_immediate("omni.isaac.ros2_bridge", True)

import subprocess
import time


class RobotDataManager(Node):
    """ROS2 node for managing Colibri G1 robot data.

    Publishes:
        /colibri_g1/odom (nav_msgs/Odometry): Robot odometry
        /colibri_g1/joint_states (sensor_msgs/JointState): Joint states
        /colibri_g1/pose (geometry_msgs/PoseStamped): Simplified pose
        /colibri_g1/goal_marker (visualization_msgs/Marker): Goal visualization
        /colibri_g1/lidar/point_cloud (sensor_msgs/PointCloud2): LiDAR point cloud
        /colibri_g1/front_cam/color_image (sensor_msgs/Image): RGB camera image
        /colibri_g1/front_cam/depth_image (sensor_msgs/Image): Depth camera image
        /clock (rosgraph_msgs/Clock): Simulation time

    Subscribes:
        /colibri_g1/cmd_vel (geometry_msgs/Twist): External velocity commands (optional)

    Args:
        env: Isaac Lab environment
        cfg: Configuration object (from ros2_sim.yaml)
        lidar_annotators: List of LiDAR annotators (one per environment), or None
        cameras: List of camera instances (one per environment), or None
    """

    def __init__(self, env, cfg, lidar_annotators=None, cameras=None):
        super().__init__("colibri_g1_ros2_bridge")

        # Store references
        self.env = env
        self.cfg = cfg
        self.robot = env.scene["robot"]
        self.lidar_annotators = lidar_annotators
        self.cameras = cameras

        # ROS2 namespace
        self.namespace = cfg.ros2.namespace

        # Create OmniGraph for clock publishing (matches isaac-go2-ros2 pattern)
        # This ensures proper simulation time synchronization with RViz
        self._create_ros_time_graph()

        # Set use_sim_time=true on this node (required for TF synchronization)
        self._set_use_sim_time()

        # Initialize publishers
        self._init_publishers()

        # Initialize subscribers
        self._init_subscribers()

        # Initialize TF broadcaster
        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)

        # Initialize static transforms (e.g., base_link -> lidar_link, base_link -> front_cam)
        self._publish_static_transforms()

        # Initialize camera publishers (using OmniGraph/Replicator)
        self._create_camera_publishers()

        # State tracking
        self.last_goal_pos = None
        # Initialize with sim time = 0 (start of simulation)
        self.last_goal_marker_time = ROSTime(seconds=0, nanoseconds=0)

        # LiDAR publish rate control (wall time)
        self.lidar_freq = cfg.sensor.lidar.publish_rate if hasattr(cfg.sensor, 'lidar') else 15.0
        self.last_lidar_pub_time = time.time()

        self.get_logger().info(f"ROS2 bridge initialized for {self.namespace}")

    def _create_ros_time_graph(self):
        """Create OmniGraph for publishing /clock topic with simulation time.

        This uses Isaac Sim's native ROS2 bridge nodes which properly synchronize
        simulation time with ROS2. This is the recommended approach from isaac-go2-ros2.
        """
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

    def _set_use_sim_time(self):
        """Set use_sim_time=true on this node for proper TF synchronization.

        This ensures the node's internal clock uses simulation time instead of
        wall time, which is required for RViz TF lookups to work correctly.
        """
        # Set use_sim_time parameter via subprocess (matches isaac-go2-ros2 pattern)
        command = ["ros2", "param", "set", "/colibri_g1_ros2_bridge", "use_sim_time", "true"]
        try:
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.get_logger().info("use_sim_time=true set on node")
        except Exception as e:
            self.get_logger().warn(f"Failed to set use_sim_time: {e}")

    def _init_publishers(self):
        """Create ROS2 publishers."""
        # Odometry publisher (50 Hz)
        self.odom_pub = self.create_publisher(Odometry, f"{self.namespace}/odom", 10)

        # Joint states publisher (50 Hz)
        self.joint_states_pub = self.create_publisher(JointState, f"{self.namespace}/joint_states", 10)

        # Pose publisher (50 Hz)
        self.pose_pub = self.create_publisher(PoseStamped, f"{self.namespace}/pose", 10)

        # Goal marker publisher (1 Hz)
        self.goal_marker_pub = self.create_publisher(Marker, f"{self.namespace}/goal_marker", 10)

        # Navigation metrics
        self.goal_pose_pub = self.create_publisher(
            PoseStamped, f"{self.namespace}/navigation/goal_pose", 10
        )
        self.distance_to_goal_pub = self.create_publisher(
            Float32, f"{self.namespace}/navigation/distance_to_goal", 10
        )
        self.nav_status_pub = self.create_publisher(
            String, f"{self.namespace}/navigation/status", 10
        )

        # Note: /clock is published via OmniGraph (see _create_ros_time_graph)
        # This ensures proper simulation time synchronization

        # LiDAR publisher (if enabled)
        if self.lidar_annotators is not None:
            self.lidar_pub = self.create_publisher(
                PointCloud2, f"{self.namespace}/lidar/point_cloud", 10
            )
            self.get_logger().info(f"LiDAR publisher created: {self.namespace}/lidar/point_cloud")

        self.get_logger().info("Publishers initialized")

    def _init_subscribers(self):
        """Create ROS2 subscribers."""
        if self.cfg.ros2.enable_cmd_vel_override:
            self.cmd_vel_sub = self.create_subscription(
                Twist, f"{self.namespace}/cmd_vel", self._cmd_vel_callback, 10
            )
            self.get_logger().info("Subscribed to cmd_vel (external control enabled)")

    def _cmd_vel_callback(self, msg: Twist):
        """Handle external velocity commands.

        Args:
            msg: Twist message with velocity commands
        """
        # TODO: Implement external velocity command override
        # For Phase 6.1, this is optional and can be implemented later
        pass

    def _publish_static_transforms(self):
        """Publish static transforms (e.g., base_link -> lidar_link, base_link -> front_cam).

        Static transforms are published once at startup and remain constant.

        Note: Each transform uses a SEPARATE StaticTransformBroadcaster to avoid
        overwrites. This matches the pattern in isaac-go2-ros2/ros2/go2_ros2_bridge.py.
        """
        # LiDAR static transform: base_link -> lidar_link
        # Use separate broadcaster for each transform (required to avoid overwrites)
        if self.lidar_annotators is not None:
            lidar_broadcaster = StaticTransformBroadcaster(self)
            lidar_transform = TransformStamped()
            # Use current sim time for static transforms (matches isaac-go2-ros2)
            lidar_transform.header.stamp = self.get_clock().now().to_msg()
            lidar_transform.header.frame_id = "base_link"
            lidar_transform.child_frame_id = self.cfg.sensor.lidar.frame_id

            # Translation from config (relative to base_link)
            translation = self.cfg.sensor.lidar.translation
            lidar_transform.transform.translation.x = float(translation[0])
            lidar_transform.transform.translation.y = float(translation[1])
            lidar_transform.transform.translation.z = float(translation[2])

            # Rotation from config (quaternion: w, x, y, z)
            orientation = self.cfg.sensor.lidar.orientation
            lidar_transform.transform.rotation.w = float(orientation[0])
            lidar_transform.transform.rotation.x = float(orientation[1])
            lidar_transform.transform.rotation.y = float(orientation[2])
            lidar_transform.transform.rotation.z = float(orientation[3])

            # Publish static transform
            lidar_broadcaster.sendTransform(lidar_transform)
            self.get_logger().info(
                f"Static transform published: base_link -> {self.cfg.sensor.lidar.frame_id}"
            )

        # Camera static transform: base_link -> front_cam
        # Use separate broadcaster for each transform (required to avoid overwrites)
        if self.cameras is not None:
            camera_broadcaster = StaticTransformBroadcaster(self)
            camera_transform = TransformStamped()
            # Use current sim time for static transforms (matches isaac-go2-ros2)
            camera_transform.header.stamp = self.get_clock().now().to_msg()
            camera_transform.header.frame_id = "base_link"
            camera_transform.child_frame_id = self.cfg.sensor.camera.frame_id

            # Translation from config (relative to base_link)
            translation = self.cfg.sensor.camera.translation
            camera_transform.transform.translation.x = float(translation[0])
            camera_transform.transform.translation.y = float(translation[1])
            camera_transform.transform.translation.z = float(translation[2])

            # Rotation for camera frame (camera looks forward with optical frame convention)
            # Optical frame: Z forward, X right, Y down
            # ROS convention needs rotation from base_link to optical frame
            # Using quaternion that rotates from robot frame to camera optical frame
            camera_transform.transform.rotation.x = -0.5
            camera_transform.transform.rotation.y = 0.5
            camera_transform.transform.rotation.z = -0.5
            camera_transform.transform.rotation.w = 0.5

            # Publish static transform
            camera_broadcaster.sendTransform(camera_transform)
            self.get_logger().info(
                f"Static transform published: base_link -> {self.cfg.sensor.camera.frame_id}"
            )

    def publish_data(self):
        """Publish all robot data (called every simulation step)."""
        # Compute simulation time for /clock topic
        # env.common_step_counter tracks total simulation steps
        # env.step_dt is the physics timestep * decimation
        sim_time_seconds = float(self.env.unwrapped.common_step_counter * self.env.unwrapped.step_dt)

        # Use simulation time for ALL message timestamps (consistency with /clock)
        # This ensures RViz with use_sim_time=true can correlate TF and sensor data
        current_time = self._to_ros_time_obj(sim_time_seconds)

        # Publish high-frequency topics (50 Hz)
        self._publish_odometry(current_time)
        self._publish_joint_states(current_time)
        self._publish_pose(current_time)
        self._publish_transforms(current_time)
        # Note: /clock is published via OmniGraph (see _create_ros_time_graph)

        # Publish low-frequency topics (conditionally)
        if self._should_publish_goal_marker(current_time):
            self._publish_goal_marker(current_time)
            self._publish_navigation_metrics(current_time)

        # Publish LiDAR data at configured rate (wall time control)
        if self.lidar_annotators is not None:
            if self._should_publish_lidar():
                self._publish_lidar_data(current_time)

    def _publish_odometry(self, current_time):
        """Publish /colibri_g1/odom.

        Args:
            current_time: ROS2 Time object
        """
        from .colibri_g1_ros2_utils import torch_to_ros_point, torch_to_ros_quaternion, torch_to_ros_vector3

        # Create odometry message
        msg = Odometry()
        msg.header.stamp = current_time.to_msg()  # Convert ROS Time to message
        msg.header.frame_id = "map"
        msg.child_frame_id = "base_link"

        # Get robot root state [13]: pos(3), quat(4), lin_vel(3), ang_vel(3)
        root_state = self.robot.data.root_state_w[0]

        # Position (world frame)
        msg.pose.pose.position = torch_to_ros_point(root_state[:3])

        # Orientation (quaternion: w, x, y, z in Isaac Lab)
        msg.pose.pose.orientation = torch_to_ros_quaternion(root_state[3:7])

        # Linear velocity (world frame)
        msg.twist.twist.linear = torch_to_ros_vector3(root_state[7:10])

        # Angular velocity (world frame)
        msg.twist.twist.angular = torch_to_ros_vector3(root_state[10:13])

        # Publish
        self.odom_pub.publish(msg)

    def _publish_joint_states(self, current_time):
        """Publish /colibri_g1/joint_states.

        Args:
            current_time: Simulation time (seconds)
        """
        # Create joint state message
        msg = JointState()
        msg.header.stamp = current_time.to_msg()

        # Get joint names from robot configuration (29 DOF for G1)
        joint_names = self.robot.data.joint_names
        msg.name = joint_names

        # Get joint positions and velocities (index 0 for single env)
        joint_pos = self.robot.data.joint_pos[0]
        joint_vel = self.robot.data.joint_vel[0]

        # Convert tensors to lists
        msg.position = joint_pos.cpu().numpy().tolist()
        msg.velocity = joint_vel.cpu().numpy().tolist()

        # Effort (torques) - optional, set to zeros for now
        msg.effort = [0.0] * len(joint_names)

        # Publish
        self.joint_states_pub.publish(msg)

    def _publish_pose(self, current_time):
        """Publish /colibri_g1/pose.

        Args:
            current_time: Simulation time (seconds)
        """
        from .colibri_g1_ros2_utils import torch_to_ros_point, torch_to_ros_quaternion

        # Create pose message
        msg = PoseStamped()
        msg.header.stamp = current_time.to_msg()
        msg.header.frame_id = "map"

        # Get robot root state
        root_state = self.robot.data.root_state_w[0]

        # Position and orientation
        msg.pose.position = torch_to_ros_point(root_state[:3])
        msg.pose.orientation = torch_to_ros_quaternion(root_state[3:7])

        # Publish
        self.pose_pub.publish(msg)

    def _publish_transforms(self, current_time):
        """Publish TF transforms (map → base_link).

        Args:
            current_time: Simulation time (seconds)
        """
        from .colibri_g1_ros2_utils import torch_to_ros_point, torch_to_ros_quaternion

        # Create transform message
        transform = TransformStamped()
        transform.header.stamp = current_time.to_msg()
        transform.header.frame_id = "map"
        transform.child_frame_id = "base_link"

        # Get robot root state
        root_state = self.robot.data.root_state_w[0]

        # Position
        position = torch_to_ros_point(root_state[:3])
        transform.transform.translation.x = position.x
        transform.transform.translation.y = position.y
        transform.transform.translation.z = position.z

        # Orientation
        transform.transform.rotation = torch_to_ros_quaternion(root_state[3:7])

        # Broadcast transform
        self.tf_broadcaster.sendTransform(transform)

    # Note: _publish_clock removed - /clock is now published via OmniGraph
    # (see _create_ros_time_graph for the OmniGraph-based implementation)

    def _publish_goal_marker(self, current_time):
        """Publish /colibri_g1/goal_marker.

        Args:
            current_time: Simulation time (seconds)
        """
        from .colibri_g1_ros2_utils import torch_to_ros_point, compute_euclidean_distance

        # Get goal position from command manager
        # Access the SimpleGoalCommand term directly (not via get_command which returns tensor)
        goal_cmd_term = self.env.command_manager._terms["goal_position"]

        # Get goal position in world frame (shape: [num_envs, 3])
        goal_pos_w = goal_cmd_term.goal_pos_w[0]  # First environment
        goal_pos_3d = goal_pos_w  # Already 3D in world frame

        # Get robot position for distance calculation
        root_state = self.robot.data.root_state_w[0]
        robot_pos = root_state[:3]  # [x, y, z]

        # Compute distance to goal for color selection
        distance = compute_euclidean_distance(robot_pos[:2], goal_pos_3d[:2])

        # Create marker message
        marker = Marker()
        marker.header.stamp = current_time.to_msg()
        marker.header.frame_id = "map"
        marker.ns = "navigation"
        marker.id = 0
        marker.type = Marker.SPHERE
        marker.action = Marker.ADD

        # Position (3D in world frame)
        marker.pose.position = torch_to_ros_point(goal_pos_3d)
        marker.pose.orientation.w = 1.0  # No rotation

        # Scale (sphere diameter = 0.3m, matching goal reach threshold)
        marker.scale.x = 0.3
        marker.scale.y = 0.3
        marker.scale.z = 0.3

        # Color based on distance: Green if far (> 0.3m), Blue if reached (< 0.3m)
        if distance > 0.3:
            # Green (approaching)
            marker.color.r = 0.0
            marker.color.g = 1.0
            marker.color.b = 0.0
            marker.color.a = 0.6
        else:
            # Blue (reached)
            marker.color.r = 0.0
            marker.color.g = 0.0
            marker.color.b = 1.0
            marker.color.a = 0.6

        # Lifetime (persistent until updated)
        marker.lifetime.sec = 0
        marker.lifetime.nanosec = 0

        # Publish
        self.goal_marker_pub.publish(marker)

        # Also publish goal pose for standard navigation interfaces
        goal_pose = PoseStamped()
        goal_pose.header.stamp = current_time.to_msg()
        goal_pose.header.frame_id = "map"
        goal_pose.pose.position = torch_to_ros_point(goal_pos_3d)
        goal_pose.pose.orientation.w = 1.0
        self.goal_pose_pub.publish(goal_pose)

        # Update last publish time
        self.last_goal_marker_time = current_time

    def _publish_navigation_metrics(self, current_time):
        """Publish navigation metrics (goal pose, distance, status).

        Args:
            current_time: Simulation time (seconds)
        """
        from .colibri_g1_ros2_utils import compute_euclidean_distance

        # Get goal position and robot position
        # Access the SimpleGoalCommand term directly (same as in _publish_goal_marker)
        goal_cmd_term = self.env.command_manager._terms["goal_position"]
        goal_pos_3d = goal_cmd_term.goal_pos_w[0]  # World frame, shape: (3,)

        root_state = self.robot.data.root_state_w[0]
        robot_pos = root_state[:3]

        # Compute distance to goal (2D distance, ignoring Z)
        distance = compute_euclidean_distance(robot_pos[:2], goal_pos_3d[:2])

        # Publish distance to goal
        distance_msg = Float32()
        distance_msg.data = distance
        self.distance_to_goal_pub.publish(distance_msg)

        # Determine navigation status
        if distance > 0.3:
            status = "approaching"
        else:
            status = "reached"

        # Publish status
        status_msg = String()
        status_msg.data = status
        self.nav_status_pub.publish(status_msg)

    def _should_publish_goal_marker(self, current_time):
        """Check if goal marker should be published.

        Args:
            current_time: ROS2 Time object

        Returns:
            bool: True if goal marker should be published
        """
        # Publish at goal_marker_rate Hz (default 1 Hz)
        # Convert to nanoseconds for comparison
        time_diff = (current_time - self.last_goal_marker_time).nanoseconds
        publish_interval_ns = int(1.0 / self.cfg.ros2.goal_marker_rate * 1e9)
        return time_diff >= publish_interval_ns

    def _to_ros_time(self, sim_time):
        """Convert simulation time to ROS time message.

        Args:
            sim_time: Simulation time (seconds)

        Returns:
            builtin_interfaces/Time: ROS timestamp message
        """
        sec = int(sim_time)
        nanosec = int((sim_time - sec) * 1e9)
        return ROSTime(seconds=sec, nanoseconds=nanosec).to_msg()

    def _to_ros_time_obj(self, sim_time):
        """Convert simulation time to ROS Time object.

        Args:
            sim_time: Simulation time (seconds)

        Returns:
            rclpy.time.Time: ROS Time object (supports arithmetic operations)
        """
        sec = int(sim_time)
        nanosec = int((sim_time - sec) * 1e9)
        return ROSTime(seconds=sec, nanoseconds=nanosec)

    def _should_publish_lidar(self):
        """Check if LiDAR data should be published based on wall time.

        Returns:
            bool: True if enough time has passed since last LiDAR publish.
        """
        dt_lidar = time.time() - self.last_lidar_pub_time
        return dt_lidar >= (1.0 / self.lidar_freq)

    def _publish_lidar_data(self, current_time):
        """Publish /colibri_g1/lidar/point_cloud.

        Args:
            current_time: ROS2 Time object for message header.

        Note:
            Point cloud data is retrieved from the RTX LiDAR annotator
            which returns data in the sensor's local frame.
            Points are filtered by distance to remove self-intersection artifacts.
        """
        # Update last publish time
        self.last_lidar_pub_time = time.time()

        # Get LiDAR data from annotator (index 0 for single env)
        try:
            lidar_data = self.lidar_annotators[0].get_data()
            if lidar_data is None or "data" not in lidar_data:
                return

            # Reshape point cloud data to Nx3 array (x, y, z)
            points = lidar_data["data"].reshape(-1, 3)

            # Filter points by distance to remove self-intersection (robot hitting itself)
            # Configurable via cfg, defaults: min=0.3m (robot body), max=100m
            min_range = getattr(self.cfg.sensor.lidar, 'min_range', 0.3)
            max_range = getattr(self.cfg.sensor.lidar, 'max_range', 100.0)

            # Compute distance from sensor origin for each point
            distances = np.linalg.norm(points, axis=1)

            # Filter: keep points within valid range
            valid_mask = (distances >= min_range) & (distances <= max_range)
            filtered_points = points[valid_mask]

            # Skip publishing if no valid points
            if len(filtered_points) == 0:
                return

            # Create PointCloud2 message
            msg = PointCloud2()
            msg.header.stamp = current_time.to_msg()
            msg.header.frame_id = self.cfg.sensor.lidar.frame_id

            # Define point fields (x, y, z as FLOAT32)
            fields = [
                PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
                PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
                PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1),
            ]

            # Create point cloud from numpy array
            msg = point_cloud2.create_cloud(msg.header, fields, filtered_points)

            # Publish
            self.lidar_pub.publish(msg)

        except Exception as e:
            self.get_logger().warn(f"Failed to publish LiDAR data: {e}")

    def _create_camera_publishers(self):
        """Initialize camera image publishers using OmniGraph.

        This sets up ROS2 image publishers for color and depth cameras using
        Isaac Sim's OmniGraph nodes which handle the rendering and publishing.
        This approach is more reliable than the Replicator writers method.
        """
        if self.cameras is None:
            return

        # Check camera configuration
        if not hasattr(self.cfg.sensor, 'camera'):
            return

        cam_cfg = self.cfg.sensor.camera

        # Create OmniGraph for camera publishing
        for i, camera in enumerate(self.cameras):
            self._create_camera_graph(
                camera,
                color_enabled=getattr(cam_cfg, 'color_image', True),
                depth_enabled=getattr(cam_cfg, 'depth_image', True),
            )

    def _create_camera_graph(self, camera, color_enabled=True, depth_enabled=True):
        """Create OmniGraph for camera image publishing.

        Uses og.Controller.edit() to create render product and camera helper nodes
        directly, which is more reliable than Replicator writers.

        Args:
            camera: Camera instance with prim_path
            color_enabled: Whether to publish color images
            depth_enabled: Whether to publish depth images
        """
        # Topic naming
        color_topic = f"{self.namespace}/front_cam/color_image"
        depth_topic = f"{self.namespace}/front_cam/depth_image"
        frame_id = self.cfg.sensor.camera.frame_id

        keys = og.Controller.Keys

        # Build node list
        nodes_to_create = [
            ("OnPlaybackTick", "omni.graph.action.OnPlaybackTick"),
            ("IsaacCreateRenderProduct", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
        ]

        # Build values to set
        values_to_set = [
            ("IsaacCreateRenderProduct.inputs:cameraPrim", camera.prim_path),
            ("IsaacCreateRenderProduct.inputs:enabled", True),
            ("IsaacCreateRenderProduct.inputs:height", self.cfg.sensor.camera.height),
            ("IsaacCreateRenderProduct.inputs:width", self.cfg.sensor.camera.width),
        ]

        # Build connections
        connections = [
            ("OnPlaybackTick.outputs:tick", "IsaacCreateRenderProduct.inputs:execIn"),
        ]

        if color_enabled:
            nodes_to_create.append(
                ("ROS2CameraHelperColor", "isaacsim.ros2.bridge.ROS2CameraHelper")
            )
            values_to_set.extend([
                ("ROS2CameraHelperColor.inputs:type", "rgb"),
                ("ROS2CameraHelperColor.inputs:topicName", color_topic),
                ("ROS2CameraHelperColor.inputs:frameId", frame_id),
                ("ROS2CameraHelperColor.inputs:useSystemTime", False),
            ])
            connections.extend([
                ("IsaacCreateRenderProduct.outputs:execOut", "ROS2CameraHelperColor.inputs:execIn"),
                ("IsaacCreateRenderProduct.outputs:renderProductPath", "ROS2CameraHelperColor.inputs:renderProductPath"),
            ])

        if depth_enabled:
            nodes_to_create.append(
                ("ROS2CameraHelperDepth", "isaacsim.ros2.bridge.ROS2CameraHelper")
            )
            values_to_set.extend([
                ("ROS2CameraHelperDepth.inputs:type", "depth"),
                ("ROS2CameraHelperDepth.inputs:topicName", depth_topic),
                ("ROS2CameraHelperDepth.inputs:frameId", frame_id),
                ("ROS2CameraHelperDepth.inputs:useSystemTime", False),
            ])
            connections.extend([
                ("IsaacCreateRenderProduct.outputs:execOut", "ROS2CameraHelperDepth.inputs:execIn"),
                ("IsaacCreateRenderProduct.outputs:renderProductPath", "ROS2CameraHelperDepth.inputs:renderProductPath"),
            ])

        # Create the OmniGraph
        og.Controller.edit(
            {
                "graph_path": "/ColibriCameraROS2Graph",
                "evaluator_name": "execution",
            },
            {
                keys.CREATE_NODES: nodes_to_create,
                keys.SET_VALUES: values_to_set,
                keys.CONNECT: connections,
            },
        )

        if color_enabled:
            self.get_logger().info(f"Color image publisher created: {color_topic}")
        if depth_enabled:
            self.get_logger().info(f"Depth image publisher created: {depth_topic}")


# Completed: Phase 6.1 - ROS2 bridge with all publishers
# Completed: Phase 6.2 - Policy integration
# Completed: Phase 6.3 - Navigation metrics
# Completed: Phase 6.4 - LiDAR sensor support
# Completed: Phase 6.5 - Camera image publishing (color + depth)
