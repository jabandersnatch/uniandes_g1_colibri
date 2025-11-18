# Docker Rebuild Instructions

## Prerequisites

1. **System reboot** (to load updated kernel 6.17.8-arch1-1)
2. **Verify veth module** is available after reboot

## Quick Rebuild

```bash
# Navigate to project
cd /home/jamendez/Documents/uniandes/MISIS/thesis/uniandes_g1_colibri/digital_twin_colibri_g1

# Stop existing container
docker-compose -f docker/docker-compose.yaml down

# Remove old image (optional, saves time if using cache)
# docker rmi colibri_g1_ros2:latest

# Rebuild with all fixes applied
docker-compose -f docker/docker-compose.yaml build

# For verbose output
# docker-compose -f docker/docker-compose.yaml build --progress=plain --no-cache
```

## Start Container

```bash
# Run sim2sim mode
docker-compose -f docker/docker-compose.yaml up isaac_sim_ros2

# Or run in background
docker-compose -f docker/docker-compose.yaml up -d isaac_sim_ros2

# View logs
docker logs -f colibri_g1_sim2sim
```

## Verification Steps

**Note**: NumPy version is now automatically verified during build (Dockerfile:241-246). Build will fail if NumPy 2.x is detected.

### 1. Check NumPy Version (Post-Build)
```bash
docker exec -it colibri_g1_sim2sim bash -c "conda activate isaaclab && python -c 'import numpy; print(\"NumPy version:\", numpy.__version__)'"
```
**Expected**: `1.26.x` (NOT 2.x)

**During Build**: Look for `✓ NumPy version verified: 1.26.x` message in build logs

### 2. Verify Extension Installation
```bash
docker exec -it colibri_g1_sim2sim bash -c "conda activate isaaclab && python -c 'import digital_twin_colibri_g1; print(\"Extension found at:\", digital_twin_colibri_g1.__file__)'"
```
**Expected**: `/workspace/uniandes_g1_colibri/digital_twin_colibri_g1/source/digital_twin_colibri_g1/__init__.py`

### 3. Monitor Startup Logs
Look for these success indicators:
- ✅ `[INFO] Activating conda environment 'isaaclab'...`
- ✅ `[SUCCESS] Extension found at: ...`
- ✅ `[INFO] Starting Sim2Sim ROS2 mode...`
- ✅ `Simulation App Startup Complete`
- ✅ No `ValueError: numpy.dtype size changed` errors
- ✅ No `ModuleNotFoundError: No module named 'digital_twin_colibri_g1'` errors

### 4. Check ROS2 Topics
```bash
# In another terminal
docker exec -it colibri_g1_sim2sim bash -c "source /opt/ros/humble/setup.bash && ros2 topic list"
```
**Expected topics**:
- `/colibri_g1/odom`
- `/colibri_g1/joint_states`
- `/colibri_g1/pose`
- `/tf`
- `/clock`

## Troubleshooting

### Build Fails with Network Error
- **Cause**: Kernel not updated, veth module missing
- **Solution**: Reboot system and retry
- **Details**: See `docker/NETWORK_TROUBLESHOOTING.md`

### NumPy Warnings During Startup
If you see:
```
ValueError: numpy.dtype size changed, may indicate binary incompatibility
```
- **Cause**: NumPy 2.x installed instead of 1.x
- **Solution**: Rebuild with `--no-cache` to ensure NumPy pinning takes effect
```bash
docker-compose -f docker/docker-compose.yaml build --no-cache
```

### Extension Not Found
If you see:
```
ModuleNotFoundError: No module named 'digital_twin_colibri_g1'
```
- **Cause**: PYTHONPATH not set or extension not installed
- **Solution**: Rebuild image (fixes are in Dockerfile)
- **Verify**: Check entrypoint output shows `[SUCCESS] Extension found`

### Container Exits Immediately
```bash
# Check logs
docker logs colibri_g1_sim2sim

# Run interactive shell to debug
docker run -it --rm colibri_g1_ros2:latest bash
conda activate isaaclab
python -c "import digital_twin_colibri_g1"
```

## Build Time Expectations

| Stage | Description | Time | Size |
|-------|-------------|------|------|
| 1 | Isaac Sim base | 5-10 min | ~15GB |
| 2 | ROS2 Humble | 5-10 min | +2GB |
| 3 | Isaac Lab + Conda | 15-20 min | +3GB |
| 4 | Extension installation | 2-5 min | +500MB |
| 5 | Final config | 1-2 min | +200MB |
| **Total** | | **30-60 min** | **~21GB** |

*Times are for full build with no cache. Subsequent builds with cache: 5-10 minutes.*

## What Changed (2025-11-18)

### Initial Fixes
1. **NumPy pinned to <2.0** before Isaac Lab installation (line 176)
2. **Extension installation** uses conda environment properly (line 214)
3. **PYTHONPATH configured** to include extension (line 256)
4. **Entrypoint updated** to use conda Python directly (entrypoint.sh:42)
5. **Additional packages** installed in conda environment (line 237)

### Enhanced Fix (CRITICAL - Applied Same Day)
6. **PIP_CONSTRAINT environment variable** enforces NumPy <2.0 globally (line 172)
7. **Constraints file created** to prevent ANY package from upgrading NumPy (line 169)
8. **Build-time verification** added to catch NumPy version issues early (line 243)

**Why the enhancement was needed**: Isaac Lab's installation process was upgrading NumPy back to 2.2.6 despite initial pinning. The PIP_CONSTRAINT approach prevents this by applying constraints to ALL pip operations.

See `docker/FIXES_APPLIED.md` for detailed explanation.

## References

- Main documentation: `README_ROS2.md`
- Architecture details: `docs/SIM2SIM_ROS2.md`
- Dependency management: `docs/DEPENDENCIES.md`
- Network issues: `docker/NETWORK_TROUBLESHOOTING.md`
- Fixes applied: `docker/FIXES_APPLIED.md`
