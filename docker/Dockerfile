# Multi-stage Dockerfile for Colibri G1 Digital Twin with ROS2
# Phase 6: Sim2Sim ROS2 Integration
#
# Build: docker build -t colibri_g1_ros2:latest -f docker/Dockerfile .
# Run: docker-compose up
#
# References:
#   - NVIDIA Isaac Sim containers: https://docs.omniverse.nvidia.com/isaacsim/
#   - ROS2 Humble: https://docs.ros.org/en/humble/

# TODO Phase 6.1: Update base image to Isaac Sim 5.0 when available
# Currently using 4.5.0 as placeholder - adjust based on actual Isaac Sim version
FROM nvcr.io/nvidia/isaac-sim:4.5.0 AS isaac_base

# Stage 2: Install ROS2 Humble
FROM isaac_base AS ros2_layer

# Install basic tools
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    lsb-release \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Add ROS2 Humble repository
RUN curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/ros2.list > /dev/null

# Install ROS2 Humble Desktop (includes RViz2, rqt, etc.)
RUN apt-get update && apt-get install -y \
    ros-humble-desktop \
    ros-humble-tf2-ros \
    ros-humble-tf2-geometry-msgs \
    python3-colcon-common-extensions \
    python3-rosdep \
    && rm -rf /var/lib/apt/lists/*

# Initialize rosdep
RUN rosdep init || true && rosdep update

# Source ROS2 setup in bashrc
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc

# Stage 3: Install Isaac Lab (assumes IsaacLab/ directory in parent)
FROM ros2_layer AS isaac_lab_layer

# TODO Phase 6.1: Adjust path based on actual Isaac Lab location
# Copy Isaac Lab source (adjust path as needed)
# COPY ../../IsaacLab /workspace/IsaacLab

# Install Isaac Lab
# WORKDIR /workspace/IsaacLab
# RUN ./isaaclab.sh --install

# Placeholder for Phase 6.1
RUN echo "Isaac Lab installation will be added in Phase 6.1" && \
    mkdir -p /workspace/IsaacLab

# Stage 4: Install Digital Twin Extension
FROM isaac_lab_layer AS colibri_extension

# Copy extension source
COPY . /workspace/uniandes_g1_colibri/digital_twin_colibri_g1

# Install extension
WORKDIR /workspace/uniandes_g1_colibri/digital_twin_colibri_g1
# TODO Phase 6.1: Uncomment when Isaac Lab is installed
# RUN pip install -e source/digital_twin_colibri_g1

# Install ROS2 Python packages
RUN pip install --no-cache-dir \
    rclpy \
    geometry-msgs \
    nav-msgs \
    sensor-msgs \
    visualization-msgs

# Stage 5: Final configuration
FROM colibri_extension AS final

# Install additional Python packages
RUN pip install --no-cache-dir \
    opencv-python \
    matplotlib

# Set working directory
WORKDIR /workspace/uniandes_g1_colibri/digital_twin_colibri_g1

# Copy entrypoint script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set environment variables
ENV ISAAC_SIM_PATH=/isaac-sim
ENV ROS_DOMAIN_ID=0
ENV PYTHONUNBUFFERED=1

# Entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command: run sim2sim
CMD ["sim2sim"]

# Labels
LABEL maintainer="Colibri G1 Digital Twin Team"
LABEL description="Isaac Sim + ROS2 Humble + Colibri G1 Digital Twin"
LABEL version="0.1.0"

# TODO Phase 6.1: Complete Docker build and test
# TODO Phase 6.2: Add volume mounts for logs and checkpoints
# TODO Phase 6.3: Optimize image size (multi-stage cleanup)
