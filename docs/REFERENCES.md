# Key References and File Locations

## Project File Structure

```
digital_twin_colibri_g1/
├── source/digital_twin_colibri_g1/
│   └── digital_twin_colibri_g1/
│       └── tasks/manager_based/digital_twin_colibri_g1/
│           ├── __init__.py                          # Task registration
│           ├── digital_twin_colibri_g1_env_cfg.py   # Main environment config
│           ├── agents/
│           │   ├── rsl_rl_ppo_cfg.py               # PPO hyperparameters
│           │   └── skrl_ppo_cfg.yaml               # SKRL config (alternative)
│           └── mdp/
│               ├── __init__.py                      # MDP exports
│               ├── commands.py                      # Custom command generators
│               ├── commands_cfg.py                  # Command configurations
│               └── rewards.py                       # Custom reward functions
├── ros2/                                            # ROS2 bridge (Phase 6)
│   ├── __init__.py
│   ├── colibri_g1_ros2_bridge.py                   # Main ROS2 node
│   └── colibri_g1_ros2_utils.py                    # Utility functions
├── sim2sim/                                         # Sim2sim entry points
│   ├── isaac_colibri_g1_ros2.py                    # Main sim2sim script
│   └── test_ros2_connection.py                     # ROS2 testing
├── cfg/                                             # Configuration files
│   └── ros2_sim.yaml                               # ROS2 sim2sim config
├── docker/                                          # Docker deployment
│   ├── Dockerfile                                  # Container build
│   ├── docker-compose.yaml                         # Orchestration
│   ├── entrypoint.sh                               # Container entrypoint
│   └── launch.sh                                   # Helper script
├── rviz/                                            # RViz2 configs
│   └── colibri_g1.rviz                             # Visualization setup
├── launch/                                          # ROS2 launch files
│   └── isaac_sim_ros2.launch.py                    # ROS2 launch
├── scripts/
│   ├── list_envs.py                                # List available tasks
│   ├── zero_agent.py                               # Test with no actions
│   ├── random_agent.py                             # Test with random actions
│   └── rsl_rl/
│       ├── train.py                                 # Training script
│       └── play.py                                  # Evaluation script
├── assets/
│   └── colivriLab/
│       └── ColibriBuilding.usd                     # Lab environment mesh
├── logs/
│   └── rsl_rl/
│       └── isaac-colibri-g1-v0/
│           └── YYYY-MM-DD_HH-MM-SS/                # Training runs
│               ├── model_*.pt                       # Checkpoints
│               ├── params/                          # Configs
│               └── videos/                          # Recorded videos
└── docs/                                            # This documentation
    ├── README.md                                   # Documentation index
    ├── OVERVIEW.md                                 # Project goals
    ├── PHASES.md                                   # Implementation phases
    ├── PATH_A_VS_PATH_B.md                         # Navigation strategies
    ├── REFERENCES.md                               # This file
    ├── SIM2SIM_ROS2.md                             # ROS2 architecture (NEW)
    └── DOCKER_SETUP.md                             # Docker guide (NEW)
```

---

## Key Project Files

### Environment Configuration
**File**: `digital_twin_colibri_g1_env_cfg.py`

**Purpose**: Defines the RL environment (observations, actions, rewards, etc.)

**Key Sections**:
- Lines 48-96: `__post_init__` - Main configuration logic
- Lines 63-71: Terrain setup (loads Colibri USD)
- Lines 99-111: Goal position command
- Lines 118-122: Goal observation
- Lines 137-149: Velocity command (PHASE 3 - to be removed in Path A)
- Lines 152-162: Goal rewards

**Parent Class**: `G1FlatEnvCfg` (Isaac Lab's proven G1 config)

---

### Custom Commands
**File**: `mdp/commands.py`

**Classes**:

1. **`SimpleGoalCommand`** (Lines 27-176)
   - Generates random goal positions
   - Transforms to robot's base frame
   - Handles visualization
   - Tracks metrics

2. **`GoalBiasedVelocityCommand`** (Lines 179-261) - Phase 3, to be removed
   - Extends `UniformVelocityCommand`
   - Blends random + goal-directed velocities
   - **NOTE**: Causes awkward locomotion, will be removed

**Key Methods**:
- `_resample_command()`: Sample new goals/velocities
- `_update_command()`: Transform to base frame each step
- `_debug_vis_callback()`: Update visualization markers

---

### Custom Rewards
**File**: `mdp/rewards.py`

**Functions**:

1. **`goal_distance_exp`** (Lines 36-78)
   - Exponential reward for approaching goal
   - Formula: `exp(-distance^2 / std^2)`
   - Compatible with velocity tracking rewards

**Usage Example**:
```python
self.rewards.goal_tracking = RewTerm(
    func=mdp.goal_distance_exp,
    weight=0.3,
    params={"command_name": "goal_position", "std": 5.0},
)
```

---

### Command Configurations
**File**: `mdp/commands_cfg.py`

**Classes**:

1. **`SimpleGoalCommandCfg`** (Lines 21-64)
   - Configuration for goal position sampling
   - Includes visualization settings (large green sphere)

2. **`GoalBiasedVelocityCommandCfg`** (Lines 67-90) - To be removed
   - Extends UniformVelocityCommandCfg
   - Adds `goal_bias` parameter

---

## Isaac Lab Reference Files

### Base Locomotion Configuration

**G1 Flat Terrain Config**:
- Path: `IsaacLab/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/config/g1/flat_env_cfg.py`
- Parent of our config
- Defines velocity tracking rewards, observations, actions

**G1 Rough Terrain Config**:
- Path: Same directory, `rough_env_cfg.py`
- Defines all G1-specific rewards (feet_air_time, joint deviations, etc.)

**Key Rewards** (from G1Rewards class):
```python
track_lin_vel_xy_exp:     weight 1.0
track_ang_vel_z_exp:      weight 2.0
feet_air_time:            weight 0.25-0.75
termination_penalty:      weight -200.0
```

---

### Velocity Tracking Environment

**Base Class**:
- Path: `IsaacLab/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/velocity_env_cfg.py`
- Defines `LocomotionVelocityRoughEnvCfg`
- Contains all standard locomotion MDP components

**Velocity Tracking Rewards** (lines 231-263):
- `track_lin_vel_xy_exp`: Exponential reward for XY velocity matching
- `track_ang_vel_z_exp`: Exponential reward for yaw velocity matching
- Formula: `exp(-error / std^2)` where `error = sum((command - actual)^2)`

**MDP Functions**:
- Path: `IsaacLab/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/mdp/rewards.py`
- Implementation of velocity tracking rewards
- Lines 87-97: `track_lin_vel_xy_yaw_frame_exp` function

---

### Navigation Reference (AnymalC)

**Navigation Environment Config**:
- Path: `IsaacLab/source/isaaclab_tasks/isaaclab_tasks/manager_based/navigation/config/anymal_c/navigation_env_cfg.py`
- **CRITICAL REFERENCE** for Path B (hierarchical approach)

**Key Insights**:
- Uses `PreTrainedPolicyActionCfg` (frozen locomotion policy)
- High-level policy outputs 3D velocity commands
- Observations: minimal (just goal, velocity, gravity)
- Rewards: only navigation-related
- Decimation: 10x higher than locomotion (slower control)

**Action Configuration** (lines 49-55):
```python
pre_trained_policy_action: mdp.PreTrainedPolicyActionCfg(
    asset_name="robot",
    policy_path="Policies/ANYmal-C/Blind/policy.pt",  # Frozen!
    low_level_decimation=4,
    low_level_actions=LOW_LEVEL_ENV_CFG.actions.joint_pos,
    low_level_observations=LOW_LEVEL_ENV_CFG.observations.policy,
)
```

**Navigation Rewards** (lines 80-94):
- `position_tracking`: Tanh reward (std=2.0, weight=0.5)
- `position_tracking_fine_grained`: Tanh reward (std=0.2, weight=0.5)
- `orientation_tracking`: Heading error (weight=-0.2)

**Navigation MDP**:
- Path: `IsaacLab/source/isaaclab_tasks/isaaclab_tasks/manager_based/navigation/mdp/`
- Contains `PreTrainedPolicyAction` implementation
- Contains navigation-specific reward functions

---

### Command Generators

**Velocity Commands**:
- Path: `IsaacLab/source/isaaclab/isaaclab/envs/mdp/commands/velocity_command.py`
- Classes: `UniformVelocityCommand`, `NormalVelocityCommand`
- Our `GoalBiasedVelocityCommand` extends this

**Position Commands**:
- Path: `IsaacLab/source/isaaclab/isaaclab/envs/mdp/commands/pose_2d_command.py`
- Classes: `UniformPose2dCommand`, `TerrainBasedPose2dCommand`
- Reference for goal position sampling

**Command Configurations**:
- Path: `IsaacLab/source/isaaclab/isaaclab/envs/mdp/commands/commands_cfg.py`
- All standard command config classes
- Shows how to configure visualizations, ranges, etc.

---

### ROS2 Integration & Sim2Sim (Phase 6)

**ROS2 Bridge Files**:
- `ros2/colibri_g1_ros2_bridge.py` - Main ROS2 node (RobotDataManager class)
- `ros2/colibri_g1_ros2_utils.py` - Helper functions for ROS2 message conversion
- `sim2sim/isaac_colibri_g1_ros2.py` - Entry point for sim2sim deployment

**Key ROS2 Topics**:
```
Publishers (50 Hz):
  /colibri_g1/odom                    # nav_msgs/Odometry
  /colibri_g1/joint_states            # sensor_msgs/JointState
  /colibri_g1/pose                    # geometry_msgs/PoseStamped
  /colibri_g1/goal_marker             # visualization_msgs/Marker (1 Hz)
  /clock                              # rosgraph_msgs/Clock

Subscribers:
  /colibri_g1/cmd_vel                 # geometry_msgs/Twist (optional)
```

**Inspiration Files**:
- `isaac-go2-ros2/ros2/g1_ros2_bridge.py` - Basic ROS2 bridge structure
- `isaac-go2-ros2/ros2/go2_ros2_bridge.py` - Sensor integration example
- `isaac-go2-ros2/isaac_g1_ros2.py` - Main entry point pattern
- `isaac-go2-ros2/go2/go2_ctrl.py` - Policy loading example

**Isaac Sim ROS2 Documentation**:
- [ROS2 Landing Page](https://docs.isaacsim.omniverse.nvidia.com/latest/ros2_tutorials/ros2_landing_page.html)
- [OmniGraph ROS2 Bridge](https://docs.isaacsim.omniverse.nvidia.com/latest/ros2_tutorials/tutorial_ros2_omnigraph.html)
- [ROS2 Messages](https://docs.isaacsim.omniverse.nvidia.com/latest/ros2_tutorials/tutorial_ros2_messages.html)
- [ROS2 TF Publishing](https://docs.isaacsim.omniverse.nvidia.com/latest/ros2_tutorials/tutorial_ros2_tf.html)

**ROS2 Packages**:
- `rclpy` - ROS2 Python client library
- `tf2_ros` - Transform library (TF2)
- `geometry_msgs` - Pose, Twist, Transform messages
- `nav_msgs` - Odometry messages
- `sensor_msgs` - JointState, Image, PointCloud2
- `visualization_msgs` - Marker (goal visualization)

**Docker Configuration**:
- `docker/Dockerfile` - Multi-stage build (Isaac Sim + ROS2 Humble)
- `docker/docker-compose.yaml` - Service orchestration with GPU support
- `docker/entrypoint.sh` - Container initialization script
- `docker/launch.sh` - Helper script for common operations

**Configuration**:
- `cfg/ros2_sim.yaml` - Hydra config for ROS2 sim2sim
  - num_envs: 1 (single robot)
  - freq: 50 Hz (control rate)
  - ROS2 settings (namespace, domain ID)
  - Policy checkpoint path

**Documentation**:
- [SIM2SIM_ROS2.md](SIM2SIM_ROS2.md) - Complete architecture and design decisions
- [DOCKER_SETUP.md](DOCKER_SETUP.md) - Docker build and troubleshooting guide
- README_ROS2.md - Quick start guide for ROS2 features

---

### Visualization Markers

**Marker Configurations**:
- Path: `IsaacLab/source/isaaclab/isaaclab/markers/config/__init__.py`
- Defines marker types: arrows, spheres, frames, etc.
- Our green sphere uses `SphereCfg` with emissive material

**Key Markers Used**:
```python
GREEN_ARROW_X_MARKER_CFG  # For velocity commands
SPHERE_MARKER_CFG         # Base for our goal spheres
```

---

## Training Scripts

### Training Script
**Path**: `scripts/rsl_rl/train.py`

**Usage**:
```bash
python scripts/rsl_rl/train.py \
    --task=Isaac-Colibri-G1-v0 \
    --num_envs 256 \
    --headless \
    --max_iterations 3000 \
    --logger tensorboard \
    --experiment_name my_experiment
```

**Key Arguments**:
- `--task`: Environment task name
- `--num_envs`: Number of parallel environments
- `--headless`: Run without GUI (faster)
- `--max_iterations`: Training iterations
- `--logger`: Logging backend (tensorboard, wandb, neptune)
- `--resume`: Resume from checkpoint
- `--load_run`: Specify run folder to resume

**Output**: Logs to `logs/rsl_rl/<task_name>/<timestamp>/`

---

### Play Script
**Path**: `scripts/rsl_rl/play.py`

**Usage**:
```bash
python scripts/rsl_rl/play.py \
    --task=Isaac-Colibri-G1-Play-v0 \
    --checkpoint logs/rsl_rl/isaac-colibri-g1-v0/2025-11-10_13-52-28/model_1500.pt \
    --num_envs 4 \
    --video
```

**Key Arguments**:
- `--task`: Use PLAY variant (fewer envs, no randomization)
- `--checkpoint`: Path to model checkpoint (.pt file)
- `--num_envs`: Number of environments to visualize
- `--video`: Record video
- `--use_pretrained_checkpoint`: Use published checkpoint (if available)

---

### Testing Scripts

**Zero Agent** (robot does nothing):
```bash
python scripts/zero_agent.py --task=Isaac-Colibri-G1-v0 --num_envs 4
```
- Useful for verifying environment setup
- Check visualizations
- Test that robot spawns correctly

**Random Agent** (random actions):
```bash
python scripts/random_agent.py --task=Isaac-Colibri-G1-v0 --num_envs 4
```
- Test that actions work
- Observe robot physics
- Check reward computation

**List Environments**:
```bash
python scripts/list_envs.py
```
- Shows all registered tasks
- Verify your task appears

---

## Documentation

**Isaac Lab Docs**:
- Main: https://isaac-sim.github.io/IsaacLab/
- Installation: https://isaac-sim.github.io/IsaacLab/main/source/setup/installation/
- Tutorials: https://isaac-sim.github.io/IsaacLab/main/source/tutorials/

**Key Concepts**:
- Manager-Based RL Env: https://isaac-sim.github.io/IsaacLab/main/source/api/isaaclab.envs.html
- MDP Terms: https://isaac-sim.github.io/IsaacLab/main/source/api/isaaclab.managers.html
- Commands: https://isaac-sim.github.io/IsaacLab/main/source/api/isaaclab.envs.mdp.html#commands

**RSL-RL Library**:
- GitHub: https://github.com/leggedrobotics/rsl_rl
- Paper: "Learning to Walk in Minutes..." (ETH Zurich)

**SKRL Library** (alternative):
- GitHub: https://github.com/Toni-SM/skrl
- Docs: https://skrl.readthedocs.io/

---

## Useful Commands

### Find Latest Training Run
```bash
ls -lt logs/rsl_rl/ | head
# Shows most recent folders first
```

### Find Latest Checkpoint
```bash
ls -lh logs/rsl_rl/isaac-colibri-g1-v0/<timestamp>/model_*.pt
# Lists all checkpoints with sizes
```

### Monitor Training (Tensorboard)
```bash
tensorboard --logdir logs/rsl_rl/
# Open browser to http://localhost:6006
```

### Git Branches
```bash
git branch -a                    # List all branches
git checkout <branch-name>       # Switch branch
git log --oneline --graph        # View commit history
```

### Check GPU Usage
```bash
nvidia-smi               # Current GPU status
watch -n 1 nvidia-smi    # Real-time monitoring
```

---

## Common File Paths (Quick Reference)

```
# Our project config
source/digital_twin_colibri_g1/digital_twin_colibri_g1/tasks/manager_based/digital_twin_colibri_g1/digital_twin_colibri_g1_env_cfg.py

# Isaac Lab G1 base config
~/Documents/uniandes/MISIS/thesis/IsaacLab/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/config/g1/flat_env_cfg.py

# Isaac Lab navigation reference
~/Documents/uniandes/MISIS/thesis/IsaacLab/source/isaaclab_tasks/isaaclab_tasks/manager_based/navigation/config/anymal_c/navigation_env_cfg.py

# Latest training logs
logs/rsl_rl/isaac-colibri-g1-v0/<FIND_LATEST_TIMESTAMP>/
```

---

## Isaac Lab Version Info

**Recommended Version**: Isaac Sim 4.5.0 or 5.0.0
**Python Version**: 3.10 or 3.11
**CUDA**: Compatible with your GPU (RTX 4080 Super)

**Check Isaac Lab Version**:
```bash
python -c "import isaaclab; print(isaaclab.__version__)"
```

**RSL-RL Version** (minimum 3.0.1):
```bash
python -c "import rsl_rl; print(rsl_rl.__version__)"
```
