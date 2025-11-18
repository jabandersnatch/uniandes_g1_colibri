# ROS2 Integration - Quick Start Guide

This guide will help you get started with the ROS2 sim2sim integration for the Colibri G1 digital twin in under 30 minutes.

## Prerequisites

✅ NVIDIA GPU (GTX 1060+ / RTX 2060+)
✅ 16+ GB RAM
✅ 50+ GB free disk space
✅ Linux (Ubuntu 22.04 recommended, Arch also supported via Docker)

## Installation

### Step 1: Install Docker + NVIDIA Container Toolkit

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/libnvidia-container/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

**Verify**:
```bash
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
# Should show your GPU info
```

### Step 2: Enable X11 Forwarding

```bash
xhost +local:docker
```

### Step 3: Build Docker Image

```bash
cd /path/to/digital_twin_colibri_g1/

# Build (takes 30-60 minutes first time)
docker-compose -f docker/docker-compose.yaml build

# Or with helper script
./docker/launch.sh build
```

**⚠️ Troubleshooting**: If you encounter a Docker network bridge error ("operation not supported"), you may need to:
1. Reboot your system (if kernel was recently updated)
2. Load the veth kernel module: `sudo modprobe veth`
3. See `docker/NETWORK_TROUBLESHOOTING.md` for detailed solutions

**Docker Image Details**:
- Base: Isaac Sim 5.1.0 (NVIDIA official)
- Includes: Isaac Lab 2.2+, ROS2 Humble, CycloneDDS
- Size: ~28-30 GB
- Build stages: 5 (Isaac base → ROS2 → Isaac Lab → Extension → Finalize)

## Quick Start

### Run Sim2Sim with ROS2

**Terminal 1** - Launch Isaac Sim with ROS2 bridge:
```bash
./docker/launch.sh sim2sim
```

**Terminal 2** - Check ROS2 topics:
```bash
# Enter container
./docker/launch.sh enter

# Inside container:
ros2 topic list
ros2 topic echo /colibri_g1/odom
ros2 topic hz /colibri_g1/joint_states
```

**Terminal 3** - Visualize in RViz2:
```bash
./docker/launch.sh rviz
```

### Verify Everything Works

1. **Isaac Sim GUI** should show:
   - G1 robot in Colibri Lab environment
   - Green goal spheres (turning blue when reached)
   - Robot navigating autonomously

2. **ROS2 topics** should publish:
   ```bash
   ros2 topic hz /colibri_g1/odom
   # Expected: ~50 Hz
   ```

3. **RViz2** should display:
   - Robot model
   - Odometry path trail
   - TF tree (map → base_link)
   - Goal markers

## Common Commands

### Docker Operations

```bash
# Build image
./docker/launch.sh build

# Run sim2sim
./docker/launch.sh sim2sim

# Launch RViz2
./docker/launch.sh rviz

# Interactive shell
./docker/launch.sh enter

# Stop containers
./docker/launch.sh stop
```

### ROS2 Commands (inside container)

```bash
# List all topics
ros2 topic list

# Monitor odometry
ros2 topic echo /colibri_g1/odom

# Check publishing rate
ros2 topic hz /colibri_g1/joint_states

# View TF tree
ros2 run tf2_tools view_frames

# Publish velocity command (manual control)
ros2 topic pub /colibri_g1/cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.5, y: 0.0, z: 0.0}}"
```

### Monitoring & Debugging

```bash
# Check container logs
docker logs -f <container_id>

# GPU usage
nvidia-smi

# ROS2 graph visualization
ros2 run rqt_graph rqt_graph
```

## Configuration

Edit `cfg/ros2_sim.yaml` to customize:

```yaml
# Simulation Settings
num_envs: 1              # Number of robots
freq: 50                 # Control frequency (Hz)

# ROS2 Settings
ros2:
  namespace: "colibri_g1"
  publish_rate: 50       # Topic publish rate

# Policy Settings
policy:
  checkpoint: "logs/rsl_rl/isaac-colibri-g1-v0/<TIMESTAMP>/model_10000.pt"
  deterministic: true

# Sensor Settings (Phase 4+)
sensor:
  enable_camera: false
  enable_lidar: false
```

## ROS2 Topics

### Published (50 Hz)

| Topic | Type | Description |
|-------|------|-------------|
| `/colibri_g1/odom` | nav_msgs/Odometry | Robot pose + velocity |
| `/colibri_g1/joint_states` | sensor_msgs/JointState | 29 joint positions/velocities |
| `/colibri_g1/pose` | geometry_msgs/PoseStamped | Simplified pose |
| `/colibri_g1/goal_marker` | visualization_msgs/Marker | Goal visualization (1 Hz) |
| `/clock` | rosgraph_msgs/Clock | Simulation time |

### Subscribed (Optional)

| Topic | Type | Description |
|-------|------|-------------|
| `/colibri_g1/cmd_vel` | geometry_msgs/Twist | External velocity commands |

## Troubleshooting

### Issue: GPU not detected

**Error**: `could not select device driver "" with capabilities: [[gpu]]`

**Solution**:
```bash
# Reinstall NVIDIA Container Toolkit
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# Verify
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

### Issue: X11 permission denied

**Error**: `Error: Can't open display: :0`

**Solution**:
```bash
xhost +local:docker
echo $DISPLAY  # Should show :0 or :1
```

### Issue: ROS2 topics not visible

**Solution**:
```bash
# Check ROS_DOMAIN_ID
echo $ROS_DOMAIN_ID  # Should be 0

# Verify network mode in docker-compose.yaml
# Should have: network_mode: host
```

### Issue: Slow performance (RTF < 0.5)

**Solution**:
```yaml
# Edit cfg/ros2_sim.yaml
freq: 25              # Reduce from 50 Hz
sensor:
  enable_camera: false
  enable_lidar: false

# Or use headless mode (no GUI)
```

## Performance Targets

| Configuration | Expected RTF | GPU Memory |
|---------------|--------------|------------|
| GUI without sensors | 0.8-0.9 | 4-5 GB |
| Headless without sensors | 0.95-1.0 | 3-4 GB |

**RTF** = Real-Time Factor (1.0 = real-time)

## Next Steps

### Learn More
- [SIM2SIM_ROS2.md](docs/SIM2SIM_ROS2.md) - Complete architecture and design decisions
- [DOCKER_SETUP.md](docs/DOCKER_SETUP.md) - Detailed Docker setup and troubleshooting
- [PHASES.md](docs/PHASES.md) - Implementation roadmap (Phase 6)

### Extend Functionality
- **Add sensors** (Phase 6.4): Enable camera/LiDAR in config
- **External goals** (Phase 6.5): Publish to `/colibri_g1/goal`
- **Sim2sim transfer** (Phase 6.5): Test with second simulator

### Development Workflow

1. **Make changes** to ROS2 bridge (`ros2/colibri_g1_ros2_bridge.py`)
2. **Rebuild image**:
   ```bash
   ./docker/launch.sh build
   ```
3. **Test changes**:
   ```bash
   ./docker/launch.sh sim2sim
   ros2 topic echo /colibri_g1/odom
   ```
4. **Iterate** until working

## Project Structure

```
digital_twin_colibri_g1/
├── ros2/                   # ROS2 bridge implementation
├── sim2sim/                # Sim2sim entry points
├── cfg/                    # Configuration files
├── docker/                 # Docker build files
├── rviz/                   # RViz2 configs
└── docs/                   # Documentation
    ├── SIM2SIM_ROS2.md    # Architecture guide
    └── DOCKER_SETUP.md    # Docker guide
```

## Support

- **Documentation Issues**: See [docs/DOCKER_SETUP.md](docs/DOCKER_SETUP.md) troubleshooting section
- **ROS2 Questions**: Check [Isaac Sim ROS2 Tutorials](https://docs.isaacsim.omniverse.nvidia.com/latest/ros2_tutorials/ros2_landing_page.html)
- **Docker Problems**: Review [Docker docs](https://docs.docker.com/) and [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/)

## Quick Reference Card

```bash
# Build
./docker/launch.sh build

# Run
./docker/launch.sh sim2sim

# Visualize
./docker/launch.sh rviz

# Debug
./docker/launch.sh enter
ros2 topic list
ros2 topic echo /colibri_g1/odom

# Stop
./docker/launch.sh stop
```

---

**Status**: Phase 6.0 Documentation ✅ Complete | Phase 6.1 Implementation 🏗️ In Progress

**Last Updated**: 2025-11-17
