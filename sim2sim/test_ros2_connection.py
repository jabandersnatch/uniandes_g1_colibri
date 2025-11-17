"""Test ROS2 connection and topic publishing.

This script tests the ROS2 bridge without Isaac Sim to verify ROS2 setup.

Usage:
    python sim2sim/test_ros2_connection.py
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String
import time


class TestNode(Node):
    """Simple test node for ROS2 verification."""

    def __init__(self):
        super().__init__("colibri_g1_test_node")

        # Create test publishers
        self.pose_pub = self.create_publisher(PoseStamped, "/colibri_g1/test/pose", 10)
        self.status_pub = self.create_publisher(String, "/colibri_g1/test/status", 10)

        # Create timer
        self.timer = self.create_timer(1.0, self.timer_callback)  # 1 Hz

        self.count = 0
        self.get_logger().info("Test node initialized")

    def timer_callback(self):
        """Publish test messages."""
        # Publish pose
        pose_msg = PoseStamped()
        pose_msg.header.stamp = self.get_clock().now().to_msg()
        pose_msg.header.frame_id = "map"
        pose_msg.pose.position.x = float(self.count)
        pose_msg.pose.position.y = 0.0
        pose_msg.pose.position.z = 0.0
        pose_msg.pose.orientation.w = 1.0
        self.pose_pub.publish(pose_msg)

        # Publish status
        status_msg = String()
        status_msg.data = f"Test message {self.count}"
        self.status_pub.publish(status_msg)

        self.get_logger().info(f"Published test messages (count: {self.count})")
        self.count += 1


def main():
    """Main function."""
    print("[INFO] Starting ROS2 connection test...")

    # Initialize ROS2
    rclpy.init()

    # Create test node
    node = TestNode()

    print("[INFO] Test node created. Publishing to:")
    print("[INFO]   /colibri_g1/test/pose")
    print("[INFO]   /colibri_g1/test/status")
    print("[INFO]")
    print("[INFO] In another terminal, run:")
    print("[INFO]   ros2 topic list")
    print("[INFO]   ros2 topic echo /colibri_g1/test/status")
    print("[INFO]")
    print("[INFO] Press Ctrl+C to stop")

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        print("\n[INFO] Stopping test node...")

    # Cleanup
    node.destroy_node()
    rclpy.shutdown()
    print("[INFO] Test complete")


if __name__ == "__main__":
    main()
