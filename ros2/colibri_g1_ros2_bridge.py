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
        from .colibri_g1_ros2_utils import torch_to_ros_point, torch_to_ros_quaternion, torch_to_ros_vector3

        # Create odometry message
        msg = Odometry()
        msg.header.stamp = self._to_ros_time(current_time)
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
        msg.header.stamp = self._to_ros_time(current_time)

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
        msg.header.stamp = self._to_ros_time(current_time)
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
        transform.header.stamp = self._to_ros_time(current_time)
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
        from .colibri_g1_ros2_utils import torch_to_ros_point, compute_euclidean_distance

        # Get goal position from command manager
        # goal_position is 2D in base frame, but we need world frame for visualization
        # Get the current goal from the command manager
        goal_cmd = self.env.command_manager.get_command("goal_position")

        # Transform goal from base frame to world frame
        # Get robot position and orientation
        root_state = self.robot.data.root_state_w[0]
        robot_pos = root_state[:3]  # [x, y, z]
        robot_quat = root_state[3:7]  # [w, x, y, z]

        # Goal is in base frame (2D: x, y), need to transform to world
        # For simplicity, we'll get the goal position directly from the command manager
        # The goal position stored internally should be in world frame
        # Check if goal_cmd has world frame position
        if hasattr(goal_cmd, "goal_pos_w"):
            goal_pos_3d = torch.cat([goal_cmd.goal_pos_w[0, :2], torch.zeros(1, device=goal_cmd.goal_pos_w.device)])
        else:
            # Fallback: use goal position from command buffer (base frame)
            # We need to transform it to world frame
            # For now, add robot z-position to make it 3D
            goal_pos_2d = goal_cmd.pos[0]  # Shape: (2,) in base frame
            # This is a simplified transformation - goal is relative to base, at ground level
            goal_pos_3d = torch.tensor(
                [robot_pos[0] + goal_pos_2d[0], robot_pos[1] + goal_pos_2d[1], robot_pos[2].item() * 0.1],
                device=robot_pos.device,
            )

        # Compute distance to goal for color selection
        distance = compute_euclidean_distance(robot_pos[:2], goal_pos_3d[:2])

        # Create marker message
        marker = Marker()
        marker.header.stamp = self._to_ros_time(current_time)
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
        goal_pose.header.stamp = self._to_ros_time(current_time)
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
        goal_cmd = self.env.command_manager.get_command("goal_position")
        root_state = self.robot.data.root_state_w[0]
        robot_pos = root_state[:3]

        # Get goal position in world frame (same logic as in _publish_goal_marker)
        if hasattr(goal_cmd, "goal_pos_w"):
            goal_pos_3d = torch.cat([goal_cmd.goal_pos_w[0, :2], torch.zeros(1, device=goal_cmd.goal_pos_w.device)])
        else:
            goal_pos_2d = goal_cmd.pos[0]
            goal_pos_3d = torch.tensor(
                [robot_pos[0] + goal_pos_2d[0], robot_pos[1] + goal_pos_2d[1], robot_pos[2].item() * 0.1],
                device=robot_pos.device,
            )

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
