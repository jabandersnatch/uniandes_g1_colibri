#!/bin/bash
# Entrypoint script for Colibri G1 Digital Twin Docker container
# Phase 6: Sim2Sim ROS2 Integration

set -e

# Source ROS2 environment
echo "[INFO] Sourcing ROS2 Humble..."
source /opt/ros/humble/setup.bash

# CRITICAL: Source Unitree ROS2 workspace (must be BEFORE conda activation)
# This makes unitree_hg, unitree_go, unitree_api available to Python
echo "[INFO] Sourcing Unitree ROS2 workspace..."
source /unitree_ros2_ws/install/setup.bash

# Source Conda environment (following isaac-go2-ros2 pattern)
echo "[INFO] Activating conda environment 'isaaclab'..."
eval "$(/root/miniconda3/bin/conda shell.bash hook)"
conda activate isaaclab

# Set environment variables
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}
export ISAAC_SIM_PATH=${ISAAC_SIM_PATH:-/isaac-sim}
export ISAACLAB_PATH=${ISAACLAB_PATH:-/workspace/IsaacLab}
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$ISAAC_SIM_PATH/exts/omni.isaac.ml_archive/pip_prebundle

# CRITICAL: Set RMW implementation for Unitree robots (uses CycloneDDS)
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# Print environment info
echo "[INFO] Environment configured:"
echo "[INFO]   ROS_DOMAIN_ID: $ROS_DOMAIN_ID"
echo "[INFO]   RMW_IMPLEMENTATION: $RMW_IMPLEMENTATION"
echo "[INFO]   ISAAC_SIM_PATH: $ISAAC_SIM_PATH"
echo "[INFO]   ISAACLAB_PATH: $ISAACLAB_PATH"
echo "[INFO]   DISPLAY: $DISPLAY"
echo ""

# Verify conda environment is active
echo "[INFO] Python location: $(which python)"

# CRITICAL: Verify unitree_hg module is importable
echo "[INFO] Checking Unitree message packages..."
python -c "from unitree_hg.msg import LowState, LowCmd; print('[SUCCESS] Unitree messages (unitree_hg) imported successfully')" || echo "[ERROR] Failed to import unitree_hg - workspace not properly sourced!"

# Verify extension installation
echo "[INFO] Checking digital_twin_colibri_g1 installation..."
python -c "import digital_twin_colibri_g1; print('[SUCCESS] Extension found at:', digital_twin_colibri_g1.__file__)" || echo "[WARNING] Extension not found in Python path"
echo ""

# Handle different run modes
case "$1" in
    sim2sim)
        echo "[INFO] Starting Sim2Sim ROS2 mode..."
        cd /workspace/uniandes_g1_colibri/digital_twin_colibri_g1
        # Use Python directly from conda environment with Isaac Sim's library path
        exec python sim2sim/isaac_colibri_g1_ros2.py
        ;;

    rviz)
        echo "[INFO] Starting RViz2..."
        exec ros2 run rviz2 rviz2 -d /workspace/uniandes_g1_colibri/digital_twin_colibri_g1/rviz/colibri_g1.rviz
        ;;

    test_ros2)
        echo "[INFO] Starting ROS2 connection test..."
        cd /workspace/uniandes_g1_colibri/digital_twin_colibri_g1
        # Use Python directly from conda environment with Isaac Sim's library path
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
