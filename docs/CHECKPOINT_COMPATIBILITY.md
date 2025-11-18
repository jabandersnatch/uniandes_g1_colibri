# Checkpoint Compatibility Guide

**Date**: 2025-11-18
**Topic**: Understanding and selecting compatible checkpoints for sim2sim deployment

## Overview

When loading a trained RL policy checkpoint, the observation space size must **exactly match** between:
1. The checkpoint (trained model)
2. The environment configuration (current setup)

A mismatch will result in a `RuntimeError` during checkpoint loading.

## Observation Space Evolution

The Colibri G1 environment has evolved over time, particularly with the addition of goal-tracking features:

### Version 1: Velocity Tracking Only (123 observations)
- **Training period**: Before 2025-11-10
- **Observation space**: 123 dimensions
- **Features**:
  - base_lin_vel (3)
  - base_ang_vel (3)
  - projected_gravity (3)
  - velocity_commands (3)
  - joint_pos (37)
  - joint_vel (37)
  - actions (37)
  - **Total**: 3+3+3+3+37+37+37 = **123**

### Version 2: Goal-Directed Navigation (125 observations)
- **Training period**: 2025-11-10 onwards
- **Observation space**: 125 dimensions
- **Features**: All from Version 1 PLUS:
  - goal_position (2) - 2D goal position in robot base frame
  - **Total**: 123 + 2 = **125**

## Training Run Analysis

### Recent Training Runs (with goal_position)

| Run Timestamp | Obs Size | Goal Position | Best Checkpoint | Notes |
|--------------|----------|---------------|-----------------|-------|
| `2025-11-11_10-29-02` | 125 | ✓ | `model_900.pt` | Latest with full goal tracking |
| `2025-11-10_23-24-32` | 125 | ✓ | `model_900.pt` | Goal tracking v2 |
| `2025-11-10_21-49-12` | 125 | ✓ | Available | Goal tracking v1 |

### Legacy Training Runs (without goal_position)

| Run Timestamp | Obs Size | Goal Position | Best Checkpoint | Notes |
|--------------|----------|---------------|-----------------|-------|
| `2025-11-09_16-20-14` | 123 | ✗ | `model_550.pt` | Legacy velocity tracking only |

## How to Check Checkpoint Compatibility

### Method 1: Inspect Checkpoint File (Python)

```python
import torch

checkpoint_path = "logs/rsl_rl/g1_flat/2025-11-11_10-29-02/model_900.pt"
checkpoint = torch.load(checkpoint_path, map_location='cpu')

# Check actor input layer size (first layer weight shape)
actor_weight = checkpoint['model_state_dict']['actor.0.weight']
obs_size = actor_weight.shape[1]

print(f"Observation space size: {obs_size}")
# Expected: 125 for goal-tracking, 123 for legacy
```

### Method 2: Check Environment Config (YAML)

```bash
# Look for goal_position in the saved environment config
grep "goal_position:" logs/rsl_rl/g1_flat/2025-11-11_10-29-02/params/env.yaml

# If found → 125 observations
# If not found → 123 observations
```

### Method 3: Automated Check Script

```bash
# Run the automated checker
python3 << 'EOF'
import torch
import os

checkpoint_path = "logs/rsl_rl/g1_flat/2025-11-11_10-29-02/model_900.pt"
env_yaml_path = "logs/rsl_rl/g1_flat/2025-11-11_10-29-02/params/env.yaml"

# Check model
checkpoint = torch.load(checkpoint_path, map_location='cpu')
obs_size = checkpoint['model_state_dict']['actor.0.weight'].shape[1]

# Check config
with open(env_yaml_path, 'r') as f:
    has_goal = 'goal_position:' in f.read()

print(f"Observation size: {obs_size}")
print(f"Has goal_position: {has_goal}")
print(f"Compatible: {(obs_size == 125 and has_goal) or (obs_size == 123 and not has_goal)}")
EOF
```

## Selecting the Right Checkpoint

### For Sim2Sim with Goal-Directed Navigation

**Requirement**: Checkpoint must have 125 observations (WITH goal_position)

**Recommended checkpoints** (sorted by recency):
1. `logs/rsl_rl/g1_flat/2025-11-11_10-29-02/model_900.pt` ✓ **Best choice**
2. `logs/rsl_rl/g1_flat/2025-11-10_23-24-32/model_900.pt` ✓ Alternative
3. `logs/rsl_rl/g1_flat/2025-11-10_21-49-12/model_*.pt` ✓ Older version

**Configuration** (`cfg/ros2_sim.yaml`):
```yaml
policy:
  checkpoint: "logs/rsl_rl/g1_flat/2025-11-11_10-29-02/model_900.pt"
```

### For Legacy Velocity Tracking Only

**Requirement**: Checkpoint must have 123 observations (WITHOUT goal_position)

**Available checkpoint**:
- `logs/rsl_rl/g1_flat/2025-11-09_16-20-14/model_550.pt` ✓

**Note**: This is NOT recommended for sim2sim as it lacks goal-tracking capabilities.

## Error: Observation Size Mismatch

### Symptom

```
RuntimeError: Error(s) in loading state_dict for ActorCritic:
  size mismatch for actor.0.weight: copying a param with shape torch.Size([256, 123])
  from checkpoint, the shape in current model is torch.Size([256, 125]).
```

### Root Cause

You are trying to load a **legacy checkpoint (123 obs)** into an environment configured with **goal_position observation (125 obs)**.

### Solution

**Option 1: Use compatible checkpoint (RECOMMENDED)**
```yaml
# In cfg/ros2_sim.yaml
policy:
  checkpoint: "logs/rsl_rl/g1_flat/2025-11-11_10-29-02/model_900.pt"  # 125 obs
```

**Option 2: Remove goal_position from environment (NOT RECOMMENDED)**

This would require modifying the environment configuration to match the legacy checkpoint, but defeats the purpose of goal-tracking navigation.

## Verifying Compatibility Before Running

Before starting sim2sim, verify compatibility:

```bash
# 1. Check checkpoint observation size
python3 -c "
import torch
cp = torch.load('logs/rsl_rl/g1_flat/2025-11-11_10-29-02/model_900.pt', map_location='cpu')
print(f'Checkpoint obs size: {cp[\"model_state_dict\"][\"actor.0.weight\"].shape[1]}')
"

# 2. Check current environment config
grep "goal_position:" source/digital_twin_colibri_g1/digital_twin_colibri_g1/tasks/manager_based/digital_twin_colibri_g1/digital_twin_colibri_g1_env_cfg.py

# 3. If both show goal_position → Compatible ✓
# 4. If checkpoint is 123 and env has goal_position → Incompatible ✗
```

## Checkpoint Training Metrics

For reference, here are the training metrics for compatible checkpoints:

### `2025-11-11_10-29-02/model_900.pt`
- **Iterations**: 900
- **Observation space**: 125
- **Goal tracking**: ✓
- **Rewards**: Includes goal_tracking, goal_tracking_fine, heading_alignment
- **Training duration**: ~1.5 hours

### `2025-11-10_23-24-32/model_900.pt`
- **Iterations**: 900
- **Observation space**: 125
- **Goal tracking**: ✓
- **Previous version** before latest improvements

## Best Practices

1. **Always verify checkpoint compatibility** before deployment
2. **Use the most recent checkpoint** with goal_position (2025-11-11_10-29-02)
3. **Document checkpoint versions** in deployment configs
4. **Keep training logs** to track observation space changes
5. **Version your environment configs** alongside checkpoints

## Migration Guide: Legacy to Goal-Tracking

If you have deployed a legacy checkpoint and want to upgrade:

### Step 1: Verify current checkpoint
```bash
# Check what you're currently using
grep "checkpoint:" cfg/ros2_sim.yaml
```

### Step 2: Update configuration
```bash
# Edit cfg/ros2_sim.yaml
# Change from:
checkpoint: "logs/rsl_rl/g1_flat/2025-11-09_16-20-14/model_550.pt"  # 123 obs

# To:
checkpoint: "logs/rsl_rl/g1_flat/2025-11-11_10-29-02/model_900.pt"  # 125 obs
```

### Step 3: Rebuild Docker (if using containerized deployment)
```bash
docker-compose -f docker/docker-compose.yaml build
```

### Step 4: Test
```bash
docker-compose -f docker/docker-compose.yaml up isaac_sim_ros2
```

## Related Files

- **Environment config**: `source/digital_twin_colibri_g1/digital_twin_colibri_g1/tasks/manager_based/digital_twin_colibri_g1/digital_twin_colibri_g1_env_cfg.py`
- **Sim2sim config**: `cfg/ros2_sim.yaml`
- **Sim2sim script**: `sim2sim/isaac_colibri_g1_ros2.py`
- **Training logs**: `logs/rsl_rl/g1_flat/*/params/env.yaml`

## References

- Isaac Lab observation manager: https://isaac-sim.github.io/IsaacLab/main/source/api/isaaclab.managers.html#observation-manager
- RSL-RL actor-critic architecture: https://github.com/leggedrobotics/rsl_rl
- PyTorch state_dict loading: https://pytorch.org/tutorials/beginner/saving_loading_models.html
