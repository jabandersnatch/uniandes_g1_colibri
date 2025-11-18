# 🔄 Docker Setup Issues and Fixes

## Issue 1: Kernel/Module Mismatch (Requires Reboot)
Kernel/module mismatch preventing Docker from working:
- **Running kernel**: 6.17.7-arch1-1 (old)
- **Installed modules**: 6.17.8-arch1-1 (new)
- **Missing module**: veth (required for Docker networking)

**Solution**: Reboot system
```bash
sudo reboot
```

## Issue 2: NumPy Incompatibility (FIXED - 2025-11-18) ✅
NumPy 2.x incompatible with Isaac Sim 4.5.0's bundled scipy, extension import failures.

**Solution Applied**:
- Pin NumPy to <2.0 before Isaac Lab installation
- Configure PYTHONPATH to include extension
- Use conda environment for all package installations

**Details**: See `docker/FIXES_APPLIED.md`

## After Reboot - Build Docker Image

```bash
cd /home/jamendez/Documents/uniandes/MISIS/thesis/uniandes_g1_colibri/digital_twin_colibri_g1

# Verify kernel is updated
uname -r  # Should show 6.17.8-arch1-1

# Load veth module
sudo modprobe veth

# Verify it loaded
lsmod | grep veth

# Build Docker image
docker-compose -f docker/docker-compose.yaml build

# Or with progress output
docker-compose -f docker/docker-compose.yaml build --progress=plain
```

## Expected Build Time
- Full build (no cache): ~30-60 minutes
- Stages:
  1. Isaac Sim 4.5.0 base (~15GB, Ubuntu 22.04)
  2. ROS2 Humble installation (~5 min)
  3. Isaac Lab installation (~15-20 min)
  4. Colibri extension installation (~2 min)
  5. Final configuration (~1 min)

## Troubleshooting
If build still fails after reboot, see: `docker/NETWORK_TROUBLESHOOTING.md`

---

**Note**: This file can be deleted after successful Docker build.
