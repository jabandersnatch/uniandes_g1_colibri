# Multi-stage Dockerfile for Colibri G1 Digital Twin with ROS2
# Phase 6: Sim2Sim ROS2 Integration
#
# Build: docker build -t colibri_g1_ros2:latest -f docker/Dockerfile .
# Run: docker-compose up or ./docker/launch.sh sim2sim
#
# References:
#   - NVIDIA Isaac Sim 4.5.0: https://catalog.ngc.nvidia.com/orgs/nvidia/containers/isaac-sim
#   - Isaac Lab Docker Guide: https://isaac-sim.github.io/IsaacLab/main/source/deployment/docker.html
#   - ROS2 Humble: https://docs.ros.org/en/humble/
#   - isaac-go2-ros2 Dockerfile: Reference implementation

######################################################################
# Stage 1: Isaac Sim 4.5.0 Base (Ubuntu 22.04)
# - Compatible with ROS2 Humble (official support)
# - Following isaac-go2-ros2 working configuration
######################################################################

FROM nvcr.io/nvidia/isaac-sim:4.5.0 AS isaac_base

LABEL org.opencontainers.image.title="Colibri G1 Digital Twin ROS2"
LABEL org.opencontainers.image.authors="Colibri G1 Team"
LABEL org.opencontainers.image.version="0.1.0"
LABEL org.opencontainers.image.description="Isaac Sim 4.5.0 + Isaac Lab 2.2 + ROS2 Humble + Colibri G1 Digital Twin"

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

# Install ROS2 GPG key and repository (stable method)
RUN curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | tee /etc/apt/sources.list.d/ros2.list > /dev/null

# Resolve dependency conflicts and install required libraries
# Note: Isaac Sim 4.5.0 uses Ubuntu 22.04 which has better ROS2 Humble compatibility
# Fix libbrotli version conflict: Isaac Sim base has newer version from PPA
RUN apt-get update && apt-get upgrade -y \
    && apt-get install -y --allow-downgrades \
    libbrotli1=1.0.9-2build6 \
    libbrotli-dev \
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

# Install Miniconda (following isaac-go2-ros2 pattern for conda isolation)
RUN mkdir -p ${DOCKER_USER_HOME}/miniconda3 \
    && wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ${DOCKER_USER_HOME}/miniconda3/miniconda.sh \
    && bash ${DOCKER_USER_HOME}/miniconda3/miniconda.sh -b -u -p ${DOCKER_USER_HOME}/miniconda3 \
    && rm ${DOCKER_USER_HOME}/miniconda3/miniconda.sh \
    && bash -c "source ${DOCKER_USER_HOME}/miniconda3/bin/activate && conda init --all"

# Add conda to PATH
ENV PATH="${DOCKER_USER_HOME}/miniconda3/bin:$PATH"

# Configure conda to avoid TOS issues (following isaac-go2-ros2)
RUN ${DOCKER_USER_HOME}/miniconda3/bin/conda config --remove channels defaults && \
    ${DOCKER_USER_HOME}/miniconda3/bin/conda config --add channels conda-forge && \
    ${DOCKER_USER_HOME}/miniconda3/bin/conda config --set channel_priority strict && \
    ${DOCKER_USER_HOME}/miniconda3/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main && \
    ${DOCKER_USER_HOME}/miniconda3/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r

# Clone Isaac Lab repository (compatible with Isaac Sim 4.5.0)
# Using conda environment like isaac-go2-ros2 for better dependency isolation
RUN git clone https://github.com/isaac-sim/IsaacLab.git ${ISAACLAB_PATH} && \
    cd ${ISAACLAB_PATH} && \
    chmod +x isaaclab.sh

# Create symbolic link to Isaac Sim
RUN ln -sf ${ISAACSIM_ROOT_PATH} ${ISAACLAB_PATH}/_isaac_sim

# Create conda environment for Isaac Lab (following isaac-go2-ros2 pattern)
# This isolates Isaac Lab dependencies from Isaac Sim's bundled packages
RUN cd ${ISAACLAB_PATH} && \
    ./isaaclab.sh --conda isaaclab

# Create necessary cache directories (for singularity compatibility)
RUN mkdir -p ${ISAACSIM_ROOT_PATH}/kit/cache && \
    mkdir -p ${DOCKER_USER_HOME}/.cache/ov && \
    mkdir -p ${DOCKER_USER_HOME}/.cache/pip && \
    mkdir -p ${DOCKER_USER_HOME}/.cache/nvidia/GLCache &&  \
    mkdir -p ${DOCKER_USER_HOME}/.nv/ComputeCache && \
    mkdir -p ${DOCKER_USER_HOME}/.nvidia-omniverse/logs && \
    mkdir -p ${DOCKER_USER_HOME}/.local/share/ov/data && \
    mkdir -p ${DOCKER_USER_HOME}/Documents

# CRITICAL: Create pip constraints file to enforce NumPy <2.0 across ALL installations
# Isaac Sim 4.5.0's bundled scipy is compiled against NumPy 1.x
# NumPy 2.x causes binary incompatibility errors
# This constraints file prevents ANY package from upgrading NumPy to 2.x
RUN echo "numpy<2.0" > /tmp/constraints.txt

# Set PIP_CONSTRAINT environment variable to apply constraints to all pip operations
ENV PIP_CONSTRAINT=/tmp/constraints.txt

# CRITICAL: Pin NumPy to <2.0 BEFORE installing Isaac Lab
# Combined with PIP_CONSTRAINT, this ensures NumPy stays at 1.x
RUN bash -c "eval \"\$(${DOCKER_USER_HOME}/miniconda3/bin/conda shell.bash hook)\" && conda activate isaaclab && pip install 'numpy<2.0'"

# Install Isaac Lab with conda environment activated (like isaac-go2-ros2)
# This ensures dependencies are installed in the isolated conda environment
# Must use the full conda path and activate via eval to initialize conda properly
# NOTE: PIP_CONSTRAINT env var (set above) ensures NumPy stays <2.0 during installation
RUN cd ${ISAACLAB_PATH} && \
    bash -c "eval \"\$(${DOCKER_USER_HOME}/miniconda3/bin/conda shell.bash hook)\" && conda activate isaaclab && ./isaaclab.sh --install"

# HACK: Remove problematic quadprog dependency (known Isaac Lab issue)
RUN bash -c "eval \"\$(${DOCKER_USER_HOME}/miniconda3/bin/conda shell.bash hook)\" && conda activate isaaclab && cd ${ISAACLAB_PATH} && ./isaaclab.sh -p -m pip uninstall -y quadprog" || true

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
# This will install dependencies from setup.py: psutil, rclpy
# CRITICAL: Use conda environment activation to ensure proper installation
# NOTE: PIP_CONSTRAINT env var ensures NumPy stays <2.0 during installation
RUN bash -c "eval \"\$(${DOCKER_USER_HOME}/miniconda3/bin/conda shell.bash hook)\" && \
    conda activate isaaclab && \
    cd /workspace/uniandes_g1_colibri/digital_twin_colibri_g1 && \
    pip install -e source/digital_twin_colibri_g1"

# Note: ROS2 message packages (geometry_msgs, nav_msgs, etc.) are already installed
# via APT in Stage 2 (ros-humble-desktop includes all standard message packages)
# They should NOT be installed via pip as they are C++ libraries with Python bindings

######################################################################
# Stage 5: Final Configuration
# - Additional Python packages
# - Environment variables
# - Entrypoint setup
######################################################################

FROM colibri_extension AS final

USER root

# Install additional Python packages for visualization and utilities
# Note: NumPy is already pinned to <2.0 in Stage 3 for Isaac Sim 4.5.0 compatibility
# NOTE: PIP_CONSTRAINT env var ensures NumPy stays <2.0 during installation
RUN bash -c "eval \"\$(${DOCKER_USER_HOME}/miniconda3/bin/conda shell.bash hook)\" && \
    conda activate isaaclab && \
    pip install --no-cache-dir opencv-python matplotlib hydra-core"

# CRITICAL: Verify NumPy version is <2.0 (fail build if not)
# This catches any accidental NumPy upgrades during installation
RUN bash -c "eval \"\$(${DOCKER_USER_HOME}/miniconda3/bin/conda shell.bash hook)\" && \
    conda activate isaaclab && \
    python -c 'import numpy; assert numpy.__version__.startswith(\"1.\"), f\"NumPy version {numpy.__version__} is not 1.x! Build failed.\"' && \
    echo \"✓ NumPy version verified: \$(python -c 'import numpy; print(numpy.__version__)')\" "

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

# CRITICAL: Add Isaac Lab and extension to PYTHONPATH so conda Python can find them
# This ensures the digital_twin_colibri_g1 module is importable
ENV PYTHONPATH="${ISAACLAB_PATH}/source/isaaclab:${ISAACLAB_PATH}/source/isaaclab_tasks:${ISAACLAB_PATH}/source/isaaclab_assets:/workspace/uniandes_g1_colibri/digital_twin_colibri_g1/source:${PYTHONPATH}"

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
LABEL org.opencontainers.image.base.name="nvcr.io/nvidia/isaac-sim:4.5.0"
LABEL org.opencontainers.image.source="https://github.com/uniandes/colibri_g1_digital_twin"
LABEL org.opencontainers.image.vendor="Universidad de los Andes"
LABEL org.opencontainers.image.licenses="BSD-3-Clause"

######################################################################
# Build Complete!
#
# Image includes:
#   - Isaac Sim 4.5.0 (Ubuntu 22.04)
#   - Isaac Lab 2.2+ in isolated conda environment (like isaac-go2-ros2)
#   - ROS2 Humble Desktop + RViz2 (officially supported on Ubuntu 22.04)
#   - CycloneDDS middleware
#   - Colibri G1 Digital Twin extension
#   - All dependencies for sim2sim deployment
#
# Key difference from previous builds:
#   - Uses conda environment to isolate Isaac Lab from Isaac Sim's bundled packages
#   - Prevents NumPy/SciPy version conflicts
#
# Total stages: 5
# Base size: ~20-25GB (Isaac Sim base)
# Additional: ~5-8GB (ROS2 + Isaac Lab + Miniconda + extensions)
######################################################################
