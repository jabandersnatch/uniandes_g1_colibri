"""ROS2 bridge for Colibri G1 digital twin.

This module implements the main ROS2 node for publishing robot state and
subscribing to commands.

Reference: isaac-go2-ros2/ros2/g1_ros2_bridge.py
"""

import rclpy
from rclpy.node import Node
from rclpy.time import Time as ROSTime
import torch

# ROS2 message types
from geometry_msgs.msg import PoseStamped, Twist, TransformStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import JointState
from std_msgs.msg import Float32, String
from visualization_msgs.msg import Marker
from rosgraph_msgs.msg import Clock

# TF2
import tf2_ros
from geometry_msgs.msg import TransformStamped


class RobotDataManager(Node):
    """ROS2 node for managing Colibri G1 robot data.

    Publishes:
        /colibri_g1/odom (nav_msgs/Odometry): Robot odometry
        /colibri_g1/joint_states (sensor_msgs/JointState): Joint states
        /colibri_g1/pose (geometry_msgs/PoseStamped): Simplified pose
        /colibri_g1/goal_marker (visualization_msgs/Marker): Goal visualization
        /clock (rosgraph_msgs/Clock): Simulation time

    Subscribes:
        /colibri_g1/cmd_vel (geometry_msgs/Twist): External velocity commands (optional)

    Args:
        env: Isaac Lab environment
        cfg: Configuration object (from ros2_sim.yaml)
    """

    def __init__(self, env, cfg):
        super().__init__("colibri_g1_ros2_bridge")

        # Store references
        self.env = env
        self.cfg = cfg
        self.robot = env.scene["robot"]

        # ROS2 namespace
        self.namespace = cfg.ros2.namespace

        # Initialize publishers
        self._init_publishers()

        # Initialize subscribers
        self._init_subscribers()

        # Initialize TF broadcaster
        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)

        # State tracking
        self.last_goal_pos = None
        self.last_goal_marker_time = 0

        self.get_logger().info(f"ROS2 bridge initialized for {self.namespace}")

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

        # Clock publisher
        self.clock_pub = self.create_publisher(Clock, "/clock", 10)

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

    def publish_data(self):
        """Publish all robot data (called every simulation step)."""
        current_time = self.env.sim_time

        # Publish high-frequency topics (50 Hz)
        self._publish_odometry(current_time)
        self._publish_joint_states(current_time)
        self._publish_pose(current_time)
        self._publish_transforms(current_time)
        self._publish_clock(current_time)

        # Publish low-frequency topics (conditionally)
        if self._should_publish_goal_marker(current_time):
            self._publish_goal_marker(current_time)
            self._publish_navigation_metrics(current_time)

    def _publish_odometry(self, current_time):
        """Publish /colibri_g1/odom.

        Args:
            current_time: Simulation time (seconds)
        """
        # TODO: Implement odometry publishing
        # Reference: isaac-go2-ros2/ros2/g1_ros2_bridge.py
        pass

    def _publish_joint_states(self, current_time):
        """Publish /colibri_g1/joint_states.

        Args:
            current_time: Simulation time (seconds)
        """
        # TODO: Implement joint states publishing
        pass

    def _publish_pose(self, current_time):
        """Publish /colibri_g1/pose.

        Args:
            current_time: Simulation time (seconds)
        """
        # TODO: Implement pose publishing
        pass

    def _publish_transforms(self, current_time):
        """Publish TF transforms (map → base_link).

        Args:
            current_time: Simulation time (seconds)
        """
        # TODO: Implement TF broadcasting
        pass

    def _publish_clock(self, current_time):
        """Publish /clock.

        Args:
            current_time: Simulation time (seconds)
        """
        msg = Clock()
        msg.clock = self._to_ros_time(current_time)
        self.clock_pub.publish(msg)

    def _publish_goal_marker(self, current_time):
        """Publish /colibri_g1/goal_marker.

        Args:
            current_time: Simulation time (seconds)
        """
        # TODO: Implement goal marker visualization
        pass

    def _publish_navigation_metrics(self, current_time):
        """Publish navigation metrics (goal pose, distance, status).

        Args:
            current_time: Simulation time (seconds)
        """
        # TODO: Implement navigation metrics publishing
        pass

    def _should_publish_goal_marker(self, current_time):
        """Check if goal marker should be published.

        Args:
            current_time: Simulation time (seconds)

        Returns:
            bool: True if goal marker should be published
        """
        # Publish at 1 Hz or when goal changes
        return (current_time - self.last_goal_marker_time) >= 1.0

    def _to_ros_time(self, sim_time):
        """Convert simulation time to ROS time.

        Args:
            sim_time: Simulation time (seconds)

        Returns:
            ROSTime: ROS timestamp
        """
        sec = int(sim_time)
        nanosec = int((sim_time - sec) * 1e9)
        return ROSTime(seconds=sec, nanoseconds=nanosec).to_msg()


# TODO Phase 6.1: Implement all publisher methods
# TODO Phase 6.2: Add policy integration
# TODO Phase 6.3: Add navigation metrics
# TODO Phase 6.4: Add sensor support (camera, LiDAR)
