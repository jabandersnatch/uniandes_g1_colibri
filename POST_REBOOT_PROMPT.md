# Post-Reboot Prompt for Claude Code

Copy and paste this prompt when you start a new Claude Code session after rebooting:

---

## Prompt:

```
I just rebooted my system to fix the Docker kernel/module mismatch (veth module issue).
I'm ready to continue with Phase 6: Sim2Sim ROS2 Integration for the Colibri G1 digital twin.

**Context:**
- Branch: feature/sim2sim-ros2
- Status: Implementation complete (5 commits), ready to build Docker image
- Blocker resolved: System rebooted, kernel 6.17.8 should now have veth module

**What I need help with:**
1. Verify kernel and veth module are working
2. Build the Docker image (Isaac Sim 5.1.0 + ROS2 Humble)
3. Test the container and ROS2 topics
4. Validate the sim2sim deployment

**Key files to review:**
@NEXT_STEPS.md - Complete post-reboot guide
@docker/REBOOT_REQUIRED.md - Quick reference
@CLAUDE.md - Project overview with Phase 6 section
@README_ROS2.md - ROS2 integration quick start

Please start by verifying the kernel version and veth module, then guide me through
building and testing the Docker image.
```

---

## Alternative Minimal Prompt:

```
Just rebooted. Ready for Phase 6 Docker build.

@NEXT_STEPS.md
@docker/REBOOT_REQUIRED.md

Start with Step 1: verify kernel and veth module.
```

---

## What Claude Will Do:

1. Ask you to check kernel version: `uname -r` (should be 6.17.8-arch1-1)
2. Load veth module: `sudo modprobe veth`
3. Verify it loaded: `lsmod | grep veth`
4. Build Docker image: `docker-compose -f docker/docker-compose.yaml build`
5. Test the container startup
6. Verify ROS2 topics are publishing
7. Guide you through RViz2 visualization

---

## Expected Timeline:

- Kernel verification: 1 minute
- Docker build: 30-60 minutes (first time)
- Container testing: 5 minutes
- ROS2 topic validation: 5 minutes
- RViz2 visualization: 5 minutes

**Total**: ~45-75 minutes

---

## Files Updated Since Last Session:

All documentation is now current with Phase 6 completion:

✅ **CLAUDE.md** - Added comprehensive Phase 6 section (170 lines)
  - Docker deployment guide
  - ROS2 topics table
  - Troubleshooting section
  - Dependency management explanation

✅ **docs/PHASES.md** - Updated Phase 6 status and git workflow
  - Marked implementation as complete
  - Updated branch status (feature/sim2sim-ros2)
  - Listed completed vs pending testing items

✅ **README_ROS2.md** - Added Docker troubleshooting and image details
  - Reboot/veth module note
  - Docker image specifications

✅ **NEXT_STEPS.md** - Complete post-reboot testing guide (created)

✅ **docker/NETWORK_TROUBLESHOOTING.md** - Comprehensive troubleshooting (created)

✅ **docker/REBOOT_REQUIRED.md** - Quick reference (created)

---

## Current Git Status:

```
Branch: feature/sim2sim-ros2 (5 commits ahead of main)

Commits:
1. feat: Add Phase 6 sim2sim ROS2 scaffolding
2. feat: Implement Phase 6.1 ROS2 bridge with policy integration
3. feat: Complete Docker configuration (Isaac Sim 5.1.0)
4. docs: Add dependency management system
5. fix: Resolve Docker network bridge error

Status: Ready to build and test
```

---

## Quick Command Reference:

After reboot, run these commands in order:

```bash
# 1. Verify kernel
uname -r

# 2. Load veth module
sudo modprobe veth

# 3. Verify veth loaded
lsmod | grep veth

# 4. Navigate to project
cd ~/Documents/uniandes/MISIS/thesis/uniandes_g1_colibri/digital_twin_colibri_g1

# 5. Build Docker image
docker-compose -f docker/docker-compose.yaml build

# 6. Test container
xhost +local:docker
docker-compose -f docker/docker-compose.yaml run --rm isaac_sim_ros2 bash

# 7. Run sim2sim
docker-compose -f docker/docker-compose.yaml up isaac_sim_ros2
```

---

**Last Updated**: 2025-11-17 19:00 (before reboot)
**Next Action**: Reboot → Use prompt above → Build Docker → Test
