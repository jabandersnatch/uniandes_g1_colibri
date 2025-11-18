# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Digital Twin for the Colibri G1 humanoid robot** built on top of Isaac Lab. The project uses the Unitree G1 humanoid robot to learn velocity tracking behaviors in a custom USD environment representing the Colibri digital twin environment.

**Framework**: Isaac Lab extension built on Isaac Sim (NVIDIA Omniverse)
**RL Libraries**: RSL-RL and SKRL for reinforcement learning
**Robot**: Unitree G1 humanoid robot
**Task**: Velocity-based locomotion in custom USD environment

## Installation & Setup

### Initial Installation

1. Install Isaac Lab first (see [Isaac Lab installation guide](https://isaac-sim.github.io/IsaacLab/main/source/setup/installation/index.html))
   - Recommended: conda or uv installation for easier Python script execution

2. Install this extension in editable mode:
   ```bash
   # From the repository root
   # If Isaac Lab is in Python venv/conda:
   python -m pip install -e source/digital_twin_colibri_g1

   # If Isaac Lab is NOT in venv/conda:
   # PATH_TO_isaaclab.sh -p -m pip install -e source/digital_twin_colibri_g1
   ```

### Verification

List available environments:
```bash
python scripts/list_envs.py
```

This should show environments with names containing `Isaac-Colibri-G1`.

### Code Formatting

Install and run pre-commit for automatic code formatting:
```bash
pip install pre-commit
pre-commit run --all-files
```

## Common Commands

### Training

Train with RSL-RL (default):
```bash
python scripts/rsl_rl/train.py --task=Isaac-Colibri-G1-v0
```

Train with SKRL:
```bash
python scripts/skrl/train.py --task=Isaac-Colibri-G1-v0
```

### Training Options

- `--num_envs <N>`: Number of parallel environments (default: 512 for training)
- `--seed <N>`: Random seed for reproducibility
- `--max_iterations <N>`: Maximum training iterations
- `--video`: Record videos during training
- `--video_length <N>`: Video length in steps (default: 200)
- `--video_interval <N>`: Record video every N steps (default: 2000)
- `--distributed`: Multi-GPU training
- `--headless`: Run without GUI (faster)
- `--device <cuda:0|cpu>`: Device for simulation

### Play/Evaluation

Play trained policy:
```bash
python scripts/rsl_rl/play.py --task=Isaac-Colibri-G1-Play-v0
```

Options:
- `--checkpoint <path>`: Path to checkpoint file
- `--use_pretrained_checkpoint`: Use published pre-trained checkpoint (if available)
- `--video`: Record video during playback
- `--num_envs <N>`: Number of environments to visualize (default: 10 for play mode)
- `--real-time`: Run at real-time speed

### Testing with Dummy Agents

Zero-action agent (robot does nothing):
```bash
python scripts/zero_agent.py --task=Isaac-Colibri-G1-v0
```

Random-action agent:
```bash
python scripts/random_agent.py --task=Isaac-Colibri-G1-v0
```

These are useful for verifying environment configuration.

## Architecture

### Package Structure

```
source/digital_twin_colibri_g1/
└── digital_twin_colibri_g1/
    ├── tasks/
    │   └── manager_based/
    │       └── digital_twin_colibri_g1/
    │           ├── __init__.py                    # Gym environment registration
    │           ├── digital_twin_colibri_g1_env_cfg.py  # Environment configurations
    │           ├── agents/
    │           │   ├── rsl_rl_ppo_cfg.py         # RSL-RL PPO configuration
    │           │   └── skrl_ppo_cfg.yaml         # SKRL PPO configuration
    │           └── mdp/
    │               ├── __init__.py
    │               └── rewards.py                # Custom reward functions
    └── ui_extension_example.py                   # Omniverse UI extension (optional)
```

### Key Components

1. **Environment Configuration** (`digital_twin_colibri_g1_env_cfg.py`):
   - `DigitalTwinColibriG1EnvCfg`: Training configuration
     - Inherits from `G1FlatEnvCfg` (Isaac Lab's G1 base configuration)
     - Loads custom USD environment from `assets/colivriLab/colivrilabv0.usd`
     - Configures 512 parallel environments with 10m spacing
     - Episode length: 20 seconds
     - Velocity commands: forward (0-1 m/s), lateral (-0.5 to 0.5 m/s), rotation (-1 to 1 rad/s)
   - `DigitalTwinColibriG1EnvCfg_PLAY`: Evaluation configuration
     - 10 environments for visualization
     - Disables randomization and noise
     - Longer episodes (30 seconds)

2. **Environment Registration** (`__init__.py`):
   - `Isaac-Colibri-G1-v0`: Training task
   - `Isaac-Colibri-G1-Play-v0`: Evaluation task
   - Both use G1's proven PPO configuration from `isaaclab_tasks` as default agent config

3. **MDP Functions** (`mdp/`):
   - Imports all standard Isaac Lab MDP functions
   - Custom reward functions can be added in `rewards.py`
   - Used by environment config to define task-specific rewards, observations, actions

4. **Agent Configurations**:
   - RSL-RL: `ColibriG1PPORunnerCfg` inherits from `G1FlatPPORunnerCfg`
   - SKRL: YAML-based configuration
   - Both can be customized with hyperparameters specific to Colibri task

### Training Pipeline

1. **Script entry** (`scripts/rsl_rl/train.py` or `scripts/skrl/train.py`)
2. **Hydra configuration loading** via `@hydra_task_config` decorator
   - Loads environment config and agent config
   - Supports config overrides via CLI
3. **Environment creation** via `gym.make(task_name, cfg=env_cfg)`
4. **Environment wrapping** with RL library-specific wrapper
5. **Runner creation** (OnPolicyRunner or DistillationRunner for RSL-RL)
6. **Training loop** with logging to `logs/rsl_rl/<experiment_name>/<timestamp>/`

### Logs Structure

```
logs/
└── rsl_rl/
    └── <experiment_name>/
        └── <timestamp>/
            ├── params/
            │   ├── env.yaml      # Environment configuration
            │   ├── agent.yaml    # Agent configuration
            │   ├── env.pkl
            │   └── agent.pkl
            ├── model_<iter>.pt   # Checkpoint files
            └── videos/           # Training videos (if --video enabled)
```

## Customization Guide

### Modifying the Environment

**Change USD environment**:
- Replace `assets/colivriLab/colivrilabv0.usd` or update path in `digital_twin_colibri_g1_env_cfg.py:63`

**Adjust velocity ranges**:
- Modify `self.commands.base_velocity.ranges` in `digital_twin_colibri_g1_env_cfg.py:95-97`

**Change number of parallel environments**:
- Edit `self.scene.num_envs` in `digital_twin_colibri_g1_env_cfg.py:81`
- Or use `--num_envs` CLI argument

**Add custom rewards**:
- Define reward function in `mdp/rewards.py`
- Add to `self.rewards` in environment config using `RewTerm`

**Modify observations**:
- Override observation groups in environment config
- G1 base config includes: base velocities, projected gravity, joint states, velocity commands, actions

### Modifying Training

**Change hyperparameters** (RSL-RL):
- Override in `agents/rsl_rl_ppo_cfg.py:29-53`
- Examples: learning rate, network architecture, training iterations, save interval

**Change experiment name**:
- Use `--experiment_name` CLI argument
- Or modify `self.experiment_name` in agent config

**Enable logging**:
- Use `--logger wandb` or `--logger tensorboard`
- Use `--log_project_name <name>` for wandb/neptune

### Resume Training

```bash
python scripts/rsl_rl/train.py --task=Isaac-Colibri-G1-v0 --resume --load_run <run_folder>
```

## Important Notes

### Isaac Lab Version Compatibility

- Requires Isaac Sim 4.5.0 or 5.0.0
- Python 3.10 or 3.11
- RSL-RL minimum version: 3.0.1
- Training scripts automatically check for correct RSL-RL version

### Python Path Issues

If Pylance can't find modules:
1. Run VSCode task `setup_python_env` (Ctrl+Shift+P → Tasks: Run Task)
2. Add extension path to `.vscode/settings.json`:
   ```json
   {
     "python.analysis.extraPaths": [
       "<path-to-repo>/source/digital_twin_colibri_g1"
     ]
   }
   ```

### Performance Tuning

- **GPU memory limited**: Reduce `num_envs` (512 → 256 or lower)
- **Complex USD scene**: Further reduce `num_envs` or increase `env_spacing`
- **Faster training**: Use `--headless` mode, disable video recording
- **Multi-GPU**: Use `--distributed` flag

### Entry Points

When working with tasks, remember that the registration system uses:
- `env_cfg_entry_point`: Points to environment config class
- `rsl_rl_cfg_entry_point`: Points to agent config class
- Task names must match the pattern in `scripts/list_envs.py` (`"Isaac-Colibri-G1"`) to be listed

The environment inherits from Isaac Lab's proven G1 locomotion configuration, so most locomotion behaviors are already well-tuned. Focus customizations on:
1. Environment-specific rewards
2. Velocity command ranges appropriate for the Colibri environment
3. Obstacle avoidance (if needed)
4. Domain-specific observations

---

## Phase 6: Sim2Sim ROS2 Integration (Docker Deployment)

### Overview

Phase 6 adds ROS2 integration for sim-to-sim transfer, enabling the trained G1 policy to run in a containerized environment with ROS2 communication.

**Status**: Implementation complete, Docker build ready after system reboot

**Branch**: `feature/sim2sim-ros2`

### Docker Deployment

The project includes a complete Docker setup with:
- **Isaac Sim 5.1.0** (latest NVIDIA simulator)
- **Isaac Lab 2.2+** (latest compatible version)
- **ROS2 Humble** (LTS until 2027)
- **CycloneDDS** (high-performance middleware)
- **Trained policy integration** (RSL-RL checkpoint loading)

### Quick Start (Docker)

```bash
# Build Docker image (30-60 min first time)
docker-compose -f docker/docker-compose.yaml build

# Run sim2sim with ROS2 bridge
docker-compose -f docker/docker-compose.yaml up isaac_sim_ros2

# In another terminal, check ROS2 topics
docker exec -it colibri_g1_sim2sim bash -c "source /opt/ros/humble/setup.bash && ros2 topic list"

# Launch RViz2 for visualization
docker-compose -f docker/docker-compose.yaml run --rm rviz2
```

### ROS2 Topics Published

The sim2sim bridge publishes:

| Topic | Type | Rate | Description |
|-------|------|------|-------------|
| `/colibri_g1/odom` | `nav_msgs/Odometry` | 50 Hz | Full odometry (pose + twist) |
| `/colibri_g1/joint_states` | `sensor_msgs/JointState` | 50 Hz | 29-DOF joint positions/velocities |
| `/colibri_g1/pose` | `geometry_msgs/PoseStamped` | 10 Hz | Simplified pose only |
| `/tf` | `tf2_msgs/TFMessage` | 50 Hz | Transform: map → base_link |
| `/colibri_g1/goal_marker` | `visualization_msgs/Marker` | 10 Hz | Goal visualization (color-coded) |
| `/colibri_g1/navigation_metrics` | Custom | 10 Hz | Distance to goal, status |
| `/clock` | `rosgraph_msgs/Clock` | Sim rate | Simulation time |

### Key Files

**ROS2 Bridge**:
- `ros2/colibri_g1_ros2_bridge.py` - Main bridge (6 publishers implemented)
- `ros2/colibri_g1_ros2_utils.py` - Conversion utilities (torch ↔ ROS2)

**Sim2Sim Entry Point**:
- `sim2sim/isaac_colibri_g1_ros2.py` - Main script with policy loading
- `cfg/ros2_sim.yaml` - Hydra configuration

**Docker**:
- `docker/Dockerfile` - Multi-stage build (5 stages)
- `docker/docker-compose.yaml` - Service orchestration
- `docker/entrypoint.sh` - Container initialization
- `docker/launch.sh` - Helper script (build, run, enter, etc.)

**Documentation**:
- `README_ROS2.md` - ROS2 integration guide
- `docs/SIM2SIM_ROS2.md` - Architecture and design
- `docs/DEPENDENCIES.md` - Dependency management (pip + apt)
- `docker/NETWORK_TROUBLESHOOTING.md` - Docker networking issues
- `NEXT_STEPS.md` - Post-implementation testing guide

### Docker Troubleshooting

**Common Issues**:

1. **Network bridge error during build**:
   - Cause: Kernel/module mismatch (veth module unavailable)
   - Solution: Reboot system to load updated kernel
   - See: `docker/NETWORK_TROUBLESHOOTING.md`

2. **GPU not detected**:
   ```bash
   # Install nvidia-container-toolkit
   # https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html
   ```

3. **X11 permission denied**:
   ```bash
   xhost +local:docker
   ```

4. **ROS2 topics not visible**:
   - Check `ROS_DOMAIN_ID=0` matches between containers
   - Verify `network_mode: host` in docker-compose.yaml

### Dependency Management

Isaac Lab uses its own dependency system (NOT `uv` or `requirements.txt`):

**Python packages** → `source/digital_twin_colibri_g1/setup.py`:
```python
INSTALL_REQUIRES = [
    "psutil",
    "rclpy",  # ROS2 Python client
]
```

**Extension packages** → `source/digital_twin_colibri_g1/config/extension.toml`:
```toml
[python.pipapi]
requirements = ["hydra-core"]
```

**ROS2 message packages** → Installed via APT (NOT pip):
```bash
# In Dockerfile Stage 2
apt-get install ros-humble-desktop  # Includes all standard messages
```

See `docs/DEPENDENCIES.md` for complete guide.

### Native Installation (Alternative to Docker)

If you prefer running natively without Docker:

```bash
# Prerequisites
sudo apt install ros-humble-desktop ros-humble-rmw-cyclonedds-cpp

# Install extension
pip install -e source/digital_twin_colibri_g1

# Run sim2sim
source /opt/ros/humble/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
python sim2sim/isaac_colibri_g1_ros2.py
```

### Policy Checkpoint

The sim2sim script loads a trained RSL-RL policy:

**Default checkpoint**: `logs/rsl_rl/g1_flat/2025-11-09_16-20-14/model_550.pt`

**To use a different checkpoint**, edit `cfg/ros2_sim.yaml`:
```yaml
policy:
  checkpoint: "path/to/your/model.pt"
  device: "cuda"
  deterministic: true
```

### Testing Workflow

1. **Build Docker image** (see `NEXT_STEPS.md`)
2. **Start sim2sim**: `docker-compose up isaac_sim_ros2`
3. **Verify ROS2 topics**: `ros2 topic list`
4. **Monitor navigation**: `ros2 topic echo /colibri_g1/navigation_metrics`
5. **Visualize in RViz2**: `docker-compose run --rm rviz2`

### Next Phase: Sim2Real

After validating Phase 6, the next step is deploying to the physical Colibri G1 robot:
- Adapt ROS2 topics to real robot interfaces
- Add sensor feedback (IMU, cameras, force-torque)
- Implement safety constraints and emergency stop
- Real-world domain randomization validation
