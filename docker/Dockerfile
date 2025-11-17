# Multi-stage Dockerfile for Colibri G1 Digital Twin with ROS2
# Phase 6: Sim2Sim ROS2 Integration
#
# Build: docker build -t colibri_g1_ros2:latest -f docker/Dockerfile .
# Run: docker-compose up or ./docker/launch.sh sim2sim
#
# References:
#   - NVIDIA Isaac Sim 5.1.0: https://catalog.ngc.nvidia.com/orgs/nvidia/containers/isaac-sim
#   - Isaac Lab Docker Guide: https://isaac-sim.github.io/IsaacLab/main/source/deployment/docker.html
#   - ROS2 Humble: https://docs.ros.org/en/humble/
#   - isaac-go2-ros2 Dockerfile: Reference implementation

######################################################################
# Stage 1: Isaac Sim 5.1.0 Base
# - Latest Isaac Sim with multi-arch support
# - Runs as rootless user by default
######################################################################

FROM nvcr.io/nvidia/isaac-sim:5.1.0 AS isaac_base

LABEL org.opencontainers.image.title="Colibri G1 Digital Twin ROS2"
LABEL org.opencontainers.image.authors="Colibri G1 Team"
LABEL org.opencontainers.image.version="0.1.0"
LABEL org.opencontainers.image.description="Isaac Sim 5.1.0 + Isaac Lab 2.2 + ROS2 Humble + Colibri G1 Digital Twin"

# Set environment variables
ENV LANG=C.UTF-8
ENV DEBIAN_FRONTEND=noninteractive
ENV ACCEPT_EULA=Y
ENV PRIVACY_CONSENT=Y

######################################################################
# Stage 2: Install ROS2 Humble
# - ROS2 Humble Desktop (includes RViz2)
# - TF2 packages for transforms
# - CycloneDDS middleware for better performance
######################################################################

FROM isaac_base AS ros2_layer

USER root

# Set timezone non-interactively
RUN ln -fs /usr/share/zoneinfo/UTC /etc/localtime

# Install locale and basic tools
RUN apt-get update && apt-get install -y \
    locales \
    software-properties-common \
    curl \
    gnupg \
    lsb-release \
    wget \
    && locale-gen en_US en_US.UTF-8 \
    && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 \
    && add-apt-repository universe \
    && rm -rf /var/lib/apt/lists/*

ENV LANG=en_US.UTF-8

# Install ROS2 apt source (latest method)
RUN export ROS_APT_SOURCE_VERSION=$(curl -s https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | grep -F "tag_name" | awk -F'"' '{print $4}') \
    && curl -L -o /tmp/ros2-apt-source.deb "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.$(. /etc/os-release && echo $VERSION_CODENAME)_all.deb" \
    && dpkg -i /tmp/ros2-apt-source.deb \
    && rm /tmp/ros2-apt-source.deb

# Resolve dependency conflicts (from isaac-go2-ros2 experience)
RUN apt-get update && apt-get upgrade -y \
    && apt-get install -y --allow-downgrades \
    libbrotli1=1.0.9-2build6 \
    && apt-mark hold libbrotli1 \
    && apt-get install -y \
    libfreetype6-dev \
    libfontconfig1-dev \
    && rm -rf /var/lib/apt/lists/*

# Install ROS2 Humble Desktop with key packages
RUN apt-get update && apt-get install -y \
    ros-humble-desktop \
    ros-humble-rmw-cyclonedds-cpp \
    ros-humble-tf2-ros \
    ros-humble-tf2-geometry-msgs \
    ros-humble-foxglove-bridge \
    ros-humble-cv-bridge \
    python3-colcon-common-extensions \
    python3-rosdep \
    && rm -rf /var/lib/apt/lists/*

# Initialize rosdep
RUN rosdep init || true && rosdep update

######################################################################
# Stage 3: Install Development Tools & Isaac Lab
# - Git, vim, tmux, htop for development
# - Clone and install Isaac Lab 2.2+
# - Link Isaac Sim installation
######################################################################

FROM ros2_layer AS isaac_lab_layer

USER root

# Install development tools
RUN apt-get update && apt-get install -y \
    tmux \
    htop \
    tree \
    vim \
    git \
    wget \
    curl \
    unzip \
    bash-completion \
    build-essential \
    cmake \
    libglib2.0-0 \
    ncurses-term \
    && rm -rf /var/lib/apt/lists/*

# Set Isaac Sim paths
ENV ISAACSIM_ROOT_PATH=/isaac-sim
ENV ISAACLAB_PATH=/workspace/IsaacLab
ENV DOCKER_USER_HOME=/root

# Clone Isaac Lab repository (latest compatible with Isaac Sim 5.1.0)
RUN git clone https://github.com/isaac-sim/IsaacLab.git ${ISAACLAB_PATH} && \
    cd ${ISAACLAB_PATH} && \
    chmod +x isaaclab.sh

# Create symbolic link to Isaac Sim
RUN ln -sf ${ISAACSIM_ROOT_PATH} ${ISAACLAB_PATH}/_isaac_sim

# Install toml dependency for extension parsing
RUN ${ISAACLAB_PATH}/isaaclab.sh -p -m pip install toml

# Install apt dependencies for Isaac Lab extensions
RUN ${ISAACLAB_PATH}/isaaclab.sh -p ${ISAACLAB_PATH}/tools/install_deps.py apt ${ISAACLAB_PATH}/source && \
    apt -y autoremove && apt clean autoclean && \
    rm -rf /var/lib/apt/lists/*

# Create necessary cache directories (for singularity compatibility)
RUN mkdir -p ${ISAACSIM_ROOT_PATH}/kit/cache && \
    mkdir -p ${DOCKER_USER_HOME}/.cache/ov && \
    mkdir -p ${DOCKER_USER_HOME}/.cache/pip && \
    mkdir -p ${DOCKER_USER_HOME}/.cache/nvidia/GLCache &&  \
    mkdir -p ${DOCKER_USER_HOME}/.nv/ComputeCache && \
    mkdir -p ${DOCKER_USER_HOME}/.nvidia-omniverse/logs && \
    mkdir -p ${DOCKER_USER_HOME}/.local/share/ov/data && \
    mkdir -p ${DOCKER_USER_HOME}/Documents

# Install Isaac Lab dependencies (use pip cache for efficiency)
RUN --mount=type=cache,target=${DOCKER_USER_HOME}/.cache/pip \
    ${ISAACLAB_PATH}/isaaclab.sh --install

# HACK: Remove problematic quadprog dependency (known Isaac Lab issue)
RUN ${ISAACLAB_PATH}/isaaclab.sh -p -m pip uninstall -y quadprog || true

# Add Isaac Lab aliases to bashrc
RUN echo "export ISAACLAB_PATH=${ISAACLAB_PATH}" >> ${HOME}/.bashrc && \
    echo "alias isaaclab=${ISAACLAB_PATH}/isaaclab.sh" >> ${HOME}/.bashrc && \
    echo "alias python=${ISAACLAB_PATH}/_isaac_sim/python.sh" >> ${HOME}/.bashrc

######################################################################
# Stage 4: Install Colibri G1 Digital Twin Extension
# - Copy project source code
# - Install extension in editable mode
# - Install ROS2 Python packages
######################################################################

FROM isaac_lab_layer AS colibri_extension

USER root

# Copy extension source (files to exclude defined in .dockerignore)
COPY . /workspace/uniandes_g1_colibri/digital_twin_colibri_g1

# Set working directory
WORKDIR /workspace/uniandes_g1_colibri/digital_twin_colibri_g1

# Install Colibri G1 extension in editable mode
RUN ${ISAACLAB_PATH}/isaaclab.sh -p -m pip install -e source/digital_twin_colibri_g1

# Install ROS2 Python packages (using Isaac Sim's Python)
RUN ${ISAACLAB_PATH}/isaaclab.sh -p -m pip install --no-cache-dir \
    rclpy \
    geometry-msgs \
    nav-msgs \
    sensor-msgs \
    visualization-msgs \
    std-msgs \
    rosgraph-msgs

######################################################################
# Stage 5: Final Configuration
# - Additional Python packages
# - Environment variables
# - Entrypoint setup
######################################################################

FROM colibri_extension AS final

USER root

# Install additional Python packages for visualization and utilities
RUN ${ISAACLAB_PATH}/isaaclab.sh -p -m pip install --no-cache-dir \
    opencv-python \
    matplotlib \
    hydra-core

# Copy entrypoint script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set working directory
WORKDIR /workspace/uniandes_g1_colibri/digital_twin_colibri_g1

# Set environment variables
ENV ISAAC_SIM_PATH=/isaac-sim
ENV ISAACLAB_PATH=/workspace/IsaacLab
ENV ROS_DISTRO=humble
ENV ROS_DOMAIN_ID=0
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ENV PYTHONUNBUFFERED=1
ENV NVIDIA_DRIVER_CAPABILITIES=all

# Source ROS2 in bashrc
RUN echo "source /opt/ros/humble/setup.bash" >> ${HOME}/.bashrc && \
    echo "export ROS_DOMAIN_ID=${ROS_DOMAIN_ID}" >> ${HOME}/.bashrc && \
    echo "export RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION}" >> ${HOME}/.bashrc

# Cleanup to reduce image size
RUN apt-get autoremove -y && \
    apt-get autoclean -y && \
    apt-get clean -y && \
    rm -rf /var/lib/apt/lists/*

# Entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command: run sim2sim
CMD ["sim2sim"]

# Final labels
LABEL org.opencontainers.image.base.name="nvcr.io/nvidia/isaac-sim:5.1.0"
LABEL org.opencontainers.image.source="https://github.com/uniandes/colibri_g1_digital_twin"
LABEL org.opencontainers.image.vendor="Universidad de los Andes"
LABEL org.opencontainers.image.licenses="BSD-3-Clause"

######################################################################
# Build Complete!
#
# Image includes:
#   - Isaac Sim 5.1.0
#   - Isaac Lab 2.2+ (latest)
#   - ROS2 Humble Desktop + RViz2
#   - CycloneDDS middleware
#   - Colibri G1 Digital Twin extension
#   - All dependencies for sim2sim deployment
#
# Total stages: 5
# Base size: ~20-25GB (Isaac Sim base)
# Additional: ~5-8GB (ROS2 + Isaac Lab + extensions)
######################################################################
