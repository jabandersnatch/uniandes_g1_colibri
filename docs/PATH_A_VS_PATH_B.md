# Path A vs Path B: Navigation Implementation Strategies

## The Core Question

**How do we combine locomotion and navigation learning?**

This is a fundamental challenge in legged robot navigation. Both require the policy to:
- Control 29 joints precisely
- Maintain balance and stability
- Track desired behaviors

But they have different objectives:
- **Locomotion**: Match velocity commands, walk smoothly
- **Navigation**: Reach goal positions efficiently

---

## Path A: End-to-End Learning (Natural Discovery)

### Concept

Train a SINGLE policy that learns both locomotion and navigation simultaneously by discovering the relationship between velocity commands and goal reaching.

### How It Works

**Reward Structure**:
```
Total Reward = Locomotion Rewards + Navigation Rewards

Locomotion (75-80%):
  + track_lin_vel_xy_exp (weight 1.0)
  + track_ang_vel_z_exp  (weight 2.0)
  + feet_air_time        (weight 0.75)
  - action_rate_l2       (weight 0.005)
  - dof_torques_l2       (weight 1.5e-7)
  ... (all standard G1 rewards)

Navigation (20-25%):
  + goal_tracking_coarse (weight 0.3, std=5.0)
  + goal_tracking_fine   (weight 0.2, std=3.0)
```

**Learning Process**:

1. **Random Exploration**: Robot gets random velocity commands
2. **Correlation Discovery**: Policy notices:
   - Moving forward when goal is ahead → high reward
   - Moving sideways when goal is lateral → high reward
   - Moving away from goal → lower reward
3. **Policy Adjustment**: Gradually biases action selection toward goal-aligned velocities
4. **Emergent Behavior**: Robot navigates naturally without forced commands

**Key Insight**: We don't tell the robot HOW to navigate, we reward it WHEN it does!

### Implementation

**File Changes**:
```python
# In digital_twin_colibri_g1_env_cfg.py

# 1. REMOVE velocity biasing (delete lines 124-149)
# 2. Keep standard UniformVelocityCommand
# 3. INCREASE goal rewards:

self.rewards.goal_tracking = RewTerm(
    func=mdp.goal_distance_exp,
    weight=0.3,  # Was 0.05 - now 6x stronger!
    params={"command_name": "goal_position", "std": 5.0},
)

self.rewards.goal_tracking_fine = RewTerm(
    func=mdp.goal_distance_exp,
    weight=0.2,  # New - for precision
    params={"command_name": "goal_position", "std": 3.0},
)
```

**Smooth Goal Transitions** (reduces disorientation):
```python
# In SimpleGoalCommand
goal_transition_time: float = 1.5  # seconds
# Interpolate from old_goal to new_goal over transition_time
```

### Advantages ✅

1. **Simple**: One policy, one training run
2. **Robust**: Explores many navigation strategies
3. **Preserves Locomotion**: Random velocity distribution maintained
4. **Discovers Emergence**: May find creative navigation strategies
5. **Easy to Debug**: Single policy to monitor
6. **Fast to Implement**: Modify existing config

### Disadvantages ❌

1. **Slower Learning**: Must discover correlation through exploration
2. **Requires Careful Tuning**: Reward balance is critical
3. **No Guarantees**: Might not converge to navigation
4. **Coupled Learning**: Can't improve locomotion separately

### When to Use

- ✅ Quick prototyping and iteration
- ✅ Research exploration
- ✅ Don't have pre-trained locomotion policy
- ✅ Want simple, maintainable system
- ✅ Time-constrained development

### Expected Training Curve

```
Iterations 0-500:    Learning to stand/walk (existing)
Iterations 500-1500:  Discovering goal-velocity correlation
Iterations 1500-3000: Refining navigation strategies
Iterations 3000+:     Polishing, reaching 50-70% goal success
```

---

## Path B: Hierarchical Navigation (Frozen Locomotion)

### Concept

Train TWO separate policies:
1. **Low-level**: Locomotion policy (velocity tracking)
2. **High-level**: Navigation policy (outputs velocity commands)

Low-level policy is trained first, then FROZEN. High-level policy learns on top.

### How It Works

**Architecture**:
```
           ┌─────────────────────────────┐
           │  Navigation Policy (learns) │
           │  Input: [goal, state]       │
           │  Output: [vx, vy, vyaw]     │
           └──────────┬──────────────────┘
                      │ velocity command
           ┌──────────▼──────────────────┐
           │ Locomotion Policy (frozen)  │
           │ Input: [vel_cmd, joints]    │
           │ Output: [joint_targets]     │
           └─────────────────────────────┘
```

**Two-Stage Training**:

**Stage 1: Train Locomotion** (3000-5000 iterations)
```bash
# Use pure velocity tracking (NO navigation)
python scripts/rsl_rl/train.py \
    --task=Isaac-Colibri-G1-v0-Locomotion \
    --max_iterations 5000
# Save: locomotion_policy.pt
```

**Stage 2: Train Navigation** (1000-2000 iterations)
```bash
# Use hierarchical config with frozen locomotion
python scripts/rsl_rl/train.py \
    --task=Isaac-Colibri-G1-v0-Navigation \
    --max_iterations 2000
# Loads: locomotion_policy.pt (frozen)
# Saves: navigation_policy.pt
```

### Implementation

**New Environment Config** (`navigation_env_cfg.py`):
```python
from isaaclab_tasks.manager_based.navigation.mdp import PreTrainedPolicyActionCfg

@configclass
class ActionsCfg:
    """High-level actions: 3D velocity commands"""

    pre_trained_policy = PreTrainedPolicyActionCfg(
        asset_name="robot",
        policy_path="logs/locomotion_policy.pt",  # Frozen!
        low_level_decimation=4,
        low_level_actions=LOW_LEVEL_CFG.actions.joint_pos,
        low_level_observations=LOW_LEVEL_CFG.observations.policy,
    )

@configclass
class ObservationsCfg:
    """Minimal observations for navigation"""

    @configclass
    class PolicyCfg(ObsGroup):
        base_lin_vel = ObsTerm(func=mdp.base_lin_vel)
        projected_gravity = ObsTerm(func=mdp.projected_gravity)
        pose_command = ObsTerm(func=mdp.generated_commands,
                              params={"command_name": "goal_position"})

    policy: PolicyCfg = PolicyCfg()

@configclass
class RewardsCfg:
    """Only navigation rewards!"""

    termination_penalty = RewTerm(func=mdp.is_terminated, weight=-400.0)
    position_tracking = RewTerm(
        func=mdp.position_command_error_tanh,
        weight=0.5,
        params={"std": 2.0, "command_name": "goal_position"},
    )
    position_tracking_fine = RewTerm(
        func=mdp.position_command_error_tanh,
        weight=0.5,
        params={"std": 0.2, "command_name": "goal_position"},
    )
```

**Key Difference**: Action space is now 3D velocity commands, not 29D joint positions!

### Advantages ✅

1. **Best Locomotion Quality**: Dedicated policy trained extensively
2. **Faster Navigation Learning**: Simpler 3D action space
3. **Modular**: Can improve locomotion independently
4. **Reusable**: Use same locomotion for multiple tasks
5. **Follows Best Practices**: How IsaacLab does it (AnymalC)
6. **Guaranteed Locomotion**: Won't degrade during navigation training

### Disadvantages ❌

1. **Complex Setup**: Two configs, two training runs
2. **Requires Good Locomotion First**: Need 5000 iterations of quality training
3. **Two Checkpoints**: More files to manage
4. **Less Flexible**: Can't adjust locomotion during navigation training
5. **Action Space Mismatch**: High-level outputs velocities, not joint targets

### When to Use

- ✅ Need best possible locomotion quality
- ✅ Have time for thorough training
- ✅ Want production-ready system
- ✅ Plan to reuse locomotion for other tasks
- ✅ Path A didn't achieve desired performance

### Expected Training Curve

```
Stage 1 (Locomotion):
Iterations 0-2000:   Learning to walk
Iterations 2000-5000: Refining gait quality
Save checkpoint

Stage 2 (Navigation):
Iterations 0-500:    Learning velocity-goal mapping
Iterations 500-1500: Efficient navigation
Iterations 1500+:    Polishing, reaching 80%+ goal success
```

---

## Side-by-Side Comparison

| Metric | Path A | Path B |
|--------|--------|--------|
| **Setup Complexity** | Low | High |
| **Total Training Time** | 3000-5000 iters | 5000 + 2000 = 7000 iters |
| **Wall-Clock Time** | Faster (one run) | Slower (two runs) |
| **Locomotion Quality** | Good (if balanced) | Excellent (dedicated) |
| **Navigation Performance** | 50-70% goal success | 70-90% goal success |
| **Action Space** | 29D (joint positions) | 3D (velocity commands) |
| **Observation Space** | Full (all sensors) | Minimal (navigation only) |
| **Debugging Ease** | Moderate | Easier (separate concerns) |
| **Maintainability** | Easier (one policy) | Moderate (two policies) |
| **Flexibility** | High (end-to-end) | Low (frozen locomotion) |
| **Risk of Failure** | Medium (balance issues) | Low (proven approach) |

---

## Recommendation: Try Both!

### Week 1-2: Path A
- Quick to implement
- Fast feedback
- Learn about reward balance
- Might be sufficient!

### Week 3-4: Path B (if needed)
- If Path A locomotion quality insufficient
- If navigation performance plateaus
- As production solution

### Hybrid Approach?

You could even:
1. Train locomotion with Path A (gets both working)
2. Extract locomotion policy
3. Use it for Path B (guaranteed quality)

---

## Implementation Checklist

### Path A

- [ ] Remove velocity biasing code
- [ ] Increase goal reward weights
- [ ] Add smooth goal transitions
- [ ] Test with random agent (visual check)
- [ ] Train 50 iterations (sanity check)
- [ ] Train 500 iterations (learning check)
- [ ] Train 3000 iterations (full training)
- [ ] Evaluate with play script
- [ ] Tune if needed

### Path B

- [ ] Create locomotion-only config
- [ ] Train locomotion policy (5000 iters)
- [ ] Save checkpoint
- [ ] Create hierarchical navigation config
- [ ] Implement PreTrainedPolicyAction
- [ ] Test setup (no crashes)
- [ ] Train navigation (2000 iters)
- [ ] Evaluate combined system
- [ ] Compare with Path A

---

## References

**IsaacLab Examples**:
- AnymalC Navigation: `isaaclab_tasks/manager_based/navigation/config/anymal_c/`
- G1 Locomotion: `isaaclab_tasks/manager_based/locomotion/velocity/config/g1/`

**Key Concepts**:
- Hierarchical RL: [Paper Reference needed]
- Locomotion-Navigation Separation: Standard in legged robotics
- Reward Shaping: [Ng et al., 1999]
