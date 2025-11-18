# Colibri G1 Point-to-Point Navigation - Project Overview

## Project Goal

Train a Unitree G1 humanoid robot to perform point-to-point navigation in the Colibri laboratory environment using reinforcement learning, while maintaining high-quality bipedal locomotion.

## Key Challenges

1. **Dual Learning Objective**: Robot must learn both:
   - High-quality bipedal walking (complex, requires smooth gaits)
   - Goal-directed navigation (requires spatial awareness and planning)

2. **Reward Balance**: Navigation rewards must guide the robot toward goals WITHOUT interfering with locomotion learning

3. **Exploration vs Exploitation**: Need randomness for locomotion diversity, but bias toward goals for navigation

## Current Approach

**Strategy**: Incremental development with conservative changes
- Start with proven G1 velocity tracking configuration
- Add goal-awareness layer by layer
- Test after each change to prevent breaking locomotion
- Use git branches for easy rollback

## Environment Details

**Robot**: Unitree G1 humanoid (29 DOF)
**Environment**: Colibri Lab USD scene (11m x 11m square)
**Framework**: Isaac Lab (NVIDIA Omniverse)
**RL Library**: RSL-RL (Proximal Policy Optimization)

**Training Setup**:
- 256-512 parallel environments
- 20-second episodes
- Goal distance: 3-6 meters from robot
- Goal threshold: 0.3m radius (tight requirement)
- Goals resample every 10-15 seconds

## Success Metrics

**Locomotion Quality**:
- Episode length > 60 steps (robot stays upright)
- Smooth gaits (low action rate, joint acceleration)
- Feet air time > 0.4s (proper bipedal walking)

**Navigation Performance**:
- Goal reached rate > 20% within episode
- Average distance to goal decreasing over training
- Mean reward improving

**Overall**:
- Training stable (no divergence)
- Policy generalizes to new goal positions
- Natural-looking movement

## Results So Far

### Phase 1: Goal Tracking Infrastructure
- ✅ Goals visualize correctly (large green spheres)
- ✅ Goal position in observation space (2D relative position)
- ✅ Metrics tracked: distance_to_goal, goal_reached
- **Baseline established**

### Phase 2: Goal Distance Reward
- ✅ Conservative exponential reward (std=5.0, weight=0.05)
- ✅ Mean reward improved: -6.42 → -5.29 (18% improvement)
- ✅ Episode length increased: 46 → 63 steps (36% longer upright)
- ✅ Training stable
- **Gentle guidance working!**

### Phase 3: Velocity Biasing (CURRENT - UNDER REVIEW)
- ⚠️ Velocity commands biased 20% toward goals
- ⚠️ Robot walking became awkward/slower
- ⚠️ Locomotion quality degraded
- **Insight**: Forcing velocity distribution breaks learned locomotion patterns
- **Decision**: Revert and try alternative approach

## Next Steps

See [PATH_A_VS_PATH_B.md](PATH_A_VS_PATH_B.md) for detailed implementation plans.

**Immediate**: Path A - Let policy discover navigation naturally
**Future**: Path B - Hierarchical navigation (if Path A insufficient)
