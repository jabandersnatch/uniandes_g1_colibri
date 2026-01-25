# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Digital Twin for Colibri G1 humanoid robot** - Isaac Lab extension for velocity-based locomotion and social navigation.

- **Framework**: Isaac Lab extension (Isaac Sim 4.5/5.0)
- **RL Libraries**: RSL-RL, SKRL
- **Robot**: Unitree G1 (29 DOF)
- **Current Branch**: `feature/sim2sim-ros2` (ROS2 Humble integration)

## Installation

```bash
# Install extension (requires Isaac Lab activated)
python -m pip install -e source/digital_twin_colibri_g1

# Verify tasks registered
python scripts/list_envs.py  # Should show Isaac-Colibri-G1-*
```

## Available Tasks

| Task ID | Purpose | num_envs |
|---------|---------|----------|
| `Isaac-Colibri-G1-v0` | Base locomotion training | 512 |
| `Isaac-Colibri-G1-Play-v0` | Visualization/evaluation | 10 |
| `Isaac-Colibri-G1-SocialNav-v0` | LiDAR + cylinder obstacles | 128 |
| `Isaac-Colibri-G1-SocialNav-Play-v0` | Social nav visualization | 4 |

**Note**: People-based tasks (`Isaac-Colibri-G1-People-*`) are deprecated - IRA doesn't work with IsaacLab.

## Common Commands

```bash
# Training (RSL-RL)
python scripts/rsl_rl/train.py --task=Isaac-Colibri-G1-v0 --num_envs 512 --headless

# Training (SKRL)
python scripts/skrl/train.py --task=Isaac-Colibri-G1-v0

# Play/evaluation
python scripts/rsl_rl/play.py --task=Isaac-Colibri-G1-Play-v0 --num_envs 10

# Resume training
python scripts/rsl_rl/train.py --task=Isaac-Colibri-G1-v0 --resume --load_run <run_folder>

# Social navigation
python scripts/rsl_rl/train.py --task=Isaac-Colibri-G1-SocialNav-v0 --num_envs 128 --headless

# Test environment setup
python scripts/zero_agent.py --task=Isaac-Colibri-G1-v0
python scripts/random_agent.py --task=Isaac-Colibri-G1-v0
```

**Key Training Options**:
- `--headless`: No GUI (faster training)
- `--video`: Record training videos
- `--logger wandb|tensorboard`: Enable logging
- `--distributed`: Multi-GPU training

## Architecture

### Key Files

**Environment Configuration** (Isaac Lab extension pattern):
```
source/digital_twin_colibri_g1/digital_twin_colibri_g1/tasks/manager_based/digital_twin_colibri_g1/
├── __init__.py                         # Gym task registration
├── digital_twin_colibri_g1_env_cfg.py  # Base env (inherits G1FlatEnvCfg)
├── social_nav_env_cfg.py               # LiDAR + cylinder obstacles
├── agents/rsl_rl_ppo_cfg.py            # PPO hyperparameters
└── mdp/
    ├── __init__.py                     # Imports isaaclab.envs.mdp.*
    ├── rewards.py                      # Custom rewards
    ├── observations.py                 # Custom observations
    ├── commands.py                     # Goal commands
    └── events.py                       # Cylinder movement
```

**ROS2 / Sim2Sim** (Unitree G1 real robot patterns):
```
ros2/colibri_g1_ros2_bridge.py    # Single-node ROS2 (publishers + subscribers)
ros2/colibri_g1_ros2_utils.py     # torch ↔ ROS2 conversions
sim2sim/isaac_colibri_g1_ros2.py  # Main sim2sim entry point
cfg/ros2_sim.yaml                 # Hydra configuration
```

### Environment Inheritance

```
G1FlatEnvCfg (isaaclab_tasks)
    └── DigitalTwinColibriG1EnvCfg
            ├── DigitalTwinColibriG1EnvCfg_PLAY
            └── DigitalTwinColibriG1SocialNavEnvCfg (adds LiDAR + cylinders)
                    └── DigitalTwinColibriG1SocialNavEnvCfg_PLAY
```

### MDP Components

Custom MDP functions in `mdp/`:
- **Rewards**: `goal_distance_exp`, `heading_alignment_reward`, `backwards_velocity_penalty`, `lidar_obstacle_proximity`, `smooth_trajectory_reward`
- **Observations**: `goal_position_observation` (goal in base frame)
- **Commands**: `SimpleGoalCommand` (autonomous goal generation), `GoalDirectedVelocityCommand`
- **Events**: `update_cylinder_obstacles` (moves cylinders via random waypoints)

### Training Logs

```
logs/rsl_rl/<experiment>/<timestamp>/
├── params/{env,agent}.yaml    # Config snapshots
├── model_<iter>.pt            # Checkpoints
└── videos/                    # If --video enabled
```

## Sim2Sim ROS2 Integration

### Unitree G1 Topic Pattern

Uses real robot topic patterns for sim2real compatibility:

| Topic | Type | Rate | Purpose |
|-------|------|------|---------|
| `/lowstate` | `unitree_hg/LowState` | 50 Hz | Motor + IMU state |
| `/lowcmd` | `unitree_hg/LowCmd` | - | Motor commands (subscribed) |
| `/utlidar/cloud` | `PointCloud2` | 15 Hz | LiDAR point cloud |
| `/front_cam/color_image` | `Image` | 50 Hz | RGB camera |
| `/front_cam/depth_image` | `Image` | 50 Hz | Depth camera |
| `/cmd_vel` | `Twist` | - | Velocity commands (subscribed) |

### Running Sim2Sim

```bash
# Native (requires ROS2 Humble)
source /opt/ros/humble/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
python sim2sim/isaac_colibri_g1_ros2.py

# Docker
docker-compose -f docker/docker-compose.yaml up isaac_sim_ros2
```

### Configuration (`cfg/ros2_sim.yaml`)

Key settings:
- `policy.checkpoint`: Path to trained model (must match observation dim)
- `ros2.use_unitree_topics`: Enable `/lowstate`, `/lowcmd` pattern
- `sensor.enable_lidar/camera`: Toggle sensors
- `performance.headless`: Run without GUI

## Social Navigation

### Cylinder Obstacles

The SocialNav task spawns moving cylinders as dynamic obstacles:

```python
# social_nav_env_cfg.py
obstacles: ObstacleManagerCfg = ObstacleManagerCfg()
    num_cylinders: int = 3          # Per environment
    cylinder_radius: float = 0.3    # Human body width
    cylinder_height: float = 1.8    # Human height
    move_speed_min: float = 0.3     # m/s
```

Cylinders use **dynamic rigid bodies** (not kinematic) due to Isaac Sim visual update bug with kinematic bodies.

### LiDAR-based Rewards

```python
# Obstacle avoidance rewards
self.rewards.obstacle_proximity_warning = RewTerm(
    func=mdp.lidar_obstacle_proximity,
    weight=-0.5,
    params={"threshold": 1.5, "std": 0.5},
)
self.rewards.obstacle_proximity_critical = RewTerm(
    func=mdp.lidar_obstacle_proximity,
    weight=-2.0,
    params={"threshold": 0.8, "std": 0.3},
)
```

## Important Notes

### Observation Dimension Mismatch

Policies are sensitive to observation dimensions. Current checkpoint expects 125 obs (with goal_position). If you see dimension errors, check:
- `cfg/ros2_sim.yaml` → `policy.checkpoint` path
- Environment observation config matches checkpoint training config

### Kinematic vs Dynamic Bodies

Isaac Sim 4.5/5.0 has a bug where kinematic bodies don't update visually. Cylinders use dynamic bodies with high damping instead:
```python
rigid_props=RigidBodyPropertiesCfg(
    kinematic_enabled=False,  # Must be False for visual updates
    disable_gravity=True,
    linear_damping=15.0,
)
```

### Code Formatting

```bash
pip install pre-commit
pre-commit run --all-files
```

### GPU Memory

Reduce `num_envs` if OOM:
- Base training: 512 → 256
- SocialNav: 128 → 64 (LiDAR + cylinders need more memory)
