# Docker Unitree Messages Import Fix

## Problem

Docker container crashed with:
```
ModuleNotFoundError: No module named 'unitree_hg.msg'
```

This occurred when running:
```bash
docker-compose -f docker/docker-compose.yaml up isaac_sim_ros2
```

## Root Causes

### 1. Missing Workspace Sourcing in Entrypoint
The `docker/entrypoint.sh` script did **not** source the Unitree ROS2 workspace:

```bash
# OLD (WRONG):
source /opt/ros/humble/setup.bash
eval "$(/root/miniconda3/bin/conda shell.bash hook)"
conda activate isaaclab
# unitree_hg NOT in Python path!
```

The workspace was built in Dockerfile Stage 3, but never added to `PYTHONPATH` or `AMENT_PREFIX_PATH` at runtime.

### 2. Silent Build Failures in Dockerfile
Dockerfile Stage 3 had no verification that `colcon build` succeeded:

```bash
# OLD (WRONG):
RUN colcon build --packages-select unitree_api unitree_go unitree_hg --executor sequential
# No checking if build actually succeeded!
RUN echo "source /unitree_ros2_ws/install/setup.bash" >> /root/.bashrc
```

If colcon failed, the container would still build successfully but fail at runtime.

### 3. Missing RMW Implementation
The `RMW_IMPLEMENTATION` environment variable was not set in the entrypoint, causing DDS initialization issues.

## Solution

### Fix 1: Update `docker/entrypoint.sh`

**Source the Unitree workspace BEFORE conda activation:**

```bash
#!/bin/bash
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
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
```

**Verify workspace is sourced with Python import check:**

```bash
# CRITICAL: Verify unitree_hg module is importable
echo "[INFO] Checking Unitree message packages..."
python -c "from unitree_hg.msg import LowState, LowCmd; print('[SUCCESS] Unitree messages imported')" || \
  echo "[ERROR] Failed to import unitree_hg - workspace not properly sourced!"
```

### Fix 2: Update `docker/Dockerfile` Stage 3

**Add comprehensive build verification:**

```dockerfile
FROM ros2_layer AS unitree_msgs_layer

RUN mkdir -p /unitree_ros2_ws/src

COPY unitree_msgs/unitree_api /unitree_ros2_ws/src/unitree_api
COPY unitree_msgs/unitree_go /unitree_ros2_ws/src/unitree_go
COPY unitree_msgs/unitree_hg /unitree_ros2_ws/src/unitree_hg

# Build with explicit error checking
RUN /bin/bash -c "source /opt/ros/humble/setup.bash && \
    cd /unitree_ros2_ws && \
    echo 'Building Unitree message packages...' && \
    colcon build --packages-select unitree_api unitree_go unitree_hg --executor sequential"

# CRITICAL: Verify build succeeded
RUN if [ ! -f /unitree_ros2_ws/install/setup.bash ]; then \
      echo "[ERROR] colcon build failed! install/setup.bash not found."; \
      exit 1; \
    fi && \
    echo "[SUCCESS] Unitree workspace built successfully"

# Verify Python packages are importable
RUN /bin/bash -c "source /unitree_ros2_ws/install/setup.bash && \
    python -c \"import unitree_hg.msg; print('[SUCCESS] unitree_hg.msg importable')\" && \
    python -c \"import unitree_go.msg; print('[SUCCESS] unitree_go.msg importable')\" && \
    python -c \"import unitree_api.msg; print('[SUCCESS] unitree_api.msg importable')\""

RUN echo "source /unitree_ros2_ws/install/setup.bash" >> /root/.bashrc
```

### Fix 3: Update `docker/Dockerfile` Final Stage

**Add RMW implementation and improve PYTHONPATH:**

```dockerfile
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# PYTHONPATH order: Colibri -> Isaac Lab -> Unitree workspace
ENV PYTHONPATH="/workspace/uniandes_g1_colibri/digital_twin_colibri_g1/source:${ISAACLAB_PATH}/source/isaaclab:${ISAACLAB_PATH}/source/isaaclab_tasks:${ISAACLAB_PATH}/source/isaaclab_assets:/unitree_ros2_ws/install:${PYTHONPATH}"
```

## How Unitree Messages Work

### ROS2 Message Generation

Unitree message packages use `rosidl` to generate Python bindings:

1. **Input**: `.msg` files in `msg/` directory
   - `LowState.msg` (robot state)
   - `LowCmd.msg` (motor commands)
   - etc.

2. **Build Step**: `colcon build` runs `rosidl_generator_py`
   - Generates Python packages
   - Installs to `/unitree_ros2_ws/install/lib/python3.10/site-packages/unitree_hg/`

3. **Import**: Python can now import these
   ```python
   from unitree_hg.msg import LowState, LowCmd
   ```

### Source Setup

The file `/unitree_ros2_ws/install/setup.bash` contains:
- `PYTHONPATH` extensions
- `AMENT_PREFIX_PATH` for CMake packages
- ROS2 environment variables

**Sourcing this is REQUIRED** for Python to find the packages.

## Verification Checklist

### Build Time (Docker build)
- [ ] `colcon build` command succeeds
- [ ] `install/setup.bash` exists
- [ ] Python imports work: `from unitree_hg.msg import LowState`

### Runtime (Container start)
- [ ] Entrypoint sources `/unitree_ros2_ws/install/setup.bash`
- [ ] Entrypoint verification test passes: "Unitree messages imported successfully"
- [ ] Sim2sim script can import: `from unitree_hg.msg import LowState, LowCmd`

### Testing

**Build the Docker image:**
```bash
cd /workspace/uniandes_g1_colibri/digital_twin_colibri_g1/
docker-compose -f docker/docker-compose.yaml build
```

Expected output in build log:
```
[Stage 3] Building Unitree message packages...
[Stage 3] Building [18/18] in .../unitree_hg
[Stage 3] [SUCCESS] Unitree workspace built successfully
[Stage 3] [SUCCESS] unitree_hg.msg importable after build
[Stage 3] [SUCCESS] unitree_go.msg importable after build
[Stage 3] [SUCCESS] unitree_api.msg importable after build
```

**Run the container:**
```bash
docker-compose -f docker/docker-compose.yaml up isaac_sim_ros2
```

Expected output at startup:
```
[INFO] Sourcing ROS2 Humble...
[INFO] Sourcing Unitree ROS2 workspace...
[INFO] Activating conda environment 'isaaclab'...
[INFO] Environment configured:
[INFO]   ROS_DOMAIN_ID: 0
[INFO]   RMW_IMPLEMENTATION: rmw_cyclonedds_cpp
[INFO]   ISAAC_SIM_PATH: /isaac-sim
[INFO]   ISAACLAB_PATH: /workspace/IsaacLab
[INFO] Python location: /root/miniconda3/envs/isaaclab/bin/python
[INFO] Checking Unitree message packages...
[SUCCESS] Unitree messages (unitree_hg) imported successfully
[INFO] Checking digital_twin_colibri_g1 installation...
[SUCCESS] Extension found at: /workspace/uniandes_g1_colibri/digital_twin_colibri_g1/source/digital_twin_colibri_g1/__init__.py
```

If you see the `[SUCCESS] Unitree messages` message, the fix is working!

## Common Issues After Fix

### Issue: Still getting ModuleNotFoundError

**Cause**: Old Docker image still cached

**Solution**:
```bash
docker-compose -f docker/docker-compose.yaml build --no-cache
```

### Issue: Build hangs during colcon build

**Cause**: Large ROS2 packages compiling

**Solution**: This is normal for first build. Wait or check memory:
```bash
docker stats colibri_g1_sim2sim
```

### Issue: "Unitree messages imported successfully" but still crashes

**Cause**: Entrypoint sourcing works but ros2/colibri_g1_ros2_bridge.py fails on other imports

**Solution**: Check the full error trace. May be missing other ROS2 packages.

## References

- **Unitree ROS2 GitHub**: https://github.com/unitreerobotics/unitree_ros2
- **ROS2 Message Generation**: https://docs.ros.org/en/humble/Concepts/Intermediate/About-ROS-2-Interfaces.html
- **Isaac Lab Docker Guide**: https://isaac-sim.github.io/IsaacLab/main/source/deployment/docker.html
