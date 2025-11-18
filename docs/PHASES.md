# Implementation Phases - Detailed Breakdown

## Phase 1-5: Point-to-Point Navigation System ✅ COMPLETE

**Branch**: `feature/goal-tracking-infrastructure`

**Status**: Production ready, needs fine-tuning

**Goal**: Complete goal-directed point-to-point navigation system for G1 humanoid robot

### Core Components Implemented

#### 1. **Goal Position Management** (`SimpleGoalCommand`)
**File**: `mdp/commands.py`

Features:
- ✅ Forward-biased goal placement (80% tight forward cone at spawn, 65% forward hemisphere after reaching)
- ✅ Reach-based resampling (not timer-based) - goals regenerate when reached
- ✅ Smooth goal transitions (1.5s interpolation between positions)
- ✅ Dual-distance spawning:
  - Initial/reset: 2-4m from robot
  - After reaching: 0.5-1.5m small jump
- ✅ Dual-color visualization:
  - Green sphere when goal is far (> 0.3m)
  - Blue sphere when goal is reached (< 0.3m)
- ✅ Transform to base frame every step for ego-centric observation

#### 2. **Goal-Directed Velocity Commands** (`GoalDirectedVelocityCommand`)
**File**: `mdp/commands.py`

Features:
- ✅ Velocity ALWAYS points toward goal (no random component)
- ✅ Distance-based speed scaling:
  - Far (>3m): Full speed (1.0 m/s)
  - Near (<3m): Smooth deceleration to 20% minimum
- ✅ Heading-aware velocity scaling:
  - Fast when facing goal (alignment factor)
  - Slow when perpendicular/backwards
- ✅ **Critical fix**: Never commands backwards velocity (clamps vx to 0 minimum)
- ✅ High-gain proportional turning (gain=5.0) for aggressive direction changes
- ✅ Updates every step (not timer-based)

#### 3. **Navigation Rewards** (`mdp/rewards.py`)

**Goal Distance Rewards**:
- ✅ `goal_distance_exp` - Exponential reward for approaching goal
  - Coarse: weight=0.3, std=5.0 (wide gradient)
  - Fine: weight=0.2, std=3.0 (tight gradient for precision)

**Locomotion Quality Rewards**:
- ✅ `backwards_velocity_penalty` - Penalizes backwards movement
  - Weight: -0.5 (moderate penalty, allows turning)
  - Threshold: -0.05 m/s (small threshold for balance adjustments)

- ✅ `heading_alignment_reward` - Rewards facing toward goal
  - Weight: 0.3 (significant encouragement)
  - std: 0.5 (exponential kernel for tight alignment)

**Reward Balance**:
```
Velocity tracking:     weight 1.0 + 2.0 = 3.0 (dominant)
Goal tracking:         weight 0.3 + 0.2 = 0.5 (guidance)
Heading alignment:     weight 0.3 (turning encouragement)
Backwards penalty:     weight -0.5 (moderate discouragement)
Ratio:                 6:1 (velocity tracking vs navigation)
```

#### 4. **Observation Space**
- ✅ Goal position (2D: x, y) in base frame added to policy observations
- ✅ All standard G1 observations preserved (velocities, joint states, etc.)

### Current Configuration
```python
# Goal Position Command
self.commands.goal_position = mdp.SimpleGoalCommandCfg(
    asset_name="robot",
    resampling_time_range=(20.0, 30.0),  # Legacy (not used - reach-based now)
    forward_bias_probability=0.65,  # 65% forward after reaching
    goal_transition_time=1.5,  # Smooth 1.5s transitions
    debug_vis=True,
    ranges=mdp.SimpleGoalCommandCfg.Ranges(
        goal_distance=(2.0, 4.0),  # Initial spawn distance
        goal_reached_distance=(0.5, 1.5),  # Small jump on reach
    ),
)

# Goal-Directed Velocity Commands
self.commands.base_velocity = mdp.GoalDirectedVelocityCommandCfg(
    asset_name="robot",
    goal_command_name="goal_position",
    min_velocity_ratio=0.2,  # 20% minimum speed
    distance_scaling_factor=3.0,  # Start slowing at 3m
    debug_vis=True,
    ranges=mdp.GoalDirectedVelocityCommandCfg.Ranges(
        lin_vel_x=(0.0, 1.0),  # Forward: 0-1.0 m/s
        lin_vel_y=(-0.5, 0.5),  # Lateral: ±0.5 m/s
        ang_vel_z=(-1.0, 1.0),  # Rotation: ±1.0 rad/s
    ),
)
```

### Key Achievements

✅ **No backwards walking**: Fixed via clamping forward velocity commands to 0 minimum
✅ **Forward-biased spawning**: 80% tight forward cone at spawn prevents backwards goals
✅ **Reach-based resampling**: Eliminates standing/waiting behavior
✅ **Smooth transitions**: 1.5s interpolation reduces disorientation
✅ **Visual feedback**: Dual-color markers show goal state clearly
✅ **Aggressive turning**: High gain (5.0) encourages fast direction changes
✅ **Balanced rewards**: Navigation guides without breaking locomotion

### Known Limitations

⚠️ **Fine-tuning needed**:
- Reward weights may need adjustment based on training results
- Turning gain (5.0) might be too aggressive for some scenarios
- Backwards penalty weight (-0.5) might need tuning
- Distance scaling factor (3.0m) could be optimized

⚠️ **Not tested**:
- Long-duration training (>1000 iterations)
- Complex environments with obstacles
- Multi-goal sequences

### Testing Checklist

#### Visual Test (GUI observation):
```bash
python scripts/random_agent.py --task=Isaac-Colibri-G1-v0 --num_envs 4
```
- ✅ Goals visible and properly colored (green → blue when reached)
- ✅ Goals spawn mostly in front (80% at spawn, 65% after reaching)
- ✅ Goals jump small distance when reached (0.5-1.5m)
- ✅ Smooth transitions between goal positions
- ✅ Velocity arrows point toward goals

#### Headless Sanity Check:
```bash
python scripts/zero_agent.py --task=Isaac-Colibri-G1-v0 --num_envs 16 --headless
```
- ✅ No crashes or errors
- ✅ Metrics logging correctly
- ✅ Goal reached events firing

#### Training Test:
```bash
python scripts/rsl_rl/train.py --task=Isaac-Colibri-G1-v0 --num_envs 256 --headless --max_iterations 200
```
- ⏳ Learning progress (needs long-term training validation)
- ⏳ Reward values stable
- ⏳ No NaN/divergence

---

## Historical: Failed Approaches (For Reference)

### Phase 3: Velocity Biasing ⚠️ ABANDONED

**Approach**: `GoalBiasedVelocityCommand` - Blend random + goal-directed velocities

**Why it failed**:
- ❌ Distribution shift: Policy trained on uniform random, not biased distribution
- ❌ Conflicting objectives: Velocity tracking vs. goal reaching
- ❌ Locomotion quality degraded (awkward, slower movement)

**Lesson learned**: Don't force velocity command distribution. Either:
1. Use fully goal-directed commands (current approach), OR
2. Let policy discover goal-velocity relationships through pure reward (hierarchical approach)

---

## Phase 6: Sim2Sim ROS2 Integration 🏗️ IN PROGRESS

**Branch**: `feature/sim2sim-ros2`

**Goal**: Enable ROS2 communication for sim2sim transfer, monitoring, and future sim2real deployment

**Status**: Phase 0 (Documentation & Planning) ✅ COMPLETE

### Implementation Phases

#### Phase 6.0: Documentation & Setup ✅ COMPLETE
- ✅ Architecture documentation ([SIM2SIM_ROS2.md](SIM2SIM_ROS2.md))
- ✅ Docker setup guide ([DOCKER_SETUP.md](DOCKER_SETUP.md))
- ✅ Quick start guide (README_ROS2.md)
- ✅ Folder structure planning
- ⏳ Docker image building (Week 1)

#### Phase 6.1: Minimal ROS2 Bridge (Week 2)
**Files to Create**:
- `ros2/colibri_g1_ros2_bridge.py` - Main ROS2 node
- `sim2sim/isaac_colibri_g1_ros2.py` - Entry point
- `cfg/ros2_sim.yaml` - Configuration

**Publishers** (5 topics @ 50 Hz):
- `/colibri_g1/odom` (nav_msgs/Odometry)
- `/colibri_g1/joint_states` (sensor_msgs/JointState)
- `/colibri_g1/pose` (geometry_msgs/PoseStamped)
- `/colibri_g1/goal_marker` (visualization_msgs/Marker)
- `/clock` (rosgraph_msgs/Clock)

**Subscribers** (optional):
- `/colibri_g1/cmd_vel` (geometry_msgs/Twist) - external override

**TF Broadcaster**:
- `map` → `base_link` (50 Hz)

**Testing**:
```bash
./docker/launch.sh sim2sim         # Launch sim2sim
ros2 topic list                     # Verify 5+ topics
ros2 topic hz /colibri_g1/odom     # Check frequency
ros2 run tf2_tools view_frames      # Verify TF tree
```

#### Phase 6.2: Policy Integration (Week 3)
**Goal**: Load trained navigation policy and run autonomous navigation

**Key Components**:
- Load RSL-RL checkpoint from `logs/rsl_rl/isaac-colibri-g1-v0/`
- Reuse `DigitalTwinColibriG1EnvCfg_PLAY` (no scene recreation!)
- Run policy inference in `torch.inference_mode()`
- Publish navigation metrics:
  - `/colibri_g1/navigation/goal_pose`
  - `/colibri_g1/navigation/distance_to_goal`
  - `/colibri_g1/navigation/status`

**Environment Configuration**:
```python
class DigitalTwinColibriG1EnvCfg_ROS2(DigitalTwinColibriG1EnvCfg_PLAY):
    def __post_init__(self):
        super().__post_init__()
        self.scene.num_envs = 1                # Single robot
        self.episode_length_s = float('inf')   # Continuous operation
```

**Testing**:
- Verify robot navigates autonomously to goals
- Monitor policy performance vs. training metrics
- Check goal reach rate (expect >20% in 20s windows)

#### Phase 6.3: Visualization & Monitoring (Week 4)
**RViz2 Configuration** (`rviz/colibri_g1.rviz`):
- Robot model (URDF from Isaac Lab)
- TF tree visualization
- Odometry path trail
- Goal markers (green/blue)
- Navigation metrics display

**ROS2 Launch File** (`launch/isaac_sim_ros2.launch.py`):
- Launch Isaac Sim + RViz2 together
- Configure topic namespaces
- Set ROS_DOMAIN_ID

**Testing**:
```bash
./docker/launch.sh rviz             # Launch RViz2
ros2 topic echo /colibri_g1/navigation/distance_to_goal
```

#### Phase 6.4: Sensor Integration (Week 5-6) - OPTIONAL
**Camera Support**:
- Front RGB camera (640x480)
- Depth camera (optional)
- Topics: `/colibri_g1/front_cam/color_image`, `/front_cam/depth_image`
- Static TF: `base_link` → `front_camera_link`

**LiDAR Support** (optional):
- 2D or 3D LiDAR sensor
- Topic: `/colibri_g1/lidar/point_cloud`
- Static TF: `base_link` → `lidar_link`

**Reference**: `isaac-go2-ros2/g1/g1_sensors.py`

#### Phase 6.5: Sim2Sim Transfer Testing (Week 7+)
**Option A**: Two Isaac Lab Instances
- Instance 1: Publishes state via ROS2
- Instance 2: Subscribes to cmd_vel, executes actions
- Verify synchronized behavior

**Option B**: Isaac Lab ↔ Mujoco
- Export policy to ONNX/TorchScript
- Load in Mujoco with ROS2 bridge
- Compare trajectories

### Folder Structure (NEW)

```
digital_twin_colibri_g1/
├── ros2/                        # ROS2 bridge layer
│   ├── __init__.py
│   ├── colibri_g1_ros2_bridge.py
│   └── colibri_g1_ros2_utils.py
├── sim2sim/                     # Sim2sim entry points
│   ├── isaac_colibri_g1_ros2.py
│   └── test_ros2_connection.py
├── cfg/                         # YAML configurations
│   └── ros2_sim.yaml
├── docker/                      # Docker deployment
│   ├── Dockerfile
│   ├── docker-compose.yaml
│   ├── entrypoint.sh
│   └── launch.sh
├── rviz/                        # RViz2 configs
│   └── colibri_g1.rviz
└── launch/                      # ROS2 launch files
    └── isaac_sim_ros2.launch.py
```

### Design Decisions

1. **Autonomous Goals**: Keep `SimpleGoalCommand` (no external ROS2 goals in Phase 1-3)
2. **Single Robot**: `num_envs=1` for realistic deployment
3. **Docker-First**: Build container before native development (ROS2 on Arch challenge)
4. **Isaac Sim 5.0**: Target latest with ROS2 Humble (LTS until 2027)
5. **Reuse Scene**: Use existing `ColibriBuilding.usd` (no recreation needed)

### Success Criteria

Phase 6 Implementation Status:

**Completed** ✅:
- [x] ROS2 bridge implementation (6 publishers)
- [x] Policy integration (RSL-RL checkpoint loading)
- [x] Docker configuration (Isaac Sim 4.5.0 on Ubuntu 22.04 + ROS2 Humble)
- [x] Dependency management system
- [x] Documentation (DEPENDENCIES.md, SIM2SIM_ROS2.md, NETWORK_TROUBLESHOOTING.md)

**Testing** (After Docker build):
- [ ] Docker container launches Isaac Sim 4.5.0 with GUI
- [ ] ROS2 topics publish at 50 Hz
- [ ] Robot navigates autonomously using trained policy
- [ ] Goals visualized in RViz2
- [ ] TF tree correct (map → base_link)
- [ ] Policy performance matches training baseline
- [ ] Real-Time Factor ≥ 0.8

**Current Status**: Code complete, Docker build pending system reboot (kernel/module mismatch)

### Documentation

- [SIM2SIM_ROS2.md](SIM2SIM_ROS2.md) - Architecture, topic structure, design decisions
- [DOCKER_SETUP.md](DOCKER_SETUP.md) - Container build, X11 forwarding, troubleshooting
- README_ROS2.md - Quick start guide
- Updated [REFERENCES.md](REFERENCES.md) - ROS2 integration references

---

## Phase 7: Hierarchical Navigation (Alternative Approach) 🏗️ FUTURE

**Branch**: `feature/hierarchical-navigation` (not yet created)

**Goal**: Separate locomotion from navigation (IsaacLab best practice)

**Two-Stage Training**:

### Stage 1: Pre-train Locomotion
- Train pure velocity tracking for 3000-5000 iterations
- Focus: High-quality bipedal walking
- Save checkpoint: `locomotion_policy.pt`
- **Do NOT touch this policy again**

### Stage 2: Train Navigation
- Create new environment config
- Use `PreTrainedPolicyActionCfg` (like AnymalC navigation)
- High-level policy outputs: 3D velocity commands `[vx, vy, vyaw]`
- Frozen locomotion policy executes commands
- Train ONLY navigation policy

**Architecture**:
```
High-level Policy (learns):
  Input: [goal_pos, base_vel, gravity]
  Output: [vel_command_x, vel_command_y, vel_command_yaw]

Low-level Policy (frozen):
  Input: [vel_command, joint_states, ...]
  Output: [joint_position_targets]
```

**File Reference**:
`IsaacLab/source/isaaclab_tasks/manager_based/navigation/config/anymal_c/navigation_env_cfg.py`

**Advantages**:
- ✅ Best locomotion quality (dedicated policy)
- ✅ Faster navigation learning (simpler problem)
- ✅ Can reuse locomotion policy for other tasks
- ✅ Follows IsaacLab conventions

**Disadvantages**:
- ⏱️ Requires well-trained locomotion policy first
- 🔧 More complex setup
- 💾 Two policies to maintain

**When to Use**:
- If current approach doesn't achieve desired performance
- If you need best possible locomotion quality
- If you want to reuse locomotion across tasks

---

## Comparison: Goal-Directed vs Hierarchical Approaches

| Aspect | Goal-Directed (Current) | Hierarchical (Future) |
|--------|-------------------------|----------------------|
| **Architecture** | Single end-to-end policy | Two-stage (navigation + locomotion) |
| **Complexity** | Simple (one policy) | Complex (two policies) |
| **Training Time** | Moderate (learn together) | Faster (focused problems) |
| **Locomotion Quality** | Good (if balanced) | Excellent (dedicated policy) |
| **Navigation Learning** | Implicit (through velocity tracking) | Explicit (high-level policy) |
| **Robustness** | High (more exploration) | Lower (frozen locomotion) |
| **Maintainability** | Easier (one checkpoint) | Complex (two checkpoints) |
| **Best For** | Quick iteration, research, demos | Production, reusability, sim2real |
| **Status** | ✅ Implemented | 📋 Future work |

**Current Decision**: Start with goal-directed approach for simplicity and faster iteration. Consider hierarchical only if:
- Locomotion quality is insufficient
- Need to reuse locomotion for other tasks
- Sim2real deployment requires separation

---

## Git Workflow & Branch Management

### Current State

```bash
main (baseline G1 velocity tracking) - Phase 0
└── [MERGED] feature/goal-tracking-infrastructure ✅ (Phase 1-5: Complete navigation system)
    └── feature/sim2sim-ros2 🔄 (Phase 6: Sim2Sim ROS2 Integration)
        └── [Current: Implementation complete, testing after reboot]
```

### Branch Status

- **main**: ✅ Phase 1-5 merged (commit: bfa1776)
  - Contains: Full point-to-point navigation system
  - Checkpoint: `logs/rsl_rl/g1_flat/2025-11-09_16-20-14/model_550.pt`

- **feature/sim2sim-ros2**: 🔄 Phase 6 in progress (5 commits)
  - Contains: ROS2 bridge + Docker + Policy integration
  - Status: Code complete, Docker build pending reboot
  - Next: Build Docker image, test ROS2 topics, validate deployment

### Recommended Next Steps

1. **Option A: Merge to main**
   ```bash
   # After final validation
   git checkout main
   git merge feature/goal-tracking-infrastructure
   git tag v1.0-point-to-point-navigation
   git push origin main --tags
   ```

2. **Option B: Create release branch for fine-tuning**
   ```bash
   # Keep infrastructure branch, create tuning branch
   git checkout -b feature/navigation-fine-tuning feature/goal-tracking-infrastructure
   # Experiment with reward weights, hyperparameters
   ```

3. **Option C: Start new feature (sim2sim/sim2real)**
   ```bash
   # Merge current work first, then branch for new feature
   git checkout main
   git merge feature/goal-tracking-infrastructure
   git checkout -b feature/sim2sim-transfer
   ```

### Finding Trained Models

```bash
# List all training runs
ls -lt logs/rsl_rl/isaac-colibri-g1-v0/

# Navigate to specific run
cd logs/rsl_rl/isaac-colibri-g1-v0/<timestamp>/

# List checkpoints
ls -lh model_*.pt

# Play latest checkpoint
python scripts/rsl_rl/play.py \
  --task=Isaac-Colibri-G1-Play-v0 \
  --checkpoint logs/rsl_rl/isaac-colibri-g1-v0/<timestamp>/model_<iteration>.pt
```

### Future Branches (Planned)

- `feature/hierarchical-navigation`: Two-stage locomotion + navigation (Phase 6)
- `feature/sim2sim-transfer`: Sim2sim with Mujoco/ROS2
- `feature/sim2real-colibri`: Real robot deployment
- `feature/obstacle-avoidance`: Navigation with obstacles
