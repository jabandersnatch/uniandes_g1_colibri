# Docker Deployment Evidence

## 4. Multi-Stage Docker Build

### 4.1 Build Architecture

The Dockerfile implements a **6-stage multi-stage build** for efficient layering and caching.

**File:** `docker/Dockerfile` (~365 lines)

### 4.2 Build Stages

```
Stage 1: isaac_base         - Isaac Sim 4.5.0 (Ubuntu 22.04)
    ↓
Stage 2: ros2_layer         - ROS2 Humble + Unitree dependencies
    ↓
Stage 3: unitree_msgs_layer - Build Unitree ROS2 messages
    ↓
Stage 4: isaac_lab_layer    - Install Isaac Lab + Miniconda
    ↓
Stage 5: colibri_extension  - Install Colibri G1 extension
    ↓
Stage 6: final              - Runtime configuration
```

### 4.3 Stage 1: Isaac Sim Base

```dockerfile
FROM nvcr.io/nvidia/isaac-sim:4.5.0 AS isaac_base

LABEL org.opencontainers.image.title="Colibri G1 Digital Twin ROS2"
LABEL org.opencontainers.image.version="0.2.0"
LABEL org.opencontainers.image.description="Isaac Sim 4.5.0 + Isaac Lab 2.2 + ROS2 Humble + Unitree G1 Messages"

ENV LANG=C.UTF-8
ENV DEBIAN_FRONTEND=noninteractive
ENV ACCEPT_EULA=Y
ENV PRIVACY_CONSENT=Y
```

**Key Decision:** Isaac Sim 4.5.0 chosen for:
- Ubuntu 22.04 base (official ROS2 Humble support)
- Stable physics engine
- Compatibility with Isaac Lab 2.2

### 4.4 Stage 2: ROS2 Humble Installation

```dockerfile
FROM isaac_base AS ros2_layer

# Install ROS2 GPG key
RUN curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
    -o /usr/share/keyrings/ros-archive-keyring.gpg

# Install ROS2 Humble Desktop with Unitree dependencies
RUN apt-get update && apt-get install -y \
    ros-humble-desktop \
    ros-humble-rmw-cyclonedds-cpp \      # CycloneDDS (Unitree requirement)
    ros-humble-rosidl-generator-dds-idl \ # Message generation
    ros-humble-tf2-ros \
    ros-humble-foxglove-bridge \
    python3-colcon-common-extensions \
    python3-rosdep \
    libyaml-cpp-dev
```

**Unitree-Specific Dependencies:**
- `ros-humble-rmw-cyclonedds-cpp`: DDS middleware for Unitree robots
- `ros-humble-rosidl-generator-dds-idl`: Required for message compilation
- `libyaml-cpp-dev`: Configuration file parsing

### 4.5 Stage 3: Unitree Message Compilation

```dockerfile
FROM ros2_layer AS unitree_msgs_layer

# Copy unitree message packages
COPY unitree_msgs/unitree_api /unitree_ros2_ws/src/unitree_api
COPY unitree_msgs/unitree_go /unitree_ros2_ws/src/unitree_go
COPY unitree_msgs/unitree_hg /unitree_ros2_ws/src/unitree_hg

# Build Unitree message packages
RUN /bin/bash -c "source /opt/ros/humble/setup.bash && \
    cd /unitree_ros2_ws && \
    colcon build --packages-select unitree_api unitree_go unitree_hg --executor sequential"

# Verify build succeeded
RUN /bin/bash -c "source /unitree_ros2_ws/install/setup.bash && \
    python3 -c \"import unitree_hg.msg; print('[SUCCESS] unitree_hg.msg importable')\""
```

**Message Packages:**
- `unitree_api`: Common API messages (all robots)
- `unitree_go`: Go2/B2 messages (20 motors)
- `unitree_hg`: G1/H1-2 messages (35 motors) - **Required for G1**

### 4.6 Stage 4: Isaac Lab Installation

```dockerfile
FROM unitree_msgs_layer AS isaac_lab_layer

# Install Miniconda (isolated Python environment)
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh \
    -O /root/miniconda3/miniconda.sh && \
    bash /root/miniconda3/miniconda.sh -b -u -p /root/miniconda3

# Clone Isaac Lab
RUN git clone https://github.com/isaac-sim/IsaacLab.git ${ISAACLAB_PATH} && \
    ln -sf ${ISAACSIM_ROOT_PATH} ${ISAACLAB_PATH}/_isaac_sim

# Create conda environment
RUN cd ${ISAACLAB_PATH} && ./isaaclab.sh --conda isaaclab

# CRITICAL: Pin NumPy to <2.0 for Isaac Sim compatibility
RUN echo "numpy<2.0" > /tmp/constraints.txt
ENV PIP_CONSTRAINT=/tmp/constraints.txt

# Install Isaac Lab
RUN cd ${ISAACLAB_PATH} && \
    bash -c "eval \"\$(conda shell.bash hook)\" && conda activate isaaclab && \
    ./isaaclab.sh --install"
```

**NumPy Pinning:** Isaac Sim 4.5.0's scipy is compiled against NumPy 1.x. NumPy 2.x causes binary incompatibility.

### 4.7 Stage 5: Extension Installation

```dockerfile
FROM isaac_lab_layer AS colibri_extension

# Copy extension source
COPY . /workspace/uniandes_g1_colibri/digital_twin_colibri_g1
WORKDIR /workspace/uniandes_g1_colibri/digital_twin_colibri_g1

# Install in editable mode
RUN bash -c "eval \"\$(conda shell.bash hook)\" && \
    conda activate isaaclab && \
    pip install -e source/digital_twin_colibri_g1"
```

### 4.8 Stage 6: Final Configuration

```dockerfile
FROM colibri_extension AS final

# Set CycloneDDS as RMW (required for Unitree)
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ENV ROS_DOMAIN_ID=0

# Add to PYTHONPATH
ENV PYTHONPATH="/workspace/uniandes_g1_colibri/digital_twin_colibri_g1/source:\
${ISAACLAB_PATH}/source/isaaclab:\
/unitree_ros2_ws/install:${PYTHONPATH}"

# Source ROS2 and Unitree workspace
RUN echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc && \
    echo "source /unitree_ros2_ws/install/setup.bash" >> ~/.bashrc

ENTRYPOINT ["/entrypoint.sh"]
CMD ["sim2sim"]
```

### 4.9 Docker Compose Configuration

**File:** `docker/docker-compose.yaml`

```yaml
version: '3.8'

services:
  isaac_sim_ros2:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    image: colibri_g1_ros2:latest
    container_name: colibri_g1_sim2sim

    # GPU access
    runtime: nvidia
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

    # Network (host mode for ROS2)
    network_mode: host

    # Display
    environment:
      - DISPLAY=${DISPLAY}
      - NVIDIA_DRIVER_CAPABILITIES=all
      - ROS_DOMAIN_ID=0
      - RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

    volumes:
      - /tmp/.X11-unix:/tmp/.X11-unix:rw
      - ~/.Xauthority:/root/.Xauthority:rw
      - ../logs:/workspace/uniandes_g1_colibri/digital_twin_colibri_g1/logs

    command: sim2sim

  rviz2:
    image: osrf/ros:humble-desktop
    container_name: colibri_g1_rviz2
    network_mode: host
    environment:
      - DISPLAY=${DISPLAY}
      - ROS_DOMAIN_ID=0
    volumes:
      - /tmp/.X11-unix:/tmp/.X11-unix:rw
      - ../rviz:/rviz
    command: rviz2 -d /rviz/colibri_g1.rviz
```

### 4.10 Entrypoint Script

**File:** `docker/entrypoint.sh`

```bash
#!/bin/bash
set -e

# Source ROS2
source /opt/ros/humble/setup.bash
source /unitree_ros2_ws/install/setup.bash

# Activate conda environment
eval "$(conda shell.bash hook)"
conda activate isaaclab

# Set environment
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=0

# Execute command
case "$1" in
  sim2sim)
    cd /workspace/uniandes_g1_colibri/digital_twin_colibri_g1
    python sim2sim/isaac_colibri_g1_ros2.py
    ;;
  bash)
    exec /bin/bash
    ;;
  *)
    exec "$@"
    ;;
esac
```

### 4.11 Build and Run Commands

```bash
# Build Docker image (30-60 min first time)
docker-compose -f docker/docker-compose.yaml build

# Run sim2sim
docker-compose -f docker/docker-compose.yaml up isaac_sim_ros2

# Check ROS2 topics
docker exec -it colibri_g1_sim2sim bash -c "\
    source /opt/ros/humble/setup.bash && \
    source /unitree_ros2_ws/install/setup.bash && \
    ros2 topic list"

# Launch RViz2
docker-compose -f docker/docker-compose.yaml run --rm rviz2

# Interactive shell
docker-compose -f docker/docker-compose.yaml run --rm isaac_sim_ros2 bash
```

### 4.12 Image Specifications

| Component | Details |
|-----------|---------|
| Base Image | `nvcr.io/nvidia/isaac-sim:4.5.0` |
| OS | Ubuntu 22.04 |
| Python | 3.10 |
| ROS2 | Humble (LTS until 2027) |
| DDS | CycloneDDS |
| Isaac Lab | 2.2+ |
| Total Size | ~30-35 GB |

### 4.13 Troubleshooting Guide

**Network Bridge Error:**
```
Error starting userland proxy: listen tcp 0.0.0.0:8080: bind: address already in use
```
**Solution:** Reboot system (kernel/module mismatch with veth module)

**GPU Not Detected:**
```bash
# Install nvidia-container-toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

**X11 Permission Denied:**
```bash
xhost +local:docker
```

**ROS2 Topics Not Visible:**
- Ensure `ROS_DOMAIN_ID=0` matches between containers
- Verify `network_mode: host` in docker-compose.yaml
- Check CycloneDDS is set: `echo $RMW_IMPLEMENTATION`
