# Colibri G1 Navigation - Documentation

Welcome to the Colibri G1 Point-to-Point Navigation documentation!

## Quick Start

**New to the project?** Start here:
1. Read [OVERVIEW.md](OVERVIEW.md) - Project goals and status
2. Read [PHASES.md](PHASES.md) - What we've built so far
3. Read [PATH_A_VS_PATH_B.md](PATH_A_VS_PATH_B.md) - Future directions

**Looking for something specific?**
- [REFERENCES.md](REFERENCES.md) - File locations and Isaac Lab references
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues (coming soon)

---

## Document Index

### [OVERVIEW.md](OVERVIEW.md)
High-level project summary:
- Project goals and challenges
- Current approach and strategy
- Environment details
- Success metrics
- Results summary

### [PHASES.md](PHASES.md)
Detailed implementation breakdown:
- Phase 1: Goal tracking infrastructure ✅
- Phase 2: Goal distance rewards ✅
- Phase 3: Velocity biasing ⚠️ (problematic)
- Phase 4: Path A - Natural discovery 🔄 (in progress)
- Phase 5: Path B - Hierarchical 📋 (planned)
- Testing strategy
- Git workflow

### [PATH_A_VS_PATH_B.md](PATH_A_VS_PATH_B.md)
Comparison of two navigation approaches:
- Path A: End-to-end learning (simple, one policy)
- Path B: Hierarchical (complex, two policies)
- Detailed pros/cons, when to use each
- Implementation checklists

### [REFERENCES.md](REFERENCES.md)
File locations and resources:
- Project file structure
- Key files explained
- Isaac Lab reference files
- Training scripts
- Useful commands
- Documentation links

---

## Current Status

**Phase**: Implementing Path A (Natural Goal Discovery)

**Latest Changes**:
- Removed velocity biasing (was causing awkward locomotion)
- Increased goal rewards (0.05 → 0.3 + 0.2)
- Added smooth goal transitions (1.5s interpolation)

**Next Steps**:
1. Test with random agent (visual verification)
2. Short training run (50-200 iterations)
3. Full training (1000-3000 iterations)
4. Evaluate and tune

---

## Training Quick Reference

```bash
# Short test (quick feedback)
python scripts/rsl_rl/train.py --task=Isaac-Colibri-G1-v0 --num_envs 256 --headless --max_iterations 200

# Full training
python scripts/rsl_rl/train.py --task=Isaac-Colibri-G1-v0 --num_envs 512 --headless --max_iterations 3000 --logger tensorboard

# Evaluate trained policy
python scripts/rsl_rl/play.py --task=Isaac-Colibri-G1-Play-v0 --checkpoint logs/.../model_1500.pt --num_envs 4
```

---

## Key Metrics to Monitor

**Locomotion Quality**:
- Episode length (target: >60 steps)
- `feet_air_time` reward (target: >0.0004)
- `action_rate_l2` penalty (lower is smoother)

**Navigation Performance**:
- `goal_tracking` reward (target: 0.015-0.030)
- `distance_to_goal` metric (should decrease)
- `goal_reached` rate (target: >0.20)

**Overall**:
- Mean reward increasing (stable growth)
- No NaN values
- Training completes without crashes

---

## Git Branches

```
main                                  ← Stable releases
├── feature/goal-tracking-infrastructure  ← Phase 1 ✅
├── feature/goal-distance-reward          ← Phase 2 ✅
├── feature/velocity-goal-bias            ← Phase 3 ⚠️ (reverted)
└── feature/path-a-natural-navigation     ← Phase 4 🔄 (current)
```

---

## Contributing

When making changes:
1. Create a new feature branch
2. Make small, testable commits
3. Test after each change
4. Document significant decisions
5. Update this documentation if needed

---

## Questions?

**Isaac Lab Issues**: https://github.com/isaac-sim/IsaacLab/issues
**Project Location**: `~/Documents/uniandes/MISIS/thesis/uniandes_g1_colibri/digital_twin_colibri_g1/`

---

**Last Updated**: 2025-11-10
**Status**: Active Development
**Phase**: Path A Implementation
