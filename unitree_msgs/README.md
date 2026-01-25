# Unitree ROS2 Message Packages

This directory contains Unitree ROS2 message packages copied from the
[unitree_ros2](https://github.com/unitreerobotics/unitree_ros2) repository.

## Contents

- `unitree_api/` - Common API messages (all robots)
- `unitree_go/` - Go2/B2 messages (quadrupeds, 20 motors)
- `unitree_hg/` - G1/H1-2 messages (humanoids, 35 motors)

## Purpose

These packages are needed for Docker builds of the Colibri G1 Digital Twin
to enable sim-to-real compatibility with the real Unitree G1 robot.

## Key Messages (unitree_hg)

- `LowState.msg` - Motor states + IMU data (published to `/lowstate`)
- `LowCmd.msg` - Motor commands (subscribed from `/lowcmd`)
- `MotorState.msg` - Individual motor state
- `MotorCmd.msg` - Individual motor command
- `IMUState.msg` - IMU sensor data

## Source

Copied from: `unitree_ros2/cyclonedds_ws/src/unitree/`

## Usage

During Docker build, these packages are copied and built with colcon:

```dockerfile
COPY unitree_msgs/unitree_api /unitree_ros2_ws/src/unitree_api
COPY unitree_msgs/unitree_go /unitree_ros2_ws/src/unitree_go
COPY unitree_msgs/unitree_hg /unitree_ros2_ws/src/unitree_hg

RUN source /opt/ros/humble/setup.bash && \
    cd /unitree_ros2_ws && \
    colcon build --packages-select unitree_api unitree_go unitree_hg
```
