# Digital Twin Colibri G1 - Project Evidence

## 1. Project Overview

**Project Name:** Digital Twin for Colibri G1 Humanoid Robot
**Repository Path:** `uniandes_g1_colibri/digital_twin_colibri_g1/`
**Framework:** Isaac Lab Extension (NVIDIA Omniverse)
**Robot:** Unitree G1 29-DOF Humanoid Robot
**Primary Task:** Velocity-based locomotion with goal-directed navigation

### 1.1 Project Objectives

The project implements four major features:

1. **Custom RL Task for Point-to-Point Velocity-Based Locomotion** (Completed)
2. **Sim2Sim Transfer with ROS2 Communication** (Phase 6 - Completed)
3. **Social Navigation with LiDAR and Obstacle Avoidance** (Partially Completed)
4. **Sim2Real Transfer to Physical Colibri G1 Robot** (Planned)

### 1.2 Technology Stack

| Component | Version/Tool | Purpose |
|-----------|--------------|---------|
| Physics Engine | Isaac Sim 4.5.0 / 5.0.0 | High-fidelity robot simulation |
| RL Framework | Isaac Lab 2.1.0 - 2.2.0 | Manager-based RL environments |
| RL Library | RSL-RL / SKRL | PPO training and inference |
| Robot Control | ROS2 Humble | Sim2Sim communication |
| Middleware | CycloneDDS | Unitree robot compatibility |
| Containerization | Docker | Deployment and reproducibility |

### 1.3 Repository Structure

```
digital_twin_colibri_g1/
├── assets/                    # USD scene assets (390+ files)
│   └── ColibriLab/           # Custom environment models
├── cfg/                       # Configuration files
│   └── ros2_sim.yaml         # Sim2sim configuration
├── docker/                    # Multi-stage Docker build (6 stages)
│   ├── Dockerfile            # ~365 lines
│   └── docker-compose.yaml
├── docs/                      # Comprehensive documentation (22 files)
├── launch/                    # ROS2 launch files
├── ros2/                      # ROS2 bridge implementation
│   ├── colibri_g1_ros2_bridge.py    # Unified ROS2 node (~675 lines)
│   └── colibri_g1_ros2_utils.py     # Conversion utilities
├── sensors/                   # Sensor management
│   └── colibri_g1_sensors.py        # RTX LiDAR + Camera (~250 lines)
├── sim2sim/                   # Sim2sim entry points
│   └── isaac_colibri_g1_ros2.py     # Main sim2sim script (~235 lines)
├── scripts/                   # Training and testing scripts
│   ├── rsl_rl/               # RSL-RL training scripts
│   └── skrl/                 # SKRL training scripts
├── source/                    # Isaac Lab extension source
│   └── digital_twin_colibri_g1/
│       └── tasks/
│           └── manager_based/
│               └── digital_twin_colibri_g1/
│                   ├── __init__.py              # Task registration
│                   ├── digital_twin_colibri_g1_env_cfg.py  # Base environment (~333 lines)
│                   ├── social_nav_env_cfg.py    # Social nav environment (~419 lines)
│                   ├── agents/                  # PPO configurations
│                   │   └── rsl_rl_ppo_cfg.py   # Custom PPO configs (~116 lines)
│                   └── mdp/                     # MDP components
│                       ├── commands.py          # Goal and velocity commands (~570 lines)
│                       ├── rewards.py           # Custom reward functions (~409 lines)
│                       ├── observations.py      # LiDAR observations (~91 lines)
│                       └── events.py            # Cylinder obstacle events (~162 lines)
├── tests/                     # Test files
└── unitree_msgs/             # ROS2 message definitions
    ├── unitree_api/
    ├── unitree_go/
    └── unitree_hg/           # G1-specific messages (35 motors)
```

### 1.4 Registered Gymnasium Tasks

| Task ID | Purpose | num_envs | Features |
|---------|---------|----------|----------|
| `Isaac-Colibri-G1-v0` | Training | 512 | Goal tracking, velocity commands |
| `Isaac-Colibri-G1-Play-v0` | Evaluation | 10 | No randomization, visualization |
| `Isaac-Colibri-G1-SocialNav-v0` | Social Nav Training | 128 | LiDAR + cylinders + avoidance |
| `Isaac-Colibri-G1-SocialNav-Play-v0` | Social Nav Evaluation | 4 | LiDAR visualization enabled |

### 1.5 Code Statistics

| Category | Files | Lines of Code |
|----------|-------|---------------|
| Core Environment Configs | 2 | ~750 |
| MDP Components | 5 | ~1,230 |
| ROS2 Integration | 2 | ~720 |
| Sim2Sim Scripts | 2 | ~280 |
| Sensors | 1 | ~250 |
| Docker | 4 | ~450 |
| Agent Configs | 2 | ~170 |
| **Total Custom Code** | **~18** | **~3,850** |

### 1.6 Development Status

| Feature | Status | Description |
|---------|--------|-------------|
| Base G1 Locomotion | Complete | Inherits from Isaac Lab's G1FlatEnvCfg |
| Goal-Directed Navigation | Complete | Custom command generators + rewards |
| ROS2 Sim2Sim Bridge | Complete | Unified single-node architecture |
| Docker Deployment | Complete | Multi-stage build with Isaac Sim 4.5.0 |
| RTX LiDAR Support | Complete | Hesai XT32 sensor integration |
| Camera Support | Complete | RGB + Depth via OmniGraph |
| Social Navigation | Partial | Infrastructure ready, rewards need tuning |
| Sim2Real | Planned | Phase 7 - Real Colibri G1 deployment |
