#!/bin/bash
# Entrypoint script for Colibri G1 Digital Twin Docker container
# Phase 6: Sim2Sim ROS2 Integration

set -e

# Source ROS2 environment
echo "[INFO] Sourcing ROS2 Humble..."
source /opt/ros/humble/setup.bash

# Source Isaac Lab environment (if using venv)
if [ -f /workspace/IsaacLab/isaaclab/bin/activate ]; then
    echo "[INFO] Sourcing Isaac Lab environment..."
    source /workspace/IsaacLab/isaaclab/bin/activate
fi

# Set environment variables
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}
export ISAAC_SIM_PATH=${ISAAC_SIM_PATH:-/isaac-sim}
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$ISAAC_SIM_PATH/exts/omni.isaac.ml_archive/pip_prebundle

# Print environment info
echo "[INFO] Environment configured:"
echo "[INFO]   ROS_DOMAIN_ID: $ROS_DOMAIN_ID"
echo "[INFO]   ISAAC_SIM_PATH: $ISAAC_SIM_PATH"
echo "[INFO]   DISPLAY: $DISPLAY"
echo ""

# Handle different run modes
case "$1" in
    sim2sim)
        echo "[INFO] Starting Sim2Sim ROS2 mode..."
        cd /workspace/uniandes_g1_colibri/digital_twin_colibri_g1
        exec python sim2sim/isaac_colibri_g1_ros2.py
        ;;

    rviz)
        echo "[INFO] Starting RViz2..."
        exec ros2 run rviz2 rviz2 -d /workspace/uniandes_g1_colibri/digital_twin_colibri_g1/rviz/colibri_g1.rviz
        ;;

    test_ros2)
        echo "[INFO] Starting ROS2 connection test..."
        cd /workspace/uniandes_g1_colibri/digital_twin_colibri_g1
        exec python sim2sim/test_ros2_connection.py
        ;;

    bash)
        echo "[INFO] Starting interactive bash shell..."
        exec /bin/bash
        ;;

    *)
        echo "[ERROR] Unknown command: $1"
        echo "Usage: docker run colibri_g1_ros2 [sim2sim|rviz|test_ros2|bash]"
        echo ""
        echo "Examples:"
        echo "  docker run colibri_g1_ros2 sim2sim     # Run sim2sim with ROS2"
        echo "  docker run colibri_g1_ros2 rviz        # Launch RViz2"
        echo "  docker run colibri_g1_ros2 test_ros2   # Test ROS2 connection"
        echo "  docker run colibri_g1_ros2 bash        # Interactive shell"
        exit 1
        ;;
esac

# TODO Phase 6.1: Add health check endpoint
# TODO Phase 6.2: Add graceful shutdown handling
