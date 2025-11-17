"""ROS2 launch file for Colibri G1 Digital Twin.

This launch file starts Isaac Sim with the ROS2 bridge and optionally RViz2.

Usage:
    ros2 launch launch/isaac_sim_ros2.launch.py
    ros2 launch launch/isaac_sim_ros2.launch.py use_rviz:=true

TODO Phase 6.3: Complete launch file implementation
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    """Generate launch description for Colibri G1 sim2sim."""

    # Declare launch arguments
    use_rviz_arg = DeclareLaunchArgument(
        "use_rviz",
        default_value="false",
        description="Launch RViz2 for visualization",
    )

    rviz_config_arg = DeclareLaunchArgument(
        "rviz_config",
        default_value="rviz/colibri_g1.rviz",
        description="Path to RViz2 configuration file",
    )

    # Get launch configurations
    use_rviz = LaunchConfiguration("use_rviz")
    rviz_config = LaunchConfiguration("rviz_config")

    # RViz2 node (conditional)
    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        arguments=["-d", rviz_config],
        condition=IfCondition(use_rviz),
        output="screen",
    )

    # TODO Phase 6.3: Add Isaac Sim launch
    # Note: Isaac Sim is typically launched via Python script, not ROS2 launch
    # This launch file primarily handles ROS2 nodes like RViz2

    # Build launch description
    return LaunchDescription(
        [
            # Arguments
            use_rviz_arg,
            rviz_config_arg,
            # Nodes
            rviz_node,
        ]
    )


# TODO Phase 6.3: Add more ROS2 nodes (rqt, plotjuggler, etc.)
# TODO Phase 6.4: Add sensor-related nodes (image_view, point_cloud viewers)
