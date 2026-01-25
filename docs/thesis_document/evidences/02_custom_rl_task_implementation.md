# Custom RL Task Implementation Evidence

## 2. Goal-Directed Locomotion Task

### 2.1 Design Philosophy

The base locomotion task extends Isaac Lab's proven `G1FlatEnvCfg` configuration while adding custom goal-directed navigation capabilities. The approach follows these principles:

1. **Inherit Proven Locomotion** - Leverage G1's tested velocity tracking rewards
2. **Add Goal Guidance** - Custom command generators direct robot toward goals
3. **Maintain Stability** - Goal rewards complement (not replace) velocity tracking

### 2.2 Environment Configuration

**File:** `source/.../digital_twin_colibri_g1_env_cfg.py`

```python
@configclass
class DigitalTwinColibriG1EnvCfg(G1FlatEnvCfg):
    """G1 humanoid robot for velocity tracking in Colibri digital twin environment."""

    def __post_init__(self):
        super().__post_init__()

        # Custom USD environment
        self.scene.terrain = TerrainImporterCfg(
            prim_path="/World/ground",
            terrain_type="usd",
            usd_path=str(ASSETS_DIR / "ColibriLab" / "ColibriLab.usd"),
        )

        # Scene settings
        self.scene.num_envs = 512  # Parallel environments
        self.scene.env_spacing = 0.2
        self.episode_length_s = 20.0  # Episode duration

        # Spawn height for raised floor
        self.events.reset_base.params["pose_range"]["z"] = (1.2, 1.2)
```

**Key Design Decisions:**
- Inherits from `G1FlatEnvCfg` for proven G1 locomotion rewards
- Custom USD terrain loads ColibriLab environment
- 512 parallel environments for efficient training
- 20-second episodes for goal navigation time

### 2.3 Custom Command Generators (Developed from Scratch)

**File:** `source/.../mdp/commands.py`

#### 2.3.1 SimpleGoalCommand (~320 lines)

A goal position command generator that samples 2D targets around the robot.

```python
class SimpleGoalCommand(CommandTerm):
    """Simple goal position command generator for navigation.

    Features:
    - Samples random 2D goals at 2-4m distance
    - Forward-biased angle sampling (80% in front)
    - Smooth transitions when goals are reached
    - Color-coded visualization (green=far, blue=reached)
    - Metrics tracking (distance_to_goal, goal_reached)
    """
```

**Key Implementation Details:**

1. **Goal Sampling Strategy:**
   ```python
   # Initial spawn: 80% in tight forward cone (30)
   is_tight_forward = torch.rand(n, device=self.device) < 0.8
   angle_offset = torch.where(
       is_tight_forward,
       torch.rand(n) * (math.pi / 3) - math.pi / 6,  # 30
       torch.rand(n) * math.pi - math.pi / 2,  # 90
   )
   ```

2. **Smooth Goal Transitions:**
   ```python
   # Linear interpolation over transition_time
   t = (elapsed / self.cfg.goal_transition_time).clamp(0.0, 1.0)
   self.goal_pos_w[transitioning_ids] = (
       self.start_goal_pos_w + t.unsqueeze(1) * (self.target_goal_pos_w - self.start_goal_pos_w)
   )
   ```

3. **Base Frame Transformation:**
   ```python
   # Transform world goal to robot's base frame
   goal_vec_w = self.goal_pos_w[:, :2] - self.robot.data.root_pos_w[:, :2]
   heading = self.robot.data.heading_w
   cos_h, sin_h = torch.cos(-heading), torch.sin(-heading)
   self.goal_pos_b[:, 0] = cos_h * goal_vec_w[:, 0] - sin_h * goal_vec_w[:, 1]
   self.goal_pos_b[:, 1] = sin_h * goal_vec_w[:, 0] + cos_h * goal_vec_w[:, 1]
   ```

#### 2.3.2 GoalDirectedVelocityCommand (~163 lines)

A velocity command generator that always points toward the goal.

```python
class GoalDirectedVelocityCommand(UniformVelocityCommand):
    """Velocity commands that ALWAYS track the goal position.

    Features:
    - Velocity direction: Always toward goal
    - Velocity magnitude: Distance-dependent (fast far, slow close)
    - Heading-aware scaling: Requires facing goal before fast movement
    - Never commands backwards velocity (prevents shuffling)
    """
```

**Critical Design Choice - No Backwards Velocity:**
```python
# NEVER allow negative forward velocity commands
# If goal is behind, robot must turn first
self.vel_command_b[env_ids, 0] = torch.clamp(cmd_vx, min=0.0)
```

**Heading-Aware Velocity Scaling:**
```python
# Alignment factor: 1.0 facing goal, 0.0 facing backwards
alignment = torch.cos(heading_error)
alignment_factor = (alignment + 1.0) / 2.0

# Scale velocity: 40% minimum when misaligned
heading_scale = 0.4 + 0.6 * alignment_factor
```

### 2.4 Custom Reward Functions (Developed from Scratch)

**File:** `source/.../mdp/rewards.py`

#### 2.4.1 Goal Distance Reward

```python
def goal_distance_exp(env, command_name: str, std: float) -> torch.Tensor:
    """Exponential reward for approaching the goal position.

    Formula: exp(-distance_squared / std^2)
    - Returns 1.0 when at goal
    - Decays exponentially with distance

    Recommended: std=5.0, weight=0.05 for conservative guidance
    """
    goal_pos_b = env.command_manager.get_command(command_name)
    distance_squared = torch.sum(torch.square(goal_pos_b[:, :2]), dim=1)
    return torch.exp(-distance_squared / (std ** 2))
```

#### 2.4.2 Backwards Velocity Penalty

```python
def backwards_velocity_penalty(env, threshold: float = -0.1, asset_cfg) -> torch.Tensor:
    """Penalize backwards velocity in robot's body frame.

    Discourages shuffling to reach goals behind the robot.
    Only penalizes when moving backwards faster than threshold.
    """
    forward_vel = asset.data.root_lin_vel_b[:, 0]
    backwards_vel = torch.clamp(-forward_vel - (-threshold), min=0.0)
    return torch.square(backwards_vel)  # L2 penalty
```

#### 2.4.3 Heading Alignment Reward

```python
def heading_alignment_reward(env, command_name: str, std: float, asset_cfg) -> torch.Tensor:
    """Reward robot for facing toward the goal position.

    Encourages turning to align heading with goal direction
    before or while moving.
    """
    goal_pos_b = env.command_manager.get_command(command_name)
    goal_angle_base = torch.atan2(goal_pos_b[:, 1], goal_pos_b[:, 0])
    heading_error = torch.abs(goal_angle_base)
    return torch.exp(-torch.square(heading_error) / (std ** 2))
```

### 2.5 Reward Structure

**Configuration in `digital_twin_colibri_g1_env_cfg.py`:**

```python
# GOAL-DIRECTED APPROACH
# Velocity commands ALWAYS point toward goal (no randomness)
# Velocity magnitude smoothly adjusts based on distance
#
# Reward Balancing:
#   Velocity tracking: weight 1.0 + 2.0 = 3.0 (learn to follow commands)
#   Goal tracking:     weight 0.3 + 0.2 = 0.5 (bonus for proximity)
#   Ratio:             6:1 (velocity tracking dominant)

# Coarse goal tracking (wide gradient)
self.rewards.goal_tracking = RewTerm(
    func=mdp.goal_distance_exp,
    weight=0.3,
    params={"command_name": "goal_position", "std": 5.0},
)

# Fine goal tracking (tight gradient)
self.rewards.goal_tracking_fine = RewTerm(
    func=mdp.goal_distance_exp,
    weight=0.2,
    params={"command_name": "goal_position", "std": 3.0},
)

# Backwards velocity penalty
self.rewards.backwards_penalty = RewTerm(
    func=mdp.backwards_velocity_penalty,
    weight=-0.5,
    params={"threshold": -0.05},
)

# Heading alignment
self.rewards.heading_alignment = RewTerm(
    func=mdp.heading_alignment_reward,
    weight=0.3,
    params={"command_name": "goal_position", "std": 0.5},
)
```

### 2.6 Observation Space

**Base Task Observations (~125 dimensions):**

| Component | Dimensions | Source |
|-----------|------------|--------|
| Base linear velocity | 3 | Inherited from G1 |
| Base angular velocity | 3 | Inherited from G1 |
| Projected gravity | 3 | Inherited from G1 |
| Velocity commands | 3 | Inherited from G1 |
| Joint positions | 29 | Inherited from G1 |
| Joint velocities | 29 | Inherited from G1 |
| Previous actions | 29 | Inherited from G1 |
| Height scan (optional) | Variable | Inherited from G1 |
| **Goal position (custom)** | **2** | **Custom addition** |

**Custom Goal Observation:**
```python
# Add goal position (2D: x, y in base frame) to policy observations
self.observations.policy.goal_position = ObsTerm(
    func=mdp.generated_commands,
    params={"command_name": "goal_position"},
)
```

### 2.7 Action Space

- **29 DOF** joint position targets
- Normalized to [-1, 1] range
- 50 Hz control frequency (configurable decimation)

### 2.8 Play/Evaluation Configuration

**File:** `DigitalTwinColibriG1EnvCfg_PLAY`

```python
@configclass
class DigitalTwinColibriG1EnvCfg_PLAY(DigitalTwinColibriG1EnvCfg):
    """Play/evaluation configuration for visualization and testing."""

    def __post_init__(self):
        super().__post_init__()

        self.scene.num_envs = 10  # Fewer for visualization
        self.scene.env_spacing = 5  # More spacing
        self.episode_length_s = 30.0  # Longer episodes

        # Disable randomization
        self.observations.policy.enable_corruption = False

        # Remove disturbances
        self.events.base_external_force_torque = None
        self.events.push_robot = None

        # Disable standing (no frozen robots)
        self.commands.base_velocity.rel_standing_envs = 0.0
```

### 2.9 Training Commands

```bash
# Basic training
python scripts/rsl_rl/train.py --task=Isaac-Colibri-G1-v0 --headless

# Full training with video
python scripts/rsl_rl/train.py --task=Isaac-Colibri-G1-v0 \
    --num_envs 512 --headless --video --max_iterations 1000

# Evaluation
python scripts/rsl_rl/play.py --task=Isaac-Colibri-G1-Play-v0 \
    --num_envs 10 --real-time

# Resume training
python scripts/rsl_rl/train.py --task=Isaac-Colibri-G1-v0 \
    --resume --load_run <run_folder>
```

### 2.10 Key Innovations

1. **Goal-Directed Velocity Commands**: Instead of random velocity sampling, commands always point toward goals with smooth speed adjustments.

2. **Forward-Biased Goal Sampling**: 80% of initial goals spawn in front of the robot, reducing initial confusion.

3. **No Backwards Command Clamping**: Prevents velocity tracking reward from encouraging backwards walking.

4. **Dual Goal Rewards**: Coarse (std=5.0) for long-range guidance, fine (std=3.0) for precision.

5. **Heading Alignment**: Encourages robot to face goals before moving fast.

6. **Smooth Goal Transitions**: Linear interpolation prevents jarring goal jumps when reached.
