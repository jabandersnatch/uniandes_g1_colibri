# Sim2Sim Docker Crash Fix Summary

**Date**: 2025-11-18
**Issue**: OverflowError causing infinite restart loop in Docker

## Problem Analysis

### Root Cause

The sim2sim ROS2 bridge was crashing with the following error:

```
OverflowError: cannot convert float infinity to integer
```

**Call Stack**:
1. `sim2sim/isaac_colibri_g1_ros2.py:74` - Set `env_cfg.episode_length_s = float("inf")`
2. `sim2sim/isaac_colibri_g1_ros2.py:171` - Created `RslRlVecEnvWrapper(env)`
3. `isaaclab_rl/rsl_rl/vecenv_wrapper.py:55` - Accessed `self.unwrapped.max_episode_length`
4. `isaaclab/envs/manager_based_rl_env.py:104` - Computed `math.ceil(inf / step_dt)` → **CRASH**

### Why Infinity Failed

Isaac Lab's `max_episode_length` property computes:
```python
def max_episode_length(self) -> int:
    return math.ceil(self.max_episode_length_s / self.step_dt)
```

When `max_episode_length_s = float("inf")`:
- `math.ceil(inf / step_dt)` = `math.ceil(inf)` → **OverflowError**
- Python's `math.ceil()` cannot convert infinity to an integer

### Why Docker Kept Restarting

The `docker-compose.yaml` had:
```yaml
restart: unless-stopped
```

This restart policy tells Docker to:
- **Always restart** the container when it exits (exit code != 0)
- Only stop if manually commanded via `docker stop` or `docker-compose down`

This created an **infinite crash loop**:
1. Container starts → crash → exit code 1
2. Docker sees exit code 1 → restarts container
3. Container starts → crash → exit code 1
4. ... repeat indefinitely

## Fixes Applied

### Fix 1: Use Finite Episode Length

**File**: `sim2sim/isaac_colibri_g1_ros2.py:74-76`

**Before**:
```python
env_cfg.episode_length_s = float("inf")  # Continuous operation
```

**After**:
```python
# Use very large finite episode length instead of infinity (RSL-RL requires finite max_episode_length)
# 10000s = ~2.7 hours of continuous operation per episode
env_cfg.episode_length_s = 10000.0
```

**Rationale**:
- RSL-RL's `RslRlVecEnvWrapper` requires a finite `max_episode_length` (integer type)
- 10,000 seconds (2.7 hours) is effectively continuous for testing purposes
- The environment will auto-reset after this duration, maintaining continuous operation
- Alternative values: 3600s (1 hour), 7200s (2 hours), 86400s (24 hours)

### Fix 2: Disable Docker Auto-Restart (Development Mode)

**File**: `docker/docker-compose.yaml:95`

**Before**:
```yaml
restart: unless-stopped
```

**After**:
```yaml
# Options: "no", "always", "on-failure", "unless-stopped"
# - "no": Never restart (good for debugging crashes)
# - "on-failure": Only restart on non-zero exit code (good for production)
# - "unless-stopped": Always restart unless manually stopped (aggressive)
# Changed to "no" for development to avoid crash loops and allow debugging
restart: "no"
```

**Rationale**:
- During development, crashes should be visible and debuggable
- `restart: "no"` prevents infinite crash loops and allows log inspection
- For production deployment, consider `restart: "on-failure"` with limited retries

## Docker Restart Policy Options

| Policy | Behavior | Use Case |
|--------|----------|----------|
| `"no"` | Never restart | Development, debugging crashes |
| `"on-failure"` | Restart only on non-zero exit | Production (with max retries) |
| `"always"` | Always restart (even on clean exit) | Critical services |
| `"unless-stopped"` | Always restart unless manually stopped | Background daemons |

**Recommendation for Production**:
```yaml
restart: on-failure
deploy:
  restart_policy:
    condition: on-failure
    delay: 5s
    max_attempts: 3
    window: 120s
```

## Testing the Fix

### Rebuild and Test

```bash
# Stop any running containers
docker-compose -f docker/docker-compose.yaml down

# Rebuild the image with the fix
docker-compose -f docker/docker-compose.yaml build

# Run sim2sim
docker-compose -f docker/docker-compose.yaml up isaac_sim_ros2

# Or use helper script
./docker/launch.sh build
./docker/launch.sh sim2sim
```

### Running with Log Capture

To run the container and save all output to a file for later review:

```bash
# Method 1: Redirect stdout and stderr to file
docker-compose -f docker/docker-compose.yaml up isaac_sim_ros2 2>&1 | tee logs/sim2sim_run_$(date +%Y%m%d_%H%M%S).log

# Method 2: Run in background and capture logs
docker-compose -f docker/docker-compose.yaml up -d isaac_sim_ros2
docker logs -f colibri_g1_sim2sim 2>&1 | tee logs/sim2sim_run_$(date +%Y%m%d_%H%M%S).log

# Method 3: View existing container logs (after run)
docker logs colibri_g1_sim2sim > logs/sim2sim_run_$(date +%Y%m%d_%H%M%S).log 2>&1

# Method 4: Follow logs with timestamps
docker-compose -f docker/docker-compose.yaml logs -f --timestamps isaac_sim_ros2 | tee logs/sim2sim_run_$(date +%Y%m%d_%H%M%S).log
```

**Explanation**:
- `2>&1` - Redirects stderr (error messages) to stdout (combines all output)
- `tee` - Writes to both file and terminal (so you can see output in real-time)
- `$(date +%Y%m%d_%H%M%S)` - Adds timestamp to filename (e.g., `sim2sim_run_20251118_045000.log`)
- `-f` - Follows log output (like `tail -f`)
- `--timestamps` - Adds timestamps to each log line

**Recommended for testing**:
```bash
# Create logs directory if it doesn't exist
mkdir -p logs

# Run with live output AND file capture
docker-compose -f docker/docker-compose.yaml up isaac_sim_ros2 2>&1 | tee logs/sim2sim_test_$(date +%Y%m%d_%H%M%S).log
```

### Expected Behavior

**Before Fix**:
- Container starts → crashes after 7-10 seconds → restarts immediately
- Infinite loop visible in `docker logs`
- Cannot inspect crash logs (overwritten by restart)

**After Fix**:
- Container starts → loads environment → loads policy → runs simulation
- No crash (max_episode_length is now a valid integer)
- No auto-restart on failure (allows debugging)

### Verify ROS2 Topics

After the container starts successfully:

```bash
# Check ROS2 topics are publishing
docker exec -it colibri_g1_sim2sim bash -c "source /opt/ros/humble/setup.bash && ros2 topic list"

# Expected output:
# /colibri_g1/odom
# /colibri_g1/joint_states
# /colibri_g1/pose
# /colibri_g1/goal_marker
# /colibri_g1/navigation_metrics
# /tf
# /clock

# Monitor odometry (save to file)
docker exec -it colibri_g1_sim2sim bash -c "source /opt/ros/humble/setup.bash && ros2 topic echo /colibri_g1/odom" | tee logs/odom_output_$(date +%Y%m%d_%H%M%S).log
```

## Additional Notes

### Episode Auto-Reset Behavior

With `episode_length_s = 10000.0`:
- The environment will auto-reset after 10,000 simulation seconds
- This triggers the `reset()` method, randomizing robot pose and goal
- Simulation continues seamlessly (no container restart)
- ROS2 topics continue publishing (no interruption)

### Adjusting Episode Length

If you need a different episode duration, edit `sim2sim/isaac_colibri_g1_ros2.py:76`:

```python
# Examples:
env_cfg.episode_length_s = 3600.0   # 1 hour
env_cfg.episode_length_s = 7200.0   # 2 hours
env_cfg.episode_length_s = 86400.0  # 24 hours
```

**Warning**: Do NOT use `float("inf")` - it will cause the same crash.

### Production Deployment

For long-running production deployments:

1. **Use a finite episode length** (e.g., 24 hours):
   ```python
   env_cfg.episode_length_s = 86400.0  # 24 hours
   ```

2. **Enable smart restart policy**:
   ```yaml
   restart: on-failure
   deploy:
     restart_policy:
       condition: on-failure
       delay: 5s
       max_attempts: 3
   ```

3. **Add health checks** (optional):
   ```yaml
   healthcheck:
     test: ["CMD", "ros2", "topic", "list"]
     interval: 30s
     timeout: 10s
     retries: 3
   ```

## Issue 2: Checkpoint Observation Size Mismatch (FIXED)

### Symptom

After fixing the infinity issue, a second error appeared:

```
RuntimeError: Error(s) in loading state_dict for ActorCritic:
  size mismatch for actor.0.weight: copying a param with shape torch.Size([256, 123])
  from checkpoint, the shape in current model is torch.Size([256, 125]).
```

### Root Cause

The configuration was using an **old checkpoint** trained WITHOUT goal_position observation:
- **Old checkpoint**: `logs/rsl_rl/g1_flat/2025-11-09_16-20-14/model_550.pt` (123 obs)
- **Current environment**: Includes `goal_position` observation (125 obs = 123 + 2)

The environment evolved to include goal-tracking features (added 2D goal position), but the checkpoint was from before this change.

### Solution

Updated `cfg/ros2_sim.yaml` to use a compatible checkpoint:

```yaml
policy:
  # OLD (incompatible - 123 obs):
  # checkpoint: "logs/rsl_rl/g1_flat/2025-11-09_16-20-14/model_550.pt"

  # NEW (compatible - 125 obs):
  checkpoint: "logs/rsl_rl/g1_flat/2025-11-11_10-29-02/model_900.pt"
```

### How to Find Compatible Checkpoints

Run this command to check any checkpoint:

```bash
python3 << 'EOF'
import torch
checkpoint = torch.load('logs/rsl_rl/g1_flat/2025-11-11_10-29-02/model_900.pt', map_location='cpu')
obs_size = checkpoint['model_state_dict']['actor.0.weight'].shape[1]
print(f"Observation space size: {obs_size}")
# Expected: 125 for goal-tracking checkpoints
EOF
```

**Compatible checkpoints** (125 observations):
- `logs/rsl_rl/g1_flat/2025-11-11_10-29-02/model_900.pt` ✓ **Recommended**
- `logs/rsl_rl/g1_flat/2025-11-10_23-24-32/model_900.pt` ✓

**Legacy checkpoints** (123 observations, NOT compatible):
- `logs/rsl_rl/g1_flat/2025-11-09_16-20-14/model_550.pt` ✗

See `docs/CHECKPOINT_COMPATIBILITY.md` for detailed guide.

## Issue 3: Policy Inference IndexError (FIXED)

### Symptom

After fixing the checkpoint compatibility, a third error appeared during the simulation loop:

```
IndexError: too many indices for tensor of dimension 2
  File "sim2sim/isaac_colibri_g1_ros2.py", line 205, in policy_inference
    actions = policy(obs_tensor)
  File "rsl_rl/modules/actor_critic.py", line 168, in get_actor_obs
    obs_list = [obs[obs_group] for obs_group in self.obs_groups["policy"]]
```

### Root Cause

The policy inference code was passing `obs["policy"]` (a tensor) to the policy, but RSL-RL's `get_inference_policy()` expects the **full observation dictionary** (not just the tensor).

**Incorrect code**:
```python
def policy_inference(policy, obs, deterministic=True):
    obs_tensor = obs["policy"]  # Extract tensor first
    actions = policy(obs_tensor)  # ✗ Policy can't index a 2D tensor
    return actions
```

**Why it failed**:
- `obs["policy"]` is a tensor of shape `[num_envs, 125]`
- The policy tries to do `obs[obs_group]` where `obs_group = "policy"`
- Tensors don't support string indexing → **IndexError**

### Solution

Pass the full observation dictionary to the policy:

```python
def policy_inference(policy, obs, deterministic=True):
    # Pass full dictionary - policy extracts obs["policy"] internally
    actions = policy(obs)  # ✓ Policy handles dictionary
    return actions
```

**How it works**:
1. `obs` is a dict: `{"policy": tensor([num_envs, 125])}`
2. Policy's `get_actor_obs()` does: `obs["policy"]` internally
3. Extracts the correct tensor and runs inference

### Reference Implementation

This matches how isaac-go2-ros2 does it:

```python
# isaac-go2-ros2/isaac_go2_ros2.py
while simulation_app.is_running():
    with torch.inference_mode():
        actions = policy(obs)  # Pass full dict
        obs, _ = env.step(actions)
```

## Issue 4: ROS2 Bridge AttributeError - sim_time (FIXED)

### Symptom

After fixing the policy inference, the simulation loop started but crashed immediately:

```
AttributeError: 'ManagerBasedRLEnv' object has no attribute 'sim_time'
  File "sim2sim/isaac_colibri_g1_ros2.py", line 120, in run_sim2sim
    ros2_bridge.publish_data()
  File "ros2/colibri_g1_ros2_bridge.py", line 121, in publish_data
    current_time = self.env.sim_time
```

### Root Cause

The ROS2 bridge was trying to access `self.env.sim_time` which doesn't exist on `ManagerBasedRLEnv`.

**Incorrect code**:
```python
def publish_data(self):
    current_time = self.env.sim_time  # ✗ Attribute doesn't exist
```

### Solution

Use ROS2's clock and compute simulation time from environment state:

```python
def publish_data(self):
    # Use ROS2 clock for message timestamps
    current_time = self.get_clock().now()

    # Compute simulation time for /clock topic
    # common_step_counter * step_dt = total simulated time
    sim_time_seconds = float(
        self.env.unwrapped.common_step_counter *
        self.env.unwrapped.step_dt
    )

    # Publish with correct timestamps
    self._publish_odometry(current_time)
    self._publish_clock(sim_time_seconds)
```

**How it works**:
1. `current_time = self.get_clock().now()` - ROS2 clock for message headers
2. `common_step_counter` - Total steps since environment creation
3. `step_dt` - Physics timestep × decimation (e.g., 0.005 × 4 = 0.02s)
4. Multiply to get total simulation time in seconds

## Related Files Modified

- `sim2sim/isaac_colibri_g1_ros2.py:76` - Fixed episode_length_s (infinity → 10000.0)
- `sim2sim/isaac_colibri_g1_ros2.py:202` - Fixed policy inference (pass full dict)
- `ros2/colibri_g1_ros2_bridge.py:123-128` - Fixed sim_time computation
- `docker/docker-compose.yaml:95` - Changed restart policy ("unless-stopped" → "no")
- `cfg/ros2_sim.yaml:29` - Updated checkpoint path (123 obs → 125 obs compatible)

## References

- Isaac Lab issue: https://github.com/isaac-sim/IsaacLab/discussions/XXX (if applicable)
- Docker restart policies: https://docs.docker.com/config/containers/start-containers-automatically/
- Python math.ceil() limitation: https://docs.python.org/3/library/math.html#math.ceil
