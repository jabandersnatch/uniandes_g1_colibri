# Docker Setup Guide - Colibri G1 ROS2 Sim2Sim

## Overview

This guide explains how to build and run the Colibri G1 digital twin with ROS2 integration in a Docker container. Docker solves several challenges:

1. **ROS2 Installation**: Difficult on Arch Linux → containerized ROS2 Humble
2. **Reproducibility**: Same environment across machines → consistent behavior
3. **Isaac Sim Dependencies**: Complex dependency management → pre-configured image
4. **Deployment**: Easy transfer to cloud/cluster → portable containers

**Target Platform**: Linux (Ubuntu, Arch, etc.) with NVIDIA GPU

---

## Prerequisites

### Host System Requirements

**Hardware**:
- ✅ NVIDIA GPU (GTX 1060 / RTX 2060 or better)
- ✅ 16 GB+ RAM (32 GB recommended)
- ✅ 50 GB+ free disk space (for Docker images + logs)

**Software**:
- ✅ Docker Engine 20.10+ ([installation guide](https://docs.docker.com/engine/install/))
- ✅ NVIDIA Container Toolkit ([installation guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html))
- ✅ X11 server (for GUI support) - pre-installed on most Linux distros

### Verify Prerequisites

**Check Docker**:
```bash
docker --version
# Expected: Docker version 20.10.0 or higher

docker run hello-world
# Expected: "Hello from Docker!" message
```

**Check NVIDIA Container Toolkit**:
```bash
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
# Expected: nvidia-smi output showing your GPU
```

**Check X11**:
```bash
echo $DISPLAY
# Expected: :0 or :1 (non-empty)

xhost +local:docker
# Expected: "access control disabled, clients can connect from any host"
```

---

## Quick Start

### 1. Build Docker Image

```bash
# Navigate to project root
cd /home/jamendez/Documents/uniandes/MISIS/thesis/uniandes_g1_colibri/digital_twin_colibri_g1/

# Build image (takes ~30-60 minutes first time)
./docker/launch.sh build

# Or manually:
docker-compose -f docker/docker-compose.yaml build
```

**Build Process**:
1. Downloads Isaac Sim base image (~10 GB)
2. Installs ROS2 Humble + dependencies (~5 GB)
3. Installs Isaac Lab + extensions
4. Configures environment variables
5. Total image size: ~20-25 GB

### 2. Run Sim2Sim with ROS2

```bash
# Launch Isaac Sim with ROS2 bridge
./docker/launch.sh sim2sim

# Or manually:
docker-compose -f docker/docker-compose.yaml up isaac_sim_ros2
```

**Expected Output**:
```
[INFO] Starting Isaac Sim ROS2 bridge...
[INFO] Loading environment: ColibriBuilding.usd
[INFO] Loading policy checkpoint: model_10000.pt
[INFO] ROS2 node initialized: colibri_g1_ros2_bridge
[INFO] Publishing topics:
  - /colibri_g1/odom (50 Hz)
  - /colibri_g1/joint_states (50 Hz)
  - /colibri_g1/goal_marker (1 Hz)
[INFO] Simulation running at 50 Hz (RTF: 0.85)
```

### 3. Monitor with RViz2 (Separate Terminal)

```bash
# Option A: Run RViz2 in container
./docker/launch.sh rviz

# Option B: Run RViz2 on host (if ROS2 Humble installed)
ros2 run rviz2 rviz2 -d rviz/colibri_g1.rviz
```

### 4. Inspect ROS2 Topics

```bash
# Enter running container
./docker/launch.sh enter

# Inside container:
ros2 topic list
ros2 topic echo /colibri_g1/odom
ros2 topic hz /colibri_g1/joint_states
```

### 5. Stop Container

```bash
# Graceful shutdown
./docker/launch.sh stop

# Or force stop:
docker-compose -f docker/docker-compose.yaml down
```

---

## Docker Architecture

### Image Layers

```
┌──────────────────────────────────────────────┐
│  colibri_g1_ros2:latest (Final Image)       │
│  - Digital twin extension installed          │
│  - Trained policy checkpoints                │
│  - RViz2 configuration files                 │
│  Size: ~25 GB                                │
└───────────────┬──────────────────────────────┘
                │
┌───────────────▼──────────────────────────────┐
│  isaac_lab_ros2_base (Intermediate Layer)   │
│  - Isaac Lab 2.2+ installed                  │
│  - ROS2 Humble + dependencies                │
│  - Python packages (rclpy, tf2_ros, etc.)    │
│  Size: ~18 GB                                │
└───────────────┬──────────────────────────────┘
                │
┌───────────────▼──────────────────────────────┐
│  nvcr.io/nvidia/isaac-sim:4.5.0 (Base)      │
│  - Isaac Sim framework                       │
│  - NVIDIA Omniverse dependencies             │
│  - CUDA, cuDNN, TensorRT libraries          │
│  Size: ~12 GB                                │
└──────────────────────────────────────────────┘
```

**Note**: This project uses Isaac Sim 4.5.0 for official ROS2 Humble support on Ubuntu 22.04. For Isaac Sim 5.0+, Ubuntu 24.04 is required with ROS2 Jazzy.

### Container Runtime Configuration

```yaml
# docker/docker-compose.yaml
services:
  isaac_sim_ros2:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    runtime: nvidia                    # NVIDIA GPU support
    environment:
      - DISPLAY=$DISPLAY               # X11 GUI forwarding
      - ROS_DOMAIN_ID=0                # ROS2 network isolation
      - NVIDIA_VISIBLE_DEVICES=all     # GPU access
    volumes:
      - /tmp/.X11-unix:/tmp/.X11-unix  # X11 socket
      - ../logs:/workspace/logs        # Training logs (persistent)
      - ../outputs:/workspace/outputs  # Simulation outputs
      - ../assets:/workspace/assets    # USD scenes (read-only)
    network_mode: host                 # ROS2 multicast support
    privileged: true                   # GPU access (alternative to runtime: nvidia)
    shm_size: '8gb'                    # Shared memory for large messages
```

**Key Configuration**:
- **runtime: nvidia**: Enables GPU passthrough via NVIDIA Container Toolkit
- **network_mode: host**: Required for ROS2 DDS multicast discovery (bypasses Docker bridge)
- **volumes**: Maps host directories into container for data persistence
- **shm_size**: Increases shared memory limit (default 64MB is too small for images/point clouds)

---

## Detailed Build Process

### Dockerfile Structure

**File**: `docker/Dockerfile`

```dockerfile
# Stage 1: Base Isaac Sim image
FROM nvcr.io/nvidia/isaac-sim:4.5.0 AS isaac_base

# Stage 2: Install ROS2 Humble
FROM isaac_base AS ros2_layer

# Add ROS2 Humble repository
RUN apt-get update && apt-get install -y curl gnupg lsb-release && \
    curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key | apt-key add - && \
    echo "deb http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" > /etc/apt/sources.list.d/ros2.list

# Install ROS2 Humble desktop (includes RViz2, rqt, etc.)
RUN apt-get update && apt-get install -y \
    ros-humble-desktop \
    ros-humble-tf2-ros \
    ros-humble-tf2-geometry-msgs \
    ros-humble-nav2-common \
    ros-humble-navigation2 \
    python3-colcon-common-extensions \
    python3-rosdep

# Initialize rosdep
RUN rosdep init && rosdep update

# Source ROS2 setup in bashrc
RUN echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc

# Stage 3: Install Isaac Lab
FROM ros2_layer AS isaac_lab_layer

# Copy Isaac Lab source (assumes IsaacLab/ directory in parent)
COPY ../../IsaacLab /workspace/IsaacLab

# Install Isaac Lab
WORKDIR /workspace/IsaacLab
RUN ./isaaclab.sh --install

# Verify installation
RUN python -c "import isaaclab; print(f'Isaac Lab {isaaclab.__version__} installed successfully')"

# Stage 4: Install Digital Twin Extension
FROM isaac_lab_layer AS colibri_extension

# Copy extension source
COPY . /workspace/uniandes_g1_colibri/digital_twin_colibri_g1

# Install extension
WORKDIR /workspace/uniandes_g1_colibri/digital_twin_colibri_g1
RUN pip install -e source/digital_twin_colibri_g1

# Verify extension registration
RUN python scripts/list_envs.py | grep "Isaac-Colibri-G1"

# Stage 5: Final configuration
FROM colibri_extension AS final

# Install additional Python packages
RUN pip install \
    rclpy \
    tf2-ros-py \
    opencv-python \
    matplotlib

# Copy ROS2 bridge code
COPY ros2/ /workspace/uniandes_g1_colibri/digital_twin_colibri_g1/ros2/
COPY sim2sim/ /workspace/uniandes_g1_colibri/digital_twin_colibri_g1/sim2sim/
COPY cfg/ /workspace/uniandes_g1_colibri/digital_twin_colibri_g1/cfg/
COPY rviz/ /workspace/uniandes_g1_colibri/digital_twin_colibri_g1/rviz/

# Set working directory
WORKDIR /workspace/uniandes_g1_colibri/digital_twin_colibri_g1

# Entrypoint script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["sim2sim"]  # Default command: run sim2sim
```

**Multi-Stage Build Benefits**:
- ✅ Smaller final image (intermediate layers discarded)
- ✅ Better caching (rebuilds only changed layers)
- ✅ Clearer dependency structure

### Entrypoint Script

**File**: `docker/entrypoint.sh`

```bash
#!/bin/bash
set -e

# Source ROS2 environment
source /opt/ros/humble/setup.bash

# Source Isaac Lab environment (if using venv)
if [ -f /workspace/IsaacLab/isaaclab/bin/activate ]; then
    source /workspace/IsaacLab/isaaclab/bin/activate
fi

# Set environment variables
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}
export ISAAC_SIM_PATH=/isaac-sim
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/isaac-sim/exts/omni.isaac.ml_archive/pip_prebundle

# Handle different run modes
case "$1" in
    sim2sim)
        echo "[INFO] Starting Sim2Sim ROS2 mode..."
        exec python sim2sim/isaac_colibri_g1_ros2.py
        ;;
    rviz)
        echo "[INFO] Starting RViz2..."
        exec ros2 run rviz2 rviz2 -d rviz/colibri_g1.rviz
        ;;
    bash)
        echo "[INFO] Starting interactive bash..."
        exec /bin/bash
        ;;
    *)
        echo "[ERROR] Unknown command: $1"
        echo "Usage: docker run colibri_g1_ros2 [sim2sim|rviz|bash]"
        exit 1
        ;;
esac
```

**Usage Examples**:
```bash
# Run sim2sim (default)
docker-compose up isaac_sim_ros2

# Run RViz2
docker-compose run --rm isaac_sim_ros2 rviz

# Interactive shell
docker-compose run --rm isaac_sim_ros2 bash
```

---

## Launch Script

**File**: `docker/launch.sh`

```bash
#!/bin/bash
# Helper script for common Docker operations

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKER_COMPOSE_FILE="$PROJECT_ROOT/docker/docker-compose.yaml"

# Enable X11 forwarding
enable_x11() {
    echo "[INFO] Enabling X11 forwarding..."
    xhost +local:docker
}

# Build Docker image
build() {
    echo "[INFO] Building Docker image..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" build
}

# Run sim2sim
sim2sim() {
    enable_x11
    echo "[INFO] Starting Sim2Sim ROS2..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" up isaac_sim_ros2
}

# Run RViz2
rviz() {
    enable_x11
    echo "[INFO] Starting RViz2..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" run --rm isaac_sim_ros2 rviz
}

# Enter container shell
enter() {
    echo "[INFO] Entering container..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" run --rm isaac_sim_ros2 bash
}

# Stop containers
stop() {
    echo "[INFO] Stopping containers..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" down
}

# Show help
help() {
    echo "Usage: $0 {build|sim2sim|rviz|enter|stop}"
    echo ""
    echo "Commands:"
    echo "  build    - Build Docker image"
    echo "  sim2sim  - Run sim2sim ROS2 bridge"
    echo "  rviz     - Launch RViz2 visualization"
    echo "  enter    - Enter container shell"
    echo "  stop     - Stop running containers"
}

# Main command handler
case "$1" in
    build)
        build
        ;;
    sim2sim)
        sim2sim
        ;;
    rviz)
        rviz
        ;;
    enter)
        enter
        ;;
    stop)
        stop
        ;;
    *)
        help
        exit 1
        ;;
esac
```

**Make executable**:
```bash
chmod +x docker/launch.sh
```

---

## Troubleshooting

### Issue 1: GPU Not Detected

**Symptoms**:
```
docker: Error response from daemon: could not select device driver "" with capabilities: [[gpu]]
```

**Solution**:
```bash
# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/libnvidia-container/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

**Verify**:
```bash
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

### Issue 2: X11 Permission Denied

**Symptoms**:
```
Error: Can't open display: :0
Authorization required, but no authorization protocol specified
```

**Solution**:
```bash
# Temporarily allow all local connections
xhost +local:docker

# Or more secure: allow specific user
xhost +SI:localuser:$(whoami)
```

**Verify**:
```bash
docker run --rm -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix ubuntu:22.04 \
    sh -c "apt-get update && apt-get install -y x11-apps && xclock"
# Should show clock GUI
```

### Issue 3: ROS2 Topics Not Visible

**Symptoms**:
```bash
ros2 topic list
# Shows only /rosout
```

**Possible Causes**:
1. **ROS_DOMAIN_ID mismatch** (container vs. host)
2. **Network mode not `host`**
3. **Firewall blocking multicast**

**Solution**:
```bash
# Check ROS_DOMAIN_ID
docker-compose run --rm isaac_sim_ros2 bash -c "echo \$ROS_DOMAIN_ID"
# Should match host: echo $ROS_DOMAIN_ID

# Verify network mode is 'host' in docker-compose.yaml
network_mode: host

# Disable firewall temporarily (testing only!)
sudo ufw disable
```

### Issue 4: Isaac Sim GUI Not Launching

**Symptoms**:
```
[Error] [omni.kit.app.plugin] No valid display found
```

**Solution**:
```bash
# Check DISPLAY variable
echo $DISPLAY
# Should be non-empty (e.g., :0)

# Test X11 forwarding
docker run --rm -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix ubuntu:22.04 \
    sh -c "apt-get update && apt-get install -y x11-apps && xeyes"
# Should show moving eyes

# If using Wayland (not X11), switch to X11 session
# Log out → select "Ubuntu on Xorg" at login screen
```

### Issue 5: Out of Shared Memory

**Symptoms**:
```
RuntimeError: DataLoader worker (pid 12345) is killed by signal: Bus error
```

**Solution**:
```yaml
# Add to docker-compose.yaml
services:
  isaac_sim_ros2:
    shm_size: '8gb'  # Increase from default 64MB
```

**Or use host IPC**:
```yaml
services:
  isaac_sim_ros2:
    ipc: host  # Share host's IPC namespace
```

### Issue 6: Slow Performance (Low RTF)

**Symptoms**:
```
Real Time Factor: 0.3 (should be ≥ 0.8)
```

**Solutions**:
1. **Use headless mode**:
   ```python
   # In sim2sim/isaac_colibri_g1_ros2.py
   app_launcher = AppLauncher(headless=True)
   ```

2. **Reduce rendering frequency**:
   ```python
   env_cfg.sim.render_interval = 16  # Render every 16 steps
   ```

3. **Lower control frequency**:
   ```yaml
   # In cfg/ros2_sim.yaml
   freq: 25  # Down from 50 Hz
   ```

4. **Disable sensors**:
   ```yaml
   sensor:
     enable_camera: false
     enable_lidar: false
   ```

---

## Volume Mounts & Data Persistence

### Default Volume Configuration

```yaml
volumes:
  # X11 socket (read-only, for GUI)
  - /tmp/.X11-unix:/tmp/.X11-unix:ro

  # Logs (persistent, read-write)
  - ../logs:/workspace/logs:rw

  # Outputs (persistent, read-write)
  - ../outputs:/workspace/outputs:rw

  # Assets (read-only, for USD scenes)
  - ../assets:/workspace/assets:ro

  # Checkpoints (persistent, read-only during inference)
  - ../logs/rsl_rl:/workspace/logs/rsl_rl:ro
```

### Accessing Container Data from Host

**Training logs**:
```bash
# Inside container
ls /workspace/logs/rsl_rl/isaac-colibri-g1-v0/

# On host (mapped via volume)
ls logs/rsl_rl/isaac-colibri-g1-v0/
```

**Simulation videos**:
```bash
# Videos saved in container
/workspace/outputs/videos/

# Accessible on host
outputs/videos/
```

---

## Advanced Configuration

### Multi-GPU Support

```yaml
services:
  isaac_sim_ros2:
    environment:
      - NVIDIA_VISIBLE_DEVICES=0,1  # Use GPUs 0 and 1
      - CUDA_VISIBLE_DEVICES=0,1
```

**Distributed training** (if added later):
```bash
docker-compose run --rm isaac_sim_ros2 \
  python scripts/rsl_rl/train.py --task=Isaac-Colibri-G1-v0 --distributed
```

### Custom ROS2 Domain

```yaml
services:
  isaac_sim_ros2:
    environment:
      - ROS_DOMAIN_ID=42  # Isolate from other ROS2 systems
```

**Use case**: Multiple developers on same network, each with different domain ID

### Headless Mode (No GUI)

```yaml
services:
  isaac_sim_ros2_headless:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    runtime: nvidia
    environment:
      - ROS_DOMAIN_ID=0
      # No DISPLAY, no X11 volumes
    volumes:
      - ../logs:/workspace/logs
      - ../outputs:/workspace/outputs
    network_mode: host
    command: ["python", "sim2sim/isaac_colibri_g1_ros2.py", "--headless"]
```

**Benefits**:
- ✅ Faster (no rendering overhead)
- ✅ Lower GPU memory usage
- ✅ Can run on headless servers / cloud

---

## Performance Benchmarks

### Expected Performance

| Configuration | RTF | GPU Memory | Notes |
|---------------|-----|------------|-------|
| GUI + Sensors (camera, LiDAR) | 0.6-0.7 | 6-8 GB | Full visualization |
| GUI without sensors | 0.8-0.9 | 4-5 GB | Recommended for development |
| Headless without sensors | 0.95-1.0 | 3-4 GB | Best for sim2sim testing |

**RTF** = Real-Time Factor (1.0 = real-time, >1.0 = faster than real-time)

### Optimization Checklist

- [ ] Use `--headless` if GUI not needed
- [ ] Disable unused sensors (`enable_camera: false`, `enable_lidar: false`)
- [ ] Reduce `render_interval` (e.g., 16 instead of 4)
- [ ] Lower control frequency (e.g., 25 Hz instead of 50 Hz)
- [ ] Use `network_mode: host` for lowest ROS2 latency
- [ ] Increase `shm_size` if using cameras/LiDAR (8 GB)
- [ ] Close other GPU applications (browsers, games, etc.)

---

## Deployment Checklist

### Before First Build

- [ ] NVIDIA drivers installed (470+)
- [ ] Docker installed (20.10+)
- [ ] NVIDIA Container Toolkit installed
- [ ] X11 forwarding enabled (`xhost +local:docker`)
- [ ] 50+ GB free disk space

### Build Process

- [ ] Clone repository with all submodules
- [ ] Verify `IsaacLab/` directory exists at `../../IsaacLab`
- [ ] Run `./docker/launch.sh build` (expect 30-60 minutes)
- [ ] Verify build success: `docker images | grep colibri_g1_ros2`

### First Run

- [ ] Run `./docker/launch.sh sim2sim`
- [ ] Verify Isaac Sim GUI launches
- [ ] Verify robot spawns in ColibriBuilding scene
- [ ] Verify ROS2 topics: `ros2 topic list` shows 5+ topics
- [ ] Verify TF tree: `ros2 run tf2_tools view_frames`
- [ ] Verify policy inference: robot moves toward goals
- [ ] Check RTF ≥ 0.8 (printed in terminal)

### Validation

- [ ] Run for 10+ minutes without crashes
- [ ] Monitor GPU memory (should be stable)
- [ ] Check goal reach rate (expect >20% in 20s episodes)
- [ ] Verify RViz2 visualization works
- [ ] Test interactive shell: `./docker/launch.sh enter`

---

## References

- [Docker Documentation](https://docs.docker.com/)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/)
- [Isaac Sim Docker Guide](https://docs.omniverse.nvidia.com/isaacsim/latest/installation/install_container.html)
- [ROS2 Humble Docker Images](https://hub.docker.com/_/ros)
- [X11 Forwarding with Docker](https://stackoverflow.com/questions/16296753/can-you-run-gui-applications-in-a-linux-docker-container)

---

## Summary

Docker deployment provides:

1. **Reproducible Environment**: Same setup across all machines
2. **Simplified ROS2 Installation**: No manual apt-get on Arch Linux
3. **GPU Passthrough**: Full Isaac Sim performance via NVIDIA Container Toolkit
4. **X11 GUI Support**: Visual debugging and RViz2 visualization
5. **Data Persistence**: Logs and outputs saved on host filesystem
6. **Isolation**: Multiple projects with different dependencies

**Next Steps**:
- Build Docker image: `./docker/launch.sh build`
- Run first sim2sim test: `./docker/launch.sh sim2sim`
- Explore RViz2: `./docker/launch.sh rviz`
- Read [SIM2SIM_ROS2.md](SIM2SIM_ROS2.md) for architecture details
