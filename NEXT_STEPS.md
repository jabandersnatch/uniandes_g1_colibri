# Phase 6: Sim2Sim ROS2 Integration - Next Steps

## Current Status ✅

**Branch**: `feature/sim2sim-ros2`

**Completed Work** (5 commits):
1. ✅ Phase 6 scaffolding (ROS2 bridge structure, Docker configs, launch scripts)
2. ✅ ROS2 bridge implementation (6 publishers: odom, joints, pose, TF, markers, metrics)
3. ✅ Policy integration (load RSL-RL checkpoints, run inference)
4. ✅ Docker configuration (Isaac Sim 5.1.0, Isaac Lab 2.2+, ROS2 Humble)
5. ✅ Dependency management system (extension.toml, setup.py, comprehensive docs)
6. ✅ Network troubleshooting (kernel mismatch diagnosis and solutions)

**Current Blocker**: System needs reboot to load kernel 6.17.8 with veth module

---

## Immediate Next Step: Reboot System 🔄

### Why?
Your system is running kernel 6.17.7-arch1-1, but modules are installed for 6.17.8-arch1-1. Docker requires the `veth` kernel module which is only available after reboot.

### How?
```bash
sudo reboot
```

---

## After Reboot: Build Docker Image 🐳

### Step 1: Verify Kernel and Load veth Module

```bash
# Check kernel version
uname -r
# Expected: 6.17.8-arch1-1

# Load veth module
sudo modprobe veth

# Verify it loaded
lsmod | grep veth
# Expected output: veth                   24576  0
```

### Step 2: Build Docker Image

```bash
cd /home/jamendez/Documents/uniandes/MISIS/thesis/uniandes_g1_colibri/digital_twin_colibri_g1

# Option A: Build with docker-compose (recommended)
docker-compose -f docker/docker-compose.yaml build

# Option B: Build with progress output (for debugging)
docker-compose -f docker/docker-compose.yaml build --progress=plain

# Option C: Direct docker build
docker build -t colibri_g1_ros2:latest -f docker/Dockerfile .
```

### Expected Build Time
- **Total**: 30-60 minutes (first build, no cache)
- **Image size**: ~25-30 GB

**Build Stages**:
1. Isaac Sim 5.1.0 base (~15 GB, mostly cached if available)
2. ROS2 Humble installation (~5-10 min)
3. Isaac Lab 2.2+ installation (~15-20 min)
4. Colibri G1 extension (~2 min)
5. Final configuration (~1 min)

### Step 3: Verify Successful Build

```bash
# Check image exists
docker images | grep colibri_g1_ros2

# Expected output:
# colibri_g1_ros2   latest   <image-id>   <timestamp>   ~28GB
```

---

## After Successful Build: Test Container 🧪

### Test 1: Container Starts

```bash
# Allow X11 forwarding
xhost +local:docker

# Start container interactively
docker-compose -f docker/docker-compose.yaml run --rm isaac_sim_ros2 bash

# Inside container, verify installations:
which ros2
which python
echo $ISAACLAB_PATH
echo $ROS_DISTRO

# Exit container
exit
```

### Test 2: ROS2 Topics (Sim2Sim Mode)

```bash
# Terminal 1: Start sim2sim
docker-compose -f docker/docker-compose.yaml up isaac_sim_ros2

# Terminal 2: Check ROS2 topics
docker exec -it colibri_g1_sim2sim bash -c "source /opt/ros/humble/setup.bash && ros2 topic list"

# Expected topics:
# /clock
# /colibri_g1/odom
# /colibri_g1/pose
# /colibri_g1/joint_states
# /colibri_g1/goal_marker
# /colibri_g1/navigation_metrics
# /tf
```

### Test 3: RViz2 Visualization

```bash
# Terminal 1: sim2sim running (from Test 2)

# Terminal 2: Launch RViz2
docker-compose -f docker/docker-compose.yaml run --rm rviz2

# In RViz2:
# - Add RobotModel display
# - Add TF display
# - Add Marker display for goal visualization
# - Verify robot visualization updates
```

---

## Troubleshooting 🔧

### Build Fails

**Issue**: Network bridge error persists after reboot
**Solution**: See `docker/NETWORK_TROUBLESHOOTING.md` for 5 alternative solutions

**Issue**: Out of disk space
```bash
# Clean Docker cache
docker system prune -a
df -h  # Check available space (need ~35GB free)
```

**Issue**: Isaac Sim image download fails
```bash
# Check internet connection
ping nvcr.io
# Retry build with --no-cache flag
```

### Container Won't Start

**Issue**: GPU not detected
```bash
# Verify nvidia-docker runtime
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi

# If fails, install nvidia-container-toolkit:
# https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html
```

**Issue**: X11 permission denied
```bash
xhost +local:docker
echo $DISPLAY  # Should show :0 or :1
```

### ROS2 Topics Not Publishing

**Issue**: Topics don't appear
```bash
# Check ROS_DOMAIN_ID
docker exec -it colibri_g1_sim2sim bash -c "echo \$ROS_DOMAIN_ID"
# Should be: 0

# Check if sim2sim script is running
docker logs colibri_g1_sim2sim

# Manually run sim2sim inside container
docker exec -it colibri_g1_sim2sim bash
source /opt/ros/humble/setup.bash
cd /workspace/uniandes_g1_colibri/digital_twin_colibri_g1
python sim2sim/isaac_colibri_g1_ros2.py
```

---

## Phase 6 Completion Checklist

After successful testing, Phase 6 is complete when:

- [ ] Docker image builds successfully
- [ ] Container starts without errors
- [ ] Isaac Sim GUI opens (if not headless)
- [ ] ROS2 topics are published at expected rates:
  - [ ] `/colibri_g1/odom` at 50 Hz
  - [ ] `/colibri_g1/joint_states` at 50 Hz
  - [ ] `/colibri_g1/pose` at 10 Hz
  - [ ] `/tf` transforms published
  - [ ] `/colibri_g1/goal_marker` updates with navigation
- [ ] Policy loads from checkpoint successfully
- [ ] Robot moves autonomously toward goals
- [ ] RViz2 visualization works
- [ ] Logs are saved to `logs/` directory

---

## Next Phase: Phase 7 (Future Work)

Once Phase 6 is validated:

1. **Sim2Real Transfer**: Deploy to physical Colibri G1 robot
   - Adapt ROS2 topics to match real robot interfaces
   - Add sensor feedback integration (IMU, cameras)
   - Implement safety constraints and estop

2. **Advanced Navigation**:
   - Add obstacle avoidance
   - Integrate perception (cameras, LiDAR)
   - Dynamic goal updates

3. **Multi-Robot Coordination**:
   - Scale to multiple G1 robots
   - Implement coordination protocols

---

## Documentation

- **Docker networking**: `docker/NETWORK_TROUBLESHOOTING.md`
- **Dependency management**: `docs/DEPENDENCIES.md`
- **ROS2 integration**: `README_ROS2.md`
- **Phase planning**: `docs/PHASES.md`
- **Sim2sim architecture**: `docs/SIM2SIM_ROS2.md`

---

## Git Workflow

```bash
# After successful validation, merge to main
git checkout main
git merge feature/sim2sim-ros2
git push origin main

# Create tag for Phase 6 completion
git tag -a v0.2.0-phase6 -m "Phase 6: Sim2Sim ROS2 Integration"
git push origin v0.2.0-phase6
```

---

**Last Updated**: 2025-11-17
**Status**: Waiting for system reboot to complete Docker build
