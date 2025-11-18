# 🔄 Reboot Required Before Docker Build

## Issue
Kernel/module mismatch preventing Docker from working:
- **Running kernel**: 6.17.7-arch1-1 (old)
- **Installed modules**: 6.17.8-arch1-1 (new)
- **Missing module**: veth (required for Docker networking)

## Solution
```bash
sudo reboot
```

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
  1. Isaac Sim 5.1.0 base (~15GB)
  2. ROS2 Humble installation (~5 min)
  3. Isaac Lab installation (~15-20 min)
  4. Colibri extension installation (~2 min)
  5. Final configuration (~1 min)

## Troubleshooting
If build still fails after reboot, see: `docker/NETWORK_TROUBLESHOOTING.md`

---

**Note**: This file can be deleted after successful Docker build.
