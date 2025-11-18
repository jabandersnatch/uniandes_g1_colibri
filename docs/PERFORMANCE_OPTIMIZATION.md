# Performance Optimization Guide

**Date**: 2025-11-18
**Topic**: Reducing startup time and improving sim2sim performance

## Current Performance Issues

### Slow Startup Time (~5 minutes)

**Symptoms**:
- Container startup takes 3-5 minutes before simulation begins
- Hundreds of USD loading warnings
- Much slower than isaac-go2-ros2 (~30 seconds)

**Root Causes**:

1. **Large USD Scene (177MB total, 88MB MainModel.usd)**
   - `assets/ColibriLab/MainModel.usd`: 88MB, 253,906 lines
   - Contains highly detailed Colibri Lab environment
   - Much larger than isaac-go2-ros2's flat terrain (~1MB)

2. **Missing Asset References (Scene16.usd)**
   - Hundreds of warnings for missing `/props/Scene16.usd`
   - USD tries to load each missing reference, adds ~1-2 seconds per batch
   - Example warnings:
     ```
     Could not open asset @/props/Scene16.usd@ for reference
     ```

3. **Docker Container Overhead**
   - Cold start: Isaac Sim initialization (~30-60s)
   - Asset caching not persistent across container restarts
   - Network bridge setup adds latency

## Comparison: Colibri G1 vs isaac-go2-ros2

| Metric | Colibri G1 | isaac-go2-ros2 | Difference |
|--------|------------|----------------|------------|
| **USD Scene Size** | 177MB | ~1MB | 176x larger |
| **Main USD File** | 88MB (MainModel.usd) | ~500KB (flat terrain) | 176x larger |
| **USD Lines** | 253,906 | ~500 | 507x more |
| **Missing References** | ~100 warnings | 0 | N/A |
| **Startup Time** | 3-5 minutes | 30-45 seconds | 4-6x slower |
| **Scene Complexity** | Full building interior | Flat plane | Much more complex |

## Optimization Strategies

### Quick Wins (Immediate)

#### 1. Use Simplified Environment for Development

**Impact**: 80% startup time reduction (5 min → 1 min)

Create a lightweight USD for testing:

```python
# In digital_twin_colibri_g1_env_cfg.py
# Option 1: Use flat terrain (fastest)
self.scene.terrain = TerrainImporterCfg(
    prim_path="/World/ground",
    terrain_type="plane",  # Flat plane instead of USD
    collision_group=-1,
    physics_material=sim_utils.RigidBodyMaterialCfg(
        friction_combine_mode="multiply",
        restitution_combine_mode="multiply",
        static_friction=1.0,
        dynamic_friction=1.0,
    ),
)

# Option 2: Use simplified USD (medium speed)
# Create assets/ColibriLab/ColibriLab_Simple.usd with just floor + walls
self.scene.terrain.usd_path = f"{ASSET_DIR}/ColibriLab/ColibriLab_Simple.usd"
```

**When to use**:
- Policy development and testing
- ROS2 bridge debugging
- Quick iteration cycles

**When NOT to use**:
- Final evaluation with realistic environment
- Visual demonstrations/videos
- Environment-specific behavior testing

#### 2. Fix Missing USD References

**Impact**: 30-60s startup time reduction

The Scene16.usd references are missing. Options:

**Option A: Remove references** (edit MainModel.usd):
```bash
# Backup first
cp assets/ColibriLab/MainModel.usd assets/ColibriLab/MainModel.usd.backup

# Remove Scene16.usd references (use USD tools or text editor)
# Search for: Scene16.usd
# Delete or comment out those reference lines
```

**Option B: Create dummy Scene16.usd**:
```bash
# Create minimal placeholder
echo '#usda 1.0' > assets/ColibriLab/props/Scene16.usd
```

**Option C: Suppress warnings** (doesn't improve speed, just cleaner logs):
```python
# In sim2sim script, before environment creation
import omni.usd
omni.usd.set_stage_loading_rules(omni.usd.StageLoadRules.LoadNone)
```

#### 3. Enable Asset Caching (Docker)

**Impact**: 20-30s improvement on subsequent runs

Mount a persistent cache volume:

```yaml
# In docker/docker-compose.yaml
volumes:
  # Add Isaac Sim cache
  - isaac_cache:/root/.cache/ov
  - isaac_cache:/root/.nvidia-omniverse

volumes:
  isaac_cache:
```

#### 4. Headless Mode (No GUI)

**Impact**: 10-20s startup reduction

```yaml
# In cfg/ros2_sim.yaml
performance:
  headless: true  # Disable Isaac Sim GUI
```

Or via environment variable:
```bash
docker-compose -f docker/docker-compose.yaml run -e HEADLESS=1 isaac_sim_ros2
```

### Medium-Term Optimizations

#### 5. Optimize USD Scene

**Impact**: 60-80% size reduction

Steps:
1. **Simplify geometry**: Remove unnecessary polygons in Blender/USD Composer
2. **Reduce texture resolution**: Compress textures from 4K → 2K or 1K
3. **Merge meshes**: Combine small objects into larger meshes
4. **Use instancing**: Replace duplicated objects with USD instances
5. **Remove hidden geometry**: Delete objects inside walls or underground

**Tools**:
- NVIDIA USD Composer (Omniverse)
- Blender with USD export
- `usdcat` for flattening layers

#### 6. Lazy Loading

**Impact**: Faster initial startup, load on demand

```python
# In environment config
from omni.isaac.core.utils.stage import set_stage_loading_rules
from pxr import UsdStage

# Load only visible/collision-relevant prims
stage = UsdStage.Open("assets/ColibriLab/ColibriLab.usd")
stage.SetLoadRules(UsdStageLoadRules.LoadNone)  # Don't load everything
```

#### 7. Pre-build Docker Image

**Impact**: Eliminate rebuild time (30-60min → 0)

```bash
# Build once, tag, and reuse
docker build -f docker/Dockerfile -t colibri_g1_ros2:v1.0 .

# Push to registry (optional)
docker tag colibri_g1_ros2:v1.0 your-registry/colibri_g1_ros2:v1.0
docker push your-registry/colibri_g1_ros2:v1.0

# Use pre-built image
docker run colibri_g1_ros2:v1.0
```

### Long-Term Optimizations

#### 8. Use Isaac Sim Standalone (Native, No Docker)

**Impact**: 50% startup reduction

```bash
# Native installation (faster than Docker)
conda activate isaaclab
python sim2sim/isaac_colibri_g1_ros2.py
```

**Pros**:
- No container overhead
- Direct GPU access
- Faster asset loading

**Cons**:
- Requires Isaac Sim installation on host
- Less portable
- Environment management complexity

#### 9. Scene Streaming (Advanced)

For very large scenes, use USD streaming:
- Load only viewport-visible geometry
- Stream assets from Omniverse Nucleus server
- Requires Omniverse Enterprise

## Recommended Development Workflow

### Phase 1: Development (Fast Iteration)
```yaml
# cfg/ros2_sim_dev.yaml
environment:
  use_custom_usd: false  # Use flat plane

performance:
  headless: true
  render_interval: 8  # Render less frequently
```

**Startup**: ~30-60 seconds

### Phase 2: Testing (Realistic Environment)
```yaml
# cfg/ros2_sim.yaml
environment:
  use_custom_usd: true
  usd_path: "assets/ColibriLab/ColibriLab_Simple.usd"  # Simplified version

performance:
  headless: false  # GUI for visual inspection
```

**Startup**: ~1-2 minutes

### Phase 3: Evaluation (Full Fidelity)
```yaml
# cfg/ros2_sim_eval.yaml
environment:
  use_custom_usd: true
  usd_path: "assets/ColibriLab/ColibriLab.usd"  # Full scene

performance:
  headless: false
  record_video: true
```

**Startup**: ~3-5 minutes (acceptable for final evaluation)

## Monitoring Startup Time

Add timing instrumentation:

```python
# In sim2sim/isaac_colibri_g1_ros2.py
import time

startup_times = {}

# Track each phase
startup_times['start'] = time.time()

# After AppLauncher
startup_times['app_ready'] = time.time()
print(f"[PERF] App init: {startup_times['app_ready'] - startup_times['start']:.1f}s")

# After environment creation
startup_times['env_ready'] = time.time()
print(f"[PERF] Env creation: {startup_times['env_ready'] - startup_times['app_ready']:.1f}s")

# After policy load
startup_times['policy_ready'] = time.time()
print(f"[PERF] Policy load: {startup_times['policy_ready'] - startup_times['env_ready']:.1f}s")

# After ROS2 init
startup_times['ros2_ready'] = time.time()
print(f"[PERF] ROS2 init: {startup_times['ros2_ready'] - startup_times['policy_ready']:.1f}s")

# Total
print(f"[PERF] TOTAL STARTUP: {startup_times['ros2_ready'] - startup_times['start']:.1f}s")
```

## Expected Startup Breakdown

With full ColibriLab USD:
- **App initialization**: 30-45s (Isaac Sim startup)
- **Environment creation**: 120-180s (USD loading + scene creation)
- **Policy loading**: 5-10s (checkpoint load + network initialization)
- **ROS2 initialization**: 2-5s (node setup + publisher creation)
- **Total**: 157-240s (2.6-4.0 minutes)

With flat terrain:
- **App initialization**: 30-45s
- **Environment creation**: 10-15s
- **Policy loading**: 5-10s
- **ROS2 initialization**: 2-5s
- **Total**: 47-75s (~1 minute)

## Troubleshooting

### Startup Hangs at "Loading USD"

**Cause**: Large USD file or network issues (if using Nucleus)

**Solutions**:
1. Use simplified USD
2. Check for missing texture/asset references
3. Disable network asset loading

### Startup Hangs at "Creating Physics Scene"

**Cause**: Too many collision meshes

**Solutions**:
1. Simplify collision meshes
2. Use collision approximations (boxes, capsules)
3. Disable collision for non-interactive objects

### Container Restarts During Startup

**Cause**: Out of memory (Docker limits)

**Solutions**:
1. Increase Docker memory limit (Settings → Resources)
2. Reduce `num_envs` (default 1 for sim2sim)
3. Use headless mode

## Summary

**Current Performance**:
- Full ColibriLab scene: 3-5 minutes startup
- Acceptable for evaluation, too slow for development

**Quick Fix (Recommended)**:
```python
# Use flat terrain for development
self.scene.terrain.terrain_type = "plane"  # Instead of USD
```
**Result**: 5 minutes → 1 minute (80% reduction)

**Future Work**:
- Create simplified ColibriLab_Simple.usd (~10MB, <1 min startup)
- Fix missing Scene16.usd references
- Implement scene streaming for very large environments

## Related Files

- **Environment config**: `source/.../digital_twin_colibri_g1_env_cfg.py`
- **USD scenes**: `assets/ColibriLab/*.usd`
- **Sim2sim script**: `sim2sim/isaac_colibri_g1_ros2.py`
- **Docker config**: `docker/docker-compose.yaml`
